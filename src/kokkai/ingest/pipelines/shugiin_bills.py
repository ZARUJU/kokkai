import logging
import os

from kokkai.db.engine import session_scope
from kokkai.db.schema import create_all
from kokkai.ingest.cli_sessions import ingest_sessions_explicit
from kokkai.ingest.parsers import shugiin_bills as parser
from kokkai.ingest.pipeline import IngestRunContext
from kokkai.ingest.pipeline import PipelineResult
from kokkai.ingest.sources import shugiin_bills as source
from kokkai.repositories import bills as bill_repository
from kokkai.repositories import diet_sessions


DEFAULT_SESSION_NUMBERS = (221,)

_LOG = logging.getLogger(__name__)


def _resolve_session_numbers(context: IngestRunContext) -> tuple[tuple[int, ...], str]:
    explicit = ingest_sessions_explicit(context, os.getenv("SHUGIIN_BILL_SESSIONS"))
    if explicit is not None:
        return explicit, "CLI または環境変数 SHUGIIN_BILL_SESSIONS"
    with session_scope() as session:
        numbers = diet_sessions.latest_session_numbers(session, 2)
    if not numbers:
        return DEFAULT_SESSION_NUMBERS, "フォールバック（会期一覧が DB に無い）"
    return tuple(numbers), "会期一覧 DB の新しい順から最大2件"


def run(context: IngestRunContext) -> PipelineResult:
    total_count = 0

    create_all()
    session_numbers, sessions_note = _resolve_session_numbers(context)
    _LOG.info(
        "衆議院議案: 対象国会回次=%s（%s）",
        ", ".join(str(n) for n in session_numbers),
        sessions_note,
    )

    for session_number in session_numbers:
        _LOG.info("衆議院議案 国会回次 %s: 一覧ページを取得", session_number)
        document = source.fetch(session_number)
        bills = parser.parse(document.text, document.url)
        _LOG.info(
            "衆議院議案 国会回次 %s: 一覧を解析 (%s 件) → DB upsert",
            session_number,
            len(bills),
        )

        with session_scope() as session:
            bill_repository.upsert_many(session, bills, document.url)

        for bill in bills:
            if bill.progress_url:
                _LOG.debug(
                    "衆議院議案 国会回次 %s: 経過取得 source_id=%s",
                    session_number,
                    bill.source_id,
                )
                progress_document = source.fetch_url(bill.progress_url)
                progress_items = parser.parse_progress_items(progress_document.text, bill.source_id)
                with session_scope() as session:
                    bill_repository.replace_progress_items(session, bill.source_id, progress_items, progress_document.url)

            if bill.text_url:
                _LOG.debug(
                    "衆議院議案 国会回次 %s: 本文情報 source_id=%s",
                    session_number,
                    bill.source_id,
                )
                text_info_document = source.fetch_url(bill.text_url)
                links = parser.parse_text_document_links(text_info_document.text, text_info_document.url)
                text_documents = []
                for link in links:
                    text_document = source.fetch_url(link.url)
                    text_documents.append(parser.parse_text_document(text_document.text, bill.source_id, link))

                with session_scope() as session:
                    bill_repository.replace_text_documents(session, bill.source_id, text_documents, text_info_document.url)

        _LOG.info(
            "衆議院議案 国会回次 %s: 経過・本文の取得まで完了（一覧 %s 件）",
            session_number,
            len(bills),
        )
        total_count += len(bills)

    _LOG.info("衆議院議案: 全国会回次で一覧あわせ %s 件処理", total_count)
    return PipelineResult(name=source.SOURCE_NAME, count=total_count)
