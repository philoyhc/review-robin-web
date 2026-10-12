"""A reviewee sees their own roster entry — participant info Item 4.

`guide/participant_info.md` Item 4, rung 2 (the scaffold): the
Reviewees page's inert "What reviewees see of their own entry" card,
its `Reviewees see:` readout, and the reviewee's own line after the role
pills on `/results`, all at the default selection (name, email or
identifier, profile; tags off).
"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Reviewee, Reviewer, ReviewSession

from ._unlock_panel import panel_columns

LINK = "https://example.edu/alice"


def _session(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Cohort A", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _alice(db: Session, rs: ReviewSession, *, profile: str | None = LINK) -> None:
    """`client` signs in as alice@example.edu (tests/conftest.py)."""
    db.add(
        Reviewee(
            session_id=rs.id, name="Alice Reviewee",
            email_or_identifier="alice@example.edu",
            profile_link=profile, tag_1="Blue",
        )
    )
    db.commit()


def _div_at(html: str, marker: str) -> str:
    start = html.rindex("<div", 0, html.index(marker))
    depth = 0
    for m in re.finditer(r"<(/?)div\b", html[start:]):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return html[start:start + m.end() + 1]
    raise AssertionError(f"{marker} never closes")


def _info(html: str) -> str:
    m = re.search(
        r'<span class="rs-self-info" data-reviewee-self-info>(.*?)</span>\s*</div>',
        html, re.S,
    )
    assert m, "no reviewee info on the role row"
    return m.group(1)


def test_the_readout_reports_the_default(client: TestClient, db: Session) -> None:
    rs = _session(client, db, "rei-readout")
    _alice(db, rs)
    html = client.get(f"/operator/sessions/{rs.id}/reviewees").text
    shown = _div_at(html, "data-reviewee-self-readout")
    assert "Reviewees see:" in shown
    assert re.findall(r'<span class="pill pill-count">([^<]*)</span>', shown) == [
        "Name", "Email", "Profile",
    ]


def test_the_card_sits_above_upload_with_a_chip_per_populated_column(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "rei-card")
    _alice(db, rs)
    html = client.get(f"/operator/sessions/{rs.id}/reviewees?unlocked=1").text
    _, left, _ = panel_columns(html)
    assert left.index("data-reviewee-self-card") < left.index('id="upload-csv"')
    card = re.search(
        r"<section[^>]*data-reviewee-self-card[^>]*>.*?</section>", html, re.S
    ).group(0)
    assert "What reviewees see of their own entry" in card
    chips = re.findall(
        r'<input type="checkbox"[^>]*value="(\w+)"([^>]*)>([^<]*)</label>', card
    )
    assert [(k, "checked" in rest, label.strip()) for k, rest, label in chips] == [
        ("name", True, "Name"),
        ("email_or_identifier", True, "Email"),
        ("profile_link", True, "Profile"),
        ("tag_1", False, "Tag 1"),
    ]
    # The scaffold is inert: nothing posts, Save / Cancel stay disabled.
    assert "<form" not in card
    assert len(re.findall(r"<button[^>]*disabled", card)) == 2


def test_a_failed_import_still_renders_the_card_and_readout(
    client: TestClient, db: Session
) -> None:
    """Item 1's Codex finding, kept: the in-place 400 re-render owes the
    own-entry keys as the GET does."""
    rs = _session(client, db, "rei-badcsv")
    _alice(db, rs)
    response = client.post(
        f"/operator/sessions/{rs.id}/reviewees/import",
        files={"file": ("r.csv", b"NotAColumn\nx\n", "text/csv")},
    )
    assert response.status_code == 400, response.status_code
    html = response.text
    assert "data-reviewee-self-card" in html
    shown = _div_at(html, "data-reviewee-self-readout")
    assert re.findall(r'<span class="pill pill-count">([^<]*)</span>', shown) == [
        "Name", "Email", "Profile",
    ]


def test_results_shows_the_reviewees_own_line_after_the_pills(
    client: TestClient, db: Session, grant_reviewee_visibility
) -> None:
    rs = _session(client, db, "rei-results")
    _alice(db, rs)
    grant_reviewee_visibility(rs)
    html = client.get(f"/me/sessions/{rs.id}/results").text
    nav = _div_at(html, 'class="rs-role-nav"')
    assert nav.index("rs-role-nav-active") < nav.index("data-reviewee-self-info")
    info = _info(html)
    assert "Alice Reviewee" in info and "alice@example.edu" in info
    assert f'<a href="{LINK}">Profile</a>' in info
    assert "Blue" not in info  # tags start off
    assert "data-reviewer-self-info" not in html


def test_a_reviewer_who_is_also_a_reviewee_sees_only_the_active_pages_line(
    client: TestClient, db: Session, grant_reviewee_visibility
) -> None:
    """`/results` carries the reviewee line; the reviewer line stays on
    the reviewer pages."""
    rs = _session(client, db, "rei-both")
    _alice(db, rs)
    db.add(Reviewer(session_id=rs.id, name="Alice Reviewer", email="alice@example.edu"))
    db.commit()
    grant_reviewee_visibility(rs)
    html = client.get(f"/me/sessions/{rs.id}/results").text
    assert "Alice Reviewee" in _info(html)
    assert "Alice Reviewer" not in _info(html)
    assert "data-reviewer-self-info" not in html
