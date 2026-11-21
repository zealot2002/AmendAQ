# Demo FAQ corpus

This folder contains a small, clearly fictional FAQ corpus for the published-FAQ path.

Files:

- `stellar_faq.en.txt` — English Q&A pairs in the batch-import format.
- `stellar_faq.zh.txt` — Chinese Q&A pairs (same fictional company).
- `import_demo.py` — seeds the local SQLite database with the demo corpus as a published library. Supports `--lang en` (default) and `--lang zh`.

The company "Stellar Systems" / "星际系统" and all data in these files are fictional. They do not contain real policies, real employee data, LAN IPs, or machine-specific paths.

## Import format

Each pair uses the format accepted by the Vue batch importer (`frontend/src/views/KnowledgeDetailView.vue`):

```text
Q1: <question>
A1: <answer>

Q2: <question>
A2: <answer>
```

Blank lines separate pairs. Both `Q1:` / `A1:` (half-width colon) and `Q1：` / `A1：` (full-width colon) work.
