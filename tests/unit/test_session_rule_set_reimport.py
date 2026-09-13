"""Re-importing a Settings CSV cannot trip ``uq_session_rule_set_session_name``.

`spec/csv_contracts.md` §4 item 7 claimed the export **filters out** seeded
rule sets because "re-emitting would either no-op or trip
``uq_session_rule_set_session_name``". Both halves of that were stale:

* nothing seeds a rule set on session create — the seeding helper went with
  the rule-set library, so every row is operator-authored; and
* ``_apply_session_rule_sets`` is an **upsert by name**, so a row whose name
  already exists in the destination is *updated*, never inserted. The unique
  constraint is unreachable from this path.

The serializer emits every row (``_non_seeded_session_rule_sets`` is
"every row for the session" despite its name). These tests pin the behaviour
that makes that safe, because *the guarantee had been resting on a claim
nobody could check* — the spec even cited a test file that does not exist.

**The single-session re-import case is already covered** by
``tests/unit/test_apply_session_config.py::test_empty_rules_json_round_trips_unchanged``,
which serialises, applies over the same session, and asserts the export is
byte-identical — and because the row exists before that apply, it already
exercises the update branch. It is not repeated here.

The duplicate-name case is the one place a collision could reach the database:
``_apply_session_rule_sets`` calls ``db.add`` per row without flushing between
them, so two rows sharing a name would both insert. It never gets that far —
the parse phase rejects the bundle first, which is the behaviour the third
test holds.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, SessionRuleSet, User
from app.services.session_config_io import (
    Row,
    apply_session_config,
    serialize_session_config,
)


def _user(db: Session, email: str) -> User:
    user = User(email=email, display_name=email.split("@", 1)[0])
    db.add(user)
    db.flush()
    return user


def _session(db: Session, code: str) -> ReviewSession:
    user = _user(db, f"op-{code}@example.edu")
    review_session = ReviewSession(
        name=code.title(), code=code, created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    return review_session


def _rule_set(db: Session, review_session: ReviewSession, name: str) -> SessionRuleSet:
    rule_set = SessionRuleSet(
        session_id=review_session.id,
        name=name,
        description="d",
        combinator="ALL_OF",
        exclude_self_reviews=False,
        seed=None,
        rules_json=[],
    )
    db.add(rule_set)
    db.flush()
    return rule_set


def _names(db: Session, review_session: ReviewSession) -> list[str]:
    return list(
        db.execute(
            select(SessionRuleSet.name).where(
                SessionRuleSet.session_id == review_session.id
            )
        )
        .scalars()
        .all()
    )


def test_import_into_a_session_that_already_carries_the_name(db: Session) -> None:
    """The collision the retired claim was about: the destination already has it.

    Upsert-by-name updates the existing row, so the count does not grow and
    the constraint is never reached.
    """
    source = _session(db, "rsr2")
    _rule_set(db, source, "Full Matrix")
    rows = serialize_session_config(db, source)

    destination = _session(db, "rsr3")
    _rule_set(db, destination, "Full Matrix")

    apply_session_config(db, destination, rows)

    assert _names(db, destination) == ["Full Matrix"]


def test_two_rows_sharing_a_name_are_rejected_before_any_write(db: Session) -> None:
    """A hand-edited bundle naming one rule set twice fails the parse phase.

    This is the only path that could reach the unique constraint, because the
    apply loop adds without flushing between rows. The rejection is a clean
    ``ApplyError`` in ``ApplyResult.errors`` — not an ``IntegrityError`` — and
    phase 2 never runs, so nothing is written.
    """
    review_session = _session(db, "rsr4")

    def _row_set(index: int, name: str) -> list[Row]:
        prefix = f"session_rule_sets[{index}]"
        return [
            Row(f"{prefix}.name", name, "string"),
            Row(f"{prefix}.description", "d", "string"),
            Row(f"{prefix}.combinator", "ALL_OF", "enum"),
            Row(f"{prefix}.exclude_self_reviews", "false", "boolean"),
            Row(f"{prefix}.seed", "", "integer"),
            Row(f"{prefix}.rules_json", "[]", "json"),
        ]

    result = apply_session_config(
        db, review_session, _row_set(1, "Dupe") + _row_set(2, "Dupe")
    )

    assert result.errors, "a duplicate name must be reported, not written"
    assert any(
        "duplicate session_rule_sets name" in error.message for error in result.errors
    ), result.errors
    assert _names(db, review_session) == [], "phase 2 must not have run"
