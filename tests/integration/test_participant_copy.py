"""Participant-facing copy on the shared pages: participant audit L2, L3
and L4, `guide/participant_surface_check.md`."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Reviewer, ReviewSession

_TEMPLATES = Path("app/web/templates")
_BRAND = "Review Robin Web"


def _participant(make_client) -> TestClient:
    return make_client(
        AuthenticatedUser(
            principal_id="pat-oid", email="pat@example.edu",
            name="Pat Participant", provider="aad",
        )
    )


def _seed_reviewer(client: TestClient, db: Session) -> None:
    client.post(
        "/operator/sessions",
        data={"name": "Copy Check", "code": "rrw-copy"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "rrw-copy")
    ).scalar_one()
    db.add(
        Reviewer(session_id=review_session.id, name="Pat", email="pat@example.edu")
    )
    db.commit()


# ── L2: one brand suffix ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "template",
    sorted(
        str(p.relative_to(_TEMPLATES))
        for p in (_TEMPLATES / "reviewer").glob("*.html")
        if "{% block title %}" in p.read_text()
    )
    # The shared pages a participant reaches (participant audit M8).
    + ["about.html", "guide.html", "me_debug.html"],
)
def test_every_participant_page_title_ends_with_the_brand(template: str) -> None:
    """The mismatch page had no suffix, the surface read "… — Review"
    and Sign-in details put the brand first (L2)."""
    text = (_TEMPLATES / template).read_text()
    title = re.search(r"{% block title %}(.*?){% endblock %}", text).group(1)
    assert title.endswith(f" — {_BRAND}"), title


def test_the_error_page_title_uses_the_same_brand(make_client) -> None:
    """The error page read "· Review Robin" where every other title reads
    "— Review Robin Web" (L2)."""
    resp = _participant(make_client).get("/me/invite/not-a-token")
    assert resp.status_code == 404
    title = re.search(r"<title>(.*?)</title>", resp.text).group(1)
    assert title.endswith(f" — {_BRAND}"), title
    assert "· Review Robin" not in resp.text


# ── L3: no operator vocabulary for a participant ─────────────────────


def test_about_explains_the_app_without_operator_jargon(make_client) -> None:
    body = _participant(make_client).get("/about").text
    assert "operator allowlist" not in body
    assert "operators upload" not in body
    assert "as an operator" not in body
    assert "The people who run" in body
    assert "If you run reviews here, signing in takes you to the" in body


def test_a_participant_gets_a_participant_guide_subtitle(
    client: TestClient, db: Session, make_client
) -> None:
    _seed_reviewer(client, db)
    body = _participant(make_client).get("/guide").text
    assert "What to expect in the reviews you take part in." in body
    assert "How to run a review session" not in body


def test_an_operator_keeps_the_operator_guide_subtitle(client: TestClient) -> None:
    body = client.get("/guide").text
    assert "How to run a review session, and what each role sees." in body


# ── L4: the participant cards say what the app does ──────────────────


def _card(name: str) -> str:
    text = (_TEMPLATES / "guide.html").read_text()
    match = re.search(
        rf'id="guide-{name}">(.*?)</div>', text, flags=re.DOTALL
    )
    assert match, name
    return " ".join(match.group(1).split())


@pytest.mark.parametrize("name", ["for_reviewers", "for_observers", "for_reviewees"])
def test_participant_cards_drop_operator_wording_and_uk_spelling(name: str) -> None:
    card = _card(name)
    assert "operator" not in card.lower()
    assert "anonymised" not in card and "summarised" not in card


def test_the_observer_card_allows_results_while_the_review_is_open() -> None:
    """Summarized can be granted to observers while ongoing
    (`_PER_CELL_VALID_MODES`), so "once the operator releases responses"
    was wrong (L4)."""
    card = _card("for_observers")
    assert "a summary can appear while the review is still open" in card


def test_the_reviewer_card_says_when_answers_can_change_and_be_read(
    client: TestClient, db: Session, make_client
) -> None:
    """The card said "revisit until the session closes". Editing ends at
    the deadline or an early close (`recall_allowed`,
    `session_accepts_responses`); reading back holds while the session
    is `ready` and after that depends on the visibility policy
    (`reviewer_sees_own_responses`) (L4)."""
    _seed_reviewer(client, db)
    body = " ".join(_participant(make_client).get("/guide").text.split())
    assert "Until the deadline passes (or the review closes early)" in body
    assert "Recall my submission" in body
    assert "You can still read your answers until the review closes" in body
    assert "only if the people running it allow it" in body
    assert "revisit until the session closes" not in body
