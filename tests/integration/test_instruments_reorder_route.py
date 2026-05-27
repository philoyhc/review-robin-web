"""HTTP-level tests for Segment 18M PR 2b — the JSON drag-and-
drop reorder endpoint at `/operator/sessions/{sid}/instruments/order`.

The service-layer invariant coverage lives in
`test_instrument_reorder_and_breaks.py`. These tests focus on
the HTTP surface: body validation, status-code mapping for the
service's ValueErrors, the lifecycle gate, and the response shape
that the operator-UI drag JS depends on.
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
        client.post(
            f"/operator/sessions/{session_id}/instruments/add-new-model"
        )


def _ordered(db: Session, session_id: int) -> list[Instrument]:
    return list(
        db.execute(
            select(Instrument)
            .where(Instrument.session_id == session_id)
            .order_by(Instrument.order, Instrument.id)
        ).scalars().all()
    )


# --------------------------------------------------------------------------- #
# Happy paths
# --------------------------------------------------------------------------- #


def test_instruments_order_swap_returns_ok_and_persists(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ord-1")
    _add_instruments(client, review_session.id, 1)
    a, b = _ordered(db, review_session.id)

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/order",
        json={"items": [b.id, a.id]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body == {"ok": True, "order": [b.id, a.id], "breaks_at": []}
    db.refresh(a)
    db.refresh(b)
    assert (b.order, a.order) == (0, 1)


def test_instruments_order_adds_break_via_null_in_items(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ord-2")
    _add_instruments(client, review_session.id, 1)
    a, b = _ordered(db, review_session.id)

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/order",
        json={"items": [a.id, None, b.id]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["breaks_at"] == [b.id]
    db.refresh(b)
    assert b.starts_new_page is True


def test_instruments_order_no_op_returns_ok_with_current_state(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ord-3")
    _add_instruments(client, review_session.id, 1)
    a, b = _ordered(db, review_session.id)

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/order",
        json={"items": [a.id, b.id]},
    )
    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "order": [a.id, b.id],
        "breaks_at": [],
    }


# --------------------------------------------------------------------------- #
# Body validation (400)
# --------------------------------------------------------------------------- #


def test_instruments_order_400_on_non_json_body(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ord-4")
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/order",
        content=b"not json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400


def test_instruments_order_400_when_items_missing(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ord-5")
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/order",
        json={},
    )
    assert response.status_code == 400


def test_instruments_order_400_when_items_contains_non_int(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ord-6")
    _add_instruments(client, review_session.id, 1)
    a, _b = _ordered(db, review_session.id)
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/order",
        json={"items": [a.id, "bogus"]},
    )
    assert response.status_code == 400


def test_instruments_order_400_when_items_contains_bool(
    client: TestClient, db: Session
) -> None:
    """``isinstance(True, int)`` is True in Python; the endpoint
    must explicitly reject booleans so they aren't silently
    coerced into 0/1 ids."""
    review_session = _make_session(client, db, code="ord-7")
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/order",
        json={"items": [True, False]},
    )
    assert response.status_code == 400


# --------------------------------------------------------------------------- #
# Invariant rejections (409)
# --------------------------------------------------------------------------- #


def test_instruments_order_409_on_leading_break(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ord-8")
    _add_instruments(client, review_session.id, 1)
    a, b = _ordered(db, review_session.id)
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/order",
        json={"items": [None, a.id, b.id]},
    )
    assert response.status_code == 409, f"body: {response.text!r}"
    assert "before the first instrument" in response.text


def test_instruments_order_409_on_trailing_break(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ord-9")
    _add_instruments(client, review_session.id, 1)
    a, b = _ordered(db, review_session.id)
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/order",
        json={"items": [a.id, b.id, None]},
    )
    assert response.status_code == 409


def test_instruments_order_409_on_double_stack(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ord-10")
    _add_instruments(client, review_session.id, 1)
    a, b = _ordered(db, review_session.id)
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/order",
        json={"items": [a.id, None, None, b.id]},
    )
    assert response.status_code == 409


def test_instruments_order_409_on_missing_id(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ord-11")
    _add_instruments(client, review_session.id, 1)
    a, _b = _ordered(db, review_session.id)
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/order",
        json={"items": [a.id]},  # missing b
    )
    assert response.status_code == 409


def test_instruments_order_409_on_duplicate(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ord-12")
    _add_instruments(client, review_session.id, 1)
    a, _b = _ordered(db, review_session.id)
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/order",
        json={"items": [a.id, a.id]},
    )
    assert response.status_code == 409


def test_instruments_order_409_on_unknown_id(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ord-13")
    _add_instruments(client, review_session.id, 1)
    a, _b = _ordered(db, review_session.id)
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/order",
        json={"items": [a.id, 99_999]},
    )
    assert response.status_code == 409


# --------------------------------------------------------------------------- #
# Template-side smoke tests
# --------------------------------------------------------------------------- #


def test_drag_handle_is_draggable(client: TestClient, db: Session) -> None:
    """The grip-dots <span> carries draggable=\"true\" so HTML5
    drag-and-drop fires dragstart from it."""
    review_session = _make_session(client, db, code="dr-1")
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    needle = (
        '<span class="instrument-card-drag-handle"\n'
        '                data-instrument-drag-handle\n'
        '                draggable="true"'
    )
    assert needle in body


def test_drag_handler_iife_renders(client: TestClient, db: Session) -> None:
    """Smoke-test that the inline drag IIFE renders so a future
    template refactor doesn't silently drop it."""
    review_session = _make_session(client, db, code="dr-2")
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    assert "Segment 18M PR 2b — drag-and-drop instrument reorder" in body
    assert "/instruments/order" in body
    assert "instrument-reorder-toast" in body
