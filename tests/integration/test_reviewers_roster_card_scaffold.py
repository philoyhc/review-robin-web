"""19P.1 rung 1 — the roster card and row expander render, inert.

Scaffold-first (`CLAUDE.md`): the roster card, its Unlock panel and the
row-selection expander land with real copy and layout and **nothing
wired**, so the shape can be looked at on the dev slot before any
behavior moves. The three cards they will eventually absorb are still
present and still live.

The suite has no JS runtime, so these assert the **mechanism** — markup,
classes, `disabled` attributes, the server-rendered counts — not the
appearance. 19L stated the same limit for the lobby bracket
(`guide/archive/segment_19L_ux_refinements.md:207-209`).
"""
from __future__ import annotations

import re

import pytest

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Reviewer, ReviewSession

R_CSV = b"ReviewerName,ReviewerEmail\nR1,r1@example.com\nR2,r2@example.com\n"


def _session(client: TestClient, db: Session, code: str) -> ReviewSession:
    client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _with_reviewers(
    client: TestClient, db: Session, code: str, csv: bytes = R_CSV
) -> ReviewSession:
    rs = _session(client, db, code)
    client.post(
        f"/operator/sessions/{rs.id}/reviewers/import",
        files={"file": ("r.csv", csv, "text/csv")},
        follow_redirects=False,
    )
    return rs


def _give_it_assignments(
    client: TestClient, db: Session, rs: ReviewSession
) -> None:
    """A reviewee roster plus generated assignments, so the confirm's
    optional clauses are reachable."""
    client.post(
        f"/operator/sessions/{rs.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nE1,e1@example.com\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{rs.id}/assignments/generate",
        data={"mode": "all_to_all"},
        follow_redirects=False,
    )


def _page(client: TestClient, rs: ReviewSession) -> str:
    response = client.get(f"/operator/sessions/{rs.id}/reviewers")
    assert response.status_code == 200
    return response.text


def _card(html: str) -> str:
    """The roster card's markup, so an assertion about it cannot be
    satisfied by the live cards lower down the same page."""
    match = re.search(r'id="roster-card".*?id="roster-unlock-panel"', html, re.S)
    assert match, "roster card not found"
    return match.group(0)


def test_the_roster_card_and_unlock_panel_render(client, db):
    html = _page(client, _with_reviewers(client, db, "rc1"))
    assert 'id="roster-card"' in html
    assert 'id="roster-unlock-panel"' in html
    assert 'id="roster-unlock-btn"' in html


def test_the_index_is_readouts_not_a_table(client, db):
    """The mockup's decision, and the fix for a real coupling: index row
    and expander in one table share `:first-child` / `:last-child`
    padding rules, so the two could not be spaced independently."""
    card = _card(_page(client, _with_reviewers(client, db, "rc2")))
    assert "<table" not in card, card
    assert 'class="roster-readouts"' in card


def test_populated_columns_carry_server_rendered_counts(client, db):
    """`col_data` is a presence map and never held counts, so these come
    from `slot_row_count` — assert the number, which is what
    distinguishes a count from a flag."""
    card = _card(_page(client, _with_reviewers(client, db, "rc3")))
    assert "Name (2)" in card, card
    assert "Email (2)" in card, card


def test_counts_are_per_column_not_the_roster_total(client, db):
    """A half-filled column reads its own number. The cheap wrong
    implementation — reusing `total_row_count` for every chip — passes
    the test above and fails this one."""
    rs = _with_reviewers(
        client,
        db,
        "rc4",
        b"ReviewerName,ReviewerEmail,ReviewerTag1\n"
        b"R1,r1@example.com,alpha\n"
        b"R2,r2@example.com,\n"
        b"R3,r3@example.com,gamma\n",
    )
    card = _card(_page(client, rs))
    assert "Name (3)" in card, card
    # Two of three rows carry a tag; the blank one must not count.
    assert "Tag 1 (2)" in card, card
    assert "Tag 1 (3)" not in card, card


def test_populated_columns_use_the_session_friendly_label(client, db):
    """The chip reads the same `field_labels.resolve_pair` as the preview
    table's own column headers, so the index cannot disagree with the
    table beneath it."""
    rs = _with_reviewers(
        client,
        db,
        "rc5",
        b"ReviewerName,ReviewerEmail,ReviewerTag1\nR1,r1@example.com,alpha\n",
    )
    client.post(
        f"/operator/sessions/{rs.id}/reviewers/field-labels",
        data={"tag_1": "Tutor"},
        follow_redirects=False,
    )
    card = _card(_page(client, rs))
    assert "Tutor (1)" in card, card
    assert "Tag 1 (1)" not in card, card


def test_an_unpopulated_column_gets_no_chip(client, db):
    """Presence still gates which chips appear; the count says how many.
    Presence is *derived* from the count rather than queried again."""
    card = _card(_page(client, _with_reviewers(client, db, "rc6")))
    assert "Tag 1" not in card, card
    assert "Tag 2" not in card, card


def test_every_unwired_unlock_control_is_inert(client, db):
    """Scaffold-first means inert controls, not merely greyed ones.

    Narrowed at 19P.1 rung 3a, which wired the tag-labels editor: the
    panel is no longer uniformly inert, so this covers what 3b and 3c
    have yet to wire. The labels editor is excised by its own card
    rather than by control name — a name list would silently stop
    covering anything the partial renames.
    """
    html = _page(client, _with_reviewers(client, db, "rc7"))
    # Bounded by the Lock control that now follows the panel, not by the
    # <script> that follows that — the old lookahead swept the control
    # into the panel's scope the moment it moved there, and the control
    # is deliberately live. Guarded below rather than trusted.
    # Div-balanced, not bounded by a lookahead on `.roster-card-actions`.
    # That control has two homes — after the panel when closed, INSIDE it
    # when open — so the lookahead stopped describing a boundary the
    # moment the panel could arrive open.
    scope = _panel(html)
    assert 'id="roster-unlock-btn"' not in scope, (
        "the scope swept in the Lock control, which is live by design"
    )
    # Each rung wires one card, so each rung adds one excision here. The
    # cards are removed by their own markers rather than by naming the
    # controls inside them: a control list stops covering anything the
    # moment a card renames one.
    labels_card = _div_block(scope, '<div class="card field-labels-editor">')
    assert labels_card, "the wired labels editor is not in the panel"
    scope = scope.replace(labels_card, "")
    assert "field-labels-editor" not in scope, "the excision missed a copy"

    danger = re.search(
        r'<section[^>]*aria-labelledby="reviewers-danger-h"[^>]*>'
        r'.*?</section>', scope, re.S,
    )
    assert danger, "the wired Danger Zone is not in the panel"
    scope = scope.replace(danger.group(0), "")
    assert "reviewers-danger-h" not in scope, "the excision missed a copy"

    controls = re.findall(r"<(?:button|input)\b[^>]*>", scope)
    assert len(controls) >= 2, (
        f"only {len(controls)} unwired controls left to check; this test "
        "passes trivially if the excision took too much"
    )
    # Match the ATTRIBUTE, not the substring: an `aria-label="… (scaffold)"`
    # must not be able to satisfy this, which is how an earlier version of
    # this assertion passed against an un-disabled control.
    undisabled = [
        c for c in controls
        if not re.search(r"(?:^|\s)disabled(?:[=\s>]|$)", c)
    ]
    assert not undisabled, f"wired controls in a scaffold panel: {undisabled}"


def test_the_replace_confirm_is_one_tick_naming_every_loss(client, db):
    """One panel must not give two accounts of one destruction. The
    reverted build split this in two and dropped the assignments clause
    the Danger Zone confirm three elements away still named.

    The roster must actually HAVE assignments for this to test the
    naming: on a bare roster every optional clause is suppressed, so the
    label under test is the shortest branch and the regression this test
    is named for would pass it unchanged.
    """
    rs = _with_reviewers(client, db, "rc8")
    _give_it_assignments(client, db, rs)
    html = _page(client, rs)
    # Scoped to the upload card's own <section>, not to whatever card
    # happens to follow it — the panel's column order is a layout choice
    # and a test should not pin it by accident.
    upload = re.search(r'id="scaffold-upload-h".*?</section>', html, re.S)
    danger = re.search(r'id="reviewers-danger-h".*?</section>', html, re.S)
    assert upload and danger, "scaffold panel columns not found"
    ticks = re.findall(r'<input[^>]*type="checkbox"[^>]*>', upload.group(0))
    assert len(ticks) == 1, f"expected one replace confirm, got {len(ticks)}"
    # Vacuity guard: prove the clause is reachable at all before asserting
    # the two confirms agree about it.
    assert "assignment" in danger.group(0), (
        "fixture produced no assignments, so this asserts nothing"
    )
    assert "assignment" in upload.group(0), (
        "the replace confirm drops a loss the Danger Zone confirm names"
    )


def test_the_replace_confirm_is_absent_on_an_empty_roster(client, db):
    """Suppressed at zero, as the live card already does — rather than
    reading "replace the existing 0 reviewers"."""
    html = _page(client, _session(client, db, "rc9"))
    # Scoped to the upload card's own <section>, not to whatever card
    # happens to follow it — the panel's column order is a layout choice
    # and a test should not pin it by accident.
    upload = re.search(r'id="scaffold-upload-h".*?</section>', html, re.S)
    assert upload, "upload column not found"
    assert "replace the existing" not in upload.group(0), upload.group(0)
    # The card itself still renders: it is informational, and every state
    # it renders in must be whole.
    assert 'id="roster-card"' in html


