# Segment 15C — Operator RTD / RuleSet libraries

**Status:** Plan stub (2026-05-09); codebase-aligned 2026-05-12
ahead of implementation kick-off.
**Sizing:** ~5-7 PRs (service + UX wiring; no schema).
**Depends on:** **Segment 13D** (PR 0 `operator_rule_sets`
rename, PR 2 `session_rule_sets`, PR 3
`operator_response_type_definitions` + provenance column on
`response_type_definitions`). All three landed; verified
2026-05-12.
**Sequenced before:** **Segment 15B** — see
"What 15B inherits from 15C" below. 15B is plan-locked and
deferred to start immediately after 15C ships.

---

## What 15B inherits from 15C

15B's per-instrument assignment work depends on two specific
15C deliverables. Calling them out explicitly so any slice
reorganisation here doesn't break 15B's downstream contract.

| 15B needs | Delivered by |
|---|---|
| `session_rule_sets` non-empty in every newly-created session (so the Instrument-card picker and the Assignments-page Generate button have a pool to operate on) | **15C Slice 1** — `materialise_seed_rule_sets` at session-create time. Workspace seeds become per-session rows automatically. |
| Rule Builder picker reads session-scoped rows (so 15B's "Edit rule" deep link from the Instrument card lands the operator on the session copy, not the library row) | **15C Slice 4** — picker source flip from `operator_rule_sets` to `session_rule_sets`; `_resolve_save_as_name` / `_name_taken_by_other` port from `(owner_user_id, name)` to `(session_id, name)`. |

The remaining 15C slices (2 / 3 / 5 / 6) are 15C-internal —
they polish the library / per-session symmetry but aren't on
15B's critical path. 15B can ship after Slice 1 + Slice 4
even if Slices 3 / 5 / 6 haven't landed yet (though landing
them together is cleaner).

---

## Goal

Symmetric two-tier library / per-session-copy model for both RTDs
and RuleSets:

- **Operator master library** — survives across sessions; the
  operator's reusable kit. Backed by the renamed
  `operator_rule_sets` table (RuleSets, post-13D PR 0) and the
  new `operator_response_type_definitions` table (RTDs, post-13D
  PR 3).
- **Per-session copy** — what a session actually uses; portable
  with the session. Backed by the new `session_rule_sets` table
  (RuleSets, post-13D PR 2) and the existing
  `response_type_definitions` table (RTDs, already per-session).

Operators can **promote** a session's RTD or RuleSet into their
library ("Save to library") and **demote** a library entry into
a session ("Add from library" — copies into the per-session
table). Both sides remain independently editable; no live
references between them.

---

## Workflow + invariants (locked 2026-05-09)

1. **Sessions are portable.** A session carries complete copies
   of every RTD and RuleSet it uses — export / import / handoff
   between operators all work without touching either operator's
   library.
2. **Library entries are reusable.** An operator authoring a new
   session doesn't have to redo their setup or "import from
   another session" to get their canonical RTDs / RuleSets.
3. **The two tiers are independent.**
   - Adding to the library doesn't touch existing sessions.
   - Deleting from the library doesn't touch any session that
     already has the copy.
   - Editing in one tier doesn't propagate to the other.
   - Deleting from a session doesn't touch the library or other
     sessions.
4. **Auto-copy on session create.** When a new session is
   created, every entry from the operator's library is copied
   into the session by default. Operators delete unwanted copies
   from the session afterwards. (Friendlier first-run; matches
   how RTDs already auto-seed today.)
5. **Workspace seeds bypass the operator library.** Workspace
   seeds (Likert5, GPA4, Full Matrix, etc.) materialise into
   every new session **directly**, never via an operator's
   library. They live as code constants (mirroring how
   `SEEDED_RESPONSE_TYPE_DEFINITIONS` already works for RTDs);
   this segment moves the existing `operator_rule_sets` rows
   with `scope=seed` over to the same pattern.
