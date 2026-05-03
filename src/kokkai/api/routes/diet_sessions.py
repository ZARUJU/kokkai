from fastapi import APIRouter
from fastapi import HTTPException

from kokkai.db.engine import session_scope
from kokkai.repositories import diet_sessions


router = APIRouter(prefix="/diet-sessions", tags=["diet-sessions"])


@router.get("")
def list_diet_sessions() -> list[dict[str, object]]:
    with session_scope() as session:
        return diet_sessions.list_all(session)


@router.get("/{number}")
def get_diet_session(number: int) -> dict[str, object]:
    with session_scope() as db_session:
        session = diet_sessions.find_by_number(db_session, number)

    if session is None:
        raise HTTPException(status_code=404, detail="Diet session not found")

    return session
