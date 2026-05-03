from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Query

from kokkai.db.engine import session_scope
from kokkai.repositories import bills as bills_repository
from kokkai.repositories import diet_sessions


router = APIRouter(prefix="/diet-sessions", tags=["diet-sessions"])


@router.get("")
def list_diet_sessions() -> list[dict[str, object]]:
    with session_scope() as session:
        return diet_sessions.list_all(session)


@router.get("/{number}/bills")
def list_bills_for_diet_session(
    number: int,
    category: str | None = Query(default=None, description="議案種別。例: 衆法, 参法, 閣法, 予算, 条約"),
) -> list[dict[str, object]]:
    """指定した国会回次の衆議院議案一覧ページに相当する議案の一覧。"""
    with session_scope() as session:
        return bills_repository.list_all(session, session_number=number, category=category)


@router.get("/{number}")
def get_diet_session(number: int) -> dict[str, object]:
    with session_scope() as db_session:
        session = diet_sessions.find_by_number(db_session, number)

    if session is None:
        raise HTTPException(status_code=404, detail="Diet session not found")

    return session