6. **Snapshot, not live reference.** Per-session copies are
   point-in-time snapshots. Editing the library after a copy
   exists has no effect on the copy; editing the copy doesn't
   write back. Provenance is tracked by the `library_origin_id`
   FK (per 13D PR 2 / PR 3) for "this came from your library"
   badges, but the FK is `SET NULL`-on-delete and never read for
   resolution.

---

## Slices

### Slice 1 — Workspace-seed materialisation (1 PR, ~150 LOC)

**Why first.** Bedrock for the rest. The workspace-shipped
seed RuleSets (Full Matrix, Intra-Group, Cross-Group,
Same-Group-Different-Role, Three-Reviewers-Per-Reviewee)
already live as code constants in
`app/services/rules/seeds.py` (exported as `SEEDS` — five
`RuleSetSchema` instances). They are **not** in
`operator_rule_sets` as DB rows today, despite that table
carrying `scope=seed` / `is_seed=True` columns. The plumbing
to read seeds from the library tier still routes through
`library.list_visible_rule_sets` filtering on `is_seed=True`,
which currently returns zero rows.

This slice formalises the existing reality: seeds are code
constants, they materialise into `session_rule_sets` (the
per-session copy table) at session-create time, and the
library-tier `is_seed` plumbing retires.

**Change.**

- Rename `SEEDS` → `SEEDED_RULE_SETS` for symmetry with
  `SEEDED_RESPONSE_TYPE_DEFINITIONS` (`app/services/instruments/_rtds.py:44`).
  Same shape (a list of seed definitions); no schema impact.
- New `materialise_seed_rule_sets(db, session)` helper —
  mirror of `ensure_default_response_type_definitions(db, session)`
  (`app/services/instruments/_instrument_crud.py:73`). For
  each entry in `SEEDED_RULE_SETS`, insert a row into
  `session_rule_sets` with `library_origin_id=None` (seeds
  never reference the library). Idempotent (skip-on-existing
  by `(session_id, name)`).
- Wire the helper into `create_session`
  (`app/services/sessions.py:42` calls
  `ensure_default_instrument` today). The new helper slots in
  alongside, at the same lifecycle hook.
- **No data migration needed.** There are zero
  `operator_rule_sets` rows with `is_seed=True` in any
  deployment today; the column has always been read-only
  plumbing. Slice 1 leaves the `is_seed` / `scope` columns on
  the model (no migration churn) but retires every read of
  them — `library.list_visible_rule_sets` flips to returning
  only `is_seed=False` rows (Personal entries only), with the
  workspace seeds served from the code constant via the new
  helper.
- `library.list_visible_rule_sets` simplifies to "Personal
  RuleSets owned by this user" — drops the seed branch.

**Audit.** New emitter
`session_rule_sets.materialised_from_seed` registered in
`EVENT_SCHEMAS` per the 11K canonical envelope.

### Slice 2 — Auto-copy operator library on session create (1 PR, ~200 LOC)

**Why.** Invariant #4 — operators don't have to import their
canonical setup every time.

**Change.**

- `app/services/sessions.py::create_session` (or its callsite in
  the session-create route) calls a new
  `materialise_operator_libraries(db, session, owner_user)`:
  - For each `operator_response_type_definitions` row owned by
    `owner_user`, insert a copy into `response_type_definitions`
    with `library_origin_id` set.
  - For each `operator_rule_sets` row owned by `owner_user`
    (Personal only post-Slice 1), copy + current-revision-snapshot
    into `session_rule_sets` with `library_origin_id` set.
- Workspace seeds (RTD + RuleSet) materialise via the existing /
  Slice 1 helpers, in the same lifecycle hook.
- Idempotent: re-running on a session that already has the
  copies is a no-op (matches `ensure_default_*` precedent).

**Audit.** New emitters
`session_rule_sets.materialised_from_library` /
`response_type_definitions.materialised_from_library` registered
in `EVENT_SCHEMAS` per the 11K canonical envelope.

### Slice 3 — RTD card: Save to / Add from library actions (1 PR, ~250 LOC)

