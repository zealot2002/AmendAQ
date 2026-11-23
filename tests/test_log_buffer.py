import logging

from amendaq.log_buffer import LogRingBuffer, install_log_buffer_handler


def test_ring_buffer_query_and_clear():
    buf = LogRingBuffer(maxlen=10)
    logger = logging.getLogger("amendaq.test.buffer")
    handler = logging.Handler()
    handler.emit = lambda r: buf.append(r, formatted=f"{r.getMessage()}")  # type: ignore[method-assign]
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    logger.info("hello joyjoy")
    items, latest = buf.query(after_id=0, limit=10)
    assert len(items) == 1
    assert latest == 1
    assert "hello" in items[0]["message"]

    buf.clear()
    items, _ = buf.tail(limit=10)
    assert items == []


def test_install_handler_captures_amendaq_logger():
    install_log_buffer_handler()
    log = logging.getLogger("amendaq.test.install")
    log.info("capture me")
    buf = install_log_buffer_handler()
    tail, latest = buf.tail(limit=5)
    assert latest >= 1
    assert any("capture me" in x["message"] for x in tail)
