from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from amendaq.agent.loop import AgentLoop
from amendaq.db.bootstrap import bootstrap_database
from amendaq.db.reset import reset_runtime_data
from amendaq.graph.extract import ingest_txt_file
from amendaq.llm.errors import LLMError
from amendaq.llm.factory import create_llm
from amendaq.knowledge.service import ensure_database
from amendaq.log import get_logger

logger = get_logger(__name__)

REFERENCE_QUESTION = (
    "我的办件 CASE-2026-001 为什么还在预审？依据哪条时限规定？"
)
REFERENCE_CASE_ID = "CASE-2026-001"
POLICY_ONLY_QUESTION = "居住证续签能否线上办理？"


def _cmd_bootstrap() -> int:
    from amendaq.db.reset import SKIP_DEMO_MARKER

    SKIP_DEMO_MARKER.unlink(missing_ok=True)
    path = bootstrap_database()
    print(f"joyjoy: knowledge database ready at {path}")
    return 0


def _cmd_reset_data(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="AmendAQ reset-data")
    parser.add_argument(
        "--with-demo",
        action="store_true",
        help="After reset, reload demo handbook + gov reference (same as bootstrap)",
    )
    args = parser.parse_args(argv)
    stats = reset_runtime_data(skip_demo_seed=not args.with_demo)
    if args.with_demo:
        bootstrap_database()
        print("joyjoy: reset complete + demo seed loaded")
    else:
        print("joyjoy: reset complete — empty schema, no demo seed")
    print(f"joyjoy: removed artifacts ≈ {stats['files_removed']} files under data/")
    print(f"joyjoy: db at {stats['db']}")
    print("joyjoy: next: export AMENDAQ_GRAPH_DOCUMENT=your_doc && uv run amendaq ingest txt ... --publish")
    return 0


def _cmd_wiki_audit(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="AmendAQ wiki audit")
    parser.add_argument("--doc-id", dest="doc_id", required=True)
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write JSON report (default: data/audit/<doc_id>_rigor.json)",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip LLM pass (deterministic checks only)",
    )
    args = parser.parse_args(argv)
    ensure_database()
    from amendaq.db.connection import connect, get_db_path
    from amendaq.wiki.rigor_audit import audit_wiki_document, write_audit_json

    conn = connect(get_db_path())
    try:
        llm = None if args.no_llm else create_llm()
        report = audit_wiki_document(conn, args.doc_id, llm=llm)
    finally:
        conn.close()
    out = args.out or Path("data/audit") / f"{args.doc_id}_rigor.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    write_audit_json(report, out)
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    print(f"joyjoy: wrote {out}")
    return 0 if report.ok else 2


def _cmd_wiki_publish(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="AmendAQ wiki publish")
    parser.add_argument("--doc-id", dest="doc_id", required=True)
    args = parser.parse_args(argv)
    ensure_database()
    from amendaq.db.connection import connect, get_db_path
    from amendaq.wiki.toc_persist import publish_mount

    mount_id = f"mount_{args.doc_id}"
    conn = connect(get_db_path())
    try:
        result = publish_mount(conn, mount_id, actor="cli")
        conn.commit()
    finally:
        conn.close()
    print(f"joyjoy: published {result}")
    return 0


def _cmd_ingest_txt(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="AmendAQ ingest txt")
    parser.add_argument("path", type=Path, help="Path to .txt document")
    parser.add_argument("--doc-id", dest="doc_id", default=None)
    parser.add_argument(
        "--section-only",
        action="store_true",
        help="Skip TOC-first; section graph only (dev)",
    )
    parser.add_argument(
        "--enrich-graph",
        action="store_true",
        help="LLM full-graph extract instead of TOC-first (legacy)",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="After ingest, publish wiki TOC for this document",
    )
    args = parser.parse_args(argv)
    if not args.path.is_file():
        print(f"file not found: {args.path}", file=sys.stderr)
        return 1
    ensure_database()
    graph = ingest_txt_file(
        args.path,
        document_id=args.doc_id,
        use_section_builder=args.section_only,
        enrich_graph=args.enrich_graph,
    )
    doc = graph.document_id
    print(
        f"joyjoy: ingested document_id={doc} entities={len(graph.entities)} "
        f"(Wiki 草稿 — 请审核后 publish)"
    )
    if args.publish:
        from amendaq.db.connection import connect, get_db_path
        from amendaq.wiki.toc_persist import publish_mount

        conn = connect(get_db_path())
        try:
            mount_id = f"mount_{doc}"
            publish_mount(conn, mount_id)
            conn.commit()
            print(f"joyjoy: published wiki mount={mount_id}")
        finally:
            conn.close()
    print(f"json: data/kg/{doc}.json")
    return 0


def _cmd_ingest_canonical(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="AmendAQ ingest canonical")
    parser.add_argument(
        "path",
        type=Path,
        help="Path to data/ingest/<doc_id>.canonical.json",
    )
    parser.add_argument("--doc-id", dest="doc_id", default=None)
    parser.add_argument(
        "--publish",
        action="store_true",
        help="After ingest, publish wiki TOC for this document",
    )
    args = parser.parse_args(argv)
    if not args.path.is_file():
        print(f"file not found: {args.path}", file=sys.stderr)
        return 1
    ensure_database()
    try:
        from amendaq.wiki.ingest_compile import ingest_canonical_json

        meta = ingest_canonical_json(
            args.path,
            document_id=args.doc_id,
            publish=args.publish,
        )
    except (ValueError, FileNotFoundError) as exc:
        logger.error("ingest canonical failed: %s", exc)
        print(f"失败: {exc}", file=sys.stderr)
        return 2
    doc = meta["document_id"]
    print(
        f"joyjoy: imported canonical document_id={doc} "
        f"chapters={meta.get('chapters')} leaves={meta.get('leaves')} "
        f"draft_nodes={meta.get('draft_nodes')}"
    )
    if args.publish:
        print(f"joyjoy: published mount_{doc}")
    return 0


