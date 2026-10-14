"""Sys Admin → Accounts: the Invite card's role chip and its Overview
neighbor (guide/admin_pages_refine.md Item 3 rung 1). A cycle chip,
"Invite as operator" ↔ "Invite as sys-admin", always solid, around the
``invite_as_sys_admin`` box. The fake operator is a super-admin, so the
chip renders.
"""

from __future__ import annotations

import uuid

from playwright.sync_api import Page, expect

ACCOUNTS = "/operator/sys-admin/users"


def test_the_cards_sit_side_by_side_at_one_height(page: Page) -> None:
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(ACCOUNTS)
    invite = page.locator(".page-grid > .card").nth(0)
    overview = page.locator("#accounts-overview")
    left, right = invite.bounding_box(), overview.bounding_box()
    assert left and right
    assert left["x"] < right["x"]
    assert left["y"] == right["y"]
    assert left["height"] == right["height"]
    # The Workspace users card stays outside the grid, spanning both.
    table = page.locator("#accounts-table-card").bounding_box()
    assert table and table["width"] >= left["width"] + right["width"]
    # Overview's pills hold labels, so they keep the labels' case rather
    # than the capitals other pills take.
    pill = overview.locator('[data-overview="super_admins"]')
    expect(pill).to_have_text("1 super-admin")
    assert pill.evaluate("el => getComputedStyle(el).textTransform") == "none"


def test_the_chip_cycles_resets_and_invites_an_admin(page: Page) -> None:
    page.goto(ACCOUNTS)
    chip = page.locator("[data-invite-role-chip]")
    expect(chip).to_have_text("Invite as operator")
    solid = chip.evaluate("el => getComputedStyle(el).backgroundColor")

    chip.click()
    expect(chip).to_have_text("Invite as sys-admin")
    assert chip.evaluate("el => getComputedStyle(el).backgroundColor") == solid

    # Cancel resets the form, and the label follows the box back.
    page.fill("#invite-email", "nobody@example.edu")
    page.click("[data-invite-cancel]")
    expect(chip).to_have_text("Invite as operator")
    expect(chip.locator("input")).not_to_be_checked()

    email = f"admin-{uuid.uuid4().hex[:8]}@example.edu"
    page.fill("#invite-email", email)
    chip.click()
    with page.expect_navigation():
        page.click("[data-invite-submit]")
    row = page.locator("#users-table tr", has_text=email)
    expect(row.locator(".pill", has_text="Admin")).to_be_visible()


def test_the_chip_sits_top_left_and_the_buttons_right(page: Page) -> None:
    """One row: the chip at its top-left, Cancel then Invite flush right
    (author, 2026-10-14)."""
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(ACCOUNTS)
    chip = page.locator("[data-invite-role-chip]").bounding_box()
    cancel = page.locator("[data-invite-cancel]").bounding_box()
    invite = page.locator("[data-invite-submit]").bounding_box()
    email = page.locator("#invite-email").bounding_box()
    assert chip and cancel and invite and email
    assert chip["y"] == cancel["y"] == invite["y"]
    assert chip["x"] == email["x"]
    assert chip["x"] + chip["width"] < cancel["x"] < invite["x"]
    # Flush right: Invite ends where the email box does.
    assert abs((invite["x"] + invite["width"]) - (email["x"] + email["width"])) < 1
    # The row's own 12px between the buttons, not the pair's 16px.
    assert abs(invite["x"] - (cancel["x"] + cancel["width"]) - 12) < 1


def test_a_narrow_card_wraps_the_buttons_together(page: Page) -> None:
    """Cancel and Invite wrap as one unit, never Invite alone (cold read
    of the one-row change, measured at 360–420px)."""
    for width in (420, 360, 320):
        page.set_viewport_size({"width": width, "height": 900})
        page.goto(ACCOUNTS)
        cancel = page.locator("[data-invite-cancel]").bounding_box()
        invite = page.locator("[data-invite-submit]").bounding_box()
        email = page.locator("#invite-email").bounding_box()
        assert cancel and invite and email
        assert cancel["y"] == invite["y"], width
        assert abs((invite["x"] + invite["width"]) - (email["x"] + email["width"])) < 1, width
