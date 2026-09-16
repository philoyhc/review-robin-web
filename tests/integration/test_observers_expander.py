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


def test_edit_is_arity_one(client: TestClient, db: Session) -> None:
    """The one action that cannot take a set. It renders disabled rather
    than absent, so the panel's shape does not change under the pointer
    as a second row is ticked."""
    js = _builder(_page(client, _session(client, db, "exp-arity")))

    assert "sel.length === 1" in js
    # Scoped to Edit's own ternary: a bare `"disabled aria-disabled" in
    # js` also matches the Delete button, which ships disabled for a
    # different reason.
    edit = re.search(r"var editable = sel\.length === 1;.*?Edit</button>", js, re.S)
    assert edit, "no Edit branch"
    assert "disabled aria-disabled" in edit.group(0), (
        "Edit renders live at arity != 1"
    )


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


def test_the_builder_is_server_rendered_once_into_a_template(
    client: TestClient, db: Session
) -> None:
    """A `<template>`, not a JS string literal, because the selects
    carry live per-session tag labels — building those option lists in
    JS would put the same data in two places."""
    s = _session(client, db, "coh-tpl")
    body = _page(client, s)

    tpl = re.search(
        r'<template id="observers-cohort-template">.*?</template>',
        body, re.S,
    )
    assert tpl, "no cohort template"
    held = tpl.group(0)
    assert "data-observer-cohort-builder" in held
    assert "data-observer-rule-cell" in held
    assert "observers-cohort-mixed-message" in held
    # Exactly one. Two would be two sources for one editor.
    assert body.count('id="observers-cohort-template"') == 1


def test_the_panel_splits_and_clones_the_builder_into_it(
    client: TestClient, db: Session
) -> None:
    js = _builder(_page(client, _session(client, db, "coh-split")))

    code = js
    assert '" is-split"' in code, "the panel does not split"
    assert "row-expander-pane-left" in code
    assert "row-expander-pane-right" in code
    assert "COHORT_TPL.content.cloneNode(true)" in code, (
        "the builder is moved rather than cloned, or not copied at all"
    )
    # The label takes the Link 1 idiom, not a card heading.
    assert "row-expander-label" in code
    assert "<h3" in code and "<h2" not in code, "an h2 reads as a card title"


def test_save_is_created_disabled_and_placed_after_the_last_x(
    client: TestClient, db: Session
) -> None:
    js = _builder(_page(client, _session(client, db, "coh-save")))

    place = re.search(r"function placeSaveButton\(nodes\) \{.*?\n        \}", js, re.S)
    assert place, "no placeSaveButton"
    held = place.group(0)
    assert "cohort-save-btn" in held
    assert "save.disabled = true" in held, "Save ships live"
    assert "/cohort-rule" in held, "Save posts nowhere"
    assert 'form="observers-bulk-form"' in held or \
           '"form", "observers-bulk-form"' in held, "Save carries no selection"
    assert "xBtn.parentNode.appendChild(save)" in held, (
        "Save is not appended to the last cell's X row — reading the "
        "X out of the DOM is not the same as putting Save beside it"
    )
    # De-duplication, which a clone of the first cell would otherwise
    # produce: measured at two Save buttons after one click of `+`.
    assert "for (var i = 1; i < all.length; i++) all[i].remove();" in held, (
        "nothing removes a duplicated Save"
    )


def test_the_rule_clone_does_not_carry_save_with_it(
    client: TestClient, db: Session
) -> None:
    """`observerAddRule` clones the FIRST rule cell. With one cell that
    is also the LAST — the cell holding Save — so the clone brought a
    second Save into the list, both posting the same form, the stale one
    carrying the stale rule."""
    body = _page(client, _session(client, db, "coh-clone"))

    fn = re.search(
        r"window\.observerAddRule = function \(btn\) \{.*?\n      \};",
        body, re.S,
    )
    assert fn, "observerAddRule is gone"
    assert "cohort-save-btn" in fn.group(0), (
        "the clone is not stripped of Save"
    )


