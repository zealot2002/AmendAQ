"""Backward-compatible import path."""
from __future__ import annotations

from amendaq.llm.openai_compat import OpenAICompatLLM

OllamaLLM = OpenAICompatLLM

__all__ = ["OllamaLLM", "OpenAICompatLLM"]
