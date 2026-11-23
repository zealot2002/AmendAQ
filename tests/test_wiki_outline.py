from pathlib import Path

from amendaq.wiki.outline import parse_outline_from_text


def test_parse_outline_has_chapters_and_leaves():
    text = Path("docs/星河科技_中文员工手册_知识库测试.txt").read_text(encoding="utf-8")
    roots = parse_outline_from_text(text)
    assert len(roots) >= 5
    leaves = [lf for ch in roots for lf in ch.children]
    assert len(leaves) >= 20
    sections = {lf.section_ref for lf in leaves}
    assert "5.1" in sections
    assert "8.5" in sections
