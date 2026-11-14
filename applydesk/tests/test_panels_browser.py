"""The Panels page in a real Chromium (segment AD1F, rung 4e): one table,
a column per panel. Rows and panels are added, ticked, copied, retired
and removed, each email checked, a CSV in and out; Form and Process link
to a chosen panel. Skips without a Chromium build, as
`test_form_browser.py`'s."""

from __future__ import annotations

from playwright.sync_api import Locator, Page

from applydesk.tests.test_form_browser import ORIGIN
from applydesk.tests.test_form_browser import page as page  # the fixture, re-exported

PANELS = f"{ORIGIN}/applydesk/operator/exercises/wa9juxbc2t/panels"
BLIND = f"{ORIGIN}/applydesk/operator/exercises/k7mfr3pq8z/panels"


def _row(page: Page, email: str) -> Locator:
    return page.locator("[data-pn-row]").filter(
        has=page.locator(f'[data-pn="email"][value="{email}"]')
    )


def _count(page: Page, key: str) -> str:
    return page.locator(f'th[data-panel="{key}"] [data-pn-count]').inner_text()


def test_ticks_rows_and_their_checks(page: Page) -> None:
    page.goto(PANELS)
    counts = page.locator("[data-pn-counts]")
    assert counts.inner_text() == "8 people · 4 panels · 4 in use"
    zoe = _row(page, "zoe.tan@example.edu")
    # Ruling 22: a row is inert until selected, its ticks too.
    tick = zoe.locator('input[data-pn-panel="panel-b"]')
    assert tick.is_disabled() and not zoe.locator('[data-pn="name"]').is_visible()
    assert zoe.locator("[data-pn-pill]").is_visible()
    zoe.locator('[data-pn-view="name"]').click()  # only its tick selects it, as RRW's
    assert zoe.get_attribute("data-sel") is None
    zoe.locator("[data-pn-select]").check()
    assert zoe.get_attribute("data-sel") == "" and zoe.locator('[data-pn="name"]').is_visible()
    tick.check()
    assert _count(page, "panel-b") == "2 people"
    assert page.locator('li[data-panel="panel-b"] [data-pn-count]').inner_text() == "2 people"
    zoe.locator("[data-pn-select]").uncheck()
    assert tick.is_disabled() and tick.is_checked()
    # An email not in the directory, and a repeated one, are named, on the
    # row and in the card; one found is a pill and names a blank row.
    page.locator('[data-pn-act="add"]').click()
    new = page.locator("[data-pn-row]").last
    assert new.get_attribute("data-sel") == ""
    assert new.locator('[data-pn="name"]').evaluate("e => e === document.activeElement")
    new.locator('[data-pn="name"]').fill("Kim Lee")
    entry = new.locator("[data-pn-entry]")
    entry.fill("kim")
    entry.press("Enter")
    assert new.locator("[data-pn-why]").inner_text() == "Not found in the directory."
    entry.fill("ZOE.TAN@example.edu")
    entry.press("Enter")
    assert new.locator("[data-pn-pill]").inner_text().startswith("zoe.tan@example.edu")
    assert new.locator("[data-pn-why]").inner_text() == "Listed more than once."
    issues = page.locator("[data-pn-issues]").inner_text()
    assert "Kim Lee: listed more than once." in issues
    new.locator('[data-pn-act="unverify"]').click()
    assert entry.input_value() == "zoe.tan@example.edu"
    # Put back to be changed, it is still the person it was.
    assert new.locator("[data-pn-why]").inner_text() == "Listed more than once."
    new.locator('[data-pn="name"]').fill("")
    entry.fill("Daniel Koh")
    entry.press("Enter")
    assert new.locator('[data-pn="name"]').input_value() == "Daniel Koh"
    assert not page.locator("[data-pn-issues]").is_visible()
    assert counts.inner_text() == "9 people · 4 panels · 4 in use"
    # Removing the only member of a panel in use is named.
    ana = _row(page, "ana.lim@example.edu")
    ana.locator("[data-pn-select]").check()
    ana.locator('[data-pn-act="remove"]').click()
    zoe.locator("[data-pn-select]").check()
    tick.uncheck()
    assert "Panel B is in use with nobody on it." in page.locator("[data-pn-issues]").inner_text()


