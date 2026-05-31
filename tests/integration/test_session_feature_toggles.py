"""Integration coverage for the per-session feature toggles
(``sessions.relationships_enabled`` / ``.observers_enabled``)
authored on the Session Edit Details page's User interface
settings card.

See ``guide/participant_model_upgrade.md`` §3.8 +
``guide/participant_model_prep.md`` row W6.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Relationship, ReviewSession, Reviewer, Reviewee


def _make_session(
    client: TestClient, db: Session, code: str = "feat-toggle"
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "FT", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _submit_edit(
    client: TestClient,
    review_session: ReviewSession,
    **overrides: object,
) -> None:
    data: dict[str, object] = {
        "name": review_session.name,
        "code": review_session.code,
        "description": review_session.description or "",
        "display_timezone": "",
    }
    data.update(overrides)
    response = client.post(
        f"/operator/sessions/{review_session.id}/edit",
        data=data,
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text


# ── Defaults + persistence ───────────────────────────────────────────


def test_session_defaults_both_toggles_to_false(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ft-default")
    assert review_session.relationships_enabled is False
    assert review_session.observers_enabled is False


def test_form_persists_relationships_enabled_true(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ft-relon")
    _submit_edit(client, review_session, relationships_enabled="true")
    db.refresh(review_session)
    assert review_session.relationships_enabled is True
    assert review_session.observers_enabled is False


def test_form_omission_persists_false(
    client: TestClient, db: Session
) -> None:
    # Start with both on, then submit without the fields — they
    # should flip back to False (HTML checkbox absence semantics).
    review_session = _make_session(client, db, code="ft-omit")
    review_session.relationships_enabled = True
    review_session.observers_enabled = True
    db.commit()
    _submit_edit(client, review_session)  # neither field in payload
    db.refresh(review_session)
    assert review_session.relationships_enabled is False
    assert review_session.observers_enabled is False


def test_form_persists_observers_enabled_true(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ft-obson")
    _submit_edit(client, review_session, observers_enabled="true")
    db.refresh(review_session)
    assert review_session.observers_enabled is True


# ── Audit ─────────────────────────────────────────────────────────────


def _audit_events(
    db: Session, session_id: int, event_type: str
) -> list[AuditEvent]:
    return list(
        db.execute(
            select(AuditEvent)
            .where(
                AuditEvent.session_id == session_id,
                AuditEvent.event_type == event_type,
            )
            .order_by(AuditEvent.id)
        ).scalars()
    )


def test_feature_toggled_audit_fires_on_change(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ft-audit")
    _submit_edit(client, review_session, relationships_enabled="true")
    events = _audit_events(db, review_session.id, "session.feature_toggled")
    assert len(events) == 1
    changes = events[0].detail.get("changes", {})
    assert "relationships_enabled" in changes
    assert changes["relationships_enabled"] == [False, True]


def test_feature_toggled_audit_silent_when_no_change(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ft-noop")
    # No toggle in payload → defaults to False → matches current → no event.
    _submit_edit(client, review_session)
    events = _audit_events(db, review_session.id, "session.feature_toggled")
    assert events == []


def test_feature_toggled_audit_carries_both_flag_diffs(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ft-both")
    _submit_edit(
        client,
        review_session,
        relationships_enabled="true",
        observers_enabled="true",
    )
    events = _audit_events(db, review_session.id, "session.feature_toggled")
    assert len(events) == 1
    changes = events[0].detail.get("changes", {})
    assert set(changes.keys()) == {
        "relationships_enabled",
        "observers_enabled",
    }


# ── Lock-on-data ──────────────────────────────────────────────────────


def _seed_one_relationship(
    db: Session, review_session: ReviewSession
) -> None:
    reviewer = Reviewer(
        session_id=review_session.id,
        name="R",
        email="r@example.org",
    )
    reviewee = Reviewee(
        session_id=review_session.id,
        name="E",
        email_or_identifier="e@example.org",
    )
    db.add_all([reviewer, reviewee])
    db.flush()
    db.add(
        Relationship(
            session_id=review_session.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
        )
    )
    db.commit()


def test_lock_on_data_silent_noop_on_true_to_false(
    client: TestClient, db: Session
) -> None:
    """When relationship rows exist, an attempt to flip
    relationships_enabled True→False is silently ignored — the
    column stays True so data doesn't orphan."""
    review_session = _make_session(client, db, code="ft-lock")
    review_session.relationships_enabled = True
    db.commit()
    _seed_one_relationship(db, review_session)

    # Submit edit form WITHOUT the toggle field — equivalent to
    # the disabled checkbox not being serialized by the browser.
    _submit_edit(client, review_session)
    db.refresh(review_session)
    assert review_session.relationships_enabled is True


def test_lock_on_data_renders_disabled_checkbox(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ft-lock-ui")
    review_session.relationships_enabled = True
    db.commit()
    _seed_one_relationship(db, review_session)

    body = client.get(
        f"/operator/sessions/{review_session.id}/edit"
    ).text
    assert 'name="relationships_enabled"' in body
    # The disabled attribute appears on the relationships checkbox.
    relationships_chunk = body.split(
        'name="relationships_enabled"', 1
    )[1].split("</label>", 1)[0]
    assert "disabled" in relationships_chunk
    assert "Has configured data" in body


# ── Nav tab visibility ────────────────────────────────────────────────


def test_relationships_nav_tab_hidden_when_flag_off(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ft-nav-off")
    body = client.get(
        f"/operator/sessions/{review_session.id}"
    ).text
    assert (
        f'href="/operator/sessions/{review_session.id}/relationships"'
        not in body
    )


def test_relationships_nav_tab_visible_when_flag_on(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ft-nav-on")
    review_session.relationships_enabled = True
    db.commit()
    body = client.get(
        f"/operator/sessions/{review_session.id}"
    ).text
    assert (
        f'href="/operator/sessions/{review_session.id}/relationships"'
        in body
    )


# ── Route guard ───────────────────────────────────────────────────────


def test_relationships_route_404_when_flag_off(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ft-route-off")
    response = client.get(
        f"/operator/sessions/{review_session.id}/relationships"
    )
    assert response.status_code == 404


def test_relationships_route_200_when_flag_on(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ft-route-on")
    review_session.relationships_enabled = True
    db.commit()
    response = client.get(
        f"/operator/sessions/{review_session.id}/relationships"
    )
    assert response.status_code == 200


# ── Edit page surface ─────────────────────────────────────────────────


def test_edit_page_renders_user_interface_settings_card(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="ft-ui")
    body = client.get(
        f"/operator/sessions/{review_session.id}/edit"
    ).text
    assert "User interface settings" in body
    assert 'name="relationships_enabled"' in body
    assert 'name="observers_enabled"' in body
    # Both unchecked by default.
    rel_chunk = body.split(
        'name="relationships_enabled"', 1
    )[1].split(">", 1)[0]
    assert "checked" not in rel_chunk
    obs_chunk = body.split(
        'name="observers_enabled"', 1
    )[1].split(">", 1)[0]
    assert "checked" not in obs_chunk
