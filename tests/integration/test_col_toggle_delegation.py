"""The column-visibility chips are delegated, not bound per chip.

Segment 19K Item 2. The block used to walk `[data-col-toggle]` at load
and register a listener on each chip, so any re-render of the table card
silently lost the behaviour — no error, no console warning, a chip that
stops responding. It is now one delegated listener per event type on
`document`, resolving its target with `closest`, which is the shape
blocks 7 and 8 of `base.html` already use.

**What this file can and cannot prove.** The suite has no JavaScript
runtime, so it cannot click a chip. What it pins is the property that
decides whether a late-rendered chip works at all: *where the listener
is registered*. A per-chip listener and a delegated one are
indistinguishable on a freshly loaded page and differ completely on a
re-rendered one, so the mechanism is the honest thing to assert and the
behaviour is a browser check recorded in the item's `Status`.

The receiver probe is deliberately not `(\\w+)\\.addEventListener`. That
regex does not match `menus[0].addEventListener` — `]` is not a word
character — so an offending receiver drops out of the match set and the
assertion passes on the mutation it exists to catch. 19J.9 shipped that
hole and found it by mutating the guard; this file starts from the fixed
form and asserts the match count as well.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession

BASE_HTML = Path("app/web/templates/base.html")

#: The block is found by its own marker rather than by index: an
#: eighth or tenth `<script>` arriving in this file must not silently
#: repoint these assertions at someone else's code.
MARKER = "shared column-visibility primitive"


def _block() -> str:
    src = BASE_HTML.read_text(encoding="utf-8", errors="replace")
    start = src.index(MARKER)
    return src[start : src.index("</script>", start)]


def test_every_listener_in_the_block_is_delegated_on_the_document() -> None:
    """The assertion that fails on `main`.

    Before this item the block read
    ``el.addEventListener("click", handler)`` inside a loop over chips.
    """
    block = _block()

    receivers = re.findall(r"([^\s;{}(]+)\.addEventListener\(", block)
    assert len(receivers) == block.count(".addEventListener("), (
        "a listener registration the receiver probe could not parse — "
        "read it rather than trusting this test"
    )
    assert receivers, "the block registers no listener at all"
    assert set(receivers) == {"document"}, (
        f"bound to {sorted(set(receivers))}; a listener on anything but "
        "`document` dies with the element it was attached to"
    )


def test_both_activation_paths_survive() -> None:
    """Pointer and keyboard. The chips are `role="button" tabindex="0"`,
    so losing the `keydown` half would leave them unreachable by
    keyboard while looking entirely fine."""
    block = _block()
    assert '"click"' in block
    assert '"keydown"' in block
    assert '"Enter"' in block and '" "' in block


def test_the_target_is_resolved_at_event_time() -> None:
    """`closest` is the whole mechanism: it is what lets a chip that did
    not exist at load resolve its own row, table and storage key."""
    block = _block()
    assert 'closest("[data-col-toggle]")' in block
    assert 'closest("[data-col-toggles-for]")' in block


def test_hydration_is_exposed_for_a_re_render() -> None:
    """Delegation keeps a late chip *clickable*; it does not restore the
    operator's saved columns, because a re-render brings chips back as
    the server rendered them — all visible. The hook is the other half,
    and it mirrors the sort primitive's `_rrwHydrateFromCookies`."""
    block = _block()
    assert "window._rrwHydrateColToggles = hydrate;" in block
    # And it still runs at load, or a first paint shows every column
    # regardless of what the operator last chose.
    assert re.search(r"window\._rrwHydrateColToggles = hydrate;\s*hydrate\(\);", block)


def test_the_storage_contract_is_untouched() -> None:
    """The key lives on the table and the value is a slot→bool map.
    Renaming either would silently reset every operator's saved columns,
    which is the one thing this refactor must not do."""
    block = _block()
    assert 'getAttribute("data-rrw-col-toggles")' in block
    assert "window.localStorage.getItem(storageKey)" in block
    assert "window.localStorage.setItem(" in block
    assert 'chip.getAttribute("aria-pressed") === "true"' in block


def test_the_rendered_markup_still_carries_what_the_block_reads(
    client: TestClient, db: Session
) -> None:
    """The other half of a delegated listener: it resolves attributes
    from markup at event time, so a template that stopped emitting one
    would break it silently. Asserted on a rendered page, not on the
    class names in `base.html`'s own comment — that comment ships in
    every response and would match a bare substring check.
    """
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": "col-toggle"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "col-toggle")
    ).scalar_one()

    rows = b"".join(
        f"Reviewer {i:03d},r{i:03d}@example.edu,Tutor {i % 3}\n".encode()
        for i in range(5)
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail,ReviewerTag1\n" + rows,
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text

    # The chip row, the pairing attribute, and the key on the table.
    assert '<p class="col-chip-row" data-col-toggles-for="reviewers-table"' in body
    assert 'data-rrw-col-toggles="rrw-reviewer-tag-visibility"' in body
    assert re.search(r'data-col-toggle="tag-1"[^>]*role="button"', body, re.S)
    assert 'aria-pressed="true"' in body
