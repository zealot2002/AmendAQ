# 从 TXT 到 Wiki：员工手册入库与问答（M3）

## 目标

- 原始知识：`data/sources/employee_handbook.txt`（公开样例手册，见 `data/sources/README.md`）
- **Ingest**：按 `#### 章节号 标题` 切分为 Wiki 政策条目
- 每条带 **内嵌 evidence**（quote + source_uri + effective_from）
- **无向量 chunk**；检索用 `search_handbook` 关键词匹配
- Agent：`handbook_qa` → search → get_policy → get_evidence → Verify → Answer

## 命令

```bash
# 1. TXT → Wiki JSON
uv run mycs ingest handbook

# 2. 问答（Mock 或 Ollama）
uv run mycs --demo handbook
uv run mycs --llm ollama "试用期有多长？"
uv run mycs-ui
```

产物：`data/wiki/canonical.json`

## 实现

| 步骤 | 模块 |
|------|------|
| Ingest | `src/mycs/wiki/ingest.py` |
| Wiki 读/search | `src/mycs/wiki/store.py` |
| 与办事 JSON 并存 | `src/mycs/knowledge/combined.py` |
| Tools | `search_handbook`, `get_handbook_policy`, `get_handbook_evidence` |

## 踩坑

- 必须先 `ingest`，否则 Wiki 文件不存在
- Ollama 改写过度可能导致 Verify 与 evidence 片段不一致（Mock 模板更容易过 Verify）

## 代码位置

见上表；系列仍保留政务 `case` demo，与员工手册场景并列。
