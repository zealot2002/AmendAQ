"""Knowledge graph relational model (SQLite)."""

KG_DDL = """
CREATE TABLE IF NOT EXISTS kg_document (
    document_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source_uri TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    catalog_mode TEXT NOT NULL DEFAULT 'hierarchical'
);

CREATE TABLE IF NOT EXISTS kg_entity (
    entity_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES kg_document(document_id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,
    name TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    properties_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_kg_entity_type ON kg_entity(entity_type);
CREATE INDEX IF NOT EXISTS idx_kg_entity_name ON kg_entity(name);
CREATE INDEX IF NOT EXISTS idx_kg_entity_doc ON kg_entity(document_id);

CREATE TABLE IF NOT EXISTS kg_entity_tag (
    entity_id TEXT NOT NULL REFERENCES kg_entity(entity_id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    PRIMARY KEY (entity_id, tag)
);

CREATE INDEX IF NOT EXISTS idx_kg_entity_tag ON kg_entity_tag(tag);

CREATE TABLE IF NOT EXISTS kg_relation (
    relation_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES kg_document(document_id) ON DELETE CASCADE,
    from_entity_id TEXT NOT NULL REFERENCES kg_entity(entity_id) ON DELETE CASCADE,
    to_entity_id TEXT NOT NULL REFERENCES kg_entity(entity_id) ON DELETE CASCADE,
    predicate TEXT NOT NULL,
    properties_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_kg_rel_from ON kg_relation(from_entity_id);
CREATE INDEX IF NOT EXISTS idx_kg_rel_pred ON kg_relation(predicate);

CREATE TABLE IF NOT EXISTS kg_evidence (
    evidence_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL REFERENCES kg_document(document_id) ON DELETE CASCADE,
    entity_id TEXT REFERENCES kg_entity(entity_id) ON DELETE SET NULL,
    relation_id TEXT REFERENCES kg_relation(relation_id) ON DELETE SET NULL,
    quote TEXT NOT NULL,
    section_ref TEXT NOT NULL DEFAULT '',
    source_uri TEXT NOT NULL
);
"""

KG_SCHEMA_FOR_LLM = """
Tables (read-only SELECT):
- kg_document(document_id, title, source_uri, ingested_at, catalog_mode)
- kg_entity(entity_id, document_id, entity_type, name, summary, properties_json)
- kg_entity_tag(entity_id, tag)
- kg_relation(relation_id, document_id, from_entity_id, to_entity_id, predicate, properties_json)
- kg_evidence(evidence_id, document_id, entity_id, relation_id, quote, section_ref, source_uri)

Join tags: kg_entity e JOIN kg_entity_tag t ON e.entity_id = t.entity_id WHERE t.tag = 'overtime'
Always LIMIT <= 20. Only SELECT statements.
"""
