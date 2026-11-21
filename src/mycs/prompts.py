"""Load system prompts from config/prompts.txt. That file is the review copy."""

from __future__ import annotations

import re
from pathlib import Path


def _prompts_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "prompts.txt"

_HEADER = re.compile(r"^\[([a-z0-9_]+)\]\s*$")


def load_prompts() -> dict[str, str]:
    path = _prompts_path()
    text = path.read_text(encoding="utf-8")
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        matched = _HEADER.match(line)
        if matched:
            current = matched.group(1)
            sections[current] = []
            continue
        if current is None:
            continue
        sections[current].append(line)
    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


def prompt(name: str, **values: object) -> str:
    prompts = load_prompts()
    if name not in prompts:
        known = ", ".join(sorted(prompts))
        raise KeyError(f"prompt {name!r} not in config/prompts.txt ({known})")
    text = prompts[name]
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", "" if value is None else str(value))
    return text


def prompt_if(name: str) -> str | None:
    return load_prompts().get(name)