**Why.** Invariant #3 — operator needs explicit promote / demote
actions on each tier.

**Change.**

- The Response Type Definitions card on the Instruments page gains
  per-row "Save to library" affordance for non-seeded session
  RTDs that aren't already linked to a library entry.
- A new "Add from library" affordance at the top of the card
  surfaces the operator's library RTDs that aren't already in
  the session; clicking copies into `response_type_definitions`.
- New routes under `/operator/sessions/{id}/instruments/rtd/`
  for the two actions; both POST + 303 redirect.
- "Saved to library" badge on session RTDs whose
  `library_origin_id IS NOT NULL`.

### Slice 4 — Rule Builder: Save to / Add from library actions (1 PR, ~250 LOC)

**Why.** Symmetric to Slice 3, on the RuleSet side.

**Change.**

- The Rule Builder page gains "Save to library" on session
  RuleSets and "Add from library" on the picker dropdown.
- New routes under `/operator/sessions/{id}/assignments/rule/`
  (or wherever the picker lives post-13A-1).
- "Saved to library" badge on session RuleSets whose
  `library_origin_id IS NOT NULL`.
- The picker's source flips from `operator_rule_sets` (the
  library, today's source) to `session_rule_sets` for the chosen
  session — operators see
  *this session's* RuleSets, with "Add from library" as the
  bridge to bring more in.
- **Per-session name-collision check.** When this slice flips the
  editor to write into `session_rule_sets`, port the existing
  `_resolve_save_as_name` / `_name_taken_by_other` helpers
  (`app/web/routes_operator/_rule_builder.py:532`) one-for-one
  to check `(session_id, name)` instead of `(owner_user_id,
  name)`. Same auto-suffix-on-Copy + reject-on-edited-name
  semantics. The `uq_session_rule_set_session_name` constraint
  from **Segment 13A-2** is the safety net behind that
  service-layer check — it guarantees uniqueness even if a
  future code path bypasses the helper.

### Slice 5 — Operator Settings: library management (1 PR, ~200 LOC)

**Why.** Operators need a place to view / edit / delete library
entries that's not tied to any one session.

**Change.**

- `/operator/settings` grows two new subsections:
  - **Response Type Definitions library** — list every
    `operator_response_type_definitions` row the operator owns;
    Add / Edit / Delete affordances.
  - **RuleSet library** — list every `operator_rule_sets` row
    the operator owns (Personal scope only post-Slice 1); Add / Edit
    / Delete affordances. The Edit affordance reuses the Rule
    Builder UI pointed at the library row (not a session copy).
