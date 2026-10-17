"""Bad numbers and ids are refused rather than answering 500 (findings
R3, R4, R8, O4, O6, P4; ``guide/findings_2026-10-16_bugs.md``)."""

from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    InstrumentResponseField,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionOperator,
    User,
)
from app.schemas.responses import ResponseUpsert
from app.services import responses as responses_service
from app.services.extracts import data_shape_extract, entity_metadata_extract
from app.services.instruments import ensure_default_instrument
from app.services.responses._core import canonical_number
from app.services.text import MAX_SQL_INT, parse_id


def _seed(db: Session) -> tuple[User, Reviewer, ReviewSession, Assignment]:
    op = User(email="op-bad@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    review_session = ReviewSession(name="S", code="bad-input", created_by_user_id=op.id)
    db.add(review_session)
    db.flush()
    db.add(SessionOperator(session_id=review_session.id, user_id=op.id, role="owner"))
    instrument = ensure_default_instrument(db, review_session)
    reviewer = Reviewer(session_id=review_session.id, name="Rae", email="rae@example.edu")
    reviewee = Reviewee(
        session_id=review_session.id, name="Carol", email_or_identifier="carol@example.edu"
    )
    db.add_all([reviewer, reviewee])
    db.flush()
    assignment = Assignment(
        session_id=review_session.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        instrument_id=instrument.id,
    )
    db.add(assignment)
    db.flush()
    return op, reviewer, review_session, assignment


def _field(db: Session, assignment: Assignment, data_type: str) -> InstrumentResponseField:
    field = db.execute(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == assignment.instrument_id,
            InstrumentResponseField.field_key == "rating",
        )
    ).scalar_one()
    field._inline_data_type = data_type
    db.flush()
    return field


# --- R3: nan, inf and very large numbers ----------------------------------


@pytest.mark.parametrize("value", ["nan", "NaN", "inf", "-Infinity", "1e400"])
def test_a_decimal_refuses_non_finite_numbers(db: Session, value: str) -> None:
    _, _, _, assignment = _seed(db)
    field = _field(db, assignment, "Decimal")
    field._inline_min, field._inline_max, field._inline_step = None, None, 0.5

    assert responses_service.validate_value(field, value) == "Must be a number."


def test_a_stepped_integer_refuses_a_number_past_a_float(db: Session) -> None:
    _, _, _, assignment = _seed(db)
    field = _field(db, assignment, "Integer")
    field._inline_min, field._inline_max, field._inline_step = None, None, 1.0

    assert responses_service.validate_value(field, "9" * 400) == "Must be a whole number."


def test_the_extracts_skip_a_stored_non_finite_value() -> None:
    field = InstrumentResponseField(_inline_data_type="Decimal")
    for acc, ingest in (
        (data_shape_extract._Acc(), data_shape_extract._ingest),
        (entity_metadata_extract._FieldAcc(), entity_metadata_extract._ingest_value),
    ):
        ingest(acc, field, "nan")
        assert acc.numeric_values == []
        assert acc.other_count == 1


# --- R4: non-canonical numbers ---------------------------------------------


@pytest.mark.parametrize(
    ("data_type", "value", "stored"),
    [
        ("Integer", "04", "4"),
        ("Integer", "+4", "4"),
        ("Integer", "-0", "0"),
        ("Decimal", "2.0", "2"),
        ("Decimal", "+2.50", "2.5"),
        ("Decimal", ".5", "0.5"),
        ("Decimal", "1e-7", "0.0000001"),
    ],
)
def test_a_number_is_canonical(data_type: str, value: str, stored: str) -> None:
    assert canonical_number(data_type, value) == stored


@pytest.mark.parametrize("value", ["0_5", "４", "²", "0x10", "1.5", " "])
def test_an_integer_refuses_what_is_not_plain_digits(value: str) -> None:
    assert canonical_number("Integer", value) is None


def test_a_saved_number_is_stored_canonical(db: Session) -> None:
    op, reviewer, review_session, assignment = _seed(db)
    _field(db, assignment, "Integer")

    responses_service.save_draft(
        db,
        review_session=review_session,
        reviewer=reviewer,
        user=op,
        upserts=[ResponseUpsert(assignment_id=assignment.id, field_key="rating", value="04")],
        correlation_id="corr",
    )

    stored = db.execute(
        select(Response.value).where(Response.assignment_id == assignment.id)
    ).scalar_one()
    assert stored == "4"


# --- R8, P4, O6: ids --------------------------------------------------------


def test_a_form_key_with_an_id_past_a_64_bit_column_is_ignored() -> None:
    upserts = responses_service.parse_form_payload(
        {"response[99999999999999999999][rating]": "3", "response[7][rating]": "4"}
    )

    assert [(u.assignment_id, u.value) for u in upserts] == [(7, "4")]


@pytest.mark.parametrize(
    ("raw", "parsed"),
    [("12", 12), (" 7 ", 7), (3, 3), ("²", None), ("١٢", None), ("-1", None),
     (str(MAX_SQL_INT + 1), None), (True, None), ("", None)],
)
def test_parse_id(raw: object, parsed: int | None) -> None:
    assert parse_id(raw) == parsed


@pytest.mark.parametrize(
    "url",
    [
        "/operator/sessions/99999999999999999999",
        "/operator/sessions/99999999999999999999/reviewees",
        "/operator/sessions?edit_id=99999999999999999999",
    ],
)
def test_an_oversized_id_answers_404(client: TestClient, url: str) -> None:
    assert client.get(url, follow_redirects=False).status_code == 404


def test_a_long_run_of_digits_in_a_search_is_not_an_id(client: TestClient) -> None:
    assert client.get("/operator/sessions?q=99999999999999999999").status_code == 200


# --- O4: the SMTP port -------------------------------------------------------


@pytest.mark.parametrize("port", ["0", "-1", "65536", "²", "99999999999999999999"])
def test_an_out_of_range_smtp_port_is_refused(client: TestClient, port: str) -> None:
    response = client.post(
        "/operator/settings",
        data={"smtp_host": "smtp.example.edu", "smtp_port": port},
        follow_redirects=False,
    )

    assert response.status_code == 422


def test_math_isfinite_guard_is_what_refuses_nan() -> None:
    # The pattern alone would refuse "nan"; ``1e400`` is what reaches the
    # finiteness check, since it is a plain decimal that overflows.
    assert math.isinf(float("1e400"))
    assert canonical_number("Decimal", "1e400") is None
