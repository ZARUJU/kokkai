from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Query

from kokkai.api.schemas import MeetingRecordDetailOut
from kokkai.api.schemas import MeetingRecordListOut
from kokkai.api.schemas import MeetingSpeechOut
from kokkai.db.engine import session_scope
from kokkai.repositories import meeting_records


router = APIRouter(prefix="/meeting-records", tags=["meeting-records"])


@router.get("/speeches", response_model=list[MeetingSpeechOut])
def list_meeting_speeches_by_speaker(
    speaker_full_name: str = Query(..., description="発言者のフルネーム（空白は無視してキー化し、DB と完全一致）"),
    session_number: int | None = Query(default=None, description="国会回次"),
    limit: int = Query(default=500, ge=1, le=2000),
) -> list[MeetingSpeechOut]:
    with session_scope() as session:
        return meeting_records.list_speeches_by_speaker_full_name(
            session,
            speaker_full_name=speaker_full_name,
            session_number=session_number,
            limit=limit,
        )


@router.get("", response_model=list[MeetingRecordListOut])
def list_meeting_records(
    session_number: int | None = Query(default=None, description="国会回次"),
    name_of_meeting: str | None = Query(default=None, description="会議名（完全一致）"),
    speaker_full_name: str | None = Query(
        default=None,
        description="会議の発言者一覧（speakers_json）に含まれる人物のフルネーム（空白除去後の完全一致）",
    ),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[MeetingRecordListOut]:
    with session_scope() as session:
        return meeting_records.list_meetings(
            session,
            session_number=session_number,
            name_of_meeting=name_of_meeting,
            speaker_full_name=speaker_full_name,
            limit=limit,
        )


@router.get("/{issue_id}", response_model=MeetingRecordDetailOut)
def get_meeting_record(issue_id: str) -> MeetingRecordDetailOut:
    with session_scope() as session:
        meeting = meeting_records.find_meeting(session, issue_id)

    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting record not found")

    return meeting
