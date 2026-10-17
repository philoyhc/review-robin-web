"""Band 1's IS FILLED / IS EMPTY leave the value box inactive, and a new
cell (``+``) starts from the offered tags only, without a stored tag the
card no longer offers (author, 2026-10-16;
``guide/archive/assignment_rule_clarify.md``, stage 1).
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
from playwright.sync_api import Locator, Page, expect

from ._builder import open_unlocked, pin_full_matrix
from .conftest import LiveServer

REVIEWERS_CSV = b"ReviewerName,ReviewerEmail,ReviewerTag1\nRana,rana@example.edu,Red\n"
REVIEWEES_CSV = b"RevieweeName,RevieweeEmail,RevieweeTag1\nCarol,carol@example.edu,Blue\n"


def _seed(api: httpx.Client, session_id: int) -> None:
    for kind, body in (("reviewers", REVIEWERS_CSV), ("reviewees", REVIEWEES_CSV)):
        response = api.post(
            f"/operator/sessions/{session_id}/{kind}/import",
            files={"file": (f"{kind}.csv", body, "text/csv")},
            follow_redirects=False,
        )
        assert response.status_code in (200, 303), response.text


def _filter_on(card: Locator, link: str) -> Locator:
    """Click the Link's pill on to Filter (the pinned matrix renders it on
    All, one click short); return its first cell."""
    wrapper = card.locator("[data-new-model-link-wrapper]").filter(
        has=card.page.locator(f'select[name="{link}_field"]')
    )
    pill = wrapper.locator("[data-new-model-rule-mode]")
    expect(pill).to_have_attribute("data-new-model-rule-mode", "all")
    pill.click()
    expect(pill).to_have_attribute("data-new-model-rule-mode", "filter")
    return wrapper.locator("[data-new-model-rule-cell]").first


def test_filled_and_empty_make_the_value_box_inactive(
    page: Page, api: httpx.Client, live_server: LiveServer, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    _seed(api, session_id)
    pin_full_matrix(live_server.database_url, session_id)
    card = open_unlocked(page, session_id)
    cell = _filter_on(card, "link1")
    operator = cell.locator("[data-new-model-operator-cycle]")
    value = cell.locator("[data-new-model-operand-value]")
    value.fill("Red")

    seen = []
    for _ in range(4):
        seen.append((operator.inner_text(), value.evaluate("i => i.readOnly")))
        operator.click()

    assert seen == [
        ("IS", False),
        ("IS NOT", False),
        ("IS FILLED", True),
        ("IS EMPTY", True),
    ]
    # Back round to IS: the box is live again and kept what was typed.
    expect(operator).to_have_text("IS")
    expect(value).to_be_editable()
    expect(value).to_have_value("Red")
    assert cell.locator("[data-new-model-op-input]").input_value() == "IS"


def test_link2_filled_shows_the_inactive_value_box(
    page: Page, api: httpx.Client, live_server: LiveServer, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    _seed(api, session_id)
    pin_full_matrix(live_server.database_url, session_id)
    card = open_unlocked(page, session_id)
    cell = _filter_on(card, "link2")
    operator = cell.locator("[data-new-model-operator-cycle]")

    for _ in range(4):  # IS THE SAME AS → … → IS FILLED
        operator.click()

    expect(operator).to_have_text("IS FILLED")
    expect(cell.locator("[data-new-model-operand-tag]")).to_be_hidden()
    value = cell.locator("[data-new-model-operand-value]")
    expect(value).to_be_visible()
    expect(value).not_to_be_editable()

    # A new cell starts on IS THE SAME AS, with its value box live.
    card.locator("[data-new-model-rule-builder]").nth(1).locator(
        "[data-new-model-rule-add]"
    ).click()
    added = card.locator('select[name="link2_field"]').nth(1).locator(
        "xpath=ancestor::*[@data-new-model-rule-cell]"
    )
    expect(added.locator("[data-new-model-operator-cycle]")).to_have_text("IS THE SAME AS")
    assert added.locator("[data-new-model-operand-value]").evaluate("i => i.readOnly") is False


def _store_pair_context_config(live_server: LiveServer, session_id: int) -> None:
    """A Link 1 rule and a Link 3 boundary on a pair-context tag, stored as
    the card could store them before it stopped offering one."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models import Instrument, SessionRuleSet

    engine = create_engine(live_server.database_url)
    try:
        with Session(engine) as db:
            instrument = db.execute(
                select(Instrument).where(Instrument.session_id == session_id)
            ).scalars().first()
            rule_set = SessionRuleSet(
                session_id=session_id,
                name=f"Band1 {instrument.id}",
                description="",
                combinator="ALL_OF",
                exclude_self_reviews=False,
                seed=None,
                rules_json=[
                    {
                        "id": "link1",
                        "enabled": True,
                        "kind": "COMPOSITE",
                        "op": "AND",
                        "rules": [
                            {
                                "id": "link1-r0",
                                "enabled": True,
                                "kind": "MATCH",
                                "predicate": {
                                    "field": "pair_context.tag1",
                                    "operator": "equals",
                                    "operand": "Pod",
                                    "case_sensitive": False,
                                },
                            }
                        ],
                    }
                ],
            )
            db.add(rule_set)
            db.flush()
            instrument.rule_set_id = rule_set.id
            instrument.group_kind = "p1"
            instrument.band1_touched_links = ["link1", "link2", "link3"]
            db.commit()
    finally:
        engine.dispose()


