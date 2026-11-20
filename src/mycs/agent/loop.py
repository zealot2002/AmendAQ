from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from dataclasses import replace
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
from mycs.planning.question_split import resolve_sub_questions
from mycs.skills.loader import evidence_text, load_skills, match_skills
from mycs.tools.registry import ToolRegistry
from mycs.ui.trace_kinds import resolve_step_kind
from mycs.ui.trace_narrative import enrich_display
from mycs.ui.trace_llm_capture import begin_llm_capture, take_llm_captures
from mycs.verifier import Verifier

OnTraceEvent = Callable[[TraceEvent], None] | None

logger = get_logger(__name__)

MAX_TOOL_ROUNDS = int(os.environ.get("MYCS_MAX_TOOL_ROUNDS", "128"))


def _by_section_requirements(
    document_id: str | None, section_refs: list[str]
) -> list[KnowledgeRequirement]:
    doc = document_id or ""
    out: list[KnowledgeRequirement] = []
    for ref in section_refs:
        if not ref:
            continue
        out.append(
            KnowledgeRequirement(
                field="graph.entity.by_section",
                source=KnowledgeSource.GRAPH,
                params={"section": ref, "document_id": doc},
            )
        )
    return out

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
        run_started = time.perf_counter()
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
        progress("正在判断是否需要拆分多个子问题…")
        sub_questions, split_meta = resolve_sub_questions(self._llm, question)
        if split_meta.get("llm_invoked"):
            pending = take_llm_captures()
            if pending:
                split_meta["llm_calls"] = pending
        emit(
            "question_split",
            {
                **split_meta,
                "original_question": question,
            },
        )

        multi_sub = (
            len(sub_questions) > 1
            and understood.intent == "graph_qa"
            and bool(understood.graph_document_id)
        )
        if multi_sub:
            from mycs.answer_format import answer_for_user, split_answer_sections

            user_parts: list[str] = []
            all_checks: list[dict[str, Any]] = []
            verify_ok = True
            for idx, sq in enumerate(sub_questions):
                progress(f"正在处理第 {idx + 1}/{len(sub_questions)} 个子问题…")
                emit(
                    "sub_question",
                    {
                        "index": idx + 1,
                        "total": len(sub_questions),
                        "text": sq,
                        "llm_invoked": False,
                    },
                )
                sub_u = replace(understood, raw_question=sq)
                sub_ctx: dict[str, Any] = {
                    "raw_question": sq,
                    "graph_document_id": understood.graph_document_id,
                    "graph_document_title": graph_doc_title,
                }
                answer, _claims, verify, _calls = self._run_retrieval_and_compose(
                    sub_u,
                    sub_ctx,
                    emit=emit,
                    progress=progress,
                )
                user_parts.append((answer_for_user(answer) or answer).strip())
                verify_ok = verify_ok and verify.ok
                all_checks.extend(verify.checks)
            user_answer = "\n\n".join(p for p in user_parts if p)
            verify = VerifyResult(
                ok=verify_ok,
                checks=all_checks,
                message="multi_sub_question verify",
            )
            emit(
                "answer",
                {
                    "text": user_answer,
                    "claims": {"sub_question_count": len(sub_questions)},
                    "multi_sub": True,
                },
            )
            elapsed = round(time.perf_counter() - run_started, 1)
            log_step(
                logger,
                "agent_run_done",
                verify_ok=verify.ok,
                answer_preview=user_answer[:200],
                answer_full_len=len(user_answer),
                multi_sub=len(sub_questions),
                elapsed_seconds=elapsed,
            )
            return AgentRunResult(
                question=question,
                case_id=understood.case_id,
                answer=user_answer,
                trace=trace,
                verify=verify,
                elapsed_seconds=elapsed,
            )

        active_q = sub_questions[0] if sub_questions else question
        understood = replace(understood, raw_question=active_q)
        context: dict[str, Any] = {
            "raw_question": active_q,
            "graph_document_id": understood.graph_document_id,
            "graph_document_title": graph_doc_title,
        }

        answer, claims, verify, compose_llm_calls = self._run_retrieval_and_compose(
            understood,
            context,
            emit=emit,
            progress=progress,
        )
        from mycs.answer_format import answer_for_user, split_answer_sections

        progress("正在核对回答是否有据…")
        _, evidence = split_answer_sections(answer)
        user_answer = answer_for_user(answer)
        if evidence:
            logger.info(
                "joyjoy: answer_evidence (not shown to user unless MYCS_CHAT_SHOW_EVIDENCE=1)\n%s",
                evidence,
            )
        emit(
            "answer",
            {
                "text": user_answer,
                "claims": claims,
                "compose_context_keys": sorted(context.keys()),
                "wiki_leaves": context.get("wiki_leaves"),
                "graph_entities": context.get("graph_entities") or context.get("graph_entity"),
                "llm_calls": compose_llm_calls,
            },
        )
        elapsed = round(time.perf_counter() - run_started, 1)
        log_step(
            logger,
            "agent_run_done",
            verify_ok=verify.ok,
            answer_preview=user_answer[:200],
            answer_full_len=len(answer),
            has_evidence=bool(evidence),
            elapsed_seconds=elapsed,
        )
        return AgentRunResult(
            question=question,
            case_id=understood.case_id,
            answer=user_answer,
            trace=trace,
            verify=verify,
            elapsed_seconds=elapsed,
        )

    def _run_retrieval_and_compose(
        self,
        understood: Any,
        context: dict[str, Any],
        *,
        emit: Callable[[str, dict[str, Any]], None],
        progress: Callable[[str], None],
    ) -> tuple[str, dict[str, Any], VerifyResult, list]:
        plan_context: dict[str, object] = {}
        valid_sections: set[str] = set()
        comprehensive_leaf_refs: list[str] = []
        if understood.intent == "graph_qa" and understood.graph_document_id:
            doc = understood.graph_document_id
            from mycs.agent.toc_recall_phase import run_graph_qa_catalog_recall

            svc = KnowledgeService()
            try:
                valid_sections, comprehensive_leaf_refs = run_graph_qa_catalog_recall(
                    llm=self._llm,
                    svc=svc,
                    document_id=doc,
                    question=understood.raw_question,
                    plan_context=plan_context,
                    context=context,
                    emit=emit,
                    progress=progress,
                )
            finally:
                svc.close()

        dropped_guard = 0
        sibling_added = 0
        composite_added = 0
        composite_leaf_refs: list[str] = []
        plan_from_comprehensive = bool(comprehensive_leaf_refs)
        if comprehensive_leaf_refs:
            progress("正在按已选叶节点加载条款正文…")
            requirements = _by_section_requirements(
                understood.graph_document_id,
                comprehensive_leaf_refs,
            )
            before_count = len(requirements)
        else:
            progress("正在拟定检索计划（需要查哪些条款）…")
            requirements = self._llm.plan(understood, plan_context)
            before_count = len(requirements)
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
                    "sibling_sections_added": sibling_added,
                    "composite_sections_added": composite_added,
                    "composite_leaf_refs": composite_leaf_refs,
                    "scope_section_refs": [],
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
                "plan_source": (
                    str(plan_context.get("recall_source") or "comprehensive_toc")
                    if plan_from_comprehensive
                    else "llm_plan"
                ),
                "llm_invoked": not plan_from_comprehensive,
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
                req.result = result
                req.satisfied = True
                self._resolver.after_tool(req, tool_name, result, context)
                summary = summarize_tool_result(tool_name, result)
                log_step(logger, "agent_tool_result", gap=req.field, api=tool_name, summary=summary)
                emit(
                    "tool",
                    {
                        "gap": req.field,
                        "source": req.source.value,
                        "api": tool_name,
                        "params": params,
                        "result": summary,
                        "result_raw": result,
                    },
                )

        progress("正在根据检索结果撰写回答…")
        clauses = evidence_text(context)
        active_skills = match_skills(load_skills(), understood.raw_question, clauses)
        if active_skills:
            context["skill_instructions"] = "\n\n".join(
                f"## {skill.name}\n{skill.instructions}".strip() for skill in active_skills
            )
            logger.info(
                "joyjoy: answer skills enabled %s",
                [skill.name for skill in active_skills],
            )
            emit(
                "skill",
                {
                    "skills": [
                        {"name": skill.name, "description": skill.description, "revise": skill.revise}
                        for skill in active_skills
                    ],
                    "llm_invoked": False,
                },
            )
        log_step(
            logger,
            "agent_compose_start",
            wiki_leaves=len(context.get("wiki_leaves") or []),
            graph_entities=len(context.get("graph_entities") or []),
            skills=[skill.name for skill in active_skills],
        )
        answer, claims = self._llm.compose_answer(understood, context)
        compose_llm_calls = take_llm_captures()
        revise_skills = [skill for skill in active_skills if skill.revise]
        if revise_skills and hasattr(self._llm, "revise_answer"):
            progress("正在按已启用技能核对结论…")
            revised = self._llm.revise_answer(
                question=understood.raw_question,
                draft=answer,
                evidence_text=clauses,
                skill_instructions=str(context.get("skill_instructions") or ""),
            )
            revise_calls = take_llm_captures()
            compose_llm_calls = compose_llm_calls + revise_calls
            changed = revised.strip() != answer.strip()
            logger.info(
                "joyjoy: skill revise skills=%s changed=%s",
                [skill.name for skill in revise_skills],
                changed,
            )
            emit(
                "skill_revise",
                {
                    "skills": [skill.name for skill in revise_skills],
                    "changed": changed,
                    "llm_invoked": True,
                    "llm_calls": revise_calls,
                },
            )
            if revised.strip():
                answer = revised.strip()
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
        return answer, claims, verify, compose_llm_calls

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
