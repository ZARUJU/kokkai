from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Query

from kokkai.api.schemas import BillDetailOut
from kokkai.api.schemas import BillProgressOut
from kokkai.api.schemas import BillSummaryOut
from kokkai.api.schemas import BillTextDocumentOut
from kokkai.db.engine import session_scope
from kokkai.repositories import bills


router = APIRouter(prefix="/bills", tags=["bills"])


@router.get("", response_model=list[BillSummaryOut])
def list_bills(
    category: str | None = Query(default=None, description="議案種別。例: 衆法, 参法, 閣法, 予算, 条約"),
    person_full_name: str | None = Query(
        default=None,
        description="議案情報の提出者・賛成者などに登場する人物のフルネーム（空白除去後の完全一致）",
    ),
) -> list[BillSummaryOut]:
    """全会期をまたいだ議案の一覧。国会回次で絞る場合は GET /diet-sessions/{number}/bills を使う。"""
    with session_scope() as session:
        return bills.list_all(
            session,
            session_number=None,
            category=category,
            person_full_name=person_full_name,
        )


@router.get("/{source_id}", response_model=BillDetailOut)
def get_bill(source_id: str) -> BillDetailOut:
    with session_scope() as db_session:
        bill = bills.find_by_source_id_with_progress(db_session, source_id)

    if bill is None:
        raise HTTPException(status_code=404, detail="Bill not found")

    return bill


@router.get("/{source_id}/progress", response_model=BillProgressOut)
def get_bill_progress(source_id: str) -> BillProgressOut:
    with session_scope() as session:
        bill = bills.find_by_source_id(session, source_id)
        if bill is None:
            raise HTTPException(status_code=404, detail="Bill not found")

        return bills.get_structured_progress(session, source_id)


@router.get("/{source_id}/texts", response_model=list[BillTextDocumentOut])
def get_bill_texts(source_id: str) -> list[BillTextDocumentOut]:
    with session_scope() as session:
        bill = bills.find_by_source_id(session, source_id)
        if bill is None:
            raise HTTPException(status_code=404, detail="Bill not found")

        return bills.list_text_documents(session, source_id)
