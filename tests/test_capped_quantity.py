from amendaq.skills.capped_quantity import apply_capped_quantity, compute_capped_quantity

_LEAVE = (
    "每满一个完整工作年度，享有 15 天带薪年假；1–2 天年假至少提前 3 个工作日申请；"
    "连续 3 天及以上年假至少提前 10 个工作日申请。\n"
    "未休年假结转余额上限 30 天；当地法律有不同要求则按当地法律执行。"
)
_QUESTION = "之前已经结转了 8 天年假，那么他最多可以拥有多少天的年假余额？"


def test_existing_plus_grant_under_cap():
    got = compute_capped_quantity(_QUESTION, _LEAVE)
    assert got is not None
    assert got["result"] == 23
    assert got["grant"] == 15
    assert got["cap"] == 30


def test_sum_above_cap_uses_cap():
    clauses = "每满一年享有 15 天。结转余额上限 20 天。"
    got = compute_capped_quantity(_QUESTION, clauses)
    assert got is not None
    assert got["result"] == 20


def test_without_existing_amount_skips():
    assert compute_capped_quantity("最多可以有多少天？", _LEAVE) is None


def test_apply_replaces_conclusion_that_states_the_cap():
    computed = compute_capped_quantity(_QUESTION, _LEAVE)
    assert computed is not None
    draft = "结论：他最多可以拥有 30 天。\n\n依据：§1.13 §1.14"
    got = apply_capped_quantity(draft, computed)
    assert "23天" in got.replace(" ", "")
    assert "依据：§1.13 §1.14" in got


def test_apply_keeps_conclusion_that_already_states_result():
    computed = compute_capped_quantity(_QUESTION, _LEAVE)
    assert computed is not None
    draft = "结论：合计 23 天，没有超过上限 30 天。"
    assert apply_capped_quantity(draft, computed) == draft
