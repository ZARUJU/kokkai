import logging
import time

from kokkai.ingest.pipeline import IngestRunContext
from kokkai.ingest.pipeline import Pipeline
from kokkai.ingest.pipeline import PipelineResult
from kokkai.ingest.pipelines import kokkai_meetings
from kokkai.ingest.pipelines import questions
from kokkai.ingest.pipelines import shugiin_bills
from kokkai.ingest.pipelines import shugiin_sessions


PIPELINES: dict[str, Pipeline] = {
    "shugiin_sessions": shugiin_sessions.run,
    "shugiin_bills": shugiin_bills.run,
    "kokkai_meetings": kokkai_meetings.run,
    "questions": questions.run,
}

_LOG = logging.getLogger(__name__)


def run(
    selected_names: list[str] | None = None,
    context: IngestRunContext | None = None,
) -> list[PipelineResult]:
    names = selected_names or list(PIPELINES)
    ctx = context or IngestRunContext()
    results: list[PipelineResult] = []

    sess = ctx.session_numbers
    sess_note = (
        ",".join(str(n) for n in sess) if sess else "なし（各 pipeline の環境変数または DB）"
    )
    _LOG.info(
        "ingest runner: %s pipeline(s): %s | CLI 会期: %s",
        len(names),
        ", ".join(names),
        sess_note,
    )

    for name in names:
        try:
            pipeline = PIPELINES[name]
        except KeyError as error:
            available = ", ".join(sorted(PIPELINES))
            raise ValueError(f"Unknown ingest pipeline: {name}. Available: {available}") from error

        _LOG.info("start pipeline %r", name)
        started = time.perf_counter()
        result = pipeline(ctx)
        elapsed = time.perf_counter() - started
        _LOG.info(
            "done pipeline %r in %.1fs (count=%s)",
            name,
            elapsed,
            result.count,
        )
        results.append(result)

    return results
