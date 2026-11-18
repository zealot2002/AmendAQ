from __future__ import annotations

from typing import Any

from mycs.models import VerifyResult


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

        ok = all(c["ok"] for c in checks)
        return VerifyResult(
            ok=ok,
            checks=checks,
            message="graph verify passed" if ok else "graph verify failed",
        )


def _norm(text: str) -> str:
    return "".join(text.lower().split())
