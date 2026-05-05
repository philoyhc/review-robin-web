"""Segment 11L — Instrument.short_label + Setup-side editor.

Service-layer + integration coverage for the new reviewer-facing
short label on `Instrument`. The reviewer surface picks up the
column in the multi-instrument rewrite (PR γ); 11L is the
Setup-side foundation that ships ahead of it.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Instrument, ReviewSession
from app.services import instruments as instruments_service


def _create_session(
    client: TestClient, db: Session, code: str = "rae-11l"
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "11L", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _default_instrument(db: Session, session_id: int) -> Instrument:
    return db.execute(
        select(Instrument).where(Instrument.session_id == session_id)
    ).scalar_one()


# ── Service layer: update_short_label ──────────────────────────────────


def test_update_short_label_persists_value(
    client: TestClient, db: Session
) -> None:
    review_session = _create_session(client, db, code="rae-11l-set")
    instrument = _default_instrument(db, review_session.id)
    user = review_session.created_by_user

    instruments_service.update_short_label(
        db, instrument=instrument, short_label="Skills", actor=user
    )
    db.refresh(instrument)
    assert instrument.short_label == "Skills"


def test_update_short_label_trims_whitespace(
    client: TestClient, db: Session
) -> None:
    review_session = _create_session(client, db, code="rae-11l-trim")
    instrument = _default_instrument(db, review_session.id)
    user = review_session.created_by_user

    instruments_service.update_short_label(
        db, instrument=instrument, short_label="  Cultural Fit  ", actor=user
    )
    db.refresh(instrument)
    assert instrument.short_label == "Cultural Fit"


def test_update_short_label_empty_string_persists_as_null(
    client: TestClient, db: Session
) -> None:
    review_session = _create_session(client, db, code="rae-11l-empty")
    instrument = _default_instrument(db, review_session.id)
    user = review_session.created_by_user

    instruments_service.update_short_label(
        db, instrument=instrument, short_label="Skills", actor=user
    )
    instruments_service.update_short_label(
        db, instrument=instrument, short_label="   ", actor=user
    )
    db.refresh(instrument)
    assert instrument.short_label is None


def test_update_short_label_none_persists_as_null(
    client: TestClient, db: Session
) -> None:
    review_session = _create_session(client, db, code="rae-11l-none")
    instrument = _default_instrument(db, review_session.id)
    user = review_session.created_by_user

    instruments_service.update_short_label(
        db, instrument=instrument, short_label="Skills", actor=user
    )
    instruments_service.update_short_label(
        db, instrument=instrument, short_label=None, actor=user
    )
    db.refresh(instrument)
    assert instrument.short_label is None


def test_update_short_label_32_char_value_accepted(
    client: TestClient, db: Session
) -> None:
    review_session = _create_session(client, db, code="rae-11l-32")
    instrument = _default_instrument(db, review_session.id)
    user = review_session.created_by_user
    label = "x" * 32  # exactly 32 chars

    instruments_service.update_short_label(
        db, instrument=instrument, short_label=label, actor=user
    )
    db.refresh(instrument)
    assert instrument.short_label == label


def test_update_short_label_33_char_value_raises(
    client: TestClient, db: Session
) -> None:
    review_session = _create_session(client, db, code="rae-11l-33")
    instrument = _default_instrument(db, review_session.id)
    user = review_session.created_by_user
    too_long = "x" * 33

    with pytest.raises(ValueError, match="exceeds 32 chars"):
        instruments_service.update_short_label(
            db, instrument=instrument, short_label=too_long, actor=user
        )


def test_update_short_label_no_op_when_unchanged(
    client: TestClient, db: Session
) -> None:
    """Setting short_label to its current value is a no-op — no audit
    event, no `invalidate_if_validated` call."""
    review_session = _create_session(client, db, code="rae-11l-noop")
    instrument = _default_instrument(db, review_session.id)
    user = review_session.created_by_user

    instruments_service.update_short_label(
        db, instrument=instrument, short_label="Skills", actor=user
    )
    db.commit()
    pre = (
        db.execute(
            select(AuditEvent).where(
                AuditEvent.event_type == "instrument.short_label_updated"
            )
        )
        .scalars()
        .all()
    )
    assert len(pre) == 1

    instruments_service.update_short_label(
        db, instrument=instrument, short_label="Skills", actor=user
    )
    post = (
        db.execute(
            select(AuditEvent).where(
                AuditEvent.event_type == "instrument.short_label_updated"
            )
        )
        .scalars()
        .all()
    )
    # No new audit event for the no-op repeat.
    assert len(post) == 1


def test_update_short_label_emits_audit_with_old_new_list(
    client: TestClient, db: Session
) -> None:
    """Audit detail uses the same `[old, new]` list shape as
    `update_instrument_description`'s `description: [old, new]`."""
    review_session = _create_session(client, db, code="rae-11l-audit")
    instrument = _default_instrument(db, review_session.id)
    user = review_session.created_by_user

    instruments_service.update_short_label(
        db, instrument=instrument, short_label="Skills", actor=user
    )
    instruments_service.update_short_label(
        db, instrument=instrument, short_label="Cultural Fit", actor=user
    )

    events = (
        db.execute(
            select(AuditEvent)
            .where(
                AuditEvent.event_type == "instrument.short_label_updated"
            )
            .order_by(AuditEvent.id)
        )
        .scalars()
        .all()
    )
    assert len(events) == 2
    assert events[0].detail["short_label"] == [None, "Skills"]
    assert events[1].detail["short_label"] == ["Skills", "Cultural Fit"]


