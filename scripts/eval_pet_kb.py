#!/usr/bin/env python3
"""Batch-evaluate FAQ agent against kb_宠物饲养指南; prints JSON summary."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from amendaq.agent.loop import AgentLoop
from amendaq.env_loader import load_project_dotenv
from amendaq.llm.factory import create_llm

DOC = "kb_宠物饲养指南"

CASES: list[dict[str, str]] = [
    {"id": "exact", "q": "幼宠刚到家不吃东西正常吗？"},
    {"id": "paraphrase", "q": "小狗刚抱回家不肯吃狗粮怎么办？"},
    {"id": "compare", "q": "养猫和养狗最大的区别是什么？"},
    {"id": "prep", "q": "接新宠物回家前要准备什么？"},
    {"id": "enumerative", "q": "新手养宠物需要准备哪些东西？"},
    {"id": "vague", "q": "疫苗"},
    {"id": "multi", "q": "猫要打哪些疫苗，分别什么时候打？"},
    {"id": "offtopic", "q": "星河科技员工年终奖怎么发？"},
    {"id": "whole_list", "q": "这份指南里和狗相关的问答有哪些？"},
    {"id": "nonsense", "q": "沉香手串怎么保养？"},
]


def _trace_metric(result) -> dict:
    leaf_count = None
    batches = None
    trimmed = False
    picks_before = None
    for ev in result.trace:
        if ev.step == "faq_flat_recall":
            leaf_count = ev.payload.get("leaf_count")
            batches = ev.payload.get("entry_batches")
        if ev.step == "faq_title_batch":
            for row in ev.payload.get("llm_calls") or []:
                pass
            phase = ev.payload.get("phase")
            if phase == "faq_title_rerank":
                trimmed = True
                picks_before = ev.payload.get("before")
    return {
        "leaf_count": leaf_count,
        "entry_batches": batches,
        "trimmed": trimmed,
        "picks_before_trim": picks_before,
        "verify_ok": result.verify.ok,
        "verify_msg": result.verify.message,
        "elapsed_s": result.elapsed_seconds,
        "answer_len": len(result.answer),
        "answer_preview": (result.answer or "")[:280].replace("\n", " "),
    }


def main() -> int:
    load_project_dotenv()
    os.environ["AMENDAQ_GRAPH_DOCUMENT"] = DOC
    llm = create_llm()
    loop = AgentLoop(llm=llm)
    out: list[dict] = []
    for case in CASES:
        t0 = time.perf_counter()
        try:
            result = loop.run(case["q"])
            err = None
        except Exception as exc:
            result = None
            err = str(exc)
        wall = round(time.perf_counter() - t0, 1)
        row = {
            "id": case["id"],
            "question": case["q"],
            "wall_s": wall,
            "error": err,
        }
        if result:
            row.update(_trace_metric(result))
        out.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    summary = {
        "document_id": DOC,
        "cases": len(out),
        "errors": sum(1 for r in out if r.get("error")),
        "verify_fail": sum(1 for r in out if not r.get("error") and not r.get("verify_ok")),
        "avg_elapsed": round(
            sum(r.get("elapsed_s") or 0 for r in out if not r.get("error"))
            / max(1, sum(1 for r in out if not r.get("error"))),
            1,
        ),
        "max_leaf_count": max((r.get("leaf_count") or 0 for r in out if not r.get("error")), default=0),
    }
    print("SUMMARY", json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())