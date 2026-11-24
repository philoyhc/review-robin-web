"""Segment 20P Item 1 rung 3a — the scale setting: a numeric response
field's ``scale`` flag and ``scale_labels``, saved by the instrument card,
kept in ``validation`` only while the field's shape is a scale's, drawn on
the reviewer surface over the number box."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import AuditEvent, InstrumentResponseField
from app.services.instruments._response_fields import (
    parse_scale_labels,
    scale_points,
    scale_shape_error,
    validation_block_from_inline,
)

from .test_instrument_builder_routes import (
    _activate,
    _generate_full_matrix,
    _instrument,
    _make_session,
    _new_model_with_tags,
    _populate_rosters,
)
from .test_response_field_branching_save import _rfs, _save
from .test_response_field_branching_surface import _controls


@pytest.mark.parametrize(
    ("data_type", "min_", "max_", "step", "error"),
    [
        ("Integer", 1, 5, 1, None),
        ("Decimal", 0, 1, 0.1, None),
        ("Decimal", 0, 10, 0.5, None),
        ("String", 1, 5, 1, "Only an Integer or a Decimal field can be a scale."),
        ("Integer", None, 5, 1, "A scale needs a Min and a Max."),
        ("Integer", 1, 5, None, "A scale needs a Step."),
        ("Integer", 5, 5, 1, "Max must be above Min."),
        ("Integer", 1, 5, 0.5, "Whole numbers only."),
        ("Decimal", 0, 1, 0.3, "Max must be Min plus a whole number of Steps."),
    ],
)
def test_the_scale_shape_rule(data_type, min_, max_, step, error) -> None:
    assert scale_shape_error(data_type, min_, max_, step) == error


def test_points_and_labels() -> None:
    assert scale_points(1, 5, 1) == 5
    assert scale_points(0, 1, 0.1) == 11
    assert parse_scale_labels("Poor||Excellent") == ["Poor", "", "Excellent"]
    assert parse_scale_labels(None) == ["", "", ""]
    assert parse_scale_labels("x" * 99)[0] == "x" * 60


def test_validation_carries_a_scale_only_while_its_shape_is_one() -> None:
    block = validation_block_from_inline("Integer", 1, 5, 1, None, True, "Poor|Fair|")
    assert block == {
        "min": 1,
        "max": 5,
        "step": 1,
        "scale": True,
        "scale_labels": ["Poor", "Fair", ""],
    }
    assert "scale" not in (validation_block_from_inline("Integer", 1, 5, None, None, True) or {})
    assert "scale" not in (validation_block_from_inline("Integer", 1, 5, 1, None) or {})


def _rating(db: Session, instrument) -> InstrumentResponseField:
    return next(f for f in instrument.response_fields if f.label == "Rating")


def test_the_card_saves_a_scale_and_audits_it(client: TestClient, db: Session) -> None:
    review_session, instrument = _new_model_with_tags(client, db, code="scale-save")
    reply = _save(
        client,
        review_session,
        instrument,
        _rfs(
            instrument,
            Rating={
                "min": "1",
                "max": "5",
                "step": "1",
                "scale": True,
                "scale_labels": "Low||High",
            },
        ),
    )
    assert reply.status_code in (200, 303), reply.text
    db.expire_all()
    rating = _rating(db, instrument)
    assert rating.scale and rating.scale_labels == "Low||High"
    assert rating.validation and rating.validation["scale"] is True
    assert rating.validation["scale_labels"] == ["Low", "", "High"]
    events = db.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "instrument.response_fields_saved")
    ).all()
    (updated,) = [u for e in events for u in (e.detail or {})["set_changes"]["updated"]]
    assert updated["field_key"] == "rating"
    assert updated["changes"]["scale"] == [False, True]
    assert updated["changes"]["scale_labels"] == [None, "Low||High"]


def test_an_integer_scale_with_no_step_takes_one(client: TestClient, db: Session) -> None:
    review_session, instrument = _new_model_with_tags(client, db, code="scale-step")
    reply = _save(
        client,
        review_session,
        instrument,
        _rfs(instrument, Rating={"min": "1", "max": "5", "step": "", "scale": True}),
    )
    assert reply.status_code in (200, 303), reply.text
    db.expire_all()
    rating = _rating(db, instrument)
    assert rating._inline_step == 1 and rating.validation and rating.validation["scale"]


def test_a_scale_that_cannot_be_one_is_refused_by_name(client: TestClient, db: Session) -> None:
    review_session, instrument = _new_model_with_tags(client, db, code="scale-bad")
    reply = _save(
        client,
        review_session,
        instrument,
        _rfs(instrument, Rating={"min": "", "max": "5", "step": "1", "scale": True}),
    )
    assert reply.status_code == 422
    assert "A scale needs a Min and a Max." in reply.text
    db.expire_all()
    assert not _rating(db, instrument).scale


def test_a_string_field_never_saves_as_a_scale(client: TestClient, db: Session) -> None:
    review_session, instrument = _new_model_with_tags(client, db, code="scale-str")
    reply = _save(client, review_session, instrument, _rfs(instrument, Comments={"scale": True}))
    assert reply.status_code in (200, 303), reply.text
    db.expire_all()
    comments = next(f for f in instrument.response_fields if f.label == "Comments")
    assert not comments.scale


@pytest.fixture
def reviewer_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="r-oid", email="r@example.edu", name="R Reviewer", provider="aad"
    )


def test_the_reviewer_surface_marks_a_scale_for_the_script(
    db: Session,
    alice: AuthenticatedUser,
    reviewer_user: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    review_session = _make_session(operator, db, code="scale-surface")
    _populate_rosters(operator, review_session.id)
    _generate_full_matrix(operator, db, review_session.id)
    instrument = _instrument(db, review_session.id)
    rating = next(f for f in instrument.response_fields if f.field_key == "rating")
    rating._inline_min, rating._inline_max, rating._inline_step = 1, 5, 1
    rating.scale, rating.scale_labels = True, "Poor||Excellent"
    rating.validation = validation_block_from_inline(
        "Integer", 1, 5, 1, None, True, rating.scale_labels
    )
    db.flush()
    _activate(operator, db, review_session.id)
    body = make_client(reviewer_user).get(f"/me/sessions/{review_session.public_id}").text
    (control,) = _controls(body, "rating")[:1]
    assert "data-rs-scale" in control
    assert 'data-rs-scale-start="Poor"' in control and 'data-rs-scale-end="Excellent"' in control
    assert "data-rs-scale-middle" not in control
    assert "rrwScaleEnhance" in body  # the script is on the page
    # A field that is not a scale stays the plain box.
    assert all("data-rs-scale" not in c for c in _controls(body, "comments"))
