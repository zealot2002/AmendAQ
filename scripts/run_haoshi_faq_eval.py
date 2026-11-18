#!/usr/bin/env -S uv run python
"""Run 10 好势 FAQ questions; write data/eval/haoshi_faq_10q.json."""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mycs.env_loader import load_project_dotenv  # noqa: E402
from mycs.agent.loop import AgentLoop  # noqa: E402
from mycs.llm.factory import create_llm  # noqa: E402

load_project_dotenv()
os.environ.setdefault("MYCS_DB", str(ROOT / "data" / "mycs.db"))
os.environ.setdefault("MYCS_GRAPH_DOCUMENT", "faq")
os.environ.setdefault("MYCS_CHAT_SHOW_EVIDENCE", "0")

CASES = [
    ("T01-下载", "好势APP怎么下载？"),
    ("T02-账号", "手机号登录收不到验证码怎么办？"),
    ("T03-模拟选号", "模拟选号能直接在APP里买彩票吗？"),
    ("T04-代购", "店主一直不接单超过15分钟怎么办？"),
    ("T05-中奖", "中奖后多久必须兑奖？逾期会怎样？"),
    ("T06-积分", "积分会过期吗？有效期多长？"),
    ("T07-店主", "申请成为好势店主需要哪些资质？"),
    ("T08-店主单", "店主出票建档需要上传什么？"),
    ("T09-数据", "走势图能不能投屏到电视上？"),
    ("T10-客服", "怎么联系人工客服？什么情况下建议转人工？"),
]


def main() -> int:
    out_path = ROOT / "data" / "eval" / "haoshi_faq_10q.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()

    llm_backend = os.environ.get("MYCS_LLM") or ("glm" if os.environ.get("GLM_API_KEY") else "ollama")
    glm_model = os.environ.get("GLM_MODEL") or ""
    pause = float(os.environ.get("MYCS_EVAL_PAUSE_SEC", "3"))
    print(f"joyjoy: haoshi faq eval backend={llm_backend} model={glm_model or 'default'} pause={pause}s", flush=True)

    loop = AgentLoop(llm=create_llm())
    results: list[dict] = []

    for i, (tid, q) in enumerate(CASES, start=1):
        print(f"joyjoy: {i}/10 {tid} ...", flush=True)
        t0 = time.time()
        row: dict
        try:
            result = loop.run(q, case_id=None)
            trace_steps = [ev.step for ev in result.trace]
            row = {
                "id": tid,
                "question": q,
                "ok": result.verify.ok,
                "verify_checks": result.verify.checks,
                "answer_preview": result.answer[:500],
                "answer_user": result.answer,
                "seconds": round(time.time() - t0, 1),
                "trace_steps": trace_steps,
                "verify_message": result.verify.message,
            }
        except Exception as exc:
            row = {
                "id": tid,
                "question": q,
                "ok": False,
                "verify_checks": [],
                "answer_preview": "",
                "seconds": round(time.time() - t0, 1),
                "trace_steps": [],
                "error": str(exc),
            }
        results.append(row)
        print(
            f"joyjoy: {tid} verify_ok={row.get('ok')} preview={str(row.get('answer_preview',''))[:80]}",
            flush=True,
        )
        if i < len(CASES):
            time.sleep(pause)

    payload = {
        "ts": ts,
        "document_id": "faq",
        "llm": llm_backend,
        "model": glm_model or None,
        "verify_ok_count": sum(1 for r in results if r.get("ok")),
        "results": results,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"joyjoy: wrote {out_path} verify_ok={payload['verify_ok_count']}/10", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())