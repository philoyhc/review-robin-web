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


def _index_cells(html: str) -> str:
    """The index row's markup, so a "Name (2)" assertion cannot be
    satisfied by the roster table further down the page."""
    row = re.search(r'id="roster-index-row".*?</tr>', html, re.S)
    assert row, "index row not found"
    return row.group(0)


def test_populated_columns_show_counts_not_presence(client, db):
    """The plan called these counts a "free re-house" of ``col_data``.
    They are not — that map is presence only — so they are their own
    query (``tag_slot_counts`` / ``slot_row_count``). Assert the number,
    which is what distinguishes a count from a flag."""
    rs = _session_with_reviewers(client, db, "scafc1")
    cells = _index_cells(_page(client, rs))
    assert "Name (2)" in cells, cells
    assert "Email (2)" in cells, cells


def test_populated_counts_are_per_column_not_the_row_count(client, db):
    """A column half-filled must read its own number, not the roster's.

    The cheap wrong implementation — reusing ``total_row_count`` for
    every chip — passes the test above and fails this one.
    """
    client.post(
        "/operator/sessions",
        data={"name": "Partial", "code": "scafc2"},
        follow_redirects=False,
    )
    rs = db.execute(
        select(ReviewSession).where(ReviewSession.code == "scafc2")
    ).scalar_one()
    client.post(
        f"/operator/sessions/{rs.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail,ReviewerTag1\n"
                b"R1,r1@example.com,alpha\n"
                b"R2,r2@example.com,\n"
                b"R3,r3@example.com,gamma\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    cells = _index_cells(_page(client, rs))
    assert "Name (3)" in cells, cells
    # Two of three rows carry a tag — the blank one must not count.
    # Named, not a bare "(2)": the roster count pill sits in the same row.
    assert "Tag 1 (2)" in cells, cells
    assert "Tag 1 (3)" not in cells, cells


def test_populated_columns_use_the_session_friendly_label(client, db):
    """The chip reads the same ``field_label_pair`` as the roster's own
    column headers, so the index cannot disagree with the table below."""
    client.post(
        "/operator/sessions",
        data={"name": "Labelled", "code": "scafc3"},
        follow_redirects=False,
    )
    rs = db.execute(
        select(ReviewSession).where(ReviewSession.code == "scafc3")
    ).scalar_one()
    client.post(
        f"/operator/sessions/{rs.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail,ReviewerTag1\n"
                b"R1,r1@example.com,alpha\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{rs.id}/reviewers/field-labels",
        data={"tag_1": "Tutor"},
        follow_redirects=False,
    )
    cells = _index_cells(_page(client, rs))
    assert "Tutor (1)" in cells, cells
    assert "Tag 1 (1)" not in cells, cells


def test_a_column_with_no_data_gets_no_chip(client, db):
    """Presence still gates which chips appear; the count says how many."""
    cells = _index_cells(_page(client, _session_with_reviewers(client, db, "scafc4")))
    assert "Tag 1" not in cells, cells
    assert "Tag 2" not in cells, cells


def test_the_index_card_does_not_repeat_the_roster_name_as_a_heading(client, db):
    """The Roster column names it; an <h2> above the table said it twice."""
    html = _page(client, _session_with_reviewers(client, db, "scafc5"))
    card = re.search(
        r'id="roster-index-scaffold".*?</table>', html, re.S
    )
    assert card, "index card not found"
    assert "<h2>" not in card.group(0), card.group(0)[:400]


def test_the_replace_confirm_is_one_tick_naming_both_losses(client, db):
    """The first draft split the replace into two ticks — one for the
    roster, one for the responses — so the operator agreed twice to a
    single action. The live card does not: it gates on one visible tick
    and carries the response-loss acknowledgement as a hidden field."""
    rs = _session_with_reviewers(client, db, "scafc6")
    panel = re.search(
        r'id="roster-unlock-panel".*?</tr>', _page(client, rs), re.S
    )
    assert panel
    upload = panel.group(0).split("<h3>Reviewer tag labels</h3>")[0]
    ticks = re.findall(r"<input[^>]*type=\"checkbox\"[^>]*>", upload)
    assert len(ticks) == 1, f"expected one replace confirm, got {len(ticks)}"
    # One sentence, both losses named.
    assert "replace the existing" in upload, upload
    assert "discard the existing" in upload, upload


def test_the_unlock_panel_uses_the_two_column_primitive(client, db):
    """1/3 upload, 2/3 labels + danger zone. The widths are CSS in
    `base.html` (`CLAUDE.md`: primitives go there, not inline), so what
    the suite can assert is that the panel reaches for them."""
    html = _page(client, _session_with_reviewers(client, db, "scafc7"))
    panel = re.search(r'id="roster-unlock-panel".*?</tr>', html, re.S)
    assert panel
    assert 'class="unlock-cols"' in panel.group(0)
    assert panel.group(0).count('class="unlock-col"') == 2
    assert "grid-template-columns: minmax(0, 1fr) minmax(0, 2fr)" in html


def test_the_index_row_has_doubled_outer_gutters(client, db):
    """Roster name and Edit control sit off the card's rule, not against
    it. Geometry, so this asserts the rule exists rather than its effect
    — the dev slot is what judges the look."""
    html = _page(client, _session_with_reviewers(client, db, "scafc8"))
    first = re.search(
        r"\.roster-index-table td:first-child\s*\{([^}]*)\}", html
    )
    last = re.search(
        r"\.roster-index-table td:last-child\s*\{([^}]*)\}", html
    )
    assert first and "padding-left: var(--space-6)" in first.group(1), first
    assert last and "padding-right: var(--space-6)" in last.group(1), last

