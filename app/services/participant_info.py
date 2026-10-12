"""What a participant is shown of their own roster entry.

`guide/participant_info.md`. One session-wide selection per participant
type, stored as a list of roster field keys on the session row (``NULL``
means the participant's default). Item 1 reads and writes the reviewers'
selection, Item 4 the reviewees', Item 5 the observers' (one migration
for all three columns, author 2026-10-12).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.services import audit, unit_of_work
from app.services import session_lifecycle as lifecycle

#: Every field a reviewer can be shown of themselves, in roster order.
REVIEWER_SELF_FIELD_KEYS: tuple[str, ...] = (
    "name",
    "email",
    "profile_link",
    "tag_1",
    "tag_2",
    "tag_3",
)

#: The selection while none is stored: tags can be shown but start off.
REVIEWER_SELF_DEFAULT: tuple[str, ...] = ("name", "email", "profile_link")

#: What a reviewee can be shown of themselves (Item 4), in roster order.
REVIEWEE_SELF_FIELD_KEYS: tuple[str, ...] = (
    "name",
    "email_or_identifier",
    "profile_link",
    "tag_1",
    "tag_2",
    "tag_3",
)

#: The reviewees' selection while none is stored, as the reviewers'.
REVIEWEE_SELF_DEFAULT: tuple[str, ...] = (
    "name",
    "email_or_identifier",
    "profile_link",
)

#: What an observer can be shown of themselves (Item 5), in roster order:
#: the roster has one tag and no profile link.
OBSERVER_SELF_FIELD_KEYS: tuple[str, ...] = ("display_name", "email", "tag_1")

#: The observers' selection while none is stored: identity on, the tag off.
OBSERVER_SELF_DEFAULT: tuple[str, ...] = ("display_name", "email")


@dataclass(frozen=True)
class _Participant:
    """One participant type's selection: its keys, default and column."""

    keys: tuple[str, ...]
    default: tuple[str, ...]
    #: The `sessions` column holding the stored selection.
    column: str
    #: The plural the audit summary reads ("reviewers see …").
    plural: str
    #: The save's lifecycle gate: the roster page's own predicate.
    #: ``require_editable`` for Reviewers and Reviewees; the Observers
    #: roster stays open while the session runs, so ``require_not_archived``.
    require: Callable[[Session, ReviewSession], ReviewSession] = (
        lifecycle.require_editable
    )


_PARTICIPANTS: dict[str, _Participant] = {
    "reviewer": _Participant(
        REVIEWER_SELF_FIELD_KEYS, REVIEWER_SELF_DEFAULT,
        "reviewer_self_fields", "reviewers",
    ),
    "reviewee": _Participant(
        REVIEWEE_SELF_FIELD_KEYS, REVIEWEE_SELF_DEFAULT,
        "reviewee_self_fields", "reviewees",
    ),
    "observer": _Participant(
        OBSERVER_SELF_FIELD_KEYS, OBSERVER_SELF_DEFAULT,
        "observer_self_fields", "observers",
        require=lifecycle.require_not_archived,
    ),
}


def self_fields_columns() -> dict[str, str]:
    """Each selection's `sessions` column, and the participant it is."""
    return {spec.column: name for name, spec in _PARTICIPANTS.items()}


class SelfFieldsError(ValueError):
    """A selection named a key outside its participant's field keys."""


def normalize_self_fields(participant: str, keys: Iterable[str]) -> list[str]:
    """The selection in roster order, each key once.

    Raises ``SelfFieldsError`` on an unknown key rather than dropping it,
    so a typo in a hand-edited Settings CSV is reported, not swallowed.
    """
    spec = _PARTICIPANTS[participant]
    items = list(keys)
    if not all(isinstance(key, str) for key in items):
        raise SelfFieldsError(f"{participant} field keys must be strings")
    chosen = {key.strip() for key in items if key.strip()}
    unknown = sorted(chosen - set(spec.keys))
    if unknown:
        raise SelfFieldsError(
            f"unknown {participant} field(s) {', '.join(unknown)}; expected "
            f"some of {', '.join(spec.keys)}"
        )
    return [key for key in spec.keys if key in chosen]


def effective_self_fields(
    review_session: ReviewSession, participant: str
) -> tuple[str, ...]:
    """The stored selection, or the default while none is stored.

    A stored value that no longer normalizes (a hand-edited row, a
    non-list) falls back to the default rather than failing the
    participant's page.
    """
    spec = _PARTICIPANTS[participant]
    stored = getattr(review_session, spec.column)
    if not isinstance(stored, list):
        return spec.default
    try:
        return tuple(normalize_self_fields(participant, stored))
    except SelfFieldsError:
        return spec.default


def set_self_fields(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    participant: str,
    keys: Iterable[str],
    correlation_id: str | None = None,
) -> None:
    """Store a participant type's selection.

    A no-op when the stored list already equals it. With nothing stored,
    saving even the default writes it, so the choice is recorded and a
    later change to the default does not move this session. Gated as the
    participant's roster page is (``_Participant.require``); the setting
    is display-only, so a save never demotes ``validated``.
    """
    spec = _PARTICIPANTS[participant]
    spec.require(db, review_session)
    new = normalize_self_fields(participant, keys)
    stored = getattr(review_session, spec.column)
    # Compared with what is stored, not the effective selection, so a
    # save over a hand-edited bad value repairs it rather than no-op.
    if stored == new:
        return
    # The audit records what was stored (``None`` while unset), not the
    # effective default, so a first save reads as NULL → list.
    old = list(stored) if isinstance(stored, list) else stored
    setattr(review_session, spec.column, new)
    db.flush()
    audit.write_event(
        db,
        event_type=f"session.{spec.column}_set",
        summary=(
            f"Session {review_session.code}: {spec.plural} see "
            f"{', '.join(new) or 'nothing'} of their own entry"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.changes({spec.column: [old, new]}),
        correlation_id=correlation_id,
    )
    unit_of_work.commit(db)


# ── The reviewer names Item 1 shipped, kept for their callers ─────────


def normalize_reviewer_self_fields(keys: Iterable[str]) -> list[str]:
    """``normalize_self_fields`` for reviewers."""
    return normalize_self_fields("reviewer", keys)


def effective_reviewer_self_fields(review_session: ReviewSession) -> tuple[str, ...]:
    """``effective_self_fields`` for reviewers."""
    return effective_self_fields(review_session, "reviewer")


def set_reviewer_self_fields(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    keys: Iterable[str],
    correlation_id: str | None = None,
) -> None:
    """``set_self_fields`` for reviewers."""
    set_self_fields(
        db,
        review_session=review_session,
        user=user,
        participant="reviewer",
        keys=keys,
        correlation_id=correlation_id,
    )
