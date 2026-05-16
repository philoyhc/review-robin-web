# Segment 17A — Housekeeping (file splits + test-suite runtime)

**Status:** Shipped 2026-05-16 (PRs #1052 → #1056). Created
2026-05-16; PR sequence added 2026-05-16. All five PRs landed
the same day — Track B (#1052 / #1053) then Track A (#1054 /
#1055 / #1056). This plan is now a historical record; current
behaviour is described in `docs/status.md`.

The "17A" segment number was freed when the AG Grid
replacement was taken off the roadmap (2026-05-16) — it is now
an aspirational item in `guide/future_possibilities.md`, not a
segment. This fills the freed slot with the code-hygiene items
surfaced by the
[2026-05-16 codebase assessment](codebase_assessment_16may.md) —
§6 (recommended file splits) and §5 weakness 8 (test-suite
runtime). It is **not** related to the AG Grid work that
briefly held this number; the only thing carried over is the
number itself.

## Goal

Pure structural / infrastructure cleanup — **no behaviour
change, no new features, no new routes or models**. Two
independent tracks; each PR small and reviewable, each
landable on its own.

## Why a separate segment

- The items are real but small, share no theme with any
  feature segment, and would only muddy a feature PR if bundled
  in (`CLAUDE.md`: "Don't bundle independent changes").
  Collecting them under one housekeeping number keeps the
  feature segments clean and gives the cleanup a place to live.
- **No dependencies, no dependents.** Can interleave at any
  cadence. Best landed *before* Segments 14B (email infra) and
  21 (reviewee surface) add their route-heavy bulk — both the
  file splits and the faster suite pay off more the earlier
  they land.

## PR sequence

Both tracks are pursued. The two tracks are independent — the
only ordering that matters is *within* each track — but the
recommended interleave runs **Track B first**: the suite
speed-ups are small, low-risk, and land before the splits, so
every Track A PR (each verified by re-running the full suite)
is cheaper to iterate on.

| PR | Track | Title | Depends on |
|---|---|---|---|
| 1 | B | Parallelise the suite with `pytest-xdist` (`-n auto`) | — |
| 2 | B | Swap migration replay for `Base.metadata.create_all()` in the SQLite engine fixture | PR 1 (compounds; not strictly required) |
| 3 | A | Split `_setup_rosters.py` into per-page slices | — |
| 4 | A | Promote `session_config_io.py` to a package | — |
| 5 | A | *(optional)* Carve Response Type Definition routes out of `_instruments.py` | — |

PR 1 → 2 is the one hard ordering (Track B order). PRs 3-5 can
land in any order and can interleave with PRs 1-2; the table
order is the recommended cadence, not a dependency chain. PR 5
is discretionary — land it only if `_instruments.py` is still
growing when the rest of the segment is done.

Each PR ships with a passing full `pytest` run on the session
container. A split (PRs 3-5) that needs test edits beyond
import-path fixes is a signal the split was not purely
structural — stop and reconsider rather than editing behaviour
tests.

## Track A — file splits

From assessment §6. The codebase precedent is the May 9 splits
of `instruments.py` and `views.py` into packages, plus the
`CLAUDE.md` conventions (operator routes split by feature area;
services split by concern into packages). Each split is pure
structure — move code, keep the public import surface stable.

- **PR 3 — `app/web/routes_operator/_setup_rosters.py`
  (1,759 LOC).** Carries three independent Setup pages in one
  slice. Split into `_setup_reviewers.py` / `_setup_reviewees.py`
  / `_setup_relationships.py`; lift the shared plumbing
  (`_redirect_keeping_selection`, the sort-value helpers, the
  `_picker_label` datalist helper) into `_shared.py`. Highest
  priority — the three route groups already barely
  cross-reference. Land first of Track A.
- **PR 4 — `app/services/session_config_io.py` (1,733 LOC).**
  Promote to a `session_config_io/` package mirroring
  `extracts/` and `instruments/`: `_serialize.py` (the
  six-section exporter), `_apply.py` (the two-phase importer),
  `_rows.py` (the `Row` NamedTuple + the `_str` / `_bool` /
  `_int` / `_decimal` / `_json` typed-cell helpers), and an
  `__init__.py` re-exporting the public surface so callers keep
  writing `from app.services import session_config_io`.
- **PR 5 (optional) — `app/web/routes_operator/_instruments.py`
  (1,398 LOC).** Carve the Response Type Definition routes
  (the block already marked "Slice 4b") into a
  `_response_types.py` slice. Do only if `_instruments.py`
  keeps growing — it is reasonably cohesive today.

Out of Track A's scope: packaging `app/web/routes_reviewer.py`
(1,362 LOC). It is on the assessment watch list, but the right
time to package it is as the first step of Segment 17B, which
will grow the reviewer surface — so it lands there, not here.

## Track B — test-suite runtime

From assessment §5 weakness 8. The suite is **1,766 tests /
~90 s**, single-process, on a session-scoped in-memory SQLite
engine that replays all 40 migrations once. Not painful yet —
this track is "do it before the suite crosses ~2-3 min", which
14B / 21 will push it toward.

- **PR 1 — `pytest-xdist` (`pytest -n auto`).** Process-level
  parallelism — the big lever (~90 s → an estimated ~25-35 s on
  a typical multi-core box). Fits the codebase: `:memory:`
  SQLite is already per-process and the per-test
  transaction-rollback isolation means no cross-test shared
  state; the `committed_engine` harness uses a per-test
  `tmp_path` DB, also xdist-safe. Each worker re-runs
  `alembic upgrade head` once at startup — offset many times
  over by the parallelism. Add `pytest-xdist` to the `[dev]`
  extra **only** (not `requirements.txt`, which is runtime-only
  for the Azure deploy; both CI test jobs install `.[dev]`),
  wire `-n auto` into the CI pytest job, and document the
  change in `README.md` per the testing-expectations note in
  `CLAUDE.md`. A short spike at the top of the PR should
  confirm worker isolation behaves before committing.
  *Not in this PR:* hoisting `TestClient` construction. It is
  already per-test only because each test installs its own
  `get_db` / `get_current_user` dependency overrides — `app`
  itself is imported once at module scope — so there is no
  clean hoist without reworking the override mechanism. Not
  worth it.
- **PR 2 — swap `alembic upgrade head` →
  `Base.metadata.create_all()`** in both SQLite engine
  fixtures: the session-scoped `engine` (`tests/conftest.py`)
  and the per-test `committed_engine`
  (`tests/integration/conftest.py`). The 40-migration replay is
  pure schema-build cost; `create_all` is near-instant.
  `committed_engine` replays the full chain *per test* (it
  backs only `test_route_persistence.py`, so the cost is
  bounded — but per-test replay is a heavier cumulative hit
  than the session engine's one-time replay, so it is worth
  swapping too). Fidelity tradeoff: SQLite tests stop
  exercising the migration chain — acceptable because the
  `ci-postgres` job already round-trips migrations. Compounds
  with PR 1 (every xdist worker saves the replay). Land after
  PR 1.
- **Not pursued:** a fast/slow marker split — it only changes
  *perceived* time, not total, and is not worth the
  marker-maintenance burden on top of the two PRs above.

## Done when

- No `app/` production file is over ~1,200 LOC without a
  deliberate reason (Track A PRs 3-4 landed; PR 5 at
  discretion).
- The full `pytest` suite runs in well under a minute on the
  session container, and CI runs it parallelised.
- No behaviour change: the test suite passes unchanged across
  every PR (a split that needs test edits beyond import-path
  fixes is a sign the split was not purely structural).

## Out of scope

- AG Grid / reviewer-surface table replacement — off the
  roadmap; an aspirational item in `guide/future_possibilities.md`.
- Any behaviour change, new feature, new route, or new model.
- `app/web/routes_reviewer.py` packaging — deferred to 17B
  (see Track A).
- `guide/archive/` compression — a recurring assessment
  grumble, but a docs-tree concern, not code hygiene; leave it
  to Segment 19 (spec / docs hygiene) if it is ever picked up.

## Related context

- `guide/codebase_assessment_16may.md` — §6 (file splits) and
  §5 weakness 8 (test-suite runtime) are the source of every
  item here.
- `guide/archive/major_refactor.md` — the May 9
  `instruments.py` / `views.py` package splits; the precedent
  Track A follows.
- `CLAUDE.md` — operator-route + service-package conventions;
  the testing-expectations note Track B updates `README.md`
  against.
