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
  flow, validation primitives and per-row completion compute. Imports the group-block
  symbols it depends on from ``_group_reconciliation``.
- ``_rollups.py`` — segment 20E: the read-only tallies (the
  per-reviewer session state, the rollup parts, the response counts).
  Imports two private helpers from ``_core``; ``_core`` never imports it.
- ``_group_reconciliation.py`` — Segment 13C / 18H group-scoped
  fan-out / collapse / reconcile machinery. Reads nothing from
  ``_core``; the dependency is uni-directional.
- ``_branching.py`` — 19T Item 10: branch conditions, whether a branch
  is open, which fields an assignment can answer, and the structure
  rules. Pure; imports no other service.
- ``_branch_rule.py`` — 19T Item 10: the save rule, "a closed branch
  holds no value", which every writer of ``Response`` rows ends in.
"""

from __future__ import annotations

from ._branch_rule import closed_governed_field_ids, drop_closed_branch_answers
from ._branching import (
    BRANCH_LOOP_MESSAGE,
    BRANCH_MODE_REQUIRE,
    BRANCH_MODE_SHOW,
    BRANCH_MODES,
    BRANCH_OPS,
    BRANCH_TOO_DEEP_MESSAGE,
    LIST_OP_CHOICES,
    LIST_OPS,
    MAX_BRANCH_DEPTH,
    NUMERIC_OP_CHOICES,
    NUMERIC_OPS,
    PARENT_DATA_TYPES,
    RANGE_OPS,
    RANGE_SEPARATOR,
    applicable_field_ids,
    branch_depth,
    branch_is_open,
    branch_mode,
    branch_structure_errors,
    canonical_condition_value,
    condition_error,
    condition_label,
    hide_below_hidden_parents,
    may_be_required_field_ids,
    parse_range,
    required_field_ids,
)
from ._core import (
    ClearResult,
    DeleteAllResult,
    MissingPosition,
    RecallResult,
    RowCompletion,
    SaveResult,
    SubmitResult,
    ValidationError,
    clear_all,
    compute_row_completion,
    delete_all_for_session,
    parse_form_payload,
    recall,
    row_completion,
    save_draft,
    stored_as_posted,
    submit,
    validate_value,
)
from ._form_keys import (
    ANSWER_KEY_PATTERN,
    PAGE_DIGEST_FIELD,
    answer_ordinals,
    digest_matches,
    page_assignment_ids,
    page_assignments,
    page_digest,
)
from ._group_reconciliation import (
    GroupAnswersWouldClear,
    GroupKeyable,
    GroupPartitions,
    clear_changed_groups,
    group_key_for_pair,
    group_keys,
    is_catch_all_key,
    keeps_answer,
    origins,
    session_group_instrument_ids,
    snapshot_group_partitions,
)
from ._rollups import (
    ReviewerSessionState,
    RollupParts,
    SessionPill,
    responses_by_assignment,
    reviewer_session_state,
    reviewer_session_state_per_instrument,
    rollup_parts_from_assignments,
    session_pill_for_reviewer,
    session_response_count,
)

__all__ = [
    # _form_keys
    "ANSWER_KEY_PATTERN",
    "PAGE_DIGEST_FIELD",
    "answer_ordinals",
    "digest_matches",
    "page_assignment_ids",
    "page_assignments",
    "page_digest",
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
    "RowCompletion",
    "row_completion",
    "delete_all_for_session",
    "parse_form_payload",
    "recall",
    "responses_by_assignment",
    "RollupParts",
    "reviewer_session_state",
    "rollup_parts_from_assignments",
    "reviewer_session_state_per_instrument",
    "save_draft",
    "session_pill_for_reviewer",
    "stored_as_posted",
    "session_response_count",
    "submit",
    "validate_value",
    # _branch_rule
    "closed_governed_field_ids",
    "drop_closed_branch_answers",
    # _branching
    "BRANCH_OPS",
    "LIST_OPS",
    "NUMERIC_OPS",
    "PARENT_DATA_TYPES",
    "LIST_OP_CHOICES",
    "NUMERIC_OP_CHOICES",
    "RANGE_OPS",
    "RANGE_SEPARATOR",
    "parse_range",
    "applicable_field_ids",
    "branch_is_open",
    "required_field_ids",
    "branch_mode",
    "BRANCH_MODE_REQUIRE",
    "BRANCH_MODE_SHOW",
    "BRANCH_MODES",
    "may_be_required_field_ids",
    "canonical_condition_value",
    "condition_label",
    "BRANCH_LOOP_MESSAGE",
    "BRANCH_TOO_DEEP_MESSAGE",
    "MAX_BRANCH_DEPTH",
    "branch_depth",
    "hide_below_hidden_parents",
    "branch_structure_errors",
    "condition_error",
    # _group_reconciliation
    "GroupAnswersWouldClear",
    "GroupPartitions",
    "clear_changed_groups",
    "keeps_answer",
    "origins",
    "session_group_instrument_ids",
    "snapshot_group_partitions",
    "group_key_for_pair",
    "is_catch_all_key",
    "GroupKeyable",
    "group_keys",
]
