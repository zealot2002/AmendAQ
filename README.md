# mycs — Knowledge Agent 智能客服

```text
.txt ──Ollama 建图──► kg_* + data/kg/*.json
问题 ──Understand/Compose (Ollama)──► Plan（Ollama 多缺口）──► kg_* API ──► Verify
```

- **无 Mock**、无针对特定题库的 `decompose` / `reason`
- **graph_qa Plan**：`graph.entity.search` +（聚合类问题）`graph.read.query`（Ollama text-to-SQL）
- 政务 demo：`gov_*` 表 + Ollama Plan

## 快速开始

```bash
uv sync --extra dev --extra ui
uv run mycs bootstrap

export MYCS_GRAPH_DOCUMENT=my_company
uv run mycs ingest txt path/to/doc.txt --doc-id my_company
uv run mycs "你的问题"

uv run mycs-ui
```

环境：`OPENAI_API_BASE`、`OPENAI_MODEL`、`MYCS_GRAPH_DOCUMENT`、`MYCS_DB`。

详见 [docs/用户使用.md](docs/用户使用.md)。