def test_only_the_upload_card_is_left_to_absorb(client, db):
    """Rung 1 added a surface and retired nothing; rung 3 retires them
    one at a time. Two of the three are in the panel now — the tag
    labels at 3a, the Danger Zone at 3b — so this counts down rather
    than pinning a fixed three.

    Was `..._three_cards_it_will_absorb_are_still_live`.
    """
    rs = _with_reviewers(client, db, "rc10")
    html = _markup(_page(client, rs))

    # Still below the table, still to move at 3c.
    assert 'id="upload-csv"' in html

    # Already moved. NOT the bare substring `danger-zone`: `base.html`'s
    # stylesheet ships on every response and mentions it eight times, so
    # that needle is true of every page in the app with or without the
    # card. Match the card's own class attribute instead.
    # (`test_reserved_shade.py` warns about exactly this trap; 19J.5 hit
    # it three times, and 19P.1 three more.)
    panel = _panel(html)
    # Scoped two ways, because a bare `"danger-zone" not in ...` fails
    # both: the card kept that class when it moved (it is the only reach
    # for the amber warning framing), and `base.html`'s inline
    # stylesheet mentions `.danger-zone` in a COMMENT, so the word is on
    # every page in the app. `_markup()` strips the stylesheet; removing
    # the panel leaves what is below the table; and the needle is the
    # class ATTRIBUTE, not the word.
    below = _markup(html).replace(panel, "")
    assert 'class="card danger-zone"' not in below, (
        "the retired Danger Zone card is back below the table"
    )
    assert 'aria-labelledby="reviewers-danger-h"' in panel, (
        "the Danger Zone is neither below the table nor in the panel"
    )
    # The live editor's own route, not a string the scaffold prints —
    # deleting the include outright must fail this.
    assert f"/operator/sessions/{rs.id}/reviewers/field-labels" in panel


def test_unlock_is_suppressed_not_disabled_when_locked(client, db):
    """A locked page must carry no roster-mutating control at all.

    `test_field_labels_editor_routes` asserts a locked Reviewers page
    contains no "Save labels" anywhere — the real editor *suppresses*
    that button rather than disabling it, and the Unlock panel holds one.
    """
    rs = _with_reviewers(client, db, "rc11")
    # Forge the state to trip the lifecycle gate, as the rest of the
    # suite does — the full activate dance is not what is under test.
    rs.status = "ready"
    db.flush()
    html = _page(client, rs)
    assert 'id="roster-unlock-btn"' not in html
    assert 'id="roster-unlock-panel"' not in html
    assert "Save labels" not in html
    # The readouts stay — they are informational, not a mutation.
    assert 'class="roster-readouts"' in html


def test_the_row_expander_script_is_gated_on_selectable(client, db):
    """Selection and the expander are one affordance: where rows cannot
    be selected the script must not run."""
    rs = _with_reviewers(client, db, "rc12")
    html = _page(client, rs)
    # The panel is built in JS, so what the server ships is the builder.
    # Assert the strings it will stamp onto the injected row, which is
    # the most a suite with no JS runtime can see.
    assert 'tr.id = "reviewers-row-expander"' in html, "expander builder absent"
    assert '"session-expander session-expander-bracketed"' in html

    edit_id = re.search(r'id="reviewer-row-(\d+)"', html).group(1)
    editing = client.get(
        f"/operator/sessions/{rs.id}/reviewers?edit_id={edit_id}"
    ).text
    # Vacuity guard: the param is `edit_id`, and an unrecognized name is
    # ignored silently rather than erroring — so a typo here would leave
    # the page in its normal state and the assertions below would pass
    # against the wrong render. Prove edit mode is actually on first.
    assert 'name="name"' in editing, "edit mode did not engage"
    # Row selection is genuinely withdrawn in edit mode...
    assert 'class="reviewer-select"' not in editing
    # ...so the expander builder goes with it.
    assert 'tr.id = "reviewers-row-expander"' not in editing


def test_rows_carry_their_status_for_the_panel_to_read(client, db):
    """The status-aware rule (which actions a selection admits) reads the
    row's state, not its rendered pill markup."""
    rs = _with_reviewers(client, db, "rc13")
    html = _page(client, rs)
    # Both attributes on one row tag, in any order. The first version
    # required them ADJACENT, which was incidental — adding a class
    # between them broke a test whose claim is only that the row carries
    # its status.
    row = re.search(r"<tr\b[^>]*id=\"reviewer-row-\d+\"[^>]*>", html)
    assert row, "no reviewer rows rendered"
    assert 'data-status="active"' in row.group(0), "rows carry no data-status"


def test_the_panel_counts_against_the_rendered_window(client, db):
    """`N of M selected`, where M is the rows select-all can reach — not
    the whole roster.

    19I Item 4 settled this for the existing selection pill, whose own
    comment says why: the rendered window is what makes the
    cap-versus-match gap legible beside the "Showing N of M" hint. A
    panel using `total_row_count` would contradict the pill sitting on
    the same page under a filter.
    """
    html = _page(client, _with_reviewers(client, db, "rc14"))
    assert "rows().length +" in html, "panel counts against the wrong pool"
    assert "{{ total_row_count }} + \" selected" not in html


def test_the_panel_survives_a_sort(client, db):
    """`_rrwApplySort` reorders every child of `tbody.rrw-rows`. The panel
    has no sort cells, so it compares null and strands at the bottom —
    and its presence when `rrwOriginalIndex` is first stamped would shift
    every index after it. It is removed before the sort and re-anchored
    after, on the capture phase so it runs first."""
    html = _page(client, _with_reviewers(client, db, "rc15"))
    assert '.rrw-sort-btn' in html, "no sort hook"
    match = re.search(
        r'table\.addEventListener\("click".*?\}, true\);', html, re.S
    )
    assert match, "sort handler is not on the capture phase"
    assert "panel.remove()" in match.group(0), match.group(0)


def test_a_server_restored_selection_renders_its_panel(client, db):
    """The bulk routes redirect through `_redirect_keeping_selection`,
    which carries the acted-on ids as `?selected=`; the server re-checks
    those boxes. Without an init render they would have neither rails nor
    a panel until the operator toggled something."""
    rs = _with_reviewers(client, db, "rc16")
    html = _page(client, rs)
    row_id = re.search(r'id="reviewer-row-(\d+)"', html).group(1)
    restored = client.get(
        f"/operator/sessions/{rs.id}/reviewers?selected={row_id}"
    ).text
    # Vacuity guard: prove the server actually restored the tick, or the
    # assertion below would pass against an unselected page.
    assert re.search(
        r'value="%s"[^>]*checked' % row_id, restored
    ), "server did not restore the selection"
    # The script seeds tick order from the restored boxes and renders once.
    assert 'if (box && box.checked) tickOrder.push(row.id);' in restored
    assert re.search(r'render\(\);\s*\}\)\(\);', restored), \
        "no init render"


def test_the_panel_renders_no_pill(client, db):
    """`spec/ui_elements.md` .session-row-selected: "**The panel is a
    pill-free zone**: its fill resolves to `--status-info-bg`'s primitive,
    so a `.pill-count` rendered inside it reopens the collision one storey
    down."

    Both tokens resolve to `--blue-pale` light and `--blue-abyss` dark, so
    a pill in there is not merely off-convention — it is invisible. The
    lobby renders the same count as bare text.
    """
    html = _page(client, _with_reviewers(client, db, "rc17"))
    builder = re.search(
        r'function build\(sel\).*?return tr;', html, re.S
    )
    assert builder, "panel builder not found"
    assert "pill-count" not in builder.group(0), builder.group(0)
    assert "pill" not in builder.group(0), builder.group(0)
    assert "row-expander-count" in builder.group(0)


def test_tick_order_prunes_on_untick_and_rebuilds_on_select_all(client, db):
    """The anchor is a function of the tick order, and 19L settled the
    rule — so the maintenance has to match the lobby's
    (`sessions_list.html:596-614`), which splices on untick and rebuilds
    wholesale on select-all. A stale entry for a row that was unticked and
    re-ticked anchors the panel at that row instead of the last one.

    No JS runtime in the suite, so this asserts the mechanism in the
    shipped source — the same limit the geometry tests state.
    """
    html = _page(client, _with_reviewers(client, db, "rc18"))
    # Anchored on the handler's own `render();` — a bare `});` stops at
    # the inner filter callback's close and captures half the body.
    handler = re.search(
        r'body\.addEventListener\("change".*?render\(\);\s*\}\);', html, re.S
    )
    assert handler, "row change handler not found"
    # The filter runs unconditionally; only the push is gated on checked.
    body = handler.group(0)
    filter_at = body.index("tickOrder = tickOrder.filter")
    push_at = body.index("tickOrder.push")
    gate_at = body.index("if (event.target.checked)")
    assert filter_at < gate_at < push_at, (
        "untick does not prune the tick order"
    )
    select_all = re.search(
        r'selectAll\.addEventListener\("change".*?render, 0\);\s*\}\);',
        html, re.S
    )
    assert select_all, "select-all handler not found"
    assert "rows().map" in select_all.group(0), (
        "select-all does not rebuild the tick order"
    )


