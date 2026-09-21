"""19R Item 2 rung 3 — the reconcile cache, read-through and write-through.

Rungs 1 and 2 landed storage and a stamp; this is where they are
actually used, and the thing to prove is not that the verdict is
correct — ``tests/unit/test_assignment_staleness.py`` already holds
that — but that it is **still correct while being served from a
cache**. Those are different claims, and a cache that never hits
satisfies the first one perfectly.

So every test here counts engine walks. ``_diff_one_instrument`` is
the engine walk, and the fixture below wraps it, so "served from the
cache" and "recomputed" are assertions about what the code did rather
than about what it returned.

The pairing matters in both directions:

- a **hit** must be provable, or the cache is decoration and the pages
  stay slow;
- a **miss** must be provable for every input the verdict is derived
  from, because a stamp that stays equal while the answer changes is
  the badge lying — the failure ``app/services/validation.py`` records
  this signal having had once already.
"""

from __future__ import annotations

from typing import Callable

import pytest
from sqlalchemy.orm import Session

from app.db.models import (
    Relationship,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionRuleSet,
    User,
)
from app.services import assignments
from app.services.assignments import _generate
from app.services.instruments import ensure_default_instrument


class EngineRuns:
    """How many times the engine walked since the last :meth:`reset`."""

    def __init__(self) -> None:
        self.count = 0

    def reset(self) -> None:
        self.count = 0


@pytest.fixture
def engine_runs(monkeypatch: pytest.MonkeyPatch) -> EngineRuns:
    """Count calls to ``_diff_one_instrument`` — one per instrument per
    reconcile walk, and the thing this whole item exists to avoid.

    Wrapped rather than stubbed: the real diff still runs, so a test
    that counts zero walks is also asserting the *cached* answer was
    right, not merely that nothing happened.
    """
    runs = EngineRuns()
    original = _generate._diff_one_instrument

    def counting(*args: object, **kwargs: object) -> object:
        runs.count += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(_generate, "_diff_one_instrument", counting)
    return runs


def _seed(
    db: Session,
    *,
    code: str,
    exclude_self: bool = False,
    self_reviewer: bool = False,
):
    user = User(email=f"op-{code}@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="Spring", code=code, created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()

    reviewers = [
        Reviewer(
            session_id=review_session.id,
            name="Alice",
            email="alice@example.edu",
            tag_1="Team A",
        ),
        Reviewer(
            session_id=review_session.id,
            name="Bob",
            email="bob@example.edu",
            tag_1="Team B",
        ),
    ]
    reviewees = [
        Reviewee(
            session_id=review_session.id,
            name="Carol",
            email_or_identifier="carol@example.edu",
            tag_1="Team A",
        ),
        Reviewee(
            session_id=review_session.id,
            name="Dan",
            email_or_identifier="dan@example.edu",
            tag_1="Team B",
        ),
    ]
    if self_reviewer:
        # Alice is also a reviewee, so the self-review rule has
        # something to exclude and the count is above zero.
        reviewees.append(
            Reviewee(
                session_id=review_session.id,
                name="Alice",
                email_or_identifier="alice@example.edu",
                tag_1="Team A",
            )
        )
    db.add_all([*reviewers, *reviewees])
    db.flush()

    relationship = Relationship(
        session_id=review_session.id,
        reviewer_id=reviewers[0].id,
        reviewee_id=reviewees[0].id,
        tag_1="mentor",
    )
    db.add(relationship)
    db.flush()

    instrument = ensure_default_instrument(db, review_session)
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
    return user, review_session, instrument, reviewers, reviewees, rule_set


def _generate_rows(db: Session, *, review_session, user, cid: str) -> None:
    assignments.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        correlation_id=cid,
    )
    db.flush()


def _read(db: Session, review_session, instrument):
    return assignments.staleness_by_instrument(db, review_session)[
        instrument.id
    ]


def _go_cold(db: Session, instrument) -> None:
    """Put the instrument back in the state every row is in after the
    rung-1 migration: stamped by nobody."""
    instrument.cached_reconcile_stamp = None
    instrument.cached_reconcile_stale = None
    instrument.cached_reconcile_eligible = None
    instrument.cached_reconcile_self_reviews_excluded = None
    db.flush()
    db.commit()


