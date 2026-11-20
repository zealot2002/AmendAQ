from mycs.ui.trace_kinds import resolve_step_kind


def test_plan_comprehensive_is_pipeline_not_llm():
    kind, label = resolve_step_kind(
        "plan",
        {
            "plan_source": "comprehensive_toc",
            "llm_invoked": False,
            "knowledge_requirements": [{"field": "graph.entity.by_section"}],
        },
    )
    assert kind == "pipeline"
    assert label == "编排判断"


def test_plan_llm_path_stays_llm():
    kind, _ = resolve_step_kind(
        "plan",
        {"plan_source": "llm_plan", "llm_invoked": True, "llm_calls": [{}]},
    )
    assert kind == "llm"


def test_toc_children_batch_is_llm():
    kind, _ = resolve_step_kind("toc_children_batch", {"phase": "L2_children"})
    assert kind == "llm"


def test_plan_flat_faq_is_pipeline_not_llm():
    kind, label = resolve_step_kind(
        "plan",
        {
            "plan_source": "flat_faq",
            "llm_invoked": False,
            "knowledge_requirements": [{"field": "graph.entity.by_section"}],
        },
    )
    assert kind == "pipeline"
    assert label == "编排判断"


def test_faq_title_batch_is_llm():
    kind, _ = resolve_step_kind("faq_title_batch", {})
    assert kind == "llm"