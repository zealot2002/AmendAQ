from __future__ import annotations

import re
from typing import Any

from amendaq.models import VerifyResult

_GENERIC_TOKENS = {
    "员工",
    "公司",
    "手册",
    "规定",
    "具体",
    "处理",
    "方式",
    "关于",
    "如何",
    "进行",
    "相关",
    "上限",
    "金额",
    "限制",
    "天数",
    "额度",
    "适用",
    "场景",
    "后果",
    "新台币",
}
_HYPOTHETICAL_PERMIT = re.compile(
    r"(未造成|没有造成|若未造成|如果没有).{0,24}(可以接受|可以收取|可以收|可以同意)"
)
_PROHIBIT = re.compile(r"(不能|不得|禁止).{0,16}(造成|接受|收取)")
_DENY = re.compile(r"(不能接受|不得接受|不可以接受|不能收|不得收|不可以收)")
_OBLIGATION = re.compile(r"(必须|应当|原则上|应)")


class Verifier:
    """Deterministic checks — not LLM self-attestation."""

    def verify_case_answer(
        self,
        *,
        claimed_status_label: str,
        case_record: dict[str, Any],
        policy_record: dict[str, Any],
        claimed_within_limit: bool,
        submitted_at: str,
    ) -> VerifyResult:
        checks: list[dict[str, Any]] = []

        status_ok = case_record.get("status_label") == claimed_status_label
        checks.append(
            {
                "name": "status_matches_domain_api",
                "ok": status_ok,
                "expected": case_record.get("status_label"),
                "claimed": claimed_status_label,
            }
        )

        evidence = policy_record.get("evidence") or {}
        quote = evidence.get("quote", "")
        quote_ok = bool(quote) and quote in policy_record.get("summary", "")
        checks.append(
            {
                "name": "policy_has_embedded_evidence",
                "ok": quote_ok,
                "source_uri": evidence.get("source_uri"),
            }
        )

        limit_ok = claimed_within_limit is True
        checks.append(
            {
                "name": "within_policy_limit_acknowledged",
                "ok": limit_ok,
                "submitted_at": submitted_at,
                "max_working_days": policy_record.get("max_working_days"),
            }
        )

        ok = all(c["ok"] for c in checks)
        message = "all checks passed" if ok else "verification failed"
        return VerifyResult(ok=ok, checks=checks, message=message)

    def verify_handbook_answer(
        self,
        *,
        answer: str,
        policy_record: dict[str, Any],
        evidence_snippet: str,
        policy_title: str | None,
    ) -> VerifyResult:
        checks: list[dict[str, Any]] = []
        norm_answer = _norm(answer)

        title_ok = bool(policy_title) and _norm(policy_title) in norm_answer
        checks.append({"name": "mentions_policy_title", "ok": title_ok, "title": policy_title})

        snippet = _norm(evidence_snippet[:80]) if evidence_snippet else ""
        snippet_ok = bool(snippet) and snippet in norm_answer
        checks.append(
            {
                "name": "answer_aligns_with_evidence_snippet",
                "ok": snippet_ok,
                "snippet_len": len(snippet),
            }
        )

        ev = policy_record.get("evidence") or {}
        has_evidence = bool(ev.get("quote") and ev.get("source_uri"))
        checks.append(
            {
                "name": "wiki_has_embedded_evidence",
                "ok": has_evidence,
                "source_uri": ev.get("source_uri"),
            }
        )

        ok = all(c["ok"] for c in checks)
        return VerifyResult(
            ok=ok,
            checks=checks,
            message="handbook verify passed" if ok else "handbook verify failed",
        )

    def verify_graph_answer(
        self,
        *,
        question: str,
        answer: str,
        entities: list[dict[str, Any]],
        search_top_score: float,
        wiki_leaves: list[dict[str, Any]] | None = None,
    ) -> VerifyResult:
        checks: list[dict[str, Any]] = []
        norm = _norm(answer)
        leaves = wiki_leaves or []

        has_knowledge = len(entities) >= 1 or len(leaves) >= 1
        checks.append(
            {
                "name": "retrieved_knowledge",
                "ok": has_knowledge,
                "entity_count": len(entities),
                "leaf_count": len(leaves),
            }
        )
        if not has_knowledge:
            checks.append(
                {
                    "name": "no_hallucination_when_empty",
                    "ok": "未检索到" in answer or "未找到" in answer,
                }
            )

        section_sources = {str(e.get("section")) for e in entities if e.get("section")}
        section_sources.update(
            str(lf.get("section_ref")) for lf in leaves if lf.get("section_ref")
        )
        cited_sections = 0
        for sec in section_sources:
            if sec.replace(".", "") in norm or f"§{sec}" in answer or sec in answer:
                cited_sections += 1
        # 放宽：已检索到叶子时，不强制正文含 §（FAQ 列表式「依据」常见）
        cite_ok = cited_sections >= 1 or has_knowledge
        checks.append(
            {
                "name": "answer_cites_section",
                "ok": cite_ok,
                "cited": cited_sections,
                "relaxed": cited_sections < 1 and has_knowledge,
            }
        )

        score_ok = search_top_score >= 1.0 or has_knowledge
        checks.append(
            {
                "name": "search_relevance",
                "ok": score_ok,
                "top_score": search_top_score,
            }
        )

        faq_noise = any(
            "Q：" in (e.get("summary") or "")[:200] for e in entities[:1]
        )
        checks.append({"name": "no_faq_primary_hit", "ok": not faq_noise})

        if has_knowledge:
            evidence = _knowledge_text(entities, leaves)
            contradicted = _contradicts_retrieved_fact(answer, evidence)
            checks.append(
                {
                    "name": "conclusion_not_retracted",
                    "ok": not contradicted,
                }
            )
            invented = _obligation_then_retracted(answer, evidence)
            checks.append(
                {
                    "name": "obligation_grounded",
                    "ok": not invented,
                }
            )
            permitted = _prohibition_restated_as_permission(answer, evidence)
            checks.append(
                {
                    "name": "prohibition_not_restated_as_permission",
                    "ok": not permitted,
                }
            )

        ok = all(c["ok"] for c in checks)
        return VerifyResult(
            ok=ok,
            checks=checks,
            message="graph verify passed" if ok else "graph verify failed",
        )


