from __future__ import annotations

import os
from pathlib import Path

from mycs.db.connection import get_db_path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def uploads_dir() -> Path:
    return repo_root() / "data" / "uploads"


def traces_dir() -> Path:
    raw = os.environ.get("MYCS_TRACE_DIR", "")
    return Path(raw) if raw else repo_root() / "data" / "traces"


def kg_dir() -> Path:
    return repo_root() / "data" / "kg"


def dev_logs_dir() -> Path:
    return repo_root() / "data" / "dev-logs"


def runtime_paths() -> dict[str, str]:
    return {
        "repo": str(repo_root()),
        "db": str(get_db_path()),
        "uploads": str(uploads_dir()),
        "traces": str(traces_dir()),
        "kg": str(kg_dir()),
        "dev_logs": str(dev_logs_dir()),
    }