def test_panels_are_made_copied_and_retired_only_unused(page: Page) -> None:
    page.goto(PANELS)
    # Every sample panel is in use: none may be retired.
    retire = page.locator('li[data-panel] [data-pn-act="retire"]')
    assert all(retire.nth(i).is_disabled() for i in range(4))
    page.locator('[data-pn-act="panel"]').click()
    name = page.locator("[data-pn-newname]")
    name.fill("panel a")
    page.locator('[data-pn-act="create"]').click()
    assert page.locator("[data-pn-newerr]").inner_text() == "A panel is already called panel a."
    name.fill("Panel C")
    name.press("Enter")
    heads = page.locator("th[data-panel] [data-pn-name]").all_inner_texts()
    assert heads[-1] == "Panel C" and _count(page, "made-1") == "0 people"
    sara = _row(page, "sara.ng@example.edu")
    assert sara.locator('input[data-pn-panel="made-1"]').is_disabled()
    sara.locator("[data-pn-select]").check()
    sara.locator('input[data-pn-panel="made-1"]').check()
    # Copy keeps the people; a copy is unused, so it may be retired.
    page.locator('li[data-panel="interviewers"] [data-pn-act="copy"]').click()
    assert (
        page.locator('th[data-panel="made-2"] [data-pn-name]').inner_text()
        == "Copy of Interviewers"
    )
    assert _count(page, "made-2") == "2 people"
    page.locator('li[data-panel="made-2"] [data-pn-act="retire"]').click()
    assert page.locator('th[data-panel="made-2"]').count() == 0
    assert page.locator('input[data-pn-panel="made-2"]').count() == 0
    assert page.locator("[data-pn-counts]").inner_text() == "8 people · 5 panels · 4 in use"
    # A person added after a panel was made gets its box.
    page.locator('[data-pn-act="add"]').click()
    assert page.locator("[data-pn-row]").last.locator('input[data-pn-panel="made-1"]').count() == 1


def test_a_panel_nothing_uses_retires(page: Page) -> None:
    page.goto(BLIND)
    page.locator('li[data-panel="interviewers"] [data-pn-act="retire"]').click()
    assert page.locator("th[data-panel] [data-pn-name]").all_inner_texts() == ["Panel A"]
    assert "Interviewers retired." in page.locator("[data-pn-said]").inner_text()


def test_a_csv_goes_out_and_comes_in(page: Page) -> None:
    page.goto(PANELS)
    csv = page.evaluate("window.applydeskPanelsCsv()")
    lines = csv.split("\r\n")
    assert lines[0] == "Name,Email,Note,Panel A,Panel B,Reviewer pool,Interviewers"
    assert lines[1] == "Zoe Tan,zoe.tan@example.edu,,x,,,"
    assert lines[4] == "Dr Hana Ito,hana.ito@example.edu,Life Sciences,,,x,"
    page.evaluate(
        """window.applydeskPanelsImport(
          "email,NAME,Panel B,Board\\r\\n" +
          "daniel.koh@example.edu,Dan Koh,yes,x\\r\\n" +
          "zoe.tan@example.edu,Zoe again,,\\r\\n" +
          "kim.lee@example.edu,Kim Lee,,\\r\\n" +
          "not-an-email,Nobody,,\\r\\n")"""
    )
    said = page.locator("[data-pn-said]").inner_text()
    assert said == (
        "1 person added. Already listed, not added: zoe.tan@example.edu. "
        "Not an email, not added: not-an-email. "
        "Not found in the directory, not added: kim.lee@example.edu. No panel called: Board."
    )
    dan = page.locator("[data-pn-row]").last  # added by the script, unselected
    assert dan.get_attribute("data-sel") is None
    assert dan.locator('[data-pn-view="name"]').inner_text() == "Dan Koh"
    assert dan.locator('input[data-pn-panel="panel-b"]').is_checked()
    assert _count(page, "panel-b") == "2 people"