def _offered(select: Locator) -> list[str]:
    return select.evaluate("s => Array.from(s.options).map(o => o.value).filter(v => v)")


def test_a_new_cell_does_not_offer_a_stored_only_tag(
    page: Page, api: httpx.Client, live_server: LiveServer, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    _seed(api, session_id)
    _store_pair_context_config(live_server, session_id)
    card = open_unlocked(page, session_id)

    link1 = card.locator('select[name="link1_field"]')
    assert _offered(link1.first) == ["reviewer.tag1", "pair_context.tag1"]
    card.locator("[data-new-model-rule-builder]").first.locator(
        "[data-new-model-rule-add]"
    ).click()
    expect(link1).to_have_count(2)
    assert _offered(link1.nth(1)) == ["reviewer.tag1"]
    assert link1.first.input_value() == "pair_context.tag1"

    boundary = card.locator('select[name="link3_boundary"]')
    assert boundary.first.input_value() == "pair_context.tag1"
    card.locator("[data-new-model-unit-add]").click()
    expect(boundary).to_have_count(2)
    assert _offered(boundary.nth(1)) == ["reviewee.tag1"]


UNTAGGED_REVIEWERS_CSV = b"ReviewerName,ReviewerEmail\nRana,rana@example.edu\n"


def test_a_new_cell_beside_a_stored_operand_opens_on_is_with_no_reviewer_tags(
    page: Page, api: httpx.Client, live_server: LiveServer, new_session: Callable[[], int]
) -> None:
    """With no usable reviewer tag, only the cell holding a stored operand
    keeps IS THE SAME AS; a cell cloned from it by ``+`` gets the trimmed
    cycle rather than an empty reviewer-tag picker."""
    session_id = new_session()
    for kind, body in (("reviewers", UNTAGGED_REVIEWERS_CSV), ("reviewees", REVIEWEES_CSV)):
        response = api.post(
            f"/operator/sessions/{session_id}/{kind}/import",
            files={"file": (f"{kind}.csv", body, "text/csv")},
            follow_redirects=False,
        )
        assert response.status_code in (200, 303), response.text
    _store_link2_operand(live_server, session_id)
    card = open_unlocked(page, session_id)
    operators = card.locator('select[name="link2_field"]').locator(
        "xpath=ancestor::*[@data-new-model-rule-cell]"
    ).locator("[data-new-model-operator-cycle]")
    expect(operators.first).to_have_text("IS THE SAME AS")

    card.locator("[data-new-model-rule-builder]").nth(1).locator(
        "[data-new-model-rule-add]"
    ).click()

    expect(operators).to_have_count(2)
    expect(operators.nth(1)).to_have_text("IS")
    assert operators.nth(1).get_attribute("data-new-model-operator-cycle") == (
        "IS|IS NOT|IS FILLED|IS EMPTY"
    )


def _store_link2_operand(live_server: LiveServer, session_id: int) -> None:
    """``reviewee.tag1 IS THE SAME AS pair_context.tag1`` in Link 2."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models import Instrument, SessionRuleSet

    engine = create_engine(live_server.database_url)
    try:
        with Session(engine) as db:
            instrument = db.execute(
                select(Instrument).where(Instrument.session_id == session_id)
            ).scalars().first()
            rule_set = SessionRuleSet(
                session_id=session_id,
                name=f"Band1 {instrument.id}",
                description="",
                combinator="ALL_OF",
                exclude_self_reviews=False,
                seed=None,
                rules_json=[
                    {
                        "id": "link2",
                        "enabled": True,
                        "kind": "COMPOSITE",
                        "op": "AND",
                        "rules": [
                            {
                                "id": "link2-r0",
                                "enabled": True,
                                "kind": "MATCH",
                                "predicate": {
                                    "field": "reviewee.tag1",
                                    "operator": "same_as",
                                    "operand": "pair_context.tag1",
                                    "case_sensitive": False,
                                },
                            }
                        ],
                    }
                ],
            )
            db.add(rule_set)
            db.flush()
            instrument.rule_set_id = rule_set.id
            instrument.band1_touched_links = ["link1", "link2", "link3"]
            db.commit()
    finally:
        engine.dispose()


def _tag_the_pair(live_server: LiveServer, session_id: int) -> None:
    """One relationship tagged ``Pod``, so the card offers ``Pair: …``."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models import Relationship, Reviewee, Reviewer

    engine = create_engine(live_server.database_url)
    try:
        with Session(engine) as db:
            reviewer = db.execute(select(Reviewer).where(Reviewer.session_id == session_id)).scalar_one()
            reviewee = db.execute(select(Reviewee).where(Reviewee.session_id == session_id)).scalar_one()
            db.add(
                Relationship(
                    session_id=session_id,
                    reviewer_id=reviewer.id,
                    reviewee_id=reviewee.id,
                    tag_1="Pod",
                )
            )
            db.commit()
    finally:
        engine.dispose()


def test_link3_skips_group_while_link2_keeps_pairs_by_a_pair_tag(
    page: Page, api: httpx.Client, live_server: LiveServer, new_session: Callable[[], int]
) -> None:
    """Item 2 (author, 2026-10-17): a Link 2 pair-tag IS picks pairs one
    by one, so the Unit of review pill cycles Individual → Not set,
    skipping Group; any other Link 2 rule leaves Group in the cycle."""
    session_id = new_session()
    _seed(api, session_id)
    _tag_the_pair(live_server, session_id)
    pin_full_matrix(live_server.database_url, session_id)
    card = open_unlocked(page, session_id)
    unit = card.locator("[data-new-model-unit-mode]")
    expect(unit).to_have_attribute("data-new-model-unit-mode", "individual")

    cell = _filter_on(card, "link2")
    cell.locator('select[name="link2_field"]').select_option("pair_context.tag1")
    operator = cell.locator("[data-new-model-operator-cycle]")
    while operator.inner_text() != "IS":
        operator.click()

    unit.click()
    expect(unit).to_have_attribute("data-new-model-unit-mode", "not_set")
    unit.click()
    expect(unit).to_have_attribute("data-new-model-unit-mode", "individual")

    operator.click()  # IS NOT
    unit.click()
    expect(unit).to_have_attribute("data-new-model-unit-mode", "group")


def test_link2_caption_reads_pairwise_for_a_pair_tag_under_is(
    page: Page, api: httpx.Client, live_server: LiveServer, new_session: Callable[[], int]
) -> None:
    """A relationship tag under IS / IS NOT judges the pair itself, so
    Link 2's caption reads "Pairwise tag" (author, 2026-10-17); any other
    tag or operator keeps "Reviewee's tag"."""
    session_id = new_session()
    _seed(api, session_id)
    _tag_the_pair(live_server, session_id)
    pin_full_matrix(live_server.database_url, session_id)
    card = open_unlocked(page, session_id)
    cell = _filter_on(card, "link2")
    caption = cell.locator("[data-new-model-rule-field-helper]")
    field = cell.locator('select[name="link2_field"]')
    operator = cell.locator("[data-new-model-operator-cycle]")
    expect(caption).to_have_text("Reviewee's tag")

    field.select_option("pair_context.tag1")
    seen = []
    for _ in range(6):
        seen.append((operator.inner_text(), caption.inner_text()))
        operator.click()
    assert seen == [
        ("IS THE SAME AS", "Reviewee's tag"),
        ("IS DIFFERENT FROM", "Reviewee's tag"),
        ("IS", "Pairwise tag"),
        ("IS NOT", "Pairwise tag"),
        ("IS FILLED", "Reviewee's tag"),
        ("IS EMPTY", "Reviewee's tag"),
    ]

    while operator.inner_text() != "IS":
        operator.click()
    expect(caption).to_have_text("Pairwise tag")
    field.select_option("reviewee.tag1")
    expect(caption).to_have_text("Reviewee's tag")
    field.select_option("pair_context.tag1")
    expect(caption).to_have_text("Pairwise tag")

    # A new cell starts on the default operator and field, so on the
    # default caption.
    card.locator("[data-new-model-rule-builder]").nth(1).locator(
        "[data-new-model-rule-add]"
    ).click()
    expect(card.locator("[data-new-model-rule-field-helper]").filter(
        has_text="Pairwise tag"
    )).to_have_count(1)


def test_a_stored_pair_tag_is_renders_the_pairwise_caption(
    page: Page, api: httpx.Client, live_server: LiveServer, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    _seed(api, session_id)
    _tag_the_pair(live_server, session_id)
    _store_link2_pair_is(live_server, session_id)
    card = open_unlocked(page, session_id)
    cell = card.locator('select[name="link2_field"]').locator(
        "xpath=ancestor::*[@data-new-model-rule-cell]"
    )
    expect(cell.locator("[data-new-model-operator-cycle]")).to_have_text("IS")
    expect(cell.locator("[data-new-model-rule-field-helper]")).to_have_text("Pairwise tag")


def _store_link2_pair_is(live_server: LiveServer, session_id: int) -> None:
    """``pair_context.tag1 IS Pod`` in Link 2."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models import Instrument, SessionRuleSet

    engine = create_engine(live_server.database_url)
    try:
        with Session(engine) as db:
            instrument = db.execute(
                select(Instrument).where(Instrument.session_id == session_id)
            ).scalars().first()
            rule_set = SessionRuleSet(
                session_id=session_id,
                name=f"Band1 {instrument.id}",
                description="",
                combinator="ALL_OF",
                exclude_self_reviews=False,
                seed=None,
                rules_json=[
                    {
                        "id": "link2",
                        "enabled": True,
                        "kind": "COMPOSITE",
                        "op": "AND",
                        "rules": [
                            {
                                "id": "link2-r0",
                                "enabled": True,
                                "kind": "MATCH",
                                "predicate": {
                                    "field": "pair_context.tag1",
                                    "operator": "equals",
                                    "operand": "Pod",
                                    "case_sensitive": False,
                                },
                            }
                        ],
                    }
                ],
            )
            db.add(rule_set)
            db.flush()
            instrument.rule_set_id = rule_set.id
            instrument.band1_touched_links = ["link1", "link2", "link3"]
            db.commit()
    finally:
        engine.dispose()
