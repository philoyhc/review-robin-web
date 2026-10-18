"""Band 1 offers IS FILLED / IS EMPTY, and relationship tags in Link 2.

Author, 2026-10-16 (``guide/archive/assignment_rule_clarify.md``, stage 1):
Link 1 and Link 2 gain IS FILLED and IS EMPTY, which take no value, and
the card stops offering pair-context tags while their meaning is
reworked. A rule already stored with one keeps its option, so a Save
does not silently drop it.
"""
from __future__ import annotations

import re

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


def _page(client: TestClient, session_public_id: str, instrument_id: int) -> str:
    return client.get(
        f"/operator/sessions/{session_public_id}/instruments?editing={instrument_id}"
    ).text


def test_filled_and_empty_store_with_no_operand(db: Session, client: TestClient) -> None:
    session, instrument = _session(db, client, "b1-filled")

    response = client.post(
        f"/operator/sessions/{session.public_id}/instruments/{instrument.id}/save",
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

    page = _page(client, session.public_id, instrument.id)
    assert ">IS FILLED</button>" in page
    assert ">IS EMPTY</button>" in page
    # Each rule's value box renders inactive.
    assert len(re.findall(r'name="link[12]_operand_value"', page)) == 2
    assert len(re.findall(r'readonly aria-disabled="true"\s+form="dfsave-\d+" name="link[12]_operand_value"', page)) == 2


def test_link1_cycle_offers_filled_and_empty(db: Session, client: TestClient) -> None:
    session, instrument = _session(db, client, "b1-cycle")

    page = _page(client, session.public_id, instrument.id)

    assert 'data-new-model-operator-cycle="IS|IS NOT|IS FILLED|IS EMPTY"' in page


def _select(page: str, name: str) -> str:
    """The first ``<select name=...>`` on the page, through its close."""
    body = page[page.index(f'name="{name}"') :]
    return body[: body.index("</select>")]


def test_pair_tags_are_a_link2_field_only(db: Session, client: TestClient) -> None:
    """``guide/archive/pair_context_tags_further_clarify.md`` Item 1 (author,
    2026-10-18): a relationship tag is offered, as "Pair: <label>", in
    Link 2's field only; Link 1, Link 2's operand list and Link 3 offer
    roster tags only."""
    session, instrument = _session(db, client, "b1-pc-offered")

    page = _page(client, session.public_id, instrument.id)

    assert len(re.findall(r'<option value="pair_context\.tag1"\s*>Pair: ', page)) == 1
    assert "pair_context." in _select(page, "link2_field")
    for name in ("link1_field", "link2_operand_tag", "link3_boundary"):
        assert "pair_context." not in _select(page, name), name
    assert "Reviewer&#39;s tag" in page or "Reviewer's tag" in page
    assert "Reviewee&#39;s tag" in page or "Reviewee's tag" in page


def _link2_rules(*rules: tuple[str, str, str, str]) -> dict[str, object]:
    """``(field, op, operand_value, operand_tag)`` per Link 2 cell."""
    return {
        "link2_mode": "filter",
        "link2_field": [r[0] for r in rules],
        "link2_op": [r[1] for r in rules],
        "link2_operand_value": [r[2] for r in rules],
        "link2_operand_tag": [r[3] for r in rules],
    }


def test_every_link2_pair_tag_operator_stores_the_pair(db: Session, client: TestClient) -> None:
    """IS / IS NOT / IS FILLED / IS EMPTY on a relationship tag all judge
    the pair (``pair_context.tagN``): assign or exclude by a value, or by
    any value."""
    session, instrument = _session(db, client, "b1-pc-map")
    form = {
        **_form(),
        **_link2_rules(
            ("pair_context.tag1", "IS", "P", ""),
            ("pair_context.tag1", "IS NOT", "C", ""),
            ("pair_context.tag1", "IS FILLED", "", ""),
            ("pair_context.tag1", "IS EMPTY", "", ""),
        ),
    }

    saved = client.post(
        f"/operator/sessions/{session.public_id}/instruments/{instrument.id}/save", data=form
    )

    assert saved.status_code == 200, saved.text
    assert [(p["field"], p["operator"], p.get("operand")) for p in _predicates(db, instrument.id)] == [
        ("pair_context.tag1", "equals", "P"),
        ("pair_context.tag1", "not_equals", "C"),
        ("pair_context.tag1", "is_not_empty", None),
        ("pair_context.tag1", "is_empty", None),
    ]

    # Each shows as the offered relationship tag, on the pair cycle,
    # under the "Pairwise tag" caption; saving again stores the same.
    page = _page(client, session.public_id, instrument.id)
    assert "selected data-new-model-stored-only" not in page
    assert len(re.findall(r'<option value="pair_context\.tag1" selected>', page)) == 4
    link2_cycles = re.findall(
        r'data-new-model-operator-cycle="([^"]*)"\s+data-new-model-operator-cycle-pair=', page
    )
    assert link2_cycles == ["IS|IS NOT|IS FILLED|IS EMPTY"] * 4
    assert len(re.findall(r'data-new-model-field-helper-pair="Pairwise tag"[^>]*>Pairwise tag<', page)) == 4
    before = _predicates(db, instrument.id)
    again = client.post(
        f"/operator/sessions/{session.public_id}/instruments/{instrument.id}/save", data=form
    )
    assert again.status_code == 200, again.text
    assert _predicates(db, instrument.id) == before


@pytest.mark.parametrize(
    ("form", "message"),
    [
        (_form(link1=("pair_context.tag1", "IS", "P")), "Who does the review no longer filters"),
        (_form(link1=("reviewer.pair_tag1", "IS", "P")), "a person's relationship tag"),
        (_form(link2=("reviewee.pair_tag1", "IS FILLED", "")), "a person's relationship tag"),
        (_form(link2=("reviewee.tag1", "IS THE SAME AS", "pair_context.tag1")), "can't be compared"),
        (_form(link2=("pair_context.tag1", "IS DIFFERENT FROM", "reviewer.tag1")), "can't be compared"),
        (_form(link2=("reviewee.tag1", "IS THE SAME AS", "reviewer.pair_tag1")), "a person's relationship tag"),
    ],
)
def test_save_refuses_a_relationship_rule_the_card_no_longer_offers(
    db: Session, client: TestClient, form: dict[str, str], message: str
) -> None:
    """A Link 1 relationship tag, a person's relationship tag and a
    relationship tag beside a cross-side operator are refused, not
    rewritten: a rewrite would change who reviews whom."""
    session, instrument = _session(db, client, "b1-pc-refused")

    card = client.post(
        f"/operator/sessions/{session.public_id}/instruments/{instrument.id}/save", data=form
    )
    fallback = client.post(
        f"/operator/sessions/{session.public_id}/instruments/{instrument.id}/fields/save",
        data=form,
        follow_redirects=False,
    )

    assert card.status_code == 422
    assert any(message in error for error in card.json()["errors"]), card.json()
    assert fallback.status_code == 400
    db.expire_all()
    assert db.get(Instrument, instrument.id).rule_set_id is None


def test_a_stored_person_pair_tag_shows_as_stored_and_save_refuses_it(
    db: Session, client: TestClient
) -> None:
    """A rule stored before Item 1 (``reviewer.pair_tagN`` /
    ``reviewee.pair_tagN``) keeps its option, named by whose tag it
    reads, and the next Save is refused until it is removed."""
    session, instrument = _session(db, client, "b1-pc-stored")
    form = _form(link1=("reviewer.tag1", "IS", "A"), link2=("reviewee.tag1", "IS FILLED", ""))
    saved = client.post(
        f"/operator/sessions/{session.public_id}/instruments/{instrument.id}/save", data=form
    )
    assert saved.status_code == 200, saved.text
    db.expire_all()
    rule_set = db.get(SessionRuleSet, db.get(Instrument, instrument.id).rule_set_id)
    rules = [dict(link, rules=[dict(c) for c in link["rules"]]) for link in rule_set.rules_json]
    rules[0]["rules"][0]["predicate"] = {**rules[0]["rules"][0]["predicate"], "field": "reviewer.pair_tag1"}
    rules[1]["rules"][0]["predicate"] = {**rules[1]["rules"][0]["predicate"], "field": "reviewee.pair_tag1"}
    rule_set.rules_json = rules
    db.commit()

    page = _page(client, session.public_id, instrument.id)

    assert re.search(
        r'<option value="reviewer\.pair_tag1" selected data-new-model-stored-only>Reviewer&#39;s pair tag: ',
        page,
    )
    assert re.search(
        r'<option value="reviewee\.pair_tag1" selected data-new-model-stored-only>Reviewee&#39;s pair tag: ',
        page,
    )
    refused = client.post(
        f"/operator/sessions/{session.public_id}/instruments/{instrument.id}/save",
        data=_form(
            link1=("reviewer.pair_tag1", "IS", "A"), link2=("reviewee.pair_tag1", "IS FILLED", "")
        ),
    )
    assert refused.status_code == 422


def _with_group(form: dict[str, object]) -> dict[str, object]:
    return {**form, "link3_mode": "grouped", "link3_boundary": "reviewee.tag1"}


@pytest.mark.parametrize(("op", "value"), [("IS", "P"), ("IS FILLED", "")])
def test_group_is_refused_beside_a_link2_pair_tag_is_or_filled(
    db: Session, client: TestClient, op: str, value: str
) -> None:
    session, instrument = _session(db, client, "b1-pc-group")
    form = _with_group(
        {**_form(), **_link2_rules(("pair_context.tag1", op, value, ""))}
    )

    card = client.post(
        f"/operator/sessions/{session.public_id}/instruments/{instrument.id}/save", data=form
    )
    fallback = client.post(
        f"/operator/sessions/{session.public_id}/instruments/{instrument.id}/fields/save",
        data=form,
        follow_redirects=False,
    )

    assert card.status_code == 422
    assert any("can't be Group" in error for error in card.json()["errors"])
    assert fallback.status_code == 400
    db.expire_all()
    stored = db.get(Instrument, instrument.id)
    assert stored.rule_set_id is None
    assert stored.group_kind is None


def test_group_stands_beside_other_link2_pair_tags(db: Session, client: TestClient) -> None:
    """Only IS and IS FILLED keep pairs one by one: IS NOT and IS EMPTY
    leave a group meaningful, and an OR list counts the IS."""
    session, instrument = _session(db, client, "b1-pc-group-ok")
    form = _with_group(
        {
            **_form(),
            **_link2_rules(
                ("pair_context.tag1", "IS NOT", "C", ""),
                ("pair_context.tag1", "IS EMPTY", "", ""),
            ),
        }
    )
    saved = client.post(
        f"/operator/sessions/{session.public_id}/instruments/{instrument.id}/save", data=form
    )
    assert saved.status_code == 200, saved.text
    db.expire_all()
    assert db.get(Instrument, instrument.id).group_kind == "r1"

    with_or = _with_group(
        {
            **_form(),
            **_link2_rules(
                ("reviewee.tag1", "IS", "A", ""),
                ("pair_context.tag1", "IS", "P", ""),
            ),
            "link2_combinator": "OR",
        }
    )
    refused = client.post(
        f"/operator/sessions/{session.public_id}/instruments/{instrument.id}/save", data=with_or
    )
    assert refused.status_code == 422


def _pair_tags_only(db: Session, client: TestClient, code: str) -> tuple[ReviewSession, Instrument]:
    """Tagged relationships, untagged rosters: the card's only usable
    tags are relationship ones."""
    session, instrument = _session(db, client, code)
    for model in (Reviewer, Reviewee):
        for row in db.execute(select(model).where(model.session_id == session.id)).scalars():
            row.tag_1 = None
    db.commit()
    return session, instrument


def test_a_stored_operand_from_an_emptied_slot_survives_with_no_reviewer_tags(
    db: Session, client: TestClient
) -> None:
    """With no usable reviewer tag (and no relationships) the cycle
    drops the cross-side operators; a stored one must still render with
    its operand, or the cell falls back to IS with no value and the next
    Save drops it. Only that cell keeps the full cycle."""
    session, instrument = _session(db, client, "b1-stored-operand")
    for relationship in db.execute(
        select(Relationship).where(Relationship.session_id == session.id)
    ).scalars():
        db.delete(relationship)
    db.commit()
    form = {
        **_form(),
        **_link2_rules(
            ("reviewee.tag1", "IS THE SAME AS", "", "reviewer.tag1"),
            ("reviewee.tag1", "IS", "A", ""),
        ),
    }
    saved = client.post(
        f"/operator/sessions/{session.public_id}/instruments/{instrument.id}/save", data=form
    )
    assert saved.status_code == 200, saved.text
    reviewer = db.execute(select(Reviewer).where(Reviewer.session_id == session.id)).scalar_one()
    reviewer.tag_1 = None
    db.commit()

    page = _page(client, session.public_id, instrument.id)

    cycles = re.findall(r'data-new-model-operator-cycle="([^"]*)"', page)
    # Link 1's default cell, then Link 2's two.
    assert cycles[1:3] == [
        "IS THE SAME AS|IS DIFFERENT FROM|IS|IS NOT|IS FILLED|IS EMPTY",
        "IS|IS NOT|IS FILLED|IS EMPTY",
    ]
    assert re.findall(r'name="link2_op"\s+data-new-model-op-input\s+value="([^"]*)"', page) == [
        "IS THE SAME AS",
        "IS",
    ]
    assert re.search(r'<option value="reviewer\.tag1" selected data-new-model-stored-only>', page)

    # The same values saved again (what the rendered cells above carry)
    # keep both rules.
    again = client.post(
        f"/operator/sessions/{session.public_id}/instruments/{instrument.id}/save", data=form
    )
    assert again.status_code == 200, again.text
    assert [(p["operator"], p.get("operand")) for p in _predicates(db, instrument.id)] == [
        ("same_as", "reviewer.tag1"),
        ("equals", "A"),
    ]


def test_link3_pill_follows_a_stored_boundary_with_only_pair_tags(
    db: Session, client: TestClient
) -> None:
    """Relationship tags make Link 2 usable; Link 1 (roster tags only)
    stays disabled, and Link 3, which groups by reviewee tags only, stays
    disabled unless a boundary is stored."""
    session, instrument = _pair_tags_only(db, client, "b1-pair-only")
    page = _page(client, session.public_id, instrument.id)
    assert page.count('title="No usable tags for this link"') == 2

    saved = client.post(
        f"/operator/sessions/{session.public_id}/instruments/{instrument.id}/fields/save",
        data={
            **_form(),
            **_link2_rules(("pair_context.tag1", "IS NOT", "C", "")),
            "link3_mode": "grouped",
            "link3_boundary": "pair_context.tag1",
        },
        follow_redirects=False,
    )
    assert saved.status_code == 303, saved.text

    page = _page(client, session.public_id, instrument.id)
    assert page.count('title="No usable tags for this link"') == 1
    assert 'onclick="newModelToggleUnitMode(this)"' in page


def test_a_default_link2_cell_on_a_pair_tag_shows_the_value_box(
    db: Session, client: TestClient
) -> None:
    """With untagged reviewees, Link 2's first option is a relationship
    tag: its default cell shows IS, so the value box shows and the
    reviewer-tag picker hides, or Save would drop the rule (cold read on
    #3120)."""
    session, instrument = _session(db, client, "b1-pc-default")
    for reviewee in db.execute(select(Reviewee).where(Reviewee.session_id == session.id)).scalars():
        reviewee.tag_1 = None
    db.commit()

    page = _page(client, session.public_id, instrument.id)

    assert re.findall(r'name="link2_op"\s+data-new-model-op-input\s+value="([^"]*)"', page) == ["IS"]
    operand_tag = re.search(r'<select data-new-model-operand-tag\s+style="([^"]*)"', page)
    assert operand_tag and "display: none" in operand_tag.group(1)
    value_boxes = re.findall(
        r'<input data-new-model-operand-value type="text" placeholder="value"\s+style="([^"]*)"', page
    )
    assert len(value_boxes) == 2 and "display: none" not in value_boxes[1]


def test_an_is_value_reading_like_a_field_is_free_text(db: Session, client: TestClient) -> None:
    session, instrument = _session(db, client, "b1-pc-literal")

    saved = client.post(
        f"/operator/sessions/{session.public_id}/instruments/{instrument.id}/save",
        data=_form(link1=("reviewer.tag1", "IS", "reviewer.pair_tag1")),
    )

    assert saved.status_code == 200, saved.text
