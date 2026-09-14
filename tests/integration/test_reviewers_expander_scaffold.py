"""19P.1 rung 1 — the Variant B surface renders, inert.

Scaffold-first (`CLAUDE.md`): the index row, its Unlock panel and the
row-expander template land with real copy and layout and **nothing
wired**, so the shape can be looked at on the dev slot before any
behaviour moves. The three cards it will eventually absorb are still
present and still live.

The suite has no JS runtime, so these assert the **mechanism** — the
markup, the classes, the `disabled` attributes — not the appearance.
19L stated the same limit for the lobby bracket
(`guide/archive/segment_19L_ux_refinements.md:207-209`).
"""
from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession

R_CSV = b"ReviewerName,ReviewerEmail\nR1,r1@example.com\nR2,r2@example.com\n"


def _session_with_reviewers(client: TestClient, db: Session, code: str) -> ReviewSession:
    client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    rs = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{rs.id}/reviewers/import",
        files={"file": ("r.csv", R_CSV, "text/csv")},
        follow_redirects=False,
    )
    return rs


def _page(client: TestClient, rs: ReviewSession) -> str:
    response = client.get(f"/operator/sessions/{rs.id}/reviewers")
    assert response.status_code == 200
    return response.text


def test_index_row_and_unlock_panel_render(client, db):
    html = _page(client, _session_with_reviewers(client, db, "scaf1"))
    assert 'id="roster-index-scaffold"' in html
    assert 'id="roster-index-row"' in html
    assert 'id="roster-unlock-panel"' in html
    # The panel reuses the lobby's bracket primitives rather than new ones.
    assert "session-expander session-expander-bracketed" in html


def test_every_unlock_control_is_inert(client, db):
    """Scaffold-first means inert controls, not merely greyed ones."""
    html = _page(client, _session_with_reviewers(client, db, "scaf2"))
    panel = re.search(
        r'id="roster-unlock-panel".*?</tr>', html, re.S
    )
    assert panel, "Unlock panel not found"
    body = panel.group(0)
    # Every interactive control inside the panel carries `disabled`.
    controls = re.findall(r"<(?:button|input)\b[^>]*>", body)
    assert controls, "no controls found in the Unlock panel"
    # Match the ATTRIBUTE, not the substring. An earlier version of this
    # test matched `"disabled" in tag`, which an `aria-label="… disabled)"`
    # satisfied — removing the real attribute left every test green.
    undisabled = [
        c for c in controls
        if not re.search(r"(?:^|\s)disabled(?:[=\s>]|$)", c)
    ]
    assert not undisabled, f"wired controls in a scaffold panel: {undisabled}"


def test_row_expander_template_is_present_and_inert(client, db):
    html = _page(client, _session_with_reviewers(client, db, "scaf3"))
    tpl = re.search(
        r'<template id="reviewer-row-expander">.*?</template>', html, re.S
    )
    assert tpl, "row-expander template not found"
    buttons = re.findall(r"<button\b[^>]*>", tpl.group(0))
    assert len(buttons) == 4, f"expected the four row actions, got {len(buttons)}"
    assert all("disabled" in b for b in buttons), buttons


def test_the_three_cards_it_will_absorb_are_still_live(client, db):
    """Rung 1 adds a surface; it retires nothing. Rung 3 does that."""
    rs = _session_with_reviewers(client, db, "scaf4")
    html = _page(client, rs)
    assert 'id="upload-csv"' in html
    assert "danger-zone" in html
    # The labels editor's own live control, not a string the scaffold
    # prints. An earlier version accepted `"Friendly labels" in html`,
    # which the scaffold's own panel satisfies — deleting the include
    # outright left every test green.
    assert f"/operator/sessions/{rs.id}/reviewers/field-labels" in html, (
        "the live friendly-labels editor must still render"
    )


def test_unlock_is_suppressed_not_disabled_when_locked(client, db):
    """A locked page must carry no roster-mutating control at all.

    Found by `test_field_labels_editor_routes`, which asserts a locked
    Reviewers page contains no "Save labels" anywhere — the real editor
    *suppresses* that button rather than disabling it. The Unlock panel
    holds one, so the panel is suppressed on the same rule. The index row
    itself is informational and stays.
    """
    from app.db.models import ReviewSession as _RS

    rs = _session_with_reviewers(client, db, "scaf6")
    db.get(_RS, rs.id).status = "ready"
    db.commit()

    html = _page(client, rs)
    assert 'id="roster-index-scaffold"' in html, "the index row is informational"
    assert 'id="roster-unlock-btn"' not in html
    assert 'id="roster-unlock-panel"' not in html
    assert "Save labels" not in html


def test_scaffold_is_absent_while_editing_a_row(client, db):
    """`edit_mode` already suppresses row selection (`selectable`), so the
    bracket scaffold must not render there either — it would offer a
    selection surface the page has deliberately withdrawn."""
    rs = _session_with_reviewers(client, db, "scaf5")
    html = client.get(f"/operator/sessions/{rs.id}/reviewers?add=1").text
    assert "Reviewers" in html, "precondition: the page rendered"
    assert 'class="reviewer-select"' not in html, (
        "precondition: edit_mode withdraws row selection — if this fails the "
        "test below is vacuous"
    )
    assert '<template id="reviewer-row-expander">' not in html


def test_index_card_renders_on_an_empty_roster(client, db):
    """The card is unconditional, so every state it renders in must be
    whole. The first draft gated its CSS and its toggle script on
    `selectable`, so an empty roster drew an unstyled card with a dead
    Unlock button over a panel that could never open."""
    client.post(
        "/operator/sessions",
        data={"name": "Empty", "code": "scaf7"},
        follow_redirects=False,
    )
    rs = db.execute(
        select(ReviewSession).where(ReviewSession.code == "scaf7")
    ).scalar_one()
    html = _page(client, rs)
    assert 'id="roster-index-scaffold"' in html
    # Unlock is offered, so its toggle must be present to make it real.
    assert 'id="roster-unlock-btn"' in html
    assert 'id="roster-unlock-panel"' in html
    assert 'getElementById("roster-unlock-btn")' in html


def test_unlock_is_absent_while_editing_a_row(client, db):
    """The plan: "Unlock and row-selection are mutually exclusive — that is
    the gate", and the Unlock gate *extends* `edit_mode`. The page already
    withdraws selection during edit/add, so the Unlock affordance goes too;
    the first draft gated only on `is_editable` and offered it there."""
    rs = _session_with_reviewers(client, db, "scaf8")
    html = client.get(f"/operator/sessions/{rs.id}/reviewers?add=1").text
    assert 'id="roster-index-scaffold"' in html, "the index row is informational"
    assert 'id="roster-unlock-btn"' not in html
    assert 'id="roster-unlock-panel"' not in html
