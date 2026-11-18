from __future__ import annotations

from typing import Any

from mycs.llm.factory import resolve_llm_model_name
from mycs.ui.trace_kinds import resolve_step_kind

_INTENT_ZH = {
    "graph_qa": "员工手册 / 政策问答",
    "handbook_qa": "员工手册问答",
    "case_status_and_policy_limit": "办件进度与时限",
    "procedure_online_only": "能否线上办理",
}

_GAP_ZH = {
    "graph.entity.search": "在知识库中搜索相关条款",
    "graph.entity.by_section": "按章节号读取条款",
    "graph.read.query": "汇总或统计类查询",
    "wiki.toc.branch": "打开某一章节的子目录",
    "wiki.toc.leaves": "读取具体条目正文",
    "wiki.toc.outline": "读取已发布目录树",
}

_OUTLINE_SOURCE_ZH = {
    "chapter_filter": "按大模型选中的章，从数据库截取节/条摘要",
    "tool_outline": "通过知识工具拉取全量目录后再本地使用",
    "local_filter": "在目录结果上按 drill 范围本地过滤",
}


def enrich_display(step: str, payload: dict[str, Any], *, question: str) -> dict[str, Any]:
    """Add 小白-friendly display block; keep raw payload for debug."""
    kind, kind_label = resolve_step_kind(step, payload)
    out = dict(payload)
    display = _narrate(step, payload, question=question)
    display["step_kind"] = kind
    display["step_kind_label"] = kind_label
    out["step_kind"] = kind
    out["step_kind_label"] = kind_label
    out["display"] = display
    return out


def _llm_label(p: dict[str, Any] | None = None) -> str:
    """Show active backend model (智谱 GLM when MYCS_LLM=glm)."""
    if isinstance(p, dict):
        calls = p.get("llm_calls")
        if isinstance(calls, list):
            backend = resolve_llm_model_name()
            for call in calls:
                if not isinstance(call, dict):
                    continue
                model = str(call.get("model") or "").strip()
                if not model:
                    continue
                if model.lower().startswith("qwen") and "智谱" in backend:
                    return backend
                if "glm" in model.lower() or "智谱" in backend:
                    return resolve_llm_model_name("glm")
                return model
    return resolve_llm_model_name()


