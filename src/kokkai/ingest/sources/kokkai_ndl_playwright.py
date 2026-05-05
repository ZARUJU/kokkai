"""国会会議録検索サイト（SPA）から billId 検索結果の min_id（= 会議録 issueID）を取得する。"""

from __future__ import annotations

import json
import logging

from playwright.sync_api import Page

logger = logging.getLogger(__name__)

_KOKKAI_TOP = "https://kokkai.ndl.go.jp/"
_RESULT_URL = "https://kokkai.ndl.go.jp/#/result?billId={bill_id}"


def reset_ndl_search_context(page: Page) -> None:
    """Vuex の残りを捨てるため、初回のみトップでストレージをクリアする。"""
    page.goto(_KOKKAI_TOP, wait_until="domcontentloaded", timeout=60_000)
    page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")


def fetch_min_ids_for_bill_id(
    page: Page,
    bill_id: str,
    *,
    reset_context: bool = True,
    navigation_timeout_ms: int = 120_000,
) -> list[str]:
    """#/result?billId=… の詳細検索 API 応答から min_id の配列を返す。

    reset_context: 真のときトップへ遷移して localStorage をクリアしてから検索する。
    取り込みバッチの2件目以降は偽にすると、トップ往復を省略できる。
    """
    if reset_context:
        reset_ndl_search_context(page)
    target = _RESULT_URL.format(bill_id=bill_id)
    try:
        with page.expect_response(
            lambda r: "/minutes/api/v1/search/detail" in r.url,
            timeout=navigation_timeout_ms,
        ) as resp_info:
            page.goto(target, wait_until="networkidle", timeout=navigation_timeout_ms)
        resp = resp_info.value
        if not resp.ok:
            logger.warning("kokkai NDL search/detail HTTP %s for billId=%s", resp.status, bill_id)
            return []
        payload = json.loads(resp.text())
    except Exception as exc:  # noqa: BLE001
        logger.warning("kokkai NDL billId fetch failed billId=%s: %s", bill_id, exc)
        return []

    data = payload.get("data")
    if not isinstance(data, list):
        return []
    out: list[str] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        mid = row.get("min_id")
        if isinstance(mid, str) and mid:
            out.append(mid)
    return out