def test_the_unlock_panel_puts_the_edit_cards_left_and_upload_right(client, db):
    """Left column: `Reviewer tag labels` over `Danger Zone`, stacked.
    Right column: `Upload Reviewers`. Author's arrangement, so it is
    pinned — a refactor that reflowed the panel would otherwise undo it
    silently.

    Asserts DOM order and stack membership, which is what the markup
    decides; the column widths are the CSS grid's and are asserted as a
    rule, not an effect.
    """
    html = _page(client, _with_reviewers(client, db, "rc19"))
    # Div-balanced, not `.*?(?=<script>)`. Rung 3a put a real partial in
    # the panel and the partial ships its own dirty-check script, so the
    # lookahead truncated the scope after the FIRST card and the two
    # order assertions below raised rather than failing. A boundary that
    # moves when the contents change is not a boundary.
    body = _panel(html)

    # `scaffold-labels-h` went with the hand-copied markup at rung 3a;
    # the partial renders a plain <h2> under its own card class.
    labels = body.index('class="card field-labels-editor"')
    danger = body.index('id="reviewers-danger-h"')
    upload = body.index('id="scaffold-upload-h"')
    assert labels < danger < upload, (
        "expected labels, then danger zone, then upload"
    )

    # The first two share the stack; upload is the grid's second child.
    # Div-balanced like the panel scope above it. This was
    # `.*?\n        </div>` — a boundary anchored on eight spaces of
    # indentation, which resolved correctly only because nothing in the
    # stack happened to close at that depth. The panel boundary two
    # lines up had already broken that way once.
    stack_html = _div_block(body, '<div class="unlock-stack">')
    assert stack_html, "left-column stack not found"
    assert 'class="card field-labels-editor"' in stack_html
    assert 'id="reviewers-danger-h"' in stack_html
    assert 'id="scaffold-upload-h"' not in stack_html, (
        "upload belongs in the right column, not the stack"
    )


def test_the_replace_confirm_is_set_apart_from_the_file_input(client, db):
    """A confirm flush against the input it gates reads as that input's
    caption. Geometry, so this asserts the rule rather than its effect —
    the suite has no layout engine."""
    html = _page(client, _with_reviewers(client, db, "rc20"))
    rule = re.search(r"\.confirm-label \{([^}]*)\}", html)
    assert rule, ".confirm-label rule not found"
    assert "margin: var(--space-4) 0 0" in rule.group(1), rule.group(1)


def test_the_panel_does_not_compound_the_base_card_margin(client, db):
    """The base `.card` carries `margin-bottom: 20px`, which
    `body.ui-v2 .card` deliberately does not override. Inside a gapped
    container that margin COMPOUNDS with the gap — the two stacked cards
    sat 36px apart against the page's 20px until this was zeroed, exactly
    as `.page-grid`, `.bottom-grid` and `.subcard-row` already do.

    Geometry, so this asserts the rules rather than their effect; the
    measured result is confirmed in a browser.
    """
    html = _page(client, _with_reviewers(client, db, "rc21"))
    assert re.search(
        r"\.unlock-panel \.card \{[^}]*margin-bottom:\s*0", html
    ), "the base card margin is not zeroed inside the panel"
    # And the gap the page uses between cards, not the token scale's 16.
    for selector in (r"\.unlock-panel \{", r"\.unlock-stack \{"):
        rule = re.search(selector + r"([^}]*)\}", html)
        assert rule, selector
        assert "gap: 20px" in rule.group(1), rule.group(1)


def test_the_hidden_unlock_panel_is_actually_hidden(client, db):
    """`hidden` is a UA `display: none`, and ANY author `display` beats
    it — so `.unlock-panel { display: grid }` silently defeated the
    attribute and the panel rendered open on load, with the toggle only
    changing the button's label.

    The markup assertion that `hidden` is present passed throughout,
    because the suite has no layout engine and the attribute was always
    there. So this asserts the guard `base.html` already applies to
    `.btn[hidden]` (`:713`); the collapse itself is confirmed in a
    browser.
    """
    html = _page(client, _with_reviewers(client, db, "rc22"))
    assert re.search(
        r"\.unlock-panel\[hidden\] \{[^}]*display:\s*none", html
    ), "an author display rule would defeat the hidden attribute"
    # And the attribute is on the element, which is the half that always held.
    assert re.search(
        r'id="roster-unlock-panel"[^>]*hidden', html
    ), "the panel does not carry the hidden attribute"


def test_the_lock_control_ships_as_the_cards_last_child(client, db):
    """Collapsed is the served state, so the markup puts the control at
    the card's foot. Open, the script moves it into the right column —
    see the test below."""
    html = _page(client, _with_reviewers(client, db, "rc23"))
    card = re.search(r'id="roster-card".*?(?=<!-- |\n  <div class="card-columns")',
                     html, re.S)
    assert card, "roster card not found"
    body = card.group(0)
    panel = body.index('id="roster-unlock-panel"')
    actions = body.index('class="roster-card-actions"')
    assert panel < actions, (
        "the control must follow the panel, so it is the card's foot "
        "when the panel is hidden"
    )


def test_the_upload_card_sits_in_its_own_right_column_stack(client, db):
    """A stack, not a second grid row. A grid row begins below the TALLER
    column, which would drop the Lock control to the panel's foot —
    measured at 125px under the upload card before this — rather than
    directly beneath the card it acts on."""
    html = _page(client, _with_reviewers(client, db, "rc24"))
    right = re.search(
        r'<div class="unlock-stack unlock-right">.*?id="scaffold-upload-h"',
        html, re.S
    )
    assert right, "upload card is not inside a right-column stack"


def test_the_lock_control_moves_between_its_two_homes(client, db):
    """One element, two homes. The panel is `display: none` when closed,
    so a control living inside it would vanish with it; rendering a
    second copy outside is how two copies of one control drift apart.
    The toggle moves the node instead."""
    html = _page(client, _with_reviewers(client, db, "rc25"))
    handler = re.search(
        r'btn\.addEventListener\("click".*?\}\);', html, re.S
    )
    assert handler, "toggle handler not found"
    body = handler.group(0)
    assert "card.appendChild(actions)" in body, body
    assert '.unlock-right").appendChild(actions)' in body, body



def test_a_zero_match_filter_still_offers_the_control_that_clears_it(client, db):
    """19P.1 rung 2a moved the filter strip INSIDE the preview-table card,
    which was gated on the FILTERED row list. A search matching nothing
    therefore removed the card — and with it the `Clear` link and the
    search box — leaving the operator reading "No reviewers match" with
    no way out but the URL bar.

    The card is now gated on the roster having rows at all; only the
    table is gated on the filtered list.
    """
    rs = _with_reviewers(client, db, "rc26")
    html = client.get(
        f"/operator/sessions/{rs.id}/reviewers?q=nothingmatchesthis"
    ).text
    # Vacuity guard: prove the filter really did match nothing.
    assert "No reviewers match the current filter." in html
    assert 'id="reviewers-table"' not in html
    # ...and the way out is still on screen.
    assert ">Clear</a>" in html, "a zero-match filter hid its own Clear"
    assert 'name="q"' in html, "a zero-match filter hid the search box"


# `base.html` ships the whole stylesheet inline on every response, so a
# bare `"some-class" in html` is satisfied by the CSS that DEFINES the
# class on every page in the app. Anything asserting about markup strips
# the style block first.
def _markup(html: str) -> str:
    return re.sub(r"<style\b.*?</style>", "", html, flags=re.S)


# A roster with a tag column and more rows than one page holds, so the
# left pane actually HAS its three tenants to find. The two-row `R_CSV`
# fixture renders that pane empty — no chip row (no tags), no pager (one
# page), no count line (nothing withheld) — which is how the first
# version of this test passed while proving nothing about placement.
_PAGE_SIZE = 200
R_CSV_TAGGED = b"ReviewerName,ReviewerEmail,ReviewerTag1.Tutor\n" + b"".join(
    f"R{n},r{n}@example.com,T{n % 3}\n".encode()
    for n in range(1, _PAGE_SIZE + 61)
)


def _left_pane(html: str) -> str:
    """The left pane's markup, balanced.

    `.*?</div>` would stop at the first close tag, which is inside the
    pager cluster's own nested divs — so it truncates before the count
    line exactly when the pane is full enough to be worth checking.
    """
    start = html.index('<div class="toolbar-pane toolbar-left">')
    depth = 0
    for m in re.finditer(r"<div\b|</div>", html[start:]):
        depth += 1 if m.group(0) != "</div>" else -1
        if depth == 0:
            return html[start:start + m.end()]
    raise AssertionError("left pane never closes")