def _narrate(step: str, p: dict[str, Any], *, question: str) -> dict[str, str]:
    if step == "understand":
        intent = str(p.get("intent") or "")
        doc_id = str(p.get("graph_document_id") or "").strip()
        doc_name = str(p.get("graph_document_title") or "").strip()
        doc_label = doc_name or doc_id or "（未指定）"
        return {
            "summary": f"调用 {_llm_label(p)}：识别问题类型、关联手册（本步会消耗大模型配额）。",
            "input": _clip(question, 500),
            "output": f"类型：{_INTENT_ZH.get(intent, intent)}；手册：{doc_label}",
        }

    if step == "toc_drill":
        mode = str(p.get("mode") or "")
        if mode == "pipeline_skip":
            reason = str(p.get("reason") or "")
            if reason == "composite_query_skip_drill":
                return {
                    "summary": "编排：识别为综合/多事项问题，跳过「逐层点选到单条」以免漏章。",
                    "input": _clip(question, 280),
                    "output": str(p.get("detail") or "将分批选章（4/5/11 等）"),
                }
            return {
                "summary": "编排：根据规则决定目录策略（不调大模型）。",
                "input": _clip(question, 280),
                "output": str(p.get("detail") or p.get("reason") or "跳过逐层目录"),
            }
        if mode == "pipeline_stop":
            return {
                "summary": "编排：当前目录层无子节点，停止下钻。",
                "input": f"层级 {p.get('level', '—')}",
                "output": str(p.get("reason") or "no_children"),
            }
        if mode == "auto_pick":
            picked = p.get("picked") if isinstance(p.get("picked"), dict) else {}
            label = f"{picked.get('section_ref', '')} {picked.get('title', '')}".strip()
            return {
                "summary": "编排：该层仅一个选项，自动进入（不调大模型）。",
                "input": f"层级 {p.get('level', '—')}",
                "output": label or str(p.get("reason") or ""),
            }
        if mode == "scope_release":
            return {
                "summary": "编排：当前章不足以作答，解除目录范围锁定，改分批选章检索。",
                "input": _clip(question, 240),
                "output": str(p.get("reason") or p.get("detail") or "—"),
            }
        if mode == "sibling_expand":
            sibs = p.get("siblings") or []
            labels = "、".join(
                f"{s.get('section_ref', '')} {s.get('title', '')}".strip()
                for s in sibs
                if isinstance(s, dict)
            )
            picked = p.get("picked") if isinstance(p.get("picked"), dict) else {}
            picked_label = f"{picked.get('section_ref', '')} {picked.get('title', '')}".strip()
            return {
                "summary": "编排：同章相关条款一并纳入检索（不调大模型）。",
                "input": f"下钻落到：{picked_label or '—'}",
                "output": f"追加：{labels or '—'}",
            }
        if mode == "llm_pick":
            choices = p.get("choices") or []
            opts = "、".join(
                f"{c.get('section_ref', '')} {c.get('title', '')}".strip()
                for c in choices
                if isinstance(c, dict)
            )[:350]
            dec = p.get("decision") if isinstance(p.get("decision"), dict) else {}
            pick_id = dec.get("node_id")
            pick_label = next(
                (
                    f"{c.get('section_ref', '')} {c.get('title', '')}".strip()
                    for c in choices
                    if isinstance(c, dict) and c.get("node_id") == pick_id
                ),
                str(pick_id or "—"),
            )
            return {
                "summary": f"调用 {_llm_label(p)}：在第 {p.get('level', '?')} 层目录中选一继续（本步消耗大模型）。",
                "input": f"可选项：{opts or '—'}",
                "output": f"选择：{pick_label}；说明：{dec.get('reason') or '—'}",
            }
        if mode == "outcome":
            path = p.get("path") or []
            chain = " → ".join(
                f"{n.get('section_ref', '')} {n.get('title', '')}".strip()
                for n in path
                if isinstance(n, dict)
            )
            llm = "是" if p.get("llm_invoked") else "否"
            return {
                "summary": "编排：目录下钻结束，汇总定位结果。",
                "input": f"本路径是否调用过大模型：{llm}",
                "output": f"范围：{chain or '（未缩小到具体章）'}；原因：{p.get('reason') or '—'}",
            }
        reason = str(p.get("reason") or "")
        path = p.get("path") or []
        chain = " → ".join(
            f"{n.get('section_ref', '')} {n.get('title', '')}".strip()
            for n in path
            if isinstance(n, dict)
        )
        return {
            "summary": "目录定位。",
            "input": _clip(question, 200),
            "output": chain or reason or "—",
        }

    if step == "toc_catalog_batch":
        bi = int(p.get("batch_index") or 0)
        bt = int(p.get("batch_total") or 0)
        action = str(p.get("action") or "")
        refs = p.get("section_refs") or []
        reason = str(p.get("reason") or "")
        offered = p.get("chapters_offered") or []
        offered_txt = "、".join(
            f"{c.get('section_ref', '')} {c.get('title', '')}".strip()
            for c in offered
            if isinstance(c, dict)
        )[:400]
        action_zh = {
            "pick": "本批选中相关章",
            "continue": "本批无相关章，继续下一批",
            "done": "目录已够，停止浏览",
            "need_full_handbook": "需要通读全手册",
        }.get(action, action)
        picked = "、".join(str(r) for r in refs) if refs else "（本批未选章）"
        return {
            "summary": f"调用 {_llm_label(p)}：章级目录第 {bi}/{bt} 批（每批一次大模型）。",
            "input": f"本批章：{offered_txt or '—'}",
            "output": f"{action_zh}；选中 {picked}。{reason}".strip(),
        }

    if step in ("outline", "toc"):
        n = int(p.get("outline_count") or 0)
        scoped = p.get("scoped")
        sel = p.get("selected_chapters") or []
        src = str(p.get("source") or "")
        doc_name = str(p.get("document_title") or "").strip()
        doc_id = str(p.get("document_id") or "").strip()
        doc_label = doc_name or doc_id or "—"
        return {
            "summary": (
                "读库：同章相关条款已并入目录摘要（SQLite，不调大模型）。"
                if src == "sibling_expand"
                else "读库：组装交给 Plan 的目录摘要（SQLite，不调大模型）。"
                if src != "tool_outline"
                else "读库：Plan 前目录摘要（部分数据来自上一步知识检索）。"
            ),
            "input": f"手册：{doc_label}；方式：{_OUTLINE_SOURCE_ZH.get(src, src or '—')}",
            "output": (
                f"共 {n} 条节点，合法 leaf {int(p.get('valid_leaf_count') or 0)} 个；"
                f"{'已缩小范围' if scoped else '较宽范围'}"
                + (f"；选中 {len(sel)} 章" if sel else "")
            ),
        }

    if step == "plan":
        reqs = p.get("knowledge_requirements") or []
        lines = []
        for i, r in enumerate(reqs, 1):
            if not isinstance(r, dict):
                continue
            field = str(r.get("field") or "")
            lines.append(f"{i}. {_GAP_ZH.get(field, field)}")
        body = "\n".join(lines) if lines else "（空计划）"
        return {
            "summary": f"调用 {_llm_label(p)}：把目录上下文转成「知识缺口」列表（本步消耗大模型）。",
            "input": _clip(question, 400),
            "output": body,
        }

    if step == "plan_guard":
        return {
            "summary": "编排：用已加载 leaf 条号白名单过滤 Plan（本地规则，不调大模型）。",
            "input": f"Plan 产出 {int(p.get('requirements_before') or 0)} 条缺口",
            "output": (
                f"保留 {int(p.get('requirements_after') or 0)} 条；"
                f"剔除越界 by_section {int(p.get('dropped_by_whitelist') or 0)} 条"
            ),
        }

    if step == "tool":
        gap = str(p.get("gap") or "")
        api = str(p.get("api") or "")
        params = p.get("params") if isinstance(p.get("params"), dict) else {}
        result = p.get("result") if isinstance(p.get("result"), dict) else {}
        inp = ""
        if gap == "wiki.toc.branch":
            root = result.get("root") if isinstance(result.get("root"), dict) else {}
            sec = str(root.get("section_ref") or params.get("section_prefix") or "").strip()
            tit = str(root.get("title") or "").strip()
            if sec or tit:
                inp = f"{sec} {tit}".strip()
        if not inp:
            inp = _clip(
                str(
                    params.get("query")
                    or params.get("section")
                    or params.get("section_prefix")
                    or params.get("document_id")
                    or params
                ),
                300,
            )
        retry_note = "（范围检索无结果后，已自动扩大为全库关键词重试）" if p.get("retried_unscoped") else ""
        if result.get("ok") is False:
            out = f"未查到有效内容（{result.get('error', '无结果')}）"
        elif "hits" in result:
            hits = result.get("hits") or []
            parts = [
                f"§{h.get('section', h.get('section_ref', '?'))} {str(h.get('name', ''))[:40]}"
                for h in hits[:5]
                if isinstance(h, dict)
            ]
            out = f"找到 {result.get('count', len(hits))} 条：" + ("；".join(parts) if parts else "无匹配")
        elif "leaf_count" in result or "leaf_sections" in result:
            secs = result.get("leaf_sections") or []
            out = f"该节点下 {result.get('leaf_count', len(secs))} 个条目" + (
                f"（如 {', '.join(str(s) for s in secs[:5])}）" if secs else ""
            )
        elif "outline_count" in result:
            out = f"目录 {result.get('outline_count', 0)} 条"
        elif "row_count" in result:
            out = f"查询返回 {result.get('row_count', 0)} 行"
        else:
            out = f"已完成（{api}）"
        return {
            "summary": f"知识检索：{_GAP_ZH.get(gap, gap)}（ToolRegistry → SQLite，不调大模型）{retry_note}",
            "input": inp or str(params)[:200],
            "output": out,
        }

    if step == "skill":
        skills = p.get("skills") or []
        names = "、".join(
            str(s.get("name") or "")
            for s in skills
            if isinstance(s, dict) and s.get("name")
        )
        return {
            "summary": "编排：按问题与已检索条款启用技能（不把业务公式写进主链）。",
            "input": _clip(question, 240),
            "output": names or "（无）",
        }

    if step == "skill_revise":
        names = "、".join(str(s) for s in (p.get("skills") or []))
        changed = "已按技能说明改写结论" if p.get("changed") else "草稿与技能说明一致，未改"
        return {
            "summary": f"调用 {_llm_label(p)}：按技能说明核对结论是否能从条款原文推出。",
            "input": names or "—",
            "output": changed,
        }

    if step == "verify":
        ok = p.get("ok")
        return {
            "summary": "规则校验：Verifier 对照检索结果检查回答（确定性逻辑，不调大模型）。",
            "input": "回答草稿 + 检索到的实体/leaf",
            "output": "通过" if ok else f"建议人工核对（{p.get('message', '')}）",
        }

    if step == "answer":
        text = str(p.get("text") or "")
        return {
            "summary": f"调用 {_llm_label(p)}：根据检索到的条款生成最终回复（本步消耗大模型）。",
            "input": "条款摘要 + 原问题",
            "output": _clip(text, 2000),
        }

    return {
        "summary": step,
        "input": _clip(question, 200),
        "output": _clip(str(p), 500),
    }


def _clip(s: str, n: int) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"
