"""An exercise's Candidates (ruling 77, segment AD2C rung 9): people kept
by hand, added through the people search (ruling 75) or a CSV upload,
removed in the list. The form's roster on an *Invitation only* exercise;
fed to gates as dossiers once AD2F stores them.

A person is listed once per exercise (``uq_candidate_pair``). Removing
someone sets ``removed_at``; adding them again clears it on the same row.
A CSV saves its good rows and lists the rest back, as the Panels roster
import does: each row is one address and, if given, a name. A row's
address is matched to a person on record, else stored as a pending
person (``people.pending``); the directory is searched one person at a
time, from the search, not per CSV row. Each add and removal is audited.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from applydesk import audit, people
from applydesk.models import Candidate, Exercise, Person

#: How a candidate came: picked in the search, or a CSV row.
VIA = ("search", "csv")
#: The most rows one CSV adds.
MAX_ROWS = 2000
#: The longest address a person row holds (``Person.email``, ``String(320)``):
#: a longer one is a bad row, not a failed insert (Codex on #4161).
MAX_EMAIL = 320
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class Refused(Exception):
    """A change that cannot be made, said to the operator."""


@dataclass(frozen=True)
class Listed:
    """One candidate as the list shows them."""

    person_id: int
    name: str
    email: str
    via: str
    added_at: datetime


@dataclass(frozen=True)
class Imported:
    """What a CSV did: how many it added, how many were listed already,
    and each row it could not read, as said back to the operator."""

    added: int
    already: int
    bad: tuple[str, ...]


def _exercise(session: Session, public_id: str) -> Exercise:
    found = session.scalar(
        select(Exercise).where(Exercise.public_id == public_id, Exercise.deleted_at.is_(None))
    )
    if found is None:
        raise Refused("That exercise is no longer on record.")
    if found.archived_at is not None:
        raise Refused("Archived: restore it to change it.")
    return found


def listing(session: Session, public_id: str) -> tuple[Listed, ...]:
    """The exercise's current candidates, in the order they were added."""
    exercise = session.scalar(select(Exercise).where(Exercise.public_id == public_id))
    if exercise is None:
        return ()
    rows = session.execute(
        select(Candidate, Person)
        .join(Person, Person.id == Candidate.person_id)
        .where(Candidate.exercise_id == exercise.id, Candidate.removed_at.is_(None))
        .order_by(Candidate.added_at, Candidate.id)
    )
    return tuple(
        Listed(p.id, p.display_name or "", p.email or "", c.via, c.added_at) for c, p in rows
    )


def add(session: Session, public_id: str, person: Person, via: str, actor: Person | None) -> bool:
    """List ``person``; False if they were listed already. Flushes."""
    if via not in VIA:
        raise ValueError(via)
    exercise = _exercise(session, public_id)
    row = session.scalar(
        select(Candidate).where(
            Candidate.exercise_id == exercise.id, Candidate.person_id == person.id
        )
    )
    now = datetime.now(UTC)
    if row is not None and row.removed_at is None:
        return False
    if row is not None:  # removed before: listed again on the same row
        row.removed_at, row.via, row.added_by_id, row.added_at = None, via, _id(actor), now
    else:
        try:
            with session.begin_nested():
                session.add(
                    Candidate(
                        exercise_id=exercise.id,
                        person_id=person.id,
                        via=via,
                        added_by_id=_id(actor),
                        added_at=now,
                    )
                )
        except IntegrityError:
            return False  # another request listed them meanwhile
    session.flush()
    audit.write_event(
        session,
        event_type="candidate.added",
        actor=actor,
        exercise=exercise,
        refs={"person_id": person.id},
        context={"via": via},
    )
    return True


def remove(session: Session, public_id: str, person_id: int, actor: Person | None) -> bool:
    """Take someone off the list; False if they were not on it. Flushes."""
    exercise = _exercise(session, public_id)
    row = session.scalar(
        select(Candidate).where(
            Candidate.exercise_id == exercise.id,
            Candidate.person_id == person_id,
            Candidate.removed_at.is_(None),
        )
    )
    if row is None:
        return False
    row.removed_at = datetime.now(UTC)
    session.flush()
    audit.write_event(
        session,
        event_type="candidate.removed",
        actor=actor,
        exercise=exercise,
        refs={"person_id": person_id},
    )
    return True


def _id(person: Person | None) -> int | None:
    return person.id if person is not None else None


def _on_record(session: Session, address: str) -> Person | None:
    """The person on record with this address: a bound one by its address
    snapshot, else a pending one."""
    key = people.email_key(address)
    if key is None:
        return None
    return session.scalar(
        select(Person)
        .where(Person.email_key == key)
        .order_by(Person.object_id.is_(None), Person.id)
    )


def import_csv(session: Session, public_id: str, text: str, actor: Person | None) -> Imported:
    """Add each good row of a CSV with an *Email* column and, if given, a
    *Name* one (any case, any order); the rest are listed back by row
    number. Flushes; the caller commits."""
    _exercise(session, public_id)
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    header = next(reader, None)
    if header is None:
        raise Refused("The file is empty.")
    names = [h.strip().casefold() for h in header]
    if "email" not in names:
        raise Refused("The file has no Email column.")
    at_email = names.index("email")
    at_name = names.index("name") if "name" in names else None
    bad: list[str] = []
    seen: set[str] = set()
    added = already = 0
    for n, row in enumerate(reader, start=2):
        if not any(cell.strip() for cell in row):
            continue
        if n - 1 > MAX_ROWS:
            bad.append(f"Rows past {MAX_ROWS} were not read.")
            break
        address = row[at_email].strip() if at_email < len(row) else ""
        name = row[at_name].strip() if at_name is not None and at_name < len(row) else ""
        if len(address) > MAX_EMAIL or not _EMAIL.fullmatch(address):
            shown = address if len(address) <= 60 else address[:57] + "…"
            bad.append(f"Row {n}: “{shown}” is not an email address.")
            continue
        key = people.email_key(address) or ""
        if key in seen:
            bad.append(f"Row {n}: {address} is in the file twice.")
            continue
        seen.add(key)
        person = _on_record(session, address) or people.pending(session, address, actor)
        if name and not person.display_name and person.object_id is None:
            person.display_name = name[:200]  # a pending person's name, from the file
        if add(session, public_id, person, "csv", actor):
            added += 1
        else:
            already += 1
    return Imported(added, already, tuple(bad))