def test_the_filter_strip_sits_in_the_tables_toolbar(client, db):
    """Right pane the filter, left pane what the table is showing —
    `Show columns:`, the pager and the count line, in the order
    `tests/unit/test_pager.py` pins."""
    rs = _with_reviewers(client, db, "rc27", csv=R_CSV_TAGGED)
    html = _markup(client.get(f"/operator/sessions/{rs.id}/reviewers").text)

    toolbar = re.search(
        r'<div class="table-card-toolbar is-split">.*?id="reviewers-table"',
        html,
        re.S,
    )
    assert toolbar, "table-card toolbar not found"
    body = toolbar.group(0)
    assert body.index("toolbar-left") < body.index("toolbar-right")
    assert 'name="q"' in body, "the search box is not in the toolbar"
    assert ">Add new</a>" in body, "`Add new` is not in the toolbar"

    # Unfiltered: the chip row and the pager. The count line is `None`
    # here by design — `views.preview_count_line` returns nothing unless
    # a filter is on, and that same flag sets `pager = None` in
    # `_shared.setup_window`. So the pager and the count line NEVER
    # render together; the left pane's three tenants are really two
    # plus an alternative, and each has to be checked where it appears.
    left = _left_pane(html)
    assert left.strip() != (
        '<div class="toolbar-pane toolbar-left"></div>'
    ), "left pane is empty — this fixture proves nothing"
    assert "col-chip-row" in left, "the column chips are not in the left pane"
    assert "table-pager" in left, "the pager is not in the left pane"
    assert "table-showing-hint" not in left, (
        "vacuity: an unfiltered view should have no count line"
    )

    # Filtered: the chip row and the count line, and no pager.
    filtered = _markup(
        client.get(f"/operator/sessions/{rs.id}/reviewers?q=r1").text
    )
    fleft = _left_pane(filtered)
    assert "table-showing-hint" in fleft, (
        "the count line is not in the toolbar's left pane"
    )
    assert "col-chip-row" in fleft
    assert "table-pager" not in fleft, "a filtered view should have no pager"

    # ...and the count line did not leak into the right pane.
    assert "table-showing-hint" not in filtered.split("toolbar-right")[1]


def test_the_toolbar_panes_are_not_cards(client, db):
    """They spend none of a card's signals, and naming them `card` both
    misleads a reader and breaks the shared `_table_card` probe, which
    finds the enclosing card by scanning back for `<div class="card`."""
    html = _markup(_page(client, _with_reviewers(client, db, "rc28")))
    panes = re.findall(r'<div class="([^"]*\btoolbar-pane\b[^"]*)"', html)
    assert len(panes) == 2, f"expected two panes, found {panes}"
    for classes in panes:
        assert "card" not in classes.split(), (
            f"a toolbar pane is styled as a card: {classes!r}"
        )


def test_an_empty_roster_still_offers_add_new(client, db):
    """`Add new` moved into the preview-table card, which was gated on
    the roster having rows. A brand-new session therefore had no way to
    type in its first reviewer at all — CSV upload or the URL bar.

    Before the move `Add` lived in the always-rendered `Operator
    actions` card, so the gate did not reach it. The three sibling
    rosters still render theirs unconditionally.
    """
    rs = _session(client, db, "rc29")
    html = client.get(f"/operator/sessions/{rs.id}/reviewers").text
    # Vacuity guard: prove the roster really is empty.
    assert "No reviewers yet." in html
    assert 'id="reviewers-table"' not in html
    assert "?add=1" in html, "an empty roster hid its only `Add new`"
    assert ">Add new</a>" in html


def test_an_empty_roster_is_not_told_it_filtered_them_out(client, db):
    """Two different causes, two different sentences: a filter that
    matched nothing is the operator's own doing and clearable, an empty
    roster is a starting point."""
    rs = _session(client, db, "rc30")
    html = client.get(f"/operator/sessions/{rs.id}/reviewers").text
    assert "No reviewers match the current filter." not in html
    assert "No reviewers yet." in html


def test_the_moved_filter_locks_while_a_row_is_being_edited(client, db):
    """15F PR 3: the filter greys out (`is-locked`) during an edit so a
    stray click on `Search` or `Clear` cannot GET the half-typed row
    away. The strip moved out of `.operator-actions-card`, where the
    only rule for that class lives, so the class needs a rule that
    reaches its new home or the lock is decorative.
    """
    rs = _with_reviewers(client, db, "rc31")
    listing = _page(client, rs)
    rid = re.search(r'id="reviewer-row-(\d+)"', listing).group(1)
    html = client.get(f"/operator/sessions/{rs.id}/reviewers?edit_id={rid}").text
    # Vacuity guard: `edit_id` typo'd is ignored silently, leaving the
    # page in its normal state — prove edit mode actually engaged.
    assert 'name="name"' in html, "edit mode did not engage"

    # The actions card still has a form of the same class (it keeps the
    # selection-driven buttons until rung 2b), and it comes first in
    # source — so find the one in the toolbar, not merely the first.
    moved = re.search(
        r'<div class="toolbar-pane toolbar-right">\s*'
        r'<form[^>]*class="(operator-actions-filter[^"]*)"',
        _markup(html),
    )
    assert moved, "moved filter form not found in the toolbar"
    assert "is-locked" in moved.group(1), "the moved filter does not lock"
    # ...and a rule that actually reaches it, not just the class.
    assert re.search(
        r"\.toolbar-right \.operator-actions-filter\.is-locked \{", html
    ), "`is-locked` on the moved filter matches no rule"


def test_only_reviewers_splits_the_shared_table_toolbar(client, db):
    """`.table-card-toolbar` is shared by seven templates and only
    Reviewers has panes. The two-column grid therefore rides a modifier:
    turning the shared class into a grid would make the other six
    templates' direct children grid items in a grid they were never laid
    out for — Observers' toolbar holds the pager and nothing else, which
    would right-align inside the LEFT half instead of across the card.
    """
    rs = _with_reviewers(client, db, "rc32")
    reviewers = client.get(f"/operator/sessions/{rs.id}/reviewers").text
    assert '<div class="table-card-toolbar is-split">' in _markup(reviewers)

    # The shared rule stays flex; only the modifier is a grid.
    shared = re.search(
        r"body\.ui-v2 \.table-card-toolbar \{(.*?)\}", reviewers, re.S
    )
    assert shared, "shared .table-card-toolbar rule is gone"
    assert "display: flex" in shared.group(1), (
        "the shared toolbar rule became a grid; six other pages use it"
    )

    for page in ("reviewees", "observers"):
        other = client.get(f"/operator/sessions/{rs.id}/{page}")
        if other.status_code != 200:
            continue
        assert "table-card-toolbar is-split" not in _markup(other.text), (
            f"{page} picked up the Reviewers-only split toolbar"
        )


def test_full_width_guidance_runs_its_prose_in_two_columns(client, db):
    """Reviewers leads its page with the guidance card at full width,
    where one measure runs to ~150 characters. The other six placements
    sit in a half-width column, where two columns would be two
    ~30-character ribbons — so the page opts in rather than the rule
    applying everywhere the class does.
    """
    rs = _with_reviewers(client, db, "rc33")
    html = client.get(f"/operator/sessions/{rs.id}/reviewers").text
    assert "page-guidance-wide" in _markup(html), "Reviewers did not opt in"
    assert re.search(
        r"\.page-guidance-wide > \.page-guidance-body \{[^}]*column-count: 2",
        html,
        re.S,
    ), "the two-column rule the template comment promises does not exist"

    # A half-width placement must not pick it up.
    other = client.get(f"/operator/sessions/{rs.id}/reviewees")
    if other.status_code == 200:
        other_markup = _markup(other.text)
        assert "page-guidance" in other_markup, "vacuity: no guidance card"
        assert "page-guidance-wide" not in other_markup


def test_the_moved_filters_buttons_keep_their_gap_from_the_search_box(
    client, db
):
    """The gap now comes from the unscoped base, not from this scope.

    It was lost twice by moving the markup — `.operator-actions-card
    .filter-actions` supplied `margin-top: 12px` and nothing followed
    the strip into the toolbar. The base rule exists so a third move
    cannot repeat that, so what this pins has moved with it: the BASE
    carries the margin, and `.toolbar-right` must not re-declare it.

    Re-declaring would pass a naive "is the margin there" check while
    hiding the base rule doing its job — and would be back to a
    per-scope copy, which is the bug.
    """
    rs = _with_reviewers(client, db, "rc34")
    html = _page(client, rs)

    # Vacuity guard. The page renders TWO `<div class="filter-actions">`
    # — the actions card still has one, and it comes first in source — so
    # `'<div class="filter-actions">' in html` is satisfied by the card's
    # and would pass with the toolbar's deleted outright (verified by
    # mutation). Find the one inside the right pane, as
    # `test_the_moved_filter_locks_while_a_row_is_being_edited` does.
    moved = re.search(
        r'<div class="toolbar-pane toolbar-right">.*?'
        r'<div class="(filter-actions)"',
        _markup(html),
        re.S,
    )
    assert moved, "the filter's button row is not in the toolbar"

    # The base carries the two declarations two bugs were spent
    # rediscovering. Matched on the bare selector at line start so the
    # scoped rules below cannot satisfy it.
    base = re.search(r"\n\s*\.filter-actions \{(.*?)\}", html, re.S)
    assert base, "no unscoped `.filter-actions` base rule"
    assert re.search(r"margin-top:\s*var\(--space-3\)", base.group(1)), (
        f"the base lost its 12px gap: {base.group(1)!r}"
    )
    assert re.search(r"align-items:\s*center", base.group(1)), (
        f"the base lost its cross-axis alignment: {base.group(1)!r}"
    )

    # ...and this scope narrows the button gap only. A `margin-top`
    # here would mean the per-scope copy is back.
    scoped = re.search(
        r"body\.ui-v2 \.toolbar-right \.filter-actions \{(.*?)\}", html, re.S
    )
    assert scoped, "no rule narrowing the moved filter's button row"
    assert "margin-top" not in scoped.group(1), (
        "`.toolbar-right` re-declares `margin-top`, hiding the base rule: "
        f"{scoped.group(1)!r}"
    )
    assert re.search(r"gap:\s*var\(--space-2\)", scoped.group(1)), (
        "the half-width pane lost its tighter button gap"
    )


