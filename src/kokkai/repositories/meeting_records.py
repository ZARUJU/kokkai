from __future__ import annotations

import json
import logging
import time
from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import delete
from sqlalchemy import exists
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from kokkai.ingest.parsers.ndl_bill_id import ndl_bill_id_from_bill_row
from kokkai.ingest.sources.kokkai_api import REQUEST_INTERVAL_SEC
from kokkai.ingest.sources.kokkai_ndl_playwright import fetch_min_ids_for_bill_id
from kokkai.models.bill import BillModel
from kokkai.models.meeting_record import MeetingRecord
from kokkai.models.meeting_record import MeetingRecordModel
from kokkai.models.meeting_record import MeetingSpeech
from kokkai.models.meeting_record import MeetingSpeechModel
from kokkai.models.meeting_record import MeetingTopic
from kokkai.models.meeting_record import MeetingTopicModel
from kokkai.ingest.parsers.common import compact_person_full_name
from kokkai.ingest.parsers.common import normalize_spaces
from kokkai.ingest.parsers.common import optional_compact_person_query

if TYPE_CHECKING:
    from playwright.sync_api import Page

logger = logging.getLogger(__name__)


def _session_bill_rows(session: Session, session_number: int) -> list[BillModel]:
    return list(
        session.scalars(
            select(BillModel).where(
                or_(
                    BillModel.session_number == session_number,
                    BillModel.submitted_session_number == session_number,
                )
            )
        ).all()
    )


def prefetch_ndl_min_ids_for_session_range(
    session: Session,
    session_from: int,
    session_to: int,
    page: Page,
    min_ids_cache: dict[str, list[str]],
    session_bills_cache: dict[int, list[BillModel]],
) -> tuple[int, int]:
    """会期範囲の bills を走査し、ユニークな billId ごとに min_id 一覧をキャッシュする。

    戻り値は (新規取得した billId 数, 走査した議案行数)。
    """
    fetched = 0
    considered = 0
    seen_bill_id: set[str] = set()
    for sn in range(session_from, session_to + 1):
        rows = _session_bill_rows(session, sn)
        session_bills_cache[sn] = rows
        for row in rows:
            considered += 1
            bill_id = ndl_bill_id_from_bill_row(row.submitted_session_number, row.category, row.number)
            if bill_id is None or bill_id in seen_bill_id:
                continue
            seen_bill_id.add(bill_id)
            if bill_id not in min_ids_cache:
                min_ids_cache[bill_id] = fetch_min_ids_for_bill_id(
                    page,
                    bill_id,
                    reset_context=not min_ids_cache,
                )
                fetched += 1
                time.sleep(REQUEST_INTERVAL_SEC)
    return fetched, considered


def resolve_bill_source_ids_for_meeting_ndl(
    session: Session,
    issue_id: str,
    session_number: int,
    page: Page,
    min_ids_cache: dict[str, list[str]],
    session_bills_cache: dict[int, list[BillModel]],
) -> list[str]:
    """会議録の会期に該当する全議案を対象に billId を組み、min_id に issue_id が含まれる行だけ会議録に紐づける。"""
    rows = session_bills_cache.get(session_number)
    if rows is None:
        rows = _session_bill_rows(session, session_number)
        session_bills_cache[session_number] = rows
    out: list[str] = []
    seen: set[str] = set()
    for row in rows:
        bill_id = ndl_bill_id_from_bill_row(row.submitted_session_number, row.category, row.number)
        if bill_id is None:
            continue
        if bill_id not in min_ids_cache:
            min_ids_cache[bill_id] = fetch_min_ids_for_bill_id(page, bill_id, reset_context=False)
            time.sleep(REQUEST_INTERVAL_SEC)
        if issue_id not in min_ids_cache[bill_id]:
            continue
        if row.source_id not in seen:
            seen.add(row.source_id)
            out.append(row.source_id)
    return out


def _encode_bill_source_ids_json(ids: list[str]) -> str:
    return json.dumps(ids, ensure_ascii=False, separators=(",", ":"))


def _decode_json_str_list(raw: str | None) -> list[str]:
    if not raw or not raw.strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(
            "JSONDecodeError for string-list column (preview %.120s)",
            raw.replace("\n", " ")[:120],
        )
        return []
    if not isinstance(data, list):
        return []
    return [str(x) for x in data if isinstance(x, str)]


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _encode_speakers_json(speakers: list[str]) -> str:
    return json.dumps(speakers, ensure_ascii=False, separators=(",", ":"))


