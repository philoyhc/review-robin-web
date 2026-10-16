"""Band 1 offers IS FILLED / IS EMPTY and no pair-context tags.

Author, 2026-10-16 (``guide/assignment_rule_clarify.md``, stage 1):
Link 1 and Link 2 gain IS FILLED and IS EMPTY, which take no value, and
the card stops offering pair-context tags while their meaning is
reworked. A rule already stored with one keeps its option, so a Save
does not silently drop it.
"""
from __future__ import annotations

import re

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
)
from app.services.instruments import ensure_default_instrument


def _session(db: Session, client: TestClient, code: str) -> tuple[ReviewSession, Instrument]:
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
        )
    )
    db.commit()
    instrument = ensure_default_instrument(db, session)
    db.commit()
    return session, instrument


def _form(**link_rules: tuple[str, str, str]) -> dict[str, str]:
    """``link1=(field, op, value)`` / ``link2=(field, op, tag)``."""
    data = {"link3_mode": "individual", "link3_touched": "true"}
    for link in ("link1", "link2"):
        data[f"{link}_touched"] = "true"
        data[f"{link}_combinator"] = "AND"
        if link not in link_rules:
            data[f"{link}_mode"] = "all"
            continue
        field, op, operand = link_rules[link]
        data.update(
            {
                f"{link}_mode": "filter",
                f"{link}_field": field,
                f"{link}_op": op,
                f"{link}_operand_value": operand if link == "link1" else "",
                f"{link}_operand_tag": operand if link == "link2" else "",
            }
        )
    return data


def _predicates(db: Session, instrument_id: int) -> list[dict[str, object]]:
    db.expire_all()
    instrument = db.get(Instrument, instrument_id)
    rules = db.get(SessionRuleSet, instrument.rule_set_id).rules_json
    return [child["predicate"] for link in rules for child in link["rules"]]


def _page(client: TestClient, session_id: int, instrument_id: int) -> str:
    return client.get(
        f"/operator/sessions/{session_id}/instruments?editing={instrument_id}"
    ).text


def test_filled_and_empty_store_with_no_operand(db: Session, client: TestClient) -> None:
    session, instrument = _session(db, client, "b1-filled")

    response = client.post(
        f"/operator/sessions/{session.id}/instruments/{instrument.id}/save",
        data=_form(
            link1=("reviewer.tag1", "IS FILLED", "ignored"),
            link2=("reviewee.tag1", "IS EMPTY", ""),
        ),
    )

    assert response.status_code == 200, response.text
    predicates = _predicates(db, instrument.id)
    assert [(p["field"], p["operator"]) for p in predicates] == [
        ("reviewer.tag1", "is_not_empty"),
        ("reviewee.tag1", "is_empty"),
    ]
    assert all(p.get("operand") is None for p in predicates)

    page = _page(client, session.id, instrument.id)
    assert ">IS FILLED</button>" in page
    assert ">IS EMPTY</button>" in page
    # Each rule's value box renders inactive.
    assert len(re.findall(r'name="link[12]_operand_value"', page)) == 2
    assert len(re.findall(r'readonly aria-disabled="true"\s+form="dfsave-\d+" name="link[12]_operand_value"', page)) == 2


def test_link1_cycle_offers_filled_and_empty(db: Session, client: TestClient) -> None:
    session, instrument = _session(db, client, "b1-cycle")

    page = _page(client, session.id, instrument.id)

    assert 'data-new-model-operator-cycle="IS|IS NOT|IS FILLED|IS EMPTY"' in page


def test_no_dropdown_offers_a_pair_context_tag(db: Session, client: TestClient) -> None:
    session, instrument = _session(db, client, "b1-no-pc")

    page = _page(client, session.id, instrument.id)

    # The session has a tagged relationship, so pair context was offered
    # before; now no select lists it, Link 3 included.
    assert 'value="pair_context.' not in page
    assert '<option value="reviewer.tag1"' in page
    assert '<option value="reviewee.tag1"' in page


