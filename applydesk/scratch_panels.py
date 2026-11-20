"""Panels on a scratch exercise (segment AD1N rung 5): the Panels page's
*Save*, and the panels Form and Process make with *+ New panel…*, kept in
the scratch store as the roster the page draws and the panels it reads.

The store holds ``(panels, roster)``: the panels in order, each with its
members, and every row of the Panels table, someone on no panel included,
so a person ticked off every panel is not lost. ``sample_data.panels_of``
and ``sample_data.roster`` read it first.

A panel the page made (``made-1``, ``new-1``) gets a key of its own,
``panel-1``..., on its first save; a saved panel keeps its key, which is
what Form's questions and Process's gates name it by.
"""

from __future__ import annotations

import re
from typing import Any, cast

from applydesk import scratch
from applydesk.sample_data import Member, Panel

PAGE = "panels"
MAX_PANELS = 50
MAX_PEOPLE = 2000
_EMAIL = re.compile(r"[^\s@<>,;]+@[^\s@<>,;]+\.[^\s@<>,;]+")
_RESERVED = re.compile(r"\s*(name|email|note)\s*", re.IGNORECASE)
_KEY = re.compile(r"[a-z][a-z0-9-]{0,40}")

Roster = tuple[tuple[Member, frozenset[str]], ...]
State = tuple[tuple[Panel, ...], Roster]


class Refused(Exception):
    """A save that cannot be kept, said to the operator."""


def saved(exercise_id: str) -> State | None:
    """The scratch exercise's panels and roster as last saved, else None."""
    held = scratch.page(exercise_id, PAGE)
    return cast(State, held) if isinstance(held, tuple) else None


def _text(v: Any, what: str, most: int) -> str:
    if not isinstance(v, str):
        raise Refused(f"{what} is malformed.")
    if len(v.strip()) > most:
        raise Refused(f"{what} is too long.")
    return v.strip()


def _fresh(taken: set[str]) -> str:
    n = 1
    while f"panel-{n}" in taken:
        n += 1
    taken.add(f"panel-{n}")
    return f"panel-{n}"


def _name(v: Any, names: set[str]) -> str:
    name = _text(v, "A panel's name", 80)
    if not name:
        raise Refused("Every panel needs a name.")
    if _RESERVED.fullmatch(name):
        raise Refused(f"{name} names a CSV column: choose another name.")
    if name.lower() in names:
        raise Refused(f"Two panels are called {name}.")
    names.add(name.lower())
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


def _assemble(
    exercise_id: str, panels: list[tuple[str, str]], people: list[tuple[Member, set[str]]]
) -> State:
    """The panels, each with the people ticked on it in roster order, and
    the roster itself."""
    built = tuple(
        Panel(exercise_id, key, name, tuple(m for m, keys in people if key in keys))
        for key, name in panels
    )
    return built, tuple((m, frozenset(keys)) for m, keys in people)


