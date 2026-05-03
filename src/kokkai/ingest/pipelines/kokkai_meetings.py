import os

from kokkai.db.engine import session_scope
from kokkai.db.schema import create_all
from kokkai.ingest.parsers import kokkai_meetings as parser
from kokkai.ingest.pipeline import PipelineResult
from kokkai.ingest.sources import kokkai_api as source
from kokkai.repositories import meeting_records as meeting_repository


DEFAULT_SESSION_FROM = 221
DEFAULT_SESSION_TO = 221


def _ingest_limit() -> int | None:
    raw = os.getenv("KOKKAI_MEETING_INGEST_LIMIT")
    if raw is None or raw == "":
        return None
    return max(0, int(raw))


def run() -> PipelineResult:
    create_all()
    total = 0
    limit = _ingest_limit()

    for issue_id in source.iter_meeting_issue_ids(DEFAULT_SESSION_FROM, DEFAULT_SESSION_TO):
        if limit is not None and total >= limit:
            break

        payload = source.fetch_meeting_page({"issueID": issue_id, "maximumRecords": 1, "recordPacking": "json"})
        source.ensure_meeting_response(payload)
        records = payload.get("meetingRecord") or []
        if not isinstance(records, list) or not records:
            continue
        raw = records[0]
        if not isinstance(raw, dict):
            continue

        record, speeches, topic_labels = parser.parse_meeting_bundle(raw)
        source_url = f"{source.BASE_URL}/meeting?issueID={issue_id}&maximumRecords=1&recordPacking=json"

        with session_scope() as session:
            bills_per_label = [
                meeting_repository.resolve_bill_source_ids(session, record.session, label) for label in topic_labels
            ]
            topics = parser.build_topics(record.issue_id, topic_labels, bills_per_label)
            speakers = parser.build_speaker_names(speeches)
            meeting_repository.upsert_meeting(session, record, speeches, topics, speakers, source_url)

        total += 1

    return PipelineResult(name=source.SOURCE_NAME, count=total)
