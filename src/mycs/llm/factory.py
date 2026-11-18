from __future__ import annotations

import os

from mycs.llm.base import AgentLLM
from mycs.llm.openai_compat import OpenAICompatLLM
from mycs.log import get_logger

logger = get_logger(__name__)

GLM_DEFAULT_BASE = "https://open.bigmodel.cn/api/paas/v4"
GLM_DEFAULT_MODEL = "glm-4-flash"
GROQ_DEFAULT_BASE = "https://api.groq.com/openai/v1"
# Groq Console 免费档常见 ID（2026-10）；更强可设 openai/gpt-oss-120b
GROQ_DEFAULT_MODEL = "openai/gpt-oss-20b"


def create_llm(backend: str | None = None) -> AgentLLM:
    name = (backend or os.environ.get("MYCS_LLM") or "").strip().lower()
    if not name:
        if _glm_api_key():
            name = "glm"
        elif _groq_api_key():
            name = "groq"
        else:
            name = "ollama"

    if name == "groq":
        key = _groq_api_key()
        if not key:
            raise RuntimeError("MYCS_LLM=groq but GROQ_API_KEY is not set")
        model = (
            os.environ.get("GROQ_MODEL")
            or os.environ.get("OPENAI_MODEL")
            or GROQ_DEFAULT_MODEL
        )
        base = os.environ.get("GROQ_API_BASE", GROQ_DEFAULT_BASE).rstrip("/")
        logger.info("joyjoy: using Groq model=%s base=%s", model, base)
        return OpenAICompatLLM(
            base_url=base,
            api_key=key,
            model=model,
            provider="openai",
            trust_env=True,
        )

    if name in ("glm", "zhipu", "zhipuai", "bigmodel"):
        key = _glm_api_key()
        if not key:
            raise RuntimeError("MYCS_LLM=glm but GLM_API_KEY (or ZHIPUAI_API_KEY) is not set")
        model = (
            os.environ.get("GLM_MODEL")
            or os.environ.get("OPENAI_MODEL")
            or GLM_DEFAULT_MODEL
        )
        base = os.environ.get("GLM_API_BASE", GLM_DEFAULT_BASE).rstrip("/")
        logger.info("joyjoy: using GLM model=%s base=%s", model, base)
        return OpenAICompatLLM(
            base_url=base,
            api_key=key,
            model=model,
            provider="openai",
            trust_env=True,
        )

    if name in ("openai", "vllm", "compat"):
        base = os.environ.get("OPENAI_API_BASE", "http://192.168.10.175:8000/v1").rstrip("/")
        # 无 API key 的兼容网关：占位即可，多数服务会忽略 Authorization
        key = os.environ.get("OPENAI_API_KEY")
        if key is None or not str(key).strip():
            key = "EMPTY"
        model = os.environ.get("OPENAI_MODEL", "Qwen3.6")
        logger.info("joyjoy: using OpenAI-compat model=%s base=%s", model, base)
        return OpenAICompatLLM(
            base_url=base,
            api_key=key,
            model=model,
            provider="openai",
            trust_env=False,
        )

    if name == "ollama":
        logger.info("joyjoy: using Ollama")
        return OpenAICompatLLM(
            base_url=os.environ.get("OPENAI_API_BASE", "http://localhost:11434/v1"),
            api_key=os.environ.get("OPENAI_API_KEY", "ollama"),
            model=os.environ.get("OPENAI_MODEL", "qwen2.5:7b"),
            provider="ollama",
            trust_env=False,
        )

    raise RuntimeError(f"unknown MYCS_LLM={name!r} (use openai, groq, glm, or ollama)")


def _groq_api_key() -> str | None:
    return os.environ.get("GROQ_API_KEY") or (
        os.environ.get("OPENAI_API_KEY")
        if (os.environ.get("OPENAI_API_BASE") or "").find("groq.com") >= 0
        else None
    )


def _glm_api_key() -> str | None:
    return os.environ.get("GLM_API_KEY") or os.environ.get("ZHIPUAI_API_KEY")
