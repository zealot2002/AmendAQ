#!/usr/bin/env -S uv run python
"""Compare AmendAQ with a locked traditional RAG pipeline on one policy handbook.

Examples:
  uv run python scripts/run_compare.py
  uv run python scripts/run_compare.py --limit 2
  uv run python scripts/run_compare.py --systems AmendAQ,traditional,lightrag
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from amendaq.env_loader import load_project_dotenv  # noqa: E402

load_project_dotenv()
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from amendaq.compare.corpus import TITLE, iter_faqs, render_faq, render_source  # noqa: E402
from amendaq.compare.lightrag_baseline import available as lightrag_available  # noqa: E402
from amendaq.compare.prepare import build_faq_db  # noqa: E402
from amendaq.compare.questions import QUESTIONS  # noqa: E402
from amendaq.compare.questions_cross20 import CROSS20_QUESTIONS  # noqa: E402
from amendaq.compare.report import render_report  # noqa: E402
from amendaq.compare.score import score_answer, summarize  # noqa: E402
from amendaq.compare.traditional import pipeline_lock  # noqa: E402
from amendaq.llm.factory import create_llm, resolve_llm_model_name  # noqa: E402

OUT_DIR = ROOT / "data" / "eval" / "compare"
DB_PATH = OUT_DIR / "amendaq.db"
REPORT_PATH = ROOT / "docs" / "对比测试_澄海手册.md"
RESULT_PATH = OUT_DIR / "results.json"


def main() -> int:
    global OUT_DIR, DB_PATH, REPORT_PATH, RESULT_PATH
    parser = argparse.ArgumentParser()
    parser.add_argument("--systems", default="AmendAQ,traditional")
    parser.add_argument("--lightrag-condition", default="faq,source")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--report", default="")
    parser.add_argument(
        "--only-prefix",
        default="",
        help="Only run question ids with this prefix (e.g. x_cross_ for the 20 cross-bench items).",
    )
    args = parser.parse_args()
    if args.out_dir:
        OUT_DIR = Path(args.out_dir)
        if not OUT_DIR.is_absolute():
            OUT_DIR = ROOT / OUT_DIR
        DB_PATH = OUT_DIR / "amendaq.db"
        RESULT_PATH = OUT_DIR / "results.json"
    if args.report:
        REPORT_PATH = Path(args.report)
        if not REPORT_PATH.is_absolute():
            REPORT_PATH = ROOT / REPORT_PATH
    _alias = {"amendaq": "amendaq", "AmendAQ": "amendaq", "traditional": "traditional", "lightrag": "lightrag"}
    systems = [_alias.get(item.strip(), item.strip().lower()) for item in args.systems.split(",") if item.strip()]
    if args.limit:
        questions = QUESTIONS[: args.limit]
    elif OUT_DIR.name == "compare200" or str(args.out_dir).rstrip("/").endswith("compare200"):
        questions = QUESTIONS[:60] + list(CROSS20_QUESTIONS)
    else:
        questions = list(QUESTIONS)
    if args.only_prefix:
        questions = [item for item in questions if str(item["id"]).startswith(args.only_prefix)]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    started = time.perf_counter()
    document_id = build_faq_db(DB_PATH)
    index_s = round(time.perf_counter() - started, 3)
    os.environ["AMENDAQ_DB"] = str(DB_PATH)
    os.environ["AMENDAQ_GRAPH_DOCUMENT"] = document_id
    os.environ["AMENDAQ_CHAT_SHOW_EVIDENCE"] = "0"
    print(
        f"joyjoy: compare doc={document_id} faqs={len(iter_faqs())} questions={len(questions)} systems={systems}",
        flush=True,
    )

    payload = _load(RESULT_PATH) if args.resume and RESULT_PATH.is_file() else _fresh(index_s)
    payload["document_id"] = document_id
    payload["faq_count"] = len(iter_faqs())
    payload["source_chars"] = len(render_source())
    payload["faq_chars"] = len(render_faq())
    if args.only_prefix and (
        OUT_DIR.name == "compare200" or str(args.out_dir).rstrip("/").endswith("compare200")
    ):
        payload["question_count"] = 60 + len(CROSS20_QUESTIONS)
    else:
        payload["question_count"] = len(questions)
    payload["generator"] = resolve_llm_model_name()
    payload["lock"] = pipeline_lock()
    payload["title"] = TITLE

    if "amendaq" in systems:
        _run_amendaq(payload, questions)
    if "traditional" in systems:
        _run_traditional(payload, questions)
    if "lightrag" in systems:
        _run_lightrag(
            payload,
            questions,
            conditions=[item.strip() for item in args.lightrag_condition.split(",") if item.strip()],
        )

    _finalize(payload)
    RESULT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report = render_report(payload)
    if payload.get("lightrag_skipped"):
        report += f"\nLightRAG 这一轮没有跑完：{payload['lightrag_skipped']}\n"
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"joyjoy: wrote {REPORT_PATH}", flush=True)
    return 0


def _run_amendaq(payload: dict, questions: list[dict]) -> None:
    from amendaq.agent.loop import AgentLoop

    block = payload["systems"].setdefault(
        "amendaq",
        {"label": "AmendAQ", "conditions": {}},
    )
    done = {row["id"] for row in block.get("_rows", [])}
    llm = create_llm()
    llm.timeout = 180
    loop = AgentLoop(llm=llm)
    rows = list(block.get("_rows", []))
    for index, spec in enumerate(questions, start=1):
        if spec["id"] in done:
            continue
        print(f"joyjoy: AmendAQ {index}/{len(questions)} {spec['id']}", flush=True)
        started = time.perf_counter()
        before = dict(llm.usage_totals)
        try:
            result = loop.run(spec["question"])
            answer = result.answer or ""
            error = None
            llm_calls = _count_llm_calls(result)
        except Exception as exc:
            answer = ""
            error = str(exc)
            llm_calls = 0
            print(f"joyjoy: AmendAQ error {spec['id']}: {exc}", flush=True)
        elapsed = round(time.perf_counter() - started, 3)
        after = llm.usage_totals
        scored = score_answer(answer, spec)
        rows.append(
            {
                "id": spec["id"],
                "kind": spec["kind"],
                "ok": scored["ok"],
                "answer": answer,
                "missing": scored["missing"],
                "forbidden": scored["forbidden"],
                "error": error,
                "total_s": elapsed,
                "retrieve_s": None,
                "generate_s": None,
                "llm_calls": llm_calls,
                "prompt_tokens": after["prompt_tokens"] - before["prompt_tokens"],
                "completion_tokens": after["completion_tokens"] - before["completion_tokens"],
            }
        )
        block["_rows"] = rows
        _write_partial(payload)
    _publish_amendaq(block, payload["index_s"])


def _publish_amendaq(block: dict, index_s: float) -> None:
    rows = block.get("_rows", [])
    cost = _cost(rows, index_s=index_s, index_llm_calls=0)
    view = {"summary": summarize(rows), "cost": cost, "rows": _public_rows(rows)}
    block["conditions"] = {"faq": view, "source": view}


def _run_traditional(payload: dict, questions: list[dict]) -> None:
    from amendaq.compare.traditional import TraditionalRAG

    block = payload["systems"].setdefault(
        "traditional",
        {"label": "传统 RAG", "conditions": {}},
    )
    corpora = {"faq": render_faq(), "source": render_source()}
    for condition, text in corpora.items():
        print(f"joyjoy: traditional index {condition} chars={len(text)}", flush=True)
        rag = TraditionalRAG(text, cache_dir=OUT_DIR / "cache" / condition)
        llm = create_llm()
        llm.timeout = 180
        cond = block["conditions"].setdefault(condition, {"rows": []})
        done = {row["id"] for row in cond["rows"]}
        for index, spec in enumerate(questions, start=1):
            if spec["id"] in done:
                continue
            print(f"joyjoy: traditional {condition} {index}/{len(questions)} {spec['id']}", flush=True)
            try:
                outcome = rag.answer(spec["question"], llm)
                error = None
            except Exception as exc:
                outcome = {
                    "answer": "",
                    "retrieve_s": None,
                    "generate_s": None,
                    "total_s": 0,
                    "llm_calls": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                }
                error = str(exc)
                print(f"joyjoy: traditional error {spec['id']}: {exc}", flush=True)
            scored = score_answer(outcome["answer"], spec)
            cond["rows"].append(
                {
                    "id": spec["id"],
                    "kind": spec["kind"],
                    "ok": scored["ok"],
                    "answer": outcome["answer"],
                    "missing": scored["missing"],
                    "forbidden": scored["forbidden"],
                    "error": error,
                    "total_s": outcome["total_s"],
                    "retrieve_s": outcome["retrieve_s"],
                    "generate_s": outcome["generate_s"],
                    "llm_calls": outcome["llm_calls"],
                    "prompt_tokens": outcome["prompt_tokens"],
                    "completion_tokens": outcome["completion_tokens"],
                }
            )
            cond["index_s"] = rag.index_seconds
            _write_partial(payload)
        cond["summary"] = summarize(cond["rows"])
        cond["cost"] = _cost(cond["rows"], index_s=rag.index_seconds, index_llm_calls=0)
        cond["rows"] = _public_rows(cond["rows"])


def _run_lightrag(payload: dict, questions: list[dict], conditions: list[str] | None = None) -> None:
    ok, reason = lightrag_available()
    if not ok:
        payload["lightrag_skipped"] = reason
        print(f"joyjoy: skip lightrag {reason}", flush=True)
        return
    from amendaq.compare.lightrag_baseline import LightRAGBaseline

    payload.pop("lightrag_skipped", None)
    block = payload["systems"].setdefault(
        "lightrag",
        {"label": "LightRAG", "conditions": {}},
    )
    corpora = {"faq": render_faq(), "source": render_source()}
    selected = conditions or list(corpora)
    for condition, text in corpora.items():
        if condition not in selected:
            continue
        print(f"joyjoy: lightrag index {condition}", flush=True)
        llm = create_llm()
        llm.timeout = 180
        baseline = None
        try:
            try:
                baseline = LightRAGBaseline(
                    text,
                    working_dir=OUT_DIR / "lightrag" / condition,
                    llm=llm,
                )
            except Exception as exc:
                payload["lightrag_skipped"] = f"{condition}: {exc}"
                print(f"joyjoy: skip lightrag {condition}: {exc}", flush=True)
                continue
            cond = block["conditions"].setdefault(condition, {"rows": []})
            done = {row["id"] for row in cond["rows"]}
            for index, spec in enumerate(questions, start=1):
                if spec["id"] in done:
                    continue
                print(f"joyjoy: lightrag {condition} {index}/{len(questions)} {spec['id']}", flush=True)
                try:
                    outcome = baseline.answer(spec["question"])
                    error = None
                except Exception as exc:
                    outcome = {
                        "answer": "",
                        "total_s": 0,
                        "retrieve_s": None,
                        "generate_s": None,
                        "llm_calls": None,
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                    }
                    error = str(exc)
                    print(f"joyjoy: lightrag error {spec['id']}: {exc}", flush=True)
                scored = score_answer(outcome["answer"], spec)
                cond["rows"].append(
                    {
                        "id": spec["id"],
                        "kind": spec["kind"],
                        "ok": scored["ok"],
                        "answer": outcome["answer"],
                        "missing": scored["missing"],
                        "forbidden": scored["forbidden"],
                        "error": error,
                        "total_s": outcome["total_s"],
                        "retrieve_s": outcome["retrieve_s"],
                        "generate_s": outcome["generate_s"],
                        "llm_calls": outcome["llm_calls"],
                        "prompt_tokens": outcome["prompt_tokens"],
                        "completion_tokens": outcome["completion_tokens"],
                    }
                )
                cond["index_s"] = baseline.index_seconds
                _write_partial(payload)
            cond["summary"] = summarize(cond["rows"])
            cond["cost"] = _cost(
                cond["rows"],
                index_s=baseline.index_seconds,
                index_llm_calls=int(baseline.index_llm_calls or 0),
            )
            cond["rows"] = _public_rows(cond["rows"])
        finally:
            if baseline is not None:
                baseline.close()


def _finalize(payload: dict) -> None:
    block = payload["systems"].get("amendaq")
    if block and block.get("_rows") and "faq" not in block.get("conditions", {}):
        _publish_amendaq(block, payload.get("index_s") or 0)


def _public_rows(rows: list[dict]) -> list[dict]:
    kept = []
    for row in rows:
        item = dict(row)
        item.pop("_raw", None)
        kept.append(item)
    return kept


def _cost(rows: list[dict], *, index_s: float, index_llm_calls: int) -> dict:
    return {
        "index_s": index_s,
        "index_llm_calls": index_llm_calls,
        "median_total_s": _median([row["total_s"] for row in rows if row.get("total_s") is not None]),
        "median_retrieve_s": _median([row["retrieve_s"] for row in rows if row.get("retrieve_s") is not None]),
        "median_generate_s": _median([row["generate_s"] for row in rows if row.get("generate_s") is not None]),
        "llm_calls": sum(int(row["llm_calls"] or 0) for row in rows),
        "prompt_tokens": sum(int(row.get("prompt_tokens") or 0) for row in rows),
        "completion_tokens": sum(int(row.get("completion_tokens") or 0) for row in rows),
    }


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return round(ordered[mid], 3)
    return round((ordered[mid - 1] + ordered[mid]) / 2, 3)


def _count_llm_calls(result) -> int:
    total = 0
    for event in result.trace:
        calls = (event.payload or {}).get("llm_calls")
        if isinstance(calls, list):
            total += len(calls)
    return total


def _fresh(index_s: float) -> dict:
    return {"index_s": index_s, "systems": {}}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_partial(payload: dict) -> None:
    RESULT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
