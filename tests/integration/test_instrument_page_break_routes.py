"""Integration tests for Segment 18M PR 2a — page-break create /
delete routes + per-instrument-card UI surface.

Service-layer invariants are covered by
`test_instrument_reorder_and_breaks.py`. These tests cover the
HTTP surface (lifecycle gating, 409 mapping, redirect targets)
and the template rendering (page-break card between instruments,
+Page break button disabled-state computation, × delete button).
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, ReviewSession


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": f"Session {code}", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _add_instruments(client: TestClient, session_id: int, n: int) -> None:
    for _ in range(n):
        response = client.post(
            f"/operator/sessions/{session_id}/instruments/add-new-model",
            follow_redirects=False,
        )
        assert response.status_code == 303


def _ordered(db: Session, session_id: int) -> list[Instrument]:
    return list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == session_id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars().all()
    )


# --------------------------------------------------------------------------- #
# /page-break/create
# --------------------------------------------------------------------------- #


def test_page_break_create_sets_flag_on_successor(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="pbc-1")
    _add_instruments(client, review_session.id, 1)
    a, b = _ordered(db, review_session.id)

    response = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{a.id}/page-break/create",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(f"#instrument-{a.id}")
    db.refresh(b)
    assert b.starts_new_page is True


def test_page_break_create_409_on_last_instrument(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="pbc-2")
    _add_instruments(client, review_session.id, 1)
    _a, b = _ordered(db, review_session.id)

    response = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{b.id}/page-break/create",
        follow_redirects=False,
    )
    assert response.status_code == 409


def test_page_break_create_409_when_already_set(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="pbc-3")
    _add_instruments(client, review_session.id, 1)
    a, _b = _ordered(db, review_session.id)

    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{a.id}/page-break/create"
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{a.id}/page-break/create",
        follow_redirects=False,
    )
    assert response.status_code == 409


def test_page_break_create_404_for_other_session(
    client: TestClient, db: Session
) -> None:
    a_session = _make_session(client, db, code="pbc-4a")
    _add_instruments(client, a_session.id, 1)
    b_session = _make_session(client, db, code="pbc-4b")
    _add_instruments(client, b_session.id, 1)
    a_inst, _ = _ordered(db, a_session.id)

    response = client.post(
        f"/operator/sessions/{b_session.id}"
        f"/instruments/{a_inst.id}/page-break/create",
        follow_redirects=False,
    )
    assert response.status_code == 404


# --------------------------------------------------------------------------- #
# /page-break/delete
# --------------------------------------------------------------------------- #


def test_page_break_delete_clears_flag(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="pbd-1")
    _add_instruments(client, review_session.id, 1)
    a, b = _ordered(db, review_session.id)
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{a.id}/page-break/create"
    )
    db.refresh(b)
    assert b.starts_new_page is True

    response = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{b.id}/page-break/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(b)
    assert b.starts_new_page is False


def test_page_break_delete_409_when_no_break(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="pbd-2")
    _add_instruments(client, review_session.id, 1)
    _a, b = _ordered(db, review_session.id)

    response = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{b.id}/page-break/delete",
        follow_redirects=False,
    )
    assert response.status_code == 409


# --------------------------------------------------------------------------- #
# Template rendering
# --------------------------------------------------------------------------- #


def test_page_break_card_renders_between_instruments(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ui-1")
    _add_instruments(client, review_session.id, 1)
    a, _b = _ordered(db, review_session.id)
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{a.id}/page-break/create"
    )

    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    assert 'class="page-break-card"' in body
    assert ">Page break</span>" in body
    assert 'data-instrument-page-break-delete' in body


def test_page_break_card_does_not_render_when_no_flag(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ui-2")
    _add_instruments(client, review_session.id, 1)
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    assert 'class="page-break-card"' not in body


def test_add_page_break_button_renders_enabled_in_normal_case(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ui-3")
    _add_instruments(client, review_session.id, 1)
    a, _b = _ordered(db, review_session.id)
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    # The +Page break button on instrument A (not last, no break
    # after) renders enabled. Locate via the data attribute.
    assert f'data-instrument-page-break-add="{a.id}"' in body
    needle = (
        f'data-instrument-page-break-add="{a.id}"\n'
        f'                  disabled'
    )
    assert needle not in body


def test_add_page_break_button_disabled_on_last_instrument(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ui-4")
    _add_instruments(client, review_session.id, 1)
    _a, b = _ordered(db, review_session.id)
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    # Find the +Page break button on B (the last instrument). It
    # must have a `disabled` attribute and a tooltip explaining
    # the trailing-break invariant.
    idx = body.find(f'data-instrument-page-break-add="{b.id}"')
    assert idx != -1
    # Look in a small window after the data-attribute.
    window = body[idx:idx + 300]
    assert "disabled" in window
    assert "trail" in window.lower()


def test_add_page_break_button_disabled_when_successor_already_flagged(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ui-5")
    _add_instruments(client, review_session.id, 2)
    a, _b, _c = _ordered(db, review_session.id)
    # Create a break between a and b. Now +Page break on a must
    # show as disabled (successor b already carries a break).
    client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{a.id}/page-break/create"
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    idx = body.find(f'data-instrument-page-break-add="{a.id}"')
    assert idx != -1
    window = body[idx:idx + 300]
    assert "disabled" in window
    assert "already exists" in window.lower()


# --------------------------------------------------------------------------- #
# AJAX delete intercept (preserves collapse state)
# --------------------------------------------------------------------------- #


def test_page_break_delete_ajax_handler_renders(
    client: TestClient, db: Session
) -> None:
    """The × delete on a page-break card POSTs via fetch (not a
    full form submit) so other instrument cards' expand state is
    preserved across the operation. Smoke-test that the inline JS
    handler is in the rendered page so a future template refactor
    doesn't silently drop it."""
    review_session = _make_session(client, db, code="ui-ajax")
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    assert "Segment 18M PR 2a — page-break × delete intercept" in body
    assert "data-instrument-page-break-delete" in body
    assert "fetch(form.action" in body
