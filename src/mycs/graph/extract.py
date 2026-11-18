from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from mycs.graph.model import GraphEntity, GraphEvidence, GraphRelation, KnowledgeGraph
from mycs.log import get_logger
from mycs.log_detail import log_step
from mycs.wiki.ingest import policies_from_text

logger = get_logger(__name__)

DEFAULT_EXTRACT_CHUNK_SIZE = 6000

EXTRACT_SYSTEM = (
    "你是企业知识图谱构建器。从给定文档片段抽取实体、关系、证据。"
    "只输出 JSON："
    '{"entities":[{"entity_id":"...","entity_type":"Policy|Concept|Person|Org",'
    '"name":"...","summary":"...","tags":["..."],"properties":{}}],'
    '"relations":[{"relation_id":"...","from_entity_id":"...","to_entity_id":"...",'
    '"predicate":"...","properties":{}}],'
    '"evidence":[{"evidence_id":"...","entity_id":"...","quote":"...","section_ref":""}]}'
)


class GraphExtractor(Protocol):
    def extract(
        self,
        text: str,
        *,
        document_id: str,
        title: str,
        source_uri: str,
    ) -> KnowledgeGraph: ...


class SectionGraphBuilder:
    """Structure-only graph from numbered sections (bootstrap seed; not LLM)."""

    def extract(
        self,
        text: str,
        *,
        document_id: str,
        title: str,
        source_uri: str,
    ) -> KnowledgeGraph:
        log_step(
            logger,
            "ingest_section_graph_start",
            document_id=document_id,
            title=title,
            chars=len(text),
        )
        policies = policies_from_text(text, source_uri=source_uri)
        entities: list[GraphEntity] = []
        relations: list[GraphRelation] = []
        evidence: list[GraphEvidence] = []
        topic_ids: dict[str, str] = {}

        for _pid, p in policies.items():
            body = p["body"]
            pid = f"{document_id}_{p['section'].replace('.', '_')}"
            entities.append(
                GraphEntity(
                    entity_id=pid,
                    entity_type="Policy",
                    name=p["title"],
                    summary=p["summary"],
                    tags=list(p.get("tags") or []),
                    properties={
                        "section": p["section"],
                        "body": body,
                        "policy_id": pid,
                    },
                )
            )
            ev_id = f"ev_{pid}"
            evidence.append(
                GraphEvidence(
                    evidence_id=ev_id,
                    entity_id=pid,
                    quote=(p["evidence"]["quote"]),
                    section_ref=p["section"],
                )
            )
            for tag in p.get("tags") or []:
                if tag not in topic_ids:
                    tid = f"{document_id}_topic_{tag}"
                    topic_ids[tag] = tid
                    entities.append(
                        GraphEntity(
                            entity_id=tid,
                            entity_type="Concept",
                            name=tag,
                            summary=f"Topic tag: {tag}",
                            tags=[tag],
                        )
                    )
                relations.append(
                    GraphRelation(
                        relation_id=f"rel_{pid}_{tag}",
                        from_entity_id=pid,
                        to_entity_id=topic_ids[tag],
                        predicate="tagged_with",
                    )
                )
            if re.search(r"prior approval|事先批准|advance approval", body, re.I):
                cid = f"{document_id}_concept_prior_approval"
                if cid not in {e.entity_id for e in entities}:
                    entities.append(
                        GraphEntity(
                            entity_id=cid,
                            entity_type="Concept",
                            name="prior approval",
                            summary="Requires advance / prior approval",
                            tags=["approval"],
                        )
                    )
                relations.append(
                    GraphRelation(
                        relation_id=f"rel_{pid}_approval",
                        from_entity_id=pid,
                        to_entity_id=cid,
                        predicate="requires_prior_approval",
                    )
                )

        graph = KnowledgeGraph(
            document_id=document_id,
            title=title,
            source_uri=source_uri,
            entities=entities,
            relations=relations,
            evidence=evidence,
        )
        log_step(
            logger,
            "ingest_section_graph_done",
            document_id=document_id,
            entities=len(graph.entities),
            relations=len(graph.relations),
            evidence=len(graph.evidence),
            sample_titles=[e.name[:60] for e in graph.entities[:8]],
        )
        return graph


