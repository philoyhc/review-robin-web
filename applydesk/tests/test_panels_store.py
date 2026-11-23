"""Panels in the database (segment AD2E rung 3, `applydesk/panels_store.py`):
the roster saved whole and loaded back as the pages read it; keys kept and
minted by the server, never reused; a stale save, a cap, a duplicate and a
panel in use refused; people matched or made pending; a page's new panels
adopted; each save audited."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from applydesk import db, panels_store, sample_data
from applydesk.models import AuditEvent, Exercise, PanelMember, Person, RosterEntry
from applydesk.models import Panel as PanelRow
from applydesk.panels_store import Refused

MODEL = "wa9juxbc2t"


@pytest.fixture
def session() -> Iterator[Session]:
    s = db.new_session()
    yield s
    s.close()


def _row(name: str, email: str, panels: list[str], note: str = "") -> dict[str, Any]:
    return {"name": name, "email": email, "note": note, "panels": panels}


def _sent(panels: list[tuple[str, str]], people: list[dict[str, Any]]) -> dict[str, Any]:
    return {"panels": [{"key": k, "name": n} for k, n in panels], "people": people}


def _revision(session: Session) -> int:
    return session.scalar(select(Exercise.panels_revision).where(Exercise.public_id == MODEL)) or 0


def _save(session: Session, sent: dict[str, Any], in_use: frozenset[str] = frozenset()) -> int:
    got = panels_store.save(session, MODEL, sent, _revision(session), None, in_use)
    session.commit()
    return got


def test_nothing_is_stored_until_the_first_save(session: Session) -> None:
    assert panels_store.load(session, MODEL) is None


def test_a_saved_roster_loads_back_as_the_pages_read_it(session: Session) -> None:
    sent = _sent(
        [("made-1", "Interviewers"), ("made-2", "Readers")],
        [
            _row("Ana Lim", "ana@example.edu", ["made-1", "made-2"], "Chair"),
            _row("", "bo@example.edu", ["made-2"]),
            _row("Cy Ong", "cy@example.edu", []),  # on no panel: still on the roster
        ],
    )
    assert _save(session, sent) == 1
    stored = panels_store.load(session, MODEL)
    assert stored is not None
    keys = [p.key for p in stored.panels]
    assert all(k.startswith("panel-") for k in keys) and "made-1" not in keys
    assert [p.name for p in stored.panels] == ["Interviewers", "Readers"]
    assert [m.email for m in stored.panels[1].members] == ["ana@example.edu", "bo@example.edu"]
    assert [(m.name, m.note) for m, _ in stored.roster] == [
        ("Ana Lim", "Chair"),
        ("bo@example.edu", ""),  # a blank name is the address, as the page shows it
        ("Cy Ong", ""),
    ]
    assert stored.roster[2][1] == frozenset()
    event = session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "exercise.panels_saved")
    ).one()
    assert event.detail["counts"] == {"panels": 2, "people": 3, "retired": 0}


def test_a_sample_s_keys_are_kept_and_a_new_key_passes_every_one_held(session: Session) -> None:
    sample = [p for p in sample_data.PANELS if p.exercise_id == MODEL]
    first = sample[0]
    sent = _sent(
        [(first.key, first.name), ("made-1", "Fresh")],
        [_row(m.name, m.email, [first.key]) for m in first.members],
    )
    _save(session, sent)
    stored = panels_store.load(session, MODEL)
    assert stored is not None and stored.panels[0].key == first.key
    fresh = stored.panels[1].key
    # Retire Fresh, then add another: its key is never given again.
    _save(session, _sent([(first.key, first.name)], []))
    _save(session, _sent([(first.key, first.name), ("made-1", "Fresh")], []))
    again = panels_store.load(session, MODEL)
    assert again is not None and again.panels[1].key not in {fresh, first.key}
    retired = session.scalars(select(PanelRow).where(PanelRow.key == fresh)).one()
    assert retired.retired_at is not None


def test_two_panels_may_swap_names_in_one_save(session: Session) -> None:
    _save(session, _sent([("made-1", "A"), ("made-2", "B")], []))
    stored = panels_store.load(session, MODEL)
    assert stored is not None
    a, b = (p.key for p in stored.panels)
    _save(session, _sent([(a, "B"), (b, "A")], []))
    swapped = panels_store.load(session, MODEL)
    assert swapped is not None and [(p.key, p.name) for p in swapped.panels] == [(a, "B"), (b, "A")]


def test_a_person_removed_and_added_again_revives_their_rows(session: Session) -> None:
    _save(session, _sent([("made-1", "P")], [_row("Ana", "ana@example.edu", ["made-1"])]))
    stored = panels_store.load(session, MODEL)
    assert stored is not None
    key = stored.panels[0].key
    _save(session, _sent([(key, "P")], []))
    _save(session, _sent([(key, "P")], [_row("Ana", "ANA@example.edu", [key])]))
    assert session.scalar(select(func.count()).select_from(RosterEntry)) == 1
    assert session.scalar(select(func.count()).select_from(PanelMember)) == 1
    again = panels_store.load(session, MODEL)
    assert again is not None and [m.email for m in again.panels[0].members] == ["ana@example.edu"]


def test_an_address_is_matched_to_a_person_else_made_pending(session: Session) -> None:
    known = Person(email="known@example.edu", email_key="known@example.edu", display_name="K")
    session.add(known)
    session.commit()
    _save(
        session,
        _sent([], [_row("K", "Known@Example.edu", []), _row("N", "new@example.edu", [])]),
    )
    entries = session.scalars(select(RosterEntry).order_by(RosterEntry.position)).all()
    assert entries[0].person_id == known.id
    new = session.get(Person, entries[1].person_id)
    assert new is not None and new.object_id is None and new.email_key == "new@example.edu"


@pytest.mark.parametrize(
    ("sent", "said"),
    [
        (_sent([("a", "X"), ("b", "x")], []), "Two panels are called x."),
        (_sent([("a", "Email")], []), "Email names a CSV column"),
        (_sent([], [_row("", "a@b.co", []), _row("", "A@B.CO", [])]), "Row 2 repeats"),
        (_sent([], [_row("", "nobody", [])]), "Row 1 has no email address."),
        (_sent([], [_row("", "a@b.co", ["zzz"])]), "not on the page"),
        (_sent([(f"k{n}", f"P{n}") for n in range(51)], []), "at most 50 panels"),
        (_sent([], [_row("", f"p{n}@x.co", []) for n in range(2001)]), "at most 2000 people"),
    ],
)
def test_a_bad_snapshot_is_refused_and_nothing_is_kept(
    session: Session, sent: dict[str, Any], said: str
) -> None:
    with pytest.raises(Refused, match=said):
        panels_store.save(session, MODEL, sent, 0, None, frozenset())
    session.rollback()
    assert panels_store.load(session, MODEL) is None


def test_a_stale_save_is_refused(session: Session) -> None:
    _save(session, _sent([("made-1", "P")], []))
    with pytest.raises(Refused) as why:
        panels_store.save(session, MODEL, _sent([], []), 0, None, frozenset())
    assert why.value.key == "stale"


def test_a_panel_in_use_may_not_be_retired(session: Session) -> None:
    _save(session, _sent([("made-1", "P")], []))
    stored = panels_store.load(session, MODEL)
    assert stored is not None
    key = stored.panels[0].key
    with pytest.raises(Refused) as why:
        panels_store.save(session, MODEL, _sent([], []), 1, None, frozenset({key}))
    assert why.value.key == "in_use"


def test_a_page_s_new_panels_are_adopted_once(session: Session) -> None:
    made = {"new-1": {"name": "Pickers", "members": [["Ana", "ana@example.edu"]]}}
    keys = panels_store.adopt(session, MODEL, made, {"new-1"}, None)
    session.commit()
    assert keys["new-1"].startswith("panel-")
    stored = panels_store.load(session, MODEL)
    assert stored is not None
    assert [p.name for p in stored.panels][-1] == "Pickers"
    assert [m.email for m in stored.panels[-1].members] == ["ana@example.edu"]
    # The sample's panels were recorded with it, keys kept.
    sample = [p.key for p in sample_data.PANELS if p.exercise_id == MODEL]
    assert [p.key for p in stored.panels][: len(sample)] == sample
    # A page that has not reloaded offers it again: the same panel.
    again = panels_store.adopt(session, MODEL, made, {"new-1"}, None)
    session.commit()
    assert again == keys
    assert len(panels_store.load(session, MODEL).panels) == len(stored.panels)  # pyright: ignore[reportOptionalMemberAccess]
