"""Health module: source status registry, error ring buffer."""
import logging

from app.health import ErrorRingHandler, SourceStatus


def test_source_status_ok_and_fail():
    SourceStatus._status.clear()
    SourceStatus.ok("javdb")
    SourceStatus.fail("sukebei", "timeout")
    snap = SourceStatus.snapshot()
    by_name = {s["source"]: s for s in snap}
    assert by_name["javdb"]["error"] is None
    assert by_name["sukebei"]["error"] == "timeout"


def test_error_ring_handler_buffers():
    handler = ErrorRingHandler(maxlen=3)
    logger = logging.getLogger("test.health")
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)
    for i in range(5):
        logger.error("boom %d", i)
    recent = handler.recent()
    assert len(recent) == 3
    assert "boom 2" in recent[0]
    logger.removeHandler(handler)