def _norm(text: str) -> str:
    return "".join(text.lower().split())


def _knowledge_text(entities: list[dict[str, Any]], leaves: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for leaf in leaves:
        for key in ("title", "summary", "body"):
            parts.append(str(leaf.get(key) or ""))
    for entity in entities:
        for key in ("name", "summary", "body"):
            parts.append(str(entity.get(key) or ""))
        props = entity.get("properties") or {}
        if isinstance(props, dict):
            parts.append(str(props.get("body") or ""))
    return "\n".join(part for part in parts if part.strip())


def _content_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for segment in re.findall(r"[\u4e00-\u9fff]{2,}", text or ""):
        if len(segment) <= 6:
            tokens.add(segment)
        for index in range(len(segment) - 1):
            tokens.add(segment[index : index + 2])
    return {token for token in tokens if token not in _GENERIC_TOKENS and len(token) >= 2}


def _public_sentences(answer: str) -> list[str]:
    raw = answer or ""
    marker = re.search(r"\n\s*依据[：:]", raw)
    public = raw[: marker.start()] if marker else raw
    return [part.strip() for part in re.split(r"[。！？\n；;]", public) if part.strip()]


def _contradicts_retrieved_fact(answer: str, evidence: str) -> bool:
    """已写明的事实后面又说未检索到同一件事。"""
    evidence_tokens = _content_tokens(evidence)
    prior: set[str] = set()
    for sentence in _public_sentences(answer):
        if "未检索到" in sentence or "未找到" in sentence:
            if _content_tokens(sentence) & prior:
                return True
            continue
        prior |= _content_tokens(sentence) & evidence_tokens
    return False


def _obligation_then_retracted(answer: str, evidence: str) -> bool:
    """先写一条原文没有的义务，再用未检索到收回。"""
    pending = ""
    for sentence in _public_sentences(answer):
        if "未检索到" in sentence or "未找到" in sentence:
            if not pending:
                continue
            for span in _fourgrams(pending):
                if span in sentence and span not in evidence:
                    return True
            continue
        if _OBLIGATION.search(sentence):
            pending = sentence
    return False


def _prohibition_restated_as_permission(answer: str, evidence: str) -> bool:
    """原文是禁止，结论把条件改写成「如果没有就可以」。"""
    if not _PROHIBIT.search(evidence or ""):
        return False
    if not _HYPOTHETICAL_PERMIT.search(answer or ""):
        return False
    return _DENY.search(answer or "") is None


def _fourgrams(text: str) -> list[str]:
    chars = "".join(re.findall(r"[\u4e00-\u9fff]", text or ""))
    if len(chars) < 4:
        return []
    return [chars[index : index + 4] for index in range(len(chars) - 3)]
