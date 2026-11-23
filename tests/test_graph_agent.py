from amendaq.models import UnderstandResult
from amendaq.planning.plan_schema import normalize_requirements


def test_llm_plan_normalizes_multi_gap():
    u = UnderstandResult(
        case_id=None,
        intent="graph_qa",
        raw_question="远程办公和协作日冲突吗？",
        graph_document_id="acme_handbook",
    )
    items = [
        {
            "field": "graph.entity.search",
            "source": "graph",
            "params": {"query": "远程办公 协作日", "limit": 5},
        },
        {
            "field": "graph.entity.by_section",
            "source": "graph",
            "params": {"section": "3.2"},
        },
        {
            "field": "graph.entity.by_section",
            "source": "graph",
            "params": {"section": "3.3"},
        },
    ]
    reqs = normalize_requirements(u, items)
    fields = [r.field for r in reqs]
    assert fields.count("graph.entity.by_section") == 2
    assert all(r.params.get("document_id") == "acme_handbook" for r in reqs)
    assert reqs[0].params["query"]


def test_llm_plan_injects_search_if_no_retrieval_gap():
    u = UnderstandResult(
        case_id=None,
        intent="graph_qa",
        raw_question="年假有多少天？",
        graph_document_id="x",
    )
    reqs = normalize_requirements(
        u,
        [{"field": "graph.read.query", "source": "graph", "params": {}}],
    )
    assert reqs[0].field == "graph.entity.search"
    assert any(r.field == "graph.read.query" for r in reqs)


def test_by_section_alone_skips_extra_search():
    u = UnderstandResult(
        case_id=None,
        intent="graph_qa",
        raw_question="年假有多少天？",
        graph_document_id="x",
    )
    reqs = normalize_requirements(
        u,
        [{"field": "graph.entity.by_section", "source": "graph", "params": {"section": "5.1"}}],
    )
    assert len(reqs) == 1
    assert reqs[0].field == "graph.entity.by_section"


def test_ollama_plan_parses_multi_gap_json():
    from amendaq.llm.ollama import OllamaLLM

    llm = OllamaLLM(base_url="http://test/v1", model="test")
    llm._json_chat = lambda s, u, max_tokens=None: {  # type: ignore[method-assign]
        "requirements": [
            {
                "field": "graph.entity.search",
                "source": "graph",
                "params": {},
            },
            {
                "field": "graph.read.query",
                "source": "graph",
                "params": {},
            },
        ]
    }
    u = UnderstandResult(
        case_id=None,
        intent="graph_qa",
        raw_question="列出所有金额限制",
        graph_document_id="corp",
    )
    reqs = llm.plan(u, {})
    assert len(reqs) >= 2
    assert {r.field for r in reqs} >= {"graph.entity.search", "graph.read.query"}
