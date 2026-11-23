from __future__ import annotations

import re
from pathlib import Path

_DOC_ID_RE = re.compile(r"^doc_[a-f0-9]+$", re.I)


def strip_file_ext(name: str) -> str:
    s = (name or "").strip()
    for ext in (".txt", ".md", ".markdown", ".pdf"):
        if s.lower().endswith(ext):
            return s[: -len(ext)].strip()
    return s


def is_technical_document_label(document_id: str, label: str) -> bool:
    doc = (document_id or "").strip()
    clean = strip_file_ext(label)
    if not clean:
        return True
    if doc and clean == doc:
        return True
    if doc and clean.startswith(doc):
        return True
    if _DOC_ID_RE.match(clean):
        return True
    return False


def title_from_handbook_text(text: str, *, max_scan: int = 4000) -> str:
    chunk = (text or "")[:max_scan]
    lines = [ln.strip() for ln in chunk.splitlines() if ln.strip()]
    for i, s in enumerate(lines):
        if s.startswith("#"):
            return s.lstrip("#").strip()[:120]
        if "员工手册" in s:
            return s[:120]
        if i + 1 < len(lines) and lines[i + 1] == "员工手册":
            return f"{s}员工手册"[:120]
        if "手册" in s and len(s) <= 80:
            return s[:120]
    for s in lines[:8]:
        if len(s) >= 4 and len(s) <= 80 and not s.startswith("第") and "。" not in s[:20]:
            if s.startswith("版本") or s.startswith("生效") or s.startswith("说明"):
                continue
            return s[:120]
    return ""


def infer_handbook_display_title(
    *,
    document_id: str,
    path: Path | None = None,
    text: str | None = None,
    stored_title: str | None = None,
) -> str:
    """Pick a 小白-friendly handbook name."""
    doc = (document_id or "").strip()
    candidates: list[str] = []
    if stored_title:
        candidates.append(stored_title.strip())
    if path and path.is_file():
        candidates.append(path.stem)
        candidates.append(path.name)
        if text is None:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = None
    if text:
        from_text = title_from_handbook_text(text)
        if from_text:
            candidates.insert(0, from_text)
    for raw in candidates:
        label = strip_file_ext(raw)
        if label and not is_technical_document_label(doc, label):
            return label
    if text:
        from_text = title_from_handbook_text(text)
        if from_text and not is_technical_document_label(doc, from_text):
            return from_text
    return "员工手册"