def _cmd_ingest_compile(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="AmendAQ ingest compile")
    parser.add_argument("path", type=Path, help="Path to .md or .txt FAQ / document")
    parser.add_argument("--doc-id", dest="doc_id", default=None)
    parser.add_argument(
        "--publish",
        action="store_true",
        help="After ingest, publish wiki TOC for this document",
    )
    parser.add_argument(
        "--canonical-out",
        type=Path,
        default=None,
        help="Override path for canonical JSON (default data/ingest/<doc_id>.canonical.json)",
    )
    args = parser.parse_args(argv)
    if not args.path.is_file():
        print(f"file not found: {args.path}", file=sys.stderr)
        return 1
    ensure_database()
    try:
        from amendaq.wiki.ingest_compile import ingest_compile_file

        meta = ingest_compile_file(
            args.path,
            document_id=args.doc_id,
            llm=None,
            rules_only=True,
            canonical_out=args.canonical_out,
            publish=args.publish,
        )
    except ValueError as exc:
        logger.error("ingest compile validation: %s", exc)
        print(f"校验失败: {exc}", file=sys.stderr)
        return 2
    doc = meta["document_id"]
    print(
        f"joyjoy: compiled document_id={doc} chapters={meta.get('chapters')} "
        f"leaves={meta.get('leaves')} draft_nodes={meta.get('draft_nodes')} "
        f"(Wiki 草稿 — 请审核后 publish)"
    )
    if meta.get("ingest_notes"):
        print("joyjoy: ingest_notes:")
        for note in meta["ingest_notes"]:
            print(f"  - {note}")
    print(f"canonical: {meta.get('canonical_json')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(argv) if argv is not None else sys.argv[1:]
    if argv and argv[0] in ("reset", "reset-data"):
        return _cmd_reset_data(argv[1:])
    if argv and argv[0] == "bootstrap":
        return _cmd_bootstrap()
    if len(argv) >= 2 and argv[0] == "ingest" and argv[1] == "handbook":
        return _cmd_bootstrap()
    if len(argv) >= 2 and argv[0] == "ingest" and argv[1] == "txt":
        return _cmd_ingest_txt(argv[2:])
    if len(argv) >= 2 and argv[0] == "ingest" and argv[1] == "compile":
        return _cmd_ingest_compile(argv[2:])
    if len(argv) >= 2 and argv[0] == "ingest" and argv[1] == "canonical":
        return _cmd_ingest_canonical(argv[2:])
    if len(argv) >= 2 and argv[0] == "wiki" and argv[1] == "publish":
        return _cmd_wiki_publish(argv[2:])
    if len(argv) >= 2 and argv[0] == "wiki" and argv[1] == "audit":
        return _cmd_wiki_audit(argv[2:])

    parser = argparse.ArgumentParser(description="AmendAQ Knowledge Agent (Ollama)")
    parser.add_argument("question", nargs="?", help="User question")
    parser.add_argument("--case-id", dest="case_id", default=None)
    parser.add_argument(
        "--demo",
        choices=["case", "policy"],
        help="Gov reference demo (requires Ollama)",
    )
    parser.add_argument(
        "--no-save-trace",
        action="store_true",
        help="Do not write JSON trace under data/traces",
    )
    args = parser.parse_args(argv)

    ensure_database()

    question = args.question
    case_id = args.case_id
    if args.demo == "case":
        question = REFERENCE_QUESTION
        case_id = case_id or REFERENCE_CASE_ID
    elif args.demo == "policy":
        question = POLICY_ONLY_QUESTION
        case_id = None

    if not question:
        parser.print_help()
        print("\nSetup:", file=sys.stderr)
        print("  uv run amendaq bootstrap", file=sys.stderr)
        print("  export AMENDAQ_GRAPH_DOCUMENT=<doc_id>", file=sys.stderr)
        print("  uv run amendaq ingest txt your.txt --doc-id <doc_id>", file=sys.stderr)
        print("  uv run amendaq ingest compile handbook.md --doc-id <doc_id>", file=sys.stderr)
        print("  uv run amendaq ingest canonical data/ingest/faq.canonical.json --doc-id faq --publish", file=sys.stderr)
        return 1

    try:
        loop = AgentLoop(llm=create_llm())
        result = loop.run(question, case_id=case_id)
    except LLMError as exc:
        logger.error("llm failed: %s", exc)
        print(f"LLM 失败: {exc}", file=sys.stderr)
        return 3

    print(result.answer)
    print()
    print(f"[耗时 {result.elapsed_seconds:.1f}s]")
    print(f"[verify ok={result.verify.ok}] {result.verify.message}")

    if not args.no_save_trace:
        trace_dir = Path(os.environ.get("AMENDAQ_TRACE_DIR", "data/traces"))
        path = AgentLoop.save_trace(result, trace_dir)
        print(f"[trace] {path}")

    return 0 if result.verify.ok else 2


if __name__ == "__main__":
    sys.exit(main())
