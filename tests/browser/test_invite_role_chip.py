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


def test_the_chip_cycles_resets_and_invites_an_admin(page: Page) -> None:
    page.goto(ACCOUNTS)
    chip = page.locator("[data-invite-role-chip]")
    expect(chip).to_have_text("Invite as operator")
    dark = chip.evaluate("el => getComputedStyle(el).backgroundColor")

    chip.click()
    expect(chip).to_have_text("Invite as sys-admin")
    assert chip.evaluate("el => getComputedStyle(el).backgroundColor") == dark

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
