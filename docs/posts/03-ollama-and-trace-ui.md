# Ollama 联调与 Trace 可视化（M2）

## 目标

- 同一 `AgentLoop`，切换 **Mock / Ollama** 后端
- OpenAI 兼容 API（默认 `http://localhost:11434/v1`）
- **Gradio** 聊天 + 右侧 Markdown trace
- **Verify 的 claims 仍由代码生成**，不让 LLM 自证

## 环境

```bash
ollama pull qwen2.5:7b   # 或 llama3.1:8b
cp .env.example .env
export MYCS_LLM=ollama   # 可选，UI 里也可选
uv sync --extra dev --extra ui
uv run python scripts/check_ollama.py
```

## 实现要点

| 组件 | 路径 |
|------|------|
| `OllamaLLM` | `src/mycs/llm/ollama.py` |
| `create_llm()` | `src/mycs/llm/factory.py` |
| 确定性 claims | `src/mycs/llm/claims.py` |
| Gradio UI | `src/mycs/ui/gradio_app.py` |

Ollama 负责 understand / plan（JSON）与用户可见回复。任一步失败抛出 **`OllamaLLMError`**，**不回退 Mock**。`build_claims()` 与 M1 一致，保证 Verifier 稳定。

## 运行

```bash
# CLI
uv run mycs --llm ollama --demo case

# Web UI（默认 http://127.0.0.1:7860）
uv run mycs-ui
```

## 遇到的问题

（联调时在此记录。）

## 踩坑

- 小模型 JSON 格式不稳定 → 直接报错；可改用 mock 后端或换模型
- `format: json` 需 Ollama 较新版本；否则可能 JSON 解析失败并抛错
- 勿让 LLM 输出 verify 结论；claims 必须来自 tool context

## 思考与总结

M2 证明 **loop 与 LLM 解耦**：M3 换 Wiki 实现时，UI 与 Ollama 层可不动。

## 代码位置

见上表；trace 仍在 `data/traces/`。
