"""Coverage for the Band 1 "Not set" pill safety gate.

Wave 5 follow-up. Every new instrument starts with all three
Band 1 link pills (Who does the review / Who is being reviewed /
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

from app.db.models import Instrument, ReviewSession, User
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


def test_set_band1_assignment_rules_replaces_owned_touched_slice(
    client: TestClient, db: Session
) -> None:
    """``set_band1_assignment_rules`` owns Link 1 + Link 2 — each
    submit is authoritative for those two bits (the operator can
    cycle a pill back to ``"Not set"``), but Link 3's bit must
    survive unchanged so the sibling ``set_unit_of_review`` writer
    isn't clobbered."""
    review_session = _make_session(client, db, code="touch-replace")
    instrument = _default_instrument(db, review_session.id)
    user = review_session.created_by_user

    # Pre-stamp link3 (the unit-of-review writer's slot) to confirm
    # the band1 writer leaves it alone.
    instrument.band1_touched_links = ["link3"]
    db.flush()

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
    assert instrument.band1_touched_links == ["link1", "link3"]

    # Subsequent submit with link2 only — link1 drops off because
    # the operator cycled it back to "Not set"; link3 stays.
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
    assert instrument.band1_touched_links == ["link2", "link3"]

    # And submit with no touched bits at all — both link1 + link2
    # clear; link3 still survives.
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
        touched_links=set(),
    )
    db.refresh(instrument)
    assert instrument.band1_touched_links == ["link3"]


def test_set_band1_assignment_rules_heals_pre_pr1452_exclude_self_reviews(
    client: TestClient, db: Session
) -> None:
    """A session whose ``SessionRuleSet`` was materialised before
    PR #1452 carries ``exclude_self_reviews=True``. The next Band 1
    save heals the column to ``False`` so self-review pairs
    materialise as Assignment rows on the next Generate."""
    from app.db.models import SessionRuleSet

    review_session = _make_session(client, db, code="self-review-heal")
    instrument = _default_instrument(db, review_session.id)
    user = review_session.created_by_user

    # Simulate a pre-fix materialisation: create the SessionRuleSet
    # with the old default and pin it to the instrument.
    legacy_rule_set = SessionRuleSet(
        session_id=review_session.id,
        name="legacy Band 1",
        description="",
        combinator="ALL_OF",
        exclude_self_reviews=True,
        seed=None,
        rules_json=[
            {
                "id": "link1",
                "kind": "COMPOSITE",
                "enabled": True,
                "op": "AND",
                "rules": [
                    {
                        "id": "link1-r0",
                        "kind": "MATCH",
                        "enabled": True,
                        "predicate": {
                            "field": "reviewer.tag1",
                            "operator": "equals",
                            "operand": "Lead",
                            "case_sensitive": False,
                        },
                    }
                ],
            }
        ],
    )
    db.add(legacy_rule_set)
    db.flush()
    instrument.rule_set_id = legacy_rule_set.id
    db.flush()

    # Operator saves Band 1 — the heal kicks in regardless of
    # whether the rules_json shape changed.
    instruments_service.set_band1_assignment_rules(
        db,
        instrument=instrument,
        link1_mode="filter",
        link1_combinator="AND",
        link1_rules=[
            {
                "field": "reviewer.tag1",
                "op": "IS",
                "operand_value": "Lead",
                "operand_tag": "",
            }
        ],
        link2_mode="all",
        link2_combinator="AND",
        link2_rules=[],
        actor=user,
        touched_links={"link1", "link2"},
    )
    db.refresh(legacy_rule_set)
    assert legacy_rule_set.exclude_self_reviews is False


def test_set_band1_assignment_rules_materialises_rule_set_without_self_review_exclusion(
    client: TestClient, db: Session
) -> None:
    """When the operator's first Band 1 filter rule materialises a
    ``SessionRuleSet``, ``exclude_self_reviews`` lands as False so
    self-review pairs flow through to ``assignments`` rows at
    generate time. The per-instrument Self review toggle on the
    Assignments page owns include / exclude; baking exclusion in
    at the rule-set level would silently disable that toggle."""
    from app.db.models import SessionRuleSet

    review_session = _make_session(client, db, code="self-review-allow")
    instrument = _default_instrument(db, review_session.id)
    user = review_session.created_by_user

    instruments_service.set_band1_assignment_rules(
        db,
        instrument=instrument,
        link1_mode="filter",
        link1_combinator="AND",
        link1_rules=[
            {
                "field": "reviewer.tag1",
                "op": "IS",
                "operand_value": "Lead",
                "operand_tag": "",
            }
        ],
        link2_mode="all",
        link2_combinator="AND",
        link2_rules=[],
        actor=user,
        touched_links={"link1", "link2"},
    )
    db.refresh(instrument)
    assert instrument.rule_set_id is not None
    rule_set = db.get(SessionRuleSet, instrument.rule_set_id)
    assert rule_set is not None
    assert rule_set.exclude_self_reviews is False


def test_set_unit_of_review_toggles_link3_touched_bit(
    client: TestClient, db: Session
) -> None:
    """Link 3's writer (``set_unit_of_review``) owns just the
    ``link3`` bit and flips it both ways — ``touched=True`` adds,
    ``touched=False`` removes — without touching the Link 1 / 2
    slice."""
    review_session = _make_session(client, db, code="link3-toggle")
    instrument = _default_instrument(db, review_session.id)
    user = review_session.created_by_user

    instrument.band1_touched_links = ["link1"]
    db.flush()

    instruments_service.set_unit_of_review(
        db,
        instrument=instrument,
        mode="individual",
        boundary_pairs=[],
        actor=user,
        touched=True,
    )
    db.refresh(instrument)
    assert instrument.band1_touched_links == ["link1", "link3"]

    # Operator cycled the Link 3 pill back to "Not set" — touched
    # flips to False and link3 drops off, link1 survives.
    instruments_service.set_unit_of_review(
        db,
        instrument=instrument,
        mode="individual",
        boundary_pairs=[],
        actor=user,
        touched=False,
    )
    db.refresh(instrument)
    assert instrument.band1_touched_links == ["link1"]


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


