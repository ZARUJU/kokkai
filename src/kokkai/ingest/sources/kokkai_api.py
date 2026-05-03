"""国立国会図書館 国会会議録検索API クライアント。

利用規約: リクエスト間に数秒の間隔を空ける。
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from typing import Any
from urllib.parse import urlencode

from kokkai.ingest.http import fetch_text

SOURCE_NAME = "kokkai_ndl_api"
BASE_URL = "https://kokkai.ndl.go.jp/api"
REQUEST_INTERVAL_SEC = 2.5

_last_request_monotonic: float = 0.0


def _throttle() -> None:
    global _last_request_monotonic
    now = time.monotonic()
    elapsed = now - _last_request_monotonic
    if _last_request_monotonic and elapsed < REQUEST_INTERVAL_SEC:
        time.sleep(REQUEST_INTERVAL_SEC - elapsed)
    _last_request_monotonic = time.monotonic()


def fetch_meeting_list_page(params: dict[str, str | int]) -> dict[str, Any]:
    _throttle()
    query = dict(params)
    url = f"{BASE_URL}/meeting_list?{urlencode(query, safe='', encoding='utf-8')}"
    document = fetch_text(SOURCE_NAME, url)
    return json.loads(document.text)


def fetch_meeting_page(params: dict[str, str | int]) -> dict[str, Any]:
    _throttle()
    query = dict(params)
    url = f"{BASE_URL}/meeting?{urlencode(query, safe='', encoding='utf-8')}"
    document = fetch_text(SOURCE_NAME, url)
    return json.loads(document.text)


def ensure_meeting_list_response(payload: dict[str, Any]) -> None:
    if payload.get("meetingRecord") is not None:
        return
    message = payload.get("message")
    if message:
        raise RuntimeError(f"kokkai API error: {message}")
    raise RuntimeError("kokkai API error: unexpected meeting_list response")


def ensure_meeting_response(payload: dict[str, Any]) -> None:
    if payload.get("meetingRecord") is not None:
        return
    message = payload.get("message")
    if message:
        raise RuntimeError(f"kokkai API error: {message}")
    raise RuntimeError("kokkai API error: unexpected meeting response")


def iter_meeting_issue_ids(
    session_from: int,
    session_to: int,
    name_of_house: str | None = None,
) -> Iterator[str]:
    start_record = 1
    while True:
        params: dict[str, str | int] = {
            "sessionFrom": session_from,
            "sessionTo": session_to,
            "startRecord": start_record,
            "maximumRecords": 100,
            "recordPacking": "json",
        }
        if name_of_house:
            params["nameOfHouse"] = name_of_house

        payload = fetch_meeting_list_page(params)
        ensure_meeting_list_response(payload)
        records = payload.get("meetingRecord") or []
        if not isinstance(records, list) or not records:
            break

        for record in records:
            if isinstance(record, dict):
                issue_id = record.get("issueID")
                if issue_id:
                    yield str(issue_id)

        next_position = payload.get("nextRecordPosition")
        if next_position is None:
            break
        start_record = int(next_position)
