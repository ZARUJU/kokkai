from sqlalchemy import text

from kokkai.db.base import Base
from kokkai.db.engine import engine
from kokkai.settings import settings

# Import model modules so SQLAlchemy registers their tables on Base.metadata.
from kokkai.models import meeting_record  # noqa: F401
from kokkai.models import bill  # noqa: F401
from kokkai.models import diet_session  # noqa: F401
from kokkai.models import question  # noqa: F401


def create_all() -> None:
    Base.metadata.create_all(bind=engine)
    _apply_sqlite_compat_migrations()


def _apply_sqlite_compat_migrations() -> None:
    if not settings.database_url.startswith("sqlite:///"):
        return

    with engine.begin() as conn:
        bills_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(bills)"))}
        if bills_cols and "canonical_key" not in bills_cols:
            conn.execute(text("ALTER TABLE bills ADD COLUMN canonical_key VARCHAR"))

        conn.execute(
            text(
                "UPDATE bills SET canonical_key = "
                "CAST(submitted_session_number AS VARCHAR) || ':' || category || ':' || CAST(number AS VARCHAR) "
                "WHERE number IS NOT NULL AND (canonical_key IS NULL OR canonical_key = '')"
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_bills_canonical_key ON bills (canonical_key)"))

        listing_cols = conn.execute(text("PRAGMA table_info(bill_listing_sessions)")).fetchall()
        if listing_cols:
            conn.execute(
                text(
                    "INSERT OR IGNORE INTO bill_listing_sessions "
                    "(bill_source_id, session_number, status, source_url, fetched_at) "
                    "SELECT source_id, session_number, status, source_url, fetched_at FROM bills"
                )
            )

        question_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(questions)"))}
        if question_cols:
            if "question_text" not in question_cols:
                conn.execute(text("ALTER TABLE questions ADD COLUMN question_text TEXT"))
            if "answer_text" not in question_cols:
                conn.execute(text("ALTER TABLE questions ADD COLUMN answer_text TEXT"))

        meeting_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(meeting_records)"))}
        if meeting_cols and "bill_source_ids_json" not in meeting_cols:
            conn.execute(
                text(
                    "ALTER TABLE meeting_records ADD COLUMN bill_source_ids_json TEXT "
                    "NOT NULL DEFAULT '[]'"
                )
            )
