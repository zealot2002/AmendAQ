# mycs

**A support agent that answers from published Q&A — not from retrieved chunks.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](pyproject.toml)
[![Dev.to series](https://img.shields.io/badge/Dev.to-%22RAG%20%E7%9A%84%E7%BB%88%E7%82%B9%E6%98%AF%E7%9F%A5%E8%AF%86%22-blue)](https://dev.to/zealot2002/series/47162)

You choose a knowledge base. The model only ticks published item IDs from the title list. It must write the answer from those full texts. A rule-based verifier — not another model call — rejects replies that invent obligations or contradict the source.

This is the runnable slice of a larger idea: RAG should end in knowledge, not in better search. The long-term shape (wiki, state APIs, knowledge requirements) is documented below. What you can run today is the path in the Dev.to series [RAG 的终点是知识](https://dev.to/zealot2002/series/47162): pick a library, select IDs, verify by rules.

[中文说明](README.zh-CN.md)

## Why this is not another RAG

| | Chunk + vector + generate | mycs (published FAQ + ID selection + rule verify) |
|---|---|---|
| Source | Raw text chunks | Published FAQ items with full answers |
| Retrieval | Vector similarity / hybrid search | LLM reads the title list and returns only IDs |
| Evidence | A chunk that "looks similar" | The full text of the selected FAQ items |
| Verification | Often none, or "do you think this is correct?" | Deterministic rules: cited source, no invented obligations, no contradiction |
| Failure mode | Hallucinates an answer from nearby chunks | Empty recall → refuses to answer |

## Screenshot / GIF

The Vue admin UI includes a process panel on the right side of the chat page that shows every step: skip-understand, title-batch selection, tool calls, compose, and rule verification. A screenshot or GIF of this panel should be added here. (No fake screenshot is included in this PR.)

## Quick start (Vue / mycs-api path)

This is the current default runnable path. The older Ollama graph build, `kg_*` APIs, government demo, and Gradio UI still exist in the repo but are not the main entry point.

1. Copy and edit the environment file:

```bash
cp .env.example .env
# Edit .env and set a provider:
#   MYCS_LLM=glm    -> fill GLM_API_KEY
#   MYCS_LLM=ollama -> set OLLAMA_BASE_URL to your Ollama host
#   MYCS_LLM=openai -> set OPENAI_API_BASE and OPENAI_MODEL
#   MYCS_LLM=groq   -> set GROQ_API_KEY
```

2. Install Python dependencies and start the dev environment:

```bash
uv sync --extra dev --extra web
scripts/restart-dev.sh
```

The script installs frontend dependencies if needed, starts the FastAPI backend (`mycs-api`) on port `8765`, and starts the Vite frontend on port `5180`. It prints the local URL, usually `http://127.0.0.1:5180/`.

3. Open the printed URL, create a library, and import a few Q&A items.

Use the **Batch Import** format:

```text
Q1: How do I reset my password?
A1: Go to Settings → Account → Reset Password and follow the email link.

Q2: What are your support hours?
A2: Live chat is available 09:00–18:00 UTC on business days.
```

4. Click **Publish** so the items become visible to the agent.

5. Go to **Chat**, select the library, and ask example questions:

- "How do I reset my password?"
- "What are your support hours?"
- "Can I call support on Saturday?"

Watch the right-hand process panel: it shows whether the model skipped the understand step, which FAQ IDs it ticked, what full texts were loaded, and whether rule verification passed.

### Advanced: CLI Q&A

If you already have a published library with `document_id` `my_kb`:

```bash
export MYCS_GRAPH_DOCUMENT=my_kb
uv run mycs "Can I call support on Saturday?"
```

The CLI path is advanced; the Vue UI is the recommended first entry.

## How it actually works

1. **Pick a knowledge base.** When a document is selected in the UI, the agent skips the generic "understand" model call because the user already chose the context.
2. **List published titles.** All `published` FAQ items in that library are loaded. If the count is below `MYCS_FAQ_SINGLE_PASS_MAX` (default 120), the whole title list is sent to the model at once.
3. **Model returns IDs only.** The model is asked to return only `section_refs` that match the question. IDs that are not in the list are discarded.
4. **Load full texts.** The agent reads the full answer text for each selected ID.
5. **Compose from source.** The model writes the final answer using only those full texts.
6. **Verify with rules.** `Verifier.verify_graph_answer` checks that an answer cites a source, that claims are not invented, and that contradictions like "must ... but not found" are rejected. For bounded quantity problems (e.g. annual leave), a skill computes the numeric bound from the question and the source text before composing the answer.

## Evaluation / reproducibility

Be honest: the **Xinghe 13-question benchmark** discussed in the blog is **not reproducible from this repo**.

- `scripts/run_xinghe_eval.py` only contains 10 questions, not 13.
- The source handbook file (`docs/星河科技_中文员工手册_知识库测试.txt`) is missing, so the script cannot re-ingest the evaluated document.
- Some older wiki-tree evaluation reports are stale.
- Some tests hard-code local desktop paths.

You can still run a demo: create a library, import your own Q&A, publish it, and ask questions while watching the process panel. A reproducible evaluation set and a shared demo corpus are still being collected.

## Limits and roadmap

### Current limits

- **Not general vector RAG.** The main path is intentionally a published-FAQ pipeline, not open-domain retrieval.
- **Scale:** Sending all published titles at once fits tens to low-hundreds of items. It is not a million-document search engine.
- **Verification:** Counts and obligations are rule-checked, but the current rules can still be too strict (false rejections) or miss some paraphrased contradictions.
- **Tree descent:** `wiki.toc.*` and `kg_*` code paths still exist but are not the main path used by the Vue UI.

### Roadmap

**Done**
- Published FAQ as the primary source.
- Skip the understand model call when a knowledge base is already selected.
- Rule-based verifier, not LLM self-attestation.
- Bounded numeric answers computed by the program from the source text.

**Next**
- Filter selected IDs by abstract/summary mismatch before composing.
- Hyponym recall (e.g. "laptop" ↔ "device") when the model returns empty.
- On verify failure, delete only the ungrounded sentences instead of rejecting the whole answer.
- Optional vector shortlist to speed up large title lists, but still not vector-as-main-retrieval.

**Later**
- Knowledge world / LLMWiki: entities, relations, events, state, timeline.
- MCP server for the knowledge API.
- Domain state APIs (case/ticket/appointment status) from part 1 of the series.

## Blog series

The code backs the Dev.to series [RAG 的终点是知识](https://dev.to/zealot2002/series/47162).

| # | Title | What it covers |
|---|-------|----------------|
| 1 | [RAG 的终点不是检索，而是知识](https://dev.to/zealot2002/rag-de-zhong-dian-bu-shi-jian-suo-er-shi-zhi-shi-550f) | From chunk retrieval to a persistent knowledge layer |
| 2 | [知识库既已选定，就别再让模型做意图分类](https://dev.to/zealot2002/zhi-shi-ku-ding-liao-jiu-bie-zai-rang-mo-xing-cai-ni-zai-wen-shi-yao-3bgh) | Skip understand, read the whole title list, return IDs |
| 3 | [三个模型只改一个变量：7B 读标题花了 27 秒](https://dev.to/zealot2002/san-ge-mo-xing-zhi-gai-ge-bian-liang-45jm) | Switching backends, cost of reading titles, comparing results |
| 4 | [答复能不能发出去，别再问模型自己对不对](https://dev.to/zealot2002/wen-da-shi-bian-ping-de-xian-fa-bu-zai-rang-mo-xing-kan-jian-2i1i) | Publish gate, compose rules, deterministic verification |

The files under `docs/posts/02-04.md` are unpublished / old outlines. They are **not** the published articles above.

## License and contributing

MIT © 2026 [zealot2002](https://github.com/zealot2002). See [LICENSE](LICENSE).

Contributions, issues, and PRs are welcome. If you try the quick start and the process panel does not match what you see, please open an issue with the trace file path from `data/traces/`.
