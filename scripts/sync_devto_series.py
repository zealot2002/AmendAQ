#!/usr/bin/env python3
"""Sync docs/posts/0*.md to Dev.to series articles (5097601–5097606)."""
from __future__ import annotations

import re
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
GITHUB = "https://github.com/zealot2002/AmendAQ"
SERIES_URL = "https://dev.to/zealot2002/series/47234"

# Dev.to-hosted screenshots (rename 2025-11; see docs/posts/images/)
IMAGE_CDN: dict[str, str] = {
    "library-list.png": "https://dev-to-uploads.s3.us-east-2.amazonaws.com/uploads/articles/g9i48809wx9ih0g1dvux.png",
    "edit-one-aq.png": "https://dev-to-uploads.s3.us-east-2.amazonaws.com/uploads/articles/nse9jskrbqtmdhvikdbv.png",
    "import-draft.png": "https://dev-to-uploads.s3.us-east-2.amazonaws.com/uploads/articles/sunqu80zqkw48f9xrfn7.png",
    "answer-and-trace.png": "https://dev-to-uploads.s3.us-east-2.amazonaws.com/uploads/articles/jmvfk7m12rw0zdobkxal.png",
    "pick-ids.png": "https://dev-to-uploads.s3.us-east-2.amazonaws.com/uploads/articles/ysg82iint17otau7oa7p.png",
    "switch-library.png": "https://dev-to-uploads.s3.us-east-2.amazonaws.com/uploads/articles/oa6p80lq6jzz06e6r1kg.png",
}

ARTICLES: dict[int, tuple[str, dict[str, str]]] = {
    5097601: (
        "01-why-amendaq.md",
        {
            "02-what-amendaq-is.md": "https://dev.to/zealot2002/amendaq-zai-mycs-li-shi-ben-ke-yi-gai-de-wen-da-539",
            "03-when-to-choose-amendaq.md": "https://dev.to/zealot2002/tong-ti-dui-zhao-zhi-hou-you-xie-chang-jing-ke-yi-xuan-ze-amendaq-1dhk",
        },
    ),
    5097602: (
        "02-what-amendaq-is.md",
        {
            "01-why-amendaq.md": "https://dev.to/zealot2002/ru-guo-tiao-zhi-du-ke-yi-gai-wan-jiu-sheng-xiao-huan-yao-xian-xiang-liang-hua-ma-501b",
            "03-when-to-choose-amendaq.md": "https://dev.to/zealot2002/tong-ti-dui-zhao-zhi-hou-you-xie-chang-jing-ke-yi-xuan-ze-amendaq-1dhk",
        },
    ),
    5097606: (
        "03-when-to-choose-amendaq.md",
        {
            "02-what-amendaq-is.md": "https://dev.to/zealot2002/amendaq-zai-mycs-li-shi-ben-ke-yi-gai-de-wen-da-539",
        },
    ),
}


def devify(fn: str, peer_links: dict[str, str]) -> tuple[str, str]:
    raw = (ROOT / "docs/posts" / fn).read_text(encoding="utf-8")
    title = raw.splitlines()[0].removeprefix("# ").strip()
    body = raw.replace("](../SERIES.md)", f"]({SERIES_URL})")
    for other, url in peer_links.items():
        body = body.replace(f"](./{other})", f"]({url})")
    for name, cdn in IMAGE_CDN.items():
        body = body.replace(f"](./images/{name})", f"]({cdn})")
    body = re.sub(r"\]\(\.\./([^)]+)\)", rf"]({GITHUB}/blob/main/docs/\1)", body)
    body = re.sub(
        r"\]\(\./(?!images/)([^)]+)\)",
        rf"]({GITHUB}/blob/main/docs/posts/\1)",
        body,
    )
    if not body.lstrip().startswith("---"):
        body = f"---\nseries: AmendAQ, a better RAG?\n---\n\n{body}"
    return title, body


def main() -> None:
    env = Path("/Users/zzy/study/opp/.env").read_text(encoding="utf-8")
    key = next(
        line.split("=", 1)[1].strip().strip('"').strip("'")
        for line in env.splitlines()
        if line.startswith("DEVTO_API_KEY=")
    )
    headers = {
        "api-key": key,
        "accept": "application/vnd.forem.api-v1+json",
        "content-type": "application/json",
    }
    with httpx.Client(timeout=180, headers=headers) as client:
        for aid, (fn, peers) in ARTICLES.items():
            title, body = devify(fn, peers)
            r = client.put(
                f"https://dev.to/api/articles/{aid}",
                json={
                    "article": {
                        "title": title,
                        "body_markdown": body,
                        "published": True,
                        "series": "AmendAQ, a better RAG?",
                        "tags": ["rag", "ai", "opensource"],
                    }
                },
            )
            print(aid, fn, r.status_code, r.json().get("url") if r.status_code < 400 else r.text[:400])


if __name__ == "__main__":
    main()