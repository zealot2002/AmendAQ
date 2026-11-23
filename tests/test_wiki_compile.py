from pathlib import Path

import pytest

from amendaq.wiki.canonical import (
    WikiCanonicalDraft,
    canonical_to_outline_roots,
    leaf_evidence_quotes,
    validate_canonical,
)
from amendaq.wiki.compile import compile_faq_markdown_rules, compile_wiki_draft
from amendaq.wiki.ingest_contract import enforce_faq_contract, validate_faq_markdown_contract

HAOSHI_FAQ = Path("/Users/zzy/Desktop/智能客服FAQ问题列表.md")


def test_validate_rejects_bad_quote():
    draft = WikiCanonicalDraft.from_dict(
        {
            "document": {"title": "t"},
            "chapters": [{"section_ref": "1", "title": "A"}],
            "leaves": [
                {
                    "section_ref": "1.1",
                    "parent_ref": "1",
                    "title": "Q",
                    "summary": "Q",
                    "body": "hello world",
                    "evidence": {"quote": "not in body"},
                }
            ],
        }
    )
    errs = validate_canonical(draft)
    assert any("quote" in e for e in errs)


def test_compile_rules_minimal():
    text = """# Demo FAQ

## 一、模块（2题）

### Q1. 怎么下载？
**答：** 请访问官网下载。

### Q2. 闪退？
**答：** 请重启手机。
"""
    draft = compile_faq_markdown_rules(text, source_uri="file://x")
    assert len(draft.chapters) == 1
    assert len(draft.leaves) == 2
    assert not validate_canonical(draft)
    roots = canonical_to_outline_roots(draft)
    assert len(roots[0].children) == 2
    quotes = leaf_evidence_quotes(draft)
    assert quotes["1.1"] in draft.leaves[0].body
    enforce_faq_contract(text, draft)


def test_faq_contract_rejects_informal_headings():
    text = """# Bad

## 模块

### 怎么下载？
**答：** 官网。

### Q2. 收费吗
没有答标记行
"""
    draft = compile_faq_markdown_rules(text)
    errs = validate_faq_markdown_contract(text, draft)
    assert any("Q数字" in e or "答" in e for e in errs)
    with pytest.raises(ValueError, match="不符合入库规范"):
        enforce_faq_contract(text, draft)


def test_handbook_contract_rejects_faq_plain_txt():
    from amendaq.ui.ingest_document import ingest_document_file
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", encoding="utf-8", delete=False) as f:
        f.write("这是 Word 导出的 FAQ，只有问：如何下载？答：去官网。\n")
        path = f.name
    try:
        with pytest.raises(ValueError, match="不符合入库规范|未生成目录"):
            ingest_document_file(Path(path), document_id="bad_plain_faq")
    finally:
        Path(path).unlink(missing_ok=True)


@pytest.mark.skipif(not HAOSHI_FAQ.is_file(), reason="haoshi FAQ not on desktop")
def test_haoshi_faq_rules_shape():
    text = HAOSHI_FAQ.read_text(encoding="utf-8")
    draft = compile_wiki_draft(None, text, rules_only=True)
    assert len(draft.chapters) >= 10
    assert len(draft.leaves) >= 38
    assert not validate_canonical(draft)
    for lf in draft.leaves:
        q = lf.evidence.quote or lf.body
        assert q.strip() in lf.body or lf.body.strip() in q


@pytest.mark.skipif(not HAOSHI_FAQ.is_file(), reason="haoshi FAQ not on desktop")
def test_haoshi_sample_fails_strict_ingest():
    """Raw 好势稿含空 ## 块与缺 Q3，strict 模式应拒绝入库。"""
    text = HAOSHI_FAQ.read_text(encoding="utf-8")
    draft = compile_wiki_draft(None, text, rules_only=True)
    with pytest.raises(ValueError, match="不符合入库规范"):
        enforce_faq_contract(text, draft)