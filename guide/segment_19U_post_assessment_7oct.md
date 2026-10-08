# Segment 19U — post-assessment, 2026-10-07

**Opened:** 2026-10-07 · **Theme:** fixes and small patches, after the 2026-10-07 corpus sweep (`guide/sweep_2026-10-07_corpus.md`), that no other plan owns · **Related:** `guide/findings_2026-10-07_corpus.md`

**Items close independently**, each with its own `### Doc impact` and
`### Status`, as in 19S. So there is **no segment-level `## Doc impact`**,
and `python3 tools/close_check.py 19U.1` reads Item 1's. The segment stays
open after Item 1 for the author's further small patches (2026-10-07), and
closes only when the author says so.

## Item 1 — session-state guard in the service layer (closed 2026-10-08)

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

### Status — closed 2026-10-08

**Laddered as planned**: rungs 2–6 are #2881–#2885 (cumulative-read
base `d8445500`), this close is PR 7. What moved:

- **Pulled forward to rung 3** (Codex on #2882): `invalidate_if_validated`
  only flushes, so the `validated → draft` flip lands in the caller's
  commit (all 44 call sites walked); the label editor and the roster and
  relationship imports run as one unit; the relationship-import hops.
- **Added at build:** `unit_of_work.atomic` (rung 3) and `after_commit`
  (rung 6, Codex on #2885); Prepare commits `workflow_run_started` before
  its steps (rung 4); the Band 2 save, the identity route and Session
  Home's config save each became one unit (rungs 5–6); purge-and-archive
  decides `can_archive` under the lock before any purge (rung 6);
  `set_group_boundary` and `bulk_save_fields`, uncalled, gate anyway.
- **Behavior changes:** an edit refused after the flip leaves the session
  `validated`; a double-submitted Revert from `validated` answers 409;
  a Generate that raises rolls back; the lobby's bulk Unarchive,
  Purge-and-archive and Delete skip a row moved first; a Quick Setup slot
  maps a refusal to its `lifecycle` reason.
- **By design:** tags take no state gate; Quick Setup's slots commit
  separately, as specified; `rehydrate_session` chains guarded saves on
  the draft it has just created.

**Proof at `e35ccb5c`.** `grep -rlE "require_(editable|not_archived|not_ready)\(|lock_session\(" app/services | wc -l`
→ 27 service files gate. `test_session_state_guard.py` holds 46 tests,
each mutation-checked by its rung's read. An AST walk of every `async`
handler in `app/web` finds no guarded call outside a `run_in_threadpool`
closure. Not pinned: the hops, and Postgres actually blocking (SQLite
ignores the lock).

**Reads: 20 over the build, plus one of this close's code nits.** One
cumulative read (rungs 2–6) and five follow-ups on rung 2, five on
rung 3, two each on rungs 4 and 5, five on rung 6. Every medium was a
commit that released the lock early or a lost audit row: Prepare's
started row (rung 4), Band 2's per-field commit (rung 5), the config
save (rung 6, the pre-push sweep). The rest were unpinned gates, stale
docstrings and spec owed at close. **Codex: six findings, all fixed** —
five on #2882 (three commits releasing the lock, one pair of writes
outside one unit, one lock wait on the event loop) and one on #2885 (log
lines before the commit). From rung 4 on, a sweep for those three shapes
ran before every push.

**Close.** `close_check.py 19U.1` passes; its coverage notes (touched
routes whose specs are not in Doc impact: `spec/instruments.md`,
`spec/quick_setup_card_spec.md`, `spec/permissions.md`,
`spec/setup_pages.md` and four more) are adjudicated as no contract
change, since those routes gained only the race-time 409 and the hop, and
Quick Setup's slots now give the "lifecycle refusal" sentence the spec
already promises. `spec-writer`'s two flags are Bc6 and A9 below.

**Left open, as register rows** in `guide/findings_2026-10-07_corpus.md`:
Bc5 (invitation sends gate on the loaded row), Bc6 (Activate's warnings
detour drops its started row), Bc7 (an uncaught Generate exception
leaves a started row with no failed row), Bc8 (the Instruments render's
ungated writes), A9 (`preview-sample` "persists nothing"). Also noted:
the lobby bulk Delete can delete a row archived since the page loaded
(archived rows are deletable anyway); two weak tests (the bulk-delete skip
uses one row; the slot-reason tests do not assert that nothing landed).

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
  configuration; **the author decides** with the Azure deployment. Still
  open at close; carried as item 11 of `guide/post_azure_todo_checklist.md`.

### Out of scope

- Reads before the lock other than the state gate (an import's identity
  check, say): the lock orders only the session row.
- The reviewer surface: a submission racing deadline expiry is another
  actor and another gate.

### Doc impact

