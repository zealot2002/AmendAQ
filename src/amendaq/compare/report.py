"""Write the comparison note from scored rows. No ranking language."""

from __future__ import annotations

from amendaq.compare.questions import QUESTIONS
from amendaq.compare.score import summarize

KIND_LABEL = {
    "lookup": "单点查找",
    "obligation": "义务对错",
    "number": "数字",
    "refusal": "拒答",
    "fabrication": "不编造",
}


def _pct(ok: int, n: int) -> str:
    if n == 0:
        return "—"
    return f"{ok}/{n}"


def render_report(payload: dict) -> str:
    systems = payload["systems"]
    lines = [
        "# 澄海精密员工手册 — 对照",
        "",
        "这不是「击败目前最好的 RAG」。对照只锁了一条传统管线，外加可选的 LightRAG。公开基准各测各的场景，这里的数字不能当成冠军榜。",
        "",
        "知识库原文在 [对比测试_澄海手册_知识库.md](对比测试_澄海手册_知识库.md)。完整题目在 [对比测试_澄海手册_题目.md](对比测试_澄海手册_题目.md)。",
        "",
        f"- 生成模型：`{payload['generator']}`，AmendAQ 与对照系统使用同一个接口。",
        f"- 已发布问答：{payload['faq_count']} 条。源手册：{payload['source_chars']} 字。",
        f"- 题目：{payload['question_count']}。星河那套十几题只做冒烟，不写进这张表。",
        "- 传统管线：固定 500 字切分，重叠 80 字；jieba 搜索模式 BM25；"
        f"`{payload['lock']['embed_model']}`（{payload['lock'].get('embed_revision') or '见运行记录'}）；"
        f"RRF 后用 `{payload['lock']['rerank_model']}`"
        f"（{payload['lock'].get('rerank_revision') or '见运行记录'}）取前 5 段。",
        "- 嵌入和重排只出现在对照系统里。型号以本次运行下载到的修订为准，写在上面。",
        "- LightRAG 1.5.8 用它自己的默认查询（mix），嵌入和重排与传统管线是同一对模型。",
        "- GraphRAG 没有进这张表。",
        "- 适用范围：一次送一个标题，几十到一百来条已发布问答。不是百万文档搜索。",
        "",
        "两个条件都列在下面。条件 A：对照系统和 AmendAQ 都只看已发布问答。条件 B：传统 RAG 与 LightRAG 看源手册正文，AmendAQ 仍看整理后的词条。AmendAQ 没有第二套语料，所以两张表里的 AmendAQ 列是同一次运行。",
        "",
        "整理稿里有运营写明的「手册没有这条规定」。源手册不收录这些句子。条件 A 里对照系统也能看到它们；条件 B 看不到。",
        "",
    ]
    if int(payload.get("faq_count") or 0) >= 200:
        lines.insert(
            6,
            (
                f"- 这一轮已发布问答 {payload['faq_count']} 条。AmendAQ 每批送 200 条标题，扫完所有批次。"
                + (
                    "含原 10 道复杂题与新增 20 道跨条题，共 30 道须同时命中两条以上已发布问答。"
                    if int(payload.get("question_count") or 0) >= 80
                    else (
                        "最后 10 道是必须跨多条已发布问答的复杂题。"
                        if int(payload.get("question_count") or 0) >= 60
                        else "题目含原来的 48 题和追加题。"
                    )
                )
                + "传统管线的向量沿用本次目录里的缓存，表上的索引耗时是加载缓存的时间。LightRAG 的索引耗时仍是第一次抽取图谱的时间。"
            ),
        )
    else:
        lines.insert(
            8,
            "- 103 条那一轮里，LightRAG 条件 A 的前两题是重排接上之前留下的，从第 3 题起有重排。",
        )
    for condition, title in (
        ("faq", "条件 A：两边都只用已发布问答"),
        ("source", "条件 B：对照系统用源手册，AmendAQ 仍用词条"),
    ):
        lines.append(f"## {title}")
        lines.append("")
        lines.append(_accuracy_table(systems, condition))
        lines.append("")
        lines.append(_cost_table(systems, condition))
        lines.append("")
        lines.extend(_kind_notes(systems, condition))
        lines.append("")
    lines.extend(_complex_section(systems, "c_", "复杂题（原 10 道）", "下面 10 道是后补的。每道都要同时用到两条以上已发布问答，只命中其中一条算没答全。"))
    lines.extend(_complex_section(systems, "x_cross_", "跨条题（新增 20 道）", "下面 20 道与第 51–60 题组合不重复。每道都要同时用到两条以上已发布问答。"))
    lines.append("## 逐题")
    lines.append("")
    lines.append(_detail_table(systems))
    lines.append("")
    return "\n".join(lines)


