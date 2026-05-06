"""View-shape adapters for operator templates.

Translate domain objects into row tuples / dataclasses that templates
iterate over. Service modules stay business-logic-only; templates stay
markup-only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, InstrumentResponseField, ReviewSession, User
from app.services import (
    assignments,
    csv_imports,
    instruments as instruments_service,
    responses as responses_service,
    session_lifecycle as lifecycle,
)
from app.web import breadcrumbs


@dataclass
class SetupRow:
    label: str
    value: str
    manage_url: str
    manage_disabled: bool = False
    manage_disabled_reason: str | None = None


def build_setup_rows(
    db: Session, review_session: ReviewSession
) -> list[SetupRow]:
    """Rows for the Session setup card on session detail."""
    sid = review_session.id
    reviewer_count = csv_imports.existing_reviewer_count(db, sid)
    reviewee_count = csv_imports.existing_reviewee_count(db, sid)
    assignment_count = assignments.existing_count(db, sid)
    instruments = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == sid)
        ).scalars()
    )
    instrument_count = len(instruments)
    if instrument_count == 0:
        instruments_value = "Number of instruments: 0"
    else:
        any_open = any(i.accepting_responses for i in instruments)
        all_open = all(i.accepting_responses for i in instruments)
        if all_open:
            status_word = "Open"
        elif not any_open:
            status_word = "Closed"
        else:
            status_word = "Mixed"
        instruments_value = (
            f"Number of instruments: {instrument_count}, Status: {status_word}"
        )

    return [
        SetupRow(
            label="Reviewers",
            value=f"Number of reviewers: {reviewer_count}",
            manage_url=f"/operator/sessions/{sid}/reviewers",
        ),
        SetupRow(
            label="Reviewees",
            value=f"Number of reviewees: {reviewee_count}",
            manage_url=f"/operator/sessions/{sid}/reviewees",
        ),
        SetupRow(
            label="Assignments",
            value=f"Number of assignments: {assignment_count}",
            manage_url=f"/operator/sessions/{sid}/assignments",
        ),
        SetupRow(
            label="Instruments",
            value=instruments_value,
            manage_url=f"/operator/sessions/{sid}/instruments",
        ),
        SetupRow(
            label="Email Invites",
            value="—",
            manage_url=f"/operator/sessions/{sid}/setupinvite",
        ),
    ]


@dataclass
class SessionStatusPills:
    """Counts shown on the standardized session-level status row
    (rendered by ``partials/session_setup_status_row.html``). The
    same five numbers / flags appear on every session-scoped page
    so the chrome reads as a single contract."""

    reviewer_count: int
    reviewee_count: int
    assignment_count: int
    instrument_count: int
    email_invites_set_up: bool


@dataclass(frozen=True)
class InstrumentHeading:
    """Title + optional subtitle for the per-instrument heading card.

    Title lands on the H2; subtitle on a `.muted` body-weight `<p>`
    below it inside `.card.rs-instrument-card`, which sits in column 1
    of the per-instrument intro grid (`.rs-intro-grid`). Either or
    both can be ``None`` — the template only renders the heading card
    when ``title`` is truthy.

    Composition rules per `spec/reviewer-surface.md` "Above the table
    — heading + help block":

    | total_count | short_label | description | title | subtitle |
    |---|---|---|---|---|
    | >1 | set     | set       | "Page #{N}: {short_label}" | description |
    | >1 | set     | unset     | "Page #{N}: {short_label}" | None |
    | >1 | unset   | set       | "Page #{N}"                | description |
    | >1 | unset   | unset     | "Page #{N}"                | None |
    | 1  | set     | set       | "{short_label}"            | description |
    | 1  | set     | unset     | "{short_label}"            | None |
    | 1  | unset   | set       | "{description}" *          | None *     |
    | 1  | unset   | unset     | None                       | None |

    \\* The single-instrument-only-description row preserves the
    legacy heading behaviour (description renders as the H2 text)
    so operators who haven't migrated to ``short_label`` yet don't
    silently lose their per-instrument context. The spec's strict
    reading was "no heading; description shown elsewhere", but
    there's no other display path for ``Instrument.description``
    today; preserving it here is a small spec deviation in service
    of operator continuity.
    """

    title: str | None
    subtitle: str | None


def page_button_label(instrument: Instrument, position: int) -> str:
    """Label for a Page N button on the reviewer surface's action row.

    Returns ``"Page #{N}: {short_label}"`` when the operator has set
    ``Instrument.short_label`` (32-char ceiling enforced at the
    schema layer per Segment 11L); falls back to bare ``"Page #{N}"``
    otherwise.
    """
    short = (instrument.short_label or "").strip()
    if short:
        return f"Page #{position}: {short}"
    return f"Page #{position}"


def instrument_heading(
    *, instrument: Instrument, position: int, total_count: int
) -> InstrumentHeading:
    """Build the per-instrument heading title + subtitle for the
    reviewer surface, per the composition table on
    :class:`InstrumentHeading`.
    """
    short = (instrument.short_label or "").strip()
    desc = (instrument.description or "").strip() or None
    if total_count == 1:
        if short:
            return InstrumentHeading(title=short, subtitle=desc)
        if desc:
            # Legacy behaviour preserved — see the docstring's note.
            return InstrumentHeading(title=desc, subtitle=None)
        return InstrumentHeading(title=None, subtitle=None)
    # Multi-instrument: position prefix is the safety-net default.
    if short:
        return InstrumentHeading(title=f"Page #{position}: {short}", subtitle=desc)
    return InstrumentHeading(title=f"Page #{position}", subtitle=desc)


@dataclass(frozen=True)
class PageButton:
    """View-shape for a Page button on the reviewer-surface action row."""

    position: int
    label: str
    href: str
    is_current: bool


def placeholder_for_field(field: InstrumentResponseField) -> str:
    """Short hint shown inside the input box when empty, so reviewers
    know what shape a value should take. Mirrors the RTD's validation
    block; returns ``""`` for List rows or when the validation block is
    incomplete (e.g. an Integer RTD missing ``step``)."""
    validation = field.validation or {}
    data_type = field.data_type
    if data_type == "String":
        max_length = validation.get("max_length")
        if max_length is None:
            return ""
        min_length = validation.get("min_length") or 0
        return f"{int(min_length)} to {int(max_length)} char"
    if data_type in ("Integer", "Decimal"):
        min_ = validation.get("min")
        max_ = validation.get("max")
        step = validation.get("step")
        if min_ is None or max_ is None or step is None:
            return ""
        if data_type == "Integer":
            return (
                f"{int(min_)} to {int(max_)}, steps of {int(step)}"
            )
        return f"{min_:.1f} to {max_:.1f}, steps of {step:.1f}"
    return ""


def constraint_summary_for_field(field: InstrumentResponseField) -> str:
    """Short ``min-max[, steps of step]`` summary used in the
    above-table constraint row on the reviewer surface. Distinct from
    ``placeholder_for_field`` (``a to b``) — this one uses the dash
    notation requested for the summary line. Returns ``""`` when the
    validation block is incomplete or absent."""
    validation = field.validation or {}
    data_type = field.data_type
    if data_type == "String":
        max_length = validation.get("max_length")
        if max_length is None:
            return ""
        min_length = validation.get("min_length") or 0
        return f"{int(min_length)}-{int(max_length)} char"
    if data_type in ("Integer", "Decimal"):
        min_ = validation.get("min")
        max_ = validation.get("max")
        step = validation.get("step")
        if min_ is None or max_ is None or step is None:
            return ""
        if data_type == "Integer":
            return f"{int(min_)}-{int(max_)}, steps of {int(step)}"
        return f"{min_:.1f}-{max_:.1f}, steps of {step:.1f}"
    # List rows are omitted from the constraint summary — the
    # ``<select>`` already constrains the choice in the input itself.
    return ""


def _bulk_state(values: list[bool]) -> str:
    """Three-state value for a bulk toggle: ``all-on`` / ``all-off`` / ``mixed``."""
    if not values:
        return "all-off"
    on = sum(1 for v in values if v)
    if on == 0:
        return "all-off"
    if on == len(values):
        return "all-on"
    return "mixed"


def build_instruments_context(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    editing: int | None = None,
    saved: int | None = None,
    rtd_error: str | None = None,
    rtd_id: int | None = None,
    rf_save_error: str | None = None,
    editing_rtd_id: int | None = None,
    rtd_delete_blocked_id: int | None = None,
    rtd_delete_blocked_rfs: int | None = None,
    rtd_delete_blocked_instruments: int | None = None,
    rtd_delete_blocked_responses: int | None = None,
    rtd_delete_blocked_assignments: int | None = None,
    rtd_would_empty_id: int | None = None,
    rtd_would_empty_instruments: str | None = None,
) -> dict[str, Any]:
    """Build the template context for the operator instruments index.

    Runs the per-request idempotent display-field / RTD backfills
    (locked-row safety net + lazy seeds + stale-row prune + RTD seed),
    derives the editing-state machine, and packages the URL-driven
    error / cascade query params into the dict the template expects.
    Commits the backfill side-effects before returning so subsequent
    queries see the seeded rows.
    """
    instruments = list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == review_session.id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars()
    )
    # Make sure every instrument has its locked Name / Email Display
    # Fields rows. The Alembic migration backfills existing instruments;
    # this is the per-request safety net for any sessions that slip
    # through (e.g. created before the migration ran).
    for instrument in instruments:
        instruments_service.ensure_locked_display_fields(
            db, instrument=instrument
        )
    # Prune Display Fields rows whose underlying data source no longer
    # has any populated value (locked Name / Email rows are exempt and
    # always kept). Runs before the lazy seeds so the canonical seed
    # order — reviewee.* before pair_context.* — falls out naturally:
    # any stale rows are gone, then the seeds append fresh in the
    # canonical sequence.
    instruments_service.prune_unpopulated_display_fields(db, review_session)
    # Per-request idempotent backfill of the lazy-seeded display
    # fields. The reviewee / assignment imports already trigger these
    # in the happy path; calling them on every GET catches sessions
    # whose roster or assignments were imported before the lazy-seed
    # logic landed (PR #203). Cheap — both helpers short-circuit when
    # there's nothing to seed.
    instruments_service.seed_display_fields_from_reviewees(db, review_session)
    instruments_service.seed_display_fields_from_assignments(db, review_session)
    # Idempotent per-request backfill of the seeded RTD catalog.
    # Existing sessions get the rows from the Slice 4a migration; this
    # call covers any session created without going through
    # ``ensure_default_instrument`` (e.g. raw fixtures in tests).
    instruments_service.ensure_default_response_type_definitions(
        db, review_session
    )
    db.commit()

    is_ready = lifecycle.is_ready(review_session)
    can_edit = not is_ready
    # State machine: ``?editing={instrument_id}`` opens that card for
    # editing. The yellow lock card on a ``ready`` session overrides
    # everything — every per-instrument card stays locked.
    editing_instrument_id = None if is_ready else editing
    # Slice 4d: the per-instrument editing state and the RTD editing
    # state are mutually exclusive — one editing context on the page
    # at a time. If both URL params are set (e.g. via a stale link),
    # the per-instrument card wins; the RTD card stays locked.
    effective_editing_rtd_id: int | None = None
    if not is_ready and editing_instrument_id is None:
        effective_editing_rtd_id = editing_rtd_id

    # "Saved" / "not saved" pill on each per-instrument card's status
    # sub-card. An instrument is "saved" if it has at least one audit
    # event indicating an operator-driven persistence of its field
    # tables (display fields saved via bulk save, edit, add, delete,
    # or move). Pure draft instruments — only seeded rows, never
    # touched — render as "not saved".
    instrument_saved_state = instruments_service.saved_state_for_session(
        db, session_id=review_session.id
    )
    rtds = instruments_service.get_session_rtds(
        db, session_id=review_session.id
    )

    rtd_delete_blocked = (
        {
            "id": rtd_delete_blocked_id,
            "response_field_count": rtd_delete_blocked_rfs or 0,
            "instrument_count": rtd_delete_blocked_instruments or 0,
            "response_count": rtd_delete_blocked_responses or 0,
            "assignment_count": rtd_delete_blocked_assignments or 0,
        }
        if rtd_delete_blocked_id is not None
        else None
    )
    rtd_would_empty = (
        {
            "id": rtd_would_empty_id,
            "instrument_numbers": [
                n for n in (rtd_would_empty_instruments or "").split(",") if n
            ],
        }
        if rtd_would_empty_id is not None
        else None
    )

    return {
        "user": user,
        "session": review_session,
        "status_pills": session_status_pills(db, review_session),
        "instruments": instruments,
        "is_ready": is_ready,
        "can_edit": can_edit,
        "bulk_accepting_state": _bulk_state(
            [i.accepting_responses for i in instruments]
        ),
        "bulk_visibility_state": _bulk_state(
            [i.responses_visible_when_closed for i in instruments]
        ),
        "editing_instrument_id": editing_instrument_id,
        "instrument_saved_state": instrument_saved_state,
        "saved_instrument_id": saved,
        "rtds": rtds,
        "rtd_error": rtd_error,
        "rtd_error_id": rtd_id,
        "rf_save_error": rf_save_error,
        "editing_rtd_id": effective_editing_rtd_id,
        "is_some_instrument_editing": editing_instrument_id is not None,
        "is_some_rtd_unlocked": effective_editing_rtd_id is not None,
        "rtd_delete_blocked": rtd_delete_blocked,
        "rtd_would_empty": rtd_would_empty,
        "breadcrumbs": breadcrumbs.operator_session_child(
            review_session, "Instruments"
        ),
    }


def session_status_pills(
    db: Session, review_session: ReviewSession
) -> SessionStatusPills:
    sid = review_session.id
    return SessionStatusPills(
        reviewer_count=csv_imports.existing_reviewer_count(db, sid),
        reviewee_count=csv_imports.existing_reviewee_count(db, sid),
        assignment_count=assignments.existing_count(db, sid),
        instrument_count=len(
            list(
                db.execute(
                    select(Instrument).where(Instrument.session_id == sid)
                ).scalars()
            )
        ),
        # The Email Invites editor lands in Segment 15 — for now no
        # session is "set up" yet. When the editor ships, swap this
        # for a real check (e.g. a non-empty email template row).
        email_invites_set_up=False,
    )


# ---------------------------------------------------------------------------
# Segment 11H — Quick Setup card scaffold
# ---------------------------------------------------------------------------
#
# The Quick Setup card on Session Home renders four slots; each slot has
# the same outer shape (file input + Submit + count indicator + dormant
# banner container) but the controls are inert until Segment 11J wires
# them up. The scaffold pins the visual + DOM contract here so 11J's
# wiring PRs are thin diffs that flip ``is_wired=True`` and supply
# ``wire_url=…`` per slot.


@dataclass(frozen=True)
class QuickSetupSlot:
    """One slot inside the Quick Setup card on Session Home.

    11J's PRs flip ``is_wired`` and supply ``wire_url`` per slot;
    11H ships every slot with ``is_wired=False`` and the controls
    rendered ``disabled``.
    """

    key: str
    """Stable slot identifier — ``reviewers`` / ``reviewees`` /
    ``assignments`` / ``settings``. Used as the DOM-id suffix
    (``#quick-setup-{key}``) so URL fragments scroll directly to a
    slot, and as the ``data-wire-target`` value so 11J's wiring
    can locate the slot without a CSS-selector contract."""

    label: str
    """Human-readable slot label, used in the H3 heading."""

    count: int
    """Current population — count of reviewers / reviewees /
    assignments. ``0`` for the configuration-import slot."""

    count_summary: str
    """Pre-rendered count copy, e.g. ``"8 currently"`` /
    ``"none yet"`` / ``"104 currently, full-matrix"``."""

    mode: str
    """``"file_upload"`` for slots 1, 2, 4; ``"rule_or_csv"`` for
    slot 3 (Assignments). Slot mode controls which inputs render
    inside the slot body."""

    is_wired: bool
    """``True`` once 11J / 12A wires the slot. While ``False`` the
    slot's controls render ``disabled`` and a ``coming_in`` tooltip
    surfaces the wiring PR's name."""

    wire_url: str | None
    """POST URL once ``is_wired=True``. ``None`` while inert."""

    coming_in: str | None
    """``"Wired in Segment 11J PR A"``-style tooltip while
    ``is_wired=False``. ``None`` once wired."""


@dataclass(frozen=True)
class QuickSetupContext:
    """Page-shape adapter output for the Quick Setup card.

    ``slots`` renders top-to-bottom in the order given; the card
    iterates and the ``quick_setup_slot`` macro renders each one.

    Two greying triggers, mutually exclusive:

    - ``is_disabled`` — session is Activated (``ready``). Whole
      card carries ``.card.disabled`` plain-greying per
      ``spec/session_home.md``; the Lock / Unlock button is not
      rendered (the operator's path forward is Pause, not unlock).
    - ``is_locked`` — session is editable (``draft`` / ``validated``)
      but the card body is greyed pending an explicit Unlock click.
      The body wrapper gets ``.locked``; the Lock / Unlock button
      sits outside the wrapper so it stays vivid. Defaults ``True``
      whenever the card is editable so the operator must
      deliberately unlock before any setup change. The button is a
      placeholder in 11H — Segment 11J wires the toggle.

    ``title`` overrides the H2 text. Session Home uses the default
    ``"Quick Setup"``; the new-session preview variant uses
    ``"Quick setup (optional)"`` to convey that the card surfaces
    early as a hint about post-creation setup paths.

    ``show_lock_toggle`` gates the Lock / Unlock footer button.
    Session Home renders it whenever the card is editable; the
    new-session preview variant suppresses it (the card is always
    unlocked there because there's nothing yet to lock).
    """

    slots: list[QuickSetupSlot]
    is_disabled: bool
    is_locked: bool
    description: str
    title: str = "Quick Setup"
    show_lock_toggle: bool = True


def build_quick_setup_context(
    db: Session, review_session: ReviewSession
) -> QuickSetupContext:
    sid = review_session.id
    # Per spec/session_home.md, Quick Setup disables when the session is
    # Activated (``ready``); ``closed`` is a reserved future state that
    # would also disable, but the predicate doesn't exist yet — when
    # ``closed`` ships, extend this check.
    is_disabled = lifecycle.is_ready(review_session)

    reviewer_count = csv_imports.existing_reviewer_count(db, sid)
    reviewee_count = csv_imports.existing_reviewee_count(db, sid)
    assignment_count = assignments.existing_count(db, sid)
    # ``assignment_mode`` is a stored string today (e.g. "FullMatrix"
    # / "Manual"); the column is plain Text, not a SQLAlchemy enum.
    assignment_mode: str | None = review_session.assignment_mode

    slots = [
        QuickSetupSlot(
            key="reviewers",
            label="Reviewers",
            count=reviewer_count,
            count_summary=(
                f"{reviewer_count} currently"
                if reviewer_count
                else "none yet"
            ),
            mode="file_upload",
            is_wired=False,
            wire_url=None,
            coming_in="Wired in Segment 11J PR A",
        ),
        QuickSetupSlot(
            key="reviewees",
            label="Reviewees",
            count=reviewee_count,
            count_summary=(
                f"{reviewee_count} currently"
                if reviewee_count
                else "none yet"
            ),
            mode="file_upload",
            is_wired=False,
            wire_url=None,
            coming_in="Wired in Segment 11J PR A",
        ),
        QuickSetupSlot(
            key="assignments",
            label="Assignments",
            count=assignment_count,
            count_summary=_assignment_summary(assignment_count, assignment_mode),
            mode="rule_or_csv",
            is_wired=False,
            wire_url=None,
            coming_in="Wired in Segment 11J PR B",
        ),
        QuickSetupSlot(
            key="settings",
            label="Session settings",
            count=0,
            count_summary="upload a session-settings CSV",
            mode="file_upload",
            is_wired=False,
            wire_url=None,
            coming_in="Wired in Segment 12A PR 6",
        ),
    ]

    description = (
        "Setup edits are paused while the session is Activated. "
        "Pause the session to re-enable bulk setup."
        if is_disabled
        else "Bulk-populate reviewers, reviewees, and assignments "
        "from files or rules in one place."
    )

    # Lock the card by default whenever it's editable. The toggle
    # itself is wired in 11J; 11H ships the lock state at fresh-page-
    # load default (locked) without state persistence.
    is_locked = not is_disabled

    return QuickSetupContext(
        slots=slots,
        is_disabled=is_disabled,
        is_locked=is_locked,
        description=description,
        # Title stays the default "Quick Setup" on Session Home.
        # Lock toggle renders whenever the card is editable; on
        # Activated sessions the operator's path forward is Pause,
        # not Unlock, so the toggle is suppressed.
        show_lock_toggle=not is_disabled,
    )


def build_new_session_quick_setup_context() -> QuickSetupContext:
    """Quick Setup placeholder for the ``/operator/sessions/new`` page.

    There is no session row yet, so all four slots show zero counts
    and no wire URLs. The card is always unlocked (``is_locked=False``)
    and the Lock / Unlock toggle is suppressed (the lock concept has
    nothing to lock here). Heading reads ``"Quick setup (optional)"``
    to convey this is a forward-looking hint, not a working surface.
    """

    slots = [
        QuickSetupSlot(
            key="reviewers",
            label="Reviewers",
            count=0,
            count_summary="none yet",
            mode="file_upload",
            is_wired=False,
            wire_url=None,
            coming_in="Wired in Segment 11J PR A",
        ),
        QuickSetupSlot(
            key="reviewees",
            label="Reviewees",
            count=0,
            count_summary="none yet",
            mode="file_upload",
            is_wired=False,
            wire_url=None,
            coming_in="Wired in Segment 11J PR A",
        ),
        QuickSetupSlot(
            key="assignments",
            label="Assignments",
            count=0,
            count_summary="none yet",
            mode="rule_or_csv",
            is_wired=False,
            wire_url=None,
            coming_in="Wired in Segment 11J PR B",
        ),
        QuickSetupSlot(
            key="settings",
            label="Session settings",
            count=0,
            count_summary="upload a session-settings CSV",
            mode="file_upload",
            is_wired=False,
            wire_url=None,
            coming_in="Wired in Segment 12A PR 6",
        ),
    ]

    return QuickSetupContext(
        slots=slots,
        is_disabled=False,
        is_locked=False,
        description=(
            "Bulk-populate reviewers, reviewees, and assignments "
            "from files or rules in one place — available on "
            "Session Home after the session is created."
        ),
        title="Quick setup (optional)",
        show_lock_toggle=False,
    )


def _assignment_summary(count: int, mode: str | None) -> str:
    if not count:
        return "none yet"
    if mode:
        return f"{count} currently, {mode}"
    return f"{count} currently"


# ---------------------------------------------------------------------------
# Segment 11H — Extract Data card scaffold
# ---------------------------------------------------------------------------
#
# The Extract Data card on Session Home renders five per-entity rows + a
# "Download all" zip-bundle footer. Read-only by nature: Segment 12A's
# PRs wire each row's Download button live; the card stays interactive
# in every lifecycle state (no lock-card wrap).


@dataclass(frozen=True)
class ExtractDataRow:
    """One row inside the Extract Data card on Session Home.

    12A's PRs flip ``is_wired`` and supply ``download_url`` per row;
    11H ships every row inert.
    """

    key: str
    """Stable identifier — ``settings`` / ``reviewers`` / ``reviewees``
    / ``assignments`` / ``responses`` / ``bundle``. DOM id is
    ``#extract-data-{key}``."""

    label: str

    filename: str
    """Final filename the download will carry, e.g.
    ``session-CS101-reviewers.csv``. Surfaced to the operator as a
    secondary line so they know what to expect."""

    count: int
    count_summary: str

    is_wired: bool
    download_url: str | None
    coming_in: str | None


@dataclass(frozen=True)
class ExtractDataContext:
    rows: list[ExtractDataRow]
    bundle: ExtractDataRow


def build_extract_data_context(
    db: Session, review_session: ReviewSession
) -> ExtractDataContext:
    sid = review_session.id
    code = review_session.code or "session"

    reviewer_count = csv_imports.existing_reviewer_count(db, sid)
    reviewee_count = csv_imports.existing_reviewee_count(db, sid)
    assignment_count = assignments.existing_count(db, sid)
    response_count = responses_service.session_response_count(db, sid)
    instrument_count = len(
        list(
            db.execute(
                select(Instrument).where(Instrument.session_id == sid)
            ).scalars()
        )
    )

    rows = [
        ExtractDataRow(
            key="settings",
            label="Session settings",
            filename=f"session-{code}-settings.csv",
            count=instrument_count,
            count_summary=_extract_summary("instrument", instrument_count),
            is_wired=False,
            download_url=None,
            coming_in="Wired in Segment 12A PR 1",
        ),
        ExtractDataRow(
            key="reviewers",
            label="Reviewers",
            filename=f"session-{code}-reviewers.csv",
            count=reviewer_count,
            count_summary=_extract_summary("reviewer", reviewer_count),
            is_wired=False,
            download_url=None,
            coming_in="Wired in Segment 12A PR 3",
        ),
        ExtractDataRow(
            key="reviewees",
            label="Reviewees",
            filename=f"session-{code}-reviewees.csv",
            count=reviewee_count,
            count_summary=_extract_summary("reviewee", reviewee_count),
            is_wired=False,
            download_url=None,
            coming_in="Wired in Segment 12A PR 3",
        ),
        ExtractDataRow(
            key="assignments",
            label="Assignments",
            filename=f"session-{code}-assignments.csv",
            count=assignment_count,
            count_summary=_extract_summary("assignment", assignment_count),
            is_wired=False,
            download_url=None,
            coming_in="Wired in Segment 12A PR 4",
        ),
        ExtractDataRow(
            key="responses",
            label="Responses",
            filename=f"session-{code}-responses.csv",
            count=response_count,
            count_summary=_extract_summary("response", response_count),
            is_wired=False,
            download_url=None,
            coming_in="Wired in Segment 12A PR 5",
        ),
    ]

    bundle = ExtractDataRow(
        key="bundle",
        label="Download all",
        filename=f"session-{code}-export.zip",
        count=sum(r.count for r in rows),
        count_summary="zip of all five CSVs above",
        is_wired=False,
        download_url=None,
        coming_in="Wired in Segment 12A PR 6",
    )

    return ExtractDataContext(rows=rows, bundle=bundle)


def _extract_summary(noun: str, count: int) -> str:
    if count == 0:
        return f"0 {noun}s"
    if count == 1:
        return f"1 {noun}"
    return f"{count} {noun}s"
