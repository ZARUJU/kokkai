"""SQLite 接続ごとに登録するユーザー定義関数。"""

from sqlalchemy import event
from sqlalchemy.engine import Engine

from kokkai.ingest.parsers.common import compact_person_full_name


def _kokkai_compact_person_dbapi(value: object) -> str:
    """NULL は空文字として比較し、三値論理で exists が意図せず真にならないようにする。"""
    if value is None:
        return ""
    return compact_person_full_name(str(value))


def register_sqlite_functions(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection: object, _connection_record: object) -> None:
        if engine.dialect.name != "sqlite":
            return
        dbapi_connection.create_function(
            "kokkai_compact_person",
            1,
            _kokkai_compact_person_dbapi,
            deterministic=True,
        )
