from amendaq.graph.extract import OllamaGraphExtractor, _merge_graph_payload
from amendaq.graph.model import KnowledgeGraph


class _FakeLLM:
    def __init__(self) -> None:
        self.calls = 0

    def _json_chat(self, system: str, user: str, max_tokens=None):
        self.calls += 1
        return {
            "entities": [
                {
                    "entity_id": f"e{self.calls}",
                    "entity_type": "Policy",
                    "name": f"Policy chunk {self.calls}",
                    "summary": "s",
                    "tags": [],
                    "properties": {},
                }
            ],
            "relations": [],
            "evidence": [],
        }


def test_llm_graph_extract_merges_chunks():
    llm = _FakeLLM()
    ext = OllamaGraphExtractor(llm)
    text = "x" * 7000
    graph = ext.extract(
        text,
        document_id="doc_x",
        title="t",
        source_uri="file://t",
    )
    assert llm.calls == 2
    assert len(graph.entities) == 2


def test_merge_graph_payload_stats():
    g = KnowledgeGraph(document_id="d", title="t", source_uri="u")
    stats = _merge_graph_payload(
        g,
        {
            "entities": [{"entity_id": "a", "name": "A"}],
            "relations": [],
            "evidence": [],
        },
    )
    assert stats["entities_added"] == 1
    stats2 = _merge_graph_payload(
        g,
        {
            "entities": [{"entity_id": "a", "name": "A"}],
            "relations": [],
            "evidence": [],
        },
    )
    assert stats2["entities_skipped"] == 1
