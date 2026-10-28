from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, asdict
from typing import Any, Iterator

from mycs.log import LOG_TAG

_DEFAULT_MAX = 2000


@dataclass
class LogRecordView:
    id: int
    ts: float
    time: str
    logger: str
    level: str
    message: str
    line: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LogRingBuffer:
    def __init__(self, *, maxlen: int = _DEFAULT_MAX) -> None:
        self._maxlen = max(100, maxlen)
        self._lock = threading.Lock()
        self._seq = 0
        self._items: deque[LogRecordView] = deque(maxlen=self._maxlen)

    def append(self, record: logging.LogRecord, *, formatted: str) -> LogRecordView:
        with self._lock:
            self._seq += 1
            item = LogRecordView(
                id=self._seq,
                ts=record.created,
                time=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(record.created)),
                logger=record.name,
                level=record.levelname,
                message=record.getMessage(),
                line=formatted,
            )
            self._items.append(item)
            return item

    def query(
        self,
        *,
        after_id: int = 0,
        limit: int = 200,
        level: str | None = None,
        q: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        limit = max(1, min(limit, 1000))
        with self._lock:
            items = list(self._items)
            latest_id = self._seq
        out: list[dict[str, Any]] = []
        level_u = (level or "").upper()
        needle = (q or "").strip().lower()
        for item in items:
            if item.id <= after_id:
                continue
            if level_u and item.level != level_u:
                continue
            if needle and needle not in item.line.lower() and needle not in item.message.lower():
                continue
            out.append(item.to_dict())
            if len(out) >= limit:
                break
        return out, latest_id

    def tail(self, *, limit: int = 200) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 1000))
        with self._lock:
            chunk = list(self._items)[-limit:]
            latest_id = self._seq
        return [x.to_dict() for x in chunk], latest_id

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def wait_after(self, after_id: int, timeout: float = 25.0) -> Iterator[LogRecordView]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                new = [x for x in self._items if x.id > after_id]
            if new:
                for item in new:
                    yield item
                after_id = new[-1].id
                continue
            time.sleep(0.35)


class _RingHandler(logging.Handler):
    def __init__(self, buffer: LogRingBuffer) -> None:
        super().__init__()
        self._buffer = buffer

    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
            self._buffer.append(record, formatted=line)
        except Exception:
            self.handleError(record)


_buffer: LogRingBuffer | None = None
_ring_attached: set[int] = set()


def get_log_buffer() -> LogRingBuffer:
    global _buffer
    if _buffer is None:
        size = int(os.environ.get("MYCS_LOG_BUFFER_SIZE", str(_DEFAULT_MAX)))
        _buffer = LogRingBuffer(maxlen=size)
    return _buffer


def attach_ring_handler_to_logger(
    logger: logging.Logger,
    *,
    formatter: logging.Formatter | None = None,
) -> None:
    lid = id(logger)
    if lid in _ring_attached:
        return
    handler = _RingHandler(get_log_buffer())
    handler.setFormatter(
        formatter
        or logging.Formatter(f"%(asctime)s [{LOG_TAG}] %(name)s %(levelname)s %(message)s")
    )
    logger.addHandler(handler)
    _ring_attached.add(lid)


def install_log_buffer_handler() -> LogRingBuffer:
    from mycs.log import configure_logging

    configure_logging()
    buf = get_log_buffer()
    logging.getLogger("mycs.api").info("log buffer ready max=%s", buf._maxlen)
    return buf