def build(sent: Any, exercise_id: str, in_use: frozenset[str]) -> State:
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
        raise Refused(f"An exercise holds at most {MAX_PANELS} panels.")
    if len(cast(list[Any], raw_people)) > MAX_PEOPLE:
        raise Refused(f"The roster holds at most {MAX_PEOPLE} people.")
    before = saved(exercise_id)
    known = {p.key for p in before[0]} if before else set[str]()
    taken = set(known)
    keys: dict[str, str] = {}
    panels: list[tuple[str, str]] = []
    names: set[str] = set()
    # A page that missed its reload after a save keyed its panels still
    # names them ``made-1``…: by name, the saved panel it became, unless
    # the post carries that panel under its own key too (Codex on #4027).
    sent_keys = {
        key
        for p in cast(list[Any], raw_panels)
        if isinstance(p, dict) and isinstance(key := cast(dict[str, Any], p).get("key"), str)
    }
    by_name = {p.name.lower(): p.key for p in before[0] if p.key not in sent_keys} if before else {}
    for raw in cast(list[Any], raw_panels):
        if not isinstance(raw, dict):
            raise Refused("A panel is malformed.")
        panel = cast(dict[str, Any], raw)
        key = _text(panel.get("key"), "A panel's key", 40)
        if not _KEY.fullmatch(key) or key in keys:
            raise Refused("A panel's key is malformed.")
        name = _name(panel.get("name"), names)
        keys[key] = key if key in known else by_name.pop(name.lower(), None) or _fresh(taken)
        panels.append((keys[key], name))
    retired = in_use - set(keys.values())
    if retired:
        raise Refused("A panel in use cannot be retired: free it on Form or Process first.")
    people: list[tuple[Member, set[str]]] = []
    seen: set[str] = set()
    for n, raw in enumerate(cast(list[Any], raw_people), 1):
        member = _member(raw, f"Row {n}")
        if member.email.lower() in seen:
            raise Refused(f"Row {n} repeats {member.email}.")
        seen.add(member.email.lower())
        ticks = cast(dict[str, Any], raw).get("panels")
        if not isinstance(ticks, list) or not all(
            isinstance(k, str) for k in cast(list[Any], ticks)
        ):
            raise Refused(f"Row {n} is malformed.")
        if any(k not in keys for k in cast(list[str], ticks)):
            raise Refused(f"Row {n} is ticked on a panel that is not on the page.")
        people.append((member, {keys[k] for k in cast(list[str], ticks)}))
    return _assemble(exercise_id, panels, people)


def adopt(exercise_id: str, made: Any, wanted: set[str]) -> tuple[dict[str, str], State | None]:
    """The panels a page made with *+ New panel…* that its save names
    (``wanted``, keys such as ``new-1``), each given a key of its own and
    added to the scratch exercise's panels, its members to the roster:
    the key map, and the state to keep once the page's own save is kept
    (None when it names no such panel). ``made`` is the page's
    ``applydeskMadePanels``: {key: {name, members: [[name, email], ...]}}."""
    if not wanted:
        return {}, None
    if not isinstance(made, dict):
        raise Refused("A panel made on this page is malformed.")
    pools = cast(dict[str, Any], made)
    before = saved(exercise_id)
    panels = [(p.key, p.name) for p in before[0]] if before else []
    people = [(m, set(keys)) for m, keys in before[1]] if before else []
    taken = {k for k, _ in panels}
    names = {n.lower() for _, n in panels}
    by_email = {m.email.lower(): i for i, (m, _) in enumerate(people)}
    keys: dict[str, str] = {}
    by_name = {n.lower(): k for k, n in panels}
    for old in sorted(wanted):
        pool = pools.get(old)
        if not isinstance(pool, dict):
            raise Refused("A panel made on this page is malformed.")
        got = cast(dict[str, Any], pool)
        typed = _text(got.get("name"), "A panel's name", 80)
        members = got.get("members")
        if not isinstance(members, list):
            raise Refused(f"{typed or 'A panel'} is malformed.")
        # Offered again by a page that has not reloaded since a save
        # adopted it (an edit made while that save was on its way keeps
        # the page from reloading): the panel kept then, by its name, not a
        # second one refused as a duplicate (Codex on #4027).
        again = by_name.get(typed.lower())
        if again is not None:
            new = again
        else:
            name = _name(typed, names)
            new = _fresh(taken)
            panels.append((new, name))
            by_name[name.lower()] = new
        keys[old] = new
        for raw in cast(list[Any], members):
            if not isinstance(raw, list) or len(cast(list[Any], raw)) != 2:
                raise Refused(f"{typed} is malformed.")
            pair = cast(list[Any], raw)
            member = _member({"name": pair[0], "email": pair[1]}, typed)
            at = by_email.get(member.email.lower())
            if at is None:
                by_email[member.email.lower()] = len(people)
                people.append((member, {new}))
            else:
                people[at][1].add(new)
    if len(panels) > MAX_PANELS:
        raise Refused(f"An exercise holds at most {MAX_PANELS} panels.")
    return keys, _assemble(exercise_id, panels, people)


def keep(exercise_id: str, state: State | None) -> None:
    if state is not None:
        scratch.save_page(exercise_id, PAGE, state)
