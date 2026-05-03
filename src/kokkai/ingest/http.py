import logging
from urllib.request import Request
from urllib.request import urlopen

from kokkai.ingest.documents import SourceDocument


_LOG = logging.getLogger(__name__)


def fetch_text(source_name: str, url: str, encoding: str = "utf-8") -> SourceDocument:
    _LOG.debug("fetch %s %s", source_name, url)
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})

    with urlopen(request, timeout=30) as response:
        body = response.read()

    return SourceDocument(
        source_name=source_name,
        url=url,
        text=body.decode(encoding, errors="replace"),
    )
