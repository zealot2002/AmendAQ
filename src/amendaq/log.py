import logging

LOG_TAG = "joyjoy"

_CONFIGURED = False


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    fmt = logging.Formatter(f"%(asctime)s [{LOG_TAG}] %(name)s %(levelname)s %(message)s")
    root_logger = logging.getLogger("amendaq")
    root_logger.setLevel(logging.INFO)
    root_logger.propagate = False
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        stream = logging.StreamHandler()
        stream.setFormatter(fmt)
        root_logger.addHandler(stream)

    from amendaq.log_buffer import attach_ring_handler_to_logger

    attach_ring_handler_to_logger(root_logger, formatter=fmt)

    for uv_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv = logging.getLogger(uv_name)
        uv.setLevel(logging.INFO)
        uv.propagate = False
        if not uv.handlers:
            h = logging.StreamHandler()
            h.setFormatter(fmt)
            uv.addHandler(h)
        attach_ring_handler_to_logger(uv, formatter=fmt)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    if name == "amendaq" or name.startswith("amendaq."):
        full = name
    else:
        full = f"amendaq.{name}"
    return logging.getLogger(full)
