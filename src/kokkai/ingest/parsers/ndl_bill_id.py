"""国立国会図書館 日本法令索引の billId（9桁）と議題テキストの対応。

形式: 1 + 会期3桁 + 提出種別2桁 + 号数3桁
提出種別: 01 内閣、02 衆議院、03 参議院、04 条約
"""

from __future__ import annotations

import re

from kokkai.ingest.parsers.common import normalize_spaces
from kokkai.ingest.parsers.kokkai_meetings import _parse_kanji_uint

_KIND_PATTERNS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("01", re.compile(r"(内閣提出|閣法)"), "閣法"),
    ("02", re.compile(r"(衆議院提出|衆法)"), "衆法"),
    ("03", re.compile(r"(参議院提出|参法)"), "参法"),
    ("04", re.compile(r"(条約)"), "条約"),
)

# billId の提出種別 → 衆議院議案経過ページ ID（g21906002）中央2桁
_NDL_KIND_TO_GIAN_MIDDLE: dict[str, str] = {
    "01": "09",
    "02": "05",
    "03": "06",
}

# 衆議院議案一覧の category → 法令索引 billId の提出種別2桁
_CATEGORY_TO_NDL_KIND: dict[str, str] = {
    "閣法": "01",
    "衆法": "02",
    "参法": "03",
    "条約": "04",
}


def ndl_kind_to_category(kind: str) -> str | None:
    for code, _, cat in _KIND_PATTERNS:
        if code == kind:
            return cat
    return None


def build_ndl_bill_id(session_number: int, ndl_kind_code: str, bill_number: int) -> str:
    return f"1{session_number:03d}{ndl_kind_code}{bill_number:03d}"


def ndl_bill_id_from_bill_row(submitted_session_number: int, category: str, number: int | None) -> str | None:
    """議案一覧行（DB）から法令索引 billId を組み立てる。種別・号がない行は対象外。"""
    if number is None:
        return None
    kind = _CATEGORY_TO_NDL_KIND.get(normalize_spaces(category))
    if kind is None:
        return None
    return build_ndl_bill_id(submitted_session_number, kind, number)


def parse_ndl_bill_id(bill_id: str) -> tuple[int, str, int] | None:
    s = bill_id.strip()
    if not re.fullmatch(r"1\d{8}", s):
        return None
    session = int(s[1:4])
    kind = s[4:6]
    number = int(s[6:9])
    if kind not in {"01", "02", "03", "04"}:
        return None
    return session, kind, number


def gian_source_id_from_ndl_bill_id(bill_id: str) -> str | None:
    """DB に無い場合の推測用。衆議院経過 URL の g21906002 形式。"""
    parsed = parse_ndl_bill_id(bill_id)
    if parsed is None:
        return None
    session, kind, number = parsed
    middle = _NDL_KIND_TO_GIAN_MIDDLE.get(kind)
    if middle is None:
        return None
    return f"g{session}{middle}{number:03d}"


def _detect_ndl_kind_code(fragment: str) -> str | None:
    for code, pattern, _cat in _KIND_PATTERNS:
        if pattern.search(fragment):
            return code
    return None


def _bill_number_from_fragment(fragment: str) -> int | None:
    m = re.search(r"第\s*([〇零一二三四五六七八九十百千\d０-９]+)\s*号", fragment)
    if not m:
        return None
    return _parse_kanji_uint(m.group(1))


def ndl_bill_ids_from_topic_label(topic_label: str, session_number: int) -> list[str]:
    """議題1行から billId を推定。複数断片（読点等）ごとに抽出。"""
    if "法律案" not in topic_label and "条約" not in topic_label:
        return []

    t = normalize_spaces(topic_label)
    pieces: list[str] = []
    seen: set[str] = set()
    for piece in re.split(r"[、]|及び", t):
        piece = normalize_spaces(piece).strip()
        if len(piece) < 4 or piece in seen:
            continue
        seen.add(piece)
        pieces.append(piece)

    out: list[str] = []
    seen_ids: set[str] = set()
    for frag in pieces:
        if "法律案" not in frag and "条約" not in frag:
            continue
        kind = _detect_ndl_kind_code(frag)
        if kind is None:
            continue
        num = _bill_number_from_fragment(frag)
        if num is None:
            continue
        bid = build_ndl_bill_id(session_number, kind, num)
        if bid not in seen_ids:
            seen_ids.add(bid)
            out.append(bid)

    if not out:
        kind = _detect_ndl_kind_code(t)
        num = _bill_number_from_fragment(t)
        if kind is not None and num is not None:
            bid = build_ndl_bill_id(session_number, kind, num)
            if bid not in seen_ids:
                out.append(bid)

    return out
