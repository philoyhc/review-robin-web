"""19S Item 9 Part A — the Owners card on Create.

The card renders below the Tags card, the third card in the Create
page's right-hand ``.bottom-left`` column, with **the same UX as Session
Home's Owners card** (author's ruling, 2026-09-23): the owners table,
then a one-at-a-time Add-owner picker suggesting workspace operators.
The creator is the first owner, listed without a Remove action, and is
not offered as a candidate.

**Create session saves everything** (author's ruling, 2026-09-23). The
``_owners_stager_js`` partial turns Add owner and Remove into staging:
each row carries a hidden ``owners`` input bound to the create form, and
without JavaScript the email box submits the one address typed into it.
Rung 3's inertness assertions are inverted here rather than deleted, so
the diff shows the control going live. The route validates the whole
list **before** creating the session — one address that is not a
workspace operator refuses the create with nothing written — then
applies it through ``session_owners.set_owners``, with the creator always
kept. The script itself is exercised in Chromium, not here: pytest has
no JavaScript runtime (``docs/unenforced_conventions.md`` §1.12's reason,
one level over).
"""

from __future__ import annotations

import csv
import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession, User
from app.services import session_owners


#: The signed-in operator the integration client authenticates as
#: (``tests/integration/conftest.py``) — the session's creator.
CREATOR = "alice@example.edu"


def _card(body: str) -> str:
    """The Owners card's own markup — opening tag to its closing one.

    A ``<div>`` depth scan, as the Tags card's tests settled on: the
    Owners card is the page's last, which is exactly the case where
    bounding at the next sibling card silently returns the document's
    tail. ``test_the_card_helper_is_bounded`` guards it.
    """
    anchor = body.find('id="session-owners"')
    assert anchor != -1, "the Owners card is missing from the Create page"
    start = body.rfind("<div", 0, anchor)
    depth = 0
    i = start
    while True:
        opened = body.find("<div", i)
        closed = body.find("</div>", i)
        assert closed != -1, "the Owners card's <div> is never closed"
        if opened != -1 and opened < closed:
            depth += 1
            i = opened + len("<div")
            continue
        depth -= 1
        i = closed + len("</div>")
        if depth == 0:
            return body[start:i]


def test_the_card_helper_is_bounded(client: TestClient) -> None:
    body = client.get("/operator/sessions/new").text
    card = _card(body)

    assert card.startswith('<div class="card" id="session-owners"')
    assert card.count("<div") == card.count("</div>")
    tail = body[body.index(card) + len(card):]
    assert "getElementById" in tail, "the page's scripts follow the card"
    assert "getElementById" not in card


def test_the_card_sits_below_tags_in_the_same_column(client: TestClient) -> None:
    body = client.get("/operator/sessions/new").text

    ui = body.find('id="user-interface-settings"')
    tags = body.find('id="session-tags"')
    owners = body.find('id="session-owners"')
    assert -1 not in (ui, tags, owners)
    assert ui < tags < owners

    # One .bottom-left column holds all three, so its gap spaces them.
    column = body.rfind('<div class="bottom-left">', 0, ui)
    assert column != -1
    assert body.rfind('<div class="bottom-left">', 0, owners) == column


def _operator(db: Session, email: str, *, is_operator: bool = True) -> User:
    user = User(email=email, is_operator=is_operator)
    db.add(user)
    db.commit()
    return user


def test_the_card_mirrors_session_home(client: TestClient, db: Session) -> None:
    """Session Home's shape: heading, subtitle, the owners table with the
    same columns, the picker's own label, and Add owner. Like Session
    Home, the picker renders only when there is someone to add."""
    _operator(db, "colleague@example.edu")
    card = _card(client.get("/operator/sessions/new").text)

    assert "Owners (optional)</h3>" in card
    assert '<p class="muted">' in card
    for column in ("Email", "Name", "Role", "Added", "Action"):
        assert f">{column}</th>" in card, column
    assert "Pick or search for a workspace operator:" in card
    assert ">Add owner</button>" in card


