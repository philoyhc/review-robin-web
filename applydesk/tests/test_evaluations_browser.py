"""The gate pages under Evaluations in a real Chromium (segment AD1H):
the table sorted as Review Robin's, click and shift-click. Without a
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
    page.get_by_role("link", name="Sort by Candidate").click(modifiers=["Shift"])
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


def test_pairs_are_approved_one_by_one_or_all_and_kept_across_pages(page: Page) -> None:
    page.goto(GATE3)
    kenji = _row(page, "Kenji Russo")
    assert kenji.locator("[data-ev-state]").text_content() == "Suggested"
    assert not page.locator("[data-ev-unsaved]").is_visible()
    kenji.get_by_role("button", name="Approve").click()
    assert kenji.locator("[data-ev-state]").text_content() == "Approved"
    assert kenji.locator('[data-ev-act="approve"]').is_disabled()
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
    page.get_by_role("button", name="Discard changes").click()
    assert set(page.locator("tbody [data-ev-state]").all_text_contents()) == {"Suggested"}
    assert not page.locator("[data-ev-unsaved]").is_visible()
    page.reload()
    assert set(page.locator("tbody [data-ev-state]").all_text_contents()) == {"Suggested"}


def test_a_pair_is_removed_and_added_within_the_total(page: Page) -> None:
    """A dossier under the Total's min is short; one at its max takes no
    more; the head's counts and the load line follow every pair."""
    page.goto(GATE3)
    assert _counts(page) == "40 dossiers · 40 filled"
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
    # One who was not on it: adding back the one removed only undoes it.
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


def test_an_automatic_gate_re_runs(page: Page, monkeypatch: pytest.MonkeyPatch) -> None:
    _as(monkeypatch, "g3", mode="automatic")
    page.goto(GATE3)
    assert page.get_by_role("button", name="+ Pair").count() == 0
    assert set(page.locator("tbody [data-ev-state]").all_text_contents()) == {"Filled"}
    page.get_by_role("button", name="Re-run").click()
    assert page.locator("[data-ev-said]").inner_text() == (
        "Re-run: every dossier filled as its sources give."
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
