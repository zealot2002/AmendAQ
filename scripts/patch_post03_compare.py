#!/usr/bin/env python3
"""Refresh docs/posts/03-when-to-choose-amendaq.md §三 from compare200 results."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULT_PATH = ROOT / "data/eval/compare200/results.json"
POST_PATH = ROOT / "docs/posts/03-when-to-choose-amendaq.md"
REPORT_PATH = ROOT / "docs/对比测试_澄海手册_200条.md"

SYS_LABEL = {
    "amendaq": "AmendAQ",
    "traditional": "传统 RAG",
    "lightrag": "LightRAG",
}


def _pct(ok: int, n: int) -> str:
    return f"{ok}/{n}" if n else "—"


def _cross_stats(payload: dict, prefix: str) -> dict[tuple[str, str], tuple[int, int]]:
    out: dict[tuple[str, str], tuple[int, int]] = {}
    for sys_key in ("amendaq", "traditional", "lightrag"):
        for cond in ("faq", "source"):
            rows = [r for r in payload["systems"][sys_key]["conditions"][cond]["rows"] if r["id"].startswith(prefix)]
            ok = sum(1 for r in rows if r["ok"])
            out[(sys_key, cond)] = (ok, len(rows))
    return out


def _cross_row_mark(payload: dict, qid: str) -> list[str]:
    cells: list[str] = []
    for sys_key in ("amendaq", "traditional", "lightrag"):
        for cond in ("faq", "source"):
            col = f"{SYS_LABEL[sys_key]} {'A' if cond == 'faq' else 'B'}"
            rows = payload["systems"][sys_key]["conditions"][cond]["rows"]
            row = next((r for r in rows if r["id"] == qid), None)
            if row is None:
                cells.append("—")
            else:
                cells.append("对" if row["ok"] else "错")
    return cells


def _extract_report_block(report: str, heading: str) -> str:
    pattern = rf"^## {re.escape(heading)}\s*$"
    m = re.search(pattern, report, re.M)
    if not m:
        return ""
    start = m.end()
    nxt = re.search(r"^## ", report[start:], re.M)
    body = report[start : start + nxt.start()] if nxt else report[start:]
    return body.strip()


def _accuracy_from_report(report: str, section: str) -> str:
    block = _extract_report_block(report, section)
    lines = []
    for line in block.splitlines():
        if line.startswith("| 类型"):
            lines.append("| 类型 | 题数 | AmendAQ | 传统 RAG | LightRAG |")
            lines.append("|---|---|---|---|---|")
            continue
        if line.startswith("| ---"):
            continue
        if not line.startswith("| "):
            continue
        row = [c.strip() for c in line.strip().strip("|").split("|")]
        if row[0] in ("合计", "**合计**"):
            row[0] = "**合计**"
            for i in range(2, 5):
                if i < len(row) and row[i] and not row[i].startswith("**"):
                    row[i] = f"**{row[i]}**"
        out = row
        if out[0] == "合计":
            out[0] = "**合计**"
        if len(out) >= 3 and out[2].startswith("amendaq"):
            pass
        if len(out) >= 3:
            out[2] = out[2].replace("amendaq", "AmendAQ")
        lines.append("| " + " | ".join(out) + " |")
        if out[0].strip("*") == "合计":
            break
    return "\n".join(lines)


def _cost_from_report(report: str, section: str) -> str:
    block = _extract_report_block(report, section)
    out: list[str] = []
    for line in block.splitlines():
        if "| 系统 |" in line:
            out = [line]
            continue
        if out and line.startswith("|"):
            parts = line.split("|")
            if len(parts) > 1 and "amendaq" in parts[1]:
                parts[1] = parts[1].replace("amendaq", "AmendAQ")
            out.append("|".join(parts))
            continue
        if out:
            break
    return "\n".join(out)


def main() -> None:
    payload = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    report = REPORT_PATH.read_text(encoding="utf-8")
    acc_a = _accuracy_from_report(report, "条件 A：两边都只用已发布问答")
    acc_b = _accuracy_from_report(report, "条件 B：对照系统用源手册，AmendAQ 仍用词条")
    cost_a = _cost_from_report(report, "条件 A：两边都只用已发布问答")
    cost_b = _cost_from_report(report, "条件 B：对照系统用源手册，AmendAQ 仍用词条")

    c_stats_faq = _cross_stats(payload, "c_")
    x_stats = _cross_stats(payload, "x_cross_")

    def fmt_cross(stats: dict[tuple[str, str], tuple[int, int]], cond: str) -> str:
        a = stats[("amendaq", cond)]
        t = stats[("traditional", cond)]
        l = stats[("lightrag", cond)]
        return f"AmendAQ **{a[0]}/{a[1]}**；传统 RAG **{t[0]}/{t[1]}**；LightRAG **{l[0]}/{l[1]}**"

    c10_body = _extract_report_block(report, "复杂题（原 10 道）")
    c10_table = ""
    for line in c10_body.splitlines():
        if line.startswith("| 题目"):
            c10_table = "\n".join(
                l.replace("amendaq A", "AmendAQ A").replace("| amendaq", "| AmendAQ") for l in c10_body.splitlines() if l.startswith("|")
            )
            break

    x20_body = _extract_report_block(report, "跨条题（新增 20 道）")
    x20_table = "\n".join(
        l.replace("amendaq A", "AmendAQ A").replace("| amendaq", "| AmendAQ")
        for l in x20_body.splitlines()
        if l.startswith("|")
    )
    x20_note = ""
    for line in x20_body.splitlines():
        if line.startswith("这 20 道"):
            x20_note = line.replace("amendaq", "AmendAQ")
            break

    total_a = (
        c_stats_faq[("amendaq", "faq")][0] + x_stats[("amendaq", "faq")][0],
        c_stats_faq[("amendaq", "faq")][1] + x_stats[("amendaq", "faq")][1],
    )
    total_ta = (
        c_stats_faq[("traditional", "faq")][0] + x_stats[("traditional", "faq")][0],
        c_stats_faq[("traditional", "faq")][1] + x_stats[("traditional", "faq")][1],
    )
    total_tb = (
        c_stats_faq[("traditional", "source")][0] + x_stats[("traditional", "source")][0],
        c_stats_faq[("traditional", "source")][1] + x_stats[("traditional", "source")][1],
    )
    total_aa = total_a
    total_ab = (
        c_stats_faq[("amendaq", "source")][0] + x_stats[("amendaq", "source")][0],
        c_stats_faq[("amendaq", "source")][1] + x_stats[("amendaq", "source")][1],
    )

    def mix30(sys: str, cond: str) -> str:
        c = c_stats_faq[(sys, cond)]
        x = x_stats[(sys, cond)]
        if x[1]:
            return f"{c[0] + x[0]}/{c[1] + x[1]}"
        return f"{c[0]}/{c[1]}（+20 道跨条未纳入 LightRAG）"

    tot_faq = {k: payload["systems"][k]["conditions"]["faq"]["summary"] for k in payload["systems"]}
    tot_src = {k: payload["systems"][k]["conditions"]["source"]["summary"] for k in payload["systems"]}

    section3 = f"""## 三、211 条 · 80 题（主对照）

