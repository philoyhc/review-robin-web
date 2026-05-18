from __future__ import annotations

import json
import logging

from app.logging_config import JsonFormatter, configure_logging, get_logger


def _record(**extra: object) -> logging.LogRecord:
    record = logging.LogRecord(
        name="app.test",
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


def test_json_formatter_merges_caller_extras() -> None:
    payload = json.loads(
        JsonFormatter().format(_record(session_id=7, correlation_id="abc"))
    )

    assert payload["session_id"] == 7
    assert payload["correlation_id"] == "abc"


def test_json_formatter_includes_exception_text() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = _record()
        record.exc_info = sys.exc_info()

    payload = json.loads(JsonFormatter().format(record))
    assert "ValueError: boom" in payload["exc_info"]


def test_configure_logging_is_idempotent() -> None:
    configure_logging()
    configure_logging()

    json_handlers = [
        h
        for h in logging.getLogger().handlers
        if getattr(h, "_rrw_json", False)
    ]
    assert len(json_handlers) == 1


def test_get_logger_returns_named_logger() -> None:
    assert get_logger("app.foo").name == "app.foo"
