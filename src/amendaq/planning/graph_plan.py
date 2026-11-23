from __future__ import annotations

from amendaq.models import KnowledgeRequirement, KnowledgeSource, UnderstandResult


def minimal_graph_fallback(understood: UnderstandResult) -> list[KnowledgeRequirement]:
    """Last resort when LLM plan JSON fails; TOC recall must have populated sections."""
    return []
