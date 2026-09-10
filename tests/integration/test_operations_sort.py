"""Cookie-driven sort on Invitations and Responses — 19I Item 11 rung 2.

Both tables opted into the shared ``data-rrw-sortable`` primitive.
The client reorders the DOM on click and writes the cascade to a
cookie; the route re-applies it so the **first paint** already lands
in the chosen order. These tests pin the server half, which is the
half a test can see.

Two things here are not obvious and are the reason the file exists:

1. **The rows are wrappers.** ``InvitationsRow.reviewer`` is the ORM
   object, so the roster pages' ``getattr(row, key)`` resolver would
   return ``None`` for every key and silently sort nothing. Ordering
   by name is what proves the resolver reaches through.
2. **Order assertions must be scoped to the tbody.** Both pages
   render a ``<datalist>`` of reviewer / reviewee labels *before* the
   table, alphabetically. Against the whole document ``find()``
   returns the datalist hit and the assertion passes whatever the
   table does — the exact failure Segment 19I Item 9 found on the
   Assignments sort tests.
"""
from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession

from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)

# Emails are deliberately in the **reverse** of name order.
#
# Both builders default to `order_by(email)`
# (`monitoring._assigned_active_reviewers`, `per_reviewee_coverage`),
# so a seed whose emails happen to match its names makes every
# name-ascending assertion pass whether or not the sort ran at all.
# The first draft of this file did exactly that.
#
# `tag_3` is left empty on purpose throughout: rung 3's chip for an
# empty slot must render disabled, and its column must stay hidden.
REVIEWERS = [
    ("Alpha R", "zulu@example.edu", "Team Z", "Cohort 2"),
    ("Bravo R", "yankee@example.edu", "Team Y", "Cohort 1"),
    ("Charlie R", "xray@example.edu", "Team X", "Cohort 3"),
]
REVIEWEES = [
    ("Delta E", "zulu-e@example.edu", "Group Q", "Wave 2"),
    ("Echo E", "yankee-e@example.edu", "Group P", "Wave 1"),
]
# Unsorted (email asc) therefore reads Charlie, Bravo, Alpha.
DEFAULT_ORDER = ["Charlie R", "Bravo R", "Alpha R"]


def _rows(body: str) -> str:
    """The rendered rows only — never the datalist above them."""
    start = body.index('<tbody class="rrw-rows">')
    return body[start : body.index("</tbody>", start)]


