from amendaq.answer_format import answer_for_user, split_answer_sections


def test_split_strips_conclusion_and_hides_evidence_from_user():
    full = "结论：可下载。\n\n依据：\n1. 官网\n2. APK"
    public, evidence = split_answer_sections(full)
    assert public == "可下载。"
    assert evidence.startswith("依据：")
    user = answer_for_user(full)
    assert user.startswith("可下载。")
    assert "官网" in user


def test_no_evidence_block():
    text = "结论：否"
    public, evidence = split_answer_sections(text)
    assert public == "否"
    assert evidence == ""


def test_terse_conclusion_merges_evidence_for_user():
    full = (
        "结论：可以。\n\n"
        "依据：\n"
        "§9.2 投屏步骤：\n"
        "1. 打开走势图\n"
        "2. 点击投屏"
    )
    merged = answer_for_user(full)
    assert merged.startswith("可以。")
    assert "§9.2" in merged
    assert "打开走势图" in merged