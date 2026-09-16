"""The Observers Unlock panel — 19P.2 rung 6.

`Upload Observers` and the `Danger Zone` moved off the foot of the page
into a collapsed panel above the preview table, the way Reviewers did at
19P.1 rung 3. Nothing renders below the table any more.

**The suite was blind to this whole move before these tests.** Every one
of the 4,131 tests that already existed passed with the cards relocated,
the `.bottom-grid` deleted and both redirects rewritten — nothing pinned
the cards' position, the container, or the redirect URLs. So the assertions
here are about *placement and plumbing*, which is precisely what nothing
else reads.

**No JS runtime, and that matters more than usual here.** `hidden` is an
inert attribute to this suite: a panel that ships collapsed and one that
ships open are the same markup to every assertion below except the one
that reads the attribute. Whether the panel actually collapses, and
whether the `Lock` control moves between its two homes, is measured in
Chromium — the results live in the PR body and the segment plan.
"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Observer, ReviewSession

CSV = b"ObserverEmail,ObserverName\no1@example.org,O1\no2@example.org,O2\n"


def _session(
    client: TestClient,
    db: Session,
    code: str,
    rows: int = 2,
    named: int | None = None,
    tagged: int = 0,
) -> ReviewSession:
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
    # `named` / `tagged` default to "every row" / "none", which is the
    # shape most of this file wants; the index test overrides them so
    # the three column counts differ from each other.
    named = rows if named is None else named
    db.add_all([
        Observer(
            session_id=s.id,
            email=f"o{n}@example.org",
            display_name=f"O{n}" if n < named else None,
            tag_1=f"t{n}" if n < tagged else None,
            status="active",
        )
        for n in range(rows)
    ])
    db.commit()
    db.refresh(s)
    return s


def _page(client: TestClient, s: ReviewSession, suffix: str = "") -> str:
    return client.get(f"/operator/sessions/{s.id}/observers{suffix}").text


def _markup(body: str) -> str:
    """The page with `<style>` and `<script>` blocks stripped.

    `base.html` inlines the whole app's CSS on every page, and it
    defines `.danger-zone` and `.bottom-grid` rules. So `"bottom-grid"
    not in body` is unfalsifiable — it fails on a page that renders no
    such element, because the RULE is always there. Both of this file's
    absence claims are about markup, so both read this.
    """
    body = re.sub(r"<style\b.*?</style>", "", body, flags=re.S)
    return re.sub(r"<script\b.*?</script>", "", body, flags=re.S)


def _card(body: str) -> str:
    """The roster card's MARKUP only.

    Bounded by the preview table's card, which is the next thing on the
    page — and stripped of the toggle script, which lives inside this
    card and contains BOTH labels (`open ? "Unlock" : "Lock"`). Read
    with the script in, an assertion that the collapsed card reads
    "Unlock" passes on the open one too, and vice versa. The first
    draft of this file did exactly that.
    """
    start = body.index('id="roster-card"')
    end = body.index('id="observers-table-card"', start)
    return _markup(body[start:end])


def _roster_count(card: str) -> str:
    """The roster readout's pill text, whitespace collapsed.

    Read as one string rather than asserted as a substring, so the
    number and its noun are pinned together — `"0" in card` is true of
    almost any page, and `"observers" in card` of every one of them.
    """
    m = re.search(
        r'roster-readout-label">Observers roster:</span>\s*'
        r'<span class="pill pill-count">(.*?)</span>',
        card, re.S,
    )
    assert m, "no roster readout in the card"
    return " ".join(m.group(1).split())


def _control_label(card: str) -> str:
    """The toggle button's own text.

    Read off the `<button>` rather than the card, because the card also
    carries a `<noscript>` twin of the control: an assertion that the
    collapsed card contains "Unlock" passed with the BUTTON relabelled
    `Lock`, matched by the fallback link beside it. The one mutation
    that survived this file's first mutation table.
    """
    m = re.search(
        r'<button[^>]*id="roster-unlock-btn"[^>]*>(.*?)</button>',
        card, re.S,
    )
    assert m, "no toggle button in the card"
    return m.group(1).strip()


def _toggle(body: str) -> str:
    """The card's own toggle script, for the claims that ARE about it."""
    m = re.search(
        r"<script>(?:(?!</script>).)*?roster-unlock-panel.*?</script>",
        body, re.S,
    )
    assert m, "the Unlock toggle is not in the response"
    return m.group(0)


