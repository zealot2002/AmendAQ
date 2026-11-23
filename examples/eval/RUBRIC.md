# Evaluation rubric

This rubric is used by `run_eval.py` to score each question against the bundled Stellar Systems demo FAQ.

## Categories

| Label | Meaning |
|-------|---------|
| **fully-correct** | The answer contains the expected fact, does not invent obligations, and rule verification passes (`verify.ok == true`). |
| **partially-correct** | The answer is directionally right but misses a key detail, or rule verification fails on a minor contradiction, or it answers an out-of-corpus question with a fabricated policy. |
| **wrong** | The answer is factually incorrect, refuses to answer an in-corpus question, or answers an out-of-corpus question as if the policy existed. |

## Expected behavior per question type

- **In-corpus questions** (`expected_behavior == "answer"`):
  - `verify.ok` should be `true`.
  - The final answer should contain at least one of the `expected_substrings`.
  - The agent should not invent numbers, obligations, or policies not in the selected FAQ.

- **Out-of-corpus questions** (`expected_behavior == "refuse"`):
  - The agent should indicate that no relevant published FAQ was found.
  - `verify.ok` may be `false` because no source was retrieved.
  - The answer should not contain a fabricated policy.

## Limitations

- This is a deterministic, string-based scorer. It does not judge paraphrased answers that omit the exact expected substring.
- The evaluation requires a configured LLM backend (`AMENDAQ_LLM` plus the matching key/base variables). Without it, the script can still do a data dry-run (`--dry-run`).
- The score is a sanity check for the published-FAQ pipeline, not a claim about general-domain RAG performance.
