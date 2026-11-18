from __future__ import annotations

import os

import uvicorn

from mycs.api.app import create_app
from mycs.log import configure_logging, get_logger
from mycs.net.localhost import ensure_localhost_no_proxy
from mycs.paths import runtime_paths

logger = get_logger(__name__)


def main() -> None:
    from mycs.env_loader import load_project_dotenv
    from mycs.llm.factory import resolve_llm_backend, resolve_llm_model_name

    ensure_localhost_no_proxy()
    load_project_dotenv(override=True)
    configure_logging()
    host = os.environ.get("MYCS_API_HOST", "127.0.0.1")
    port = int(os.environ.get("MYCS_API_PORT", "8765"))
    paths = runtime_paths()
    logger.info("mycs-api starting host=%s port=%s", host, port)
    logger.info(
        "joyjoy: llm backend=%s display=%s",
        resolve_llm_backend(),
        resolve_llm_model_name(),
    )
    logger.info("paths db=%s uploads=%s traces=%s kg=%s", paths["db"], paths["uploads"], paths["traces"], paths["kg"])
    uvicorn.run(
        "mycs.api.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=os.environ.get("MYCS_API_RELOAD", "").strip() in ("1", "true", "yes"),
    )


if __name__ == "__main__":
    main()
