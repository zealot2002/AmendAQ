from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from mycs.knowledge.service import KnowledgeService
from mycs.llm.base import AgentLLM
from mycs.llm.factory import create_llm
from mycs.log import get_logger
from mycs.log_detail import log_step, summarize_tool_result
from mycs.models import AgentRunResult, KnowledgeRequirement, KnowledgeSource, TraceEvent, VerifyResult
from mycs.planning.plan_schema import apply_toc_section_whitelist
from mycs.planning.resolver import GapResolver
from mycs.planning.query_intent import is_whole_document_query, search_keywords_for
from mycs.planning.toc_batch_select import run_toc_batch_chapter_select
from mycs.planning.toc_drill import run_toc_drill
from mycs.tools.registry import ToolRegistry
from mycs.ui.trace_kinds import resolve_step_kind
from mycs.ui.trace_narrative import enrich_display
from mycs.ui.trace_llm_capture import begin_llm_capture, take_llm_captures
from mycs.verifier import Verifier

OnTraceEvent = Callable[[TraceEvent], None] | None

logger = get_logger(__name__)

MAX_TOOL_ROUNDS = 16

_GAP_ORDER = {
    "wiki.toc.branch": 0,
    "wiki.toc.leaves": 1,
    "graph.entity.search": 2,
    "graph.entity.by_section": 3,
    "graph.entity.catalog_match": 4,
    "graph.read.query": 5,
    "graph.entity.evidence": 6,
    "graph.relation.neighbors": 7,
}


def _sort_gaps(reqs: list[KnowledgeRequirement]) -> list[KnowledgeRequirement]:
    return sorted(reqs, key=lambda r: (_GAP_ORDER.get(r.field, 50), r.field))


