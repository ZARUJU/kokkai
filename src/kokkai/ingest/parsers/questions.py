import re
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.parse import urlparse

from kokkai.ingest.parsers.common import clean_kokkai_speaker_name
from kokkai.ingest.parsers.common import normalize_spaces
from kokkai.models.question import Question


def parse_shugiin(html: str, source_url: str) -> list[Question]:
    session_number = _extract_session_number(html, source_url)
    row_pattern = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
    cell_pattern = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.IGNORECASE | re.DOTALL)

    questions: list[Question] = []
    for row_html in row_pattern.findall(html):
        cells = cell_pattern.findall(row_html)
        if len(cells) < 9:
            continue

        number = _parse_int(_strip_tags(cells[0]))
        title = _anchor_text(cells[1]) or _strip_tags(cells[1])
        submitter = _normalize_person_name(_strip_tags(cells[2]))
        status = _empty_to_none(_strip_tags(cells[3]))
        details_url = _first_link(cells[4], source_url)
        question_url = _first_link(cells[5], source_url)
        answer_url = _first_link(cells[7], source_url)

        if number is None or not title:
            continue

        questions.append(
            Question(
                source_id=f"shugiin-{session_number}-{number:03d}",
                chamber="shugiin",
                session_number=session_number,
                number=number,
                title=title,
                submitter=submitter,
                status=status,
                details_url=details_url,
                question_url=question_url,
                answer_url=answer_url,
                question_text=None,
                answer_text=None,
            )
        )

    return questions


