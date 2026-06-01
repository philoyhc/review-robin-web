"""Service + route coverage for the W15 Band 3 visibility editor —
per-instrument, per-audience policies on
``instrument_view_policies``.

The persistence half ships here; the W7 resolver + W16 / W17
surfaces consuming the rows are separate slices. These tests
pin the operator-facing contract: per-audience vocabulary,
mode encoding, upsert semantics (insert vs update vs no-op),
and the ``instrument.view_policy_set`` audit emission.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    Instrument,
    InstrumentViewPolicy,
    ReviewSession,
    User,
)
from app.services import visibility_policies


# ── Service-level: encode / decode + validation ──────────────────────


def test_encode_mode_round_trips_three_coherent_modes() -> None:
    for mode, expected_pair in [
        ("raw", ("row", "identified")),
        ("anonymized", ("row", "deidentified")),
        ("summarized", ("aggregated", "deidentified")),
    ]:
        assert visibility_policies.encode_mode(mode) == expected_pair
        assert (
            visibility_policies.decode_mode(*expected_pair) == mode
        )


def test_encode_mode_rejects_unknown_label() -> None:
    with pytest.raises(visibility_policies.VisibilityPolicyError) as excinfo:
        visibility_policies.encode_mode("verbose")
    assert excinfo.value.code == "invalid_mode"


def test_decode_mode_rejects_incoherent_aggregated_identified() -> None:
    """The reserved-incoherent combo. The schema column types
    accept it; the encoder / decoder rejects."""
    with pytest.raises(visibility_policies.VisibilityPolicyError):
        visibility_policies.decode_mode("aggregated", "identified")


def _setup(db: Session) -> tuple[ReviewSession, Instrument, User]:
    user = User(email="op@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="S", code="vp-test", created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    instrument = Instrument(
        session_id=review_session.id,
        name="I",
        order=1,
    )
    db.add(instrument)
    db.flush()
    return review_session, instrument, user


def test_upsert_policy_insert_emits_audit(db: Session) -> None:
    review_session, instrument, user = _setup(db)
    row, changes = visibility_policies.upsert_policy(
        db,
        review_session=review_session,
        instrument=instrument,
        audience="reviewee",
        enabled=True,
        mode="anonymized",
        visible_when="after_release",
        user=user,
    )
    db.commit()
    assert row.enabled is True
    assert row.granularity == "row"
    assert row.identification == "deidentified"
    assert row.visible_when == "after_release"
    # Insert paints every field as a change.
    assert set(changes.keys()) == {
        "enabled",
        "granularity",
        "identification",
        "visible_when",
        "observer_tag",
    }
    events = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "instrument.view_policy_set"
        )
    ).scalars().all()
    assert len(events) == 1


def test_upsert_policy_update_emits_only_when_changed(db: Session) -> None:
    review_session, instrument, user = _setup(db)
    visibility_policies.upsert_policy(
        db,
        review_session=review_session,
        instrument=instrument,
        audience="reviewee",
        enabled=False,
        mode="anonymized",
        visible_when="after_release",
        user=user,
    )
    db.commit()
    # Same-values re-save → no audit event, no changes.
    _, changes = visibility_policies.upsert_policy(
        db,
        review_session=review_session,
        instrument=instrument,
        audience="reviewee",
        enabled=False,
        mode="anonymized",
        visible_when="after_release",
        user=user,
    )
    db.commit()
    assert changes == {}
    events = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "instrument.view_policy_set"
        )
    ).scalars().all()
    assert len(events) == 1  # only the insert


def test_upsert_policy_rejects_peer_reviewer_non_raw(db: Session) -> None:
    review_session, instrument, user = _setup(db)
    with pytest.raises(visibility_policies.VisibilityPolicyError) as excinfo:
        visibility_policies.upsert_policy(
            db,
            review_session=review_session,
            instrument=instrument,
            audience="peer_reviewer",
            enabled=True,
            mode="anonymized",
            visible_when="while_ongoing",
            user=user,
        )
    assert excinfo.value.code == "invalid_mode"


def test_upsert_policy_rejects_peer_reviewer_after_release_when(
    db: Session,
) -> None:
    """Peer reviewer's When cycle is only while_ongoing ⇄ throughout."""
    review_session, instrument, user = _setup(db)
    with pytest.raises(visibility_policies.VisibilityPolicyError) as excinfo:
        visibility_policies.upsert_policy(
            db,
            review_session=review_session,
            instrument=instrument,
            audience="peer_reviewer",
            enabled=True,
            mode="raw",
            visible_when="after_release",
            user=user,
        )
    assert excinfo.value.code == "invalid_visible_when"


def test_upsert_policy_observer_tag_rejected_for_non_observer(
    db: Session,
) -> None:
    review_session, instrument, user = _setup(db)
    with pytest.raises(visibility_policies.VisibilityPolicyError) as excinfo:
        visibility_policies.upsert_policy(
            db,
            review_session=review_session,
            instrument=instrument,
            audience="reviewee",
            enabled=True,
            mode="anonymized",
            visible_when="after_release",
            observer_tag="committee",
            user=user,
        )
    assert excinfo.value.code == "observer_tag_misuse"


