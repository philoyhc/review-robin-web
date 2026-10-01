"""The tag typeahead and the Create page's Owners card.

Each test names the row of ``guide/post_azure_todo_checklist.md`` item 5
it repeats (``guide/archive/browser_test.md`` rung 5). Headless Chromium draws no
datalist popup, so the typeahead tests read the suggestions the script
writes into ``#tag-vocabulary`` instead; the popup itself stays a hand
check.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable

import httpx
import pytest
from playwright.sync_api import Page, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from ._builder import sign_in
from .conftest import COLLEAGUE_EMAIL, FAKE_OPERATOR_EMAIL, SECOND_COLLEAGUE_EMAIL


def _tagged_session(api: httpx.Client, tags: str) -> int:
    code = f"t{uuid.uuid4().hex[:8]}"
    response = api.post(
        "/operator/sessions",
        data={"name": f"Tagged {code}", "code": code, "tags": tags},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return int(response.headers["location"].split("?")[0].rsplit("/", 1)[1])


def _suggestions(page: Page) -> list[str]:
    return page.locator("#tag-vocabulary option").evaluate_all(
        "options => options.map(o => o.value)"
    )


@pytest.mark.parametrize(
    "where", ["create", "session_home"], ids=["Create", "Session Home"]
)
def test_tag_suggestions_complete_only_the_last_tag(
    page: Page, api: httpx.Client, where: str
) -> None:
    """Item 5, 'The tag popup, after each comma'."""
    session_id = _tagged_session(api, "pilot, ethics, alpha")
    url = (
        "/operator/sessions/new"
        if where == "create"
        else f"/operator/sessions/{session_id}?editing=1"
    )
    page.goto(url)
    box = page.locator("input[data-tag-typeahead]:visible").first

    box.fill("a")
    assert "alpha" in _suggestions(page)
    box.fill("pilot, e")
    assert "pilot, ethics" in _suggestions(page)
    assert all(option.startswith("pilot, ") for option in _suggestions(page))
    box.fill("pilot, p")
    assert "pilot, pilot" not in _suggestions(page)


def test_enter_in_a_lobby_tag_box_never_submits(
    page: Page, api: httpx.Client
) -> None:
    """Item 5, 'The keyboard picks' (Chromium; Safari stays a hand check)."""
    session_id = _tagged_session(api, "pilot")
    page.goto("/operator/sessions")
    posted: list[str] = []
    page.on("request", lambda r: posted.append(r.url) if r.method == "POST" else None)

    page.locator(f"input.sessions-list-select-row[value='{session_id}']").check()
    tags = page.locator("[data-expander-field=tags]")
    expect(tags).to_be_visible()
    tags.fill("pilot, e")
    tags.press("Enter")

    # A submission would POST; give it a second to start before saying none did.
    with pytest.raises(PlaywrightTimeoutError):
        page.wait_for_event("request", lambda r: r.method == "POST", timeout=1000)
    assert posted == []
    page.reload()
    expect(page.locator(f"input.sessions-list-select-row[value='{session_id}']")).to_have_count(1)


def test_create_stages_owners_and_saves_what_remains(
    page: Page, api: httpx.Client
) -> None:
    """Item 5, 'Create is unchanged' (JavaScript on)."""
    sign_in(api, COLLEAGUE_EMAIL)
    sign_in(api, SECOND_COLLEAGUE_EMAIL)
    page.goto("/operator/sessions/new")
    # With script on, Create waits for Name and Code.
    expect(page.get_by_role("button", name="Create session")).to_be_disabled()
    table = page.locator("#session-owners-table")
    add = page.locator("#session-owners-add")
    expect(add).to_be_visible()

    for email in (COLLEAGUE_EMAIL, SECOND_COLLEAGUE_EMAIL):
        page.locator("#session-owners-email").fill(email)
        add.click()
        expect(table.locator("tr").filter(has_text=email)).to_have_count(1)
    # A staged row's Remove takes it out with no confirm (no dialog
    # listener here, so one would be dismissed and fail the count).
    second = table.locator("tr").filter(has_text=SECOND_COLLEAGUE_EMAIL)
    second.get_by_role("button", name="Remove").click()
    expect(second).to_have_count(0)

    code = f"c{uuid.uuid4().hex[:8]}"
    page.locator("input[name=name]").fill(f"Created {code}")
    page.locator("input[name=code]").fill(code)
    with page.expect_navigation():
        page.get_by_role("button", name="Create session").click()

    owners = page.locator("#owners-card code")
    expect(owners).to_have_text([FAKE_OPERATOR_EMAIL, COLLEAGUE_EMAIL], use_inner_text=True)


def test_create_without_javascript_saves_the_typed_owner(
    page_as: Callable[..., Page], api: httpx.Client
) -> None:
    """Item 5, 'Create is unchanged' (JavaScript off)."""
    sign_in(api, COLLEAGUE_EMAIL)
    page = page_as(javascript=False)
    page.goto("/operator/sessions/new")
    # With no script the staging buttons stay hidden and the typed
    # address submits with the form, never added.
    expect(page.locator("#session-owners-add")).to_be_hidden()
    page.locator("#session-owners-email").fill(COLLEAGUE_EMAIL)
    name = page.locator("input[name=name]")
    # Without the script's trim, the field's own pattern refuses spaces.
    name.fill("   ")
    assert name.evaluate("el => el.validity.patternMismatch")
    code = f"n{uuid.uuid4().hex[:8]}"
    name.fill(f"No script {code}")
    page.locator("input[name=code]").fill(code)
    submit = page.get_by_role("button", name="Create session")
    expect(submit).to_be_enabled()
    with page.expect_navigation():
        submit.click()

    expect(page).to_have_url(re.compile(r"/operator/sessions/\d+"))
    owners = page.locator("#owners-card code")
    expect(owners).to_have_text(
        [FAKE_OPERATOR_EMAIL, COLLEAGUE_EMAIL], use_inner_text=True
    )
