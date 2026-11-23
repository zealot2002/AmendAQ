# mycs

**AmendAQ: a support agent that answers from published Q&A you can revise one row at a time — not from retrieved chunks.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](pyproject.toml)
[![Dev.to series](https://img.shields.io/badge/Dev.to-AmendAQ-blue)](https://dev.to/zealot2002/series/47234)

You choose a knowledge base. The model only ticks published item IDs from the title list. It must write the answer from those full texts. A rule-based verifier — not another model call — rejects replies that invent obligations or contradict the source. Changing one rule means editing that published row. The next question reads the new text. There is no re-embed step.

This is the runnable slice of a larger idea: RAG should end in knowledge, not in better search. The long-term shape (wiki, state APIs, knowledge requirements) is documented below. What you can run today is [AmendAQ, a better RAG?](https://dev.to/zealot2002/series/47234): pick a library, select IDs, verify by rules.

[中文说明](README.zh-CN.md)

## Why this is not another RAG

| | Chunk + vector + generate | AmendAQ (published FAQ + ID selection + rule verify) |
|---|---|---|
| Source | Raw text chunks | Published FAQ items with full answers |
| Retrieval | Vector similarity / hybrid search | LLM reads the title list and returns only IDs |
| Evidence | A chunk that "looks similar" | The full text of the selected FAQ items |
| Verification | Often none, or "do you think this is correct?" | Deterministic rules: cited source, no invented obligations, no contradiction |
| Failure mode | Hallucinates an answer from nearby chunks | Empty recall → refuses to answer |

## Screenshot

The Vue admin UI includes a process panel on the right side of the chat page that shows every step: skip-understand, title-batch selection, tool calls, compose, and rule verification.

![Process panel](docs/images/process-panel-devto.png)

> This is a real capture from an earlier demo. It shows the older Xinghe data, but the visible workflow is the same one this repo runs today: skip understand, batch-select FAQ IDs, load full texts, verify by rules.

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

3. Seed the bundled demo corpus:

```bash
uv run python examples/demo/import_demo.py
```

This creates a fictional library called **Stellar Systems Demo** and imports the 10 Q&A pairs from `examples/demo/stellar_faq.en.txt` as published items.

4. Open the printed URL, go to **Knowledge Base**, click the **Stellar Systems Demo** library, and confirm the items are published.

5. Go to **Chat**, select the demo library, and ask:

- "When is the quarterly bonus paid?"
- "How many remote work days are allowed per week?"
- "Can I bring my pet to the office?" (not in the demo corpus — expect a refusal)

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
2. **List published titles.** All `published` FAQ items in that library are loaded. If the count is at or below `MYCS_FAQ_SINGLE_PASS_MAX` (default 200), the whole title list is sent to the model at once. Above that, titles go out in batches of `MYCS_FAQ_BATCH_SIZE` (default 200), and every batch is scanned.
3. **Model returns IDs only.** The model is asked to return only `section_refs` that match the question. IDs that are not in the list are discarded.
4. **Load full texts.** The agent reads the full answer text for each selected ID.
5. **Compose from source.** The model writes the final answer using only those full texts.
6. **Verify with rules.** `Verifier.verify_graph_answer` checks that an answer cites a source, that claims are not invented, and that contradictions like "must ... but not found" are rejected. For bounded quantity problems (e.g. annual leave), a skill computes the numeric bound from the question and the source text before composing the answer.

## Evaluation / reproducibility

A bundled, runnable evaluation is now in `examples/eval/`:

```bash
uv run python examples/eval/run_eval.py        # English FAQ + questions
uv run python examples/eval/run_eval.py --lang zh  # Chinese FAQ + questions
```

It imports the fictional **Stellar Systems Demo** FAQ from `examples/demo/`, runs 12 questions through `AgentLoop`, and scores each answer with the rubric in `examples/eval/RUBRIC.md`. The questions are designed to show the product's strengths (ID selection, rule verification, program-computed numeric answers, refusal when missing). A dry-run mode is available that imports and validates the data without calling an LLM:

```bash
uv run python examples/eval/run_eval.py --dry-run
```

The Chenghai handbook comparison (211 published Q&A, 60 questions, same `Qwen3.6` for mycs, a fixed traditional RAG pipeline, and LightRAG) is written up in [docs/posts/03-when-to-choose-amendaq.md](docs/posts/03-when-to-choose-amendaq.md). Reproduce it with `scripts/run_compare.py`. On condition A, scores were AmendAQ 55/60, traditional RAG 56/60, LightRAG 54/60. The 10 questions that need two or more entries were 10/10 for AmendAQ. Traditional RAG was faster (median 7.6s vs 21.2s).

The original **Xinghe 13-question benchmark** is **still not reproducible from this repo**:

- `scripts/run_xinghe_eval.py` only contains 10 questions, not 13, and now carries a clear header note.
- The source handbook file (`docs/星河科技_中文员工手册_知识库测试.txt`) is missing, so the script cannot re-ingest the evaluated document.
- Some older wiki-tree evaluation reports are stale.
- Some tests hard-code local desktop paths.

## Limits and roadmap

### Current limits

- **Not general vector RAG.** The main path is intentionally a published-FAQ pipeline, not open-domain retrieval.
- **Scale:** Sending published titles in batches of 200 fits tens to low hundreds of items. It is not a million-document search engine.
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

The code backs the Dev.to series [AmendAQ, a better RAG?](https://dev.to/zealot2002/series/47234).

| # | Title | What it covers |
|---|-------|----------------|
| 1 | [如果一条制度可以改完就生效，还要先向量化吗](https://dev.to/zealot2002/ru-guo-tiao-zhi-du-ke-yi-gai-wan-jiu-sheng-xiao-huan-yao-xian-xiang-liang-hua-ma-501b) | Why a revisable Q&A row is a better unit than a vector chunk |
| 2 | [AmendAQ 在 mycs 里是一本可以改的问答](https://dev.to/zealot2002/amendaq-zai-mycs-li-shi-ben-ke-yi-gai-de-wen-da-539) | Pick a library, return IDs, verify by rules |
| 3 | [同题对照之后，有些场景可以选择 AmendAQ](https://dev.to/zealot2002/tong-ti-dui-zhao-zhi-hou-you-xie-chang-jing-ke-yi-xuan-ze-amendaq-1dhk) | Same 60 questions against traditional RAG and LightRAG |

Source files: [docs/posts/](docs/posts/). Index: [docs/SERIES.md](docs/SERIES.md).

## License and contributing

MIT © 2026 [zealot2002](https://github.com/zealot2002). See [LICENSE](LICENSE).

Contributions, issues, and PRs are welcome. If you try the quick start and the process panel does not match what you see, please open an issue with the trace file path from `data/traces/`.