def _panel(body: str) -> str:
    """The panel's markup, bounded by the COLLAPSED control after it.

    Only valid on a closed page. Open, the control moves inside the
    panel — into whichever stack holds a card — so this bound would cut
    the panel short and silently drop everything after it. Asserted
    rather than assumed: every caller here reads a closed page, and a
    future one that doesn't should fail loudly instead of quietly
    testing half a panel.
    """
    card = _card(body)
    assert 'aria-expanded="false"' in card, (
        "_panel() is only valid on a collapsed page — open, the control "
        "moves inside the panel and this bound truncates it"
    )
    start = card.index('id="roster-unlock-panel"')
    end = card.index('class="roster-card-actions"', start)
    return card[start:end]


# ── Placement ─────────────────────────────────────────────────────────


def test_both_cards_move_into_the_panel_and_nothing_stays_below(
    client: TestClient, db: Session
) -> None:
    """The move itself: both cards inside the panel, the container they
    came from gone, and nothing after the table."""
    body = _page(client, _session(client, db, "unl-1"))

    panel = _panel(body)
    assert 'id="upload-csv"' in panel, "the upload card did not move"
    assert "danger-zone" in panel, "the Danger Zone did not move"

    # The container they came from is retired, not merely emptied.
    markup = _markup(body)
    assert "bottom-grid" not in markup, "the .bottom-grid still renders"

    # And nothing mutating is left after the table. Read by position,
    # because "not in the panel" and "not on the page" are different
    # claims and only the second one is the rung.
    after = markup[markup.index('id="observers-table-card"'):]
    assert 'id="upload-csv"' not in after
    assert "danger-zone" not in after


def test_upload_goes_left_and_the_danger_zone_right(
    client: TestClient, db: Session
) -> None:
    """Author's ruling: `Upload Observers` left, `Danger Zone` right —
    the order they already had in the grid, so the operator's muscle
    memory for this page survives the move.

    NOT Reviewers' arrangement, which is the mirror of this. Its left
    column holds a tag-labels editor Observers does not have, so the
    columns cannot correspond anyway.
    """
    panel = _panel(_page(client, _session(client, db, "unl-2")))

    left = panel.index('class="unlock-stack"')
    right = panel.index('class="unlock-stack unlock-right"')
    upload = panel.index('id="upload-csv"')
    danger = panel.index("danger-zone")

    assert left < upload < right, "Upload is not in the left stack"
    assert right < danger, "the Danger Zone is not in the right stack"


def test_the_lock_control_ships_as_the_cards_last_child(
    client: TestClient, db: Session
) -> None:
    """Collapsed, the control is the card's last child; open, it belongs
    under the Danger Zone inside the panel. One element, two homes — the
    toggle MOVES it, so where it *starts* decides whether the first
    click moves it out of a place it was never in.
    """
    card = _card(_page(client, _session(client, db, "unl-3")))
    assert card.index('id="roster-unlock-panel"') < card.index(
        'class="roster-card-actions"'
    ), "the collapsed control is not after the panel"
    # The label names the state the control moves TO, not "Done": the
    # panel is a lock state, not a form being finished.
    assert _control_label(card) == "Unlock", _control_label(card)

    # Open, it is inside the panel's right-hand stack instead — below
    # the Danger Zone, which is the card that stack holds.
    open_card = _card(
        _page(client, _session(client, db, "unl-3b"), "?unlocked=1")
    )
    right = open_card.index('class="unlock-stack unlock-right"')
    danger = open_card.index("danger-zone")
    actions = open_card.index('class="roster-card-actions"')
    assert right < danger < actions, (
        "the open control is not under the Danger Zone in the right stack"
    )
    assert open_card.index('aria-expanded="true"') > right
    assert _control_label(open_card) == "Lock", _control_label(open_card)

    # And the toggle knows both homes, which is what makes one element
    # serve two positions — the open one read off the template's marker
    # rather than named as a column, see the empty-roster test below.
    toggle = _toggle(_page(client, _session(client, db, "unl-3c")))
    assert "card.appendChild(actions)" in toggle
    assert 'panel.querySelector("[data-lock-home]").appendChild(actions)' in (
        toggle
    )