def test_a_stored_pair_context_rule_keeps_its_option_and_saves(
    db: Session, client: TestClient
) -> None:
    session, instrument = _session(db, client, "b1-stored-pc")
    saved = client.post(
        f"/operator/sessions/{session.id}/instruments/{instrument.id}/save",
        data=_form(link1=("pair_context.tag1", "IS", "P")),
    )
    assert saved.status_code == 200, saved.text

    page = _page(client, session.id, instrument.id)
    assert re.search(
        r'<option value="pair_context\.tag1" selected data-new-model-stored-only>', page
    )
    assert page.count('value="pair_context.tag1"') == 1

    # Saving the card as it stands keeps the rule.
    again = client.post(
        f"/operator/sessions/{session.id}/instruments/{instrument.id}/save",
        data=_form(link1=("pair_context.tag1", "IS", "P")),
    )
    assert again.status_code == 200, again.text
    assert _predicates(db, instrument.id) == [
        {
            "field": "pair_context.tag1",
            "operator": "equals",
            "operand": "P",
            "case_sensitive": False,
        }
    ]


def _pair_tags_only(db: Session, client: TestClient, code: str) -> tuple[ReviewSession, Instrument]:
    """Tagged relationships, untagged rosters: every tag the card used to
    offer was a pair-context one."""
    session, instrument = _session(db, client, code)
    for model in (Reviewer, Reviewee):
        for row in db.execute(select(model).where(model.session_id == session.id)).scalars():
            row.tag_1 = None
    db.commit()
    return session, instrument


def test_a_stored_pair_context_operand_survives_with_no_reviewer_tags(
    db: Session, client: TestClient
) -> None:
    """With no usable reviewer tag the cycle drops the cross-side
    operators; a stored one must still render with its operand, or the
    cell falls back to IS with no value and the next Save drops it."""
    session, instrument = _session(db, client, "b1-stored-operand")
    form = _form(link2=("reviewee.tag1", "IS THE SAME AS", "pair_context.tag1"))
    # A second Link 2 rule, comparing with a value.
    form.update(
        {
            "link2_field": ["reviewee.tag1", "reviewee.tag1"],
            "link2_op": ["IS THE SAME AS", "IS"],
            "link2_operand_value": ["", "A"],
            "link2_operand_tag": ["pair_context.tag1", ""],
        }
    )
    saved = client.post(
        f"/operator/sessions/{session.id}/instruments/{instrument.id}/save", data=form
    )
    assert saved.status_code == 200, saved.text
    reviewer = db.execute(select(Reviewer).where(Reviewer.session_id == session.id)).scalar_one()
    reviewer.tag_1 = None
    db.commit()

    page = _page(client, session.id, instrument.id)

    cycles = re.findall(r'data-new-model-operator-cycle="([^"]*)"', page)
    # Link 1's default cell, then Link 2's two: only the stored-operand
    # cell keeps the cross-side operators.
    assert cycles[1:3] == [
        "IS THE SAME AS|IS DIFFERENT FROM|IS|IS NOT|IS FILLED|IS EMPTY",
        "IS|IS NOT|IS FILLED|IS EMPTY",
    ]
    assert re.findall(r'name="link2_op"\s+data-new-model-op-input\s+value="([^"]*)"', page) == [
        "IS THE SAME AS",
        "IS",
    ]
    assert re.search(
        r'<option value="pair_context\.tag1" selected data-new-model-stored-only>', page
    )

    # The same values saved again (what the rendered cells above carry)
    # keep both rules.
    again = client.post(
        f"/operator/sessions/{session.id}/instruments/{instrument.id}/save", data=form
    )
    assert again.status_code == 200, again.text
    assert [(p["operator"], p.get("operand")) for p in _predicates(db, instrument.id)] == [
        ("same_as", "pair_context.tag1"),
        ("equals", "A"),
    ]


def test_stored_rules_keep_their_pills_live_with_only_pair_tags(
    db: Session, client: TestClient
) -> None:
    """A Link whose only usable tags were pair-context ones keeps a live
    pill while it has stored rules (or a stored boundary), so the stored
    state can still be edited; with nothing stored it is disabled."""
    session, instrument = _pair_tags_only(db, client, "b1-pair-only")
    page = _page(client, session.id, instrument.id)
    assert page.count('title="No usable tags for this link"') == 3

    saved = client.post(
        f"/operator/sessions/{session.id}/instruments/{instrument.id}/fields/save",
        data={
            **_form(link1=("pair_context.tag1", "IS", "P")),
            "link3_mode": "grouped",
            "link3_boundary": "pair_context.tag1",
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303, saved.text

    page = _page(client, session.id, instrument.id)
    # Link 2 has nothing stored and stays disabled; Links 1 and 3 are live.
    assert page.count('title="No usable tags for this link"') == 1
    assert 'onclick="newModelToggleRuleMode(this)"' in page
    assert 'onclick="newModelToggleUnitMode(this)"' in page
