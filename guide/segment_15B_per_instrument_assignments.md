# Segment 15B — Per-instrument assignments

**Status:** Plan stub (2026-05-09).
**Sizing:** ~1 segment-sized chunk (5-7 PRs).
**Depends on:** none strictly required, but **15A first** is
recommended so the per-instrument assignment UI can consume the
session-level friendly-label resolver without re-introducing
hardcoded literals.

---

## Goal

Let each `Instrument` have its own assignment set, so that (for
example) "the Manager survey" can collect different reviewer →
reviewee pairings than "the Peer survey" within the same session.
Today, every instrument shares the session's single assignment list.

---

## Why now

The schema **already supports** per-instrument assignments. From
`app/db/models/assignment.py:22-43`:

```
__table_args__ = (UniqueConstraint(
    "session_id", "reviewer_id", "reviewee_id", "instrument_id",
    name="uq_assignment_unique",
),)
```

`Assignment` carries `instrument_id` as a non-null FK, and the
unique constraint includes it — so the same `(reviewer, reviewee)`
pair coexists across instruments by design. The reviewer surface
already iterates Assignment rows per instrument
(Segment 11D follow-on shipped this multi-instrument render).

What blocks per-instrument assignments today is the **service
layer**, not the schema:
`app/services/assignments.py::replace_assignments` (around line
574-583) takes a single `pairs` list and **fans out across every
instrument in the session** with the same `context` and `include`
replicated identically per fan-out. That uniform fan-out is a
policy choice that made sense when every session had one
instrument; it's now the only thing standing between the schema
and the feature.

---

## Migration & invariants (locked 2026-05-09)

Three properties this segment must preserve. They're already
implicit in today's behaviour; calling them out explicitly here
so reviewers can hold each slice against them.

1. **Schema migration is a no-op — pre-15B data already looks
   like 15B data.** Sessions today have N Assignment rows per
   `(reviewer, reviewee)` pair (one per instrument, identical
   except for `instrument_id`), because `Assignment.instrument_id`
   + the `(session_id, reviewer_id, reviewee_id, instrument_id)`
   unique constraint are already present. Pre-15B sessions
   simply have "instrument #1 has these assignments and
   instrument #2 has the same assignments" — and stay that way
   until an operator divergent-edits one of them. No backfill,
   no Alembic migration in 15B itself (the only schema move is
   `instruments.rule_set_id`, pre-positioned by Segment 13D PR 4 — pointer targets `session_rule_sets`, the per-session copy table introduced by 13D PR 2 / 15C).

2. **Default instrument #1 always exists and always has
   assignments.** `services.instruments.ensure_default_instrument`
   (called from `replace_assignments`) already guarantees every
   session has at least one instrument; `replace_assignments`
   already writes Assignment rows for every instrument in the
   session. The single-instrument flow continues to behave like
   the old model — instrument #1 is the survivor of the
   one-session-one-assignment-list world, and any single-
   instrument session looks byte-identical to its pre-15B self.

3. **Multi-instrument UX only activates when N > 1.** When a
   session has exactly one instrument, the Assignments page,
   the Quick Setup Assignments slot, and every other
   assignment-related surface render exactly as they do today —
   no tab strip, no "All Instruments" view, no per-instrument
   repetition. The per-instrument selector / tabs / cards only
   render when `len(instruments) > 1`. Operators who never add
   a second instrument should not see any new chrome.

### Rider — possible Instruments-page UI rethink (deferred)

A side-effect of this segment is that operators who do exercise
multi-instrument sessions will accumulate more instruments per
session than the current Instruments page anticipates. The
existing layout stacks per-instrument cards downward
indefinitely; that becomes unwieldy past ~3-4 instruments.

**Possible future direction:** convert the per-instrument cards
into a tab strip (one tab per instrument, one card visible at a
time), mirroring the Assignments-page tabs Slice 4 introduces.
Same data, less scroll.

**Out of scope here.** The Instruments-page rebuild belongs in a
follow-on UI segment, not in 15B's already-substantial slice
ladder. Surface it once 15B has shipped and operator feedback
confirms the scroll burden is real.

---

## Approach

### Slice 1 — Service-layer scope (1 PR, ~200 LOC)

