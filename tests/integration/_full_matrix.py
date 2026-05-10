"""Shared helper: look up the seeded "Full Matrix" RuleSet id.

Every deployment seeds a single ``Full Matrix`` RuleSet in the
operator-library tier (see ``app/services/rules/seeds.py``). Tests
that previously POSTed to the standalone
``/assignments/full-matrix`` route now POST to
``/assignments/rule-based/generate`` with ``rule_set_id`` set to
this seed's id — same end-to-end behaviour, single engine path.
The standalone route retired in 12C-1 PR 3.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import RuleSet


def full_matrix_seed_id(db: Session) -> int:
    return db.execute(
        select(RuleSet.id).where(
            RuleSet.is_seed.is_(True), RuleSet.name == "Full Matrix"
        )
    ).scalar_one()
