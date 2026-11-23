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

    def faq_list_published_leaves(self, *, document_id: str) -> dict[str, Any]:
        slim = [
            {
                "section_ref": x["section_ref"],
                "title": x["title"],
                "summary": "",
                "node_id": x["node_id"],
            }
            for x in self.leaves
        ]
        return {"leaves": slim}

    def wiki_list_leaves(self, *, document_id: str) -> dict[str, Any]:
        return self.faq_list_published_leaves(document_id=document_id)

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


class _CountingPickLLM:
    calls = 0

    def review_faq_title_batch(self, **kwargs: Any) -> dict[str, Any]:
        _CountingPickLLM.calls += 1
        assert kwargs["batch_total"] == 1
        batch = kwargs["entries_in_batch"]
        assert len(batch) == 12
        return {"action": "done", "section_refs": [str(batch[0]["section_ref"])], "reason": "one-shot"}


def test_flat_faq_skips_rerank_when_under_top_k(monkeypatch):
    monkeypatch.setenv("MYCS_FAQ_RECALL_MAX_PICKS", "5")

    class _OrderedLLM:
        def review_faq_title_batch(self, **kwargs: Any) -> dict[str, Any]:
            batch = kwargs["entries_in_batch"]
            order = [str(batch[1]["section_ref"]), str(batch[0]["section_ref"])]
            return {"action": "pick", "section_refs": order, "reason": "order"}

    flat = run_flat_faq_recall(
        llm=_OrderedLLM(),
        svc=_FakeLeavesSvc(),  # type: ignore[arg-type]
        document_id="faq",
        question="AI推荐",
    )
    assert flat.leaf_section_refs == ["§1.1", "§9.3"]


def test_flat_faq_trims_excessive_llm_picks(monkeypatch):
    monkeypatch.setenv("MYCS_FAQ_RECALL_MAX_PICKS", "2")

    class _GreedyLLM:
        def review_faq_title_batch(self, **kwargs: Any) -> dict[str, Any]:
            batch = kwargs["entries_in_batch"]
            refs = [str(c["section_ref"]) for c in batch]
            return {"action": "done", "section_refs": refs, "reason": "all"}

    svc = _FakeLeavesSvc()
    flat = run_flat_faq_recall(
        llm=_GreedyLLM(),
        svc=svc,  # type: ignore[arg-type]
        document_id="faq",
        question="AI推荐",
    )
    assert len(flat.leaf_section_refs) <= 2
    assert flat.leaf_section_refs


def test_flat_faq_single_pass_under_max(monkeypatch):
    monkeypatch.setenv("MYCS_FAQ_SINGLE_PASS_MAX", "120")

    class _ManyLeavesSvc(_FakeLeavesSvc):
        def faq_list_published_leaves(self, *, document_id: str) -> dict[str, Any]:
            base = super().faq_list_published_leaves(document_id=document_id)
            extra = [
                {
                    "section_ref": f"§{i}.{i}",
                    "title": f"条目{i}",
                    "summary": "",
                    "node_id": f"n{i}",
                }
                for i in range(3, 13)
            ]
            base["leaves"] = list(base["leaves"]) + extra
            return base

    _CountingPickLLM.calls = 0
    flat = run_flat_faq_recall(
        llm=_CountingPickLLM(),
        svc=_ManyLeavesSvc(),  # type: ignore[arg-type]
        document_id="faq",
        question="任意",
    )
    assert _CountingPickLLM.calls == 1
    assert len(flat.trace_events) == 1
    assert flat.reason == "flat_faq_done"


def test_faq_over_200_is_two_batches(monkeypatch):
    monkeypatch.delenv("MYCS_FAQ_BATCH_SIZE", raising=False)
    monkeypatch.delenv("MYCS_FAQ_SINGLE_PASS_MAX", raising=False)

    class _Svc(_FakeLeavesSvc):
        def faq_list_published_leaves(self, *, document_id: str) -> dict[str, Any]:
            return {
                "leaves": [
                    {
                        "section_ref": f"1.{i}",
                        "title": f"条目{i}",
                        "summary": "摘要",
                        "node_id": f"n{i}",
                    }
                    for i in range(1, 212)
                ]
            }

    sizes: list[int] = []

    class _Count:
        def review_faq_title_batch(self, **kwargs: Any) -> dict[str, Any]:
            sizes.append(len(kwargs["entries_in_batch"]))
            return {"section_refs": [], "reason": "none"}

    run_flat_faq_recall(
        llm=_Count(),
        svc=_Svc(),  # type: ignore[arg-type]
        document_id="faq",
        question="任意",
    )
    assert sizes == [200, 11]


def test_flat_faq_done_does_not_skip_later_slices(monkeypatch):
    monkeypatch.setenv("MYCS_FAQ_SINGLE_PASS_MAX", "8")
    monkeypatch.setenv("MYCS_FAQ_BATCH_SIZE", "4")
    monkeypatch.setenv("MYCS_FAQ_RECALL_MAX_PICKS", "5")

    class _Svc(_FakeLeavesSvc):
        def faq_list_published_leaves(self, *, document_id: str) -> dict[str, Any]:
            return {
                "leaves": [
                    {
                        "section_ref": f"1.{i}",
                        "title": f"条目{i}",
                        "summary": "",
                        "node_id": f"n{i}",
                    }
                    for i in range(1, 10)
                ]
            }

    class _DoneThenPick:
        calls = 0

        def review_faq_title_batch(self, **kwargs: Any) -> dict[str, Any]:
            _DoneThenPick.calls += 1
            batch = kwargs["entries_in_batch"]
            if _DoneThenPick.calls == 1:
                return {"action": "done", "section_refs": [str(batch[0]["section_ref"])], "reason": "stop"}
            return {"section_refs": [str(batch[0]["section_ref"])], "reason": "later"}

    flat = run_flat_faq_recall(
        llm=_DoneThenPick(),
        svc=_Svc(),  # type: ignore[arg-type]
        document_id="faq",
        question="任意",
    )
    assert _DoneThenPick.calls == 3
    assert flat.leaf_section_refs == ["1.1", "1.5", "1.9"]