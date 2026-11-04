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
        page.locator("#upload-csv-form .unlock-col-actions button[type=submit]:not([data-directory-recheck])").click()
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
        page.locator("#upload-csv-form .unlock-col-actions button[type=submit]:not([data-directory-recheck])").click()
    page.wait_for_load_state("load")
    assert looked_up == []
    assert _seen(page) == []
    expect(page.locator("[data-directory-check]")).to_contain_text("matched by mail")


def test_a_failed_lookup_stops_the_count_and_uploads(
    page: Page, new_session: Callable[[], str], tmp_path: Path
) -> None:
    """A directory timing out answers each lookup as an error: the count
    stops at once rather than waiting out every address, and the upload
    checks what is left within its own budget (Codex, #3555)."""
    session_id = new_session()
    roster = tmp_path / "reviewers.csv"
    many = [f"person{i}@example.edu" for i in range(60)]
    roster.write_text(
        "ReviewerName,ReviewerEmail\n"
        + "\n".join(f"P{i},{a}" for i, a in enumerate(many)) + "\n"
    )
    batches: list[list[str]] = []

    def time_out(route) -> None:
        keys = json.loads(route.request.post_data)["keys"]
        batches.append(keys)
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"outcomes": {k: {"status": "ERROR", "error_kind": "timeout"} for k in keys}}),
        )

    page.route("**/directory-lookup", time_out)
    page.goto(app_url(f"/operator/sessions/{session_id}/reviewers?unlocked=1"))
    page.locator("#upload-csv-form input[name=file]").set_input_files(str(roster))
    with page.expect_navigation():
        page.locator("#upload-csv-form .unlock-col-actions button[type=submit]:not([data-directory-recheck])").click()
    page.wait_for_load_state("load")
    assert 1 <= len(batches) <= 2  # two in flight; the first answer stops the other four
    expect(page.locator("[data-directory-check]")).to_contain_text("not found")


def test_the_count_falls_by_batches_of_ten(
    page: Page, new_session: Callable[[], str], tmp_path: Path
) -> None:
    """Segment 20I Item 2: 25 addresses go in three requests of 10, 10
    and 5, at most two at once, and the count falls by each batch to zero."""
    session_id = new_session()
    roster = tmp_path / "reviewers.csv"
    many = [f"batch{i}@example.edu" for i in range(25)]
    roster.write_text(
        "ReviewerName,ReviewerEmail\n"
        + "\n".join(f"P{i},{a}" for i, a in enumerate(many)) + "\n"
    )
    batches: list[list[str]] = []
    page.on(
        "request",
        lambda r: batches.append(json.loads(r.post_data)["keys"])
        if r.url.endswith("/directory-lookup") else None,
    )
    page.add_init_script(_RECORD)
    page.goto(app_url(f"/operator/sessions/{session_id}/reviewers?unlocked=1"))
    page.locator("#upload-csv-form input[name=file]").set_input_files(str(roster))
    with page.expect_navigation():
        page.locator("#upload-csv-form .unlock-col-actions button[type=submit]:not([data-directory-recheck])").click()
    page.wait_for_load_state("load")
    assert sorted(len(b) for b in batches) == [5, 10, 10]
    assert sorted(k for b in batches for k in b) == sorted(many)
    seen = _seen(page)
    assert seen[0] == 25 and seen[-1] == 0
    assert seen == sorted(seen, reverse=True)
    assert set(seen) <= {25, 20, 15, 10, 5, 0}  # falls by a batch, not by one
    expect(page.locator("[data-directory-check]")).to_contain_text("25 not found")


