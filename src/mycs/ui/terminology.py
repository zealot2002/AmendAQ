"""User-facing terminology (keep internal code names: draft, wiki_toc, publish)."""

WIKI = "Wiki 目录"
WIKI_DRAFT = "Wiki 草稿"
WIKI_PUBLISHED = "已发布"
KG = "知识图谱"

STEP_LABELS_UI = {
    "upload": "1. 上传文档 (.txt)",
    "ingest_draft": f"2. 解析入库 → {WIKI_DRAFT}（{WIKI} + {KG}）",
    "review": f"3. 人工审核（编辑节点，仍为{WIKI_DRAFT}）",
    "publish": f"4. 发布 {WIKI}（{WIKI_DRAFT} → {WIKI_PUBLISHED}）",
    "qa_ready": f"5. 智能问答（仅读{WIKI_PUBLISHED}的 {WIKI} 边界）",
}
