"""ingest の --session（および環境変数）から得た回次リストを統一処理する。"""

from __future__ import annotations

from kokkai.ingest.pipeline import IngestRunContext
from kokkai.ingest.pipeline import parse_sessions_csv


def sessions_from_argv_tokens(tokens: list[str] | None) -> tuple[int, ...] | None:
    """`--session` の繰り返し・カンマ区切りを flatten した回次リスト。無指定は None。"""
    if not tokens:
        return None
    out: list[int] = []
    for chunk in tokens:
        for piece in chunk.split(","):
            p = piece.strip()
            if p:
                out.append(int(p))
    return tuple(out) if out else None


def build_run_context(argv_session_tokens: list[str] | None) -> IngestRunContext:
    nums = sessions_from_argv_tokens(argv_session_tokens)
    return IngestRunContext(session_numbers=nums)


def ingest_sessions_explicit(context: IngestRunContext | None, env_raw: str | None) -> tuple[int, ...] | None:
    """CLI があればそれを優先。無ければ環境変数のカンマ区切り。"""
    if context and context.session_numbers:
        return context.session_numbers
    return parse_sessions_csv(env_raw)
