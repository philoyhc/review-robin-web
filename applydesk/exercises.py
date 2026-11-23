"""An exercise's own settings, stored (segment AD2B,
`applydesk/guide/archive/segment_AD2B_exercises.md`): name, code, description,
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

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from applydesk import audit, db, operators, sample_data
from applydesk.ids import generate_public_id
from applydesk.models import Exercise, ExerciseTag, Person

#: The stored eligibility and the words the pages show (AD-60: NULL is
#: unset, shown as "Not set"; never stored as text).
ELIGIBILITY: dict[str, str] = {
    "open": "Open to all signed in",
    "invitation": "Invitation only",
}
NOT_SET = "Not set"
#: An ordinary exercise's name while its row has none.
UNTITLED = "Untitled exercise"


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


def from_row(found: Exercise) -> sample_data.Exercise:
    """An ordinary exercise in the pages' shape (segment AD2G): a blank
    Draft, its *Created* the row's. `overlay` lays its stored settings
    over it, as over a sample's."""
    made = found.created_at if found.created_at.tzinfo else found.created_at.replace(tzinfo=UTC)
    return sample_data.Exercise(
        public_id=found.public_id,
        code="",
        name=found.name or UNTITLED,
        state="Draft",
        form_open=True,
        eligibility=NOT_SET,
        blind=False,
        opens=NOT_SET,
        application_stage_ends=NOT_SET,
        expected_outcome=NOT_SET,
        summary="",
        created=made.isoformat(timespec="minutes"),
    )


def ordinary(public_id: str) -> sample_data.Exercise | None:
    """The ordinary exercise with this ID, archived or not, unless deleted
    or a sample: `sample_data.exercise`'s reader for every exercise but a
    sample."""
    if sample_data.is_sample(public_id):
        return None
    session = db.new_session()
    try:
        found = row(session, public_id)
        return from_row(found) if found is not None else None
    finally:
        session.close()


def ordinaries() -> tuple[sample_data.Exercise, ...]:
    """Every ordinary exercise not deleted, newest first."""
    session = db.new_session()
    try:
        rows = session.scalars(
            select(Exercise)
            .where(
                Exercise.deleted_at.is_(None),
                Exercise.public_id.not_in(sorted(sample_data.SAMPLE_IDS)),
            )
            .order_by(Exercise.created_at.desc(), Exercise.id.desc())
        )
        return tuple(from_row(r) for r in rows)
    finally:
        session.close()


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


@dataclass(frozen=True)
class Stored:
    """A sample as the database has it, with its row's state, from one
    read: the revision a page names must describe the values it shows
    (Codex on #4137; cold read at AD2B rung 6)."""

    exercise: sample_data.Exercise
    revision: int
    archived: bool
    deleted: bool

    @property
    def live(self) -> bool:
        return not (self.archived or self.deleted)


def stored_all_at(samples: tuple[sample_data.Exercise, ...]) -> tuple[Stored, ...]:
    """Each of `samples` as the database has it, in one session."""
    if not samples:
        return ()
    session = db.new_session()
    try:
        rows = {
            e.public_id: e
            for e in session.scalars(
                select(Exercise).where(Exercise.public_id.in_([s.public_id for s in samples]))
            )
        }
        out: list[Stored] = []
        for s in samples:
            found = rows.get(s.public_id)
            deleted = found is not None and found.deleted_at is not None
            settings = settings_of(session, found) if found is not None and not deleted else None
            out.append(
                Stored(
                    overlay(s, settings),
                    settings.revision if settings else 0,
                    found is not None and found.archived_at is not None,
                    deleted,
                )
            )
        return tuple(out)
    finally:
        session.close()


def stored_all(samples: tuple[sample_data.Exercise, ...]) -> tuple[sample_data.Exercise, ...]:
    """Each of `samples` as the database has it, deleted ones left out:
    a deleted exercise leaves every page (segment AD2B rung 6)."""
    return tuple(s.exercise for s in stored_all_at(samples) if not s.deleted)


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
    if exercise.created_by_id is None:  # set when it was made; kept (cold read)
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
        actor=actor,
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
    eligibility = eligibility_of(fields["eligibility"])
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


