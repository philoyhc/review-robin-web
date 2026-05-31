"""Integration coverage for the placeholder Setup-Observers page
(Phase 2 placeholder P1 in
``guide/participant_model_prep.md``).

The page renders behind the per-session ``observers_enabled``
toggle; this test file pins the route gate (404 off / 200 on),
the four placeholder cards, the empty-state on the observers
list when no rows exist, the populated-state when rows are
seeded, and the nav tab visibility flip.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Observer, ReviewSession


def _make_session(
    client: TestClient, db: Session, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Obs", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _enable_observers(
    db: Session, review_session: ReviewSession
) -> None:
    review_session.observers_enabled = True
    db.commit()
    db.refresh(review_session)


# ── Route gate ────────────────────────────────────────────────────────


def test_observers_route_404_when_flag_off(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "obs-off")
    response = client.get(
        f"/operator/sessions/{review_session.id}/observers"
    )
    assert response.status_code == 404


def test_observers_route_200_when_flag_on(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "obs-on")
    _enable_observers(db, review_session)
    response = client.get(
        f"/operator/sessions/{review_session.id}/observers"
    )
    assert response.status_code == 200


# ── Nav tab visibility ───────────────────────────────────────────────


def test_observers_nav_tab_hidden_when_flag_off(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "obs-nav-off")
    body = client.get(
        f"/operator/sessions/{review_session.id}"
    ).text
    assert (
        f'href="/operator/sessions/{review_session.id}/observers"'
        not in body
    )


def test_observers_nav_tab_visible_when_flag_on(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "obs-nav-on")
    _enable_observers(db, review_session)
    body = client.get(
        f"/operator/sessions/{review_session.id}"
    ).text
    assert (
        f'href="/operator/sessions/{review_session.id}/observers"'
        in body
    )


# ── Placeholder cards ────────────────────────────────────────────────


def test_observers_page_renders_four_placeholder_cards(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "obs-cards")
    _enable_observers(db, review_session)
    body = client.get(
        f"/operator/sessions/{review_session.id}/observers"
    ).text
    # Four card anchor ids established by the template.
    assert 'id="observers-list"' in body
    assert 'id="observers-upload"' in body
    assert 'id="observers-actions"' in body
    assert 'id="observers-danger"' in body
    # Card headings.
    assert ">Observers<" in body
    assert "Upload observers" in body
    assert "Operator actions" in body
    assert "Danger Zone" in body


def test_observers_page_renders_inert_controls(
    client: TestClient, db: Session
) -> None:
    """Every interactive control is ``disabled`` on the placeholder
    page — clicking does nothing until the Observer roster slice
    wires the routes. Button styles + labels mirror the Reviewers
    page (``btn secondary`` for Upload + bulk actions,
    ``btn destructive`` for the Danger Zone delete)."""
    review_session = _make_session(client, db, "obs-inert")
    _enable_observers(db, review_session)
    body = client.get(
        f"/operator/sessions/{review_session.id}/observers"
    ).text
    assert 'type="file" accept=".csv,text/csv" aria-label="CSV file" disabled' in body
    # Each interactive button is btn-secondary (Upload + bulk
    # actions) or btn-destructive (Danger Zone), and disabled.
    assert "disabled aria-disabled=\"true\">Upload</button>" in body
    assert "disabled aria-disabled=\"true\">Edit</button>" in body
    assert "disabled aria-disabled=\"true\">Inactivate</button>" in body
    assert "disabled aria-disabled=\"true\">Activate</button>" in body
    assert (
        'class="btn destructive"' in body
        and "disabled aria-disabled=\"true\">Delete all observers</button>" in body
    )


# ── List card states ─────────────────────────────────────────────────


def test_observers_list_renders_mock_row_when_empty(
    client: TestClient, db: Session
) -> None:
    """When no observers exist, the list card still renders the
    four-column table with a mock placeholder row so operators
    can preview the eventual shape."""
    review_session = _make_session(client, db, "obs-empty")
    _enable_observers(db, review_session)
    body = client.get(
        f"/operator/sessions/{review_session.id}/observers"
    ).text
    # The four column headers — Name / Email / Tag1 / Status.
    assert "<th>Name</th>" in body
    assert "<th>Email</th>" in body
    assert "<th>Tag1</th>" in body
    assert "<th>Status</th>" in body
    # Mock row content.
    assert "Jane Doe" in body
    assert "jane.doe@example.org" in body
    assert ">committee<" in body
    assert ">active<" in body


def test_observers_list_renders_seeded_rows(
    client: TestClient, db: Session
) -> None:
    """The page reads from the ``observers`` table directly so a
    row seeded outside the (not-yet-wired) upload flow still
    shows in place of the mock row."""
    review_session = _make_session(client, db, "obs-seeded")
    _enable_observers(db, review_session)
    db.add_all(
        [
            Observer(
                session_id=review_session.id,
                email="zoe@example.org",
                display_name="Zoe",
                tag_1="committee",
            ),
            Observer(
                session_id=review_session.id,
                email="alex@example.org",
                display_name="Alex",
            ),
        ]
    )
    db.commit()
    body = client.get(
        f"/operator/sessions/{review_session.id}/observers"
    ).text
    assert "zoe@example.org" in body
    assert "alex@example.org" in body
    # Display name + tag values render.
    assert ">Zoe<" in body
    assert ">committee<" in body
    # Empty-tag row shows "—" placeholder for the tag column.
    assert ">—<" in body
    # Mock row gone now that real rows exist.
    assert "Jane Doe" not in body


# ── Chrome ───────────────────────────────────────────────────────────


def test_observers_page_marks_observers_nav_tab_active(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "obs-active")
    _enable_observers(db, review_session)
    body = client.get(
        f"/operator/sessions/{review_session.id}/observers"
    ).text
    assert 'class="nav-tab active"' in body
    # The active tab should be Observers — sanity-check the URL
    # appears alongside the active class.
    assert (
        f'class="nav-tab active"\n       href="/operator/sessions/{review_session.id}/observers"'
        in body
    )
