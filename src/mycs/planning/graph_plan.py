from __future__ import annotations

from mycs.models import KnowledgeRequirement, KnowledgeSource, UnderstandResult


def minimal_graph_fallback(understood: UnderstandResult) -> list[KnowledgeRequirement]:
    """Last resort when LLM plan JSON fails (still not question-specific)."""
    return [
        KnowledgeRequirement(
            field="graph.entity.search",
            source=KnowledgeSource.GRAPH,
            params={
                "query": understood.raw_question,
                "document_id": understood.graph_document_id,
                "limit": 8,
            },
        ),
    ]