def _seed(client: TestClient, db: Session, code: str) -> ReviewSession:
    r = client.post(
        "/operator/sessions",
        data={"name": "S", "code": code},
        follow_redirects=False,
    )
    assert r.status_code == 303, r.text
    s = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()

    reviewers = (
        "ReviewerName,ReviewerEmail,ReviewerTag1,ReviewerTag2\n"
        + "\n".join(f"{n},{e},{t1},{t2}" for n, e, t1, t2 in REVIEWERS)
    )
    reviewees = (
        "RevieweeName,RevieweeEmail,RevieweeTag1,RevieweeTag2\n"
        + "\n".join(f"{n},{e},{t1},{t2}" for n, e, t1, t2 in REVIEWEES)
    )
    for path, payload in (
        ("reviewers", reviewers),
        ("reviewees", reviewees),
    ):
        resp = client.post(
            f"/operator/sessions/{s.id}/{path}/import",
            files={"file": ("r.csv", payload.encode(), "text/csv")},
            follow_redirects=False,
        )
        assert resp.status_code in (200, 303), resp.text

    pin_full_matrix_on_all_instruments(db, s.id)
    generate_via_page_button(client, s.id)
    client.get(f"/operator/sessions/{s.id}/assignments?validated=1")
    resp = client.post(
        f"/operator/sessions/{s.id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    assert resp.status_code == 303, resp.text
    db.refresh(s)
    return s


def _sorted_body(
    client: TestClient, session_id: int, page: str, key: str, direction: str
) -> str:
    client.cookies.set(
        f"rrw-sort-{page}-{session_id}",
        json.dumps([{"key": key, "dir": direction}]),
        path=f"/operator/sessions/{session_id}",
    )
    return client.get(f"/operator/sessions/{session_id}/{page}").text


# --------------------------------------------------------------------------- #
# Invitations — one row per reviewer.
# --------------------------------------------------------------------------- #


def test_invitations_cookie_sort_by_name_asc(
    client: TestClient, db: Session
) -> None:
    s = _seed(client, db, "inv-sort-asc")
    rows = _rows(_sorted_body(client, s.id, "invitations", "name", "asc"))
    assert (
        rows.find("Alpha R") < rows.find("Bravo R") < rows.find("Charlie R")
    )


def test_invitations_cookie_sort_by_name_desc(
    client: TestClient, db: Session
) -> None:
    s = _seed(client, db, "inv-sort-desc")
    rows = _rows(_sorted_body(client, s.id, "invitations", "name", "desc"))
    assert (
        rows.find("Charlie R") < rows.find("Bravo R") < rows.find("Alpha R")
    )


def test_invitations_sort_reaches_through_the_row_wrapper(
    client: TestClient, db: Session
) -> None:
    """The assertion that fails if the resolver is `getattr(row, key)`.

    `InvitationsRow` has no `name` — it lives on `.reviewer`. A
    resolver that misses it returns `None` for every row, every
    comparison ties, and the stable sort leaves the default
    email order untouched: Charlie, Bravo, Alpha. Sorting by name
    must invert that.
    """
    s = _seed(client, db, "inv-sort-wrapper")
    # Unsorted first — `client.cookies` persists, so a fetch after
    # `_sorted_body` would still carry the cookie and prove nothing.
    unsorted = _rows(
        client.get(f"/operator/sessions/{s.id}/invitations").text
    )
    assert [unsorted.find(n) for n in DEFAULT_ORDER] == sorted(
        unsorted.find(n) for n in DEFAULT_ORDER
    )

    rows = _rows(_sorted_body(client, s.id, "invitations", "name", "asc"))
    positions = [rows.find(n) for n in ("Alpha R", "Bravo R", "Charlie R")]
    assert positions == sorted(positions)


def test_invitations_unsorted_without_a_cookie(
    client: TestClient, db: Session
) -> None:
    """No cookie ⇒ no reordering: the builder's email order survives."""
    s = _seed(client, db, "inv-sort-none")
    rows = _rows(client.get(f"/operator/sessions/{s.id}/invitations").text)
    positions = [rows.find(n) for n in DEFAULT_ORDER]
    assert positions == sorted(positions)


# --------------------------------------------------------------------------- #
# Responses — one row per reviewee.
# --------------------------------------------------------------------------- #


def test_responses_cookie_sort_by_name_asc(
    client: TestClient, db: Session
) -> None:
    s = _seed(client, db, "resp-sort-asc")
    rows = _rows(_sorted_body(client, s.id, "responses", "name", "asc"))
    assert rows.find("Delta E") < rows.find("Echo E")


def test_responses_cookie_sort_by_name_desc(
    client: TestClient, db: Session
) -> None:
    s = _seed(client, db, "resp-sort-desc")
    rows = _rows(_sorted_body(client, s.id, "responses", "name", "desc"))
    assert rows.find("Echo E") < rows.find("Delta E")


# --------------------------------------------------------------------------- #
# The markup contract the client half needs.
# --------------------------------------------------------------------------- #


def test_both_tables_carry_the_sort_markers(
    client: TestClient, db: Session
) -> None:
    s = _seed(client, db, "ops-sort-markers")
    for page, table in (
        ("invitations", "invitations-table"),
        ("responses", "responses-table"),
    ):
        body = client.get(f"/operator/sessions/{s.id}/{page}").text
        assert f'<table id="{table}"' in body
        assert f'data-rrw-sortable="rrw-sort-{page}-{s.id}"' in body
        assert '<tbody class="rrw-rows">' in body
        # Every sortable header carries a key and a button, and every
        # rendered row carries a value for it.
        assert 'class="rrw-sortable"' in body
        assert "rrwSortHeaderClick(event, this)" in body
        assert "data-sort-value=" in _rows(body)


def test_progress_columns_sort_by_percentage_not_raw_count() -> None:
    """`0/2` and `0/8` are equally far along; `1/2` beats `1/8`.

    The columns show `done/total` and the totals differ per row, so
    ordering by the raw done count orders nothing an operator would
    recognise. `None` for "nothing to do" — empty on both sides, and
    both sort empty last regardless of direction.
    """
    from app.web.routes_operator._operations import _completion_pct

    assert _completion_pct(0, 2) == _completion_pct(0, 8) == 0
    assert _completion_pct(1, 2) > _completion_pct(1, 8)
    assert _completion_pct(2, 2) == 100
    # Nothing to do is not "0% done".
    assert _completion_pct(0, 0) is None


# --------------------------------------------------------------------------- #
# Tag columns and their chips — rung 3.
# --------------------------------------------------------------------------- #


def test_both_pages_render_the_tag_columns(
    client: TestClient, db: Session
) -> None:
    """The tags were always on the row objects — `InvitationsRow.reviewer`
    and `ResponsesRow.reviewee` are the ORM objects — so this rung is
    template-only. That is what makes it worth asserting: nothing in
    the service or query layer changed, so nothing there would fail if
    the columns silently stopped rendering."""
    s = _seed(client, db, "ops-tags")
    inv = _rows(client.get(f"/operator/sessions/{s.id}/invitations").text)
    assert "Team Z" in inv and "Cohort 2" in inv
    resp = _rows(client.get(f"/operator/sessions/{s.id}/responses").text)
    assert "Group Q" in resp and "Wave 2" in resp


def test_an_empty_tag_slot_renders_a_disabled_chip(
    client: TestClient, db: Session
) -> None:
    """`tag_3` is empty across the seed, so its chip is disabled and
    cannot be turned on. Slots 1 and 2 have data and are live."""
    s = _seed(client, db, "ops-tags-empty")
    for page in ("invitations", "responses"):
        body = client.get(f"/operator/sessions/{s.id}/{page}").text
        chips = body[
            body.index('class="col-chip-row"') : body.index("</p>", body.index('class="col-chip-row"'))
        ]
        for slot in ("tag-1", "tag-2"):
            i = chips.index(f'data-col-toggle="{slot}"')
            assert 'aria-pressed="true"' in chips[i : i + 200], (page, slot)
        i3 = chips.index('data-col-toggle="tag-3"')
        assert 'aria-disabled="true"' in chips[i3 : i3 + 200], page


def test_both_pages_declare_the_shared_primitive(
    client: TestClient, db: Session
) -> None:
    s = _seed(client, db, "ops-tags-primitive")
    for page, table, key in (
        ("invitations", "invitations-table", "rrw-invitation-tag-visibility"),
        ("responses", "responses-table", "rrw-response-tag-visibility"),
    ):
        body = client.get(f"/operator/sessions/{s.id}/{page}").text
        assert f'data-rrw-col-toggles="{key}"' in body
        assert f'data-col-toggles-for="{table}"' in body
        # The page's own slot -> column-class mapping, which the shared
        # primitive deliberately does not know about.
        assert f"#{table}.col-hidden-tag-1 .tag-col-1" in body


def test_invitations_cookie_sort_by_tag(
    client: TestClient, db: Session
) -> None:
    """Tag columns are sortable like the rosters'. Tag order is the
    reverse of name order in the seed, so this cannot pass by
    accident."""
    s = _seed(client, db, "inv-tag-sort")
    rows = _rows(_sorted_body(client, s.id, "invitations", "tag_1", "asc"))
    # Team X (Charlie), Team Y (Bravo), Team Z (Alpha)
    assert (
        rows.find("Charlie R") < rows.find("Bravo R") < rows.find("Alpha R")
    )


def test_responses_cookie_sort_by_tag(
    client: TestClient, db: Session
) -> None:
    s = _seed(client, db, "resp-tag-sort")
    rows = _rows(_sorted_body(client, s.id, "responses", "tag_1", "asc"))
    # Group P (Echo) before Group Q (Delta) — the reverse of name asc.
    assert rows.find("Echo E") < rows.find("Delta E")
