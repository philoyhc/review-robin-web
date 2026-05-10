# Segment 15D — Assignments revamp: Pair Context as Setup primary, Assignments goes derived

**Status:** Planning. **Holistic-sequence revision
2026-05-10** — fast-tracked into the locked sequence
**13E → 12C → 15D → 12A-3**. All design open questions
settled (page name, generation triggering, JSON-column
fate, Quick Setup integration, lifecycle gating); schema
prep absorbed into 13E (ships the new `relationships`
table inert); deferred 12C work folded in (Quick Setup
slot 3 retire-and-restore, chrome restructure, Operations
Assignments page move). Sized as **8 PRs** (locked
2026-05-10).

**Codebase-check revision 2026-05-10**: PR 6 expanded
to absorb the now-deferred 12C-1 PR 3 + PR 4 work
(bulk Include toggle + ad-hoc-toggle drop + validation
copy refresh — they ship on the Operations Assignments
page from the start, no Setup-page intermediate). PR 6's
`Assignment.context` drop confirmed to retire the
`assignment_context_*` keys alongside the
`pair_context_*` lift (codebase scan confirmed both
families are operator-typed via the manual CSV only;
no rule-engine or non-display consumer). PR 7 keeps the
manual-CSV `parse_manual_csv` / `replace_assignments`
route as a **dev-only feature** (no operator UI; route
+ handler stay accessible).

> **Schema prep handled by 13E** — see
> `guide/segment_13E_db_prep.md`. The
> `relationships` table is created inert in 13E PR 2;
> 15D wires it. The follow-on "schemas-needed-beforehand"
> doc previously contemplated for this segment **becomes
> the 13E plan**; the "revised 13C that prepares for
> 15D" follow-on stays open as a separate concern (13C
> proper is still planning).

## Why this matters

12C settled that manual assignments are a discouraged
workflow — rule-based per-instrument is the default.
Stepping back further: **why does manual assignments exist
at all?**

In larger sessions, hand-curating pair-by-pair assignments
is impractical. The actual operator need that "manual"
addresses is **pairwise information that can't be derived
from per-entity attributes alone** — for example:

- Reviewer A has a *conflict of interest* with Reviewee B.
- Reviewer C is Reviewee D's *mentor*.
- Reviewer E previously *peer-reviewed* Reviewee F and
  shouldn't be paired with them again this cycle.

Today the only way to express these constraints is to
encode them implicitly — by hand-uploading an assignments
CSV that excludes the bad pairs and includes the good
ones. That's brittle (the operator re-derives the
constraints every cycle) and conflates two different
things: the **constraint** ("don't pair these two") and
the **execution** ("here are the rows").

The right primitive is a **per-pair attribute table** that
the operator populates once, parallel to the reviewer +
reviewee rosters. Rules consume it the same way they
consume reviewer / reviewee tags. Generation runs from
*all three* inputs.

## Goal

