# Segment 17A — Housekeeping (file splits + test-suite runtime)

**Status:** Stub. Created 2026-05-16.

The "17A" segment number was vacated when the AG Grid
replacement renumbered 17A → 22 (2026-05-16). This fills the
freed slot with the code-hygiene items surfaced by the
[2026-05-16 codebase assessment](codebase_assessment_16may.md) —
§6 (recommended file splits) and §5 weakness 8 (test-suite
runtime). It is **not** related to the old 17A scope; the only
thing carried over is the number.

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

## Track A — file splits

From assessment §6. The codebase precedent is the May 9 splits
of `instruments.py` and `views.py` into packages, plus the
`CLAUDE.md` conventions (operator routes split by feature area;
services split by concern into packages). Each split is pure
structure — move code, keep the public import surface stable.

- **PR 1 — `app/web/routes_operator/_setup_rosters.py`
  (1,759 LOC).** Carries three independent Setup pages in one
  slice. Split into `_setup_reviewers.py` / `_setup_reviewees.py`
  / `_setup_relationships.py`; lift the shared plumbing
  (`_redirect_keeping_selection`, the sort-value helpers, the
  `_picker_label` datalist helper) into `_shared.py`. Highest
  priority — the three route groups already barely
  cross-reference.
- **PR 2 — `app/services/session_config_io.py` (1,733 LOC).**
  Promote to a `session_config_io/` package mirroring
  `extracts/` and `instruments/`: `_serialize.py` (the
  six-section exporter), `_apply.py` (the two-phase importer),
  `_rows.py` (the `Row` NamedTuple + the `_str` / `_bool` /
  `_int` / `_decimal` / `_json` typed-cell helpers), and an
  `__init__.py` re-exporting the public surface so callers keep
  writing `from app.services import session_config_io`.
- **PR 3 (optional) — `app/web/routes_operator/_instruments.py`
  (1,398 LOC).** Carve the Response Type Definition routes
  (the block already marked "Slice 4b") into a
  `_response_types.py` slice. Do only if `_instruments.py`
  keeps growing — it is reasonably cohesive today.

Out of Track A's scope: packaging `app/web/routes_reviewer.py`
(1,362 LOC). It is on the assessment watch list, but the right
time to package it is as the first step of whichever of
Segment 17B or 22 next touches the reviewer surface — so it
lands there, not here.

## Track B — test-suite runtime

From assessment §5 weakness 8. The suite is **1,766 tests /
~90 s**, single-process, on a session-scoped in-memory SQLite
engine that replays all 40 migrations once. Not painful yet —
this track is "do it before the suite crosses ~2-3 min", which
14B / 21 will push it toward.

- **`pytest-xdist` (`pytest -n auto`).** Process-level
  parallelism — the big lever (~90 s → an estimated ~25-35 s on
  a typical multi-core box). Fits the codebase: `:memory:`
  SQLite is already per-process and the per-test
  transaction-rollback isolation means no cross-test shared
  state. Each worker re-runs `alembic upgrade head` once at
  startup — offset many times over by the parallelism. A short
  spike should confirm worker isolation behaves before
  committing.
- **Swap `alembic upgrade head` → `Base.metadata.create_all()`**
  in the SQLite `engine` fixture (`tests/conftest.py`). The
  40-migration replay is pure session-startup cost;
  `create_all` is near-instant. Fidelity tradeoff: SQLite tests
  stop exercising the migration chain — acceptable because the
  `ci-postgres` job already round-trips migrations. Compounds
  with xdist (every worker saves the replay).
- **(Optional) hoist app / `TestClient` construction** to
  module or session scope if `tests/integration/conftest.py`
  rebuilds it per-test. Modest win; check first.
- **Not pursued alone:** a fast/slow marker split — it only
  changes *perceived* time, not total, and is not worth the
  marker-maintenance burden unless paired with the above.

Recommended Track B order: xdist first, then the `create_all`
swap (they compound). Wire `-n auto` into the CI pytest job and
document the change in `README.md` per the testing-expectations
note in `CLAUDE.md`.

## Done when

- No `app/` production file is over ~1,200 LOC without a
  deliberate reason (Track A PRs 1-2 landed; PR 3 at
  discretion).
- The full `pytest` suite runs in well under a minute on the
  session container, and CI runs it parallelised.
- No behaviour change: the test suite passes unchanged across
  every PR (a split that needs test edits beyond import-path
  fixes is a sign the split was not purely structural).

## Out of scope

- AG Grid / reviewer-surface table replacement — that is
  **Segment 22** (the segment this number was vacated from).
- Any behaviour change, new feature, new route, or new model.
- `app/web/routes_reviewer.py` packaging — deferred to 17B / 22
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
