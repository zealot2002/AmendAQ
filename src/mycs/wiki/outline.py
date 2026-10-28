from __future__ import annotations

import re
from dataclasses import dataclass, field

from mycs.wiki.ingest import policies_from_text

CHAPTER_RE = re.compile(r"^(\d+)\.\s+([^\d\n].+?)\s*$", re.MULTILINE)
SECTION_RE = re.compile(r"^(\d+\.\d+)\s+(.+?)\s*$", re.MULTILINE)


@dataclass
class OutlineNode:
    node_key: str
    kind: str
    section_ref: str
    title: str
    body: str = ""
    summary: str = ""
    children: list[OutlineNode] = field(default_factory=list)
    chapter_num: str = ""


def parse_outline_from_text(
    text: str,
    *,
    source_uri: str = "",
) -> list[OutlineNode]:
    """Build chapter → section(leaf) tree from numbered Chinese handbook."""
    policies = policies_from_text(text, source_uri=source_uri or None)
    chapters: dict[str, OutlineNode] = {}
    roots: list[OutlineNode] = []

    for chap in CHAPTER_RE.finditer(text):
        num = chap.group(1)
        title = chap.group(2).strip()
        if num in chapters:
            continue
        node = OutlineNode(
            node_key=f"ch_{num}",
            kind="chapter",
            section_ref=f"{num}.",
            title=title,
            chapter_num=num,
        )
        chapters[num] = node
        roots.append(node)

    if not roots:
        roots.append(
            OutlineNode(
                node_key="ch_0",
                kind="chapter",
                section_ref="",
                title="Document",
                chapter_num="0",
            )
        )
        chapters["0"] = roots[0]

    for _pid, p in sorted(policies.items(), key=lambda x: x[1]["section"]):
        sec = p["section"]
        chap_num = sec.split(".")[0]
        ch = chapters.get(chap_num)
        if not ch:
            ch = OutlineNode(
                node_key=f"ch_{chap_num}",
                kind="chapter",
                section_ref=f"{chap_num}.",
                title=f"Chapter {chap_num}",
                chapter_num=chap_num,
            )
            chapters[chap_num] = ch
            roots.append(ch)
        leaf = OutlineNode(
            node_key=f"sec_{sec.replace('.', '_')}",
            kind="leaf",
            section_ref=sec,
            title=p["title"],
            body=p["body"],
            summary=p["summary"],
            chapter_num=chap_num,
        )
        ch.children.append(leaf)

    roots.sort(key=lambda n: _sort_section(n.section_ref))
    for ch in roots:
        ch.children.sort(key=lambda n: _sort_section(n.section_ref))
    return roots


def _sort_section(ref: str) -> tuple[int, ...]:
    parts = [p for p in ref.replace(".", " ").split() if p.isdigit()]
    return tuple(int(p) for p in parts) if parts else (0,)
