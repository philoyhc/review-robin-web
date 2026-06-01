"""Service + route coverage for the redesigned Band 3 visibility
editor — per-(instrument, audience) policies on
``instrument_view_policies`` with per-window mode pairs.

The W15 follow-on swaps the axis: the editor column is now the
**window** ("Session ongoing" / "Responses released") rather
than a single mode + ``visible_when`` value. The service
matches: ``upsert_policy`` takes ``while_ongoing_mode`` and
``after_release_mode`` (each ``None`` for "off in this window"
or one of the operator-facing labels Raw / Anonymized /
Summarized).

Per-(audience, window) cell rules:

- ``peer_reviewer`` Session-ongoing must be ``"raw"`` —
  baseline self-view always on.
- ``peer_reviewer`` Responses-released must be ``None`` or
  ``"raw"``.
- ``reviewee`` Session-ongoing must be ``None`` — strict
  per-pair flow rule.
- ``reviewee`` Responses-released: any of the three modes or
  ``None``.
- ``observer`` in either window: any of the three modes or
  ``None``.

Legacy columns (``enabled`` / ``granularity`` /
``identification`` / ``visible_when``) get mirror-written from
the per-window state so a rolled-back deploy still reads
sensible values; they retire in the contract-step PR.
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
    with pytest.raises(visibility_policies.VisibilityPolicyError):
        visibility_policies.decode_mode("aggregated", "identified")


def test_valid_modes_for_cell_locks_per_audience() -> None:
    """Spot-check the per-(audience, window) valid-mode map."""
    assert (
        visibility_policies.valid_modes_for_cell(
            "peer_reviewer", "while_ongoing"
        )
        == frozenset({"raw"})
    )
    assert (
        visibility_policies.valid_modes_for_cell(
            "reviewee", "while_ongoing"
        )
        == frozenset({None})
    )
    assert (
        visibility_policies.valid_modes_for_cell(
            "observer", "after_release"
        )
        == frozenset({None, "raw", "anonymized", "summarized"})
    )


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


def test_upsert_policy_insert_writes_per_window_pairs(db: Session) -> None:
    review_session, instrument, user = _setup(db)
    row, changes = visibility_policies.upsert_policy(
        db,
        review_session=review_session,
        instrument=instrument,
        audience="reviewee",
        while_ongoing_mode=None,
        after_release_mode="anonymized",
        user=user,
    )
    db.commit()
    assert row.while_ongoing_granularity is None
    assert row.while_ongoing_identification is None
    assert row.after_release_granularity == "row"
    assert row.after_release_identification == "deidentified"
    # Legacy mirror — sensible representative + visible_when.
    assert row.enabled is True
    assert row.granularity == "row"
    assert row.identification == "deidentified"
    assert row.visible_when == "after_release"
    events = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "instrument.view_policy_set"
        )
    ).scalars().all()
    assert len(events) == 1
    # Insert paints every column as a change.
    assert "while_ongoing_granularity" in changes
    assert "after_release_granularity" in changes
    assert "enabled" in changes


def test_upsert_policy_throughout_when_both_windows_set(
    db: Session,
) -> None:
    review_session, instrument, user = _setup(db)
    row, _ = visibility_policies.upsert_policy(
        db,
        review_session=review_session,
        instrument=instrument,
        audience="observer",
        while_ongoing_mode="summarized",
        after_release_mode="summarized",
        user=user,
    )
    db.commit()
    assert row.while_ongoing_granularity == "aggregated"
    assert row.after_release_granularity == "aggregated"
    # Legacy mirror — both windows same mode collapses to
    # visible_when="throughout".
    assert row.enabled is True
    assert row.visible_when == "throughout"


def test_upsert_policy_both_none_disables(db: Session) -> None:
    """Setting both windows to ``None`` is the explicit
    'audience can't view this instrument' state."""
    review_session, instrument, user = _setup(db)
    # Start with after_release on.
    visibility_policies.upsert_policy(
        db,
        review_session=review_session,
        instrument=instrument,
        audience="reviewee",
        while_ongoing_mode=None,
        after_release_mode="anonymized",
        user=user,
    )
    db.commit()
    # Turn it off.
    row, changes = visibility_policies.upsert_policy(
        db,
        review_session=review_session,
        instrument=instrument,
        audience="reviewee",
        while_ongoing_mode=None,
        after_release_mode=None,
        user=user,
    )
    db.commit()
    assert row.while_ongoing_granularity is None
    assert row.after_release_granularity is None
    assert row.enabled is False
    assert row.visible_when is None
    # Changes recorded the flip on both the pair column + the
    # legacy mirror.
    assert "after_release_granularity" in changes
    assert "enabled" in changes


