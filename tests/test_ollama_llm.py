import json

import pytest

from mycs.llm.errors import OllamaLLMError
from mycs.llm.ollama import OllamaLLM
from mycs.models import UnderstandResult


def test_ollama_understand_parses_json():
    llm = OllamaLLM(base_url="http://test/v1", model="test")

    def fake_raw(system, user, json_mode=False, max_tokens=None):
        assert json_mode
        return json.dumps(
            {"case_id": "CASE-2026-001", "intent": "case_status_and_policy_limit"}
        )

    llm._raw_chat = fake_raw  # type: ignore[method-assign]
    u = llm.understand("办件 CASE-2026-001 预审", None)
    assert u.case_id == "CASE-2026-001"


def test_ollama_plan_raises_on_bad_json():
    llm = OllamaLLM(base_url="http://test/v1", model="test")
    llm._json_chat = lambda s, u: (_ for _ in ()).throw(ValueError("bad"))  # type: ignore[method-assign, assignment]
    understood = UnderstandResult(
        case_id="CASE-2026-001",
        intent="case_status_and_policy_limit",
        raw_question="预审",
    )
    with pytest.raises(OllamaLLMError, match="plan failed"):
        llm.plan(understood)
