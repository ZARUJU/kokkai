import os

from kokkai.db.engine import session_scope
from kokkai.db.schema import create_all
from kokkai.ingest.parsers import shugiin_bills as parser
from kokkai.ingest.pipeline import PipelineResult
from kokkai.ingest.sources import shugiin_bills as source
from kokkai.repositories import bills as bill_repository
from kokkai.repositories import diet_sessions


DEFAULT_SESSION_NUMBERS = (221,)


def _parse_session_env() -> tuple[int, ...] | None:
    raw = os.getenv("SHUGIIN_BILL_SESSIONS")
    if raw is None or raw.strip() == "":
        return None
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return None
    return tuple(int(p) for p in parts)


def _resolve_session_numbers() -> tuple[int, ...]:
    env_sessions = _parse_session_env()
    if env_sessions is not None:
        return env_sessions
    with session_scope() as session:
        numbers = diet_sessions.latest_session_numbers(session, 2)
    if not numbers:
        return DEFAULT_SESSION_NUMBERS
    return tuple(numbers)


def run() -> PipelineResult:
    total_count = 0

    create_all()
    for session_number in _resolve_session_numbers():
        document = source.fetch(session_number)
        bills = parser.parse(document.text, document.url)

        with session_scope() as session:
            bill_repository.upsert_many(session, bills, document.url)

        for bill in bills:
            if bill.progress_url:
                progress_document = source.fetch_url(bill.progress_url)
                progress_items = parser.parse_progress_items(progress_document.text, bill.source_id)
                with session_scope() as session:
                    bill_repository.replace_progress_items(session, bill.source_id, progress_items, progress_document.url)

            if bill.text_url:
                text_info_document = source.fetch_url(bill.text_url)
                links = parser.parse_text_document_links(text_info_document.text, text_info_document.url)
                text_documents = []
                for link in links:
                    text_document = source.fetch_url(link.url)
                    text_documents.append(parser.parse_text_document(text_document.text, bill.source_id, link))

                with session_scope() as session:
                    bill_repository.replace_text_documents(session, bill.source_id, text_documents, text_info_document.url)

        total_count += len(bills)

    return PipelineResult(name=source.SOURCE_NAME, count=total_count)