def test_list_for_instrument_returns_persisted_audiences_only(
    db: Session,
) -> None:
    review_session, instrument, user = _setup(db)
    visibility_policies.upsert_policy(
        db,
        review_session=review_session,
        instrument=instrument,
        audience="reviewee",
        enabled=True,
        mode="anonymized",
        visible_when="after_release",
        user=user,
    )
    db.commit()
    persisted = visibility_policies.list_for_instrument(
        db, instrument.id
    )
    assert set(persisted.keys()) == {"reviewee"}
    assert persisted["reviewee"].enabled is True


# ── Route-level: POST /instruments/{id}/view-policy ──────────────────


def _alice_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "S", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    db.refresh(session)
    return session


def _instrument_for(db: Session, session: ReviewSession) -> Instrument:
    return db.execute(
        select(Instrument).where(Instrument.session_id == session.id)
    ).scalars().first()


def test_route_save_persists_three_audiences(
    client: TestClient, db: Session
) -> None:
    review_session = _alice_session(client, db, code="vp-route")
    instrument = _instrument_for(db, review_session)
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/view-policy",
        data={
            "peer_reviewer_enabled": "true",
            "peer_reviewer_mode": "raw",
            "peer_reviewer_visible_when": "throughout",
            "reviewee_enabled": "true",
            "reviewee_mode": "summarized",
            "reviewee_visible_when": "after_release",
            "observer_enabled": "false",
            "observer_mode": "anonymized",
            "observer_visible_when": "after_release",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert (
        f"/operator/sessions/{review_session.id}/instruments"
        in response.headers["location"]
    )
    rows = db.execute(
        select(InstrumentViewPolicy).where(
            InstrumentViewPolicy.instrument_id == instrument.id
        )
    ).scalars().all()
    by_audience = {row.audience: row for row in rows}
    assert by_audience["peer_reviewer"].enabled is True
    assert by_audience["peer_reviewer"].visible_when == "throughout"
    assert by_audience["reviewee"].granularity == "aggregated"
    assert by_audience["observer"].enabled is False


def test_route_save_invalid_mode_returns_422(
    client: TestClient, db: Session
) -> None:
    review_session = _alice_session(client, db, code="vp-bad-mode")
    instrument = _instrument_for(db, review_session)
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/view-policy",
        data={
            "peer_reviewer_enabled": "true",
            "peer_reviewer_mode": "anonymized",
            "peer_reviewer_visible_when": "while_ongoing",
        },
        follow_redirects=False,
    )
    assert response.status_code == 422


def test_route_save_skips_audiences_with_missing_slots(
    client: TestClient, db: Session
) -> None:
    """If only some audiences arrive in the form payload, the
    others are skipped rather than rejecting the whole save —
    lets a future audience addition roll out without a
    coordinated form-payload change."""
    review_session = _alice_session(client, db, code="vp-partial")
    instrument = _instrument_for(db, review_session)
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/view-policy",
        data={
            "reviewee_enabled": "true",
            "reviewee_mode": "anonymized",
            "reviewee_visible_when": "after_release",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    rows = db.execute(
        select(InstrumentViewPolicy).where(
            InstrumentViewPolicy.instrument_id == instrument.id
        )
    ).scalars().all()
    assert {r.audience for r in rows} == {"reviewee"}


# ── Template render: form + chip state on GET ────────────────────────


def test_instruments_page_renders_visibility_form_per_instrument(
    client: TestClient, db: Session
) -> None:
    review_session = _alice_session(client, db, code="vp-render")
    instrument = _instrument_for(db, review_session)
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    assert (
        f'action="/operator/sessions/{review_session.id}/instruments/{instrument.id}/view-policy"'
        in body
    )
    # Hidden inputs for all three audiences render.
    for audience in ("peer_reviewer", "reviewee", "observer"):
        for slot in ("enabled", "mode", "visible_when"):
            assert (
                f'name="{audience}_{slot}"' in body
            )


def test_instruments_page_reflects_persisted_state(
    client: TestClient, db: Session
) -> None:
    """A persisted (reviewee, summarized, throughout) row
    surfaces with the chip's current slug + the matching hidden
    input default."""
    review_session = _alice_session(client, db, code="vp-prefill")
    instrument = _instrument_for(db, review_session)
    client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/view-policy",
        data={
            "reviewee_enabled": "true",
            "reviewee_mode": "summarized",
            "reviewee_visible_when": "throughout",
        },
        follow_redirects=False,
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    # Hidden inputs carry the persisted values.
    assert (
        'name="reviewee_enabled"\n                   data-new-model-visibility-input="reviewee-enabled"\n                   value="true"'
        in body
    )
    assert (
        'name="reviewee_mode"\n                   data-new-model-visibility-input="reviewee-mode"\n                   value="summarized"'
        in body
    )
    assert (
        'name="reviewee_visible_when"\n                   data-new-model-visibility-input="reviewee-visible_when"\n                   value="throughout"'
        in body
    )
