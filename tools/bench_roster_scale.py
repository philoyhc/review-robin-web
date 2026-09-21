#!/usr/bin/env python3
"""Roster-scale benchmark — what the operator surfaces cost on a large session.

Seeds a synthetic session of a given size into a **local** Postgres, then times
each operator page against it, separating SQL time from Python time and counting
queries. The method behind `guide/app_responsiveness.md` (2026-09-20).

Not in CI, and not a repo dependency: it needs a Postgres cluster you are willing
to write to, which the test suite (in-memory SQLite) deliberately is not. The
numbers that matter here are per-request **query counts** and the SQL / Python
split; wall-clock is machine-specific and only comparable within one run.

    # a throwaway cluster, then the schema
    /usr/lib/postgresql/16/bin/initdb -D /tmp/pgdata -U rrw_app --auth=trust
    /usr/lib/postgresql/16/bin/pg_ctl -D /tmp/pgdata -o '-p 5433' -l /tmp/pg.log start
    createdb -h 127.0.0.1 -p 5433 -U rrw_app rrw
    export DATABASE_URL=postgresql+psycopg://rrw_app@127.0.0.1:5433/rrw
    alembic upgrade head

    python3 tools/bench_roster_scale.py seed --reviewers 1000 --reviewees 1000
    python3 tools/bench_roster_scale.py bench --session 1
    python3 tools/bench_roster_scale.py profile --session 1 --path /assignments

    # the same session after the operator has actually generated through a rule
    python3 tools/bench_roster_scale.py pin-rule --session 1
    python3 tools/bench_roster_scale.py post --session 1 --path /workflow/prepare

Every subcommand refuses any `DATABASE_URL` that is not loopback. This tool
writes tens of thousands of rows, drives the real Prepare and Activate
routes, and signs in as whoever `--operator-email` names — none of which
may ever meet a deployed database.
"""
from __future__ import annotations

import argparse
import cProfile
import io
import os
import pstats
import statistics
import sys
import time
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import Engine, create_engine, event, insert, select  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

LOOPBACK = ("@127.0.0.1", "@localhost", "@/", "host=/")

PAGES = (
    ("Lobby", "/operator/sessions", False),
    ("Lobby: archived", "/operator/sessions/archived", False),
    ("Session Home", "", True),
    ("Assignments", "/assignments", True),
    ("Invitations", "/invitations", True),
    ("Responses", "/responses", True),
    ("Validate", "/validate", True),
    ("Setup: reviewers", "/reviewers", True),
    ("Setup: reviewers p5", "/reviewers?offset=800", True),
    ("Setup: reviewers ?q=", "/reviewers?q=Reviewer+00500", True),
    ("Setup: reviewers ?q=Team", "/reviewers?q=Team+3", True),
    ("Setup: reviewees", "/reviewees", True),
    ("Setup: relationships", "/relationships", True),
    ("Setup: observers", "/observers", True),
)


