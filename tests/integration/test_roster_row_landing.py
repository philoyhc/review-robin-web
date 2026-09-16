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
        data={f"{page[:-1]}_ids": [ids[0]], "confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text[:300]
    loc = response.headers["location"]
    assert loc.endswith(f"#{page}-table-card"), loc
    assert f"#{noun}-row-" not in loc


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


# ── The page's half ───────────────────────────────────────────────────


@pytest.mark.parametrize("page,noun", PAGES)
def test_the_page_sends_the_offset_the_route_reads(
    client: TestClient, db: Session, page: str, noun: str
) -> None:
    """Both halves or neither. The route reading `filter_offset` is
    worth nothing if the form never posts it, and a hidden input with an
    empty value reads as absent for an `int` field with a default — so
    this asserts a real number, not the field's presence.
    """
    rs = _make_session(client, db, f"snd-{page[:4]}")
    _seed(db, rs.id, page, n=3)
    body = client.get(f"{_base(rs.id, page)}?offset=200").text
    markup = re.sub(r"<(style|script)\b.*?</\1>", "", body, flags=re.S)

    fields = re.findall(
        r'<input type="hidden" name="filter_offset" value="([^"]*)">', markup
    )
    assert len(fields) >= 1, "no filter_offset in any form shell"
    assert all(f.isdigit() for f in fields), fields


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
