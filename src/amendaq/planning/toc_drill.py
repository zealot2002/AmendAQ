from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from amendaq.knowledge.service import KnowledgeService
from amendaq.log import get_logger
from amendaq.log_detail import log_step
from amendaq.planning.query_intent import is_whole_document_query
from amendaq.planning.sibling_expand import scope_section_refs, select_related_siblings
from amendaq.ui.trace_llm_capture import take_llm_captures

logger = get_logger(__name__)

MAX_DRILL_LEVELS = 5


class TocBranchSelector(Protocol):
    def select_toc_branch(
        self,
        *,
        question: str,
        level: int,
        path: list[dict[str, str]],
        choices: list[dict[str, Any]],
    ) -> dict[str, Any]: ...


@dataclass
class TocDrillResult:
    path: list[dict[str, Any]] = field(default_factory=list)
    scope_node_id: str | None = None
    scope_section_prefix: str | None = None
    scope_section_refs: list[str] = field(default_factory=list)
    sibling_nodes: list[dict[str, Any]] = field(default_factory=list)
    stopped_at_level: int = 0
    reason: str = ""
    trace_events: list[dict[str, Any]] = field(default_factory=list)


def _expand_related_siblings(
    result: TocDrillResult,
    *,
    svc: KnowledgeService,
    document_id: str,
    question: str,
    path: list[dict[str, Any]],
) -> None:
    """Pull same-chapter leaves that share the picked topic (e.g. 5.1 → 5.5)."""
    if len(path) < 2:
        return
    parent = path[-2]
    picked = path[-1]
    parent_id = str(parent.get("node_id") or "")
    if not parent_id or picked.get("kind") != "leaf":
        return
    bucket = svc.wiki_list_toc_children(
        parent_node_id=parent_id,
        document_id=document_id,
    )
    siblings = select_related_siblings(picked, list(bucket.get("nodes") or []), question)
    result.sibling_nodes = siblings
    result.scope_section_refs = scope_section_refs(picked, siblings)
    if not siblings:
        return
    slim = [
        {
            "node_id": n.get("node_id"),
            "section_ref": n.get("section_ref"),
            "title": n.get("title"),
        }
        for n in siblings
    ]
    result.trace_events.append(
        {
            "mode": "sibling_expand",
            "llm_invoked": False,
            "picked": {
                "section_ref": picked.get("section_ref"),
                "title": picked.get("title"),
                "node_id": picked.get("node_id"),
            },
            "siblings": slim,
            "scope_section_refs": result.scope_section_refs,
            "reason": "同章标题相邻条款一并纳入，避免单叶漏掉结转/上限等规则",
        }
    )
    logger.info(
        "joyjoy: toc sibling expand picked=%s siblings=%s",
        picked.get("section_ref"),
        [n.get("section_ref") for n in siblings],
    )


def _auto_pick_single(choices: list[dict[str, Any]]) -> dict[str, Any] | None:
    if len(choices) == 1:
        return choices[0]
    return None


