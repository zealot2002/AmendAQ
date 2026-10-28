from __future__ import annotations

import os
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[3] / "data" / "mycs.db"


def get_db_path() -> Path:
    raw = os.environ.get("MYCS_DB", "")
    return Path(raw) if raw else DEFAULT_DB


def connect(path: Path | None = None) -> sqlite3.Connection:
    db = path or get_db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