def _toolbar_right(html: str) -> str:
    """The right pane's markup, div-balanced.

    `split(...)[1]` returns the rest of the DOCUMENT, so an assertion
    reading "in the toolbar" would actually mean "at or after it" —
    first-match semantics hide that until something moves.
    """
    marker = '<div class="toolbar-pane toolbar-right">'
    start = html.index(marker)
    depth, i = 1, start + len(marker)
    for tag in re.finditer(r"<div\b|</div>", html[i:]):
        depth += 1 if tag.group(0) != "</div>" else -1
        if depth == 0:
            return html[start:i + tag.end()]
    raise AssertionError("the right pane never closes")


def test_the_toolbar_controls_land_on_the_table_not_the_top_of_the_page(
    client, db
):
    """Reported from the dev slot: `Clear`, `Add new` and `Search` threw
    the operator to the very top of the page, away from the rows they
    were filtering.

    Each reloads the page, and a reload with no fragment lands at the
    top. The pager solved this at 19J.8 — `#reviewers-table-card` sits
    on the table card, which carries `scroll-margin-top` — so `Clear`
    and `Search` take the SAME anchor and land where a page turn does.

    `Add new` does NOT: see the test below.
    """
    rs = _with_reviewers(client, db, "rc35")
    html = _markup(client.get(
        f"/operator/sessions/{rs.id}/reviewers?q=R1"
    ).text)

    # Vacuity guard: `Clear` renders only while a filter is active.
    assert ">Clear</a>" in html, "the filter is not active on this render"
    right = _toolbar_right(html)

    form = re.search(r'<form[^>]*method="get"[^>]*>', right, re.S)
    assert form, "the toolbar's filter form is missing"
    assert 'action="/operator/sessions/' in form.group(0)
    assert re.search(r'action="[^"]*#reviewers-table-card"', form.group(0)), (
        f"`Search` submits without the anchor: {form.group(0)!r}"
    )

    clear = re.search(r'<a[^>]*>\s*Clear</a>', right, re.S)
    assert clear, "`Clear` is not in the toolbar"
    assert re.search(r'href="[^"]*#reviewers-table-card"', clear.group(0)), (
        f"`Clear` lands at the top of the page: {clear.group(0)!r}"
    )


def test_add_new_lands_on_the_editor_not_the_table(client, db):
    """`Add new` enters edit mode, and the editor is SPLIT across two
    cards: the blank row is in the table, the heading and Save / Cancel
    are in the card above it.

    Landing on the table card therefore showed the row to fill in with
    Save 84px ABOVE the viewport — measured in Chromium at both 800px
    and 1000px tall. A row to type into and no visible way to save it is
    worse than the jump this segment set out to fix, so this one control
    takes the editor's anchor instead. Rung 2b rehomes the block and can
    revisit.
    """
    rs = _with_reviewers(client, db, "rc36")
    html = _markup(client.get(f"/operator/sessions/{rs.id}/reviewers").text)
    right = _toolbar_right(html)

    add = re.search(r'<a[^>]*>\s*Add new</a>', right, re.S)
    assert add, "`Add new` is not in the toolbar"
    assert 'href="' in add.group(0), "vacuity: the disabled variant has no href"
    assert re.search(r'href="[^"]*#reviewers-row-editor"', add.group(0)), (
        f"`Add new` lands somewhere other than the editor: {add.group(0)!r}"
    )

    # ...and the anchor it names exists once edit mode is on, or it is a
    # fragment pointing at nothing.
    editing = _markup(
        client.get(f"/operator/sessions/{rs.id}/reviewers?add=1").text
    )
    assert 'id="reviewers-row-editor"' in editing, (
        "`Add new` points at an id the add-mode render does not have"
    )
    assert ">Save<" in editing, "vacuity: not actually in add mode"
    # Cancel returns to the list, so it lands where the list is.
    cancel = re.search(r'<a[^>]*>\s*Cancel</a>', editing, re.S)
    assert cancel and "#reviewers-table-card" in cancel.group(0), (
        f"`Cancel` lands at the top of the page: {cancel and cancel.group(0)!r}"
    )


def test_a_failed_import_still_renders_real_anchors(client, db):
    """The re-render that the fix silently did nothing on.

    `_shared.py`'s import-error path builds its own context and did not
    set `pager_anchor` / `row_editor_anchor`. Jinja's `Undefined` is
    falsy rather than loud, so the card emitted `id=""` and every
    control targeting it emitted a bare `#` — which means "top of
    document". The landing anchors were inert on exactly the page an
    operator reads hardest.
    """
    rs = _with_reviewers(client, db, "rc37")
    response = client.post(
        f"/operator/sessions/{rs.id}/reviewers/import",
        files={"file": ("bad.csv", b"NotAColumn,Nope\nx,y\n", "text/csv")},
        follow_redirects=False,
    )
    # Vacuity guard: this must be the error re-render, not a redirect.
    assert response.status_code == 400, response.status_code
    html = _markup(response.text)
    assert 'id=""' not in html, "an element on the error page has an empty id"
    assert 'id="reviewers-table-card"' in html
    assert not re.search(r'(?:href|action)="[^"]*#"', html), (
        "a control on the error page points at a bare `#`, which means "
        "the top of the document"
    )


def test_the_busy_indicator_skips_a_same_url_form_submit(client, db):
    """Giving the filter form a fragment created a second problem.

    Sending it again unchanged now produces a URL identical to the
    current one — path, query AND fragment — which the navigate
    algorithm treats as a same-document fragment navigation: no fetch,
    so no `pageshow`, so the busy indicator arms and never clears until
    the 60s give-up timer. The click handler has guarded this case for
    links all along; the submit handler had no counterpart.

    Verified in Chromium that `pageshow` really does not fire on such a
    submit. This pins the MECHANISM only — the suite has no JS runtime,
    so it cannot observe the indicator itself.
    """
    rs = _with_reviewers(client, db, "rc38")
    html = _page(client, rs)

    submit_handler = re.search(
        r'addEventListener\("submit".*?\n\s*\}\);', html, re.S
    )
    assert submit_handler, "the submit listener is gone"
    body = submit_handler.group(0)
    assert "target.href === window.location.href" in body, (
        "the submit listener has no same-URL guard, so a filter strip "
        "sent again unchanged leaves the busy indicator armed"
    )
    # ...and it must return rather than fall through to arming.
    assert re.search(
        r"if \(target\.href === window\.location\.href\) return;", body
    ), "the same-URL guard does not actually skip arming"


# --- 19P.1 rung 2b: the expander's controls are live -----------------

def _builder(html: str) -> str:
    """The expander's build function, which is where its markup lives
    now — as JS string literals, not as rendered HTML."""
    start = html.index('tr.id = "reviewers-row-expander"')
    return html[start:html.index("td.innerHTML = html;", start)]


def test_the_expander_posts_to_the_same_routes_the_card_did(client, db):
    """The controls moved; the routes did not. Each button carries
    `form="reviewers-bulk-form"` and a `formaction`, exactly as it did
    in the card — the selection reaches the POST through the row
    checkboxes' own `form=`, so a button needs only to say where.
    """
    rs = _with_reviewers(client, db, "rc39")
    build = _builder(_page(client, rs))

    assert 'form="reviewers-bulk-form"' in build
    for route in ("/bulk-inactivate", "/bulk-reactivate", "/bulk-delete"):
        assert route in build, f"the expander cannot reach {route}"
    # Vacuity guard: `formaction` is what makes a route reachable from a
    # button that lives outside its form.
    assert "formaction=" in build


def test_the_expanders_delete_ships_disabled_and_is_paired(client, db):
    """Step 1's constraint, stated as a test: nothing syncs an injected
    pair until its first tick, so a live-by-default Delete would be a
    destructive control with its gate open."""
    rs = _with_reviewers(client, db, "rc40")
    build = _builder(_page(client, rs))

    assert 'data-delete-btn=\\"reviewers-bulk-delete\\"' in build or (
        'data-delete-btn="reviewers-bulk-delete"' in build
    ), "Delete is not paired to a confirm"
    assert 'data-delete-confirm' in build, "no confirm checkbox"
    # The button ships disabled; the checkbox does not.
    delete_at = build.index("btn destructive")
    assert "disabled" in build[delete_at:delete_at + 400], (
        "the expander's Delete does not ship `disabled`"
    )
    # The confirm has to post with the selection, or the route 400s.
    assert 'name=\\"confirm\\" value=\\"true\\"' in build or (
        'name="confirm" value="true"' in build
    )


