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


def _strip(body: str) -> tuple[str, str]:
    """The button row and the status row, as separate slices."""
    buttons_at = body.find('class="filter-actions"')
    confirm_at = body.find('class="filter-confirm"')
    assert buttons_at != -1, "no button row"
    assert confirm_at != -1, "no status row"
    assert buttons_at < confirm_at, "status row must follow the buttons"
    return (
        body[buttons_at:confirm_at],
        body[confirm_at : body.index("</form>", confirm_at)],
    )


@pytest.mark.parametrize("page", ROSTER_PAGES)
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


@pytest.mark.parametrize("page", ROSTER_PAGES)
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

    # Ordering: after Add, before Search.
    assert buttons.index(">Add</a>") < start < buttons.index(">Search</button>")


@pytest.mark.parametrize("page", ROSTER_PAGES)
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


@pytest.mark.parametrize("page", ROSTER_PAGES)
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
    assert gained == sorted(f"session_{p}.html" for p in ROSTER_PAGES)


def test_the_new_row_style_cannot_reach_the_other_pages() -> None:
    """The CSS is scoped under `.operator-actions-card` rather than
    added to `.filter-actions`, so the three non-roster users of that
    class cannot be reflowed by it."""
    base = (TEMPLATES.parent / "base.html").read_text()
    assert ".operator-actions-card .filter-confirm {" in base
    assert "\n      .filter-confirm {" not in base, "unscoped rule"
