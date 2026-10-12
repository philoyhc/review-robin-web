"""A reviewer sees their own roster entry — participant info Item 1, rung 2.

`guide/participant_info.md` Item 1. The scaffold: the Reviewers page's
roster card reports `Shown on surface:` (and its two readout labels
shorten), the Unlock panel carries the selector card inert, and the
reviewer surface and its preview show the reviewer's own fields after
the role pills. Nothing stores a selection yet, so every page shows the
default: name, email and profile, tags off.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Reviewer, ReviewSession
from app.web import views

from .test_reviewer_surface_display_fields import (
    _activate,
    _operator_creates_session_with_pair,
)

LINK = "https://example.edu/rae"


@pytest.fixture
def rae() -> AuthenticatedUser:
    """The reviewer ``_operator_creates_session_with_pair`` rosters."""
    return AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )


def _pair(
    client: TestClient, db: Session, code: str, *, profile: str = LINK
) -> ReviewSession:
    rs = _operator_creates_session_with_pair(
        client, db, code=code,
        reviewer_email="rae@example.edu", reviewee_ident="carol@example.edu",
    )
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == rs.id)
    ).scalar_one()
    reviewer.name = "Rae Reviewer"
    reviewer.profile_link = profile
    reviewer.tag_1 = "Blue"
    db.commit()
    client.post(
        f"/operator/sessions/{rs.id}/reviewers/field-labels",
        data={"tag_1": "Cohort", "tag_2": "", "tag_3": ""},
        follow_redirects=False,
    )
    return rs


def _div_at(html: str, marker: str) -> str:
    """The `<div>` whose opening tag carries ``marker``, balanced."""
    start = html.index(marker)
    start = html.rindex("<div", 0, start)
    depth, i = 0, start
    for m in re.finditer(r"<(/?)div\b", html[start:]):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            i = start + m.end()
            break
    return html[start:html.index(">", i) + 1]


# ── The view helpers ─────────────────────────────────────────────────


def _session_stub() -> SimpleNamespace:
    return SimpleNamespace(id=1, field_labels=[])


def test_the_line_keeps_roster_order_and_skips_empty_fields() -> None:
    reviewer = SimpleNamespace(
        name="Rae", email="rae@example.edu", profile_link="",
        tag_1="Blue", tag_2=None, tag_3="  ",
    )
    line = views.reviewer_self_line(
        _session_stub(), reviewer,
        ["tag_3", "tag_1", "profile_link", "email", "name", "tag_2"],
    )
    assert [f.key for f in line] == ["name", "email", "tag_1"]


def test_the_default_shows_name_email_and_profile_not_tags() -> None:
    assert views.REVIEWER_SELF_DEFAULT == ("name", "email", "profile_link")
    readout = views.reviewer_self_readout(
        _session_stub(), views.REVIEWER_SELF_DEFAULT
    )
    assert readout == ["Name", "Email", "Profile"]


# ── The Reviewers page ───────────────────────────────────────────────


def test_the_readout_row_reports_what_the_surface_shows(
    client: TestClient, db: Session
) -> None:
    rs = _pair(client, db, "rsi-readout")
    html = client.get(f"/operator/sessions/{rs.id}/reviewers").text
    readouts = _div_at(html, 'class="roster-readouts"')
    assert 'roster-readout-label">Roster:</span>' in readouts
    assert 'roster-readout-label">Populated:</span>' in readouts
    assert "Reviewers roster:" not in html
    assert "Populated columns:" not in html
    shown = _div_at(html, "data-reviewer-self-readout")
    assert "Shown on surface:" in shown
    assert re.findall(r'<span class="pill pill-count">([^<]*)</span>', shown) == [
        "Name", "Email", "Profile",
    ]


def test_the_card_sits_above_upload_with_a_chip_per_populated_column(
    client: TestClient, db: Session
) -> None:
    rs = _pair(client, db, "rsi-card")
    html = client.get(f"/operator/sessions/{rs.id}/reviewers").text
    card = re.search(
        r"<section[^>]*data-reviewer-self-card[^>]*>.*?</section>", html, re.S
    )
    assert card, "the reviewer-information card is missing"
    card_html = card.group(0)
    assert "Reviewer information shown on surface" in card_html
    # Above `Upload Reviewers`, in the panel's right column.
    right = html.index("unlock-stack unlock-right")
    assert right < html.index("data-reviewer-self-card") < html.index('id="upload-csv"')
    chips = re.findall(
        r'<input type="checkbox"[^>]*value="(\w+)"\s*(checked)?>([^<]*)</label>',
        card_html,
    )
    assert [(k, bool(c), label.strip()) for k, c, label in chips] == [
        ("name", True, "Name"),
        ("email", True, "Email"),
        ("profile_link", True, "Profile"),
        ("tag_1", False, "Cohort"),
    ]
    # Inert: nothing posts, and both buttons are disabled.
    assert "<form" not in card_html
    assert len(re.findall(r"<button[^>]*disabled", card_html)) == 2


def test_no_profile_chip_without_a_profile(
    client: TestClient, db: Session
) -> None:
    rs = _pair(client, db, "rsi-noprof", profile="")
    html = client.get(f"/operator/sessions/{rs.id}/reviewers").text
    card = re.search(
        r"<section[^>]*data-reviewer-self-card[^>]*>.*?</section>", html, re.S
    ).group(0)
    assert 'value="profile_link"' not in card
    # The default still selects it, so the readout still says so.
    shown = _div_at(html, "data-reviewer-self-readout")
    assert ">Profile<" in shown


def test_locked_the_readout_stays_and_the_card_goes(
    client: TestClient, db: Session
) -> None:
    rs = _pair(client, db, "rsi-locked")
    _activate(client, db, rs)
    html = client.get(f"/operator/sessions/{rs.id}/reviewers").text
    assert "Shown on surface:" in _div_at(html, "data-reviewer-self-readout")
    assert "data-reviewer-self-card" not in html


# ── The reviewer surface and its preview ─────────────────────────────


def _info(html: str) -> str:
    m = re.search(
        r'<span class="rs-self-info" data-reviewer-self-info>(.*?)</span>\s*</div>',
        html, re.S,
    )
    assert m, "no reviewer info on the role row"
    return m.group(1)


def test_the_surface_shows_the_reviewers_own_fields_after_the_pills(
    client: TestClient,
    db: Session,
    rae: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    rs = _pair(client, db, "rsi-surface")
    _activate(client, db, rs)
    html = make_client(rae).get(f"/me/sessions/{rs.id}").text
    nav = _div_at(html, 'class="rs-role-nav"')
    assert nav.index("rs-role-nav-active") < nav.index("data-reviewer-self-info")
    info = _info(html)
    assert "Rae Reviewer" in info
    assert "rae@example.edu" in info
    assert f'<a href="{LINK}">Profile</a>' in info
    # Tags start off.
    assert "Cohort" not in info and "Blue" not in info


def test_the_preview_shows_a_static_reviewer_pill_and_the_line(
    client: TestClient, db: Session
) -> None:
    rs = _pair(client, db, "rsi-preview")
    html = client.get(
        f"/operator/sessions/{rs.id}/preview-surface/1",
        params={"reviewer_email": "rae@example.edu"},
    ).text
    nav = _div_at(html, 'class="rs-role-nav"')
    assert re.search(r'<span class="pill pill-role-reviewer rs-role-nav-active">Reviewer</span>', nav)
    # No navigator links to the previewed reviewer's other surfaces.
    assert "<a " not in nav.split("data-reviewer-self-info")[0]
    assert "Rae Reviewer" in _info(html)
