"""Shared helpers for the display-field / response-field /
RTD-card integration test files.

Per ``guide/archive/major_refactor.md`` §12.D the original
``test_display_field_routes.py`` (2,167 LOC, 53 tests) split into
six per-surface files. The seven helper functions below were
shared by ~30 of those tests; this module avoids duplicating them
across the resulting files. Mirrors the
``tests/integration/_preview_iframe.py`` shared-helper-module
convention.

The ``reviewer_user`` ``@pytest.fixture`` was used by exactly one
test (``test_bulk_fields_save_interleaves_and_renders_on_reviewer_surface``)
and stays inline in the file that owns that test
(``test_response_field_bulk_save.py``).
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Instrument,
    InstrumentDisplayField,
    ReviewSession,
    RuleSet,
)
from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _populate_rosters(client: TestClient, session_id: int) -> None:
    client.post(
        f"/operator/sessions/{session_id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nR,r@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{session_id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )


def _full_matrix_seed_id(db: Session) -> int:
    return db.execute(
        select(RuleSet.id).where(
            RuleSet.is_seed.is_(True), RuleSet.name == "Full Matrix"
        )
    ).scalar_one()


def _generate_full_matrix(
    client: TestClient, db: Session, session_id: int
) -> None:
    """Generate via the seeded "Full Matrix" RuleSet through the
    rule-based generate route. Replaces the standalone full-matrix
    route retired in 12C-1 PR 3.

    ``exclude_self_review="false"`` mirrors the legacy helper's
    pass-through behaviour (the legacy route's empty-string default
    also resolved to ``False``)."""

    pin_full_matrix_on_all_instruments(db, session_id)
    generate_via_page_button(client, session_id)


def _activate(client: TestClient, db: Session, session_id: int) -> None:
    client.get(f"/operator/sessions/{session_id}?validated=1")
    client.post(
        f"/operator/sessions/{session_id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )


def _validate(client: TestClient, db: Session, session_id: int) -> None:
    client.get(f"/operator/sessions/{session_id}?validated=1")


def _instrument(db: Session, session_id: int) -> Instrument:
    return db.execute(
        select(Instrument).where(Instrument.session_id == session_id)
    ).scalar_one()


def _seed_pair_context_display_fields(db: Session, instrument: Instrument) -> None:
    """Pair-context display fields are no longer auto-seeded by
    ensure_default_instrument (item #14, 2026-05-01). Tests that
    exercise edit/delete on those rows seed them explicitly. Append
    after the locked Name + Email rows that ``ensure_default_instrument``
    already seeded (Slice 1 of Segment 10D)."""
    db.refresh(instrument)
    base = max((f.order for f in instrument.display_fields), default=-1) + 1
    for offset, slot in enumerate(("1", "2", "3")):
        db.add(
            InstrumentDisplayField(
                instrument_id=instrument.id,
                label="",
                source_type="pair_context",
                source_field=slot,
                order=base + offset,
                visible=True,
            )
        )
    db.commit()