# --- the hit ---------------------------------------------------------


def test_generate_leaves_the_verdict_warm(
    db: Session, engine_runs: EngineRuns
) -> None:
    """The write-through is the point: Generate has just diffed, so the
    first render after it should not diff again."""
    user, review_session, instrument, *_ = _seed(db, code="rc-warm")
    _generate_rows(db, review_session=review_session, user=user, cid="c1")

    engine_runs.reset()
    state = _read(db, review_session, instrument)
    assert engine_runs.count == 0
    assert state.stale is False
    assert state.eligible == 4


def test_a_cold_instrument_warms_within_the_session(
    db: Session, engine_runs: EngineRuns
) -> None:
    """One walk, then none — and the ``1`` is the anti-vacuity control
    for every ``0`` in this file. If the probe counted nothing, the
    hits above would prove nothing either.

    **Within the session**, deliberately. The read path flushes the
    warm and does not commit it, so across two real requests this warm
    survives only if something downstream commits. What makes the cache
    durable is the write-through, which the test above covers; this one
    covers the read path's own half.
    """
    user, review_session, instrument, *_ = _seed(db, code="rc-cold")
    _generate_rows(db, review_session=review_session, user=user, cid="c1")
    _go_cold(db, instrument)

    engine_runs.reset()
    first = _read(db, review_session, instrument)
    assert engine_runs.count == 1

    engine_runs.reset()
    second = _read(db, review_session, instrument)
    assert engine_runs.count == 0
    assert second == first


def test_a_hit_carries_eligible_and_self_reviews_excluded(
    db: Session, engine_runs: EngineRuns
) -> None:
    """Both counts, not just the verdict — the Assignments view renders
    them, which is why the cache holds four columns instead of two.

    ``self_reviews_excluded`` is asserted above zero: it is evidence
    that the rule dropped something, so a cache serving ``0`` for it
    would be indistinguishable from a roster with nothing to drop.
    """
    user, review_session, instrument, *_ = _seed(
        db, code="rc-counts", exclude_self=True, self_reviewer=True
    )
    _generate_rows(db, review_session=review_session, user=user, cid="c1")

    engine_runs.reset()
    state = _read(db, review_session, instrument)
    assert engine_runs.count == 0
    assert state.self_reviews_excluded == 1
    assert state.eligible == 5


# --- the miss --------------------------------------------------------


def _add_a_reviewer(db: Session, ctx) -> None:
    _, review_session, _, _, _, _ = ctx
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Erin",
            email="erin@example.edu",
        )
    )
    db.flush()
    db.commit()


def _edit_the_relationship(db: Session, ctx) -> None:
    _, review_session, _, reviewers, reviewees, _ = ctx
    row = (
        db.query(Relationship)
        .filter(Relationship.session_id == review_session.id)
        .one()
    )
    row.tag_1 = "peer"
    db.flush()
    db.commit()


def _change_the_rule(db: Session, ctx) -> None:
    *_, rule_set = ctx
    rule_set.rules_json = [
        {
            "id": "team-a-only",
            "kind": "MATCH",
            "enabled": True,
            "predicate": {
                "field": "reviewer.tag1",
                "operator": "equals",
                "operand": "Team A",
                "case_sensitive": False,
            },
        }
    ]
    db.flush()
    db.commit()


def _repin_the_instrument(db: Session, ctx) -> None:
    _, review_session, instrument, _, _, _ = ctx
    other = SessionRuleSet(
        session_id=review_session.id,
        name="Another",
        description="",
        combinator="ALL_OF",
        exclude_self_reviews=False,
        seed=None,
        rules_json=[],
    )
    db.add(other)
    db.flush()
    instrument.rule_set_id = other.id
    db.flush()
    db.commit()


def _flip_self_reviews(db: Session, ctx) -> None:
    _, review_session, _, _, _, _ = ctx
    review_session.self_reviews_active = not review_session.self_reviews_active
    db.flush()
    db.commit()


