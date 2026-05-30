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

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import (
    Assignment,
    Instrument,
    InstrumentResponseField,
    Response,
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
        f"/me/sessions/{review_session.id}/1/save",
        data=data,
        follow_redirects=False,
    )
    rae_client.post(
        f"/me/sessions/{review_session.id}/submit",
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
        f"/me/sessions/{review_session.id}/summary"
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
        f"/me/sessions/{review_session.id}/summary"
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
        f"/me/sessions/{review_session.id}/summary"
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
        f"/me/sessions/{review_session.id}/summary"
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
        f"/me/sessions/{review_session.id}/summary.csv"
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
        f"/me/sessions/{review_session.id}/summary.csv"
    )
    assert csv_resp.status_code == 200
    body = csv_resp.text
    assert "rating" in body
    assert "comments" in body
    assert "Carol did fine work" in body


# ── Segment 18K PR 4 — visibility-drop confirm guard ──────────────────────


def _band2_un_pin_response_field_payload(
    instrument: Instrument, un_pin_key: str
) -> dict:
    """Build a band2-state payload that mirrors the live JS round-
    trip — every existing response field appears with its current
    inline shape, but ``selected=False`` on the one we're un-
    pinning. ``acknowledged_drop`` is left to the caller."""
    fields = sorted(instrument.response_fields, key=lambda f: f.order)
    response_fields = []
    for f in fields:
        rf: dict = {
            "id": f.id,
            "name": f.label,
            "data_type": (f._inline_data_type or "String").lower(),
            "min": "" if f._inline_min is None else str(int(f._inline_min)),
            "max": "" if f._inline_max is None else str(int(f._inline_max)),
            "step": "" if f._inline_step is None else str(int(f._inline_step)),
            "list_options": f._inline_list_csv or "",
            "selected": f.visible and f.field_key != un_pin_key,
            "required": f.required,
            "help_text_visible": f.help_text_visible,
            "help_text": f.help_text or "",
        }
        response_fields.append(rf)
    return {
        "selected_display_keys": ["reviewee.name"],
        "response_fields": response_fields,
    }


def _seed_response_for_assignment(
    db: Session,
    *,
    assignment: Assignment,
    field: InstrumentResponseField,
    value: str,
    submitted: bool,
) -> Response:
    """Drop a saved (or saved-and-submitted) ``Response`` row onto
    the given assignment / field pair. Lets the visibility-drop
    confirm-guard tests exercise the post-submit path without
    routing the session through ``activate`` (which would also
    lock band2-state via ``_require_instrument_editable``)."""
    row = Response(
        assignment_id=assignment.id,
        response_field_id=field.id,
        value=value,
        submitted_at=datetime.now(timezone.utc) if submitted else None,
    )
    db.add(row)
    db.commit()
    return row


def test_band2_state_un_pin_with_responses_requires_acknowledgement(
    client: TestClient,
    db: Session,
    rae: AuthenticatedUser,
) -> None:
    """Segment 18K PR 4 — the visibility-drop confirm guard.
    POSTing a band2-state that flips ``visible: True → False`` on a
    field with saved responses must 409 with a structured payload
    naming the field + response count when
    ``acknowledged_drop`` is missing/false. Re-POSTing the same
    payload with ``acknowledged_drop=true`` lets the flip through.

    Seeded directly into the validated-state DB rather than going
    through ``_activate`` + ``_submit`` because
    ``_require_instrument_editable`` blocks band2-state once the
    session reaches ``ready`` (the operator-side lock guards
    structural mutations during active review)."""
    review_session = _seed_session_with_rae_and_one_reviewee(
        client, db, code="vis-guard-ack", reviewer_email=rae.email
    )
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    comments_field = db.execute(
        select(InstrumentResponseField)
        .where(InstrumentResponseField.instrument_id == instrument.id)
        .where(InstrumentResponseField.field_key == "comments")
    ).scalar_one()
    assignment = db.execute(
        select(Assignment)
        .where(Assignment.instrument_id == instrument.id)
    ).scalars().first()
    assert assignment is not None
    _seed_response_for_assignment(
        db,
        assignment=assignment,
        field=comments_field,
        value="Saved comment",
        submitted=True,
    )

    payload = _band2_un_pin_response_field_payload(
        instrument, un_pin_key="comments"
    )

    # Without ack — 409 with structured detail.
    resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{instrument.id}/band2-state",
        json=payload,
    )
    assert resp.status_code == 409
    detail = resp.json()
    assert detail["error"] == "drop_acknowledgement_required"
    assert detail["field_label"] == "Comments"
    assert detail["responses"] == 1

    # And the field is still visible — the failed save didn't commit.
    db.expire_all()
    comments_field = db.execute(
        select(InstrumentResponseField)
        .where(InstrumentResponseField.instrument_id == instrument.id)
        .where(InstrumentResponseField.field_key == "comments")
    ).scalar_one()
    assert comments_field.visible is True

    # Now re-POST with ack=true — succeeds.
    payload["acknowledged_drop"] = True
    resp_ok = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{instrument.id}/band2-state",
        json=payload,
    )
    assert resp_ok.status_code == 200

    db.expire_all()
    comments_field = db.execute(
        select(InstrumentResponseField)
        .where(InstrumentResponseField.instrument_id == instrument.id)
        .where(InstrumentResponseField.field_key == "comments")
    ).scalar_one()
    assert comments_field.visible is False