def test_the_recheck_counts_down_every_unmatched_address_then_rechecks(
    page: Page, new_session: Callable[[], str], tmp_path: Path
) -> None:
    """Segment 20I Item 1: "Recheck N unmatched" counts the roster's
    unmatched addresses down as an upload does, asking for each afresh
    though the upload's answers are still kept, then posts the recheck."""
    session_id = new_session()
    roster = tmp_path / "reviewers.csv"
    roster.write_text(
        "ReviewerName,ReviewerEmail\n"
        + "\n".join(f"P{i},{a}" for i, a in enumerate(ADDRESSES)) + "\n"
    )
    page.add_init_script(_RECORD)
    page.goto(app_url(f"/operator/sessions/{session_id}/reviewers?unlocked=1"))
    page.locator("#upload-csv-form input[name=file]").set_input_files(str(roster))
    with page.expect_navigation():
        page.locator("#upload-csv-form .unlock-col-actions button[type=submit]:not([data-directory-recheck])").click()
    page.wait_for_load_state("load")
    _seen(page)

    unmatched = [a for a in ADDRESSES if a != "e0123456@example.edu"]
    looked_up: list[str] = []
    page.on(
        "request",
        lambda r: looked_up.extend(json.loads(r.post_data)["keys"])
        if r.url.endswith("/directory-lookup") else None,
    )
    button = page.locator("[data-directory-recheck]")
    expect(button).to_have_text(f"Recheck {len(unmatched)} unmatched")
    with page.expect_navigation():
        button.click()
    page.wait_for_load_state("load")

    assert sorted(looked_up) == sorted(unmatched)
    seen = _seen(page)
    assert seen[0] == len(unmatched) and seen[-1] == 0
    assert seen == sorted(seen, reverse=True)
    expect(page.locator("[data-directory-check]")).to_contain_text("Recheck of the unmatched addresses")
    expect(page.locator("[data-directory-check]")).to_contain_text("4 not found, 1 ambiguous")


def test_one_failed_key_in_a_batch_stops_the_count(
    page: Page, new_session: Callable[[], str], tmp_path: Path
) -> None:
    """A batch is failed by any of its keys, not only its first: the
    seventh key of the first batch errors, and no further batch goes."""
    session_id = new_session()
    roster = tmp_path / "reviewers.csv"
    many = [f"mid{i}@example.edu" for i in range(40)]
    roster.write_text(
        "ReviewerName,ReviewerEmail\n"
        + "\n".join(f"P{i},{a}" for i, a in enumerate(many)) + "\n"
    )
    batches: list[list[str]] = []

    def answer(route) -> None:
        keys = json.loads(route.request.post_data)["keys"]
        batches.append(keys)
        outcomes = {k: {"status": "NOT_FOUND", "error_kind": None} for k in keys}
        if keys[0] == many[0]:
            outcomes[keys[6]] = {"status": "ERROR", "error_kind": "throttled"}
        route.fulfill(status=200, content_type="application/json", body=json.dumps({"outcomes": outcomes}))

    page.route("**/directory-lookup", answer)
    page.goto(app_url(f"/operator/sessions/{session_id}/reviewers?unlocked=1"))
    page.locator("#upload-csv-form input[name=file]").set_input_files(str(roster))
    with page.expect_navigation():
        page.locator("#upload-csv-form .unlock-col-actions button[type=submit]:not([data-directory-recheck])").click()
    page.wait_for_load_state("load")
    # The first batch's answer stops the count: at most the other batch
    # already in flight went too, of the four.
    assert 1 <= len(batches) <= 2


def test_a_submit_the_browser_blocks_counts_again_next_time(
    page: Page, new_session: Callable[[], str], tmp_path: Path
) -> None:
    """A counted form whose own validation then blocks the submit is
    unmarked, so the next Upload counts again rather than skipping the
    count (findings L2)."""
    session_id = new_session()
    roster = tmp_path / "reviewers.csv"
    roster.write_text("ReviewerName,ReviewerEmail\nArun,arun.kumar@example.edu\n")
    keys_asked: list[str] = []
    page.on("request", lambda r: keys_asked.append(r.url) if r.url.endswith("/directory-keys") else None)
    page.goto(app_url(f"/operator/sessions/{session_id}/reviewers?unlocked=1"))
    page.locator("#upload-csv-form input[name=file]").set_input_files(str(roster))
    # A required field that passes at the click and is emptied while the
    # count runs, so the count's own submit is blocked.
    page.evaluate(
        """() => {
          const form = document.getElementById('upload-csv-form');
          const probe = document.createElement('input');
          probe.name = 'probe'; probe.required = true; probe.value = 'x';
          probe.id = 'probe';
          form.appendChild(probe);
          const real = window.fetch;
          window.fetch = function (url) {
            if (String(url).endsWith('/directory-keys') && !window.__emptied) {
              window.__emptied = true;
              probe.value = '';
            }
            return real.apply(this, arguments);
          };
        }"""
    )
    page.locator("#upload-csv-form .unlock-col-actions button[type=submit]").click()
    page.wait_for_function("() => window.__emptied === true")
    page.wait_for_timeout(500)
    assert "/reviewers/import" not in page.url  # the browser blocked it
    page.fill("#probe", "y")
    with page.expect_navigation():
        page.locator("#upload-csv-form .unlock-col-actions button[type=submit]").click()
    assert len(keys_asked) == 2  # the second Upload counted again