def meeting_issue_exists(session: Session, issue_id: str) -> bool:
    return session.get(MeetingRecordModel, issue_id) is not None


def upsert_meeting(
    session: Session,
    record: MeetingRecord,
    speeches: list[MeetingSpeech],
    topics: list[MeetingTopic],
    speakers: list[str],
    source_url: str,
    meeting_bill_source_ids: list[str] | None = None,
) -> None:
    fetched_at = datetime.now(UTC)
    bills_json = _encode_bill_source_ids_json(meeting_bill_source_ids or [])
    meeting_values = {
        "issue_id": record.issue_id,
        "session": record.session,
        "name_of_house": record.name_of_house,
        "name_of_meeting": record.name_of_meeting,
        "issue": record.issue,
        "meeting_date": record.meeting_date,
        "closing": record.closing,
        "image_kind": record.image_kind,
        "search_object": record.search_object,
        "meeting_url": record.meeting_url,
        "pdf_url": record.pdf_url,
        "meeting_start_hhmm": record.meeting_start_hhmm,
        "meeting_end_hhmm": record.meeting_end_hhmm,
        "header_info_text": record.header_info_text,
        "speakers_json": _encode_speakers_json(speakers),
        "bill_source_ids_json": bills_json,
        "source_url": source_url,
        "fetched_at": fetched_at,
    }

    statement = insert(MeetingRecordModel).values(meeting_values)
    excluded = statement.excluded
    statement = statement.on_conflict_do_update(
        index_elements=[MeetingRecordModel.issue_id],
        set_={
            "session": excluded.session,
            "name_of_house": excluded.name_of_house,
            "name_of_meeting": excluded.name_of_meeting,
            "issue": excluded.issue,
            "meeting_date": excluded.meeting_date,
            "closing": excluded.closing,
            "image_kind": excluded.image_kind,
            "search_object": excluded.search_object,
            "meeting_url": excluded.meeting_url,
            "pdf_url": excluded.pdf_url,
            "meeting_start_hhmm": excluded.meeting_start_hhmm,
            "meeting_end_hhmm": excluded.meeting_end_hhmm,
            "header_info_text": excluded.header_info_text,
            "speakers_json": excluded.speakers_json,
            "bill_source_ids_json": excluded.bill_source_ids_json,
            "source_url": excluded.source_url,
            "fetched_at": excluded.fetched_at,
        },
    )
    session.execute(statement)

    session.execute(delete(MeetingSpeechModel).where(MeetingSpeechModel.issue_id == record.issue_id))
    session.execute(delete(MeetingTopicModel).where(MeetingTopicModel.issue_id == record.issue_id))

    if speeches:
        speech_values = [
            {
                "speech_id": item.speech_id,
                "issue_id": item.issue_id,
                "speech_order": item.speech_order,
                "speaker": item.speaker,
                "speaker_yomi": item.speaker_yomi,
                "speaker_group": item.speaker_group,
                "speaker_position": item.speaker_position,
                "speaker_role": item.speaker_role,
                "speech": item.speech,
                "start_page": item.start_page,
                "speech_url": item.speech_url,
                "record_create_time": _utc(item.record_create_time),
                "record_update_time": _utc(item.record_update_time),
            }
            for item in speeches
        ]
        session.execute(insert(MeetingSpeechModel).values(speech_values))

    if topics:
        topic_values = [
            {
                "source_id": item.source_id,
                "issue_id": item.issue_id,
                "topic_order": item.topic_order,
                "label": item.label,
                "bill_source_ids_json": _encode_bill_source_ids_json(list(item.bill_source_ids)),
            }
            for item in topics
        ]
        session.execute(insert(MeetingTopicModel).values(topic_values))


def list_meetings(
    session: Session,
    session_number: int | None = None,
    name_of_meeting: str | None = None,
    speaker_full_name: str | None = None,
    limit: int = 100,
) -> list[dict[str, object]]:
    statement = select(MeetingRecordModel)
    if session_number is not None:
        statement = statement.where(MeetingRecordModel.session == session_number)
    if name_of_meeting:
        statement = statement.where(MeetingRecordModel.name_of_meeting == name_of_meeting)
    apply_speaker, norm = optional_compact_person_query(speaker_full_name)
    if apply_speaker:
        if not norm:
            return []
        j_table = func.json_each(MeetingRecordModel.speakers_json).table_valued("value").alias("j")
        statement = statement.where(
            exists(
                select(1).select_from(j_table).where(
                    func.kokkai_compact_person(j_table.c.value) == norm,
                )
            )
        )

    statement = statement.order_by(MeetingRecordModel.meeting_date.desc(), MeetingRecordModel.issue_id).limit(limit)
    rows = session.scalars(statement).all()
    return [meeting_to_dict(row) for row in rows]


