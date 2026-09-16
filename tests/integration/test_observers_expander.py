"""The Observers row expander — 19P.2 rung 4.

The four row actions, the selected count and the delete gate moved out
of the `Operator actions` card and into a panel this page builds in JS
against the selected rows. The card retired; the editor's Save / Cancel
moved into the edit row's own bar.

**Most of this contract is invisible to pytest.** The panel does not
exist until a checkbox is ticked, and there is no JS runtime here — so
what these tests pin is the *builder*: that the response carries a
script which would produce the right panel, and that nothing it
replaced is still server-rendered. Whether the panel actually appears,
where it anchors, and which buttons it shows for a given selection are
measured in Chromium; `scratchpad/expander_r4.py` is that pass.

Every assertion reads a scoped slice. `base.html` inlines the entire
app's CSS and JS on every page, so a page-wide substring check passes
on markup from a different page entirely.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Observer, ReviewSession


def _session(client: TestClient, db: Session, code: str, rows: int = 3):
    response = client.post(
        "/operator/sessions",
        data={"name": "Obs", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    s = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    s.observers_enabled = True
    db.add_all([
        Observer(
            session_id=s.id,
            email=f"o{n}@example.org",
            display_name=f"O{n}",
            status="active" if n % 2 == 0 else "inactive",
        )
        for n in range(rows)
    ])
    db.commit()
    db.refresh(s)
    return s


def _builder(body: str) -> str:
    """The expander's own script, by what it builds rather than by
    position — `base.html` ships a dozen other scripts on this page."""
    m = re.search(
        r"<script>(?:(?!</script>).)*?observers-row-expander.*?</script>",
        body, re.S,
    )
    assert m, "the expander builder is not in the response"
    return m.group(0)


def _page(client: TestClient, s: ReviewSession, suffix: str = "") -> str:
    return client.get(
        f"/operator/sessions/{s.id}/observers{suffix}"
    ).text


# ── What the builder would produce ────────────────────────────────────


def test_the_panel_carries_all_four_row_actions(
    client: TestClient, db: Session
) -> None:
    s = _session(client, db, "exp-four")
    js = _builder(_page(client, s))

    assert "exp-edit" in js, "no Edit"
    assert "/bulk-inactivate" in js, "no Inactivate"
    assert "/bulk-reactivate" in js, "no Activate"
    assert "/bulk-delete" in js, "no Delete"


def test_the_panel_is_the_bracketed_expander_not_a_new_primitive(
    client: TestClient, db: Session
) -> None:
    """Reuses `base.html`'s `.session-expander` family unchanged, as the
    lobby and Reviewers do. A page-local lookalike would be a fourth
    spelling of one idea."""
    js = _builder(_page(client, _session(client, db, "exp-prim")))

    assert "session-expander session-expander-bracketed" in js
    assert "row-expander-body" in js
    assert "row-expander-actions" in js


def test_the_count_is_bare_text_because_the_panel_is_pill_free(
    client: TestClient, db: Session
) -> None:
    """`spec/ui_elements.md` calls the panel a pill-free zone: its fill
    resolves to the same primitive the pale pills do, so a `.pill-count`
    rendered inside it is invisible. The card this came from could
    afford one; the panel cannot."""
    js = _builder(_page(client, _session(client, db, "exp-pill")))

    assert "row-expander-count" in js
    assert '"</strong> of " + rows().length + " selected' in js
    body = _page(client, _session(client, db, "exp-pill2"))
    # And the old placeholder is not still in the markup beside it.
    assert 'id="observers-selected-count"' not in body


def test_the_delete_ships_disabled_with_its_gate_beside_it(
    client: TestClient, db: Session
) -> None:
    """Nothing syncs an injected pair until its first tick, so a
    live-by-default Delete would be a destructive control with its gate
    open."""
    js = _builder(_page(client, _session(client, db, "exp-gate")))

    delete = re.search(r"btn destructive.*?Delete</button>", js, re.S)
    assert delete, "no Delete in the builder"
    assert 'data-delete-btn="observers-bulk-delete"' in delete.group(0)
    assert "disabled aria-disabled" in delete.group(0)

    confirm = re.search(r"confirm-label.*?</label>", js, re.S)
    assert confirm, "no confirm gate in the builder"
    assert 'data-delete-confirm="observers-bulk-delete"' in confirm.group(0)
    assert 'form="observers-bulk-form"' in confirm.group(0)


def test_the_status_actions_are_chosen_by_the_selection(
    client: TestClient, db: Session
) -> None:
    """`Inactivate` acts on active rows and `Activate` on inactive ones,
    so a selection that is all one status gets exactly one actionable
    button. Rendering the other offers a control that no-ops on every
    row.

    The decision needs each row's status in the DOM — asserted on the
    rows, since the builder reading an attribute nothing writes would
    silently render neither button.
    """
    s = _session(client, db, "exp-status")
    body = _page(client, s)
    js = _builder(body)

    assert "statusActions" in js
    assert 'dataset.status === "active"' in js
    assert 'tr[data-status]' in js, "the builder reads no rows"

    # The CONDITIONALS, not just the read. Making `statusActions` push
    # both labels unconditionally passed every other assertion here:
    # the attribute is still read, the function still exists, and both
    # `formaction`s are still in the text. Whether the right button
    # appears for a given selection is measured in Chromium — a
    # mixed-status select-all offers both, a single active row offers
    # only `Inactivate`, and after acting on it the panel offers only
    # `Activate`. This is the most pytest can hold: that the choice is
    # made at all.
    fn = re.search(r"function statusActions\(sel\) \{.*?\n        \}", js, re.S)
    assert fn, "statusActions is gone"
    assert 'if (hasActive) out.push("Inactivate");' in fn.group(0), (
        "Inactivate is offered for selections with no active row"
    )
    assert 'if (hasInactive) out.push("Activate");' in fn.group(0), (
        "Activate is offered for selections with no inactive row"
    )

    rows = re.findall(r'<tr[^>]*id="observer-row-\d+"[^>]*>', body)
    assert rows, "no rows rendered"
    for row in rows:
        assert re.search(r'data-status="(active|inactive)"', row), row


def test_edit_is_arity_one(client: TestClient, db: Session) -> None:
    """The one action that cannot take a set. It renders disabled rather
    than absent, so the panel's shape does not change under the pointer
    as a second row is ticked."""
    js = _builder(_page(client, _session(client, db, "exp-arity")))

    assert "sel.length === 1" in js
    assert "disabled aria-disabled" in js


def test_edit_navigates_to_the_row_it_opens(
    client: TestClient, db: Session
) -> None:
    """Entering edit mode is a navigation, and without a fragment it
    lands at the top of the document. Delegated from the table, because
    the panel is replaced on every selection change — binding the button
    directly would bind one that is about to be thrown away."""
    js = _builder(_page(client, _session(client, db, "exp-editnav")))

    assert '.exp-edit[data-edit-id]' in js, "the handler is not delegated"
    assert '"#observer-row-"' in js, "Edit navigates without a fragment"
    assert '"?edit_id="' in js


# ── What the panel replaced ───────────────────────────────────────────


def test_nothing_the_panel_builds_is_also_server_rendered(
    client: TestClient, db: Session
) -> None:
    """A survivor would be a second control with the same id — and both
    the delete pairing and this page's own script reach theirs with a
    first-match `querySelector`, so the copy would silently take the
    wiring."""
    body = _page(client, _session(client, db, "exp-nodup"))

    for gone in (
        'id="observers-edit-btn"',
        'id="observers-inactivate-btn"',
        'id="observers-reactivate-btn"',
        'id="observers-delete-btn"',
        'id="observers-selected-count"',
        'id="observers-delete-confirm"',
        'id="observers-delete-ack"',
    ):
        assert gone not in body, f"{gone} is server-rendered as well"


# ── The edit row's own bar ────────────────────────────────────────────


@pytest.mark.parametrize("mode", ["add", "edit"])
def test_the_editor_carries_its_save_and_cancel_in_a_row_bar(
    client: TestClient, db: Session, mode: str
) -> None:
    """Save and Cancel came out of the retired card. They belong with
    the row they act on, not a table's height above it."""
    s = _session(client, db, f"exp-bar-{mode}")
    if mode == "add":
        body = _page(client, s, "?add=1")
    else:
        row_id = db.execute(
            select(Observer.id).where(Observer.session_id == s.id)
        ).scalars().first()
        body = _page(client, s, f"?edit_id={row_id}")

    bar = re.search(
        r'<tr class="session-expander session-expander-bracketed '
        r'row-editor-bar">.*?</tr>',
        body, re.S,
    )
    assert bar, f"no editor bar in {mode} mode"
    held = bar.group(0)
    assert 'form="observer-edit-form"' in held, "Save reaches no form"
    assert ">Save</button>" in held
    assert ">Cancel</a>" in held
    assert held.index(">Save</button>") < held.index(">Cancel</a>"), (
        "Save then Cancel — the order the card rendered"
    )
    # Cancel leaves the editor for the list, so it lands where the list
    # is: the same anchor Clear and Search take.
    assert "#observers-table-card" in held


