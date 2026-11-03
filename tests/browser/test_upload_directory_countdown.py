"""The roster Upload card counts its directory check down from the page
(segment 20H Item 6): Upload asks which of the file's addresses still
need a lookup, looks each up once, and says how many are left, then
uploads. A second upload of the same file within the cache's life looks
nothing up. Local runs ask the fake directory, so every address answers."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import Page, expect

from .conftest import app_url

ADDRESSES = [
    "e0123456@example.edu",
    "office@example.edu",
    "nobody@example.edu",
    "one@example.edu",
    "two@example.edu",
    "three@example.edu",
]

#: Each value the count line shows, kept across the upload's navigation.
_RECORD = """
document.addEventListener('DOMContentLoaded', function () {
  var line = document.querySelector('[data-directory-countdown]');
  if (!line) { return; }
  var left = line.querySelector('[data-directory-countdown-left]');
  function note() {
    if (line.hidden) { return; }
    var seen = JSON.parse(sessionStorage.getItem('countdown') || '[]');
    seen.push(Number(left.textContent));
    sessionStorage.setItem('countdown', JSON.stringify(seen));
  }
  new MutationObserver(note).observe(line, {attributes: true, childList: true,
    characterData: true, subtree: true});
});
"""


def _seen(page: Page) -> list[int]:
    value = page.evaluate("() => sessionStorage.getItem('countdown')")
    page.evaluate("() => sessionStorage.removeItem('countdown')")
    return json.loads(value or "[]")


def test_the_upload_counts_down_then_reads_what_it_looked_up(
    page: Page, new_session: Callable[[], str], tmp_path: Path
) -> None:
    session_id = new_session()
    roster = tmp_path / "reviewers.csv"
    rows = [f"Person {i},{a.upper() if i == 0 else a}" for i, a in enumerate(ADDRESSES)]
    roster.write_text("ReviewerName,ReviewerEmail\n" + "\n".join(rows) + "\n")
    looked_up: list[str] = []
    page.on(
        "request",
        lambda r: looked_up.extend(json.loads(r.post_data)["keys"])
        if r.url.endswith("/directory-lookup") else None,
    )
    page.add_init_script(_RECORD)
    page.goto(app_url(f"/operator/sessions/{session_id}/reviewers?unlocked=1"))
    expect(page.locator("[data-directory-countdown]")).to_be_hidden()

    page.locator("#upload-csv-form input[name=file]").set_input_files(str(roster))
    with page.expect_navigation():
        page.locator("#upload-csv-form .unlock-col-actions button[type=submit]").click()
    page.wait_for_load_state("load")

    assert sorted(looked_up) == sorted(ADDRESSES)  # each once, folded
    seen = _seen(page)
    assert seen[0] == len(ADDRESSES) and seen[-1] == 0
    assert seen == sorted(seen, reverse=True)  # only ever falls
    expect(page.locator("[data-directory-check]")).to_contain_text("matched by mail")

    # The same file again, within the cache's life: nothing to look up.
    looked_up.clear()
    page.locator("#upload-csv-form input[name=file]").set_input_files(str(roster))
    page.locator("#upload-csv-form input[name=confirm_replace]").check()
    with page.expect_navigation():
        page.locator("#upload-csv-form .unlock-col-actions button[type=submit]").click()
    page.wait_for_load_state("load")
    assert looked_up == []
    assert _seen(page) == []
    expect(page.locator("[data-directory-check]")).to_contain_text("matched by mail")