def test_edit_is_offered_for_exactly_one_row(client, db):
    """Arity, which rung 1 deliberately left unexpressed because every
    control was `disabled` then and a gate would have been
    indistinguishable from the scaffold.

    Verified against a real DOM in Chromium: one row offers Edit
    enabled with the row's id, two rows offer it disabled.
    """
    rs = _with_reviewers(client, db, "rc41")
    build = _builder(_page(client, rs))

    # Pins the DIRECTION, not just the presence of a gate. The first
    # version asserted `"sel.length === 1" in build` and
    # `"data-edit-id" in build`, and a cold read showed both survive
    # inverting the ternary — Edit dead at one row, live with an empty
    # id at two. Source-level either way: the suite has no JS runtime,
    # so what a test can reach here is the expression, and the rendered
    # behavior is checked in Chromium (one row enabled and carrying
    # the id, two rows disabled).
    assert re.search(
        r"var editable = sel\.length === 1;", build
    ), "no arity gate on Edit"
    assert re.search(
        r"""\(editable\s*\?\s*' data-edit-id="'""", build
    ), (
        "the arity gate is inverted or restructured: Edit must carry the "
        "row id when `editable`, not when it is not"
    )


def test_edit_lands_on_the_row_it_is_about_to_edit(client, db):
    """`Edit` enters edit mode, so it lands on the editor (#2405).

    The editor used to be a card above the table and the anchor named
    that card; with the card gone the editor IS the row, so the anchor
    is the row's own id. Landing on the table card instead would put
    the row — and the bar under it — below the fold on any roster long
    enough to scroll.
    """
    html = _page(client, _with_reviewers(client, db, "rc42"))
    handler = re.search(
        r'\.exp-edit\[data-edit-id\].*?window\.location =.*?;', html, re.S
    )
    assert handler, "no Edit click handler"
    assert "edit_id=" in handler.group(0)
    assert '"#reviewer-row-"' in handler.group(0), (
        "Edit lands somewhere other than the row it edits"
    )
    assert "reviewers-row-editor" not in handler.group(0), (
        "Edit still names the retired editor card"
    )


def test_the_status_actions_are_offered_only_where_they_act(client, db):
    """One status in the selection offers one action; a mixed selection
    offers both. Measured in Chromium across all four cases."""
    html = _page(client, _with_reviewers(client, db, "rc43"))

    # Pins the MAPPING, both halves of it. The first version asserted
    # that the status check and `statusActions(sel)` merely appeared,
    # and a cold read showed that swapping the two labels — offering
    # `Activate` for active rows, a no-op on every one of them — left
    # every test in the file passing.
    #
    # Active rows are the ones Inactivate can act on, and vice versa;
    # an action offered for the status it cannot change is a control
    # that does nothing. `statusActions` is defined above `build`, so
    # this reads the whole script.
    assert re.search(
        r'if \(hasActive\) out\.push\("Inactivate"\);', html
    ), "active rows are not offered `Inactivate`"
    assert re.search(
        r'if \(hasInactive\) out\.push\("Activate"\);', html
    ), "inactive rows are not offered `Activate`"
    assert 'row.dataset.status === "active"' in html, (
        "the expander no longer reads row status"
    )

    # ...and the label -> route mapping, which is the second place the
    # same swap could hide.
    build = _builder(html)
    assert "statusActions(sel)" in build, "the buttons are not status-aware"
    assert re.search(
        r'label === "Inactivate"\s*\?\s*"/bulk-inactivate"\s*:\s*'
        r'"/bulk-reactivate"',
        build,
    ), "the label no longer maps to the route that performs it"


# ---------------------------------------------------------------- rung 2b
# step 3: the Add / Edit editor leaves `.card-columns` for its own card.
#
# Every assertion below is structural — WHERE the editor renders, not
# whether it renders. A flat `'row-editor-anchored' in html` passes
# with the editor still nested in the container, which is the entire
# change, so the substring form would have guarded nothing.


def _add_page(client: TestClient, rs: ReviewSession) -> str:
    response = client.get(f"/operator/sessions/{rs.id}/reviewers?add=1")
    assert response.status_code == 200
    # The fixture must actually BE in edit mode, or every absence
    # assertion below passes against a page with no editor at all.
    # Keyed on the blank row rather than a heading: the editor card and
    # its "Add new reviewer" title were removed once Save and Cancel
    # moved to the row's own bar, and a guard keyed to chrome fails the
    # moment the chrome changes.
    assert 'id="reviewers-row-editor"' in response.text, "not in add mode"
    assert 'name="name"' in response.text, "the add row has no fields"
    return _markup(response.text)


def _div_block(html: str, marker: str) -> str:
    """The element opened by `marker`, div-balanced.

    Same reason as `_left_pane`: `.*?</div>` stops at the first close
    tag, which here is the left column's — so a truncated block would
    report the editor "outside" the container whatever its real nesting.
    """
    start = html.index(marker)
    depth, i = 1, start + len(marker)
    for tag in re.finditer(r"<div\b|</div>", html[i:]):
        depth += 1 if tag.group(0) != "</div>" else -1
        if depth == 0:
            return html[start:i + tag.end()]
    raise AssertionError(f"{marker} never closes")


def _card_columns(html: str) -> str:
    return _div_block(html, '<div class="card-columns">')


def _panel(html: str) -> str:
    """The Unlock panel, found by its id rather than by a literal tag.

    The opening tag's attributes are not fixed: `hidden` is there only
    while the panel is closed, so a marker with `hidden` baked into it
    silently stops matching the moment a page arrives open — which is
    what `?unlocked=1` does after a labels save.
    """
    m = re.search(r'<div\b[^>]*id="roster-unlock-panel"[^>]*>', html)
    assert m, "Unlock panel not found"
    return _div_block(html, m.group(0))


def _count_cards(block: str) -> int:
    """Elements whose class list carries the `card` token.

    `\bcard\b` counts `card-columns` too — `-` is a word boundary — so
    the container scored itself and the first version of the caller
    below failed against correct markup.

    Matches double-quoted `class="…"` only. Every template in this repo
    quotes attributes that way, and Jinja renders them that way; a
    single-quoted class would be invisible here.
    """
    return sum(
        1
        for m in re.finditer(r'class="([^"]*)"', block)
        if "card" in m.group(1).split()
    )


def test_card_columns_renders_only_where_the_unlock_panel_cannot(client, db):
    """Rung 3a's complement, from the outside.

    The tag-labels editor has two homes and one include: the Unlock
    panel when the panel can render, `.card-columns` when it cannot. The
    container therefore appears on exactly the pages the panel does not,
    and holds that one card when it does appear.

    Was `..._is_left_holding_the_labels_editor_alone`, which asserted the
    container is always present — true between 2b and 3a, false after.
    """
    rs = _with_reviewers(client, db, "rc-s3-alone")

    # Draft, not editing: the panel renders, so the container must not.
    resting = _markup(_page(client, rs))
    assert 'id="roster-unlock-panel"' in resting, "no panel on a draft page"
    assert 'class="card-columns"' not in resting, (
        "the container renders alongside the panel — two homes at once"
    )

    # Add mode: the panel stands down, so the container takes over.
    adding = _add_page(client, rs)
    assert 'id="roster-unlock-panel"' not in adding, (
        "the panel renders during an edit"
    )
    block = _card_columns(adding)
    assert "Reviewer tag labels" in block, (
        "the editor has no home at all while editing"
    )
    assert _count_cards(block) == 1, (
        "`.card-columns` holds more than the tag-labels editor"
    )


def test_the_editor_is_the_row_and_the_anchor_names_it(client, db):
    """Replaces two tests that pinned the editor CARD's position.

    That card was retired once Save and Cancel moved into the row's own
    bar: what was left of it described where the controls had gone. So
    the contract is no longer "the card sits outside `.card-columns`,
    immediately above the table" but "there is no card, and the anchor
    the navigations carry names the row you type into".
    """
    html = _add_page(client, _with_reviewers(client, db, "rc-iseditor"))

    assert 'class="card row-editor-anchored"' not in html, (
        "the editor card is back"
    )
    assert ">Add new reviewer</h2>" not in html, (
        "the retired card's heading is back"
    )

    # The anchor is on the add row itself, and that row is in the table.
    row = re.search(
        r'<tr[^>]*id="reviewers-row-editor"[^>]*>', html
    )
    assert row, "nothing carries the editor anchor"
    assert "reviewer-edit-row" in row.group(0), (
        "the anchor is on something other than the edit row"
    )
    table = _div_block(html, '<div class="card table-pager-anchored"')
    assert 'id="reviewers-row-editor"' in table, (
        "the editor anchor is outside the table card"
    )

    # ...and it carries the landing margin, or it arrives flush.
    assert "row-action-target" in row.group(0), (
        "the add row has no landing margin"
    )

    # The mode is still ANNOUNCED. The card's `<h2>` was the only
    # accessible name for "you are adding" versus "you are editing";
    # what replaced it visually is a highlighted row, which reaches
    # nobody using a screen reader. Removing the card lost this
    # silently, so it is pinned rather than trusted.
    bar = re.search(
        r'<tr class="[^"]*\brow-editor-bar\b[^"]*">.*?</tr>', html, re.S
    )
    assert bar, "no editor bar"
    label = re.search(
        r'<span class="visually-hidden"[^>]*>\s*([^<]+?)\s*</span>',
        bar.group(0),
    )
    assert label, "the edit mode has no accessible name"
    assert label.group(1) == "Add new reviewer", label.group(1)
    assert 'aria-live' in bar.group(0), (
        "the mode is not announced when a failed save re-renders the "
        "page into it under the operator"
    )