def test_form_and_process_link_to_the_chosen_panel(page: Page) -> None:
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/wa9juxbc2t/form")
    card = page.locator(".fc", has=page.locator('[data-sum="label"]:text-is("Preferred reviewer")'))
    card.locator("[data-fc-toggle]").click()
    link = card.locator("[data-pick-edit]")
    assert link.is_visible() and link.inner_text() == "Edit on Panels →"
    assert (link.get_attribute("href") or "").endswith("/wa9juxbc2t/panels#panel-pool")
    card.locator('[data-f="pool"]').select_option("institution")
    assert not link.is_visible()
    card.locator('[data-f="pool"]').select_option("panel-b")
    assert (link.get_attribute("href") or "").endswith("#panel-panel-b")
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/c4xh2ndv6s/process")
    gate = page.locator('.pc-item[data-item="gate"]')
    page.locator("#pc-cards > .pc").nth(1).locator("[data-fc-toggle]").first.click()
    assert not gate.locator("[data-pick-edit]").is_visible()  # no panel yet


# --- 4d-4e cold read ---
def test_a_form_type_change_hides_the_edit_link(page: Page) -> None:
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/wa9juxbc2t/form")
    card = page.locator(".fc", has=page.locator('[data-sum="label"]:text-is("Preferred reviewer")'))
    card.locator("[data-fc-toggle]").click()
    link = card.locator("[data-pick-edit]")
    assert link.is_visible()
    card.locator('[data-f="type"]').select_option("string")
    card.locator('[data-f="type"]').select_option("people")
    assert not link.is_visible()


def test_a_panel_made_in_place_has_no_edit_link_yet(page: Page) -> None:
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/c4xh2ndv6s/process")
    page.locator("#pc-cards > .pc").nth(1).locator("[data-fc-toggle]").first.click()
    gate = page.locator('.pc-item[data-item="gate"]')
    link = gate.locator("[data-pick-edit]")
    gate.locator("[data-pc-panel]").select_option("__new")
    gate.locator('[data-np="name"]').fill("Interview panel")
    gate.locator('[data-np="members"]').fill("daniel.koh@example.edu")
    gate.get_by_role("button", name="Create panel").click()
    assert not link.is_visible()  # made here: not on Panels until saving


def test_csv_guards_formulas_and_refuses_an_open_quote(page: Page) -> None:
    page.goto(PANELS)
    page.locator('[data-pn-act="add"]').click()
    row = page.locator("[data-pn-row]").last
    row.locator('[data-pn="name"]').fill("=SUM(A1)")
    row.locator("[data-pn-entry]").fill("mei.chen@example.edu")
    row.locator("[data-pn-entry]").press("Enter")
    assert "'=SUM(A1),mei.chen@example.edu," in page.evaluate("window.applydeskPanelsCsv()")
    page.evaluate(
        """window.applydeskPanelsImport('email,name\\r\\nob@x.edu,O"Brien\\r\\nk@x.edu,K\\r\\n')"""
    )
    said = page.locator("[data-pn-said]").inner_text()
    assert said == "A quote mark is not closed, so the file cannot be read: nothing imported."


def test_focus_stays_on_the_page_after_retire_and_the_last_remove(page: Page) -> None:
    page.goto(BLIND)
    page.locator('li[data-panel="interviewers"] [data-pn-act="retire"]').click()
    assert page.evaluate("document.activeElement.dataset.pnAct") == "panel"
    for _ in range(3):
        first = page.locator("[data-pn-row]").first
        first.locator("[data-pn-select]").check()
        first.locator('[data-pn-act="remove"]').click()
    assert page.evaluate("document.activeElement.dataset.pnAct") == "add"


