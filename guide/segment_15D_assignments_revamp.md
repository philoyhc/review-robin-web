# Segment 15D — Assignments revamp: Pair Context as Setup primary, Assignments goes derived

**Status:** Planning. Initial sketch 2026-05-10. Builds on
12C's lock that manual assignments retire from Quick Setup;
takes the next step and retires the manual assignments
*table input* entirely.

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

### Naming

Working title **"Relationships"**. Alternatives, with
trade-offs:

| Name | Pros | Cons |
|---|---|---|
| **Relationships** *(default)* | Reads naturally; matches the conceptual content (mentorship / COI / history). | Slightly broader than what's actually stored — could imply more semantics than 3 string tags + status. |
| **Pairs** | Terse; matches the row-per-pair shape. | Generic; doesn't hint at what the pair attributes are. |
| **Pair Notes** | Clear that this is annotation-style data. | "Notes" understates the rule-driving role. |
| **Pair Context** | Matches existing schema vocabulary (`pair_context_1/2/3` already used in `Assignment.context` JSON, the display-fields seed catalogue, and the Rule Builder source enumeration). | Awkward as a page title; jargony. |

Recommendation: **Relationships** for the page title;
**`pair_context`** stays as the schema-level
identifier (matches the existing `source_type` enum used
by display fields and — once 15D ships — by Rule Builder
matchers / filters). Two-name strategy: friendly name in
the chrome, machine-name in the data layer. Same pattern
as `email_or_identifier` (machine) vs "Reviewee email"
(UI).

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
column also retires its `pair_context_*` keys; the
canonical pair context lives on the `relationships`
table, joined at generation time.

Generation runs:

- On Quick Setup completion (when the Settings CSV
  carries per-instrument `rule_set_name` references —
  12A-2 PR 1's chain step).
- On the operator's explicit **Generate** click on the
  Operations Assignments page (replaces today's Rule
  Based card on the Setup Assignments page).
- On any mutation that affects the candidate set —
  roster change, Relationships change, Instrument
  RuleSet swap — surfaces a "ready to regenerate" cue.
  (Maybe — TBD; might keep Generate fully manual.)

## Optional Assignments preview page (Operations)

Whether a separate Assignments page remains depends on
the operator's preview / override needs. **Likely yes**,
but reframed as an **Operations** surface:

- Read-only preview of the current generated
  assignments table (what the engine produced from the
  4-input chain).
- Bulk overrides:
  - **Exclude self-reviews** toggle (the 12C-1 PR 3
    bulk control, with its `sessions.self_reviews_active`
    column).
  - Possibly: per-row Include checkbox stays as
    last-mile override (12C-1 model preserved).
- **Generate** button (replaces the Setup-page Rule
  Based card's Generate).
- Per-instrument breakdown — N assignments per
  instrument; surface zero-row instruments as warnings.

This page lives on the **Operations** chrome row
alongside Validate / Previews / Invitations / Responses
— it's lifecycle-time information, not setup-time
authoring.

## Workflow consequences

**Pre-15D operator setup flow:**
1. Build rosters (Reviewers + Reviewees pages or Quick Setup).
2. Define instruments + per-instrument RuleSets.
3. Generate assignments via the Setup Assignments page's
   Rule Based card (or manually upload — discouraged).
4. Validate, Activate, etc.

**Post-15D operator setup flow:**
1. Build rosters (Reviewers + Reviewees pages or Quick
   Setup).
2. **Build relationships** (new Relationships page or
   Quick Setup) — encode per-pair constraints
   (mentorship, COI, prior cohort, etc.) as
   PairContextTag1-3.
3. Define instruments + per-instrument RuleSets that
   consume the new `pair_context.tag_N` source class
   for generation logic.
4. Validate, Activate. Generation runs as part of the
   chain or via the Operations Assignments page's
   Generate button.

The shift: per-pair info goes from "implicit in the
manual assignments CSV" → "explicit in a parallel
Relationships table". Operators name their constraints
in plain language; rules act on them.

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
2. **Schema.** Drop the `pair_context_*` keys from
   `Assignment.context` JSON in a follow-on cleanup PR
   once the backfill is observed clean. The JSON column
   itself stays — other context keys (TBD) may use it.
3. **Generation behaviour.** Sessions without
   relationships rows (greenfield, or sessions whose
   rosters never had pair context) generate the same as
   before; the new source class just doesn't fire on
   any rule.
4. **No operator-visible breakage** for sessions that
   didn't use pair context. Sessions that did get the
   migration silently — operators see the same
   assignments after Generate.

## Schema implications (high-level)

> Detailed in the follow-on "schemas-needed-beforehand"
> doc per the planning conversation. Sketch only here:

- **New table `pair_contexts`** (or `relationships`):
  `(session_id, reviewer_id, reviewee_id, tag_1, tag_2,
  tag_3, status, created_at, updated_at)` with unique
  constraint on `(session_id, reviewer_id, reviewee_id)`.
- **`Assignment.context.pair_context_*` retires**
  (lifted to the new table). The JSON column itself
  stays as a generic per-row context bag.
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

- **Page name.** Recommend Relationships; alternatives
  Pairs / Pair Notes / Pair Context. Settle on PR scoping.
- **Keep or retire the Operations Assignments preview
  page entirely.** A pure-derived assignments table has
  no operator-typed input, so the page is just a
  read-only confirmation surface. Worth keeping for the
  exclude-self-reviews bulk toggle + Generate trigger,
  but the operator could equally trigger Generate from
  Session Home and skip the preview. Settle when 15D's
  PR sequence is sized.
- **Generation triggering.** Today the operator clicks
  Generate explicitly. Post-15D — should the system
  auto-regenerate on relevant mutations (roster /
  Relationships / RuleSet change), or stay manual?
  Auto-regenerate is cleaner conceptually; manual is
  safer (operator confirms before assignments shift).
  Likely manual with a "ready to regenerate" cue.
- **What other context keys (besides `pair_context_*`)
  should the `Assignment.context` JSON column hold
  going forward**, if any? If none, drop the column
  entirely instead of just clearing the keys.
- **Quick Setup integration.** Add a new Relationships
  slot to the Quick Setup card (slot 3 in the new
  numbering: Reviewers / Reviewees / Relationships /
  Settings = 4 slots again)? Or leave Relationships
  off Quick Setup and require it via the dedicated
  page? Probably yes — symmetry with Reviewers /
  Reviewees argues for inclusion. Slot order: 1
  Reviewers, 2 Reviewees, 3 Relationships, 4 Settings.
- **Lifecycle gating on Relationships changes.** Same
  as rosters (editable in `draft` / `validated`)? Or
  more permissive (editable in `ready` so operators
  can patch a discovered COI mid-cycle)? Probably
  match rosters for simplicity; mid-cycle pair-context
  edits without a Generate re-run are not honoured by
  the existing assignments anyway.

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