- Delete-confirm dialog on each side surfaces a count of
  sessions that already hold copies (for transparency only —
  invariant #3 still applies, deletion does not cascade).

### Slice 6 — Lifecycle + audit polish (1 PR, ~100 LOC)

**Why.** Cleanup that benefits from landing after the new flows
exist:

- New `ValidationRule` keys for
  `instruments.no_session_rtd_for_field` (an
  `InstrumentResponseField` references an RTD whose session row
  has been deleted) — surfaces on the Validate page.
- Audit-event registration for the four new emitters
  (`operator_rtd.created` / `.updated` / `.deleted`,
  `session_rtd.saved_to_library` and equivalents on the RuleSet
  side).
- Inert audit at PR-close: `grep` for any stale
  `operator_rule_sets.scope == "seed"` references in the codebase
  (Slice 1 should have removed them all).

---

## Risks + open questions

- **Rule Builder picker UX.** Today's picker is an `<input list>`
  + `<datalist>` with all visible RuleSets; post-15C it shows
  only the session's `session_rule_sets` rows + an "Add from
  library" button to bring more in. Worth a small interaction
  spike before Slice 4 to confirm the flow doesn't add
  friction.
- **Library editing while in-flight.** If an operator edits a
  library entry while a session has a copy out, the copy is
  unaffected (snapshot semantics). Operators may expect the
  edit to propagate; the "Saved to library" badge + a hover
  tooltip should communicate this clearly.
- **Workspace-seed tier post-Slice 1.** Operators cannot
  "Save to library" a seed directly (seeds aren't library
  rows — they're code constants). They can still copy a
  session's seed RuleSet into their library by name — Slice
  4's "Save to library" runs unchanged on a session-RuleSet
  copy whose origin is a seed (the `library_origin_id`
  stays NULL because seeds bypass the library). Confirm this
  matches operator expectations before Slice 1 ships.
- **Existing data migration.** Pre-15C sessions don't have
  `session_rule_sets` rows; instruments don't yet point at
  anything (`instruments.rule_set_id` is brand-new from 13D
  PR 4 and 15B hasn't shipped). Slice 1's
  `materialise_seed_rule_sets` and Slice 2's
  `materialise_operator_libraries` both run on session create
  only, so existing sessions don't backfill. Operators
  wanting to apply a library entry to an existing pre-15C
  session use the Slice 4 "Add from library" affordance.
  For workspace seeds on an existing pre-15C session, the
  same affordance copies a seed from the code constant into
  the session — same Slice 4 mechanism, different source.

---

## Critical files

- New: `app/services/sessions.py::materialise_operator_libraries`
  helper (Slice 2), routes + templates for the four new
  affordances (Slices 3 / 4 / 5).
- Touched:
  - `app/services/rules/seeds.py` — rename `SEEDS` →
    `SEEDED_RULE_SETS`; add `materialise_seed_rule_sets`
    helper (Slice 1).
  - `app/services/rules/library.py` — drop the seed branch
    from `list_visible_rule_sets` (Slice 1); add library
    list helpers for the operator-Settings subsection
    (Slice 5).
  - `app/services/instruments/_rtds.py` — RTD library
    helpers (Slice 3).
  - `app/services/sessions.py` — hook
    `materialise_seed_rule_sets` next to
    `ensure_default_instrument` at session-create
    (`sessions.py:42`).
  - `app/web/routes_operator/_rule_builder.py` —
    `_resolve_save_as_name` / `_name_taken_by_other`
    port from `(owner_user_id, name)` on
    `operator_rule_sets` to `(session_id, name)` on
    `session_rule_sets` (Slice 4).
  - `app/web/routes_operator/_instruments.py` +
    `_settings.py` — new POST handlers (Slices 3 / 5).
  - `app/web/views/_rule_builder.py` —
    `_build_rule_builder_options` flips datasource
    (Slice 4).
  - `app/web/views/_instruments.py` + `_settings.py` —
    new view-adapter shapes (Slices 3 / 5).
  - Templates for the RTD card + Rule Builder + operator
    Settings + rule-builder picker partial
    (`_rule_builder_card.html`).
- No schema changes — every table / column comes from 13D.
  `operator_rule_sets.is_seed` and `.scope` columns stay on
  the model (Slice 1 retires the reads, not the columns);
  pruning them is a future cleanup migration outside this
  segment.

---

## Verification

- `pytest -q` green on SQLite + `ci-postgres` after each slice.
- `ruff check .` green.
- Audit-event gate (`tests/unit/test_audit_detail_schema.py`)
  catches any envelope drift in the four new emitters.
- New tests per slice:
  - Slice 1: `test_seed_rule_set_materialisation.py` —
    seeds copy into `session_rule_sets` on session create;
    `operator_rule_sets.scope == "seed"` row count after
    migration is zero.
  - Slice 2: `test_session_create_auto_copies_library.py` —
    operator with N library RTDs / M library RuleSets gets N
    new `response_type_definitions` rows + M new
    `session_rule_sets` rows on session create, all with
    `library_origin_id` set.
  - Slices 3 / 4: route-level tests for the four new actions
    (Save to library + Add from library on each side); badge
    rendering assertions.
  - Slice 5: operator-Settings page renders the two library
    subsections; delete-confirm shows the session-count
    summary.
- Manual smoke on the dev slot for Slices 3-5 (the
  promote / demote flows are user-facing).
