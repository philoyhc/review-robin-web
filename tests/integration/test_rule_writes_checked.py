"""Rule and Band 2 writes are checked before they are stored.

Findings S2 and E1 (``guide/findings_2026-10-16_bugs.md``): the Settings
import stored ``rules_json`` and ``band2_state`` unchecked, and the Band 1
card offered and stored a rule the engine rejects. In each case the stored
value made the Instruments, Assignments or Validate page answer 500 until
it was replaced. The writers now refuse the value instead.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    Relationship,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionRuleSet,
    User,
)
from app.schemas.rules import rules_payload_error
from app.services import assignments
from app.services.instruments import decode_band1_state, ensure_default_instrument
from app.services.instruments._band1 import keeps_pairs_by_pair_tag
from app.services.session_config_io import (
    Row,
    apply_session_config,
    serialize_session_config,
)


def _match(field: str, operator: str, operand: str) -> dict[str, object]:
    return {
        "id": "r1",
        "enabled": True,
        "kind": "MATCH",
        "predicate": {
            "field": field,
            "operator": operator,
            "operand": operand,
            "case_sensitive": False,
        },
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"x": 1},
        [1],
        [{"kind": "NOPE"}],
        [_match("pair_context.tag1", "same_as", "pair_context.tag2")],
        [_match("reviewee.tag1", "equals", "A"), _match("reviewee.tag2", "equals", "B")],
    ],
    ids=["object", "not-a-rule", "unknown-kind", "same-side", "duplicate-ids"],
)
def test_rules_payload_error_names_what_the_reader_refuses(payload: object) -> None:
    assert rules_payload_error(payload) is not None


def test_rules_payload_error_passes_what_the_reader_loads() -> None:
    assert rules_payload_error([]) is None
    assert rules_payload_error([_match("reviewee.tag1", "same_as", "reviewer.tag1")]) is None


# --- Band 1 card -----------------------------------------------------------


def _session_with_tags(db: Session, client: TestClient, code: str) -> tuple[ReviewSession, Instrument]:
    assert (
        client.post(
            "/operator/sessions", data={"name": "S", "code": code}, follow_redirects=False
        ).status_code
        == 303
    )
    session = db.execute(select(ReviewSession).where(ReviewSession.code == code)).scalar_one()
    reviewer = Reviewer(session_id=session.id, name="R", email="r@example.edu", tag_1="A")
    reviewee = Reviewee(
        session_id=session.id, name="E", email_or_identifier="e@example.edu", tag_1="A"
    )
    db.add_all([reviewer, reviewee])
    db.flush()
    db.add(
        Relationship(
            session_id=session.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
            tag_1="P",
            tag_2="P",
        )
    )
    db.commit()
    instrument = ensure_default_instrument(db, session)
    db.commit()
    return session, instrument


def _link2_form(field: str, operand: str) -> dict[str, str]:
    return {
        "link1_mode": "all",
        "link1_combinator": "AND",
        "link1_touched": "true",
        "link2_mode": "filter",
        "link2_combinator": "AND",
        "link2_field": field,
        "link2_op": "IS THE SAME AS",
        "link2_operand_value": "",
        "link2_operand_tag": operand,
        "link2_touched": "true",
        "link3_mode": "individual",
        "link3_touched": "true",
    }


def _stored_rules(db: Session, instrument_id: int) -> list[object] | None:
    db.expire_all()
    instrument = db.get(Instrument, instrument_id)
    if instrument.rule_set_id is None:
        return None
    return db.get(SessionRuleSet, instrument.rule_set_id).rules_json


def test_band1_fallback_save_refuses_a_same_side_rule(db: Session, client: TestClient) -> None:
    session, instrument = _session_with_tags(db, client, "e1-fallback")
    before = _stored_rules(db, instrument.id)

    response = client.post(
        f"/operator/sessions/{session.public_id}/instruments/{instrument.id}/fields/save",
        data=_link2_form("reviewee.tag1", "reviewee.tag2"),
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "compares across populations" in response.text
    assert _stored_rules(db, instrument.id) == before
    assert client.get(f"/operator/sessions/{session.public_id}/assignments").status_code == 200


def test_band1_card_save_refuses_a_same_side_rule(db: Session, client: TestClient) -> None:
    session, instrument = _session_with_tags(db, client, "e1-card")
    before = _stored_rules(db, instrument.id)

    response = client.post(
        f"/operator/sessions/{session.public_id}/instruments/{instrument.id}/save",
        data=_link2_form("reviewee.tag1", "reviewee.tag1"),
    )

    assert response.status_code == 422
    body = response.json()
    assert body["ok"] is False
    assert any("compares across populations" in error for error in body["errors"])
    assert _stored_rules(db, instrument.id) == before
    assert client.get(f"/operator/sessions/{session.public_id}/validate").status_code == 200


def test_band1_card_save_keeps_a_cross_side_rule(db: Session, client: TestClient) -> None:
    session, instrument = _session_with_tags(db, client, "e1-ok")

    response = client.post(
        f"/operator/sessions/{session.public_id}/instruments/{instrument.id}/save",
        data=_link2_form("reviewee.tag1", "reviewer.tag1"),
    )

    assert response.status_code == 200, response.text
    stored = _stored_rules(db, instrument.id)
    assert stored and stored[0]["rules"][0]["predicate"]["operand"] == "reviewer.tag1"


def test_band1_refusal_leaves_a_stored_rule_and_its_links_alone(
    db: Session, client: TestClient
) -> None:
    """The update-in-place path: a rule set already exists, and the
    refusal comes before the first write (``band1_touched_links``)."""
    session, instrument = _session_with_tags(db, client, "e1-update")
    saved = client.post(
        f"/operator/sessions/{session.public_id}/instruments/{instrument.id}/save",
        data=_link2_form("reviewee.tag1", "reviewer.tag1"),
    )
    assert saved.status_code == 200, saved.text
    before_rules = _stored_rules(db, instrument.id)
    before_links = db.get(Instrument, instrument.id).band1_touched_links

    refused = client.post(
        f"/operator/sessions/{session.public_id}/instruments/{instrument.id}/fields/save",
        data={**_link2_form("reviewee.tag1", "reviewee.tag2"), "link1_touched": ""},
        follow_redirects=False,
    )

    assert refused.status_code == 400
    assert _stored_rules(db, instrument.id) == before_rules
    assert db.get(Instrument, instrument.id).band1_touched_links == before_links


# --- Settings import -------------------------------------------------------


def _seed_for_import(db: Session, code: str) -> tuple[User, ReviewSession]:
    operator = User(email=f"op-{code}@example.edu", display_name="Op")
    db.add(operator)
    db.flush()
    session = ReviewSession(name=code.title(), code=code, created_by_user_id=operator.id)
    db.add(session)
    db.flush()
    db.add(Reviewer(session_id=session.id, name="R", email="r@example.edu"))
    db.add(Reviewee(session_id=session.id, name="E", email_or_identifier="e@example.edu"))
    db.flush()
    instrument = ensure_default_instrument(db, session)
    rule_set = SessionRuleSet(
        session_id=session.id,
        name="Band1",
        description="",
        combinator="ALL_OF",
        exclude_self_reviews=False,
        seed=None,
        rules_json=[],
    )
    db.add(rule_set)
    db.flush()
    instrument.rule_set_id = rule_set.id
    db.commit()
    return operator, session


def _with_cell(rows: list[Row], suffix: str, value: str) -> list[Row]:
    assert any(row.field.endswith(suffix) for row in rows), suffix
    return [
        Row(row.field, value, row.data_type) if row.field.endswith(suffix) else row
        for row in rows
    ]


@pytest.mark.parametrize(
    "value",
    [
        '[{"kind": "NOPE"}]',
        '{"x": 1}',
        "[1]",
        '[{"id": "a", "enabled": true, "kind": "MATCH", "predicate": {"field":'
        ' "pair_context.tag1", "operator": "same_as", "operand": "pair_context.tag2"}}]',
    ],
    ids=["unknown-kind", "object", "not-a-rule", "same-side"],
)
def test_settings_import_refuses_rules_the_engine_rejects(db: Session, value: str) -> None:
    operator, session = _seed_for_import(db, "s2-rules")
    rows = _with_cell(serialize_session_config(db, session), ".rules_json", value)

    result = apply_session_config(db, session, rows, user=operator)

    assert result.errors
    assert any("rules_json" in error.message for error in result.errors)
    db.rollback()
    stored = db.execute(
        select(SessionRuleSet).where(SessionRuleSet.session_id == session.id)
    ).scalar_one()
    assert stored.rules_json == []
    assignments.staleness_by_instrument(db, session)


@pytest.mark.parametrize("value", ["[1, 2]", '"text"', "7"])
def test_settings_import_refuses_a_band2_state_that_is_not_an_object(
    db: Session, value: str
) -> None:
    operator, session = _seed_for_import(db, "s2-band2")
    rows = _with_cell(serialize_session_config(db, session), ".band2_state", value)

    result = apply_session_config(db, session, rows, user=operator)

    assert any(
        error.field.endswith(".band2_state") and "JSON object" in error.message
        for error in result.errors
    )


_LINK2_PAIR_IS = (
    '[{"id": "link2", "enabled": true, "kind": "COMPOSITE", "op": "AND", "rules": ['
    '{"id": "link2-r0", "enabled": true, "kind": "MATCH", "predicate": {"field":'
    ' "pair_context.tag1", "operator": "equals", "operand": "Friend"}}]}]'
)


def test_settings_import_refuses_group_beside_a_link2_pair_tag_is(db: Session) -> None:
    """Band 1's Save refuses the combination (Item 2, author 2026-10-17);
    an import must not store it either."""
    operator, session = _seed_for_import(db, "item2-group")
    rows = _with_cell(serialize_session_config(db, session), ".rules_json", _LINK2_PAIR_IS)
    rows = _with_cell(rows, ".group_kind", "r1")

    result = apply_session_config(db, session, rows, user=operator)

    assert any(
        error.field.endswith(".group_kind") and "relationship tag" in error.message
        for error in result.errors
    )


def test_settings_import_keeps_a_link2_pair_tag_is_on_an_individual_instrument(
    db: Session,
) -> None:
    operator, session = _seed_for_import(db, "item2-indiv")
    rows = _with_cell(serialize_session_config(db, session), ".rules_json", _LINK2_PAIR_IS)

    result = apply_session_config(db, session, rows, user=operator)

    assert not result.errors


def _one_rule(link: str, predicate: str) -> str:
    return (
        f'[{{"id": "{link}", "enabled": true, "kind": "COMPOSITE", "op": "AND", "rules": ['
        f'{{"id": "{link}-r0", "enabled": true, "kind": "MATCH", "predicate": {predicate}}}]}}]'
    )


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (
            _one_rule("link1", '{"field": "pair_context.tag1", "operator": "equals", "operand": "F"}'),
            "Who does the review no longer filters",
        ),
        (
            _one_rule("link1", '{"field": "reviewer.pair_tag1", "operator": "equals", "operand": "F"}'),
            "a person's relationship tag",
        ),
        (
            _one_rule("link2", '{"field": "reviewee.pair_tag2", "operator": "is_not_empty"}'),
            "a person's relationship tag",
        ),
        (
            _one_rule(
                "link2",
                '{"field": "reviewee.tag1", "operator": "same_as", "operand": "pair_context.tag1"}',
            ),
            "can't be compared",
        ),
    ],
    ids=["link1-pair", "reviewer-pair-tag", "reviewee-pair-tag", "pair-operand"],
)
def test_settings_import_refuses_a_relationship_rule_the_card_no_longer_offers(
    db: Session, value: str, message: str
) -> None:
    """``guide/archive/pair_context_tags_further_clarify.md`` Item 1: the import
    refuses what Band 1's Save refuses, with the same reason."""
    operator, session = _seed_for_import(db, "pt-import")
    rows = _with_cell(serialize_session_config(db, session), ".rules_json", value)

    result = apply_session_config(db, session, rows, user=operator)

    assert any(
        error.field.endswith(".rules_json") and message in error.message
        for error in result.errors
    ), result.errors


