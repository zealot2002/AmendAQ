from __future__ import annotations

import json
import logging
from typing import Any


def _truncate_json(obj: Any, max_chars: int) -> str:
    text = json.dumps(obj, ensure_ascii=False, default=str)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


def log_step(
    logger: logging.Logger,
    step: str,
    *,
    level: int = logging.INFO,
    max_json_chars: int = 6000,
    **fields: Any,
) -> None:
    """Structured workflow log (tag joyjoy is on the AmendAQ logger formatter)."""
    parts: list[str] = []
    for key, val in fields.items():
        if isinstance(val, (dict, list, tuple)):
            parts.append(f"{key}={_truncate_json(val, max_json_chars)}")
        else:
            parts.append(f"{key}={val!r}")
    logger.log(level, "step=%s %s", step, " ".join(parts))


def summarize_tool_result(tool: str, result: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {"raw": str(result)[:500]}
    if result.get("ok") is False:
        return {"ok": False, "error": result.get("error"), "tool": tool}
    out: dict[str, Any] = {"ok": True, "tool": tool}
    if "count" in result:
        out["count"] = result["count"]
    if tool in ("kg_search_entities", "kg_find_entities"):
        hits = result.get("hits") or []
        out["hits"] = [
            {
                "entity_id": h.get("entity_id"),
                "section": h.get("section"),
                "name": (h.get("name") or "")[:80],
                "search_score": h.get("search_score"),
            }
            for h in hits[:8]
        ]
    elif tool in ("wiki_resolve_branch", "wiki_get_subtree"):
        root = result.get("root") or {}
        leaves = result.get("leaves") or []
        out["root"] = {
            "node_id": root.get("node_id"),
            "section_ref": root.get("section_ref"),
            "title": root.get("title"),
        }
        out["leaf_count"] = len(leaves)
        out["leaf_sections"] = [lf.get("section_ref") for lf in leaves[:12]]
    elif tool == "wiki_get_toc_outline":
        nodes = result.get("nodes") or []
        out["outline_count"] = len(nodes)
        out["sample"] = [
            {"section_ref": n.get("section_ref"), "title": (n.get("title") or "")[:60]}
            for n in nodes[:10]
        ]
    elif tool == "wiki_get_leaves":
        leaves = result.get("leaves") or []
        out["sections"] = [lf.get("section_ref") for lf in leaves[:15]]
    elif tool == "kg_nl_query":
        out["sql"] = (result.get("sql") or "")[:300]
        rows = result.get("rows") or []
        out["row_count"] = len(rows)
    else:
        keys = list(result.keys())[:12]
        out["keys"] = keys
    return out
