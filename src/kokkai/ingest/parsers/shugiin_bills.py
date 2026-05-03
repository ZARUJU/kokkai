import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin

from kokkai.ingest.parsers.common import normalize_spaces
from kokkai.models.bill import Bill
from kokkai.models.bill import BillProgressItem
from kokkai.models.bill import BillTextDocument


@dataclass(frozen=True)
class _Cell:
    text: str
    hrefs: tuple[str, ...]


@dataclass(frozen=True)
class _Table:
    caption: str | None
    rows: tuple[tuple[_Cell, ...], ...]


class _BillTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[_Table] = []
        self._in_table = False
        self._caption: list[str] | None = None
        self._rows: list[tuple[_Cell, ...]] = []
        self._current_row: list[_Cell] | None = None
        self._current_cell_text: list[str] | None = None
        self._current_cell_hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = tag.lower()
        if tag_name == "table":
            self._in_table = True
            self._caption = None
            self._rows = []
        elif tag_name == "caption" and self._in_table:
            self._caption = []
        elif tag_name == "tr" and self._in_table:
            self._current_row = []
        elif tag_name in {"td", "th"} and self._current_row is not None:
            self._current_cell_text = []
            self._current_cell_hrefs = []
        elif tag_name == "a" and self._current_cell_text is not None:
            href = _get_attr(attrs, "href")
            if href:
                self._current_cell_hrefs.append(href)

    def handle_data(self, data: str) -> None:
        if self._current_cell_text is not None:
            self._current_cell_text.append(data)
        elif self._caption is not None:
            self._caption.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag_name = tag.lower()
        if tag_name in {"td", "th"} and self._current_row is not None and self._current_cell_text is not None:
            self._current_row.append(
                _Cell(
                    text=normalize_spaces("".join(self._current_cell_text)),
                    hrefs=tuple(self._current_cell_hrefs),
                )
            )
            self._current_cell_text = None
            self._current_cell_hrefs = []
        elif tag_name == "tr" and self._current_row is not None:
            if self._current_row:
                self._rows.append(tuple(self._current_row))
            self._current_row = None
        elif tag_name == "caption" and self._caption is not None:
            self._caption = [normalize_spaces("".join(self._caption))]
        elif tag_name == "table" and self._in_table:
            caption = self._caption[0] if self._caption else None
            self.tables.append(_Table(caption=caption, rows=tuple(self._rows)))
            self._in_table = False
            self._caption = None
            self._rows = []


@dataclass(frozen=True)
class TextDocumentLink:
    item_order: int
    label: str
    url: str


