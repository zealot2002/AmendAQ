from mycs.planning.chapter_hints import (
    drill_matches_seeded_chapters,
    is_composite_handbook_query,
    merged_chapter_seeds,
    seed_chapter_refs_from_question,
    seed_leaf_sections_from_question,
)


def test_merged_chapter_seeds_ai_and_shopkeeper():
    chapters = [
        {"section_ref": "7.", "title": "店主申请"},
        {"section_ref": "9.", "title": "数据分析"},
        {"section_ref": "10.", "title": "支付与其他"},
    ]
    q = "AI推荐可靠吗？\n如何申请成为店主？"
    refs = merged_chapter_seeds(q, chapters)
    assert "7." in refs
    assert "9." in refs
    assert "10." not in refs


def test_composite_offboarding_question():
    q = (
        "一名员工准备离职，还有未使用的年假、尚未报销的业务费用，"
        "以及公司笔记本电脑。离职前需要重点处理哪些事项？请分别引用并区分必须和原则上。"
    )
    assert is_composite_handbook_query(q)
    chapters = [
        {"section_ref": "4.", "title": "薪酬与报销"},
        {"section_ref": "5.", "title": "假期"},
        {"section_ref": "11.", "title": "纪律与离职"},
    ]
    refs = seed_chapter_refs_from_question(q, chapters)
    assert "4." in refs
    assert "5." in refs
    assert "11." in refs


def test_composite_leaf_sections_offboarding():
    q = (
        "一名员工准备离职，还有未使用的年假、尚未报销的业务费用，"
        "以及公司笔记本电脑。离职前需要重点处理哪些事项？"
    )
    outline = [
        {"kind": "leaf", "section_ref": "4.3", "title": "费用报销", "summary": ""},
        {"kind": "leaf", "section_ref": "5.1", "title": "年假", "summary": ""},
        {"kind": "leaf", "section_ref": "11.2", "title": "辞职通知", "summary": ""},
        {"kind": "leaf", "section_ref": "11.3", "title": "公司财产", "summary": ""},
    ]
    refs = seed_leaf_sections_from_question(q, outline)
    assert "4.3" in refs
    assert "5.1" in refs
    assert "11.2" in refs
    assert "11.3" in refs


def test_drill_mismatch_learning_budget_vs_chapter4():
    assert not drill_matches_seeded_chapters("4.3", ["6."])
    assert drill_matches_seeded_chapters("6.4", ["6."])


def test_learning_budget_chapter_seed():
    chapters = [
        {"section_ref": "4.", "title": "薪酬与报销"},
        {"section_ref": "6.", "title": "绩效与发展"},
    ]
    q = "员工希望使用公司的年度学习预算报销一门专业课程"
    refs = seed_chapter_refs_from_question(q, chapters)
    assert "6." in refs
