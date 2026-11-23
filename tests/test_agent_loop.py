import os

import pytest

from amendaq.agent.loop import AgentLoop
from amendaq.cli import POLICY_ONLY_QUESTION, REFERENCE_CASE_ID, REFERENCE_QUESTION

pytestmark = pytest.mark.skipif(
    os.environ.get("AMENDAQ_INTEGRATION") != "1",
    reason="requires Ollama; set AMENDAQ_INTEGRATION=1",
)


def test_reference_case_scenario():
    loop = AgentLoop()
    result = loop.run(REFERENCE_QUESTION, case_id=REFERENCE_CASE_ID)
    assert result.verify.ok
    assert "预审" in result.answer or "pre" in result.answer.lower()
    steps = [e.step for e in result.trace]
    assert steps.index("plan") < steps.index("tool")


def test_policy_only_no_case():
    loop = AgentLoop()
    result = loop.run(POLICY_ONLY_QUESTION)
    assert result.verify.ok
