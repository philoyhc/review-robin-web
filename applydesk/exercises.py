"""An exercise's own settings, stored (segment AD2B,
`applydesk/guide/segment_AD2B_exercises.md`): name, code, description,
eligibility, blind, help contact, timezone and tags on the `exercise` row.

The pages keep `sample_data.Exercise`'s shape until AD2G retires the
simulation: `overlay` lays the stored settings over the sample's, whose
stages, form and applications stay sample data until AD2C–AD2F. A row
with `revision` 0 has no settings recorded yet, and the sample's stand.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from applydesk import audit, db, sample_data
from applydesk.models import Exercise, ExerciseTag, Person

#: The stored eligibility and the words the pages show (AD-60: NULL is
#: unset, shown as "Not set"; never stored as text).
ELIGIBILITY: dict[str, str] = {
    "open": "Open to all signed in",
    "invitation": "Invitation only",
}
NOT_SET = "Not set"


@dataclass(frozen=True)
class Settings:
    """An exercise's stored settings. None is unset: a help contact or
    timezone then takes the operator settings' default (AD-54)."""

    name: str | None
    code: str | None
    description: str | None
    eligibility: str | None
    blind: bool
    help_contact: str | None
    timezone: str | None
    tags: tuple[str, ...]
    created_at: datetime
    revision: int


def _key(text: str | None) -> str | None:
    return text.casefold() if text else None


def row(session: Session, public_id: str) -> Exercise | None:
    """The exercise's row, unless deleted."""
    return session.scalar(
        select(Exercise).where(Exercise.public_id == public_id, Exercise.deleted_at.is_(None))
    )


def tags_of(session: Session, exercise: Exercise) -> tuple[str, ...]:
    return tuple(
        session.scalars(
            select(ExerciseTag.label)
            .where(ExerciseTag.exercise_id == exercise.id)
            .order_by(ExerciseTag.id)
        )
    )


def settings_of(session: Session, exercise: Exercise) -> Settings | None:
    """The stored settings, or None while none are recorded."""
    if exercise.revision < 1:
        return None
    return Settings(
        name=exercise.name,
        code=exercise.code,
        description=exercise.description,
        eligibility=exercise.eligibility,
        blind=exercise.blind,
        help_contact=exercise.help_contact,
        timezone=exercise.timezone,
        tags=tags_of(session, exercise),
        created_at=exercise.created_at,
        revision=exercise.revision,
    )


def overlay(sample: sample_data.Exercise, settings: Settings | None) -> sample_data.Exercise:
    """`sample` with the stored settings laid over it, in the pages' words:
    unset eligibility reads "Not set", an unset help contact or timezone
    reads "" (the operator settings' default)."""
    if settings is None:
        return sample
    created = settings.created_at
    if created.tzinfo is None:  # SQLite keeps no offset: stored as UTC
        created = created.replace(tzinfo=UTC)
    return replace(
        sample,
        name=settings.name or sample.name,
        code=settings.code or "",
        summary=settings.description or "",
        eligibility=ELIGIBILITY.get(settings.eligibility or "", NOT_SET),
        blind=settings.blind,
        help_contact=settings.help_contact or "",
        timezone=settings.timezone or "",
        tags=settings.tags,
        # In the exercise's own timezone, as the sample writes it.
        created=created.astimezone(
            ZoneInfo(settings.timezone or sample_data.DEFAULT_TIMEZONE)
        ).isoformat(timespec="minutes"),
    )


def stored(sample: sample_data.Exercise) -> sample_data.Exercise:
    """`sample` as the database has it: the pages' one reader (through
    `lookups.exercise_or_404` and the Lobby)."""
    return stored_at(sample)[0]


def stored_at(sample: sample_data.Exercise) -> tuple[sample_data.Exercise, int]:
    """`sample` as the database has it, with the revision those settings
    are at, from one read: Details' Lock names that revision, so it must
    describe the values the page shows (Codex on #4137). 0 while none
    are recorded."""
    session = db.new_session()
    try:
        found = row(session, sample.public_id)
        settings = settings_of(session, found) if found is not None else None
        return overlay(sample, settings), settings.revision if settings else 0
    finally:
        session.close()


def stored_all(samples: tuple[sample_data.Exercise, ...]) -> tuple[sample_data.Exercise, ...]:
    """Each of `samples` as the database has it, in one session."""
    if not samples:
        return samples
    session = db.new_session()
    try:
        rows = {
            e.public_id: e
            for e in session.scalars(
                select(Exercise).where(
                    Exercise.public_id.in_([s.public_id for s in samples]),
                    Exercise.deleted_at.is_(None),
                )
            )
        }
        return tuple(
            overlay(s, settings_of(session, rows[s.public_id]) if s.public_id in rows else None)
            for s in samples
        )
    finally:
        session.close()


