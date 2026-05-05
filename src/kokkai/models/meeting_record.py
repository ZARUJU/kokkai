from dataclasses import dataclass
from datetime import date
from datetime import datetime

from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from kokkai.db.base import Base


@dataclass(frozen=True)
class MeetingRecord:
    issue_id: str
    session: int
    name_of_house: str
    name_of_meeting: str
    issue: str
    meeting_date: date
    closing: str | None
    image_kind: str | None
    search_object: int | None
    meeting_url: str | None
    pdf_url: str | None
    meeting_start_hhmm: str | None
    meeting_end_hhmm: str | None
    header_info_text: str | None


@dataclass(frozen=True)
class MeetingSpeech:
    speech_id: str
    issue_id: str
    speech_order: int
    speaker: str | None
    speaker_yomi: str | None
    speaker_group: str | None
    speaker_position: str | None
    speaker_role: str | None
    speech: str | None
    start_page: int | None
    speech_url: str | None
    record_create_time: datetime | None
    record_update_time: datetime | None


@dataclass(frozen=True)
class MeetingTopic:
    source_id: str
    issue_id: str
    topic_order: int
    label: str
    bill_source_ids: tuple[str, ...]


class MeetingRecordModel(Base):
    __tablename__ = "meeting_records"

    issue_id: Mapped[str] = mapped_column(String, primary_key=True)
    session: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name_of_house: Mapped[str] = mapped_column(String, nullable=False)
    name_of_meeting: Mapped[str] = mapped_column(String, nullable=False, index=True)
    issue: Mapped[str] = mapped_column(String, nullable=False)
    meeting_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    closing: Mapped[str | None] = mapped_column(String)
    image_kind: Mapped[str | None] = mapped_column(String)
    search_object: Mapped[int | None] = mapped_column(Integer)
    meeting_url: Mapped[str | None] = mapped_column(String)
    pdf_url: Mapped[str | None] = mapped_column(String)
    meeting_start_hhmm: Mapped[str | None] = mapped_column(String)
    meeting_end_hhmm: Mapped[str | None] = mapped_column(String)
    header_info_text: Mapped[str | None] = mapped_column(Text)
    speakers_json: Mapped[str] = mapped_column(Text, nullable=False)
    bill_source_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    source_url: Mapped[str] = mapped_column(String, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MeetingSpeechModel(Base):
    __tablename__ = "meeting_speeches"

    speech_id: Mapped[str] = mapped_column(String, primary_key=True)
    issue_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    speech_order: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str | None] = mapped_column(String)
    speaker_yomi: Mapped[str | None] = mapped_column(String)
    speaker_group: Mapped[str | None] = mapped_column(String)
    speaker_position: Mapped[str | None] = mapped_column(String)
    speaker_role: Mapped[str | None] = mapped_column(String)
    speech: Mapped[str | None] = mapped_column(Text)
    start_page: Mapped[int | None] = mapped_column(Integer)
    speech_url: Mapped[str | None] = mapped_column(String)
    record_create_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    record_update_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MeetingTopicModel(Base):
    __tablename__ = "meeting_topics"

    source_id: Mapped[str] = mapped_column(String, primary_key=True)
    issue_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    topic_order: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    bill_source_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
