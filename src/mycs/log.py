import logging

LOG_TAG = "joyjoy"

_CONFIGURED = False


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    fmt = logging.Formatter(f"%(asctime)s [{LOG_TAG}] %(name)s %(levelname)s %(message)s")
    mycs = logging.getLogger("mycs")
    mycs.setLevel(logging.INFO)
    mycs.propagate = False
    if not any(isinstance(h, logging.StreamHandler) for h in mycs.handlers):
        stream = logging.StreamHandler()
        stream.setFormatter(fmt)
        mycs.addHandler(stream)

    from mycs.log_buffer import attach_ring_handler_to_logger

    attach_ring_handler_to_logger(mycs, formatter=fmt)

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
    if name == "mycs" or name.startswith("mycs."):
        full = name
    else:
        full = f"mycs.{name}"
    return logging.getLogger(full)
