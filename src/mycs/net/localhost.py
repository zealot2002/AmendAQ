from __future__ import annotations

import os


def ensure_localhost_no_proxy() -> None:
    """Keep loopback out of HTTP(S)_PROXY so local services (Gradio, uvicorn) start cleanly."""
    extra = ("127.0.0.1", "localhost", "::1")
    for key in ("NO_PROXY", "no_proxy"):
        cur = os.environ.get(key, "")
        parts = [p.strip() for p in cur.split(",") if p.strip()]
        for host in extra:
            if host not in parts:
                parts.append(host)
        os.environ[key] = ",".join(parts)
