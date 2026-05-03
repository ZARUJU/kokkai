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
class Bill:
    source_id: str
    session_number: int
    submitted_session_number: int
    category: str
    number: int | None
    title: str
    status: str
    progress_url: str | None
    text_url: str | None


class BillModel(Base):
    __tablename__ = "bills"

    source_id: Mapped[str] = mapped_column(String, primary_key=True)
    session_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    submitted_session_number: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False, index=True)
    number: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    progress_url: Mapped[str | None] = mapped_column(String)
    text_url: Mapped[str | None] = mapped_column(String)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


@dataclass(frozen=True)
class BillProgressItem:
    source_id: str
    bill_source_id: str
    item_order: int
    name: str
    value: str | None


class BillProgressItemModel(Base):
    __tablename__ = "bill_progress_items"

    source_id: Mapped[str] = mapped_column(String, primary_key=True)
    bill_source_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    item_order: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


@dataclass(frozen=True)
class BillTextDocument:
    source_id: str
    bill_source_id: str
    item_order: int
    label: str
    document_url: str
    content_text: str | None


class BillTextDocumentModel(Base):
    __tablename__ = "bill_text_documents"

    source_id: Mapped[str] = mapped_column(String, primary_key=True)
    bill_source_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    item_order: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    document_url: Mapped[str] = mapped_column(String, nullable=False)
    content_text: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(String, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