def test_settings_import_refuses_group_beside_a_link2_pair_tag_filled(db: Session) -> None:
    """IS FILLED keeps pairs one by one too (pair tags Item 1), and the
    error names it beside IS."""
    operator, session = _seed_for_import(db, "pt-group-filled")
    filled = _LINK2_PAIR_IS.replace(
        '"operator": "equals", "operand": "Friend"', '"operator": "is_not_empty"'
    )
    rows = _with_cell(serialize_session_config(db, session), ".rules_json", filled)
    rows = _with_cell(rows, ".group_kind", "r1")

    result = apply_session_config(db, session, rows, user=operator)

    assert any(
        error.field.endswith(".group_kind") and "IS or IS FILLED" in error.message
        for error in result.errors
    ), result.errors


# --- Findings E1 (2026-10-22): a rule the card can't show ---------------------


def _composite(link: str, children: list[dict[str, object]], **extra: object) -> dict[str, object]:
    return {"id": link, "enabled": True, "kind": "COMPOSITE", "op": "AND", "rules": children, **extra}


def _child(predicate: dict[str, object], **extra: object) -> dict[str, object]:
    return {"id": "c0", "enabled": True, "kind": "MATCH", "predicate": predicate, **extra}


_IS_A = {"field": "reviewee.tag1", "operator": "equals", "operand": "A", "case_sensitive": False}


