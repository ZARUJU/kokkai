from datetime import UTC
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from kokkai.models.diet_session import DietSession
from kokkai.models.diet_session import DietSessionModel


def upsert_many(session: Session, sessions: list[DietSession], source_url: str) -> None:
    if not sessions:
        return

    fetched_at = datetime.now(UTC)
    values = [
        {
            "number": diet_session.number,
            "session_type": diet_session.session_type,
            "start_date": diet_session.start_date,
            "end_date": diet_session.end_date,
            "end_note": diet_session.end_note,
            "total_days": diet_session.total_days,
            "statutory_days": diet_session.statutory_days,
            "extension_days": diet_session.extension_days,
            "source_url": source_url,
            "fetched_at": fetched_at,
        }
        for diet_session in sessions
    ]

    statement = insert(DietSessionModel).values(values)
    excluded = statement.excluded
    statement = statement.on_conflict_do_update(
        index_elements=[DietSessionModel.number],
        set_={
            "session_type": excluded.session_type,
            "start_date": excluded.start_date,
            "end_date": excluded.end_date,
            "end_note": excluded.end_note,
            "total_days": excluded.total_days,
            "statutory_days": excluded.statutory_days,
            "extension_days": excluded.extension_days,
            "source_url": excluded.source_url,
            "fetched_at": excluded.fetched_at,
        },
    )
    session.execute(statement)


def latest_session_numbers(session: Session, limit: int = 2) -> list[int]:
    rows = session.scalars(
        select(DietSessionModel.number).order_by(DietSessionModel.number.desc()).limit(limit)
    ).all()
    return [int(n) for n in rows]


def list_all(session: Session) -> list[dict[str, object]]:
    rows = session.scalars(select(DietSessionModel).order_by(DietSessionModel.number.desc())).all()
    return [to_dict(row) for row in rows]


def find_by_number(session: Session, number: int) -> dict[str, object] | None:
    row = session.get(DietSessionModel, number)
    return to_dict(row) if row else None


def to_dict(row: DietSessionModel) -> dict[str, object]:
    fetched_at = row.fetched_at
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=UTC)

    return {
        "number": row.number,
        "session_type": row.session_type,
        "start_date": row.start_date.isoformat() if row.start_date else None,
        "end_date": row.end_date.isoformat() if row.end_date else None,
        "end_note": row.end_note,
        "total_days": row.total_days,
        "statutory_days": row.statutory_days,
        "extension_days": row.extension_days,
        "source_url": row.source_url,
        "fetched_at": fetched_at.isoformat(),
    }
