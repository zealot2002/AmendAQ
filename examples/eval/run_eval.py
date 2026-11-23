"""Run a reproducible evaluation against the bundled Stellar Systems demo FAQ.

Run from the repo root:

    uv run python examples/eval/run_eval.py
    uv run python examples/eval/run_eval.py --lang zh

Dry-run (no LLM calls):

    uv run python examples/eval/run_eval.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "eval"

sys.path.insert(0, str(ROOT / "src"))

# These imports only touch the local SQLite layer and do not need an LLM client.
from amendaq.db.connection import connect, get_db_path
from amendaq.kb.service import KbService
from amendaq.knowledge.service import ensure_database


def _norm(text: str) -> str:
    return "".join(text.lower().split())


def _import_demo(lang: str) -> tuple[str, Path, Path]:
    faq_path = ROOT / "examples" / "demo" / f"stellar_faq.{lang}.txt"
    questions_path = ROOT / "examples" / "eval" / f"eval_questions.{lang}.json"
    title = "Stellar Systems Demo" if lang == "en" else "星际系统演示"

    if not faq_path.is_file():
        raise FileNotFoundError(faq_path)
    if not questions_path.is_file():
        raise FileNotFoundError(questions_path)

    ensure_database()
    text = faq_path.read_text(encoding="utf-8")
    conn = connect(get_db_path())
    try:
        kb = KbService(conn)
        for lib in kb.list_libraries():
            if lib.get("display_title") == title:
                doc_id = lib["document_id"]
                kb.import_items(doc_id, text, as_draft=False)
                conn.commit()
                print(f"joyjoy: re-used demo library {doc_id}")
                return doc_id, faq_path, questions_path

        lib = kb.create_library(
            title=title,
            description="Fictional employee handbook FAQ for public demo",
        )
        doc_id = lib["document_id"]
        kb.import_items(doc_id, text, as_draft=False)
        conn.commit()
        print(f"joyjoy: created demo library {doc_id}")
        return doc_id, faq_path, questions_path
    finally:
        conn.close()


def _load_questions(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _score(row: dict[str, Any], lang: str) -> str:
    expected = row["expected_behavior"]
    answer = row["answer"]
    verify_ok = row["verify_ok"]
    norm_answer = _norm(answer)

    if expected == "refuse":
        refuse_keys = (
            ["未找到", "notfound", "norelevant", "拒答", "未检索到", "nosuitable"]
            if lang == "zh"
            else ["未找到", "notfound", "norelevant", "拒答", "未检索到", "nosuitable"]
        )
        if any(k in norm_answer for k in refuse_keys):
            return "fully-correct"
        if verify_ok:
            return "wrong"
        return "partially-correct"

    expected_subs = [str(s).lower() for s in row.get("expected_substrings", [])]
    has_sub = any(s in norm_answer for s in expected_subs)
    if verify_ok and has_sub:
        return "fully-correct"
    if has_sub:
        return "partially-correct"
    return "wrong"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run demo FAQ eval")
    parser.add_argument("--lang", choices=["en", "zh"], default="en", help="Language of the demo FAQ and questions")
    parser.add_argument("--dry-run", action="store_true", help="Import data and validate, but do not call the LLM")
    args = parser.parse_args()

    try:
        doc_id, faq_path, questions_path = _import_demo(args.lang)
    except FileNotFoundError as exc:
        print(f"Missing file: {exc}", file=sys.stderr)
        return 1

    questions = _load_questions(questions_path)

    if args.dry_run:
        print(f"joyjoy: dry-run ok, lang={args.lang}, library={doc_id}, questions={len(questions['questions'])}")
        return 0

    # These imports pull in the LLM client and its HTTP dependencies.
    from amendaq.agent.loop import AgentLoop
    from amendaq.llm.factory import create_llm

    try:
        llm = create_llm()
    except RuntimeError as exc:
        print(f"LLM not configured: {exc}", file=sys.stderr)
        print("Set a provider in .env (e.g. AMENDAQ_LLM=glm + GLM_API_KEY) and try again.", file=sys.stderr)
        return 2

    os.environ["AMENDAQ_GRAPH_DOCUMENT"] = doc_id
    loop = AgentLoop(llm=llm)

    results: list[dict[str, Any]] = []
    counts = {"fully-correct": 0, "partially-correct": 0, "wrong": 0}

    print(f"\nRunning {len(questions['questions'])} questions against {doc_id}...\n")
    for q in questions["questions"]:
        print(f"joyjoy: {q['id']} - {q['question']}")
        try:
            result = loop.run(q["question"], case_id=None)
            answer = result.answer
            verify_ok = result.verify.ok
            verify_msg = result.verify.message
        except Exception as exc:
            answer = f"ERROR: {exc}"
            verify_ok = False
            verify_msg = str(exc)

        row = {
            "id": q["id"],
            "question": q["question"],
            "answer": answer,
            "verify_ok": verify_ok,
            "verify_message": verify_msg,
            "expected_behavior": q["expected_behavior"],
            "expected_substrings": q.get("expected_substrings", []),
        }
        row["score"] = _score(row, args.lang)
        counts[row["score"]] += 1
        results.append(row)
        print(f"  -> {row['score']} (verify_ok={verify_ok})")
        time.sleep(0.5)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = OUT_DIR / f"stellar_demo_{args.lang}_{ts}.json"
    out_path.write_text(
        json.dumps(
            {
                "ts": ts,
                "document_id": doc_id,
                "lang": args.lang,
                "llm_backend": os.environ.get("AMENDAQ_LLM", "unknown"),
                "counts": counts,
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\njoyjoy: wrote report to {out_path}\n")
    print("Summary:")
    print(f"  fully-correct:     {counts['fully-correct']}/{len(results)}")
    print(f"  partially-correct: {counts['partially-correct']}/{len(results)}")
    print(f"  wrong:             {counts['wrong']}/{len(results)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