@pytest.mark.parametrize(
    "state,adding,panel_expected",
    [("draft", False, True), ("draft", True, False),
     ("validated", False, True), ("validated", True, False),
     ("ready", False, False), ("ready", True, False),
     ("expired", False, False), ("expired", True, False),
     ("archived", False, False), ("archived", True, False)],
)
def test_the_labels_editor_renders_exactly_once_in_every_state(
    client, db, state, adding, panel_expected
):
    """The invariant rung 3a's `unlock_available` exists to hold.

    One include, two positions. Two renders would put two
    `#field-labels-form-reviewer` ids on one page — and the partial's own
    script resolves its inputs by `getElementById`, so the dirty-check
    would drive the wrong copy. Zero renders loses the labels entirely,
    which on a locked session is the only place they are shown in full
    (the roster readouts pill only the columns that HOLD data, so a
    friendly label on an empty tag column appears nowhere else).

    Parametrized over BOTH axes of `unlock_available`, not just the
    lifecycle: `edit_mode` is the other half, and on an editable session
    it is the half that decides which home renders. A first version
    covered the five states at rest only — five of the ten that matter —
    so a third include gated on `edit_mode` would have rendered the
    editor twice in add mode with nothing counting it.
    """
    rs = _with_reviewers(client, db, f"rc-3a-{state[:5]}-{int(adding)}")
    review_session = db.get(ReviewSession, rs.id)
    review_session.status = state
    db.flush()
    url = f"/operator/sessions/{review_session.id}/reviewers"
    if adding:
        url += "?add=1"
    response = client.get(url)
    assert response.status_code == 200
    html = _markup(response.text)
    where = f"{state}, add={adding}"

    assert html.count('id="field-labels-form-reviewer"') == 1, where
    assert html.count("Reviewer tag labels") == 1, where

    # The form's TARGET, in whichever home it landed. Unguarded until a
    # cold read pointed the fallback copy at `/reviewees/field-labels`
    # and watched the whole suite pass — a live Save, during an edit,
    # writing this page's labels onto another roster's and 303ing.
    assert html.count(
        f'action="/operator/sessions/{review_session.id}'
        f'/reviewers/field-labels"'
    ) == 1, where
    # ...and all three slots, which the fallback copy also did not pin:
    # it could be cut to one and nothing failed.
    for slot in ("tag_1", "tag_2", "tag_3"):
        assert f'name="{slot}"' in html, f"{where}: {slot} missing"

    in_panel = 'id="roster-unlock-panel"' in html
    assert in_panel is panel_expected, where
    if panel_expected:
        panel = _panel(html)
        assert "field-labels-editor" in panel, f"{where}: editor outside panel"
        assert 'class="card-columns"' not in html, where
    else:
        assert "field-labels-editor" in _card_columns(html), where


def test_no_empty_script_element_is_left_behind(client, db):
    """Step 2 left two `<script></script>` pairs on the page after the
    code inside them moved. Harmless, and exactly the kind of residue a
    substring test never sees, so it gets its own assertion.
    """
    for html in (
        _page(client, _with_reviewers(client, db, "rc-s3-js1")),
        _add_page(client, _with_reviewers(client, db, "rc-s3-js2")),
    ):
        empty = re.findall(r"<script\b[^>]*>\s*</script>", html)
        assert not empty, f"{len(empty)} empty <script> element(s) shipped"


def test_the_editor_card_is_absent_outside_edit_mode(client, db):
    """The `edit_mode` gate itself.

    Stated four times — template comment, commit message, plan, and the
    comment over `test_edit_id_renders_target_row_as_inputs` claiming
    *that* assertion pins it — and guarded nowhere until a cold read
    replaced the gate with `{% if true %}` and watched all 4,014 tests
    pass.

    Before step 3 the "only" was pinned by accident, through the card's
    OLD class: `test_reviewers_page_filter.py` asserts
    `'class="card operator-actions-card"' not in markup` on a plain
    load. Renaming the class moved the editor out from under it. And
    moving the card out of `.card-columns` is exactly what stopped
    `..._labels_editor_alone` from noticing a leak: it counts cards
    INSIDE the container, and a leaked editor is now outside it.
    """
    html = _markup(_page(client, _with_reviewers(client, db, "rc-s3-gate")))
    # Not vacuous: the page rendered, and rendered the card the editor
    # sits above, so "absent" means absent rather than "never built".
    assert 'id="reviewers-table-card"' in html, "the page did not render"

    assert 'class="card row-editor-anchored"' not in html, (
        "the editor's card renders outside edit mode"
    )
    # The heading and the Save button independently, because the card
    # could be renamed and the contents still leak.
    assert ">Add new reviewer</h2>" not in html
    assert ">Edit reviewer</h2>" not in html
    assert 'form="reviewer-edit-form">Save</button>' not in html, (
        "the editor's Save renders with no row to save"
    )


@pytest.mark.parametrize(
    "state,adding",
    [("draft", False), ("draft", True), ("ready", False), ("archived", False)],
)
def test_the_roster_note_claims_nothing_the_page_does_not_show(
    client, db, state, adding
):
    """It names two things: an Unlock control, and live cards below.

    Both are gated; the note was not, so on a locked session it read
    "the roster's tag labels live behind Unlock" with no Unlock on the
    page, and "those two are still live in the cards below" with no
    cards below. Asserted as a biconditional rather than as absence, so
    it fails whichever side stops matching.
    """
    rs = _with_reviewers(client, db, f"rc-note-{state[:4]}-{int(adding)}")
    review_session = db.get(ReviewSession, rs.id)
    review_session.status = state
    db.flush()
    url = f"/operator/sessions/{review_session.id}/reviewers"
    if adding:
        url += "?add=1"
    html = _markup(client.get(url).text)
    where = f"{state}, add={adding}"

    note = "live behind" in html
    unlock = 'id="roster-unlock-btn"' in html
    cards = 'class="bottom-grid"' in html
    assert note == unlock, f"{where}: note {note}, Unlock control {unlock}"
    assert note == cards, f"{where}: note {note}, cards below {cards}"


# ---------------------------------------------------------------- UI pass
# Three adjustments asked for after 3a: the panel surviving a labels
# save, the caret landing in the new row, and the edit row's controls
# moving into an expander bar beneath it.


def test_the_panel_arrives_open_when_the_flag_is_set(client, db):
    """`Save labels` 303s back with `?unlocked=1`.

    Without it the panel ships collapsed and shuts itself on every save,
    which is the bug this fixes. `hidden` is asserted as an attribute of
    the panel's own tag, not as a substring of the page — several other
    elements on this page carry it.
    """
    rs = _with_reviewers(client, db, "rc-open")
    closed = _markup(_page(client, rs))
    opened = _markup(
        client.get(f"/operator/sessions/{rs.id}/reviewers?unlocked=1").text
    )

    assert re.search(r'id="roster-unlock-panel"[^>]*\bhidden', closed), (
        "the panel does not ship collapsed by default"
    )
    assert not re.search(r'id="roster-unlock-panel"[^>]*\bhidden', opened), (
        "`?unlocked=1` did not open the panel"
    )

    # The Lock control has two homes and the toggle MOVES the one
    # element between them, so arriving open has to start it inside the
    # panel — otherwise the first Lock click moves it out of a place it
    # was never in.
    assert 'id="roster-unlock-btn"' not in _panel(closed), (
        "the control starts inside the panel while closed"
    )
    # Inside `.unlock-right` specifically, not merely somewhere in the
    # panel. The toggle reopens into `panel.querySelector(".unlock-right")`,
    # so a server render anywhere else puts the control in one place on
    # arrival and another after a Lock/Unlock round trip — and the panel's
    # foot is exactly where a sibling test measures it as 125px adrift
    # from the card it belongs under.
    right = _div_block(opened, '<div class="unlock-stack unlock-right">')
    assert 'id="roster-unlock-btn"' in right, (
        "arriving open, the control is not in the right-hand stack the "
        "toggle would move it back into"
    )
    assert opened.count('id="roster-unlock-btn"') == 1, "two Lock controls"
    # The label is on its own line inside the button, so match the
    # element and read its text rather than needling `>Lock<`.
    btn = re.search(
        r'<button[^>]*id="roster-unlock-btn".*?</button>', _panel(opened), re.S
    )
    assert btn, "no Lock control in the open panel"
    assert "Lock" in btn.group(0) and "Unlock" not in btn.group(0), (
        "the open panel offers Unlock, not Lock"
    )
    assert 'aria-expanded="true"' in btn.group(0), (
        "an open panel reports itself collapsed to assistive tech"
    )