def test_the_builder_helpers_are_defined_before_the_selection_script(
    client: TestClient, db: Session
) -> None:
    """The two-rule restore bug, pinned by ordering.

    `refresh()` runs at the end of the selection IIFE and calls
    `window.observerAddRule` to grow the editor to N cells. That
    assignment used to come AFTER the IIFE, so a `?selected=` restore of
    a shared cohort of two or more rules threw a TypeError, which the
    `try/catch` around the rule load swallowed into
    `setEditorToDefault()` — the operator saw a blank one-rule builder
    for a rule that had two. Reproduced in Chromium on `main`.
    """
    body = _page(client, _session(client, db, "coh-order"))

    assign = body.index("window.observerAddRule = function")
    # The selection IIFE, located by something only it contains.
    use = body.index("function armDirtyGate(nodes)")
    assert assign < use, (
        "observerAddRule is assigned after the script that calls it"
    )


def test_the_dirty_gate_is_re_armed_per_rebuild_not_once(
    client: TestClient, db: Session
) -> None:
    """The panel is thrown away and rebuilt on every selection change.
    A baseline held across rebuilds would compare this selection's rule
    against the previous one's, leaving `Save` live against an unchanged
    rule."""
    js = _builder(_page(client, _session(client, db, "coh-dirty")))

    assert "function armDirtyGate" in js
    assert "var baseline = ruleSignature(nodes.block);" in js, (
        "the baseline is not taken inside the arming function"
    )
    # Armed from `refresh()`, which runs per rebuild — not from the
    # IIFE body, which runs once.
    refresh = re.search(r"function refresh\(\) \{.*?\n        \}", js, re.S)
    assert refresh and "armDirtyGate(nodes)" in refresh.group(0), (
        "the gate is armed once rather than per rebuild"
    )
    # Every control that can change the rule reaches the gate.
    gate = re.search(r"function armDirtyGate\(nodes\) \{.*?\n        \}", js, re.S)
    for event in ('"input"', '"change"', '"click"'):
        assert event in gate.group(0), f"the gate ignores {event}"


def test_the_click_path_rebinds_the_save_it_replaces(
    client: TestClient, db: Session
) -> None:
    """`X` on the last rule cell destroys `Save` and gets a replacement.

    `Save` rides inside that cell's flex row — the shape the plan asked
    for — so `observerRemoveRule` takes it with the cell.
    `placeSaveButton` builds a new one; if the click path discards the
    return, `nodes.save` keeps pointing at the removed node and `sync()`
    thereafter toggles a detached button while the visible one stays
    greyed out for the rest of that selection. In a two-cell builder the
    first cell's `X` is `disabled`, so every `X` in a two-rule edit hits
    this path.

    **This is a text guard and cannot be more.** There is no JS runtime
    here, so the assertion is that the assignment is written, not that
    it works — deleting the `nodes.save =` passed all 70 tests in this
    file's neighbourhood. What proves the behaviour is Chromium:
    three cells, `X` the last, `Save` must come back live because two
    cells differ from the one-cell baseline.
    """
    js = _builder(_page(client, _session(client, db, "coh-rebind")))

    handler = re.search(
        r'addEventListener\("click".*?\}, 0\);', js, re.S
    )
    assert handler, "the delegated click handler is gone"
    assert "nodes.save = placeSaveButton(nodes);" in handler.group(0), (
        "the click path drops the replacement Save on the floor"
    )
    # Twice: the click path above, and the render path in `refresh()`
    # that was always right. Counting rather than slicing, because the
    # two are not in a fixed order in the file.
    assert js.count("nodes.save = placeSaveButton(nodes);") == 2, (
        "expected the rebinding on both the render and the click path"
    )


