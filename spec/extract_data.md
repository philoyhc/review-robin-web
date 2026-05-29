# Extract data page — functional spec

The Operations-row workbench for **shaping the session's response
data for offline analysis**. Operators come here once responses
have started arriving, pick the lens that matches their analysis
question, configure chip-driven options, and download a CSV (or
a zip of CSVs).

The page is deliberately **not** an in-app analysis tool: no
charts, no pivots, no dashboards. Its job is to cut the response
data along the dimension the operator asks for so the actual
analysis can happen in Excel / pandas / a notebook with the
shape the operator already wants.

The page complements the Session Home **Extract setup** card
(which exports the round-trippable Reviewers / Reviewees /
Relationships / Settings CSVs for porting / cloning a session).
Setup data lives on Home; response data lives here. The split is
the load-bearing decision behind the page's existence — see
`guide/extract_data.md` for the rationale.

> **Implementation status — shipped through the four per-card
> wirings (2026-05-29).** Page chrome + skeleton landed in the
> Extract-data tab carve. The intro `Extract all data` card,
> the `By instrument` card, and the two metadata cards (Reviewer
> response metadata + Reviewee response metadata) are wired
> end-to-end: chips drive query-string params on a real download
> route, chip state persists per session via `localStorage`,
> and every download emits an audit event. The full-width
> **Data shaper** card below the grid ships its full
> **placeholder UI** — two stacked chip rows (scope ⇒ axis +
> instrument + response field; content ⇒ per-axis pool of
> identification + aggregate chips with all the field-scoped
> behaviour: Name ↔ Email coupling, data-type filtering,
> `List items` fan-out chip for List fields, `Discrete steps`
> fan-out chip for low-cardinality numeric fields), the stack
> of Data shape sub-cards (each with preview row + four
> ✓ / ✎ / X / + action icons on the same row as a
> right-anchored `Download` button, always-present blank
> starter card), and the disabled outer `Zip all` button.
> All interactions are client-side only; persistence and
> file generation are deferred — see "Data shaper card" +
> "Data shaper — row-key contract" below.

## Page identity

| Field | Value |
|---|---|
| Page name | Extract data (operator-facing label in chrome) |
| Template | `operator/session_extract_data.html` |
| URL | `/operator/sessions/{id}/extract-data` |
| Route | `app/web/routes_operator/_extract_data.py::session_extract_data` |
| Grouping | Operations |

## Chrome and navigation

The Operations row carries the tab at the right-hand end:

```
Operations  [Assignments][Validate][Previews][Invitations][Responses][Extract data]
```

End-of-strip placement is deliberate — the page is an
**end-of-flow** surface. Operators reach for it once response
data has started arriving, after monitoring (Invitations /
Responses) has done its job. See `spec/operations_pages.md`
"Page identity" for the strip-order rationale.

The page renders with the standard Operations-page chrome:
two-row session chrome, breadcrumbs via
`operator_session_child("Extract data")`, and the **Workflow
card** at the top per `spec/workflow_card.md`. Same lifecycle
behaviour as the other Operations pages — read-mostly, no
edit-lock card, available in every lifecycle state. The page
itself never wraps behind a yellow lock card; downloads stay
useful even after the session closes.

## Page layout

Three regions, top to bottom:

1. **Workflow card** — standard Operations-page chrome.
2. **Two-column grid of half-width cards**, in the
   `.extract-data-grid` layout (`align-items: end` so
   neighbouring cards bottom-align across columns):
   - **Left column (response data lenses)** — `Extract all
     data` intro card on top, `By instrument` card below.
   - **Right column (metadata lenses)** — `Reviewer response
     metadata` card on top, `Reviewee response metadata` card
     below.

   The grid collapses to a single column on narrow viewports.
3. **Full-width `Data shaper` card** below the grid (see
   the dedicated "Data shaper card" section below for the
   chip vocabulary + the row-key contract).

Each card on the grid shares a uniform body shape:

- `h2` heading (`Extract all data` / `By instrument` /
  `Reviewer response metadata` / `Reviewee response metadata`).
