"""Segment 19S Item 6 — the Tags card on ``/operator/sessions/new``.

Rung 1 landed the card inert; **rung 2 made it live**, and the three
assertions that pinned inertness are inverted here by design rather
than deleted, so the change is visible in the diff.

The mechanism under test is **ordering, not precedence logic**. All 13
Create-form fields overlap the settings CSV, and
``_apply_session_metadata`` already resolves each by one of two rules —
*fill-blanks* for operator-typed identity, *force-apply* for session
config. A typed tag is operator-typed, so the form wins; it wins by the
route calling ``set_tags`` **after** the staged Quick Setup uploads, of
which the settings CSV is the last. Nothing in
``_apply_session_tags`` changes: that applier is wipe-and-replace and
is shared with ``POST /sessions/{id}/import-config`` on an *existing*
session, where the wipe is the round-trip behaviour 18P PR D2 pinned.

**The empty-box case is the control.** It asserts the CSV's tags land
when nothing opposes them, which is what stops
``test_a_typed_tag_beats_a_settings_csv_carrying_other_tags`` passing
vacuously: on its own, that test is satisfied by a bundle that applied
nothing at all. Degenerating ``_settings_csv`` to an empty bundle is
caught here and only here.

Both CSV shapes are covered because they fail differently. A bundle
carrying **no** ``session_tags[]`` rows is indistinguishable from one
asking for none, so the applier wipes — that is the case a write
ordered *before* it would lose silently. A bundle carrying **other**
tags is the case the ordering decides.
"""

from __future__ import annotations

import asyncio
import csv
import io

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import Session as SASession

from app.db.models import AuditEvent, ReviewSession, User
from app.services import session_tags
from app.web.routes_operator import _quick_setup


def _card(body: str) -> str:
    """The Tags card's own markup — its anchor to its closing tag.

    Bounded at the **next** ``<div class="card"``, or at the end of the
    page when it is the last one. A first draft returned ``body[start:]``
    — the whole tail of the document — so every ``in card`` assertion was
    really an assertion about the rest of the page. Nothing passed
    vacuously at the time, but the mutation set had degenerated this
    helper to ``""`` (the narrowing) and never to ``body`` (the widening
    it actually had), which is `docs/unenforced_conventions.md` §1.11's
    own subject. ``test_the_card_helper_is_bounded`` is the guard.
    """
    start = body.find('id="session-tags"')
    assert start != -1, "the Tags card is missing from the page"
    start = body.rfind('<div class="card"', 0, start)
    end = body.find('<div class="card"', start + 1)
    return body[start:] if end == -1 else body[start:end]


def _settings_csv(rows: list[tuple[str, str, str]]) -> bytes:
    """A settings bundle in the exporter's own shape.

    The field names and ``data_type`` values below are read off
    ``session_config_io/_serialize.py`` rather than guessed — a first
    draft used ``str`` for the type and a bare ``help_contact`` for the
    field, and the bundle applied nothing at all while the test read as
    though the ordering had failed.
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(("field", "value", "data_type"))
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


def _create(
    client: TestClient,
    *,
    code: str,
    tags: str | None = None,
    settings: bytes | None = None,
) -> None:
    data: dict[str, str] = {"name": "Tagged", "code": code, "description": ""}
    if tags is not None:
        data["tags"] = tags
    files = (
        {"settings_file": ("settings.csv", settings, "text/csv")}
        if settings is not None
        else None
    )
    # The status assertion below is a **diagnostic, not a guard**:
    # removing it fails nothing, because a non-303 create leaves no
    # session and every caller's tag assertion fails anyway. It is kept
    # so that failure reads as "the create was rejected" rather than as
    # "the tags are empty", which is the wrong thing to go looking at.
    response = client.post(
        "/operator/sessions", data=data, files=files, follow_redirects=False
    )
    assert response.status_code == 303, response.text


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    """A committed session to run the settings helper against."""
    _create(client, code=code)
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _tags_of(db: Session, code: str) -> list[str]:
    row = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    return session_tags.tags_for_sessions(db, [row.id])[row.id]


def test_the_tags_card_renders_below_user_interface_settings(
    client: TestClient,
) -> None:
    """The card sits in the bottom row's right column, under the
    UI-settings card, per the plan's `Decision`."""
    body = client.get("/operator/sessions/new").text

    ui_pos = body.find('id="user-interface-settings"')
    tags_pos = body.find('id="session-tags"')
    assert -1 not in (ui_pos, tags_pos)
    assert ui_pos < tags_pos, "Tags sits below User interface settings"

    card = _card(body)
    assert "Tags (optional)</h3>" in card, (
        "the heading carries the (optional) qualifier — it is the "
        "field's visible label, not a section title above a second one"
    )
    assert "Comma-separated" in card, "the copy says how to type two"
    # The heading being the label is load-bearing for accessibility:
    # there is no <label> element, so the input's accessible name comes
    # from it. If the id or the reference is dropped, the box becomes an
    # unlabelled text input rather than merely an untidy one.
    assert 'id="session-tags-heading"' in card
    assert 'aria-labelledby="session-tags-heading"' in card


