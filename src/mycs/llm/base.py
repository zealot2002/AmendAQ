from __future__ import annotations

from typing import Protocol

from mycs.models import KnowledgeRequirement, UnderstandResult


class AgentLLM(Protocol):
    def understand(self, question: str, case_id: str | None) -> UnderstandResult: ...

    def plan(
        self,
        understood: UnderstandResult,
        plan_context: dict[str, object] | None = None,
    ) -> list[KnowledgeRequirement]: ...

    def select_toc_branch(
        self,
        *,
        question: str,
        level: int,
        path: list[dict[str, str]],
        choices: list[dict[str, object]],
    ) -> dict[str, object]: ...

    def review_toc_catalog_batch(
        self,
        *,
        question: str,
        batch_index: int,
        batch_total: int,
        chapter_total: int,
        chapters_in_batch: list[dict[str, object]],
        already_selected: list[dict[str, str]],
        batches_remaining: int,
        composite_query: bool = False,
        enumerative_query: bool = False,
    ) -> dict[str, object]: ...

    def compose_answer(
        self,
        understood: UnderstandResult,
        context: dict[str, object],
    ) -> tuple[str, dict[str, object]]: ...

    def revise_answer(
        self,
        *,
        question: str,
        draft: str,
        evidence_text: str,
        skill_instructions: str,
    ) -> str: ...
