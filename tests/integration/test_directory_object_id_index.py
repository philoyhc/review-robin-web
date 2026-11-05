"""Segment 20G rung 4: with object ids stored normalized, the code's
account matches compare the column plainly, so Postgres can serve them
from the column's index rather than scanning a ``lower(...)`` of every
row. Planned here are the code's own statements: `users.users_by_principal`
(sign-in, the invite) and the account arm of `participants.Viewer.clause`.
The clause's other arm, a row matched by mail (``lower(trim(email))``),
has no index; this rung does not change it.

Postgres only (the ``ci-postgres`` job): sequential scans are switched
off for the statement, since at a test's size the planner would rightly
prefer one. What is proved is that each statement can use the index at
all, which ``lower(column) = ...`` could not.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import Observer, Reviewee, Reviewer
from app.services.participants import Viewer
from app.services.users import users_by_principal

ID = "1a2b3c4d-aaaa-4bbb-8ccc-ddddeeeeffff"


def _plan(db: Session, statement) -> str:
    compiled = statement.compile(db.get_bind(), compile_kwargs={"literal_binds": True})
    db.execute(text("SET LOCAL enable_seqscan = off"))
    return "\n".join(row[0] for row in db.execute(text(f"EXPLAIN {compiled}")))


@pytest.fixture
def postgres_only(db: Session) -> None:
    if db.get_bind().dialect.name != "postgresql":
        pytest.skip("Postgres only: the index plan is checked in ci-postgres")


@pytest.mark.parametrize(
    ("model", "address"),
    [
        (Reviewer, Reviewer.email),
        (Reviewee, Reviewee.email_or_identifier),
        (Observer, Observer.email),
    ],
)
def test_a_roster_rows_account_match_uses_the_index(
    db: Session, postgres_only: None, model, address
) -> None:
    viewer = Viewer.from_parts("someone@example.edu", ID.upper())
    by_account = viewer.clause(model, address).clauses[0]
    plan = _plan(db, select(model.id).where(by_account))
    assert f"ix_{model.__tablename__}_directory_object_id" in plan, plan


def test_a_user_by_principal_uses_the_index(db: Session, postgres_only: None) -> None:
    plan = _plan(db, users_by_principal(ID.upper()))
    assert "ix_users_external_principal_id" in plan, plan
