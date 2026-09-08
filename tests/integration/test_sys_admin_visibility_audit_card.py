"""Segment 19C Item 10 rung 1 — the Visibility grid audit card, scaffold.

The card is the retrospective half of Item 9. That item closed the door
— the Settings-CSV import now refuses a `(audience, window)` cell the
Band 3 editor refuses — but the guard is prospective, and any row an
import wrote before it is still stored and still honoured by
`resolve_mode`. The card is where a sys-admin will see those rows.

Rung 1 shipped the shape; **rung 2 wired the check**. The placeholder
banner and the test that pinned it are gone, which is the transition
rung 1's assertion was there to force.

Workspace-wide by construction: the query spans every session, which no
per-session operator may see, so the card lives behind
`require_sys_admin` and nowhere else. `test_sys_admin_chrome.py` covers
that gate on this page; this file covers the card on it.
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import (
    AuditEvent,
    Instrument,
    InstrumentViewPolicy,
    ReviewSession,
)
from app.services import visibility_policies


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


def _instrument(db: Session, review_session: ReviewSession, *, name: str) -> Instrument:
    instrument = Instrument(session_id=review_session.id, name=name, order=1)
    db.add(instrument)
    db.flush()
    return instrument


def _policy(
    db: Session,
    instrument: Instrument,
    audience: str,
    *,
    while_ongoing: str | None = None,
    after_release: str | None = None,
) -> InstrumentViewPolicy:
    """Write a policy row directly.

    Deliberately not through `upsert_policy`: that validates the cell and
    would refuse every case this file exists to cover. These rows stand in
    for what the pre-Item-9 import could persist."""
    kwargs: dict[str, str] = {}
    for window, mode in (
        ("while_ongoing", while_ongoing),
        ("after_release", after_release),
    ):
        if mode is None:
            continue
        granularity, identification = visibility_policies.MODE_LABELS[mode]
        kwargs[f"{window}_granularity"] = granularity
        kwargs[f"{window}_identification"] = identification
    policy = InstrumentViewPolicy(
        instrument_id=instrument.id, audience=audience, **kwargs
    )
    db.add(policy)
    db.flush()
    return policy


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


def test_no_findings_says_so_in_words(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Empty is the expected steady state, and must read as reassurance.

    An empty table reads as "not implemented yet"; a sentence reads as an
    answer."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    review_session = _make_session(client, db, code="vga-empty")
    _instrument(db, review_session, name="Feedback")
    db.commit()

    body = _flat(client.get("/operator/sys-admin/sessions").text)
    assert "<strong>No findings.</strong>" in body
    assert "carries a mode its audience and window allow" in body


def test_a_legal_grid_produces_no_findings(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The control for every case below: a grid the editor would accept
    must be silent, or the check would be reporting everything."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    review_session = _make_session(client, db, code="vga-legal")
    instrument = _instrument(db, review_session, name="Feedback")
    _policy(db, instrument, "reviewee", after_release="raw")
    _policy(db, instrument, "observer", while_ongoing="summarized")
    _policy(db, instrument, "peer_reviewer", while_ongoing="raw")
    db.commit()

    body = _flat(client.get("/operator/sys-admin/sessions").text)
    assert "<strong>No findings.</strong>" in body


def test_the_reviewee_mid_flight_grant_is_reported(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The row the whole item exists for."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    review_session = _make_session(client, db, code="vga-re")
    instrument = _instrument(db, review_session, name="Feedback")
    _policy(db, instrument, "reviewee", while_ongoing="raw")
    db.commit()

    body = _flat(client.get("/operator/sys-admin/sessions").text)
    assert "<strong>No findings.</strong>" not in body
    # Session, instrument, audience, cell, stored mode, reason.
    assert "vga-re" in body
    assert "Feedback" in body
    assert '<span class="pill pill-role-reviewee">Reviewee</span>' in body
    assert "Session ongoing" in body
    assert "<code>raw</code>" in body
    assert "Cell accepts only off" in body


def test_the_other_two_audiences_are_checked_by_the_same_path(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The check reads `_PER_CELL_VALID_MODES`, so every cell is covered
    by construction — the reviewee's is the one with a disclosure behind
    it, not the only one that can be wrong."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    review_session = _make_session(client, db, code="vga-others")
    instrument = _instrument(db, review_session, name="Feedback")
    _policy(db, instrument, "observer", while_ongoing="raw")
    _policy(db, instrument, "peer_reviewer", while_ongoing="summarized")
    db.commit()

    body = _flat(client.get("/operator/sys-admin/sessions").text)
    assert '<span class="pill pill-role-observer">Observer</span>' in body
    # The reviewer audience is stored as `peer_reviewer`; the pill class
    # is `pill-role-reviewer`, which is the only one base.html styles.
    assert '<span class="pill pill-role-reviewer">Reviewer</span>' in body


def test_a_half_set_pair_is_reported_with_its_own_reason(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`decode_pair_to_mode` reads a half-set pair as "off", so without a
    distinct check this cell would be reported as legal and silent."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    review_session = _make_session(client, db, code="vga-half")
    instrument = _instrument(db, review_session, name="Feedback")
    policy = _policy(db, instrument, "reviewee")
    policy.after_release_granularity = "row"
    policy.after_release_identification = None
    db.commit()

    body = _flat(client.get("/operator/sys-admin/sessions").text)
    assert "set both or neither" in body
    assert "<code>half-set pair</code>" in body


def test_the_incoherent_pair_is_reported_with_its_own_reason(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`aggregated` + `identified` is reserved and decodes to no mode."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    review_session = _make_session(client, db, code="vga-incoh")
    instrument = _instrument(db, review_session, name="Feedback")
    policy = _policy(db, instrument, "observer")
    policy.after_release_granularity = "aggregated"
    policy.after_release_identification = "identified"
    db.commit()

    body = _flat(client.get("/operator/sys-admin/sessions").text)
    assert "the reserved-incoherent pair" in body


def test_live_findings_sort_above_closed_ones(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A hit on a `ready` or `expired` session is reachable now; one on a
    `draft` or `archived` session is closed by the lifecycle whatever the
    row says. The reader is deciding what to do this morning."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    # Codes chosen so alphabetical order would put the draft first —
    # otherwise the sort could pass on the session code alone.
    draft = _make_session(client, db, code="aaa-draft")
    live = _make_session(client, db, code="zzz-live")
    live.status = "ready"
    for review_session in (draft, live):
        instrument = _instrument(db, review_session, name="Feedback")
        _policy(db, instrument, "reviewee", while_ongoing="raw")
    db.commit()

    body = client.get("/operator/sys-admin/sessions").text
    card = body[body.index("<h2>Visibility grid audit</h2>") :]
    assert card.index("zzz-live") < card.index("aaa-draft")
    assert "Reachable now" in card


def test_the_card_writes_nothing(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Read-only is a contract, not an intention: rendering the card must
    leave no audit event and no changed row behind."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    review_session = _make_session(client, db, code="vga-ro")
    instrument = _instrument(db, review_session, name="Feedback")
    policy = _policy(db, instrument, "reviewee", while_ongoing="raw")
    db.commit()
    before = db.execute(select(func.count()).select_from(AuditEvent)).scalar_one()

    assert client.get("/operator/sys-admin/sessions").status_code == 200

    after = db.execute(select(func.count()).select_from(AuditEvent)).scalar_one()
    assert after == before
    db.refresh(policy)
    assert policy.while_ongoing_granularity == "row"
    assert policy.while_ongoing_identification == "identified"