def eligibility_of(words: str) -> str | None:
    """Who may apply, from the pages' words to the stored enum ("Not set"
    to None, AD-60)."""
    return next((k for k, v in ELIGIBILITY.items() if v == words), None)


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


# --------------------------------------------------------------------------- #
# The Operator Lobby's panel and the Archive (segment AD2B rung 6).

#: Tags an exercise carries at most, and a tag's longest (Semantics).
MAX_TAGS = 20
MAX_TAG = 40


def parse_tags(text: str) -> list[str]:
    """Comma-separated tags as typed: trimmed, blanks dropped, each once
    ignoring case, in the case first typed. Refused past the limits."""
    seen: dict[str, str] = {}
    for part in text.split(","):
        tag = " ".join(part.split())
        if not tag:
            continue
        if max(len(tag), len(tag.casefold())) > MAX_TAG:  # the key is casefolded
            raise Refused(f"A tag is at most {MAX_TAG} characters.", key="tag_long", field="tags")
        seen.setdefault(tag.casefold(), tag)
    if len(seen) > MAX_TAGS:
        raise Refused(
            f"An exercise carries at most {MAX_TAGS} tags.", key="tags_many", field="tags"
        )
    return list(seen.values())


def _locked(session: Session, public_id: str) -> Exercise:
    found = session.scalar(
        select(Exercise)
        .where(Exercise.public_id == public_id, Exercise.deleted_at.is_(None))
        .with_for_update()
    )
    if found is None:
        raise Refused("That exercise is no longer on record.", key="gone")
    return found


def _live(exercise: Exercise) -> None:
    """An archived exercise is read-only until restored (the author,
    2026-11-22)."""
    if exercise.archived_at is not None:
        raise Refused(
            "Archived: restore it from the Archive to change it.", key="archived_readonly"
        )


def _ready(session: Session, exercise: Exercise, actor: Person | None) -> None:
    """Record a sample's settings before a first change (revision 0)."""
    if exercise.revision < 1:
        sample = sample_data.exercise(exercise.public_id)
        if sample is not None:
            record_sample(session, exercise, sample, actor)


def _put_tags(session: Session, exercise: Exercise, tags: list[str]) -> None:
    for old in session.scalars(select(ExerciseTag).where(ExerciseTag.exercise_id == exercise.id)):
        session.delete(old)
    session.flush()
    for tag in tags:
        session.add(ExerciseTag(exercise_id=exercise.id, label=tag, label_key=tag.casefold()))


def _changed(
    session: Session,
    exercise: Exercise,
    actor: Person | None,
    changes: dict[str, list[Any]],
) -> None:
    exercise.revision += 1
    session.flush()
    audit.write_event(
        session,
        event_type="exercise.details_changed",
        actor=actor,
        exercise=exercise,
        payload=audit.changes(changes),
        context={"revision": exercise.revision},
    )


def save_panel(
    session: Session,
    public_id: str,
    name: str,
    code: str,
    tags: list[str],
    opened: int,
    actor: Person | None,
) -> int:
    """The panel's *Save* for one exercise: its name, code and tags, if
    no one saved since the Lobby opened at revision `opened`."""
    exercise = _locked(session, public_id)
    _live(exercise)
    if exercise.revision != opened:
        raise Refused(
            "Not saved: someone else changed this exercise since the Lobby opened. Reload.",
            key="stale",
        )
    name = " ".join(name.split())
    code = code.strip()
    if not name or len(name) > 200:
        raise Refused("A name of 1 to 200 characters is needed.", key="name", field="name")
    if max(len(code), len(code.casefold())) > 40:  # its key is casefolded
        raise Refused("An exercise code is at most 40 characters.", key="code_long", field="code")
    _ready(session, exercise, actor)
    # A published exercise's code is fixed (G2), here as on Details (Codex on #4140).
    sample = sample_data.exercise(public_id)
    if sample is not None and sample.state != "Draft" and (code or None) != exercise.code:
        raise Refused("A published exercise's code is fixed.", key="code_fixed", field="code")
    if (clash := _clash(session, exercise, code or None)) is not None:
        raise Refused(f"{code} is already {clash.name}'s code.", key="code_taken", field="code")
    before_tags = list(tags_of(session, exercise))
    changes: dict[str, list[Any]] = {}
    if exercise.name != name:
        changes["name"] = [exercise.name, name]
    if exercise.code != (code or None):
        changes["code"] = [exercise.code, code or None]
    if before_tags != tags:
        changes["tags"] = [before_tags, tags]
    if not changes:
        return exercise.revision
    exercise.name, exercise.code, exercise.code_key = name, code or None, _key(code)
    if "tags" in changes:
        _put_tags(session, exercise, tags)
    _changed(session, exercise, actor, changes)
    return exercise.revision


