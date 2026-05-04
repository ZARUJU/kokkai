from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class PipelineResult:
    name: str
    count: int


@dataclass(frozen=True)
class IngestRunContext:
    """ingest CLI / runner が pipeline に渡すオプション。"""

    session_numbers: tuple[int, ...] | None = None


def parse_sessions_csv(value: str | None) -> tuple[int, ...] | None:
    """環境変数などのカンマ区切り整数列をパースする。空無効時は None。"""
    if value is None or value.strip() == "":
        return None
    parts = [p.strip() for p in value.split(",") if p.strip()]
    if not parts:
        return None
    return tuple(int(p) for p in parts)


Pipeline = Callable[[IngestRunContext], PipelineResult]