Replace today's Assignments **Setup** page with a new
per-pair-attributes Setup page (working name
**"Relationships"** — see naming options below). The
Assignments table becomes **always system-derived** from
rosters + per-pair attributes + RuleSets; manual
assignment-row uploads retire entirely. A read-only
Assignments **Operations** page may persist for previewing
generated assignments and surfacing bulk overrides
(e.g. 12C-1's exclude-self-reviews toggle).

The four Setup primitives become:

1. **Reviewers** — per-reviewer attributes (existing).
2. **Reviewees** — per-reviewee attributes (existing).
3. **Relationships** *(new)* — per-pair attributes.
4. **Instruments** — what the operator asks reviewers
   about (existing).

Plus **Email Template** for the email surface; rule-based
generation (drives RuleSets per instrument via Rule
Builder) reads from all four.

## The new Relationships page (Setup)

### Naming (locked 2026-05-10)

**Page title: "Relationships".** Schema-level identifier
stays `pair_context` (matches the existing `source_type`
enum used by display fields and — once 15D ships — by
Rule Builder matchers / filters). Two-name strategy:
friendly name in the chrome, machine-name in the data
layer. Same pattern as `email_or_identifier` (machine)
vs "Reviewee email" (UI).

Alternatives considered (Pairs / Pair Notes / Pair
Context) and rejected — Relationships reads most
naturally for the per-pair-attribute use case
(mentorship / COI / prior-cohort).

### Surface

- New **Setup** row tab in the chrome between
  **Reviewees** and **Instruments** (post-12C-3 reorder
  Instruments stays after Relationships).
- Page surface mirrors today's Reviewers + Reviewees
  pages: **upload CSV**, preview table with column
  visibility toggles, edit-row affordances per the
  inline-edit pattern when it lands (`unfinished_business`
  #25).
- Status row pill on every session-scoped page surfaces
  the count: `Relationships: <n> · <m active>`.

### Row shape

Per-pair, keyed on the (reviewer, reviewee) pair. Columns:

| Column | Type | Notes |
|---|---|---|
| `ReviewerEmail` | string (FK lookup) | Resolved against `reviewers.email` on import. |
| `RevieweeEmail` (or `RevieweeIdentifier`) | string (FK lookup) | Resolved against `reviewees.email_or_identifier`. |
| `PairContextTag1` | string (free-form) | Operator-named. E.g. "Mentor", "COI", "Prior cohort". |
| `PairContextTag2` | string (free-form) | Slot 2 — same shape. |
| `PairContextTag3` | string (free-form) | Slot 3 — same shape. |
| `Status` | enum (`active` / `inactive`) | Inactive rows are ignored by rule generation. Mirrors the per-row Inactivate pattern from `unfinished_business` #36. |

Three tag slots mirror the reviewer / reviewee tag
shape today — operators are already used to thinking in
"3 free-form tags", so the per-pair table reads
consistently.

### CSV format (export + import)

Round-trips with the existing per-entity CSV pattern
(12A-1 PR 2 for rosters; the 12A-1 export track grows a
new `{code}_relationships.csv` extract). 6-column wide
shape:

```
ReviewerEmail,RevieweeEmail,PairContextTag1,PairContextTag2,PairContextTag3,Status
```

Header pinned in unit tests; same per-entity-import flow
as `parse_reviewer_csv` / `parse_reviewee_csv`. Wipe-and-
replace on upload.

### Lifecycle gating

Same as the rosters: editable in `draft` / `validated`;
locked in `ready` / `paused` / `closed`. Inactivating a
row mid-cycle doesn't re-run generation; the operator
runs Generate explicitly to apply the change.

## Rule Builder enhancement

Rule Builder's source enumeration today supports
`reviewer.tag_N`, `reviewee.tag_N`, and
`reviewee.profile_link`. Add `pair_context.tag_N`
(N = 1, 2, 3) as a fourth source class so rules can
filter / quota / match on per-pair attributes:

- **MATCH rule.** "Pair where `pair_context.tag_1 ==
  'Mentor'`" → guarantee the pair lands in the
  assignments table.
- **FILTER rule.** "Exclude pair where
  `pair_context.tag_1 == 'COI'`" → drop the pair from
  candidate set before the engine runs.
- **QUOTA rule.** "At most N self-reviews per reviewer"
  becomes generalisable to "At most N pairs where
  `pair_context.tag_3 == 'Prior cohort'` per reviewer".
- **COMPOSITE rule.** Combines as today.

The existing `_is_self_review` predicate
(`is_self_review`, post-12A-1 PR 4a rename) stays — it's
a derived predicate (computed on-the-fly from
`reviewer.email == reviewee.email_or_identifier`), not
an operator-typed pair attribute. Self-review is
orthogonal to pair context.

## Assignments — always derived

After 15D, every `Assignment` row is **system-generated**
from the four-input chain:

```
reviewers + reviewees + relationships + ruleset
   → engine → assignments
```

There is no operator-write path into the `assignments`
table. The current routes that write rows directly
(manual CSV upload, full-matrix POST — already retired
per 12C — etc.) are gone. The `Assignment.context` JSON
column **retires entirely** (locked 2026-05-10): the
canonical pair context lives on the `relationships`
table, joined at generation time, and "which instrument
does this assignment apply to" is already covered by
`Assignment.instrument_id`. With both moves, the JSON
column has no remaining tenants — drop the column in the
migration rather than just clearing keys.

### Generation triggering (locked 2026-05-10)

**Manual Generate after Validate.** Generation does **not**
auto-fire from Quick Setup completion or from any
mutation. The operator runs Generate explicitly, and
runs it after the session validates so the engine
operates on validated inputs.

The Quick Setup chain (post-12C) ends after
reviewers → reviewees → relationships → settings; it
does **not** chain into Generate. Earlier sketches that
suggested auto-generate-on-Quick-Setup-completion are
superseded.

The flow is:

```
Quick Setup → Validate → Generate → (Activate)
```

**"Super buttons" for next-action shortcuts.** The
Operations Assignments page (and likely Session Home)
can offer multi-step shortcut actions that chain
common sequences in one click — e.g. "Validate +
Generate", "Validate + Generate + Activate", or
"Regenerate after roster change → Validate". Treat
these as UI sugar over the underlying explicit steps;
each underlying action stays scoped and individually
clickable so the operator can still pause / inspect
between steps if they want. Sized as a standalone slice
inside 15D, or split off as a follow-on UI polish PR.

## Operations Assignments page (locked 2026-05-10)

A dedicated Assignments page remains, **reframed as an
Operations row tab** alongside Validate / Previews /
Invitations / Responses — lifecycle-time information,
not setup-time authoring.

Surface:

- Read-only preview of the current generated
  assignments table (what the engine produced from the
  4-input chain).
- **Generate** button (replaces today's Setup-page
  Rule Based card's Generate). Operator-driven; runs
  the engine against the four current inputs and
  rewrites the `assignments` table.
- **Super buttons** (per the locked decision above) for
  Validate + Generate / Validate + Generate +
  Activate-style chains. Render as Primary buttons in
  a top action row; underlying single-step actions
  remain available for granular flows.
- Per-instrument breakdown — N assignments per
  instrument; surface zero-assignment instruments as
  warnings. Mirrors the role today's status pills
  serve, but at instrument granularity.
- Bulk overrides:
  - **Exclude self-reviews** toggle (the 12C-1 PR 3
    bulk control, with its `sessions.self_reviews_active`
    column). Moves here from its current Setup-row
    home as part of 15D's Setup-vs-Operations split.
  - Per-row Include checkbox (12C-1 model preserved)
    stays as the last-mile override on individual
    rows.

## Workflow consequences

**Pre-15D operator setup flow:**
1. Build rosters (Reviewers + Reviewees pages or Quick Setup).
2. Define instruments + per-instrument RuleSets.
3. Generate assignments via the Setup Assignments page's
   Rule Based card (or manually upload — discouraged).
4. Validate, Activate, etc.

**Post-15D operator setup flow:**
1. Build rosters + relationships + instruments
   (Reviewers + Reviewees + Relationships + Instruments
   pages, or Quick Setup with all four roster-style
   slots populated).
2. **Validate** — checks rosters, relationships,
   instruments, per-instrument RuleSets.
3. **Generate** (operator-driven) — runs the engine
   against the four-input chain; populates the
   assignments table on the Operations Assignments
   page.
4. **Activate**, etc.

Steps 2 + 3 may be condensed via a "Validate +
Generate" super button (per the locked Operations
Assignments page surface). Generation is **never**
implicit in another step — Quick Setup completion does
not auto-Generate; mutations don't auto-regenerate.

The shift: per-pair info goes from "implicit in the
manual assignments CSV" → "explicit in a parallel
Relationships table". Operators name their constraints
in plain language; rules act on them. Generation
becomes a deliberate, validated, operator-clicked
action — not a hidden side-effect of upload.

## Quick Setup integration (locked 2026-05-10)

The Quick Setup card grows back to **4 slots** with
Relationships joining the roster-class slots:

| Slot | Upload | Status |
|---|---|---|
| 1 | Reviewers CSV | Existing (12C unchanged) |
| 2 | Reviewees CSV | Existing (12C unchanged) |
| 3 | **Relationships CSV** *(new)* | Optional — a cycle works without explicit relationships |
| 4 | Settings CSV | Existing (12C-2 — was slot 3 after manual-assignments retirement, now slot 4 again) |

Relationships is treated as **entirely parallel** to
Reviewers and Reviewees in the chain — same upload /
preview / wipe-and-replace contract; same lifecycle gate;
same `parse_relationship_csv` per-entity importer. The
distinguishing trait is **optionality**: a session can
generate assignments with only rosters + RuleSets (no
explicit pair context), so slot 3 is leave-empty-friendly
in a way slots 1 + 2 aren't (rosters are required for
any non-empty session).

The `quick_setup_submit_all` chain ordering becomes:
reviewers → reviewees → relationships → settings.
Generation does **not** fire from Quick Setup completion
(per the locked manual-Generate-after-Validate
decision); Quick Setup leaves the operator on Session
Home with Validate + Generate as the next obvious
action.

## Migration story

**Existing sessions** with manually-typed assignment rows
keep their current `Assignment.context.pair_context_*`
data. 15D's migration:

1. **Backfill.** For every session with non-empty
   `Assignment.context.pair_context_*` values, lift each
   distinct pair into a new `relationships` row carrying
   the same tag values. Audit-log a
   `relationships.migrated_from_assignment_context` event
   per session with counts.
2. **Schema.** **Drop the `Assignment.context` JSON
   column entirely** (locked 2026-05-10 — the only
   tenants were `pair_context_*` keys, and "which
   instrument does this apply to" is already covered by
   `Assignment.instrument_id`). Lands as a follow-on
   cleanup migration once the backfill is observed
   clean.
3. **Generation behaviour.** Sessions without
   relationships rows (greenfield, or sessions whose
   rosters never had pair context) generate the same as
   before; the new source class just doesn't fire on
   any rule.
4. **No operator-visible breakage** for sessions that
   didn't use pair context. Sessions that did get the
   migration silently — operators see the same
   assignments after Generate.

## Lifecycle gating (locked 2026-05-10)

Relationships changes follow the **same gate as the
rosters**: editable in `draft` / `validated`; locked
in `ready` / `paused` / `closed`. Mid-cycle edits
without a Generate re-run aren't honoured by the
existing assignments table anyway, so the simpler
matched-to-rosters gate is the right call. Operators
who discover a COI mid-cycle Pause → edit Relationships
→ Generate → Activate, mirroring the roster-edit
workflow.

## Schema implications (high-level)

> Detailed in the follow-on "schemas-needed-beforehand"
> doc per the planning conversation. Sketch only here:

- **New table `pair_contexts`** (or `relationships`):
  `(session_id, reviewer_id, reviewee_id, tag_1, tag_2,
  tag_3, status, created_at, updated_at)` with unique
  constraint on `(session_id, reviewer_id, reviewee_id)`.
- **`Assignment.context` JSON column retires entirely.**
  `pair_context_*` keys lift to the new
  `relationships` table; "which instrument does this
  apply to" is already on `Assignment.instrument_id`.
  No remaining tenants — drop the column.
- **Rule schema** adds a `pair_context.tag_N` source in
  the matcher / filter / quota grammar (validated
  against `RuleSetSchema` in `app/schemas/rules.py`).
- **No changes** to display-fields source enum
  (`pair_context` is already there); the resolver just
  joins against the new table instead of reading from
  `Assignment.context`.

## Out of scope

- **Reverse-engineering legacy assignments tables into
  pair context.** The migration is a straight backfill
  from existing `Assignment.context.pair_context_*`
  values; we don't try to infer pair context from
  assignment rows that lack it.
- **A "manual override" affordance for individual
  assignment rows.** Per the 12C direction, manual
  assignment-row authoring is gone. The per-row Include
  checkbox stays as the post-generation override, but
  it doesn't add new rows — it just deactivates ones
  the engine produced.
- **Multi-tag pair-context fanout** (e.g. one pair with
  two distinct mentor tags). 3 free-form tag slots is
  enough; if an operator needs >3, they collapse into
  a single tag with a comma-separated value.
- **Pair context per instrument.** Pair context lives
  at the (reviewer, reviewee) level, not the
  (reviewer, reviewee, instrument) level. If an operator
  needs instrument-specific pair context, they encode
  it in the rule (e.g. "exclude COI pairs only on
  Instrument #1").
- **Importing pair context via the Settings CSV.** The
  Settings CSV (12A-1 / 12A-2) covers session-level
  config; the per-pair Relationships table travels in
  its own per-entity CSV like rosters.

## PR sequence (8 PRs, locked 2026-05-10)

Depends on **13E** (`sessions.self_reviews_active`
column + `relationships` table) and **12C-1** (the
self-review revamp's generation-path wiring + Rule
Builder checkbox + bulk Include toggle landing page +
ad-hoc-toggle drops + full-matrix cleanup) having
shipped. Coordinates with **12A-3** for the
Relationships per-entity export + import + Quick Setup
slot 3 graduation.

PRs are sequenced for dependency safety; some can
parallel-ship within the dependency graph.

### PR 1 — Relationships service + per-entity importer

- New `app/services/relationships.py` with CRUD on the
  `relationships` table (created in 13E PR 2).
- `parse_relationship_csv` importer (mirrors
  `parse_reviewer_csv` / `parse_reviewee_csv`).
- Resolves `ReviewerEmail` against
  `reviewers.email`; resolves `RevieweeEmail`
  against `reviewees.email_or_identifier`. Rejects rows
  with unknown identifiers.
- Wipe-and-replace per-row upsert pattern; unique
  constraint enforced by 13E's
  `uq_relationships_session_reviewer_reviewee`.
- Audit event `relationships.imported` registered in
  `EVENT_SCHEMAS`.
- *Note:* the per-entity export route + the
  `/relationships` Manage page upload form ship in
  **12A-3 PR 2** alongside the Relationships extract;
  this PR is the service-layer foundation.

### PR 2 — Relationships Setup page + chrome integration

- New page `/operator/sessions/{id}/relationships`
  with upload / preview / status pill, mirroring the
  Reviewers + Reviewees Setup pages.
- Chrome nav: insert Relationships tab into the Setup
  row between Reviewees and Instruments. Setup row
  reads:
  `Reviewers · Reviewees · Relationships ·
  Instruments · Email Template`.
- Status pill on every session-scoped page surfaces
  the Relationships count.
- View-shape adapter slot in `views/_setup.py`
  (Setup card on Session Home gains a Relationships
  row).
- *No chrome moves for Assignments yet* — that's
  PR 6's job.

### PR 3 — Rule grammar additions (`pair_context.tag_N`)

- Extend `app/schemas/rules.py` `RuleSetSchema` to
  accept `pair_context.tag_1` / `.tag_2` / `.tag_3`
  as source values in MATCH / FILTER / QUOTA /
  COMPOSITE rules.
- Rule Builder UI: add `Pair context` source class
  to the source-picker dropdown; render with
  `tag_N` slot selector.
- Engine reads pair_context tags from the
  `relationships` table at generation time
  (joined on `(session_id, reviewer_id, reviewee_id)`).
- Independent of PR 2; can ship in parallel.

### PR 4 — Generation-path consumption of relationships

- `app/services/rules/engine.py` joins
  `relationships` on `(session_id, reviewer_id,
  reviewee_id)` per pair when evaluating
  `pair_context.tag_N` matchers / filters / quotas.
- Inactive relationships rows (`status = "inactive"`)
  are filtered out of the candidate set before rule
  evaluation.
- Tests: rule using `pair_context.tag_1 == "Mentor"`
  matches the right pairs; inactive rows skipped;
  pair without a `relationships` row gets empty tag
  values (no false matches).

### PR 5 — Backfill `Assignment.context.pair_context_*` into `relationships`

- One-time data migration that scans every
  `Assignment` row with a non-empty
  `context.pair_context_*` value and inserts a
  `relationships` row per distinct
  `(session_id, reviewer_id, reviewee_id)` carrying
  the same tag values.
- Audit event
  `relationships.migrated_from_assignment_context`
  per session with counts.
- Idempotent: re-running the migration skips
  already-existing relationships rows (unique
  constraint).
- Tests: backfill on a session with mixed
  pair-context values produces the expected
  `relationships` rows; running twice is a no-op.

### PR 6 — Operations Assignments page + chrome restructure + drop `Assignment.context`

Absorbs the deferred 12C-1 PR 3 + PR 4 work
(Bulk Include toggle + ad-hoc-toggle drop) per the
2026-05-10 codebase-check revision — the toggle
lands on this page from the start instead of
relocating from a brief Setup-page intermediate.

- Move Assignments from the Setup row to the
  Operations row. Chrome nav after this PR:
  - Setup: Reviewers · Reviewees · Relationships ·
    Instruments · Email Template
  - Operations: Validate · Previews · Assignments
    · Invitations · Responses
- New Operations Assignments page surface:
  - Read-only preview of the current generated
    assignments table.
  - **Generate** button (replaces today's Setup-page
    Rule Based card's Generate).
  - **Bulk Include toggle for self-reviews**
    (absorbed from the deferred 12C-1 PR 3). Header
    row above the preview table — toggle + state
    pill + counts ("Self-reviews: ON (3 active, 0
    deactivated)"). POSTs to
    `/assignments/self-reviews/active`; single
    transaction writes
    `sessions.self_reviews_active` + updates every
    self-review row's `include` to match. New
    `assignments.self_reviews_active_set` event in
    `EVENT_SCHEMAS` with `counts.flipped` + the
    resulting boolean.
  - Per-instrument breakdown with zero-assignment
    warnings.
  - Per-row Include checkbox stays as last-mile
    override.
- **Drop ad-hoc `exclude_self_review` form field
  from the (formerly Setup-page) Rule Based card**
  surface as it's reconstructed under the
  Operations page (absorbed from the deferred
  12C-1 PR 4).
- **Refresh validation copy** for the
  `assignments.self_reviews_present` row + any
  related banner copy to point at the new bulk
  toggle (absorbed from 12C-1 PR 4).
- **Drop the `Assignment.context` JSON column.**
  Destructive Alembic migration; depends on PR 5
  having shipped (backfill of `pair_context_*` to
  `relationships` complete). **The
  `assignment_context_*` keys retire alongside**
  per the 2026-05-10 codebase-check decision —
  they were operator-typed via the manual CSV only,
  and 15D's "manual upload retires from operator
  surfaces" leaves no operator workflow that
  produces them. The future "friendly labels for
  assignment_context" plan (noted in
  `app/db/models/session_field_label.py:53` as
  "deferred") is permanently retired by this drop.
  No backfill — the column drops empty post-PR 5.
- Status pills on every session-scoped page
  reflect the new chrome layout.
- **Open consideration:** the Operations Assignments
  page may make sense to combine with the Validate
  page surface (one "what-just-happened? next
  action?" Operations stop). Decide during PR
  scoping; no schema impact either way.
- Tests: chrome reorder integration tests; bulk
  toggle works post-relocation; drop migration
  round-trips on SQLite + Postgres; display fields
  + assignments preview template correctly drop
  references to `assignment_context_*` /
  `pair_context_*` (latter now read from
  `relationships`); assert no remaining production
  code path writes to `Assignment.context` after
  the drop.

### PR 7 — Quick Setup slot restructure

- Quick Setup card grows back to **4 slots**:
  - Slot 1: Reviewers (existing)
  - Slot 2: Reviewees (existing)
  - Slot 3: Relationships (NEW — uses PR 1's
    importer)
  - Slot 4: Settings (was slot 3 in 12C-2 PR 1's
    deferred state; here flipped to live alongside
    12A-3 PR 1's Settings importer)
- **Operator UI: drops the legacy slot-3 dropdown
  + manual upload from the Quick Setup card.** The
  underlying `parse_manual_csv` /
  `replace_assignments` route + handler stays as a
  **dev-only feature** — no operator UI surfaces
  it; tests + admin tooling can still hit the
  endpoint. Documented in code (route docstring +
  handler) as "dev-only — not exposed to
  operators". The Quick Setup template branch +
  view-shape adapter slot for slot 3 manual
  upload + dropdown are removed; the route's
  template form is retired.
- Drops the legacy `rule="full_matrix"` /
  `rule="rule_based"` payload variants in
  `_quick_setup.py` (those handler branches retire
  with the operator-facing Quick Setup slot 3
  retirement). The `session_rule_set_id` form-data
  field also retires.
- `quick_setup_submit_all` chain: reviewers →
  reviewees → relationships → settings. **No
  auto-Generate** (per the locked manual-Generate-
  after-Validate decision).
- Coordinates with 12A-3 PR 3 (Settings slot
  graduation).

### PR 8 — Super buttons (Validate + Generate, etc.)

- Multi-step shortcut actions on the Operations
  Assignments page (and possibly Session Home):
  - "Validate + Generate" — runs Validate; if no
    errors, runs Generate; surfaces a single
    success / failure banner.
  - "Validate + Generate + Activate" — same chain
    + Activate; for the operator who's confident
    in their setup.
- Underlying single-step actions (Validate,
  Generate, Activate) remain available so the
  operator can still pause / inspect between
  steps.
- UI sugar — no new audit events (each underlying
  step emits its own event), no new schema.
- May be split off as a follow-on UI polish PR if
  PR 6 + 7 leave too little room.

## Open questions

_None — all five settled 2026-05-10:_

- _**Page name** — Relationships (chrome); `pair_context`
  (schema)._
- _**Operations Assignments page** — kept and reframed as
  Operations row, with Generate + super buttons + bulk
  overrides._
- _**Generation triggering** — manual after Validate.
  Quick Setup does not auto-Generate; mutations don't
  auto-regenerate. Super buttons available for
  multi-step shortcuts._
- _**`Assignment.context` JSON column** — drop entirely
  (no remaining tenants once `pair_context_*` lifts to
  the new table; `instrument_id` is already its own
  column)._
- _**Quick Setup integration** — Relationships joins as
  slot 3, parallel to Reviewers + Reviewees. Optional
  (cycle works without it)._
- _**Lifecycle gating on Relationships** — match
  rosters (editable in `draft` / `validated`)._

## Related context

- 12A-1 PR 4a (#725) — `is_self_review` predicate
  (renamed from `_is_self_review`).
  `app/services/assignments.py:401-405`. Stays as a
  derived predicate, not migrated to Relationships.
- 12C — manual assignments removed from Quick Setup
  (Sub-segment 12C-2); bulk Include toggle on
  Assignments page (Sub-segment 12C-1, soon to move to
  the Operations Assignments page if it persists);
  chrome reorder Instruments before Assignments
  (Sub-segment 12C-3).
- 13C — Enhanced Instruments (group-scoped instruments,
  per `instruments.group_kind`). Need a revised 13C
  that maximally prepares for 15D without removing the
  current Assignments page; that's the second
  follow-on doc.
- 15A — Friendly labels on the `pair_context.N`
  source. Today the editor surface is inert
  (`session_field_labels` table scaffolded but no
  resolver); 15A's editor needs a small extension to
  surface PairContextTag1/2/3 alongside the reviewer
  and reviewee tags. Per-pair tag labels come naturally
  with the new Relationships page.
- 15B — Per-instrument RuleSet selection
  (`Instrument.rule_set_id`). 15D's generation chain
  reads from per-instrument RuleSets; 15B is a hard
  prerequisite.
- 15C — Operator-library RuleSets. Independent of 15D
  but RuleSets that consume `pair_context.tag_N`
  matchers can travel via the operator library too;
  worth confirming on PR scoping.
- Existing pair-context schema:
  - `Assignment.context: JSON` —
    `app/db/models/assignment.py:45`, holds
    `pair_context_1/2/3` keys today.
  - Display-field source enum supports
    `("pair_context", "1"|"2"|"3")` —
    `app/services/instruments/_display_fields.py:48-65`.
  - CSV column shape `PairContext1/2/3` is recognised
    by today's manual assignment importer —
    `app/services/assignments.py:346-348`.
