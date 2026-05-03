"""ingest CLI 用の logging 初期化。"""

from __future__ import annotations

import logging
import os


def configure(level: int | None = None) -> None:
    effective = level if level is not None else level_from_env()
    logging.basicConfig(
        level=effective,
        format="%(levelname)s [%(name)s] %(message)s",
        force=True,
    )


def level_from_env() -> int:
    raw = os.getenv("KOKKAI_INGEST_LOG_LEVEL", "INFO").strip().upper()
    return getattr(logging, raw, logging.INFO)