def test_the_lock_control_follows_the_column_that_has_a_card(
    client: TestClient, db: Session
) -> None:
    """`Lock` sits beneath the card its column holds — and on an EMPTY
    roster the right column holds none, because the Danger Zone is gated
    on rows.

    The first draft left it floating at the top of that empty column,
    level with the Upload card's heading. It lands on the two likeliest
    paths, not an edge case: first use, and immediately after
    `delete-all` — which redirects back `?unlocked=1` precisely because
    uploading a replacement is the likely next move.

    Reviewers cannot reach this, its right column holding the
    always-rendered Upload card, so following Reviewers means keeping
    the RELATIONSHIP rather than the column.
    """
    # Populated: the marker is on the right stack, under the Danger Zone.
    full = _card(
        _page(client, _session(client, db, "unl-20", rows=2), "?unlocked=1")
    )
    right = full.index('class="unlock-stack unlock-right"')
    assert full.index("data-lock-home") > right, (
        "the lock home is not the right stack on a populated roster"
    )
    assert full.index("danger-zone") < full.index(
        'class="roster-card-actions"'
    ), "Lock is not beneath the Danger Zone"

    # Empty: it moves to the left stack, under Upload.
    empty = _card(
        _page(client, _session(client, db, "unl-21", rows=0), "?unlocked=1")
    )
    assert "danger-zone" not in empty
    left = empty.index('class="unlock-stack"')
    right_empty = empty.index('class="unlock-stack unlock-right"')
    home = empty.index("data-lock-home")
    assert left < home < right_empty, (
        "Lock is stranded in the empty right column"
    )
    assert empty.index('id="upload-csv"') < empty.index(
        'class="roster-card-actions"'
    ) < right_empty, "Lock is not beneath the Upload card"

    # One control either way — the macro has one definition and only
    # one branch renders it.
    for card in (full, empty):
        assert card.count('id="roster-unlock-btn"') == 1
        assert card.count("data-lock-home") == 1


def test_the_panel_ships_hidden_and_unlocked_opens_it(
    client: TestClient, db: Session
) -> None:
    """`?unlocked=1` is the whole server side of the panel's open state.

    The `hidden` attribute is the only thing distinguishing these two
    responses to this suite — with no layout engine a collapsed panel
    and an open one carry identical markup otherwise.
    """
    s = _session(client, db, "unl-4")

    shut = _page(client, s)
    assert re.search(r'id="roster-unlock-panel"\s+hidden', shut), (
        "the panel does not ship collapsed"
    )
    assert 'aria-expanded="false"' in _card(shut)

    open_ = _page(client, s, "?unlocked=1")
    assert not re.search(r'id="roster-unlock-panel"\s+hidden', open_), (
        "?unlocked=1 does not open the panel"
    )
    assert 'aria-expanded="true"' in _card(open_)


# ── The redirects the plan called out ─────────────────────────────────