def retag(
    session: Session, public_ids: list[str], tags: list[str], actor: Person | None, *, add: bool
) -> None:
    """*All tags to all* (`add`) or *Remove from all*: `tags` added to, or
    taken from, each exercise; one past the limit refuses the lot."""
    wanted = {t.casefold() for t in tags}
    for public_id in sorted(set(public_ids)):
        exercise = _locked(session, public_id)
        _live(exercise)
        _ready(session, exercise, actor)
        before = list(tags_of(session, exercise))
        held = {t.casefold() for t in before}
        if add:
            after = before + [t for t in tags if t.casefold() not in held]
        else:
            after = [t for t in before if t.casefold() not in wanted]
        if len(after) > MAX_TAGS:
            raise Refused(
                f"{exercise.name} would carry more than {MAX_TAGS} tags.", key="tags_many"
            )
        if after != before:
            _put_tags(session, exercise, after)
            _changed(session, exercise, actor, {"tags": [before, after]})


def _owned(session: Session, exercise: Exercise, actor: operators.Actor) -> None:
    if not operators.is_owner(session, exercise, actor):
        raise Refused(
            f"Only an Owner of {exercise.name or 'an exercise'} may do that.", key="not_owner"
        )


def archive(session: Session, public_ids: list[str], actor: operators.Actor) -> None:
    """Archive each exercise (Owner-only, every one or none): it leaves
    the Lobby for the Archive and frees its code."""
    for public_id in sorted(set(public_ids)):
        exercise = _locked(session, public_id)
        _owned(session, exercise, actor)
        _ready(session, exercise, actor.person)
        if exercise.archived_at is None:
            exercise.archived_at = datetime.now(UTC)
            exercise.revision += 1
            session.flush()
            audit.write_event(
                session, event_type="exercise.archived", actor=actor.person, exercise=exercise
            )


def restore(session: Session, public_id: str, actor: operators.Actor) -> None:
    """Bring an archived exercise back (Owner-only), unless another live
    exercise has taken its code since."""
    exercise = _locked(session, public_id)
    _owned(session, exercise, actor)
    if exercise.archived_at is None:
        return
    if (clash := _clash(session, exercise, exercise.code)) is not None:
        raise Refused(
            f"Not restored: {exercise.code} is now {clash.name}'s code. Change one first.",
            key="restore_taken",
        )
    exercise.archived_at = None
    exercise.revision += 1
    session.flush()
    audit.write_event(
        session, event_type="exercise.restored", actor=actor.person, exercise=exercise
    )


def delete(session: Session, public_ids: list[str], actor: operators.Actor) -> None:
    """Delete each exercise (Owner-only, every one or none): it leaves
    every page; its row and audit trail stay (ruling 74)."""
    for public_id in sorted(set(public_ids)):
        exercise = _locked(session, public_id)
        _owned(session, exercise, actor)
        _live(exercise)  # restored first, as the spec says (cold read)
        exercise.deleted_at = datetime.now(UTC)
        exercise.revision += 1
        session.flush()
        audit.write_event(
            session, event_type="exercise.deleted", actor=actor.person, exercise=exercise
        )


#: The most live exercises one person may have made (segment AD2G; the
#: author, 2026-11-23): archive or delete one to make another.
MOST_MADE = 50