def test_the_copy_says_create_session_saves_the_owners(
    client: TestClient, db: Session
) -> None:
    """Unlike Session Home, where Add owner writes at once, nothing here
    persists until Create session — so the card says so, and Add owner is
    an outline button rather than a second Primary beside Create session
    (author's ruling, 2026-09-23)."""
    _operator(db, "colleague@example.edu")
    card = _card(client.get("/operator/sessions/new").text)

    assert "saved when you create the" in card
    assert 'class="btn secondary" type="button"' in card


def test_the_creator_is_the_first_owner_and_cannot_be_removed(
    client: TestClient, db: Session
) -> None:
    body = client.get("/operator/sessions/new").text
    card = _card(body)
    assert f"<code>{CREATOR}</code>" in card
    assert "<td>owner</td>" in card
    assert "Remove" not in card, "a session always keeps one owner"


def test_the_picker_suggests_other_workspace_operators(
    client: TestClient, db: Session
) -> None:
    """Everyone ``add_owner`` would accept, minus the creator — who owns
    the session the moment it exists. A non-operator is never offered."""
    _operator(db, "colleague@example.edu")
    _operator(db, "outsider@example.edu", is_operator=False)
    card = _card(client.get("/operator/sessions/new").text)

    datalist = card[card.index("<datalist"):card.index("</datalist>")]
    assert 'value="colleague@example.edu"' in datalist
    assert "outsider@example.edu" not in datalist
    assert f'value="{CREATOR}"' not in datalist
    assert 'list="session-owners-candidates"' in card


def test_with_no_one_to_add_the_picker_says_so(client: TestClient) -> None:
    card = _card(client.get("/operator/sessions/new").text)

    assert "No other workspace operators are available to add." in card
    assert "<datalist" not in card


def test_the_picker_is_wired_to_the_create_form(
    client: TestClient, db: Session
) -> None:
    """Rung 3's inertness assertion, inverted: the box has a ``name`` and
    a ``form=``, the card declares the stager's wiring, and the creator's
    row carries its hidden ``owners`` input like every staged row will."""
    _operator(db, "colleague@example.edu")
    body = client.get("/operator/sessions/new").text
    card = _card(body)

    # The email box itself, not the creator row's hidden input, which
    # carries the same name — asserting ``name="owners"`` anywhere in the
    # card passed with the box's name removed.
    box = card[card.index('id="session-owners-email"'):]
    box = box[:box.index(">")]
    assert 'name="owners"' in box
    assert 'form="create-session-form"' in box
    assert "data-owners-stager" in card
    assert 'data-owners-form="create-session-form"' in card
    assert f'value="{CREATOR}"' in card, "the creator's row submits too"
    assert 'type="button"' in card and 'type="submit"' not in card, (
        "Add owner stages; only Create session submits"
    )
    assert "data-owners-stager" in body[body.index(card) + len(card):], (
        "the stager script ships with the page"
    )


def _create(client: TestClient, code: str, **extra):
    data = {"name": "Owned", "code": code, "description": "", **extra}
    files = data.pop("files", None)
    return client.post(
        "/operator/sessions", data=data, files=files, follow_redirects=False
    )


def _owners_of(db: Session, code: str) -> list[str]:
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    return sorted(row.email for row in session_owners.list_owners(db, review_session))


def test_a_staged_co_owner_owns_the_created_session(
    client: TestClient, db: Session
) -> None:
    _operator(db, "colleague@example.edu")
    response = _create(client, "OWNERS-ADD", owners=["", "colleague@example.edu"])
    assert response.status_code == 303, response.text
    assert _owners_of(db, "OWNERS-ADD") == sorted(
        [CREATOR, "colleague@example.edu"]
    )