源手册约 4997 字。AmendAQ 每批 200 条标题，211 条扫两批。在原有 60 题上新增 [20 道跨条题](../跨条题-20.md)，与第 51–60 题组合不重复；**共 30 道**须同时命中两条以上 AQ（原 `c_*` 10 道 + 新增 `x_cross_*` 20 道）。传统 RAG 向量用本目录缓存；LightRAG 跨条 20 道若表内为「—」，表示该轮未跑完或沿用 60 题结果。

### 条件 A：都用已发布问答

**按类型**

{acc_a}

**成本与延迟**

{cost_a}

### 条件 B：对照看源手册

**按类型**

{acc_b}

**成本与延迟**

{cost_b}

### 跨两条以上 AQ · 原 10 道（`c_*`）

{c10_table}

**小计（条件 A）**：{fmt_cross(c_stats_faq, "faq")}。条件 B：AmendAQ **{c_stats_faq[('amendaq', 'source')][0]}/10**；传统 RAG **{c_stats_faq[('traditional', 'source')][0]}/10**；LightRAG **{c_stats_faq[('lightrag', 'source')][0]}/10**。

### 跨条题 · 新增 20 道（`x_cross_*`）

{x20_table}

{x20_note}

### 30 道跨条合计

| 范围 | AmendAQ A | 传统 A | 传统 B | LightRAG A | LightRAG B |
|---|---|---|---|---|---|
| 30 道跨条 | **{total_aa[0]}/{total_aa[1]}** | **{total_ta[0]}/{total_ta[1]}** | **{total_tb[0]}/{total_tb[1]}** | **{mix30('lightrag', 'faq')}** | **{mix30('lightrag', 'source')}** |

