#!/usr/bin/env python3
"""M0: verify Ollama OpenAI-compatible endpoint (used from M2)."""

from __future__ import annotations

import os
import sys

import httpx

DEFAULT_BASE = "http://localhost:11434/v1"


def main() -> int:
    base = os.environ.get("OPENAI_API_BASE", DEFAULT_BASE).rstrip("/")
    url = f"{base}/models"
    try:
        r = httpx.get(url, timeout=5.0)
        r.raise_for_status()
    except Exception as exc:
        print(f"joyjoy: Ollama check failed: {exc}", file=sys.stderr)
        print(f"  Expected GET {url}", file=sys.stderr)
        return 1
    print(f"joyjoy: Ollama reachable at {base}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