def _from_sample(sample: sample_data.Exercise) -> dict[str, object]:
    """A sample's settings as stored values: its words back to the enum,
    "Not set" and "" to NULL (AD-60)."""
    eligibility = next((k for k, v in ELIGIBILITY.items() if v == sample.eligibility), None)
    return {
        "name": sample.name,
        "code": sample.code or None,
        "code_key": _key(sample.code),
        "description": sample.summary or None,
        "eligibility": eligibility,
        "blind": sample.blind,
        "help_contact": sample.help_contact or None,
        "timezone": sample.timezone or None,
    }


def record_sample(
    session: Session, exercise: Exercise, sample: sample_data.Exercise, actor: Person | None
) -> bool:
    """Record a sample's settings on its row (the seed), once: a row whose
    settings are recorded is left as it is. True if it recorded them."""
    if exercise.revision >= 1:
        return False
    values = _from_sample(sample)
    for name, value in values.items():
        setattr(exercise, name, value)
    if sample.created:
        exercise.created_at = datetime.fromisoformat(sample.created).astimezone(UTC)
    exercise.created_by_id = actor.id if actor is not None else None
    exercise.revision = 1
    seen: set[str] = set()
    for tag in sample.tags:
        if tag.casefold() not in seen:
            seen.add(tag.casefold())
            session.add(ExerciseTag(exercise_id=exercise.id, label=tag, label_key=tag.casefold()))
    session.flush()
    audit.write_event(
        session,
        event_type="exercise.settings_recorded",
        actor=None,
        exercise=exercise,
        payload=audit.snapshot({**values, "tags": list(sample.tags)}),
    )
    return True


class Refused(Exception):
    """A Details save the rules refuse: `field` names the field it is
    about, as the card points there; `key` names the rule."""

    def __init__(self, message: str, *, key: str, field: str = "name") -> None:
        super().__init__(message)
        self.key = key
        self.field = field


#: The fields Details' *Lock* saves, in the order the audit lists them.
DETAILS = ("name", "code", "description", "eligibility", "blind", "help_contact", "timezone")


def details_from_page(fields: dict[str, Any]) -> dict[str, Any]:
    """Details as the card sends them (the sample's words) as stored
    values: "Not set" and "" to NULL (AD-60), the default timezone to NULL
    (AD-54)."""
    eligibility = next((k for k, v in ELIGIBILITY.items() if v == fields["eligibility"]), None)
    zone = fields["timezone"] or None
    return {
        "name": fields["name"],
        "code": fields["code"] or None,
        "description": fields["summary"] or None,
        "eligibility": eligibility,
        "blind": bool(fields["blind"]),
        "help_contact": fields["help_contact"] or None,
        "timezone": None if zone == sample_data.DEFAULT_TIMEZONE else zone,
    }


def _clash(session: Session, exercise: Exercise, code: str | None) -> Exercise | None:
    if not code:
        return None
    return session.scalar(
        select(Exercise).where(
            Exercise.code_key == _key(code),
            Exercise.id != exercise.id,
            Exercise.archived_at.is_(None),
            Exercise.deleted_at.is_(None),
        )
    )


def save_details(
    session: Session,
    sample: sample_data.Exercise,
    values: dict[str, Any],
    opened: int,
    actor: Person | None,
) -> int:
    """Details' *Lock* (segment AD2B rung 3): `values` (stored form) saved
    on the exercise's row, if no one saved since the page opened at
    revision `opened` (ruling 74). Audited with the fields that changed.
    The new revision; refused if stale, gone, or the code is taken. The
    caller commits (and rolls back on a refusal)."""
    exercise = session.scalar(
        select(Exercise)
        .where(Exercise.public_id == sample.public_id, Exercise.deleted_at.is_(None))
        .with_for_update()
    )
    if exercise is None:
        raise Refused("This exercise is no longer on record.", key="gone")
    if exercise.revision != opened:
        raise Refused(
            "Not saved: someone else changed the details since this page opened."
            " Reload to see them.",
            key="stale",
        )
    if exercise.revision < 1:  # nothing recorded yet: the page's values first
        record_sample(session, exercise, sample, actor)
    clash = _clash(session, exercise, values["code"])
    if clash is not None:
        raise Refused(
            f"{values['code']} is already {clash.name}'s code.", key="code_taken", field="code"
        )
    before = {k: getattr(exercise, k) for k in DETAILS}
    changed = {k: [before[k], values[k]] for k in DETAILS if before[k] != values[k]}
    if not changed:
        return exercise.revision
    for name, value in values.items():
        setattr(exercise, name, value)
    exercise.code_key = _key(values["code"])
    exercise.revision += 1
    session.flush()
    audit.write_event(
        session,
        event_type="exercise.details_changed",
        actor=actor,
        exercise=exercise,
        payload=audit.changes(changed),
        context={"revision": exercise.revision},
    )
    return exercise.revision


def archived_at() -> dict[str, datetime]:
    """When each archived (not deleted) exercise was archived, by its
    public ID: the Archive page's rows (segment AD2B rung 5)."""
    session = db.new_session()
    try:
        return {
            public_id: at
            for public_id, at in session.execute(
                select(Exercise.public_id, Exercise.archived_at).where(
                    Exercise.archived_at.is_not(None), Exercise.deleted_at.is_(None)
                )
            )
            if at is not None
        }
    finally:
        session.close()
