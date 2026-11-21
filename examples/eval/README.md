# Reproducible evaluation

This folder contains a self-contained evaluation set for the published-FAQ path.

Files:

- `eval_questions.json` — 12 questions against the fictional Stellar Systems demo FAQ.
- `RUBRIC.md` — scoring rubric.
- `run_eval.py` — imports the demo FAQ, publishes it, runs the questions through `AgentLoop`, and scores the results.

## Run

Make sure the demo FAQ has been seeded first:

```bash
uv run python examples/demo/import_demo.py        # English demo
uv run python examples/demo/import_demo.py --lang zh  # Chinese demo
```

Then run the evaluation:

```bash
uv run python examples/eval/run_eval.py        # English questions
uv run python examples/eval/run_eval.py --lang zh  # Chinese questions
```

The script uses the LLM backend configured in your `.env` (e.g. `MYCS_LLM=glm`).

## Dry-run

To verify that the data and questions load correctly without calling an LLM:

```bash
uv run python examples/eval/run_eval.py --dry-run
uv run python examples/eval/run_eval.py --lang zh --dry-run
```

## Output

The script prints a per-question table and a summary like:

```text
fully-correct:     9/12
partially-correct: 2/12
wrong:             1/12
```

A detailed JSON report is written to `data/eval/stellar_demo_<timestamp>.json`.

## Notes

- This evaluation is **not** the original Xinghe 13-question benchmark from the blog. That benchmark is missing its handbook file and is not reproducible in this repo.
- This bundled eval is honest and runnable: the source FAQ, questions, rubric, and scoring script are all in this folder.
