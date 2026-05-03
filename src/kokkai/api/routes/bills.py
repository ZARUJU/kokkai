from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Query

from kokkai.db.engine import session_scope
from kokkai.repositories import bills


router = APIRouter(prefix="/bills", tags=["bills"])


@router.get("")
def list_bills(
    category: str | None = Query(default=None, description="議案種別。例: 衆法, 参法, 閣法, 予算, 条約"),
) -> list[dict[str, object]]:
    """全会期をまたいだ議案の一覧。国会回次で絞る場合は GET /diet-sessions/{number}/bills を使う。"""
    with session_scope() as session:
        return bills.list_all(session, session_number=None, category=category)


@router.get("/{source_id}")
def get_bill(source_id: str) -> dict[str, object]:
    with session_scope() as db_session:
        bill = bills.find_by_source_id_with_progress(db_session, source_id)

    if bill is None:
        raise HTTPException(status_code=404, detail="Bill not found")

    return bill


@router.get("/{source_id}/progress")
def get_bill_progress(source_id: str) -> dict[str, object]:
    with session_scope() as session:
        bill = bills.find_by_source_id(session, source_id)
        if bill is None:
            raise HTTPException(status_code=404, detail="Bill not found")

        return bills.get_structured_progress(session, source_id)


@router.get("/{source_id}/texts")
def get_bill_texts(source_id: str) -> list[dict[str, object]]:
    with session_scope() as session:
        bill = bills.find_by_source_id(session, source_id)
        if bill is None:
            raise HTTPException(status_code=404, detail="Bill not found")

        return bills.list_text_documents(session, source_id)
