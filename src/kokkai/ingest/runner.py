from kokkai.ingest.pipeline import Pipeline
from kokkai.ingest.pipeline import PipelineResult
from kokkai.ingest.pipelines import kokkai_meetings
from kokkai.ingest.pipelines import shugiin_bills
from kokkai.ingest.pipelines import shugiin_sessions


PIPELINES: dict[str, Pipeline] = {
    "shugiin_bills": shugiin_bills.run,
    "shugiin_sessions": shugiin_sessions.run,
    "kokkai_meetings": kokkai_meetings.run,
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
