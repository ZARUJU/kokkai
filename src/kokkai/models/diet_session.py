from dataclasses import dataclass
from datetime import date
from datetime import datetime

from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from kokkai.db.base import Base


@dataclass(frozen=True)
class DietSession:
    number: int
    session_type: str
    start_date: date | None
    end_date: date | None
    end_note: str | None
    total_days: int | None
    statutory_days: int | None
    extension_days: int | None


class DietSessionModel(Base):
    __tablename__ = "diet_sessions"

    number: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_type: Mapped[str] = mapped_column(String, nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    end_note: Mapped[str | None] = mapped_column(String)
    total_days: Mapped[int | None] = mapped_column(Integer)
    statutory_days: Mapped[int | None] = mapped_column(Integer)
    extension_days: Mapped[int | None] = mapped_column(Integer)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
