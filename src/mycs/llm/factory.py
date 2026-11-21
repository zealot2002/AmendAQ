from __future__ import annotations

import os

from mycs.llm.base import AgentLLM
from mycs.llm.openai_compat import OpenAICompatLLM
from mycs.log import get_logger

logger = get_logger(__name__)

GLM_DEFAULT_BASE = "https://open.bigmodel.cn/api/paas/v4"
GLM_DEFAULT_MODEL = "glm-4-flash-250414"
ZHIPU_DISPLAY = "智谱 GLM"
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

    # 只有没写明用 ollama 时，才避免落到 ~/.zshrc 里的 openai/Qwen 网关
    if name in ("openai", "vllm", "compat") and _glm_api_key():
        if os.environ.get("MYCS_LLM_FORCE_OPENAI", "").strip().lower() not in (
            "1",
            "true",
            "yes",
        ):
            logger.warning(
                "joyjoy: MYCS_LLM=%s ignored; GLM_API_KEY present, using 智谱 GLM",
                name,
            )
            name = "glm"

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
        model = os.environ.get("GLM_MODEL") or GLM_DEFAULT_MODEL
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
        base = (os.environ.get("OPENAI_API_BASE") or "").strip().rstrip("/")
        if not base:
            raise RuntimeError("MYCS_LLM=openai but OPENAI_API_BASE is not set")
        # 无 API key 的兼容网关：占位即可，多数服务会忽略 Authorization
        key = os.environ.get("OPENAI_API_KEY")
        if key is None or not str(key).strip():
            key = "EMPTY"
        model = os.environ.get("OPENAI_MODEL") or "default"
        logger.info("joyjoy: using OpenAI-compat model=%s base=%s", model, base)
        return OpenAICompatLLM(
            base_url=base,
            api_key=key,
            model=model,
            provider="openai",
            trust_env=False,
        )

    if name == "ollama":
        base = _ollama_base_url()
        model = os.environ.get("OLLAMA_MODEL") or "qwen2.5:7b"
        logger.info("joyjoy: using Ollama model=%s base=%s", model, base)
        return OpenAICompatLLM(
            base_url=base,
            api_key=os.environ.get("OLLAMA_API_KEY") or "ollama",
            model=model,
            provider="ollama",
            trust_env=False,
        )

    if name == "qwen":
        base = (os.environ.get("QWEN_BASE_URL") or "http://192.168.10.175:8000/v1").strip().rstrip("/")
        model = os.environ.get("QWEN_MODEL") or "Qwen3.6"
        logger.info("joyjoy: using Qwen model=%s base=%s", model, base)
        return OpenAICompatLLM(
            base_url=base,
            api_key=os.environ.get("QWEN_API_KEY") or "EMPTY",
            model=model,
            provider="openai",
            trust_env=False,
        )

    raise RuntimeError(f"unknown MYCS_LLM={name!r} (use glm, ollama, qwen, openai, or groq)")


def _groq_api_key() -> str | None:
    return os.environ.get("GROQ_API_KEY") or (
        os.environ.get("OPENAI_API_KEY")
        if (os.environ.get("OPENAI_API_BASE") or "").find("groq.com") >= 0
        else None
    )


def _glm_api_key() -> str | None:
    return os.environ.get("GLM_API_KEY") or os.environ.get("ZHIPUAI_API_KEY")


def resolve_llm_backend() -> str:
    name = (os.environ.get("MYCS_LLM") or "").strip().lower()
    if not name:
        if _glm_api_key():
            return "glm"
        if _groq_api_key():
            return "groq"
        return "ollama"
    if name in ("openai", "vllm", "compat") and _glm_api_key():
        if os.environ.get("MYCS_LLM_FORCE_OPENAI", "").strip().lower() not in (
            "1",
            "true",
            "yes",
        ):
            return "glm"
    return name


def resolve_llm_model_name(backend: str | None = None) -> str:
    name = (backend or resolve_llm_backend()).lower()
    if name in ("glm", "zhipu", "zhipuai", "bigmodel"):
        model = os.environ.get("GLM_MODEL") or GLM_DEFAULT_MODEL
        return f"{ZHIPU_DISPLAY} · {model}"
    if name == "groq":
        return os.environ.get("GROQ_MODEL") or GROQ_DEFAULT_MODEL
    if name in ("openai", "vllm", "compat"):
        return os.environ.get("OPENAI_MODEL") or "openai-compat"
    if name == "ollama":
        return os.environ.get("OLLAMA_MODEL") or "qwen2.5:7b"
    if name == "qwen":
        return os.environ.get("QWEN_MODEL") or "Qwen3.6"
    return "大模型"


def _ollama_base_url() -> str:
    raw = (
        os.environ.get("OLLAMA_BASE_URL")
        or os.environ.get("OLLAMA_HOST")
        or "http://127.0.0.1:11434"
    ).strip().rstrip("/")
    if raw.endswith("/v1"):
        return raw
    return raw + "/v1"
