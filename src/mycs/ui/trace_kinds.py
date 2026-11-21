from __future__ import annotations

from typing import Any

KIND_LABELS: dict[str, str] = {
    "llm": "大模型",
    "retrieval": "知识检索",
    "pipeline": "编排判断",
    "load": "读库加载",
    "rules": "规则校验",
}


def resolve_step_kind(step: str, payload: dict[str, Any] | None = None) -> tuple[str, str]:
    """Map trace step + payload to execution kind (aligned with AgentLoop behavior)."""
    p = payload or {}
    explicit = str(p.get("step_kind") or "").strip()
    if explicit:
        label = str(p.get("step_kind_label") or "").strip() or KIND_LABELS.get(explicit, explicit)
        return explicit, label

    if step == "understand":
        if p.get("llm_invoked") is False:
            return "pipeline", KIND_LABELS["pipeline"]
        return "llm", KIND_LABELS["llm"]
    if step == "toc_drill":
        mode = str(p.get("mode") or "")
        if mode == "llm_pick":
            return "llm", KIND_LABELS["llm"]
        return "pipeline", KIND_LABELS["pipeline"]
    if step in ("toc_catalog_batch", "toc_children_batch", "faq_title_batch"):
        return "llm", KIND_LABELS["llm"]
    if step == "plan":
        if p.get("llm_invoked") is False:
            return "pipeline", KIND_LABELS["pipeline"]
        if str(p.get("plan_source") or "") in ("comprehensive_toc", "flat_faq"):
            return "pipeline", KIND_LABELS["pipeline"]
        return "llm", KIND_LABELS["llm"]
    if step == "answer":
        return "llm", KIND_LABELS["llm"]
    if step == "skill":
        return "pipeline", KIND_LABELS["pipeline"]
    if step == "skill_revise":
        return "llm", KIND_LABELS["llm"]
    if step == "plan_guard":
        return "pipeline", KIND_LABELS["pipeline"]
    if step == "tool":
        return "retrieval", KIND_LABELS["retrieval"]
    if step in ("outline", "toc"):
        src = str(p.get("source") or "")
        if src in ("tool_outline", "tool_api"):
            return "retrieval", KIND_LABELS["retrieval"]
        return "load", KIND_LABELS["load"]
    if step == "verify":
        return "rules", KIND_LABELS["rules"]
    return "pipeline", KIND_LABELS["pipeline"]
