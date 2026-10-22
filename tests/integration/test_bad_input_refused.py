"""Bad numbers and ids are refused rather than answering 500 (findings
R3, R4, R8, O4, O6, P4; ``guide/findings_2026-10-16_bugs.md``)."""

from __future__ import annotations


import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
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
    # Reviewer writes take the session's accepting gate (findings L3).
    review_session.status = "ready"
    db.flush()

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
    # Since 19V Item 2 a key names a row by its ordinal on the page, not
    # an id, so no key reaches a column at all: an ordinal the page
    # doesn't have, however large, is ignored, and the largest 64-bit id
    # is still reachable by its ordinal.
    upserts = responses_service.parse_form_payload(
        {
            "response[99999999999999999999][rating]": "3",
            f"response[{MAX_SQL_INT + 1}][rating]": "2",
            f"response[{MAX_SQL_INT}][rating]": "5",
            "response[0][rating]": "1",
            "response[3][rating]": "6",
            "response[1][rating]": "4",
            "response[2][rating]": "8",
        },
        page_assignment_ids=[7, MAX_SQL_INT],
    )

    assert [(u.assignment_id, u.value) for u in upserts] == [(7, "4"), (MAX_SQL_INT, "8")]


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


# Findings 2026-10-22 P2: every route that takes an id list in its form
# body (`grep -rn "list\[int\] = Form" app/web`), `{sid}` the session's
# public id.
_FORM_ID_LIST_ROUTES = [
    *(
        (f"/operator/sessions/{action}", "session_ids")
        for action in (
            "bulk-tags", "bulk-unarchive", "bulk-delete-archived", "bulk-archive",
            "bulk-delete",
        )
    ),
    *(
        (f"/operator/sessions/{{sid}}/{roster}/{action}", f"{roster[:-1]}_ids")
        for roster in ("reviewers", "reviewees", "observers", "relationships")
        for action in ("bulk-inactivate", "bulk-reactivate", "bulk-delete")
    ),
    ("/operator/sessions/{sid}/assignments/bulk-inactivate", "assignment_ids"),
    ("/operator/sessions/{sid}/assignments/bulk-activate", "assignment_ids"),
    ("/operator/sys-admin/users/bulk-demote", "user_ids"),
]