class _TextInfoLinkParser(HTMLParser):
    def __init__(self, source_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[TextDocumentLink] = []
        self._source_url = source_url
        self._current_href: str | None = None
        self._current_text: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return

        href = _get_attr(attrs, "href")
        if href and href.startswith("./"):
            self._current_href = href
            self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_text is not None:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or self._current_href is None or self._current_text is None:
            return

        label = normalize_spaces("".join(self._current_text))
        if label:
            self.links.append(
                TextDocumentLink(
                    item_order=len(self.links) + 1,
                    label=label,
                    url=urljoin(self._source_url, self._current_href),
                )
            )
        self._current_href = None
        self._current_text = None


class _MainLayoutTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_parts: list[str] = []
        self._main_depth = 0
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = tag.lower()
        element_id = _get_attr(attrs, "id")
        if tag_name == "div" and element_id == "mainlayout":
            self._main_depth = 1
            return

        if self._main_depth:
            self._main_depth += 1
            if tag_name == "div" and element_id == "breadcrumb":
                self._skip_depth = 1
            elif self._skip_depth:
                self._skip_depth += 1

        if self._main_depth and not self._skip_depth and tag_name in {"br", "p", "tr", "li", "h1", "h2", "h3"}:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._main_depth and not self._skip_depth:
            self.text_parts.append(data)

    def handle_endtag(self, _tag: str) -> None:
        if not self._main_depth:
            return
        if self._skip_depth:
            self._skip_depth -= 1
        self._main_depth -= 1


def parse(html: str, source_url: str) -> list[Bill]:
    parser = _BillTableParser()
    parser.feed(html)

    session_number = _parse_session_number(html, source_url)
    bills: list[Bill] = []
    for table in parser.tables:
        category = _parse_category(table.caption)
        if category is None:
            continue

        for row in table.rows:
            bill = _parse_row(row, category, session_number, source_url)
            if bill is not None:
                bills.append(bill)

    return bills


def parse_progress_items(html: str, bill_source_id: str) -> list[BillProgressItem]:
    parser = _BillTableParser()
    parser.feed(html)

    items: list[BillProgressItem] = []
    for table in parser.tables:
        for row in table.rows:
            if len(row) != 2 or row[0].text == "項目":
                continue

            name = row[0].text
            if not name:
                continue

            items.append(
                BillProgressItem(
                    source_id=f"{bill_source_id}:progress:{len(items) + 1}",
                    bill_source_id=bill_source_id,
                    item_order=len(items) + 1,
                    name=name,
                    value=row[1].text or None,
                )
            )

    return items


def parse_text_document_links(html: str, source_url: str) -> list[TextDocumentLink]:
    parser = _TextInfoLinkParser(source_url)
    parser.feed(html)
    return parser.links


def parse_text_document(html: str, bill_source_id: str, link: TextDocumentLink) -> BillTextDocument:
    parser = _MainLayoutTextParser()
    parser.feed(html)
    content_text = _clean_text_document_content("".join(parser.text_parts))
    return BillTextDocument(
        source_id=_build_text_document_source_id(bill_source_id, link.url),
        bill_source_id=bill_source_id,
        item_order=link.item_order,
        label=link.label,
        document_url=link.url,
        content_text=content_text or None,
    )


def _parse_session_number(html: str, source_url: str) -> int:
    heading_match = re.search(r"第\s*(\d+)\s*回国会\s*議案の一覧", html)
    if heading_match:
        return int(heading_match.group(1))

    url_match = re.search(r"kaiji(\d+)\.htm", source_url)
    if url_match:
        return int(url_match.group(1))

    raise ValueError("Could not parse session number from bill list")


def _parse_category(caption: str | None) -> str | None:
    if caption is None:
        return None

    match = re.fullmatch(r"(.+)の一覧", normalize_spaces(caption))
    if match:
        return match.group(1)
    if normalize_spaces(caption) == "決算その他":
        return "決算その他"
    return None


def _parse_row(row: tuple[_Cell, ...], category: str, session_number: int, source_url: str) -> Bill | None:
    if not row or row[0].text == "提出回次":
        return None

    cells = list(row)
    number: int | None
    if len(cells) == 6:
        submitted_session_number = _parse_int(cells[0].text)
        number = _parse_int(cells[1].text)
        title = cells[2].text
        status = cells[3].text
        progress_url = _first_absolute_url(cells[4], source_url)
        text_url = _first_absolute_url(cells[5], source_url)
    elif len(cells) == 5 and _parse_int(cells[0].text) is not None:
        submitted_session_number = _parse_int(cells[0].text)
        number = _parse_int(cells[1].text)
        title = cells[2].text
        status = cells[3].text
        progress_url = _first_absolute_url(cells[4], source_url)
        text_url = None
    elif len(cells) == 5 and _parse_int(cells[1].text) is not None:
        category = cells[0].text or category
        submitted_session_number = _parse_int(cells[1].text)
        number = None
        title = cells[2].text
        status = cells[3].text
        progress_url = _first_absolute_url(cells[4], source_url)
        text_url = None
    elif len(cells) == 4:
        submitted_session_number = _parse_int(cells[0].text)
        number = None
        title = cells[1].text
        status = cells[2].text
        progress_url = _first_absolute_url(cells[3], source_url)
        text_url = None
    else:
        return None

    if submitted_session_number is None or not title:
        return None

    return Bill(
        source_id=_build_source_id(session_number, category, number, title, progress_url),
        session_number=session_number,
        submitted_session_number=submitted_session_number,
        category=category,
        number=number,
        title=title,
        status=status,
        progress_url=progress_url,
        text_url=text_url,
    )


def _parse_int(value: str) -> int | None:
    return int(value) if re.fullmatch(r"\d+", normalize_spaces(value)) else None


def _first_absolute_url(cell: _Cell, source_url: str) -> str | None:
    if not cell.hrefs:
        return None
    return urljoin(source_url, cell.hrefs[0])


def _build_source_id(
    session_number: int,
    category: str,
    number: int | None,
    title: str,
    progress_url: str | None,
) -> str:
    if progress_url:
        match = re.search(r"/keika/([^/.]+)\.htm", progress_url, re.IGNORECASE)
        if match:
            return match.group(1)

    number_part = str(number) if number is not None else "none"
    title_part = re.sub(r"\W+", "-", title).strip("-")
    return f"{session_number}-{category}-{number_part}-{title_part}"


def _build_text_document_source_id(bill_source_id: str, document_url: str) -> str:
    match = re.search(r"/honbun/(.+?)\.htm", document_url, re.IGNORECASE)
    if match:
        return f"{bill_source_id}:text:{match.group(1)}"
    return f"{bill_source_id}:text:{document_url}"


def _clean_text_document_content(value: str) -> str:
    text = value.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    text = re.sub(r"[ \t\u3000]+", " ", text)
    text = _strip_site_footer(text)
    lines = [_clean_text_document_line(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(lines)


def _strip_site_footer(value: str) -> str:
    return re.sub(
        r"\s*ホームページについて\s+Webアクセシビリティ\s+リンク・著作権等について\s+お問い合わせ\s+衆議院\s+〒100-0014.*$",
        "",
        value,
        flags=re.DOTALL,
    )


def _clean_text_document_line(value: str) -> str:
    text = value.strip()
    text = re.sub(r"[ \t\u3000]+", " ", text)
    return text


def _get_attr(attrs: list[tuple[str, str | None]], name: str) -> str | None:
    for attr_name, value in attrs:
        if attr_name.lower() == name and value is not None:
            return value
    return None
