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
measured in Chromium — that pass runs outside the repo (the agent
sandbox's scratchpad), so its results live in the PR body and the
segment plan's `### Status` rather than in a file a reader could open.

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
    return _code(m.group(0))


def _markup_only(body: str) -> str:
    """The page without its `<style>` and `<script>` blocks."""
    body = re.sub(r"<style\b.*?</style>", "", body, flags=re.S)
    return re.sub(r"<script\b.*?</script>", "", body, flags=re.S)


def _code(js: str) -> str:
    """The script with `//` comments stripped.

    Every comment in this builder explains what the code does, using the
    same identifiers — so `"is-split" in js` passed with the class no
    longer emitted, matched by the comment saying why it is emitted.

    `_builder()` returns this, rather than callers remembering to wrap.
    The first fix stripped comments at the two call sites that had
    already been caught, which leaves the hole open for the next
    assertion whose identifier a comment repeats — which is exactly how
    it opened. Nothing in this file asserts on reasoning text; if
    something ever needs to, it can read the response directly.
    """
    return "\n".join(
        re.sub(r"//.*$", "", line) for line in js.split("\n")
    )


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

    # And each label posts to its OWN route. Swapping the two branches
    # — so `Inactivate` posts `/bulk-reactivate` — passed the whole
    # suite: both route strings are still in the builder and both
    # conditionals still exist. Nothing tied a label to a route.
    assert '? "/bulk-inactivate" : "/bulk-reactivate"' in js, (
        "the status labels and their routes can disagree"
    )

    rows = re.findall(r'<tr[^>]*id="observer-row-\d+"[^>]*>', body)
    assert rows, "no rows rendered"
    for row in rows:
        assert re.search(r'data-status="(active|inactive)"', row), row


def test_edit_takes_any_selection(client: TestClient, db: Session) -> None:
    """operator pages Item 4: `Edit` on one row opens the row editor, on
    several their rule alone — so it is live at any arity, carrying the
    selected ids."""
    js = _builder(_page(client, _session(client, db, "exp-arity")))

    edit = re.search(r'class="btn secondary exp-edit".*?Edit</button>', js, re.S)
    assert edit, "no Edit button"
    assert "data-edit-ids" in edit.group(0)
    assert "disabled" not in edit.group(0), "Edit renders disabled"


def test_edit_navigates_to_the_editor_for_its_arity(
    client: TestClient, db: Session
) -> None:
    """Entering edit mode is a navigation, and without a fragment it
    lands at the top of the document. Delegated from the table, because
    the panel is replaced on every selection change."""
    js = _builder(_page(client, _session(client, db, "exp-editnav")))

    assert '.exp-edit[data-edit-ids]' in js, "the handler is not delegated"
    assert '"#observer-row-"' in js, "Edit navigates without a fragment"
    assert '"?edit_id="' in js, "one row does not open the row editor"
    assert '"rule_id="' in js, "several rows do not open the rule editor"


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
    # The colspan. Hardcoded in the template because this page has no
    # conditional columns — which is true, and was unpinned until a
    # cold read changed the 7 to a 4 and watched the whole suite pass
    # with the bar spanning four of seven columns. Counted from the
    # `<thead>` rather than repeated, so the two cannot drift.
    head = re.search(r"<thead>.*?</thead>", body, re.S)
    assert head, "no thead"
    columns = len(re.findall(r"<th\b", head.group(0)))
    assert f'colspan="{columns}"' in held, (
        f"the bar spans the wrong number of columns (table has {columns})"
    )
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


# ── The cohort editor, in the expander — 19P.2 rung 5 ─────────────────
#
# The editor moved out of its card and into the panel's left pane, and
# `.card-columns` retired with it. As with the rest of this file: the
# panel does not exist without JS, so what is pinned here is the
# template it is cloned from, the builder that clones it, and the
# absence of the card. The behavior — the dirty gate, the reposition
# on add, the mixed reset — is measured in Chromium.


def test_the_cohort_card_and_its_grid_are_gone(
    client: TestClient, db: Session
) -> None:
    s = _session(client, db, "coh-gone")
    body = _page(client, s)

    assert 'class="card-columns"' not in body, "the grid survived"
    assert 'id="observers-cohort-block"' not in body
    assert 'id="observers-cohort-empty"' not in body, (
        "the 'select observers below' placeholder has no home now: at "
        "zero selected the whole panel is absent, which says it better"
    )
    assert 'id="observers-cohort-heading"' not in body
    assert 'id="observers-cohort-save-btn"' not in body


def test_the_expander_carries_no_builder(
    client: TestClient, db: Session
) -> None:
    """operator pages Item 4 rung 4, the author's ruling: selecting rows
    shows no cohort builder; `Edit` opens the one editing surface. So the
    page ships no builder template, and the panel neither splits nor
    clones one — nor guards an edit it can no longer hold."""
    body = _page(client, _session(client, db, "coh-none"))
    js = _builder(body)

    assert 'id="observers-cohort-template"' not in body
    assert "data-observer-cohort-builder" not in _markup_only(body)
    for retired in ("COHORT_TPL", "is-split", "cohort-save-btn",
                    "cohortDirty", "okToDiscardCohortEdit", "beforeunload"):
        assert retired not in js, f"the expander still carries {retired}"


def test_the_split_modifier_has_a_rule_behind_it(
    client: TestClient, db: Session
) -> None:
    """The row editor's bar splits as the expander's panel once did
    (operator pages Item 4), and the class is inert without this. Read
    off the response rather than `base.html` on disk, because what ships
    is what the page carries."""
    body = _page(client, _session(client, db, "coh-css"))

    assert "body.ui-v2 .row-expander-body.is-split {" in body, (
        "nothing lays the two panes out"
    )
    assert "body.ui-v2 .row-expander-pane-right {" in body
    assert "body.ui-v2 .row-expander-label {" in body
    # The builder's two sizes, `button.<class>` in both cases. A
    # class-only selector here is (0,2,1) and loses to the shared
    # `body.ui-v2 button.btn` — the Save rule's first draft shipped
    # exactly that and did nothing, with this assertion green.
    assert "body.ui-v2 button.cohort-cell-btn {" in body
    assert "body.ui-v2 button.cohort-combinator-btn {" in body
    # And nothing on the page re-sizes a button from its own markup:
    # `spec/ui_elements.md` §6 calls an inline `style` on a button a
    # defect, because a role living in one template cannot be restyled
    # from here. These four were the last on any Setup page.
    for tag in re.finditer(r"<button\b[^>]*>", body, re.S):
        assert "style=" not in tag.group(0), (
            "an inline-styled button is back: " + tag.group(0)[:120]
        )
    # Top-flush, not a shared bottom edge: the builder is taller, and
    # bottom-aligning would anchor Save to a button row it has no
    # relationship with.
    rule = re.search(
        r"body\.ui-v2 \.row-expander-body\.is-split \{(.*?)\}", body, re.S
    )
    assert rule and "align-items: start" in rule.group(1), (
        "the panes share a bottom edge"
    )
