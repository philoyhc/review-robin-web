"""Reviewer summary HTML + CSV — per-response-field visibility.

The reviewer surface form filters Band 3 response fields by
``InstrumentResponseField.visible``; the operator toggles the
flag via the Band 2 pill chip (the paired
``data-source-type="response"`` pill). A field whose pill is
un-pinned must not appear on the reviewer surface, the reviewer
summary HTML page, or the reviewer-record CSV download.

Pins that the summary HTML and the CSV honour ``visible``:

* Hidden fields are absent from the summary column headers /
  cells and from the CSV preamble / data rows.
* Visible fields still render normally.
* Toggling visible False after responses are saved drops the
  column from both surfaces; the underlying ``Response`` row
  survives in the DB and rehydrates if visibility flips back.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import (
    Instrument,
    InstrumentResponseField,
    ReviewSession,
)
from app.main import app
from app.web.deps import get_current_user

from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


@pytest.fixture
def rae() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )


def _seed_session_with_rae_and_one_reviewee(
    operator_client: TestClient,
    db: Session,
    *,
    code: str,
    reviewer_email: str,
) -> ReviewSession:
    operator_client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    operator_client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                f"ReviewerName,ReviewerEmail\nRae,{reviewer_email}\n".encode(),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    operator_client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(operator_client, review_session.id)
    return review_session


def _activate(operator_client: TestClient, review_session: ReviewSession) -> None:
    operator_client.post(
        f"/operator/sessions/{review_session.id}/workflow/prepare",
        follow_redirects=False,
    )
    operator_client.post(
        f"/operator/sessions/{review_session.id}/workflow/activate",
        follow_redirects=False,
    )


def _submit(
    rae_client: TestClient, review_session: ReviewSession, db: Session
) -> None:
    from app.db.models import Assignment
    assignment_ids = [
        a.id
        for a in db.execute(
            select(Assignment).where(
                Assignment.session_id == review_session.id
            )
        ).scalars()
    ]
    data: dict[str, str] = {}
    for aid in assignment_ids:
        data[f"response[{aid}][rating]"] = "5"
        data[f"response[{aid}][comments]"] = "Carol did fine work"
    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/1/save",
        data=data,
        follow_redirects=False,
    )
    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        follow_redirects=False,
    )


def _hide_field(
    db: Session, review_session: ReviewSession, field_key: str
) -> None:
    """Mirror the Band 2 chip un-pin: flip
    ``InstrumentResponseField.visible`` to ``False`` directly on
    the (only) instrument's matching field."""
    instrument = db.execute(
        select(Instrument).where(
            Instrument.session_id == review_session.id
        )
    ).scalar_one()
    field = db.execute(
        select(InstrumentResponseField)
        .where(InstrumentResponseField.instrument_id == instrument.id)
        .where(InstrumentResponseField.field_key == field_key)
    ).scalar_one()
    field.visible = False
    db.commit()


def test_summary_html_hides_column_for_invisible_response_field(
    client: TestClient,
    db: Session,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """A response field flipped to ``visible=False`` after the
    reviewer submitted must drop its column from the summary
    HTML — same as the reviewer surface, which filters by
    ``visible`` already."""
    review_session = _seed_session_with_rae_and_one_reviewee(
        client, db, code="vis-html-hide", reviewer_email=rae.email
    )
    _activate(client, review_session)
    rae_client = make_client(rae)
    _submit(rae_client, review_session, db)

    _hide_field(db, review_session, "comments")

    app.dependency_overrides[get_current_user] = lambda: rae
    body = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/summary"
    ).text
    # Comments column dropped; its value not rendered.
    assert "Comments" not in body
    assert "Carol did fine work" not in body
    # Rating column still present.
    assert "Rating" in body


def test_summary_html_keeps_column_when_visible(
    client: TestClient,
    db: Session,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """Sanity check: with both default fields visible, both
    columns and the saved values render."""
    review_session = _seed_session_with_rae_and_one_reviewee(
        client, db, code="vis-html-keep", reviewer_email=rae.email
    )
    _activate(client, review_session)
    rae_client = make_client(rae)
    _submit(rae_client, review_session, db)

    app.dependency_overrides[get_current_user] = lambda: rae
    body = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/summary"
    ).text
    assert "Rating" in body
    assert "Comments" in body
    assert "Carol did fine work" in body


def test_summary_html_round_trips_when_visibility_toggles_back(
    client: TestClient,
    db: Session,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """Hiding a field doesn't delete its ``Response`` rows —
    flipping ``visible`` back to ``True`` should rehydrate the
    column with the original value."""
    review_session = _seed_session_with_rae_and_one_reviewee(
        client, db, code="vis-html-roundtrip", reviewer_email=rae.email
    )
    _activate(client, review_session)
    rae_client = make_client(rae)
    _submit(rae_client, review_session, db)

    _hide_field(db, review_session, "comments")
    app.dependency_overrides[get_current_user] = lambda: rae
    body_hidden = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/summary"
    ).text
    assert "Carol did fine work" not in body_hidden

    # Flip back to visible.
    instrument = db.execute(
        select(Instrument).where(
            Instrument.session_id == review_session.id
        )
    ).scalar_one()
    field = db.execute(
        select(InstrumentResponseField)
        .where(InstrumentResponseField.instrument_id == instrument.id)
        .where(InstrumentResponseField.field_key == "comments")
    ).scalar_one()
    field.visible = True
    db.commit()

    body_again = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/summary"
    ).text
    assert "Comments" in body_again
    assert "Carol did fine work" in body_again


def test_summary_csv_hides_column_for_invisible_response_field(
    client: TestClient,
    db: Session,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """The reviewer-record CSV mirrors the summary HTML — a
    hidden response field is absent from the preamble *and*
    from every data row."""
    review_session = _seed_session_with_rae_and_one_reviewee(
        client, db, code="vis-csv-hide", reviewer_email=rae.email
    )
    _activate(client, review_session)
    rae_client = make_client(rae)
    _submit(rae_client, review_session, db)

    _hide_field(db, review_session, "comments")

    app.dependency_overrides[get_current_user] = lambda: rae
    csv_resp = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/summary.csv"
    )
    assert csv_resp.status_code == 200
    body = csv_resp.text
    # Comments field_key absent from the preamble lines and the
    # data rows.
    assert "comments" not in body
    assert "Carol did fine work" not in body
    # Rating still present.
    assert "rating" in body


def test_summary_csv_keeps_column_when_visible(
    client: TestClient,
    db: Session,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """Sanity check: with both default fields visible, both
    field_keys + the saved comments value land in the CSV."""
    review_session = _seed_session_with_rae_and_one_reviewee(
        client, db, code="vis-csv-keep", reviewer_email=rae.email
    )
    _activate(client, review_session)
    rae_client = make_client(rae)
    _submit(rae_client, review_session, db)

    app.dependency_overrides[get_current_user] = lambda: rae
    csv_resp = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/summary.csv"
    )
    assert csv_resp.status_code == 200
    body = csv_resp.text
    assert "rating" in body
    assert "comments" in body
    assert "Carol did fine work" in body