Replace the single fan-out in `replace_assignments` with a
per-instrument scope. Two API options:

- **A (recommended).** Add an `instrument_id` parameter; default
  `None` keeps current behaviour (apply to every instrument).
  Callers that want per-instrument behaviour pass an explicit id
  and call once per instrument.
- **B.** Replace the `pairs` parameter with
  `pairs_by_instrument: dict[int, list[…]]`; backfill an
  "all instruments" key for the existing call site.

Recommend A — smaller blast radius, every existing call site stays
behaviour-compatible without touching the parameter shape.

Also touch:
- `assignments.existing_count`,
  `assignments.delete_session_assignments`,
  `csv_imports.parse_manual_csv` — gain optional `instrument_id`
  filters.
- `monitoring.per_reviewer_coverage` — already iterates Assignment
  rows; just confirm the instrument-scope is honoured in the
  pivot.

Audit envelope stays unchanged; the existing `instrument_id` field
inside `assignments.replaced` payload (already part of 11K's
canonical schema for this event family) starts carrying
real per-instrument variation.

### Slice 2 — Persist the per-instrument RuleSet selection (1 PR, ~150 LOC)

**Today (post-15C).** RuleSets live in two tiers: the operator
library (`operator_rule_sets`, post-13D PR 0 rename — visible
across all of an operator's sessions) and per-session copies
(`session_rule_sets` —
auto-copied from the operator library on session create + the
operator's "Add from library" / "Save to library" actions; see
`segment_15C_operator_libraries.md`). Per-instrument application
of a `session_rule_sets` row is the missing link this slice
delivers.

**Goal.** Make the selection persistent and per-instrument: each
instrument records the per-session RuleSet copy currently in
effect for it.

**Schema dependency.** `instruments.rule_set_id` (nullable FK to
`session_rule_sets`, `ON DELETE SET NULL`) is pre-positioned by
**Segment 13D PR 4**; the `session_rule_sets` table itself by
**13D PR 2** (see `segment_13D_db_prep.md` for the FK-direction
rationale and the library / per-session-copy split). The
`uq_session_rule_set_session_name` constraint added by
**Segment 13A-2** guarantees name-based references into the
table are unambiguous — relevant for 12A-1's settings-CSV
serialisation (`instruments[N].rule_set_name` resolves by name)
and for the picker label rendering this slice consumes. This
slice is pure service / route work — no migration in 15B.

**Service-layer change.** `replace_assignments` (touched in Slice
1) accepts `instrument_id` and writes the chosen
`session_rule_sets.id` onto that instrument row alongside the new
Assignment rows. The Rule Builder POST handlers
(`app/web/routes_operator/_rule_builder.py`) thread the
`instrument_id` from the URL through into the persistence call.
The picker reads from `session_rule_sets` (the session's local
copies), not from `operator_rule_sets` (the library) — operators "Add from
library" via the dedicated action introduced in 15C, then choose
from the session's local pool here.

**Resolution semantics.** No "session default + per-instrument
override" inheritance — the column is the single source of
truth per instrument. NULL = "no RuleSet currently applied to
this instrument" (initial state for every existing instrument
post-13D PR 4; also the state after a reset-assignments action).
A future **session-level default** (e.g. a
`sessions.default_session_rule_set_id` column to seed new
instruments from) is left out of this segment; revisit if
operator feedback asks for it. Most teams will set the same
session-level RuleSet on every instrument, which works fine
without inheritance.

**FK behaviour wired through to the UX:**

- **Delete instrument** (existing 10D action): the instrument's
  pointer dies with the row; the session's RuleSet copy is
  untouched. No UX warning needed beyond what 10D already shows.