def _accuracy_table(systems: dict, condition: str) -> str:
    header = ["类型", "题数"]
    keys = _system_keys(systems, condition)
    header.extend(_system_label(systems, key) for key in keys)
    rows = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    kinds = ["lookup", "obligation", "number", "refusal", "fabrication"]
    totals = {key: [0, 0] for key in keys}
    for kind in kinds:
        cells = [KIND_LABEL[kind], ""]
        n_per_key: list[int] = []
        for key in keys:
            summary = systems[key]["conditions"][condition]["summary"]["by_kind"].get(kind, {"n": 0, "ok": 0})
            n_per_key.append(summary["n"])
            cells.append(_pct(summary["ok"], summary["n"]))
            totals[key][0] += summary["ok"]
            totals[key][1] += summary["n"]
        cells[1] = str(max(n_per_key) if n_per_key else 0)
        rows.append("| " + " | ".join(cells) + " |")
    total_cells = ["合计", str(next(iter(totals.values()))[1] if totals else 0)]
    for key in keys:
        ok, n = totals[key]
        total_cells.append(_pct(ok, n))
    rows.append("| " + " | ".join(total_cells) + " |")
    return "\n".join(rows)


def _cost_table(systems: dict, condition: str) -> str:
    lines = [
        "| 系统 | 索引耗时 | 索引生成次数 | 单题耗时中位 | 单题检索中位 | 单题生成中位 | 生成次数 | 输入 token | 输出 token |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for key in _system_keys(systems, condition):
        block = systems[key]["conditions"][condition]
        cost = block["cost"]
        lines.append(
            "| "
            + " | ".join(
                [
                    _system_label(systems, key),
                    _seconds(cost.get("index_s")),
                    str(cost.get("index_llm_calls", 0)),
                    _seconds(cost.get("median_total_s")),
                    _seconds(cost.get("median_retrieve_s")),
                    _seconds(cost.get("median_generate_s")),
                    str(cost.get("llm_calls", 0)),
                    str(cost.get("prompt_tokens", 0)),
                    str(cost.get("completion_tokens", 0)),
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def _kind_notes(systems: dict, condition: str) -> list[str]:
    keys = _system_keys(systems, condition)
    if "amendaq" not in keys:
        return []
    notes = ["这一条件下，只按上表已经分出高低的类型来说："]
    mine = systems["amendaq"]["conditions"][condition]["summary"]["by_kind"]
    others = [key for key in keys if key != "amendaq"]
    any_line = False
    for kind in ["lookup", "obligation", "number", "refusal", "fabrication"]:
        my = mine.get(kind, {"n": 0, "ok": 0})
        if my["n"] == 0:
            continue
        my_rate = my["ok"] / my["n"]
        for key in others:
            other = systems[key]["conditions"][condition]["summary"]["by_kind"].get(kind, {"n": 0, "ok": 0})
            if other["n"] == 0:
                continue
            rate = other["ok"] / other["n"]
            label = _system_label(systems, key)
            if my_rate > rate:
                notes.append(
                    f"- {KIND_LABEL[kind]}：AmendAQ {_pct(my['ok'], my['n'])}，{label} {_pct(other['ok'], other['n'])}。"
                )
                any_line = True
            elif rate > my_rate:
                notes.append(
                    f"- {KIND_LABEL[kind]}：{label} 更高，{_pct(other['ok'], other['n'])}；AmendAQ 是 {_pct(my['ok'], my['n'])}。"
                )
                any_line = True
    my_cost = systems["amendaq"]["conditions"][condition]["cost"]
    for key in others:
        other_cost = systems[key]["conditions"][condition]["cost"]
        my_med = my_cost.get("median_total_s")
        other_med = other_cost.get("median_total_s")
        if my_med is None or other_med is None:
            continue
        label = _system_label(systems, key)
        if other_med < my_med:
            notes.append(
                f"- 延迟：{label} 单题中位 {other_med:.1f} 秒，AmendAQ {my_med:.1f} 秒。"
            )
            any_line = True
        elif my_med < other_med:
            notes.append(
                f"- 延迟：AmendAQ 单题中位 {my_med:.1f} 秒，{label} {other_med:.1f} 秒。"
            )
            any_line = True
    if not any_line:
        notes.append("- 这一轮没有分出高低。")
    return notes


def _detail_table(systems: dict) -> str:
    keys = [key for key in ("amendaq", "traditional", "lightrag") if key in systems]
    header = ["题", "类型"]
    for key in keys:
        header.append(_system_label(systems, key) + " A")
        if key != "amendaq":
            header.append(_system_label(systems, key) + " B")
    rows = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    by_id = {item["id"]: item for item in QUESTIONS}
    seen: set[str] = set()
    for key in keys:
        for cond in ("faq", "source"):
            for row in systems[key]["conditions"].get(cond, {}).get("rows", []):
                seen.add(row["id"])
    order = [item["id"] for item in QUESTIONS if item["id"] in seen]
    for qid in order:
        spec = by_id[qid]
        cells = [spec.get("question") or qid, KIND_LABEL.get(spec["kind"], spec["kind"])]
        for key in keys:
            faq_rows = systems[key]["conditions"].get("faq", {}).get("rows", [])
            cells.append(_mark(faq_rows, qid))
            if key != "amendaq":
                source_rows = systems[key]["conditions"].get("source", {}).get("rows", [])
                cells.append(_mark(source_rows, qid))
        rows.append("| " + " | ".join(cells) + " |")
    return "\n".join(rows)


def _complex_section(systems: dict, prefix: str, heading: str, intro: str) -> list[str]:
    specs = [item for item in QUESTIONS if str(item["id"]).startswith(prefix)]
    if not specs:
        return []
    amendaq_rows = systems.get("amendaq", {}).get("conditions", {}).get("faq", {}).get("rows", [])
    have = {row["id"] for row in amendaq_rows}
    if any(spec["id"] not in have for spec in specs):
        return []
    keys = [key for key in ("amendaq", "traditional", "lightrag") if key in systems]
    lines = [f"## {heading}", "", intro, ""]
    header = ["题目", "类型"]
    for key in keys:
        header.append(_system_label(systems, key) + " A")
        if key != "amendaq":
            header.append(_system_label(systems, key) + " B")
    rows = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    totals = {key: {"faq": [0, 0], "source": [0, 0]} for key in keys}
    for spec in specs:
        cells = [spec.get("question") or spec["id"], KIND_LABEL.get(spec["kind"], spec["kind"])]
        for key in keys:
            for cond in ("faq", "source"):
                if key == "amendaq" and cond == "source":
                    continue
                cond_rows = systems[key]["conditions"].get(cond, {}).get("rows", [])
                mark = _mark(cond_rows, spec["id"])
                cells.append(mark)
                totals[key][cond][1] += 1
                if mark == "对":
                    totals[key][cond][0] += 1
        rows.append("| " + " | ".join(cells) + " |")
    lines.extend(rows)
    lines.append("")
    bits = []
    for key in keys:
        label = _system_label(systems, key)
        faq_ok, faq_n = totals[key]["faq"]
        if key == "amendaq":
            bits.append(f"{label} {faq_ok}/{faq_n}")
            continue
        source_ok, source_n = totals[key]["source"]
        bits.append(f"{label} 条件 A {faq_ok}/{faq_n}、条件 B {source_ok}/{source_n}")
    lines.append(f"这 {len(specs)} 道单独计：" + "；".join(bits) + "。")
    lines.append("")
    return lines


def _mark(rows: list[dict], qid: str) -> str:
    for row in rows:
        if row["id"] == qid:
            return "对" if row["ok"] else "错"
    return "—"


def _system_keys(systems: dict, condition: str) -> list[str]:
    keys = []
    for key in ("amendaq", "traditional", "lightrag"):
        if key in systems and condition in systems[key]["conditions"]:
            keys.append(key)
    return keys


def _system_label(systems: dict, key: str) -> str:
    return systems[key].get("label", key)


def _seconds(value: object) -> str:
    if value is None:
        return "—"
    return f"{float(value):.1f}s"


def empty_summary() -> dict:
    return summarize([])