def _unpin_the_instrument(db: Session, ctx) -> None:
    _, _, instrument, _, _, _ = ctx
    instrument.rule_set_id = None
    db.flush()
    db.commit()


MISS_CASES: list[tuple[str, Callable[[Session, tuple], None]]] = [
    ("a reviewer joins the roster", _add_a_reviewer),
    ("a relationship tag is edited", _edit_the_relationship),
    ("the pinned rule's predicates change", _change_the_rule),
    ("the instrument is re-pinned", _repin_the_instrument),
    ("the instrument is unpinned", _unpin_the_instrument),
    ("the session's self-review toggle flips", _flip_self_reviews),
]


@pytest.mark.parametrize(
    "mutate", [c[1] for c in MISS_CASES], ids=[c[0] for c in MISS_CASES]
)
def test_every_input_recomputes_the_verdict(
    db: Session,
    engine_runs: EngineRuns,
    mutate: Callable[[Session, tuple], None],
) -> None:
    ctx = _seed(db, code="rc-miss")
    user, review_session, instrument, *_ = ctx
    _generate_rows(db, review_session=review_session, user=user, cid="c1")

    # Warm, and prove it: without this the "recomputed" below could be
    # a cache that was never populated in the first place.
    engine_runs.reset()
    _read(db, review_session, instrument)
    assert engine_runs.count == 0

    mutate(db, ctx)

    engine_runs.reset()
    _read(db, review_session, instrument)
    assert engine_runs.count == 1


def test_adding_a_reviewer_is_seen_as_stale_through_the_cache(
    db: Session, engine_runs: EngineRuns
) -> None:
    """The miss above proves the engine ran; this proves the answer it
    produced reached the caller. A cache that recomputed and then
    returned its stale copy would pass the other test."""
    ctx = _seed(db, code="rc-stale")
    user, review_session, instrument, *_ = ctx
    _generate_rows(db, review_session=review_session, user=user, cid="c1")
    assert _read(db, review_session, instrument).stale is False

    _add_a_reviewer(db, ctx)

    after = _read(db, review_session, instrument)
    assert after.stale is True
    assert after.eligible == 6


def test_regenerating_clears_a_stale_verdict_without_a_further_walk(
    db: Session, engine_runs: EngineRuns
) -> None:
    """The case the whole design turns on. The verdict is a diff
    against the materialised rows, so Generate changes the answer while
    every engine input holds still — without the write-through and the
    row-set component of the stamp, the cached ``stale=True`` would
    outlive the regenerate that made it fresh."""
    ctx = _seed(db, code="rc-regen")
    user, review_session, instrument, *_ = ctx
    _generate_rows(db, review_session=review_session, user=user, cid="c1")
    _add_a_reviewer(db, ctx)
    assert _read(db, review_session, instrument).stale is True

    _generate_rows(db, review_session=review_session, user=user, cid="c2")

    engine_runs.reset()
    state = _read(db, review_session, instrument)
    assert engine_runs.count == 0
    assert state.stale is False
    assert state.eligible == 6


# --- the write-back guard --------------------------------------------


def test_a_read_never_commits(
    db: Session, engine_runs: EngineRuns, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The read path warms the cache but must not commit, because it
    runs inside a render that has its own writes in flight: the
    workflow card runs validation and then, on the ``?validated=1``
    entry, promotes ``draft → validated`` in the same request.
    Committing a cache row is not worth reaching into that.

    Asserted against the session rather than against the database,
    because "did not commit" is a statement about what the code did.
    """
    user, review_session, instrument, *_ = _seed(db, code="rc-nocommit")
    _generate_rows(db, review_session=review_session, user=user, cid="c1")
    _go_cold(db, instrument)

    commits = 0
    original_commit = db.commit

    def counting_commit() -> None:
        nonlocal commits
        commits += 1
        original_commit()

    monkeypatch.setattr(db, "commit", counting_commit)

    engine_runs.reset()
    state = _read(db, review_session, instrument)

    assert engine_runs.count == 1
    assert commits == 0
    # The warm did happen — it is simply the caller's to commit.
    assert instrument.cached_reconcile_stamp is not None
    assert state.eligible == 4
