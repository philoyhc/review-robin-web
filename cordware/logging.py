"""Host-owned process logging (v0.8 §3, "Construction, lifecycle and logging").

The host configures the root logger once: one JSON line per record on
stdout, the shape RRW's structured logging has had since segment 14A.
Applications log under their own named loggers and never touch the root.
`ApplicationFilter` stamps each record that reaches the root handler with
the application that wrote it (`reviewrobin`, or `cordware` for the
host), so the shared Log Analytics workspace can be read per application.
uvicorn's and gunicorn's own loggers keep their own handlers and do not
propagate to the root, so their lines stay plain text, as before 21A.

Any keyword passed in ``extra=`` that is not a reserved ``LogRecord``
attribute is merged into the JSON object, as a top-level key.
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Mapping
from datetime import datetime, timezone

HOST = "cordware"

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


class ApplicationFilter(logging.Filter):
    """Stamp ``record.application`` from the logger name.

    ``loggers`` maps a logger-name prefix (``"app"``) to the application
    that logs under it (``"reviewrobin"``). A record from any other
    logger is the host's. A record that already carries ``application``
    keeps it."""

    def __init__(self, loggers: Mapping[str, str]) -> None:
        super().__init__()
        self._loggers = dict(loggers)

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "application"):
            record.application = HOST
            for prefix, application in self._loggers.items():
                if record.name == prefix or record.name.startswith(prefix + "."):
                    record.application = application
                    break
        return True


def configure_logging(level: str, loggers: Mapping[str, str]) -> None:
    """Install the JSON handler on the root logger.

    ``level`` is a standard level name; an unrecognized one falls back to
    ``INFO``. Idempotent: a handler this function added before is
    replaced, so building the host twice (tests) does not double output."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    for handler in list(root.handlers):
        if getattr(handler, "_cordware_json", False):
            root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(ApplicationFilter(loggers))
    handler._cordware_json = True  # type: ignore[attr-defined]
    root.addHandler(handler)
