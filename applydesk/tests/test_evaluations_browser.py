"""The gate pages under Evaluations in a real Chromium (segment AD1H):
the table sorted as Review Robin's, click and shift-click; and AD1G
rung 6b's operations by mode, kept in the tab. Without a
Chromium build the test skips, saying why; ``RRW_REQUIRE_BROWSER=1``
(set by CI) turns that skip into a failure."""

from __future__ import annotations

import pytest
from playwright.sync_api import Locator, Page

from applydesk.tests.test_form_browser import page as page

ORIGIN = "http://applydesk.test"
GATE3 = f"{ORIGIN}/applydesk/operator/exercises/wa9juxbc2t/evaluations/gate_3"


def _badges(page: Page) -> list[str]:
    return page.locator("th.ev-sortable .ev-sort-badge").all_inner_texts()


def test_a_column_sorts_and_shift_adds_it_to_the_cascade(page: Page) -> None:
    """As Review Robin's tables (author, 2026-11-17): a click sorts, again
    reverses, again clears; shift-click adds a column to the cascade."""
    page.goto(GATE3)
    assert _badges(page) == ["↕", "↕", "↕", "↕"]
    page.get_by_role("link", name="Sort by Evaluator").click()
    assert page.url.endswith("?sort=evaluator#ev-table-card")
    assert _badges(page) == ["↕", "1↑", "↕", "↕"]
    page.get_by_role("link", name="Sort by Applicant").click(modifiers=["Shift"])
    assert "sort=evaluator%2Ccandidate" in page.url
    assert _badges(page) == ["2↑", "1↑", "↕", "↕"]
    rows = page.locator("tbody tr")
    first = [rows.nth(i).locator("td").nth(1).inner_text() for i in range(4)]
    assert first == sorted(first, key=str.casefold)
    page.get_by_role("link", name="Sort by Evaluator").click()  # alone, up: replaces
    assert _badges(page) == ["↕", "1↑", "↕", "↕"]
    page.get_by_role("link", name="Sort by Evaluator").click()
    assert _badges(page) == ["↕", "1↓", "↕", "↕"]
    page.get_by_role("link", name="Sort by Evaluator").click()
    assert _badges(page) == ["↕", "↕", "↕", "↕"] and "sort=" not in page.url


# --- AD1G rung 6b: each mode's operations, kept in the tab ---
def _as(monkeypatch: pytest.MonkeyPatch, key: str, **changes: object) -> None:
    """The model exercise's gate ``key`` changed for one test (its mode, or
    sent no more), as Process would have set it."""
    from dataclasses import replace

    from applydesk import stages, workflow

    model = stages._STAGES["wa9juxbc2t"]  # pyright: ignore[reportPrivateUsage]  -- a sample's shape
    staged = tuple(
        replace(st, columns=tuple(replace(c, **changes) if c.key == key else c for c in st.columns))
        for st in model
    )
    monkeypatch.setitem(stages._STAGES, "wa9juxbc2t", staged)  # pyright: ignore[reportPrivateUsage]  -- as above
    monkeypatch.setitem(workflow._GATES["wa9juxbc2t"], key, ("Ready", ""))  # pyright: ignore[reportPrivateUsage]  -- as above


def _row(page: Page, who: str, evaluator: str = "") -> Locator:
    rows = page.locator("tbody tr", has_text=who)
    return rows.filter(has_text=evaluator).first if evaluator else rows.first


def _counts(page: Page) -> str:
    return page.locator("[data-ev-counts]").inner_text()


