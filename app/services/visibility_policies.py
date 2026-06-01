"""Per-instrument visibility policy upserts.

Owns the persistence layer for the Band 3 visibility editor on
the Instruments page (W15). One row per ``(instrument, audience)``
on ``instrument_view_policies``; up to three audiences per
instrument (``peer_reviewer`` / ``reviewee`` / ``observer``).
Operator-facing modes (Raw / Anonymized / Summarized) encode to
``(granularity, identification)`` pairs stored per-window
(``while_ongoing_*`` / ``after_release_*``) via the helpers
below.

See ``spec/visibility_policy.md`` for the full functional
contract and ``guide/archive/participant_model_upgrade.md`` §3.3 for
the design rationale + audience-scope semantics.

Audit emission: every write emits one
``instrument.view_policy_set`` event per ``(instrument,
audience)`` row touched, via the canonical ``audit.changes``
envelope. No-op writes (no change) emit nothing.
"""

from __future__ import annotations

from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    InstrumentViewPolicy,
    ReviewSession,
    User,
)
from app.services import audit
from app.services import session_lifecycle as lifecycle


# Three audiences are operator-configurable; the operator audience
# is implicit (always sees everything) and never stored.
AUDIENCES: tuple[str, ...] = ("peer_reviewer", "reviewee", "observer")


# Operator-facing modes ↔ stored axes.
#
# Aggregated + identified is incoherent ("averaging Alice" isn't a
# thing) so only three of the four combinations are accepted.
MODE_LABELS: dict[str, tuple[str, str]] = {
    "raw": ("row", "identified"),
    "anonymized": ("row", "deidentified"),
    "summarized": ("aggregated", "deidentified"),
}


# Per-audience-per-window valid modes for the redesigned Band 3
# editor (W15 follow-on). Each entry's value set is the modes the
# operator may pick for that (audience, window) cell; ``None``
# means "off in this window" and is always allowed except where
# noted.
#
# - peer_reviewer Session-ongoing: **always Raw** — the operator
#   cannot turn the reviewer's own-work-during-session view off
#   (it's the baseline; mirrors how Operator always sees
#   everything). Editor renders this cell as a static "Raw
#   responses" pill.
# - peer_reviewer Responses-released: ``None`` / ``raw`` /
#   ``summarized``. After release the reviewer can either see
#   nothing, see their own raw submitted responses (read-only —
#   no recall / resubmit), or see an Anonymized summary across
#   the responses they themselves authored (e.g. a histogram
#   across the reviewees they reviewed on this instrument). Per-
#   pair flow stays strict: the reviewer's grant only covers
#   responses they themselves keyed in; the summarized form just
#   aggregates the multi-reviewee fan-out of those rows.
#   ``anonymized`` stays disallowed — anonymising one's own work
#   against oneself is incoherent.
# - reviewee Session-ongoing: **always off** — the strict
#   per-pair flow says reviewees don't see responses while the
#   review is in flight. Editor renders this cell as a static
#   "—" pill.
# - reviewee Responses-released: any of the three modes or off.
# - observer (both windows): any of the three modes or off.

_PER_CELL_VALID_MODES: dict[tuple[str, str], frozenset[str | None]] = {
    ("peer_reviewer", "while_ongoing"): frozenset({"raw"}),
    ("peer_reviewer", "after_release"): frozenset(
        {None, "raw", "summarized"}
    ),
    ("reviewee", "while_ongoing"): frozenset({None}),
    ("reviewee", "after_release"): frozenset(
        {None, "raw", "anonymized", "summarized"}
    ),
    ("observer", "while_ongoing"): frozenset(
        {None, "raw", "anonymized", "summarized"}
    ),
    ("observer", "after_release"): frozenset(
        {None, "raw", "anonymized", "summarized"}
    ),
}


def valid_modes_for_cell(
    audience: str, window: str
) -> frozenset[str | None]:
    """Return the set of allowed modes for the ``(audience,
    window)`` cell in the Band 3 editor. Includes ``None`` when
    "off in this window" is a permitted state. Used by the
    editor / view-adapter to drive the chip cycle, and by the
    service-layer validator below."""
    return _PER_CELL_VALID_MODES[(audience, window)]


