from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class PipelineResult:
    name: str
    count: int


Pipeline = Callable[[], PipelineResult]
