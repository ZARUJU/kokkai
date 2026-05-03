import re
from datetime import date
from html.parser import HTMLParser

from kokkai.ingest.parsers.common import normalize_spaces
from kokkai.ingest.parsers.common import parse_days
from kokkai.ingest.parsers.common import parse_japanese_date
from kokkai.models.diet_session import DietSession


class _SessionTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "tr":
            self._current_row = []
        elif tag.lower() in {"td", "th"} and self._current_row is not None:
            self._current_cell = []

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._current_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"td", "th"} and self._current_row is not None and self._current_cell is not None:
            text = normalize_spaces("".join(self._current_cell))
            self._current_row.append(text)
            self._current_cell = None
        elif tag.lower() == "tr" and self._current_row is not None:
            if self._current_row:
                self.rows.append(self._current_row)
            self._current_row = None


def parse(html: str) -> list[DietSession]:
    parser = _SessionTableParser()
    parser.feed(html)

    sessions: list[DietSession] = []
    for row in parser.rows:
        if len(row) != 6 or not row[0].startswith("第"):
            continue

        number, session_type = parse_session_label(row[0])
        end_date, end_note = parse_end_date(row[2])
        sessions.append(
            DietSession(
                number=number,
                session_type=session_type,
                start_date=parse_japanese_date(row[1]),
                end_date=end_date,
                end_note=end_note,
                total_days=parse_days(row[3]),
                statutory_days=parse_days(row[4]),
                extension_days=parse_days(row[5]),
            )
        )

    return sessions


def parse_session_label(value: str) -> tuple[int, str]:
    match = re.search(r"第\s*(\d+)\s*回\s*[（(]\s*([^）)]+)\s*[）)]", normalize_spaces(value))
    if not match:
        raise ValueError(f"Unsupported session label: {value}")
    return int(match.group(1)), match.group(2)


def parse_end_date(value: str) -> tuple[date | None, str | None]:
    text = normalize_spaces(value)
    if not text:
        return None, None

    end_date = parse_japanese_date(text)
    note = None
    if "解散" in text:
        note = "解散"
    return end_date, note

