from kokkai.ingest.documents import SourceDocument
from kokkai.ingest.http import fetch_text


SOURCE_NAME = "shugiin_bills"
SOURCE_URL_TEMPLATE = "https://www.shugiin.go.jp/internet/itdb_gian.nsf/html/gian/kaiji{session_number}.htm"


def build_url(session_number: int) -> str:
    return SOURCE_URL_TEMPLATE.format(session_number=session_number)


def fetch(session_number: int) -> SourceDocument:
    return fetch_text(SOURCE_NAME, build_url(session_number), encoding="shift_jis")


def fetch_url(url: str) -> SourceDocument:
    return fetch_text(SOURCE_NAME, url, encoding="shift_jis")
