"""Coverage for the Band 1 "Not set" pill safety gate.

Wave 5 follow-up. Every new instrument starts with all three
Band 1 link pills (Pool of reviewers / Pool of those reviewed /
Unit of review) in the ``"Not set"`` state. Until the operator
clicks each pill at least once, the instrument is considered
unconfigured by the workflow card — preventing operators from
silently shipping the implicit Full Matrix default that the
Wave 5 RuleSet collapse enabled.

The gate keys off ``Instrument.band1_touched_links`` (a sticky
JSON list); the bulk-save form carries one ``{link}_touched``
hidden input per link, and the per-pill JS toggle flips it to
``"true"`` on first click and never back.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, ReviewSession
from app.services import instruments as instruments_service
from app.web import views


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": f"NS-{code}", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _default_instrument(db: Session, session_id: int) -> Instrument:
    return db.execute(
        select(Instrument).where(Instrument.session_id == session_id)
    ).scalar_one()


# --------------------------------------------------------------------------- #
# is_configured contract
# --------------------------------------------------------------------------- #


def test_default_instrument_is_unconfigured_until_band1_touched(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="def-untouched")
    instrument = _default_instrument(db, review_session.id)
    # Bare default ships with visible Rating + Comments response
    # fields but no Band 1 pills touched.
    assert instrument.band1_touched_links in (None, [])
    assert instruments_service.is_configured(db, instrument) is False
    assert instruments_service.has_unconfigured(db, review_session.id) is True


def test_is_configured_requires_all_three_band1_links_touched(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="three-of-three")
    instrument = _default_instrument(db, review_session.id)

    for partial in (["link1"], ["link1", "link2"], ["link2", "link3"]):
        instrument.band1_touched_links = list(partial)
        db.flush()
        assert instruments_service.is_configured(db, instrument) is False, (
            f"partial touched set {partial} should not flip is_configured"
        )

    instrument.band1_touched_links = ["link1", "link2", "link3"]
    db.flush()
    assert instruments_service.is_configured(db, instrument) is True
    assert instruments_service.has_unconfigured(db, review_session.id) is False


# --------------------------------------------------------------------------- #
# Service stickiness
# --------------------------------------------------------------------------- #


def test_set_band1_assignment_rules_unions_touched_links_stickily(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="sticky-touch")
    instrument = _default_instrument(db, review_session.id)
    user = review_session.created_by_user

    instruments_service.set_band1_assignment_rules(
        db,
        instrument=instrument,
        link1_mode="all",
        link1_combinator="AND",
        link1_rules=[],
        link2_mode="all",
        link2_combinator="AND",
        link2_rules=[],
        actor=user,
        touched_links={"link1"},
    )
    db.refresh(instrument)
    assert instrument.band1_touched_links == ["link1"]

    # A second call that only re-touches link2 must NOT un-touch link1.
    instruments_service.set_band1_assignment_rules(
        db,
        instrument=instrument,
        link1_mode="all",
        link1_combinator="AND",
        link1_rules=[],
        link2_mode="all",
        link2_combinator="AND",
        link2_rules=[],
        actor=user,
        touched_links={"link2"},
    )
    db.refresh(instrument)
    assert instrument.band1_touched_links == ["link1", "link2"]


def test_set_unit_of_review_marks_link3_touched(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="link3-touch")
    instrument = _default_instrument(db, review_session.id)
    user = review_session.created_by_user

    instruments_service.set_unit_of_review(
        db,
        instrument=instrument,
        mode="individual",
        boundary_pairs=[],
        actor=user,
        touched=True,
    )
    db.refresh(instrument)
    assert "link3" in (instrument.band1_touched_links or [])


# --------------------------------------------------------------------------- #
# Form parser
# --------------------------------------------------------------------------- #


def test_parse_band1_form_picks_up_touched_flags() -> None:
    from starlette.datastructures import FormData

    form = FormData(
        [
            ("link1_mode", "all"),
            ("link2_mode", "all"),
            ("link1_touched", "true"),
            ("link2_touched", "false"),
        ]
    )
    parsed = instruments_service.parse_band1_form(form)
    assert parsed["touched_links"] == {"link1"}


def test_parse_link3_form_returns_touched_bit() -> None:
    from starlette.datastructures import FormData

    form_touched = FormData(
        [("link3_mode", "individual"), ("link3_touched", "true")]
    )
    mode, pairs, touched = instruments_service.parse_link3_form(form_touched)
    assert mode == "individual"
    assert pairs == []
    assert touched is True

    form_untouched = FormData([("link3_mode", "individual")])
    _, _, touched = instruments_service.parse_link3_form(form_untouched)
    assert touched is False


# --------------------------------------------------------------------------- #
# Workflow card surfacing
# --------------------------------------------------------------------------- #


def test_workflow_card_surfaces_untouched_band1_as_setup_empty(
    client: TestClient, db: Session
) -> None:
    """Wire-the-rosters but-leave-Band-1-untouched session: the
    workflow card must surface ``instruments_configured_ok=False``
    and stay in the Empty Setup state, forcing the operator to
    click each Band 1 pill before proceeding."""
    review_session = _make_session(client, db, code="ws-untouched")

    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nA,a@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nC,c@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )

    ctx = views.build_workflow_card_context(
        db, review_session, return_to="assignments"
    )
    assert ctx["setup_checklist"]["reviewers_ok"] is True
    assert ctx["setup_checklist"]["reviewees_ok"] is True
    assert ctx["setup_checklist"]["instruments_configured_ok"] is False
    assert ctx["is_setup_empty"] is True

    # Marking the default instrument's Band 1 touched flips the gate.
    instrument = _default_instrument(db, review_session.id)
    instrument.band1_touched_links = ["link1", "link2", "link3"]
    db.flush()
    db.commit()

    ctx = views.build_workflow_card_context(
        db, review_session, return_to="assignments"
    )
    assert ctx["setup_checklist"]["instruments_configured_ok"] is True
    assert ctx["is_setup_empty"] is False


# --------------------------------------------------------------------------- #
# Template render
# --------------------------------------------------------------------------- #


def test_instruments_page_renders_not_set_pill_for_default(
    client: TestClient, db: Session
) -> None:
    """The Instruments page renders each Band 1 link pill as
    ``"Not set"`` for an untouched default instrument and emits
    the hidden ``{link}_touched=false`` inputs the bulk-save form
    needs."""
    review_session = _make_session(client, db, code="render-not-set")
    instrument = _default_instrument(db, review_session.id)
    body = client.get(
        f"/operator/sessions/{review_session.id}"
        f"/instruments?editing={instrument.id}"
    ).text
    flat = " ".join(body.split())
    # All three Band 1 pills render the "not_set" data-attr.
    assert flat.count('data-new-model-rule-mode="not_set"') == 2
    assert 'data-new-model-unit-mode="not_set"' in flat
    # Each link carries a touched hidden input wired into the
    # per-instrument bulk-save form.
    assert (
        'name="link1_touched" data-new-model-touched-input value="false"'
        in flat
    )
    assert (
        'name="link2_touched" data-new-model-touched-input value="false"'
        in flat
    )
    assert (
        'name="link3_touched" data-new-model-link3-touched-input value="false"'
        in flat
    )
    # The visible pill label reads "Not set" three times.
    assert flat.count(">Not set</span>") >= 3