def parse_sangiin(html: str, source_url: str) -> list[Question]:
    session_number = _extract_session_number(html, source_url)
    title_pattern = re.compile(
        r'<a[^>]+href="(?P<href>[^"]*meisai/m(?P<code>\d+)\.htm[^"]*)"[^>]*>(?P<title>.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    entries = list(title_pattern.finditer(html))

    questions: list[Question] = []
    for index, match in enumerate(entries):
        code = match.group("code")
        number = int(code[-3:])
        title = normalize_spaces(_strip_tags(match.group("title")))
        details_url = urljoin(source_url, unescape(match.group("href")))
        chunk_end = entries[index + 1].start() if index + 1 < len(entries) else len(html)
        chunk = html[match.start() : chunk_end]

        submitter = _extract_submitter(chunk)
        question_url = _extract_url(chunk, rf'syuh/s{code}\.htm')
        answer_url = _extract_url(chunk, rf'touh/t{code}\.htm')

        questions.append(
            Question(
                source_id=f"sangiin-{session_number}-{number:03d}",
                chamber="sangiin",
                session_number=session_number,
                number=number,
                title=title,
                submitter=submitter,
                status=None,
                details_url=details_url,
                question_url=urljoin(source_url, question_url) if question_url else None,
                answer_url=urljoin(source_url, answer_url) if answer_url else None,
                question_text=None,
                answer_text=None,
            )
        )

    return questions


def _extract_session_number(html: str, source_url: str) -> int:
    for pattern in (
        r"第\s*(\d+)\s*回国会",
        r"/(\d{1,3})/syuisyo\.htm",
        r"kaiji(\d+)_l\.htm",
    ):
        match = re.search(pattern, html + " " + source_url)
        if match:
            return int(match.group(1))
    raise ValueError("Could not extract session number from question list")


def _extract_submitter(chunk: str) -> str | None:
    patterns = (
        r"提出者[^<]*</[^>]+>\s*<[^>]*>\s*([^<]+?)\s*君",
        r"提出者[^<\n]*[:：]?\s*([^<\n]+?)\s*君",
    )
    for pattern in patterns:
        match = re.search(pattern, chunk, re.IGNORECASE | re.DOTALL)
        if match:
            raw = normalize_spaces(unescape(_strip_tags(match.group(1))))
            return _normalize_person_name(raw)
    return None


def _extract_url(chunk: str, target_pattern: str) -> str | None:
    match = re.search(rf'href="(?P<href>[^"]*{target_pattern}[^"]*)"', chunk, re.IGNORECASE)
    if match:
        return unescape(match.group("href"))
    return None


def _first_link(cell_html: str, source_url: str) -> str | None:
    match = re.search(r'href="([^"]+)"', cell_html, re.IGNORECASE)
    if not match:
        return None
    return urljoin(source_url, unescape(match.group(1)))


def _anchor_text(cell_html: str) -> str | None:
    match = re.search(r"<a[^>]*>(.*?)</a>", cell_html, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return _empty_to_none(_strip_tags(match.group(1)))


def _strip_tags(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    return normalize_spaces(unescape(text))


def _parse_int(value: str) -> int | None:
    text = normalize_spaces(value)
    return int(text) if re.fullmatch(r"\d+", text) else None


def _normalize_person_name(raw: str | None) -> str | None:
    """会議録の speaker と同様、敬称・記号類を除去して表示用氏名を正規化する。"""
    if raw is None:
        return None
    text = normalize_spaces(raw)
    if not text:
        return None
    return clean_kokkai_speaker_name(text)


def _empty_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    text = normalize_spaces(value)
    return text if text else None


def extract_document_text(html: str, document_url: str | None = None) -> str | None:
    text = _focus_html_main_region(html, document_url)
    text = re.sub(r"(?is)<script\b.*?</script>", " ", text)
    text = re.sub(r"(?is)<style\b.*?</style>", " ", text)
    text = re.sub(r"(?is)<noscript\b.*?</noscript>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|tr|li|h1|h2|h3|div|section|article|table|hr)>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text).replace("\u00a0", " ").replace("\u3000", " ")
    text = re.sub(r"[ \t]+", " ", text)
    lines = [normalize_spaces(line) for line in text.splitlines()]
    lines = _drop_noise_document_lines(lines)
    joined = "\n".join(line for line in lines if line)
    joined = _strip_common_footer(joined)
    joined = _strip_boilerplate_head(joined)
    joined = re.sub(r"\n{3,}", "\n\n", joined).strip()
    return joined or None


def _get_attr(attrs: list[tuple[str, str | None]], name: str) -> str | None:
    for attr_name, value in attrs:
        if attr_name.lower() == name and value is not None:
            return value
    return None


class _RegionLayoutTextParser(HTMLParser):
    """衆議院 mainlayout／参議院 ContentsBox のように本文周りの DIV だけを抜き出す。"""

    def __init__(self, target_id: str, skip_breadcrumb: bool) -> None:
        super().__init__(convert_charrefs=True)
        self._target_id = target_id.lower()
        self._skip_breadcrumb = skip_breadcrumb
        self.text_parts: list[str] = []
        self._region_depth = 0
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_name = tag.lower()
        element_id = (_get_attr(attrs, "id") or "").lower()
        if self._region_depth == 0:
            if tag_name == "div" and element_id == self._target_id:
                self._region_depth = 1
            return

        self._region_depth += 1
        if self._skip_breadcrumb and tag_name == "div" and element_id == "breadcrumb":
            self._skip_depth = 1
        elif self._skip_depth:
            self._skip_depth += 1

        if self._region_depth > 0 and not self._skip_depth and tag_name in {
            "br",
            "p",
            "tr",
            "li",
            "h1",
            "h2",
            "h3",
            "table",
            "hr",
        }:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._region_depth > 0 and not self._skip_depth:
            self.text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._region_depth <= 0:
            return
        if self._skip_depth:
            self._skip_depth -= 1
        self._region_depth -= 1


def _focus_html_main_region(html: str, document_url: str | None) -> str:
    if not document_url:
        return html
    host = (urlparse(document_url).hostname or "").lower()
    target: tuple[str, bool] | None = None
    if host.endswith("shugiin.go.jp"):
        target = ("mainlayout", True)
    elif host.endswith("sangiin.go.jp"):
        target = ("contentsbox", False)
    if target is None:
        return html

    pid, skip_crumb = target
    parser = _RegionLayoutTextParser(pid, skip_breadcrumb=skip_crumb)
    try:
        parser.feed(html)
    except Exception:
        return html

    extracted = "".join(parser.text_parts)
    if normalize_spaces(extracted):
        return extracted
    return html


_NOISE_LINES_EXACT = frozenset(
    {
        "メインへスキップ",
        "メインへ",
        "本文へ",
        "サイトマップ",
        "ヘルプ",
        "English",
        "トップページに戻る",
        "文字サイズの変更",
        "標準",
        "拡大",
        "最大",
        "検索",
        "検索方法",
        "サイト内検索",
        "リンク集",
        "よくある質問",
        "音声読み上げ音声読み上げアイコン",
        "利用案内",
        "著作権",
        "免責事項",
        "ご意見・ご質問",
    }
)


def _drop_noise_document_lines(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        stripped = normalize_spaces(line)
        if not stripped:
            continue
        if stripped in _NOISE_LINES_EXACT:
            continue
        if _is_noise_line_by_prefix_or_pattern(stripped):
            continue
        out.append(stripped)
    return out


def _is_noise_line_by_prefix_or_pattern(line: str) -> bool:
    if line.startswith(("Copyright", "〒", "電話（代表）", "案内図")):
        return True
    if line.startswith(("All rights reserved", "すべての機能をご利用いただくには")):
        return True
    if line.startswith(("Adobe Acrobat", "アクロバットリーダー")):
        return True
    if "PDFファイルを表示するには" in line:
        return True
    # 衆議院本文ページ上部の経過‧PDF/HTML へのリンクバーなど
    if line.count("|") >= 2 and ("PDF" in line or "HTML" in line) and ("質問" in line or "答弁" in line or "経過" in line):
        return True
    # 単独の院名だけ（ヘッダ alt などが混ざった行）
    if line in frozenset({"衆議院", "参議院"}):
        return True
    return False


def _strip_boilerplate_head(text: str) -> str:
    drop_head = frozenset(
        {
            "質問主意書",
            "答弁書",
            "質問主意書 ： 衆議院",
        }
    )
    lines = text.splitlines()
    while lines:
        head = normalize_spaces(lines[0])
        if head in drop_head:
            lines.pop(0)
            continue
        if re.fullmatch(r"第\s*\d+\s*回国会[（\(][^）\)]+[）\)]", head):
            lines.pop(0)
            continue
        break
    return "\n".join(lines)


def _strip_common_footer(value: str) -> str:
    patterns = (
        r"\n(?:ホームページについて|Webアクセシビリティ|リンク・著作権等について|お問い合わせ).*$",
        r"\n案内図[^\n]*",
        r"\n(?:Copyright|Copyright©).*$",
        r"\n(?:利用案内|著作権|免責事項|ご意見・ご質問).*$",
        r"\nAll rights reserved\..*$",
        r"\nAdobe AcrobatReader.*$",
        r"\n(?:最新版をお持ちでない方は|こちらから入手できます).*$",
    )
    text = value
    for pattern in patterns:
        text = re.sub(pattern, "", text, flags=re.DOTALL | re.IGNORECASE)
    return text
