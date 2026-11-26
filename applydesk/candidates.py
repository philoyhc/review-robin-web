"""An exercise's Candidates, shown as *Populate Dossiers* (rulings 77, 83;
segments AD2C rung 9, AD2K): entries kept by hand, added through the people
search (ruling 75) or a CSV upload, removed in the list. The form's roster
on an *Invitation only* exercise; where the item is the first, each entry's
dossier is minted once the exercise is published (rulings 81, 83,
`dossiers`).

Each entry is one dossier, so a person may hold several, up to the
exercise's ``dossiers_per_person``; an add past it is refused. Removing an
entry sets ``removed_at``; adding the person again is a new entry, never
the old one back (ruling 83). A CSV saves its good rows and lists the rest
back, as the Panels roster import does: each row is one address and, if
given, a name and a title. A row's address is matched to a person on
record, else stored as a pending person (``people.pending``); the
directory is searched one person at a time, from the search, not per CSV
row. Each add and removal is audited.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from applydesk import audit, dossiers, people
from applydesk.models import Candidate, Exercise, Person

#: How a candidate came: picked in the search, or a CSV row.
VIA = ("search", "csv")
#: The most rows one CSV adds.
MAX_ROWS = 2000
#: The most dossiers one person may hold in an exercise (segment AD2K).
MAX_PER_PERSON = 20
#: The longest title an entry holds (``Candidate.title``).
MAX_TITLE = 300
#: The longest address a person row holds (``Person.email``, ``String(320)``):
#: a longer one is a bad row, not a failed insert (Codex on #4161).
MAX_EMAIL = 320
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class Refused(Exception):
    """A change that cannot be made, said to the operator."""


@dataclass(frozen=True)
class Listed:
    """One entry as the list shows it."""

    id: int
    person_id: int
    name: str
    email: str
    via: str
    added_at: datetime
    title: str = ""


@dataclass(frozen=True)
class Imported:
    """What a CSV did: how many it added, how many were listed already as
    often as the exercise allows, and each row it could not read, as said
    back to the operator."""

    added: int
    already: int
    bad: tuple[str, ...]


def _exercise(session: Session, public_id: str, *, lock: bool = False) -> Exercise:
    query = select(Exercise).where(Exercise.public_id == public_id, Exercise.deleted_at.is_(None))
    # Locked while an add counts a person's entries, so two adds at once
    # cannot both pass the per-person limit (Postgres; SQLite writes one at
    # a time anyway).
    found = session.scalar(query.with_for_update() if lock else query)
    if found is None:
        raise Refused("That exercise is no longer on record.")
    if found.archived_at is not None:
        raise Refused("Archived: restore it to change it.")
    return found


def listing(session: Session, public_id: str) -> tuple[Listed, ...]:
    """The exercise's current entries, in the order they were added."""
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
        Listed(c.id, p.id, p.display_name or "", p.email or "", c.via, c.added_at, c.title)
        for c, p in rows
    )


def held(session: Session, exercise: Exercise, person_id: int) -> int:
    """How many live entries ``person_id`` holds in ``exercise``."""
    return (
        session.scalar(
            select(func.count())
            .select_from(Candidate)
            .where(
                Candidate.exercise_id == exercise.id,
                Candidate.person_id == person_id,
                Candidate.removed_at.is_(None),
            )
        )
        or 0
    )


def full(session: Session, public_id: str) -> frozenset[int]:
    """The people holding as many entries as the exercise allows: the
    search leaves them out."""
    exercise = session.scalar(select(Exercise).where(Exercise.public_id == public_id))
    if exercise is None:
        return frozenset()
    rows = session.execute(
        select(Candidate.person_id)
        .where(Candidate.exercise_id == exercise.id, Candidate.removed_at.is_(None))
        .group_by(Candidate.person_id)
        .having(func.count() >= exercise.dossiers_per_person)
    )
    return frozenset(r for (r,) in rows)


def already(session: Session, public_id: str) -> str:
    """What an add past the limit says."""
    most = _exercise(session, public_id).dossiers_per_person
    return "Already listed." if most == 1 else f"Already listed {most} times, the most allowed."


