from kokkai.ingest.documents import SourceDocument
from kokkai.ingest.http import fetch_text


SOURCE_NAME = "questions"
SHUGIIN_LIST_URL = (
    "https://www.shugiin.go.jp/internet/itdb_shitsumon.nsf/html/shitsumon/kaiji{session}_l.htm"
)
SANGIIN_LIST_URL = "https://www.sangiin.go.jp/japanese/joho1/kousei/syuisyo/{session}/syuisyo.htm"


def fetch_shugiin(session_number: int) -> SourceDocument:
    url = SHUGIIN_LIST_URL.format(session=session_number)
    return fetch_text(SOURCE_NAME, url, encoding="shift_jis")


def fetch_sangiin(session_number: int) -> SourceDocument:
    url = SANGIIN_LIST_URL.format(session=session_number)
    return fetch_text(SOURCE_NAME, url, encoding="utf-8")


def fetch_url(url: str, chamber: str) -> SourceDocument:
    encoding = "shift_jis" if chamber == "shugiin" else "utf-8"
    return fetch_text(SOURCE_NAME, url, encoding=encoding)
