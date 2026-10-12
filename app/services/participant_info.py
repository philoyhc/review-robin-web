"""What a participant is shown of their own roster entry.

`guide/participant_info.md`. One session-wide selection per participant,
stored as a list of roster field keys on the session row (``NULL`` means
the participant's default). Item 1 reads and writes the reviewers'
selection; the reviewee and observer columns exist (one migration for
all three, author 2026-10-12) but stay ``NULL`` until their items.
"""

from __future__ import annotations

from collections.abc import Iterable

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


class SelfFieldsError(ValueError):
    """A selection named a key outside ``REVIEWER_SELF_FIELD_KEYS``."""


def normalize_reviewer_self_fields(keys: Iterable[str]) -> list[str]:
    """The selection in roster order, each key once.

    Raises ``SelfFieldsError`` on an unknown key rather than dropping it,
    so a typo in a hand-edited Settings CSV is reported, not swallowed.
    """
    items = list(keys)
    if not all(isinstance(key, str) for key in items):
        raise SelfFieldsError("reviewer field keys must be strings")
    chosen = {key.strip() for key in items if key.strip()}
    unknown = sorted(chosen - set(REVIEWER_SELF_FIELD_KEYS))
    if unknown:
        raise SelfFieldsError(
            f"unknown reviewer field(s) {', '.join(unknown)}; expected "
            f"some of {', '.join(REVIEWER_SELF_FIELD_KEYS)}"
        )
    return [key for key in REVIEWER_SELF_FIELD_KEYS if key in chosen]


def effective_reviewer_self_fields(review_session: ReviewSession) -> tuple[str, ...]:
    """The stored selection, or the default while none is stored.

    A stored value that no longer normalizes (a hand-edited row, a
    non-list) falls back to the default rather than failing the
    reviewer's page.
    """
    stored = review_session.reviewer_self_fields
    if not isinstance(stored, list):
        return REVIEWER_SELF_DEFAULT
    try:
        return tuple(normalize_reviewer_self_fields(stored))
    except SelfFieldsError:
        return REVIEWER_SELF_DEFAULT


def set_reviewer_self_fields(
    db: Session,
    *,
    review_session: ReviewSession,
    user: User,
    keys: Iterable[str],
    correlation_id: str | None = None,
) -> None:
    """Store the reviewers' selection.

    A no-op when the stored list already equals it. With nothing stored,
    saving even the default writes it, so the choice is recorded and a
    later change to the default does not move this session. Gated by
    ``is_editable`` like every Reviewers-page setting; the setting is
    display-only, so a save never demotes ``validated``.
    """
    lifecycle.require_editable(db, review_session)
    new = normalize_reviewer_self_fields(keys)
    stored = review_session.reviewer_self_fields
    # Compared with what is stored, not the effective selection, so a
    # save over a hand-edited bad value repairs it rather than no-op.
    if stored == new:
        return
    # The audit records what was stored (``None`` while unset), not the
    # effective default, so a first save reads as NULL → list.
    old = list(stored) if isinstance(stored, list) else stored
    review_session.reviewer_self_fields = new
    db.flush()
    audit.write_event(
        db,
        event_type="session.reviewer_self_fields_set",
        summary=(
            f"Session {review_session.code}: reviewers see "
            f"{', '.join(new) or 'nothing'} of their own entry"
        ),
        actor_user_id=user.id,
        session=review_session,
        payload=audit.changes({"reviewer_self_fields": [old, new]}),
        correlation_id=correlation_id,
    )
    unit_of_work.commit(db)
