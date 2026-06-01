"""Per-instrument visibility policy upserts.

Owns the persistence layer for the Band 3 visibility editor on
the Instruments page (W15). One row per ``(instrument, audience)``
on ``instrument_view_policies``; up to three audiences per
instrument (``peer_reviewer`` / ``reviewee`` / ``observer``).
Operator-facing modes (Raw / Anonymized / Summarized) encode to
the two underlying ``granularity`` + ``identification`` columns
via the helpers below.

See ``spec/visibility_policy.md`` for the full functional
contract and ``guide/participant_model_upgrade.md`` §3.3 for
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


VALID_VISIBLE_WHEN: frozenset[str] = frozenset(
    {"while_ongoing", "after_release", "throughout", "always"}
)


# Per-audience valid mode + window vocabularies the editor lets the
# operator pick from. The DB doesn't constrain these (the
# ``always`` value is reserved for operator forward-compatibility);
# the service rejects anything outside the per-audience set so a
# direct API call can't bypass the editor.

PEER_REVIEWER_MODES: frozenset[str] = frozenset({"raw"})
PEER_REVIEWER_WHENS: frozenset[str] = frozenset(
    {"while_ongoing", "throughout"}
)

REVIEWEE_OBSERVER_MODES: frozenset[str] = frozenset(
    {"raw", "anonymized", "summarized"}
)
REVIEWEE_OBSERVER_WHENS: frozenset[str] = frozenset(
    {"while_ongoing", "after_release", "throughout"}
)


class VisibilityPolicyError(ValueError):
    """Raised when a visibility-policy upsert violates an invariant.

    Codes:
    - ``invalid_audience`` — ``audience`` not in :data:`AUDIENCES`.
    - ``invalid_mode`` — ``mode`` outside the per-audience set.
    - ``invalid_visible_when`` — ``visible_when`` outside the
      per-audience set.
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


def _validate(
    *,
    audience: str,
    mode: str,
    visible_when: str,
    observer_tag: str | None,
) -> None:
    if audience not in AUDIENCES:
        raise VisibilityPolicyError(
            "invalid_audience",
            f"audience must be one of {sorted(AUDIENCES)}; got "
            f"{audience!r}.",
        )
    valid_modes = (
        PEER_REVIEWER_MODES
        if audience == "peer_reviewer"
        else REVIEWEE_OBSERVER_MODES
    )
    if mode not in valid_modes:
        raise VisibilityPolicyError(
            "invalid_mode",
            f"audience {audience!r} only accepts mode in "
            f"{sorted(valid_modes)}; got {mode!r}.",
        )
    valid_whens = (
        PEER_REVIEWER_WHENS
        if audience == "peer_reviewer"
        else REVIEWEE_OBSERVER_WHENS
    )
    if visible_when not in valid_whens:
        raise VisibilityPolicyError(
            "invalid_visible_when",
            f"audience {audience!r} only accepts visible_when in "
            f"{sorted(valid_whens)}; got {visible_when!r}.",
        )
    if observer_tag is not None and audience != "observer":
        raise VisibilityPolicyError(
            "observer_tag_misuse",
            "observer_tag is only meaningful for the observer "
            "audience.",
        )


def list_for_instrument(
    db: Session, instrument_id: int
) -> dict[str, InstrumentViewPolicy]:
    """Read every persisted policy row for the instrument, keyed
    by audience. Audiences with no row simply aren't in the dict —
    the resolver treats a missing row as ``enabled = FALSE``.
    """
    rows = db.execute(
        select(InstrumentViewPolicy).where(
            InstrumentViewPolicy.instrument_id == instrument_id
        )
    ).scalars()
    return {row.audience: row for row in rows}


def upsert_policy(
    db: Session,
    *,
    review_session: ReviewSession,
    instrument: Instrument,
    audience: str,
    enabled: bool,
    mode: str,
    visible_when: str,
    observer_tag: str | None = None,
    user: User,
    correlation_id: str | None = None,
) -> tuple[InstrumentViewPolicy, dict[str, list[object]]]:
    """Insert or update the ``(instrument, audience)`` row.

    Returns the persisted row plus a ``changes`` dict (empty when
    no field changed). Only emits ``instrument.view_policy_set``
    when ``changes`` is non-empty.

    Validates the per-audience vocabulary; the caller's route
    layer should translate :class:`VisibilityPolicyError` to HTTP
    422.
    """
    _validate(
        audience=audience,
        mode=mode,
        visible_when=visible_when,
        observer_tag=observer_tag,
    )

    granularity, identification = encode_mode(mode)
    existing = db.execute(
        select(InstrumentViewPolicy).where(
            InstrumentViewPolicy.instrument_id == instrument.id,
            InstrumentViewPolicy.audience == audience,
        )
    ).scalar_one_or_none()

    # S14 — mirror-write the per-window pair columns alongside
    # the legacy (enabled, granularity, identification,
    # visible_when) quadruple. The pairs encode the audience's
    # mode in each window; NULL ≡ "off in this window".
    # ``always`` is treated as ``throughout`` (sets both pairs)
    # — the legacy reserved-for-operator value never reached
    # the participant-facing audiences in practice.
    if not enabled:
        per_window_pairs = {
            "while_ongoing_granularity": None,
            "while_ongoing_identification": None,
            "after_release_granularity": None,
            "after_release_identification": None,
        }
    else:
        sets_while = visible_when in ("while_ongoing", "throughout", "always")
        sets_after = visible_when in ("after_release", "throughout", "always")
        per_window_pairs = {
            "while_ongoing_granularity": (
                granularity if sets_while else None
            ),
            "while_ongoing_identification": (
                identification if sets_while else None
            ),
            "after_release_granularity": (
                granularity if sets_after else None
            ),
            "after_release_identification": (
                identification if sets_after else None
            ),
        }

    proposed = {
        "enabled": enabled,
        "granularity": granularity,
        "identification": identification,
        "visible_when": visible_when,
        **per_window_pairs,
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
    iterable of dicts with keys ``audience`` / ``enabled`` /
    ``mode`` / ``visible_when`` / optional ``observer_tag``.
    Validation is per-row — the first violation raises; rows
    already applied stay flushed because the route layer wraps the
    whole save in a transaction. Returns the list of
    ``(audience, changes)`` pairs in input order; ``changes`` is
    empty when the row was a no-op.

    Commits the transaction at the end (matches the rest of the
    services package's commit-at-the-edge convention)."""
    result: list[tuple[str, dict[str, list[object]]]] = []
    for row in rows:
        _, changes = upsert_policy(
            db,
            review_session=review_session,
            instrument=instrument,
            audience=str(row["audience"]),
            enabled=bool(row["enabled"]),
            mode=str(row["mode"]),
            visible_when=str(row["visible_when"]),
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
    "VALID_VISIBLE_WHEN",
    "PEER_REVIEWER_MODES",
    "PEER_REVIEWER_WHENS",
    "REVIEWEE_OBSERVER_MODES",
    "REVIEWEE_OBSERVER_WHENS",
    "VisibilityPolicyError",
    "decode_mode",
    "encode_mode",
    "list_for_instrument",
    "upsert_many",
    "upsert_policy",
]
