import re
from datetime import date


def normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("\u3000", " ")).strip()


def parse_days(value: str) -> int | None:
    match = re.search(r"\d+", normalize_spaces(value))
    return int(match.group(0)) if match else None


def parse_japanese_date(value: str) -> date | None:
    text = normalize_spaces(value)
    match = re.search(r"(令和|平成|昭和)(元|\d+)年\s*(\d+)月\s*(\d+)日", text)
    if not match:
        return None

    era, era_year, month, day = match.groups()
    year = 1 if era_year == "元" else int(era_year)
    return date(_to_western_year(era, year), int(month), int(day))


def _to_western_year(era: str, year: int) -> int:
    starts = {
        "令和": 2018,
        "平成": 1988,
        "昭和": 1925,
    }
    return starts[era] + year
