from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

SECTION_RE = re.compile(
    r"^(?:####\s+)?(\d+\.\d+)\s+(.+?)\s*$",
    re.MULTILINE,
)
DEFAULT_SOURCE = Path(__file__).resolve().parents[3] / "data" / "sources" / "employee_handbook.txt"
DEFAULT_WIKI_OUT = Path(__file__).resolve().parents[3] / "data" / "wiki" / "canonical.json"


def policies_from_text(
    text: str,
    *,
    source_uri: str | None = None,
    effective_from: str | None = None,
) -> dict[str, Any]:
    effective = effective_from or date.today().isoformat()
    uri = source_uri or "file://data/sources/employee_handbook.txt"
    matches = list(SECTION_RE.finditer(text))
    policies: dict[str, Any] = {}

    for i, match in enumerate(matches):
        section_id = match.group(1)
        title = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk = text[start:end]
        chap = re.search(r"^\d+\.\s+[^\d]", chunk, re.MULTILINE)
        if chap:
            chunk = chunk[: chap.start()]
        chunk = re.split(r"\s13\.\s+常见问题", chunk)[0]
        chunk = re.split(r"\sQ：", chunk)[0]
        body = re.sub(r"\s+", " ", chunk.strip())
        if len(body) > 800:
            body = body[:800] + "…"
        policy_id = f"handbook_{section_id.replace('.', '_')}"
        quote = body if len(body) <= 400 else body[:400] + "…"
        policies[policy_id] = {
            "policy_id": policy_id,
            "section": section_id,
            "title": title,
            "summary": body[:280] + ("…" if len(body) > 280 else ""),
            "body": body,
            "tags": _tags_for(title, body),
            "evidence": {
                "quote": quote,
                "source_uri": uri,
                "effective_from": effective,
                "section_ref": section_id,
            },
        }
    return policies


def ingest_handbook_txt(
    source_path: Path | None = None,
    out_path: Path | None = None,
    *,
    effective_from: str | None = None,
) -> dict[str, Any]:
    """Legacy JSON export (optional). Primary store is SQLite via bootstrap."""
    src = source_path or DEFAULT_SOURCE
    out = out_path or DEFAULT_WIKI_OUT
    text = src.read_text(encoding="utf-8")
    effective = effective_from or date.today().isoformat()
    source_uri = f"file://{src.resolve()}"
    policies = policies_from_text(text, source_uri=source_uri, effective_from=effective)
    wiki = {
        "source_document": str(src.name),
        "effective_from": effective,
        "policies": policies,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(wiki, ensure_ascii=False, indent=2), encoding="utf-8")
    return wiki


def _tags_for(title: str, body: str) -> list[str]:
    blob = (title + " " + body).lower()
    tags = [title.lower()]
    keywords = [
        ("overtime", ["overtime", "加班"]),
        ("pto", ["paid time off", "pto", "年假", "vacation", "休假"]),
        ("sick", ["sick leave", "病假"]),
        ("at_will", ["at will", "at-will", "随意"]),
        ("harassment", ["harassment", "骚扰"]),
        ("introductory", ["introductory", "试用", "introductory period"]),
        ("tips", ["tips", "小费", "tip"]),
        ("meals", ["meal period", "用餐", "meal"]),
        ("remote_work", ["远程办公", "远程"]),
        ("security", ["安全事件", "账号", "泄露", "遗失", "2小时"]),
        ("gift", ["礼品", "2,000", "2000"]),
        ("learning_budget", ["学习预算", "18,000", "18000"]),
        ("resignation", ["辞职", "离职", "公司财产"]),
        ("performance", ["绩效", "目标"]),
        ("ai_tools", ["ai工具", "ai"]),
    ]
    for tag, keys in keywords:
        if any(k in blob for k in keys):
            tags.append(tag)
    return list(dict.fromkeys(tags))
