from __future__ import annotations

from typing import Any

from mycs.db.catalog_mode import CATALOG_FLAT_FAQ, infer_catalog_mode
from mycs.planning.flat_faq import run_flat_faq_recall


class _FakeLeavesSvc:
    def __init__(self) -> None:
        self.leaves = [
            {
                "node_id": "a",
                "section_ref": "§9.3",
                "title": "Q37 AI推荐可靠吗",
                "kind": "leaf",
            },
            {
                "node_id": "b",
                "section_ref": "§1.1",
                "title": "下载方式",
                "kind": "leaf",
            },
        ]

    def wiki_list_leaves(self, *, document_id: str) -> dict[str, Any]:
        return {"leaves": self.leaves}

    def document_display_title(self, *, document_id: str) -> str:
        return "好势 FAQ"


class _PickAiFaqLLM:
    def review_faq_title_batch(self, **kwargs: Any) -> dict[str, Any]:
        batch = kwargs["entries_in_batch"]
        refs = [str(c["section_ref"]) for c in batch if "AI" in str(c.get("title") or "")]
        return {"action": "pick", "section_refs": refs, "reason": "test"}


def test_flat_faq_picks_matching_title_only():
    flat = run_flat_faq_recall(
        llm=_PickAiFaqLLM(),
        svc=_FakeLeavesSvc(),  # type: ignore[arg-type]
        document_id="faq",
        question="AI推荐可靠吗",
    )
    assert flat.leaf_section_refs == ["§9.3"]
    assert len(flat.trace_events) >= 1
    assert flat.reason == "flat_faq_done"


def test_infer_catalog_mode_for_faq_id():
    assert infer_catalog_mode("faq") == CATALOG_FLAT_FAQ
    assert infer_catalog_mode("employee_handbook") != CATALOG_FLAT_FAQ