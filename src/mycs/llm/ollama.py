"""Backward-compatible import path."""
from __future__ import annotations

from mycs.llm.openai_compat import OpenAICompatLLM

OllamaLLM = OpenAICompatLLM

__all__ = ["OllamaLLM", "OpenAICompatLLM"]
