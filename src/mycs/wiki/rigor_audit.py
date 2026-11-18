from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mycs.log import get_logger
from mycs.wiki.canonical import (
    CanonicalChapter,
    CanonicalEvidence,
    CanonicalLeaf,
    WikiCanonicalDraft,
    validate_canonical,
)

logger = get_logger(__name__)

_FAQ_Q_TITLE = re.compile(r"^Q\d+", re.I)


@dataclass
class RigorIssue:
    severity: str  # block | warn
    section_ref: str
    code: str
    message: str
    ops_action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "section_ref": self.section_ref,
            "code": self.code,
            "message": self.message,
            "ops_action": self.ops_action,
        }


@dataclass
class WikiRigorReport:
    document_id: str
    status_filter: str
    ok: bool
    deterministic_issues: list[RigorIssue] = field(default_factory=list)
    llm_issues: list[RigorIssue] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "status_filter": self.status_filter,
            "ok": self.ok,
            "deterministic_issues": [i.to_dict() for i in self.deterministic_issues],
            "llm_issues": [i.to_dict() for i in self.llm_issues],
            "summary": self.summary,
            "issue_count": len(self.deterministic_issues) + len(self.llm_issues),
            "block_count": sum(
                1
                for i in self.deterministic_issues + self.llm_issues
                if i.severity == "block"
            ),
        }


def load_wiki_snapshot(
    conn: sqlite3.Connection,
    document_id: str,
    *,
    prefer_status: str = "published",
) -> tuple[WikiCanonicalDraft, str]:
    """Load TOC into canonical draft; fall back to draft if nothing published."""
    status = prefer_status
    rows = conn.execute(
        """
        SELECT * FROM wiki_toc_node
        WHERE document_id = ? AND status = ? AND disabled = 0
        ORDER BY sort_key, depth
        """,
        (document_id, status),
    ).fetchall()
    if not rows:
        status = "draft"
        rows = conn.execute(
            """
            SELECT * FROM wiki_toc_node
            WHERE document_id = ? AND status = ? AND disabled = 0
            ORDER BY sort_key, depth
            """,
            (document_id, status),
        ).fetchall()
    if not rows:
        raise ValueError(f"no wiki_toc_node for document_id={document_id}")

    ch_by_id: dict[str, sqlite3.Row] = {}
    chapters: list[CanonicalChapter] = []
    leaves: list[CanonicalLeaf] = []
    for row in rows:
        if row["kind"] == "chapter":
            ch_by_id[row["node_id"]] = row
            chapters.append(
                CanonicalChapter(
                    section_ref=str(row["section_ref"]),
                    title=str(row["title"]),
                )
            )
    for row in rows:
        if row["kind"] != "leaf":
            continue
        parent = ch_by_id.get(row["parent_id"])
        parent_ref = (
            str(parent["section_ref"]).rstrip(".") if parent else ""
        )
        entity_id = str(row["entity_id"] or "")
        quote = ""
        if entity_id:
            prow = conn.execute(
                "SELECT evidence_quote FROM wiki_policy WHERE policy_id = ?",
                (entity_id,),
            ).fetchone()
            if prow:
                quote = str(prow["evidence_quote"] or "")
        if not quote:
            quote = (row["body"] or "")[:500]
        leaves.append(
            CanonicalLeaf(
                section_ref=str(row["section_ref"]),
                parent_ref=parent_ref,
                title=str(row["title"]),
                summary=str(row["summary"] or ""),
                body=str(row["body"] or ""),
                evidence=CanonicalEvidence(quote=quote),
            )
        )
    mount = conn.execute(
        "SELECT display_title FROM wiki_document_mount WHERE document_id = ? LIMIT 1",
        (document_id,),
    ).fetchone()
    title = str(mount["display_title"]) if mount else document_id
    draft = WikiCanonicalDraft(document_title=title, chapters=chapters, leaves=leaves)
    return draft, status


