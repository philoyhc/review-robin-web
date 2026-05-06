from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel


class Severity(str, Enum):
    error = "error"
    warning = "warning"
    info = "info"


class ValidationIssue(BaseModel):
    severity: Severity
    source: str
    row_number: int | None = None
    field: str | None = None
    message: str
    detail: dict[str, Any] | None = None
    # Per-issue fix-link fields stamped by the validate-session-setup
    # rule registry (Segment 11G PR B). Defaults preserve back-compat
    # for ``csv_imports``-emitted issues that don't run through the
    # registry — those continue to render without a "Fix on …" link.
    rule_key: str | None = None
    fix_url: str | None = None
    fix_anchor: str | None = None
    fix_page_label: str | None = None
    why: str | None = None
    """One-paragraph rationale stamped by the rule registry; surfaced
    via the per-issue ``<details>`` "Why this check?" disclosure on
    the Validate page (Segment 11G PR C)."""

    @property
    def is_blocking(self) -> bool:
        return self.severity is Severity.error
