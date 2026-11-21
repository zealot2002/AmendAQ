from mycs.agent.loop import understand_for_question


class _Boom:
    def understand(self, question: str, case_id: str | None):
        raise AssertionError("understand should not be called")


def test_selected_document_skips_understand(monkeypatch):
    monkeypatch.setenv("MYCS_GRAPH_DOCUMENT", "kb_demo")
    understood, invoked = understand_for_question(_Boom(), "铁王座怎么来的 CASE-2026-001", None)
    assert invoked is False
    assert understood.intent == "graph_qa"
    assert understood.graph_document_id == "kb_demo"
    assert understood.case_id == "CASE-2026-001"


def test_missing_document_still_calls_understand(monkeypatch):
    monkeypatch.delenv("MYCS_GRAPH_DOCUMENT", raising=False)

    class _LLM:
        def understand(self, question: str, case_id: str | None):
            from mycs.models import UnderstandResult

            return UnderstandResult(
                case_id=case_id,
                intent="procedure_online_only",
                raw_question=question,
            )

    understood, invoked = understand_for_question(_LLM(), "能否线上办理", None)
    assert invoked is True
    assert understood.intent == "procedure_online_only"