def test_band2_state_un_pin_without_responses_no_ack_needed(
    client: TestClient,
    db: Session,
) -> None:
    """A response field with NO saved responses can be un-pinned
    without the ``acknowledged_drop`` flag — the guard fires only
    on the lossy case. Covers the fresh-card flow where the
    operator drops a default field before any reviewer submits."""
    review_session = _seed_session_with_rae_and_one_reviewee(
        client, db, code="vis-guard-noresp", reviewer_email="rae@example.edu"
    )
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    payload = _band2_un_pin_response_field_payload(
        instrument, un_pin_key="comments"
    )
    resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{instrument.id}/band2-state",
        json=payload,
    )
    assert resp.status_code == 200

    db.expire_all()
    comments_field = db.execute(
        select(InstrumentResponseField)
        .where(InstrumentResponseField.instrument_id == instrument.id)
        .where(InstrumentResponseField.field_key == "comments")
    ).scalar_one()
    assert comments_field.visible is False


# ── Part 4 scenarios — flip path interaction with submit / group fan-out ──


def test_pill_state_stays_submitted_after_chip_un_pin_post_submit(
    client: TestClient,
    db: Session,
    rae: AuthenticatedUser,
) -> None:
    """Part 4 — Operator un-pins a Band 2 response chip *after* the
    reviewer has submitted. The Comments column drops from the
    reviewer-facing surfaces, but ``pill_state`` stays
    ``"submitted"`` (no recall trigger) — the reviewer is still
    done. The reviewer's saved ``Response`` rows survive in the
    DB with ``submitted_at`` intact for the audit path."""
    from app.db.models import Reviewer
    from app.services.responses import reviewer_session_state

    review_session = _seed_session_with_rae_and_one_reviewee(
        client, db, code="vis-post-submit", reviewer_email=rae.email
    )
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    fields = {f.field_key: f for f in instrument.response_fields}
    assignment = db.execute(
        select(Assignment).where(Assignment.instrument_id == instrument.id)
    ).scalars().first()
    assert assignment is not None
    # Seed both required-field rows as submitted so the rollup
    # genuinely rolls up to "submitted".
    _seed_response_for_assignment(
        db,
        assignment=assignment,
        field=fields["rating"],
        value="5",
        submitted=True,
    )
    _seed_response_for_assignment(
        db,
        assignment=assignment,
        field=fields["comments"],
        value="Carol did fine work",
        submitted=True,
    )

    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == review_session.id)
    ).scalar_one()
    before = reviewer_session_state(
        db, reviewer=reviewer, session_id=review_session.id
    )
    assert before.pill_state == "submitted"

    payload = _band2_un_pin_response_field_payload(
        instrument, un_pin_key="comments"
    )
    payload["acknowledged_drop"] = True
    resp = client.post(
        f"/operator/sessions/{review_session.id}"
        f"/instruments/{instrument.id}/band2-state",
        json=payload,
    )
    assert resp.status_code == 200

    db.expire_all()
    comments_field = db.execute(
        select(InstrumentResponseField)
        .where(InstrumentResponseField.instrument_id == instrument.id)
        .where(InstrumentResponseField.field_key == "comments")
    ).scalar_one()
    assert comments_field.visible is False
    saved = db.execute(
        select(Response).where(Response.response_field_id == comments_field.id)
    ).scalars().all()
    assert len(saved) == 1
    assert saved[0].submitted_at is not None
    assert saved[0].value == "Carol did fine work"

    # And the rollup still reads "submitted" — un-pinning didn't
    # recall the assignment.
    after = reviewer_session_state(
        db, reviewer=reviewer, session_id=review_session.id
    )
    assert after.pill_state == "submitted"


# ── Segment 18K PR 5 — reviewer-surface dropped-fields banner ─────────────


