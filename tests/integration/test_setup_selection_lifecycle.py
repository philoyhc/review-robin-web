"""The selection surface renders only where it can act — 19I Item 3 PR 1.

The four roster pages gated row selection on `is_ready`, which is *only*
`status == "ready"`. So an `expired` or `archived` session rendered
checkboxes and a live Delete while every mutation 409'd, and a `ready`
session rendered a Delete that nothing could ever enable.

The gate is now `lifecycle.is_editable` — `draft` or `validated` — which
is what `_require_editable` enforces on the routes, so the page and the
route agree by construction rather than by two lists kept in step.

Observers **left this contract entirely at 19P.2 rung 2.** Every
mutating observers route relaxed from `_require_editable` to
`_require_not_archived`, on the author's ruling that an observer row is
a view grant: observers never appear in assignments, never produce
responses, and no readiness rule references them, so freezing their
roster at Activate bought nothing. Its whole surface — checkboxes, bulk
card, upload and Danger Zone — now renders **until** `archived`, and the
routes accept until then too. `archived` is the one state where both
still stop. What was an exception on *checkboxes only* became the page's
rule.

So the `FROZEN` parametrizations below cover the three pages that still
freeze at `is_editable`; Observers has its own section at the foot,
which asserts the opposite in the same shape.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Observer,
    Relationship,
    Reviewee,
    Reviewer,
    ReviewSession,
)

EDITABLE = ("draft", "validated")
FROZEN = ("ready", "expired", "archived")
ALL_STATUSES = EDITABLE + FROZEN
# The three pages that still freeze at `is_editable` — see the module
# docstring for why Observers is not among them. Was `CHECKBOX_PAGES`,
# from when the divergence was checkboxes only; it is now every surface
# on the page, so the name says what the tuple is for rather than which
# control first diverged. (The rename was done with a blanket
# search-and-replace, which rewrote this comment into saying the name
# changed from `FROZEN_PAGES` to `FROZEN_PAGES` — caught by a cold
# read.) `ALL_PAGES` below still carries all four.
FROZEN_PAGES = ("reviewers", "reviewees", "relationships")
ALL_PAGES = FROZEN_PAGES + ("observers",)
# Observers still freezes here, and only here.
OBSERVERS_FROZEN = ("archived",)
OBSERVERS_LIVE = ("draft", "validated", "ready", "expired")

SELECT_CLASS = {
    "reviewers": "reviewer-select",
    "reviewees": "reviewee-select",
    "relationships": "relationship-select",
    "observers": "observer-select",
}


def _session(client: TestClient, db: Session, *, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "S", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    s = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    s.relationships_enabled = True
    s.observers_enabled = True
    reviewer = Reviewer(session_id=s.id, name="R", email="r@example.edu")
    reviewee = Reviewee(
        session_id=s.id, name="E", email_or_identifier="e@example.edu"
    )
    db.add_all([reviewer, reviewee])
    db.add(Observer(session_id=s.id, email="o@example.edu", display_name="O"))
    db.flush()
    db.add(
        Relationship(
            session_id=s.id, reviewer_id=reviewer.id, reviewee_id=reviewee.id
        )
    )
    db.commit()
    return s


def _render(client: TestClient, s: ReviewSession, page: str) -> str:
    r = client.get(f"/operator/sessions/{s.id}/{page}")
    assert r.status_code == 200, (page, s.status, r.status_code)
    return r.text


@pytest.mark.parametrize("page", FROZEN_PAGES)
@pytest.mark.parametrize("status", EDITABLE)
def test_the_selection_surface_renders_while_editable(
    db: Session, client: TestClient, page: str, status: str
) -> None:
    s = _session(client, db, code=f"sl-on-{page}-{status}")
    s.status = status
    db.commit()

    body = _render(client, s, page)

    assert f'class="{SELECT_CLASS[page]}"' in body, "row checkboxes"
    assert f'id="{page}-bulk-form"' in body, "the form they post to"

    # The controls live in the row expander, which is BUILT IN JS against
    # the selected rows — so they are not in the response as markup at
    # all, and a substring assertion on their attributes reads the
    # builder's string literals rather than rendered HTML. What is
    # checkable here is that the builder ships and is reachable; the
    # controls themselves are pinned against the builder in
    # `test_reviewers_roster_card_scaffold.py` and
    # `test_roster_expander.py`.
    #
    # **All three pages, not just Reviewers**: 19P.3 rung 3 took the last
    # two. This branch was `if page == "reviewers": ... return` with the
    # card-era ids below it, and leaving that shape would have left two
    # parametrizations asserting ids that no longer exist in any state —
    # which is the vacuity a cold read caught here once already.
    assert f'tr.id = "{page}-row-expander"' in body, "the builder"
    assert "/bulk-delete" in body, "Delete's route"
    assert "data-delete-confirm" in body, "the delete gate"


@pytest.mark.parametrize("page", FROZEN_PAGES)
@pytest.mark.parametrize("status", FROZEN)
def test_the_selection_surface_is_gone_once_the_session_is_frozen(
    db: Session, client: TestClient, page: str, status: str
) -> None:
    """`ready` is open for responses; `expired` and `archived` are over.
    None of the three can accept a roster mutation, so none of them
    offers one."""
    s = _session(client, db, code=f"sl-off-{page}-{status}")
    s.status = status
    db.commit()

    body = _render(client, s, page)

    assert f'class="{SELECT_CLASS[page]}"' not in body, "no row checkboxes"
    assert f'id="{page}-bulk-form"' not in body, "no bulk form"

    # The card-era ids stopped existing in EVERY state — Reviewers at
    # 19P.1 rung 2b, these two at 19P.3 rung 3 — so asserting their
    # absence here can no longer fail. A cold read caught that vacuity on
    # the Reviewers branch; the same fix now covers all three, rather
    # than leaving two pages asserting nothing until someone notices.
    #
    # Needles are the expander's OWN: the roster lock card also carries a
    # `data-delete-confirm` and it renders when frozen, so a bare
    # attribute check would fail on an unrelated gate.
    assert f'tr.id = "{page}-row-expander"' not in body, "no builder"
    assert f"{page}-bulk-delete" not in body, "no delete gate"
    assert "/bulk-delete" not in body, "no route to delete with"


@pytest.mark.parametrize("page", FROZEN_PAGES)
@pytest.mark.parametrize("status", FROZEN)
def test_reading_the_roster_still_works_when_frozen(
    db: Session, client: TestClient, page: str, status: str
) -> None:
    """The filter strip is read-only and stays. Hiding it would make a
    completed session's roster unsearchable for no safety gain."""
    s = _session(client, db, code=f"sl-read-{page}-{status}")
    s.status = status
    db.commit()

    body = _render(client, s, page)

    assert '<select name="status">' in body, "the status filter"
    assert ">Search</button>" in body, "the search submit"


