import logging

from kokkai.db.engine import session_scope
from kokkai.db.schema import create_all
from kokkai.ingest.parsers import questions as parser
from kokkai.ingest.pipeline import PipelineResult
from kokkai.ingest.sources import questions as source
from kokkai.models.question import Question
from kokkai.repositories import questions as question_repository


_LOG = logging.getLogger(__name__)


def run() -> PipelineResult:
    create_all()

    shugiin_doc = source.fetch_shugiin()
    shugiin_questions = parser.parse_shugiin(shugiin_doc.text, shugiin_doc.url)
    shugiin_questions = _attach_document_texts(shugiin_questions)
    with session_scope() as session:
        question_repository.upsert_many(session, shugiin_questions, shugiin_doc.url)
    _LOG.info("質問主意書(衆議院): %s 件", len(shugiin_questions))

    sangiin_doc = source.fetch_sangiin()
    sangiin_questions = parser.parse_sangiin(sangiin_doc.text, sangiin_doc.url)
    sangiin_questions = _attach_document_texts(sangiin_questions)
    with session_scope() as session:
        question_repository.upsert_many(session, sangiin_questions, sangiin_doc.url)
    _LOG.info("質問主意書(参議院): %s 件", len(sangiin_questions))

    total = len(shugiin_questions) + len(sangiin_questions)
    return PipelineResult(name=source.SOURCE_NAME, count=total)


def _attach_document_texts(items: list[Question]) -> list[Question]:
    out: list[Question] = []
    for item in items:
        question_text = _fetch_and_extract(item.question_url, item.chamber)
        answer_text = _fetch_and_extract(item.answer_url, item.chamber)
        out.append(
            Question(
                source_id=item.source_id,
                chamber=item.chamber,
                session_number=item.session_number,
                number=item.number,
                title=item.title,
                submitter=item.submitter,
                status=item.status,
                details_url=item.details_url,
                question_url=item.question_url,
                answer_url=item.answer_url,
                question_text=question_text,
                answer_text=answer_text,
            )
        )
    return out


def _fetch_and_extract(url: str | None, chamber: str) -> str | None:
    if not url:
        return None
    document = source.fetch_url(url, chamber)
    return parser.extract_document_text(document.text, document.url)