> **读表**：总分上传统 RAG 条件 A 仍略高（**{tot_faq['traditional']['ok']}/{tot_faq['traditional']['n']}** vs AmendAQ **{tot_faq['amendaq']['ok']}/{tot_faq['amendaq']['n']}**）。但在**必须凑齐多条 AQ** 的子集里，AmendAQ 在条件 B 为 **{total_ab[0]}/{total_ab[1]}**，高于传统 RAG **{total_tb[0]}/{total_tb[1]}**（条件 A 跨条 30 道：**{total_aa[0]}/{total_aa[1]}** vs **{total_ta[0]}/{total_ta[1]}**）。原 10 道复杂题 AmendAQ 仍为 **10/10**。

### 211 条 · 80 题逐题（对/错）

"""

    # detail table from report
    detail = _extract_report_block(report, "逐题")
    detail_lines = []
    for line in detail.splitlines():
        if not line.startswith("|"):
            continue
        if line.startswith("| 题"):
            detail_lines.append("| 题目 | 类型 | AmendAQ A | 传统 RAG A | 传统 RAG B | LightRAG A | LightRAG B |")
            detail_lines.append("|---|---|---|---|---|---|---|")
            continue
        if line.startswith("| ---"):
            continue
        detail_lines.append(
            line.replace("amendaq A", "AmendAQ A").replace("| amendaq |", "| AmendAQ |")
        )
    section3 += "\n".join(detail_lines) + "\n"

    post = POST_PATH.read_text(encoding="utf-8")
    post = re.sub(
        r"> 公开语料：.*\n",
        "> 公开语料：[测试知识库原文](../对比测试_澄海手册_知识库.md) · [80 题题干与标准答案](../对比测试_澄海手册_题目.md) · [新增跨条 20 道](../跨条题-20.md)\n",
        post,
        count=1,
    )
    post = re.sub(
        r"\*\*211 条 / 60 题\*\*（含 10 道",
        "**211 条 / 80 题**（含 **30 道**跨条：原 10 道",
        post,
        count=1,
    )

    new_post, n = re.subn(
        r"## 三、211 条 · \d+ 题（主对照）.*?## 四、对照表分析",
        section3 + "\n---\n\n## 四、对照表分析",
        post,
        count=1,
        flags=re.S,
    )
    if n != 1:
        raise SystemExit(f"patch section 3 failed: {n}")

    # §四 conclusions
    new_post = re.sub(
        r"- \*\*211 条 / 60 题 / 条件 A\*\*：.*?。\n",
        f"- **211 条 / 80 题 / 条件 A**：传统 RAG **{tot_faq['traditional']['ok']}/{tot_faq['traditional']['n']}**，AmendAQ **{tot_faq['amendaq']['ok']}/{tot_faq['amendaq']['n']}**，LightRAG **{tot_faq['lightrag']['ok']}/{tot_faq['lightrag']['n']}**（LightRAG 合计分母若仍为 60，见上文跨条 20 道说明）。\n",
        new_post,
        count=1,
    )
    new_post = re.sub(
        r"- \*\*条件 B（只看源手册的对照）\*\*：211 条时.*?。\n",
        f"- **条件 B（只看源手册的对照）**：AmendAQ **{tot_src['amendaq']['ok']}/{tot_src['amendaq']['n']}**，传统 RAG **{tot_src['traditional']['ok']}/{tot_src['traditional']['n']}**，LightRAG **{tot_src['lightrag']['ok']}/{tot_src['lightrag']['n']}**。\n",
        new_post,
        count=1,
    )
    new_post = re.sub(
        r"- 跨条 10 道：AmendAQ \*\*10/10\*\*。",
        f"- 跨条 30 道：AmendAQ 条件 A **{total_aa[0]}/{total_aa[1]}**（原 10 道仍 **10/10**）；条件 B **{total_ab[0]}/{total_ab[1]}**，高于传统 RAG **{total_tb[0]}/{total_tb[1]}**。",
        new_post,
        count=1,
    )
    cost_am = payload["systems"]["amendaq"]["conditions"]["faq"]["cost"]
    cost_tr = payload["systems"]["traditional"]["conditions"]["faq"]["cost"]
    cost_lr = payload["systems"]["lightrag"]["conditions"]["faq"]["cost"]
    new_post = re.sub(
        r"- 单题中位：传统 RAG \*\*7\.6s\*\*.*?。\n",
        f"- 单题中位：传统 RAG **{cost_tr.get('median_total_s', 0):.1f}s**，AmendAQ **{cost_am.get('median_total_s', 0):.1f}s**，LightRAG **{cost_lr.get('median_total_s', 0):.1f}s**。\n",
        new_post,
        count=1,
    )
    new_post = re.sub(
        r"- 输入 token 合计：传统 RAG \*\*11\.3 万\*\*.*?。\n",
        f"- 输入 token 合计：传统 RAG **{cost_tr.get('prompt_tokens', 0) / 10000:.1f} 万**，AmendAQ **{cost_am.get('prompt_tokens', 0) / 10000:.1f} 万**，LightRAG **{cost_lr.get('prompt_tokens', 0) / 10000:.1f} 万**。\n",
        new_post,
        count=1,
    )
    new_post = re.sub(
        r"2\. 60 题总分接近.*?。\n",
        f"2. 80 题总分条件 A 传统 **{tot_faq['traditional']['ok']}/{tot_faq['traditional']['n']}** vs AmendAQ **{tot_faq['amendaq']['ok']}/{tot_faq['amendaq']['n']}**；跨条 30 道条件 B 才是 AmendAQ 拉开差距的场景（**{total_ab[0]}/{total_ab[1]}** vs **{total_tb[0]}/{total_tb[1]}**）。\n",
        new_post,
        count=1,
    )
    new_post = re.sub(
        r"3\. 若「更好」指更快更省 → 传统 RAG；.*?差距最多 2 分。\n",
        "3. 若「更好」指更快更省 → 传统 RAG；若指改一条不用重建索引 → AmendAQ；若指多子问题凑齐多条 AQ → 看 30 道跨条子集与条件 B。\n",
        new_post,
        count=1,
    )
    new_post = re.sub(
        r"\| 一题要同时用上两条以上规定，漏一条即错 \| \*\*AmendAQ\*\*：本测 \*\*10/10\*\*；",
        f"| 一题要同时用上两条以上规定，漏一条即错 | **AmendAQ**：原 10 道 **10/10**，30 道合计条件 B **{total_ab[0]}/{total_ab[1]}**；",
        new_post,
        count=1,
    )
    new_post = re.sub(
        r"\*\*语料与题目（全文）\*\*：.*\n",
        "**语料与题目（全文）**：[测试知识库原文](../对比测试_澄海手册_知识库.md) · [80 题题干](../对比测试_澄海手册_题目.md) · [跨条 20 道](../跨条题-20.md)\n",
        new_post,
        count=1,
    )

    POST_PATH.write_text(new_post, encoding="utf-8")
    print("patched", POST_PATH)


if __name__ == "__main__":
    main()