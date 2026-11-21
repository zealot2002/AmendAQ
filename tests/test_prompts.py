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


def test_composite_selection_does_not_add_ordinary_cap():
    from mycs.planning.flat_faq import faq_title_notes

    kind_note, composite_note = faq_title_notes(
        enumerative_query=False,
        composite_query=True,
        pick_cap=5,
    )
    assert kind_note == ""
    assert "每一件事" in composite_note
    assert "通常 1～3 条" not in composite_note


def test_capped_quantity_skill_uses_prompt_file():
    skill = next(s for s in load_skills() if s.name == "capped-quantity")
    assert "不得超过该上限" in skill.instructions
    assert "config/prompts.txt" not in skill.instructions
