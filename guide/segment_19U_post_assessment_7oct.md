# Segment 19U — post-assessment, 2026-10-07

**Opened:** 2026-10-07 · **Theme:** fixes and small patches, after the 2026-10-07 corpus sweep (`guide/sweep_2026-10-07_corpus.md`), that no other plan owns · **Related:** `guide/findings_2026-10-07_corpus.md`

**Items close independently**, each with its own `### Doc impact` and
`### Status`, as in 19S. So there is **no segment-level `## Doc impact`**,
and `python3 tools/close_check.py 19U.1` reads Item 1's. The segment stays
open after Item 1 for the author's further small patches (2026-10-07), and
closes only when the author says so.

## Item 1 — session-state guard in the service layer

### Opportunity

Findings **Bc4**: a save checks the session's lifecycle state on the row
loaded with the request, then writes. A scheduled activation committing
in between can leave a roster replaced on a `ready` session, let
`invalidate_if_validated` write `draft` over the committed `ready`, or
let a manual **Activate** that read `validated` activate a second time.
Bc3 (#2877) closed this for the schedule saves only, from the routes;
Codex on #2877 flagged that a service caller skipping that call reopens
the race.

### Decision

**Ruled 2026-10-07 (a), with manual Activate.** Every service that writes
a session's setup, roster, instruments, schedule or lifecycle starts with
one primitive in `app/services/session_guard.py`, which locks and re-reads
the session row (`FOR NO KEY UPDATE`, `populate_existing`, as in Bc3)
and refuses unless the session is in an allowed state:

- `require_state(db, session, allowed, *, code, message)` raises
  `SessionStateConflict` (a `LifecycleError`). `lock_session` moves
  here, re-exported from `scheduled_events`. The predicates are the
  routes' own: `is_editable`, `not is_archived`, `not is_ready`.
- An app-level handler renders `SessionStateConflict` as today's 409
  page, so no route grows a `try`.
- The 11 lifecycle transitions lock and re-read before their
  precondition, so a manual Activate that loses the race fails
  `not_validated`.

**Rejected:** (b), locking from each route, which leaves the invariant
in 66 handlers' call order; and compare-and-set on the status write,
which fixes only `invalidate_if_validated` while the rows written before
it still land on a `ready` session.

### Semantics

- **Re-entrant.** Several guarded calls in one request re-lock and
  re-read; `lock_session` flushes first, so an unflushed edit survives.
- **Early route checks stay** as cheap refusals; the service check is
  authoritative, and can only refuse more.
- **Async handlers** await their body, then run the guarded part
  through `run_in_threadpool`, so a lock wait never blocks the loop.
- **SQLite** ignores the lock: tests prove read order, with Bc3's
  commit-at-the-lock stand-in.
- **Lands in** `spec/lifecycle.md` "Concurrency safety" and
  `spec/architecture.md` "Three-layer split".

### Judgment calls — decided

- `SessionStateConflict` subclasses `LifecycleError`, so existing
  catches keep working, and `_lifecycle_error_response` maps it to 409.
- Observers keep `not is_archived` and the deletes keep `not is_ready`:
  the primitive takes the predicate and widens no gate.

### Blast radius (measured)

Taken 2026-10-07 at `9eda6273`.

| What | Count | Command |
|---|---|---|
| Gated mutating route handlers | 66 (51 sync, 15 async) | AST walk of `app/web/routes_operator/*.py` for the gate helpers, `_render*` excluded |
| `_require_editable` call sites | 42 | `grep -rn "_require_editable" app/ \| wc -l` |
| `invalidate_if_validated(` callers | 44 | `grep -rn "invalidate_if_validated(" app/ \| grep -v "def " \| wc -l` |
| Lifecycle transition functions | 11 | `grep -n "^def " app/services/session_lifecycle.py` |

### PR ladder

1. **PR 1 — plan and Bc4 ruling.** Prose only.
2. **PR 2 — primitive, 409 handler, lifecycle transitions.** Not roster,
   instrument or schedule services.
3. **PR 3 — rosters**: reviewers, reviewees, observers, `csv_imports`
   saves and delete-alls, `field_labels`, with their async handlers' hop.
4. **PR 4 — relationships and assignments**, with the relationship
   imports' hop.
5. **PR 5 — instruments and visibility policies**, with the eight async
   JSON handlers' hop.
6. **PR 6 — session saves**: `update_session`, the display zone, tags,
   the two deletes; `session_config_io` moves to `session_guard`. Last
   build rung: `diff-reviewer` on the cumulative diff from PR 2's base.
7. **PR 7 — item close**: spec sweep, register strike, `### Status`
   compacted. The file stays in `guide/`.

### Definition of done

- Every service a route gates on session state calls the guard before
  its first read; listed in `### Status` with the grep that proves it.
- `tests/integration/test_session_state_guard.py` has a commit-at-the-lock
  test per rung, each failing without its change.
- No gated `async` handler calls a guarded service on the event loop.
- Findings Bc4 struck in `guide/findings_2026-10-07_corpus.md`.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19U.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- Item 1 marked closed in its heading; the file stays in `guide/` while 19U is open

### Open questions

- A Postgres `lock_timeout` to bound a stuck wait: deployment
  configuration; **the author decides** with the Azure deployment.

### Out of scope

- Reads before the lock other than the state gate (an import's identity
  check, say): the lock orders only the session row.
- The reviewer surface: a submission racing deadline expiry is another
  actor and another gate.

### Doc impact

- `spec/lifecycle.md` — "Concurrency safety": every state-gated save and every transition is decided under the session lock, in the service; §2's qualification, §2.3, §7 "Atomic commits" and the `session.invalidated` audit row: the automatic `validated → draft` flip lands in the caller's commit, and only the operator's Revert commits it alone (PR 7).
- `spec/workflow_card.md` — Prepare failures: a Generate that raises now rolls itself back (the session keeps its status), and the run's `workflow_run_started` is committed before the steps (PR 7).
- `spec/architecture.md` — "Three-layer split": a lifecycle-state gate is a service rule, and `session_guard` is its primitive (PR 7).
- `guide/findings_2026-10-07_corpus.md` — Bc4 ruled (PR 1), struck at close (PR 7).
- `guide/todo_master.md` — the segment's in-progress line names Item 1 while it is open (PR 1), and drops it at the item close (PR 7).
