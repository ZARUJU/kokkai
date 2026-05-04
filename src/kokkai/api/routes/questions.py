from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Query

from kokkai.api.schemas import QuestionOut
from kokkai.db.engine import session_scope
from kokkai.repositories import questions as questions_repository


router = APIRouter(prefix="/questions", tags=["questions"])


@router.get("", response_model=list[QuestionOut])
def list_questions(
    chamber: str | None = Query(default=None, description="院別。`shugiin` または `sangiin`"),
    session_number: int | None = Query(default=None, description="国会回次"),
    person_full_name: str | None = Query(
        default=None,
        description="提出者のフルネーム（議案一覧と同様、空白除去後の完全一致）",
    ),
) -> list[QuestionOut]:
    with session_scope() as session:
        return questions_repository.list_all(
            session,
            chamber=chamber,
            session_number=session_number,
            person_full_name=person_full_name,
        )


@router.get("/{source_id}", response_model=QuestionOut)
def get_question(source_id: str) -> QuestionOut:
    with session_scope() as session:
        item = questions_repository.find_by_source_id(session, source_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return item
