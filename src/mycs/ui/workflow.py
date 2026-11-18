from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from mycs.db.connection import connect, get_db_path
from mycs.document_id import generate_document_id
from mycs.knowledge.service import KnowledgeService, ensure_database
from mycs.ui.ingest_document import ingest_document_file, run_ingest_uploaded
from mycs.log import get_logger
from mycs.log_detail import log_step
from mycs.paths import uploads_dir
from mycs.ui import wiki_admin
from mycs.ui.active_document import resolve_active_document_id, set_active_document_id
from mycs.ui.terminology import STEP_LABELS_UI, WIKI, WIKI_DRAFT, WIKI_PUBLISHED

logger = get_logger(__name__)

STEP_LABELS = [
    "upload",
    "ingest_draft",
    "review",
    "publish",
    "qa_ready",
]


def _ensure_upload_dir() -> Path:
    d = uploads_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def workflow_state(document_id: str) -> dict[str, Any]:
    """Derive pipeline step from DB."""
    doc = (document_id or "").strip() or resolve_active_document_id()
    state: dict[str, Any] = {
        "document_id": doc,
        "uploaded_path": None,
        "draft_nodes": 0,
        "published_leaves": 0,
        "mount_id": None,
        "current_step": "upload",
        "steps": {k: "pending" for k in STEP_LABELS},
    }
    if not doc:
        return state

    upload_glob = list(_ensure_upload_dir().glob(f"{doc}*"))
    if upload_glob:
        state["uploaded_path"] = str(upload_glob[-1])
        state["steps"]["upload"] = "done"

    ensure_database()
    svc = KnowledgeService()
    try:
        mounts = svc.wiki_list_mounts().get("mounts") or []
        mount = next((m for m in mounts if m["document_id"] == doc), None)
        if mount:
            state["mount_id"] = mount["mount_id"]
            state["document_title"] = str(mount.get("display_title") or "").strip() or doc
            state["draft_nodes"] = int(mount.get("draft_count") or 0)
            state["published_leaves"] = int(mount.get("published_leaves") or 0)
            if state["draft_nodes"] > 0:
                state["steps"]["ingest_draft"] = "done"
                state["steps"]["review"] = "current"
                state["current_step"] = "review"
            if state["published_leaves"] > 0:
                state["steps"]["ingest_draft"] = "done"
                state["steps"]["review"] = "done"
                state["steps"]["publish"] = "done"
                state["steps"]["qa_ready"] = "done"
                state["current_step"] = "qa_ready"
            elif state["draft_nodes"] > 0:
                state["steps"]["ingest_draft"] = "done"
                state["current_step"] = "review"
                state["steps"]["review"] = "current"
        elif state["steps"]["upload"] == "done":
            state["steps"]["ingest_draft"] = "current"
            state["current_step"] = "ingest_draft"
        if not state.get("document_title") and doc:
            state["document_title"] = svc.document_display_title(document_id=doc)
    finally:
        svc.close()
    logger.debug("workflow_state doc=%s step=%s", doc, state["current_step"])
    return state


def save_upload_bytes(filename: str, content: bytes) -> dict[str, Any]:
    ensure_database()
    conn = connect(get_db_path())
    try:
        doc = generate_document_id(filename, conn)
    finally:
        conn.close()
    suffix = Path(filename or "upload.txt").suffix or ".txt"
    dest = _ensure_upload_dir() / f"{doc}{suffix}"
    dest.write_bytes(content)
    from mycs.document_display import infer_handbook_display_title
    from mycs.wiki.toc_persist import ensure_mount

    try:
        text = dest.read_text(encoding="utf-8")
        title = infer_handbook_display_title(
            document_id=doc,
            path=dest,
            text=text,
            stored_title=filename,
        )
        conn = connect(get_db_path())
        try:
            ensure_mount(conn, document_id=doc, display_title=title)
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("joyjoy: upload ensure_mount failed doc=%s: %s", doc, exc)

    set_active_document_id(doc)
    logger.info("upload saved document_id=%s path=%s bytes=%s", doc, dest, len(content))
    return {
        "document_id": doc,
        "path": str(dest),
        "workflow": workflow_state(doc),
    }