def find_meeting(session: Session, issue_id: str) -> dict[str, object] | None:
    row = session.get(MeetingRecordModel, issue_id)
    if row is None:
        return None

    detail = meeting_to_dict(row)
    detail["header_info_text"] = row.header_info_text
    detail["topics"] = list_topics(session, issue_id)
    detail["speech_count"] = count_speeches(session, issue_id)
    return detail


def list_topics(session: Session, issue_id: str) -> list[dict[str, object]]:
    rows = session.scalars(
        select(MeetingTopicModel)
        .where(MeetingTopicModel.issue_id == issue_id)
        .order_by(MeetingTopicModel.topic_order)
    ).all()
    return [topic_to_dict(row) for row in rows]


def count_speeches(session: Session, issue_id: str) -> int:
    rows = session.scalars(select(MeetingSpeechModel).where(MeetingSpeechModel.issue_id == issue_id)).all()
    return len(rows)


def list_speeches_by_speaker_full_name(
    session: Session,
    speaker_full_name: str,
    session_number: int | None = None,
    limit: int = 500,
) -> list[dict[str, object]]:
    norm = compact_person_full_name(speaker_full_name)
    if not norm:
        return []

    statement = (
        select(MeetingSpeechModel)
        .join(MeetingRecordModel, MeetingSpeechModel.issue_id == MeetingRecordModel.issue_id)
        .where(
            MeetingSpeechModel.speaker.isnot(None),
            func.kokkai_compact_person(MeetingSpeechModel.speaker) == norm,
        )
    )
    if session_number is not None:
        statement = statement.where(MeetingRecordModel.session == session_number)
    statement = statement.order_by(
        MeetingRecordModel.meeting_date.desc(),
        MeetingSpeechModel.issue_id,
        MeetingSpeechModel.speech_order,
    ).limit(limit)
    rows = session.scalars(statement).all()
    return [speech_to_dict(row) for row in rows]


def speech_to_dict(row: MeetingSpeechModel) -> dict[str, object]:
    rc = _utc(row.record_create_time)
    ru = _utc(row.record_update_time)

    return {
        "speech_id": row.speech_id,
        "issue_id": row.issue_id,
        "speech_order": row.speech_order,
        "speaker": row.speaker,
        "speaker_yomi": row.speaker_yomi,
        "speaker_group": row.speaker_group,
        "speaker_position": row.speaker_position,
        "speaker_role": row.speaker_role,
        "speech": row.speech,
        "start_page": row.start_page,
        "speech_url": row.speech_url,
        "record_create_time": rc.isoformat() if rc else None,
        "record_update_time": ru.isoformat() if ru else None,
    }


def meeting_to_dict(row: MeetingRecordModel) -> dict[str, object]:
    fetched_at = row.fetched_at
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=UTC)

    return {
        "issue_id": row.issue_id,
        "session": row.session,
        "name_of_house": row.name_of_house,
        "name_of_meeting": row.name_of_meeting,
        "issue": row.issue,
        "meeting_date": row.meeting_date.isoformat(),
        "closing": row.closing,
        "image_kind": row.image_kind,
        "search_object": row.search_object,
        "meeting_url": row.meeting_url,
        "pdf_url": row.pdf_url,
        "meeting_start_hhmm": row.meeting_start_hhmm,
        "meeting_end_hhmm": row.meeting_end_hhmm,
        "speakers": _decode_json_str_list(row.speakers_json),
        "bill_source_ids": _decode_json_str_list(row.bill_source_ids_json),
        "source_url": row.source_url,
        "fetched_at": fetched_at.isoformat(),
    }


def topic_to_dict(row: MeetingTopicModel) -> dict[str, object]:
    return {
        "source_id": row.source_id,
        "issue_id": row.issue_id,
        "topic_order": row.topic_order,
        "label": row.label,
        "bill_source_ids": _decode_json_str_list(row.bill_source_ids_json),
    }
