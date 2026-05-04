import logging
import os

from kokkai.db.engine import session_scope
from kokkai.db.schema import create_all
from kokkai.ingest.cli_sessions import ingest_sessions_explicit
from kokkai.ingest.parsers import questions as parser
from kokkai.ingest.pipeline import IngestRunContext
from kokkai.ingest.pipeline import PipelineResult
from kokkai.ingest.sources import questions as source
from kokkai.models.question import Question
from kokkai.repositories import diet_sessions
from kokkai.repositories import questions as question_repository


_LOG = logging.getLogger(__name__)

DEFAULT_SESSION_NUMBERS = (221,)


def _resolve_session_numbers(context: IngestRunContext) -> tuple[tuple[int, ...], str]:
    explicit = ingest_sessions_explicit(context, os.getenv("QUESTIONS_SESSIONS"))
    if explicit is not None:
        return explicit, "CLI または環境変数 QUESTIONS_SESSIONS"
    with session_scope() as session:
        numbers = diet_sessions.latest_session_numbers(session, 2)
    if not numbers:
        return DEFAULT_SESSION_NUMBERS, "フォールバック（会期一覧が DB に無い）"
    return tuple(numbers), "会期一覧 DB の新しい順から最大2件"


def run(context: IngestRunContext) -> PipelineResult:
    create_all()
    session_numbers, sessions_note = _resolve_session_numbers(context)
    _LOG.info(
        "質問主意書: 対象国会回次=%s（%s）",
        ", ".join(str(n) for n in session_numbers),
        sessions_note,
    )

    total = 0
    for sn in session_numbers:
        _LOG.info("質問主意書 国会回次 %s: 衆議院一覧を取得", sn)
        shugiin_doc = source.fetch_shugiin(sn)
        shugiin_questions = parser.parse_shugiin(shugiin_doc.text, shugiin_doc.url)
        shugiin_questions = _attach_document_texts(shugiin_questions)
        with session_scope() as session:
            question_repository.upsert_many(session, shugiin_questions, shugiin_doc.url)
        total += len(shugiin_questions)
        _LOG.info("質問主意書 国会回次 %s: 衆議院 %s 件", sn, len(shugiin_questions))

        _LOG.info("質問主意書 国会回次 %s: 参議院一覧を取得", sn)
        sangiin_doc = source.fetch_sangiin(sn)
        sangiin_questions = parser.parse_sangiin(sangiin_doc.text, sangiin_doc.url)
        sangiin_questions = _attach_document_texts(sangiin_questions)
        with session_scope() as session:
            question_repository.upsert_many(session, sangiin_questions, sangiin_doc.url)
        total += len(sangiin_questions)
        _LOG.info("質問主意書 国会回次 %s: 参議院 %s 件", sn, len(sangiin_questions))

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
