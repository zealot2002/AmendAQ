from __future__ import annotations

from typing import Any

from amendaq.planning.comprehensive_toc import run_comprehensive_toc_recall


class _FakeKnowledge:
    def __init__(self) -> None:
        self.chapters = [
            {"node_id": "c1", "section_ref": "1.", "title": "订单", "kind": "chapter"},
            {"node_id": "c2", "section_ref": "2.", "title": "其他", "kind": "chapter"},
        ]
        self.children: dict[str, list[dict[str, Any]]] = {
            "c1": [
                {"node_id": "l1", "section_ref": "1.1", "title": "状态A", "kind": "leaf"},
                {"node_id": "l2", "section_ref": "1.2", "title": "无关FAQ", "kind": "leaf"},
            ],
        }

    def wiki_list_chapters(self, *, document_id: str) -> dict[str, Any]:
        return {"chapters": self.chapters}

    def wiki_list_toc_children(
        self, *, parent_node_id: str, document_id: str
    ) -> dict[str, Any]:
        return {"nodes": self.children.get(parent_node_id, [])}


class _PickOrderChapterLLM:
    def review_toc_catalog_batch(self, **kwargs: Any) -> dict[str, Any]:
        batch = kwargs["chapters_in_batch"]
        refs = [str(c["section_ref"]) for c in batch if c.get("section_ref") == "1."]
        return {"action": "pick", "section_refs": refs, "reason": "test"}

    def review_toc_children_batch(self, **kwargs: Any) -> dict[str, Any]:
        # Simulate LLM choosing nothing — must not inject all leaves.
        return {"action": "continue", "section_refs": [], "reason": "none_in_batch"}


def test_no_whole_doc_skip_and_no_empty_child_leaf_fallback():
    svc = _FakeKnowledge()
    comp = run_comprehensive_toc_recall(
        llm=_PickOrderChapterLLM(),
        svc=svc,  # type: ignore[arg-type]
        document_id="doc",
        question="代购订单有哪些状态？",
        enumerative_query=True,
    )
    assert comp.selected_chapter_refs == ["1."]
    assert comp.leaf_section_refs == []
    assert "whole_document" not in (comp.reason or "")
    assert all(
        e.get("reason") != "whole_document_all_chapters"
        for e in comp.trace_events
        if isinstance(e, dict)
    )


class _PickOneLeafLLM(_PickOrderChapterLLM):
    def review_toc_children_batch(self, **kwargs: Any) -> dict[str, Any]:
        return {"action": "pick", "section_refs": ["1.1"], "reason": "status"}


def test_sparse_leaf_selection_only():
    comp = run_comprehensive_toc_recall(
        llm=_PickOneLeafLLM(),
        svc=_FakeKnowledge(),  # type: ignore[arg-type]
        document_id="doc",
        question="状态A是什么",
    )
    assert comp.leaf_section_refs == ["1.1"]


class _RejectForeignChapterRef(_PickOrderChapterLLM):
    def review_toc_catalog_batch(self, **kwargs: Any) -> dict[str, Any]:
        # Simulate model returning a chapter not in this batch (common failure mode).
        return {"action": "pick", "section_refs": ["7."], "reason": "hallucinated"}


def test_l1_ignores_section_refs_not_in_batch():
    comp = run_comprehensive_toc_recall(
        llm=_RejectForeignChapterRef(),
        svc=_FakeKnowledge(),  # type: ignore[arg-type]
        document_id="doc",
        question="无关",
    )
    assert comp.selected_chapter_refs == []


def test_l1_empty_no_fallback_all_chapters():
    class _NeverPickChapter(_PickOrderChapterLLM):
        def review_toc_catalog_batch(self, **kwargs: Any) -> dict[str, Any]:
            return {"action": "continue", "section_refs": [], "reason": "irrelevant"}

    comp = run_comprehensive_toc_recall(
        llm=_NeverPickChapter(),
        svc=_FakeKnowledge(),  # type: ignore[arg-type]
        document_id="doc",
        question="无关问题",
    )
    assert comp.selected_chapter_refs == []
    assert comp.reason == "L1_empty_no_chapters"