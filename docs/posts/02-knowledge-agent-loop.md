# 从一条办件咨询开始：手写 Knowledge Agent 最小闭环

## 目标

在 **M0 + M1** 交付可运行的参考实现：

- 自研 `AgentLoop`（不使用 LangGraph / LangChain）
- `KnowledgeRequirement` 规划（不是 search 关键词）
- Stub Tools + **Mock LLM**
- JSON **trace** 落盘
- 确定性 **Verify**

## 环境（M0）

```bash
cd mycs
uv sync --extra dev
uv run mycs --demo case
uv run python scripts/check_ollama.py   # M2 前可选，检查 Ollama 是否可达
```

目录要点：

```text
src/mycs/          Agent、Tools、Verifier、MockLLM
data/reference/    种子：办件、政策、办事指南
data/traces/       运行 trace（gitignore）
tests/
```

## 实现

### Reference 场景

1. **办件 + 政策时限**（默认 demo）  
   问：「我的办件 CASE-2026-001 为什么还在预审？依据哪条时限规定？」  
   Plan 缺口：`case.status` → `case.procedure_id` → `policy.review_time_limit`。

2. **纯政策**（无 case_id）  
   问：「居住证续签能否线上办理？」  
   仅调用 `get_procedure`。

### 闭环步骤

```text
Understand → Plan → Tool* → Verify → Answer
```

对应代码：`src/mycs/agent/loop.py`。

### 运行

```bash
uv run mycs --demo case
uv run mycs --demo policy
uv run mycs "自定义问题" --case-id CASE-2026-001
```

## 遇到的问题

（实现过程中可在此补充真实 issue。）

## 踩坑

- **Plan 写成搜索词**：应用 `KnowledgeRequirement.field + tool + source`，不要 `search("预审")`。
- **先 case 后 policy**：`get_policy_for_stage` 依赖 `case.procedure_id`，Tool 顺序要在 Plan 里可解释。
- **Verify 交给 LLM**：M1 的 `Verifier` 只对比 Domain 返回与 Wiki 内嵌 `evidence`，不用模型自证。

## 思考与总结

M1 故意用 Mock LLM，是为了让 **trace 可复现**；M2 再换 Ollama，loop 与 ToolRegistry 接口不变。

## 代码位置

| 模块 | 路径 |
|------|------|
| AgentLoop | `src/mycs/agent/loop.py` |
| MockLLM | `src/mycs/llm/mock.py` |
| Tools | `src/mycs/tools/registry.py` |
| Verifier | `src/mycs/verifier.py` |
| CLI | `src/mycs/cli.py` |
| 种子数据 | `data/reference/*.json` |