- One-line `.form-help` body copy explaining the lens's
  shape and the analysis question it answers.
- A single chip row (`.col-chip-row`) configuring the lens.
- An action row (`.extract-data-card-actions`) carrying a
  single `Zip all` secondary button that issues the
  download.

Chip state on every card persists via `localStorage`, keyed
to the session id (`rrw-extract-data-chips-{session_id}`).
Reload preserves the operator's selection.

## Chip vocabulary

Every chip uses the canonical `pill pill-count tag-chip`
selectable-chip primitive (`spec/ui_elements.md` §10), with
`is-selected` + `aria-pressed` driving the visual state.
Three families of chip live on the page:

- **Family / scope toggles** (intro card) — pick which
  lenses participate in the top-level `Zip all`.
- **Instrument chips** (by-instrument + the two metadata
  cards) — one per session instrument, labelled
  `#{N}: {short_label}` where `{N}` is the instrument's
  1-based session position (stable as chips toggle) and
  `{short_label}` falls back to `Instrument_{N}` when the
  operator left it blank. `#{N}` is always carried — even
  on single-instrument sessions — so the positional ordering
  reads consistently across cards.
- **Cross-cutting toggles** (by-instrument card +
  metadata cards) — `Include metadata` / `All assignment
  rows` on the by-instrument card; `All reviewers` /
  `All reviewees` on the metadata cards.

Chip ↔ button wiring is uniform across the four wired cards:
the chip set composes the query string for the card's
`Zip all` button, and a small inline-JS sync function updates
the button's `href` on every chip toggle. The by-instrument
card additionally **disables** its button (sets
`aria-disabled="true"` + `href="#"`) when the per-instrument
chip set goes empty (an empty zip is not useful). The
metadata cards do **not** disable — zero-instrument selection
ships a valid CSV carrying only the cross-instrument totals
(see "Reviewer / Reviewee response metadata cards" below).

## `Extract all data` card (intro)

Top-left card. The page's "I trust the default, give me
everything" affordance, sitting alongside the per-card
configurable surfaces below.

| Field | Value |
|---|---|
| Heading | `Extract all data` |
| Body copy | "Configure what you need on the lens cards and download the specific files. Use **Zip all** to download all response files (as configured using the other cards) at once." |
| Button id | `extract-data-zip-all` |
| Button target | `/operator/sessions/{id}/export/responses_bundle.zip` |

**Chip row (all default-selected):**

| Chip slot | Label | Role |
|---|---|---|
| `by-instruments` | `By instruments` | Scope: include the by-instrument CSVs |
| `reviewer-metadata` | `Reviewer response metadata` | Scope: include the reviewer metadata CSV |
| `reviewee-metadata` | `Reviewee response metadata` | Scope: include the reviewee metadata CSV |
| `data-shaper` | `Data shaper` | Scope: include the (forthcoming) Data shaper outputs |

The chip set is the future scope-filter for the top-level
`Zip all` zip. Today the button always ships the full
`responses_bundle.zip` (unified Responses CSV +
reviewer/reviewee stats + per-instrument long-format files);
chip-driven filtering of that bundle is a follow-up. The
chips persist via the shared `localStorage` plumbing so the
operator's intent survives reload even before the wiring
lands.

## `By instrument` card

Below the intro on the left. Cross-reviewer comparison on a
single rubric — "how did everyone score on this instrument?"

| Field | Value |
|---|---|
| Heading | `By instrument` |
| Body copy | "One CSV per instrument; rows = (reviewer × reviewee) pairs; columns = response fields side-by-side. Optimised for cross-reviewer comparison on a single rubric." |
| Button id | `extract-data-by-instrument-zip` |
| Button target | `/operator/sessions/{id}/export/by_instrument_bundle.zip` |
| Bundle filename | `{code}_by_instrument.zip` |
| Member filenames | `{code}_by_instrument_{slug}.csv` (one per instrument) |

**Chip row.** Per-instrument chips followed by the two
cross-cutting toggles:

