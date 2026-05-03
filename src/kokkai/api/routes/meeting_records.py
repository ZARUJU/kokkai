from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Query

from kokkai.db.engine import session_scope
from kokkai.repositories import meeting_records


router = APIRouter(prefix="/meeting-records", tags=["meeting-records"])


@router.get("")
def list_meeting_records(
    session_number: int | None = Query(default=None, description="国会回次"),
    name_of_meeting: str | None = Query(default=None, description="会議名（完全一致）"),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, object]]:
    with session_scope() as session:
        return meeting_records.list_meetings(
            session,
            session_number=session_number,
            name_of_meeting=name_of_meeting,
            limit=limit,
        )


@router.get("/{issue_id}")
def get_meeting_record(issue_id: str) -> dict[str, object]:
    with session_scope() as session:
        meeting = meeting_records.find_meeting(session, issue_id)

    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting record not found")

    return meeting
