"""Link 2's cross-side operand list hides pair-context tags while the field
is a pair-context tag (author, 2026-10-16; findings E1): the engine
refuses pair context compared with pair context. Only the editing view
narrows. The rendered list keeps every option, so a stored rule keeps
its own (``spec/instruments.md``, Link 1 / Link 2).
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
from playwright.sync_api import Locator, Page

from ._builder import open_unlocked, pin_full_matrix
from .conftest import LiveServer

REVIEWERS_CSV = b"ReviewerName,ReviewerEmail,ReviewerTag1\nRana,rana@example.edu,Red\n"
REVIEWEES_CSV = b"RevieweeName,RevieweeEmail,RevieweeTag1\nCarol,carol@example.edu,Blue\n"


def _seed(api: httpx.Client, live_server: LiveServer, session_id: int) -> None:
    for kind, body in (("reviewers", REVIEWERS_CSV), ("reviewees", REVIEWEES_CSV)):
        response = api.post(
            f"/operator/sessions/{session_id}/{kind}/import",
            files={"file": (f"{kind}.csv", body, "text/csv")},
            follow_redirects=False,
        )
        assert response.status_code in (200, 303), response.text
    # A tagged relationship, written directly: the Relationships page
    # sits behind its feature toggle, and only the tag matters here.
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models import Relationship, Reviewee, Reviewer

    engine = create_engine(live_server.database_url)
    try:
        with Session(engine) as db:
            reviewer = db.execute(
                select(Reviewer).where(Reviewer.session_id == session_id)
            ).scalar_one()
            reviewee = db.execute(
                select(Reviewee).where(Reviewee.session_id == session_id)
            ).scalar_one()
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


def _set_field(card: Locator, value: str) -> None:
    card.locator('select[name="link2_field"]').first.evaluate(
        """(select, value) => {
            select.value = value;
            select.dispatchEvent(new Event('change'));
        }""",
        value,
    )


def _operands(card: Locator) -> dict[str, bool]:
    """Each operand option's value, and whether it can be chosen."""
    return card.locator('select[name="link2_operand_tag"]').first.evaluate(
        """(select) => Object.fromEntries(
            Array.from(select.options)
                .filter(o => o.value)
                .map(o => [o.value, !o.disabled && !o.hidden])
        )"""
    )


def test_a_pair_context_field_hides_pair_context_operands(
    page: Page, api: httpx.Client, live_server: LiveServer, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    _seed(api, live_server, session_id)
    pin_full_matrix(live_server.database_url, session_id)
    card = open_unlocked(page, session_id)

    _set_field(card, "reviewee.tag1")
    assert _operands(card) == {"reviewer.tag1": True, "pair_context.tag1": True}

    _set_field(card, "pair_context.tag1")
    assert _operands(card) == {"reviewer.tag1": True, "pair_context.tag1": False}

    _set_field(card, "reviewee.tag1")
    assert _operands(card) == {"reviewer.tag1": True, "pair_context.tag1": True}


def test_a_hidden_operand_clears_when_the_field_turns_pair_context(
    page: Page, api: httpx.Client, live_server: LiveServer, new_session: Callable[[], int]
) -> None:
    session_id = new_session()
    _seed(api, live_server, session_id)
    pin_full_matrix(live_server.database_url, session_id)
    card = open_unlocked(page, session_id)
    operand = card.locator('select[name="link2_operand_tag"]').first

    _set_field(card, "reviewee.tag1")
    operand.evaluate("(select) => { select.value = 'pair_context.tag1'; }")
    _set_field(card, "pair_context.tag1")

    assert operand.evaluate("(select) => select.value") == ""
