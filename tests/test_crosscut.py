"""SQLite UDF と API スキーマのスモークテスト。"""

from sqlalchemy import text

from kokkai.api.schemas import BillDetailOut
from kokkai.api.schemas import BillProgressOut
from kokkai.api.schemas import BillSummaryOut
from kokkai.api.schemas import QuestionOut
from kokkai.db.engine import engine
from kokkai.db.engine import session_scope
from kokkai.ingest.parsers.common import compact_person_full_name
from kokkai.repositories import bills
from kokkai.repositories import questions as questions_repository


def test_kokkai_compact_person_udf_matches_python() -> None:
    raw = "山田　太 郎"
    with engine.connect() as conn:
        got = conn.execute(text("SELECT kokkai_compact_person(:x)"), {"x": raw}).scalar_one()
    assert got == compact_person_full_name(raw)


def test_bill_schemas_validate_repository_payload() -> None:
    with session_scope() as session:
        lst = bills.list_all(session, session_number=None, category=None, person_full_name=None)
        if not lst:
            return
        BillSummaryOut.model_validate(lst[0])
        sid = str(lst[0]["source_id"])
        detail = bills.find_by_source_id_with_progress(session, sid)
        assert detail is not None
        BillDetailOut.model_validate(detail)
        BillProgressOut.model_validate(detail["progress"])


def test_question_schemas_validate_repository_payload() -> None:
    with session_scope() as session:
        lst = questions_repository.list_all(session, chamber=None, session_number=None)
        if not lst:
            return
        QuestionOut.model_validate(lst[0])
        sid = str(lst[0]["source_id"])
        one = questions_repository.find_by_source_id(session, sid)
        assert one is not None
        QuestionOut.model_validate(one)
