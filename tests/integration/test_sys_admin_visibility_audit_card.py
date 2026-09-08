"""Segment 19C Item 10 rung 1 — the Visibility grid audit card, scaffold.

The card is the retrospective half of Item 9. That item closed the door
— the Settings-CSV import now refuses a `(audience, window)` cell the
Band 3 editor refuses — but the guard is prospective, and any row an
import wrote before it is still stored and still honoured by
`resolve_mode`. The card is where a sys-admin will see those rows.

**Rung 1 ships the shape, not the check** (`CLAUDE.md`: a new card lands
scaffold-first). These tests pin the copy and the placement, and pin the
placeholder banner *present* — so rung 2 cannot wire the real check
without coming back here and saying so.

Workspace-wide by construction: the query spans every session, which no
per-session operator may see, so the card lives behind
`require_sys_admin` and nowhere else. `test_sys_admin_chrome.py` covers
that gate on this page; this file covers the card on it.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import ReviewSession


def _flat(html: str) -> str:
    """Collapse whitespace before matching copy.

    The template wraps prose across source lines, so a sentence a reader
    sees as one string is not one string in the markup. Normalizing here
    means these assertions survive the template being re-wrapped, which a
    literal match would not."""
    return re.sub(r"\s+", " ", html)


def _make_session(client: TestClient, db: Session, *, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Cohort A", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def test_card_renders_on_sessions_diagnostics(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    _make_session(client, db, code="vga-1")

    body = _flat(client.get("/operator/sys-admin/sessions").text)
    assert "<h2>Visibility grid audit</h2>" in body
    # The reason the card exists, in the card: the disclosure it looks for.
    assert "reading responses while the review is still running" in body
    # Read-only is stated, not implied — the card must never look like a
    # place to clear a cell.
    assert "Read-only." in body


def test_card_is_marked_a_placeholder_until_rung_2(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pinned deliberately.

    The scaffold renders sample rows so the layout can be reviewed, and a
    reader must not mistake them for findings in their workspace. When
    rung 2 lands the real check, this test fails — which is the point:
    the banner and this assertion come out together, in the same diff
    that makes the rows real."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    _make_session(client, db, code="vga-2")

    body = _flat(client.get("/operator/sys-admin/sessions").text)
    assert "Placeholder — not yet wired." in body
    assert "not findings from this workspace" in body


def test_the_scaffold_queries_nothing(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rung 1 must not touch `instrument_view_policies`.

    A session carrying a policy row renders exactly the same card as one
    without: the scaffold's rows are fixed text. This is what makes rung
    1 reviewable as layout alone."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    bare = _make_session(client, db, code="vga-3")
    body_before = client.get("/operator/sys-admin/sessions").text

    from app.db.models import Instrument, InstrumentViewPolicy

    instrument = Instrument(session_id=bare.id, name="Feedback", order=1)
    db.add(instrument)
    db.flush()
    db.add(
        InstrumentViewPolicy(
            instrument_id=instrument.id,
            audience="reviewee",
            while_ongoing_granularity="row",
            while_ongoing_identification="identified",
        )
    )
    db.commit()

    body_after = client.get("/operator/sys-admin/sessions").text
    start = body_after.index("<h2>Visibility grid audit</h2>")
    end = body_after.index("</div>", start)
    assert body_after[start:end] == body_before[
        body_before.index("<h2>Visibility grid audit</h2>") : body_before.index(
            "</div>", body_before.index("<h2>Visibility grid audit</h2>")
        )
    ]