#: Why *New exercise* or *Duplicate* was refused, by the key the Lobby's
#: redirect carries (findings 2026-11-20 S11: a key, never the text).
MAKE_REFUSALS: dict[str, str] = {
    "name_needed": "A name is needed.",
    "name_long": "A name is at most 200 characters.",
    "full": f"At most {MOST_MADE} live exercises of your making: archive or delete one first.",
    "not_listed": "Only someone on the operator list may make an exercise.",
}


def _fresh_id(session: Session) -> str:
    """A public ID no sample and no row has."""
    while True:
        public_id = generate_public_id()
        taken = sample_data.is_sample(public_id) or session.scalar(
            select(Exercise.id).where(Exercise.public_id == public_id)
        )
        if not taken:
            return public_id


def make(
    session: Session, actor: operators.Actor, name: str, *, source_id: str | None = None
) -> Exercise:
    """*New exercise* (`source_id` None) or *Duplicate settings only*
    (segment AD2G): an ordinary exercise's row, the actor its Owner, in
    the caller's transaction. Refused past :data:`MOST_MADE` live
    exercises the actor made, counted under a lock on their person row so
    two at once cannot both pass. Flushed, not committed."""
    name = name.strip()
    if not name:
        raise Refused(MAKE_REFUSALS["name_needed"], key="name_needed")
    if len(name) > 200:
        raise Refused(MAKE_REFUSALS["name_long"], key="name_long")
    if actor.person is None:
        raise Refused(MAKE_REFUSALS["not_listed"], key="not_listed")
    session.scalar(select(Person.id).where(Person.id == actor.person.id).with_for_update())
    made_count = session.scalar(
        select(func.count(Exercise.id)).where(
            Exercise.created_by_id == actor.person.id,
            Exercise.deleted_at.is_(None),
            Exercise.archived_at.is_(None),
            # The seed records the samples' creator too; they never count.
            Exercise.public_id.not_in(sorted(sample_data.SAMPLE_IDS)),
        )
    )
    if (made_count or 0) >= MOST_MADE:
        raise Refused(MAKE_REFUSALS["full"], key="full")
    try:
        made = operators.create_exercise(session, actor, _fresh_id(session), name)
    except operators.Refused as why:
        raise Refused(str(why), key=why.key) from None
    if source_id is not None:
        copy_settings(session, source_id, made, actor.person)
    return made


def copy_settings(session: Session, source_id: str, target: Exercise, actor: Person | None) -> None:
    """*Duplicate settings only*: `target` (a new exercise's row) takes
    the source's settings and tags, named "Copy of …", with no code."""
    source = _locked(session, source_id)
    _ready(session, source, actor)
    target.name = f"Copy of {source.name}"[:200]
    target.code = target.code_key = None
    target.description, target.eligibility, target.blind = (
        source.description,
        source.eligibility,
        source.blind,
    )
    target.help_contact, target.timezone = source.help_contact, source.timezone
    target.created_by_id = actor.id if actor is not None else None
    target.revision = 1
    session.flush()
    _put_tags(session, target, list(tags_of(session, source)))
    session.flush()
    audit.write_event(
        session,
        event_type="exercise.duplicated",
        actor=actor,
        exercise=target,
        refs={"source_exercise_id": source.id},
    )


def is_deleted(public_id: str) -> bool:
    """Whether the exercise is deleted: it leaves every page (rung 6)."""
    session = db.new_session()
    try:
        return (
            session.scalar(
                select(Exercise.id).where(
                    Exercise.public_id == public_id, Exercise.deleted_at.is_not(None)
                )
            )
            is not None
        )
    finally:
        session.close()


def is_archived(public_id: str) -> bool:
    """Whether the exercise is archived: read-only until restored
    (the author, 2026-11-22; as Review Robin's archived sessions)."""
    session = db.new_session()
    try:
        return (
            session.scalar(
                select(Exercise.id).where(
                    Exercise.public_id == public_id,
                    Exercise.archived_at.is_not(None),
                    Exercise.deleted_at.is_(None),
                )
            )
            is not None
        )
    finally:
        session.close()
