"""An observer sees their own roster entry — participant info Item 5.

`guide/participant_info.md` Item 5, rung 2 (the scaffold): the Observers
page's "What observers see of their own entry" card, inert at the
default; the `Observers see:` readout; the observer's own line after the
role pills on `/collation`. Nothing reads or writes
`sessions.observer_self_fields` yet, so every surface shows the default:
name and email, the tag off.
"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Observer, ReviewSession

from ._unlock_panel import panel_columns


def _session(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Cohort A", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303
    rs = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    rs.observers_enabled = True
    db.commit()
    return rs


def _alice(db: Session, rs: ReviewSession, *, tag: str | None = "Panel") -> None:
    """`client` signs in as alice@example.edu (tests/conftest.py)."""
    db.add(Observer(
        session_id=rs.id, email="alice@example.edu",
        display_name="Alice Observer", status="active", tag_1=tag,
    ))
    db.commit()


def _div_at(html: str, marker: str) -> str:
    start = html.rindex("<div", 0, html.index(marker))
    depth = 0
    for m in re.finditer(r"<(/?)div\b", html[start:]):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return html[start:start + m.end() + 1]
    raise AssertionError(f"{marker} never closes")


def _card(html: str) -> str:
    return re.search(
        r"<section[^>]*data-observer-self-card[^>]*>.*?</section>", html, re.S
    ).group(0)


def _chips(card: str) -> list[tuple[str, bool, str]]:
    return [
        (key, "checked" in rest, label.strip())
        for key, rest, label in re.findall(
            r'<input type="checkbox"[^>]*value="(\w+)"([^>]*)>([^<]*)</label>',
            card,
        )
    ]


def _readout(html: str) -> list[str]:
    shown = _div_at(html, "data-observer-self-readout")
    assert "Observers see:" in shown
    return re.findall(r'<span class="pill pill-count">([^<]*)</span>', shown)


def test_the_readout_reports_the_default(client: TestClient, db: Session) -> None:
    rs = _session(client, db, "obi-readout")
    _alice(db, rs)
    html = client.get(f"/operator/sessions/{rs.id}/observers").text
    assert _readout(html) == ["Name", "Email"]


def test_the_card_heads_the_right_column_inert_at_the_default(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "obi-card")
    _alice(db, rs)
    html = client.get(f"/operator/sessions/{rs.id}/observers?unlocked=1").text
    _, _, right = panel_columns(html)
    assert right.index("data-observer-self-card") < right.index("danger-zone")
    card = _card(html)
    assert "What observers see of their own entry" in card
    assert _chips(card) == [
        ("display_name", True, "Name"),
        ("email", True, "Email"),
        ("tag_1", False, "Tag"),
    ]
    # The scaffold posts nothing: no form, Save and Cancel disabled.
    assert "<form" not in card
    assert len(re.findall(r"<button[^>]*disabled", card)) == 2


def test_the_tag_is_offered_only_while_a_row_holds_one(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "obi-notag")
    _alice(db, rs, tag=None)
    card = _card(client.get(f"/operator/sessions/{rs.id}/observers?unlocked=1").text)
    assert [key for key, _, _ in _chips(card)] == ["display_name", "email"]


def test_an_empty_roster_still_renders_the_card(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "obi-empty")
    html = client.get(f"/operator/sessions/{rs.id}/observers?unlocked=1").text
    assert [key for key, _, _ in _chips(_card(html))] == ["display_name", "email"]
    assert _readout(html) == ["Name", "Email"]


def test_a_failed_import_still_renders_the_card_and_readout(
    client: TestClient, db: Session
) -> None:
    """Item 1's Codex finding, kept: the in-place 400 re-render owes the
    own-entry keys as the GET does."""
    rs = _session(client, db, "obi-badcsv")
    _alice(db, rs)
    response = client.post(
        f"/operator/sessions/{rs.id}/observers/import",
        files={"file": ("o.csv", b"ObserverName\nX\n", "text/csv")},
    )
    assert response.status_code == 400, response.status_code
    assert "data-observer-self-card" in response.text
    assert _readout(response.text) == ["Name", "Email"]


def test_collation_shows_the_observers_own_line_after_the_pills(
    client: TestClient, db: Session
) -> None:
    rs = _session(client, db, "obi-collation")
    _alice(db, rs)
    html = client.get(f"/me/sessions/{rs.id}/collation").text
    nav = _div_at(html, 'class="rs-role-nav"')
    assert nav.index("rs-role-nav-active") < nav.index("data-observer-self-info")
    info = re.search(
        r'<span class="rs-self-info" data-observer-self-info>(.*?)</span>\s*</div>',
        html, re.S,
    )
    assert info, "no observer info on the role row"
    assert "Alice Observer" in info.group(1)
    assert "alice@example.edu" in info.group(1)
    assert "Panel" not in info.group(1)  # the tag starts off
    assert "data-reviewer-self-info" not in html
    assert "data-reviewee-self-info" not in html