def test_duplicates_and_the_creator_collapse(client: TestClient, db: Session) -> None:
    """The creator's own hidden row, a case variant and a repeat all fold
    into one set; the creator is kept however the list arrives."""
    _operator(db, "colleague@example.edu")
    creator = CREATOR
    response = _create(
        client,
        "OWNERS-DEDUPE",
        owners=[creator, "Colleague@Example.edu", "colleague@example.edu"],
    )
    assert response.status_code == 303, response.text
    assert _owners_of(db, "OWNERS-DEDUPE") == sorted(
        [creator, "colleague@example.edu"]
    )


def test_no_staged_owner_leaves_the_creator_alone(
    client: TestClient, db: Session
) -> None:
    creator = CREATOR
    response = _create(client, "OWNERS-NONE", owners=[creator, ""])
    assert response.status_code == 303, response.text
    assert _owners_of(db, "OWNERS-NONE") == [creator]
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "OWNERS-NONE")
    ).scalar_one()
    added = db.execute(
        select(AuditEvent).where(
            AuditEvent.session_id == review_session.id,
            AuditEvent.event_type == "session.owner_added",
        )
    ).scalars().all()
    assert added == []


@pytest.mark.parametrize("known", [True, False], ids=["non-operator", "unknown"])
def test_an_address_add_owner_would_refuse_refuses_the_create(
    client: TestClient, db: Session, known: bool
) -> None:
    """Validated before the session exists, so nothing is written — no
    half-created session carrying some of the owners."""
    _operator(db, "colleague@example.edu")
    if known:
        _operator(db, "outsider@example.edu", is_operator=False)
    response = _create(
        client,
        "OWNERS-REFUSED",
        owners=["colleague@example.edu", "outsider@example.edu"],
    )
    assert response.status_code == 422, response.text
    assert "outsider@example.edu" in response.text
    assert db.execute(
        select(ReviewSession).where(ReviewSession.code == "OWNERS-REFUSED")
    ).scalar_one_or_none() is None


def test_a_failed_upload_keeps_the_staged_owners(
    client: TestClient, db: Session
) -> None:
    """As the Tags box keeps what was typed: the operator sent back to fix
    a CSV does not also lose who they staged."""
    _operator(db, "colleague@example.edu")
    response = _create(
        client,
        "OWNERS-UPLOAD-FAIL",
        owners=["colleague@example.edu"],
        files={"reviewers_file": ("r.csv", b"NotAHeader\ngarbage\n", "text/csv")},
    )
    assert response.status_code == 303, response.text
    assert "quick_setup_error=reviewers" in response.headers["location"], (
        "the upload really failed"
    )
    assert "colleague@example.edu" in _owners_of(db, "OWNERS-UPLOAD-FAIL")


def test_one_create_is_one_correlation_id(client: TestClient, db: Session) -> None:
    """Every audit event one create produces — the session, a Quick Setup
    upload, the settings bundle, tags, owners — shares one id.
    ``request_correlation_id`` mints a fresh id per call, and the route
    used to call it once per step."""
    _operator(db, "colleague@example.edu")
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(("field", "value", "data_type"))
    writer.writerow(("session.help_contact", "help@example.edu", "string"))
    response = _create(
        client,
        "OWNERS-CORR",
        owners=["colleague@example.edu"],
        tags="pilot",
        files={
            "reviewers_file": (
                "r.csv", b"ReviewerName,ReviewerEmail\nR,r@example.edu\n", "text/csv"
            ),
            "settings_file": ("s.csv", buf.getvalue().encode(), "text/csv"),
        },
    )
    assert response.status_code == 303, response.text
    assert "quick_setup_error" not in response.headers["location"]
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "OWNERS-CORR")
    ).scalar_one()
    events = db.execute(
        select(AuditEvent).where(AuditEvent.session_id == review_session.id)
    ).scalars().all()
    kinds = {e.event_type for e in events}
    for kind in ("session.created", "session.tag_added", "session.owner_added"):
        assert kind in kinds, (kind, sorted(kinds))
    assert len(kinds) >= 5, sorted(kinds)
    assert len({e.correlation_id for e in events}) == 1, sorted(
        (e.event_type, e.correlation_id) for e in events
    )