@pytest.mark.parametrize(
    ("rules", "message"),
    [
        ([{**_child(_IS_A), "id": "extra"}], "not one of the card's Links"),
        ([{**_child(_IS_A), "id": "link1"}], "is a MATCH rule; the card reads a Link only as a COMPOSITE"),
        ([_composite("link3", [_child(_IS_A)])], "not one of the card's Links"),
        ([_composite("link2", [_child(_IS_A)], enabled=False)], "is disabled"),
        ([_composite("link2", [_child(_IS_A)], op="NOT")], "'NOT'"),
        ([_composite("link2", [{**_child(_IS_A), "kind": "FILTER"}])], "a FILTER rule"),
        ([_composite("link2", [_child(_IS_A, enabled=False)])], "a disabled rule"),
        ([_composite("link2", [_child(_IS_A, enabled="false")])], "a disabled rule"),
        (
            [_composite("link2", [_child({**_IS_A, "operator": "in", "operand": ["A"]})])],
            "operator 'in'",
        ),
        (
            [
                _composite(
                    "link1",
                    [
                        _child(
                            {
                                "field": "reviewer.tag1",
                                "operator": "same_as",
                                "operand": "reviewee.tag1",
                            }
                        )
                    ],
                )
            ],
            "operator 'same_as'; Who does the review offers IS, IS NOT, IS FILLED and IS EMPTY",
        ),
        ([_composite("link2", [_child({**_IS_A, "case_sensitive": True})])], "case-sensitive"),
        ([_composite("link2", [_child({**_IS_A, "operand": "  "})])], "no value"),
    ],
    ids=[
        "top-level-match",
        "link-id-not-composite",
        "other-link",
        "disabled-link",
        "not-op",
        "filter-child",
        "disabled-child",
        "string-false-child",
        "in-operator",
        "link1-cross-side",
        "case-sensitive",
        "blank-value",
    ],
)
def test_settings_import_refuses_a_rule_the_card_cant_show(
    db: Session, rules: list[dict[str, object]], message: str
) -> None:
    """The engine applies each of these, the card hides it, and the
    card's next Save drops or rewrites it; the import refuses it with
    the reason instead of storing it."""
    operator, session = _seed_for_import(db, "e1-shape")
    rows = _with_cell(serialize_session_config(db, session), ".rules_json", json.dumps(rules))

    result = apply_session_config(db, session, rows, user=operator)

    assert any(
        error.field.endswith(".rules_json")
        and "can't show" in error.message
        and message in error.message
        for error in result.errors
    ), result.errors
    db.rollback()
    stored = db.execute(
        select(SessionRuleSet).where(SessionRuleSet.session_id == session.id)
    ).scalar_one()
    assert stored.rules_json == []


