# 系列博文索引 — mycs 智能客服

代码与文章同仓同步。完整里程碑见 [PLAN.md](./PLAN.md)。

## 产品范围

**泛化智能客服**：政府办事咨询、企业公众支持、学校政策问答等。核心能力是 **Knowledge Agent + 可核查答复**；**不绑定订单/电商**。动态事实（办件进度、工单状态、学籍等）通过 **可选的领域状态 API** 接入；许多场景仅依赖 Wiki 即可闭环。

## 实现约定（全系列）

- **主路径**：Knowledge Requirement → 结构化 Wiki +（可选）领域状态 API → Verify → Answer。
- **证据**：Wiki 内嵌 `evidence`（原文引用 + 来源 + 生效时间），**不使用向量 chunk / RAG 检索里程碑**。
- **演示域**：默认 Reference 场景为办事/政策咨询 + 可选 `case_id`；[01](./posts/01-rag-end-is-knowledge.md) 中的 iPhone/订单叙事仅为理论举例。
- **Agent 编排**：**M1–M4 自研 `AgentLoop`**，不依赖 LangGraph / LangChain；trace 与 `KnowledgeRequirement` / `Verifier` 边界见 [PLAN.md](./PLAN.md#agent-编排与框架选型)。M6 可选 LangGraph（HITL 等），非必须。
- **日志 tag**：`joyjoy`。

## 文章列表

| # | 文件 | 里程碑 | 摘要 |
|---|------|--------|------|
| 1 | [posts/01-rag-end-is-knowledge.md](./posts/01-rag-end-is-knowledge.md) | — | RAG 演进与企业知识 OS（理论） |
| 2 | [posts/02-knowledge-agent-loop.md](./posts/02-knowledge-agent-loop.md) | M0–M1 | 最小 Agent 闭环（Mock LLM，泛化咨询场景） ✅ |
| 3 | [posts/03-ollama-and-trace-ui.md](./posts/03-ollama-and-trace-ui.md) | M2 | Ollama 联调与 trace 可视化 ✅ |
| 4 | [posts/04-wiki-embedded-evidence.md](./posts/04-wiki-embedded-evidence.md) | M3 | 员工手册 TXT→Wiki 与问答 ✅ |
| 5 | [posts/05-verify-without-chunk-rag.md](./posts/05-verify-without-chunk-rag.md) | M4 | 政策 Verify + 可选 Case 状态 API |
| 6 | [posts/06-mcp-knowledge-api.md](./posts/06-mcp-knowledge-api.md) | M5 | MCP 暴露 Knowledge API |
| 7 | [posts/07-hitl-and-eval.md](./posts/07-hitl-and-eval.md) | M6 | 知识治理与评测（可选：LangGraph 迁移笔记作附录） |

## 模板（新博文）

```markdown
# 标题

## 目标
## 实现
## 遇到的问题
## 踩坑
## 思考与总结
## 代码位置
```
