"""Host-owned logging: the JSON shape, the application stamp, host events.

Segment 21A rung A3 (`guide/segment_21A_cordware_foundations.md`). The
formatter cases moved here from `tests/unit/test_logging_config.py` with
`configure_logging()`.
"""

from __future__ import annotations

import io
import json
import logging
import sys
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from cordware.logging import ApplicationFilter, JsonFormatter, configure_logging
from cordware.main import AppEntry, create_app


def _record(name: str = "app.test", **extra: object) -> logging.LogRecord:
    record = logging.LogRecord(
        name=name,
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_json_formatter_emits_core_fields() -> None:
    payload = json.loads(JsonFormatter().format(_record()))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.test"
    assert payload["message"] == "hello world"
    assert "timestamp" in payload


def test_json_formatter_merges_caller_extras_at_the_top_level() -> None:
    payload = json.loads(JsonFormatter().format(_record(session_id=7, correlation_id="abc")))

    assert payload["session_id"] == 7
    assert payload["correlation_id"] == "abc"


def test_json_formatter_includes_exception_text() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        record = _record()
        record.exc_info = sys.exc_info()

    payload = json.loads(JsonFormatter().format(record))
    assert "ValueError: boom" in payload["exc_info"]


@pytest.mark.parametrize(
    ("logger", "application"),
    [
        ("app", "reviewrobin"),
        ("app.services.sessions", "reviewrobin"),
        ("apple", "cordware"),
        ("uvicorn.error", "cordware"),
        ("cordware", "cordware"),
    ],
)
def test_application_filter_stamps_by_logger_prefix(logger: str, application: str) -> None:
    record = _record(name=logger)
    assert ApplicationFilter({"app": "reviewrobin"}).filter(record)
    assert record.application == application


def test_application_filter_keeps_an_explicit_stamp() -> None:
    record = _record(application="other")
    ApplicationFilter({"app": "reviewrobin"}).filter(record)
    assert record.application == "other"


def _json_handlers() -> list[logging.Handler]:
    return [h for h in logging.getLogger().handlers if getattr(h, "_cordware_json", False)]


def test_configure_logging_is_idempotent() -> None:
    configure_logging("INFO", {})
    configure_logging("INFO", {})
    assert len(_json_handlers()) == 1


@pytest.fixture
def capture(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[], io.StringIO]]:
    """Call it in the test body to send the host's JSON lines to a buffer.

    The handler binds `sys.stdout` when a host is built, and pytest swaps
    `sys.stdout` again as the test body starts, so the swap has to happen
    there. A host built afterwards writes to the buffer."""

    def start() -> io.StringIO:
        buffer = io.StringIO()
        monkeypatch.setattr(sys, "stdout", buffer)
        return buffer

    yield start
    monkeypatch.undo()
    configure_logging("INFO", {})  # rebind to the real stdout


def _lines(buffer: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in buffer.getvalue().splitlines() if line]


def test_an_rrw_record_reaches_the_host_handler_stamped(
    capture: Callable[[], io.StringIO],
) -> None:
    captured = capture()
    create_app(apps=())
    logging.getLogger("app.services.sessions").warning("probe", extra={"event": "probe"})
    (line,) = [entry for entry in _lines(captured) if entry.get("event") == "probe"]
    assert line["application"] == "reviewrobin"
    assert line["logger"] == "app.services.sessions"


def test_building_rrw_adds_no_root_handler() -> None:
    from app.main import create_app as create_rrw

    before = list(logging.getLogger().handlers)
    create_rrw()
    assert logging.getLogger().handlers == before


def test_the_host_logs_start_and_stop_with_the_mounted_set(
    capture: Callable[[], io.StringIO],
) -> None:
    captured = capture()
    with TestClient(create_app(apps=())):
        pass
    events = [(e["event"], e["application"]) for e in _lines(captured) if "event" in e]
    assert ("host.started", "cordware") in events
    assert ("host.stopping", "cordware") in events
    (started,) = [e for e in _lines(captured) if e.get("event") == "host.started"]
    assert started["mounted"] == []


def failing_factory() -> None:
    raise RuntimeError("startup validation failed")


def test_a_mounted_startup_failure_is_logged_before_it_propagates(
    capture: Callable[[], io.StringIO],
) -> None:
    captured = capture()
    registry = {"bad": AppEntry(path="/bad", factory=f"{__name__}:failing_factory", logger="bad")}
    with pytest.raises(RuntimeError):
        create_app(apps=("bad",), registry=registry)
    (line,) = [e for e in _lines(captured) if e.get("event") == "host.app_startup_failed"]
    assert line["app"] == "bad"
    assert line["level"] == "ERROR"
    assert "startup validation failed" in str(line["exc_info"])