- `spec/lifecycle.md` — "Concurrency safety": every state-gated save and every transition is decided under the session lock, in the service; §2's qualification, §2.3, §7 "Atomic commits" and the `session.invalidated` audit row: the automatic `validated → draft` flip lands in the caller's commit, and only the operator's Revert commits it alone; §2.6: `/revert` decides invalidate or revert under the lock, through `operator_revert`; §3.1: the route's `_require_editable` is an early refusal and the service's `require_editable` decides; the lobby bulk Delete skips a row the guard refuses (PR 7).
- `spec/workflow_card.md` — Prepare failures: a Generate that raises now rolls itself back (the session keeps its status), and the run's `workflow_run_started` is committed before the steps; Revert dispatches under the lock (PR 7).
- `spec/session_home.md` — Revert dispatches by the status read under the lock, not the loaded row (PR 7).
- `spec/sessions_overview.md` — bulk Delete skips a row the guard refuses; Purge and archive decides `can_archive` under the lock before any purge, and its purges land in the archive's one commit (PR 7).
- `spec/architecture.md` — "Three-layer split": a lifecycle-state gate is a service rule, and `session_guard` is its primitive; the `unit_of_work` paragraph names `atomic` and `after_commit` beside `single_commit` (PR 7).
- `guide/findings_2026-10-07_corpus.md` — Bc4 ruled (PR 1), struck at close (PR 7).
- `guide/todo_master.md` — the segment's in-progress line names Item 1 while it is open (PR 1), and drops it at the item close (PR 7).

## Item 2 — Session Home session edit UI adjustment (closed 2026-10-08)

### Opportunity

Session Home's **Session details** card ends in two half-width sub-cards
— **User interface settings** (the Relationships / Observers toggles)
and **Tags** — with the Save / Cancel / Lock cluster under Tags. Each
holds one or two controls of the card's own form, so the card reads as
three boxes for one save. The author's mock-up (2026-10-08) folds them
into the card.

### Decision

**Ruled 2026-10-08 by the author.** Tags becomes a field of the card,
under **Description** in the left column; the two toggles follow under
Tags, under one label, **Optional setup tabs**, with no subtitle (the
"Per-session toggles for the optional Setup tabs." line goes). The Save
/ Cancel / Lock cluster moves to the foot of the right column. No
sub-card is left inside the card. Nothing about what saves, or when,
changes: same `config-save` form, same edit window, same
`tags_present` marker, same lock-on-data on the toggles.

**Rejected:** keeping the toggles in a sub-card under Tags (the
mock-up's interim state) — the author asked for the contents to leave
it.

### Judgment calls — decided

- The Tags helper ("Comma-separated; also editable from the sessions
  list.") becomes a field's `.form-help` below the box, edit-only, per
  `spec/ui_elements.md` "Helper text": a card subtitle no longer applies
  once there is no card. The mock-up shows it above the box; flip on
  the author's word.
- The Create page keeps its own **User interface settings** and **Tags**
  cards: the ruling names Session Home only.

### Blast radius (measured)

Taken 2026-10-08 at `0e330810`.

| What | Count | Command |
|---|---|---|
| Templates | 1 | `grep -rln "config-ui-settings-card" app/web/templates` |
| Test files asserting the old structure | 3 | `grep -rln "config-ui-settings-card\|config-tags-card" tests/` |
| Live specs naming the Session Home sub-cards | 8 | `grep -rln "User interface settings\|config-tags-card\|Tags card" spec/` |

### Status — closed 2026-10-08

**Shipped as planned, in one PR.** Session Home's details card holds no
sub-card: Tags (`#config-tags-field`) sits under Description, the
toggles (`#config-optional-tabs`, labelled "Optional setup tabs", no
subtitle) under Tags, and the Save / Cancel / Lock cluster at the foot
of the right column. The save path is untouched. The Tags helper moved
below the box as `.form-help` (judgment call above). Rendered in
Chromium in both modes before the PR; the author's browser check is
still owed. The close's `spec-writer` pass edited seven of the eight
named specs (`spec/session_home.md` through `spec/setup_pages.md`) and
flagged `spec/session_owners.md` and `spec/operator_ui_concept.md`'s
"approximates Session Home's placements" for the Create page, both
reworded and the former added to Doc impact. Left as is, not this
item's: `spec/settings_inventory.md`'s `display_timezone` row still
names the retired Edit Session Details form.

### PR ladder

1. **One PR**: the plan, the template, its tests, the specs, the close.
   A rearrangement of existing controls with no new behavior, so no
   scaffold rung.

### Definition of done

- Session Home's details card holds no `.card` and no `.bottom-grid`;
  Tags sits under Description and the toggles under Tags, labelled
  "Optional setup tabs"; the Save cluster foots the right column
  (`tests/integration/test_session_home_tags_card.py`).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19U.2` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- Item 2 marked closed in its heading; the file stays in `guide/` while 19U is open

### Open questions

- None.

### Out of scope

- The Create page's cards (`spec/session_owners.md` describes their
  layout), and the Guide's screencaps of it.

### Doc impact

- `spec/session_home.md` — the details card: Tags and the optional-tab toggles as fields of the card, no sub-cards, the Save cluster at the foot of the right column.
- `spec/ui_elements.md` — "Helper text": the single-field-card case names only the Create page's Tags card; Session Home's Tags helper is a field's `.form-help`.
- `spec/rrw_functional_spec.md` — the Session details card's sub-card bullets become fields.
- `spec/operator_ui_concept.md` — where the toggles live on Session Home.
- `spec/settings_inventory.md` — `relationships_enabled` / `observers_enabled`: where they are authored.
- `spec/participant_model.md` — the `relationships_enabled` row's authoring surface.
- `spec/visual_style_rrw.md` — the optional Setup tabs' toggle location.
- `spec/setup_pages.md` — the optional tabs' toggle location.
- `spec/session_owners.md` — Create's layout no longer "approximates Session Home's placements"; Session Home holds Tags and the toggles as fields.
