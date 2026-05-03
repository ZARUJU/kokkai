from kokkai.ingest.documents import SourceDocument
from kokkai.ingest.http import fetch_text


SOURCE_NAME = "shugiin_sessions"
SOURCE_URL = "https://www.shugiin.go.jp/internet/itdb_annai.nsf/html/statics/shiryo/kaiki.htm"


def fetch() -> SourceDocument:
    return fetch_text(SOURCE_NAME, SOURCE_URL, encoding="shift_jis")
