from datetime import UTC
from datetime import datetime
import re

from sqlalchemy import delete
from sqlalchemy import exists
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from kokkai.models.bill import Bill
from kokkai.models.bill import BillListingSessionModel
from kokkai.models.bill import BillModel
from kokkai.models.bill import BillProgressItem
from kokkai.models.bill import canonical_key_for_bill
from kokkai.models.bill import BillProgressItemModel
from kokkai.models.bill import BillTextDocument
from kokkai.models.bill import BillTextDocumentModel
from kokkai.ingest.parsers.common import compact_person_full_name


_PERSON_MATCH_PROGRESS_NAMES: frozenset[str] = frozenset(
    {
        "議案提出者一覧",
        "議案提出の賛成者",
        "議案提出者",
    }
)


def _bill_source_ids_for_person_compact(session: Session, norm: str) -> set[str]:
    if not norm:
        return set()
    rows = session.scalars(
        select(BillProgressItemModel).where(
            BillProgressItemModel.name.in_(_PERSON_MATCH_PROGRESS_NAMES),
            BillProgressItemModel.value.isnot(None),
        )
    ).all()
    out: set[str] = set()
    for row in rows:
        candidates: list[str] = []
        if row.name in ("議案提出者一覧", "議案提出の賛成者"):
            candidates.extend(_split_person_values(row.value))
        elif row.name == "議案提出者":
            summary = _parse_submitter_summary(row.value, [])
            rep = summary.get("representative")
            if isinstance(rep, str):
                candidates.append(rep)
        for person in candidates:
            if compact_person_full_name(person) == norm:
                out.add(row.bill_source_id)
                break
    return out


def upsert_many(session: Session, bills: list[Bill], source_url: str) -> None:
    if not bills:
        return

    fetched_at = datetime.now(UTC)
    values = [
        {
            "source_id": bill.source_id,
            "session_number": bill.session_number,
            "submitted_session_number": bill.submitted_session_number,
            "category": bill.category,
            "canonical_key": canonical_key_for_bill(
                bill.submitted_session_number,
                bill.category,
                bill.number,
            ),
            "number": bill.number,
            "title": bill.title,
            "status": bill.status,
            "progress_url": bill.progress_url,
            "text_url": bill.text_url,
            "source_url": source_url,
            "fetched_at": fetched_at,
        }
        for bill in bills
    ]

    statement = insert(BillModel).values(values)
    excluded = statement.excluded
    statement = statement.on_conflict_do_update(
        index_elements=[BillModel.source_id],
        set_={
            "session_number": excluded.session_number,
            "submitted_session_number": excluded.submitted_session_number,
            "category": excluded.category,
            "canonical_key": excluded.canonical_key,
            "number": excluded.number,
            "title": excluded.title,
            "status": excluded.status,
            "progress_url": excluded.progress_url,
            "text_url": excluded.text_url,
            "source_url": excluded.source_url,
            "fetched_at": excluded.fetched_at,
        },
    )
    session.execute(statement)

    listing_values = [
        {
            "bill_source_id": bill.source_id,
            "session_number": bill.session_number,
            "status": bill.status,
            "source_url": source_url,
            "fetched_at": fetched_at,
        }
        for bill in bills
    ]
    listing_stmt = insert(BillListingSessionModel).values(listing_values)
    listing_excluded = listing_stmt.excluded
    listing_stmt = listing_stmt.on_conflict_do_update(
        index_elements=[
            BillListingSessionModel.bill_source_id,
            BillListingSessionModel.session_number,
        ],
        set_={
            "status": listing_excluded.status,
            "source_url": listing_excluded.source_url,
            "fetched_at": listing_excluded.fetched_at,
        },
    )
    session.execute(listing_stmt)


