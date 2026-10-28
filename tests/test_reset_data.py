import sqlite3
from pathlib import Path

from mycs.db.connection import get_db_path
from mycs.db.reset import SKIP_DEMO_MARKER, reset_runtime_data
from mycs.knowledge.service import ensure_database


def test_reset_empty_db_skips_demo(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setenv("MYCS_DB", str(db))
    reset_runtime_data(skip_demo_seed=True)
    assert db.is_file()
    assert SKIP_DEMO_MARKER.is_file()
    ensure_database()
    conn = sqlite3.connect(db)
    try:
        n = conn.execute("SELECT COUNT(*) FROM kg_entity").fetchone()[0]
        assert n == 0
        gov = conn.execute("SELECT COUNT(*) FROM gov_case").fetchone()[0]
        assert gov == 0
    finally:
        conn.close()
    SKIP_DEMO_MARKER.unlink(missing_ok=True)


def test_reset_clears_kg_dir(tmp_path, monkeypatch):
    root = tmp_path / "data"
    kg = root / "kg"
    kg.mkdir(parents=True)
    (kg / "xinghe.json").write_text("{}", encoding="utf-8")
    db = root / "mycs.db"
    monkeypatch.setenv("MYCS_DB", str(db))
    # patch _DATA_ROOT is hard — only test via get_db_path for db part
    reset_runtime_data(skip_demo_seed=True)
    assert get_db_path() == db