@pytest.fixture
def owned_session_id(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> str:
    """A session alice owns, with relationships and observers on, and
    alice a sys-admin, so every route above reaches its own handler."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": "oversized-form"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "oversized-form")
    ).scalar_one()
    review_session.relationships_enabled = True
    review_session.observers_enabled = True
    db.commit()
    return review_session.public_id


@pytest.mark.parametrize(("path", "field"), _FORM_ID_LIST_ROUTES)
def test_an_oversized_id_in_a_form_body_answers_404(
    client: TestClient, owned_session_id: str, path: str, field: str
) -> None:
    url = path.format(sid=owned_session_id)

    def post(row_id: int) -> int:
        return client.post(
            url, data={field: [str(row_id)]}, follow_redirects=False
        ).status_code

    # The largest 64-bit id still binds; one past it was SQLite's 500.
    # (The Accounts route's own answer to an unknown id is a 404 too.)
    assert post(MAX_SQL_INT) < 500
    assert post(MAX_SQL_INT + 1) == 404


@pytest.mark.parametrize(
    "cursor",
    # The last is past Python's 4,300-digit int limit (Codex on #3236).
    [str(MAX_SQL_INT + 1), "99999999999999999999", "9" * 5000],
)
def test_an_oversized_audit_log_cursor_answers_404(
    client: TestClient, owned_session_id: str, cursor: str
) -> None:
    url = f"/operator/sys-admin/sessions/{owned_session_id}/audit-log"

    assert client.get(f"{url}?cursor={MAX_SQL_INT}").status_code == 200
    assert client.get(f"{url}?cursor={cursor}").status_code == 404


def test_a_route_without_a_form_body_is_not_made_to_read_one(
    client: TestClient,
) -> None:
    """An oversized id in a body the route does not declare is never
    read, so it cannot refuse the request."""
    response = client.request(
        "GET",
        "/operator/sessions",
        content=f"session_ids={MAX_SQL_INT + 1}",
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == 200


# --- O4: the SMTP port -------------------------------------------------------


@pytest.mark.parametrize("port", ["0", "-1", "65536", "²", "99999999999999999999"])
def test_an_out_of_range_smtp_port_is_refused(client: TestClient, port: str) -> None:
    response = client.post(
        "/operator/settings",
        data={"smtp_host": "smtp.example.edu", "smtp_port": port},
        follow_redirects=False,
    )

    assert response.status_code == 422


def test_a_plain_decimal_past_a_float_is_refused() -> None:
    # The pattern takes ``1e400``; the finiteness check is what refuses it.
    assert canonical_number("Decimal", "1e400") is None


@pytest.mark.parametrize(
    ("data_type", "value", "step"),
    [("Decimal", "1e308", 0.5), ("Decimal", "1.5e308", 0.25), ("Integer", "9" * 308, 0.5)],
)
def test_a_finite_number_whose_step_offset_overflows_is_refused(
    db: Session, data_type: str, value: str, step: float
) -> None:
    _, _, _, assignment = _seed(db)
    field = _field(db, assignment, data_type)
    field._inline_min, field._inline_max, field._inline_step = None, None, step

    assert responses_service.validate_value(field, value) is not None


def test_an_integer_longer_than_int_reads_is_refused(db: Session) -> None:
    _, _, _, assignment = _seed(db)
    field = _field(db, assignment, "Integer")
    field._inline_min, field._inline_max, field._inline_step = None, None, None

    assert responses_service.validate_value(field, "9" * 5000) == "Must be a whole number."


@pytest.mark.parametrize(
    ("value", "stored"),
    [("1e23", "100000000000000000000000"), ("12345678901234567890", "12345678901234567890"),
     ("0.1000000000000000000001", "0.1000000000000000000001"), ("-0.0", "0"), ("100", "100")],
)
def test_a_decimal_keeps_its_typed_digits(value: str, stored: str) -> None:
    assert canonical_number("Decimal", value) == stored


@pytest.mark.parametrize(
    ("mn", "mx", "step", "typed"),
    [(0, 0.0001, 0.00001, "0.00002"), (1000000, 1000002, 0.5, "1000000.5"), (0, 1, 0.1, "0.3")],
)
def test_a_step_column_is_labelled_as_its_answers_are_stored(
    mn: float, mx: float, step: float, typed: str
) -> None:
    field = InstrumentResponseField(
        _inline_data_type="Decimal", _inline_min=mn, _inline_max=mx, _inline_step=step
    )

    assert canonical_number("Decimal", typed) in data_shape_extract.discrete_step_values(field)


def test_a_band2_response_field_id_in_unicode_digits_is_a_new_field(db: Session) -> None:
    """P4 at its call site: ``"²"`` once passed ``isdigit()`` and failed
    ``int()``; it now reads as no id, which is a new field."""
    from app.services import instruments as instruments_service

    op, _, _, assignment = _seed(db)
    instrument = assignment.instrument
    instruments_service.set_band2_state(
        db,
        instrument=instrument,
        state={
            "response_fields": [
                {"id": "²", "name": "Score", "data_type": "string"},
            ]
        },
        actor=op,
        acknowledged_drop=True,
    )

    names = set(
        db.execute(
            select(InstrumentResponseField.label).where(
                InstrumentResponseField.instrument_id == instrument.id
            )
        ).scalars()
    )
    assert "Score" in names


@pytest.mark.parametrize(
    ("text", "too_large"),
    [
        ("9" * 5000, True),
        ("0" * 5000 + "7", False),
        (str(MAX_SQL_INT), False),
        (str(MAX_SQL_INT + 1), True),
        ("+" + str(MAX_SQL_INT + 1), True),
        ("12a", False),
    ],
)
def test_too_large_reads_any_length_of_digits(text: str, too_large: bool) -> None:
    from app.web.oversized_ids import _too_large

    assert _too_large(text) is too_large
