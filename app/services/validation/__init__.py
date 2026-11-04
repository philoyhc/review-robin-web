"""Pre-activation setup validation as a registered rule list.

Each rule emits ``ValidationIssue`` instances annotated with the
rule's ``key``, ``fix_url``, and (where the issue points at a
specific row) a ``fix_anchor``. The Validate page (Segment 11G)
renders a "Fix on {page} ↗" deep-link per issue and surfaces a
"Why this check?" disclosure (PR C) by reading these fields.

The previous monolithic ``validate_session_setup`` function
became one rule per check; the public signature is unchanged
(``list[ValidationIssue]``).

Was a single 1,506-line ``validation.py`` until segment 20E rung 4b cut
it along its seams, behind this re-export wall, so
``from app.services import validation`` and
``from app.services.validation import <name>`` work as before:

- ``_inputs.py`` — ``ValidationRule``, ``ValidationInputs``,
  ``load_validation_inputs``.
- ``_rosters.py`` — the session's own fields and the rosters.
- ``_assignments.py`` — assignments.
- ``_instruments.py`` — instruments.
- ``_registry.py`` — ``REGISTERED_RULES`` and ``validate_session_setup``.

A new rule goes in its area's module and is registered in
``_registry.py``. A test that replaces a name here reaches callers outside
the package only.
"""

from __future__ import annotations

from app.services.validation._inputs import (
    ValidationRule,
    ValidationInputs,
    load_validation_inputs,
)
from app.services.validation._rosters import (
    _check_session_no_name,
    _check_session_no_code,
    _check_session_end_passed,
    _check_reviewers_empty,
    _check_reviewers_duplicate_email,
    _check_observers_duplicate_email,
    _CROSS_ROSTER_WHY,
    _ROSTER_IDENTITY_FIELDS,
    _ROSTER_SINGULAR,
    _IdentityHolder,
    _identity_holders_by_email,
    _cross_roster_identity_issues,
    _check_reviewers_cross_roster_identity,
    _check_reviewees_cross_roster_identity,
    _check_observers_cross_roster_identity,
    _check_reviewees_empty,
    _check_reviewees_duplicate_id,
    _duplicate_accounts,
    _check_reviewers_duplicate_account,
    _check_reviewees_duplicate_account,
    _check_observers_duplicate_account,
    _DUPLICATE_ACCOUNT_WHY,
    _check_reviewees_unreachable_for_results,
    _check_email_template_no_help_contact,
    _check_reviewees_mirror_drift,
    _MIRROR_DRIFT_WHY,
)
from app.services.validation._assignments import (
    _check_assignments_no_included_pairs,
    _active_assignment_presence,
    _included_instrument_ids,
    _active_reviewers,
    _check_assignments_reviewer_missing,
    _check_assignments_reviewer_missing_for_instrument,
    _check_assignments_instrument_empty,
)
from app.services.validation._instruments import (
    _check_instruments_no_fields,
    _check_instruments_no_rule_pinned,
    _check_new_model_no_visible_response_fields,
    _staleness,
    _check_instruments_rule_set_unloadable,
    _check_instruments_stale_generated,
    _check_instruments_zero_included,
    _check_instruments_no_display_fields,
)
from app.services.validation._registry import (
    _session_edit_url,
    _reviewers_url,
    _reviewees_url,
    _observers_url,
    _instruments_url,
    _assignments_url,
    REGISTERED_RULES,
    validate_session_setup,
)

__all__ = [
    "ValidationRule",
    "ValidationInputs",
    "load_validation_inputs",
    "_check_session_no_name",
    "_check_session_no_code",
    "_check_session_end_passed",
    "_check_reviewers_empty",
    "_check_reviewers_duplicate_email",
    "_check_observers_duplicate_email",
    "_CROSS_ROSTER_WHY",
    "_ROSTER_IDENTITY_FIELDS",
    "_ROSTER_SINGULAR",
    "_IdentityHolder",
    "_identity_holders_by_email",
    "_cross_roster_identity_issues",
    "_check_reviewers_cross_roster_identity",
    "_check_reviewees_cross_roster_identity",
    "_check_observers_cross_roster_identity",
    "_check_reviewees_empty",
    "_check_reviewees_duplicate_id",
    "_duplicate_accounts",
    "_check_reviewers_duplicate_account",
    "_check_reviewees_duplicate_account",
    "_check_observers_duplicate_account",
    "_DUPLICATE_ACCOUNT_WHY",
    "_check_reviewees_unreachable_for_results",
    "_check_email_template_no_help_contact",
    "_check_reviewees_mirror_drift",
    "_MIRROR_DRIFT_WHY",
    "_check_assignments_no_included_pairs",
    "_active_assignment_presence",
    "_included_instrument_ids",
    "_active_reviewers",
    "_check_assignments_reviewer_missing",
    "_check_assignments_reviewer_missing_for_instrument",
    "_check_assignments_instrument_empty",
    "_check_instruments_no_fields",
    "_check_instruments_no_rule_pinned",
    "_check_new_model_no_visible_response_fields",
    "_staleness",
    "_check_instruments_rule_set_unloadable",
    "_check_instruments_stale_generated",
    "_check_instruments_zero_included",
    "_check_instruments_no_display_fields",
    "_session_edit_url",
    "_reviewers_url",
    "_reviewees_url",
    "_observers_url",
    "_instruments_url",
    "_assignments_url",
    "REGISTERED_RULES",
    "validate_session_setup",
]
