"""Settings CSV import — ``apply_session_config`` orchestrator.

Parses a Settings CSV (3-column ``field,value,data_type`` shape)
and applies it to a session as a wipe-and-replace. Two-phase:
parse + validate first (collect every error before reporting),
then apply in a single transaction.

Reachable only via Quick Setup slot 4 (graduated in 12A-3 PR 4) —
no standalone Manage page. The lifecycle gate
(``status in {"draft", "validated"}``) lives at the route layer.

Originally a single ~1,360-line module; Segment 18O Track C
carved the per-section parse + apply work into sibling modules
inside this package. The public surface
(``ApplyError`` / ``ApplyResult`` / ``apply_session_config``)
stays here; private re-exports the unit tests reach for
(``_ParseError`` / ``_parse_group_kind``) live in
``_apply_shared`` + the package ``__init__``.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.services import audit
from app.services import session_lifecycle as lifecycle

from ._apply_data_shape import _apply_data_shapes
from ._apply_email import _apply_email_overrides
from ._apply_field_label import _apply_field_labels
from ._apply_instrument import (
    _apply_instruments,
    _wipe_instruments_and_dependents,
)
from ._apply_parse import ApplyError, _parse_rows
from ._apply_rule_set import _apply_session_rule_sets
from ._apply_session import _apply_session_metadata
from ._apply_shared import _ParsedConfig
from ._rows import Row


@dataclass(frozen=True)
class ApplyResult:
    """Outcome of an ``apply_session_config`` call.

    On success ``counts`` carries the number of rows written per
    section (e.g. ``{"rtds": 3, "instruments": 2, ...}``) and
    ``errors`` is empty. On failure ``errors`` enumerates every
    parse / validation issue and ``counts`` is empty (the apply
    transaction never ran)."""

    counts: dict[str, int]
    errors: list[ApplyError]

    @property
    def ok(self) -> bool:
        return not self.errors


def apply_session_config(
    db: Session,
    review_session: ReviewSession,
    rows: list[Row],
    *,
    user: User | None = None,
    correlation_id: str | None = None,
) -> ApplyResult:
    """Parse + apply a Settings CSV against ``review_session``.

    Phase 1 — parse + validate every row. Collect every error
    before reporting; one bad row doesn't mask the next.

    Phase 2 — apply the typed plan in a single DB transaction
    (wipe-and-replace per the "Idempotency model" section of the
    12A-2 plan). On any apply error, raise; the caller's
    transaction handler rolls back.

    Returns ``ApplyResult`` with ``counts`` on success, ``errors``
    on validation failure (apply is not attempted)."""

    plan, errors = _parse_rows(rows)
    if errors:
        return ApplyResult(counts={}, errors=errors)

    counts = _apply_plan(
        db,
        review_session,
        plan,
        user=user,
        correlation_id=correlation_id,
    )
    return ApplyResult(counts=counts, errors=[])


def _apply_plan(
    db: Session,
    review_session: ReviewSession,
    plan: _ParsedConfig,
    *,
    user: User | None,
    correlation_id: str | None,
) -> dict[str, int]:
    counts = {
        "session": 0,
        "email_overrides": 0,
        "rtds": 0,
        "instruments": 0,
        "display_fields": 0,
        "response_fields": 0,
        "session_rule_sets": 0,
        "field_labels": 0,
        "data_shapes": 0,
    }

    counts["session"] = _apply_session_metadata(review_session, plan)
    counts["email_overrides"] = _apply_email_overrides(review_session, plan)
    # Per-session RTD table retired 2026-05-26 — ``rtds[*]`` rows
    # in old bundles are silently dropped at parse time. Instrument
    # response fields still wipe-and-replace below; that step also
    # clears the Assignments + Responses that pre-existed the
    # re-import. The pre-2026-05-26 ``_apply_rtds`` helper did the
    # same instrument wipe; we hoist it inline here.
    _wipe_instruments_and_dependents(db, review_session)
    db.flush()
    counts["session_rule_sets"] = _apply_session_rule_sets(
        db, review_session, plan
    )
    db.flush()
    inst_counts = _apply_instruments(db, review_session, plan)
    counts.update(inst_counts)
    counts["field_labels"] = _apply_field_labels(db, review_session, plan)
    counts["data_shapes"] = _apply_data_shapes(db, review_session, plan)
    db.flush()

    if user is not None:
        lifecycle.invalidate_if_validated(
            db,
            review_session=review_session,
            user=user,
            reason="settings_imported",
            correlation_id=correlation_id,
        )

    audit.write_event(
        db,
        event_type="session.settings_imported",
        summary=(
            f"Imported Settings CSV for session {review_session.code}"
        ),
        actor_user_id=user.id if user is not None else None,
        session=review_session,
        payload=audit.counts(**counts),
        correlation_id=correlation_id,
    )

    return counts


# Re-exports for the package ``__init__`` and the unit tests that
# reach for ``_ParseError`` / ``_parse_group_kind`` via the legacy
# ``_apply`` module path.
from ._apply_shared import _ParseError, _parse_group_kind  # noqa: E402, F401
