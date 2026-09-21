"""19R Item 3 rung 1 — the parity oracle for the monitoring rollups.

Item 3 replaces the Python rollups behind the Invitations and Responses
pages (`monitoring.per_reviewer_progress` and `per_reviewee_coverage`)
with aggregate queries. The risk is not that the new form is slow; it is
that it is **subtly different**, and the differences live exactly where a
plain `GROUP BY` does not reach:

- a group-scoped instrument counts **once per group**, not once per
  member, so the reviewer rollup collapses member rows before counting;
- `include=False` rows are excluded;
- the two functions disagree with each other about inactive reviewers,
  on purpose — see `test_an_inactive_reviewer_is_excluded_one_side_only`.

So this rung lands the oracle before anything depends on it: one fixture
carrying all three, and expectations **derived by hand from the
contract** rather than captured from a run. Each expectation below shows
its arithmetic, so a reader can check the number rather than trust it.

**The implementation lists are the harness.** Today each holds one
entry, so these tests pin the Python implementation's answers. Rungs 2
and 3 add the SQL implementation to the same list and every case below
becomes a parity test with no new test code — which is the point of
proving the oracle first.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable

import pytest
from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Instrument,
    InstrumentResponseField,
    Invitation,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services import monitoring

#: Implementations under test. One entry each today; rungs 2 and 3 append
#: the SQL form, and every case below runs against both.
REVIEWER_IMPLEMENTATIONS: list[tuple[str, Callable]] = [
    # Rung 3 added the split form — per-reviewee instruments in one
    # aggregate, group-scoped ones still in Python, the two halves
    # added. The old one stays until the item closes.
    ("python", monitoring._per_reviewer_progress_python),
    ("split", monitoring.per_reviewer_progress),
]
REVIEWEE_IMPLEMENTATIONS: list[tuple[str, Callable]] = [
    # Rung 2 added the aggregate form. The Python one stays until the
    # item closes: it is what the new one is checked against, and every
    # case below now runs twice with no new test code.
    ("python", monitoring._per_reviewee_coverage_python),
    ("sql", monitoring.per_reviewee_coverage),
]

reviewer_impl = pytest.mark.parametrize(
    "rollup",
    [impl for _, impl in REVIEWER_IMPLEMENTATIONS],
    ids=[name for name, _ in REVIEWER_IMPLEMENTATIONS],
)
reviewee_impl = pytest.mark.parametrize(
    "rollup",
    [impl for _, impl in REVIEWEE_IMPLEMENTATIONS],
    ids=[name for name, _ in REVIEWEE_IMPLEMENTATIONS],
)

T0 = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


class Fixture:
    """The session every case below reads, and the names to address it by."""

    def __init__(self, **kw: object) -> None:
        self.__dict__.update(kw)


@pytest.fixture
def rollups(db: Session) -> Fixture:
    """One session carrying every shape the rewrite has to preserve.

    Reviewers — `alice` and `bob` active, `zoe` **inactive**.
    Reviewees — `carol` and `dan` share `tag_1 = "Team A"`; `erin` is
    `"Team B"` alone.
    Instruments — `solo` is per-reviewee with one required and one
    optional field; `grouped` carries `group_kind = "r1"`, so it groups
    by `reviewee.tag_1` and carol + dan are one group.
    """
    user = User(email="op-r2parity@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="Spring", code="r2-parity", created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    sid = review_session.id

    alice = Reviewer(session_id=sid, name="Alice", email="alice@example.edu")
    bob = Reviewer(session_id=sid, name="Bob", email="bob@example.edu")
    zoe = Reviewer(
        session_id=sid,
        name="Zoe",
        email="zoe@example.edu",
        status="removed",
    )
    carol = Reviewee(
        session_id=sid,
        name="Carol",
        email_or_identifier="carol@example.edu",
        tag_1="Team A",
    )
    dan = Reviewee(
        session_id=sid,
        name="Dan",
        email_or_identifier="dan@example.edu",
        tag_1="Team A",
    )
    erin = Reviewee(
        session_id=sid,
        name="Erin",
        email_or_identifier="erin@example.edu",
        tag_1="Team B",
    )
    db.add_all([alice, bob, zoe, carol, dan, erin])
    db.flush()

    solo = Instrument(
        session_id=sid, name="Solo", order=0, session_seq=1, group_kind=None
    )
    grouped = Instrument(
        session_id=sid, name="Grouped", order=1, session_seq=2, group_kind="r1"
    )
    # A **second** group-scoped instrument on the same boundary tag, so
    # "Team A on `grouped`" and "Team A on `grouped2`" are distinct
    # units. A dedupe keyed on the group alone collapses them into one.
    grouped2 = Instrument(
        session_id=sid, name="Grouped Two", order=2, session_seq=3, group_kind="r1"
    )
    db.add_all([solo, grouped, grouped2])
    db.flush()

    q1 = InstrumentResponseField(
        instrument_id=solo.id, field_key="q1", label="Q1", required=True, order=0
    )
    q2 = InstrumentResponseField(
        instrument_id=solo.id, field_key="q2", label="Q2", required=False, order=1
    )
    g1 = InstrumentResponseField(
        instrument_id=grouped.id, field_key="g1", label="G1", required=True, order=0
    )
    g2 = InstrumentResponseField(
        instrument_id=grouped.id, field_key="g2", label="G2", required=False, order=1
    )
    h1 = InstrumentResponseField(
        instrument_id=grouped2.id, field_key="h1", label="H1", required=True, order=0
    )
    db.add_all([q1, q2, g1, g2, h1])
    db.flush()

    def assign(reviewer, reviewee, instrument, *, include=True) -> Assignment:
        row = Assignment(
            session_id=sid,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
            instrument_id=instrument.id,
            include=include,
        )
        db.add(row)
        return row

    a1 = assign(alice, carol, solo)
    a2 = assign(alice, dan, solo)
    a3 = assign(alice, carol, grouped)
    a4 = assign(alice, dan, grouped)
    a5 = assign(alice, erin, grouped)
    a6 = assign(bob, carol, solo, include=False)
    a7 = assign(bob, erin, solo)
    a8 = assign(zoe, erin, solo)
    a9 = assign(alice, carol, grouped2)
    a10 = assign(alice, dan, grouped2)
    db.flush()

    def respond(assignment, field, value, *, submitted_at) -> Response:
        row = Response(
            assignment_id=assignment.id,
            response_field_id=field.id,
            value=value,
            saved_at=T0,
            submitted_at=submitted_at,
        )
        db.add(row)
        return row

    # a1 answered and submitted; a2 submitted but with the required
    # field left empty; a3 answered; a5, a7 untouched; a8 answered but
    # belongs to the inactive reviewer.
    respond(a1, q1, "yes", submitted_at=T0)
    respond(a2, q1, "", submitted_at=T0 + timedelta(hours=1))
    # a3 carries **two** rows, and it is carol's *later* assignment.
    # Both facts are load-bearing for `last_response_at`, which is a max
    # over two nestings — the rows of one assignment, then the
    # assignments of one reviewee:
    #   * two rows at +6h and +2h, so taking the wrong one within an
    #     assignment gives +2h;
    #   * a3 after a1, whose only row is at +0h, so taking the first
    #     assignment with any stamp gives +0h.
    # Only a max over both nestings gives +6h.
    respond(a3, g1, "ok", submitted_at=T0 + timedelta(hours=6))
    respond(a3, g2, "note", submitted_at=T0 + timedelta(hours=2))
    respond(a8, q1, "yes", submitted_at=T0 + timedelta(hours=3))
    # A **draft**: a value typed but never submitted. The two rollups
    # read it differently on purpose — see
    # `test_a_draft_is_complete_to_one_rollup_and_not_the_other`.
    respond(a9, h1, "wip", submitted_at=None)

    # Invitations. `ReviewerProgress` carries the row and its
    # `last_reminder_at`, and `summary_counts` reads the status — so a
    # fixture without them lets an implementation drop the join and
    # still pass everything else, which would silently undercount
    # `invited` / `opened` and make both reminder loops skip every
    # reviewer. Alice has been opened and reminded; bob has been sent
    # and not opened; **zoe has none**, so "no invitation" is covered
    # too.
    db.add_all(
        [
            Invitation(
                session_id=sid,
                reviewer_id=alice.id,
                token_hash="tok-alice-r2parity",
                status="opened",
                sent_at=T0,
                opened_at=T0 + timedelta(hours=1),
                last_reminder_at=T0 + timedelta(hours=4),
            ),
            Invitation(
                session_id=sid,
                reviewer_id=bob.id,
                token_hash="tok-bob-r2parity",
                status="sent",
                sent_at=T0,
            ),
        ]
    )
    db.flush()

    return Fixture(
        session=review_session,
        alice=alice,
        bob=bob,
        zoe=zoe,
        carol=carol,
        dan=dan,
        erin=erin,
        solo=solo,
        grouped=grouped,
        grouped2=grouped2,
        a1=a1,
        a2=a2,
        a3=a3,
        a4=a4,
        a5=a5,
        a6=a6,
        a7=a7,
        a8=a8,
        a9=a9,
        a10=a10,
    )


def _utc_naive(value: datetime | None) -> datetime | None:
    """The same instant, as a naive UTC datetime.

    The columns are `DateTime(timezone=True)`, which Postgres honours
    and SQLite does not — a value written aware comes back naive there.
    So the oracle compares **instants**, not datetime objects, and a
    rung-2 aggregate returning an aware `MAX(submitted_at)` on Postgres
    still matches the naive one SQLite hands back.
    """
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _by_email(rows) -> dict[str, object]:
    return {row.reviewer.email: row for row in rows}


def _by_identifier(rows) -> dict[str, object]:
    return {row.reviewee.email_or_identifier: row for row in rows}


# --- the reviewer side -----------------------------------------------


@reviewer_impl
def test_reviewer_rows_are_the_right_reviewers_in_email_order(
    db: Session, rollups: Fixture, rollup: Callable
) -> None:
    """`zoe` is inactive. `bob`'s only other row is `include=False`, so
    he is present on the strength of a7 alone.

    Asserted as an **ordered list**, not a set: `_assigned_active_reviewers`
    orders by email, the operations routes paginate whatever order they
    are handed when no sort cookie is set, and an aggregate without an
    `ORDER BY` would return database order and still satisfy a set
    comparison — while rows moved between pages.
    """
    rows = rollup(db, rollups.session)
    assert [r.reviewer.email for r in rows] == [
        "alice@example.edu",
        "bob@example.edu",
    ]


@reviewer_impl
def test_a_group_counts_once_per_group_not_once_per_member(
    db: Session, rollups: Fixture, rollup: Callable
) -> None:
    """Alice holds seven included assignments, which are five units:

    | rows | unit |
    |---|---|
    | a1 — carol on `solo` | its own |
    | a2 — dan on `solo` | its own |
    | a3, a4 — carol + dan, `grouped`, Team A | **one** |
    | a5 — erin, `grouped`, Team B | its own |
    | a9, a10 — carol + dan, `grouped2`, Team A | **one** |

    This is the number a plain `GROUP BY` over assignments gets wrong,
    and the reason the plan keeps a hybrid on the table.
    """
    alice = _by_email(rollup(db, rollups.session))["alice@example.edu"]
    assert alice.assignment_count == 5


@reviewer_impl
def test_alices_progress_is_two_of_four_with_two_required_missing(
    db: Session, rollups: Fixture, rollup: Callable
) -> None:
    """Counted units: a1, a2, a3 (for Team A on `grouped`), a5, and a9
    (for Team A on `grouped2`).

    - a1 — `q1 = "yes"`, required satisfied → complete.
    - a2 — `q1 = ""`, so the required field is *present but empty*,
      which the contract counts as missing → not complete, 1 missing.
    - a3 — `g1 = "ok"` → complete.
    - a5 — no rows at all → not complete, 1 missing.
    - a9 — `h1 = "wip"`, a draft. Non-empty, so nothing is missing and
      this rollup calls it complete; the unsubmitted row is what keeps
      the pill off `submitted`.

    Five required fields across the five units, two of them unmet.
    `in progress` rather than `submitted` because a2 and a5 leave
    required fields unmet and a9 is unsubmitted, and not `not started`
    because three units carry answers.
    """
    alice = _by_email(rollup(db, rollups.session))["alice@example.edu"]
    assert alice.completed_count == 3
    assert alice.required_total == 5
    assert alice.missing_required_count == 2
    assert alice.required_done == 3
    assert alice.pill_state == "in progress"


@reviewer_impl
def test_the_invitation_and_its_reminder_ride_on_the_row(
    db: Session, rollups: Fixture, rollup: Callable
) -> None:
    """`ReviewerProgress` carries the reviewer's `Invitation` and
    surfaces `last_reminder_at` from it — the Invitations page renders
    both, and the manual and scheduled reminder loops filter on them.

    An implementation that dropped the join would return `None` for
    every reviewer and still satisfy every count in this file, so the
    join is asserted directly, in all three of its states: reminded,
    invited-but-never-reminded, and no invitation at all.
    """
    rows = _by_email(rollup(db, rollups.session))
    alice = rows["alice@example.edu"]
    assert alice.invitation is not None
    assert alice.invitation.status == "opened"
    assert _utc_naive(alice.last_reminder_at) == _utc_naive(
        T0 + timedelta(hours=4)
    )

    bob = rows["bob@example.edu"]
    assert bob.invitation is not None
    assert bob.invitation.status == "sent"
    assert bob.last_reminder_at is None

    # zoe has no invitation, and no row either — the third state is
    # covered by the reviewer set itself.
    assert "zoe@example.edu" not in rows


@reviewer_impl
def test_an_excluded_row_is_not_work(
    db: Session, rollups: Fixture, rollup: Callable
) -> None:
    """Bob has two assignments; a6 is `include=False`, so he carries one
    unit, unanswered — `not started`, with its one required field
    counted as missing."""
    bob = _by_email(rollup(db, rollups.session))["bob@example.edu"]
    assert bob.assignment_count == 1
    assert bob.completed_count == 0
    assert bob.required_total == 1
    assert bob.missing_required_count == 1
    assert bob.pill_state == "not started"


# --- the reviewee side -----------------------------------------------


@reviewee_impl
def test_reviewee_rows_are_in_identifier_order(
    db: Session, rollups: Fixture, rollup: Callable
) -> None:
    """Ordered by `email_or_identifier`, and asserted as a list for the
    same reason as the reviewer side above."""
    rows = rollup(db, rollups.session)
    assert [r.reviewee.email_or_identifier for r in rows] == [
        "carol@example.edu",
        "dan@example.edu",
        "erin@example.edu",
    ]


@reviewee_impl
def test_carol_is_adequately_covered(
    db: Session, rollups: Fixture, rollup: Callable
) -> None:
    """a1, a3 and a9 — three assignments, two of them answered with the
    required field satisfied and submitted. a9 is the draft, which this
    rollup does **not** count. Two of three is at or above the adequate
    fraction, so `adequate` rather than `complete` or `at risk`.

    a6 is `include=False` and does not count against her. Note that no
    group dedupe happens on this side: carol's two grouped assignments
    are two rows here, where alice's collapse.
    """
    carol = _by_identifier(rollup(db, rollups.session))["carol@example.edu"]
    assert carol.reviewer_count == 3
    assert carol.completed_count == 2
    assert (
        carol.completed_count / carol.reviewer_count
        >= monitoring.AT_RISK_THRESHOLDS["adequate_fraction"]
    )
    assert carol.pill_state == "adequate"
    # +6h: a3's later row. Not +0h (a1, her first assignment with a
    # stamp) and not +2h (a3's other row).
    assert _utc_naive(carol.last_response_at) == _utc_naive(
        T0 + timedelta(hours=6)
    )


@reviewee_impl
def test_a_response_that_completes_nothing_still_reads_as_no_responses(
    db: Session, rollups: Fixture, rollup: Callable
) -> None:
    """Dan's a2 *has* a response row — it is simply empty where the
    required field is — and a4 has none. Zero complete out of two, which
    `_classify_coverage` calls `no responses` rather than `at risk`.

    Pinned deliberately: the bucket name is about completions, not about
    whether anything was typed, and a rewrite that keyed the bucket off
    the existence of response rows would change it.
    """
    dan = _by_identifier(rollup(db, rollups.session))["dan@example.edu"]
    assert dan.reviewer_count == 3
    assert dan.completed_count == 0
    assert dan.pill_state == "no responses"
    # ...and the timestamp still comes from that row.
    assert _utc_naive(dan.last_response_at) == _utc_naive(
        T0 + timedelta(hours=1)
    )


@reviewee_impl
def test_erin_is_at_risk_below_the_adequate_fraction(
    db: Session, rollups: Fixture, rollup: Callable
) -> None:
    """One of erin's three assignments is complete. The threshold is read
    from the constant rather than written as `0.5`, so moving it moves
    this test with it."""
    erin = _by_identifier(rollup(db, rollups.session))["erin@example.edu"]
    assert erin.reviewer_count == 3
    assert erin.completed_count == 1
    assert (
        erin.completed_count / erin.reviewer_count
        < monitoring.AT_RISK_THRESHOLDS["adequate_fraction"]
    )
    assert erin.pill_state == "at risk"


# --- where the two sides disagree, on purpose ------------------------


def test_an_inactive_reviewer_is_excluded_one_side_only(
    db: Session, rollups: Fixture
) -> None:
    """`zoe` is inactive. The reviewer rollup drops her; the reviewee
    rollup still counts her assignment against erin — a8 is one of the
    three in `test_erin_is_at_risk_below_the_adequate_fraction`, and its
    answer is the one completion erin has.

    This asymmetry is not obviously right, but it is what ships, and an
    oracle's job is to pin what ships so a rewrite cannot change it by
    accident. If it is to change, that is its own item.
    """
    reviewers = _by_email(monitoring.per_reviewer_progress(db, rollups.session))
    assert "zoe@example.edu" not in reviewers

    erin = _by_identifier(
        monitoring.per_reviewee_coverage(db, rollups.session)
    )["erin@example.edu"]
    assert erin.reviewer_count == 3
    assert erin.completed_count == 1


def test_a_draft_is_complete_to_one_rollup_and_not_the_other(
    db: Session, rollups: Fixture
) -> None:
    """a9 carries `h1 = "wip"` with no `submitted_at`.

    The reviewer rollup counts it **complete**: it asks only whether
    every required field has a non-empty value, and uses the missing
    `submitted_at` to hold the pill off `submitted` instead. The
    reviewee rollup does **not**: `_assignment_complete` requires a
    `submitted_at` on every required field.

    So the same row is one completion on alice's line and not one on
    carol's. Like the inactive-reviewer split above, this is pinned
    because it is what ships — and because it is exactly the kind of
    difference a rewrite would iron out by accident while both sides
    kept passing their own tests.
    """
    alice = _by_email(monitoring.per_reviewer_progress(db, rollups.session))[
        "alice@example.edu"
    ]
    carol = _by_identifier(
        monitoring.per_reviewee_coverage(db, rollups.session)
    )["carol@example.edu"]

    # Alice's three completions include a9; drop it and she has two.
    assert alice.completed_count == 3
    # Carol's three assignments include a9, and she has two completions.
    assert carol.reviewer_count == 3
    assert carol.completed_count == 2


def test_summary_counts_ride_on_the_reviewer_rollup(
    db: Session, rollups: Fixture
) -> None:
    """`summary_counts` derives entirely from `per_reviewer_progress`, so
    a change to that rollup moves these too — including the invitation
    half, which is why the fixture seeds two.

    Two assigned reviewers; both invited (alice `opened`, bob `sent` —
    `invited` counts anything past `pending`); one opened; neither
    submitted, so both incomplete.
    """
    counts = monitoring.summary_counts(db, rollups.session)
    assert counts.assigned == 2
    assert counts.invited == 2
    assert counts.opened == 1
    assert counts.submitted == 0
    assert counts.incomplete == 2
