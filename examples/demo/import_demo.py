"""Seed the local database with the fictional Stellar Systems demo FAQ.

Run from the repo root:

    uv run python examples/demo/import_demo.py
    uv run python examples/demo/import_demo.py --lang zh

The script creates a knowledge library, imports the demo Q&A as published items,
and prints the resulting document_id so you can ask questions via the Vue UI
or the CLI.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(ROOT / "src"))

from mycs.db.connection import connect, get_db_path
from mycs.kb.service import KbService
from mycs.knowledge.service import ensure_database


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the Stellar Systems demo FAQ")
    parser.add_argument("--lang", choices=["en", "zh"], default="en", help="Which demo FAQ file to import")
    args = parser.parse_args()

    txt_path = Path(__file__).parent / f"stellar_faq.{args.lang}.txt"
    title = "Stellar Systems Demo" if args.lang == "en" else "星际系统演示"
    description = "Fictional employee handbook FAQ for public demo"

    if not txt_path.is_file():
        print(f"Demo FAQ file not found: {txt_path}", file=sys.stderr)
        return 1

    ensure_database()
    text = txt_path.read_text(encoding="utf-8")
    conn = connect(get_db_path())
    try:
        kb = KbService(conn)
        for lib in kb.list_libraries():
            if lib.get("display_title") == title:
                doc_id = lib["document_id"]
                kb.import_items(doc_id, text, as_draft=False)
                conn.commit()
                print(f"joyjoy: re-used demo library {doc_id}")
                return _print_next_steps(doc_id)

        lib = kb.create_library(title=title, description=description)
        doc_id = lib["document_id"]
        kb.import_items(doc_id, text, as_draft=False)
        conn.commit()
        print(f"joyjoy: created demo library {doc_id}")
        return _print_next_steps(doc_id)
    finally:
        conn.close()


def _print_next_steps(doc_id: str) -> int:
    print(f"joyjoy: imported demo FAQ items")
    print(f"joyjoy: next: export MYCS_GRAPH_DOCUMENT={doc_id}")
    print(f"joyjoy:          or select '{doc_id}' in the Vue UI")
    return 0


if __name__ == "__main__":
    sys.exit(main())
