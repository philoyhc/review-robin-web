"""Row actions on Setup-Reviewees and Setup-Relationships land on the
row they acted on.

19P.3 rung 1 — the contract Reviewers got at 19P.1 and Observers at
19P.2, carried to the last two roster pages. A bare 303 lands at the top
of the document; two things carry the operator's place through the POST:
the pager ``offset``, and a fragment naming the acted-on row.

**Both pages in one file, parametrized**, because 19P.3's whole risk is
drift between two pages that should be identical. A per-page file lets
one page quietly gain a guard the other does not — which is the failure
19P.1's spec cold read spent fifteen findings on, one level up.

**`create` is a conversion, not an argument.** The other four row
actions already called ``_redirect_keeping_selection`` and needed
``offset=`` / ``anchor=`` added. ``create`` returned a **bare**
``RedirectResponse`` on both pages: no selection, no filter, no offset,
no fragment. So it lost more than the others did, and rung 1 rewrites it
rather than extending it. The plan said "five POSTs gain offset and a
fragment"; the fifth had to gain the filter round-trip too.

Whether the browser actually scrolls is checked in Chromium — the suite
has no layout engine, so ``scroll-margin-top`` is invisible to it. What
is pinned here is the wiring on both halves: the route reads what the
page sends, and the page sends a real value.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Relationship, Reviewee, Reviewer, ReviewSession

#: ``(page, noun, id-attr)`` — the two pages this rung moves.
PAGES = [("reviewees", "reviewee"), ("relationships", "relationship")]


def _make_session(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "R", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    rs = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    # Relationships is gate-hidden like Observers — its routes 404
    # behind `require_relationships_enabled_session`.
    rs.relationships_enabled = True
    db.commit()
    db.refresh(rs)
    return rs


def _seed(db: Session, sid: int, page: str, n: int = 3) -> list[int]:
    """Rows on whichever page is under test, returning their ids.

    Relationships needs a reviewer and a reviewee per row, so both pages
    seed reviewers/reviewees; only the row type differs.
    """
    reviewers = [
        Reviewer(session_id=sid, name=f"Rr{i}", email=f"rr{i}@example.org")
        for i in range(n)
    ]
    reviewees = [
        Reviewee(session_id=sid, name=f"Re{i}", email_or_identifier=f"re{i}@example.org")
        for i in range(n)
    ]
    db.add_all(reviewers + reviewees)
    db.commit()
    for r in reviewers + reviewees:
        db.refresh(r)

    if page == "reviewees":
        return [r.id for r in reviewees]

    rows = [
        Relationship(
            session_id=sid, reviewer_id=reviewers[i].id, reviewee_id=reviewees[i].id
        )
        for i in range(n)
    ]
    db.add_all(rows)
    db.commit()
    for r in rows:
        db.refresh(r)
    return [r.id for r in rows]


def _row_action_payloads(page: str, rid: int) -> list[tuple[str, str, dict]]:
    """Every row action on the page, not the two that happened to get
    written first — a cold read on the Reviewers original deleted
    ``offset=`` / ``anchor=`` from the single commonest action and the
    whole suite stayed green.
    """
    ids_field = f"{page[:-1]}_ids"
    if page == "reviewees":
        update = {
            "name": "Alice", "email_or_identifier": "alice@example.org",
            "profile_link": "", "tag_1": "", "tag_2": "", "tag_3": "",
            "status_value": "active",
        }
    else:
        # `"Name (handle)"` — the canonical picker label
        # (`_picker_label`), matched exactly. A bare email 400s.
        update = {
            "reviewer_pick": "Rr0 (rr0@example.org)",
            "reviewee_pick": "Re0 (re0@example.org)",
            "tag_1": "", "tag_2": "", "tag_3": "", "status_value": "active",
        }
    return [
        ("update", "{base}/{rid}/update", update),
        ("bulk-inactivate", "{base}/bulk-inactivate", {ids_field: [rid]}),
        ("bulk-reactivate", "{base}/bulk-reactivate", {ids_field: [rid]}),
    ]


def _base(sid: int, page: str) -> str:
    return f"/operator/sessions/{sid}/{page}"


# ── The route's half ──────────────────────────────────────────────────


@pytest.mark.parametrize("page,noun", PAGES)
def test_every_row_action_lands_on_the_row_it_acted_on(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    rs = _make_session(client, db, f"land-{page[:4]}")
    ids = _seed(db, rs.id, page)
    base = _base(rs.id, page)

    for name, template, data in _row_action_payloads(page, ids[0]):
        response = client.post(
            template.format(base=base, rid=ids[0]),
            data=data, follow_redirects=False,
        )
        assert response.status_code == 303, (name, response.text[:300])
        loc = response.headers["location"]
        assert loc.endswith(f"#{noun}-row-{ids[0]}"), (name, loc)


@pytest.mark.parametrize("page,noun", PAGES)
def test_every_row_action_carries_the_pager_offset(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """The offset is what makes the fragment resolvable at all: without
    it the redirect answers page 1, where the acted-on row is not."""
    rs = _make_session(client, db, f"off-{page[:4]}")
    ids = _seed(db, rs.id, page)
    base = _base(rs.id, page)

    for name, template, data in _row_action_payloads(page, ids[0]):
        response = client.post(
            template.format(base=base, rid=ids[0]),
            data={**data, "filter_offset": "200"}, follow_redirects=False,
        )
        q = parse_qs(urlparse(response.headers["location"]).query)
        assert q.get("offset") == ["200"], (name, response.headers["location"])


@pytest.mark.parametrize("page,noun", PAGES)
def test_delete_lands_on_the_table_card_because_its_rows_are_gone(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """A delete has no row to return to, so the route sends the card a
    step earlier rather than leaving the fallback script to catch it."""
    rs = _make_session(client, db, f"del-{page[:4]}")
    ids = _seed(db, rs.id, page)
    response = client.post(
        f"{_base(rs.id, page)}/bulk-delete",
        data={f"{page[:-1]}_ids": [ids[0]], "confirm": "true",
              "filter_offset": "200"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text[:300]
    loc = response.headers["location"]
    assert loc.endswith(f"#{page}-table-card"), loc
    assert f"#{noun}-row-" not in loc
    # ...and it still keeps the operator's page. Having no row to land on
    # is not having no place to return to — the offset was the one
    # mutation that survived the Observers original, and dropping it here
    # survived this file's first table too.
    assert parse_qs(urlparse(loc).query).get("offset") == ["200"], loc


# ── The create conversion ─────────────────────────────────────────────


@pytest.mark.parametrize("page,noun", PAGES)
def test_a_create_carries_the_filter_offset_and_focus(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """`create` answered with a BARE redirect on both pages — no
    selection, no filter, no offset, no fragment — so it lost the
    operator's whole view, not just their scroll position.

    `focus` is the create-only half: rows list by id, so a new row
    appends past the end and on a roster over one page is not on the
    page the form was submitted from. The fragment alone would name a
    row the response never rendered.
    """
    rs = _make_session(client, db, f"new-{page[:4]}")
    _seed(db, rs.id, page)
    if page == "reviewees":
        payload = {
            "name": "Zed", "email_or_identifier": "zed@example.org",
            "profile_link": "", "tag_1": "", "tag_2": "", "tag_3": "",
            "status_value": "active",
        }
    else:
        payload = {
            "reviewer_pick": "Rr1 (rr1@example.org)",
            "reviewee_pick": "Re2 (re2@example.org)",
            "tag_1": "", "tag_2": "", "tag_3": "", "status_value": "active",
        }
    response = client.post(
        f"{_base(rs.id, page)}/create",
        data={**payload, "filter_status": "active", "filter_q": "e",
              "filter_offset": "200"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text[:400]
    loc = response.headers["location"]
    q = parse_qs(urlparse(loc).query)

    assert q.get("offset") == ["200"], loc
    assert q.get("status") == ["active"], f"the filter was dropped: {loc}"
    assert q.get("q") == ["e"], f"the search was dropped: {loc}"
    assert "focus" in q, f"no focus on a create: {loc}"
    assert loc.endswith(f"#{noun}-row-{q['focus'][0]}"), loc


@pytest.mark.parametrize("page,noun", PAGES)
def test_creating_a_row_pages_to_where_the_new_row_actually_is(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """`focus` has to *do* something, not just ride in the Location.

    Rows list by id, so a create appends past the end of a multi-page
    roster and is not on the page the form was submitted from. `focus`
    reaches `_setup_row_window` as `locate_id` and relocates the window
    onto the page holding the new row; the fragment then resolves.

    Asserted by **following the redirect and looking for the row**,
    because the param's presence in the header proves only that it was
    sent. Deleting `locate_id=focus_id` from both render helpers left
    every other test in this file green.
    """
    rs = _make_session(client, db, f"pg-{page[:4]}")
    _seed(db, rs.id, page, n=230)
    if page == "reviewees":
        payload = {
            "name": "Zed", "email_or_identifier": "zed@example.org",
            "profile_link": "", "tag_1": "", "tag_2": "", "tag_3": "",
            "status_value": "active",
        }
    else:
        payload = {
            "reviewer_pick": "Rr1 (rr1@example.org)",
            "reviewee_pick": "Re2 (re2@example.org)",
            "tag_1": "", "tag_2": "", "tag_3": "", "status_value": "active",
        }
    response = client.post(
        f"{_base(rs.id, page)}/create", data=payload, follow_redirects=False
    )
    assert response.status_code == 303, response.text[:400]
    loc = response.headers["location"]
    new_id = parse_qs(urlparse(loc).query)["focus"][0]

    landed = client.get(loc).text
    assert f'id="{noun}-row-{new_id}"' in landed, (
        "the redirect landed on a page the new row is not on — `focus` "
        "reached the URL but not the pager window"
    )


# ── The page's half ───────────────────────────────────────────────────


def _shell(markup: str, form_id: str) -> str:
    """One form shell by id. Both shells must be read separately: only
    one renders per request, and a `>= 1` count over the page cannot
    tell which."""
    i = markup.index(f'id="{form_id}"')
    return markup[i:markup.index("</form>", i)]


@pytest.mark.parametrize("page,noun", PAGES)
def test_both_form_shells_send_the_offset_the_route_reads(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """Both halves or neither, on **both** shells.

    **Seeded past one page on purpose.** `clamp_offset` pulls an offset
    past the end back to 0, so a 3-row roster renders `value="0"` and
    any `isdigit()` assertion holds however the value is computed —
    which is how `"current_offset": 0` survived this file's first
    mutation table. 230 rows makes 200 a real offset.

    **And each shell by id**, because only one renders per request: the
    bulk shell on a plain GET, the edit shell under `?edit_id=`. A
    page-wide count of `>= 1` cannot tell which one it found, and
    `update` — the route that reads it — posts from the edit shell.
    """
    rs = _make_session(client, db, f"snd-{page[:4]}")
    ids = _seed(db, rs.id, page, n=230)

    bulk = client.get(f"{_base(rs.id, page)}?offset=200").text
    bulk = re.sub(r"<(style|script)\b.*?</\1>", "", bulk, flags=re.S)
    assert 'name="filter_offset" value="200"' in _shell(
        bulk, f"{page}-bulk-form"
    ), "the bulk shell does not send the live offset"

    edit = client.get(f"{_base(rs.id, page)}?edit_id={ids[210]}").text
    edit = re.sub(r"<(style|script)\b.*?</\1>", "", edit, flags=re.S)
    shell = _shell(edit, f"{noun}-edit-form")
    m = re.search(r'name="filter_offset" value="(\d+)"', shell)
    assert m and m.group(1) != "0", (
        "the edit shell does not send the offset of the page the edited "
        f"row is on: {shell[:200]}"
    )


@pytest.mark.parametrize("page,noun", PAGES)
def test_rows_and_the_fallback_are_both_present(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """The fragment needs a row carrying that id, and the landing offset
    needs the class `base.html` hangs `scroll-margin-top` on.

    And the fallback catches what the fragment cannot resolve. **These
    pages have two such cases, not Observers' one** — they ship
    `rrw-sortable` headers, so a row can move off the restored page
    under the operator's cookie-held sort as well as drop out of a
    filtered view.
    """
    rs = _make_session(client, db, f"row-{page[:4]}")
    ids = _seed(db, rs.id, page)
    body = client.get(_base(rs.id, page)).text
    markup = re.sub(r"<(style|script)\b.*?</\1>", "", body, flags=re.S)

    assert f'id="{noun}-row-{ids[0]}"' in markup
    assert "row-action-target" in markup, "no landing offset on the rows"
    # The fallback lives in a script, so read the script, not the markup.
    assert f'hash.indexOf("#{noun}-row-")' in body, "no fragment fallback"
    assert "rrw-sortable" in markup, (
        "this page is not sortable after all — the fallback's second "
        "case does not apply and its comment is wrong"
    )


@pytest.mark.parametrize("page,noun", PAGES)
def test_the_fallback_survives_an_empty_filtered_view(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """The fallback must not live inside the `{% if rows %}` branch.

    Its first case taken to the limit IS the empty filtered view —
    inactivate the last row matching `status=active` and the redirect
    lands on `#<noun>-row-N` with nothing rendered. A fallback that only
    ships when there are rows is absent exactly when it is needed.

    The first draft string-matched the pager-cluster include and landed
    inside that branch on both pages. Harmless today, because the
    empty-state card carries no id for `getElementById` to find — and a
    live defect the moment rung 2 or 3 gives it one.
    """
    rs = _make_session(client, db, f"emp-{page[:4]}")
    _seed(db, rs.id, page, n=2)
    body = client.get(f"{_base(rs.id, page)}?q=zzz-matches-nothing").text

    assert "match the current filter" in body or "No " in body, (
        "the fixture did not reach the empty-filtered branch"
    )
    assert f'hash.indexOf("#{noun}-row-")' in body, (
        "the fallback is trapped inside the rows branch"
    )
    # ...and it has something to scroll to. The script looks up
    # `pager_anchor` by id; on the empty-filtered branch the table card
    # is not rendered, so without an id here `getElementById` returns
    # null and the fallback no-ops in the one state its first case
    # actually reaches.
    assert f'id="{page}-table-card"' in body, (
        "the empty-filtered card carries no landing anchor, so the "
        "fallback has nothing to find"
    )


@pytest.mark.parametrize("page,noun", PAGES)
def test_add_carries_the_active_filter_into_add_mode(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """The create route's filter round-trip is only reachable if `Add`
    carries the filter *in*.

    `Add` is a GET, so the page is rebuilt from the URL. Linked bare as
    `?add=1` — which is how both these pages shipped — the rebuild uses
    `filter_status="all"` / `filter_q=""`, the form shell renders those
    defaults, and the create redirect then round-trips nothing. The
    route half works and the flow does not.

    **Driven GET → POST**, because a test that posts the filter fields
    directly cannot see this: it supplies what the UI would have lost.
    That is exactly how this file's first draft missed it.
    """
    rs = _make_session(client, db, f"add-{page[:4]}")
    _seed(db, rs.id, page, n=3)
    listing = client.get(f"{_base(rs.id, page)}?status=active&q=re").text

    # The link the operator actually clicks.
    m = re.search(rf'href="([^"]*{page}[^"]*add=1[^"]*)"', listing)
    assert m, "no Add link on the page"
    href = m.group(1).replace("&amp;", "&")
    assert "status=active" in href, f"Add drops the status filter: {href}"
    assert "q=re" in href, f"Add drops the search: {href}"

    # ...and following it renders a shell that will post them back.
    add_page = client.get(href).text
    shell = _shell(
        re.sub(r"<(style|script)\b.*?</\1>", "", add_page, flags=re.S),
        f"{noun}-edit-form",
    )
    assert 'name="filter_status" value="active"' in shell, shell[:220]
    assert 'name="filter_q" value="re"' in shell, shell[:220]
