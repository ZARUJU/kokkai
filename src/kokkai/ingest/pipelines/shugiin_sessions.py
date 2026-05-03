from kokkai.ingest.parsers import shugiin_sessions as parser
from kokkai.ingest.pipeline import PipelineResult
from kokkai.ingest.sources import shugiin_sessions as source
from kokkai.db.schema import create_all
from kokkai.db.engine import session_scope
from kokkai.repositories import diet_sessions


def run() -> PipelineResult:
    document = source.fetch()
    sessions = parser.parse(document.text)

    create_all()
    with session_scope() as session:
        diet_sessions.upsert_many(session, sessions, document.url)

    return PipelineResult(name=document.source_name, count=len(sessions))