def list_all(
    session: Session,
    session_number: int | None = None,
    category: str | None = None,
    person_full_name: str | None = None,
) -> list[dict[str, object]]:
    statement = select(BillModel)
    if person_full_name and person_full_name.strip():
        norm = compact_person_full_name(person_full_name)
        if not norm:
            return []
        person_ids = _bill_source_ids_for_person_compact(session, norm)
        if not person_ids:
            return []
        statement = statement.where(BillModel.source_id.in_(person_ids))
    if session_number is not None:
        listed_in_session = exists(
            select(1).where(
                BillListingSessionModel.bill_source_id == BillModel.source_id,
                BillListingSessionModel.session_number == session_number,
            )
        )
        statement = statement.where(
            or_(
                listed_in_session,
                BillModel.session_number == session_number,
            )
        )
    if category is not None:
        statement = statement.where(BillModel.category == category)

    statement = statement.order_by(
        BillModel.session_number.desc(),
        BillModel.category,
        BillModel.number,
        BillModel.title,
    )
    rows = session.scalars(statement).all()
    out = [to_dict(row) for row in rows]
    _attach_listing_sessions(session, out)
    return out


def find_by_source_id(session: Session, source_id: str) -> dict[str, object] | None:
    row = session.get(BillModel, source_id)
    if row is None:
        return None
    bill = to_dict(row)
    _attach_listing_sessions(session, [bill])
    return bill


def find_by_source_id_with_progress(session: Session, source_id: str) -> dict[str, object] | None:
    bill = find_by_source_id(session, source_id)
    if bill is None:
        return None

    bill["progress"] = get_structured_progress(session, source_id)
    key = bill.get("canonical_key")
    bill["related_bill_source_ids"] = _list_related_source_ids(
        session,
        key if isinstance(key, str) else None,
        source_id,
    )
    return bill


def upsert_progress_items(
    session: Session,
    items: list[BillProgressItem],
    source_url: str,
    fetched_at: datetime | None = None,
) -> None:
    if not items:
        return

    fetched_at = fetched_at or datetime.now(UTC)
    values = [
        {
            "source_id": item.source_id,
            "bill_source_id": item.bill_source_id,
            "item_order": item.item_order,
            "name": item.name,
            "value": item.value,
            "source_url": source_url,
            "fetched_at": fetched_at,
        }
        for item in items
    ]

    statement = insert(BillProgressItemModel).values(values)
    excluded = statement.excluded
    statement = statement.on_conflict_do_update(
        index_elements=[BillProgressItemModel.source_id],
        set_={
            "bill_source_id": excluded.bill_source_id,
            "item_order": excluded.item_order,
            "name": excluded.name,
            "value": excluded.value,
            "source_url": excluded.source_url,
            "fetched_at": excluded.fetched_at,
        },
    )
    session.execute(statement)


def replace_progress_items(
    session: Session,
    bill_source_id: str,
    items: list[BillProgressItem],
    source_url: str,
) -> None:
    session.execute(delete(BillProgressItemModel).where(BillProgressItemModel.bill_source_id == bill_source_id))
    upsert_progress_items(session, items, source_url)


def upsert_text_documents(
    session: Session,
    documents: list[BillTextDocument],
    source_url: str,
    fetched_at: datetime | None = None,
) -> None:
    if not documents:
        return

    fetched_at = fetched_at or datetime.now(UTC)
    values = [
        {
            "source_id": document.source_id,
            "bill_source_id": document.bill_source_id,
            "item_order": document.item_order,
            "label": document.label,
            "document_url": document.document_url,
            "content_text": document.content_text,
            "source_url": source_url,
            "fetched_at": fetched_at,
        }
        for document in documents
    ]

    statement = insert(BillTextDocumentModel).values(values)
    excluded = statement.excluded
    statement = statement.on_conflict_do_update(
        index_elements=[BillTextDocumentModel.source_id],
        set_={
            "bill_source_id": excluded.bill_source_id,
            "item_order": excluded.item_order,
            "label": excluded.label,
            "document_url": excluded.document_url,
            "content_text": excluded.content_text,
            "source_url": excluded.source_url,
            "fetched_at": excluded.fetched_at,
        },
    )
    session.execute(statement)


