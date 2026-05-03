from kokkai.db.engine import session_scope
from kokkai.db.schema import create_all
from kokkai.ingest.parsers import shugiin_bills as parser
from kokkai.ingest.pipeline import PipelineResult
from kokkai.ingest.sources import shugiin_bills as source
from kokkai.repositories import bills as bill_repository


DEFAULT_SESSION_NUMBERS = (221,)


def run() -> PipelineResult:
    total_count = 0

    create_all()
    for session_number in DEFAULT_SESSION_NUMBERS:
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
