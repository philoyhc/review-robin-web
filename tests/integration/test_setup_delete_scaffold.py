"""Delete-selected-rows strip — Segment 19I Item 2, PRs 1 and 3.

The layout and the gate's *states*. PR 1 landed this with nothing
behind the button; PR 3 wired it, so the assertions that pinned
`Delete` as inert now pin it as wired — the same tests, moved forward
with the code rather than deleted and re-invented.

Behaviour of the route itself lives in
`test_setup_bulk_delete_routes.py`. What stays here is the shape:
the second row carries all three status items (`Showing N of M`, the
selected-count pill, the gate) and the button row carries none of
them; the three non-roster pages sharing `.filter-actions` gained
none of it.
"""
from __future__ import annotations

import pathlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Observer, Relationship, Reviewee, Reviewer, ReviewSession

TEMPLATES = pathlib.Path("app/web/templates/operator")
ROSTER_PAGES = ("reviewers", "reviewees", "observers", "relationships")

#: The pages whose filter strip and `Add new` moved into the table
#: card's toolbar. Reviewers at 19P.1 rung 2a, Observers at 19P.2
#: rung 3, **Reviewees and Relationships at 19P.3 rung 2** — so this is
#: now every roster page, and the tuple is `ROSTER_PAGES` by value.
#:
#: Kept as its own name rather than collapsed into `ROSTER_PAGES`: the
#: two tuples mean different things and only happen to agree today.
#: `ROSTER_PAGES` is which pages exist; this is which of them moved
#: their strip. A page added later belongs to the first immediately and
#: to this one only once it has.
TOOLBAR_PAGES = ROSTER_PAGES

#: The pages that still render the count-and-gate strip server-side.
#:
#: Reviewers left at 19P.1 rung 2b and **Observers at 19P.2 rung 4**:
#: their selection surface is the row expander, built in JS against the
#: selected rows, so there is no `.filter-confirm` row to slice and the
#: count and the gate are not in the response at all. Asserting the
#: card's shape there would pin a card that no longer exists. Their
#: equivalents live with the rest of the expander's contract —
#: `test_reviewers_roster_card_scaffold.py` and
#: `test_observers_expander.py`.
#:
#: Reviewees and Relationships still render it. **Not because they have
#: not migrated** — 19P.3 rung 2 moved their filter strip into the table
#: toolbar, which is why they are in `TOOLBAR_PAGES` above. The card is
#: slimmed, not retired: it keeps the selection-driven four and the
#: count-and-gate row until **19P.3 rung 3** builds their expander. These
#: two tuples stop agreeing at that rung, not at this one.
CARD_STRIP_PAGES = ("reviewees", "relationships")


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed(db: Session, review_session: ReviewSession) -> None:
    review_session.relationships_enabled = True
    review_session.observers_enabled = True
    reviewer = Reviewer(
        session_id=review_session.id, name="Ali", email="ali@example.edu"
    )
    reviewee = Reviewee(
        session_id=review_session.id,
        name="Carol",
        email_or_identifier="carol@example.edu",
    )
    db.add_all([reviewer, reviewee])
    db.add(
        Observer(
            session_id=review_session.id,
            email="obs@example.edu",
            display_name="Obs",
        )
    )
    db.flush()
    db.add(
        Relationship(
            session_id=review_session.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
        )
    )
    db.commit()


def _div_slice(body: str, start: int) -> str:
    """The one `<div>` opening at ``start``, closed by depth count.

    The status row used to be bounded by the next `</form>`, which held
    while every page wrapped its strip in the GET filter form. 19P.2
    rung 3 took that wrapper off Observers, so the slice ran past the
    card close and ended ~900 chars later inside `observers-bulk-form`'s
    hidden inputs — three tests were reading a slab instead of a row.
    No assertion false-passed, but the helper's stated contract did not
    hold for one of its three pages. Counting depth does not care
    whether a form is in the way.
    """
    depth, i = 0, start
    while True:
        nxt_open = body.find("<div", i)
        nxt_close = body.index("</div>", i)
        if nxt_open != -1 and nxt_open < nxt_close:
            depth += 1
            i = nxt_open + 4
            continue
        depth -= 1
        i = nxt_close + len("</div>")
        if depth == 0:
            return body[start:i]


def _strip(body: str) -> tuple[str, str]:
    """The button row and the status row, as separate slices."""
    buttons_at = body.find('class="filter-actions"')
    confirm_at = body.find('class="filter-confirm"')
    assert buttons_at != -1, "no button row"
    assert confirm_at != -1, "no status row"
    assert buttons_at < confirm_at, "status row must follow the buttons"
    return (
        body[buttons_at:confirm_at],
        _div_slice(body, body.rfind("<div", 0, confirm_at)),
    )


@pytest.mark.parametrize("page", CARD_STRIP_PAGES)
def test_the_status_row_carries_the_count_and_the_gate(
    db: Session, client: TestClient, page: str
) -> None:
    """The status row holds the selected count and the delete gate.

    It held `Showing N of M` too until Segment 19I Item 4 moved that to
    the preview table — and **this test did not notice**, because the
    version that named all three only ever asserted the hint's absence
    from the button row, never its presence here. A test whose name
    claims three and pins two. The hint's new home is pinned in
    `test_setup_showing_hint.py`."""
    review_session = _make_session(client, db, code=f"sc-{page}")
    _seed(db, review_session)

    body = client.get(f"/operator/sessions/{review_session.id}/{page}").text
    buttons, status = _strip(body)

    assert f'id="{page}-selected-count"' not in buttons
    assert f'id="{page}-delete-confirm"' not in buttons

    assert f'id="{page}-selected-count"' in status
    assert f'id="{page}-delete-confirm"' in status
    assert "Yes, delete these" in status


