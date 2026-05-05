"""国会会議録 API 応答のパースと、議事冒頭（会議録情報）からのメタデータ抽出。"""

from __future__ import annotations

import re
from datetime import date
from datetime import datetime
from typing import Any

from kokkai.ingest.parsers.common import clean_kokkai_speaker_name
from kokkai.ingest.parsers.common import normalize_spaces
from kokkai.ingest.parsers.common import parse_japanese_date
from kokkai.models.meeting_record import MeetingRecord
from kokkai.models.meeting_record import MeetingSpeech
from kokkai.models.meeting_record import MeetingTopic

_DIGITS = {
    "〇": 0,
    "零": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


def _to_ascii_digits(value: str) -> str:
    return value.translate(str.maketrans("０１２３４５６７８９", "0123456789"))


def _parse_kanji_uint(value: str) -> int | None:
    text = normalize_spaces(_to_ascii_digits(value))
    if not text:
        return None
    if re.fullmatch(r"\d+", text):
        return int(text)
    if len(text) == 1:
        digit = _DIGITS.get(text)
        return digit if digit is not None else None
    if text == "十":
        return 10
    if "十" in text:
        left, _, right = text.partition("十")
        if left:
            tens = _DIGITS.get(left)
            if tens is None:
                return None
        else:
            tens = 1
        ones = _DIGITS.get(right, 0) if right else 0
        return tens * 10 + ones
    return None


def _to_24h_hour(period: str, hour: int) -> int:
    if period == "午前":
        return 0 if hour == 12 else hour
    if period == "午後":
        return 12 if hour == 12 else hour + 12
    raise ValueError(period)


def _match_to_hhmm(match: re.Match[str]) -> str:
    period = match.group("period")
    hour_raw = match.group("hour")
    minute_raw = match.group("minute")
    hour = _parse_kanji_uint(hour_raw)
    if hour is None:
        raise ValueError(hour_raw)
    minute = _parse_kanji_uint(minute_raw) if minute_raw else 0
    if minute is None:
        raise ValueError(minute_raw)
    hour_24 = _to_24h_hour(period, hour)
    return f"{hour_24:02d}:{minute:02d}"


_TIME_ANCHOR_PATTERN = re.compile(
    r"(?P<period>午前|午後)(?P<hour>[〇零一二三四五六七八九十\d０-９]+)時"
    r"(?:(?P<minute>[〇零一二三四五六七八九十\d０-９]+)分)?"
    r"(?P<kind>開議|閉会|散会|延会)"
)


def extract_start_end_hhmm(header: str) -> tuple[str | None, str | None]:
    starts: list[str] = []
    ends: list[str] = []
    for match in _TIME_ANCHOR_PATTERN.finditer(header):
        kind = match.group("kind")
        try:
            hhmm = _match_to_hhmm(match)
        except ValueError:
            continue
        if kind == "開議":
            starts.append(hhmm)
        elif kind in ("閉会", "散会", "延会"):
            ends.append(hhmm)
    start = starts[0] if starts else None
    end = ends[-1] if ends else None
    return start, end


def _is_timekeeper_agenda_line(body: str) -> bool:
    """午前/午後…時…分?開議|閉会|散会|延会 だけの行（議題ではない）。"""
    text = normalize_spaces(body)
    return bool(text and _TIME_ANCHOR_PATTERN.fullmatch(text))


def extract_closing_hhmm_from_text(text: str | None) -> str | None:
    """本文中の閉会・散会・延会に付いた時刻のうち、最後のものを HH:MM で返す。"""
    if not text:
        return None
    ends: list[str] = []
    for match in _TIME_ANCHOR_PATTERN.finditer(text):
        kind = match.group("kind")
        if kind not in ("閉会", "散会", "延会"):
            continue
        try:
            ends.append(_match_to_hhmm(match))
        except ValueError:
            continue
    return ends[-1] if ends else None


_TOPIC_LINE_PATTERN = re.compile(
    r"^[　 \t]*([一二三四五六七八九十百千\d０-９]+)　(.+)$",
)


def _is_separator_only_topic_body(body: str) -> bool:
    """罫線・ダッシュ類だけの行（議題ではない）。"""
    t = normalize_spaces(body).strip()
    if len(t) < 2:
        return False
    return bool(
        re.fullmatch(r"[-\s.ー─━－―═・〱〲\u2010-\u2015\u2500-\u257F]+", t)
    )


def _is_paren_only_topic_stub(body: str) -> bool:
    """本文全体が一対の全角括弧だけ（所管区分等の小見出しで議題本体ではない）。"""
    t = normalize_spaces(body).strip()
    return bool(re.fullmatch(r"（[^）]*）", t)) and len(t) > 2


def extract_topic_labels(header: str) -> list[str]:
    topics: list[str] = []
    seen: set[str] = set()
    flag_block = False
    for raw_line in header.replace("\r\n", "\n").splitlines():
        line = raw_line.rstrip("\r")
        if "本日の会議に付した案件" in line:
            flag_block = True
            continue
        if line.strip().startswith("――――"):
            flag_block = False

        match = _TOPIC_LINE_PATTERN.match(line)
        if match:
            body = normalize_spaces(match.group(2))
            flag_block = False
        elif flag_block:
            loose = re.match(r"^[　 \t]+(\S.*)$", line)
            if not loose:
                continue
            body = normalize_spaces(loose.group(1))
        else:
            continue

        if len(body) < 4:
            continue
        if body in seen:
            continue
        if "議事日程" in body and "号" in body:
            continue
        if re.fullmatch(r"令和\d+年\d+月\d+日.*", body):
            continue
        if _is_timekeeper_agenda_line(body):
            continue
        if _is_separator_only_topic_body(body):
            continue
        if _is_paren_only_topic_stub(body):
            continue
        seen.add(body)
        topics.append(body)
    return topics


def _as_speech_list(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _parse_api_date(value: Any) -> date | None:
    """API の `date` は文字列 (YYYY-MM-DD)、数値 (YYYYMMDD)、datetime 文字列などで返ることがある。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, int):
        text = str(value)
        if len(text) == 8 and text.isdigit():
            try:
                return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
            except ValueError:
                return None
        return None
    text = str(value).strip()
    if not text:
        return None
    if "T" in text:
        text = text.split("T", 1)[0].strip()
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            pass
    if len(text) == 8 and text.isdigit():
        try:
            return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
        except ValueError:
            return None
    for sep in ("/", "."):
        if sep in text:
            parts = [p.strip() for p in text.replace(".", sep).split(sep) if p.strip()]
            if len(parts) == 3 and all(p.isdigit() for p in parts):
                try:
                    y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
                    return date(y, m, d)
                except ValueError:
                    break
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _parse_api_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and re.fullmatch(r"-?\d+", value):
        return int(value)
    return None


def _header_info_text(speeches: list[dict[str, Any]]) -> str | None:
    for speech in speeches:
        if str(speech.get("speaker") or "") == "会議録情報":
            raw = speech.get("speech")
            if isinstance(raw, str) and raw.strip():
                return raw
    for speech in speeches:
        order = _coerce_int(speech.get("speechOrder"))
        if order == 0:
            raw = speech.get("speech")
            if isinstance(raw, str) and raw.strip():
                return raw
    return None


def extract_closing_hhmm_from_ordered_speeches(speeches: list[dict[str, Any]]) -> str | None:
    """発言順に全文を走査し、最後に現れる閉会・散会・延会の時刻を HH:MM で返す。"""
    ordered = sorted(speeches, key=lambda s: _coerce_int(s.get("speechOrder")) or 0)
    last_end: str | None = None
    for speech in ordered:
        raw = speech.get("speech")
        if not isinstance(raw, str) or not raw.strip():
            continue
        found = extract_closing_hhmm_from_text(raw)
        if found is not None:
            last_end = found
    return last_end


def parse_meeting_bundle(raw: dict[str, Any]) -> tuple[MeetingRecord, list[MeetingSpeech], list[str]]:
    speeches = _as_speech_list(raw.get("speechRecord"))
    header = _header_info_text(speeches)
    start_hhmm, end_hhmm = extract_start_end_hhmm(header or "")
    if end_hhmm is None:
        end_hhmm = extract_closing_hhmm_from_ordered_speeches(speeches)
    topics = extract_topic_labels(header or "") if header else []

    meeting_date = _parse_api_date(raw.get("date"))
    if meeting_date is None and header:
        meeting_date = parse_japanese_date(header)
    if meeting_date is None:
        raise ValueError("meetingRecord.date is missing or invalid")

    session_value = _coerce_int(raw.get("session"))
    if session_value is None:
        raise ValueError("meetingRecord.session is missing or invalid")

    record = MeetingRecord(
        issue_id=str(raw.get("issueID") or ""),
        session=session_value,
        name_of_house=str(raw.get("nameOfHouse") or ""),
        name_of_meeting=str(raw.get("nameOfMeeting") or ""),
        issue=str(raw.get("issue") or ""),
        meeting_date=meeting_date,
        closing=str(raw["closing"]) if raw.get("closing") is not None else None,
        image_kind=str(raw["imageKind"]) if raw.get("imageKind") is not None else None,
        search_object=_coerce_int(raw.get("searchObject")),
        meeting_url=str(raw["meetingURL"]) if raw.get("meetingURL") is not None else None,
        pdf_url=str(raw["pdfURL"]) if raw.get("pdfURL") is not None else None,
        meeting_start_hhmm=start_hhmm,
        meeting_end_hhmm=end_hhmm,
        header_info_text=header,
    )

    if not record.issue_id:
        raise ValueError("meetingRecord.issueID is missing")

    parsed_speeches: list[MeetingSpeech] = []
    for speech in speeches:
        speech_id = str(speech.get("speechID") or "")
        if not speech_id:
            continue
        parsed_speeches.append(
            MeetingSpeech(
                speech_id=speech_id,
                issue_id=record.issue_id,
                speech_order=int(_coerce_int(speech.get("speechOrder")) or 0),
                speaker=str(speech["speaker"]) if speech.get("speaker") is not None else None,
                speaker_yomi=str(speech["speakerYomi"]) if speech.get("speakerYomi") is not None else None,
                speaker_group=str(speech["speakerGroup"]) if speech.get("speakerGroup") is not None else None,
                speaker_position=str(speech["speakerPosition"]) if speech.get("speakerPosition") is not None else None,
                speaker_role=str(speech["speakerRole"]) if speech.get("speakerRole") is not None else None,
                speech=str(speech["speech"]) if speech.get("speech") is not None else None,
                start_page=_coerce_int(speech.get("startPage")),
                speech_url=str(speech["speechURL"]) if speech.get("speechURL") is not None else None,
                record_create_time=_parse_api_datetime(str(speech["createTime"])) if speech.get("createTime") else None,
                record_update_time=_parse_api_datetime(str(speech["updateTime"])) if speech.get("updateTime") else None,
            )
        )

    return record, parsed_speeches, topics


def build_topics(issue_id: str, labels: list[str]) -> list[MeetingTopic]:
    topics: list[MeetingTopic] = []
    for order, label in enumerate(labels):
        topics.append(
            MeetingTopic(
                source_id=f"{issue_id}:topic:{order}",
                issue_id=issue_id,
                topic_order=order,
                label=label,
            )
        )
    return topics


def build_speaker_names(speeches: list[MeetingSpeech]) -> list[str]:
    ordered = sorted(speeches, key=lambda s: s.speech_order)
    seen: set[str] = set()
    names: list[str] = []
    for sp in ordered:
        raw = (sp.speaker or "").strip()
        if not raw:
            continue
        clean = clean_kokkai_speaker_name(raw)
        if not clean:
            continue
        if clean in seen:
            continue
        seen.add(clean)
        names.append(clean)
    return names

