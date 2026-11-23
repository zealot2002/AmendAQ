#!/usr/bin/env -S uv run python
"""Run 10 Xinghe handbook questions; write JSON + markdown report.

NOTE: This script is NOT reproducible in the current repo. It expects
`docs/星河科技_中文员工手册_知识库测试.txt`, which is missing, and it hard-codes
local paths. Use `examples/eval/run_eval.py` for the bundled, runnable demo
evaluation instead.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("AMENDAQ_GRAPH_DOCUMENT", "xinghe_handbook")
os.environ.setdefault("AMENDAQ_DB", str(ROOT / "data" / "amendaq.db"))

from amendaq.agent.loop import AgentLoop  # noqa: E402
from amendaq.llm.factory import create_llm  # noqa: E402

QUESTIONS = [
    "根据星河科技员工手册，如果一个全职员工刚好完成了一个完整工作年度，但之前已经结转了 8 天年假，那么他最多可以拥有多少天的年假余额？为什么？",
    "根据星河科技员工手册，员工发现自己的公司账号可能已经泄露，但他目前还无法确定是否真的被盗。按照员工手册，他应该怎么处理？最晚什么时候必须报告？",
    "根据星河科技员工手册，一名员工每周远程办公 3 天，同时团队把周二和周四设为协作日。这样的安排是否一定违反员工手册？请说明原因。",
    "根据星河科技员工手册，员工购买了一门价值 20,000 新台币的专业课程，希望使用公司的年度学习预算报销。他可以直接申请吗？如果不能，需要谁批准？",
    "根据星河科技员工手册，某员工收到客户赠送的一份价值 1,800 新台币的礼品，同时客户希望员工在后续项目中“优先考虑他们”。员工能不能接受？",
    "根据星河科技员工手册，如果员工在 6 月刚完成一次正式绩效评估，之后因为公司业务方向发生重大变化，他是否可以修改自己的绩效目标？员工手册中有哪些依据支持这个判断？",
    "根据星河科技员工手册，员工想使用一个免费的第三方 AI 工具帮自己分析客户数据。这个工具没有经过公司安全部门批准，但员工认为数据“不太敏感”。根据手册，他应该怎么做？",
    "根据星河科技员工手册，假设员工在周五 17:00 发现公司笔记本电脑丢失，但当天晚上无法联系直属主管。他最合理的处理方式是什么？员工手册是否要求他等到下一个工作日？",
    "根据星河科技员工手册，请找出员工手册中所有明确出现的“金额限制”，并说明每一个金额分别适用于什么场景，以及超过该金额会发生什么。",
    "根据星河科技员工手册，综合员工手册判断：一名员工准备离职，同时还有未使用的年假、尚未报销的业务费用，以及一台公司笔记本电脑在手上。他离职前需要重点处理哪些事项？请分别引用相关规则并区分“必须”和“原则上”。",
]


def _tools_from_trace(result) -> list[str]:
    apis: list[str] = []
    for ev in result.trace:
        if ev.step == "tool":
            api = (ev.payload or {}).get("api")
            if api:
                apis.append(str(api))
    return apis


def _plan_gaps(result) -> list[str]:
    for ev in result.trace:
        if ev.step == "plan":
            reqs = (ev.payload or {}).get("knowledge_requirements") or []
            return [r.get("field", "") for r in reqs]
    return []


def main() -> int:
    out_dir = ROOT / "data" / "eval"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = out_dir / f"xinghe_{ts}.json"
    md_path = ROOT / "docs" / "测试报告_星河科技.md"
    summary_path = ROOT / "docs" / "测试报告_星河科技_评估汇总.md"

    import os

    handbook = ROOT / "docs" / "星河科技_中文员工手册_知识库测试.txt"
    if handbook.is_file() and os.environ.get("AMENDAQ_EVAL_SKIP_INGEST") != "1":
        from amendaq.graph.extract import ingest_txt_file

        os.environ["AMENDAQ_WIKI_AUTO_PUBLISH"] = "1"
        ingest_txt_file(handbook, document_id="xinghe_handbook")
        print("joyjoy: eval re-ingest + publish xinghe_handbook", flush=True)

    llm_backend = os.environ.get("AMENDAQ_LLM") or ("glm" if os.environ.get("GLM_API_KEY") else "ollama")
    glm_model = os.environ.get("GLM_MODEL") or os.environ.get("OPENAI_MODEL") or ""
    pause = float(os.environ.get("AMENDAQ_EVAL_PAUSE_SEC", "12" if "plus" in glm_model else "3"))
    print(f"joyjoy: eval backend={llm_backend} model={glm_model or 'default'} pause={pause}s", flush=True)
    loop = AgentLoop(llm=create_llm())
    rows: list[dict] = []

    for i, q in enumerate(QUESTIONS, start=1):
        print(f"joyjoy: Q{i}/10 ...", flush=True)
        try:
            result = loop.run(q, case_id=None)
            row = {
                "n": i,
                "question": q,
                "answer": result.answer,
                "verify_ok": result.verify.ok,
                "verify_message": result.verify.message,
                "verify_checks": result.verify.checks,
                "plan_gaps": _plan_gaps(result),
                "apis": _tools_from_trace(result),
                "error": None,
            }
        except Exception as exc:
            row = {
                "n": i,
                "question": q,
                "answer": "",
                "verify_ok": False,
                "verify_message": str(exc),
                "verify_checks": [],
                "plan_gaps": [],
                "apis": [],
                "error": str(exc),
            }
        rows.append(row)
        if i < len(QUESTIONS):
            time.sleep(pause)
        json_path.write_text(
            json.dumps(
                {
                    "ts": ts,
                    "document_id": "xinghe_handbook",
                    "llm_backend": llm_backend,
                    "llm_model": glm_model or None,
                    "results": rows,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    _write_markdown(rows, md_path, ts)
    _write_summary(
        rows,
        summary_path,
        ts,
        json_path,
        llm_backend=llm_backend,
        llm_model=glm_model,
    )
    print(f"joyjoy: wrote {md_path}")
    print(f"joyjoy: wrote {summary_path}")
    return 0


def _write_markdown(rows: list[dict], path: Path, ts: str) -> None:
    lines = [
        "# 星河科技员工手册 — 知识库测试报告",
        "",
        f"- 文档：`星河科技_中文员工手册_知识库测试.txt` → `document_id=xinghe_handbook`",
        f"- 执行：`uv run python scripts/run_xinghe_eval.py`（{ts} UTC）",
        "- 后端：**GLM / Ollama** Understand → LLM Plan → Compose + 图 Verify",
        "",
    ]
    for row in rows:
        lines.append(f"## Q{row['n']}")
        lines.append("")
        lines.append(f"**问题**：{row['question']}")
        lines.append("")
        v = "通过" if row["verify_ok"] else "未通过"
        lines.append(f"**Verify**：{v} — {row['verify_message']}")
        lines.append("")
        gaps = row.get("plan_gaps") or []
        if gaps:
            lines.append(f"**Plan 缺口**：{', '.join(gaps)}")
            lines.append("")
        apis = row.get("apis") or []
        if apis:
            lines.append(f"**调用 API**：{', '.join(apis)}")
            lines.append("")
        if row.get("error"):
            lines.append(f"**错误**：{row['error']}")
            lines.append("")
        ans = (row.get("answer") or "").strip()
        lines.append("**回答**：")
        lines.append("")
        lines.append(ans if ans else "（无）")
        lines.append("")
        lines.append("---")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_summary(
    rows: list[dict],
    path: Path,
    ts: str,
    json_path: Path,
    *,
    llm_backend: str,
    llm_model: str = "",
) -> None:
    verify_pass = sum(1 for r in rows if r["verify_ok"])
    multi_gap = sum(1 for r in rows if len(r.get("plan_gaps") or []) >= 2)
    lines = [
        "# 星河科技员工手册 — 测试评估汇总（Wiki TOC + LLM Plan）",
        "",
        f"**执行**：`uv run python scripts/run_xinghe_eval.py`（{ts} UTC）",
        f"**LLM**：`AMENDAQ_LLM={llm_backend}`"
        + (f" · `{llm_model}`" if llm_model else ""),
        f"**原始结果**：`{json_path.relative_to(ROOT)}`",
        "**建图**：`xinghe_handbook`（`data/kg/xinghe_handbook.json`）",
        "",
        "## 本轮架构",
        "",
        "| 项 | 说明 |",
        "|----|------|",
        "| Ingest | TOC-first draft → `AmendAQ wiki publish` |",
        "| Plan | `wiki_toc_outline` + `wiki.toc.branch` / graph 缺口 |",
        "| Verify | `wiki_leaves` + 实体；无检索时禁胡编 |",
        "",
        "## 结果总览",
        "",
        f"| 指标 | 数值 |",
        f"|------|------|",
        f"| Verify 通过 | **{verify_pass}/10** |",
        f"| Plan ≥2 缺口 | **{multi_gap}/10** |",
        "",
        "## 逐题",
        "",
        "| # | Verify | Plan 缺口数 | 内容（人工速评） |",
        "|---|--------|-------------|------------------|",
    ]
    for row in rows:
        v = "✅" if row["verify_ok"] else "❌"
        ng = len(row.get("plan_gaps") or [])
        content = _quick_content_note(row["n"], row.get("answer") or "", row["verify_ok"])
        lines.append(f"| {row['n']} | {v} | {ng} | {content} |")
    lines.extend(
        [
            "",
            "明细：`docs/测试报告_星河科技.md`",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _quick_content_note(n: int, answer: str, verify_ok: bool) -> str:
    if not verify_ok and not answer:
        return "Ollama/运行失败"
    a = answer.lower()
    checks = {
        1: ("20", "5.1", "5.5", "结转"),
        2: ("2", "小时", "8.5", "立即"),
        3: ("不一定", "3.2", "3.3"),
        4: ("18000", "18,000", "部门", "6.4"),
        5: ("不能", "不应", "7.3", "冲突"),
        6: ("6.2", "调整", "目标"),
        7: ("8.4", "批准", "不得"),
        8: ("立即", "8.5", "2", "不必"),
        9: ("18", "2000", "2,000", "礼品", "预算"),
        10: ("11.", "4.3", "5.", "离职", "归还"),
    }
    keys = checks.get(n, ())
    hit = sum(1 for k in keys if k.lower() in a or k in answer)
    if hit >= max(2, len(keys) // 2):
        return "✅ 要点覆盖较好"
    if hit >= 1:
        return "⚠️ 部分要点"
    return "⚠️ 待人工核对"


if __name__ == "__main__":
    raise SystemExit(main())
