"""Release TOC drill scope when the model says the current chapter is the wrong place."""

from __future__ import annotations

import re

from mycs.planning.toc_drill import TocDrillResult

_RELEASE_REASON = re.compile(
    r"不包含|未涵盖|未涉及|不涉及|不在本章|不在.*章|另找|其他章|需寻找|需找|进一步查找|"
    r"无.*规定|没有.*相关|未提及|未说明|无直接|并不包含",
    re.I,
)


def should_release_drill_scope(drill: TocDrillResult) -> bool:
    """True when drill reason indicates the scoped chapter cannot answer the question."""
    reason = (drill.reason or "").strip()
    if reason in (
        "reached_leaf",
        "only_one_child",
        "whole_document_query_skip_drill",
        "composite_query_skip_drill",
        "no_mount",
        "no_children",
    ):
        return False
    if _RELEASE_REASON.search(reason):
        return True
    if not drill.path:
        return False
    last = drill.path[-1]
    if last.get("kind") != "leaf" and len(reason) >= 36:
        if _RELEASE_REASON.search(reason) or any(
            w in reason for w in ("寻找", "其他", "另一", "别的章")
        ):
            return True
    return False


def clear_drill_scope(drill: TocDrillResult) -> None:
    drill.scope_node_id = None
    drill.scope_section_prefix = None
    drill.scope_section_refs = []