def replace_text_documents(
    session: Session,
    bill_source_id: str,
    documents: list[BillTextDocument],
    source_url: str,
) -> None:
    session.execute(delete(BillTextDocumentModel).where(BillTextDocumentModel.bill_source_id == bill_source_id))
    upsert_text_documents(session, documents, source_url)


def list_progress_items(session: Session, bill_source_id: str) -> list[dict[str, object]]:
    rows = session.scalars(
        select(BillProgressItemModel)
        .where(BillProgressItemModel.bill_source_id == bill_source_id)
        .order_by(BillProgressItemModel.item_order)
    ).all()
    return [progress_item_to_dict(row) for row in rows]


def get_structured_progress(session: Session, bill_source_id: str) -> dict[str, object]:
    rows = session.scalars(
        select(BillProgressItemModel)
        .where(BillProgressItemModel.bill_source_id == bill_source_id)
        .order_by(BillProgressItemModel.item_order)
    ).all()
    values = {row.name: _clean_text(row.value) for row in rows}
    submitters = _split_person_values(values.get("議案提出者一覧"))

    return {
        "bill_type": values.get("議案種類"),
        "submit_session": _parse_int_value(values.get("議案提出回次")),
        "bill_number": _parse_int_value(values.get("議案番号")),
        "title": values.get("議案件名"),
        "submitter": _parse_submitter_summary(values.get("議案提出者"), submitters),
        "submitter_groups": _split_semicolon_values(values.get("議案提出会派")),
        "submitters": submitters,
        "supporters": _split_person_values(values.get("議案提出の賛成者")),
        "house_of_representatives": {
            "preliminary_received_date": _parse_date_value(values.get("衆議院予備審査議案受理年月日")),
            "preliminary_referral": _parse_date_detail(values.get("衆議院予備付託年月日／衆議院予備付託委員会"), "committee"),
            "received_date": _parse_date_value(values.get("衆議院議案受理年月日")),
            "referral": _parse_date_detail(values.get("衆議院付託年月日／衆議院付託委員会"), "committee"),
            "committee_result": _parse_date_detail(values.get("衆議院審査終了年月日／衆議院審査結果"), "result"),
            "plenary_result": _parse_date_detail(values.get("衆議院審議終了年月日／衆議院審議結果"), "result"),
            "vote_attitudes": _split_semicolon_values(values.get("衆議院審議時会派態度")),
            "supporting_groups": _split_semicolon_values(values.get("衆議院審議時賛成会派")),
            "opposing_groups": _split_semicolon_values(values.get("衆議院審議時反対会派")),
        },
        "house_of_councillors": {
            "preliminary_received_date": _parse_date_value(values.get("参議院予備審査議案受理年月日")),
            "preliminary_referral": _parse_date_detail(values.get("参議院予備付託年月日／参議院予備付託委員会"), "committee"),
            "received_date": _parse_date_value(values.get("参議院議案受理年月日")),
            "referral": _parse_date_detail(values.get("参議院付託年月日／参議院付託委員会"), "committee"),
            "committee_result": _parse_date_detail(values.get("参議院審査終了年月日／参議院審査結果"), "result"),
            "plenary_result": _parse_date_detail(values.get("参議院審議終了年月日／参議院審議結果"), "result"),
        },
        "promulgation": _parse_date_detail(values.get("公布年月日／法律番号"), "law_number"),
    }


def list_text_documents(session: Session, bill_source_id: str) -> list[dict[str, object]]:
    rows = session.scalars(
        select(BillTextDocumentModel)
        .where(BillTextDocumentModel.bill_source_id == bill_source_id)
        .order_by(BillTextDocumentModel.item_order)
    ).all()
    return [text_document_to_dict(row) for row in rows]