def test_reviewer_surface_banner_names_dropped_field(
    client: TestClient,
    db: Session,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """Segment 18K PR 5 — When an operator un-pins a Band 2 chip
    on a field where the reviewer has a saved Response, the next
    GET of the reviewer surface renders an informational banner
    naming the field. Read-only contract: the values stay in the
    DB for the audit path; the banner just surfaces the
    disappearance so the reviewer isn't silently missing answers."""
    review_session = _seed_session_with_rae_and_one_reviewee(
        client, db, code="vis-banner", reviewer_email=rae.email
    )
    _activate(client, review_session)
    rae_client = make_client(rae)
    _submit(rae_client, review_session, db)
    _hide_field(db, review_session, "comments")

    app.dependency_overrides[get_current_user] = lambda: rae
    body = rae_client.get(
        f"/me/sessions/{review_session.id}/1"
    ).text
    assert "Some saved responses are no longer collected" in body
    assert "<em>Comments</em>" in body
    # Field rendered alongside an instrument-context label (the
    # default seeded instrument has neither short_label nor name,
    # so the fallback ``Instrument <id>`` runs).
    assert "Instrument" in body


def test_reviewer_surface_no_banner_when_no_dropped_fields(
    client: TestClient,
    db: Session,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """No saved responses on hidden fields → no banner. Sanity
    check that the banner is properly gated and doesn't leak onto
    every surface render."""
    review_session = _seed_session_with_rae_and_one_reviewee(
        client, db, code="vis-banner-none", reviewer_email=rae.email
    )
    _activate(client, review_session)
    rae_client = make_client(rae)
    _submit(rae_client, review_session, db)

    app.dependency_overrides[get_current_user] = lambda: rae
    body = rae_client.get(
        f"/me/sessions/{review_session.id}/1"
    ).text
    assert "Some saved responses are no longer collected" not in body


def test_reviewer_surface_banner_disappears_when_visibility_restored(
    client: TestClient,
    db: Session,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """Flipping ``visible`` back to ``True`` rehydrates the column
    (already pinned by the existing round-trip tests) and removes
    the dropped-fields banner — the previously-saved response is
    no longer "dropped" because the operator restored the chip."""
    review_session = _seed_session_with_rae_and_one_reviewee(
        client, db, code="vis-banner-restore", reviewer_email=rae.email
    )
    _activate(client, review_session)
    rae_client = make_client(rae)
    _submit(rae_client, review_session, db)
    _hide_field(db, review_session, "comments")

    app.dependency_overrides[get_current_user] = lambda: rae
    body_hidden = rae_client.get(
        f"/me/sessions/{review_session.id}/1"
    ).text
    assert "Some saved responses are no longer collected" in body_hidden

    # Restore visibility.
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    field = db.execute(
        select(InstrumentResponseField)
        .where(InstrumentResponseField.instrument_id == instrument.id)
        .where(InstrumentResponseField.field_key == "comments")
    ).scalar_one()
    field.visible = True
    db.commit()

    body_restored = rae_client.get(
        f"/me/sessions/{review_session.id}/1"
    ).text
    assert "Some saved responses are no longer collected" not in body_restored


def test_group_scoped_instrument_visibility_filter_applies(
    client: TestClient,
    db: Session,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """Part 4 — Group-scoped instruments honour ``visible`` just
    like individual ones. The group-fan-out invariant carries
    through: there's one source-of-truth ``InstrumentResponseField``
    row, so one ``visible`` flip applies to every reviewee row the
    group surfaces. Mirrors the individual-instrument test above
    but with ``Instrument.group_kind`` set + a second reviewee in
    the same group."""
    from app.db.models import Reviewee

    review_session = _seed_session_with_rae_and_one_reviewee(
        client, db, code="vis-group", reviewer_email=rae.email
    )
    # Add a second reviewee in the same group as Carol so the
    # group fan-out surfaces both rows; flip the instrument into
    # group mode via ``group_kind``.
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Dale",
            email_or_identifier="dale@example.edu",
            tag_1="g1",
        )
    )
    carol = db.execute(
        select(Reviewee).where(
            Reviewee.session_id == review_session.id,
            Reviewee.email_or_identifier == "carol@example.edu",
        )
    ).scalar_one()
    carol.tag_1 = "g1"
    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).scalar_one()
    instrument.group_kind = "r1"
    db.commit()

    _activate(client, review_session)
    rae_client = make_client(rae)
    _submit(rae_client, review_session, db)

    # Hide Comments via direct ``visible`` mutation — the
    # band2-state un-pin path is locked once the session is ready
    # (``_require_instrument_editable``), and the filter under test
    # is the read-side one. ``test_band2_state_un_pin_*`` above pins
    # the write path; this test pins the read path under group
    # fan-out.
    _hide_field(db, review_session, "comments")

    app.dependency_overrides[get_current_user] = lambda: rae
    summary_html = rae_client.get(
        f"/me/sessions/{review_session.id}/summary"
    ).text
    assert "Comments" not in summary_html
    assert "Carol did fine work" not in summary_html
    assert "Rating" in summary_html

    csv_resp = rae_client.get(
        f"/me/sessions/{review_session.id}/summary.csv"
    )
    assert csv_resp.status_code == 200
    csv_body = csv_resp.text
    assert "comments" not in csv_body
    assert "Carol did fine work" not in csv_body
    assert "rating" in csv_body
