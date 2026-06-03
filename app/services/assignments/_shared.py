"""Cross-slice plumbing for the assignments service package.

Tiny helper set shared by ``_coverage``, ``_self_review``, and
``_generate``. Reads nothing from siblings; siblings read from here.
"""
from __future__ import annotations

import os

from app.db.models import Reviewee, Reviewer


def _is_test_env() -> bool:
    """Match :func:`app.services.audit._is_test_env` for the self-
    review classification invariant (PR 4 of
    ``guide/self_review_consolidate.md``) — strict-mode in
    pytest, log-and-correct in production."""
    return "PYTEST_CURRENT_TEST" in os.environ or "pytest" in os.environ.get(
        "_", ""
    )


def _is_active(row: Reviewer | Reviewee) -> bool:
    return (row.status or "active") == "active"
