"""Lookups a test knows will find something (segment 22D rung 7).

``db.get`` and ``re.search`` return ``None`` on a miss, which a test that
has just written the row or fetched the page rules out. These assert it
once, so the rest of the test reads the row or the match as it is; a
miss fails at the lookup, with what was looked for, rather than as an
``AttributeError`` a line later.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditEvent


def must_get[M](db: Session, model: type[M], pk: object) -> M:
    """``db.get(model, pk)``, for a row the test knows exists."""
    row = db.get(model, pk)
    assert row is not None, f"no {model.__name__} {pk!r}"
    return row


def must_search(pattern: str, text: str, flags: int = 0) -> re.Match[str]:
    """``re.search(pattern, text, flags)``, for a pattern the text must contain."""
    match = re.search(pattern, text, flags)
    assert match is not None, f"no match for {pattern!r}"
    return match


def detail_of(event: AuditEvent) -> dict[str, Any]:
    """An audit event's ``detail``, for an event type that always writes one."""
    assert event.detail is not None, f"{event.event_type} has no detail"
    return event.detail
