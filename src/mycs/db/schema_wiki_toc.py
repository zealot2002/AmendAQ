"""Enterprise Wiki TOC (multi-document tree)."""

WIKI_TOC_DDL = """
CREATE TABLE IF NOT EXISTS wiki_toc_node (
    node_id TEXT PRIMARY KEY,
    parent_id TEXT,
    mount_id TEXT NOT NULL,
    document_id TEXT,
    kind TEXT NOT NULL,
    section_ref TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    sort_key INTEGER NOT NULL DEFAULT 0,
    depth INTEGER NOT NULL DEFAULT 0,
    entity_id TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    disabled INTEGER NOT NULL DEFAULT 0,
    content_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (parent_id) REFERENCES wiki_toc_node(node_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_wiki_toc_mount ON wiki_toc_node(mount_id, status);
CREATE INDEX IF NOT EXISTS idx_wiki_toc_parent ON wiki_toc_node(parent_id);
CREATE INDEX IF NOT EXISTS idx_wiki_toc_section ON wiki_toc_node(document_id, section_ref, status);

CREATE TABLE IF NOT EXISTS wiki_document_mount (
    mount_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    parent_node_id TEXT NOT NULL,
    display_title TEXT NOT NULL,
    sort_key INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_wiki_mount_doc ON wiki_document_mount(document_id);

CREATE TABLE IF NOT EXISTS wiki_publish_audit (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    mount_id TEXT NOT NULL,
    action TEXT NOT NULL,
    node_count INTEGER NOT NULL DEFAULT 0,
    actor TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
"""
