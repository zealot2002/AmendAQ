from __future__ import annotations

import os
from pathlib import Path

from mycs.log import get_logger

logger = get_logger(__name__)


def load_project_dotenv(*, override: bool = True) -> bool:
    """Load repo-root `.env` (MYCS_LLM, GLM_API_KEY, …). Used at API/worker startup."""
    root = Path(__file__).resolve().parents[2]
    env_path = root / ".env"
    if not env_path.is_file():
        key = os.environ.get("GLM_API_KEY") or os.environ.get("ZHIPUAI_API_KEY")
        if key and (os.environ.get("MYCS_LLM") or "").strip().lower() in ("", "openai", "vllm", "compat"):
            os.environ["MYCS_LLM"] = "glm"
            os.environ.setdefault("GLM_MODEL", "glm-4-flash-250414")
            logger.info("joyjoy: no .env; GLM key in env → MYCS_LLM=glm")
        return False
    loaded = 0
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if not key:
            continue
        if override or key not in os.environ:
            os.environ[key] = val
            loaded += 1
    logger.info(
        "joyjoy: loaded .env from %s keys=%s MYCS_LLM=%s GLM_MODEL=%s",
        env_path,
        loaded,
        os.environ.get("MYCS_LLM"),
        os.environ.get("GLM_MODEL"),
    )
    return True