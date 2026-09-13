"""``staleness_by_instrument`` — the signal restored in Segment 19N.

A ``stale`` pill was specified in ``spec/assignments.md`` and then
switched off: ``views/_assignments.py`` hardcoded ``is_stale = False``
because the per-rule eligibility helper that fed ``compute_staleness``
retired, and without it every pinned instrument read as stale. The
comment recording that was right about the failure mode — *an
always-stale badge trains the operator to ignore it* — and the fix was to
turn the signal off rather than re-base it, which left three consumers
dead: the pill, the ``any_stale`` aggregate (retired in turn once its
only consumer was), and the ``instruments.stale_generated`` validation
rule, which stayed in the
registry as a **no-op** with a severity, a fix link, and a ``why``
describing exactly the situation it no longer detected.

**The basis is now the engine's own diff**, and the two tests that matter
here are the ones proving the old basis was wrong in kind, not merely
unavailable:

- ``test_a_swap_that_keeps_the_count_equal_is_still_stale`` — the old
  predicate compared ``eligible_count != generated_count``. Swapping one
  reviewer for another leaves the totals identical and the *set*
  different, so a count basis reports "fresh" on a session whose pairs
  have entirely moved.
- ``test_an_unpinned_full_matrix_instrument_can_go_stale`` — the old
  predicate also required ``rule_id is not None``. Since Wave 5 PR 5.3 a
  NULL ``rule_set_id`` is the Full Matrix default at the diff site, so
  unpinned instruments generate like any other and can fall out of step
  like any other.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionRuleSet,
    User,
)
from app.services import assignments
from app.services.instruments import ensure_default_instrument


def _seed(
    db: Session, *, code: str, pin: bool = True, exclude_self: bool = False
):
    user = User(email=f"op-{code}@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="Spring", code=code, created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    db.add_all(
        [
            Reviewer(
                session_id=review_session.id,
                name="Alice",
                email="alice@example.edu",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Carol",
                email_or_identifier="carol@example.edu",
            ),
        ]
    )
    db.flush()
    instrument = ensure_default_instrument(db, review_session)
    if pin:
        rule_set = SessionRuleSet(
            session_id=review_session.id,
            name="Full Matrix",
            description="",
            combinator="ALL_OF",
            exclude_self_reviews=exclude_self,
            seed=None,
            rules_json=[],
        )
        db.add(rule_set)
        db.flush()
        instrument.rule_set_id = rule_set.id
    db.flush()
    return user, review_session, instrument


def _generate(db: Session, *, review_session, user, cid: str) -> None:
    assignments.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        correlation_id=cid,
    )
    db.flush()


def _state(db: Session, review_session, instrument):
    return assignments.staleness_by_instrument(db, review_session)[
        instrument.id
    ]


def test_freshly_generated_is_not_stale(db: Session) -> None:
    user, review_session, instrument = _seed(db, code="stale-fresh")
    _generate(db, review_session=review_session, user=user, cid="c1")
    assert _state(db, review_session, instrument).stale is False


def test_never_generated_is_not_stale(db: Session) -> None:
    """The false positive that retired the previous signal.

    A run would insert this instrument's whole fan-out, so a naive
    "would a run change anything" reports stale on every fresh session.
    Not-yet-generated has its own carriers — the Workflow card's Generate
    step and the ``assignments.*`` empty rules.
    """
    _user, review_session, instrument = _seed(db, code="stale-never")
    assert _state(db, review_session, instrument).stale is False


def test_a_reviewer_added_after_generate_is_stale(db: Session) -> None:
    user, review_session, instrument = _seed(db, code="stale-added")
    _generate(db, review_session=review_session, user=user, cid="c1")
    db.add(
        Reviewer(
            session_id=review_session.id, name="Bob", email="bob@example.edu"
        )
    )
    db.flush()
    assert _state(db, review_session, instrument).stale is True


def _tag_rule(tag: str) -> list[dict]:
    return [
        {
            "id": "link1",
            "kind": "COMPOSITE",
            "enabled": True,
            "op": "AND",
            "rules": [
                {
                    "id": "link1-r0",
                    "kind": "MATCH",
                    "enabled": True,
                    "predicate": {
                        "field": "reviewer.tag1",
                        "operator": "equals",
                        "operand": tag,
                        "case_sensitive": False,
                    },
                }
            ],
        }
    ]


def test_a_rule_change_that_keeps_the_count_equal_is_still_stale(
    db: Session,
) -> None:
    """The case a count-based predicate cannot see.

    ``eligible_count != generated_count`` was the retired basis. Here the
    rule is repointed from one reviewer tag to another: the engine
    produces exactly as many pairs as exist, and a **disjoint set** of
    them. A count comparison reports "fresh" on a session whose every
    assignment names a reviewer the rule no longer selects.

    **Why a rule change and not a roster edit.** Deleting a roster entry
    cascades its assignment rows away, so a swap leaves the counts
    unequal and a count basis catches it by accident. The first version
    of this test did exactly that and **passed under both bases** — a
    mutation reinstating the count comparison escaped it. Equal-count
    drift is the only state that discriminates them, and under Full
    Matrix no pair is ever ineligible, so it takes a rule predicate to
    build.
    """
    user, review_session, instrument = _seed(db, code="stale-rule")
    alice = db.query(Reviewer).filter_by(
        session_id=review_session.id, email="alice@example.edu"
    ).one()
    alice.tag_1 = "Lead"
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Dan",
            email="dan@example.edu",
            tag_1="Peer",
        )
    )
    rule_set = db.query(SessionRuleSet).filter_by(
        session_id=review_session.id
    ).one()
    rule_set.rules_json = _tag_rule("Lead")
    db.flush()

    _generate(db, review_session=review_session, user=user, cid="c1")
    before = _state(db, review_session, instrument)
    assert before.stale is False
    rows = db.query(Assignment).filter_by(session_id=review_session.id).all()
    assert [r.reviewer_id for r in rows] == [alice.id], (
        "the rule should select only the Lead-tagged reviewer"
    )

    rule_set.rules_json = _tag_rule("Peer")
    db.flush()

    after = _state(db, review_session, instrument)
    assert after.eligible == before.eligible, (
        "this test is only meaningful while the pair count is unchanged; "
        f"{before.eligible} -> {after.eligible}"
    )
    assert after.stale is True


def test_a_narrowed_rule_that_only_deletes_pairs_is_stale(
    db: Session,
) -> None:
    """Staleness is not only about pairs that are missing.

    An operator tightening a rule leaves rows the engine would no longer
    produce and nothing new to add — ``to_delete`` is non-empty and
    ``to_insert`` is empty. A predicate watching only for *missing* pairs
    calls this fresh while the page still shows assignments for reviewers
    the rule has dropped. Found by a mutation that ignored ``to_delete``
    and escaped every other case here, because each of those happens to
    insert something too.
    """
    user, review_session, instrument = _seed(db, code="stale-narrow")
    alice = db.query(Reviewer).filter_by(
        session_id=review_session.id, email="alice@example.edu"
    ).one()
    alice.tag_1 = "Lead"
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Dan",
            email="dan@example.edu",
            tag_1="Peer",
        )
    )
    db.flush()
    _generate(db, review_session=review_session, user=user, cid="c1")
    before = _state(db, review_session, instrument)
    assert before.stale is False
    assert before.eligible == 2

    rule_set = db.query(SessionRuleSet).filter_by(
        session_id=review_session.id
    ).one()
    rule_set.rules_json = _tag_rule("Lead")
    db.flush()

    after = _state(db, review_session, instrument)
    assert after.eligible == 1, "the narrowed rule should select one pair"
    assert after.stale is True


def test_an_unpinned_full_matrix_instrument_can_go_stale(
    db: Session,
) -> None:
    """The case a ``rule_id is not None`` gate cannot see.

    The instrument carries no pinned rule, which since Wave 5 PR 5.3
    means Full Matrix at the diff site rather than "skipped".
    """
    user, review_session, instrument = _seed(
        db, code="stale-unpinned", pin=False
    )
    assert instrument.rule_set_id is None
    _generate(db, review_session=review_session, user=user, cid="c1")
    assert _state(db, review_session, instrument).stale is False

    db.add(
        Reviewer(
            session_id=review_session.id, name="Bob", email="bob@example.edu"
        )
    )
    db.flush()
    assert _state(db, review_session, instrument).stale is True


def test_eligible_carries_the_engine_fan_out(db: Session) -> None:
    """``eligible`` was always 0 — the field's docstring promised "pairs
    the engine would produce if run" and the dict feeding it was never
    populated."""
    user, review_session, instrument = _seed(db, code="stale-eligible")
    _generate(db, review_session=review_session, user=user, cid="c1")
    assert _state(db, review_session, instrument).eligible == 1
