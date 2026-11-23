"""Fixed-width character chunks. Boundaries ignore headings and Q/A lines."""

from __future__ import annotations

CHUNK_CHARS = 500
CHUNK_OVERLAP = 80


def chunk_chars(
    text: str,
    *,
    size: int = CHUNK_CHARS,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    if size <= 0:
        raise ValueError("size must be positive")
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must be >= 0 and smaller than size")
    raw = (text or "").replace("\r\n", "\n")
    if not raw:
        return []
    step = size - overlap
    pieces: list[str] = []
    start = 0
    length = len(raw)
    while start < length:
        piece = raw[start : start + size]
        if piece.strip():
            pieces.append(piece)
        if start + size >= length:
            break
        start += step
    return pieces
