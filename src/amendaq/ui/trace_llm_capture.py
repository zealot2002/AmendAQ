from __future__ import annotations

import contextvars
from typing import Any

_buffer: contextvars.ContextVar[list[dict[str, Any]] | None] = contextvars.ContextVar(
    "amendaq_llm_trace_buffer",
    default=None,
)


def begin_llm_capture() -> None:
    _buffer.set([])


def is_capturing() -> bool:
    return _buffer.get() is not None


def record_llm_exchange(
    *,
    system: str,
    user: str,
    response_text: str,
    json_mode: bool,
    model: str,
    api_response: dict[str, Any] | None = None,
) -> None:
    buf = _buffer.get()
    if buf is None:
        return
    usage = None
    if api_response and isinstance(api_response.get("usage"), dict):
        usage = api_response.get("usage")
    buf.append(
        {
            "model": model,
            "json_mode": json_mode,
            "request": {
                "system": system,
                "user": user,
            },
            "response_text": response_text,
            "usage": usage,
            "response_api": api_response,
        }
    )


def take_llm_captures() -> list[dict[str, Any]]:
    buf = _buffer.get()
    if not buf:
        return []
    out = list(buf)
    buf.clear()
    return out
