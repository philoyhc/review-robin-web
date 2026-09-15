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

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession

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


def test_every_unlock_control_is_inert(client, db):
    """Scaffold-first means inert controls, not merely greyed ones."""
    html = _page(client, _with_reviewers(client, db, "rc7"))
    panel = re.search(
        r'id="roster-unlock-panel".*?(?=<script>)', html, re.S
    )
    assert panel, "Unlock panel not found"
    controls = re.findall(r"<(?:button|input)\b[^>]*>", panel.group(0))
    assert controls, "no controls found in the Unlock panel"
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
    danger = re.search(r'id="scaffold-danger-h".*?</section>', html, re.S)
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


def test_the_three_cards_it_will_absorb_are_still_live(client, db):
    """Rung 1 adds a surface; it retires nothing. Rung 3 does that."""
    rs = _with_reviewers(client, db, "rc10")
    html = _page(client, rs)
    assert 'id="upload-csv"' in html
    # NOT the bare substring `danger-zone`: base.html's stylesheet ships on
    # every response and mentions it eight times, so that assertion is true
    # of every page in the app with or without the card. Match the card's
    # own class attribute instead. (`test_reserved_shade.py` warns about
    # exactly this trap; 19J.5 hit it three times.)
    assert 'class="card danger-zone"' in html
    # The live editor's own route, not a string the scaffold prints —
    # deleting the include outright must fail this.
    assert f"/operator/sessions/{rs.id}/reviewers/field-labels" in html


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
    assert re.search(
        r'id="reviewer-row-\d+"\s+data-status="active"', html
    ), "rows carry no data-status"


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
    panel = re.search(r'id="roster-unlock-panel".*?(?=<script>)', html, re.S)
    assert panel, "Unlock panel not found"
    body = panel.group(0)

    labels = body.index('id="scaffold-labels-h"')
    danger = body.index('id="scaffold-danger-h"')
    upload = body.index('id="scaffold-upload-h"')
    assert labels < danger < upload, (
        "expected labels, then danger zone, then upload"
    )

    # The first two share the stack; upload is the grid's second child.
    stack = re.search(r'<div class="unlock-stack">.*?\n        </div>', body, re.S)
    assert stack, "left-column stack not found"
    assert 'id="scaffold-labels-h"' in stack.group(0)
    assert 'id="scaffold-danger-h"' in stack.group(0)
    assert 'id="scaffold-upload-h"' not in stack.group(0), (
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

