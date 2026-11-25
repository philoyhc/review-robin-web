"""Segment 20Q rung 6 — the guard: the participant pages at 390 × 844 on
a touch phone (the lobby, the surface open and closed, Across and
Stacked, the summary, About, Guide, the sign-in details, results and
collation; the pre-open and invitation-mismatch notices carry no table
and are left to the URL crawl). Every response table is laid out as
cards, no page scrolls sideways, and nothing tappable is too
small to tap: a control (a button, a box, a list, a button-styled link)
is at least 44 px tall, and a text link or text button inside a line
(an address, *clear*, a role pill) at least 24 px, WCAG 2.2's minimum
target with its inline exception."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from playwright.sync_api import Page, expect

from ._builder import REVIEWER_EMAIL, activate, seed_rosters, session_pk
from .conftest import LiveServer, app_url

PHONE: dict[str, Any] = {
    "viewport": {"width": 390, "height": 844},
    "is_mobile": True,
    "has_touch": True,
}
REVIEWEE_EMAIL = "carol@example.edu"
OBSERVER_EMAIL = "olive@example.edu"

_TOO_SMALL = """() => {
  const seen = el => {
    if (el.closest('[hidden], [aria-hidden="true"], .visually-hidden')) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden';
  };
  const inline = el => (el.tagName === 'A' && !el.classList.contains('btn'))
    || el.classList.contains('btn-reset')
    || (el.tagName === 'INPUT' && ['checkbox', 'radio'].includes(el.type));
  const out = [];
  document.querySelectorAll('a[href], button, input, select, textarea, summary').forEach(el => {
    if (el.type === 'hidden' || el.classList.contains('sc-box-hidden') || !seen(el)) return;
    const h = el.getBoundingClientRect().height, need = inline(el) ? 24 : 44;
    const text = (el.textContent || el.value || '').trim().slice(0, 24);
    const name = `${el.tagName.toLowerCase()}.${el.className || ''} "${text}"`;
    if (h + 0.5 < need) out.push(`${name} ${Math.round(h)}px < ${need}`);
  });
  return out;
}"""


def _check(page: Page, name: str) -> list[str]:
    problems: list[str] = []
    overflow = page.evaluate(
        "() => document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    if overflow > 0:
        problems.append(f"{name}: the page scrolls {overflow}px sideways")
    for scroller in page.locator(".table-scroll").all():
        if not scroller.is_visible():
            continue
        spill = scroller.evaluate("el => el.scrollWidth - el.clientWidth")
        if spill > 0:
            problems.append(f"{name}: a table scrolls {spill}px sideways")
    flat = page.evaluate(
        """() => [...document.querySelectorAll('table.rs-table > tbody > tr')]
            .filter(tr => getComputedStyle(tr).display !== 'block').length"""
    )
    if flat:
        problems.append(f"{name}: {flat} table row(s) not laid out as cards")
    problems += [f"{name}: {p}" for p in page.evaluate(_TOO_SMALL)]
    return problems


def _release(database_url: str, session_id: str) -> None:
    """Close the session with its responses released: Rana reads her
    own, Carol hers, and Olive observes them."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models import Instrument, InstrumentViewPolicy, Observer, ReviewSession
    from app.services.visibility_policies import MODE_LABELS

    granularity, identification = MODE_LABELS["raw"]
    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            pk = session_pk(database_url, session_id)
            review_session = db.get(ReviewSession, pk)
            assert review_session is not None
            review_session.observers_enabled = True
            db.add(Observer(session_id=pk, email=OBSERVER_EMAIL, display_name="Olive"))
            for instrument in db.execute(
                select(Instrument).where(Instrument.session_id == pk)
            ).scalars():
                for audience in ("peer_reviewer", "reviewee", "observer"):
                    policy = InstrumentViewPolicy(instrument_id=instrument.id, audience=audience)
                    if audience == "peer_reviewer":
                        policy.while_ongoing_granularity = granularity
                        policy.while_ongoing_identification = identification
                    policy.after_release_granularity = granularity
                    policy.after_release_identification = identification
                    db.add(policy)
            review_session.status = "expired"
            review_session.responses_release_at = datetime.now(UTC) - timedelta(hours=1)
            review_session.responses_release_until = None
            db.commit()
    finally:
        engine.dispose()


def _stack(database_url: str, session_id: str) -> None:
    """The session's instrument in the stacked layout (20K)."""
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import Session

    from app.db.models import Instrument

    engine = create_engine(database_url)
    try:
        with Session(engine) as db:
            for instrument in db.execute(
                select(Instrument).where(
                    Instrument.session_id == session_pk(database_url, session_id)
                )
            ).scalars():
                instrument.response_layout = "stacked"
            db.commit()
    finally:
        engine.dispose()


def test_every_participant_page_fits_a_phone(
    page_as: Callable[..., Page],
    api: httpx.Client,
    live_server: LiveServer,
    new_session: Callable[[], str],
) -> None:
    session_id = new_session()
    seed_rosters(api, session_id)
    activate(api, live_server.database_url, session_id)
    problems: list[str] = []

    reviewer = page_as(REVIEWER_EMAIL, **PHONE)
    reviewer.goto(app_url("/me"))
    problems += _check(reviewer, "lobby (open)")
    reviewer.goto(app_url(f"/me/sessions/{session_id}/1"))
    expect(reviewer.locator("table.rs-table")).to_be_visible()
    problems += _check(reviewer, "review surface (open)")
    card = reviewer.locator("table.rs-table > tbody > tr").first
    card.locator("input[type='number']").first.fill("3")
    card.locator("textarea").first.fill("Clear and well argued.")
    reviewer.locator(".rs-action-row").first.get_by_role("button", name="Submit").click()
    reviewer.wait_for_url("**/summary")
    problems += _check(reviewer, "summary (submitted)")

    _release(live_server.database_url, session_id)
    visits = [
        (reviewer, "/me", "lobby (released)"),
        (reviewer, f"/me/sessions/{session_id}/summary", "summary (released)"),
        (reviewer, f"/me/sessions/{session_id}/1", "review surface (closed)"),
        (reviewer, "/about", "about"),
        (reviewer, "/auth/me/debug", "sign-in details"),
        (reviewer, "/guide", "guide"),
        (page_as(REVIEWEE_EMAIL, **PHONE), f"/me/sessions/{session_id}/results", "results"),
        (page_as(OBSERVER_EMAIL, **PHONE), f"/me/sessions/{session_id}/collation", "collation"),
    ]
    for page, path, name in visits:
        response = page.goto(app_url(path))
        assert response is not None and response.ok, (name, response and response.status)
        problems += _check(page, name)

    _stack(live_server.database_url, session_id)
    reviewer.goto(app_url(f"/me/sessions/{session_id}/1"))
    problems += _check(reviewer, "review surface (closed, stacked)")
    assert not problems, "\n".join(problems)