def test_the_card_helper_is_bounded(client: TestClient) -> None:
    """``_card`` returns the Tags card, not the rest of the page.

    The guard the helper's own docstring names. Every other render test
    reads ``assert X in _card(body)``, so a helper that over-returns
    makes all of them weaker without failing any — the widening mutation
    is invisible unless something asserts the boundary itself.
    """
    body = client.get("/operator/sessions/new").text
    card = _card(body)

    assert 'id="session-tags"' in card
    assert card.count('<div class="card"') == 1, (
        "the slice stops at the next card, so it holds exactly one"
    )
    # The card is the last on the page today, so an unbounded helper
    # returns nearly the same string. Anchor on something that is
    # definitely outside it and definitely on the page.
    assert 'id="user-interface-settings"' not in card
    assert "_schedule_ordering_js" not in card
    assert len(card) < len(body) / 4, (
        "one card, not the tail of the document"
    )


def test_the_two_stacked_cards_use_the_documented_column_primitive(
    client: TestClient,
) -> None:
    """The right-hand `.bottom-grid` cell is a `.bottom-left` column.

    Cards inside `.bottom-grid` carry no ``margin-bottom``
    (`spec/ui_elements.md` §4), so a plain ``<div>`` cell renders two
    stacked cards flush — which is what the dev slot showed. The fix
    that spacing belongs to is `.bottom-left`'s ``gap``, §10's named
    primitive for exactly this, not a new app-wide card rule: a rule
    keyed on adjacent cards also matches the cards *inside* a
    `.bottom-left`, so it would double the gap the first time a second
    card returns to one of Session Home's columns.
    """
    body = client.get("/operator/sessions/new").text

    grid = body.find('class="bottom-grid"')
    assert grid != -1
    cell = body.rfind('<div class="bottom-left">', grid, body.find('id="session-tags"'))
    assert cell != -1, (
        "the cell holding both cards is a .bottom-left flex column"
    )
    ui_pos = body.find('id="user-interface-settings"')
    assert cell < ui_pos, "the column wraps both cards, not just Tags"


def test_the_tags_input_is_wired_to_the_create_form(
    client: TestClient,
) -> None:
    """The inversion of rung 1's inertness assertion, kept in that
    shape so the diff shows the control going live.

    Both halves are needed and rung 1 asserted the absence of both: a
    ``name`` is what a browser submits, and ``form=`` is what associates
    a control rendered outside ``<form>`` with it.
    """
    card = _card(client.get("/operator/sessions/new").text)
    assert 'name="tags"' in card, "a named input is what gets submitted"
    assert 'form="create-session-form"' in card, (
        "the card renders outside the <form>, so the association is "
        "explicit or the value never arrives"
    )


def test_a_typed_tag_is_written_on_create(
    client: TestClient, db: Session
) -> None:
    """The round trip, asserted through the route rather than the
    service, per the plan's Definition of done."""
    _create(client, code="tags-basic", tags="pilot, 2026")
    assert _tags_of(db, "tags-basic") == ["2026", "pilot"]


def test_a_typed_tag_beats_a_settings_csv_carrying_other_tags(
    client: TestClient, db: Session
) -> None:
    """The case the ordering decides: both sides name tags, and the
    box's win is whole-field rather than merged — the same shape
    *fill-blanks* gives the other five operator-typed fields."""
    csv_bytes = _settings_csv(
        [
            ("session_tags[1].tag", "from-csv", "string"),
            ("session_tags[2].tag", "also-csv", "string"),
        ]
    )
    _create(client, code="tags-vs-csv", tags="typed", settings=csv_bytes)
    assert _tags_of(db, "tags-vs-csv") == ["typed"], (
        "the CSV's tags are replaced wholesale, not merged with the "
        "typed one"
    )


def test_a_typed_tag_survives_a_settings_csv_with_no_tag_rows(
    client: TestClient, db: Session
) -> None:
    """The case a write ordered *before* the CSV would lose silently.

    ``_apply_session_tags`` has no section-presence flag, so a bundle
    carrying no ``session_tags[]`` rows is indistinguishable from one
    asking for none and clears the session's tags. Ordering the write
    after it is what makes Create immune; the same hazard on
    ``POST /sessions/{id}/import-config`` is out of scope and recorded
    in the plan.
    """
    csv_bytes = _settings_csv([("session.help_contact", "x@example.edu", "string")])
    _create(client, code="tags-vs-empty", tags="typed", settings=csv_bytes)
    assert _tags_of(db, "tags-vs-empty") == ["typed"]


