"""Shared helpers for tests that exercise the page-level
"Generate assignments" flow on the Assignments page.

Wave 5 PR 5.2 retired the RuleSet seeding helper. The 5 seeded
``session_rule_sets`` rows (``Full Matrix`` + friends) are no
longer auto-materialised on session create. Tests that need a
``Full Matrix`` SessionRuleSet to pin against now lazily
synthesise one on-demand via :func:`pin_full_matrix_on_all_instruments`.

New-model instruments default to Full Matrix via the synthetic
empty-rules schema (Wave 4 PR 1) whenever ``rule_set_id`` is
NULL — so tests that exclusively use new-model instruments can
skip the pin entirely.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, SessionRuleSet


_BAND1_LINKS_ALL = ["link1", "link2", "link3"]


def mark_band1_touched_on_all_instruments(
    db: Session, session_id: int, *, links: list[str] | None = None
) -> None:
    """Mark every instrument's Band 1 link pills as deliberately
    clicked (``Instrument.band1_touched_links``). Fixture-time
    helper for tests that need to bypass the Wave 5 "Not set"
    pill safety gate — the gate forces operators to click each
    of the three Band 1 link pills before ``is_configured``
    flips True, which most setup-bypass tests aren't trying to
    exercise.
    """
    target = sorted(set(links or _BAND1_LINKS_ALL))
    instruments = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == session_id)
        ).scalars()
    )
    for instrument in instruments:
        instrument.band1_touched_links = list(target)
    db.flush()
    db.commit()


def pin_full_matrix_on_all_instruments(
    db: Session,
    session_id: int,
    *,
    name: str = "Full Matrix",
    mark_band1_touched: bool = True,
) -> int:
    """Pin a ``Full Matrix``-equivalent ``session_rule_sets`` row
    on every instrument in the session and return that row's id.
    Lazily materialises the row if absent (Wave 5 PR 5.2 retired
    the auto-seed). The helper writes the column directly (no
    audit emission) — fixture-time setup for tests that need a
    known materialisation input on legacy instruments.

    ``mark_band1_touched`` (default True) also stamps each
    instrument's ``band1_touched_links`` with all three link ids
    so the Wave 5 "Not set" pill safety gate sees the instrument
    as configured. Pass ``False`` to leave the touched set
    untouched (used by tests that exercise the gate itself).
    """
    rule_set_id = db.execute(
        select(SessionRuleSet.id).where(
            SessionRuleSet.session_id == session_id,
            SessionRuleSet.name == name,
        )
    ).scalar_one_or_none()
    if rule_set_id is None:
        rs = SessionRuleSet(
            session_id=session_id,
            name=name,
            description="",
            combinator="ALL_OF",
            # ``exclude_self_reviews=False`` matches the pre-Wave-5
            # ``SEED_FULL_MATRIX`` seed (every reviewer × every
            # reviewee including self). Per-session toggles can
            # override at generate time.
            exclude_self_reviews=False,
            seed=None,
            rules_json=[],
        )
        db.add(rs)
        db.flush()
        rule_set_id = rs.id
    instruments = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == session_id)
        ).scalars()
    )
    for instrument in instruments:
        instrument.rule_set_id = rule_set_id
        if mark_band1_touched:
            instrument.band1_touched_links = list(_BAND1_LINKS_ALL)
    db.flush()
    db.commit()
    return rule_set_id


def generate_via_page_button(
    client: TestClient,
    session_id: int,
    *,
    confirm_replace: bool = False,
    acknowledge_response_loss: bool = False,
) -> Response:
    """POST to the Slice 3a page-level Generate route. Mirrors what
    the operator does after pinning rules on the Instruments page.
    """
    data: dict[str, str] = {}
    if confirm_replace:
        data["confirm_replace"] = "true"
    if acknowledge_response_loss:
        data["acknowledge_response_loss"] = "true"
    return client.post(
        f"/operator/sessions/{session_id}/assignments/generate",
        data=data,
        follow_redirects=False,
    )