- **Delete a session's RuleSet copy** (operator removes it from
  the session, a 15C affordance): SQL `SET NULL` on every
  `instruments.rule_set_id` pointing at it. **UX gate to add in
  this slice:** the delete-confirm dialog grows a line listing
  every instrument in the session that currently applies the
  RuleSet ("Removing will clear this rule from N instrument(s):
  [list]. Their next assignment generation will require choosing
  a new rule.").
- **Delete from the operator library** (13A action, surfaced via
  15C's library-management UI): does **not** touch any instrument
  pointer. Instrument pointers target session copies, which
  survive library deletes via the `library_origin_id SET NULL`
  cascade introduced in 13D PR 2.
- **Reset an instrument's assignments** (a new 15B affordance):
  `UPDATE instruments SET rule_set_id = NULL WHERE id = ?` plus
  the existing assignment-row delete. Session-RuleSet copy
  untouched.

### Slice 3 — Manual-assignment CSV column (1 PR, ~100 LOC)

`parse_manual_csv` today reads `(ReviewerEmail, RevieweeEmail,
PairContext1, PairContext2, PairContext3)`. Add an optional
`Instrument` column (matched against `Instrument.short_label` first,
then `Instrument.name`). Empty value → "all instruments" (current
behaviour, preserves backwards compatibility for existing files).

Validation: unknown instrument label → row-level
`ValidationIssue` from the existing CSV-import error pipeline,
same shape as unknown-reviewer / unknown-reviewee errors.

### Slice 4 — Assignments page UI (2 PRs, ~600 LOC total)

**Honours invariant #3** (multi-instrument UX only activates when
N > 1). When `len(instruments) == 1`, this slice is a no-op
visually — the page renders exactly as it does today. The tab
strip, the "All Instruments" affordance, and the per-instrument
chrome only mount when a second instrument exists.

When N > 1, the Assignments page becomes per-instrument in two
PR sub-slices:

- **4a — Per-instrument tabs / cards.** A tab strip per instrument
  (consume `Instrument.short_label` via `views.page_button_label`)
  + an "All Instruments" tab showing the union (read-only) when
  multiple instruments diverge.
- **4b — Per-instrument Rule Based card + Manual upload.** Each
  per-instrument tab gets its own Rule Based card (the picker
  writes through to `instruments.rule_set_id` per Slice 2) and
  its own manual CSV upload.

Operators who don't care about per-instrument differences keep an
"apply to all" affordance — a button at the top of the All
Instruments tab that copies the current tab's selection to every
other instrument in one click.

### Slice 5 — Quick Setup card (1 PR, ~100 LOC)

`/operator/sessions/{id}` Quick Setup Assignments slot grows the
same instrument selector as a `<select>` in front of the file
input + Generate button. Default = "All instruments" (current
behaviour). Audit/lifecycle wiring is already in place from
Segment 11J.

### Slice 6 — Validation + reviewer-surface confirmation (1 PR, ~100 LOC)

`validate_session_setup` already checks "every reviewer has ≥1
assignment". That generalises naturally — no schema change, but
the per-instrument breakdown should surface in the Validate page
(e.g. "Alice is missing assignments for the Peer survey"). Add a
new `ValidationRule` keyed
`assignments.reviewer_missing_for_instrument`.

The reviewer surface is already multi-instrument-aware (Segment
11D follow-on shipped this); it'll naturally show empty pages for
instruments where the reviewer has no assignments. Confirm via a
manual smoke test on the dev slot — there's no template change
needed, but the empty-state copy may want polish.

### Slice 7 (deferred — only on real use case) — `AssignmentContext1-3`

**Out of 13D scope by design.** 13D's DB-prep segment explicitly
*does not* pre-position columns for AssignmentContext (see
`segment_13D_db_prep.md` scope-sweep table); this slice owns the
schema + service + UI work end-to-end if it ever lands.

**Semantics (locked 2026-05-09).** AssignmentContext is logic-
bearing per-assignment information (e.g. "this assignment is for
Award X category") that drives downstream filtering, reporting,
or rule evaluation. Distinct from `PairContext1-3` which is
display-only info about a (reviewer, reviewee) pairing (e.g.
"she was your student in NN1101"). The two have categorically
different infrastructure needs — labels for PairContext (handled
in 15A); rule-engine integration for AssignmentContext.

**Why deferred.** Most use cases for logic-bearing per-assignment
fields are derivable from existing reviewer + reviewee tags
evaluated through the rule engine. This slice should only land
when a real use case surfaces that **cannot** be expressed via
tags + rules.

**If it lands, it needs (in one PR-sized slice):**

1. **Schema.** Add `assignment_context_1 / _2 / _3 VARCHAR(255)`
   columns on `Assignment` (mirrors the tag pattern, plays well
   with CSV) **or** reserve well-known keys
   `assignment_context_1/2/3` inside the existing
   `Assignment.context` JSON dict (cheaper but harder to type and
   to import / export). Recommendation at write time: named
   columns.
2. **Rule-engine integration.** New predicate operands so RuleSets
   can filter / quota / order on AssignmentContext values. Touches
   `app/services/rules/engine.py` + the Rule Builder UI.
3. **CSV import column.** Manual-assignment CSV grows
   `AssignmentContext1` / `2` / `3` columns alongside the existing
   `PairContext1-3`.
4. **Friendly labelling.** Once the columns exist, plumb them into
   the 15A resolver (add `assignment_context` to the `source_type`
   enum). The Settings editor subsection picks them up
   automatically.

**Triggering criterion.** Surface a concrete operator request
that fails the "can this be expressed via reviewer + reviewee tags
plus rules?" sniff test before authoring the slice.

---

## Risks + open questions

- **Existing data migration.** Sessions with multiple instruments
  today have N copies of every Assignment (one per instrument)
  with identical context / include. After Slice 1, those copies
  remain identical until an operator divergent-edits them — no
  migration needed, but the audit log will show "no-op" assignment
  replays from the first divergent edit. Acceptable.
- **Seeded RuleSets, post-15C.** Workspace seeds (Full Matrix
  etc.) move out of `operator_rule_sets` to a code constant in
  15C (mirroring how `SEEDED_RESPONSE_TYPE_DEFINITIONS` already
  works), and are materialised into `session_rule_sets` directly
  on session create — same mechanism as auto-copy from the
  operator library. The instrument's pointer therefore always
  targets a `session_rule_sets` row, regardless of whether the
  origin is a seed, a library entry, or an inline-authored rule.
  No special-casing in this slice's persistence code.
- **Email invitations.** Reviewer-scoped, not instrument-scoped.
  No change needed — reviewers receive one invitation per session
  regardless of how their assignments break down by instrument.
- **CSV export.** When Segment 12A export ships, the manual-CSV
  shape gains the `Instrument` column for sessions where it's
  populated. Pin that in the 12A spec when this segment lands.

---

## Critical files

- Touched: `app/services/assignments.py`,
  `app/services/csv_imports.py`,
  `app/services/rules/library.py`,
  `app/services/rules/engine.py`,
  `app/services/validation.py`,
  `app/web/routes_operator/_assignments.py`,
  `app/web/routes_operator/_rule_builder.py`,
  `app/web/routes_operator/_quick_setup.py`,
  `app/web/views/_rule_builder.py` + `_quick_setup.py`,
  `app/web/templates/operator/session_assignments.html`.
- Schema dependency only: `instruments.rule_set_id` is
  pre-positioned by Segment 13D PR 2 (`SET NULL` on RuleSet
  delete). No migration in this segment.
- Possibly touched in Slice 6: `app/web/views/_validate.py`,
  `app/web/templates/operator/session_validate.html`.

---

## Verification

- `pytest -q` green on SQLite + `ci-postgres` after each slice.
- `ruff check .` green.
- New tests per slice:
  - Slice 1: `test_assignments_service.py` regression tests for the
    `instrument_id=None` (apply to all) vs. per-instrument paths;
    audit-event payload assertions.
  - Slice 2: `test_instrument_rule_set_persistence.py` — choosing
    a RuleSet writes `instruments.rule_set_id`; Reset clears it
    back to NULL; deleting the RuleSet clears every pointer to it
    via SQL `SET NULL` (the schema-level cascade is covered by
    13D PR 2's schema test, but the route-level UX warning copy
    also lands here).
  - Slice 3: `test_manual_csv_per_instrument_column.py` — happy
    path + unknown-instrument error.
  - Slice 4 / 5: existing assignment-page integration tests
    parameterised over single-instrument vs. multi-instrument
    sessions.
  - Slice 6: new `assignments.reviewer_missing_for_instrument`
    `ValidationRule` covered in `test_session_validate_page.py`.
- Manual smoke on the dev slot for Slice 4-6 (per-instrument tabs
  render, divergent assignments persist correctly, reviewer
  surface honours the per-instrument scope).
