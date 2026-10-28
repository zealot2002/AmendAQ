from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class KnowledgeSource(str, Enum):
    WIKI = "wiki"
    DOMAIN_API = "domain_api"
    GRAPH = "graph"


@dataclass
class KnowledgeRequirement:
    """Structured knowledge gap — not a search keyword list."""

    field: str
    source: KnowledgeSource
    params: dict[str, Any] = field(default_factory=dict)
    satisfied: bool = False
    result: Any | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["source"] = self.source.value
        return d


@dataclass
class UnderstandResult:
    case_id: str | None
    intent: str
    raw_question: str
    wiki_topics: list[str] = field(default_factory=list)
    graph_document_id: str | None = None


@dataclass
class TraceEvent:
    step: str
    payload: dict[str, Any]
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VerifyResult:
    ok: bool
    checks: list[dict[str, Any]]
    message: str


@dataclass
class AgentRunResult:
    question: str
    case_id: str | None
    answer: str
    trace: list[TraceEvent]
    verify: VerifyResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "case_id": self.case_id,
            "answer": self.answer,
            "verify": asdict(self.verify),
            "trace": [e.to_dict() for e in self.trace],
        }
