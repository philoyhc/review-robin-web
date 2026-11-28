"""An exercise's panels and the Panels roster in the database (segment
AD2E, rulings 19, 20, 22, 23 and 39).

``load`` builds the pages' shapes, ``sample_data.Panel`` and the roster
``(Member, panel keys)`` rows, from the stored rows; None until Panels is
first saved, so the pages keep the sample's. ``save`` replaces the roster
with the page's snapshot under the exercise's row lock, guarded by
``exercise.panels_revision``. ``adopt`` stores the panels Form and Process
make with *+New panel…*, with those pages' own saves.

Keys are ``panel-<n>``, minted here past every key the exercise has held,
retired ones and the sample's included, so a key is never given twice
(ruling 37). A page's own placeholder keys (``made-1``, ``new-1``) never
reach a row. Each address is matched to a person on record, else stored as
a pending person, as Create dossiers' CSV is. Rows are retired, never deleted
(ruling 74): a person removed and added again revives their row.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from applydesk import audit, db, directory_check, people, sample_data
from applydesk.models import Exercise, PanelMember, Person, RosterEntry
from applydesk.models import Panel as PanelRow
from applydesk.sample_data import Member, Panel

#: An exercise's panels and roster, at most (the author, 2026-11-23).
MAX_PANELS = 50
MAX_PEOPLE = 2000
_EMAIL = re.compile(r"[^\s@<>,;]+@[^\s@<>,;]+\.[^\s@<>,;]+")
_RESERVED = re.compile(r"\s*(name|email|note)\s*", re.IGNORECASE)
_KEY = re.compile(r"[a-z][a-z0-9-]{0,40}")

Roster = tuple[tuple[Member, frozenset[str]], ...]


@dataclass(frozen=True)
class State:
    """The panels in order, each with its members in roster order, and
    every row of the Panels table, someone on no panel included."""

    panels: tuple[Panel, ...]
    roster: Roster


class Refused(Exception):
    """A save that cannot be kept, said to the operator; ``key`` names the
    kind of refusal for a caller that tells them apart."""

    def __init__(self, message: str, key: str = "refused") -> None:
        super().__init__(message)
        self.key = key


def _now() -> datetime:
    return datetime.now(UTC)


def _exercise(session: Session, public_id: str, *, lock: bool = False) -> Exercise:
    query = select(Exercise).where(Exercise.public_id == public_id, Exercise.deleted_at.is_(None))
    found = session.scalar(
        query.with_for_update().execution_options(populate_existing=True) if lock else query
    )
    if found is None:
        raise Refused("That exercise is no longer on record.", key="gone")
    return found


# --- Load ------------------------------------------------------------------


def _assemble(
    public_id: str, panels: list[tuple[str, str]], people: list[tuple[Member, set[str]]]
) -> State:
    built = tuple(
        Panel(public_id, key, name, tuple(m for m, keys in people if key in keys))
        for key, name in panels
    )
    return State(built, tuple((m, frozenset(keys)) for m, keys in people))


def load(session: Session, public_id: str) -> State | None:
    """The panels and roster Panels last saved, else None (never saved:
    the pages keep the sample's)."""
    exercise = session.scalar(select(Exercise).where(Exercise.public_id == public_id))
    if exercise is None or exercise.panels_revision < 1:
        return None
    panels = list(
        session.scalars(
            select(PanelRow)
            .where(PanelRow.exercise_id == exercise.id, PanelRow.retired_at.is_(None))
            .order_by(PanelRow.position)
        )
    )
    rows = session.execute(
        select(RosterEntry, Person)
        .join(Person, Person.id == RosterEntry.person_id)
        .where(RosterEntry.exercise_id == exercise.id, RosterEntry.retired_at.is_(None))
        .order_by(RosterEntry.position)
    ).all()
    by_id = {p.id: p.key for p in panels}
    ticks: dict[int, set[str]] = {}
    if rows:
        for member in session.scalars(
            select(PanelMember).where(
                PanelMember.roster_entry_id.in_([e.id for e, _ in rows]),
                PanelMember.retired_at.is_(None),
            )
        ):
            if member.panel_id in by_id:
                ticks.setdefault(member.roster_entry_id, set()).add(by_id[member.panel_id])
    # A blank name reads as the address, as the page shows it; it is stored
    # blank, since an address may be longer than a name's column (Codex on
    # #4170).
    people_rows = [
        (Member(e.name or p.email or "", p.email or "", e.note), ticks.get(e.id, set()))
        for e, p in rows
    ]
    return _assemble(public_id, [(p.key, p.name) for p in panels], people_rows)


def lock(session: Session, public_id: str) -> Exercise:
    """Take the exercise's lock in ``session``: a save that reads the
    panels before it writes holds it first. A no-op write as well as the
    row lock, since SQLite has no row locks but serializes writers: any
    two saves that read and change the panels take turns (Codex on #4171)."""
    exercise = _exercise(session, public_id, lock=True)
    session.execute(
        update(Exercise)
        .where(Exercise.id == exercise.id)
        .values(panels_revision=Exercise.panels_revision)
        .execution_options(synchronize_session=False)
    )
    return exercise


def stored(public_id: str) -> State | None:
    """The panels Panels last saved, read in a session of its own (the
    readers in ``sample_data``, which no route hands a session); None if
    never saved."""
    session = db.new_session()
    try:
        return load(session, public_id)
    finally:
        session.close()


def revision(public_id: str) -> int:
    """How many times the exercise's panels were saved: the Panels page
    sends the one it opened at, and a save from an older one is refused."""
    session = db.new_session()
    try:
        found = session.scalar(
            select(Exercise.panels_revision).where(Exercise.public_id == public_id)
        )
    finally:
        session.close()
    return found or 0


def _before(session: Session, exercise: Exercise) -> State:
    """What the page started from: the stored roster, else the sample's."""
    stored = load(session, exercise.public_id)
    if stored is not None:
        return stored
    panels = [p for p in sample_data.PANELS if p.exercise_id == exercise.public_id]
    people_rows: dict[str, tuple[Member, set[str]]] = {}
    for p in panels:
        for m in p.members:
            people_rows.setdefault(m.email.lower(), (m, set()))[1].add(p.key)
    return _assemble(
        exercise.public_id, [(p.key, p.name) for p in panels], list(people_rows.values())
    )


def taken_keys(session: Session, exercise: Exercise) -> set[str]:
    """Every panel key the exercise has held, retired ones and the
    sample's included: a new key is minted past them."""
    keys = {p.key for p in sample_data.PANELS if p.exercise_id == exercise.public_id}
    keys |= set(session.scalars(select(PanelRow.key).where(PanelRow.exercise_id == exercise.id)))
    return keys


def _fresh(taken: set[str]) -> str:
    n = 1
    while f"panel-{n}" in taken:
        n += 1
    taken.add(f"panel-{n}")
    return f"panel-{n}"


# --- The page's snapshot, checked -------------------------------------------


def _text(v: Any, what: str, most: int) -> str:
    if not isinstance(v, str):
        raise Refused(f"{what} is malformed.")
    if len(v.strip()) > most:
        raise Refused(f"{what} is too long.")
    return v.strip()


def _name(v: Any, names: set[str]) -> str:
    name = _text(v, "A panel's name", 80)
    if not name:
        raise Refused("Every panel needs a name.")
    if _RESERVED.fullmatch(name):
        raise Refused(f"{name} names a CSV column: choose another name.")
    if name.casefold() in names:
        raise Refused(f"Two panels are called {name}.")
    names.add(name.casefold())
    return name


def _member(v: Any, what: str) -> Member:
    if not isinstance(v, dict):
        raise Refused(f"{what} is malformed.")
    got = cast(dict[str, Any], v)
    email = _text(got.get("email"), what, 254)
    if not _EMAIL.fullmatch(email):
        raise Refused(f"{what} has no email address.")
    return Member(
        _text(got.get("name", ""), what, 200) or email,
        email,
        _text(got.get("note", ""), what, 200),
    )


def _parse(
    public_id: str, sent: Any, before: State, taken: set[str], in_use: frozenset[str]
) -> State:
    """The Panels page's snapshot, checked: panels with distinct names, a
    row per person with a distinct address, ticks naming its panels. A
    panel ``in_use`` (a question's or a gate's) may not be retired."""
    if not isinstance(sent, dict):
        raise Refused("The panels are malformed.")
    got = cast(dict[str, Any], sent)
    raw_panels, raw_people = got.get("panels"), got.get("people")
    if not isinstance(raw_panels, list) or not isinstance(raw_people, list):
        raise Refused("The panels are malformed.")
    if len(cast(list[Any], raw_panels)) > MAX_PANELS:
        raise Refused(f"An exercise holds at most {MAX_PANELS} panels.", key="cap")
    if len(cast(list[Any], raw_people)) > MAX_PEOPLE:
        raise Refused(f"The roster holds at most {MAX_PEOPLE} people.", key="cap")
    known = {p.key for p in before.panels}
    # A page that missed its reload after a save keyed its panels still
    # names them ``made-1``…: by name, the saved panel it became, unless
    # the post carries that panel under its own key too (Codex on #4027).
    sent_keys = {
        key
        for p in cast(list[Any], raw_panels)
        if isinstance(p, dict) and isinstance(key := cast(dict[str, Any], p).get("key"), str)
    }
    by_name = {p.name.casefold(): p.key for p in before.panels if p.key not in sent_keys}
    keys: dict[str, str] = {}
    panels: list[tuple[str, str]] = []
    names: set[str] = set()
    for raw in cast(list[Any], raw_panels):
        if not isinstance(raw, dict):
            raise Refused("A panel is malformed.")
        panel = cast(dict[str, Any], raw)
        key = _text(panel.get("key"), "A panel's key", 40)
        if not _KEY.fullmatch(key) or key in keys:
            raise Refused("A panel's key is malformed.")
        name = _name(panel.get("name"), names)
        keys[key] = key if key in known else by_name.pop(name.casefold(), None) or _fresh(taken)
        panels.append((keys[key], name))
    if in_use - set(keys.values()):
        raise Refused(
            "A panel in use cannot be retired: free it on Form or Process first.", key="in_use"
        )
    people: list[tuple[Member, set[str]]] = []
    seen: set[str] = set()
    for n, raw in enumerate(cast(list[Any], raw_people), 1):
        member = _member(raw, f"Row {n}")
        if member.email.casefold() in seen:
            raise Refused(f"Row {n} repeats {member.email}.")
        seen.add(member.email.casefold())
        ticks = cast(dict[str, Any], raw).get("panels")
        if not isinstance(ticks, list) or not all(
            isinstance(k, str) for k in cast(list[Any], ticks)
        ):
            raise Refused(f"Row {n} is malformed.")
        if any(k not in keys for k in cast(list[str], ticks)):
            raise Refused(f"Row {n} is ticked on a panel that is not on the page.")
        people.append((member, {keys[k] for k in cast(list[str], ticks)}))
    return _assemble(public_id, panels, people)


# --- Save ------------------------------------------------------------------


def _on_record(
    session: Session,
    address: str,
    actor: Person | None,
    bound: Mapping[str, Person] | None = None,
) -> Person:
    """The person the directory resolved this address to (``bound``, segment
    AD2Y), else the person on record with it (a bound one by its address
    snapshot, else a pending one), else a new pending person."""
    key = people.email_key(address)
    if bound and key and key in bound:
        return bound[key]
    found = session.scalar(
        select(Person)
        .where(Person.email_key == key)
        .order_by(Person.object_id.is_(None), Person.id)
    )
    return found or people.pending(session, address, actor)


def _write(
    session: Session,
    exercise: Exercise,
    state: State,
    actor: Person | None,
    bound: Mapping[str, Person] | None = None,
) -> dict[str, int]:
    """Make the stored rows say ``state``: panels by key, roster entries
    by person, memberships by pair; whatever the state drops is retired."""
    at = _now()
    panel_rows = {
        r.key: r
        for r in session.scalars(select(PanelRow).where(PanelRow.exercise_id == exercise.id))
    }
    # Retire first: a name a retired panel frees may be taken by another.
    wanted = {p.key for p in state.panels}
    retired = 0
    for key, row in panel_rows.items():
        if key not in wanted and row.retired_at is None:
            row.retired_at = at
            retired += 1
    # Names park on their keys first, so two panels swapping names never
    # meet the live-name index half-way.
    for p in state.panels:
        if p.key in panel_rows and panel_rows[p.key].retired_at is None:
            panel_rows[p.key].name_key = f"\u0001{p.key}"
    session.flush()
    for position, p in enumerate(state.panels):
        row = panel_rows.get(p.key)
        if row is None:
            row = PanelRow(exercise_id=exercise.id, key=p.key)
            session.add(row)
            panel_rows[p.key] = row
        row.name, row.name_key, row.position, row.retired_at = (
            p.name,
            p.name.casefold(),
            position,
            None,
        )
    session.flush()
    entries = {
        e.person_id: e
        for e in session.scalars(select(RosterEntry).where(RosterEntry.exercise_id == exercise.id))
    }
    kept: dict[int, tuple[RosterEntry, frozenset[str]]] = {}
    for position, (member, keys) in enumerate(state.roster):
        person = _on_record(session, member.email, actor, bound)
        if person.id in kept:
            raise Refused(f"{member.email} is someone already on the roster under another address.")
        entry = entries.get(person.id)
        if entry is None:
            entry = RosterEntry(exercise_id=exercise.id, person_id=person.id)
            session.add(entry)
            entries[person.id] = entry
        entry.name, entry.note, entry.position, entry.retired_at = (
            "" if member.name == member.email else member.name,
            member.note,
            position,
            None,
        )
        kept[person.id] = (entry, keys)
    for person_id, entry in entries.items():
        if person_id not in kept and entry.retired_at is None:
            entry.retired_at = at
    session.flush()
    entry_ids = [e.id for e in entries.values()]
    pairs = (
        {
            (m.panel_id, m.roster_entry_id): m
            for m in session.scalars(
                select(PanelMember).where(PanelMember.roster_entry_id.in_(entry_ids))
            )
        }
        if entry_ids
        else {}
    )
    live: set[tuple[int, int]] = set()
    for entry, keys in kept.values():
        for key in keys:
            pair = (panel_rows[key].id, entry.id)
            live.add(pair)
            member_row = pairs.get(pair)
            if member_row is None:
                session.add(PanelMember(panel_id=pair[0], roster_entry_id=pair[1]))
            else:
                member_row.retired_at = None
    for pair, member_row in pairs.items():
        if pair not in live and member_row.retired_at is None:
            member_row.retired_at = at
    session.flush()
    return {"panels": len(state.panels), "people": len(state.roster), "retired": retired}


def save(
    session: Session,
    public_id: str,
    sent: Any,
    opened: int,
    actor: Person | None,
    in_use: Callable[[], frozenset[str]],
    *,
    lookup: directory_check.Lookup | None = None,
    tenant_id: str = "",
) -> int:
    """Keep the Panels page's snapshot ``sent`` as the exercise's panels and
    roster, if no save came between (``opened``, the revision the page
    loaded); the new revision. A member ``lookup`` resolved is bound to
    their account's person (segment AD2Y). Flushed, not committed: the caller's
    transaction holds the change and its audit."""
    exercise = lock(session, public_id)
    if exercise.archived_at is not None:
        raise Refused("Archived: restore it to change it.", key="archived")
    if opened != exercise.panels_revision:
        raise Refused(
            "Not saved: Panels was saved since this page opened. Reload to see it.", key="stale"
        )
    before = _before(session, exercise)
    # What uses a panel is read under the lock, so a Process save that adds
    # a gate on it cannot land between the check and this save (cold read).
    state = _parse(public_id, sent, before, taken_keys(session, exercise), in_use())
    # Segment AD2Y: the members the directory resolved are bound to their
    # accounts' people; the rest are on record or pending, as before.
    bound = directory_check.bind(session, lookup, tenant_id, actor) if lookup else {}
    counts = _write(session, exercise, state, actor, bound)
    exercise.panels_revision += 1
    audit.write_event(
        session,
        event_type="exercise.panels_saved",
        actor=actor,
        exercise=exercise,
        payload=audit.counts(**counts),
        context={"revision": exercise.panels_revision},
    )
    session.flush()
    return exercise.panels_revision


def adopt(
    session: Session, public_id: str, made: Any, wanted: set[str], actor: Person | None
) -> dict[str, str]:
    """Store the panels a page made with *+New panel…* that its save names
    (``wanted``, keys such as ``new-1``), each given a key of its own and
    added to the exercise's panels, its members to the roster; the key
    map. ``made`` is the page's ``applydeskMadePanels``:
    {key: {name, members: [[name, email], ...]}}. A panel the exercise
    already holds by that name (a page that has not reloaded since a save
    adopted it) is that panel, not a second one. Flushed, not committed:
    the caller's own save shares the transaction."""
    if not wanted:
        return {}
    if not isinstance(made, dict):
        raise Refused("A panel made on this page is malformed.")
    pools = cast(dict[str, Any], made)
    exercise = lock(session, public_id)
    if exercise.archived_at is not None:
        raise Refused("Archived: restore it to change it.", key="archived")
    before = _before(session, exercise)
    taken = taken_keys(session, exercise)
    panels = [(p.key, p.name) for p in before.panels]
    roster = [(m, set(keys)) for m, keys in before.roster]
    before_panels = list(panels)
    before_roster = [(m, set(keys)) for m, keys in roster]
    names = {n.casefold() for _, n in panels}
    by_name = {n.casefold(): k for k, n in panels}
    by_email = {m.email.casefold(): i for i, (m, _) in enumerate(roster)}
    keys: dict[str, str] = {}
    for old in sorted(wanted):
        pool = pools.get(old)
        if not isinstance(pool, dict):
            raise Refused("A panel made on this page is malformed.")
        got = cast(dict[str, Any], pool)
        typed = _text(got.get("name"), "A panel's name", 80)
        members = got.get("members")
        if not isinstance(members, list):
            raise Refused(f"{typed or 'A panel'} is malformed.")
        again = by_name.get(typed.casefold())
        if again is not None:
            new = again
        else:
            name = _name(typed, names)
            new = _fresh(taken)
            panels.append((new, name))
            by_name[name.casefold()] = new
        keys[old] = new
        for raw in cast(list[Any], members):
            if not isinstance(raw, list) or len(cast(list[Any], raw)) != 2:
                raise Refused(f"{typed} is malformed.")
            pair = cast(list[Any], raw)
            member = _member({"name": pair[0], "email": pair[1]}, typed)
            at = by_email.get(member.email.casefold())
            if at is None:
                by_email[member.email.casefold()] = len(roster)
                roster.append((member, {new}))
            else:
                roster[at][1].add(new)
    if len(panels) > MAX_PANELS:
        raise Refused(f"An exercise holds at most {MAX_PANELS} panels.", key="cap")
    if len(roster) > MAX_PEOPLE:
        raise Refused(f"The roster holds at most {MAX_PEOPLE} people.", key="cap")
    # Offered again by a page that missed its reload, with nothing new: the
    # panels as they stand, no save written (cold read).
    if (panels, roster) == (before_panels, before_roster):
        return keys
    counts = _write(session, exercise, _assemble(public_id, panels, roster), actor)
    exercise.panels_revision += 1
    audit.write_event(
        session,
        event_type="exercise.panels_saved",
        actor=actor,
        exercise=exercise,
        payload=audit.counts(**counts),
        context={"revision": exercise.panels_revision},
    )
    session.flush()
    return keys


def unbound_addresses(session: Session, sent: Any) -> list[str]:
    """The addresses Panels' snapshot ``sent`` names that no bound person
    holds: those a save asks the directory about (segment AD2Y), so a
    roster already bound costs no lookup. A malformed snapshot names none;
    the save then says why."""
    got = cast(dict[str, Any], sent) if isinstance(sent, dict) else {}
    rows = got.get("people")
    if not isinstance(rows, list):
        return []
    addresses: dict[str, str] = {}
    for row in cast(list[Any], rows):
        email = cast(dict[str, Any], row).get("email") if isinstance(row, dict) else None
        key = people.email_key(email) if isinstance(email, str) else None
        if key:
            addresses.setdefault(key, cast(str, email).strip())
    if not addresses:
        return []
    known = set(
        session.scalars(
            select(Person.email_key).where(
                Person.email_key.in_(list(addresses)), Person.object_id.is_not(None)
            )
        )
    )
    return [address for key, address in addresses.items() if key not in known]