def test_parse_band1_form_pads_missing_field_when_tag_options_empty() -> None:
    """Browsers omit empty <select>s from form submissions. When a
    link's tag_options is empty (no tags configured for that side),
    the ``{link}_field`` select renders with zero options and isn't
    posted, while the sibling op / operand_value / operand_tag
    hidden inputs still submit one entry each. The parser pads
    ``fields`` so the arrays realign; the service's blank-field
    guard then treats it as a no-op rule.
    """
    from starlette.datastructures import FormData

    form = FormData(
        [
            ("link1_mode", "all"),
            ("link2_mode", "all"),
            # No link1_field — empty select didn't submit.
            ("link1_op", "IS"),
            ("link1_operand_value", ""),
            ("link1_operand_tag", ""),
            # link2 fully populated (sanity).
            ("link2_op", "IS"),
            ("link2_operand_value", ""),
            ("link2_operand_tag", ""),
        ]
    )
    parsed = instruments_service.parse_band1_form(form)
    assert len(parsed["link1_rules"]) == 1
    assert parsed["link1_rules"][0]["field"] == ""
    assert parsed["link1_rules"][0]["op"] == "IS"


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


# --------------------------------------------------------------------------- #
# configured_counts + the status-row pill (2026-09-07)
# --------------------------------------------------------------------------- #


def test_configured_counts_agrees_with_is_configured_instrument_by_instrument(
    client: TestClient, db: Session
) -> None:
    """The batched count and the per-instrument predicate answer the same
    question, so they must never disagree.

    They are two implementations of one rule — a visible response field
    plus all three Band 1 links — which is exactly the shape that drifts.
    `has_unconfigured` now reads its answer from `configured_counts`, so
    this is the pin for all three.
    """
    review_session = _make_session(client, db, code="counts-agree")
    first = _default_instrument(db, review_session.id)

    second = Instrument(session_id=review_session.id, name="Second")
    db.add(second)
    db.flush()

    for touched_first, touched_second in (
        (None, None),
        (["link1", "link2", "link3"], None),
        (["link1", "link2", "link3"], ["link1", "link2", "link3"]),
    ):
        first.band1_touched_links = touched_first
        second.band1_touched_links = touched_second
        db.flush()

        total, configured = instruments_service.configured_counts(
            db, review_session.id
        )
        one_by_one = sum(
            1
            for inst in (first, second)
            if instruments_service.is_configured(db, inst)
        )

        assert total == 2
        assert configured == one_by_one
        assert instruments_service.has_unconfigured(db, review_session.id) is (
            configured < total
        )


def test_configured_counts_is_zero_zero_without_instruments(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db, code="counts-empty")
    db.delete(_default_instrument(db, review_session.id))
    db.flush()

    assert instruments_service.configured_counts(db, review_session.id) == (0, 0)


def test_status_row_reports_instruments_as_configured_over_total(
    client: TestClient, db: Session
) -> None:
    """The pill reports both numbers, done-first, and takes its tint from
    whether they match.

    Until 2026-09-07 it showed the bare total, so an instrument with no
    visible response field — one a reviewer would meet as an empty page —
    counted exactly like a finished one, and the row read done for a
    session that could not be answered.

    Order is `configured / total`, matching the Responses pill in the same
    row (`3 drafts / 5`). The first cut of this shipped total-first and
    read backwards as a fraction: `5 / 3` is not a proportion anyone can
    complete, so the direction is asserted, not just the pair of numbers.
    """
    review_session = _make_session(client, db, code="pill-two-numbers")
    instrument = _default_instrument(db, review_session.id)
    # Created through the service, not the model, so it is seeded with the
    # default response fields. A bare `Instrument(...)` has none, and
    # `is_configured` would then refuse it however many Band 1 links are
    # touched — the test could never reach its all-configured case.
    second = instruments_service.create_instrument(
        db,
        review_session=review_session,
        actor=db.execute(select(User)).scalars().first(),
    )
    db.flush()

    url = f"/operator/sessions/{review_session.id}"

    # Untouched Band 1 links on both: 0 of 2 configured -> amber. Two
    # instruments rather than one so the two numbers differ and the order
    # is actually pinned.
    body = " ".join(client.get(url).text.split())
    assert '<span class="pill pill-warning">0 / 2</span>' in body

    instrument.band1_touched_links = ["link1", "link2", "link3"]
    db.flush()

    body = " ".join(client.get(url).text.split())
    assert '<span class="pill pill-warning">1 / 2</span>' in body

    second.band1_touched_links = ["link1", "link2", "link3"]
    db.flush()

    # All configured -> blue.
    body = " ".join(client.get(url).text.split())
    assert '<span class="pill pill-info">2 / 2</span>' in body


def test_status_row_reports_no_instruments_as_none(
    client: TestClient, db: Session
) -> None:
    """Zero reads `none` like Reviewers and Reviewees, not "0 / 0".

    Instruments are required to validate, so it takes the same warning
    tint those two use rather than inventing a third treatment.
    """
    review_session = _make_session(client, db, code="pill-no-instruments")
    db.delete(_default_instrument(db, review_session.id))
    db.flush()

    body = " ".join(client.get(f"/operator/sessions/{review_session.id}").text.split())
    assert "Instruments: <span class=\"pill pill-warning\">none</span>" in body
