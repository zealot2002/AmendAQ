from __future__ import annotations

from pathlib import Path
from typing import Any

from mycs.ui.ingest_document import ingest_document_file
from mycs.knowledge.service import KnowledgeService, ensure_database
from mycs.log import get_logger

logger = get_logger(__name__)


def list_mounts() -> dict[str, Any]:
    ensure_database()
    svc = KnowledgeService()
    try:
        return svc.wiki_list_mounts()
    finally:
        svc.close()


def get_toc(document_id: str) -> dict[str, Any]:
    ensure_database()
    svc = KnowledgeService()
    try:
        from mycs.wiki.toc_query import fetch_nodes

        doc = document_id.strip()
        mounts = svc.wiki_list_mounts().get("mounts") or []
        mount = next((m for m in mounts if m["document_id"] == doc), None)
        # 管理台审核必须看到草稿；问答侧仍只读 published（allowed_statuses）
        nodes = fetch_nodes(
            svc._conn,
            document_id=doc,
            kinds=("chapter", "leaf"),
            statuses=("draft", "published"),
        )
        return {
            "document_id": doc,
            "mount": mount,
            "nodes": nodes,
            "count": len(nodes),
        }
    finally:
        svc.close()


def _outline_md(document_id: str, status_note: str) -> str:
    data = get_toc(document_id)
    lines = [f"**{status_note}** · nodes={data.get('count', 0)}", ""]
    mount = data.get("mount")
    if mount:
        lines.append(
            f"mount `{mount['mount_id']}` · draft={mount.get('draft_count')} · "
            f"published_leaves={mount.get('published_leaves')}"
        )
        lines.append("")
    for n in data.get("nodes") or []:
        indent = "  " * max(0, int(n.get("depth", 0)) - 2)
        sec = n.get("section_ref") or ""
        lines.append(f"{indent}- [{sec}] {n.get('title')} `{n.get('node_id')}`")
    return "\n".join(lines) if lines else "（无目录节点，请先 ingest）"


def ingest_and_draft(file_path: str, doc_id: str) -> str:
    path = Path(file_path)
    if not path.is_file():
        return f"文件不存在: {file_path}"
    ensure_database()
    document_id = doc_id or path.stem
    logger.info("wiki ingest_and_draft path=%s document_id=%s", path, document_id)
    ingest_document_file(path, document_id=document_id)
    from mycs.ui.terminology import WIKI_DRAFT, WIKI_PUBLISHED

    return _outline_md(doc_id or path.stem, f"{WIKI_DRAFT}已生成（尚未{WIKI_PUBLISHED}）")


def publish_document(document_id: str) -> dict[str, Any]:
    ensure_database()
    svc = KnowledgeService()
    try:
        mounts = svc.wiki_list_mounts().get("mounts") or []
        mount = next((m for m in mounts if m["document_id"] == document_id), None)
        if not mount:
            return {"ok": False, "message": f"未找到 mount: {document_id}"}
        result = svc.wiki_publish_mount(mount["mount_id"], actor="vue-admin")
        logger.info("wiki publish document_id=%s mount=%s result=%s", document_id, mount["mount_id"], result)
        return {"ok": True, **result}
    finally:
        svc.close()


def publish_doc(document_id: str) -> str:
    result = publish_document(document_id)
    if not result.get("ok"):
        return result.get("message", "publish failed")
    from mycs.ui.terminology import WIKI, WIKI_PUBLISHED

    return _outline_md(document_id, f"{WIKI}已{WIKI_PUBLISHED} nodes={result.get('published_nodes')}")


def save_node_edit(
    node_id: str,
    title: str,
    summary: str,
    body: str | None = None,
) -> dict[str, Any]:
    if not node_id.strip():
        return {"ok": False, "message": "请填写 node_id"}
    ensure_database()
    svc = KnowledgeService()
    try:
        svc.wiki_update_node(
            node_id.strip(),
            title=title or None,
            summary=summary or None,
            body=body,
        )
        return {"ok": True, "node_id": node_id.strip()}
    finally:
        svc.close()