| Chip slot | Label | Role |
|---|---|---|
| `instrument-{id}` | `#{N}: {short_label}` | Membership filter — only selected instruments ship as zip members. |
| `include-metadata` | `Include metadata` | When **off**, drops the meta-header block + blank separator row from every CSV. |
| `all-assignment-rows` | `All assignment rows` | When **off**, drops assignment rows whose response-field cells are all empty. |

All default-selected.

**Query-string wiring** (composed by the chip-sync JS,
consumed by `export_by_instrument_bundle_zip`):

- `?instrument=<id>` (repeated) — only the listed instrument
  ids ship; omitted = every instrument on the session.
  `counts.instrument_files` on the audit event reports the
  **delivered** count post-filter, stable as chips toggle.
- `?meta=0` — set when `Include metadata` is off.
- `?all_rows=0` — set when `All assignment rows` is off.

**Button-disable behaviour.** Zero instruments selected
greys the `Zip all` button (`aria-disabled="true"` +
`href="#"`); an empty zip is never a useful download.

**Member CSV shape** (per
`app/services/extracts/by_instrument_extract.py`):

1. **Meta header** — instrument identity (Instrument /
   Description / Data Type rows), per-response-field
   metadata sub-block (Response field / Data Type / Min /
   Max / Step / List / Helptext), assignment count, pool /
   unit-of-review / self-review configuration. Pool rule
   rows render fields as `{source_type}.{friendly_label}`
   so the row disambiguates which side of the assignment
   owns the slot. Skipped entirely when `meta=0`.
2. **Blank separator row.** Skipped with the meta block.
3. **Wide data-table header** — `ReviewerName`,
   `ReviewerEmail`, three reviewer tag columns,
   `RevieweeName`, `RevieweeEmail`, three reviewee tag
   columns, one column per response field (label or
   field key), `SelfReview`, `SavedAt`, `SubmittedAt`.
4. **Data rows** — one row per (reviewer, reviewee /
   group) pair, sorted by composed reviewee name then
   reviewer. Group-scoped instruments collapse to one row
   per (reviewer × group × field), same as the unified
   Responses CSV. Rows with no non-empty response cells
   drop out when `all_rows=0`.

**Audit event.**
`session.by_instrument_bundle_extracted` with
`counts.instrument_files = N` (the post-filter delivered
count).

## `Reviewer` / `Reviewee response metadata` cards

Right column. **Activity rollups, not response data.** A
single CSV per card, one row per reviewer (or reviewee),
with cross-instrument totals plus optional per-field
aggregates broken out by instrument. The intended analysis
question is "how much did each reviewer produce, and what
did the numbers / strings look like in aggregate?" —
auditing and coaching on the reviewer side, feedback-packet
shaping on the reviewee side.

The two cards are functionally symmetric — only the entity
name and the toggle slot change. The shipped column shape
moved the old per-statistic chips (`Count` / `Mean` /
`Median` / `Min` / `Max` / `Length`) **into the column
shape** of the CSV itself, where they apply by data type.

| Field | Reviewer card | Reviewee card |
|---|---|---|
| Heading | `Reviewer response metadata` | `Reviewee response metadata` |
| Card id | `extract-data-by-reviewer` | `extract-data-by-reviewee` |
| Body copy | "Per-reviewer metadata about the responses each reviewer produced — how many, when saved / submitted, against which instruments. Optimised for reviewer audit and coaching." | "Per-reviewee metadata about the responses produced about each reviewee — how many, when saved / submitted, against which instruments. Optimised for the feedback packet handed to the reviewed person." |
| Button id | `extract-data-reviewer-metadata-zip` | `extract-data-reviewee-metadata-zip` |
| Button target | `/operator/sessions/{id}/export/reviewer_metadata.csv` | `/operator/sessions/{id}/export/reviewee_metadata.csv` |
| Filename | `{code}_reviewer_metadata.csv` | `{code}_reviewee_metadata.csv` |
| Audit event | `session.reviewer_metadata_extracted` | `session.reviewee_metadata_extracted` |

