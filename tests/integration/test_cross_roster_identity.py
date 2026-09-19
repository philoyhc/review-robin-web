"""One mailbox, one name — enforced on every path into every roster.

19Q Item 7. `csv_imports.check_cross_table_identity` had the rule right
and only the CSV path could reach it: the Add form wrote the row the CSV
refused, and nothing flagged it afterwards. Measured on the running app
before the fix, same session, same input — CSV **400** and zero rows,
the form **303** and one row.

The parity case below is that measurement turned into an assertion: it
drives both paths with the same input and requires the same verdict. The
rest cover what answering the item's two open questions added —
observers joining (so the check is three-way), and exact name comparison
(which makes a blank name a question the code has to answer).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Observer, Reviewee, Reviewer

from ._invitation_states import _create_session


def _session(client: TestClient, db: Session, code: str):
    """A session with observers enabled — every observers route is gated
    on `observers_enabled` and 404s without it
    (`_shared.require_observers_enabled_session`)."""
    review_session = _create_session(client, db, code)
    review_session.observers_enabled = True
    db.flush()
    return review_session

EMAIL = "aisha.haddad@example.edu"
ROSTER_FORM = {"profile_link": "", "tag_1": "", "tag_2": "", "tag_3": "", "status": "active"}

#: (roster, create path, the form's identity field, its name field)
ROSTERS = [
    ("reviewers", "reviewers/create", "email", "name"),
    ("reviewees", "reviewees/create", "email_or_identifier", "name"),
    ("observers", "observers/create", "email", "display_name"),
]


def _add(client: TestClient, session_id: int, path: str, **fields: str):
    return client.post(
        f"/operator/sessions/{session_id}/{path}",
        data={**ROSTER_FORM, **fields},
        follow_redirects=False,
    )


def _rows(db: Session, model, session_id: int) -> list:
    return list(
        db.execute(select(model).where(model.session_id == session_id)).scalars()
    )


def test_the_add_form_and_the_csv_reach_the_same_verdict(
    client: TestClient, db: Session
) -> None:
    """The item's whole point, and the measurement that opened it.

    A reviewee holds the mailbox under one name. Both paths are then
    offered a reviewer with that mailbox and a *different* name; before
    19Q Item 7 the CSV refused and the form accepted.
    """
    session = _session(client, db, "xr-parity")
    _add(client, session.id, "reviewees/create",
         name="Aisha Haddadx", email_or_identifier=EMAIL)

    csv = f"ReviewerName,ReviewerEmail\nAisha Haddad,{EMAIL}\n".encode()
    uploaded = client.post(
        f"/operator/sessions/{session.id}/reviewers/import",
        files={"file": ("r.csv", csv, "text/csv")},
        follow_redirects=True,
    )
    assert "names must match" in uploaded.text
    assert _rows(db, Reviewer, session.id) == []

    typed = _add(client, session.id, "reviewers/create",
                 name="Aisha Haddad", email=EMAIL)
    assert typed.status_code == 400, (
        "the Add form accepted what the CSV refused — the asymmetry 19Q "
        "Item 7 exists to remove"
    )
    assert _rows(db, Reviewer, session.id) == []


@pytest.mark.parametrize(("roster", "path", "id_field", "name_field"), ROSTERS)
def test_every_roster_refuses_a_mailbox_held_under_another_name(
    client: TestClient, db: Session, roster: str, path: str,
    id_field: str, name_field: str,
) -> None:
    """Three-way since the author's ruling: each roster checks the other
    two. A reviewee holds the mailbox; every roster must refuse a
    differently-named row for it, including the reviewee roster itself
    via the reviewer seeded below."""
    session = _session(client, db, f"xr-{roster}")
    holder_path, holder_id = (
        ("reviewers/create", "email") if roster == "reviewees"
        else ("reviewees/create", "email_or_identifier")
    )
    _add(client, session.id, holder_path, name="Held Name", **{holder_id: EMAIL})

    response = _add(client, session.id, path,
                    **{id_field: EMAIL, name_field: "Different Name"})
    assert response.status_code == 400, f"{roster} accepted a conflicting name"


@pytest.mark.parametrize(("roster", "path", "id_field", "name_field"), ROSTERS)
def test_the_same_name_is_the_legitimate_case_and_still_creates(
    client: TestClient, db: Session, roster: str, path: str,
    id_field: str, name_field: str,
) -> None:
    """The control, and the reason this is a name check and not an email
    check: one person is commonly reviewer and reviewee both, and may
    observe too. Without this the item would have banned self-review."""
    session = _session(client, db, f"xr-same-{roster}")
    holder_path, holder_id = (
        ("reviewers/create", "email") if roster == "reviewees"
        else ("reviewees/create", "email_or_identifier")
    )
    _add(client, session.id, holder_path, name="Aisha Haddad", **{holder_id: EMAIL})

    response = _add(client, session.id, path,
                    **{id_field: EMAIL, name_field: "Aisha Haddad"})
    assert response.status_code == 303, f"{roster} refused the same name"


def test_an_unnamed_observer_does_not_collide(
    client: TestClient, db: Session
) -> None:
    """Where the author's two answers meet.

    `Observer.display_name` is nullable and its CSV column optional,
    where the other two names are not. Under an exact comparison a blank
    name would differ from every real one, so without the skip every
    unnamed observer would collide with the reviewer sharing its
    mailbox.
    """
    session = _session(client, db, "xr-unnamed")
    _add(client, session.id, "reviewers/create", name="Aisha Haddad", email=EMAIL)

    response = _add(client, session.id, "observers/create",
                    email=EMAIL, display_name="")
    assert response.status_code == 303
    assert len(_rows(db, Observer, session.id)) == 1


def test_a_name_only_edit_is_caught(client: TestClient, db: Session) -> None:
    """The within-roster gate fires only on an identifier edit, so
    renaming a row into disagreement is invisible to it. The cross-roster
    guard keys on the resulting pair instead."""
    session = _session(client, db, "xr-rename")
    _add(client, session.id, "reviewers/create", name="Aisha Haddad", email=EMAIL)
    _add(client, session.id, "reviewees/create",
         name="Aisha Haddad", email_or_identifier=EMAIL)
    reviewee = _rows(db, Reviewee, session.id)[0]

    response = client.post(
        f"/operator/sessions/{session.id}/reviewees/{reviewee.id}/update",
        data={**ROSTER_FORM, "name": "Someone Else", "email_or_identifier": EMAIL},
        follow_redirects=False,
    )
    assert response.status_code == 400, (
        "a name-only edit walked past the guard; it must key on the "
        "resulting (identifier, name) pair, not on what changed"
    )


def test_an_unknown_kind_is_loud() -> None:
    """It used to return `[]`, so an observer CSV routed through the
    shared path would have been checked, found nothing, and reported
    success — a guard that passes by not running."""
    from app.services import csv_imports

    with pytest.raises(ValueError, match="unknown kind"):
        csv_imports.check_cross_table_identity(
            None, session_id=1, rows=[], kind="relationships"  # type: ignore[arg-type]
        )


def test_the_single_row_helper_is_loud_too() -> None:
    """Both entry points guard the kind, and both need saying.

    A mutant that reverted only `cross_table_identity_conflict`'s guard
    survived the case above: it asserts on `check_cross_table_identity`,
    and the services call the other function. Two guards, two tests.
    """
    from app.services import csv_imports

    with pytest.raises(ValueError, match="unknown kind"):
        csv_imports.cross_table_identity_conflict(
            None,  # type: ignore[arg-type]
            session_id=1,
            kind="relationships",
            identifier="x@example.edu",
            name="X",
        )


def test_an_unnamed_holder_does_not_block_a_named_row(
    client: TestClient, db: Session
) -> None:
    """The skip runs on both sides of the comparison.

    `test_an_unnamed_observer_does_not_collide` covers the *incoming*
    row being unnamed. This is the mirror — the row already in the
    session is the unnamed one — and a mutant that stopped skipping
    blank holder names survived until it was written.
    """
    session = _session(client, db, "xr-unnamed-holder")
    _add(client, session.id, "observers/create", email=EMAIL, display_name="")

    response = _add(client, session.id, "reviewers/create",
                    name="Aisha Haddad", email=EMAIL)
    assert response.status_code == 303, (
        "an unnamed observer blocked a named reviewer; a missing name "
        "cannot disagree with one, on either side"
    )


def test_the_name_comparison_is_case_sensitive(
    client: TestClient, db: Session
) -> None:
    """The author's ruling of 2026-09-19, which nothing pinned until a
    mutant folded the comparison and every test passed.

    **Case is a difference.** That is the choice, and this is what goes
    red if someone tidies it into a `.lower()`.
    """
    session = _session(client, db, "xr-exact-case")
    _add(client, session.id, "reviewers/create", name="Aisha Haddad", email=EMAIL)
    response = _add(client, session.id, "reviewees/create",
                    name="aisha haddad", email_or_identifier=EMAIL)
    assert response.status_code == 400, (
        "'aisha haddad' was accepted against 'Aisha Haddad' — the "
        "comparison is case-sensitive by ruling, not incidentally"
    )


def test_surrounding_whitespace_is_not_a_difference(
    client: TestClient, db: Session
) -> None:
    """**And this is the half "exact" does not mean.**

    Both paths trim a name long before it reaches the comparison —
    `_cell` on the CSV side, `_normalised_name` in the services — so
    `'Aisha Haddad '` is stored and compared as `'Aisha Haddad'` and
    cannot conflict with it. The plan first claimed a trailing space
    would fail; writing this case is what disproved it.
    """
    session = _session(client, db, "xr-exact-space")
    _add(client, session.id, "reviewers/create", name="Aisha Haddad", email=EMAIL)
    response = _add(client, session.id, "reviewees/create",
                    name="Aisha Haddad ", email_or_identifier=EMAIL)
    assert response.status_code == 303, (
        "a trailing space was treated as a conflict; names are trimmed "
        "upstream, so it never reaches the comparison"
    )


def test_the_observer_csv_import_checks_too(
    client: TestClient, db: Session
) -> None:
    """The call site 19Q Item 7 added, and the one no test reached.

    The observers CSV skipped the cross-table check entirely and said so
    in a docstring — *a person can be both an observer and a reviewer by
    design*. True, and never an argument for the exclusion: the check
    has always allowed one person to hold two roles and blocks only two
    **names**.
    """
    session = _session(client, db, "xr-observer-csv")
    _add(client, session.id, "reviewers/create", name="Aisha Haddad", email=EMAIL)

    csv = f"ObserverName,ObserverEmail\nAisha Haddadx,{EMAIL}\n".encode()
    response = client.post(
        f"/operator/sessions/{session.id}/observers/import",
        files={"file": ("o.csv", csv, "text/csv")},
        follow_redirects=True,
    )
    assert "names must match" in response.text
    assert _rows(db, Observer, session.id) == []


def test_an_unnamed_observer_row_in_a_csv_does_not_collide(
    client: TestClient, db: Session
) -> None:
    """The CSV path has its own blank-name skip, and needs its own case.

    `test_an_unnamed_observer_does_not_collide` drives the Add form,
    which goes through `cross_table_identity_conflict`; the importer
    goes through `check_cross_table_identity`. Two functions, two skips
    — a mutant that removed only the importer's survived until this was
    written. `ObserverName` is an optional column, so a blank cell is a
    real shape, not a contrived one.
    """
    session = _session(client, db, "xr-csv-unnamed")
    _add(client, session.id, "reviewers/create", name="Aisha Haddad", email=EMAIL)

    csv = f"ObserverName,ObserverEmail\n,{EMAIL}\n".encode()
    response = client.post(
        f"/operator/sessions/{session.id}/observers/import",
        files={"file": ("o.csv", csv, "text/csv")},
        follow_redirects=True,
    )
    assert "names must match" not in response.text
    assert len(_rows(db, Observer, session.id)) == 1, (
        "an unnamed observer row was blocked by the reviewer sharing its "
        "mailbox; a missing name cannot disagree with one"
    )
