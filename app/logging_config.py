"""Structured (JSON) application logging — Segment 14A PR 1.

This is the *application log* stream — operational events and
failures meant for an operator / Application Insights. It is
deliberately distinct from the other two streams:

* ``audit_events`` rows (``app.services.audit``) — the durable,
  user-attributable record of domain mutations.
* user-facing validation messages (``ValidationIssue`` & friends)
  — surfaced in templates, never a log.

Records are emitted as one JSON object per line on stdout so the
Azure App Service log stream / Application Insights can ingest
them without a parser. ``configure_logging`` is idempotent — safe
to call once per process from ``create_app``.

Call sites use the stdlib logger directly::

    from app.logging_config import get_logger

    log = get_logger(__name__)
    log.info("session activated", extra={"session_id": 7})

Any keyword passed in ``extra=`` that is not a reserved
``LogRecord`` attribute is merged into the JSON object.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from app.config import settings

# Attribute names the stdlib sets on every ``LogRecord``. Anything
# on a record's ``__dict__`` that is *not* in this set was supplied
# by the caller via ``extra=`` and is merged into the JSON payload.
_RESERVED_RECORD_KEYS = frozenset(
    {
        "name",
        "msg",
        "args",
        "levelname",
        "levelno",
        "pathname",
        "filename",
        "module",
        "exc_info",
        "exc_text",
        "stack_info",
        "lineno",
        "funcName",
        "created",
        "msecs",
        "relativeCreated",
        "thread",
        "threadName",
        "processName",
        "process",
        "taskName",
    }
)


class JsonFormatter(logging.Formatter):
    """Render a ``LogRecord`` as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _RESERVED_RECORD_KEYS or key.startswith("_"):
                continue
            if key == "message":
                continue
            payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging() -> None:
    """Install the JSON formatter on the root logger.

    Idempotent: clears any handlers it previously added so repeated
    calls (e.g. test app construction) don't multiply output.
    """
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    for handler in list(root.handlers):
        if getattr(handler, "_rrw_json", False):
            root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler._rrw_json = True  # type: ignore[attr-defined]
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return the named application logger."""
    return logging.getLogger(name)
