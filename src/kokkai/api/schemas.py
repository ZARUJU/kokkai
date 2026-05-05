"""OpenAPI 用のレスポンススキーマ（リポジトリの dict 形と一致）。"""

from __future__ import annotations

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class HealthOut(BaseModel):
    status: str


class DietSessionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: int
    session_type: str
    start_date: str | None
    end_date: str | None
    end_note: str | None
    total_days: int | None
    statutory_days: int | None
    extension_days: int | None
    source_url: str
    fetched_at: str


class BillListingSessionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_number: int
    status: str
    source_url: str
    fetched_at: str


class BillSummaryOut(BaseModel):
    """一覧・詳細ヘッダ共通の議案ボディ（詳細は別フィールドで拡張）。"""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    session_number: int
    submitted_session_number: int
    category: str
    canonical_key: str | None
    number: int | None
    title: str
    status: str
    progress_url: str | None
    text_url: str | None
    source_url: str
    fetched_at: str
    listing_sessions: list[BillListingSessionOut] = Field(default_factory=list)


class SubmitterSummaryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    representative: str | None
    count: int | None


class DateDetailOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str | None = None
    committee: str | None = None
    result: str | None = None
    law_number: str | None = None


class HouseOfRepresentativesProgressOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preliminary_received_date: str | None
    preliminary_referral: DateDetailOut
    received_date: str | None
    referral: DateDetailOut
    committee_result: DateDetailOut
    plenary_result: DateDetailOut
    vote_attitudes: list[str]
    supporting_groups: list[str]
    opposing_groups: list[str]


class HouseOfCouncillorsProgressOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preliminary_received_date: str | None
    preliminary_referral: DateDetailOut
    received_date: str | None
    referral: DateDetailOut
    committee_result: DateDetailOut
    plenary_result: DateDetailOut


class BillProgressOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bill_type: str | None
    submit_session: int | None
    bill_number: int | None
    title: str | None
    submitter: SubmitterSummaryOut
    submitter_groups: list[str]
    submitters: list[str]
    supporters: list[str]
    house_of_representatives: HouseOfRepresentativesProgressOut
    house_of_councillors: HouseOfCouncillorsProgressOut
    promulgation: DateDetailOut


class BillDetailOut(BillSummaryOut):
    progress: BillProgressOut
    related_bill_source_ids: list[str]


class BillTextDocumentOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    bill_source_id: str
    item_order: int
    label: str
    document_url: str
    content_text: str | None
    source_url: str
    fetched_at: str


class QuestionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
    source_url: str
    fetched_at: str


class MeetingRecordListOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issue_id: str
    session: int
    name_of_house: str
    name_of_meeting: str
    issue: str
    meeting_date: str
    closing: str | None
    image_kind: str | None
    search_object: int | None
    meeting_url: str | None
    pdf_url: str | None
    meeting_start_hhmm: str | None
    meeting_end_hhmm: str | None
    speakers: list[str]
    bill_source_ids: list[str]
    source_url: str
    fetched_at: str


class MeetingTopicOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    issue_id: str
    topic_order: int
    label: str


class MeetingRecordDetailOut(MeetingRecordListOut):
    header_info_text: str | None
    topics: list[MeetingTopicOut]
    speech_count: int


class MeetingSpeechOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
    record_create_time: str | None
    record_update_time: str | None
