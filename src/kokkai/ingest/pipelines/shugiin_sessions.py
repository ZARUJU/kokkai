import logging

from kokkai.db.engine import session_scope
from kokkai.db.schema import create_all
from kokkai.ingest.parsers import shugiin_sessions as parser
from kokkai.ingest.pipeline import PipelineResult
from kokkai.ingest.sources import shugiin_sessions as source
from kokkai.repositories import diet_sessions


_LOG = logging.getLogger(__name__)


def run() -> PipelineResult:
    _LOG.info("衆議院会期一覧: 取得開始")
    document = source.fetch()
    sessions = parser.parse(document.text)
    _LOG.info("衆議院会期一覧: 解析済み %s 件 source=%s", len(sessions), document.url)

    create_all()
    with session_scope() as session:
        diet_sessions.upsert_many(session, sessions, document.url)

    _LOG.info("衆議院会期一覧: DB upsert 完了")
    return PipelineResult(name=document.source_name, count=len(sessions))
