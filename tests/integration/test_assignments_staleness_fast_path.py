"""post_assessment_1oct E5 — the reconcile verdict before the first Prepare.

At 1,000 x 1,000 the Assignments and Validate pages took 6.5 and 7.3 s
on every load before the first Prepare: ``staleness_by_instrument``
walked the Full Matrix default's 1,000,000 pairs, and the cache it
warmed was flushed but never committed on a GET. Two changes, each
held here:

- **Counted, not walked.** An instrument on the Full Matrix default
  with no rows gets its verdict from
  ``_full_matrix_never_generated_state``. It must equal what the walk
  reports, so the parity tests below run both on a roster built to
  catch the edges — case and whitespace in addresses, two reviewers on
  one address, a reviewee identifier held twice, inactive rows on both
  sides, an empty address, a non-email identifier that matches a
  reviewer (the engine needs no "@") — with the override in all three
  states, on a per-reviewee and a group-scoped instrument.
- **Committed on GET.** ``persist_reconcile_warm`` commits a warm the
  request made, and the two page routes call it. The service itself
  still never commits (``test_reconcile_cache_wiring.py``).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Reviewee, Reviewer, ReviewSession, User
from app.services import assignments
from app.services.assignments import _generate
from app.services.instruments import ensure_default_instrument


def _seed(
    db: Session, code: str, group_kind: str | None = None
) -> tuple[ReviewSession, object]:
    user = User(email=f"op-{code}@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(name="Fast", code=code, created_by_user_id=user.id)
    db.add(review_session)
    db.flush()
    sid = review_session.id
    db.add_all(
        [
            Reviewer(session_id=sid, name="Alice", email="Alice@Example.edu"),
            Reviewer(session_id=sid, name="Bob", email="bob@example.edu"),
            Reviewer(session_id=sid, name="Bob twin", email=" bob@example.edu "),
            Reviewer(session_id=sid, name="Cy", email="cy@example.edu", status="inactive"),
            Reviewer(session_id=sid, name="Blank", email=""),
            Reviewer(session_id=sid, name="Code", email="R-0042"),
            Reviewee(session_id=sid, name="Alice", email_or_identifier="alice@example.edu"),
            Reviewee(session_id=sid, name="Bob", email_or_identifier="BOB@example.edu"),
            Reviewee(
                session_id=sid,
                name="Cy",
                email_or_identifier="cy@example.edu",
                status="inactive",
            ),
            Reviewee(session_id=sid, name="Cy again", email_or_identifier="CY@example.edu"),
            Reviewee(session_id=sid, name="Blank", email_or_identifier=""),
            Reviewee(session_id=sid, name="Anon", email_or_identifier="R-0042"),
        ]
    )
    db.flush()
    instrument = ensure_default_instrument(db, review_session)
    assert instrument.rule_set_id is None  # the Full Matrix default
    instrument.group_kind = group_kind
    db.flush()
    return review_session, instrument


@pytest.mark.parametrize("group_kind", [None, "r1"], ids=["per-reviewee", "group"])
@pytest.mark.parametrize("override", [None, False, True])
def test_the_count_equals_the_walk(
    db: Session, override: bool | None, group_kind: str | None
) -> None:
    review_session, instrument = _seed(db, f"fp-parity-{override}-{group_kind}", group_kind)
    inputs = _generate._load_reconcile_inputs(db, review_session, None)

    walked = _generate._diff_one_instrument(
        db,
        review_session=review_session,
        instrument=instrument,
        session_rule_set=None,
        reviewers=inputs.reviewers,
        reviewees=inputs.reviewees,
        pair_context_lookup=inputs.pair_context_lookup,
        override_exclude_self_reviews=override,
    )
    counted = _generate._full_matrix_never_generated_state(
        inputs.reviewers,
        inputs.reviewees,
        override_exclude_self_reviews=override,
    )

    assert not walked.existing_rows
    assert counted.stale is False
    assert counted.eligible == walked.pairs_count
    assert counted.self_reviews_excluded == walked.excluded_counts.get("self_review", 0)
    # Six self-review pairs, by the engine's test: Alice once, each Bob
    # once, Cy (inactive) against both Cy identifiers, and the "R-0042"
    # code against itself; the blank address matches nothing. So the
    # override's exclusion is exercised, not vacuous.
    assert counted.self_reviews_excluded == (6 if override else 0)


def test_a_never_generated_full_matrix_instrument_is_not_walked(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    review_session, instrument = _seed(db, "fp-nowalk")

    def walk(*args: object, **kwargs: object) -> object:
        raise AssertionError("the fast path walked the matrix")

    monkeypatch.setattr(_generate, "_diff_one_instrument", walk)
    state = assignments.staleness_by_instrument(db, review_session)[instrument.id]

    assert state.stale is False
    assert state.eligible == 36
    # Warmed for the caller to commit, and marked so a GET can.
    assert instrument.cached_reconcile_stamp is not None
    assert db.info.get(_generate._RECONCILE_WARM_PENDING) is True


def test_persist_commits_only_a_warm(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    commits: list[None] = []
    original = db.commit
    monkeypatch.setattr(db, "commit", lambda: (commits.append(None), original()))

    db.info.pop(_generate._RECONCILE_WARM_PENDING, None)
    assignments.persist_reconcile_warm(db)
    assert commits == []

    review_session, _ = _seed(db, "fp-persist")
    assignments.staleness_by_instrument(db, review_session)
    assignments.persist_reconcile_warm(db)
    assert len(commits) == 1
    assert _generate._RECONCILE_WARM_PENDING not in db.info


@pytest.mark.parametrize("suffix", ["/assignments", "/validate"])
def test_the_page_gets_commit_their_warm(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch, suffix: str
) -> None:
    response = client.post(
        "/operator/sessions",
        data={"name": "Pages", "code": f"fp-page{suffix.strip('/')}"},
        follow_redirects=False,
    )
    session_id = int(response.headers["location"].split("?")[0].rsplit("/", 1)[1])
    calls: list[Session] = []
    original = assignments.persist_reconcile_warm
    monkeypatch.setattr(
        assignments,
        "persist_reconcile_warm",
        lambda session: (calls.append(session), original(session)),
    )

    commits: list[None] = []
    original_commit = db.commit
    monkeypatch.setattr(db, "commit", lambda: (commits.append(None), original_commit()))
    db.info.pop(_generate._RECONCILE_WARM_PENDING, None)

    assert client.get(f"/operator/sessions/{session_id}{suffix}").status_code == 200
    # The cold first load warmed the verdict, and the route committed it.
    assert len(calls) == 1
    assert commits, "the warm was not committed"
    assert _generate._RECONCILE_WARM_PENDING not in db.info
