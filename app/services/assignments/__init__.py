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
  roster + pairs queries, the per-session destructive
  ``delete_all_assignments`` op).
- ``_self_review.py`` — canonical self-review classification +
  recompute / verify invariant + breakdown reporters +
  per-instrument bulk include flip.
- ``_generate.py`` — the rule-runner + Full Matrix synthetic
  schema + diff / materialise / reconcile pipeline +
  ``bulk_set_assignment_include``.
"""
from __future__ import annotations

# Public + private re-exports. The F401 noqa markers on the
# private (single-underscore) names acknowledge that these
# imports are deliberate re-exports rather than dead code; a
# handful of tests reach in via ``assignments._<name>`` and the
# byte-stable surface keeps those working unchanged.
from ._coverage import (
    PAIR_PREVIEW_LIMIT,
    _apply_pair_search,  # noqa: F401
    assignment_fields_with_data,
    compute_staleness,
    count_pairs,
    delete_all_assignments,
    display_source_presence,
    existing_count,
    existing_count_per_instrument,
    get_or_create_default_instrument,
    included_count_per_instrument,
    latest_generated_event_per_instrument,
    list_pairs,
    list_reviewees,
    list_reviewers,
    reviewee_fields_with_data,
    reviewer_fields_with_data,
)
from ._generate import (
    ReconcileImpact,
    _diff_one_instrument,  # noqa: F401
    _full_matrix_schema,  # noqa: F401
    _InstrumentDiff,  # noqa: F401
    _load_reconcile_inputs,  # noqa: F401
    _logger,  # noqa: F401
    _materialise_one_instrument,  # noqa: F401
    _ReconcileInputs,  # noqa: F401
    _session_rule_set_to_schema,  # noqa: F401
    bulk_set_assignment_include,
    coverage_stats,
    generate_full_matrix,
    reconcile_impact,
    replace_assignments,
)
from ._self_review import (
    _self_review_assignment_ids,  # noqa: F401
    classify_self_review,
    count_self_review_candidates,
    count_self_reviews_in_assignments,
    is_self_review,
    recompute_self_review_classification,
    self_review_breakdown_per_instrument,
    set_instrument_self_reviews_active,
    verify_self_review_classification,
)
from ._shared import _is_active, _is_test_env  # noqa: F401


__all__ = [
    "PAIR_PREVIEW_LIMIT",
    "ReconcileImpact",
    "assignment_fields_with_data",
    "bulk_set_assignment_include",
    "classify_self_review",
    "compute_staleness",
    "count_pairs",
    "count_self_review_candidates",
    "count_self_reviews_in_assignments",
    "coverage_stats",
    "delete_all_assignments",
    "display_source_presence",
    "existing_count",
    "existing_count_per_instrument",
    "generate_full_matrix",
    "get_or_create_default_instrument",
    "included_count_per_instrument",
    "is_self_review",
    "latest_generated_event_per_instrument",
    "list_pairs",
    "list_reviewees",
    "list_reviewers",
    "reconcile_impact",
    "recompute_self_review_classification",
    "replace_assignments",
    "reviewee_fields_with_data",
    "reviewer_fields_with_data",
    "self_review_breakdown_per_instrument",
    "set_instrument_self_reviews_active",
    "verify_self_review_classification",
]