# ── _instrument_label fallback rule ────────────────────────────────────


def test_instrument_label_prefers_short_label(
    client: TestClient, db: Session
) -> None:
    """The audit-summary helper picks short_label first, then trimmed
    description, then the system handle. Verified indirectly by
    setting both fields and reading the audit-event summary on a
    field-add."""
    review_session = _create_session(client, db, code="rae-11l-pref")
    instrument = _default_instrument(db, review_session.id)
    user = review_session.created_by_user

    instruments_service.update_instrument_description(
        db,
        instrument=instrument,
        description="A long-form blurb.",
        actor=user,
    )
    instruments_service.update_short_label(
        db, instrument=instrument, short_label="Skills", actor=user
    )

    # Read the most recent description-update audit summary; it uses
    # `instrument.name` directly (a known outlier in the existing
    # codebase), so just verify _instrument_label itself directly.
    db.refresh(instrument)
    assert instruments_service._instrument_label(instrument) == "Skills"

    # Drop short_label; falls through to description.
    instruments_service.update_short_label(
        db, instrument=instrument, short_label=None, actor=user
    )
    db.refresh(instrument)
    assert (
        instruments_service._instrument_label(instrument)
        == "A long-form blurb."
    )

    # Drop description; falls through to the system handle.
    instruments_service.update_instrument_description(
        db, instrument=instrument, description=None, actor=user
    )
    db.refresh(instrument)
    assert (
        instruments_service._instrument_label(instrument) == instrument.name
    )


# ── Bulk fields-save handler accepts short_label ───────────────────────


def test_bulk_save_accepts_short_label_alongside_description(
    client: TestClient, db: Session
) -> None:
    """The Instruments-page Save click POSTs description + short_label
    in one round-trip; both persist."""
    review_session = _create_session(client, db, code="rae-11l-bulk")
    instrument = _default_instrument(db, review_session.id)

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields/save",
        data={
            "short_label": "Skills",
            "description": "Rate candidates on technical skills.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    db.refresh(instrument)
    assert instrument.short_label == "Skills"
    assert instrument.description == "Rate candidates on technical skills."


def test_bulk_save_short_label_too_long_returns_400(
    client: TestClient, db: Session
) -> None:
    """The HTML5 ``maxlength=32`` attribute catches oversized labels in
    the browser; if a malformed POST slips through, the server-side
    cap returns HTTP 400 as a defensive fallback."""
    review_session = _create_session(client, db, code="rae-11l-toolong")
    instrument = _default_instrument(db, review_session.id)

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields/save",
        data={"short_label": "x" * 33},
        follow_redirects=False,
    )
    assert response.status_code == 400


def test_bulk_save_short_label_lifecycle_gate_when_ready(
    client: TestClient, db: Session
) -> None:
    """`_require_instrument_editable` rejects edits when the session is
    `ready`. Same gate applies to short_label updates."""
    from app.services import session_lifecycle as lifecycle

    review_session = _create_session(client, db, code="rae-11l-ready")
    instrument = _default_instrument(db, review_session.id)
    # Move the session to ready directly; short-circuiting the
    # full activate flow keeps the test focused on the gate.
    review_session.status = "ready"
    instrument.accepting_responses = True
    db.commit()
    assert lifecycle.is_ready(review_session)

    response = client.post(
        f"/operator/sessions/{review_session.id}/instruments/{instrument.id}/fields/save",
        data={"short_label": "Skills"},
        follow_redirects=False,
    )
    assert response.status_code == 409  # _require_instrument_editable


# ── Operator UI: short_label input renders ─────────────────────────────


def test_instruments_page_renders_short_label_input_in_edit_mode(
    client: TestClient, db: Session
) -> None:
    review_session = _create_session(client, db, code="rae-11l-ui-edit")
    instrument = _default_instrument(db, review_session.id)
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments?editing={instrument.id}"
    ).text
    assert (
        f'form="dfsave-{instrument.id}"' in body
    )
    assert 'name="short_label"' in body
    assert 'maxlength="32"' in body


def test_instruments_page_renders_short_label_in_readonly_when_set(
    client: TestClient, db: Session
) -> None:
    review_session = _create_session(client, db, code="rae-11l-ui-set")
    instrument = _default_instrument(db, review_session.id)
    user = review_session.created_by_user
    instruments_service.update_short_label(
        db, instrument=instrument, short_label="Skills", actor=user
    )
    db.commit()

    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    assert 'class="short-label-text"' in body
    assert ">Skills</p>" in body


def test_instruments_page_omits_short_label_in_readonly_when_unset(
    client: TestClient, db: Session
) -> None:
    review_session = _create_session(client, db, code="rae-11l-ui-unset")
    body = client.get(
        f"/operator/sessions/{review_session.id}/instruments"
    ).text
    assert 'class="short-label-text"' not in body
