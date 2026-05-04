from kokkai.ingest.documents import SourceDocument
from kokkai.ingest.http import fetch_text


SOURCE_NAME = "questions"
SHUGIIN_URL = "https://www.shugiin.go.jp/internet/itdb_shitsumon.nsf/html/shitsumon/kaiji221_l.htm"
SANGIIN_URL = "https://www.sangiin.go.jp/japanese/joho1/kousei/syuisyo/221/syuisyo.htm"


def fetch_shugiin() -> SourceDocument:
    return fetch_text(SOURCE_NAME, SHUGIIN_URL, encoding="shift_jis")


def fetch_sangiin() -> SourceDocument:
    return fetch_text(SOURCE_NAME, SANGIIN_URL, encoding="utf-8")


def fetch_url(url: str, chamber: str) -> SourceDocument:
    encoding = "shift_jis" if chamber == "shugiin" else "utf-8"
    return fetch_text(SOURCE_NAME, url, encoding=encoding)
