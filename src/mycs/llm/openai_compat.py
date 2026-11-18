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
        system = (
            "你是客服 Agent 的理解模块。只输出 JSON，不要 markdown。"
            "字段：case_id (string|null), intent (string), graph_document_id (string|null)。"
            "intent：case_status_and_policy_limit | procedure_online_only | graph_qa。"
            "无办件号且问政策/手册/流程 → graph_qa。"
            "问能否线上办理 → procedure_online_only。"
            "办件进度/预审/时限 → case_status_and_policy_limit，并提取 CASE-YYYY-NNN。"
        )
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
        system = (
            "你是知识库目录导航模块（像查字典一样一层层缩小范围）。只输出 JSON，不要 markdown。"
            '格式：{"action":"select"|"stop","node_id":string|null,"reason":string}。'
            "规则："
            "1) choices 是当前层级并列目录（含 node_id、section_ref、title、kind）；"
            "2) action=select 时必须给出最相关条目的 node_id；"
            "3) kind=leaf 表示已到具体条款，选中后停止展开；"
            "4) action=stop 表示无法判断或需保持上一层范围，node_id 为 null；"
            "5) 只选一个条目，不要编造 node_id。"
        )
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
    ) -> dict[str, Any]:
        composite_note = ""
        if composite_query:
            composite_note = (
                "\n\n【综合/多事项问题】用户可能在问多个彼此独立的事项（如离职+年假+报销+归还电脑）。"
                "每一事项可能落在**不同章**；本批命中的章不能代表已覆盖全部。"
                "必须在本批选出所有可能相关的章；"
                f"在 batches_remaining_after_this>0 时**禁止 action=done**，只能用 pick 或 continue。"
            )
        system = (
            "你是知识库目录分批浏览助手。手册一级目录（章）很多，系统会**分批**把章列表发给你。"
            "你的目标是：根据用户问题，找出**可能包含答案的章**，不要漏掉相关章。"
            "只输出 JSON，不要 markdown。格式："
            '{"action":"pick"|"continue"|"done"|"need_full_handbook","section_refs":["6.",...],"reason":"..."}。'
            "\n\n说明："
            f"- 全手册共 {chapter_total} 章，分 {batch_total} 批展示；"
            "每批只含部分章，**当前批里没有相关章不代表手册其他章没有**，除非已看完所有批。"
            "\n\naction 含义："
            "- pick：本批中有相关章，把 section_ref 写入 section_refs（可多选）；"
            "若仍需查看后续批次继续找，action 仍用 pick 并只写本批命中的章；"
            "- continue：本批完全不相关，且还需要看后续批次；"
            "- done：仅当**已看完所有批**且 already_selected 已覆盖问题的全部事项时才能用；"
            "- need_full_handbook：问题需要通读全手册（如「所有」「全部」「列举每一个」），不再分批。"
            "\nsection_ref 必须来自本批 chapters 列表，不得编造。"
            + composite_note
        )
        user = json.dumps(
            {
                "question": question,
                "batch_index": batch_index,
                "batch_total": batch_total,
                "chapter_total": chapter_total,
                "batches_remaining_after_this": batches_remaining,
                "already_selected_chapters": already_selected,
                "chapters_in_this_batch": chapters_in_batch,
                "composite_query": composite_query,
            },
            ensure_ascii=False,
        )
        try:
            data = self._json_chat(system, user, max_tokens=768)
            action = str(data.get("action") or "continue").lower()
            refs = data.get("section_refs") or []
            if not isinstance(refs, list):
                refs = []
            return {
                "action": action,
                "section_refs": [str(r) for r in refs if r],
                "reason": str(data.get("reason") or ""),
            }
        except Exception as exc:
            logger.error("llm toc batch review failed batch=%s: %s", batch_index, exc)
            return {"action": "continue", "section_refs": [], "reason": str(exc)}

    def plan(
        self,
        understood: UnderstandResult,
        plan_context: dict[str, object] | None = None,
    ) -> list[KnowledgeRequirement]:
        plan_context = plan_context or {}
        system = (
            "你是 Knowledge Agent 的规划模块。只输出 JSON，不要 markdown："
            '{"requirements":[{"field":"...","source":"graph|domain_api|wiki","params":{...}}]}。'
            "规划的是**知识缺口**（Knowledge Requirement），不是 search 关键词列表，不要 tool 字段。"
            "\n\nintent=graph_qa 时（员工手册/政策 Wiki）："
            "输入含 wiki_toc_outline（已选相关章下的节/条摘要）、wiki_selected_chapters（章列表）、"
            "wiki_drill_path（逐层定位路径，可能为空）。"
            "outline 中的 section_ref 是唯一合法条号来源。"
            "1) 若已有 drill 范围，优先 graph.entity.search + by_section，branch 仅作补充；"
            "2) 否则 wiki.toc.branch：params.node_id 或 section_prefix 限定子树；"
            "3) graph.entity.search（query 用用户原问；若有 branch 则检索限定在该子树）；"
            "4) graph.entity.by_section 的 section 必须来自 wiki_toc_outline 的 leaf section_ref；"
            "若 wiki_scope_section_refs 含多条，每一条都要单独 by_section，不要只查落下的那一节；"
            "5) wiki.toc.leaves 可指定 node_ids 直接取叶子；"
            "6) graph.read.query 仅用于列举/汇总/金额类。"
            "禁止臆造条号、禁止 neighbors 凑数。"
            "params.document_id 必须等于 graph_document_id。"
            "requirements[].field 只能是合法缺口名（如 graph.entity.search），"
            "不得把 wiki_drill_path、wiki_toc_outline 等输入字段当作 field。"
            "\n\nintent=case_status_and_policy_limit：case.status、case.record、"
            "gov.policy.review_time_limit（procedure_id=__from_case__ review_stage=pre_review）。"
            "\n\nintent=procedure_online_only：gov.procedure.online_available。"
        )
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
        system = (
            "你是智能客服。优先根据 tool_results.wiki_leaves 与 graph_entities 作答。"
            "引用章节号（§x.y）。禁止编造检索结果中不存在的数字、时限、金额。"
            "若 wiki_leaves/graph_entities 为空，只回答「当前知识库未检索到相关条款，请补充或联系管理员」。"
            "多章节需综合。只输出中文正文。"
            "\n\n【回答格式 — 必须遵守】"
            "\n1. 「结论：」段 = **用户唯一默认可见的完整答复**（不可只写一句话敷衍）："
            "首句直接回答是/否/可否/数量/时限；随后用编号分条写清步骤、链接、电话、时限、"
            "操作路径等可操作要点，均须来自 wiki_leaves / graph_entities 原文，禁止编造。"
            "\n2. 空一行后写「依据：」：仅作条款对照，每条带 § 号；可简短，勿把仅写在依据里的细节"
            "当作对客答案（细则必须在结论段已写出）。"
            "\n3. 除上述两段外不要写标题、markdown 或客套话。"
            "\n4. 若问题涉及多项（如离职+年假+报销），结论段分事项写全；依据段列对应 §。"
            "严格区分原文措辞：「必须/不得」=强制，「应/原则上」=一般要求，"
            "「建议/可」=非强制。不得把「原则上」写成「必须」。"
        )
        skill_text = str(context.get("skill_instructions") or "").strip()
        if skill_text:
            system += (
                "\n\n【已启用技能】下面是推理约束，不是新的事实。"
                "数字、时限、金额仍只能来自问题和条款原文。"
                "对客正文不要写出技能名称。\n"
                + skill_text
            )
        slim = {
            "wiki_leaves": context.get("wiki_leaves"),
            "graph_entities": context.get("graph_entities") or context.get("graph_entity"),
            "graph_sql_result": context.get("graph_sql_result"),
            "case": context.get("case"),
            "policy": context.get("policy"),
            "procedure": context.get("procedure"),
        }
        user = json.dumps(
            {
                "intent": understood.intent,
                "question": understood.raw_question,
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
        system = (
            "你是客服回答的核对模块。先只根据用户问题、条款原文和技能说明，独立得出结论应有的数量或判断，再对照草稿。"
            "技能说明是推理约束，不是新的事实；数字、时限、金额只能来自问题和条款原文。"
            "草稿若在依据里先给出一个数量，又改用另一个数量作为「结论：」那一行，视为不符合，必须改写。"
            "不得因为草稿后面的句子能自圆其说就原样返回。"
            "改写后的正文仍用「结论：」和「依据：」；结论段须含完整对客要点，依据只保留与结论一致的 § 对照。"
            "对客正文不要出现技能名称。不要写核对过程。"
            "只有结论与你独立推出的结果一致时，才原样输出草稿。"
        )
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
