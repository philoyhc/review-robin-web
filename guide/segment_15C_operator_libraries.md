# Segment 15C — Operator RTD / RuleSet libraries

**Status:** Plan stub (2026-05-09).
**Sizing:** ~5-7 PRs (service + UX wiring; no schema).
**Depends on:** **Segment 13D** (PR 2 `session_rule_sets`, PR 3
`operator_response_type_definitions` + provenance column on
`response_type_definitions`).
**Sequenced before:** **Segment 15B** — once 15C lands,
`session_rule_sets` rows exist for 15B's `instruments.rule_set_id`
to point at, and per-instrument application becomes a small
follow-on rather than the segment that has to bootstrap the copy
infrastructure.

---

## Goal

Symmetric two-tier library / per-session-copy model for both RTDs
and RuleSets:

- **Operator master library** — survives across sessions; the
  operator's reusable kit. Backed by the existing `rule_sets`
  table (RuleSets) and the new
  `operator_response_type_definitions` table (RTDs, post-13D
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
   this segment moves the existing `rule_sets` rows with
   `scope=seed` over to the same pattern.
6. **Snapshot, not live reference.** Per-session copies are
   point-in-time snapshots. Editing the library after a copy
   exists has no effect on the copy; editing the copy doesn't
   write back. Provenance is tracked by the `library_origin_id`
   FK (per 13D PR 2 / PR 3) for "this came from your library"
   badges, but the FK is `SET NULL`-on-delete and never read for
   resolution.

---

## Slices

### Slice 1 — Workspace-seed migration (1 PR, ~150 LOC)

**Why first.** Bedrock for the rest. Today `rule_sets` mixes
operator-library Personal entries with workspace-shipped Seeds
(`scope ∈ {seed, personal}`). The library / copy split makes that
mix awkward — Seeds are vendor-shipped, never operator-edited,
and shouldn't appear in operator-library management UIs. Move
them to a code constant (mirroring `SEEDED_RESPONSE_TYPE_DEFINITIONS`).

**Change.**

- New `app/services/rules/seeds.py::SEEDED_RULE_SETS` constant,
  same shape as `SEEDED_RESPONSE_TYPE_DEFINITIONS` (list of
  rule-tree dicts with name + description + combinator + rules).
- New `materialise_seed_rule_sets(db, session)` mirror of
  `ensure_default_response_type_definitions` — copies each seed
  into `session_rule_sets` (the per-session table) on session
  create. Idempotent.
- One-shot data migration: every existing `rule_sets` row with
  `scope=seed` deleted (the constant is now the source of
  truth). For sessions that already had instruments pointing at
  a seed RuleSet — none today since `instruments.rule_set_id`
  is brand-new from 13D PR 4 and 15B hasn't shipped — no
  pointer fix-up needed.
- `app/services/rules/library.py::list_visible_rule_sets`
  loses its seed branch; it now reads only Personal RuleSets
  from the operator library.

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
  - For each `rule_sets` row owned by `owner_user` (Personal
    only post-Slice 1), copy + current-revision-snapshot into
    `session_rule_sets` with `library_origin_id` set.
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
- The picker's source flips from `rule_sets` (today) to
  `session_rule_sets` for the chosen session — operators see
  *this session's* RuleSets, with "Add from library" as the
  bridge to bring more in.

### Slice 5 — Operator Settings: library management (1 PR, ~200 LOC)

**Why.** Operators need a place to view / edit / delete library
entries that's not tied to any one session.

**Change.**

- `/operator/settings` grows two new subsections:
  - **Response Type Definitions library** — list every
    `operator_response_type_definitions` row the operator owns;
    Add / Edit / Delete affordances.
  - **RuleSet library** — list every `rule_sets` row the
    operator owns (Personal scope only post-Slice 1); Add / Edit
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
  `rule_sets.scope == "seed"` references in the codebase (Slice
  1 should have removed them all).

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
- **Workspace-seed tier post-Slice 1.** Operators lose the
  ability to "Save to library" a seed (it's no longer in the
  rule_sets table). They can still copy a session's seed
  RuleSet into their library by name — Slice 4's "Save to
  library" runs unchanged on a session-RuleSet copy whose
  origin is a seed. Confirm this matches operator expectations
  before Slice 1 ships.
- **Existing data migration.** Pre-15C sessions don't have
  `session_rule_sets` rows; instruments don't yet point at
  anything. Slice 2's `materialise_operator_libraries` runs
  on session create only, so existing sessions don't backfill.
  Operators wanting to apply a library entry to an existing
  session use the Slice 4 "Add from library" affordance.

---

## Critical files

- New: `app/services/rules/seeds.py` (Slice 1),
  `app/services/sessions.py::materialise_operator_libraries`
  helper (Slice 2), routes + templates for the four new
  affordances (Slices 3 / 4 / 5).
- Touched: `app/services/rules/library.py`,
  `app/services/instruments/_rtds.py`,
  `app/services/sessions.py`,
  `app/web/routes_operator/_rule_builder.py` +
  `_instruments.py` + `_settings.py`,
  `app/web/views/_rule_builder.py` + `_instruments.py` +
  `_settings.py`,
  templates for the RTD card + Rule Builder + operator
  Settings.
- No schema changes — every table / column comes from 13D.

---

## Verification

- `pytest -q` green on SQLite + `ci-postgres` after each slice.
- `ruff check .` green.
- Audit-event gate (`tests/unit/test_audit_detail_schema.py`)
  catches any envelope drift in the four new emitters.
- New tests per slice:
  - Slice 1: `test_seed_rule_set_materialisation.py` —
    seeds copy into `session_rule_sets` on session create;
    `rule_sets.scope == "seed"` row count after migration is
    zero.
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