def test_settings_import_keeps_both_card_links(db: Session) -> None:
    operator, session = _seed_for_import(db, "e1-card-shape")
    rules = [
        _composite(
            "link1",
            [_child({"field": "reviewer.tag1", "operator": "is_not_empty", "operand": None}, id="c2")],
        ),
        _composite(
            "link2",
            [
                _child(_IS_A),
                _child(
                    {"field": "reviewee.tag2", "operator": "different_from", "operand": "reviewer.tag2"},
                    id="c1",
                ),
            ],
            op="OR",
        ),
    ]
    rows = _with_cell(serialize_session_config(db, session), ".rules_json", json.dumps(rules))

    result = apply_session_config(db, session, rows, user=operator)

    assert not result.errors, result.errors


def test_a_zero_operand_is_a_value_not_blank(db: Session, client: TestClient) -> None:
    """A numeric ``0`` is a value the card's text box shows as ``0``
    (Codex on #3237): the import keeps it and the card hydrates it."""
    rules = [_composite("link2", [_child({**_IS_A, "operand": 0})])]
    operator, session = _seed_for_import(db, "e1-zero")
    rows = _with_cell(serialize_session_config(db, session), ".rules_json", json.dumps(rules))

    assert not apply_session_config(db, session, rows, user=operator).errors

    _session, instrument = _session_with_tags(db, client, "e1-zero-decode")
    _store_rules(db, instrument, rules)
    state = decode_band1_state(instrument, db)
    assert [rule["operand_value"] for rule in state["link2"]["rules"]] == ["0"]