def test_pairs_are_approved_by_dossier_or_all_and_kept_across_pages(page: Page) -> None:
    page.goto(GATE3)
    kenji = _row(page, "Kenji Russo")
    kenjis = page.locator("tbody tr", has_text="Kenji Russo").locator("[data-ev-state]")
    assert kenji.locator("[data-ev-state]").text_content() == "Suggested"
    assert not page.locator("[data-ev-unsaved]").is_visible()
    kenji.get_by_role("button", name="Approve").click()
    # Ruling 34: a dossier's evaluators are approved together.
    assert kenjis.count() == 2 and set(kenjis.all_text_contents()) == {"Approved"}
    assert page.locator("[data-ev-said]").inner_text() == "Evaluators approved for Kenji Russo."
    # AD-25: a second click on Approved takes the approval back.
    kenji.get_by_role("button", name="Approved").click()
    assert set(kenjis.all_text_contents()) == {"Suggested"}
    assert not page.locator("[data-ev-unsaved]").is_visible()
    kenji.get_by_role("button", name="Approve").click()
    assert page.locator("[data-ev-unsaved]").is_visible()
    # Kept in the tab: a sort reloads the page, the approval stands.
    page.get_by_role("link", name="Sort by Evaluator").click()
    first = page.locator("tbody tr", has_text="Kenji Russo").first
    states = page.locator("tbody tr", has_text="Kenji Russo").locator("[data-ev-state]")
    assert "Approved" in states.all_text_contents()
    assert first.is_visible()
    page.get_by_role("button", name="Approve all").click()
    assert page.locator("[data-ev-said]").inner_text() == "All 80 pairs approved."
    assert set(page.locator("tbody [data-ev-state]").all_text_contents()) == {"Approved"}
    assert page.get_by_role("button", name="Approve all").is_disabled()
    # AD-25: discarding more than a few changes asks first.
    asked: list[str] = []
    page.once("dialog", lambda d: (asked.append(d.message), d.dismiss())[1])
    page.get_by_role("button", name="Discard changes").click()
    assert asked and "Discard all 80 changes" in asked[0]
    assert set(page.locator("tbody [data-ev-state]").all_text_contents()) == {"Approved"}
    page.once("dialog", lambda d: d.accept())
    page.get_by_role("button", name="Discard changes").click()
    assert set(page.locator("tbody [data-ev-state]").all_text_contents()) == {"Suggested"}
    assert not page.locator("[data-ev-unsaved]").is_visible()
    page.reload()
    assert set(page.locator("tbody [data-ev-state]").all_text_contents()) == {"Suggested"}
    # AD-25: Approve all asks first while a dossier is short; declined,
    # nothing is approved.
    _row(page, "Kenji Russo").get_by_role("button", name="Remove").click()
    asked.clear()
    page.once("dialog", lambda d: (asked.append(d.message), d.dismiss())[1])
    page.get_by_role("button", name="Approve all").click()
    assert asked == ["Approve every pair? 1 dossier is still short of evaluators."]
    assert "Approved" not in page.locator("tbody [data-ev-state]").all_text_contents()


def test_a_pair_is_removed_and_added_within_the_total(page: Page) -> None:
    """A dossier under the Total's min is short; one at its max takes no
    more; the head's counts and the load line follow every pair."""
    page.goto(GATE3)
    assert _counts(page) == "40 dossiers · 40 filled"
    assert not page.locator("[data-ev-add]").is_visible()  # closed until + Pair
    page.get_by_role("button", name="+ Pair").click()
    page.get_by_role("button", name="Cancel").click()
    assert not page.locator("[data-ev-add]").is_visible()
    load = page.locator("[data-ev-load]").inner_text()
    pair = _row(page, "Kenji Russo")
    evaluator = pair.locator("td").nth(1).inner_text()
    pair.get_by_role("button", name="Remove").click()
    assert pair.locator("[data-ev-state]").text_content() == "Removed"
    other = page.locator("tbody tr", has_text="Kenji Russo").nth(1)
    assert other.locator("[data-ev-state]").text_content() == "Short by 1"
    assert _counts(page) == "40 dossiers · 39 filled · 1 short"
    assert page.locator("[data-ev-load]").inner_text() != load
    # + Pair: Kenji's own evaluator is not offered again; another is.
    page.get_by_role("button", name="+ Pair").click()
    page.locator("[data-ev-add-who]").select_option(label="Kenji Russo")
    offered = page.locator("[data-ev-add-evaluator] option").all_inner_texts()
    other_name = other.locator("td").nth(1).inner_text()
    assert not [o for o in offered if o.startswith(other_name + " ·")]
    # Adding back the one removed only undoes the removal.
    back = next(o for o in offered if o.startswith(evaluator + " ·"))
    page.locator("[data-ev-add-evaluator]").select_option(label=back)
    page.get_by_role("button", name="Add the pair").click()
    assert page.locator("tbody tr[data-ev-added]").count() == 0
    assert pair.locator("[data-ev-state]").text_content() == "Suggested"
    assert not page.locator("[data-ev-unsaved]").is_visible()
    pair.get_by_role("button", name="Remove").click()
    # One who was not on it is added.
    offered = page.locator("[data-ev-add-evaluator] option").all_inner_texts()
    fresh = next(o for o in offered if not o.startswith(evaluator + " ·"))
    page.locator("[data-ev-add-evaluator]").select_option(label=fresh)
    page.get_by_role("button", name="Add the pair").click()
    added = page.locator("tbody tr[data-ev-added]")
    assert added.count() == 1 and "Added" in (added.text_content() or "")
    assert _counts(page) == "40 dossiers · 40 filled"
    # At its max, two: no third.
    page.get_by_role("button", name="Add the pair").click()
    assert page.locator("[data-ev-add-why]").inner_text() == (
        "Kenji Russo already has the most evaluators, 2."
    )
    # Undo puts the removed back; the added one removed goes.
    added.get_by_role("button", name="Remove").click()
    pair.get_by_role("button", name=f"Undo removing {evaluator} from Kenji Russo").click()
    assert _counts(page) == "40 dossiers · 40 filled"
    assert not page.locator("[data-ev-unsaved]").is_visible()


