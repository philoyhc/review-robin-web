"""An exercise's emails in the database (segment AD2L; rulings 16, 54 and
65): the ticks Process records, and each email's template.

``sends`` reads the (item, audience) pairs Process ticks, None until a
Process save records them, so a sample keeps its own. ``save_sends``
replaces them with a Process save's, in that save's transaction: a pair
no longer ticked is retired (ruling 74), ticked again revived.

``templates`` reads each saved template by (item, audience); one never
saved is absent, so a sample's card keeps its default. ``save_template``
keeps one card's template under the exercise's lock
(``panels_store.lock``), guarded by the template's ``version``: a card
opened before another save of the same template is refused, while other
cards are not. The caller says, under the lock, whether Process still
owes the email.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from applydesk import audit, db, panels_store
from applydesk.models import EmailSend, EmailTemplate, Exercise, Person

#: A subject's and a body's most characters, as the Emails card says.
MAX_SUBJECT = 300
MAX_BODY = 20000

Pair = tuple[str, str]


@dataclass(frozen=True)
class Template:
    """A template as a card reads it: its text, and how many times it was
    saved (the version a card sends back)."""

    subject: str
    body: str
    version: int

    @property
    def written(self) -> bool:
        """Written once it has a subject and a body; else still owed."""
        return bool(self.subject.strip() and self.body.strip())


class Refused(Exception):
    """A save that cannot be kept, said to the operator; ``key`` names the
    kind of refusal for a caller that tells them apart."""

    def __init__(self, message: str, key: str = "refused") -> None:
        super().__init__(message)
        self.key = key


def _now() -> datetime:
    return datetime.now(UTC)


def _exercise(session: Session, public_id: str) -> Exercise | None:
    return session.scalar(select(Exercise).where(Exercise.public_id == public_id))


# --- The ticks ---------------------------------------------------------------


def sends(session: Session, public_id: str) -> frozenset[Pair] | None:
    """The (item, audience) pairs Process ticks, else None (never recorded:
    a sample keeps its own)."""
    exercise = _exercise(session, public_id)
    if exercise is None or not exercise.sends_saved:
        return None
    rows = session.execute(
        select(EmailSend.item, EmailSend.audience).where(
            EmailSend.exercise_id == exercise.id, EmailSend.retired_at.is_(None)
        )
    ).all()
    return frozenset((item, audience) for item, audience in rows)


def stored_sends(public_id: str) -> frozenset[Pair] | None:
    """The ticks, read in a session of their own (``workflow``'s readers,
    which no route hands a session)."""
    session = db.new_session()
    try:
        return sends(session, public_id)
    finally:
        session.close()


def save_sends(session: Session, public_id: str, ticks: Iterable[Pair]) -> int:
    """Make the stored ticks say ``ticks``, a Process save's, in that save's
    transaction (the caller holds the exercise's lock); how many are
    ticked. Flushed, not committed."""
    exercise = _exercise(session, public_id)
    if exercise is None:
        raise Refused("That exercise is no longer on record.", key="gone")
    wanted = set(ticks)
    at = _now()
    rows = {
        (r.item, r.audience): r
        for r in session.scalars(select(EmailSend).where(EmailSend.exercise_id == exercise.id))
    }
    for pair, row in rows.items():
        if pair not in wanted and row.retired_at is None:
            row.retired_at = at
        elif pair in wanted:
            row.retired_at = None
    for item, audience in wanted - set(rows):
        session.add(EmailSend(exercise_id=exercise.id, item=item, audience=audience))
    exercise.sends_saved = True
    session.flush()
    return len(wanted)


# --- The templates -----------------------------------------------------------


def templates(session: Session, public_id: str) -> dict[Pair, Template]:
    """Each saved template by (item, audience); one never saved is absent."""
    exercise = _exercise(session, public_id)
    if exercise is None:
        return {}
    rows = session.scalars(select(EmailTemplate).where(EmailTemplate.exercise_id == exercise.id))
    return {(r.item, r.audience): Template(r.subject, r.body, r.version) for r in rows}


def stored_templates(public_id: str) -> dict[Pair, Template]:
    """The saved templates, read in a session of their own."""
    session = db.new_session()
    try:
        return templates(session, public_id)
    finally:
        session.close()


def save_template(
    session: Session,
    public_id: str,
    pair: Pair,
    subject: str,
    body: str,
    opened: int,
    actor: Person | None,
    *,
    owed: Callable[[], bool],
) -> int:
    """Keep one card's template, if Process still owes it (``owed``, read
    under the lock) and no save of it came between (``opened``, the
    version the card loaded); the new version. Flushed, not committed: the
    caller's transaction holds it and its audit."""
    if len(subject) > MAX_SUBJECT or len(body) > MAX_BODY:
        raise Refused(
            f"A subject is at most {MAX_SUBJECT} characters, a body {MAX_BODY:,}.", key="long"
        )
    exercise = panels_store.lock(session, public_id)
    if exercise.archived_at is not None:
        raise Refused("Archived: restore it to change it.", key="archived")
    if not owed():
        raise Refused("That email is not one Process owes now: reload Emails.", key="not_owed")
    item, audience = pair
    row = session.scalar(
        select(EmailTemplate).where(
            EmailTemplate.exercise_id == exercise.id,
            EmailTemplate.item == item,
            EmailTemplate.audience == audience,
        )
    )
    if (row.version if row is not None else 0) != opened:
        raise Refused(
            "Not saved: this email was saved since the page opened. Reload to see it.",
            key="stale",
        )
    if row is None:
        row = EmailTemplate(exercise_id=exercise.id, item=item, audience=audience, version=0)
        session.add(row)
    row.subject, row.body, row.saved_at = subject, body, _now()
    row.version += 1
    audit.write_event(
        session,
        event_type="exercise.email_saved",
        actor=actor,
        exercise=exercise,
        context={
            "item": item,
            "audience": audience,
            "version": row.version,
            "written": bool(subject.strip() and body.strip()),
        },
    )
    session.flush()
    return row.version
