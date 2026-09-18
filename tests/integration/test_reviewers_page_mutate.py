"""Reviewers Setup page — selection-driven Edit + Add new row +
bulk inactivate / reactivate — Segment 15F PR 3.

Pins the server-rendered edit state (``?edit_id=`` / ``?add=1``),
the create / update / bulk POST routes, validation-error
re-rendering, and the defensive ``invitations_send_one`` status
guard folded in from PR 6.
"""
from __future__ import annotations

import re

import pytest

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Invitation, Reviewer, ReviewSession


def _make_session(
    client: TestClient, db: Session, *, code: str, status: str = "draft"
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    if status != "draft":
        review_session.status = status
        db.commit()
    return review_session


def _seed(db: Session, session_id: int, names: list[str]) -> list[Reviewer]:
    rows = [
        Reviewer(
            session_id=session_id,
            name=name,
            email=f"{name.lower()}@example.edu",
        )
        for name in names
    ]
    db.add_all(rows)
    db.commit()
    return rows


def _landing_script(body: str) -> str:
    """The edit-row landing script, isolated from the rest of the page.

    Everything it does — `scrollIntoView`, `focus`, reading the hash —
    also appears somewhere in `base.html`, which inlines the whole app's
    JS and CSS on every page. An assertion against the whole response
    therefore says nothing about THIS template.
    """
    m = re.search(
        r"<script>(?:(?!</script>).)*?"
        r'querySelector\(".reviewer-edit-row"\).*?</script>',
        body, re.S,
    )
    assert m, "the edit-row landing script is not served"
    return m.group(0)


# --------------------------------------------------------------------------- #
# Non-edit render — checkbox column + inert-by-default buttons.
# --------------------------------------------------------------------------- #


def test_plain_render_has_checkbox_column_and_action_buttons(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-m-plain")
    _seed(db, review_session.id, ["Alice", "Bob"])

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text
    # Per-row select checkboxes + select-all.
    assert 'class="reviewer-select"' in body
    assert 'id="reviewers-select-all"' in body
    # The four action buttons moved into the row expander at 19P.1
    # rung 2b, so what is checkable in a response with nothing selected
    # is the builder that emits them and the routes they post to. Their
    # arity, status-awareness and delete gate are pinned against a real
    # DOM in `test_reviewers_roster_card_scaffold.py`.
    # Sliced to the builder: `/bulk-inactivate` is also the bulk form
    # shell's own `action`, so asserting it against the whole response
    # passes with the expander's status-action loop deleted outright.
    start = body.index('tr.id = "reviewers-row-expander"')
    build = body[start:body.index("td.innerHTML = html;", start)]
    for route in ("/bulk-inactivate", "/bulk-reactivate", "/bulk-delete"):
        assert route in build, f"the expander cannot reach {route}"
    assert "?add=1" in body  # Add new row link
    # No per-row Actions column.
    assert "reviewer-edit-row" not in body


# --------------------------------------------------------------------------- #
# Edit — server-rendered edit state.
# --------------------------------------------------------------------------- #


def test_edit_id_renders_target_row_as_inputs(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-m-editget")
    rows = _seed(db, review_session.id, ["Alice", "Bob"])

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
        f"?edit_id={rows[0].id}"
    ).text
    assert "reviewer-edit-row" in body
    assert 'id="reviewer-edit-form"' in body
    # Focused Edit card with Save + Cancel.
    # No editor card: the row is the editor, and its controls hang in
    # the bar directly beneath it.
    assert 'class="card row-editor-anchored"' not in body, (
        "the editor card is back"
    )
    assert "row-editor-bar" in body
    assert ">Save</button>" in body
    assert ">Cancel</a>" in body
    # The edited row's name prefilled into an input.
    assert 'name="name"' in body
    assert 'value="Alice"' in body
    # 19P.1 rung 2b: there is nothing left to gray out. `is-locked`
    # existed so a stray click on the filter or an action button could
    # not throw away a half-typed row; the filter moved to the toolbar
    # at rung 2a and the action buttons to the expander at 2b, and the
    # editor itself must stay interactive. Step 3 gave the editor its
    # own card, which this assertion pins the PRESENCE of, in place of a
    # lock with nothing to lock. It does NOT pin that the card renders
    # only in edit mode — an earlier version of this comment claimed it
    # did, and a cold read disproved that by deleting the gate and
    # watching all 4,014 tests pass. The absence half lives in
    # `test_reviewers_roster_card_scaffold.py`
    # (`..._is_absent_outside_edit_mode`).

    # The `Operator actions` shell it used to live in is gone from this
    # page. Four other roster pages still use the class, so the rule
    # stays in `base.html`; what is pinned here is that Reviewers no
    # longer reaches for it. WHERE the new card sits — outside
    # `.card-columns`, which is the whole of step 3 — is structural and
    # a flat substring cannot see it; that is pinned by
    # `test_reviewers_roster_card_scaffold.py`.
    #
    # `<style>` is stripped first: `base.html` inlines the whole app's
    # CSS, and both the rule and a comment naming it live there, so the
    # bare substring is true of every page in the app. The first version
    # of this assertion did not strip, and could not pass.
    markup = re.sub(r"<style\b.*?</style>", "", body, flags=re.S)
    assert "operator-actions-card" not in markup, (
        "the retired `Operator actions` shell is back on Reviewers"
    )
    assert "operator-actions-main is-locked" not in body, (
        "a lock is back, over an editor that must stay usable"
    )


def test_edit_post_updates_row_and_redirects(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-m-editpost")
    rows = _seed(db, review_session.id, ["Alice"])

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/{rows[0].id}/update",
        data={
            "name": "Alice Renamed",
            "email": "alice@example.edu",
            "tag_1": "Mentor",
            "tag_2": "",
            "tag_3": "",
            "status": "inactive",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.expire_all()
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.id == rows[0].id)
    ).scalar_one()
    assert reviewer.name == "Alice Renamed"
    assert reviewer.tag_1 == "Mentor"
    assert reviewer.status == "inactive"


def test_edit_post_validation_error_rerenders_with_values(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-m-editerr")
    rows = _seed(db, review_session.id, ["Alice", "Bob"])

    # Rename Bob to Alice's email → duplicate-email rejection.
    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/{rows[1].id}/update",
        data={
            "name": "Bob",
            "email": "alice@example.edu",
            "tag_1": "",
            "tag_2": "",
            "tag_3": "",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    # Re-rendered in edit mode with the error + the submitted email.
    assert "reviewer-edit-row" in response.text
    # Matched as the ELEMENT, not the class name. `banner-error` used
    # to be the needle and survived only in `base.html`'s inline
    # stylesheet, so it matched every page in the app, error or not —
    # and `row-editor-error` acquired its own rule in that same
    # stylesheet the moment the message was styled, which would have
    # reproduced the vacuity exactly. Same trap `_markup()` exists for.
    assert '<span class="row-editor-error">' in response.text, (
        "no save error rendered"
    )
    assert 'value="alice@example.edu"' in response.text
    # The DB row is untouched.
    db.expire_all()
    bob = db.execute(
        select(Reviewer).where(Reviewer.id == rows[1].id)
    ).scalar_one()
    assert bob.email == "bob@example.edu"


def test_edit_id_outside_cap_is_force_included(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-m-editcap")
    rows = _seed(
        db, review_session.id, [f"R{i:04d}" for i in range(250)]
    )
    # The 250th row is past the 200 unfiltered cap.
    target = rows[240]

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
        f"?edit_id={target.id}"
    ).text
    assert "reviewer-edit-row" in body
    assert f'value="{target.name}"' in body


def test_edit_unknown_reviewer_id_falls_back_to_plain_list(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-m-editstale")
    _seed(db, review_session.id, ["Alice"])

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers?edit_id=999999"
    ).text
    # Stale id → no edit row, plain list renders.
    assert "reviewer-edit-row" not in body
    assert 'class="reviewer-select"' in body


# --------------------------------------------------------------------------- #
# Add new row.
# --------------------------------------------------------------------------- #


def test_add_renders_blank_edit_row(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-m-addget")
    _seed(db, review_session.id, ["Alice"])

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers?add=1"
    ).text
    assert "reviewer-edit-row" in body
    # The blank row IS the editor: its heading card went when Save and
    # Cancel moved into the row's own bar, so what marks add mode is
    # the row carrying the landing anchor.
    assert 'id="reviewers-row-editor"' in body
    assert ">Save</button>" in body


def test_add_works_on_empty_roster(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-m-addempty")
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers?add=1"
    ).text
    # The blank edit row renders even with zero existing reviewers.
    assert "reviewer-edit-row" in body


def test_add_post_creates_row_and_redirects(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-m-addpost")

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/create",
        data={
            "name": "Newbie",
            "email": "newbie@example.edu",
            "tag_1": "",
            "tag_2": "",
            "tag_3": "",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    reviewer = db.execute(
        select(Reviewer).where(
            Reviewer.session_id == review_session.id
        )
    ).scalar_one()
    assert reviewer.name == "Newbie"
    assert reviewer.email == "newbie@example.edu"


def test_add_post_validation_error_rerenders_in_add_mode(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-m-adderr")

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/create",
        data={
            "name": "Bad",
            "email": "not-an-email",
            "tag_1": "",
            "tag_2": "",
            "tag_3": "",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert 'id="reviewers-row-editor"' in response.text
    # Matched as the ELEMENT, not the class name. `banner-error` used
    # to be the needle and survived only in `base.html`'s inline
    # stylesheet, so it matched every page in the app, error or not —
    # and `row-editor-error` acquired its own rule in that same
    # stylesheet the moment the message was styled, which would have
    # reproduced the vacuity exactly. Same trap `_markup()` exists for.
    assert '<span class="row-editor-error">' in response.text, (
        "no save error rendered"
    )
    # The bad value is preserved for correction.
    assert 'value="not-an-email"' in response.text
    # Nothing was persisted.
    assert (
        db.execute(
            select(Reviewer).where(
                Reviewer.session_id == review_session.id
            )
        ).first()
        is None
    )


# --------------------------------------------------------------------------- #
# Bulk inactivate / reactivate.
# --------------------------------------------------------------------------- #


def test_bulk_inactivate_flips_selected_rows(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-m-bulkinact")
    rows = _seed(db, review_session.id, ["Alice", "Bob", "Carol"])

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/bulk-inactivate",
        data={"reviewer_ids": [rows[0].id, rows[2].id]},
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.expire_all()
    statuses = {
        r.name: r.status
        for r in db.execute(
            select(Reviewer).where(
                Reviewer.session_id == review_session.id
            )
        ).scalars()
    }
    assert statuses == {
        "Alice": "inactive",
        "Bob": "active",
        "Carol": "inactive",
    }


def test_bulk_action_keeps_selection(
    db: Session, client: TestClient
) -> None:
    """After a bulk action the redirect carries the acted-on ids
    so the operator clears the selection themselves."""
    review_session = _make_session(client, db, code="rev-m-keepsel")
    rows = _seed(db, review_session.id, ["Alice", "Bob", "Carol"])

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/bulk-inactivate",
        data={"reviewer_ids": [rows[0].id, rows[2].id]},
        follow_redirects=False,
    )
    loc = response.headers["location"]
    assert f"selected={rows[0].id}" in loc
    assert f"selected={rows[2].id}" in loc

    body = client.get(loc).text
    table = body[body.find('id="reviewers-table"') :]
    # The acted-on rows render their checkbox checked.
    for rid in (rows[0].id, rows[2].id):
        marker = f'value="{rid}"'
        cell = table[table.find(marker) - 160 : table.find(marker) + 160]
        assert "checked" in cell
    # The untouched row is not pre-checked.
    bob_marker = f'value="{rows[1].id}"'
    bob_cell = table[
        table.find(bob_marker) - 160 : table.find(bob_marker) + 160
    ]
    assert "checked" not in bob_cell


def test_bulk_action_keeps_filter(
    db: Session, client: TestClient
) -> None:
    """The active search / status filter rides through a bulk
    action so the operator lands back on the same filtered view."""
    review_session = _make_session(client, db, code="rev-m-keepfilter")
    rows = _seed(db, review_session.id, ["Alice", "Bob", "Carol"])

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/bulk-inactivate",
        data={
            "reviewer_ids": [rows[0].id],
            "filter_status": "active",
            "filter_q": "Ali",
        },
        follow_redirects=False,
    )
    loc = response.headers["location"]
    assert "status=active" in loc
    assert "q=Ali" in loc


def test_bulk_reactivate_flips_selected_rows(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-m-bulkreact")
    rows = _seed(db, review_session.id, ["Alice", "Bob"])
    for r in rows:
        r.status = "inactive"
    db.commit()

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/bulk-reactivate",
        data={"reviewer_ids": [rows[0].id]},
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.expire_all()
    statuses = {
        r.name: r.status
        for r in db.execute(
            select(Reviewer).where(
                Reviewer.session_id == review_session.id
            )
        ).scalars()
    }
    assert statuses == {"Alice": "active", "Bob": "inactive"}


def test_bulk_with_id_outside_session_is_rejected(
    db: Session, client: TestClient
) -> None:
    session_a = _make_session(client, db, code="rev-m-bulk-a")
    rows_a = _seed(db, session_a.id, ["Alice"])
    session_b = _make_session(client, db, code="rev-m-bulk-b")
    rows_b = _seed(db, session_b.id, ["Bob"])

    response = client.post(
        f"/operator/sessions/{session_a.id}/reviewers/bulk-inactivate",
        data={"reviewer_ids": [rows_a[0].id, rows_b[0].id]},
        follow_redirects=False,
    )
    assert response.status_code == 400


# --------------------------------------------------------------------------- #
# Lifecycle gate.
# --------------------------------------------------------------------------- #


def test_edit_mode_suppressed_on_ready_session(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(
        client, db, code="rev-m-ready", status="ready"
    )
    rows = _seed(db, review_session.id, ["Alice"])

    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
        f"?edit_id={rows[0].id}"
    ).text
    # Ready session → edit mode suppressed, lock card shown instead.
    assert "reviewer-edit-row" not in body
    assert "card lock" in body


def test_create_on_ready_session_is_409(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(
        client, db, code="rev-m-ready-create", status="ready"
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/create",
        data={
            "name": "X",
            "email": "x@example.edu",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert response.status_code == 409


# --------------------------------------------------------------------------- #
# PR 6 fold-in — defensive invitations_send_one status guard.
# --------------------------------------------------------------------------- #


def test_send_invitation_to_inactive_reviewer_is_409(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(
        client, db, code="rev-m-send-inactive", status="ready"
    )
    reviewer = Reviewer(
        session_id=review_session.id,
        name="Inactive",
        email="inactive@example.edu",
        status="inactive",
    )
    db.add(reviewer)
    db.flush()
    invitation = Invitation(
        session_id=review_session.id,
        reviewer_id=reviewer.id,
        token_hash="x" * 64,
        status="pending",
    )
    db.add(invitation)
    db.commit()

    response = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/invitations/{invitation.id}/send",
        follow_redirects=False,
    )
    assert response.status_code == 409


# ── Row actions land on the row they acted on (19P.1) ────────────────────
#
# A bare 303 lands at the top of the document: measured at 821px of jump
# from a mid-table action. Two things carry the operator's place through
# the POST — the pager offset, and a fragment naming the acted-on row.


# Every row action, not the two that happened to get written first. A
# cold read deleted `offset=` and `anchor=` from `reviewers_update`
# alone — the commonest action on the page — and the whole suite stayed
# green, because all three redirect tests exercised the bulk routes.
_ROW_ACTIONS = [
    ("update", "{base}/{rid}/update", {
        "name": "Alice", "email": "alice@example.edu",
        "tag_1": "", "tag_2": "", "tag_3": "", "status": "active",
    }),
    ("bulk-inactivate", "{base}/bulk-inactivate", {"reviewer_ids": ["{rid}"]}),
    ("bulk-reactivate", "{base}/bulk-reactivate", {"reviewer_ids": ["{rid}"]}),
]


def _post_row_action(client, base, rid, template, data, **extra):
    payload = {k: ([rid] if v == ["{rid}"] else v) for k, v in data.items()}
    payload.update(extra)
    return client.post(
        template.format(base=base, rid=rid), data=payload,
        follow_redirects=False,
    )


@pytest.mark.parametrize("name,template,data", _ROW_ACTIONS)
def test_every_row_action_lands_on_the_row_it_acted_on(
    db: Session, client: TestClient, name: str, template: str, data: dict
) -> None:
    review_session = _make_session(client, db, code=f"rev-anch-{name[:6]}")
    rows = _seed(db, review_session.id, ["Alice"])
    base = f"/operator/sessions/{review_session.id}/reviewers"

    response = _post_row_action(client, base, rows[0].id, template, data)
    assert response.status_code == 303, name
    assert response.headers["location"].endswith(
        f"#reviewer-row-{rows[0].id}"
    ), f"{name}: {response.headers['location']}"


@pytest.mark.parametrize("name,template,data", _ROW_ACTIONS)
def test_every_row_action_carries_the_pager_offset(
    db: Session, client: TestClient, name: str, template: str, data: dict
) -> None:
    """Without it the 303 answered with page 1 whatever page the action
    was taken from — so the operator lost their place AND the row the
    anchor names was not in the response to be found."""
    review_session = _make_session(client, db, code=f"rev-off-{name[:6]}")
    rows = _seed(db, review_session.id, ["Alice"])
    base = f"/operator/sessions/{review_session.id}/reviewers"

    loc = _post_row_action(
        client, base, rows[0].id, template, data, filter_offset=200
    ).headers["location"]
    assert "offset=200" in loc, f"{name}: {loc}"

    plain = _post_row_action(
        client, base, rows[0].id, template, data
    ).headers["location"]
    assert "offset=" not in plain, f"{name}: {plain}"


def test_the_page_actually_sends_the_offset_it_asks_the_route_to_read(
    db: Session, client: TestClient
) -> None:
    """The render half, which the route-level tests above cannot see.

    They POST `filter_offset` themselves, so they prove the route READS
    the field and never that the page SENDS one. A cold read deleted
    both hidden inputs — killing the feature in every browser — and all
    4,038 tests passed.

    Seeded past the 200-row page cap so the value is a real non-zero
    offset: a field rendering `0` on every page would satisfy a presence
    check while carrying nothing.
    """
    review_session = _make_session(client, db, code="rev-sends-offset")
    _seed(db, review_session.id, [f"R{n}" for n in range(1, 231)])
    base = f"/operator/sessions/{review_session.id}/reviewers"

    bulk = re.search(
        r'<form[^>]*id="reviewers-bulk-form".*?</form>',
        client.get(f"{base}?offset=200").text, re.S,
    )
    assert bulk, "bulk form not rendered on page 2"
    assert 'name="filter_offset" value="200"' in bulk.group(0), (
        "the bulk form does not carry the page it was rendered on"
    )

    # `.order_by` is load-bearing (19O Item 6, raised on #2444): a
    # `SELECT` with no `ORDER BY` has no guaranteed row order, so
    # indexing `[210]` was asking the database for its 211th row by
    # luck. SQLite happens to return insertion order for this shape
    # and Postgres need not, which makes it a `ci-postgres`-only flake
    # — the worst kind, because the suite is green where it is written.
    rid = db.execute(
        select(Reviewer.id)
        .where(Reviewer.session_id == review_session.id)
        .order_by(Reviewer.id)
    ).scalars().all()[210]
    edit = re.search(
        r'<form[^>]*id="reviewer-edit-form".*?</form>',
        client.get(f"{base}?edit_id={rid}").text, re.S,
    )
    assert edit, "edit form not rendered"
    assert 'name="filter_offset" value="200"' in edit.group(0), (
        "the edit form does not carry the page the edited row is on"
    )


def test_delete_lands_on_the_table_card_because_its_rows_are_gone(
    db: Session, client: TestClient
) -> None:
    review_session = _make_session(client, db, code="rev-delanchor")
    rows = _seed(db, review_session.id, ["Alice"])

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/bulk-delete",
        data={
            "reviewer_ids": [rows[0].id],
            "confirm": "true",
            "acknowledge_response_loss": "true",
            "filter_offset": 200,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    loc = response.headers["location"]
    assert loc.endswith("#reviewers-table-card"), loc
    assert "#reviewer-row-" not in loc, (
        "delete anchored a row it had just removed"
    )
    # A delete has no row to name, but it still has a page to come back
    # to. `_ROW_ACTIONS` cannot cover this one — deleting the row it
    # acts on leaves nothing for the anchor assertion to name — so the
    # offset half is asserted here. Added at 19P.2 rung 1, where the
    # equivalent mutation on the Observers copy was the only survivor.
    assert "offset=200" in loc, loc


def test_rows_and_the_fallback_are_both_present_for_the_landing(
    db: Session, client: TestClient
) -> None:
    """The two halves the anchor needs, and that they refer to each other.

    Whether the browser actually scrolls is checked in Chromium — the
    suite has no layout engine. What is pinned here is that a row the
    redirect can name carries the class that gives it its landing
    margin, and that the fallback script exists for the case the
    fragment cannot resolve (a status change that drops the row out of a
    filtered view).
    """
    review_session = _make_session(client, db, code="rev-landing")
    rows = _seed(db, review_session.id, ["Alice"])
    body = client.get(
        f"/operator/sessions/{review_session.id}/reviewers"
    ).text

    row = re.search(
        rf'<tr\b[^>]*id="reviewer-row-{rows[0].id}"[^>]*>', body
    )
    assert row, "the row the redirect names is not rendered"
    assert "row-action-target" in row.group(0), (
        "the row carries no landing margin"
    )
    assert "tr.row-action-target" in body, "no rule gives it that margin"

    # Read the fallback's OWN text. `'"reviewers-table-card"' in body`
    # was satisfied by the table card's `id=` attribute, which renders
    # regardless — so deleting the two operative lines of the script
    # left that assertion green.
    script = re.search(
        r"<script>(?:(?!</script>).)*?#reviewer-row-.*?</script>", body, re.S
    )
    assert script, "the fallback script is gone"
    for needle in ("getElementById", "reviewers-table-card", "scrollIntoView"):
        assert needle in script.group(0), f"the fallback lost {needle}"


def test_add_new_carries_the_active_filter_into_add_mode(
    db: Session, client: TestClient
) -> None:
    """The filter was lost at the NAVIGATION, not at the POST.

    `Add new` linked to a bare `?add=1`, so the add page rendered
    unfiltered and its hidden `filter_*` fields held defaults — which
    the create route then faithfully honoured all the way back to an
    unfiltered list.
    """
    review_session = _make_session(client, db, code="rev-addfilter")
    _seed(db, review_session.id, ["Alice", "Bob"])
    base = f"/operator/sessions/{review_session.id}/reviewers"

    body = client.get(f"{base}?status=inactive&q=ali").text
    link = re.search(r'<a[^>]*>\s*Add new\s*</a>', body)
    assert link, "no Add new link"
    assert "status=inactive" in link.group(0), link.group(0)
    assert "q=ali" in link.group(0), link.group(0)

    # An unfiltered view carries neither — `status=all` is the default
    # and an empty search is nothing, so spelling them out would be
    # noise in the URL.
    plain = re.search(
        r'<a[^>]*>\s*Add new\s*</a>', client.get(base).text
    ).group(0)
    assert "status=" not in plain and "q=" not in plain, plain


def test_creating_a_row_pages_to_where_the_new_row_actually_is(
    db: Session, client: TestClient
) -> None:
    """Rows list by id, so a create appends past the end.

    On a roster over one page the new row is not on the page the add
    form was submitted from, so the redirect's `#reviewer-row-<id>`
    named a row the response did not render and the landing fell back
    to the table card. `focus` moves the window to the row instead.
    """
    review_session = _make_session(client, db, code="rev-createpage")
    _seed(db, review_session.id, [f"R{n}" for n in range(1, 231)])
    base = f"/operator/sessions/{review_session.id}/reviewers"

    response = client.post(
        f"{base}/create",
        data={
            "name": "Zed", "email": "zed@example.edu",
            "tag_1": "", "tag_2": "", "tag_3": "", "status": "active",
            "filter_offset": 0,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    loc = response.headers["location"]
    created = db.execute(
        select(Reviewer).where(Reviewer.email == "zed@example.edu")
    ).scalar_one()
    assert f"focus={created.id}" in loc, loc
    assert loc.endswith(f"#reviewer-row-{created.id}"), loc

    # The row the fragment names is actually in the response it lands on.
    landed = client.get(loc.split("#")[0]).text
    assert f'id="reviewer-row-{created.id}"' in landed, (
        "the redirect lands on a page that does not render the new row"
    )
    assert ">Zed<" in landed


def test_a_save_error_renders_in_the_row_bar_and_is_reachable(
    db: Session, client: TestClient
) -> None:
    """The message moved out of the editor card when that card went.

    Two halves. The message has to render WITH the row it is about —
    the card put it a table's height away — and the operator has to be
    able to see it: a failed save is not a navigation, it re-renders in
    place with a 400 and no fragment, so the page arrives at the top
    with the row below the fold. Measured before the fix: the message
    rendered at y=995 in a 900px viewport.

    The scroll itself is a browser behavior the suite cannot run. What
    is pinned here is that the message is in the bar, and that the
    script which lands on the row is served on this render at all — it
    was gated on `add_mode` and a failed EDIT reaches the same state.
    """
    review_session = _make_session(client, db, code="rev-errhome")
    _seed(db, review_session.id, ["Alice"])
    base = f"/operator/sessions/{review_session.id}/reviewers"

    response = client.post(
        f"{base}/create",
        data={
            "name": "Dup", "email": "alice@example.edu",
            "tag_1": "", "tag_2": "", "tag_3": "", "status": "active",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    body = response.text

    bar = re.search(
        r'<tr class="[^"]*\brow-editor-bar\b[^"]*">.*?</tr>', body, re.S,
    )
    assert bar, "no editor bar on the error render"
    assert '<span class="row-editor-error">' in bar.group(0), (
        "the save error is not in the bar with the row it is about"
    )
    assert "already uses" in bar.group(0), "the message itself is missing"

    assert "reviewer-edit-row" in body

    # The EDIT error path, which is the one the script's gate decides.
    # A failed create is still add mode, so a script gated on `add_mode`
    # renders here and this assertion passed against the bug — checked
    # by mutation, which is how the first version of this test was found
    # to be testing the wrong half.
    _seed(db, review_session.id, ["Bob"])
    bob = db.execute(
        select(Reviewer).where(Reviewer.email == "bob@example.edu")
    ).scalar_one()
    edit_err = client.post(
        f"{base}/{bob.id}/update",
        data={
            "name": "Bob", "email": "alice@example.edu",
            "tag_1": "", "tag_2": "", "tag_3": "", "status": "active",
        },
        follow_redirects=False,
    )
    assert edit_err.status_code == 400
    edit_body = edit_err.text
    assert '<span class="row-editor-error">' in edit_body, (
        "no error on a failed edit"
    )

    # Scoped to the landing script itself. `"scrollIntoView" in body`
    # is satisfied by `base.html`'s banner-scroll script, which ships on
    # every ui-v2 page — so that assertion passed with this commit's
    # entire fix replaced by a no-op, which a cold read demonstrated
    # against the full suite. Same trap, and the same fix, as the
    # fallback-script assertion 140 lines up in this file.
    script = _landing_script(edit_body)
    assert "scrollIntoView" in script, (
        "nothing brings the row on screen on an edit error, which "
        "re-renders with no fragment"
    )
    # ...and it only scrolls when no fragment decided the position.
    assert "window.location.hash" in script, (
        "the script scrolls unconditionally, fighting the landing anchor"
    )
    assert "block: \"center\"" in script, (
        "the row is brought on screen without being centred, so a long "
        "row can still land with its bar below the fold"
    )


def test_delete_all_comes_back_with_the_panel_open(
    db: Session, client: TestClient
) -> None:
    """The control lives inside the Unlock panel now, so a bare redirect
    closes the panel the operator was working in.

    The Danger Zone itself is gone from that response — the roster is
    empty and the card is gated on rows — but the labels editor and the
    upload card are not, and uploading a replacement is the likely next
    move. Rung 3a's labels save needed the same flag for the same
    reason; 3b shipped without it because the plan read "redirect-only"
    off the status code rather than the contract.
    """
    review_session = _make_session(client, db, code="rev-da-open")
    _seed(db, review_session.id, ["Alice"])

    response = client.post(
        f"/operator/sessions/{review_session.id}/reviewers/delete-all",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/operator/sessions/{review_session.id}/reviewers"
        "?unlocked=1#roster-card"
    ), response.headers["location"]


# The Danger Zone's roster-count gate is NOT tested here.
#
# Rung 3c retired the roster-card note, and the test that lived at this
# point — `..._the_roster_note_promises_delete_all_only_when_it_renders`
# — was a biconditional between that note and the Danger Zone. I kept
# its gate half and renamed it, on the stated ground that it was "the
# only assertion in the suite" that the card is ABSENT on an empty
# roster.
#
# That was false, and the cold read caught it. `test_reviewers_roster_
# card_scaffold.py::test_the_danger_zone_is_gated_on_the_roster_having_
# rows` has asserted exactly that since 3b, and asserts it more
# strongly: it also pins the `/reviewers/delete-all` route absent from
# the whole page, which the version here did not.
#
# The uniqueness claim came from grepping for the literal string
# `reviewers-danger-h` and finding no other absence assertion. The
# sibling reaches the same element through the `_danger()` helper, so
# the grep could not see it — the same "trust a substring" mistake that
# produced this segment's vacuous assertions, this time aimed at the
# test suite instead of the page. Retired rather than kept as a weaker
# duplicate that invites someone to delete the better one.
