from mycs.planning.question_split import (
    normalize_sub_questions,
    resolve_sub_questions,
    should_attempt_question_split,
)


class _FakeSplitLLM:
    def split_questions(self, question: str) -> dict:
        if "\n" in question:
            parts = [ln.strip() for ln in question.splitlines() if ln.strip()]
            return {"questions": parts, "reason": "test"}
        return {"questions": [question.strip()], "reason": "single"}


def test_should_split_multiline():
    assert should_attempt_question_split("A?\nB?")


def test_resolve_sub_questions_multiline():
    q = "AI推荐可靠吗？\n如何申请成为店主？"
    subs, meta = resolve_sub_questions(_FakeSplitLLM(), q)
    assert len(subs) == 2
    assert meta["llm_invoked"] is True


def test_normalize_fallback_single():
    out = normalize_sub_questions("only one", {"questions": ["only one"]})
    assert out == ["only one"]