"""Knowledge base (flat FAQ) — library + Q&A items."""

KB_DDL = """
CREATE TABLE IF NOT EXISTS kb_library (
    document_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_kb_library_title ON kb_library(title);

CREATE TABLE IF NOT EXISTS kb_faq_item (
    item_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES kb_library(document_id) ON DELETE CASCADE,
    sort_key INTEGER NOT NULL DEFAULT 0,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    section_ref TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft',
    disabled INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_kb_faq_doc ON kb_faq_item(document_id, sort_key);
CREATE INDEX IF NOT EXISTS idx_kb_faq_status ON kb_faq_item(document_id, status);
"""