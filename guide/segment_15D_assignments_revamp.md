# Segment 15D — Assignments revamp: Pair Context as Setup primary, Assignments goes derived

**Status:** Planning. Initial sketch 2026-05-10. **All open
questions settled 2026-05-10** — page name, generation
triggering, JSON-column fate, Quick Setup integration, and
lifecycle gating all locked. Ready to size into PRs once
the two follow-on docs land. Builds on 12C's lock that
manual assignments retire from Quick Setup; takes the next
step and retires the manual assignments *table input*
entirely.

> **Two follow-on docs to write next** (per the planning
> conversation): (a) the schemas this segment needs
> beforehand, distilled out of this plan; (b) a revised 13C
> that maximally prepares for 15D without removing the
> current Assignments page.

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