def add(
    session: Session,
    public_id: str,
    person: Person,
    via: str,
    actor: Person | None,
    *,
    mint: bool = True,
    title: str = "",
) -> bool:
    """Add an entry for ``person``; False if they already hold as many as
    the exercise allows (``dossiers_per_person``). Flushes. With ``mint``,
    its dossier is given where Populate Dossiers is the first item (rulings
    81, 83); a CSV mints once, after its rows."""
    if via not in VIA:
        raise ValueError(via)
    exercise = _exercise(session, public_id, lock=True)
    if held(session, exercise, person.id) >= exercise.dossiers_per_person:
        return False
    row = Candidate(
        exercise_id=exercise.id,
        person_id=person.id,
        via=via,
        title=title[:MAX_TITLE],
        added_by_id=_id(actor),
        added_at=datetime.now(UTC),
    )
    session.add(row)
    session.flush()
    audit.write_event(
        session,
        event_type="candidate.added",
        actor=actor,
        exercise=exercise,
        refs={"person_id": person.id, "candidate_id": row.id},
        context={"via": via},
    )
    if mint:
        dossiers.sync_candidates(session, exercise, actor)  # ruling 81: on each add
    return True


def remove(session: Session, public_id: str, entry_id: int, actor: Person | None) -> bool:
    """Take one entry off the list, retiring its dossier; False if it was
    not on it. Flushes."""
    exercise = _exercise(session, public_id)
    row = session.scalar(
        select(Candidate).where(
            Candidate.exercise_id == exercise.id,
            Candidate.id == entry_id,
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
        refs={"person_id": row.person_id, "candidate_id": row.id},
    )
    dossiers.retire_for(session, exercise, row, actor)
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
    """Add each good row of a CSV with an *Email* column and, if given,
    *Name* and *Title* ones (any case, any order), one entry a row; the rest
    are listed back by row number. A person may be in the file as often as
    the exercise allows entries (segment AD2K). Flushes; the caller
    commits."""
    most = _exercise(session, public_id).dossiers_per_person
    reader = csv.reader(io.StringIO(text.lstrip("﻿")))
    try:
        header = next(reader, None)
    except csv.Error as error:  # a field past the parser's limit (Codex on #4161)
        raise Refused("The file could not be read as a CSV.") from error
    if header is None:
        raise Refused("The file is empty.")
    names = [h.strip().casefold() for h in header]
    if "email" not in names:
        raise Refused("The file has no Email column.")
    at_email = names.index("email")
    at_name = names.index("name") if "name" in names else None
    at_title = names.index("title") if "title" in names else None
    bad: list[str] = []
    seen: dict[str, int] = {}
    added = already = 0
    n = 1
    while True:
        n += 1
        try:
            row = next(reader)
        except StopIteration:
            break
        except csv.Error:  # a field past the parser's limit: the rest is not read
            bad.append(f"Row {n} could not be read; the rows after it were not read.")
            break
        if not any(cell.strip() for cell in row):
            continue
        if n - 1 > MAX_ROWS:
            bad.append(f"Rows past {MAX_ROWS} were not read.")
            break
        address = row[at_email].strip() if at_email < len(row) else ""
        name = row[at_name].strip() if at_name is not None and at_name < len(row) else ""
        title = row[at_title].strip() if at_title is not None and at_title < len(row) else ""
        if len(address) > MAX_EMAIL or not _EMAIL.fullmatch(address):
            shown = address if len(address) <= 60 else address[:57] + "…"
            bad.append(f"Row {n}: “{shown}” is not an email address.")
            continue
        key = people.email_key(address) or ""
        if seen.get(key, 0) >= most:
            bad.append(
                f"Row {n}: {address} is in the file twice."
                if most == 1
                else f"Row {n}: {address} is in the file more than {most} times."
            )
            continue
        seen[key] = seen.get(key, 0) + 1
        person = _on_record(session, address) or people.pending(session, address, actor)
        if name and not person.display_name and person.object_id is None:
            person.display_name = name[:200]  # a pending person's name, from the file
        if add(session, public_id, person, "csv", actor, mint=False, title=title):
            added += 1
        else:
            already += 1
    if added:  # once for the file (ruling 81), not per row
        dossiers.sync_candidates(session, _exercise(session, public_id), actor)
    return Imported(added, already, tuple(bad))