def test_delete_all_returns_with_the_panel_still_open(
    client: TestClient, db: Session
) -> None:
    """A control inside the panel must not close the panel it was used
    from.

    Named in the plan's rung-6 entry because 19P.1 rung 3b shipped
    exactly this omission on Reviewers and had to fix it after the fact
    — the cut table justified that slice as "redirect-only" because the
    route already answered 303. It matched the status code; it did not
    match the contract.
    """
    s = _session(client, db, "unl-5")
    response = client.post(
        f"/operator/sessions/{s.id}/observers/delete-all",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert response.headers["location"].endswith(
        "/observers?unlocked=1#roster-card"
    ), response.headers["location"]


def test_a_successful_import_returns_with_the_panel_still_open(
    client: TestClient, db: Session
) -> None:
    """Same rule, stated once about the panel rather than three times
    about its controls: a Save does not close this card, `Lock` does."""
    s = _session(client, db, "unl-6", rows=0)
    response = client.post(
        f"/operator/sessions/{s.id}/observers/import",
        files={"file": ("o.csv", CSV, "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert response.headers["location"].endswith(
        "/observers?unlocked=1#roster-card"
    ), response.headers["location"]


def test_a_failed_import_arrives_with_the_panel_open(
    client: TestClient, db: Session
) -> None:
    """The one path `?unlocked=1` cannot reach: a parse failure
    re-renders the page in place and returns 400 WITH it.

    Left collapsed, the operator would see no errors at all —
    `validation_results.html` renders the issue list *inside* the card
    the panel holds. Invisible to every other assertion in this file,
    because `hidden` hides nothing without a layout engine: the issues
    are in the markup either way.
    """
    s = _session(client, db, "unl-7", rows=0)
    response = client.post(
        f"/operator/sessions/{s.id}/observers/import",
        files={"file": ("bad.csv", b"NotAColumn\nx\n", "text/csv")},
        follow_redirects=False,
    )
    assert response.status_code == 400, response.status_code
    assert not re.search(
        r'id="roster-unlock-panel"\s+hidden', response.text
    ), "a failed import answers with the errors hidden"


# ── Gating ────────────────────────────────────────────────────────────


def test_the_panel_renders_on_ready_where_reviewers_would_not(
    client: TestClient, db: Session
) -> None:
    """`not is_archived`, NOT Reviewers' `is_editable`.

    Rung 2 relaxed every mutating observers route to
    `_require_not_archived` — import and delete-all included — so on
    `ready` both of this panel's tenants are live. Suppressing them here
    would hide controls their own routes accept, which is the silent
    failure of rung 2 in reverse.
    """
    s = _session(client, db, "unl-8")
    s.status = "ready"
    db.flush()
    card = _card(_page(client, s))
    assert 'id="roster-unlock-btn"' in card
    assert 'id="upload-csv"' in card
    assert "danger-zone" in card


def test_the_panel_is_suppressed_on_archived_but_the_index_stays(
    client: TestClient, db: Session
) -> None:
    """Suppressed, not disabled — the page must not offer a control its
    route will refuse, and every route here 409s on `archived`.

    The PANEL, not the card. The readouts are informational in every
    lifecycle state, which is exactly what a mutating control is not: an
    operator on an archived session still wants to know how big the
    roster is and which columns arrived. The first draft of this rung
    gated the whole card and was corrected by the author.
    """
    s = _session(client, db, "unl-9")
    s.status = "archived"
    db.flush()
    markup = _markup(_page(client, s))
    assert 'id="roster-card"' in markup, "the index went with the panel"
    assert 'class="roster-readouts"' in markup
    assert 'id="roster-unlock-panel"' not in markup
    assert 'id="roster-unlock-btn"' not in markup
    assert 'id="upload-csv"' not in markup
    assert "danger-zone" not in markup


def test_the_panel_stands_down_in_edit_mode(
    client: TestClient, db: Session
) -> None:
    """Unlock and row-editing are mutually exclusive — the Unlock
    affordance stands down while a row is being typed into. The index
    stays, for the same reason it survives `archived`."""
    s = _session(client, db, "unl-10")
    first = db.execute(
        select(Observer).where(Observer.session_id == s.id)
    ).scalars().first()
    for suffix in ("?add=1", f"?edit_id={first.id}"):
        markup = _markup(_page(client, s, suffix))
        assert 'id="roster-unlock-panel"' not in markup, suffix
        assert 'id="roster-unlock-btn"' not in markup, suffix
        assert 'class="roster-readouts"' in markup, suffix


def test_the_index_lists_every_column_the_table_renders(
    client: TestClient, db: Session
) -> None:
    """The rule `reviewer_column_state` was written waiting for a second
    caller to settle: **the index mirrors the columns the preview table
    renders**, so the two cannot disagree.

    On Reviewers that is identity plus only the POPULATED tag slots,
    because its unpopulated tag columns are hidden. Here it is all
    three, because none are hidden — this page has one fixed tag slot
    that always renders and no column chips at all (rung 3). Same
    sentence, different answer, because the two tables differ.

    A zero is the point, not an omission: `Tag (0)` says the CSV carried
    no `ObserverTag1` column, which is a fact about the import.
    """
    s = _session(client, db, "unl-16", rows=0)
    card = _card(_page(client, s))
    assert "Observers roster:" in card
    assert _roster_count(card) == "0 observers", _roster_count(card)
    for label in ("Name (0)", "Email (0)", "Tag (0)"):
        assert label in card, f"{label} missing from an empty roster"

    # Populated, each count is its OWN column's. Deliberately made to
    # differ from each other and from the roster size: three rows, two
    # with a name, one with a tag. Equal counts would let any readout
    # stand in for any other — the mutation "Name counts email" passed
    # against a fixture where every row had both.
    s2 = _session(client, db, "unl-17", rows=3, named=2, tagged=1)
    card2 = _card(_page(client, s2))
    assert _roster_count(card2) == "3 observers", _roster_count(card2)
    assert "Email (3)" in card2, "Email is required, so it tracks rows"
    assert "Name (2)" in card2, "Name is not counting its own column"
    assert "Tag (1)" in card2, "Tag is not counting its own column"

    # And the roster count is a real one, not the pluralizer agreeing
    # with itself.
    s3 = _session(client, db, "unl-17b", rows=1)
    assert _roster_count(_card(_page(client, s3))) == "1 observer"


def test_the_index_counts_the_whole_roster_not_the_filtered_window(
    client: TestClient, db: Session
) -> None:
    """It is the ROSTER index, so a search must not shrink it.

    The two counts this page carries answer different questions —
    `total_row_count` is the roster, `displayed_row_count` the window
    the filter left — and they are equal on every unfiltered page, which
    is how swapping them survived the first mutation table.
    """
    s = _session(client, db, "unl-19", rows=3)
    unfiltered = _card(_page(client, s))
    filtered = _card(_page(client, s, "?q=o0%40example.org"))

    assert _roster_count(unfiltered) == "3 observers"
    assert _roster_count(filtered) == "3 observers", (
        "a search shrank the roster index"
    )
    # ...and the filter really did bite, or the assertion above is
    # about nothing.
    body = _page(client, s, "?q=o0%40example.org")
    rows = body.count('class="observer-select"')
    assert rows == 1, f"the filter matched {rows} rows, not 1"


def test_the_tag_column_reads_tag_not_tag1(
    client: TestClient, db: Session
) -> None:
    """Author's call, 19P.2 rung 6: this page has exactly one tag slot,
    so the digit numbered a series of one.

    Both display sites move together — the index and the `<th>` — or
    the index disagrees with the table it indexes. The CSV column stays
    `ObserverTag1`: an identifier in a file contract, and renaming it
    would break every existing import for a cosmetic gain.
    """
    body = _page(client, _session(client, db, "unl-18"))
    markup = _markup(body)
    assert "<th>Tag</th>" in markup, "the table header still reads Tag1"
    assert "<th>Tag1</th>" not in markup
    assert "Tag1 (" not in markup, "the index still reads Tag1"
    # ...and the contract the operator uploads against is untouched.
    assert "ObserverTag1" in markup, (
        "the CSV column name was renamed with the display label"
    )

    # Every DISPLAY site moves together, or one row reads `Tag` in its
    # column header and `Observer: Tag 1` in its Cohort cell. The cold
    # read found both of these still carrying the digit.
    assert "Observer: Tag 1" not in markup, (
        "the cohort rule builder still offers `Observer: Tag 1`"
    )
    assert ">Observer: Tag</option>" in markup
    from app.web.views._observers import _COHORT_OBSERVER_FRIENDLY
    assert _COHORT_OBSERVER_FRIENDLY["observer.tag1"] == "Observer: Tag"
    # The stored KEY is not a display label and must not move — a saved
    # `cohort_rule` holds it.
    assert 'value="observer.tag1"' in markup


def test_the_danger_zone_is_gated_on_rows_and_upload_is_not(
    client: TestClient, db: Session
) -> None:
    """The gate travelled with the card and is not cosmetic:
    `delete_all_observers` is not a no-op on an empty roster — it writes
    an audit row reading "Deleted all 0 observers" — so an ungated card
    offers a destructive control with nothing to destroy.

    Upload keeps no such gate: an empty roster is exactly when the
    initial bulk import is wanted.
    """
    panel = _panel(_page(client, _session(client, db, "unl-11", rows=0)))
    assert "danger-zone" not in panel
    assert 'id="upload-csv"' in panel


# ── The things a move quietly breaks ──────────────────────────────────


def test_each_confirm_key_still_appears_exactly_once(
    client: TestClient, db: Session
) -> None:
    """`base.html` pairs a confirm to its button with a first-match
    `querySelector`, so a duplicated key gates the WRONG button.

    A move is exactly how a key gets duplicated — the card is copied to
    its new home and the old one left behind. Counted on the rendered
    page, which is the only place the collision could happen.
    """
    body = _page(client, _session(client, db, "unl-12"))
    for key in ("replace-observers", "delete-all"):
        assert body.count(f'data-delete-confirm="{key}"') == 1, key
        assert body.count(f'data-delete-btn="{key}"') == 1, key


def test_each_confirm_sentence_is_one_flex_item(
    client: TestClient, db: Session
) -> None:
    """`.confirm-label` is `display: flex`, so the sentence must live in
    ONE child element.

    A bare text run inside a flex container becomes its own anonymous
    flex item and takes the container's 8px `gap` with it, detaching the
    closing "." from the pill before it — 12px off instead of the pill's
    own 4px margin. `spec/ui_elements.md` §6 states the constraint and
    records exactly how the defect arrives: *"by moving a label onto it
    — correctly, a class over an inline style — and it was invisible in
    the markup."*

    Which is exactly how it arrived here. This rung swapped
    `style="font-weight: normal;"` for `class="confirm-label"` on both
    confirms and did not bring the wrapper; the cold read measured 12px
    in Chromium on both. Nothing in the suite would have caught it, so
    this test is the thing that makes the constraint checkable rather
    than merely written down.
    """
    panel = _panel(_page(client, _session(client, db, "unl-22")))

    for key in ("replace-observers", "delete-all"):
        label = re.search(
            r'<label class="confirm-label">(.*?)</label>',
            panel[panel.index(f'data-delete-confirm="{key}"') - 400:],
            re.S,
        )
        assert label, key
        body = label.group(1)
        # Everything after the checkbox must be inside one element: no
        # bare text between the `<input>` and the wrapper, and none
        # after the wrapper closes.
        after_input = body[body.index(">", body.index("<input")) + 1:]
        after_input = re.sub(r"\{#.*?#\}", "", after_input, flags=re.S)
        assert after_input.strip().startswith("<span>"), (
            f"{key}: the sentence does not start in a wrapper"
        )
        assert after_input.strip().endswith("</span>"), (
            f"{key}: text escapes the wrapper — the closing period is "
            "its own flex item and detaches from the pill"
        )


def test_the_danger_zone_can_carry_its_own_accessible_name(
    client: TestClient, db: Session
) -> None:
    """`aria-labelledby` on a role-less `<div>` is dead markup: a
    `<div>` is `generic` and a generic element takes no accessible name.

    The first draft added the attribute to a `<div>` — so the thing the
    rung added did nothing, and Chromium exposed one region on the page
    (the upload card) rather than two.
    """
    panel = _panel(_page(client, _session(client, db, "unl-23")))
    assert '<section class="card danger-zone"' in panel, (
        "the Danger Zone is a div, so its aria-labelledby is inert"
    )
    assert 'aria-labelledby="observers-danger-h"' in panel
    assert 'id="observers-danger-h"' in panel, "nothing to point at"


def test_the_panel_is_reachable_without_javascript(
    client: TestClient, db: Session
) -> None:
    """This rung moves both mutating cards behind a button, so with JS
    off the page would lose the import and the delete-all outright.

    `?unlocked=1` already renders the panel open server-side — it exists
    for the redirects both controls answer with — so the fallback is a
    link to a state the server supports, not new machinery.
    """
    card = _card(_page(client, _session(client, db, "unl-13")))
    assert "<noscript>" in card
    assert "?unlocked=1#roster-card" in card, (
        "no no-JS route into the panel"
    )
    # And back out again, from the open page.
    open_card = _card(
        _page(client, _session(client, db, "unl-14"), "?unlocked=1")
    )
    assert "<noscript>" in open_card
    assert re.search(
        r'<noscript>\s*<a class="btn secondary"\s*\n?\s*href="[^"]*/observers#roster-card"',
        open_card,
    ), "no no-JS route back out of the panel"


def test_the_toggle_moves_one_control_rather_than_rendering_two(
    client: TestClient, db: Session
) -> None:
    """Two copies of one control is how they drift apart, and the
    `querySelector` in the toggle would find only the first of them.

    Pinned on both arrival states, because the bug this guards against
    is a second copy appearing in one of them.
    """
    for suffix in ("", "?unlocked=1"):
        card = _card(
            _page(client, _session(client, db, f"unl-15{len(suffix)}"),
                  suffix)
        )
        assert card.count('id="roster-unlock-btn"') == 1, suffix
        assert card.count('class="roster-card-actions"') == 1, suffix