def run_toc_drill(
    *,
    llm: TocBranchSelector,
    svc: KnowledgeService,
    document_id: str,
    question: str,
) -> TocDrillResult:
    """Layer-by-layer TOC navigation: L1 chapters → L2 sections (leaves) → …"""
    result = TocDrillResult()
    if is_whole_document_query(question):
        result.reason = "whole_document_query_skip_drill"
        result.trace_events.append(
            {
                "mode": "pipeline_skip",
                "reason": result.reason,
                "llm_invoked": False,
                "detail": "规则识别为整本手册类问题，不逐层点选目录",
            }
        )
        log_step(
            logger,
            "toc_drill_skip",
            document_id=document_id,
            reason=result.reason,
            question=question[:200],
        )
        return result
    volume_id = svc.wiki_mount_volume_node_id(document_id)
    if not volume_id:
        result.reason = "no_mount"
        result.trace_events.append(
            {
                "mode": "pipeline_skip",
                "reason": result.reason,
                "llm_invoked": False,
                "detail": "手册尚未挂载目录",
            }
        )
        log_step(logger, "toc_drill_skip", document_id=document_id, reason=result.reason)
        return result

    parent_id = volume_id
    path: list[dict[str, Any]] = []

    for level in range(1, MAX_DRILL_LEVELS + 1):
        bucket = svc.wiki_list_toc_children(
            parent_node_id=parent_id,
            document_id=document_id,
        )
        choices = list(bucket.get("nodes") or [])
        if not choices:
            result.reason = "no_children"
            result.stopped_at_level = level - 1
            result.trace_events.append(
                {
                    "mode": "pipeline_stop",
                    "level": level,
                    "reason": result.reason,
                    "llm_invoked": False,
                }
            )
            break

        auto = _auto_pick_single(choices)
        if auto:
            decision = {
                "action": "select",
                "node_id": auto["node_id"],
                "reason": "only_one_child",
            }
            result.trace_events.append(
                {
                    "mode": "auto_pick",
                    "level": level,
                    "llm_invoked": False,
                    "picked": {
                        "section_ref": auto.get("section_ref"),
                        "title": auto.get("title"),
                        "node_id": auto.get("node_id"),
                    },
                    "reason": "该层只有一个子节点，自动进入",
                }
            )
            log_step(
                logger,
                "toc_drill_auto",
                level=level,
                node_id=auto["node_id"],
                title=auto.get("title"),
            )
        else:
            path_labels = [{"section_ref": p.get("section_ref"), "title": p.get("title")} for p in path]
            log_step(
                logger,
                "toc_drill_ask_llm",
                level=level,
                question=question[:200],
                path=path_labels,
                choices=choices,
            )
            decision = llm.select_toc_branch(
                question=question,
                level=level,
                path=path_labels,
                choices=choices,
            )
            log_step(logger, "toc_drill_llm_reply", level=level, decision=decision)
            slim_choices = [
                {
                    "section_ref": c.get("section_ref"),
                    "title": c.get("title"),
                    "kind": c.get("kind"),
                }
                for c in choices[:12]
            ]
            result.trace_events.append(
                {
                    "mode": "llm_pick",
                    "level": level,
                    "llm_invoked": True,
                    "choices": choices,
                    "choices_preview": slim_choices,
                    "decision": decision,
                    "llm_calls": take_llm_captures(),
                }
            )

        action = str(decision.get("action") or "select").lower()
        if action in ("stop", "done", "halt"):
            result.scope_node_id = path[-1]["node_id"] if path else None
            result.scope_section_prefix = path[-1].get("section_ref") if path else None
            result.path = list(path)
            result.stopped_at_level = level
            result.reason = str(decision.get("reason") or "llm_stop")
            result.trace_events.append(
                {
                    "mode": "outcome",
                    "level": level,
                    "llm_invoked": action != "select",
                    "reason": result.reason,
                    "path": [
                        {"section_ref": p.get("section_ref"), "title": p.get("title")}
                        for p in path
                    ],
                    "scope_section_prefix": result.scope_section_prefix,
                }
            )
            break

        node_id = decision.get("node_id")
        picked = next((c for c in choices if c.get("node_id") == node_id), None)
        if not picked:
            result.scope_node_id = path[-1]["node_id"] if path else None
            result.scope_section_prefix = path[-1].get("section_ref") if path else None
            result.path = list(path)
            result.stopped_at_level = level
            result.reason = "invalid_node_id"
            result.trace_events.append(
                {
                    "mode": "outcome",
                    "level": level,
                    "llm_invoked": True,
                    "reason": result.reason,
                    "path": [
                        {"section_ref": p.get("section_ref"), "title": p.get("title")}
                        for p in path
                    ],
                }
            )
            log_step(logger, "toc_drill_invalid_pick", level=level, node_id=node_id)
            break

        path.append(picked)
        parent_id = str(picked["node_id"])
        result.scope_node_id = parent_id
        result.scope_section_prefix = picked.get("section_ref") or None
        result.path = list(path)

        if picked.get("kind") == "leaf":
            result.stopped_at_level = level
            result.reason = "reached_leaf"
            result.trace_events.append(
                {
                    "mode": "outcome",
                    "level": level,
                    "llm_invoked": any(e.get("mode") == "llm_pick" for e in result.trace_events),
                    "reason": result.reason,
                    "path": [
                        {"section_ref": p.get("section_ref"), "title": p.get("title")}
                        for p in path
                    ],
                    "scope_section_prefix": result.scope_section_prefix,
                }
            )
            log_step(
                logger,
                "toc_drill_leaf",
                level=level,
                section_ref=picked.get("section_ref"),
                title=picked.get("title"),
            )
            _expand_related_siblings(
                result,
                svc=svc,
                document_id=document_id,
                question=question,
                path=path,
            )
            break
    else:
        result.reason = result.reason or "max_levels"

    if not any(e.get("mode") == "outcome" for e in result.trace_events):
        result.trace_events.append(
            {
                "mode": "outcome",
                "llm_invoked": any(e.get("mode") == "llm_pick" for e in result.trace_events),
                "reason": result.reason,
                "path": [
                    {"section_ref": p.get("section_ref"), "title": p.get("title")}
                    for p in result.path
                ],
                "scope_section_prefix": result.scope_section_prefix,
            }
        )

    if not result.scope_section_refs and result.scope_section_prefix:
        result.scope_section_refs = [result.scope_section_prefix]

    log_step(
        logger,
        "toc_drill_done",
        document_id=document_id,
        scope_node_id=result.scope_node_id,
        section_prefix=result.scope_section_prefix,
        path=[{"section_ref": p.get("section_ref"), "title": p.get("title")} for p in result.path],
        reason=result.reason,
    )
    return result
