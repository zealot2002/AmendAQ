from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphEvidence:
    evidence_id: str
    quote: str
    section_ref: str = ""
    entity_id: str | None = None
    relation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "entity_id": self.entity_id,
            "relation_id": self.relation_id,
            "quote": self.quote,
            "section_ref": self.section_ref,
        }


@dataclass
class GraphEntity:
    entity_id: str
    entity_type: str
    name: str
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "name": self.name,
            "summary": self.summary,
            "tags": self.tags,
            "properties": self.properties,
        }


@dataclass
class GraphRelation:
    relation_id: str
    from_entity_id: str
    to_entity_id: str
    predicate: str
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation_id": self.relation_id,
            "from_entity_id": self.from_entity_id,
            "to_entity_id": self.to_entity_id,
            "predicate": self.predicate,
            "properties": self.properties,
        }


@dataclass
class KnowledgeGraph:
    document_id: str
    title: str
    source_uri: str
    entities: list[GraphEntity] = field(default_factory=list)
    relations: list[GraphRelation] = field(default_factory=list)
    evidence: list[GraphEvidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "title": self.title,
            "source_uri": self.source_uri,
            "entities": [e.to_dict() for e in self.entities],
            "relations": [r.to_dict() for r in self.relations],
            "evidence": [ev.to_dict() for ev in self.evidence],
        }