def test_an_assigned_gate_starts_empty_and_takes_pairs(
    page: Page, monkeypatch: pytest.MonkeyPatch
) -> None:
    _as(monkeypatch, "g3", mode="assigned")
    page.goto(GATE3)
    assert _counts(page) == "40 dossiers · 0 filled · 40 short"
    kenji = page.locator("tbody tr:not([data-ev-added])", has_text="Kenji Russo")
    assert kenji.locator("[data-ev-state]").text_content() == "Not assigned"
    page.get_by_role("button", name="+ Pair").click()
    page.locator("[data-ev-add-who]").select_option(label="Kenji Russo")
    page.get_by_role("button", name="Add the pair").click()
    first = page.locator("tbody tr[data-ev-added]")
    assert first.locator("[data-ev-state]").text_content() == "Short by 1"
    assert not kenji.is_visible()  # its None yet row gives way
    page.get_by_role("button", name="Add the pair").click()
    assert set(page.locator("tbody tr[data-ev-added] [data-ev-state]").all_text_contents()) == {
        "Assigned"
    }
    assert _counts(page) == "40 dossiers · 1 filled · 39 short"


def test_an_automatic_gate_is_edited_by_hand_never_re_run(
    page: Page, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ruling 48: an Automatic fill is never re-made, only edited by hand:
    no Re-run, and + Pair and Remove as the other modes."""
    _as(monkeypatch, "g3", mode="automatic")
    page.goto(GATE3)
    assert page.get_by_role("button", name="Re-run").count() == 0
    assert page.get_by_role("button", name="+ Pair").count() == 1
    pair = page.locator("tbody tr").first
    pair.get_by_role("button", name="Remove").click()
    assert pair.locator("[data-ev-state]").text_content() == "Removed"
    assert page.locator("[data-ev-unsaved]").is_visible()
    # The edit is kept through a reload, as in the other modes.
    page.reload()
    assert pair.locator("[data-ev-state]").text_content() == "Removed"
    pair.get_by_role("button", name="Undo", exact=False).click()
    assert pair.locator("[data-ev-state]").text_content() != "Removed"


def test_an_approval_stands_through_undo_and_goes_with_an_added_pair(page: Page) -> None:
    page.goto(GATE3)
    pair = _row(page, "Kenji Russo")
    pair.get_by_role("button", name="Approve").click()
    assert page.locator("[data-ev-said]").inner_text() == "Evaluators approved for Kenji Russo."
    assert pair.get_by_role("button", name="Remove").evaluate("b => b === document.activeElement")
    pair.get_by_role("button", name="Remove").click()
    pair.get_by_role("button", name="Undo", exact=False).click()
    assert pair.locator("[data-ev-state]").text_content() == "Approved"
    page.get_by_role("button", name="Discard changes").click()
    # An added pair approved, then removed: no change is left behind.
    page.get_by_role("button", name="+ Pair").click()
    page.locator("[data-ev-add-who]").select_option(label="Kenji Russo")
    pair.get_by_role("button", name="Remove").click()
    page.get_by_role("button", name="Add the pair").click()
    added = page.locator("tbody tr[data-ev-added]")
    added.get_by_role("button", name="Approve").click()
    # The dossier's other pair is approved with it (ruling 34), and taken
    # back with it.
    other = page.locator("tbody tr:not([data-ev-added])", has_text="Kenji Russo").nth(1)
    assert other.locator("[data-ev-state]").text_content() == "Approved"
    added.get_by_role("button", name="Approved").click()
    assert other.locator("[data-ev-state]").text_content() == "Suggested"
    added.get_by_role("button", name="Remove").click()
    pair.get_by_role("button", name="Undo", exact=False).click()
    assert not page.locator("[data-ev-unsaved]").is_visible()
    page.locator("[data-ev-add-who]").press("Escape")  # the box still open
    assert not page.locator("[data-ev-add]").is_visible()


def test_added_pairs_show_on_the_first_page_and_as_the_search_finds(
    page: Page, monkeypatch: pytest.MonkeyPatch
) -> None:
    from applydesk import paging

    monkeypatch.setattr(paging, "PAGE_SIZE", 40)
    page.goto(GATE3)
    pair = _row(page, "Kenji Russo")
    gone = pair.locator("td").nth(1).inner_text()
    pair.get_by_role("button", name="Remove").click()
    page.get_by_role("button", name="+ Pair").click()
    page.locator("[data-ev-add-who]").select_option(label="Kenji Russo")
    fresh = next(
        o
        for o in page.locator("[data-ev-add-evaluator] option").all_inner_texts()
        if not o.startswith(gone + " ·")
    )
    page.locator("[data-ev-add-evaluator]").select_option(label=fresh)
    page.get_by_role("button", name="Add the pair").click()
    added = page.locator("tbody tr[data-ev-added]")
    name = added.locator("td").nth(1).locator("span").first.inner_text()
    page.goto(f"{GATE3}?offset=40")
    assert added.count() == 0  # the first page's only
    page.goto(f"{GATE3}?q=nobody-at-all")
    assert added.count() == 0
    page.goto(f"{GATE3}?q={name.split()[-1]}")
    assert added.count() == 1
    page.goto(f"{GATE3}?q=kenji")
    assert added.count() == 1


def test_a_stale_change_kept_in_the_tab_counts_for_nothing(page: Page) -> None:
    page.goto(GATE3)
    page.evaluate(
        """() => sessionStorage.setItem("applydesk-ev:wa9juxbc2t:g3:suggested", JSON.stringify({
            removed: ["nobody|x@example.edu"],
            added: [{d: "gone", e: "x@example.edu", n: "X", s: "Y"}],
            approved: ["nobody|y@example.edu"]}))"""
    )
    page.reload()
    assert not page.locator("[data-ev-unsaved]").is_visible()
    assert page.locator("tbody tr[data-ev-added]").count() == 0
    page.evaluate("""() => sessionStorage.setItem("applydesk-ev:wa9juxbc2t:g3:suggested", "{}")""")
    page.reload()
    assert not page.locator("[data-ev-unsaved]").is_visible()


def test_a_source_s_min_and_max_hold_as_the_total_s(
    page: Page, monkeypatch: pytest.MonkeyPatch
) -> None:
    """As the server's fill: a dossier its second source gives fewer than
    that source's min is short, its Total met or not; + Pair stops at a
    source's max."""
    from applydesk.stages import Source, Total

    two = (Source("panel", "residential-staff", 1, 2), Source("panel", "current-ras", 1, 1))
    _as(monkeypatch, "g3", sources=two, total=Total(2, 3))
    page.goto(GATE3)
    assert "short" not in _counts(page)
    pair = page.locator("tbody tr", has_text="Kenji Russo").filter(has_text="Current RAs").first
    pair.get_by_role("button", name="Remove").click()
    others = page.locator("tbody tr:not(.ev-removed)", has_text="Kenji Russo")
    assert set(others.locator("[data-ev-state]").all_text_contents()) == {"Short"}
    assert _counts(page).endswith("· 1 short")
    pair.get_by_role("button", name="Undo", exact=False).click()
    # Under the Total's max of 3 once a staff member is off it, but at
    # Current RAs' max of 1.
    page.locator("tbody tr", has_text="Kenji Russo").filter(
        has_text="Residential staff"
    ).first.get_by_role("button", name="Remove").click()
    page.get_by_role("button", name="+ Pair").click()
    page.locator("[data-ev-add-who]").select_option(label="Kenji Russo")
    ra = next(
        o
        for o in page.locator("[data-ev-add-evaluator] option").all_inner_texts()
        if o.endswith("· Current RAs")
    )
    page.locator("[data-ev-add-evaluator]").select_option(label=ra)
    page.get_by_role("button", name="Add the pair").click()
    assert page.locator("[data-ev-add-why]").inner_text() == (
        "Kenji Russo already has the most from Current RAs, 1."
    )


def test_no_one_is_offered_to_review_themself(page: Page, monkeypatch: pytest.MonkeyPatch) -> None:
    """Gate 1's current RAs review every applicant but themselves: Aisha,
    an RA applying to return, is not offered for her own dossier."""
    _as(monkeypatch, "g1", mode="suggested")
    page.goto(GATE3.replace("gate_3", "gate_1"))
    page.get_by_role("button", name="+ Pair").click()
    page.locator("[data-ev-add-who]").select_option(label="Aisha Bello")
    # Her 29 reviewers are on it already: no one is left but herself, and
    # she is not offered.
    assert page.locator("[data-ev-add-evaluator] option").count() == 0
    page.get_by_role("button", name="Add the pair").click()
    assert page.locator("[data-ev-add-why]").inner_text() == "No one left to add from its panels."


def test_undo_and_add_hold_the_limits_and_the_picker_follows(page: Page) -> None:
    """Codex on #3961: Undo cannot take a dossier past its max, and the
    open + Pair picker follows an Undo, so no evaluator is added twice."""
    page.goto(GATE3)
    rows = page.locator("tbody tr:not([data-ev-added])", has_text="Kenji Russo")
    first, second = rows.nth(0), rows.nth(1)
    gone = first.locator("td").nth(1).inner_text()
    first.get_by_role("button", name="Remove").click()
    page.get_by_role("button", name="+ Pair").click()
    page.locator("[data-ev-add-who]").select_option(label="Kenji Russo")
    fresh = next(
        o
        for o in page.locator("[data-ev-add-evaluator] option").all_inner_texts()
        if not o.startswith(gone + " ·")
    )
    page.locator("[data-ev-add-evaluator]").select_option(label=fresh)
    page.get_by_role("button", name="Add the pair").click()
    # Back at its max of two: Undo would make three.
    first.get_by_role("button", name="Undo", exact=False).click()
    assert first.locator("[data-ev-state]").text_content() == "Removed"
    assert page.locator("[data-ev-said]").inner_text() == (
        "Not undone: Kenji Russo already has the most evaluators, 2. Remove one first."
    )
    # The picker follows: both removed, the first chosen, then undone.
    page.locator("tbody tr[data-ev-added]").get_by_role("button", name="Remove").click()
    second.get_by_role("button", name="Remove").click()
    page.locator("[data-ev-add-evaluator]").select_option(
        label=next(
            o
            for o in page.locator("[data-ev-add-evaluator] option").all_inner_texts()
            if o.startswith(gone + " ·")
        )
    )
    first.get_by_role("button", name="Undo", exact=False).click()
    offered = page.locator("[data-ev-add-evaluator] option").all_inner_texts()
    assert not [o for o in offered if o.startswith(gone + " ·")]
    page.get_by_role("button", name="Add the pair").click()
    assert _counts(page) == "40 dossiers · 40 filled"
    assert (
        page.locator("tbody tr", has_text="Kenji Russo")
        .locator("td:nth-child(2)", has_text=gone)
        .count()
        == 1
    )