def _database_url() -> str:
    """The database to work against — loopback only, for every subcommand.

    The guard is here rather than on the write paths because reading is not
    the safe half: `_client` overrides `get_current_user`, so a `bench` or
    `profile` run against a reachable database would read another account's
    sessions with a fabricated identity, and `post` drives the real Prepare
    and Activate routes — replacing assignments, deleting responses, sending
    invitations. One gate on the way in covers all of it (Codex P1 on #2513).
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is unset — point it at a local Postgres.")
    if not any(marker in url for marker in LOOPBACK):
        sys.exit(f"refusing to run against a non-loopback database: {url!r}")
    return url


# ---------------------------------------------------------------------------
# seed
# ---------------------------------------------------------------------------


def seed(args: argparse.Namespace) -> None:
    from app.db.models import (
        Assignment,
        Instrument,
        InstrumentResponseField,
        Invitation,
        Observer,
        Relationship,
        Response,
        Reviewee,
        Reviewer,
        ReviewSession,
        SessionOperator,
        User,
    )

    url = _database_url()
    engine = create_engine(url, future=True)
    started = time.perf_counter()

    with Session(engine) as db:
        user = db.execute(
            select(User).where(User.email == args.operator_email)
        ).scalar_one_or_none()
        if user is None:
            user = User(
                email=args.operator_email,
                display_name="Bench Operator",
                external_principal_id="bench-oid",
                is_operator=True,
            )
            db.add(user)
            db.flush()

        review_session = ReviewSession(
            name=f"Bench {args.code}",
            code=args.code,
            status="draft",
            created_by_user_id=user.id,
            assignment_mode="rule_based",
            relationships_enabled=True,
            observers_enabled=True,
        )
        db.add(review_session)
        db.flush()
        db.add(
            SessionOperator(
                session_id=review_session.id, user_id=user.id, role="owner"
            )
        )

        instruments = [
            Instrument(
                session_id=review_session.id,
                name=f"Instrument {n + 1}",
                order=n,
                session_seq=n + 1,
            )
            for n in range(args.instruments)
        ]
        db.add_all(instruments)
        db.flush()
        fields_by_instrument: dict[int, list[int]] = {}
        for instrument in instruments:
            for n in range(args.fields):
                field = InstrumentResponseField(
                    instrument_id=instrument.id,
                    field_key=f"q{n + 1}",
                    label=f"Question {n + 1}",
                    order=n,
                )
                db.add(field)
                db.flush()
                fields_by_instrument.setdefault(instrument.id, []).append(field.id)
        db.commit()
        session_id = review_session.id

        db.execute(
            insert(Reviewer),
            [
                {
                    "session_id": session_id,
                    "name": f"Reviewer {n:05d}",
                    "email": f"reviewer{n:05d}@example.edu",
                    "status": "active",
                    "tag_1": f"Team {n % 10}",
                    "tag_2": f"Cohort {n % 4}",
                }
                for n in range(args.reviewers)
            ],
        )
        db.execute(
            insert(Reviewee),
            [
                {
                    "session_id": session_id,
                    "name": f"Reviewee {n:05d}",
                    "email_or_identifier": f"reviewee{n:05d}@example.edu",
                    "status": "active",
                    "tag_1": f"Team {n % 10}",
                }
                for n in range(args.reviewees)
            ],
        )
        db.commit()

        reviewer_ids = list(
            db.execute(
                select(Reviewer.id)
                .where(Reviewer.session_id == session_id)
                .order_by(Reviewer.id)
            ).scalars()
        )
        reviewee_ids = list(
            db.execute(
                select(Reviewee.id)
                .where(Reviewee.session_id == session_id)
                .order_by(Reviewee.id)
            ).scalars()
        )

        pairs = [
            {
                "session_id": session_id,
                "reviewer_id": reviewer_id,
                "reviewee_id": reviewee_ids[(index + offset + 1) % len(reviewee_ids)],
                "instrument_id": instrument.id,
                "include": True,
                "is_self_review": False,
                "created_by_mode": "rule_based",
            }
            for instrument in instruments
            for index, reviewer_id in enumerate(reviewer_ids)
            for offset in range(args.per_reviewer)
        ]
        db.execute(insert(Assignment), pairs)
        db.execute(
            insert(Relationship),
            [
                {
                    "session_id": session_id,
                    "reviewer_id": reviewer_id,
                    "reviewee_id": reviewee_ids[
                        (index + offset + 1) % len(reviewee_ids)
                    ],
                    "tag_1": f"Team {index % 10}",
                    "status": "active",
                }
                for index, reviewer_id in enumerate(reviewer_ids)
                for offset in range(args.per_reviewer)
            ],
        )
        db.execute(
            insert(Observer),
            [
                {
                    "session_id": session_id,
                    "email": f"observer{n:05d}@example.edu",
                    "display_name": f"Observer {n:05d}",
                    "status": "active",
                    "tag_1": f"Team {n % 10}",
                }
                for n in range(args.observers)
            ],
        )
        db.execute(
            insert(Invitation),
            [
                {
                    "session_id": session_id,
                    "reviewer_id": reviewer_id,
                    "token_hash": f"bench-{session_id}-{reviewer_id}",
                    "status": "sent",
                }
                for reviewer_id in reviewer_ids
            ],
        )
        db.commit()

        answered = db.execute(
            select(Assignment.id, Assignment.instrument_id)
            .where(Assignment.session_id == session_id)
            .order_by(Assignment.id)
        ).all()
        cutoff = int(len(answered) * args.answered)
        now = datetime.now(timezone.utc)
        rows = [
            {
                "assignment_id": assignment_id,
                "response_field_id": field_id,
                "value": "4",
                "saved_at": now,
                "submitted_at": now,
                "version": 1,
            }
            for assignment_id, instrument_id in answered[:cutoff]
            for field_id in fields_by_instrument[instrument_id]
        ]
        for start in range(0, len(rows), 20_000):
            db.execute(insert(Response), rows[start : start + 20_000])
        db.commit()

    print(
        f"session_id={session_id} code={args.code} "
        f"reviewers={len(reviewer_ids)} reviewees={len(reviewee_ids)} "
        f"instruments={args.instruments} assignments={len(pairs)} "
        f"relationships={len(reviewer_ids) * args.per_reviewer} "
        f"observers={args.observers} "
        f"responses={len(rows)} in {time.perf_counter() - started:.1f}s"
    )


# ---------------------------------------------------------------------------
# bench / profile
# ---------------------------------------------------------------------------


def seed_lobby(args: argparse.Namespace) -> None:
    """Add N sessions owned by the bench operator — the lobby's own axis.

    The lobby renders every non-archived session the operator can see, with
    no pager and no cap (`guide/roster_search_filter.md` explains why the
    client-side Filter can work there and not on a roster). Its cost
    therefore scales with **session count**, not roster size, which is a
    different question from everything else this tool measures — so the
    sessions it writes are deliberately near-empty.
    """
    from app.db.models import ReviewSession, SessionOperator, SessionTag, User

    url = _database_url()
    engine = create_engine(url, future=True)
    started = time.perf_counter()
    with Session(engine) as db:
        user = db.execute(
            select(User).where(User.email == args.operator_email)
        ).scalar_one()
        existing = db.execute(
            select(SessionOperator.id).where(SessionOperator.user_id == user.id)
        ).all()
        statuses = ("draft", "validated", "ready", "expired", "archived")
        for n in range(args.sessions):
            review_session = ReviewSession(
                name=f"Lobby filler {n:04d}",
                code=f"{args.prefix}{n:04d}",
                status=statuses[n % len(statuses)],
                created_by_user_id=user.id,
                assignment_mode="rule_based",
            )
            db.add(review_session)
            db.flush()
            db.add(
                SessionOperator(
                    session_id=review_session.id, user_id=user.id, role="owner"
                )
            )
            for tag in (f"Term {n % 6}", f"Faculty {n % 4}"):
                db.add(SessionTag(session_id=review_session.id, tag=tag))
        db.commit()
        total = db.execute(
            select(SessionOperator.id).where(SessionOperator.user_id == user.id)
        ).all()
    print(
        f"added {args.sessions} sessions (was {len(existing)}, now {len(total)}) "
        f"in {time.perf_counter() - started:.1f}s"
    )


class _SqlMeter:
    """Per-request query count and cumulative SQL time."""

    def __init__(self, engine: Engine) -> None:
        self.count = 0
        self.seconds = 0.0
        event.listen(engine, "before_cursor_execute", self._before)
        event.listen(engine, "after_cursor_execute", self._after)

    def reset(self) -> None:
        self.count = 0
        self.seconds = 0.0

    def _before(self, conn, cursor, statement, params, context, many) -> None:  # noqa: ANN001
        conn.info.setdefault("_bench_t0", []).append(time.perf_counter())

    def _after(self, conn, cursor, statement, params, context, many) -> None:  # noqa: ANN001
        self.count += 1
        self.seconds += time.perf_counter() - conn.info["_bench_t0"].pop()


def _client(engine: Engine, email: str):  # noqa: ANN202 — TestClient, imported late
    from fastapi.testclient import TestClient

    from app.auth.identity import AuthenticatedUser, get_current_user
    from app.config import settings
    from app.db.session import get_db
    from app.main import app

    settings.operator_emails = [email]
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db() -> Iterator[Session]:
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        principal_id="bench-oid", email=email, name="Bench Operator", provider="aad"
    )
    return TestClient(app)


def bench(args: argparse.Namespace) -> None:
    engine = create_engine(_database_url(), future=True)
    meter = _SqlMeter(engine)
    client = _client(engine, args.operator_email)
    root = f"/operator/sessions/{args.session}"

    print(f"{'page':26s} {'total':>9s} {'sql':>9s} {'python':>9s} {'queries':>8s} {'html':>9s}")
    for label, suffix, scoped in PAGES:
        if args.only and args.only.lower() not in label.lower():
            continue
        url = f"{root}{suffix}" if scoped else suffix
        first = client.get(url, follow_redirects=False)
        if first.status_code != 200:
            print(f"{label:26s} HTTP {first.status_code} {url}")
            continue
        totals: list[float] = []
        sql_times: list[float] = []
        queries = 0
        for _ in range(args.runs):
            meter.reset()
            started = time.perf_counter()
            client.get(url, follow_redirects=False)
            totals.append((time.perf_counter() - started) * 1000)
            sql_times.append(meter.seconds * 1000)
            queries = meter.count
        total = statistics.median(totals)
        sql = statistics.median(sql_times)
        print(
            f"{label:26s} {total:8.0f}ms {sql:8.0f}ms {total - sql:8.0f}ms "
            f"{queries:8d} {len(first.content) / 1024:8.0f}K"
        )


def pin_rule(args: argparse.Namespace) -> None:
    """Pin one MATCH rule on every instrument — the shape an operator authors.

    ``reviewer.tag1 same_as reviewee.tag1`` keeps a tenth of the matrix on the
    seeded rosters, which is the point: it is the *narrow* case, and the engine
    still walks every pair to find it.
    """
    from app.db.models import Instrument, SessionRuleSet

    url = _database_url()
    engine = create_engine(url, future=True)
    with Session(engine) as db:
        rule_set = SessionRuleSet(
            session_id=args.session,
            name="Same team",
            description="",
            combinator="ALL_OF",
            exclude_self_reviews=False,
            seed=1,
            rules_json=[
                {
                    "id": "same_team",
                    "kind": "MATCH",
                    "enabled": True,
                    "predicate": {
                        "field": "reviewer.tag1",
                        "operator": "same_as",
                        "operand": "reviewee.tag1",
                    },
                }
            ],
        )
        db.add(rule_set)
        db.flush()
        instruments = list(
            db.execute(
                select(Instrument).where(Instrument.session_id == args.session)
            ).scalars()
        )
        for instrument in instruments:
            instrument.rule_set_id = rule_set.id
        rule_set_id, pinned = rule_set.id, len(instruments)
        db.commit()
    print(f"pinned rule_set {rule_set_id} on {pinned} instruments")


def post(args: argparse.Namespace) -> None:
    """Time one mutating operator POST — Prepare, Activate, Generate."""
    engine = create_engine(_database_url(), future=True)
    meter = _SqlMeter(engine)
    client = _client(engine, args.operator_email)
    url = f"/operator/sessions/{args.session}{args.path}"
    meter.reset()
    started = time.perf_counter()
    response = client.post(
        url,
        data={"acknowledge_response_loss": "true"},
        follow_redirects=False,
    )
    elapsed = time.perf_counter() - started
    print(
        f"POST {args.path:28s} {elapsed:8.1f}s  sql {meter.seconds:6.1f}s  "
        f"queries {meter.count:5d}  HTTP {response.status_code} "
        f"-> {response.headers.get('location', '')}"
    )


def profile(args: argparse.Namespace) -> None:
    engine = create_engine(_database_url(), future=True)
    client = _client(engine, args.operator_email)
    url = f"/operator/sessions/{args.session}{args.path}"
    client.get(url, follow_redirects=False)  # warm
    profiler = cProfile.Profile()
    profiler.enable()
    client.get(url, follow_redirects=False)
    profiler.disable()
    stream = io.StringIO()
    pstats.Stats(profiler, stream=stream).sort_stats("tottime").print_stats(args.rows)
    print("\n".join(stream.getvalue().splitlines()[4:]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--operator-email", default="bench@example.edu")

    seed_parser = sub.add_parser("seed", parents=[common], help="write a large session")
    seed_parser.add_argument("--reviewers", type=int, default=1000)
    seed_parser.add_argument("--reviewees", type=int, default=1000)
    seed_parser.add_argument("--per-reviewer", type=int, default=5)
    seed_parser.add_argument("--instruments", type=int, default=2)
    seed_parser.add_argument("--fields", type=int, default=3)
    seed_parser.add_argument("--observers", type=int, default=200)
    seed_parser.add_argument("--answered", type=float, default=0.6)
    seed_parser.add_argument("--code", default="BENCH1")
    seed_parser.set_defaults(func=seed)

    lobby_parser = sub.add_parser(
        "seed-lobby", parents=[common], help="add N near-empty sessions"
    )
    lobby_parser.add_argument("--sessions", type=int, default=50)
    lobby_parser.add_argument("--prefix", default="LOB")
    lobby_parser.set_defaults(func=seed_lobby)

    bench_parser = sub.add_parser("bench", parents=[common], help="time every page")
    bench_parser.add_argument("--session", type=int, required=True)
    bench_parser.add_argument("--runs", type=int, default=3)
    bench_parser.add_argument(
        "--only", default="", help="substring filter over the page labels"
    )
    bench_parser.set_defaults(func=bench)

    pin_parser = sub.add_parser("pin-rule", parents=[common], help="pin a MATCH rule")
    pin_parser.add_argument("--session", type=int, required=True)
    pin_parser.set_defaults(func=pin_rule)

    post_parser = sub.add_parser("post", parents=[common], help="time a mutating POST")
    post_parser.add_argument("--session", type=int, required=True)
    post_parser.add_argument("--path", required=True, help='e.g. "/workflow/prepare"')
    post_parser.set_defaults(func=post)

    profile_parser = sub.add_parser("profile", parents=[common], help="cProfile one page")
    profile_parser.add_argument("--session", type=int, required=True)
    profile_parser.add_argument("--path", default="", help='e.g. "/assignments"')
    profile_parser.add_argument("--rows", type=int, default=20)
    profile_parser.set_defaults(func=profile)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
