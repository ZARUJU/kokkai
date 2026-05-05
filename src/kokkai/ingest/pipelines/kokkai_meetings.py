import logging
import os
from typing import Any

from playwright.sync_api import sync_playwright

from kokkai.db.engine import session_scope
from kokkai.db.schema import create_all
from kokkai.ingest.cli_sessions import ingest_sessions_explicit
from kokkai.ingest.parsers import kokkai_meetings as parser
from kokkai.ingest.pipeline import IngestRunContext
from kokkai.ingest.pipeline import PipelineResult
from kokkai.ingest.sources import kokkai_api as source
from kokkai.repositories import diet_sessions
from kokkai.repositories import meeting_records as meeting_repository


DEFAULT_SESSION_FALLBACK_FROM = 221
DEFAULT_SESSION_FALLBACK_TO = 221

_LOG = logging.getLogger(__name__)


def _stop_playwright(*, playwright, ndl_browser) -> None:
    if ndl_browser is not None:
        try:
            ndl_browser.close()
        except Exception:  # noqa: BLE001
            pass
    if playwright is not None:
        try:
            playwright.stop()
        except Exception:  # noqa: BLE001
            pass


def _resolve_session_range(context: IngestRunContext) -> tuple[int, int, str]:
    explicit = ingest_sessions_explicit(context, os.getenv("KOKKAI_MEETING_SESSIONS"))
    if explicit is not None:
        return min(explicit), max(explicit), "CLI または環境変数 KOKKAI_MEETING_SESSIONS"
    with session_scope() as session:
        numbers = diet_sessions.latest_session_numbers(session, 2)
    if not numbers:
        return (
            DEFAULT_SESSION_FALLBACK_FROM,
            DEFAULT_SESSION_FALLBACK_TO,
            "フォールバック（会期一覧が DB に無い）",
        )
    return (
        min(numbers),
        max(numbers),
        "会期一覧 DB の新しい順から最大2件",
    )


def _ingest_limit() -> int | None:
    raw = os.getenv("KOKKAI_MEETING_INGEST_LIMIT")
    if raw is None or raw == "":
        return None
    return max(0, int(raw))


def _reingest_meetings() -> bool:
    raw = os.getenv("KOKKAI_MEETING_REINGEST")
    if raw is None or raw.strip() == "":
        return False
    return raw.strip().lower() in ("1", "true", "yes", "on")


def run(context: IngestRunContext) -> PipelineResult:
    create_all()
    total = 0
    skipped_existing = 0
    skipped_no_record = 0
    skipped_parse_error = 0
    limit = _ingest_limit()
    reingest = _reingest_meetings()

    session_from, session_to, range_note = _resolve_session_range(context)
    _LOG.info(
        "国会会議録: 回次 sessionFrom=%s sessionTo=%s（%s） reingest=%s limit=%s",
        session_from,
        session_to,
        range_note,
        reingest,
        limit if limit is not None else "なし",
    )
    _LOG.info("国会会議録: meeting_list から issue_id を列挙して取得します")

    playwright = None
    ndl_browser = None
    ndl_page = None
    min_ids_cache: dict[str, list[str]] = {}
    session_bills_cache: dict[int, list[Any]] = {}
    try:
        playwright = sync_playwright().start()
        ndl_browser = playwright.chromium.launch(headless=True)
        ndl_page = ndl_browser.new_page()
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("国会会議録: Playwright を起動できません（議案紐づけは行いません）: %s", exc)
        _stop_playwright(playwright=playwright, ndl_browser=ndl_browser)
        playwright = None
        ndl_browser = None
        ndl_page = None

    if ndl_page is not None:
        try:
            with session_scope() as session:
                n_fetch, n_rows = meeting_repository.prefetch_ndl_min_ids_for_session_range(
                    session,
                    session_from,
                    session_to,
                    ndl_page,
                    min_ids_cache,
                    session_bills_cache,
                )
            _LOG.info(
                "国会会議録: NDL min_id プリフェッチ完了（走査した議案行=%s 新規 billId 取得=%s）",
                n_rows,
                n_fetch,
            )
        except Exception as exc:  # noqa: BLE001
            _LOG.warning("国会会議録: NDL プリフェッチに失敗（会議単位でフォールバック取得）: %s", exc)

    stopped_for_limit = False
    try:
        for issue_id in source.iter_meeting_issue_ids(session_from, session_to):
            if limit is not None and total >= limit:
                stopped_for_limit = True
                break

            if not reingest:
                with session_scope() as session:
                    if meeting_repository.meeting_issue_exists(session, issue_id):
                        skipped_existing += 1
                        _LOG.debug("国会会議録: issue_id=%s は DB に既存のためスキップ", issue_id)
                        continue

            _LOG.debug("国会会議録: issue_id=%s を meeting API で取得", issue_id)
            payload = source.fetch_meeting_page({"issueID": issue_id, "maximumRecords": 1, "recordPacking": "json"})
            source.ensure_meeting_response(payload)
            records = payload.get("meetingRecord") or []
            if not isinstance(records, list) or not records:
                skipped_no_record += 1
                _LOG.debug("国会会議録: issue_id=%s は meeting 応答にレコード無し", issue_id)
                continue
            raw = records[0]
            if not isinstance(raw, dict):
                skipped_no_record += 1
                continue

            try:
                record, speeches, topic_labels = parser.parse_meeting_bundle(raw)
            except ValueError as exc:
                skipped_parse_error += 1
                _LOG.warning("国会会議録: issue_id=%s をスキップ（パース不可: %s）", issue_id, exc)
                continue
            source_url = f"{source.BASE_URL}/meeting?issueID={issue_id}&maximumRecords=1&recordPacking=json"

            with session_scope() as session:
                meeting_bills: list[str] = []
                if ndl_page is not None:
                    meeting_bills = meeting_repository.resolve_bill_source_ids_for_meeting_ndl(
                        session,
                        record.issue_id,
                        record.session,
                        ndl_page,
                        min_ids_cache,
                        session_bills_cache,
                    )
                topics = parser.build_topics(record.issue_id, topic_labels)
                speakers = parser.build_speaker_names(speeches)
                meeting_repository.upsert_meeting(
                    session,
                    record,
                    speeches,
                    topics,
                    speakers,
                    source_url,
                    meeting_bills,
                )

            total += 1
            _LOG.debug(
                "国会会議録: issue_id=%s を保存（session=%s meeting=%s）",
                issue_id,
                record.session,
                record.name_of_meeting,
            )
    finally:
        _stop_playwright(playwright=playwright, ndl_browser=ndl_browser)

    _LOG.info(
        "国会会議録: 完了 ingested=%s skipped_existing=%s skipped_empty_response=%s skipped_parse_error=%s stopped_for_limit=%s",
        total,
        skipped_existing,
        skipped_no_record,
        skipped_parse_error,
        stopped_for_limit,
    )
    return PipelineResult(name=source.SOURCE_NAME, count=total)
