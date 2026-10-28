from __future__ import annotations

import shutil
from pathlib import Path

from mycs.db.bootstrap import ensure_schema
from mycs.db.connection import get_db_path
from mycs.log import get_logger

logger = get_logger(__name__)

_DATA_ROOT = Path(__file__).resolve().parents[3] / "data"
SKIP_DEMO_MARKER = _DATA_ROOT / ".skip_demo_seed"

_CLEAR_DIRS = (
    _DATA_ROOT / "kg",
    _DATA_ROOT / "traces",
    _DATA_ROOT / "eval",
    _DATA_ROOT / "uploads",
)
_CLEAR_FILES = (
    _DATA_ROOT / "wiki" / "canonical.json",
    _DATA_ROOT / "mycs.db",
)


def _clear_dir(path: Path) -> int:
    if not path.is_dir():
        path.mkdir(parents=True, exist_ok=True)
        return 0
    removed = 0
    for child in path.iterdir():
        if child.name.startswith("."):
            continue
        if child.is_file():
            child.unlink()
            removed += 1
        elif child.is_dir():
            shutil.rmtree(child)
            removed += 1
    return removed


def reset_runtime_data(*, skip_demo_seed: bool = True) -> dict[str, object]:
    """
    Remove SQLite + ingested artifacts. Optionally mark DB to skip demo handbook/gov seed.
    Keeps data/sources and data/reference (fixture inputs, not runtime state).
    """
    db_path = get_db_path()
    stats: dict[str, object] = {"db": str(db_path), "files_removed": 0, "skip_demo_seed": skip_demo_seed}

    if db_path.is_file():
        db_path.unlink()
        stats["files_removed"] = int(stats["files_removed"]) + 1  # type: ignore[arg-type]

    for f in _CLEAR_FILES:
        if f.is_file() and f != db_path:
            f.unlink()
            stats["files_removed"] = int(stats["files_removed"]) + 1  # type: ignore[arg-type]

    for d in _CLEAR_DIRS:
        stats["files_removed"] = int(stats["files_removed"]) + _clear_dir(d)  # type: ignore[arg-type]

    if skip_demo_seed:
        SKIP_DEMO_MARKER.parent.mkdir(parents=True, exist_ok=True)
        SKIP_DEMO_MARKER.write_text("1\n", encoding="utf-8")
    else:
        SKIP_DEMO_MARKER.unlink(missing_ok=True)

    ensure_schema(db_path)
    logger.info(
        "joyjoy: reset runtime data db=%s skip_demo=%s removed=%s",
        db_path,
        skip_demo_seed,
        stats["files_removed"],
    )
    return stats


def should_skip_demo_seed() -> bool:
    return SKIP_DEMO_MARKER.is_file()