def to_dict(row: BillModel) -> dict[str, object]:
    fetched_at = row.fetched_at
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=UTC)

    return {
        "source_id": row.source_id,
        "session_number": row.session_number,
        "submitted_session_number": row.submitted_session_number,
        "category": row.category,
        "canonical_key": row.canonical_key,
        "number": row.number,
        "title": row.title,
        "status": row.status,
        "progress_url": row.progress_url,
        "text_url": row.text_url,
        "source_url": row.source_url,
        "fetched_at": fetched_at.isoformat(),
    }


def listing_session_to_dict(row: BillListingSessionModel) -> dict[str, object]:
    fetched_at = row.fetched_at
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=UTC)
    return {
        "session_number": row.session_number,
        "status": row.status,
        "source_url": row.source_url,
        "fetched_at": fetched_at.isoformat(),
    }


def _list_related_source_ids(
    session: Session,
    canonical_key: str | None,
    exclude_source_id: str,
) -> list[str]:
    if not canonical_key:
        return []
    rows = session.scalars(
        select(BillModel.source_id)
        .where(
            BillModel.canonical_key == canonical_key,
            BillModel.source_id != exclude_source_id,
        )
        .order_by(BillModel.source_id)
    ).all()
    return list(rows)


def _attach_listing_sessions(session: Session, bill_dicts: list[dict[str, object]]) -> None:
    if not bill_dicts:
        return

    ids = [str(d["source_id"]) for d in bill_dicts]
    rows = session.scalars(
        select(BillListingSessionModel)
        .where(BillListingSessionModel.bill_source_id.in_(ids))
        .order_by(
            BillListingSessionModel.bill_source_id,
            BillListingSessionModel.session_number,
        )
    ).all()
    by_bill: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        by_bill.setdefault(row.bill_source_id, []).append(listing_session_to_dict(row))

    for d in bill_dicts:
        sid = str(d["source_id"])
        entries = by_bill.get(sid)
        if not entries:
            entries = [
                {
                    "session_number": d["session_number"],
                    "status": d["status"],
                    "source_url": d["source_url"],
                    "fetched_at": d["fetched_at"],
                }
            ]
        d["listing_sessions"] = entries


def progress_item_to_dict(row: BillProgressItemModel) -> dict[str, object]:
    fetched_at = row.fetched_at
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=UTC)

    return {
        "source_id": row.source_id,
        "bill_source_id": row.bill_source_id,
        "item_order": row.item_order,
        "name": row.name,
        "value": row.value,
        "source_url": row.source_url,
        "fetched_at": fetched_at.isoformat(),
    }


def text_document_to_dict(row: BillTextDocumentModel) -> dict[str, object]:
    fetched_at = row.fetched_at
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=UTC)

    return {
        "source_id": row.source_id,
        "bill_source_id": row.bill_source_id,
        "item_order": row.item_order,
        "label": row.label,
        "document_url": row.document_url,
        "content_text": _clean_text_document_content(row.content_text),
        "source_url": row.source_url,
        "fetched_at": fetched_at.isoformat(),
    }


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None

    text = re.sub(r"\s+", " ", value.replace("\u3000", " ")).strip()
    return text if text and text != "／" else None


def _parse_int_value(value: str | None) -> int | None:
    text = _clean_text(value)
    return int(text) if text and re.fullmatch(r"\d+", text) else None


def _parse_date_detail(value: str | None, detail_key: str) -> dict[str, str | None]:
    left, right = _split_slash_value(value)
    return {
        "date": _parse_date_value(left),
        detail_key: _empty_to_none(right),
    }


def _split_slash_value(value: str | None) -> tuple[str | None, str | None]:
    text = _clean_text(value)
    if text is None:
        return None, None

    left, separator, right = text.partition("／")
    if not separator:
        return text, None
    return _empty_to_none(left), _empty_to_none(right)


