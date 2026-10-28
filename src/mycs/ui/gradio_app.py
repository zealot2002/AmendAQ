from __future__ import annotations

import json
import os
from pathlib import Path

import gradio as gr

from mycs.agent.loop import AgentLoop
from mycs.ui import wiki_admin
from mycs.ui.workflow import (
    ingest_uploaded,
    mounts_table_md,
    publish_and_refresh,
    save_upload,
    workflow_markdown,
)
from mycs.llm.errors import LLMError
from mycs.llm.factory import create_llm
from mycs.log import get_logger
from mycs.net.localhost import ensure_localhost_no_proxy

logger = get_logger(__name__)

_UI_THEME = gr.themes.Soft()
_UI_CSS = ".workflow-box { border-left: 4px solid #6366f1; padding-left: 12px; }"


def _format_trace_md(result) -> str:
    lines = ["### Agent Trace", ""]
    step_icons = {
        "understand": "🧠",
        "toc": "📑",
        "plan": "📋",
        "tool": "🔧",
        "verify": "✓",
        "answer": "💬",
    }
    for event in result.trace:
        icon = step_icons.get(event.step, "•")
        lines.append(f"**{icon} {event.step}**")
        lines.append("```json")
        lines.append(json.dumps(event.payload, ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")
    lines.append(f"**verify** ok={result.verify.ok} — {result.verify.message}")
    return "\n".join(lines)


def chat_fn(message: str, case_id: str, graph_doc: str):
    message = (message or "").strip()
    if not message:
        return "", "请输入问题。", ""
    case_id = (case_id or "").strip() or None
    if graph_doc.strip():
        os.environ["MYCS_GRAPH_DOCUMENT"] = graph_doc.strip()
    logger.info("ui chat case_id=%s graph_doc=%s", case_id, graph_doc)
    try:
        loop = AgentLoop(llm=create_llm())
        result = loop.run(message, case_id=case_id)
    except LLMError as exc:
        err = f"**LLM 失败：**\n\n```\n{exc}\n```"
        return err, err, ""
    trace_dir = Path(os.environ.get("MYCS_TRACE_DIR", "data/traces"))
    path = AgentLoop.save_trace(result, trace_dir)
    footer = f"\n\n---\n_verify: {'通过' if result.verify.ok else '未通过'}_ · trace: `{path}`"
    return result.answer, _format_trace_md(result) + footer, result.answer


def main() -> None:
    ensure_localhost_no_proxy()
    default_doc = os.environ.get("MYCS_GRAPH_DOCUMENT", "")
    with gr.Blocks(title="mycs 知识库工作流") as demo:
        gr.Markdown(
            "# mycs — 从上传到问答\n"
            "完整链路：**上传 txt → Wiki 草稿 → 审核 → 发布 Wiki → Plan+TOC 问答**"
        )

        shared_doc = gr.State(value=default_doc)

        with gr.Tabs():
            with gr.Tab("① 工作流", id="workflow"):
                with gr.Row():
                    with gr.Column(scale=1):
                        wf_status = gr.Markdown(
                            value=workflow_markdown(default_doc),
                            elem_classes=["workflow-box"],
                        )
                        gr.Markdown("#### 企业 Wiki 挂载一览")
                        mounts_md = gr.Markdown(value=mounts_table_md())
                        refresh_mounts = gr.Button("刷新挂载列表", size="sm")
                    with gr.Column(scale=1):
                        gr.Markdown("#### Step 1 · 上传")
                        doc_id_wf = gr.Textbox(
                            label="document_id",
                            placeholder="例如 xinghe_handbook",
                            value=default_doc,
                        )
                        file_up = gr.File(
                            label="上传员工手册 / 政策 .txt",
                            file_types=[".txt"],
                            type="filepath",
                        )
                        btn_upload = gr.Button("保存上传", variant="secondary")
                        gr.Markdown("#### Step 2 · 解析 Wiki 草稿")
                        btn_ingest = gr.Button("生成 Wiki 草稿（目录 + 图谱）", variant="secondary")
                        gr.Markdown("#### Step 4 · 发布 Wiki")
                        btn_publish = gr.Button("发布 Wiki（草稿→已发布）", variant="primary")
                        wf_log = gr.Markdown("")

                with gr.Accordion("Step 3 · 目录预览 / 编辑", open=True):
                    outline_wf = gr.Markdown()
                    with gr.Row():
                        node_id = gr.Textbox(label="node_id（从目录复制）")
                        node_title = gr.Textbox(label="title")
                    node_summary = gr.Textbox(label="summary", lines=2)
                    btn_save_node = gr.Button("保存节点编辑", size="sm")

                def _sync_doc(doc: str) -> str:
                    return doc.strip()

                def on_upload(file, doc):
                    wf, new_doc = save_upload(file, doc)
                    outline = wiki_admin._outline_md(new_doc, "上传后") if new_doc else ""
                    return wf, new_doc, outline, mounts_table_md()

                def on_ingest(doc):
                    combined, new_doc = ingest_uploaded(doc)
                    return combined, new_doc, combined, mounts_table_md()

                def on_publish(doc):
                    combined, new_doc = publish_and_refresh(doc)
                    os.environ["MYCS_GRAPH_DOCUMENT"] = new_doc
                    return combined, new_doc, combined, mounts_table_md()

                def on_save_node(nid, title, summary, doc):
                    wiki_admin.save_node_edit(nid, title, summary)
                    return wiki_admin._outline_md(doc, "已保存节点")

                btn_upload.click(
                    on_upload,
                    inputs=[file_up, doc_id_wf],
                    outputs=[wf_status, shared_doc, outline_wf, mounts_md],
                )
                btn_ingest.click(
                    on_ingest,
                    inputs=[doc_id_wf],
                    outputs=[wf_status, shared_doc, outline_wf, mounts_md],
                )
                btn_publish.click(
                    on_publish,
                    inputs=[doc_id_wf],
                    outputs=[wf_status, shared_doc, outline_wf, mounts_md],
                )
                btn_save_node.click(
                    on_save_node,
                    inputs=[node_id, node_title, node_summary, doc_id_wf],
                    outputs=[outline_wf],
                )
                refresh_mounts.click(lambda: mounts_table_md(), outputs=[mounts_md])
                demo.load(
                    lambda d: (
                        workflow_markdown(d),
                        wiki_admin._outline_md(d, "当前目录") if d else "",
                        mounts_table_md(),
                    ),
                    inputs=[doc_id_wf],
                    outputs=[wf_status, outline_wf, mounts_md],
                )

            with gr.Tab("② 问答", id="chat"):
                gr.Markdown("使用 **已发布** 的 document_id；Trace 含 toc → plan → tool → verify。")
                with gr.Row():
                    with gr.Column(scale=2):
                        chatbot = gr.Chatbot(label="对话", height=400)
                        msg = gr.Textbox(label="问题", placeholder="例如：年假结转上限是多少？")
                        case_id = gr.Textbox(
                            label="case_id（政务 demo 可选）",
                            placeholder="CASE-2026-001",
                        )
                        graph_doc = gr.Textbox(
                            label="graph document_id",
                            value=default_doc,
                        )
                        submit = gr.Button("发送", variant="primary")
                    with gr.Column(scale=1):
                        trace_out = gr.Markdown(label="Trace")

                def on_submit(message, cid, gdoc, history):
                    answer, trace_md, _ = chat_fn(message, cid, gdoc)
                    history = history or []
                    history = history + [(message, answer)]
                    return history, trace_md, ""

                submit.click(
                    on_submit,
                    inputs=[msg, case_id, graph_doc, chatbot],
                    outputs=[chatbot, trace_out, msg],
                )
                msg.submit(
                    on_submit,
                    inputs=[msg, case_id, graph_doc, chatbot],
                    outputs=[chatbot, trace_out, msg],
                )
                demo.load(lambda d: d, inputs=[shared_doc], outputs=[graph_doc])

            with gr.Tab("③ Wiki 审核（高级）", id="wiki"):
                gr.Markdown("CLI 路径 ingest、按路径刷新（与工作流上传目录等效）。")
                doc_id = gr.Textbox(label="document_id", value=default_doc)
                refresh = gr.Button("刷新目录")
                outline = gr.Markdown()
                txt_path = gr.Textbox(
                    label="服务器本地 txt 路径",
                    placeholder="docs/星河科技_中文员工手册_知识库测试.txt",
                )
                with gr.Row():
                    ingest_btn = gr.Button("解析 → Wiki 草稿")
                    publish_btn = gr.Button("发布 published", variant="primary")
                edit_out = gr.Textbox(label="保存结果")

                refresh.click(
                    lambda d: wiki_admin._outline_md(d.strip(), "目录"),
                    inputs=[doc_id],
                    outputs=[outline],
                )
                ingest_btn.click(
                    wiki_admin.ingest_and_draft,
                    inputs=[txt_path, doc_id],
                    outputs=[outline],
                )
                publish_btn.click(wiki_admin.publish_doc, inputs=[doc_id], outputs=[outline])

    port = int(os.environ.get("MYCS_UI_PORT", "7860"))
    demo.launch(
        server_name="127.0.0.1",
        server_port=port,
        theme=_UI_THEME,
        css=_UI_CSS,
    )


if __name__ == "__main__":
    main()
