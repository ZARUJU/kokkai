from dataclasses import dataclass


@dataclass(frozen=True)
class SourceDocument:
    source_name: str
    url: str
    text: str
