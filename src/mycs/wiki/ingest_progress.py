from __future__ import annotations

from typing import Callable, Protocol

from mycs.log import get_logger
from mycs.log_detail import log_step

logger = get_logger(__name__)


class IngestProgressFn(Protocol):
    def __call__(self, *, stage: str, percent: int, message: str) -> None: ...


def report_ingest_progress(
    on_progress: IngestProgressFn | None,
    *,
    stage: str,
    percent: int,
    message: str,
) -> None:
    percent = max(0, min(100, int(percent)))
    log_step(logger, "ingest_progress", stage=stage, percent=percent, message=message)
    logger.info("joyjoy: ingest %s %s%% — %s", stage, percent, message)
    if on_progress is not None:
        on_progress(stage=stage, percent=percent, message=message)


def noop_ingest_progress(*, stage: str, percent: int, message: str) -> None:
    pass


def wrap_progress(callback: Callable[[str, int, str], None] | None) -> IngestProgressFn | None:
    if callback is None:
        return None

    def fn(*, stage: str, percent: int, message: str) -> None:
        callback(stage, percent, message)

    return fn