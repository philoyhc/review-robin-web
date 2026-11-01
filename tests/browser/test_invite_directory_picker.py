"""Sys Admin → Accounts: the invite box's directory picker (segment 19Z,
invite from the directory, rung 19). The live server runs with fake auth,
so the search asks the fake directory: typing a name offers its people,
and picking one puts "Name <address>" in the box, which invites the
address (author, 2026-11-01)."""

from __future__ import annotations

from playwright.sync_api import Page, expect

from .conftest import app_url

ACCOUNTS = "/operator/sys-admin/users"


def test_a_name_offers_the_directory_s_people(page: Page) -> None:
    page.goto(app_url(ACCOUNTS))
    box = page.locator("#invite-email")
    options = page.locator("#invite-directory-options option")

    box.press_sequentially("Jane")
    expect(options).to_have_count(1)
    expect(options.first).to_have_attribute("value", "Jane Tan <jane.tan@example.edu>")
    # Her sign-in name differs from her mail, so the label keeps it.
    expect(options.first).to_have_attribute("label", "e0123456@example.edu")
    expect(page.locator("[data-directory-status]")).to_be_hidden()

    # A pick puts "Name <address>" in the box, and the offer stands.
    box.fill("Jane Tan <jane.tan@example.edu>")
    box.dispatch_event("input")
    page.wait_for_timeout(500)
    expect(options).to_have_count(1)
    expect(page.locator("[data-invite-submit]")).to_be_enabled()


def test_a_picked_name_and_address_invites_the_address(page: Page) -> None:
    """The local run checks nothing, so the row takes the picked name."""
    import uuid

    address = f"picked-{uuid.uuid4().hex[:8]}@example.edu"
    page.goto(app_url(ACCOUNTS))
    page.fill("#invite-email", f"Pat Picked <{address}>")
    with page.expect_navigation():
        page.click("[data-invite-submit]")
    row = page.locator("#users-table tr", has_text=address)
    expect(row).to_contain_text("Pat Picked")


def test_too_short_offers_nothing_and_no_match_says_so(page: Page) -> None:
    page.goto(app_url(ACCOUNTS))
    box = page.locator("#invite-email")
    status = page.locator("[data-directory-status]")

    box.press_sequentially("zzzq")
    expect(status).to_have_text("No one in the directory matches that.")
    expect(page.locator("#invite-directory-options option")).to_have_count(0)

    box.fill("ja")
    box.dispatch_event("input")
    expect(status).to_be_hidden()

    box.fill("Arun")
    box.dispatch_event("input")
    expect(page.locator("#invite-directory-options option")).to_have_count(1)
    page.click("[data-invite-cancel]")
    expect(page.locator("#invite-directory-options option")).to_have_count(0)


def test_an_answer_for_old_text_is_dropped(page: Page) -> None:
    """A slow answer arriving after the box was shortened fills nothing."""
    page.goto(app_url(ACCOUNTS))
    release: list = []
    page.route("**/directory-search*", lambda route: release.append(route))
    box = page.locator("#invite-email")
    box.press_sequentially("Jane")
    page.wait_for_timeout(500)
    assert release, "the search was asked"
    box.fill("ja")
    box.dispatch_event("input")
    page.wait_for_timeout(400)
    release[0].continue_()
    page.wait_for_timeout(500)
    expect(page.locator("#invite-directory-options option")).to_have_count(0)
    expect(page.locator("[data-directory-status]")).to_be_hidden()


def test_a_sign_in_name_search_keeps_its_match_in_the_label(page: Page) -> None:
    page.goto(app_url(ACCOUNTS))
    page.locator("#invite-email").press_sequentially("e0123")
    option = page.locator("#invite-directory-options option")
    expect(option).to_have_count(1)
    expect(option.first).to_have_attribute("label", "e0123456@example.edu")

    # Arun's sign-in name is his mail: nothing added.
    page.locator("#invite-email").fill("Arun")
    page.locator("#invite-email").dispatch_event("input")
    expect(option.first).to_have_attribute("value", "Arun Kumar <arun.kumar@example.edu>")
    assert option.first.get_attribute("label") is None


def test_an_unavailable_directory_shows_its_reason(page: Page) -> None:
    """The fake directory fails on its throttled address, as Graph would."""
    page.goto(app_url(ACCOUNTS))
    page.locator("#invite-email").press_sequentially("throttled@example.edu")
    expect(page.locator("[data-directory-status]")).to_have_text(
        "The directory can't be searched just now (throttled (429)). Type the full address."
    )


def test_an_expired_sign_in_says_to_sign_in_again(page: Page) -> None:
    page.goto(app_url(ACCOUNTS))
    page.route(
        "**/directory-search*",
        lambda route: route.fulfill(
            json={"available": False, "people": [], "reason": "unauthorized (401) InvalidAuthenticationToken"}
        ),
    )
    page.locator("#invite-email").press_sequentially("Jane")
    expect(page.locator("[data-directory-status]")).to_have_text(
        "Your sign-in's directory access has expired. Sign out and back in, then search again."
    )


def test_an_expired_token_is_renewed_and_the_search_asked_again(page: Page) -> None:
    """Graph token renewal (cordware/spec/identity.md, "Graph"): the
    first answer says the token expired; the picker renews it through
    /.auth/refresh and asks once more, which the fake directory answers."""
    refreshes: list[str] = []
    answers = {"n": 0}

    def refresh(route) -> None:
        refreshes.append(route.request.url)
        route.fulfill(status=200, body="")

    def search(route) -> None:
        answers["n"] += 1
        if answers["n"] == 1:
            route.fulfill(json={"available": False, "people": [], "reason": "unauthorized (401)"})
        else:
            route.continue_()

    page.goto(app_url(ACCOUNTS))
    page.route("**/.auth/refresh", refresh)
    page.route("**/directory-search*", search)
    page.locator("#invite-email").press_sequentially("Jane")
    expect(page.locator("#invite-directory-options option")).to_have_count(1)
    expect(page.locator("[data-directory-status]")).to_be_hidden()
    assert len(refreshes) == 1


def test_a_page_renews_the_token_once_in_45_minutes(page: Page) -> None:
    refreshes: list[str] = []
    page.route("**/.auth/refresh", lambda route: (refreshes.append(route.request.url), route.fulfill(status=200, body="")))
    page.goto(app_url(ACCOUNTS))
    page.wait_for_load_state("networkidle")
    assert len(refreshes) == 1
    page.reload()
    page.wait_for_load_state("networkidle")
    assert len(refreshes) == 1  # stamped: not again within 45 minutes
    page.evaluate("localStorage.setItem('cordware.graphRenewedAt', String(Date.now() - 46 * 60 * 1000))")
    page.reload()
    page.wait_for_load_state("networkidle")
    assert len(refreshes) == 2
