"""Load pluggable answer skills. The agent loop does not know any domain."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from mycs.paths import repo_root


@dataclass(frozen=True)
class AnswerSkill:
    name: str
    description: str
    question_any: tuple[str, ...] = ()
    evidence_any: tuple[str, ...] = ()
    revise: bool = False
    instructions: str = ""
    path: str = ""


def skill_dirs() -> list[Path]:
    """Built-in packs, then repo skills/, then MYCS_SKILLS_DIR. Later dirs override the same name."""
    dirs = [Path(__file__).resolve().parent / "packs", repo_root() / "skills"]
    extra = (os.environ.get("MYCS_SKILLS_DIR") or "").strip()
    if extra:
        dirs.append(Path(extra))
    return dirs


def load_skills() -> list[AnswerSkill]:
    by_name: dict[str, AnswerSkill] = {}
    for root in skill_dirs():
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*/SKILL.md")):
            skill = _parse_skill(path)
            if skill.name:
                by_name[skill.name] = skill
    return list(by_name.values())


def evidence_text(context: dict) -> str:
    parts: list[str] = []
    for leaf in context.get("wiki_leaves") or []:
        if isinstance(leaf, dict):
            parts.append(
                " ".join(
                    str(leaf.get(key) or "")
                    for key in ("section_ref", "title", "summary", "body")
                )
            )
    entities = context.get("graph_entities") or []
    if isinstance(entities, dict):
        entities = [entities]
    for ent in entities:
        if isinstance(ent, dict):
            parts.append(
                " ".join(
                    str(ent.get(key) or "")
                    for key in ("section", "name", "summary", "body")
                )
            )
    return "\n".join(part for part in parts if part.strip())


def match_skills(
    skills: list[AnswerSkill],
    question: str,
    evidence_text: str,
) -> list[AnswerSkill]:
    q = question or ""
    ev = evidence_text or ""
    matched: list[AnswerSkill] = []
    for skill in skills:
        if not skill.question_any and not skill.evidence_any:
            continue
        if skill.question_any and not any(tok in q for tok in skill.question_any):
            continue
        if skill.evidence_any and not any(tok in ev for tok in skill.evidence_any):
            continue
        matched.append(skill)
    return matched


def _parse_skill(path: Path) -> AnswerSkill:
    text = path.read_text(encoding="utf-8")
    meta, body = _split_frontmatter(text)
    question_any = tuple(_as_list(meta.get("question_any")))
    evidence_any = tuple(_as_list(meta.get("evidence_any")))
    return AnswerSkill(
        name=str(meta.get("name") or path.parent.name).strip(),
        description=str(meta.get("description") or "").strip(),
        question_any=question_any,
        evidence_any=evidence_any,
        revise=_as_bool(meta.get("revise")),
        instructions=body.strip(),
        path=str(path),
    )


def _split_frontmatter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    raw = text[3:end].strip("\n")
    body = text[end + 4 :]
    meta: dict[str, object] = {}
    key: str | None = None
    for line in raw.splitlines():
        if line.startswith("  - ") and key:
            bucket = meta.get(key)
            if not isinstance(bucket, list):
                bucket = []
                meta[key] = bucket
            bucket.append(line[4:].strip())
            continue
        if ":" not in line or line.startswith(" "):
            continue
        name, value = line.split(":", 1)
        key = name.strip()
        value = value.strip()
        if value == "":
            meta[key] = []
        else:
            meta[key] = value
    return meta, body


def _as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _as_bool(value: object) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")
