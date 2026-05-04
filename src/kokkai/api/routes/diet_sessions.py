from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Query

from kokkai.api.schemas import BillSummaryOut
from kokkai.api.schemas import DietSessionOut
from kokkai.db.engine import session_scope
from kokkai.repositories import bills as bills_repository
from kokkai.repositories import diet_sessions


router = APIRouter(prefix="/diet-sessions", tags=["diet-sessions"])


@router.get("", response_model=list[DietSessionOut])
def list_diet_sessions() -> list[DietSessionOut]:
    with session_scope() as session:
        return diet_sessions.list_all(session)


@router.get("/{number}/bills", response_model=list[BillSummaryOut])
def list_bills_for_diet_session(
    number: int,
    category: str | None = Query(default=None, description="議案種別。例: 衆法, 参法, 閣法, 予算, 条約"),
    person_full_name: str | None = Query(
        default=None,
        description="議案情報の提出者・賛成者などに登場する人物のフルネーム（空白除去後の完全一致）",
    ),
) -> list[BillSummaryOut]:
    """指定した国会回次の衆議院議案一覧ページに相当する議案の一覧。"""
    with session_scope() as session:
        return bills_repository.list_all(
            session,
            session_number=number,
            category=category,
            person_full_name=person_full_name,
        )


@router.get("/{number}", response_model=DietSessionOut)
def get_diet_session(number: int) -> DietSessionOut:
    with session_scope() as db_session:
        session = diet_sessions.find_by_number(db_session, number)

    if session is None:
        raise HTTPException(status_code=404, detail="Diet session not found")

    return session
