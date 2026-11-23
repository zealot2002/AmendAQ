from amendaq.skills.loader import AnswerSkill, load_skills, match_skills


def _skill(**kwargs) -> AnswerSkill:
    base = dict(
        name="capped-quantity",
        description="",
        question_any=("最多", "上限", "余额"),
        evidence_any=("上限", "最多", "不超过"),
        revise=True,
        instructions="add then cap",
    )
    base.update(kwargs)
    return AnswerSkill(**base)


def test_skill_matches_when_question_and_clauses_both_hit():
    skills = [_skill()]
    got = match_skills(
        skills,
        "最多还能有多少天年假余额",
        "可获得15个带薪年假日。最多可以结转至20天的余额上限。",
    )
    assert [s.name for s in got] == ["capped-quantity"]


def test_skill_skips_when_clauses_have_no_cap_language():
    got = match_skills(
        [_skill()],
        "最多还能有多少天",
        "全职员工每完成一个完整工作年度可获得15个带薪年假日。",
    )
    assert got == []


def test_builtin_capped_quantity_skill_loads():
    names = [skill.name for skill in load_skills()]
    assert "capped-quantity" in names


def test_skill_without_triggers_is_not_auto_enabled():
    silent = _skill(name="manual-only", question_any=(), evidence_any=())
    got = match_skills([silent], "最多余额", "上限 20 天")
    assert got == []
