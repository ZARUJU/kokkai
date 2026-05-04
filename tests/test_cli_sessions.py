from kokkai.ingest.cli_sessions import build_run_context
from kokkai.ingest.cli_sessions import ingest_sessions_explicit
from kokkai.ingest.cli_sessions import sessions_from_argv_tokens
from kokkai.ingest.pipeline import IngestRunContext


def test_sessions_from_argv_tokens_repeatable_and_csv() -> None:
    got = sessions_from_argv_tokens(["220,221", "222"])
    assert got == (220, 221, 222)


def test_sessions_from_argv_tokens_none_when_missing() -> None:
    assert sessions_from_argv_tokens(None) is None
    assert sessions_from_argv_tokens([]) is None


def test_build_run_context_preserves_cli_order() -> None:
    ctx = build_run_context(["221", "219,218"])
    assert ctx.session_numbers == (221, 219, 218)


def test_ingest_sessions_explicit_prefers_cli() -> None:
    ctx = IngestRunContext(session_numbers=(210,))
    assert ingest_sessions_explicit(ctx, "211,212") == (210,)


def test_ingest_sessions_explicit_env_when_no_cli() -> None:
    ctx = IngestRunContext(session_numbers=None)
    assert ingest_sessions_explicit(ctx, "211,212") == (211, 212)


def test_ingest_sessions_explicit_empty_env() -> None:
    ctx = IngestRunContext(session_numbers=None)
    assert ingest_sessions_explicit(ctx, None) is None
    assert ingest_sessions_explicit(ctx, "  ") is None