class AgentLoop:
    def __init__(
        self,
        tools: ToolRegistry | None = None,
        llm: AgentLLM | None = None,
        verifier: Verifier | None = None,
        resolver: GapResolver | None = None,
    ) -> None:
        self._tools = tools or ToolRegistry()
        self._llm = llm or create_llm()
        self._verifier = verifier or Verifier()
        self._resolver = resolver or GapResolver()

    def run(
        self,
        question: str,
        case_id: str | None = None,
        *,
        on_event: OnTraceEvent = None,
    ) -> AgentRunResult:
        trace: list[TraceEvent] = []
        begin_llm_capture()

        def progress(label: str) -> None:
            if on_event:
                on_event(TraceEvent(step="progress", payload={"label": label}))

        def emit(step: str, payload: dict[str, Any]) -> None:
            body = dict(payload)
            if "llm_calls" not in body:
                kind, _ = resolve_step_kind(step, body)
                if kind == "llm":
                    pending = take_llm_captures()
                    if pending:
                        body["llm_calls"] = pending
            rich = enrich_display(step, body, question=question)
            ev = TraceEvent(step=step, payload=rich)
            trace.append(ev)
            if on_event:
                on_event(ev)

        log_step(logger, "agent_run_start", question=question[:400], case_id=case_id)
        progress("正在理解您的问题…")
        understood = self._llm.understand(question, case_id)
        graph_doc_title = ""
        if understood.graph_document_id:
            _title_svc = KnowledgeService()
            try:
                graph_doc_title = _title_svc.document_display_title(
                    document_id=understood.graph_document_id
                )
            finally:
                _title_svc.close()
        emit(
            "understand",
            {
                "case_id": understood.case_id,
                "intent": understood.intent,
                "wiki_topics": understood.wiki_topics,
                "graph_document_id": understood.graph_document_id,
                "graph_document_title": graph_doc_title,
            },
        )
        context: dict[str, Any] = {
            "raw_question": understood.raw_question,
            "graph_document_id": understood.graph_document_id,
            "graph_document_title": graph_doc_title,
        }

        plan_context: dict[str, object] = {}
        valid_sections: set[str] = set()
        if understood.intent == "graph_qa" and understood.graph_document_id:
            doc = understood.graph_document_id
            progress("正在对照知识目录定位相关章节…")
            svc = KnowledgeService()
            try:
                drill = run_toc_drill(
                    llm=self._llm,
                    svc=svc,
                    document_id=doc,
                    question=understood.raw_question,
                )

                for drill_ev in drill.trace_events:
                    emit("toc_drill", drill_ev)
                plan_context["wiki_drill_path"] = [
                    {
                        "section_ref": p.get("section_ref"),
                        "title": p.get("title"),
                        "node_id": p.get("node_id"),
                    }
                    for p in drill.path
                ]
                if drill.scope_section_prefix:
                    plan_context["wiki_scope_section_prefix"] = drill.scope_section_prefix

                whole_doc = is_whole_document_query(understood.raw_question)
                use_batch_catalog = whole_doc or drill.reason in (
                    "whole_document_query_skip_drill",
                    "no_mount",
                    "no_children",
                )

                if drill.scope_node_id and not whole_doc and not use_batch_catalog:
                    branch = self._tools.call(
                        "wiki_resolve_branch",
                        node_id=drill.scope_node_id,
                        document_id=doc,
                    )
                    req = KnowledgeRequirement(
                        field="wiki.toc.branch",
                        source=KnowledgeSource.WIKI,
                        params={"node_id": drill.scope_node_id, "document_id": doc},
                    )
                    self._resolver.after_tool(req, "wiki_resolve_branch", branch, context)
                    emit(
                        "tool",
                        {
                            "gap": "wiki.toc.branch",
                            "source": "wiki",
                            "api": "wiki_resolve_branch",
                            "params": {"node_id": drill.scope_node_id, "document_id": doc},
                            "result": summarize_tool_result("wiki_resolve_branch", branch),
                            "result_raw": branch,
                        },
                    )

                if use_batch_catalog:
                    progress("正在分批浏览手册章节目录（可继续索要后续批次）…")
                    batch_res = run_toc_batch_chapter_select(
                        llm=self._llm,
                        svc=svc,
                        document_id=doc,
                        question=understood.raw_question,
                    )
                    for batch_row in batch_res.batch_log:
                        emit("toc_catalog_batch", batch_row)
                    plan_context["wiki_selected_chapters"] = batch_res.selected_section_refs
                    batch_total = max(
                        1,
                        (batch_res.total_chapters + batch_res.batch_size - 1)
                        // batch_res.batch_size,
                    )
                    plan_context["catalog_note"] = (
                        f"手册共 {batch_res.total_chapters} 章，已浏览 "
                        f"{batch_res.batches_shown}/{batch_total} 批，"
                        f"选中 {len(batch_res.selected_section_refs)} 章用于检索。"
                    )
                    progress("正在加载选中章节下的条款摘要…")
                    outline = (
                        svc.wiki_outline_for_chapters(
                            document_id=doc,
                            chapter_section_refs=batch_res.selected_section_refs,
                            max_nodes=80,
                        ).get("nodes")
                        or []
                    )
                    scoped = bool(batch_res.selected_section_refs)
                    outline_source = "chapter_filter"
                else:
                    progress("正在加载该范围内的目录摘要…")
                    toc = self._tools.call("wiki_get_toc_outline", document_id=doc, max_nodes=200)
                    emit(
                        "tool",
                        {
                            "gap": "wiki.toc.outline",
                            "source": "wiki",
                            "api": "wiki_get_toc_outline",
                            "params": {"document_id": doc, "max_nodes": 200},
                            "result": summarize_tool_result("wiki_get_toc_outline", toc),
                            "result_raw": toc,
                        },
                    )
                    outline = toc.get("nodes") or []
                    prefix = drill.scope_section_prefix or ""
                    outline_source = "tool_outline"
                    if prefix:
                        pref = prefix.rstrip(".")
                        outline = [
                            n
                            for n in outline
                            if str(n.get("section_ref") or "") == pref
                            or str(n.get("section_ref") or "").startswith(f"{pref}.")
                        ]
                        outline_source = "local_filter"
                    scoped = bool(prefix)

                plan_context["wiki_toc_outline"] = outline
                context["wiki_toc_outline"] = outline
                context["wiki_drill_path"] = plan_context.get("wiki_drill_path")
                valid_sections = {
                    str(n["section_ref"])
                    for n in outline
                    if n.get("kind") == "leaf" and n.get("section_ref")
                }
                doc_title = svc.document_display_title(document_id=doc)
                emit(
                    "outline",
                    {
                        "outline_count": len(outline),
                        "document_id": doc,
                        "document_title": doc_title,
                        "scoped": scoped,
                        "selected_chapters": plan_context.get("wiki_selected_chapters") or [],
                        "source": outline_source,
                        "valid_leaf_count": len(valid_sections),
                        "outline_nodes": outline,
                        "catalog_note": plan_context.get("catalog_note"),
                    },
                )
                log_step(
                    logger,
                    "agent_toc_ready",
                    document_id=doc,
                    outline_count=len(outline),
                    valid_leaf_sections=sorted(valid_sections)[:20],
                    drill_path=plan_context.get("wiki_drill_path"),
                    selected_chapters=plan_context.get("wiki_selected_chapters"),
                )
            finally:
                svc.close()

        progress("正在拟定检索计划（需要查哪些条款）…")
        requirements = self._llm.plan(understood, plan_context)
        before_count = len(requirements)
        dropped_guard = 0
        if valid_sections:
            requirements = apply_toc_section_whitelist(requirements, valid_sections)
            dropped_guard = max(0, before_count - len(requirements))
        requirements = _sort_gaps(requirements)
        if understood.intent == "graph_qa" and before_count:
            emit(
                "plan_guard",
                {
                    "valid_leaf_sections": sorted(valid_sections)[:24],
                    "requirements_before": before_count,
                    "requirements_after": len(requirements),
                    "dropped_by_whitelist": dropped_guard,
                },
            )
        emit(
            "plan",
            {
                "knowledge_requirements": [r.to_dict() for r in requirements],
                "plan_context": {
                    k: v
                    for k, v in plan_context.items()
                    if k != "wiki_toc_outline"
                }
                | {
                    "wiki_toc_outline_count": len(plan_context.get("wiki_toc_outline") or []),
                    "wiki_toc_outline": plan_context.get("wiki_toc_outline") or [],
                },
            },
        )
        log_step(
            logger,
            "agent_plan_ready",
            requirement_count=len(requirements),
            requirements=[r.to_dict() for r in requirements],
        )

        rounds = 0
        while requirements and rounds < MAX_TOOL_ROUNDS:
            rounds += 1
            pending = _sort_gaps([r for r in requirements if not r.satisfied])
            if not pending:
                break
            log_step(logger, "agent_tool_round", round=rounds, pending=[r.field for r in pending])
            for req in pending:
                tool_name, params = self._resolver.resolve(req, context)
                progress(f"正在查阅：{req.field}…")
                log_step(logger, "agent_tool_call", gap=req.field, api=tool_name, params=params)
                result = self._tools.call(tool_name, **params)
                retried_unscoped = False
                if (
                    tool_name == "kg_search_entities"
                    and int(result.get("count") or 0) == 0
                    and (params.get("entity_id_in") or params.get("section_prefix"))
                ):
                    broad = {
                        k: v
                        for k, v in params.items()
                        if k not in ("entity_id_in", "section_prefix")
                    }
                    broad["query"] = search_keywords_for(context.get("raw_question", ""))
                    broad["limit"] = max(int(broad.get("limit") or 8), 15)
                    log_step(
                        logger,
                        "agent_search_retry_unscoped",
                        gap=req.field,
                        query=broad.get("query"),
                    )
                    result = self._tools.call(tool_name, **broad)
                    params = broad
                    retried_unscoped = True
                req.result = result
                req.satisfied = True
                self._resolver.after_tool(req, tool_name, result, context)
                summary = summarize_tool_result(tool_name, result)
                log_step(logger, "agent_tool_result", gap=req.field, api=tool_name, summary=summary)
                tool_payload: dict[str, Any] = {
                    "gap": req.field,
                    "source": req.source.value,
                    "api": tool_name,
                    "params": params,
                    "result": summary,
                    "result_raw": result,
                }
                if retried_unscoped:
                    tool_payload["retried_unscoped"] = True
                emit("tool", tool_payload)

        progress("正在根据检索结果撰写回答…")
        log_step(
            logger,
            "agent_compose_start",
            wiki_leaves=len(context.get("wiki_leaves") or []),
            graph_entities=len(context.get("graph_entities") or []),
        )
        answer, claims = self._llm.compose_answer(understood, context)
        compose_llm_calls = take_llm_captures()
        progress("正在核对回答是否有据…")
        verify = self._run_verify(understood, context, claims, answer=answer)
        emit(
            "verify",
            {
                "ok": verify.ok,
                "checks": verify.checks,
                "message": verify.message,
                "verify_raw": {
                    "ok": verify.ok,
                    "checks": verify.checks,
                    "message": verify.message,
                },
            },
        )
        emit(
            "answer",
            {
                "text": answer,
                "claims": claims,
                "compose_context_keys": sorted(context.keys()),
                "wiki_leaves": context.get("wiki_leaves"),
                "graph_entities": context.get("graph_entities") or context.get("graph_entity"),
                "llm_calls": compose_llm_calls,
            },
        )
        log_step(
            logger,
            "agent_run_done",
            verify_ok=verify.ok,
            answer_preview=answer[:200],
        )

        return AgentRunResult(
            question=question,
            case_id=understood.case_id,
            answer=answer,
            trace=trace,
            verify=verify,
        )

    def _run_verify(
        self,
        understood: Any,
        context: dict[str, Any],
        claims: dict[str, Any],
        *,
        answer: str = "",
    ) -> VerifyResult:
        if understood.intent == "procedure_online_only":
            proc = context.get("procedure", {})
            ok = proc.get("online_available") == claims.get("online_available")
            return VerifyResult(
                ok=ok,
                checks=[{"name": "online_flag_consistent", "ok": ok}],
                message="ok" if ok else "online flag mismatch",
            )

        if understood.intent == "graph_qa":
            entities = context.get("graph_entities") or []
            leaves = context.get("wiki_leaves") or []
            return self._verifier.verify_graph_answer(
                question=understood.raw_question,
                answer=answer,
                entities=entities,
                wiki_leaves=leaves,
                search_top_score=float(claims.get("search_top_score") or 0),
            )

        if understood.intent == "handbook_qa":
            policy = dict(context.get("handbook_policy") or {})
            ev = context.get("handbook_evidence") or policy.get("evidence") or {}
            snippet = str(claims.get("evidence_snippet") or ev.get("quote") or "")
            title = str(claims.get("policy_title") or policy.get("title") or "")
            return self._verifier.verify_handbook_answer(
                answer=answer,
                policy_record=policy,
                evidence_snippet=snippet,
                policy_title=title,
            )

        case = context.get("case", {})
        policy = context.get("policy", {})
        return self._verifier.verify_case_answer(
            claimed_status_label=claims["claimed_status_label"],
            case_record=case,
            policy_record=policy,
            claimed_within_limit=claims["claimed_within_limit"],
            submitted_at=claims["submitted_at"],
        )

    @staticmethod
    def save_trace(result: AgentRunResult, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        from datetime import datetime, timezone

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        case_part = result.case_id or "no-case"
        path = directory / f"trace-{case_part}-{stamp}.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info("trace written to %s", path)
        return path
