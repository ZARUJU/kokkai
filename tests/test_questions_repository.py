from sqlalchemy import delete

from kokkai.db.schema import create_all
from kokkai.db.engine import session_scope
from kokkai.models.question import Question
from kokkai.models.question import QuestionModel
from kokkai.repositories import questions as questions_repository


_FIXTURE_SOURCE_ID = "__test_q_person_filter__"


def test_list_questions_filters_by_person_full_name() -> None:
    create_all()
    fixture = Question(
        source_id=_FIXTURE_SOURCE_ID,
        chamber="shugiin",
        session_number=999_997,
        number=99,
        title="テスト用質問主意書（人物フィルタ）",
        submitter="山田太郎君",
        status=None,
        details_url=None,
        question_url=None,
        answer_url=None,
        question_text=None,
        answer_text=None,
    )
    try:
        with session_scope() as session:
            session.execute(delete(QuestionModel).where(QuestionModel.source_id == _FIXTURE_SOURCE_ID))
            questions_repository.upsert_many(session, [fixture], "https://example.com/q-list.htm")

        with session_scope() as session:
            matched = questions_repository.list_all(
                session,
                chamber="shugiin",
                session_number=999_997,
                person_full_name="山田　太 郎",
            )
            assert len(matched) == 1
            assert matched[0]["source_id"] == _FIXTURE_SOURCE_ID

            empty = questions_repository.list_all(
                session,
                chamber="shugiin",
                session_number=999_997,
                person_full_name="佐藤花子",
            )
            assert empty == []

    finally:
        with session_scope() as session:
            session.execute(delete(QuestionModel).where(QuestionModel.source_id == _FIXTURE_SOURCE_ID))
