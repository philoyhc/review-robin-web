"""Shared helpers for tests that exercise the page-level
"Generate assignments" flow on the Assignments page.

Post-15B Slice 3a, materialisation flows through:

1. The operator pins a ``session_rule_sets`` row on each instrument
   (``instruments.rule_set_id``) — Slice 2a per-card picker, or via
   the Settings CSV apply path (Slice 2b), or directly through
   :func:`pin_full_matrix_on_all_instruments` in tests.
2. The operator clicks the page-level **Generate assignments**
   button on ``/operator/sessions/{id}/assignments`` — Slice 3a
   POST to ``/assignments/generate`` calling
   ``replace_assignments(instrument_id=None)``.

The pre-15B operator-tier ``operator_rule_sets`` library still
seeds a ``Full Matrix`` row on every deployment; tests look that
up via :func:`full_matrix_seed_id` for legacy-shape assertions
that haven't migrated yet.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Instrument, RuleSet, SessionRuleSet


def full_matrix_seed_id(db: Session) -> int:
    return db.execute(
        select(RuleSet.id).where(
            RuleSet.is_seed.is_(True), RuleSet.name == "Full Matrix"
        )
    ).scalar_one()


def pin_full_matrix_on_all_instruments(
    db: Session, session_id: int, *, name: str = "Full Matrix"
) -> int:
    """Pin the named ``session_rule_sets`` row on every instrument
    in the session and return that row's id. The helper writes the
    column directly (no audit emission) — fixture-time setup for
    tests that need a known materialisation input.
    """
    rule_set_id = db.execute(
        select(SessionRuleSet.id).where(
            SessionRuleSet.session_id == session_id,
            SessionRuleSet.name == name,
        )
    ).scalar_one()
    instruments = list(
        db.execute(
            select(Instrument).where(Instrument.session_id == session_id)
        ).scalars()
    )
    for instrument in instruments:
        instrument.rule_set_id = rule_set_id
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