def test_an_unsaved_rule_edit_is_guarded_on_every_discard_path(
    client: TestClient, db: Session
) -> None:
    """An unsaved cohort edit is DISCARDED by anything that rebuilds the
    panel or leaves the page, and was discarded silently.

    Measured before this guard: untick the row, tick a second one, or
    hit Search, and the edit vanished with nothing written to the DB and
    nothing said. Nothing auto-saves — the only write is the explicit
    POST — so the loss is real and total.

    Four paths ask the page's own question and then declare the
    navigation deliberate: the row checkbox, select-all, `Edit`, and the
    three `.exp-submit` bulk buttons. `beforeunload` catches what is
    left — `Search`, `Clear`, the pager, `Add new`.

    **A text guard, like its neighbours.** There is no JS runtime here,
    and the panel does not exist until a box is ticked. Chromium is the
    behavioural pin. What this file can do is make each claim fail on
    its own, so every assertion below is scoped to the ONE construct it
    is about — the cold read on the first draft found three mutations
    surviving because a bare substring matched a second, innocent
    occurrence elsewhere in the same script.
    """
    js = _builder(_page(client, _session(client, db, "coh-guard")))

    assert 'window.confirm("Discard unsaved changes?")' in js, (
        "no confirm on the in-page discard paths"
    )
    # The condition, not just the call: a guard that always returns
    # true is a guard that never asks, and reads identically otherwise.
    assert "if (!cohortDirty) return true;" in js, (
        "okToDiscardCohortEdit does not consult the dirty flag"
    )

    # Every discard path asks. Counted on the CALL SITE pattern, which
    # the function's own definition line does not match — `>= 3` against
    # the bare name passed with a call site deleted, because the
    # definition made up the difference.
    assert js.count("if (!okToDiscardCohortEdit())") >= 4, (
        "a discard path does not ask — expected the row checkbox, "
        "select-all, Edit and the bulk submits"
    )

    # Declining must leave the selection alone, or the confirm is
    # decoration: the panel would rebuild anyway and the edit still go.
    assert "restoreBox(t, !t.checked);" in js, (
        "declining still unticks the row"
    )
    # Select-all is tri-state, so declining has to restore the dash as
    # well as the tick — recomputed from the rows, not inverted.
    select_all = re.search(
        r"if \(t === selectAll\) \{.*?\n            \}", js, re.S
    )
    assert select_all and "syncSelectAll();" in select_all.group(0), (
        "declining still moves select-all"
    )
    # And a declined bulk submit must not post.
    assert "event.preventDefault();" in js, (
        "declining still fires the bulk action"
    )

    # The nav-away half.
    assert 'addEventListener("beforeunload"' in js, "no nav-away guard"
    assert "if (intentionalNav) return undefined;" in js, (
        "the deliberate navigations still warn"
    )

    # Save carries the flag, and carries it from the CREATION site —
    # `X` on the last rule cell destroys the Save inside that cell and
    # `placeSaveButton` builds a replacement, so a listener attached
    # once per panel did not reach it and Save raised "Leave site?".
    # Scoped to that function, because `intentionalNav = true;` also
    # appears on the Edit and bulk-submit paths and satisfied a
    # page-wide substring with this listener deleted.
    place = re.search(
        r"function placeSaveButton\(nodes\) \{.*?\n        \}", js, re.S
    )
    assert place and "intentionalNav = true;" in place.group(0), (
        "a rebuilt Save does not carry the intentional-nav flag"
    )

    # And the flag is cleared when the panel goes, or `beforeunload`
    # blocks every later navigation over an edit already discarded —
    # which is what the first draft did.
    render = re.search(r"function renderPanel\(\) \{.*?\n        \}", js, re.S)
    assert render and "cohortDirty = false;" in render.group(0), (
        "the dirty flag outlives the panel that held the edit"
    )


def test_a_mixed_selection_resets_the_builder_and_says_so(
    client: TestClient, db: Session
) -> None:
    """Author's call, 2026-09-16: mixed keeps today's behavior rather
    than growing per-box "(Multiple values)", which needs per-field
    comparison the whole-rule signature cannot do."""
    js = _builder(_page(client, _session(client, db, "coh-mixed")))

    assert "distinct" in js
    assert "nodes.mixed.hidden = (distinct <= 1)" in js, (
        "the mixed message does not follow the signature count"
    )
    assert re.search(r"\} else \{\s*setEditorToDefault\(nodes\.block\);", js), (
        "a mixed selection does not reset the builder"
    )


def test_the_split_modifier_has_a_rule_behind_it(
    client: TestClient, db: Session
) -> None:
    """The class the builder emits is inert without this. Read off the
    response rather than `base.html` on disk, because what ships is what
    the page carries."""
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
