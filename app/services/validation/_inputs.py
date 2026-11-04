"""What every rule reads: ``ValidationRule``, ``ValidationInputs`` and
``load_validation_inputs``. Segment 20E rung 4b, moved unchanged from
``validation.py``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import ColumnElement, select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    InstrumentDisplayField,
    InstrumentResponseField,
    Observer,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.schemas.validation import Severity, ValidationIssue

# --------------------------------------------------------------------------- #
# Rule shape
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ValidationRule:
    """One pre-activation check.

    ``key`` is the stable identifier the audit log + UI surfaces
    use (e.g. ``"reviewers.duplicate_email"``); change it only via
    a migration once 11K's audit-event detail schema lands.

    ``check`` runs the actual query and yields raw
    ``ValidationIssue`` instances; the orchestrator stamps
    ``rule_key`` / ``fix_url`` / ``fix_page_label`` and ``source``
    onto each issue. ``fix_anchor`` is set per-issue by the check
    itself when the issue points at a specific row (e.g. the
    duplicate-email rule sets the anchor to the first duplicate's
    ``#reviewer-row-{id}``).
    """

    key: str
    source: str
    severity: Severity
    why: str
    fix_url: Callable[[ReviewSession], str]
    fix_page_label: str
    check: Callable[
        [Session, ReviewSession, ValidationInputs],
        Iterable[ValidationIssue],
    ]


@dataclass(frozen=True)
class ValidationInputs:
    """What one report run loads once, for every check to read.

    Twenty-two checks each loading for themselves is how two of them
    come to disagree about what "the session's instruments" means. It
    is also why one run issued 43 queries for 21 distinct reads
    (19R Item 5; ``docs/performance.md`` Finding 6).

    **Measured, not guessed.** This carries exactly what more than one
    check loaded: the instrument list, the three rosters, the roster
    non-empty probes (now ``bool()`` over a list already loaded), the
    per-instrument response-field / visible-response-field /
    display-field presence, and ``included_count_per_instrument``. A
    load only one check makes stays in that check.

    **Per run, never a cache.** :func:`validate_session_setup` builds
    one of these per call and drops it. A check must not see a roster
    older than the request that asked.
    """

    instruments: tuple[Instrument, ...]
    reviewers: tuple[Reviewer, ...]
    reviewees: tuple[Reviewee, ...]
    observers: tuple[Observer, ...]
    #: Instrument ids with at least one ``InstrumentResponseField`` row.
    instruments_with_response_fields: frozenset[int]
    #: …with at least one ``visible=True`` response field.
    instruments_with_visible_response_fields: frozenset[int]
    #: …with at least one ``InstrumentDisplayField`` row.
    instruments_with_display_fields: frozenset[int]
    included_count_by_instrument: Mapping[int, int]
    #: Loads filled on first use and shared for the run, for checks that
    #: need a heavier read only some runs reach: ``staleness``, the
    #: engine's per-instrument verdicts (findings E4's cold read).
    _memo: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    @property
    def active_reviewees(self) -> tuple[Reviewee, ...]:
        """The roster filtered in Python rather than re-queried."""
        return tuple(r for r in self.reviewees if r.status == "active")


def load_validation_inputs(
    db: Session, review_session: ReviewSession
) -> ValidationInputs:
    """Load everything more than one registered rule needs, once.

    The three rosters are ordered by id so that "the first duplicate's
    row" in a ``fix_anchor`` is a fact rather than whatever the dialect
    happened to return — SQLite grants an unordered ``SELECT`` the
    insertion order anyway, so no test fails if the clause goes, which
    is exactly why it is stated here once instead of per rule.

    The per-instrument presence sets join through
    ``Instrument.session_id`` rather than an ``IN`` over instrument
    ids. The id list is short today, but ``IN`` is the shape that hits
    SQLite's 999-variable ceiling once it is not.
    """
    # Local import: ``assignments`` imports this module's siblings.
    from app.services import assignments as assignments_service

    def _instrument_ids(
        field_model: type[InstrumentResponseField]
        | type[InstrumentDisplayField],
        *extra: ColumnElement[bool],
    ) -> frozenset[int]:
        stmt = (
            select(field_model.instrument_id)
            .join(Instrument, Instrument.id == field_model.instrument_id)
            .where(Instrument.session_id == review_session.id)
            .distinct()
        )
        for clause in extra:
            stmt = stmt.where(clause)
        return frozenset(row[0] for row in db.execute(stmt).all())

    return ValidationInputs(
        instruments=tuple(
            db.execute(
                select(Instrument)
                .where(Instrument.session_id == review_session.id)
                .order_by(Instrument.order, Instrument.id)
            ).scalars()
        ),
        reviewers=tuple(
            db.execute(
                select(Reviewer)
                .where(Reviewer.session_id == review_session.id)
                .order_by(Reviewer.id)
            ).scalars()
        ),
        reviewees=tuple(
            db.execute(
                select(Reviewee)
                .where(Reviewee.session_id == review_session.id)
                .order_by(Reviewee.id)
            ).scalars()
        ),
        observers=tuple(
            db.execute(
                select(Observer)
                .where(Observer.session_id == review_session.id)
                .order_by(Observer.id)
            ).scalars()
        ),
        instruments_with_response_fields=_instrument_ids(
            InstrumentResponseField
        ),
        instruments_with_visible_response_fields=_instrument_ids(
            InstrumentResponseField, InstrumentResponseField.visible.is_(True)
        ),
        instruments_with_display_fields=_instrument_ids(
            InstrumentDisplayField
        ),
        included_count_by_instrument=(
            assignments_service.included_count_per_instrument(
                db, review_session.id
            )
        ),
    )
