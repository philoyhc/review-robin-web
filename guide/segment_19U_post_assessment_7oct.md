# Segment 19U — post-assessment, 2026-10-07

**Opened:** 2026-10-07 · **Theme:** fixes and small patches, after the 2026-10-07 corpus sweep (`guide/sweep_2026-10-07_corpus.md`), that no other plan owns · **Related:** `guide/findings_2026-10-07_corpus.md`

**Items close independently**, each with its own `### Doc impact` and
`### Status`, as in 19S. So there is **no segment-level `## Doc impact`**,
and `python3 tools/close_check.py 19U.1` reads Item 1's. The segment stays
open after Item 1 for the author's further small patches (2026-10-07), and
closes only when the author says so.

## Item 1 — session-state guard in the service layer

**Theme:** every save that a session's lifecycle state gates decides that gate under the session lock, inside the service. **Related:** `spec/lifecycle.md`, `spec/architecture.md`.

### Opportunity

Findings **Bc4**: a save checks the session's lifecycle state on the row
loaded with the request, then writes. Nothing stops that state changing
in between. On Postgres, a scheduled activation committing in that gap
has three effects:

- a roster import replaces the roster and cascades assignments on a
  `ready` session;
- `invalidate_if_validated`, reading the stale `validated`, writes
  `draft` over the committed `ready`;
- a manual **Activate** that read `validated` activates a second time,
  writing a second `session.activated` row.

