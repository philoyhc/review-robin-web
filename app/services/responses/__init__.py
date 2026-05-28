"""Responses service package.

Was a single 1,444-line ``responses.py`` until Segment 18N PR 4
carved the Segment 13C / 18H group-reconciliation block out as
``_group_reconciliation.py``. The public surface is preserved
here as an explicit re-export wall so external callers — both
``from app.services import responses`` and
``from app.services.responses import <symbol>`` — continue to
work byte-identical to the pre-package shape.

Layout:

- ``_core.py`` — save / submit / recall / clear / delete-all
  flow, validation primitives, per-row completion compute, and
  the ``ReviewerSessionState`` rollup. Imports the group-block
  symbols it depends on from ``_group_reconciliation``.
- ``_group_reconciliation.py`` — Segment 13C / 18H group-scoped
  fan-out / collapse / reconcile machinery. Reads nothing from
  ``_core``; the dependency is uni-directional.
"""

from __future__ import annotations

from ._core import (
    ClearResult,
    DeleteAllResult,
    MissingPosition,
    RecallResult,
    ReviewerSessionState,
    SaveResult,
    SessionPill,
    SubmitResult,
    ValidationError,
    clear_all,
    compute_row_completion,
    delete_all_for_session,
    parse_form_payload,
    recall,
    reviewer_session_state,
    reviewer_session_state_per_instrument,
    save_draft,
    session_pill_for_reviewer,
    session_response_count,
    submit,
    validate_value,
)
from ._group_reconciliation import (
    group_key_for_pair,
    group_keys,
    reconcile_group_responses_for_relationship_change,
    reconcile_group_responses_for_tag_change,
)


__all__ = [
    # _core
    "ClearResult",
    "DeleteAllResult",
    "MissingPosition",
    "RecallResult",
    "ReviewerSessionState",
    "SaveResult",
    "SessionPill",
    "SubmitResult",
    "ValidationError",
    "clear_all",
    "compute_row_completion",
    "delete_all_for_session",
    "parse_form_payload",
    "recall",
    "reviewer_session_state",
    "reviewer_session_state_per_instrument",
    "save_draft",
    "session_pill_for_reviewer",
    "session_response_count",
    "submit",
    "validate_value",
    # _group_reconciliation
    "group_key_for_pair",
    "group_keys",
    "reconcile_group_responses_for_relationship_change",
    "reconcile_group_responses_for_tag_change",
]
