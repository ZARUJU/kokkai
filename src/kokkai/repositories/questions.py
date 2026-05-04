from datetime import UTC
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from kokkai.ingest.parsers.common import clean_kokkai_speaker_name
from kokkai.ingest.parsers.common import compact_person_full_name
from kokkai.ingest.parsers.common import normalize_spaces
from kokkai.ingest.parsers.common import optional_compact_person_query
from kokkai.models.question import Question
from kokkai.models.question import QuestionModel


def upsert_many(session: Session, questions: list[Question], source_url: str) -> None:
    if not questions:
        return

    fetched_at = datetime.now(UTC)
    values = [
        {
            "source_id": question.source_id,
            "chamber": question.chamber,
            "session_number": question.session_number,
            "number": question.number,
            "title": question.title,
            "submitter": question.submitter,
            "status": question.status,
            "details_url": question.details_url,
            "question_url": question.question_url,
            "answer_url": question.answer_url,
            "question_text": question.question_text,
            "answer_text": question.answer_text,
            "source_url": source_url,
            "fetched_at": fetched_at,
        }
        for question in questions
    ]
    statement = insert(QuestionModel).values(values)
    excluded = statement.excluded
    statement = statement.on_conflict_do_update(
        index_elements=[QuestionModel.source_id],
        set_={
            "chamber": excluded.chamber,
            "session_number": excluded.session_number,
            "number": excluded.number,
            "title": excluded.title,
            "submitter": excluded.submitter,
            "status": excluded.status,
            "details_url": excluded.details_url,
            "question_url": excluded.question_url,
            "answer_url": excluded.answer_url,
            "question_text": excluded.question_text,
            "answer_text": excluded.answer_text,
            "source_url": excluded.source_url,
            "fetched_at": excluded.fetched_at,
        },
    )
    session.execute(statement)


def list_all(
    session: Session,
    chamber: str | None = None,
    session_number: int | None = None,
    person_full_name: str | None = None,
) -> list[dict[str, object]]:
    apply_person, norm = optional_compact_person_query(person_full_name)
    if apply_person and not norm:
        return []

    statement = select(QuestionModel)
    if chamber is not None:
        statement = statement.where(QuestionModel.chamber == chamber)
    if session_number is not None:
        statement = statement.where(QuestionModel.session_number == session_number)

    statement = statement.order_by(
        QuestionModel.session_number.desc(),
        QuestionModel.chamber,
        QuestionModel.number,
    )
    rows = session.scalars(statement).all()
    if apply_person:
        rows = [
            row
            for row in rows
            if submitter_compact_key(row.submitter) == norm
        ]
    return [to_dict(row) for row in rows]


def find_by_source_id(session: Session, source_id: str) -> dict[str, object] | None:
    row = session.get(QuestionModel, source_id)
    if row is None:
        return None
    return to_dict(row)


def to_dict(row: QuestionModel) -> dict[str, object]:
    fetched_at = row.fetched_at
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=UTC)

    return {
        "source_id": row.source_id,
        "chamber": row.chamber,
        "session_number": row.session_number,
        "number": row.number,
        "title": row.title,
        "submitter": _normalized_person_name(row.submitter),
        "status": row.status,
        "details_url": row.details_url,
        "question_url": row.question_url,
        "answer_url": row.answer_url,
        "question_text": row.question_text,
        "answer_text": row.answer_text,
        "source_url": row.source_url,
        "fetched_at": fetched_at.isoformat(),
    }


def submitter_compact_key(raw_submitter: str | None) -> str | None:
    """クエリ側の人物名（`compact_person_full_name`）と DB 側提出者を照合するときのキー。"""
    display = _normalized_person_name(raw_submitter)
    if not display:
        return None
    key = compact_person_full_name(display)
    return key if key else None


def _normalized_person_name(value: str | None) -> str | None:
    """会議録 speaker と同様の敬称除去。DB に旧形式が残っても一覧・詳細で揃える。"""
    if not value:
        return None
    text = normalize_spaces(value)
    if not text:
        return None
    return clean_kokkai_speaker_name(text)