def test_add_mode_puts_the_caret_in_the_new_rows_name_field(client, db):
    """Markup-level: the field is marked and a script targets it.

    Whether focus actually lands is a browser question — the suite has
    no JS runtime — and it is checked in Chromium. What is pinned here
    is that the two halves still refer to each other, and that the
    marked field is the one in the ADD row rather than any other input.
    """
    html = _add_page(client, _with_reviewers(client, db, "rc-caret"))
    assert html.count('class="row-editor-first-field"') == 1, (
        "the caret target is missing or ambiguous"
    )
    assert ".row-editor-first-field" in html, "nothing focuses the field"

    # It is the Name box of the edit row, not some other input.
    edit_row = re.search(
        r'<tr class="reviewer-edit-row[^"]*"[^>]*>.*?</tr>', html, re.S
    )
    assert edit_row, "no edit row"
    assert 'class="row-editor-first-field"' in edit_row.group(0), (
        "the caret target is outside the edit row"
    )
    assert 'name="name"' in edit_row.group(0)

    # `autofocus` does NOT work here — a fragment navigation beats it —
    # so its absence is deliberate and pinned, or someone re-adds it and
    # believes it works.
    #
    # Matched as an ATTRIBUTE, with scripts stripped first: the script
    # below the table carries a comment naming `autofocus` to say why it
    # is not used, and a bare substring reads that comment as markup.
    # Same trap `_markup()` exists for one storey down.
    no_js = re.sub(r"<script\b.*?</script>", "", html, flags=re.S)
    assert not re.search(r"<[a-z][^>]*\bautofocus\b", no_js), (
        "`autofocus` is back; it is a no-op behind a fragment navigation"
    )


@pytest.mark.parametrize("url_suffix", ["?add=1", "?edit_id={rid}"])
def test_the_edit_row_carries_an_expander_bar_beneath_it(
    client, db, url_suffix
):
    """Both editors: the Add row and the Edit row.

    The bar is the row's own controls, on the analogy of a selected row,
    so the row reads as selected and the bar hangs off it. Parametrized
    because the two are separate blocks in the template and a macro used
    once is a macro that can silently stop being used twice.
    """
    rs = _with_reviewers(client, db, f"rc-bar-{len(url_suffix)}")
    rid = db.execute(
        select(Reviewer.id).where(Reviewer.session_id == rs.id)
    ).scalars().first()
    html = _markup(
        client.get(
            f"/operator/sessions/{rs.id}/reviewers"
            + url_suffix.format(rid=rid)
        ).text
    )

    assert html.count('class="session-expander session-expander-bracketed '
                      'row-editor-bar"') == 1, "no editor bar, or two"

    # It follows the edit row IMMEDIATELY: a bar separated from its row
    # by another row is not the selected-row analogy.
    # Class list matched loosely: the row carries `reviewer-edit-row`,
    # `session-row-selected` and `row-action-target`, and pinning the
    # exact string broke the moment a fourth was added for the landing
    # margin. What this asserts is adjacency, not the attribute.
    m = re.search(
        r'<tr class="[^"]*\breviewer-edit-row\b[^"]*"[^>]*>.*?</tr>\s*'
        r'<tr class="session-expander session-expander-bracketed '
        r'row-editor-bar">',
        html, re.S,
    )
    assert m, "the bar does not directly follow the row it belongs to"

    # Exactly one Save on the page — the card's pair moved, it was not
    # copied. Two submits on one form is the shape 2b step 2 avoided.
    assert html.count('form="reviewer-edit-form">Save</button>') == 1, (
        "two Save buttons on one edit form"
    )
    bar = re.search(
        r'<tr class="session-expander session-expander-bracketed '
        r'row-editor-bar">.*?</tr>', html, re.S,
    ).group(0)
    assert ">Save</button>" in bar and ">Cancel</a>" in bar, (
        "the bar is missing a control"
    )


def test_the_editor_bar_spans_the_row_it_hangs_from(client, db):
    """A colspan that does not match leaves the bar short or overflowing.

    Counted from the rendered header rather than trusted: the template
    derives it from the same flags `<thead>` branches on, and this is
    what proves the derivation right.
    """
    html = _add_page(client, _with_reviewers(client, db, "rc-span"))
    header = re.search(r"<thead>.*?</thead>", html, re.S)
    assert header, "no header"
    columns = len(re.findall(r"<th\b", header.group(0)))
    assert columns > 3, f"only {columns} columns found; the count is wrong"

    span = re.search(
        r'row-editor-bar">\s*<td colspan="(\d+)"', html
    )
    assert span, "the bar's cell has no colspan"
    assert int(span.group(1)) == columns, (
        f"bar spans {span.group(1)} of {columns} columns"
    )


# ------------------------------------------------------------- rung 3b
# The Danger Zone moves into the Unlock panel, wired, and gated on the
# roster having rows — which the scaffold copy was not.


def _danger(html: str) -> str:
    """The Danger Zone card in the panel, found by its heading id.

    Not by an exact class string: these regexes pinned
    `class="card" aria-labelledby=…` and broke the moment the card got
    its `danger-zone` class back, which is the attribute most likely to
    change on a card.
    """
    m = re.search(
        r'<section[^>]*aria-labelledby="reviewers-danger-h"[^>]*>.*?</section>',
        _panel(html), re.S,
    )
    return m.group(0) if m else ""


def test_the_danger_zone_is_wired_in_the_panel(client, db):
    """Everything the route refuses without, asserted where it renders.

    The scaffold's copy was inert; this pins that the real one carries a
    form to the right action, the confirm the route requires, and the
    pairing keys that gate the button — each read inside the card, so a
    control that drifts out of it fails here rather than passing on a
    page-wide substring.
    """
    rs = _with_reviewers(client, db, "rc-3b-wired")
    card = _danger(_markup(_page(client, rs)))
    assert card, "no Danger Zone in the panel"

    assert f'action="/operator/sessions/{rs.id}/reviewers/delete-all"' in card
    assert 'name="confirm" value="true"' in card, "no confirm to tick"
    assert 'data-delete-confirm="delete-all"' in card
    assert 'data-delete-btn="delete-all"' in card
    # The ATTRIBUTE, not the substring. `aria-disabled="true"` contains
    # "disabled", so the bare needle is true of this card whether or not
    # the button ships disabled — proved by dropping only `disabled` and
    # watching this pass. The correct form is twenty lines up in this
    # same file, with a comment explaining exactly why the substring
    # will not do; this test did not reuse it.
    button = re.search(r"<button[^>]*data-delete-btn[^>]*>", card)
    assert button, "no destructive button in the card"
    assert re.search(r"(?:^|\s)disabled(?:[=\s>]|$)", button.group(0)), (
        "the destructive button starts enabled"
    )
    assert "btn destructive" in card, "not the destructive role"

    # The card's identity, which nothing else held: the heading text
    # (`spec/setup_pages.md` names this card "Danger Zone"), the class
    # that reaches `base.html`'s amber warning framing, and the
    # `.confirm-label` this slice kept the scaffold's markup FOR. All
    # three could be changed with the suite green.
    assert ">Danger Zone</h2>" in card, "the card lost its name"
    assert "danger-zone" in card, (
        "the card lost the class that frames it as destructive"
    )
    assert 'class="confirm-label"' in card, (
        "the confirm lost the class kept over the live card's inline style"
    )

    # One pair on the page. `sync` resolves a confirm's button with a
    # first-match `querySelector`, so a second pair keyed the same way
    # gates the wrong button — which is why the old card had to go in
    # this same slice rather than a later one.
    html = _markup(_page(client, rs))
    assert html.count('data-delete-confirm="delete-all"') == 1
    assert html.count('data-delete-btn="delete-all"') == 1


def test_the_danger_zone_is_gated_on_the_roster_having_rows(client, db):
    """The divergence 3b settles.

    The live card was `{% if total_row_count > 0 %}`; the scaffold copy
    it replaced rendered unconditionally, so an empty roster offered
    "delete the existing 0 reviewers" — a destructive control with
    nothing to destroy, which the route refuses anyway.
    """
    empty = _session(client, db, "rc-3b-empty")
    html = _markup(_page(client, empty))
    assert 'id="roster-unlock-panel"' in html, "no panel to look in"
    assert not _danger(html), (
        "an empty roster offers Delete all reviewers"
    )
    # The ROUTE, not the bare word: the roster card's own note says
    # "delete-all lives behind Unlock", so the substring matches the
    # page's prose. Third instance of that trap in this segment.
    assert f"/operator/sessions/{empty.id}/reviewers/delete-all" not in html, (
        "the route is still reachable on an empty roster"
    )

    # ...and the fixture is not vacuous: with rows, it renders.
    assert _danger(_markup(_page(client, _with_reviewers(client, db, "rc-3b-full"))))


# The response acknowledgement is NOT tested here. A test lived at this
# point that asserted `("reviewer response" in card) == (ack in card)`
# against `_with_reviewers` — a fixture with no responses — so both
# sides were False and it asserted nothing. Deleting the hidden field
# from the template left it green.
#
# `test_setup_danger_zone_delete_all.py` already covers the contract
# properly and better: it builds an instrument, an assignment and saved
# responses, is parametrized across all four roster pages, and finds
# the form by its action URL, so it followed Reviewers' form into the
# panel without being re-aimed. Three of its tests fail when the field
# goes. Duplicating that fixture here to re-assert the same thing would
# be a second, weaker copy of a guard that works.
