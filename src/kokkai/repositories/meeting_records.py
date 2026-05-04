import json
import logging
import re
from datetime import UTC
from datetime import datetime

from sqlalchemy import delete
from sqlalchemy import exists
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

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

logger = logging.getLogger(__name__)


def _normalize_for_bill_match(value: str) -> str:
    text = normalize_spaces(value)
    for token in (
        "（内閣提出）",
        "（衆法）",
        "（参法）",
        "（閣法）",
        "（予算）",
    ):
        text = text.replace(token, "")
    return text


_PROC_TOPIC_SUFFIXES = (
    "の趣旨説明並びに質疑",
    "の趣旨説明及び質疑",
    "の趣旨説明",
    "並びに質疑",
    "及び質疑",
)


def _bill_fragments_from_topic_label(topic_label: str) -> list[str]:
    """読点・「及び」と 演説…並びに… の折り畳みで、議案名らしい断片を得る。"""
    t = _normalize_for_bill_match(topic_label)
    for suffix in sorted(_PROC_TOPIC_SUFFIXES, key=len, reverse=True):
        if t.endswith(suffix):
            t = t[: -len(suffix)].strip()
            break
    fragments: list[str] = []
    seen: set[str] = set()
    for piece in re.split(r"[、]|及び", t):
        piece = normalize_spaces(piece).strip()
        if "法律案" not in piece:
            continue
        if "並びに" in piece:
            tail = piece.split("並びに")[-1].strip()
            if "法律案" in tail:
                piece = tail
        if len(piece) >= 6 and piece not in seen:
            seen.add(piece)
            fragments.append(piece)
    return fragments


def _match_score_title(candidate: str, haystack: str) -> int:
    """マッチ強度（長い一致を優先）。candidate=DB議題名、haystack=議題断片または全文。"""
    if candidate in haystack:
        return len(candidate)
    if len(haystack) >= 12 and haystack in candidate:
        return len(haystack)
    return 0


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


def _best_bill_for_haystack(rows: list[BillModel], haystack: str) -> str | None:
    if len(haystack) < 6:
        return None
    best_score = 0
    best_id: str | None = None
    for row in rows:
        if "法律案" not in row.title:
            continue
        candidate = _normalize_for_bill_match(row.title)
        if not candidate or len(candidate) < 6:
            continue
        score = _match_score_title(candidate, haystack)
        if score > best_score:
            best_score = score
            best_id = row.source_id
    if best_score < 8:
        return None
    return best_id


def resolve_bill_source_ids(session: Session, session_number: int, topic_label: str) -> list[str]:
    """議題に含まれる法令案断片ごとに bills を照合し、重複のない source_id リストを返す。"""
    if "法律案" not in topic_label:
        return []

    norm_topic = _normalize_for_bill_match(topic_label)
    if len(norm_topic) < 4:
        return []

    rows = _session_bill_rows(session, session_number)
    fragments = _bill_fragments_from_topic_label(topic_label)
    haystacks = fragments if fragments else [norm_topic]

    out: list[str] = []
    seen: set[str] = set()
    for haystack in haystacks:
        bid = _best_bill_for_haystack(rows, haystack)
        if bid and bid not in seen:
            seen.add(bid)
            out.append(bid)
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
) -> None:
    fetched_at = datetime.now(UTC)
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
