"""Structured (JSON) application logging — Segment 14A PR 1.

This is the *application log* stream — operational events and
failures meant for an operator / Application Insights. It is
deliberately distinct from the other two streams:

* ``audit_events`` rows (``app.services.audit``) — the durable,
  user-attributable record of domain mutations.
* user-facing validation messages (``ValidationIssue`` & friends)
  — surfaced in templates, never a log.

RRW logs under its own named loggers (``app.*``) and never configures
the root logger: the Cordware host does, once per process, and renders
each record as one JSON line with ``application: reviewrobin``
(``cordware/logging.py``, segment 21A).

Call sites use the stdlib logger directly::

    from app.logging_config import get_logger

    log = get_logger(__name__)
    log.info("session activated", extra={"session_id": 7})

Any keyword passed in ``extra=`` that is not a reserved
``LogRecord`` attribute is merged into the JSON object.
"""
from __future__ import annotations

import logging


def get_logger(name: str) -> logging.Logger:
    """Return the named application logger."""
    return logging.getLogger(name)