def test_a_panel_may_not_take_a_csv_column_s_name(page: Page) -> None:
    """Codex on #3882: a panel called Email would read the Email column
    as its own on import."""
    page.goto(PANELS)
    page.locator('[data-pn-act="panel"]').click()
    page.locator("[data-pn-newname]").fill("email")
    page.locator('[data-pn-act="create"]').click()
    err = page.locator("[data-pn-newerr]").inner_text()
    assert err == "email names a CSV column: choose another name."
    # Nor may one made in place, on Form.
    page.goto(f"{ORIGIN}/applydesk/operator/exercises/wa9juxbc2t/form")
    card = page.locator(".fc", has=page.locator('[data-sum="label"]:text-is("Preferred reviewer")'))
    card.locator("[data-fc-toggle]").click()
    card.locator('[data-f="pool"]').select_option("__new")
    box = card.locator("[data-newpanel]")
    box.locator('[data-np="name"]').fill("Note")
    box.locator('[data-np="members"]').fill("daniel.koh@example.edu")
    box.get_by_role("button", name="Create panel").click()
    assert box.locator("[data-np-err]").inner_text() == (
        "Note names a column of the Panels CSV: choose another name."
    )


def test_a_guarded_csv_reads_back_the_same(page: Page) -> None:
    """Codex on #3882: a panel named -External exports as '-External;
    the import undoes the guard, so its memberships come back."""
    page.goto(PANELS)
    page.locator('[data-pn-act="panel"]').click()
    page.locator("[data-pn-newname]").fill("-External")
    page.locator('[data-pn-act="create"]').click()
    zoe = _row(page, "zoe.tan@example.edu")
    zoe.locator("[data-pn-select]").check()
    zoe.locator('input[data-pn-panel="made-1"]').check()
    zoe.locator('[data-pn="note"]').fill("=chair")
    csv = page.evaluate("window.applydeskPanelsCsv()")
    assert "'-External" in csv and "'=chair" in csv
    zoe.locator('[data-pn-act="remove"]').click()
    page.evaluate("(t) => window.applydeskPanelsImport(t)", csv)
    assert page.locator("[data-pn-said]").inner_text().startswith("1 person added.")
    back = page.locator("[data-pn-row]").last
    assert back.locator('input[data-pn-panel="made-1"]').is_checked()
    assert back.locator('[data-pn-view="note"]').inner_text() == "=chair"


def test_select_all_turns_every_row_live_and_back(page: Page) -> None:
    """Ruling 22: several rows may be selected at once; unselected, every
    box is inert again and shows what it holds."""
    page.goto(PANELS)
    every = page.locator("[data-pn-select-all]")
    every.check()
    ticks = page.locator("input[data-pn-panel]")
    assert all(not ticks.nth(i).is_disabled() for i in range(ticks.count()))
    zoe = _row(page, "zoe.tan@example.edu")
    zoe.locator('[data-pn="note"]').fill("Chair")
    zoe.locator("[data-pn-select]").uncheck()
    assert every.evaluate("e => e.indeterminate")
    every.check()  # a click on a part-ticked box selects every row
    assert zoe.get_attribute("data-sel") == ""
    every.uncheck()
    assert all(ticks.nth(i).is_disabled() for i in range(ticks.count()))
    assert zoe.locator('[data-pn-view="note"]').inner_text() == "Chair"


def test_an_email_put_back_and_left_keeps_its_pill(page: Page) -> None:
    """Cold read on rung 6a: x then unselecting, with nothing typed, must
    not leave a directory email marked not found."""
    page.goto(PANELS)
    zoe = _row(page, "zoe.tan@example.edu")
    zoe.locator("[data-pn-select]").check()
    zoe.locator('[data-pn-act="unverify"]').click()
    assert zoe.locator("[data-pn-why]").inner_text() == ""
    zoe.locator("[data-pn-select]").uncheck()
    assert zoe.locator("[data-pn-pill]").is_visible()
    assert not zoe.locator('[data-pn-view="email"]').is_visible()


def test_removing_rows_keeps_focus_and_the_header_tick(page: Page) -> None:
    page.goto(BLIND)
    rows = page.locator("[data-pn-row]")
    rows.nth(0).locator("[data-pn-select]").check()
    rows.nth(1).locator("[data-pn-select]").check()
    every = page.locator("[data-pn-select-all]")
    assert every.evaluate("e => e.indeterminate")
    rows.nth(0).locator('[data-pn-act="remove"]').click()
    assert page.evaluate("document.activeElement.matches('[data-pn-select]')")
    rows.nth(0).locator('[data-pn-act="remove"]').click()
    assert not every.evaluate("e => e.indeterminate || e.checked")