class VisibilityPolicyError(ValueError):
    """Raised when a visibility-policy upsert violates an invariant.

    Codes:
    - ``invalid_audience`` — ``audience`` not in :data:`AUDIENCES`.
    - ``invalid_mode`` — ``mode`` outside the per-(audience, window)
      set.
    - ``observer_tag_misuse`` — non-NULL ``observer_tag`` supplied
      for a non-observer audience.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def encode_mode(mode: str) -> tuple[str, str]:
    """Map an operator-facing mode label to the
    ``(granularity, identification)`` pair stored on
    :class:`InstrumentViewPolicy`. Raises
    :class:`VisibilityPolicyError` with code ``invalid_mode`` on
    unknown labels."""
    if mode not in MODE_LABELS:
        raise VisibilityPolicyError(
            "invalid_mode",
            f"mode must be one of {sorted(MODE_LABELS)}; got {mode!r}.",
        )
    return MODE_LABELS[mode]


def decode_mode(granularity: str, identification: str) -> str:
    """Reverse of :func:`encode_mode`. Returns ``"raw"`` /
    ``"anonymized"`` / ``"summarized"``. Raises
    :class:`VisibilityPolicyError` on the reserved-incoherent
    ``aggregated``+``identified`` pair."""
    for mode, pair in MODE_LABELS.items():
        if pair == (granularity, identification):
            return mode
    raise VisibilityPolicyError(
        "invalid_mode",
        f"granularity={granularity!r} + identification="
        f"{identification!r} is not a valid stored mode.",
    )


def list_for_instrument(
    db: Session, instrument_id: int
) -> dict[str, InstrumentViewPolicy]:
    """Read every persisted policy row for the instrument, keyed
    by audience. Audiences with no row simply aren't in the dict —
    the resolver treats a missing row as "this audience cannot
    view this instrument in any form".
    """
    rows = db.execute(
        select(InstrumentViewPolicy).where(
            InstrumentViewPolicy.instrument_id == instrument_id
        )
    ).scalars()
    return {row.audience: row for row in rows}


def decode_pair_to_mode(
    granularity: str | None, identification: str | None
) -> str | None:
    """Decode a per-window ``(granularity, identification)`` pair
    into an operator-facing mode (``"raw"`` / ``"anonymized"`` /
    ``"summarized"``). ``None`` on either side means "off in this
    window" → returns ``None``. The reserved-incoherent
    ``aggregated`` + ``identified`` pair also returns ``None`` so
    a corrupt row reads as "off" rather than 500ing.
    """
    if granularity is None or identification is None:
        return None
    try:
        return decode_mode(granularity, identification)
    except VisibilityPolicyError:
        return None


def resolve_mode(
    policy: InstrumentViewPolicy | None,
    *,
    while_ongoing_open: bool,
    after_release_open: bool,
) -> str | None:
    """Pick the operator-facing mode that applies right now for
    one ``(instrument, audience)`` grant.

    Inputs: the persisted policy row (or ``None`` if no row
    exists), plus two booleans describing which session-level
    window is currently open. Returns ``"raw"`` / ``"anonymized"``
    / ``"summarized"`` / ``None`` — ``None`` means "the audience
    cannot view this instrument right now" and the caller renders
    nothing.

    Window precedence: when both windows are open at once (a
    session whose release window happens to start before the
    deadline arrives), ``after_release`` wins. Operator
    semantics align — picking a mode under "Responses released"
    is the operator's explicit "this is what gets shown once the
    release window opens"; picking a session-ongoing mode is the
    pre-release shape. If only one window is open, that
    window's mode applies. If neither is open, the audience
    sees nothing regardless of stored state.

    A missing row, or a row whose relevant window pair is
    ``(NULL, NULL)``, returns ``None``.
    """
    if policy is None:
        return None
    if after_release_open:
        mode = decode_pair_to_mode(
            policy.after_release_granularity,
            policy.after_release_identification,
        )
        if mode is not None:
            return mode
    if while_ongoing_open:
        return decode_pair_to_mode(
            policy.while_ongoing_granularity,
            policy.while_ongoing_identification,
        )
    return None


def _validate_per_window(
    *,
    audience: str,
    while_ongoing_mode: str | None,
    after_release_mode: str | None,
    observer_tag: str | None,
) -> None:
    """Per-(audience, window) cell validation for the redesigned
    Band 3 editor. Same error codes as :func:`_validate` so the
    route translates uniformly to 422."""
    if audience not in AUDIENCES:
        raise VisibilityPolicyError(
            "invalid_audience",
            f"audience must be one of {sorted(AUDIENCES)}; got "
            f"{audience!r}.",
        )
    for window_name, mode in (
        ("while_ongoing", while_ongoing_mode),
        ("after_release", after_release_mode),
    ):
        allowed = _PER_CELL_VALID_MODES[(audience, window_name)]
        if mode not in allowed:
            raise VisibilityPolicyError(
                "invalid_mode",
                f"audience {audience!r} {window_name} cell only "
                f"accepts modes in "
                f"{sorted(repr(v) for v in allowed)}; got {mode!r}.",
            )
    if observer_tag is not None and audience != "observer":
        raise VisibilityPolicyError(
            "observer_tag_misuse",
            "observer_tag is only meaningful for the observer "
            "audience.",
        )


def upsert_policy(
    db: Session,
    *,
    review_session: ReviewSession,
    instrument: Instrument,
    audience: str,
    while_ongoing_mode: str | None,
    after_release_mode: str | None,
    observer_tag: str | None = None,
    user: User,
    correlation_id: str | None = None,
) -> tuple[InstrumentViewPolicy, dict[str, list[object]]]:
    """Insert or update the ``(instrument, audience)`` row.

    Per-window mode semantics:

    - ``while_ongoing_mode`` — the audience's mode during
      ``[sessions.activated_at, sessions.deadline)``. ``None``
      means "off in this window".
    - ``after_release_mode`` — the audience's mode during
      ``[sessions.responses_release_at,
      sessions.responses_release_until)``. ``None`` means "off
      in this window".
    - Both ``None`` ⇒ this audience cannot view this instrument
      in any form. Both same value ⇒ the legacy
      ``visible_when = "throughout"`` shape.

    Returns the persisted row plus a ``changes`` dict (empty when
    no field changed). Only emits ``instrument.view_policy_set``
    when ``changes`` is non-empty.

    Validates per-(audience, window) — Reviewer Session-ongoing
    must be ``"raw"`` (baseline self-view always on); Reviewee
    Session-ongoing must be ``None``; the others accept the
    three coherent modes plus ``None``.
    """
    _validate_per_window(
        audience=audience,
        while_ongoing_mode=while_ongoing_mode,
        after_release_mode=after_release_mode,
        observer_tag=observer_tag,
    )

    while_ongoing_pair: tuple[str | None, str | None] = (None, None)
    after_release_pair: tuple[str | None, str | None] = (None, None)
    if while_ongoing_mode is not None:
        while_ongoing_pair = encode_mode(while_ongoing_mode)
    if after_release_mode is not None:
        after_release_pair = encode_mode(after_release_mode)

    existing = db.execute(
        select(InstrumentViewPolicy).where(
            InstrumentViewPolicy.instrument_id == instrument.id,
            InstrumentViewPolicy.audience == audience,
        )
    ).scalar_one_or_none()

    proposed = {
        "while_ongoing_granularity": while_ongoing_pair[0],
        "while_ongoing_identification": while_ongoing_pair[1],
        "after_release_granularity": after_release_pair[0],
        "after_release_identification": after_release_pair[1],
        "observer_tag": observer_tag,
    }
    changes: dict[str, list[object]] = {}
    if existing is None:
        # On insert every column is a "change" from default →
        # the chosen value, so the audit envelope records the
        # full snapshot.
        for field, new_value in proposed.items():
            changes[field] = [None, new_value]
        row = InstrumentViewPolicy(
            instrument_id=instrument.id,
            audience=audience,
            **proposed,
        )
        db.add(row)
    else:
        for field, new_value in proposed.items():
            old_value = getattr(existing, field)
            if old_value != new_value:
                changes[field] = [old_value, new_value]
                setattr(existing, field, new_value)
        row = existing

    if not changes:
        return row, {}

    lifecycle.invalidate_if_validated(
        db,
        review_session=review_session,
        user=user,
        reason="instrument_view_policy_set",
        correlation_id=correlation_id,
    )
    db.flush()

    audit.write_event(
        db,
        event_type="instrument.view_policy_set",
        summary=(
            f"Visibility for instrument "
            f"{instrument.short_label or instrument.name or instrument.id} "
            f"({audience}) updated"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.changes(changes),
        refs={"instrument_id": instrument.id, "policy_id": row.id},
        correlation_id=correlation_id,
    )
    return row, changes


def upsert_many(
    db: Session,
    *,
    review_session: ReviewSession,
    instrument: Instrument,
    rows: Iterable[dict[str, object]],
    user: User,
    correlation_id: str | None = None,
) -> list[tuple[str, dict[str, list[object]]]]:
    """Upsert several audience rows in one call. ``rows`` is an
    iterable of dicts with keys ``audience`` /
    ``while_ongoing_mode`` / ``after_release_mode`` / optional
    ``observer_tag``. Each mode value is either ``None``
    ("off in this window") or one of the operator-facing labels
    ``"raw"`` / ``"anonymized"`` / ``"summarized"``.

    Validation is per-row — the first violation raises; rows
    already applied stay flushed because the route layer wraps
    the whole save in a transaction. Returns the list of
    ``(audience, changes)`` pairs in input order; ``changes`` is
    empty when the row was a no-op.

    Commits the transaction at the end (matches the rest of the
    services package's commit-at-the-edge convention)."""

    def _mode_or_none(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    result: list[tuple[str, dict[str, list[object]]]] = []
    for row in rows:
        _, changes = upsert_policy(
            db,
            review_session=review_session,
            instrument=instrument,
            audience=str(row["audience"]),
            while_ongoing_mode=_mode_or_none(row.get("while_ongoing_mode")),
            after_release_mode=_mode_or_none(row.get("after_release_mode")),
            observer_tag=(
                str(row["observer_tag"])
                if row.get("observer_tag") is not None
                else None
            ),
            user=user,
            correlation_id=correlation_id,
        )
        result.append((str(row["audience"]), changes))
    db.commit()
    return result


__all__ = [
    "AUDIENCES",
    "MODE_LABELS",
    "VisibilityPolicyError",
    "decode_mode",
    "decode_pair_to_mode",
    "encode_mode",
    "list_for_instrument",
    "resolve_mode",
    "upsert_many",
    "upsert_policy",
    "valid_modes_for_cell",
]
