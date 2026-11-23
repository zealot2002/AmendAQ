from __future__ import annotations

from amendaq.compare.chunking import chunk_chars
from amendaq.compare.corpus import faq_only_answers, iter_faqs, render_faq, render_source
from amendaq.compare.questions import QUESTIONS
from amendaq.compare.score import score_answer
from amendaq.kb.import_parse import parse_faq_import_text


def test_corpus_scale_and_two_views() -> None:
    faqs = iter_faqs()
    assert len(faqs) >= 200
    source = render_source()
    faq = render_faq()
    assert source != faq
    assert "Q1：" not in source
    for answer in faq_only_answers():
        assert answer not in source
        assert answer in faq
    parsed = parse_faq_import_text(faq)
    assert len(parsed) == len(faqs)


def test_question_set_and_gold() -> None:
    assert len(QUESTIONS) >= 140
    ids = [item["id"] for item in QUESTIONS]
    assert len(ids) == len(set(ids))
    kinds = {item["kind"] for item in QUESTIONS}
    assert kinds == {"lookup", "obligation", "number", "refusal", "fabrication"}
    for spec in QUESTIONS:
        scored = score_answer(spec["gold"], spec)
        assert scored["ok"], (spec["id"], scored)


def test_score_rejects_flipped_obligation_and_empty() -> None:
    gift = next(item for item in QUESTIONS if item["id"] == "gift_conflict")
    flipped = score_answer("可以接受这份礼品，因为没有超过 2000 元。", gift)
    assert not flipped["ok"]
    assert score_answer("", gift)["ok"] is False
    leave = next(item for item in QUESTIONS if item["id"] == "leave_balance")
    assert not score_answer("结转上限是 30 天，所以余额为 30 天。", leave)["ok"]


def test_chunks_are_fixed_width_and_ignore_line_breaks() -> None:
    text = ("甲" * 10) + "\n" + ("乙" * 1190)
    pieces = chunk_chars(text, size=500, overlap=80)
    assert len(pieces) == 3
    assert len(pieces[0]) == 500
    assert len(pieces[1]) == 500
    assert pieces[0].endswith("乙")
    assert "\n" in pieces[0]


def test_score_accepts_same_fact_in_another_wording() -> None:
    course = next(item for item in QUESTIONS if item["id"] == "course_budget")
    assert score_answer(
        "不可以直接报销。年度上限 18,000 元，超出须部门负责人书面批准。",
        course,
    )["ok"]
    assert not score_answer("可以直接报销，找总经理批准，上限 18000 元。", course)["ok"]
    meal = next(item for item in QUESTIONS if item["id"] == "meal")
    assert score_answer("出勤当天 30 元，不可以累计到下一天。", meal)["ok"]
    bonus = next(item for item in QUESTIONS if item["id"] == "bonus_absent")
    assert score_answer("无法回答。文档未提及年终奖，也未包含第13薪的规定。", bonus)["ok"]
    assert not score_answer("年终奖是13薪。", bonus)["ok"]
    holiday = next(item for item in QUESTIONS if item["id"] == "holiday_duty")
    assert score_answer("值班 8 小时换成 16 小时调休，不能兑换现金。", holiday)["ok"]
    commute = next(item for item in QUESTIONS if item["id"] == "commute_absent")
    assert score_answer(
        "没有信息表明有每月交通补贴。私车公用是每公里 2 元，那不是通勤补贴。无法确定每月金额。",
        commute,
    )["ok"]
    assert not score_answer("每月交通补贴按每公里 2 元。", commute)["ok"]


def test_score_ignores_spaces_and_digit_edges() -> None:
    pay = next(item for item in QUESTIONS if item["id"] == "pay_day")
    assert score_answer("工资一般在次月5个自然日内到账，银行假日提前到前一个工作日。", pay)["ok"]
    marriage = next(item for item in QUESTIONS if item["id"] == "marriage")
    assert not score_answer("可以请 13 天。", marriage)["ok"]
    assert score_answer(marriage["gold"], marriage)["ok"]


def test_import_publishes_every_faq(tmp_path) -> None:
    from amendaq.compare.prepare import build_faq_db
    from amendaq.db.connection import connect

    db = tmp_path / "compare.db"
    document_id = build_faq_db(db)
    conn = connect(db)
    try:
        published = conn.execute(
            "SELECT COUNT(*) AS n FROM kb_faq_item WHERE document_id = ? AND status = 'published'",
            (document_id,),
        ).fetchone()["n"]
    finally:
        conn.close()
    assert published == len(iter_faqs())
