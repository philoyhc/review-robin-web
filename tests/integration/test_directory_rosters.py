"""Roster addresses resolved through the directory (segment 21F, rung 4):
the import stores each row's account and counts the check, the single-row
add binds, an address edit rebinds or clears, and mail for a row given by
UPN goes to the directory's mail.

The directory is `cordware.graph.FakeDirectory`'s invented accounts:
Jane Tan (mail `jane.tan@`, UPN `e0123456@`), and `office@`, which is one
account's mail and another's UPN.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from cordware.graph import FakeDirectory
from app.db.models import AuditEvent, Observer, Reviewee, Reviewer
from app.services import directory_accounts
from app.web.routes_operator import _setup_observers, _shared

from ._invitation_states import _create_session

JANE_ID = "11111111-1111-4111-8111-111111111111"
JANE = {"directory_object_id": JANE_ID, "directory_mail": "jane.tan@example.edu", "directory_upn": "e0123456@example.edu"}
ROSTER_FORM = {"profile_link": "", "tag_1": "", "tag_2": "", "tag_3": "", "status": "active"}


@pytest.fixture
def directory(monkeypatch: pytest.MonkeyPatch) -> FakeDirectory:
    fake = FakeDirectory()
    monkeypatch.setattr(_shared, "directory_or_none", lambda request: fake)
    monkeypatch.setattr(_setup_observers, "directory_or_none", lambda request: fake)
    return fake


def _session(client: TestClient, db: Session, code: str):
    review_session = _create_session(client, db, code)
    review_session.observers_enabled = True
    db.flush()
    return review_session


def _bound(row) -> dict[str, str | None]:
    return {name: getattr(row, name) for name in directory_accounts.UNBOUND}


def _row(db: Session, model, session_id: int, **where):
    query = select(model).where(model.session_id == session_id)
    for name, value in where.items():
        query = query.where(getattr(model, name) == value)
    return db.execute(query).scalar_one()


def test_an_import_binds_each_resolved_address_and_counts_the_check(
    client: TestClient, db: Session, directory: FakeDirectory
) -> None:
    session = _session(client, db, "dir-import")
    csv = (
        "ReviewerName,ReviewerEmail\n"
        "Jane by mail,Jane.Tan@example.edu\n"
        "Jane by UPN,e0123456@example.edu\n"
        "Office,office@example.edu\n"
        "Nobody,nobody@example.edu\n"
    ).encode()
    response = client.post(
        f"/operator/sessions/{session.public_id}/reviewers/import",
        files={"file": ("r.csv", csv, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303

    assert _bound(_row(db, Reviewer, session.id, name="Jane by mail")) == JANE
    assert _bound(_row(db, Reviewer, session.id, name="Jane by UPN")) == JANE
    # One account's mail is another's UPN: no binding, mail matching as before.
    assert _bound(_row(db, Reviewer, session.id, name="Office")) == directory_accounts.UNBOUND
    assert _bound(_row(db, Reviewer, session.id, name="Nobody")) == directory_accounts.UNBOUND
    # The address as written is kept.
    assert _row(db, Reviewer, session.id, name="Jane by mail").email == "Jane.Tan@example.edu"

    event = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "reviewers.imported")
    ).scalar_one()
    counts = event.detail["counts"]
    assert {k: v for k, v in counts.items() if k.startswith("directory_")} == {
        "directory_by_mail": 1,
        "directory_by_upn": 1,
        "directory_not_found": 1,
        "directory_ambiguous": 1,
        "directory_not_checked": 0,
    }


def test_a_quick_setup_upload_binds_too(
    client: TestClient, db: Session, directory: FakeDirectory, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.web.routes_operator import _quick_setup

    monkeypatch.setattr(_quick_setup, "directory_or_none", lambda request: directory)
    session = _session(client, db, "dir-quick")
    for roster, csv in (
        ("reviewers", "ReviewerName,ReviewerEmail\nJane,e0123456@example.edu\n"),
        ("reviewees", "RevieweeName,RevieweeEmail\nJane,jane.tan@example.edu\n"),
        ("observers", "ObserverName,ObserverEmail\nJane,e0123456@example.edu\n"),
    ):
        response = client.post(
            f"/operator/sessions/{session.public_id}/quick-setup/{roster}",
            files={"file": (f"{roster}.csv", csv.encode(), "text/csv")},
            follow_redirects=False,
        )
        assert response.status_code in (200, 303), response.text[:300]
    for model in (Reviewer, Reviewee, Observer):
        assert _bound(_row(db, model, session.id)) == JANE
    event = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "reviewers.imported")
    ).scalar_one()
    assert event.detail["counts"]["directory_by_upn"] == 1


def test_anonymous_reviewee_identifiers_are_neither_looked_up_nor_counted(
    client: TestClient, db: Session, directory: FakeDirectory
) -> None:
    session = _session(client, db, "dir-anon")
    csv = "RevieweeName,RevieweeEmail\nAnon,STU-0001\nJane,e0123456@example.edu\n".encode()
    client.post(
        f"/operator/sessions/{session.public_id}/reviewees/import",
        files={"file": ("e.csv", csv, "text/csv")},
        follow_redirects=False,
    )
    assert _bound(_row(db, Reviewee, session.id, name="Anon")) == directory_accounts.UNBOUND
    assert _bound(_row(db, Reviewee, session.id, name="Jane")) == JANE
    event = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "reviewees.imported")
    ).scalar_one()
    assert event.detail["counts"]["directory_by_upn"] == 1
    assert sum(v for k, v in event.detail["counts"].items() if k.startswith("directory_")) == 1


def test_an_observer_import_binds_too(
    client: TestClient, db: Session, directory: FakeDirectory
) -> None:
    session = _session(client, db, "dir-obs")
    csv = "ObserverName,ObserverEmail\nJane,e0123456@example.edu\n".encode()
    response = client.post(
        f"/operator/sessions/{session.public_id}/observers/import",
        files={"file": ("o.csv", csv, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert _bound(_row(db, Observer, session.id)) == JANE


@pytest.mark.parametrize(
    ("roster", "model", "field", "name_field"),
    [
        ("reviewers", Reviewer, "email", "name"),
        ("reviewees", Reviewee, "email_or_identifier", "name"),
        ("observers", Observer, "email", "display_name"),
    ],
)
def test_the_single_add_binds_and_an_address_edit_rebinds_or_clears(
    client: TestClient, db: Session, directory: FakeDirectory, roster: str, model, field: str, name_field: str
) -> None:
    session = _session(client, db, f"dir-edit-{roster}")
    base = f"/operator/sessions/{session.public_id}/{roster}"
    created = client.post(
        f"{base}/create",
        data={**ROSTER_FORM, field: "e0123456@example.edu", name_field: "Jane"},
        follow_redirects=False,
    )
    assert created.status_code == 303
    row = _row(db, model, session.id)
    assert _bound(row) == JANE

    def edit(address: str) -> None:
        response = client.post(
            f"{base}/{row.id}/update",
            data={**ROSTER_FORM, field: address, name_field: "Jane"},
            follow_redirects=False,
        )
        assert response.status_code == 303, response.text[:500]
        db.refresh(row)

    # The same address in another case keeps the binding.
    edit("E0123456@example.edu")
    assert _bound(row) == JANE
    # Alice to Bob: an address that doesn't resolve clears it, never keeps it.
    edit("nobody@example.edu")
    assert _bound(row) == directory_accounts.UNBOUND
    # And one that resolves binds afresh.
    edit("jane.tan@example.edu")
    assert _bound(row) == JANE


def test_without_a_token_nothing_binds_and_an_edit_clears(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_shared, "directory_or_none", lambda request: None)
    session = _session(client, db, "dir-none")
    base = f"/operator/sessions/{session.public_id}/reviewers"
    client.post(f"{base}/create", data={**ROSTER_FORM, "email": "e0123456@example.edu", "name": "Jane"})
    row = _row(db, Reviewer, session.id)
    assert _bound(row) == directory_accounts.UNBOUND
    # A bound row edited with no directory to ask loses its binding.
    for name, value in JANE.items():
        setattr(row, name, value)
    db.commit()
    client.post(f"{base}/{row.id}/update", data={**ROSTER_FORM, "email": "jane.tan@example.edu", "name": "Jane"})
    db.refresh(row)
    assert _bound(row) == directory_accounts.UNBOUND


def test_mail_for_a_row_given_by_upn_goes_to_the_directory_mail() -> None:
    by_upn = Reviewer(name="Jane", email="e0123456@example.edu", **JANE)
    unbound = Reviewer(name="Ext", email="guest@other.example")
    no_mail = Reviewer(
        name="Lab", email="lab01@example.edu", directory_object_id="x", directory_mail=None, directory_upn="lab01@example.edu"
    )
    assert directory_accounts.recipient(by_upn) == "jane.tan@example.edu"
    assert directory_accounts.recipient(unbound) == "guest@other.example"
    assert directory_accounts.recipient(no_mail) == "lab01@example.edu"


# --- rung 4b: the counts on the Setup page ---


def test_the_setup_page_shows_the_last_imports_directory_check(
    client: TestClient, db: Session, directory: FakeDirectory
) -> None:
    session = _session(client, db, "dir-page")
    page = client.get(f"/operator/sessions/{session.public_id}/reviewers?unlocked=1")
    assert "data-directory-check" not in page.text  # no import yet
    csv = (
        "ReviewerName,ReviewerEmail\n"
        "Jane,e0123456@example.edu\nOffice,office@example.edu\nNobody,nobody@example.edu\n"
    ).encode()
    client.post(
        f"/operator/sessions/{session.public_id}/reviewers/import",
        files={"file": ("r.csv", csv, "text/csv")},
        follow_redirects=False,
    )
    text = client.get(f"/operator/sessions/{session.public_id}/reviewers?unlocked=1").text
    line = text[text.index("data-directory-check") :].split("</p>")[0]
    assert "0 matched by mail" in line and "1 by sign-in name" in line
    assert "1 not found" in line and "1 ambiguous" in line
    assert "not checked" not in line


def test_an_unchecked_import_says_so(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(_setup_observers, "directory_or_none", lambda request: None)
    session = _session(client, db, "dir-page-none")
    client.post(
        f"/operator/sessions/{session.public_id}/observers/import",
        files={"file": ("o.csv", b"ObserverName,ObserverEmail\nJane,e0123456@example.edu\n", "text/csv")},
        follow_redirects=False,
    )
    text = client.get(f"/operator/sessions/{session.public_id}/observers?unlocked=1").text
    assert "checked against the directory" in text and "Importing the file again" in text
    assert "no directory access" not in text  # the counts can't tell why (Codex, #3429)


def test_an_import_with_no_address_to_check_shows_nothing(
    client: TestClient, db: Session, directory: FakeDirectory
) -> None:
    session = _session(client, db, "dir-page-anon")
    client.post(
        f"/operator/sessions/{session.public_id}/reviewees/import",
        files={"file": ("e.csv", b"RevieweeName,RevieweeEmail\nAnon,STU-0001\n", "text/csv")},
        follow_redirects=False,
    )
    text = client.get(f"/operator/sessions/{session.public_id}/reviewees?unlocked=1").text
    assert "data-directory-check" not in text


def test_several_rosters_share_one_lookup_and_are_counted_apart(
    directory: FakeDirectory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Quick Setup and rehydrate save several rosters in one request: one
    lookup under one budget, so the request stays inside the front end's
    limit (Codex, #3430), and each roster counts its own addresses."""
    from app.services import csv_imports

    calls: list[list[str]] = []
    real = directory_accounts.look_up_all
    monkeypatch.setattr(
        directory_accounts, "look_up_all", lambda d, keys, **kw: calls.append(keys) or real(d, keys, **kw)
    )
    reviewers, reviewees = csv_imports.directory_checks(
        directory, [["e0123456@example.edu"], ["jane.tan@example.edu", "nobody@example.edu"]]
    )
    assert len(calls) == 1
    assert reviewers.counts["directory_by_upn"] == 1 and reviewers.counts["directory_not_found"] == 0
    assert reviewees.counts["directory_by_mail"] == 1 and reviewees.counts["directory_not_found"] == 1
