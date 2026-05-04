from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from kokkai.db.base import Base


@dataclass(frozen=True)
class Question:
    source_id: str
    chamber: str
    session_number: int
    number: int
    title: str
    submitter: str | None
    status: str | None
    details_url: str | None
    question_url: str | None
    answer_url: str | None
    question_text: str | None
    answer_text: str | None


class QuestionModel(Base):
    __tablename__ = "questions"

    source_id: Mapped[str] = mapped_column(String, primary_key=True)
    chamber: Mapped[str] = mapped_column(String, nullable=False, index=True)
    session_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    submitter: Mapped[str | None] = mapped_column(String)
    status: Mapped[str | None] = mapped_column(String)
    details_url: Mapped[str | None] = mapped_column(String)
    question_url: Mapped[str | None] = mapped_column(String)
    answer_url: Mapped[str | None] = mapped_column(String)
    question_text: Mapped[str | None] = mapped_column(Text)
    answer_text: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