def knowledge_graph_from_outline_roots(
    roots: list,
    *,
    document_id: str,
    title: str,
    source_uri: str,
    leaf_quotes: dict[str, str] | None = None,
) -> KnowledgeGraph:
    """Build Policy entities + evidence from compiled outline (FAQ / canonical ingest)."""
    from mycs.wiki.outline import OutlineNode

    quotes = leaf_quotes or {}
    entities: list[GraphEntity] = []
    evidence: list[GraphEvidence] = []
    for ch in roots:
        if not isinstance(ch, OutlineNode):
            continue
        for leaf in ch.children:
            if leaf.kind != "leaf":
                continue
            sec = leaf.section_ref
            pid = f"{document_id}_{sec.replace('.', '_')}"
            body = leaf.body
            entities.append(
                GraphEntity(
                    entity_id=pid,
                    entity_type="Policy",
                    name=leaf.title,
                    summary=leaf.summary or leaf.title,
                    tags=[],
                    properties={
                        "section": sec,
                        "body": body,
                        "policy_id": pid,
                    },
                )
            )
            quote = quotes.get(sec) or (body[:500] if body else "")
            evidence.append(
                GraphEvidence(
                    evidence_id=f"ev_{pid}",
                    entity_id=pid,
                    quote=quote,
                    section_ref=sec,
                )
            )
    graph = KnowledgeGraph(
        document_id=document_id,
        title=title,
        source_uri=source_uri,
        entities=entities,
        relations=[],
        evidence=evidence,
    )
    log_step(
        logger,
        "ingest_outline_graph_done",
        document_id=document_id,
        entities=len(graph.entities),
        evidence=len(graph.evidence),
    )
    return graph


