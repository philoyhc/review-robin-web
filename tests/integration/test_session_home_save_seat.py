"""Session Home's Save keeps the operator's seat (19U Item 4).

The behavior (still unlocked, same scroll, no fragment, Lock drops the
param) is driven in Chromium by ``tests/browser/test_session_home_save.py``;
these pin the markup it rests on, so a run without a browser still sees
it go.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession


def _make_session(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def test_only_saves_reload_opts_into_the_cross_fade(
    client: TestClient, db: Session
) -> None:
    """``@view-transition`` takes no selector, so no page declares it in
    CSS: Session Home adds it from script, on the way out when the card's
    form submits and on the way back when the card's scroll key waits,
    so only Save's reload fades (a fade in progress swallows clicks —
    the Owners card's browser tests met that when it was static)."""
    review_session = _make_session(client, db, "seat-fade")
    home = client.get(f"/operator/sessions/{review_session.id}").text
    head = " ".join(home[: home.index("</head>")].split())
    assert "window.rrwSaveFade = function" in head
    assert "prefers-reduced-motion: no-preference" in head
    assert "'@view-transition { navigation: auto; }'" in head
    assert "if (fromSave) window.rrwSaveFade();" in head
    # Never a static rule, on this page or any other.
    assert "@view-transition {" not in home.replace(
        "'@view-transition { navigation: auto; }'", ""
    )
    assert "@view-transition" not in client.get("/operator/sessions").text


def test_the_card_form_remembers_the_scroll_and_lock_drops_the_param(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, "seat-script")
    body = client.get(f"/operator/sessions/{review_session.id}?editing=1").text

    script = body[body.index("var KEY = 'sessionHomeScrollY:'"):]
    script = script[: script.index("</script>")]
    assert f"getElementById('config-save-{review_session.id}')" in script
    assert "addEventListener('submit'" in script
    assert "window.rrwSaveFade();" in script
    assert "window.scrollTo(0, y)" in script
    # The banner check matches base.html's: only a shown banner wins.
    assert "getClientRects().length" in script

    set_mode = body[body.index("function setMode(card, mode)"):]
    set_mode = set_mode[: set_mode.index("sync(card);")]
    assert "searchParams.delete('editing')" in set_mode
    assert "history.replaceState" in set_mode