The button label reads `Download` (not `Zip all`) on both
metadata cards because each card produces a single CSV — no
zipping happens. The by-instrument card keeps `Zip all`
because it really does zip N CSVs together.

**Chip row.** Per-instrument chips inline before the entity-
scope toggle:

| Chip slot | Label | Role |
|---|---|---|
| `instrument-{id}` | `#{N}: {short_label}` | Selects which instruments contribute per-(instrument, field) column blocks; also scopes the cross-instrument totals when at least one is selected. |
| `all-reviewers` / `all-reviewees` | `All reviewers` / `All reviewees` | When **off**, drops body rows for entities with zero non-empty responses in scope. |

All default-selected.

**Query-string wiring** (consumed by
`export_reviewer_metadata_csv` /
`export_reviewee_metadata_csv`):

- `?instrument=<id>` (repeated) — adds a per-(instrument,
  field) column block for each listed instrument. Omitted
  means *no* per-field blocks (cross-instrument totals
  scan **every** session instrument so they stay
  meaningful).
- `?all=0` — set when `All reviewers` / `All reviewees`
  is off.

**No disable on zero instruments.** Unlike the
by-instrument card, zero-instrument selection is a valid
export: the CSV ships with just the four cross-instrument
header columns. The button stays enabled.

### CSV column shape

The Reviewer side is the canonical structure; the Reviewee
side swaps `ReviewerName` / `ReviewerEmail` for
`RevieweeName` / `RevieweeEmail` and the `all_reviewers` /
`all_reviewees` slot — otherwise identical.

**Always columns:**

| Column | Meaning |
|---|---|
| `ReviewerName` / `RevieweeName` | Roster name. |
| `ReviewerEmail` / `RevieweeEmail` | Roster email / identifier. |
| `Assigned` | Number of response cells the entity is supposed to fill in (or have filled in about them), scoped to the in-scope instruments. Counts at the (entity × field) cell level — see "Group-scoped semantics" below for the asymmetric dedupe rule. |
| `Count` | Number of those cells with a non-empty response. |

**Per (instrument, field) column block** (one block per
selected instrument, for every response field on that
instrument). Column prefix:
`#{N}: {short_label}.{field_label}` (mirroring the
by-instrument card's chip label convention, with the same
`Instrument_{N}` fallback). Footprint depends on the field's
data type:

| Field data type | Block columns |
|---|---|
| Numeric (Integer / Decimal) | `.Assigned`, `.Count`, `.Mean`, `.Median`, `.Min`, `.Max` |
| String | `.Assigned`, `.Count`, `.Length` (sum of chars across non-empty responses) |
| Anything else (e.g. List) | `.Assigned`, `.Count` |

### Row scoping

| Scenario | Rows shipped |
|---|---|
| No instruments selected | Every roster entry — base columns only. Totals scan every session instrument so the operator still gets a meaningful overview. |
| One or more instruments selected, `All {entity}` ON | Every roster entry. Totals scoped to the selected instruments; per-(instrument, field) blocks ship for those. |
| One or more instruments selected, `All {entity}` OFF | Only entries with at least one non-empty response on any field of the selected instruments. |

Sort order: active rows first, then by name / email — same
as the Reviewers / Reviewees CSVs.

### Group-scoped semantics

Group-scoped instruments fan responses across every member
assignment at save time (the save layer copies the answer
onto every (reviewer × member) assignment row). The two
sides handle that asymmetry differently:

- **Reviewer side.** A reviewer fills one form per group,
  not one per member. `Assigned` dedupes by
  `(reviewer, instrument, group_key)` — one count per
  group, not per member-assignment. `Count` and per-field
  rollups dedupe by `(reviewer, group_key, field_id)` —
  each group answer counts once, no matter how many
  members received the fan-out.
- **Reviewee side.** From a reviewee's perspective there
  is exactly one cell per (reviewer, field) about them,
  so each member-assignment correctly counts on its own.
  No dedupe.