def test_an_empty_box_leaves_a_settings_csv_s_tags_alone(
    client: TestClient, db: Session
) -> None:
    """The other half of the rule. An empty box must write *nothing*,
    not an empty tag set: ``set_tags`` is a replace, so calling it
    unconditionally would drop what the CSV had just applied."""
    csv_bytes = _settings_csv([("session_tags[1].tag", "from-csv", "string")])
    _create(client, code="tags-empty-box", tags="", settings=csv_bytes)
    assert _tags_of(db, "tags-empty-box") == ["from-csv"]

    # ...and the same with the field absent entirely, which is what a
    # browser sends if the input is ever unwired again.
    _create(client, code="tags-absent", settings=csv_bytes)
    assert _tags_of(db, "tags-absent") == ["from-csv"]


def test_an_empty_box_emits_no_tag_added_event(
    client: TestClient, db: Session
) -> None:
    """A create with no typed tag is silent in the audit log, which is
    the observable difference between *writing nothing* and *writing an
    empty set*."""
    _create(client, code="tags-silent", tags="   ")
    row = db.execute(
        select(ReviewSession).where(ReviewSession.code == "tags-silent")
    ).scalar_one()
    events = db.execute(
        select(AuditEvent.event_type).where(
            AuditEvent.session_id == row.id,
            AuditEvent.event_type.in_(
                ("session.tag_added", "session.tag_removed")
            ),
        )
    ).scalars().all()
    assert events == [], (
        "a blank box wrote nothing, so there is no tag event — a "
        "whitespace-only value is blank too"
    )


def test_a_typed_tag_survives_a_failed_quick_setup_upload(
    client: TestClient, db: Session
) -> None:
    """Not in the plan, and decided while building: the write also runs
    on the Quick-Setup error path.

    Ordering it after the settings block left the typed tag discarded
    whenever an earlier slot failed and the handler returned early —
    the operator is sent back to fix a CSV and the thing they typed on
    this page is gone. Writing it before the error redirect is safe in
    the same sense the success path is: a block that failed wrote no
    tags, and a block that never ran cannot have.
    """
    response = client.post(
        "/operator/sessions",
        data={"name": "Tagged", "code": "tags-bad-csv", "tags": "typed"},
        files={
            "reviewers_file": (
                "reviewers.csv",
                b"NotAHeader\nnonsense\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "quick_setup_error=reviewers" in response.headers["location"], (
        "the upload failed, which is the precondition of this test"
    )
    assert _tags_of(db, "tags-bad-csv") == ["typed"]


def test_the_settings_slot_commits_its_own_work(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``_run_quick_setup_settings`` commits, whatever the Tags box.

    Found by a review of this rung and **not caused by it**:
    ``apply_session_config`` flushes but never commits, and ``get_db``
    closes without committing, so all three of this helper's callers
    returned a success redirect over work that was then rolled back.
    Verified on ``main`` against a file-backed SQLite read through a
    second session — the session row persists and **neither** the CSV's
    ``help_contact`` nor its tags do.

    What this rung did was make it *conditional*: a typed tag reached
    ``set_tags``, whose own commit saved the settings import as a side
    effect, so the loss only showed when the box was blank. Worse than
    uniformly broken, which is why the fix rides here rather than
    waiting for an item of its own.

    **Asserted on the helper rather than through the route**, after
    three route-level attempts measured nothing — each recorded because
    the next person will reach for them in the same order:

    * reading rows back proves nothing. The integration ``db`` fixture
      shares a transaction with the app, so a flushed row reads exactly
      like a committed one. That blind spot is why the suite was green
      while production dropped the import.
    * counting ``after_commit`` **events** proves nothing. That fixture
      joins an external transaction, so a commit releasing a savepoint
      emits none, and a draft asserting on them passed with the fix
      removed.
    * counting commits across a whole create does not isolate this
      path: a create *with* a CSV takes one fewer baseline commit than
      one without, so the difference cancels and the comparison reads
      2 against 2 either way.

    Calling the helper directly removes all three confounds. The spy is
    on ``Session.commit`` as a **class** attribute, because the route
    resolves its own session through ``get_db`` — an instance patch on
    the ``db`` fixture counts nothing the app does.
    """
    review_session = _make_session(client, db, code="settings-commit")
    calls: list[str] = []
    real_commit = SASession.commit

    def _spy(self: SASession, *args: object, **kwargs: object) -> None:
        calls.append("c")
        return real_commit(self, *args, **kwargs)

    monkeypatch.setattr(SASession, "commit", _spy)
    reason = asyncio.run(
        _quick_setup._run_quick_setup_settings(
            file=UploadFile(
                filename="s.csv",
                file=io.BytesIO(
                    _settings_csv(
                        [("session.help_contact", "x@example.edu", "string")]
                    )
                ),
            ),
            review_session=review_session,
            user=db.get(User, review_session.created_by_user_id),
            db=db,
        )
    )

    assert reason is None, f"the bundle was rejected: {reason}"
    assert calls, (
        "the settings import never committed — apply_session_config "
        "only flushes and get_db closes without committing, so the "
        "work is rolled back behind a success redirect"
    )
