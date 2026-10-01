"""The tag typeahead and the Create page's Owners card.

Each test names the row of ``guide/post_azure_todo_checklist.md`` item 5
it repeats (``guide/browser_test.md`` rung 5). Headless Chromium draws no
datalist popup, so the typeahead tests read the suggestions the script
writes into ``#tag-vocabulary`` instead; the popup itself stays a hand
check.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from playwright.sync_api import Page, expect

from .conftest import COLLEAGUE_EMAIL
from .test_owners_card import FAKE_OPERATOR_EMAIL, _sign_in_colleague


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

    expect(page).to_have_url("/operator/sessions")
    assert posted == []


def test_create_stages_owners_and_saves_what_remains(
    page: Page, api: httpx.Client
) -> None:
    """Item 5, 'Create is unchanged' (JavaScript on)."""
    _sign_in_colleague(api)
    page.goto("/operator/sessions/new")
    table = page.locator("#session-owners-table")
    add = page.locator("#session-owners-add")
    expect(add).to_be_visible()

    page.locator("#session-owners-email").fill(COLLEAGUE_EMAIL)
    add.click()
    staged = table.locator("tr").filter(has_text=COLLEAGUE_EMAIL)
    expect(staged).to_have_count(1)
    staged.get_by_role("button", name="Remove").click()  # no confirm
    expect(staged).to_have_count(0)

    page.locator("#session-owners-email").fill(COLLEAGUE_EMAIL)
    add.click()
    expect(staged).to_have_count(1)
    code = f"c{uuid.uuid4().hex[:8]}"
    page.locator("input[name=name]").fill(f"Created {code}")
    page.locator("input[name=code]").fill(code)
    with page.expect_navigation():
        page.get_by_role("button", name="Create session").click()

    owners = page.locator("#owners-card code")
    expect(owners).to_have_text([FAKE_OPERATOR_EMAIL, COLLEAGUE_EMAIL], use_inner_text=True)
