"""Assignments service package.

Was a single 1,426-line module until the Segment 18O Track B
carve split it into three concern-scoped sub-modules. The public
surface is preserved here as an explicit re-export wall so external
callers — both ``from app.services import assignments`` and
``from app.services.assignments import <symbol>`` — continue to
work byte-identical to the pre-package shape.

Layout:

- ``_shared.py`` — ``_is_test_env`` (strict-mode self-review
  invariant gate) + ``_is_active`` (row-active predicate).
- ``_coverage.py`` — read-only summaries the Validate page +
  Workflow card + Assignments page consume (counts, staleness,
  roster + pairs queries).
- ``_self_review.py`` — canonical self-review classification +
  recompute / verify invariant + breakdown reporters +
  per-instrument bulk include flip.
- ``_generate.py`` — the rule-runner + Full Matrix synthetic
  schema + diff / materialise / reconcile pipeline +
  ``bulk_set_assignment_include``.
"""

from __future__ import annotations

# Public + private re-exports. The redundant ``as`` aliases on the
# private (single-underscore) names mark that these
# imports are deliberate re-exports rather than dead code; a
# handful of tests reach in via ``assignments._<name>`` and the
# byte-stable surface keeps those working unchanged.
from ._coverage import (
    PAIR_PREVIEW_LIMIT,
    count_pairs,
    existing_count,
    existing_count_per_instrument,
    get_or_create_default_instrument,
    included_count_per_instrument,
    list_pairs,
    list_reviewees,
    list_reviewers,
)
from ._coverage import _apply_pair_search as _apply_pair_search
from ._generate import (
    InstrumentReconcileState,
    ReconcileImpact,
    bulk_set_assignment_include,
    generate_full_matrix,
    persist_reconcile_warm,
    reconcile_impact,
    replace_assignments,
    staleness_by_instrument,
)
from ._generate import _diff_one_instrument as _diff_one_instrument
from ._generate import _full_matrix_schema as _full_matrix_schema
from ._generate import _InstrumentDiff as _InstrumentDiff
from ._generate import _load_reconcile_inputs as _load_reconcile_inputs
from ._generate import _logger as _logger
from ._generate import _materialise_one_instrument as _materialise_one_instrument
from ._generate import _ReconcileInputs as _ReconcileInputs
from ._generate import _session_rule_set_to_schema as _session_rule_set_to_schema
from ._self_review import (
    AssignmentPair,
    classify_self_review,
    classify_self_review_pairs,
    is_self_review,
    recompute_self_review_classification,
    self_review_breakdown_per_instrument,
    set_instrument_self_reviews_active,
    verify_self_review_classification,
)
from ._self_review import _self_review_assignment_ids as _self_review_assignment_ids
from ._shared import _is_active as _is_active
from ._shared import _is_test_env as _is_test_env

__all__ = [
    "PAIR_PREVIEW_LIMIT",
    "AssignmentPair",
    "ReconcileImpact",
    "bulk_set_assignment_include",
    "classify_self_review",
    "classify_self_review_pairs",
    "count_pairs",
    "existing_count",
    "existing_count_per_instrument",
    "generate_full_matrix",
    "get_or_create_default_instrument",
    "included_count_per_instrument",
    "is_self_review",
    "list_pairs",
    "list_reviewees",
    "list_reviewers",
    "reconcile_impact",
    "InstrumentReconcileState",
    "persist_reconcile_warm",
    "staleness_by_instrument",
    "recompute_self_review_classification",
    "replace_assignments",
    "self_review_breakdown_per_instrument",
    "set_instrument_self_reviews_active",
    "verify_self_review_classification",
]