Bc3 (#2877) closed this for the three schedule saves only, by calling
`lock_session` from the route before the gate. Codex on #2877 flagged
the shape: the invariant lives in route choreography, so a service
caller that skips it reopens the race.

Measured below: 66 gated mutating route handlers, about 80 service entry
points, 11 lifecycle transitions.

### Decision

**Ruled 2026-10-07 (option a, with manual Activate):** the state gate
moves into the service layer. Every service function that mutates a
session's setup, roster, instruments, schedule or lifecycle starts with
one primitive. The primitive locks and re-reads the session row, then
refuses unless the session is in an allowed state. The lock is
`SELECT … FOR NO KEY UPDATE` with `populate_existing`, as in Bc3. The
gate, the reads after it and the write all happen under that one lock,
and no caller can leave it out.

- **Primitive.** A new module `app/services/session_guard.py`:
  - `lock_session` moves here, re-exported from `scheduled_events`.
  - New `require_state(db, session, allowed, *, code, message)`. It
    locks, re-reads, and raises `SessionStateConflict` (a subclass of
    `LifecycleError`) when `allowed(session)` is false.
  - The named predicates are the ones the routes use today:
    `is_editable`, `not is_archived`, `not is_ready`.
- **One 409.** An app-level handler renders `SessionStateConflict` the
  way `_http_exception_handler` renders today's `HTTPException(409)`. So
  no route grows a `try`, and the page an operator sees does not change.
- **Lifecycle transitions** (`mark_validated`, `activate_session`,
  `expire_session`, `revert_session_to_draft`, `archive_session`,
  `unarchive_session`, the release pair, `invalidate_session`,
  `observe_deadline`) lock and re-read before their precondition. A
  manual Activate that loses the race to the scheduled one then fails
  `not_validated`. The scheduled observer already re-checks (Bc3).

**Rejected — (b), lock from each route (Bc3's shape extended).** It
touches fewer files. But the invariant would stay in 66 handlers' call
order, and the next handler written without it reopens the race; that is
Codex's point on #2877.

**Rejected — compare-and-set on the status write.** It fixes
`invalidate_if_validated` alone. The roster rows, assignments and
instrument edits written before the status write would still land on a
`ready` session.

### Semantics

- **Re-entrant within a request.** A request that calls several guarded
  services takes the lock once and re-reads each time. `lock_session`
  flushes first, so an unflushed edit survives; Bc3 tests this. The lock
  holds until the request's commit or its teardown.
- **Early route checks stay** as cheap refusals, before an upload is
  parsed. The service check is the authoritative one: it can refuse a
  request the route's check let through, never the reverse.
- **Reads before the lock.** Only the state gate is in scope. A route
  that reads other rows before the save (an import's cross-table
  identity check, say) still reads them unlocked; *Out of scope*.
- **Async handlers.** 15 gated handlers are `async`. Each awaits its
  body (form, file or JSON), then runs the guarded remainder through
  `run_in_threadpool`. Bc3 did the same for the Settings import: a lock
  wait on the event loop can stall the worker whose other requests hold
  the lock.
- **SQLite** ignores `FOR NO KEY UPDATE`, so tests prove the order of
  reads and writes, not that Postgres blocks. They use Bc3's
  commit-at-the-lock stand-in (`tests/integration/test_scheduled_events_locking.py`).
- **Lands in** `spec/lifecycle.md` "Concurrency safety", which says
  every state-gated save is decided under the lock, and
  `spec/architecture.md` "Three-layer split", which records that state
  gates are a service rule.

### Judgment calls — decided

- `SessionStateConflict` subclasses `LifecycleError`, so the routes that
  already catch `LifecycleError` keep catching it, and `code` maps
  through `_lifecycle_error_response` unchanged.
- Observers keep their own predicate (`not is_archived`), and Delete
  data / Delete session keep theirs (`not is_ready`). The primitive takes
  the predicate; it does not widen any gate.
- `sessions.update_session` guards itself. Session Home and the lobby
  keep their early `lock_session` call, so their validation reads also
  happen under the lock. Both calls are service calls.

### Blast radius (measured)

Taken 2026-10-07 at `9eda6273`.

| What | Count | Command |
|---|---|---|
| Gated mutating route handlers | 66 (51 sync, 15 async) | AST walk of `app/web/routes_operator/*.py` for `_require_editable` / `_require_instrument_editable` / `_require_not_archived` / `_require_not_ready` / `is_editable` calls, `_render*` excluded |
| `_require_editable` call sites | 42 | `grep -rn "_require_editable" app/ \| wc -l` |
| `is_editable(` call sites | 22 | `grep -rn "is_editable(" app/ --include=*.py \| grep -v "def is_editable" \| wc -l` |
| `invalidate_if_validated(` callers | 44 | `grep -rn "invalidate_if_validated(" app/ \| grep -v "def " \| wc -l` |
| Lifecycle transition functions | 11 | `grep -n "^def " app/services/session_lifecycle.py` |
| `lock_session(` call sites | 11 | `grep -rn "lock_session(" app/ --include=*.py \| grep -v "def lock_session" \| wc -l` |
| Test files naming a 409 | 50 | `grep -rln "revert to draft to edit\|409" tests/ \| wc -l` |

### PR ladder

1. **PR 1 — this plan, and the Bc4 ruling in the register.** Prose only.
2. **PR 2 — the primitive and the lifecycle transitions.** Lands
   `session_guard.py`, the `SessionStateConflict` handler, and locks in
   the 11 transitions, so manual Activate cannot double-fire. Must not
   touch roster, instrument or schedule services.
3. **PR 3 — rosters.** Reviewers, reviewees and observers services;
   `csv_imports` save and delete-all; `field_labels`. The async import
   handlers (`_handle_import`, the Quick Setup runners,
   `observers_import_submit`) hop to the threadpool. Must not touch
   relationships or assignments.
4. **PR 4 — relationships and assignments.** Their services, plus
   `relationships_import_submit`'s hop.
5. **PR 5 — instruments.** `instruments_service` mutators, plus the
   eight async JSON handlers' hop.
6. **PR 6 — session saves.** `update_session`,
   `set_session_display_timezone`, `session_tags.set_tags`,
   `delete_session`, `responses.delete_all_for_session`.
   `session_config_io` and the two routes switch to `session_guard`.
   This is the last build rung: run `diff-reviewer` on the cumulative
   diff from PR 2's base.
7. **PR 7 — item close.** Spec sweep, register strike, `### Status` compacted. The file stays in `guide/`, because the segment stays open.

Code rungs 2–6 are one item ladder, so they take one cumulative read at
rung 6. A rung that reopens code after that read takes its own read.

### Definition of done

- Every mutating function in `app/services/` that a route gates on
  session state calls `session_guard.require_state` before its first read
  of setup data. Listed in `## Status` at close, with the grep that
  proves it.
- `tests/integration/test_session_state_guard.py` holds a
  commit-at-the-lock test for each of: manual Activate, a roster import,
  a relationship save, an instrument edit and a Session Home save. Each
  fails without its rung's change.
- No gated `async` handler calls a guarded service on the event loop.
- `spec/lifecycle.md` "Concurrency safety" and `spec/architecture.md`
  "Three-layer split" state the rule.
- Findings Bc4 struck in `guide/findings_2026-10-07_corpus.md`.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19U.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- Item 1 marked closed in its heading; the file stays in `guide/` while 19U is open

### Open questions

- Should a Postgres `lock_timeout` bound a stuck lock wait? It is
  deployment configuration rather than code. **The author decides**,
  with the Azure deployment (`guide/post_azure_todo_checklist.md`).

### Out of scope

- **Reads before the lock that are not the state gate.** For example,
  an import's identity check against rows another request is writing.
  Not reported, and the lock does not order rows other than the session.
- **The reviewer surface.** A submission racing deadline expiry
  (`session_accepts_responses`) is a different actor and a different
  gate. If it matters, it gets its own finding.
- **Removing the early route checks.** They stay, so the order in which
  routes refuse does not change in this segment.

### Doc impact

- `spec/lifecycle.md` — "Concurrency safety": every state-gated save and every transition is decided under the session lock, in the service (PR 7).
- `spec/architecture.md` — "Three-layer split": a lifecycle-state gate is a service rule, and `session_guard` is its primitive (PR 7).
- `guide/findings_2026-10-07_corpus.md` — Bc4 ruled (PR 1), struck at close (PR 7).
- `guide/todo_master.md` — the segment's in-progress line names Item 1 while it is open (PR 1), and drops it at the item close (PR 7).