def test_stop_and_save_saves_what_was_looked_up(
    page: Page, new_session: Callable[[], str], tmp_path: Path
) -> None:
    """While the recheck counts, its button reads "Stop and save" (author,
    2026-11-04). Clicking it sends no more batches, waits for those in
    flight, then posts the recheck: what was looked up is saved, and the
    rest are not checked, with nothing more asked of the directory."""
    session_id = new_session()
    roster = tmp_path / "reviewers.csv"
    many = [f"stop{i}@example.edu" for i in range(25)]
    roster.write_text(
        "ReviewerName,ReviewerEmail\n"
        + "\n".join(f"P{i},{a}" for i, a in enumerate(many)) + "\n"
    )
    page.goto(app_url(f"/operator/sessions/{session_id}/reviewers?unlocked=1"))
    page.locator("#upload-csv-form input[name=file]").set_input_files(str(roster))
    with page.expect_navigation():
        page.locator("#upload-csv-form .unlock-col-actions button[type=submit]:not([data-directory-recheck])").click()
    page.wait_for_load_state("load")

    # Both first batches are held until after the click, so the third
    # (five keys) is never sent.
    held: list = []
    page.route("**/directory-lookup", lambda route: held.append(route))
    button = page.locator("[data-directory-recheck]")
    expect(button).to_have_text("Recheck 25 unmatched")
    button.click()
    expect(button).to_have_text("Stop and save")
    for _ in range(50):
        if len(held) == 2:
            break
        page.wait_for_timeout(100)
    assert len(held) == 2

    button.click()
    expect(button).to_have_text("Saving…")
    page.wait_for_timeout(300)
    assert len(held) == 2  # nothing more sent
    with page.expect_navigation():
        for route in held:
            route.continue_()
    page.wait_for_load_state("load")

    line = page.locator("[data-directory-check]")
    expect(line).to_contain_text("Recheck of the unmatched addresses")
    expect(line).to_contain_text("20 not found")
    expect(line).to_contain_text("5 not checked")
    expect(line).to_contain_text("Not checked because the recheck was stopped.")


def test_a_failed_lookup_while_saving_ends_the_ordinary_way(
    page: Page, new_session: Callable[[], str], tmp_path: Path
) -> None:
    """A batch that fails while saving ends the count as any failed lookup
    does, not as a stop: no `stop=true`, so the server checks what is left
    and the line names no stop (findings on #3575)."""
    session_id = new_session()
    roster = tmp_path / "reviewers.csv"
    many = [f"fail{i}@example.edu" for i in range(25)]
    roster.write_text(
        "ReviewerName,ReviewerEmail\n"
        + "\n".join(f"P{i},{a}" for i, a in enumerate(many)) + "\n"
    )
    page.goto(app_url(f"/operator/sessions/{session_id}/reviewers?unlocked=1"))
    page.locator("#upload-csv-form input[name=file]").set_input_files(str(roster))
    with page.expect_navigation():
        page.locator("#upload-csv-form .unlock-col-actions button[type=submit]:not([data-directory-recheck])").click()
    page.wait_for_load_state("load")

    held: list = []
    page.route("**/directory-lookup", lambda route: held.append(route))
    posted: list[str] = []
    page.on("request", lambda r: posted.append(r.post_data or "") if r.url.endswith("/directory-recheck") else None)
    button = page.locator("[data-directory-recheck]")
    button.click()
    for _ in range(50):
        if len(held) == 2:
            break
        page.wait_for_timeout(100)
    button.click()
    expect(button).to_have_text("Saving…")
    keys = json.loads(held[0].request.post_data)["keys"]
    with page.expect_navigation():
        held[0].fulfill(json={"outcomes": {k: {"status": "ERROR", "error_kind": "server"} for k in keys}})
    page.wait_for_load_state("load")

    assert len(posted) == 1 and "stop=true" not in posted[0]
    line = page.locator("[data-directory-check]")
    expect(line).to_contain_text("25 not found")
    expect(line).not_to_contain_text("stopped")
