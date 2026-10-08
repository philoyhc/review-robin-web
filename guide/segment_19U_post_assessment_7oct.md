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
base `d8445500`), the close PR 7. What moved:

- **Pulled forward to rung 3** (Codex on #2882): `invalidate_if_validated`
  only flushes, so the `validated → draft` flip lands in the caller's
  commit; the label editor and the roster and relationship imports run
  as one unit.
- **Added at build:** `unit_of_work.atomic` and `after_commit`; Prepare
  commits `workflow_run_started` before its steps; the Band 2 save, the
  identity route and the config save each became one unit;
  purge-and-archive decides `can_archive` under the lock.
- **Behavior changes:** a refused edit leaves the session `validated`; a
  double Revert answers 409; a raising Generate rolls back; the lobby's
  bulk actions skip a row moved first.

**Proof at `e35ccb5c`.** `grep -rlE "require_(editable|not_archived|not_ready)\(|lock_session\(" app/services | wc -l`
→ 27 service files gate; `test_session_state_guard.py` holds 46 tests,
each mutation-checked by its rung's read. Not pinned: Postgres actually
blocking (SQLite ignores the lock).

**Reads: 20, plus Codex's six findings, all fixed.** Every medium was a
commit that released the lock early or a lost audit row. **Close:**
`close_check.py 19U.1` passes; its uncited-route notes are adjudicated as
no contract change (those routes gained only the race-time 409). Left
open as register rows Bc5–Bc8 and A9, since fixed in #2888–#2890.

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
| Live specs naming the Session Home sub-cards | 10 (9 edited; `spec/sessions_overview.md` already said "Tags field") | `grep -rln "User interface settings\|config-tags-card\|Tags card" spec/` |

### Status — closed 2026-10-08

**Shipped as planned, in one PR** (#2892); the save path is untouched.
The Tags helper sits below the box (judgment call above). Rendered in
Chromium in both modes; the author's browser check is owed. The close's
`spec-writer` pass edited seven specs and I reworded two more
(`spec/session_owners.md` added to Doc impact). The cold read's two
findings (a test passing on a CSS comment, a stale line in
`spec/participant_model.md`) are fixed. Not this item's: the
`display_timezone` row in `spec/settings_inventory.md` still names the
retired Edit Session Details form, and some code comments still name
the old "User interface settings card".

### PR ladder

1. **One PR**: the plan, the template, its tests, the specs, the close.
   A rearrangement of existing controls with no new behavior, so no
   scaffold rung.

### Definition of done

- Session Home's details card holds no `.card` and no `.bottom-grid`;
  Tags sits under Description and the toggles under Tags, labeled
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

## Item 3 — Session Home optional-tab chips (closed 2026-10-08)

### Opportunity

After Item 2 the author asked (2026-10-08) for three follow-ups on the
details card: Tags sits too close to the Description box; the field's
label undersells it ("tabs", where each also gates a page); and the two
toggles are bare checkboxes inside text labels, where clicking the text
did nothing in edit mode because each label wrapped two checkboxes.

### Decision

**Ruled 2026-10-08 by the author.** Tags gets a wider gap below
Description. The label becomes **Optional setup tabs and pages**. The
toggles become two selector chips, **Relationships** and **Observers**,
in the rosters' "Show columns" style, **inert while the card is
locked**. Each unlocked chip is a `<label>` around its checkbox, so the
form, the lock-on-data rule and the save are unchanged.

**Rejected:** chips as `role="button"` spans with a script writing a
hidden input, as the column chips work — the form would depend on
script, and a Cancel's `form.reset()` would leave the fill stale.

### Judgment calls — decided

- A locked chip is `.tag-chip.is-locked`: no edge or pointer, as
  `is-disabled`, but not struck through; on takes the card's
  display-value colors, off is faded, so the reserved shade stays on
  controls (`tests/unit/test_reserved_shade.py`).
- The selected fill reads `:has(> input:checked)`, so no script syncs it.
- A lock-on-data chip in edit mode is `is-locked` too, with a title
  saying why.

### Blast radius (measured)

Taken 2026-10-08 at `64056c04`.

| What | Count | Command |
|---|---|---|
| Templates | 2 (`session_detail.html`, `base.html`) | `grep -rln "config-optional-tabs" app/web/templates` + the chip CSS |
| Test files pinning the field | 4 | `grep -rln "config-optional-tabs\|Optional setup tabs" tests/ --include=*.py` |
| Live specs naming the field | 7 | `grep -rln "Optional setup tabs" spec/` |

### Status — closed 2026-10-08

**Shipped as planned, in one PR**, with `spec/ui_elements.md` added to
Doc impact for the new chip states. Driven in Chromium: a locked click
does nothing, an unlocked click ticks the box and enables Save, Cancel
clears the fill, Save persists, Space toggles from the keyboard. The
author's browser check is owed. **Two reads.** The first, of `68c2949d`: locked
chips stated on/off by color alone (now `role="checkbox"` with
`aria-checked`), the gap on the wrong spec bullet (also `spec-writer`'s
flag), two stale "one inert chip" / "only on controls" lines, two
unpinned CSS rules (now pinned and mutation-checked), and the tooltip
missing from the spec; all fixed. The second, of the fix `2226afef`,
was clean, each new pin mutation-checked.

### PR ladder

1. **One PR**: plan, template, CSS, tests, specs, close.

### Definition of done

- The chips render as above in both modes
  (`tests/integration/test_session_feature_toggles.py`,
  `tests/integration/test_chip_edge.py`).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19U.3` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- Item 3 marked closed in its heading; the file stays in `guide/` while 19U is open

### Open questions

- None.

### Out of scope

- The Create page's **User interface settings** checkboxes: the ruling
  names Session Home.

### Doc impact

- `spec/session_home.md` — the field: label, chips, the locked state, lock-on-data, the gap under Description.
- `spec/ui_elements.md` — "Label or control": a chip around a checkbox and `.tag-chip.is-locked`.
- `spec/rrw_functional_spec.md` — §8.8's field name and its chips.
- `spec/operator_ui_concept.md` — the field's name.
- `spec/settings_inventory.md` — the field's name in the two toggle rows.
- `spec/participant_model.md` — the field's name in the two toggle rows.
- `spec/visual_style_rrw.md` — the field's name.
- `spec/setup_pages.md` — the field's name.

## Item 4 — Session Home Save keeps the card and the seat (closed 2026-10-08)

### Opportunity

The author (2026-10-08): Save on the details card also locked it, though
the card has its own Lock; and Save's reload jumped the page, because
the redirect's `#session-config` scrolled the card's top edge into view
from the Save button at its foot.

### Decision

**Ruled 2026-10-08 by the author ("way 2 plus the save delink").** Save
returns to `?editing=1` with no fragment; only Lock locks. The reload
stays, made quiet: the card's form stores `scrollY` on submit and an
inline script restores it (the Instruments page's pattern), and Session
Home opts into `@view-transition` so the reload cross-fades.

**Rejected:** saving without a reload (`fetch` and swap the page body):
no repaint at all, but the card's dirty tracking, the tag typeahead and
the Danger Zone confirms bind at load and would need rewiring, and a
422 would need an inline home; Way 2 first, that if the reload still
shows.

### Judgment calls — decided

- `@view-transition` takes no selector, so no CSS declares it: Session
  Home's `rrwSaveFade` adds the rule from script on Save's way out and
  back, and only for `prefers-reduced-motion: no-preference`.
- The restore defers to a *shown* `.banner-scroll-target` only, as
  `base.html`'s banner scroll does: Quick Setup's error banners render
  `hidden` on every load.
- An in-place Lock or Unlock rewrites `?editing` with
  `history.replaceState`, so a reload after Lock stays locked.
- The `/edit` 308 keeps its `#session-config`: it is a stale-bookmark
  entry, not a save.

### Blast radius (measured)

Taken 2026-10-08 at `26adcc5d`.

| What | Count | Command |
|---|---|---|
| Routes | 1 (`session_config_submit`) | `grep -n 'id}#session-config"' app/web/routes_operator/_session_home.py` |
| Tests pinning Save's redirect | 2 | `grep -rln 'id}#session-config"' tests/ --include=*.py` |
| Specs naming Save's return | 3 | `grep -rln -i 'returns to Home in display mode\|back to Home in \*\*display\*\* mode\|shared .\/config. POST' spec/` |

### Status — closed 2026-10-08

**Shipped as planned, in one PR.** Driven in Chromium: Save comes back
unlocked at the same `scrollY`, restored before the first frame paints;
Lock locks in place and a reload stays locked. Found at build: the
restore first deferred to *any* `.banner-scroll-target`, and a hidden
Quick Setup banner cancelled it on every load; and a static
`@view-transition` on Session Home made every Home → Home reload fade,
which held the Owners card's browser tests' clicks (`<html> intercepts
pointer events`) — hence the script-added rule, Save only. The author's
browser check is owed.

### PR ladder

1. **One PR**: plan, route, template, tests (one in `tests/browser/`),
   specs, close.

### Definition of done

- Save redirects to `?editing=1` with no fragment; the scroll is
  restored and Lock drops the param
  (`tests/browser/test_session_home_save.py`,
  `tests/integration/test_session_home_save_seat.py`).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19U.4` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- Item 4 marked closed in its heading; the file stays in `guide/` while 19U is open

### Open questions

- None.

### Out of scope

- The Instruments page's own scroll restore, which defers to any
  `.banner-scroll-target`, shown or not: no hidden one renders there today.

### Doc impact

- `spec/session_home.md` — "Edit affordance behavior": Save returns unlocked, no fragment; the scroll restore, the view transition, Lock's `replaceState`.
- `spec/rrw_functional_spec.md` — §8.8: Save returns unlocked at the operator's scroll; Lock locks.
- `spec/operator_button_audit.md` — §5b row 156: Save's return.