def deterministic_rigor_checks(draft: WikiCanonicalDraft, *, faq_mode: bool) -> list[RigorIssue]:
    issues: list[RigorIssue] = []
    for err in validate_canonical(draft):
        issues.append(
            RigorIssue(
                severity="block",
                section_ref="",
                code="canonical",
                message=err,
                ops_action="按 ingest 契约修复该条后重新入库",
            )
        )
    titles: dict[str, list[str]] = {}
    for lf in draft.leaves:
        if faq_mode and not _FAQ_Q_TITLE.match(lf.title.strip()):
            issues.append(
                RigorIssue(
                    severity="block",
                    section_ref=lf.section_ref,
                    code="faq_title_format",
                    message="叶标题须以 Q 题号开头",
                    ops_action="运营在源稿或审核页改正标题，重新发布",
                )
            )
        if lf.summary.strip() == lf.title.strip() and len(lf.body.strip()) > 80:
            issues.append(
                RigorIssue(
                    severity="warn",
                    section_ref=lf.section_ref,
                    code="summary_is_title_only",
                    message="summary 仅复制标题，未写可检索摘要",
                    ops_action="将 body 要点写入 summary（前 280 字）",
                )
            )
        if len(lf.body.strip()) < 12:
            issues.append(
                RigorIssue(
                    severity="block",
                    section_ref=lf.section_ref,
                    code="body_too_short",
                    message="答案 body 过短",
                    ops_action="补全正文答案",
                )
            )
        key = lf.title.strip().lower()
        titles.setdefault(key, []).append(lf.section_ref)
    for title, refs in titles.items():
        if len(refs) > 1:
            issues.append(
                RigorIssue(
                    severity="warn",
                    section_ref=",".join(refs),
                    code="duplicate_title",
                    message=f"重复题干：{title[:40]}",
                    ops_action="合并或区分题号，避免寻址歧义",
                )
            )
    return issues


def llm_rigor_enabled() -> bool:
    return os.environ.get("MYCS_WIKI_LLM_AUDIT", "1").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def run_llm_rigor_audit(llm: Any, draft: WikiCanonicalDraft) -> tuple[list[RigorIssue], str]:
    if not llm_rigor_enabled():
        return [], ""
    catalog = [
        {
            "section_ref": lf.section_ref,
            "title": lf.title,
            "summary": lf.summary[:280],
            "body_preview": lf.body[:400],
        }
        for lf in draft.leaves[:80]
    ]
    system = (
        "你是企业知识库质检员。检查 Wiki 叶节点是否适合作为客服唯一依据。"
        "输出 JSON：{"
        '"summary": string, '
        '"issues": [{"severity":"block"|"warn","section_ref":string,"code":string,'
        '"message":string,"ops_action":string}]'
        "}。"
        "关注：题答不符、summary 不能检索、跨题混杂、占位符电话、缺步骤、标题与 body 矛盾。"
        "block=必须人工改后才能上线；warn=建议改。不要编造库中不存在的 section_ref。"
    )
    user = json.dumps(
        {"document_title": draft.document_title, "leaves": catalog},
        ensure_ascii=False,
    )
    if not hasattr(llm, "_json_chat"):
        logger.info("joyjoy: wiki llm audit skipped (llm has no _json_chat)")
        return [], ""
    try:
        data = llm._json_chat(system, user, max_tokens=2048)  # type: ignore[attr-defined]
    except Exception as exc:
        logger.warning("joyjoy: wiki llm audit failed: %s", exc)
        return [], f"LLM 审核未执行: {exc}"
    out: list[RigorIssue] = []
    for raw in data.get("issues") or []:
        if not isinstance(raw, dict):
            continue
        out.append(
            RigorIssue(
                severity=str(raw.get("severity") or "warn"),
                section_ref=str(raw.get("section_ref") or ""),
                code=str(raw.get("code") or "llm"),
                message=str(raw.get("message") or ""),
                ops_action=str(raw.get("ops_action") or "请运营人工核对并修改"),
            )
        )
    summary = str(data.get("summary") or "")
    logger.info("joyjoy: wiki llm audit issues=%s", len(out))
    return out, summary


def audit_wiki_document(
    conn: sqlite3.Connection,
    document_id: str,
    *,
    llm: Any | None = None,
    faq_mode: bool | None = None,
) -> WikiRigorReport:
    draft, status = load_wiki_snapshot(conn, document_id)
    is_faq = faq_mode if faq_mode is not None else document_id == "faq"
    det = deterministic_rigor_checks(draft, faq_mode=is_faq)
    llm_issues: list[RigorIssue] = []
    llm_summary = ""
    if llm is not None:
        llm_issues, llm_summary = run_llm_rigor_audit(llm, draft)
    blocks = [i for i in det + llm_issues if i.severity == "block"]
    report = WikiRigorReport(
        document_id=document_id,
        status_filter=status,
        ok=not blocks,
        deterministic_issues=det,
        llm_issues=llm_issues,
        summary=llm_summary
        or ("通过确定性校验" if not det and not llm_issues else "存在需运营处理的问题"),
    )
    logger.info(
        "joyjoy: wiki rigor audit doc=%s ok=%s det=%s llm=%s",
        document_id,
        report.ok,
        len(det),
        len(llm_issues),
    )
    return report


def write_audit_json(report: WikiRigorReport, path: Path | str) -> None:
    payload = report.to_dict()
    payload["ts"] = datetime.now(timezone.utc).isoformat()
    p = path if isinstance(path, str) else str(path)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)