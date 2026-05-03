from urllib.request import Request
from urllib.request import urlopen

from kokkai.ingest.documents import SourceDocument


def fetch_text(source_name: str, url: str, encoding: str = "utf-8") -> SourceDocument:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})

    with urlopen(request, timeout=30) as response:
        body = response.read()

    return SourceDocument(
        source_name=source_name,
        url=url,
        text=body.decode(encoding, errors="replace"),
    )
