from __future__ import annotations

import asyncio
import json
import os
import queue
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from mycs.agent.loop import AgentLoop
from mycs.models import TraceEvent
from mycs.db.connection import connect, get_db_path
from mycs.document_id import generate_document_id
from mycs.llm.errors import LLMError
from mycs.llm.factory import create_llm
from mycs.log import configure_logging, get_logger
from mycs.log_buffer import get_log_buffer, install_log_buffer_handler
from mycs.paths import runtime_paths
from mycs.ui import wiki_admin
from mycs.ui.active_document import resolve_active_document_id, set_active_document_id
from mycs.knowledge.service import ensure_database
from mycs.ui.workflow import (
    ingest_uploaded,
    save_upload_bytes,
    workflow_state,
)

configure_logging()
logger = get_logger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]


def _require_document_id(explicit: str = "") -> str:
    doc = (explicit or "").strip() or resolve_active_document_id()
    if not doc:
        raise HTTPException(400, "尚无文档，请先上传 .txt（document_id 将自动生成）")
    return doc


def create_app() -> FastAPI:
    buf = install_log_buffer_handler()
    paths = runtime_paths()
    logger.info("API create_app db=%s uploads=%s traces=%s kg=%s", paths["db"], paths["uploads"], paths["traces"], paths["kg"])
    logger.info("log buffer capacity=%s", os.environ.get("MYCS_LOG_BUFFER_SIZE", "2000"))

    app = FastAPI(title="mycs API", version="0.1.0")
    origins = os.environ.get(
        "MYCS_CORS_ORIGINS",
        "http://127.0.0.1:5180,http://localhost:5180",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_log_middleware(request: Request, call_next):
        t0 = time.perf_counter()
        logger.info("→ %s %s", request.method, request.url.path)
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("✗ %s %s unhandled error", request.method, request.url.path)
            raise
        ms = (time.perf_counter() - t0) * 1000
        logger.info("← %s %s status=%s %.1fms", request.method, request.url.path, response.status_code, ms)
        return response

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/context")
    def api_context() -> dict[str, Any]:
        from mycs.knowledge.service import KnowledgeService, ensure_database

        doc = resolve_active_document_id()
        paths = runtime_paths()
        title = ""
        if doc:
            ensure_database()
            svc = KnowledgeService()
            try:
                title = svc.document_display_title(document_id=doc)
            finally:
                svc.close()
        return {
            "document_id": doc,
            "document_title": title,
            "paths": paths,
            "log_buffer_size": buf._maxlen,
        }

    @app.get("/api/mounts")
    def list_mounts() -> dict[str, Any]:
        logger.info("list mounts")
        return wiki_admin.list_mounts()

    @app.get("/api/workflow/current")
    def workflow_current() -> dict[str, Any]:
        doc = resolve_active_document_id()
        return workflow_state(doc)

    @app.get("/api/workflow/{document_id}")
    def workflow(document_id: str) -> dict[str, Any]:
        return workflow_state(document_id)

    @app.post("/api/upload")
    async def upload(file: UploadFile = File(...)) -> dict[str, Any]:
        content = await file.read()
        name = file.filename or "upload.txt"
        result = save_upload_bytes(name, content)
        return result

    @app.post("/api/ingest")
    def ingest(body: DocumentBody | None = None) -> dict[str, Any]:
        explicit = (body.document_id if body else "") or ""
        doc = _require_document_id(explicit)
        logger.info("ingest document_id=%s", doc)
        ingest_uploaded(doc)
        return {
            "document_id": doc,
            "workflow": workflow_state(doc),
            "toc": wiki_admin.get_toc(doc),
        }

    @app.post("/api/ingest/path")
    def ingest_path(body: IngestPathBody) -> dict[str, Any]:
        path = Path(body.path)
        if not path.is_file():
            raise HTTPException(400, f"file not found: {body.path}")
        ensure_database()
        conn = connect(get_db_path())
        try:
            doc = (body.document_id or "").strip() or generate_document_id(path.name, conn)
        finally:
            conn.close()
        logger.info("ingest/path document_id=%s path=%s", doc, path)
        wiki_admin.ingest_and_draft(str(path), doc)
        set_active_document_id(doc)
        return {
            "document_id": doc,
            "workflow": workflow_state(doc),
            "toc": wiki_admin.get_toc(doc),
        }

    @app.post("/api/publish")
    def publish(body: DocumentBody | None = None) -> dict[str, Any]:
        explicit = (body.document_id if body else "") or ""
        doc = _require_document_id(explicit)
        logger.info("publish document_id=%s", doc)
        result = wiki_admin.publish_document(doc)
        if not result.get("ok"):
            raise HTTPException(404, result.get("message", "publish failed"))
        set_active_document_id(doc)
        return {
            "document_id": doc,
            "publish": result,
            "workflow": workflow_state(doc),
            "toc": wiki_admin.get_toc(doc),
        }

    @app.get("/api/toc/{document_id}")
    def toc(document_id: str) -> dict[str, Any]:
        doc = document_id.strip() or resolve_active_document_id()
        if not doc:
            raise HTTPException(400, "尚无 document_id")
        return wiki_admin.get_toc(doc)

    @app.patch("/api/nodes/{node_id}")
    def patch_node(node_id: str, body: NodePatchBody) -> dict[str, Any]:
        logger.info("patch node node_id=%s", node_id)
        return wiki_admin.save_node_edit(
            node_id,
            body.title or "",
            body.summary or "",
        )

    @app.post("/api/chat")
    def chat(body: ChatBody) -> dict[str, Any]:
        message = (body.message or "").strip()
        if not message:
            raise HTTPException(400, "message required")
        doc = (body.document_id or "").strip() or resolve_active_document_id()
        if not doc:
            raise HTTPException(400, "请先上传并发布文档后再问答")
        os.environ["MYCS_GRAPH_DOCUMENT"] = doc
        case_id = (body.case_id or "").strip() or None
        logger.info("chat start document_id=%s case_id=%s q_len=%s", doc, case_id, len(message))
        try:
            loop = AgentLoop(llm=create_llm())
            result = loop.run(message, case_id=case_id)
        except LLMError as exc:
            logger.error("chat llm error: %s", exc)
            raise HTTPException(502, str(exc)) from exc
        trace_dir = Path(os.environ.get("MYCS_TRACE_DIR", runtime_paths()["traces"]))
        trace_path = AgentLoop.save_trace(result, trace_dir)
        trace_steps = [e.step for e in result.trace]
        logger.info(
            "chat done verify_ok=%s trace_path=%s answer_len=%s trace_steps=%s",
            result.verify.ok,
            trace_path,
            len(result.answer),
            trace_steps,
        )
        payload = result.to_dict()
        payload["trace_path"] = str(trace_path)
        payload["document_id"] = doc
        return payload

    @app.post("/api/chat/stream")
    def chat_stream(body: ChatBody) -> StreamingResponse:
        message = (body.message or "").strip()
        if not message:
            raise HTTPException(400, "message required")
        doc = (body.document_id or "").strip() or resolve_active_document_id()
        if not doc:
            raise HTTPException(400, "请先上传并发布文档后再问答")
        case_id = (body.case_id or "").strip() or None
        logger.info("chat stream start document_id=%s q_len=%s", doc, len(message))

        event_q: queue.Queue[tuple[str, Any]] = queue.Queue()

        def on_event(ev: TraceEvent) -> None:
            if ev.step == "progress":
                event_q.put(("progress", ev.payload))
            else:
                event_q.put(("trace", ev.to_dict()))

        def worker() -> None:
            try:
                os.environ["MYCS_GRAPH_DOCUMENT"] = doc
                loop = AgentLoop(llm=create_llm())
                result = loop.run(message, case_id=case_id, on_event=on_event)
                trace_dir = Path(os.environ.get("MYCS_TRACE_DIR", runtime_paths()["traces"]))
                trace_path = AgentLoop.save_trace(result, trace_dir)
                payload = result.to_dict()
                payload["trace_path"] = str(trace_path)
                payload["document_id"] = doc
                event_q.put(("done", payload))
            except LLMError as exc:
                logger.error("chat stream llm error: %s", exc)
                event_q.put(("error", str(exc)))
            except Exception as exc:
                logger.exception("chat stream failed")
                event_q.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

        def generate():
            while True:
                kind, data = event_q.get()
                if kind == "progress":
                    line = json.dumps({"type": "progress", "payload": data}, ensure_ascii=False)
                    yield f"data: {line}\n\n"
                elif kind == "trace":
                    line = json.dumps({"type": "trace", "event": data}, ensure_ascii=False)
                    yield f"data: {line}\n\n"
                elif kind == "done":
                    line = json.dumps({"type": "done", "result": data}, ensure_ascii=False)
                    yield f"data: {line}\n\n"
                    break
                elif kind == "error":
                    line = json.dumps({"type": "error", "message": data}, ensure_ascii=False)
                    yield f"data: {line}\n\n"
                    break

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/api/logs")
    def logs_list(
        after_id: int = Query(0, ge=0),
        limit: int = Query(200, ge=1, le=1000),
        level: str | None = None,
        q: str | None = None,
        tail: bool = False,
    ) -> dict[str, Any]:
        buf = get_log_buffer()
        if tail:
            items, latest_id = buf.tail(limit=limit)
        else:
            items, latest_id = buf.query(after_id=after_id, limit=limit, level=level, q=q)
        return {"items": items, "latest_id": latest_id, "count": len(items), "paths": runtime_paths()}

    @app.delete("/api/logs")
    def logs_clear() -> dict[str, bool]:
        get_log_buffer().clear()
        logger.info("log buffer cleared by user")
        return {"ok": True}

    @app.get("/api/logs/stream")
    async def logs_stream(after_id: int = Query(0, ge=0)) -> StreamingResponse:
        buf = get_log_buffer()

        async def event_gen():
            cursor = after_id
            while True:
                batch = await asyncio.to_thread(lambda c=cursor: list(buf.wait_after(c, timeout=20.0)))
                if not batch:
                    yield ": keepalive\n\n"
                    continue
                for item in batch:
                    cursor = item.id
                    yield f"data: {json.dumps(item.to_dict(), ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    dist = _REPO_ROOT / "frontend" / "dist"
    if dist.is_dir():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=str(dist), html=True), name="spa")

    return app


class DocumentBody(BaseModel):
    document_id: str = ""


class IngestPathBody(BaseModel):
    path: str
    document_id: str = ""


class NodePatchBody(BaseModel):
    title: str | None = None
    summary: str | None = None


class ChatBody(BaseModel):
    message: str
    document_id: str = ""
    case_id: str = ""