def test_settings_import_refuses_a_combinator_the_card_cant_show(db: Session) -> None:
    """The card joins its Links with ALL_OF and never shows the rule
    set's combinator, which its Save keeps (Codex on #3237)."""
    operator, session = _seed_for_import(db, "e1-any-of")
    rows = _with_cell(serialize_session_config(db, session), ".combinator", "ANY_OF")

    result = apply_session_config(db, session, rows, user=operator)

    assert any(
        error.field.endswith(".combinator") and "'ANY_OF'" in error.message
        for error in result.errors
    ), result.errors


def test_settings_import_marks_a_link_with_rules_touched(db: Session) -> None:
    """A Link holding rules the card shows, left out of
    ``band1_touched_links``, would read as Not set and lose its rules at
    the next Save; the import marks it touched (Codex on #3237)."""
    operator, session = _seed_for_import(db, "e1-touched")
    rules = [_composite("link2", [_child(_IS_A)])]
    rows = _with_cell(serialize_session_config(db, session), ".rules_json", json.dumps(rules))
    rows = _with_cell(rows, ".band1_touched_links", '["link3"]')

    assert not apply_session_config(db, session, rows, user=operator).errors

    instrument = db.execute(
        select(Instrument).where(Instrument.session_id == session.id)
    ).scalar_one()
    assert instrument.band1_touched_links == ["link3", "link2"]
    state = decode_band1_state(instrument, db)
    assert state["link2"]["touched"] and state["link2"]["mode"] == "filter"
    assert not state["link1"]["touched"]


def _store_rules(db: Session, instrument: Instrument, rules: list[dict[str, object]]) -> None:
    rule_set = SessionRuleSet(
        session_id=instrument.session_id,
        name=f"stored-{instrument.id}",
        description="",
        combinator="ALL_OF",
        exclude_self_reviews=False,
        seed=None,
        rules_json=rules,
    )
    db.add(rule_set)
    db.flush()
    instrument.rule_set_id = rule_set.id
    db.commit()


def test_the_card_does_not_show_a_disabled_rule_the_engine_skips(
    db: Session, client: TestClient
) -> None:
    """A rule set stored before the import refused the shape: the card
    reads it as the engine does, so its next Save keeps what applies."""
    _session, instrument = _session_with_tags(db, client, "e1-decode")
    _store_rules(
        db,
        instrument,
        [
            _composite(
                "link1", [_child({**_IS_A, "field": "reviewer.tag1"}, id="c2")], enabled=False
            ),
            _composite(
                "link2",
                [_child(_IS_A), _child({**_IS_A, "operand": "B"}, id="c1", enabled=False)],
            ),
        ],
    )

    state = decode_band1_state(instrument, db)

    assert state["link1"]["mode"] == "all" and state["link1"]["rules"] == []
    assert [rule["operand_value"] for rule in state["link2"]["rules"]] == ["A"]


