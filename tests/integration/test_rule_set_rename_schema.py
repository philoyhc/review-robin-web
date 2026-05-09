"""Schema-level coverage for Segment 13D PR 0 — rename of
``rule_sets`` to ``operator_rule_sets``.

The rest of the rule-set persistence contract is exercised by
``test_rule_set_schema.py`` (which uses the ORM and therefore
keeps passing through the rename — the ``RuleSet`` class is
unchanged, only its ``__tablename__`` flipped).

This file is the gate that proves the table is genuinely named
``operator_rule_sets`` post-migration, by reaching it via raw
SQL on the table name. If the rename migration regressed, the
ORM tests would still pass (SQLAlchemy resolves the table
through the class) but the raw-SQL queries here would error.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import RuleSet, RuleSetRevision, User


def _make_user(db: Session, email: str) -> User:
    user = User(email=email, display_name=email.split("@", 1)[0])
    db.add(user)
    db.flush()
    return user


def test_table_reachable_under_new_name(db: Session) -> None:
    """Inserting via the ORM and reading back via raw SQL on the
    new table name proves the rename took effect."""

    owner = _make_user(db, "renamed-rt@example.edu")
    rs = RuleSet(
        name="post-rename",
        scope="personal",
        owner_user_id=owner.id,
        is_seed=False,
    )
    db.add(rs)
    db.flush()

    rows = db.execute(
        text(
            "SELECT id, name FROM operator_rule_sets "
            "WHERE id = :rid"
        ),
        {"rid": rs.id},
    ).all()
    assert rows == [(rs.id, "post-rename")]


def test_old_table_name_no_longer_resolves(db: Session) -> None:
    """Sanity gate: the pre-rename name is gone. Tested via raw SQL
    so a stray ORM mapping doesn't mask a forgotten migration."""

    from sqlalchemy.exc import OperationalError, ProgrammingError

    import pytest

    with pytest.raises((OperationalError, ProgrammingError)):
        db.execute(text("SELECT 1 FROM rule_sets LIMIT 1"))


def test_rule_set_revisions_fk_still_cascades(db: Session) -> None:
    """The FK from ``rule_set_revisions.rule_set_id`` to the renamed
    ``operator_rule_sets.id`` continues to cascade on delete. Verifies
    the cross-table FK reference survived the rename on both SQLite
    (which stores FKs textually) and Postgres (which stores them by
    object id)."""

    owner = _make_user(db, "fk-cascade@example.edu")
    rs = RuleSet(
        name="cascade-victim",
        scope="personal",
        owner_user_id=owner.id,
        is_seed=False,
    )
    db.add(rs)
    db.flush()
    rev = RuleSetRevision(
        rule_set_id=rs.id,
        revision_no=1,
        combinator="ALL_OF",
        exclude_self_reviews=True,
        rules_json=[],
        created_at=datetime(2026, 5, 9, tzinfo=timezone.utc),
    )
    db.add(rev)
    db.flush()
    rev_id = rev.id

    db.delete(rs)
    db.flush()

    assert (
        db.execute(
            select(RuleSetRevision).where(RuleSetRevision.id == rev_id)
        ).scalar_one_or_none()
        is None
    )
