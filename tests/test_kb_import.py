from mycs.kb.import_parse import parse_faq_import_text


def test_parse_qna_pairs():
    text = """Q1：题目1
A1：题目1答案

Q2：题目2
A2：题目2答案"""
    rows = parse_faq_import_text(text)
    assert len(rows) == 2
    assert rows[0].question == "题目1"
    assert rows[0].answer == "题目1答案"
    assert rows[1].question == "题目2"
    assert rows[1].answer == "题目2答案"


def test_parse_qna_pairs_multiline_and_halfwidth():
    text = """Q1: 怎么请假？
A1: 先在系统提交。
部门负责人审批后生效。

Q2: 审批要多久？
A2: 一个工作日。"""
    rows = parse_faq_import_text(text)
    assert len(rows) == 2
    assert rows[0].question == "怎么请假？"
    assert rows[0].answer == "先在系统提交。\n部门负责人审批后生效。"
    assert rows[1].answer == "一个工作日。"


def test_parse_qna_question_can_span_lines():
    text = """Q1：年假怎么算？
含当年已休和上年结转。
A1：按自然年计算。
结转部分单独列出。"""
    rows = parse_faq_import_text(text)
    assert len(rows) == 1
    assert rows[0].question == "年假怎么算？\n含当年已休和上年结转。"
    assert rows[0].answer == "按自然年计算。\n结转部分单独列出。"


def test_parse_markdown_faq():
    text = """# T

## A

### Q1. 怎么下载？
**答：**
去应用商店搜索下载。

### Q2. 收费吗？
**答：**
基础功能免费。
"""
    rows = parse_faq_import_text(text)
    assert len(rows) == 2
    assert "下载" in rows[0].question
    assert "应用商店" in rows[0].answer


def test_parse_markdown_faq_without_chapter():
    text = """### Q1. 怎么修改登录密码？
**答：**
打开「设置 - 账号安全」，按短信验证后设置新密码。

### Q2. 忘记密码怎么办？
**答：**
在登录页点「忘记密码」，用绑定手机号重置。"""
    rows = parse_faq_import_text(text)
    assert len(rows) == 2
    assert rows[0].question == "怎么修改登录密码？"
    assert "账号安全" in rows[0].answer
    assert rows[1].question == "忘记密码怎么办？"


def test_parse_numbered_q_a():
    text = """1. Q：本员工手册适用哪些人员？
A：适用于正式员工、实习生及固定期限员工。
2. Q：公司标准工作周与核心协作时间是？
A：标准工作周周一至周五。"""
    rows = parse_faq_import_text(text)
    assert len(rows) == 2
    assert "适用哪些人员" in rows[0].question
    assert "正式员工" in rows[0].answer


def test_parse_loose_qa():
    text = """问：营业时间？
答：9:00-18:00

问：地址？
答：北京市朝阳区"""
    rows = parse_faq_import_text(text)
    assert len(rows) == 2
    assert rows[0].question == "营业时间？"