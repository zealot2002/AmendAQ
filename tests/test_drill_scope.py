from amendaq.planning.drill_scope import should_release_drill_scope
from amendaq.planning.toc_drill import TocDrillResult


def test_release_when_reason_says_chapter_lacks_topic():
    drill = TocDrillResult(
        path=[{"kind": "chapter", "section_ref": "4.", "title": "薪酬与报销"}],
        scope_section_prefix="4.",
        reason="当前层级均不涉及年度学习预算的规定，需寻找绩效章",
    )
    assert should_release_drill_scope(drill)


def test_no_release_on_reached_leaf():
    drill = TocDrillResult(
        path=[
            {"kind": "chapter", "section_ref": "8.", "title": "信息安全"},
            {"kind": "leaf", "section_ref": "8.5", "title": "安全事件"},
        ],
        scope_section_prefix="8.5",
        reason="reached_leaf",
    )
    assert not should_release_drill_scope(drill)