def test_upsert_policy_no_op_emits_no_audit(db: Session) -> None:
    review_session, instrument, user = _setup(db)
    visibility_policies.upsert_policy(
        db,
        review_session=review_session,
        instrument=instrument,
        audience="reviewee",
        while_ongoing_mode=None,
        after_release_mode=None,
        user=user,
    )
    db.commit()
    _, changes = visibility_policies.upsert_policy(
        db,
        review_session=review_session,
        instrument=instrument,
        audience="reviewee",
        while_ongoing_mode=None,
        after_release_mode=None,
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


def test_upsert_policy_rejects_peer_reviewer_session_ongoing_off(
    db: Session,
) -> None:
    """Reviewer Session-ongoing is the baseline self-view
    guarantee — must be ``"raw"``, never ``None``."""
    review_session, instrument, user = _setup(db)
    with pytest.raises(
        visibility_policies.VisibilityPolicyError
    ) as excinfo:
        visibility_policies.upsert_policy(
            db,
            review_session=review_session,
            instrument=instrument,
            audience="peer_reviewer",
            while_ongoing_mode=None,
            after_release_mode="raw",
            user=user,
        )
    assert excinfo.value.code == "invalid_mode"


def test_upsert_policy_rejects_peer_reviewer_anonymized_after_release(
    db: Session,
) -> None:
    review_session, instrument, user = _setup(db)
    with pytest.raises(visibility_policies.VisibilityPolicyError):
        visibility_policies.upsert_policy(
            db,
            review_session=review_session,
            instrument=instrument,
            audience="peer_reviewer",
            while_ongoing_mode="raw",
            after_release_mode="anonymized",
            user=user,
        )


def test_upsert_policy_rejects_reviewee_session_ongoing_on(
    db: Session,
) -> None:
    """Reviewee Session-ongoing must be ``None`` — strict
    per-pair flow rule."""
    review_session, instrument, user = _setup(db)
    with pytest.raises(visibility_policies.VisibilityPolicyError):
        visibility_policies.upsert_policy(
            db,
            review_session=review_session,
            instrument=instrument,
            audience="reviewee",
            while_ongoing_mode="raw",
            after_release_mode=None,
            user=user,
        )


def test_upsert_policy_observer_tag_rejected_for_non_observer(
    db: Session,
) -> None:
    review_session, instrument, user = _setup(db)
    with pytest.raises(
        visibility_policies.VisibilityPolicyError
    ) as excinfo:
        visibility_policies.upsert_policy(
            db,
            review_session=review_session,
            instrument=instrument,
            audience="reviewee",
            while_ongoing_mode=None,
            after_release_mode="anonymized",
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
        audience="observer",
        while_ongoing_mode="anonymized",
        after_release_mode="summarized",
        user=user,
    )
    db.commit()
    persisted = visibility_policies.list_for_instrument(
        db, instrument.id
    )
    assert set(persisted.keys()) == {"observer"}
    row = persisted["observer"]
    assert row.while_ongoing_granularity == "row"
    assert row.while_ongoing_identification == "deidentified"
    assert row.after_release_granularity == "aggregated"
    assert row.after_release_identification == "deidentified"


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
            "peer_reviewer_while_ongoing_mode": "raw",
            "peer_reviewer_after_release_mode": "raw",
            "reviewee_while_ongoing_mode": "",
            "reviewee_after_release_mode": "summarized",
            "observer_while_ongoing_mode": "anonymized",
            "observer_after_release_mode": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    rows = db.execute(
        select(InstrumentViewPolicy).where(
            InstrumentViewPolicy.instrument_id == instrument.id
        )
    ).scalars().all()
    by_audience = {row.audience: row for row in rows}
    # Reviewers: both windows Raw.
    assert by_audience["peer_reviewer"].while_ongoing_granularity == "row"
    assert by_audience["peer_reviewer"].after_release_granularity == "row"
    # Reviewees: only after_release set, Summarized.
    assert by_audience["reviewee"].while_ongoing_granularity is None
    assert by_audience["reviewee"].after_release_granularity == "aggregated"
    # Observer: only while_ongoing set, Anonymized.
    assert by_audience["observer"].while_ongoing_granularity == "row"
    assert by_audience["observer"].while_ongoing_identification == "deidentified"
    assert by_audience["observer"].after_release_granularity is None


def test_route_save_rejects_reviewee_session_ongoing_with_mode(
    client: TestClient, db: Session
) -> None:
    review_session = _alice_session(client, db, code="vp-bad-cell")
    instrument = _instrument_for(db, review_session)
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/view-policy",
        data={
            "reviewee_while_ongoing_mode": "raw",
            "reviewee_after_release_mode": "anonymized",
        },
        follow_redirects=False,
    )
    assert response.status_code == 422
    assert "Session-ongoing" in response.text or "while_ongoing" in response.text


def test_route_save_skips_audiences_with_missing_slots(
    client: TestClient, db: Session
) -> None:
    """An audience absent from the form payload doesn't get a row."""
    review_session = _alice_session(client, db, code="vp-partial")
    instrument = _instrument_for(db, review_session)
    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/view-policy",
        data={
            "reviewee_while_ongoing_mode": "",
            "reviewee_after_release_mode": "anonymized",
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


def test_instruments_page_renders_per_window_form(
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
    # Hidden inputs for all three audiences × two windows render.
    for audience in ("peer_reviewer", "reviewee", "observer"):
        for window in ("while_ongoing", "after_release"):
            assert f'name="{audience}_{window}_mode"' in body
    # Per-cell static-pill anchors.
    assert "Reviewers" in body
    assert "Reviewees" in body
    assert "Observers" in body
    # New column headings.
    assert "Session ongoing" in body
    assert "Responses released" in body


def test_instruments_page_reflects_persisted_state(
    client: TestClient, db: Session
) -> None:
    review_session = _alice_session(client, db, code="vp-prefill")
    instrument = _instrument_for(db, review_session)
    client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/view-policy",
        data={
            "observer_while_ongoing_mode": "summarized",
            "observer_after_release_mode": "raw",
        },
        follow_redirects=False,
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    # The observer-while_ongoing hidden input carries the
    # persisted value.
    assert (
        'name="observer_while_ongoing_mode"\n                   data-new-model-vp-input="observer-while_ongoing"\n                   value="summarized"'
        in body
    )
    assert (
        'name="observer_after_release_mode"\n                   data-new-model-vp-input="observer-after_release"\n                   value="raw"'
        in body
    )