def test_the_card_reads_a_string_false_as_the_engine_does(
    db: Session, client: TestClient
) -> None:
    """The engine reads ``"false"`` as False (Pydantic's lax bool), so
    the card hides that Link, and a ``case_sensitive: "false"`` rule
    imports (Codex on #3237)."""
    _session, instrument = _session_with_tags(db, client, "e1-str-false")
    _store_rules(db, instrument, [_composite("link2", [_child(_IS_A)], enabled="false")])

    assert decode_band1_state(instrument, db)["link2"]["mode"] == "all"

    operator, session = _seed_for_import(db, "e1-str-case")
    rules = [_composite("link2", [_child({**_IS_A, "case_sensitive": "false"})])]
    rows = _with_cell(serialize_session_config(db, session), ".rules_json", json.dumps(rules))
    assert not apply_session_config(db, session, rows, user=operator).errors


def test_a_link_whose_rules_are_all_disabled_reads_as_all(
    db: Session, client: TestClient
) -> None:
    """The engine skips a Composite with no enabled child, so the card
    shows that Link as All, not as Filter with no rules."""
    _session, instrument = _session_with_tags(db, client, "e1-all-off")
    _store_rules(db, instrument, [_composite("link2", [_child(_IS_A, enabled=False)])])

    state = decode_band1_state(instrument, db)

    assert state["link2"]["mode"] == "all" and state["link2"]["rules"] == []


def _add_rule_set(db: Session, session: ReviewSession, name: str, rules: list[object]) -> None:
    db.add(
        SessionRuleSet(
            session_id=session.id,
            name=name,
            description="",
            combinator="ALL_OF",
            exclude_self_reviews=False,
            seed=None,
            rules_json=rules,
        )
    )
    db.commit()


# The legacy seeded shapes an older session can still export.
_LEGACY_MATCH = _child(
    {"field": "reviewer.tag1", "operator": "same_as", "operand": "reviewee.tag1"}, id="intra_group"
)
_LEGACY_QUOTA = {
    "id": "three_reviewers_each",
    "enabled": True,
    "kind": "QUOTA",
    "scope": "PER_REVIEWEE",
    "min": 3,
    "max": 3,
    "selection": {"strategy": "RANDOM", "seed": 42},
}


def test_settings_import_keeps_a_rule_set_no_instrument_uses(db: Session) -> None:
    """The export carries every rule set; one no instrument uses has no
    card to hide its rules, so it round-trips as it did before E1."""
    operator, session = _seed_for_import(db, "e1-orphan")
    _add_rule_set(db, session, "Intra-group peer review", [_LEGACY_MATCH])
    _add_rule_set(db, session, "Three reviewers per reviewee", [_LEGACY_QUOTA])

    result = apply_session_config(db, session, serialize_session_config(db, session), user=operator)

    assert not result.errors, result.errors
    stored = {
        rule_set.name: rule_set.rules_json
        for rule_set in db.execute(
            select(SessionRuleSet).where(SessionRuleSet.session_id == session.id)
        ).scalars()
    }
    assert stored["Intra-group peer review"] == [_LEGACY_MATCH]
    assert stored["Three reviewers per reviewee"] == [_LEGACY_QUOTA]


def test_settings_import_refuses_the_same_rule_set_once_an_instrument_uses_it(
    db: Session,
) -> None:
    operator, session = _seed_for_import(db, "e1-used")
    rows = _with_cell(
        serialize_session_config(db, session), ".rules_json", json.dumps([_LEGACY_MATCH])
    )

    result = apply_session_config(db, session, rows, user=operator)

    assert any(
        error.field.endswith(".rules_json")
        and "instruments[1] uses this rule set" in error.message
        and "not one of the card's Links" in error.message
        for error in result.errors
    ), result.errors


def test_a_disabled_link2_does_not_keep_pairs_by_pair_tag() -> None:
    """``keeps_pairs_by_pair_tag`` skips a disabled Link as the engine
    does, as it already skipped a disabled rule inside one."""
    pair_is = _child({"field": "pair_context.tag1", "operator": "equals", "operand": "F"})

    assert keeps_pairs_by_pair_tag([_composite("link2", [pair_is])])
    assert not keeps_pairs_by_pair_tag([_composite("link2", [pair_is], enabled=False)])
