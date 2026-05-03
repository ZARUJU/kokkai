from kokkai.ingest.pipeline import Pipeline
from kokkai.ingest.pipeline import PipelineResult
from kokkai.ingest.pipelines import shugiin_sessions


PIPELINES: dict[str, Pipeline] = {
    "shugiin_sessions": shugiin_sessions.run,
}


def run(selected_names: list[str] | None = None) -> list[PipelineResult]:
    names = selected_names or list(PIPELINES)
    results: list[PipelineResult] = []

    for name in names:
        try:
            pipeline = PIPELINES[name]
        except KeyError as error:
            available = ", ".join(sorted(PIPELINES))
            raise ValueError(f"Unknown ingest pipeline: {name}. Available: {available}") from error

        results.append(pipeline())

    return results
