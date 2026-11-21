from mycs.prompts import load_prompts, prompt
from mycs.skills.loader import load_skills


def test_prompt_file_has_every_section():
    names = set(load_prompts())
    assert {
        "understand",
        "toc_select",
        "toc_catalog",
        "faq_title",
        "plan",
        "compose",
        "revise",
        "compile",
        "rigor_audit",
        "graph_extract",
        "text2sql",
        "organize_external",
        "skill_capped_quantity",
    } <= names


def test_prompt_fills_placeholders():
    text = prompt("faq_title_ordinary", pick_cap=5)
    assert "硬性上限 5 条" in text
    assert "{{" not in text


def test_capped_quantity_skill_uses_prompt_file():
    skill = next(s for s in load_skills() if s.name == "capped-quantity")
    assert "不得超过该上限" in skill.instructions
    assert "config/prompts.txt" not in skill.instructions