@pytest.mark.parametrize("status", OBSERVERS_FROZEN)
def test_the_whole_observers_surface_goes_on_archived(
    db: Session, client: TestClient, status: str
) -> None:
    """What is left of the old gate, and the UPPER bound of the new one.

    The re-aiming that widened this gate dropped Observers from
    `test_the_upload_and_danger_zone_cards_go_when_frozen`, and its
    first replacement checked only the two bulk ids — so loosening
    `.bottom-grid` to render Upload and Danger Zone on `archived`, over
    routes that 409, passed the whole suite. Mutation-verified.

    Re-tightening probes a widened gate's lower bound; nothing probed
    the upper. Every control the sibling test above asserts PRESENT on
    a live session is asserted absent here, so the pair brackets it —
    including, since rung 4, the expander builder rather than the
    server-rendered buttons it replaced. A cold read caught that claim
    standing while the assertion behind it had gone vacuous.
    """
    s = _session(client, db, code=f"sl-obs-{status}")
    s.status = status
    db.commit()

    body = _render(client, s, "observers")

    assert 'id="observers-delete-btn"' not in body
    assert 'id="observers-bulk-form"' not in body
    # 19P.2 rung 4 moved the row actions into an injected panel, so the
    # `observers-delete-btn` line above can no longer fail on ANY state
    # — it is not server-rendered anywhere. What brackets the live
    # sibling now is the builder's absence, which is what this asserts.
    assert "observers-row-expander" not in body, (
        "archived ships the expander builder over routes that 409"
    )
    assert '<input type="checkbox" class="observer-select"' not in body
    assert 'class="card danger-zone"' not in body
    assert "/observers/delete-all" not in body
    assert "/observers/import" not in body


