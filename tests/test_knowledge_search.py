from mycs.knowledge.search import score_entity, tokenize


def test_tokenize_bigrams_overlap_long_question():
    q = "走势图能不能投屏到电视上？"
    title = "Q36. 走势图能投屏到电视吗？"
    assert tokenize(q) & tokenize(title)


def test_score_t09_cast_screen():
    q = "走势图能不能投屏到电视上？"
    title = "Q36. 走势图能投屏到电视吗？"
    summary = title
    body = (
        "支持。在电视频道页面点击「扫一扫」按钮，扫码对应的电视二维码绑定电视，"
        "再选择走势图或海报投屏，适合店内大屏展示。"
    )
    assert score_entity(q, title, summary, body) >= 4.0