def _parse_date_value(value: str | None) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None

    text = re.sub(r"(令和|平成|昭和)\s+", r"\1", text)
    match = re.search(r"(令和|平成|昭和)(元|\d+)年\s*(\d+)月\s*(\d+)日", text)
    if not match:
        return None

    era, era_year, month, day = match.groups()
    year = 1 if era_year == "元" else int(era_year)
    western_year = {"令和": 2018, "平成": 1988, "昭和": 1925}[era] + year
    return f"{western_year:04d}/{int(month):02d}/{int(day):02d}"


def _split_semicolon_values(value: str | None) -> list[str]:
    text = _clean_text(value)
    if text is None:
        return []
    return [part for part in (_empty_to_none(part) for part in text.split(";")) if part is not None]


def _split_person_values(value: str | None) -> list[str]:
    return [person for person in (_clean_person_text(part) for part in _split_semicolon_values(value)) if person is not None]


def _parse_submitter_summary(raw_value: str | None, submitters: list[str]) -> dict[str, object]:
    text = _clean_text(raw_value)
    if text is None:
        representative = submitters[0] if submitters else None
        count = len(submitters) if submitters else None
        return {"representative": representative, "count": count}

    match = re.fullmatch(r"(.+?)(?:君|氏|さん|殿|様)?外([一二三四五六七八九十百千万\d]+)名", text)
    if match:
        representative = _clean_person_text(match.group(1))
        outside_count = _parse_japanese_count(match.group(2))
        inferred_count = outside_count + 1 if outside_count is not None else None
    else:
        representative = _clean_person_text(text)
        inferred_count = 1 if representative else None

    return {
        "representative": representative,
        "count": len(submitters) if submitters else inferred_count,
    }


def _clean_person_text(value: str | None) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None

    text = re.sub(r"(君|氏|さん|殿|様)(?=外[一二三四五六七八九十百千万\d]+名|$|;)", "", text)
    text = re.sub(r"(君|氏|さん|殿|様)", "", text)
    text = re.sub(r"外[一二三四五六七八九十百千万\d]+名$", "", text)
    return _empty_to_none(text)


def _parse_japanese_count(value: str) -> int | None:
    if re.fullmatch(r"\d+", value):
        return int(value)

    digits = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if value in digits:
        return digits[value]
    if value == "十":
        return 10
    if value.startswith("十") and len(value) == 2:
        return 10 + digits.get(value[1], 0)
    if value.endswith("十") and len(value) == 2:
        return digits.get(value[0], 0) * 10
    if "十" in value and len(value) == 3:
        return digits.get(value[0], 0) * 10 + digits.get(value[2], 0)
    return None


def _empty_to_none(value: str | None) -> str | None:
    text = _clean_text(value)
    return text if text else None


def _clean_text_document_content(value: str | None) -> str | None:
    if value is None:
        return None

    text = value.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    text = re.sub(r"[ \t\u3000]+", " ", text).strip()
    text = _strip_site_footer(text).strip()
    if not text:
        return None

    # Older ingested rows collapsed every paragraph into one line. Add conservative
    # breaks around common bill-document headings so API output remains readable.
    if "\n" not in text:
        text = re.sub(r"\s+(附 則|理 由)\s+", r"\n\1\n", text)
        text = re.sub(r"\s+(第[一二三四五六七八九十百千万\d]+条)", r"\n\1", text)
        text = re.sub(r"\s+(第一|第二|第三|第四|第五|第六|第七|第八|第九|第十)\s+", r"\n\1 ", text)
        text = re.sub(r"\s+([一二三四五六七八九十])\s+", r"\n\1 ", text)
        text = re.sub(r"\s+([０-９\d]+)\s+", r"\n\1 ", text)
        text = re.sub(r"\s+(（[^）]+）)", r"\n\1", text)

    lines = [_clean_text(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def _strip_site_footer(value: str) -> str:
    return re.sub(
        r"\s*ホームページについて\s+Webアクセシビリティ\s+リンク・著作権等について\s+お問い合わせ\s+衆議院\s+〒100-0014.*$",
        "",
        value,
        flags=re.DOTALL,
    )