class OllamaGraphExtractor:
    """LLM-driven extraction (full document or chunked)."""

    def __init__(self, llm: Any) -> None:
        self._llm = llm

    def extract(
        self,
        text: str,
        *,
        document_id: str,
        title: str,
        source_uri: str,
    ) -> KnowledgeGraph:
        import os

        chunk_size = int(os.environ.get("MYCS_GRAPH_EXTRACT_CHUNK_SIZE", str(DEFAULT_EXTRACT_CHUNK_SIZE)))
        total = len(text)
        chunk_total = max(1, (total + chunk_size - 1) // chunk_size)
        log_step(
            logger,
            "ingest_llm_graph_start",
            document_id=document_id,
            title=title,
            chars=total,
            chunk_size=chunk_size,
            chunk_total=chunk_total,
        )
        merged = KnowledgeGraph(
            document_id=document_id,
            title=title,
            source_uri=source_uri,
        )
        idx = 0
        for start in range(0, total, chunk_size):
            chunk = text[start : start + chunk_size]
            idx += 1
            end = start + len(chunk)
            log_step(
                logger,
                "ingest_llm_graph_chunk_start",
                document_id=document_id,
                chunk_index=idx,
                chunk_total=chunk_total,
                byte_range=f"{start}-{end}",
                chunk_chars=len(chunk),
                text_preview=chunk[:240].replace("\n", " "),
            )
            user = json.dumps(
                {
                    "document_id": document_id,
                    "chunk_index": idx,
                    "text": chunk,
                },
                ensure_ascii=False,
            )
            try:
                log_step(
                    logger,
                    "ingest_llm_graph_chunk_llm_call",
                    chunk_index=idx,
                    user_chars=len(user),
                )
                data = self._llm._json_chat(EXTRACT_SYSTEM, user)  # type: ignore[attr-defined]
            except Exception as exc:
                log_step(
                    logger,
                    "ingest_llm_graph_chunk_failed",
                    chunk_index=idx,
                    error=str(exc),
                )
                raise
            llm_counts = {
                "entities": len(data.get("entities") or []),
                "relations": len(data.get("relations") or []),
                "evidence": len(data.get("evidence") or []),
            }
            merge_stats = _merge_graph_payload(merged, data)
            log_step(
                logger,
                "ingest_llm_graph_chunk_done",
                chunk_index=idx,
                llm_returned=llm_counts,
                merge=merge_stats,
                graph_totals={
                    "entities": len(merged.entities),
                    "relations": len(merged.relations),
                    "evidence": len(merged.evidence),
                },
                sample_entities=[
                    {
                        "entity_id": e.get("entity_id"),
                        "name": (e.get("name") or "")[:50],
                        "entity_type": e.get("entity_type"),
                    }
                    for e in (data.get("entities") or [])[:6]
                ],
            )
        log_step(
            logger,
            "ingest_llm_graph_done",
            document_id=document_id,
            entities=len(merged.entities),
            relations=len(merged.relations),
            evidence=len(merged.evidence),
            sample_entities=[{"id": e.entity_id, "name": e.name[:50]} for e in merged.entities[:10]],
        )
        return merged


def _merge_graph_payload(graph: KnowledgeGraph, data: dict[str, Any]) -> dict[str, int]:
    seen_e = {e.entity_id for e in graph.entities}
    seen_r = {r.relation_id for r in graph.relations}
    seen_ev = {e.evidence_id for e in graph.evidence}
    stats = {
        "entities_added": 0,
        "entities_skipped": 0,
        "relations_added": 0,
        "relations_skipped": 0,
        "evidence_added": 0,
        "evidence_skipped": 0,
    }
    for raw in data.get("entities") or []:
        eid = raw.get("entity_id")
        if not eid or eid in seen_e:
            stats["entities_skipped"] += 1
            continue
        seen_e.add(eid)
        stats["entities_added"] += 1
        graph.entities.append(
            GraphEntity(
                entity_id=eid,
                entity_type=str(raw.get("entity_type") or "Concept"),
                name=str(raw.get("name") or eid),
                summary=str(raw.get("summary") or ""),
                tags=list(raw.get("tags") or []),
                properties=dict(raw.get("properties") or {}),
            )
        )
    for raw in data.get("relations") or []:
        rid = raw.get("relation_id")
        if not rid or rid in seen_r:
            stats["relations_skipped"] += 1
            continue
        seen_r.add(rid)
        stats["relations_added"] += 1
        graph.relations.append(
            GraphRelation(
                relation_id=rid,
                from_entity_id=str(raw["from_entity_id"]),
                to_entity_id=str(raw["to_entity_id"]),
                predicate=str(raw.get("predicate") or "related_to"),
                properties=dict(raw.get("properties") or {}),
            )
        )
    for raw in data.get("evidence") or []:
        evid = raw.get("evidence_id")
        if not evid or evid in seen_ev:
            stats["evidence_skipped"] += 1
            continue
        seen_ev.add(evid)
        stats["evidence_added"] += 1
        graph.evidence.append(
            GraphEvidence(
                evidence_id=evid,
                entity_id=raw.get("entity_id"),
                relation_id=raw.get("relation_id"),
                quote=str(raw.get("quote") or ""),
                section_ref=str(raw.get("section_ref") or ""),
            )
        )
    return stats


def ingest_txt_file(
    path: Path,
    *,
    document_id: str | None = None,
    json_out: Path | None = None,
    use_section_builder: bool = False,
    enrich_graph: bool = False,
) -> KnowledgeGraph:
    import os

    text = path.read_text(encoding="utf-8")
    doc_id = document_id or path.stem
    source_uri = f"file://{path.resolve()}"
    enrich_graph = enrich_graph or os.environ.get("MYCS_INGEST_ENRICH_GRAPH", "").strip() in (
        "1",
        "true",
        "yes",
    )
    if enrich_graph:
        mode = "llm_enrich_graph"
    elif use_section_builder:
        mode = "section_builder_only"
    else:
        mode = "toc_draft_then_section_graph"
    from mycs.document_display import infer_handbook_display_title

    handbook_title = infer_handbook_display_title(
        document_id=doc_id,
        path=path,
        text=text,
        stored_title=path.name,
    )
    log_step(
        logger,
        "ingest_txt_file_start",
        path=str(path),
        document_id=doc_id,
        handbook_title=handbook_title,
        chars=len(text),
        mode=mode,
    )
    from mycs.db.connection import connect, get_db_path
    from mycs.graph.persist import export_graph_json, persist_graph
    from mycs.wiki.toc_persist import ingest_document_toc_draft, publish_mount

    if enrich_graph:
        from mycs.llm.factory import create_llm

        log_step(logger, "ingest_llm_graph_create_extractor", document_id=doc_id)
        extractor: GraphExtractor = OllamaGraphExtractor(create_llm())
        graph = extractor.extract(
            text,
            document_id=doc_id,
            title=handbook_title,
            source_uri=source_uri,
        )
        log_step(
            logger,
            "ingest_llm_graph_persist_sqlite",
            document_id=doc_id,
            entities=len(graph.entities),
            relations=len(graph.relations),
        )
        persist_graph(graph, get_db_path())
        log_step(logger, "ingest_llm_graph_persist_done", document_id=doc_id)
    elif use_section_builder:
        extractor = SectionGraphBuilder()
        graph = extractor.extract(
            text,
            document_id=doc_id,
            title=handbook_title,
            source_uri=source_uri,
        )
        persist_graph(graph, get_db_path())
    else:
        conn = connect(get_db_path())
        try:
            from mycs.log_detail import log_step
            log_step(
                logger,
                "ingest_toc_draft_start",
                document_id=doc_id,
                chars=len(text),
            )
            meta = ingest_document_toc_draft(
                conn,
                text,
                document_id=doc_id,
                title=handbook_title,
                source_uri=source_uri,
            )
            log_step(
                logger,
                "ingest_toc_draft_done",
                document_id=doc_id,
                mount_id=meta.get("mount_id"),
                nodes=meta.get("nodes"),
                entities=meta.get("entities"),
            )
            import os

            if os.environ.get("MYCS_WIKI_AUTO_PUBLISH", "").strip() in ("1", "true", "yes"):
                pub = publish_mount(conn, meta["mount_id"])
                log_step(logger, "ingest_auto_publish", mount_id=meta["mount_id"], result=pub)
            conn.commit()
        finally:
            conn.close()
        log_step(logger, "ingest_section_graph_after_toc", document_id=doc_id)
        extractor = SectionGraphBuilder()
        graph = extractor.extract(
            text,
            document_id=doc_id,
            title=handbook_title,
            source_uri=source_uri,
        )

    out = json_out or Path(__file__).resolve().parents[3] / "data" / "kg" / f"{doc_id}.json"
    export_graph_json(graph, out)
    log_step(
        logger,
        "ingest_txt_file_done",
        document_id=doc_id,
        json_out=str(out),
        entities=len(graph.entities),
        relations=len(graph.relations),
    )
    return graph