def save_upload(file_obj: Any, document_id: str) -> tuple[str, str]:
    doc = (document_id or "").strip()
    if file_obj is None:
        return workflow_markdown(doc, "❌ 请选择文件"), ""
    path = Path(file_obj.name if hasattr(file_obj, "name") else str(file_obj))
    if not path.is_file():
        return workflow_markdown(doc, "❌ 无法读取文件"), ""
    result = save_upload_bytes(path.name, path.read_bytes())
    return workflow_markdown(result["document_id"], f"✅ 已保存到 `{result['path']}`"), result["document_id"]


def ingest_uploaded(document_id: str) -> tuple[str, str]:
    doc = (document_id or "").strip() or resolve_active_document_id()
    ensure_database()
    try:
        run_ingest_uploaded(doc)
    except ValueError as exc:
        return workflow_markdown(doc, f"❌ {exc}"), doc
    outline = wiki_admin._outline_md(doc, f"{WIKI_DRAFT}已生成")
    header = workflow_markdown(doc, "✅ Ingest 完成")
    return header + "\n\n---\n\n" + outline, doc


def publish_and_refresh(document_id: str) -> tuple[str, str]:
    doc = (document_id or "").strip() or resolve_active_document_id()
    if not doc:
        return workflow_markdown("", "❌ 尚无文档可发布"), doc
    logger.info("publish start document_id=%s", doc)
    md = wiki_admin.publish_doc(doc)
    set_active_document_id(doc)
    header = workflow_markdown(doc, "✅ 已发布，问答可用")
    logger.info("publish done document_id=%s", doc)
    return header + "\n\n---\n\n" + md, doc


def workflow_markdown(document_id: str, extra: str = "") -> str:
    st = workflow_state(document_id)
    icons = {"pending": "⬜", "current": "🔄", "done": "✅"}
    titles = STEP_LABELS_UI
    lines = ["### 知识库工作流", ""]
    if extra:
        lines.append(extra)
        lines.append("")
    lines.append(f"**document_id**：`{st['document_id'] or '（上传后自动生成）'}`")
    if st.get("mount_id"):
        lines.append(
            f"**mount**：`{st['mount_id']}` · {WIKI_DRAFT}节点 {st['draft_nodes']} · "
            f"{WIKI_PUBLISHED}条目 {st['published_leaves']}"
        )
    if st.get("uploaded_path"):
        lines.append(f"**上传文件**：`{st['uploaded_path']}`")
    lines.append("")
    for key in STEP_LABELS:
        status = st["steps"].get(key, "pending")
        lines.append(f"{icons.get(status, '⬜')} {titles[key]}")
    lines.append("")
    nxt = {
        "upload": "请上传 .txt 或 .md",
        "ingest_draft": "点击「整理目录」生成 Wiki 草稿",
        "review": f"检查下方{WIKI}树（当前为{WIKI_DRAFT}），编辑后发布",
        "publish": f"点击「发布 {WIKI}」",
        "qa_ready": "切换到「问答」Tab 提问",
    }
    lines.append(f"**下一步**：{nxt.get(st['current_step'], '—')}")
    return "\n".join(lines)


def mounts_table_md() -> str:
    ensure_database()
    svc = KnowledgeService()
    try:
        mounts = svc.wiki_list_mounts().get("mounts") or []
    finally:
        svc.close()
    if not mounts:
        return "（尚无挂载文档）"
    lines = [
        f"| document_id | mount | {WIKI_DRAFT}节点 | {WIKI_PUBLISHED}条目 |",
        "|---|---|---|---|",
    ]
    for m in mounts:
        lines.append(
            f"| `{m['document_id']}` | `{m['mount_id']}` | {m.get('draft_count', 0)} | {m.get('published_leaves', 0)} |"
        )
    return "\n".join(lines)
