from __future__ import annotations

import hashlib
import re
import sqlite3
from pathlib import Path


def _ascii_slug(stem: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", stem).strip("_").lower()
    if len(slug) >= 3 and slug[0].isalpha():
        return slug[:48]
    return ""


def generate_document_id(filename: str, conn: sqlite3.Connection | None = None) -> str:
    """Derive stable, unique document_id from upload filename (no user input)."""
    stem = Path(filename).stem or "upload"
    base = _ascii_slug(stem)
    if not base:
        digest = hashlib.sha256(stem.encode("utf-8")).hexdigest()[:10]
        base = f"doc_{digest}"
    if conn is None:
        return base
    candidate = base
    n = 1
    while _document_id_taken(conn, candidate):
        candidate = f"{base}_{n}"
        n += 1
    return candidate


def _document_id_taken(conn: sqlite3.Connection, document_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM kb_library WHERE document_id = ? LIMIT 1",
        (document_id,),
    ).fetchone()
    if row:
        return True
    row = conn.execute(
        "SELECT 1 FROM wiki_document_mount WHERE document_id = ? LIMIT 1",
        (document_id,),
    ).fetchone()
    if row:
        return True
    uploads = uploads_dir()
    if uploads.is_dir():
        for p in uploads.glob(f"{document_id}.*"):
            if p.is_file():
                return True
    return False


def uploads_dir() -> Path:
    from mycs.paths import uploads_dir as _uploads_dir

    return _uploads_dir()
