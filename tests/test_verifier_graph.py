from mycs.verifier import Verifier

_PAY = "工资按月发放，一般次月 5 个自然日内发放；遇银行假日，提前至前一个工作日发放。"
_GIFT = "单次每人礼品价值不超过 2000 新台币，不能造成义务或利益冲突；禁止收现金、现金等价物。"
_OFFBOARD = "归还电脑、门禁、文件等公司资产，不得留存公司机密副本；最终薪资按当地法规、流程结算。"


def _graph(answer: str, body: str):
    return Verifier().verify_graph_answer(
        question="q",
        answer=answer,
        entities=[],
        wiki_leaves=[{"section_ref": "1.1", "title": "t", "summary": body, "body": body}],
        search_top_score=1,
    )


def test_retracted_fact_fails():
    answer = f"结论：{_PAY}未检索到碰到银行放假的具体处理方式。"
    result = _graph(answer, _PAY)
    assert result.ok is False
    assert any(c["name"] == "conclusion_not_retracted" and not c["ok"] for c in result.checks)


def test_grounded_fact_without_retraction_passes():
    result = _graph(f"结论：{_PAY}", _PAY)
    assert result.ok is True


def test_hypothetical_permission_fails():
    answer = "结论：金额未超过 2000 新台币，且未造成义务或利益冲突的情况下，可以接受。"
    result = _graph(answer, _GIFT)
    assert result.ok is False
    assert any(
        c["name"] == "prohibition_not_restated_as_permission" and not c["ok"] for c in result.checks
    )


def test_direct_refusal_passes_permission_check():
    answer = "结论：不能接受。原文规定不能造成义务或利益冲突。"
    result = _graph(answer, _GIFT)
    assert result.ok is True


def test_invented_obligation_in_one_sentence_fails():
    answer = (
        "结论：离职前，员工必须归还电脑、门禁、文件等公司资产，不得留存公司机密副本；"
        "原则上应结清未使用的年假和尚未报销的业务费用；"
        "未检索到关于离职时如何处理未使用的年假和尚未报销的业务费用的具体规定。"
    )
    result = _graph(answer, _OFFBOARD)
    assert result.ok is False
    assert any(c["name"] == "obligation_grounded" and not c["ok"] for c in result.checks)


def test_invented_obligation_then_retracted_fails():
    answer = (
        "结论：必须归还电脑。原则上，员工应结清未使用的年假和尚未报销的业务费用。"
        "未检索到关于离职时如何处理未使用的年假和尚未报销的业务费用的具体规定。"
    )
    result = _graph(answer, _OFFBOARD)
    assert result.ok is False
    assert any(c["name"] == "obligation_grounded" and not c["ok"] for c in result.checks)


def test_amount_disclaimer_for_a_different_matter_passes():
    body = "每个自然年度学习预算上限 18000 新台币。单次礼品不超过 2000 新台币，不能造成义务或利益冲突。"
    answer = (
        "结论：明确出现的金额限制如下。学习预算上限 18000 新台币。"
        "礼品不超过 2000 新台币。未检索到关于费用报销的具体金额限制。"
    )
    result = _graph(answer, body)
    assert result.ok is True