@pytest.mark.parametrize("status", ("ready", "expired"))
def test_observers_keep_their_checkboxes_for_the_cohort_editor(
    db: Session, client: TestClient, status: str
) -> None:
    """The one deliberate exception. Observers' checkboxes drive the
    cohort rule editor, which is gated on `not archived` on purpose so
    it stays live mid-session — narrowing them to `is_editable` would
    break that surface to fix a different one."""
    s = _session(client, db, code=f"sl-cohort-{status}")
    s.status = status
    db.commit()

    body = _render(client, s, "observers")

    # Pinned on the checkbox markup, not the bare class name: that name
    # also appears in the page's own `querySelectorAll(".observer-select")`,
    # which renders whatever the gate says — the 19H.1 trap, and a mutant
    # narrowing this gate walked straight through the looser assertion.
    assert '<input type="checkbox" class="observer-select"' in body, (
        "checkboxes stay for the rule editor"
    )


@pytest.mark.parametrize("page", FROZEN_PAGES)
@pytest.mark.parametrize("status", FROZEN)
def test_the_route_still_refuses_even_though_the_page_no_longer_asks(
    db: Session, client: TestClient, page: str, status: str
) -> None:
    """The page is not the gate. Hiding a control is a courtesy; the
    409 is the guarantee, and it is unchanged."""
    s = _session(client, db, code=f"sl-post-{page}-{status}")
    model = {
        "reviewers": Reviewer,
        "reviewees": Reviewee,
        "observers": Observer,
        "relationships": Relationship,
    }[page]
    row_id = db.execute(
        select(model.id).where(model.session_id == s.id)
    ).scalars().first()
    s.status = status
    db.commit()

    field = {
        "reviewers": "reviewer_ids",
        "reviewees": "reviewee_ids",
        "observers": "observer_ids",
        "relationships": "relationship_ids",
    }[page]
    response = client.post(
        f"/operator/sessions/{s.id}/{page}/bulk-delete",
        data={field: [row_id], "confirm": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 409, response.status_code
    assert db.get(model, row_id) is not None


# ── Upload + Danger Zone ───────────────────────────────────────────────


@pytest.mark.parametrize("page", ALL_PAGES)
@pytest.mark.parametrize("status", EDITABLE)
def test_the_upload_and_danger_zone_cards_render_while_editable(
    db: Session, client: TestClient, page: str, status: str
) -> None:
    s = _session(client, db, code=f"dz-on-{page}-{status}")
    s.status = status
    db.commit()

    body = _render(client, s, page)

    # Reviewers moved its Danger Zone into the Unlock panel at 19P.1
    # rung 3b, so it has no `.danger-zone` card. Asserted by its own
    # marker rather than skipped: what this test is about is that the
    # control is OFFERED while the session is editable, and that claim
    # holds on all four pages — only its home differs.
    if page == "reviewers":
        # The card kept its `danger-zone` class when it moved into the
        # panel — that class is the only reach for the amber warning
        # framing — so what distinguishes the new home is the heading
        # id, not the class. WHERE it renders is pinned, with the
        # panel-scoping that needs, in
        # `test_reviewers_roster_card_scaffold.py`; what this test
        # claims is only that the control is offered while editable.
        assert 'aria-labelledby="reviewers-danger-h"' in body, (
            "Reviewers offers no delete-all while editable"
        )
    else:
        assert 'class="card danger-zone"' in body
    assert f"/{page}/delete-all" in body


@pytest.mark.parametrize("page", FROZEN_PAGES)
@pytest.mark.parametrize("status", FROZEN)
def test_the_upload_and_danger_zone_cards_go_when_frozen(
    db: Session, client: TestClient, page: str, status: str
) -> None:
    """The author's rule for rows is a rule about editing, and an
    import and a delete-all are edits. Both 409'd on `expired` and
    `archived` while still rendering — the same defect the row
    selection had, one card down the page."""
    s = _session(client, db, code=f"dz-off-{page}-{status}")
    s.status = status
    db.commit()

    body = _render(client, s, page)

    assert 'class="card danger-zone"' not in body
    assert f"/{page}/delete-all" not in body
    assert f"/{page}/import" not in body


@pytest.mark.parametrize("page", FROZEN_PAGES)
@pytest.mark.parametrize("status", FROZEN)
def test_delete_all_still_refuses_when_frozen(
    db: Session, client: TestClient, page: str, status: str
) -> None:
    """Again: the page is a courtesy, the 409 is the guarantee."""
    s = _session(client, db, code=f"dz-post-{page}-{status}")
    s.status = status
    db.commit()

    response = client.post(
        f"/operator/sessions/{s.id}/{page}/delete-all",
        data={"confirm": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 409, response.status_code


# ── Observers, the divergence — 19P.2 rung 2 ──────────────────────────
#
# The same claims as above, inverted, in the same shape. Every mutating
# observers route moved from `_require_editable` to
# `_require_not_archived`; the page's gates moved with them, so the page
# and the route still agree by construction — at a different predicate.


#: Every mutating observers route, as (suffix, form data). Seven, which
#: is two more than the segment plan's ladder enumerated: `bulk-delete`
#: was an enumeration slip (rung 4 moves `Delete` into the expander, so
#: it was always inside "the whole expander takes the looser gate"), and
#: `import` was a ruling — `session_observers.html` gates Upload and
#: Danger Zone with ONE `{% if %}`, so delete-all could not become
#: reachable on `ready` without the upload card rendering beside it, and
#: a rendered control the server 409s is the failure this rung removes.
#:
#: Parametrized per route on purpose: relaxing the template alone, or
#: six of the seven, must fail here rather than pass on a spot check.
_OBSERVER_MUTATORS = (
    ("create", {
        "email": "new@example.org", "display_name": "New",
        "tag_1": "", "status": "active",
    }),
    ("{id}/update", {
        "email": "o@example.edu", "display_name": "Renamed",
        "tag_1": "", "status": "active",
    }),
    ("bulk-inactivate", {"observer_ids": ["{id}"]}),
    ("bulk-reactivate", {"observer_ids": ["{id}"]}),
    ("bulk-delete", {"observer_ids": ["{id}"], "confirm": "true"}),
    ("cohort-rule", {
        "observer_ids": ["{id}"],
        "cohort_combinator": "AND",
        "cohort_rule_field": "reviewer.tag1",
        "cohort_rule_op": "IS",
        "cohort_rule_operand_tag": "observer.tag1",
        "cohort_rule_operand_value": "blue",
    }),
    ("delete-all", {"confirm": "true"}),
)


def _post_mutator(client, s, row_id, suffix, data):
    payload = {
        k: ([row_id] if v == ["{id}"] else v) for k, v in data.items()
    }
    return client.post(
        f"/operator/sessions/{s.id}/observers/"
        + suffix.format(id=row_id),
        data=payload,
        follow_redirects=False,
    )


@pytest.mark.parametrize("suffix,data", _OBSERVER_MUTATORS)
@pytest.mark.parametrize("status", ("ready", "expired"))
def test_every_observers_mutator_accepts_where_it_used_to_409(
    db: Session, client: TestClient, status: str, suffix: str, data: dict
) -> None:
    """The rung, stated as the thing an operator can now do.

    `== 303`, not `!= 409`. The first draft asserted the weaker form on
    the reasoning that "a route that started 400ing for an unrelated
    reason would be a different bug" — which was wrong on this page: a
    400 from `create` / `update` IS the route's own error-render path,
    and a cold read found that path broken on `ready` while this test
    stayed green. A redirect is what acceptance looks like here, so it
    is what is asserted.
    """
    s = _session(client, db, code=f"ob-relax-{status[:3]}-{suffix[:6]}")
    row_id = db.execute(
        select(Observer.id).where(Observer.session_id == s.id)
    ).scalars().one()
    s.status = status
    db.commit()

    response = _post_mutator(client, s, row_id, suffix, data)

    assert response.status_code == 303, (
        f"{suffix} did not accept on {status}: "
        f"{response.status_code} {response.text[:200]}"
    )


@pytest.mark.parametrize("suffix,data", _OBSERVER_MUTATORS)
def test_every_observers_mutator_still_refuses_on_archived(
    db: Session, client: TestClient, suffix: str, data: dict
) -> None:
    """The half the relaxation must not take with it. `archived` is
    the hard stop, and it is the only one left."""
    s = _session(client, db, code=f"ob-arch-{suffix[:8]}")
    row_id = db.execute(
        select(Observer.id).where(Observer.session_id == s.id)
    ).scalars().one()
    s.status = "archived"
    db.commit()

    response = _post_mutator(client, s, row_id, suffix, data)

    assert response.status_code == 409, (
        f"{suffix} accepted on archived: {response.status_code}"
    )
    assert db.get(Observer, row_id) is not None


@pytest.mark.parametrize("status", ("ready", "expired"))
def test_the_observers_import_accepts_mid_session(
    db: Session, client: TestClient, status: str
) -> None:
    """The seventh route, and the one the ladder did not name.

    Separated from the parametrized set because it posts a file rather
    than a form, not because it is a different claim.
    """
    s = _session(client, db, code=f"ob-imp-{status[:4]}")
    s.status = status
    db.commit()

    response = client.post(
        f"/operator/sessions/{s.id}/observers/import",
        files={"file": (
            "o.csv",
            b"ObserverEmail,ObserverName\nnew@example.org,New\n",
            "text/csv",
        )},
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 303, response.status_code
    assert db.execute(
        select(Observer).where(
            Observer.session_id == s.id,
            Observer.email == "new@example.org",
        )
    ).scalar_one_or_none() is not None


def test_the_observers_import_still_refuses_on_archived(
    db: Session, client: TestClient
) -> None:
    s = _session(client, db, code="ob-imp-arch")
    s.status = "archived"
    db.commit()

    response = client.post(
        f"/operator/sessions/{s.id}/observers/import",
        files={"file": (
            "o.csv", b"ObserverEmail\nnew@example.org\n", "text/csv",
        )},
        data={"confirm_replace": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 409, response.status_code


@pytest.mark.parametrize("status", OBSERVERS_LIVE)
def test_the_whole_observers_surface_renders_wherever_the_routes_accept(
    db: Session, client: TestClient, status: str
) -> None:
    """Page and route agree by construction — the property 19I.3 was
    written to establish, re-established at the new predicate.

    Every control here has a route in `_OBSERVER_MUTATORS` above, so a
    template relaxed further than the routes fails the route tests and
    a template relaxed less fails this one.
    """
    s = _session(client, db, code=f"ob-surface-{status[:4]}")
    s.status = status
    db.commit()

    body = _render(client, s, "observers")

    assert '<input type="checkbox" class="observer-select"' in body
    assert 'id="observers-bulk-form"' in body
    assert 'class="card danger-zone"' in body
    assert "/observers/delete-all" in body
    assert "/observers/import" in body
    # 19P.2 rung 4 moved the four row actions into a row expander the
    # script builds against the selection, so `observers-delete-btn` is
    # no longer in the response. What IS in the response is the script
    # that builds it — read as its own text, because `base.html` inlines
    # every page's JS and a page-wide substring check would pass on any
    # page in the app.
    panel = re.search(
        r"<script>(?:(?!</script>).)*?observers-row-expander.*?</script>",
        body, re.S,
    )
    assert panel, "no expander builder"
    assert "/bulk-delete" in panel.group(0)
    assert 'data-delete-btn="observers-bulk-delete"' in panel.group(0)


@pytest.mark.parametrize("status", OBSERVERS_LIVE)
def test_add_and_edit_actually_open_an_editor_wherever_they_render(
    db: Session, client: TestClient, status: str
) -> None:
    """A rendered control that does nothing is the failure this rung
    exists to remove, and the rung shipped two of them.

    `_render_observers_page` discarded `edit_id` / `add_mode` on
    `ready` — correct while `create` / `update` took
    `_require_editable`, since the page then could not save. Relaxing
    those routes and the buttons above them without this left `Add` and
    `Edit` rendering on `ready` and opening nothing.
    """
    s = _session(client, db, code=f"ob-editor-{status[:4]}")
    row_id = db.execute(
        select(Observer.id).where(Observer.session_id == s.id)
    ).scalars().one()
    s.status = status
    db.commit()
    base = f"/operator/sessions/{s.id}/observers"

    # The controls are reachable...
    listing = _render(client, s, "observers")
    assert "?add=1" in listing, "no Add link"
    # `Edit` is built by the expander since rung 4, so what the response
    # carries is the builder. Scoped to the script's own text.
    panel = re.search(
        r"<script>(?:(?!</script>).)*?observers-row-expander.*?</script>",
        listing, re.S,
    )
    assert panel and "exp-edit" in panel.group(0), "no Edit in the expander"

    # ...and both open a real editor. Scoped to the `<tr>`: `Add`'s own
    # href carries `#observers-row-editor`, so a bare substring check
    # on the id passes on a page with no add row at all.
    add_row = re.search(
        r'<tr\b[^>]*id="observers-row-editor"', client.get(f"{base}?add=1").text
    )
    assert add_row, f"Add opens no editor on {status}"

    edit_body = client.get(f"{base}?edit_id={row_id}").text
    edit_row = re.search(
        rf'<tr\b[^>]*id="observer-row-{row_id}"[^>]*>', edit_body, re.S
    )
    assert edit_row and "observer-edit-row" in edit_row.group(0), (
        f"Edit opens no editor on {status}"
    )


def test_archived_opens_no_editor_even_by_hand_crafted_url(
    db: Session, client: TestClient
) -> None:
    """The upper bound of the fix above.

    Deleting the suppression outright — rather than moving it from
    `is_ready` to `is_archived` — passes every other test here: the
    buttons are gone on `archived`, so nothing NAVIGATES to the editor.
    A typed `?add=1` still would, over routes that 409. Mutation
    survived until this was written.
    """
    s = _session(client, db, code="ob-arch-editor")
    row_id = db.execute(
        select(Observer.id).where(Observer.session_id == s.id)
    ).scalars().one()
    s.status = "archived"
    db.commit()
    base = f"/operator/sessions/{s.id}/observers"

    assert not re.search(
        r'<tr\b[^>]*id="observers-row-editor"', client.get(f"{base}?add=1").text
    ), "archived opens an add editor the routes refuse"

    edit_row = re.search(
        rf'<tr\b[^>]*id="observer-row-{row_id}"[^>]*>',
        client.get(f"{base}?edit_id={row_id}").text, re.S,
    )
    assert edit_row and "observer-edit-row" not in edit_row.group(0), (
        "archived opens an edit editor the routes refuse"
    )


@pytest.mark.parametrize("status", OBSERVERS_LIVE)
def test_a_rejected_save_comes_back_editable_wherever_it_can_save(
    db: Session, client: TestClient, status: str
) -> None:
    """The second face of the same defect, and the one that loses work.

    The error banner is scoped to `{% if edit_mode %}`, so dropping
    `add_mode` on the error-render path took the operator's typed
    values AND the reason with it: a mistyped email on `ready` answered
    400 with a bare roster page.
    """
    s = _session(client, db, code=f"ob-err-{status[:4]}")
    s.status = status
    db.commit()

    response = client.post(
        f"/operator/sessions/{s.id}/observers/create",
        data={
            # Duplicate of the row `_session` seeds — a guaranteed
            # rejection that is the service's, not the gate's.
            "email": "o@example.edu", "display_name": "Typo",
            "tag_1": "", "status": "active",
        },
        follow_redirects=False,
    )

    assert response.status_code == 400, response.status_code
    body = response.text
    assert 'id="observer-edit-form"' in body, (
        f"the rejected save lost its form on {status}"
    )
    assert "Typo" in body, "the operator's typed values were dropped"
    # The banner, read inside the edit-mode block it lives in rather
    # than page-wide — `base.html` inlines the whole app's CSS, so a
    # bare class-name check would pass on any page.
    assert re.search(r'id="observer-edit-form"', body)
    assert "already" in body.lower(), "no reason given for the rejection"


@pytest.mark.parametrize("status", ("ready", "expired"))
def test_the_lock_card_goes_where_the_roster_stays_live(
    db: Session, client: TestClient, status: str
) -> None:
    """The card explains why a page's controls are absent. They are not
    absent here any more, so a card reading "cannot be modified while
    the session is ongoing" would contradict the roster beneath it.

    `_roster_lock_card.html` took a `lock_when` parameter for this;
    the other three pages keep the default and are untouched.
    """
    s = _session(client, db, code=f"ob-lock-{status[:4]}")
    s.status = status
    db.commit()

    body = _render(client, s, "observers")

    assert '<div class="card lock">' not in body, (
        "the lock card contradicts the live roster under it"
    )
    assert "cannot be modified" not in body


def test_archived_still_says_why_the_observers_roster_is_frozen(
    db: Session, client: TestClient
) -> None:
    """The relaxation must not take the explanation with it."""
    s = _session(client, db, code="ob-lock-arch")
    s.status = "archived"
    db.commit()

    body = _render(client, s, "observers")

    assert '<div class="card lock">' in body
    assert "The observers cannot be modified because the session is archived" in body
