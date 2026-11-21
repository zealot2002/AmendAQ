from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Literal

import httpx

from mycs.llm.claims import build_claims
from mycs.llm.errors import LLMError
from mycs.llm.patterns import CASE_ID_PATTERN
from mycs.log import get_logger
from mycs.log_detail import log_step
from mycs.models import KnowledgeRequirement, UnderstandResult
from mycs.planning.graph_plan import minimal_graph_fallback
from mycs.prompts import prompt
from mycs.planning.plan_schema import normalize_requirements
from mycs.ui.trace_llm_capture import record_llm_exchange

logger = get_logger(__name__)

ProviderKind = Literal["ollama", "openai"]


class OpenAICompatLLM:
    """OpenAI-compatible chat (Ollama / 智谱 GLM / others)."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
        trust_env: bool | None = None,
        provider: ProviderKind | None = None,
        max_tokens: int | None = None,
    ) -> None:
        self.base_url = (
            base_url or os.environ.get("OPENAI_API_BASE", "http://localhost:11434/v1")
        ).rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "ollama")
        self.model = model or os.environ.get("OPENAI_MODEL", "qwen2.5:7b")
        self.timeout = timeout
        self.max_tokens = max_tokens or int(
            os.environ.get("GROQ_MAX_TOKENS")
            or os.environ.get("GLM_MAX_TOKENS", "2048")
        )
        if trust_env is None:
            self.trust_env = _default_trust_env(self.base_url)
        else:
            self.trust_env = trust_env
        self.provider = provider or _infer_provider(self.base_url)

    def understand(self, question: str, case_id: str | None) -> UnderstandResult:
        system = prompt("understand")
        user = json.dumps({"question": question, "hint_case_id": case_id}, ensure_ascii=False)
        try:
            data = self._json_chat(system, user)
        except Exception as exc:
            logger.error("llm understand failed: %s", exc)
            raise LLMError(f"understand failed: {exc}") from exc

        extracted = data.get("case_id") or case_id
        if not extracted:
            match = CASE_ID_PATTERN.search(question)
            if match:
                extracted = match.group(0).upper()
        intent = data.get("intent") or "graph_qa"
        if intent == "handbook_qa":
            intent = "graph_qa"
        doc = os.environ.get("MYCS_GRAPH_DOCUMENT") or data.get("graph_document_id") or None
        out = UnderstandResult(
            case_id=extracted,
            intent=intent,
            raw_question=question,
            wiki_topics=[],
            graph_document_id=doc,
        )
        log_step(
            logger,
            "llm_understand",
            case_id=out.case_id,
            intent=out.intent,
            graph_document_id=out.graph_document_id,
            question=question[:300],
        )
        return out

    def select_toc_branch(
        self,
        *,
        question: str,
        level: int,
        path: list[dict[str, str]],
        choices: list[dict[str, object]],
    ) -> dict[str, Any]:
        system = prompt("toc_select")
        user = json.dumps(
            {
                "question": question,
                "level": level,
                "path_so_far": path,
                "choices": choices,
            },
            ensure_ascii=False,
        )
        try:
            data = self._json_chat(system, user, max_tokens=512)
            action = str(data.get("action") or "select").lower()
            node_id = data.get("node_id")
            if action in ("stop", "done", "halt"):
                return {"action": "stop", "node_id": None, "reason": data.get("reason") or "stop"}
            if not node_id:
                return {"action": "stop", "node_id": None, "reason": "missing node_id"}
            return {
                "action": "select",
                "node_id": str(node_id),
                "reason": str(data.get("reason") or ""),
            }
        except Exception as exc:
            logger.error("llm toc drill failed level=%s: %s", level, exc)
            if choices:
                return {
                    "action": "select",
                    "node_id": choices[0]["node_id"],
                    "reason": f"fallback_first_choice ({exc})",
                }
            return {"action": "stop", "node_id": None, "reason": str(exc)}

    def review_toc_catalog_batch(
        self,
        *,
        question: str,
        batch_index: int,
        batch_total: int,
        chapter_total: int,
        chapters_in_batch: list[dict[str, object]],
        already_selected: list[dict[str, str]],
        batches_remaining: int,
        composite_query: bool = False,
        enumerative_query: bool = False,
    ) -> dict[str, Any]:
        composite_note = (
            "\n\n" + prompt("toc_catalog_composite") if composite_query else ""
        )
        enumerative_note = (
            "\n\n" + prompt("toc_catalog_enumerative") if enumerative_query else ""
        )
        _ = (chapter_total, batch_total, already_selected, batches_remaining)
        system = prompt(
            "toc_catalog",
            composite_note=composite_note,
            enumerative_note=enumerative_note,
        )
        user = json.dumps(
            {
                "question": question,
                "chapters": chapters_in_batch,
                "composite_query": composite_query,
                "enumerative_query": enumerative_query,
            },
            ensure_ascii=False,
        )
        try:
            data = self._json_chat(system, user, max_tokens=768)
            refs = data.get("section_refs") or []
            if not isinstance(refs, list):
                refs = []
            return {
                "section_refs": [str(r) for r in refs if r],
                "reason": str(data.get("reason") or ""),
            }
        except Exception as exc:
            logger.error("llm toc batch review failed batch=%s: %s", batch_index, exc)
            return {"section_refs": [], "reason": str(exc)}

    def review_toc_children_batch(
        self,
        *,
        question: str,
        parent_section_ref: str,
        parent_title: str,
        batch_index: int,
        batch_total: int,
        children_in_batch: list[dict[str, object]],
        already_selected: list[dict[str, str]],
        batches_remaining: int,
        enumerative_query: bool = False,
        composite_query: bool = False,
    ) -> dict[str, Any]:
        enumerative_note = (
            "\n\n" + prompt("toc_children_enumerative") if enumerative_query else ""
        )
        composite_note = (
            "\n\n" + prompt("toc_children_composite") if composite_query else ""
        )
        system = prompt(
            "toc_children",
            enumerative_note=enumerative_note,
            composite_note=composite_note,
        )
        _ = (batch_total, batches_remaining, already_selected, parent_title)
        user = json.dumps(
            {
                "question": question,
                "entries": children_in_batch,
                "enumerative_query": enumerative_query,
                "composite_query": composite_query,
            },
            ensure_ascii=False,
        )
        try:
            data = self._json_chat(system, user, max_tokens=768)
            refs = data.get("section_refs") or []
            if not isinstance(refs, list):
                refs = []
            return {
                "section_refs": [str(r) for r in refs if r],
                "reason": str(data.get("reason") or ""),
            }
        except Exception as exc:
            logger.error(
                "llm toc children batch failed parent=%s batch=%s: %s",
                parent_section_ref,
                batch_index,
                exc,
            )
            return {"action": "continue", "section_refs": [], "reason": str(exc)}

    def review_faq_title_batch(
        self,
        *,
        question: str,
        document_title: str,
        batch_index: int,
        batch_total: int,
        entry_total: int,
        entries_in_batch: list[dict[str, object]],
        already_selected: list[dict[str, str]],
        batches_remaining: int,
        enumerative_query: bool = False,
        composite_query: bool = False,
        recall_exhaustive_batches: bool = True,
        max_picks: int = 5,
    ) -> dict[str, Any]:
        pick_cap = max(1, int(max_picks))
        if enumerative_query:
            enumerative_note = "\n\n" + prompt("faq_title_enumerative", pick_cap=pick_cap)
        else:
            enumerative_note = "\n\n" + prompt("faq_title_ordinary", pick_cap=pick_cap)
        composite_note = (
            "\n\n" + prompt("faq_title_composite", pick_cap=pick_cap) if composite_query else ""
        )
        _ = (batches_remaining, already_selected, recall_exhaustive_batches)
        system = prompt(
            "faq_title",
            enumerative_note=enumerative_note,
            composite_note=composite_note,
        )
        user = json.dumps(
            {
                "question": question,
                "document_title": document_title,
                "entries": entries_in_batch,
                "enumerative_query": enumerative_query,
                "composite_query": composite_query,
                "max_picks": pick_cap,
            },
            ensure_ascii=False,
        )
        try:
            token_cap = 2048 if batch_total <= 1 and entry_total > 24 else 768
            data = self._json_chat(system, user, max_tokens=token_cap)
            refs = data.get("section_refs") or []
            if not isinstance(refs, list):
                refs = []
            return {
                "section_refs": [str(r) for r in refs if r],
                "reason": str(data.get("reason") or ""),
            }
        except Exception as exc:
            logger.error("llm faq title batch failed batch=%s: %s", batch_index, exc)
            return {"action": "continue", "section_refs": [], "reason": str(exc)}

    def plan(
        self,
        understood: UnderstandResult,
        plan_context: dict[str, object] | None = None,
    ) -> list[KnowledgeRequirement]:
        plan_context = plan_context or {}
        system = prompt("plan")
        outline_raw = plan_context.get("wiki_toc_outline") or []
        user_payload = {
            "intent": understood.intent,
            "case_id": understood.case_id,
            "graph_document_id": understood.graph_document_id,
            "question": understood.raw_question,
            "wiki_drill_path": plan_context.get("wiki_drill_path") or [],
            "wiki_scope_section_prefix": plan_context.get("wiki_scope_section_prefix"),
            "wiki_scope_section_refs": plan_context.get("wiki_scope_section_refs") or [],
            "wiki_selected_chapters": plan_context.get("wiki_selected_chapters") or [],
            "wiki_toc_outline": outline_raw,
            "catalog_note": plan_context.get("catalog_note") or "",
        }
        user = json.dumps(user_payload, ensure_ascii=False)
        log_step(
            logger,
            "llm_plan_request",
            payload={**user_payload, "wiki_toc_outline_count": len(outline_raw)},
            max_json_chars=4000,
        )
        plan_tokens = max(1024, min(4096, 768 + len(outline_raw) * 24))
        try:
            data = self._json_chat(system, user, max_tokens=plan_tokens)
            log_step(logger, "llm_plan_raw_response", requirements=data.get("requirements"))
            items = list(data.get("requirements") or [])
            reqs = normalize_requirements(understood, items)
            if not reqs:
                raise ValueError("empty requirements after normalize")
            log_step(
                logger,
                "llm_plan_normalized",
                gaps=[r.field for r in reqs],
                requirements=[r.to_dict() for r in reqs],
            )
            return reqs
        except LLMError as exc:
            logger.error("llm plan failed (llm): %s", exc)
            if understood.intent in ("graph_qa", "handbook_qa"):
                logger.info("joyjoy: using minimal graph plan fallback after llm error")
                return minimal_graph_fallback(understood)
            raise
        except Exception as exc:
            logger.error("llm plan failed: %s", exc)
            if understood.intent in ("graph_qa", "handbook_qa"):
                logger.info("joyjoy: using minimal graph plan fallback")
                return minimal_graph_fallback(understood)
            raise LLMError(f"plan failed: {exc}") from exc

    def compose_answer(
        self,
        understood: UnderstandResult,
        context: dict[str, object],
    ) -> tuple[str, dict[str, object]]:
        claims = build_claims(understood, context)  # type: ignore[arg-type]
        system = prompt("compose")
        skill_text = str(context.get("skill_instructions") or "").strip()
        if skill_text:
            system += "\n\n" + prompt("compose_skill") + "\n" + skill_text
        slim = {
            "wiki_leaves": context.get("wiki_leaves"),
            "graph_entities": context.get("graph_entities") or context.get("graph_entity"),
            "graph_sql_result": context.get("graph_sql_result"),
            "case": context.get("case"),
            "policy": context.get("policy"),
            "procedure": context.get("procedure"),
        }
        from mycs.planning.chapter_hints import (
            is_multi_part_question,
            question_lines_for_seeding,
        )

        q = understood.raw_question or ""
        sub_qs = question_lines_for_seeding(q) if is_multi_part_question(q) else []
        user = json.dumps(
            {
                "intent": understood.intent,
                "question": q,
                "sub_questions": sub_qs,
                "must_answer_every_sub_question": bool(sub_qs),
                "tool_results": slim,
            },
            ensure_ascii=False,
        )
        try:
            log_step(
                logger,
                "llm_compose_request",
                wiki_leaves=len(slim.get("wiki_leaves") or []),
                graph_entities=len(slim.get("graph_entities") or []),
            )
            text = self._text_chat(system, user)
            text = text.strip()
            if not text:
                raise ValueError("empty answer")
            log_step(logger, "llm_compose_done", answer_len=len(text), preview=text[:180])
            return text, claims
        except LLMError:
            raise
        except Exception as exc:
            logger.error("llm compose failed: %s", exc)
            raise LLMError(f"compose failed: {exc}") from exc

    def revise_answer(
        self,
        *,
        question: str,
        draft: str,
        evidence_text: str,
        skill_instructions: str,
    ) -> str:
        system = prompt("revise")
        user = json.dumps(
            {
                "question": question,
                "clauses": evidence_text,
                "skills": skill_instructions,
                "draft": draft,
            },
            ensure_ascii=False,
        )
        text = self._text_chat(system, user).strip()
        return text or draft

    def _json_chat(
        self, system: str, user: str, *, max_tokens: int | None = None
    ) -> dict[str, Any]:
        content = self._raw_chat(
            system, user, json_mode=True, max_tokens=max_tokens
        )
        content = _strip_json_fence(content)
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMError(f"invalid JSON from model: {content[:200]!r}") from exc

    def _text_chat(self, system: str, user: str) -> str:
        return self._raw_chat(system, user, json_mode=False)

    def _raw_chat(
        self,
        system: str,
        user: str,
        *,
        json_mode: bool,
        max_tokens: int | None = None,
    ) -> str:
        url = f"{self.base_url}/chat/completions"
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "temperature": 0.2,
            "max_tokens": max_tokens or self.max_tokens,
        }
        if json_mode:
            if self.provider == "ollama":
                body["format"] = "json"
            else:
                body["response_format"] = {"type": "json_object"}
        # Qwen3 / vLLM 推理模型默认关闭 thinking，避免 content=null 且耗尽 max_tokens
        if self.provider == "openai" and _env_truthy("OPENAI_ENABLE_THINKING", default=False) is False:
            body["chat_template_kwargs"] = {"enable_thinking": False}
        headers = {"Authorization": f"Bearer {self.api_key}"}
        logger.info(
            "llm chat provider=%s model=%s json=%s",
            self.provider,
            self.model,
            json_mode,
        )
        retries = int(
            os.environ.get("GROQ_HTTP_RETRIES")
            or os.environ.get("GLM_HTTP_RETRIES", "6")
        )
        vendor = "Groq" if "groq.com" in self.base_url.lower() else "LLM"
        data: dict[str, Any] | None = None
        last_exc: Exception | None = None
        for attempt in range(retries):
            try:
                with httpx.Client(timeout=self.timeout, trust_env=self.trust_env) as client:
                    resp = client.post(url, json=body, headers=headers)
                    if resp.status_code == 429:
                        wait = min(90, 8 * (2**attempt))
                        logger.info(
                            "joyjoy: %s 429 rate limit, retry in %ss (%s/%s)",
                            vendor,
                            wait,
                            attempt + 1,
                            retries,
                        )
                        time.sleep(wait)
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    break
            except Exception as exc:
                last_exc = exc
                if attempt + 1 >= retries:
                    break
                wait = min(60, 5 * (2**attempt))
                logger.info("joyjoy: %s request error, retry in %ss: %s", vendor, wait, exc)
                time.sleep(wait)
        if data is None:
            msg = str(last_exc) if last_exc else "rate limit or network after retries"
            raise LLMError(f"HTTP chat failed: {msg}") from last_exc
        try:
            message = data["choices"][0]["message"]
            choice = message.get("content")
            if not (isinstance(choice, str) and choice.strip()):
                # 部分推理模型把正文放在 reasoning
                alt = message.get("reasoning") or message.get("reasoning_content")
                if isinstance(alt, str) and alt.strip():
                    choice = alt
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise LLMError(f"unexpected API response: {data!r}") from exc
        if not isinstance(choice, str):
            raise LLMError("unexpected message content type")
        try:
            record_llm_exchange(
                system=system,
                user=user,
                response_text=choice,
                json_mode=json_mode,
                model=self.model,
                api_response=data,
            )
        except Exception:
            pass
        return choice


def _env_truthy(name: str, *, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _infer_provider(base_url: str) -> ProviderKind:
    low = base_url.lower()
    if "11434" in low or "localhost" in low or "127.0.0.1" in low:
        return "ollama"
    return "openai"


def _default_trust_env(base_url: str) -> bool:
    return _infer_provider(base_url) == "openai"


def _strip_json_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()