The asymmetry keeps both columns intuitive: a reviewer who
reviews 3 groups of 2 members each on a 2-field instrument
sees `Assigned = 6` (3 × 2), and an individual member of
one of those groups, reviewed by 3 reviewers, sees the
same `Assigned = 6` (3 × 2) on the reviewee side.

This matches the dedupe contract `entity_stats_extract.py`
already enforces for the analogous draft/submitted activity
rollup that ships inside the top-level responses bundle.

### Audit envelope

Both routes emit a `_IDENTITY | {"counts"}` event with the
same payload shape:

```json
{
  "counts": {
    "rows": <body row count, header excluded>,
    "instruments": <chip selection size, 0 when none selected>
  }
}
```

## `Data shaper` card

Full-width, below the two-column grid. The page's
**generalised builder** for custom CSV shapes —
"compose the cut you want by toggling chips, see the
column header live in a preview row, save it under a
name, repeat." The card sits last because it requires
the most operator attention; the canned lens cards
above it cover the common cases without configuration.

| Field | Value |
|---|---|
| Heading | `Data shaper` |
| Body copy | "Compose a custom data shape — pick the axes (reviewer / reviewee / instrument / response field), the grouping, and the aggregations — and export the result alongside the canned lens CSVs." |
| Card id | `extract-data-shaper` |
| Button id | `extract-data-shaper-zip` |
| Button target | `#` (placeholder — `aria-disabled`) |

