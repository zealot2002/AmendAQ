from mycs.kb.import_parse import parse_faq_import_text


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