@pytest.mark.parametrize("page", CARD_STRIP_PAGES)
def test_delete_renders_destructive_and_wired(
    db: Session, client: TestClient, page: str
) -> None:
    """PR 1 asserted the opposite of the `formaction` line below —
    that there was no route behind the button. PR 3 put one there."""
    review_session = _make_session(client, db, code=f"sc-del-{page}")
    _seed(db, review_session)

    body = client.get(f"/operator/sessions/{review_session.id}/{page}").text
    buttons, _status = _strip(body)

    start = buttons.find(f'id="{page}-delete-btn"')
    assert start != -1, "no Delete button"
    element = buttons[buttons.rfind("<button", 0, start) : buttons.index(">", start) + 1]

    assert "btn destructive" in element, "Destructive role per ui_elements §6"
    assert 'type="submit"' in element
    assert f'form="{page}-bulk-form"' in element, "posts the selection form"
    assert 'formaction="/operator/sessions/' in element
    assert f"/{page}/bulk-delete" in element
    assert "disabled" in element, "ships disabled; the gate enables it"

    # Ordering: there is nothing left to order against. 19P.1 rung 2a
    # moved Reviewers' `Add` and `Search` into the table's toolbar, 19P.2
    # rung 3 did the same for Observers and **19P.3 rung 2 for these two**,
    # so every roster strip now holds the selection-driven four alone.
    #
    # `spec/ui_elements.md` §6 (`:385`) sites the roster Delete "between
    # `Add` and `Search`", which is now false on all four. Rung 5 fixes
    # it, under Item 3's "Rung 2 adds five" Doc-impact addendum — which
    # this comment's predecessor claimed as already recorded when it was
    # not, twice running. Checked against the guide before writing it.
    # (A `page in TOOLBAR_PAGES` assertion stood here briefly. With
    # `TOOLBAR_PAGES = ROSTER_PAGES` and this test parametrized over a
    # subset of it, that compares two module constants and never touches
    # the render — it could not fail for any code change.)
    # Both spellings: the rename moved the label, and a strip that got
    # `Add` back under its old name would be the same regression.
    # Checking only the new spelling let the old one through.
    assert (
        ">Add new</a>" not in buttons
        and ">Add</a>" not in buttons
        and ">Search</button>" not in buttons
    ), f"{page}'s strip should no longer carry Add / Add new or Search"


@pytest.mark.parametrize("page", CARD_STRIP_PAGES)
def test_the_gate_starts_inactive_and_is_paired_to_the_button(
    db: Session, client: TestClient, page: str
) -> None:
    """Stage 1 of the gate ships disabled — nothing is selected on a
    fresh render — and is bound to the button by the app-wide
    `data-delete-confirm` key rather than a second bespoke script."""
    review_session = _make_session(client, db, code=f"sc-gate-{page}")
    _seed(db, review_session)

    body = client.get(f"/operator/sessions/{review_session.id}/{page}").text
    _buttons, status = _strip(body)

    start = status.find(f'id="{page}-delete-confirm"')
    element = status[status.rfind("<input", 0, start) : status.index(">", start) + 1]
    assert "disabled" in element, "no selection yet, so no gate"
    assert f'data-delete-confirm="{page}-bulk-delete"' in element
    assert f'data-delete-btn="{page}-bulk-delete"' in body, "unpaired key"


@pytest.mark.parametrize("page", CARD_STRIP_PAGES)
def test_the_checkbox_submits_with_the_selection_form(
    db: Session, client: TestClient, page: str
) -> None:
    """The gate is only a gate if its tick reaches the server. The
    checkbox lives inside the GET filter form, so it needs `form=` to
    post with the bulk form — without the `name`/`form` pair it would
    look identical and submit nothing."""
    review_session = _make_session(client, db, code=f"sc-name-{page}")
    _seed(db, review_session)

    body = client.get(f"/operator/sessions/{review_session.id}/{page}").text
    _buttons, status = _strip(body)

    start = status.find(f'id="{page}-delete-confirm"')
    element = status[status.rfind("<input", 0, start) : status.index(">", start) + 1]
    assert 'name="confirm"' in element
    assert 'value="true"' in element
    assert f'form="{page}-bulk-form"' in element


def test_the_other_filter_actions_pages_did_not_gain_the_row() -> None:
    """`.filter-actions` is shared by seven templates; only the four
    roster pages get the second row. Read from source rather than
    rendered, because Invitations and Responses need a validated
    session to render at all and their *absence* is the claim."""
    sharing = sorted(
        p.name
        for p in TEMPLATES.glob("session_*.html")
        if 'class="filter-actions"' in p.read_text()
    )
    assert len(sharing) == 7, sharing

    gained = sorted(
        p.name
        for p in TEMPLATES.glob("session_*.html")
        if 'class="filter-confirm"' in p.read_text()
    )
    # Reviewers gave the row up at 19P.1 rung 2b and Observers at
    # 19P.2 rung 4 — the count and the gate moved into the row expander
    # each time — so neither is among the pages that have one. The
    # claim this test makes is unchanged: the three non-roster users of
    # `.filter-actions` never gained it.
    assert gained == sorted(f"session_{p}.html" for p in CARD_STRIP_PAGES)


def test_the_new_row_style_cannot_reach_the_other_pages() -> None:
    """The CSS is scoped under `.operator-actions-card` rather than
    added to `.filter-actions`, so the three non-roster users of that
    class cannot be reflowed by it."""
    base = (TEMPLATES.parent / "base.html").read_text()
    assert ".operator-actions-card .filter-confirm {" in base
    assert "\n      .filter-confirm {" not in base, "unscoped rule"