**Implementation status.** Placeholder UI shipped end-to-
end through PRs landing 2026-05-29 (#1589 → #1603). The
chip-driven UX described below is real and survives reload;
the **file generation** that turns a saved shape into a CSV
in the top-level `Zip all` bundle is the next wiring slice
(out of scope for this spec — see "Out of scope" at the
end of this section).

### Two stacked chip rows

The card opens with **two `<p class="col-chip-row">` rows**
stacked vertically. The first row answers "what subset of
data are we looking at?", the second answers "what columns
go in the CSV?". Splitting them keeps the row scannable as
the operator narrows the scope and picks columns.

#### Scope row (top)

Three mutex chip groups separated by vertical pipes (`|`):

1. **Axis chip** — `Reviewer` and `Reviewee`, **mutually
   exclusive**. Clicking the off chip deselects whichever
   sibling axis was on. Rationale: the full
   `reviewer × reviewee` matrix is already downloadable via
   the By-instrument card; a row keyed by both leaves
   little to aggregate. (The `data-shaper-axis-chip="..."`
   attribute drives mount / unmount of the per-axis pool on
   the content row below.)
2. **Instrument scope chip** — one per session instrument,
   labelled `#{N}: {short_label}` exactly like the
   By-instrument card. **Mutually exclusive** — one
   instrument at a time. Selecting an instrument also
   reveals its **response-field scope chips** in the next
   group; deselecting it hides them. With no instrument
   selected the (eventual) aggregate columns span every
   session instrument, matching the legacy "By reviewer" /
   "By reviewee" framings.
3. **Response-field scope chip** — one per response field
   on the selected instrument, **mutually exclusive**, chip
   text = the field's friendly label
   (`field.label` falling back to `field.field_key`).
   Each field chip carries the field's data type as
   `data-shaper-field-data-type` so the content row's
   field-scoped chips can filter appropriately; List fields
   additionally carry `data-shaper-field-list-options` (CSV
   of option labels), and numeric fields with a finite,
   small (≤12) discrete-value set additionally carry
   `data-shaper-field-discrete-steps` (CSV of step values
   pre-computed server-side by
   `_discrete_steps_values(field)` in the route).

   The group's leading `|` and the chips themselves render
   only when an instrument is selected — no orphan pipe
   when no field chips would follow.

The unifying rationale: the Data shaper is for **fine-
grained shape composition**, and fine-grained analysis
benefits from one-at-a-time focus. Cross-instrument and
cross-axis summaries already live elsewhere (the canned
lens cards and the metadata cards); the Data shaper covers
the focused cuts those don't.

#### Content row (one row below)

The per-axis chip pool mounts dynamically into a
`<span data-shaper-relevant-chips>` slot when the operator
toggles `Reviewer` or `Reviewee` on. The pool has two
sub-groups separated by `|`:

##### Identification chips (left of the pipe)

| Chip | Slot | Semantics |
|---|---|---|
| `{Reviewer\|Reviewee} Name` | `{axis}:name` | Per-individual name column. **Auto-couples with Email** — selecting Name auto-selects Email. |
| `{Reviewer\|Reviewee} Email` | `{axis}:email` | Per-individual email column. Can stand alone. Deselecting Email while Name is on cascades the deselect to Name. |
| `Tag 1` / `Tag 2` / `Tag 3` | `{axis}:tag-1` / `tag-2` / `tag-3` | Per-tag-slot columns. Labels render via `field_labels.resolve(session, "{axis}", "tag_N")` so operator renames on the Setup pages flow through; falls back to `Tag 1` / `Tag 2` / `Tag 3` when no override is set. |

**Name ↔ Email coupling rationale.** People share names, so
`Name` alone isn't a sound row key. The auto-select +
cascade-deselect rule keeps the operator in the valid
"Email-with-or-without-Name" or "Tags-only" or "nothing"
states — see "Row-key contract" below for what each state
means for the CSV.

##### Aggregate chips (right of the pipe)

| Chip | Slot | When it renders |
|---|---|---|
| `Assigned` | `{axis}:assigned` | Always (field-independent). |
| `Count` | `{axis}:count` | Always (field-independent). |
| `|` (intra-pool pipe after `Count`) | — (marker `data-shaper-relevant-for="field-scoped"`) | Shows iff the data type is numeric or string (the chips it introduces). Hides for List fields — the trailing `list-or-discrete` pipe (below) carries the single separator between `Count` and `List items` instead. Also hides when no response field is selected, so the row never carries an orphan `|`. |
| `Mean` / `Median` / `Min` / `Max` | `{axis}:mean` / `:median` / `:min` / `:max` | Numeric (Integer / Decimal) fields. Marked `data-shaper-relevant-for="numeric"`. |
| `Length` | `{axis}:length` | String fields. Marked `data-shaper-relevant-for="string"` — sums character count across non-empty responses. |
| `|` (trailing pipe) | — (marker `data-shaper-relevant-for="list-or-discrete"`) | Single pipe shared by the two fan-out chips below. Shows iff `List items` or `Discrete steps` will render. |
| `List items` | `{axis}:list-items` (marker `data-shaper-relevant-for="list-items"`) | List fields with a non-empty options CSV. Selecting the single `List items` chip emits **one preview-row column per list option** (the JS reads the active field chip's `data-shaper-field-list-options` CSV at render time). Same fan-out shape as `Discrete steps`. |
| `Discrete steps` | `{axis}:discrete-steps` (marker `data-shaper-relevant-for="discrete-steps"`) | Numeric fields with ≤12 discrete values (i.e. `min`, `max`, `step` defined and `(max - min) / step + 1 ≤ 12`). Selecting the single `Discrete steps` chip emits **one preview-row column per step value** (e.g. an Integer 1..5/step 1 yields columns `1` `2` `3` `4` `5`). Step values are read at render time from the active field chip's `data-shaper-field-discrete-steps` CSV. |

All field-scoped aggregates hide entirely until a response
field is selected (without one there's no value vector to
summarise). Selected chips that get hidden by a data-type
swap auto-deselect so the preview row stays consistent.

**Per-data-type chip-row layout** (what the operator
actually sees after picking a response field; `[ID] |`
prefix elided):

| Data type | Rendered row |
|---|---|
| Numeric, no discrete steps | `Assigned Count | Mean Median Min Max` |
| Numeric, ≤12 discrete steps | `Assigned Count | Mean Median Min Max | Discrete steps` |
| String | `Assigned Count | Length` |
| List (with options) | `Assigned Count | List items` |
| Other types | `Assigned Count` |

### Preview-table + Data shape sub-cards

Below the two chip rows, a `<div data-shaper-stack>` holds
a stack of **Data shape sub-cards**. One sub-card per
shape; the operator can add more via the `+` icon on any
existing card.

Each sub-card carries:

1. A **preview row** — a `<table class="shaper-preview-
   table">` whose `<thead><tr>` mirrors the currently-
   selected column chips on the active shape. Cells are
   `width: auto` so each header sizes to its label.
   Empty-state placeholder (muted italic) reads
   "Pick chips above to compose this shape's columns" —
   keeps the table visible so the operator sees something
   to interact with.
2. An **action row** with four squarish `btn secondary`
   icon buttons (matching the Instruments page Response
   Fields builder pattern — see `instruments_index.html`
   lines 3833-3843 for the source) followed by a
   right-anchored `Download` button:
   - `✓` (`data-shape-save`) — flips the card to saved
     mode (name input → plain text, `✓` → `✎`).
   - `✎` (`data-shape-edit`) — flips back to edit mode
     (the inverse of save).
   - `X` (`data-shape-delete`) — removes the sub-card from
     the stack. Never strips the page of its last sub-card:
     a delete on the final remaining card is a no-op,
     mirroring the Response Fields builder's always-present
     empty row.
   - `+` (`data-shape-add`) — clones a fresh blank sub-card
     immediately after this one and makes it the active
     target.
   - `Download` (`data-shape-download`) — sits on the same
     row as the icon group, pushed to the right edge via
     `margin-left: auto`. Placeholder until the file-gen
     wiring slice teaches it to extract this shape's CSV —
     currently renders with `href="#"` and
     `aria-disabled="true"`.

The **always-present blank sub-card** on initial load gives
the operator an immediate edit target without requiring a
preceding "Add a shape" click — matching the Band-3
Response Fields builder's always-present empty row.

### Row-key contract — for the file-gen wiring slice

The shipped chip-toggle behaviour is purely client-side;
the **row identity** that each selection implies for the
file-gen pipeline is pinned here as the contract that
pipeline must honour. Symmetric across axes — swap
`reviewer` ↔ `reviewee` throughout.

| Chip selection on the active shape | Row identity of the produced CSV |
|---|---|
| `Name` + `Email` selected (Name implies Email, so this is the same as "Name selected") | **One row per individual** — every reviewer / reviewee on the session gets its own row. |
| Only `Email` selected (no `Name`) | **One row per individual** — Email is the canonical unique identifier. The `Name` column simply isn't emitted. |
| Only some subset of tag chips selected — no `Name` / `Email` | **One row per distinct tag-combination** — the rows are aggregates of the individuals sharing the selected tag values. With three tag chips on, the row key is the (Tag 1, Tag 2, Tag 3) tuple; with one, it's that one tag's value. |
| Nothing selected (neither identification nor tag chips) | **A single summary row** across every reviewer / reviewee on the session — the aggregate columns are computed across the whole roster. |
| `Name` / `Email` **and** tag chips selected | `Name` / `Email` wins for row identity — **one row per individual**. The tag chips emit additional identification columns on each row but don't roll up. |

The instrument and response-field scope chips on the scope
row narrow what "in-scope responses" means for the
aggregate columns:

- No instrument chip selected → aggregates span every
  instrument on the session.
- An instrument chip selected → aggregates scope to that
  instrument's responses.
- A response field chip selected → aggregates narrow
  further to that single instrument-field cell.

Aggregate-chip data-type filtering follows the same rules
the Reviewer / Reviewee response metadata cards already
use: numeric fields surface `Mean` / `Median` / `Min` /
`Max` (+ `Discrete steps` when ≤12 entries); string fields
surface `Length`; list fields surface one option chip per
list value; other types just surface `Assigned` and
`Count`. Group-scoped instruments inherit the asymmetric
dedupe rule: reviewer side dedupes by `(reviewer,
instrument, group_key)`, reviewee side does not (each
member-assignment counts on its own).

### Cross-cutting behaviours specific to the Data shaper

- **Chip-state persistence.** Every chip on the page —
  including the Data shaper card's axis, instrument,
  response-field, identification, and aggregate chips —
  persists `aria-pressed` via the shared
  `rrw-extract-data-chips-{session_id}` `localStorage`
  store described in the page's "Cross-cutting
  behaviours" section below.
- **Dynamic chip pools.** Two slots host chips that
  mount / unmount on selection:
  `data-shaper-relevant-chips` (the per-axis content
  pool — mounted on axis toggle), and
  `data-shaper-field-chips` (the per-instrument
  response-field pool — mounted on instrument toggle).
  Each pool's mount is idempotent — re-applying the
  current selection state restores the pool to the
  correct contents. The two fan-out chips (`List items`
  / `Discrete steps`) live **statically** inside each
  per-axis pool template and are hidden / shown via the
  `data-shaper-relevant-for` filter rather than cloned
  in / out (the dynamic per-option List chips that
  shipped briefly in #1600 retired in #1608).
- **Lifecycle behaviour.** The card renders identically
  in every session lifecycle state. Once the file-gen
  pipeline wires the `Zip all` button, the same
  no-yellow-lock-card behaviour the rest of the page
  already has will apply.

### Out of scope (file-gen wiring slice)

The placeholder slice deliberately doesn't ship the
following — they're the explicit follow-up:

- **Per-session persistence of saved shapes.** No DB
  schema decision yet; `localStorage` covers chip state
  but not saved-shape names + column-chip selections.
- **The file-generation pipeline.** Turning a saved
  shape into a CSV in the top-level `Zip all` bundle is
  the bulk of the wiring work and depends on the
  persistence model.
- **Audit events.** `session.data_shaper_extracted` (or
  per-shape variants) will register against
  `EVENT_SCHEMAS` when the route lands.
- **Column-chip drag-to-reorder + sort-icon click**
  inside the preview row. The chips currently render
  in chip-selection order; reorder is a follow-up.

## Cross-cutting behaviours

**Chip-state persistence.** Every chip on the page persists
its `aria-pressed` state via `localStorage` keyed to the
session id (`rrw-extract-data-chips-{session_id}`). Reload
restores the operator's last selection across all four
cards. The store is per-session so cross-session contamination
doesn't happen.

**Live button-href sync.** A single inline-JS module wires
every chip on the page to two sync functions (one for the
by-instrument card, one shared across the two metadata
cards). On every toggle: the chip flips its visual state,
the new state is persisted, and the affected card's `Zip
all` button has its `href` rebuilt from the current chip
selection. Right-click "Copy link" therefore yields a URL
that reflects the live chip configuration — useful for
operators who want to script the download or paste it into
a runbook.

**Lifecycle behaviour.** The page renders identically in
every lifecycle state. Downloads stay available even after
the session closes — inspecting what was extracted is a
valid post-close use case. No yellow lock card wrap.

## Where to look (implementation pointers)

- `app/web/routes_operator/_extract_data.py` — page route.
- `app/web/routes_operator/_extracts.py` — all download
  routes (`reviewer_metadata.csv`, `reviewee_metadata.csv`,
  `by_instrument_bundle.zip`, plus the top-level
  `responses_bundle.zip` driven by the intro card).
- `app/web/templates/operator/session_extract_data.html` —
  template + inline chip-sync JS.
- `app/services/extracts/entity_metadata_extract.py` —
  Reviewer / Reviewee metadata extract builders.
- `app/services/extracts/by_instrument_extract.py` — wide
  per-instrument extract serialiser.
- `app/services/extracts/zip_bundle.py` —
  `build_by_instrument_bundle` zip wrapper consumed by
  `export_by_instrument_bundle_zip`.
- `_discrete_steps_values` in
  `app/web/routes_operator/_extract_data.py` — small
  helper computing the Data shaper's `Discrete steps`
  step vocabulary for qualifying numeric fields
  (≤12 distinct values).
- `tests/unit/test_extract_data_route_helpers.py` —
  unit tests for the discrete-steps helper covering the
  Integer / Decimal / threshold-boundary / non-numeric
  cases.
- `guide/extract_data.md` — landing plan, design rationale,
  open-question resolutions, and the Data shaper's
  pending file-gen + persistence wiring.
