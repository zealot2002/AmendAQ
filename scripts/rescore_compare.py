#!/usr/bin/env -S uv run python
"""Recompute ok/summary from stored answers. Does not call the model again."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from amendaq.compare.questions import QUESTIONS  # noqa: E402
from amendaq.compare.report import render_report  # noqa: E402
from amendaq.compare.score import score_answer, summarize  # noqa: E402

RESULT_PATH = ROOT / "data" / "eval" / "compare" / "results.json"
REPORT_PATH = ROOT / "docs" / "对比测试_澄海手册.md"
SPECS = {item["id"]: item for item in QUESTIONS}


def main() -> int:
    payload = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    AmendAQ = payload["systems"].get("amendaq")
    if AmendAQ and amendaq.get("_rows"):
        _rescore_rows(amendaq["_rows"])
        view = {
            "summary": summarize(amendaq["_rows"]),
            "cost": amendaq["conditions"]["faq"]["cost"],
            "rows": amendaq["_rows"],
        }
        amendaq["conditions"] = {"faq": view, "source": view}
    for key in ("traditional", "lightrag"):
        block = payload["systems"].get(key)
        if not block:
            continue
        for cond in block.get("conditions", {}).values():
            if not cond.get("rows"):
                continue
            _rescore_rows(cond["rows"])
            cond["summary"] = summarize(cond["rows"])
    RESULT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report = render_report(payload)
    if payload.get("lightrag_skipped"):
        report += f"\nLightRAG 这一轮没有跑完：{payload['lightrag_skipped']}\n"
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"joyjoy: rescored {REPORT_PATH}")
    return 0


def _rescore_rows(rows: list[dict]) -> None:
    for row in rows:
        spec = SPECS[row["id"]]
        scored = score_answer(row.get("answer") or "", spec)
        row["ok"] = scored["ok"]
        row["kind"] = spec["kind"]
        row["missing"] = scored["missing"]
        row["forbidden"] = scored["forbidden"]


if __name__ == "__main__":
    raise SystemExit(main())
