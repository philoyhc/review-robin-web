"""Coverage for Segment 15B Slice 2a — per-instrument Assignment
Rule picker on the Instruments page.

PIN-only semantics: Save persists ``instruments.rule_set_id`` and
fires ``instrument.rule_pinned``. It does NOT touch ``Assignment``
rows or emit ``assignments.generated`` — materialisation belongs to
the explicit Generate surfaces (Slice 3a / Slice 4).
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    AuditEvent,
    Instrument,
    ReviewSession,
    SessionRuleSet,
)


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Picker", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _add_session_rule_set(
    db: Session, *, review_session: ReviewSession, name: str
) -> SessionRuleSet:
    row = SessionRuleSet(
        session_id=review_session.id,
        name=name,
        description=f"{name} rule",
        combinator="ALL_OF",
        exclude_self_reviews=False,
        seed=None,
        rules_json=[],
        is_seeded=False,
    )
    db.add(row)
    db.flush()
    return row


def _index_url(session_id: int) -> str:
    return f"/operator/sessions/{session_id}/instruments"


def _save_url(session_id: int, instrument_id: int) -> str:
    return (
        f"/operator/sessions/{session_id}"
        f"/instruments/{instrument_id}/fields/save"
    )


def test_picker_disabled_when_card_locked(
    client: TestClient, db: Session
) -> None:
    """Default render: the picker `<select>` carries the ``disabled``
    attribute since the card is locked (no ``?editing`` query param)."""

    review_session = _make_session(client, db, code="pick-lock")
    _add_session_rule_set(db, review_session=review_session, name="My Rule")

    body = client.get(_index_url(review_session.id)).text

    [instrument] = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == review_session.id)
        ).scalars()
    )
    section_start = f'id="instrument-{instrument.id}-rule-picker"'
    assert section_start in body
    # Locate the picker `<select>` and confirm the ``disabled`` flag.
    picker_chunk = body.split(section_start, 1)[1].split("</select>", 1)[0]
    assert 'data-instrument-rule-picker="' + str(instrument.id) + '"' in picker_chunk
    assert "disabled" in picker_chunk


def test_picker_enabled_in_edit_mode(
    client: TestClient, db: Session
) -> None:
    """When the card is in edit mode (``?editing={id}``), the
    `<select>` no longer carries ``disabled``."""

    review_session = _make_session(client, db, code="pick-edit")
    _add_session_rule_set(db, review_session=review_session, name="My Rule")
    [instrument] = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == review_session.id)
        ).scalars()
    )

    body = client.get(
        _index_url(review_session.id) + f"?editing={instrument.id}"
    ).text

    section = body.split(
        f'id="instrument-{instrument.id}-rule-picker"', 1
    )[1].split("</select>", 1)[0]
    assert (
        'data-instrument-rule-picker="' + str(instrument.id) + '"' in section
    )
    assert "disabled" not in section


def test_save_persists_rule_set_id_and_emits_pin_event(
    client: TestClient, db: Session
) -> None:
    """Posting the bulk-save form with ``rule_set_id=<id>`` writes
    the column and fires ``instrument.rule_pinned`` with the
    before/after ``changes`` envelope."""

    review_session = _make_session(client, db, code="pick-save")
    rule_set = _add_session_rule_set(
        db, review_session=review_session, name="My Rule"
    )
    [instrument] = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == review_session.id)
        ).scalars()
    )
    assert instrument.rule_set_id is None

    response = client.post(
        _save_url(review_session.id, instrument.id),
        data={"rule_set_id": str(rule_set.id)},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    db.refresh(instrument)
    assert instrument.rule_set_id == rule_set.id

    event = db.execute(
        select(AuditEvent)
        .where(
            AuditEvent.session_id == review_session.id,
            AuditEvent.event_type == "instrument.rule_pinned",
        )
    ).scalars().one()
    detail = event.detail or {}
    assert detail["refs"]["instrument_id"] == instrument.id
    assert detail["changes"]["rule_set_id"] == [None, rule_set.id]


def test_save_with_empty_rule_set_id_clears_pin(
    client: TestClient, db: Session
) -> None:
    """Posting an empty string for ``rule_set_id`` clears the pin
    back to NULL (the "— No rule —" sentinel)."""

    review_session = _make_session(client, db, code="pick-clear")
    rule_set = _add_session_rule_set(
        db, review_session=review_session, name="My Rule"
    )
    [instrument] = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == review_session.id)
        ).scalars()
    )
    instrument.rule_set_id = rule_set.id
    db.flush()
    db.commit()

    response = client.post(
        _save_url(review_session.id, instrument.id),
        data={"rule_set_id": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303

    db.refresh(instrument)
    assert instrument.rule_set_id is None

    events = list(
        db.execute(
            select(AuditEvent)
            .where(
                AuditEvent.session_id == review_session.id,
                AuditEvent.event_type == "instrument.rule_pinned",
            )
            .order_by(AuditEvent.id)
        ).scalars()
    )
    assert events[-1].detail["changes"]["rule_set_id"] == [rule_set.id, None]


def test_save_no_op_skips_event(client: TestClient, db: Session) -> None:
    """Re-saving with the same value (or NULL on an already-NULL
    pin) does not fire a new ``instrument.rule_pinned`` event."""

    review_session = _make_session(client, db, code="pick-noop")
    _add_session_rule_set(db, review_session=review_session, name="My Rule")
    [instrument] = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == review_session.id)
        ).scalars()
    )
    assert instrument.rule_set_id is None

    client.post(
        _save_url(review_session.id, instrument.id),
        data={"rule_set_id": ""},
        follow_redirects=False,
    )

    pin_events = list(
        db.execute(
            select(AuditEvent).where(
                AuditEvent.session_id == review_session.id,
                AuditEvent.event_type == "instrument.rule_pinned",
            )
        ).scalars()
    )
    assert pin_events == []


def test_save_does_not_touch_assignments(
    client: TestClient, db: Session
) -> None:
    """PIN-only contract: Save writes the column but does NOT call
    ``replace_assignments`` — no ``Assignment`` rows appear and no
    ``assignments.generated`` event fires."""

    review_session = _make_session(client, db, code="pick-no-mat")
    rule_set = _add_session_rule_set(
        db, review_session=review_session, name="My Rule"
    )
    [instrument] = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == review_session.id)
        ).scalars()
    )

    client.post(
        _save_url(review_session.id, instrument.id),
        data={"rule_set_id": str(rule_set.id)},
        follow_redirects=False,
    )

    assignment_rows = list(
        db.execute(
            select(Assignment).where(Assignment.session_id == review_session.id)
        ).scalars()
    )
    assert assignment_rows == []
    gen_events = list(
        db.execute(
            select(AuditEvent).where(
                AuditEvent.session_id == review_session.id,
                AuditEvent.event_type == "assignments.generated",
            )
        ).scalars()
    )
    assert gen_events == []


def test_cross_session_rule_set_id_rejected(
    client: TestClient, db: Session
) -> None:
    """Posting a ``rule_set_id`` belonging to a different session
    yields 400 — the service helper validates same-session FK
    affinity before pinning."""

    session_a = _make_session(client, db, code="pick-a")
    session_b = _make_session(client, db, code="pick-b")
    rule_set_b = _add_session_rule_set(
        db, review_session=session_b, name="B-Rule"
    )
    [instrument_a] = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == session_a.id)
        ).scalars()
    )

    response = client.post(
        _save_url(session_a.id, instrument_a.id),
        data={"rule_set_id": str(rule_set_b.id)},
        follow_redirects=False,
    )
    assert response.status_code == 400

    db.refresh(instrument_a)
    assert instrument_a.rule_set_id is None


def test_open_rule_builder_threads_instrument_id(
    client: TestClient, db: Session
) -> None:
    """The Open Rule Builder button on each card links to the
    editor with ``instrument_id=<id>`` so the editor's back-link
    returns to the Instruments page anchored at that card."""

    review_session = _make_session(client, db, code="pick-ob")
    rule_set = _add_session_rule_set(
        db, review_session=review_session, name="My Rule"
    )
    [instrument] = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == review_session.id)
        ).scalars()
    )
    instrument.rule_set_id = rule_set.id
    db.flush()
    db.commit()

    body = client.get(_index_url(review_session.id)).text
    # The Rule Builder button carries instrument_id and the
    # currently-pinned rule_set_id as query params.
    assert f"instrument_id={instrument.id}" in body
    assert f"rule_set_id={rule_set.id}" in body
    # The editor itself renders "Back to Instruments" instead of the
    # default "Back to Assignments" when ``instrument_id`` is set.
    editor_body = client.get(
        f"/operator/sessions/{review_session.id}/assignments"
        f"/rule-based-editor?instrument_id={instrument.id}"
    ).text
    assert "Back to Instruments" in editor_body
    assert "Back to Assignments" not in editor_body


def test_picker_options_carry_no_eligibility_count(
    client: TestClient, db: Session
) -> None:
    """The dropdown `<option>` rows carry no per-option eligibility
    count — the rule engine is run only for a rule actually pinned
    to an instrument. An instrument with no rule pinned shows "--"
    for its eligible-pair count, not a number."""

    review_session = _make_session(client, db, code="pick-elig")
    _add_session_rule_set(db, review_session=review_session, name="My Rule")
    [instrument] = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == review_session.id)
        ).scalars()
    )

    body = client.get(_index_url(review_session.id)).text
    section = body.split(
        f'id="instrument-{instrument.id}-rule-picker"', 1
    )[1].split("Open Rule Builder", 1)[0]
    # No per-option count attribute anywhere in the picker.
    assert "data-eligible-pairs" not in section
    # Unpinned instrument → "—" rather than a number (consistent
    # with the Assignments-page status block).
    pill = section.split(
        f'data-instrument-rule-picker-count="{instrument.id}"', 1
    )[1].split("</span>", 1)[0]
    assert "—" in pill


def test_picker_count_shows_number_once_a_rule_is_pinned(
    client: TestClient, db: Session
) -> None:
    """Once a rule is pinned to the instrument the eligible-pair
    count renders as a number (0 here — empty rosters), not "--"."""

    review_session = _make_session(client, db, code="pick-pinned")
    rule = _add_session_rule_set(
        db, review_session=review_session, name="My Rule"
    )
    [instrument] = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == review_session.id)
        ).scalars()
    )
    instrument.rule_set_id = rule.id
    db.commit()

    body = client.get(_index_url(review_session.id)).text
    section = body.split(
        f'id="instrument-{instrument.id}-rule-picker"', 1
    )[1].split("Open Rule Builder", 1)[0]
    pill = section.split(
        f'data-instrument-rule-picker-count="{instrument.id}"', 1
    )[1].split("</span>", 1)[0]
    assert "—" not in pill
    assert "0" in pill


def test_picker_renders_no_rule_sets_state(
    client: TestClient, db: Session
) -> None:
    """When no ``session_rule_sets`` rows exist (test sessions are
    created without auto-copy seeded entries — fresh client doesn't
    have any), the card shows the empty-pool message + a Rule
    Builder deep-link to the "Create new" surface."""

    review_session = _make_session(client, db, code="pick-empty")
    # Delete any auto-copied/seeded rule sets so the picker pool is
    # truly empty for this assertion.
    db.execute(
        SessionRuleSet.__table__.delete().where(
            SessionRuleSet.session_id == review_session.id
        )
    )
    db.commit()
    [instrument] = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == review_session.id)
        ).scalars()
    )

    body = client.get(_index_url(review_session.id)).text
    assert "No RuleSets visible" in body
    assert f"new=1&amp;instrument_id={instrument.id}" in body


def test_picker_save_invalidates_validated_session(
    client: TestClient, db: Session
) -> None:
    """Mirroring the existing instrument-card mutators: pinning a
    rule on a validated session flips status back to draft so the
    operator re-validates before generating."""

    from app.services import session_lifecycle as lifecycle

    review_session = _make_session(client, db, code="pick-val")
    rule_set = _add_session_rule_set(
        db, review_session=review_session, name="R"
    )
    [instrument] = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == review_session.id)
        ).scalars()
    )
    review_session.status = lifecycle.SessionStatus.validated.value
    db.flush()
    db.commit()

    client.post(
        _save_url(review_session.id, instrument.id),
        data={"rule_set_id": str(rule_set.id)},
        follow_redirects=False,
    )

    db.refresh(review_session)
    assert review_session.status == "draft"


def test_eligibility_cache_skips_engine_on_unchanged_inputs(
    client: TestClient, db: Session, monkeypatch
) -> None:
    """`evaluate_session_rule_eligibility` caches the per-rule count
    on the `session_rule_sets` row: a second call with unchanged
    rosters + rule returns the cached count without re-running the
    rule engine; a roster change forces a recompute."""
    from app.db.models import Reviewer, Reviewee
    from app.services.rules import engine as engine_mod, session_library

    review_session = _make_session(client, db, code="elig-cache")
    rule = _add_session_rule_set(
        db, review_session=review_session, name="My Rule"
    )
    [instrument] = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == review_session.id)
        ).scalars()
    )
    instrument.rule_set_id = rule.id
    db.add(Reviewer(session_id=review_session.id, name="R", email="r@x.edu"))
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="E",
            email_or_identifier="e@x.edu",
        )
    )
    db.commit()

    calls: list[int] = []
    real_evaluate = engine_mod.evaluate

    def _counting(*args: object, **kwargs: object) -> object:
        calls.append(1)
        return real_evaluate(*args, **kwargs)

    monkeypatch.setattr(engine_mod, "evaluate", _counting)

    first = session_library.evaluate_session_rule_eligibility(
        db, review_session
    )
    assert len(calls) == 1  # cold compute
    assert rule.id in first

    second = session_library.evaluate_session_rule_eligibility(
        db, review_session
    )
    assert len(calls) == 1  # cache hit — engine not re-run
    assert second == first

    # A roster change invalidates the cache.
    db.add(
        Reviewer(session_id=review_session.id, name="R2", email="r2@x.edu")
    )
    db.commit()
    session_library.evaluate_session_rule_eligibility(db, review_session)
    assert len(calls) == 2  # recomputed