def test_the_editor_bar_announces_the_mode_it_is_in(
    client: TestClient, db: Session
) -> None:
    """The card carried an `<h2>` — "Add new observer" / "Edit observer"
    — and that heading was the only accessible name for the state the
    page is in. What replaces it visually is a highlighted row, and a
    highlight reaches nobody using a screen reader."""
    s = _session(client, db, "exp-announce")
    body = _page(client, s, "?add=1")

    bar = re.search(
        r'<tr class="session-expander session-expander-bracketed '
        r'row-editor-bar">.*?</tr>',
        body, re.S,
    )
    assert bar
    assert 'class="visually-hidden" aria-live="polite"' in bar.group(0)
    assert "Add new observer" in bar.group(0)


def test_a_rejected_save_puts_its_reason_in_the_row_bar(
    client: TestClient, db: Session
) -> None:
    """The error lived in the editor card. It belongs with the row
    anyway: the message is about the values in the row above."""
    s = _session(client, db, "exp-err")
    response = client.post(
        f"/operator/sessions/{s.id}/observers/create",
        data={
            "email": "o0@example.org", "display_name": "Dup",
            "tag_1": "", "status": "active",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400

    bar = re.search(
        r'<tr class="session-expander session-expander-bracketed '
        r'row-editor-bar">.*?</tr>',
        response.text, re.S,
    )
    assert bar, "no editor bar on a rejected save"
    assert "row-editor-error" in bar.group(0), "the reason is elsewhere"


def test_the_edit_row_reads_as_selected(
    client: TestClient, db: Session
) -> None:
    """The row being edited takes the same rails a selected row does, so
    the bar beneath it closes the same bracket."""
    s = _session(client, db, "exp-sel")
    row_id = db.execute(
        select(Observer.id).where(Observer.session_id == s.id)
    ).scalars().first()
    body = _page(client, s, f"?edit_id={row_id}")

    row = re.search(rf'<tr[^>]*id="observer-row-{row_id}"[^>]*>', body)
    assert row
    assert "session-row-selected" in row.group(0)
