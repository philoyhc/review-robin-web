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
`guide/archive/extract_data.md` for the rationale.

> **Implementation status — fully wired end-to-end (2026-05-30).**
> Page chrome + skeleton landed in the Extract-data tab carve.
> Every card on the page is wired: the intro `Extract all data`
> card, the `By instrument` card, the two metadata cards
> (Reviewer / Reviewee response metadata), and the full-width
> `Data shaper` card all drive real download routes. Chip state
> persists per session via `localStorage` for the canned-lens
> cards and **per-shape via the `data_shapes` table** for the
> Data shaper; every download emits an audit event.
>
> The Data shaper carries two stacked chip rows (scope ⇒ axis
> + empty-row drop + Self-review handling + instrument + response
> field; content ⇒ per-axis pool of identification + aggregate
> chips with field-scoped behaviour: Name ↔ Email coupling,
> data-type filtering, `List items` fan-out for List fields,
> `Discrete steps` fan-out for low-cardinality numeric fields),
> a stack of Data shape sub-cards (preview row + Save / Edit /
> Cancel / Delete / +Shape / Download action row), and the
> outer `Zip all` button.
>
> The Self-review handling chip slice (PRs #1642 → #1647 +
> #1659) and the chip-controlled-drop slice (PRs #1654 → #1659)
> closed out the wiring, including the cross-card consistency
> sweep that converted all four empty-row-drop chips to two-
> state cycling pills with explicit labels per state.

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
  metadata cards + Data shaper) — two-state cycling pills
  that flip between an "include everything" label and a
  "drop empty rows" label so the OFF state reads as a
  named intent rather than a not-pressed chip:

  | Card | "Include" label | "Drop empty" label |
  |---|---|---|
  | By instrument | `All assignment rows` | `Assignment rows with data` |
  | Reviewer response metadata | `All reviewers` | `Reviewers with responses` |
  | Reviewee response metadata | `All reviewees` | `Reviewees with responses` |
  | Data shaper | `All rows` | `Rows with data` |

  The by-instrument card also keeps an `Include metadata`
  toggle (single-label) that drops the meta-header block
  on each CSV. All toggles default to the "include" state.
- **Self-review handling chip** (metadata cards + Data
  shaper scope row) — single-pill three-state cycle
  (`Include self` → `Exclude self` → `Both` → …) shipped
  in the 2026-05-30 chip slice (PRs #1642 → #1647 — see
  `guide/archive/extract_data.md`). Drives the column-name
  suffix (`_self` / `_noself` / `_both`) on every
  aggregate column, the filename suffix on the download
  (`{code}_reviewer_metadata{_suffix}.csv` and friends),
  and the audit-event `context.self_review_handling`
  slot. The `exclude_self` state adds
  `Assignment.is_self_review.is_(False)` to the pool
  query against the canonical column from
  `guide/archive/self_review_consolidate.md`. On the
  metadata cards the chip state lives only in the query
  string (one-shot per download); on the Data shaper it
  persists per-shape on
  `data_shapes.self_review_handling` and round-trips
  through Settings CSV.

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
| `data-shaper` | `Data shaper` | Scope: include the Data shaper outputs — drives `?data_shapes=0` on the bundle URL when off. |
| `token-keys` | `Token keys` | Scope: include `participant_tokens.csv` in the bundle — drives `?tokens=0` when off. **Conditional**: chip + the matching Token keys card below only render when `session.observers_enabled` is on, since the tokens have no consumer without observers today. |

The chip set is the scope-filter for the top-level
`Zip all` zip. `data-shaper` + `token-keys` are wired
(drive `?data_shapes=0` / `?tokens=0` on the bundle URL);
`by-instruments` / `reviewer-metadata` / `reviewee-metadata`
remain placeholder for the eventual scope split — today the
bundle always carries those three regardless of chip state.
The chips persist via the shared `localStorage` plumbing so
the operator's intent survives reload.

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

| Chip slot | Labels (on / off) | Role |
|---|---|---|
| `instrument-{id}` | `#{N}: {short_label}` | Membership filter — only selected instruments ship as zip members. |
| `include-metadata` | `Include metadata` | When **off**, drops the meta-header block + blank separator row from every CSV. |
| `all-assignment-rows` | `All assignment rows` / `Assignment rows with data` | Two-state cycling pill — when **off**, drops assignment rows whose response-field cells are all empty. Both labels ride on `data-label-on` / `data-label-off`; the page JS swaps `textContent` on toggle (PR #1657, chip-controlled-drop consistency sweep). |

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

| Chip slot | Labels (on / off) | Role |
|---|---|---|
| `instrument-{id}` | `#{N}: {short_label}` | Selects which instruments contribute per-(instrument, field) column blocks; also scopes the cross-instrument totals when at least one is selected. |
| `all-reviewers` / `all-reviewees` | `All reviewers` / `Reviewers with responses` (or `All reviewees` / `Reviewees with responses`) | Two-state cycling pill — when **off**, drops body rows for entities with zero non-empty responses in scope. Both labels ride on `data-label-on` / `data-label-off`; the page JS swaps `textContent` on toggle (PR #1657, chip-controlled-drop consistency sweep). |

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
- `?self_review_handling=` — `include_self` (default) /
  `exclude_self` / `both`. Drives the Self-review handling
  chip's three-state filter + column-name suffix +
  filename suffix (`_self` / `_noself` / `_both`). Unknown
  values silently fall through to `include_self` so today's
  chip-less direct-URL workflows keep working.

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

Identity columns stay un-suffixed (they describe the row,
not the response pool). Aggregate columns — including
`Assigned` and `Count` — carry the Self-review handling chip
suffix on every single-state extract, and emit twice on
`both` (once each for `_self` and `_noself`):

| Column | Meaning |
|---|---|
| `ReviewerName` / `RevieweeName` | Roster name. |
| `ReviewerEmail` / `RevieweeEmail` | Roster email / identifier. |
| `Assigned{_self\|_noself}` | Number of response cells the entity is supposed to fill in (or have filled in about them), scoped to the in-scope instruments **AND** the chip's self-review filter. Counts at the (entity × field) cell level — see "Group-scoped semantics" below for the asymmetric dedupe rule. |
| `Count{_self\|_noself}` | Number of those cells with a non-empty response. |

On `?self_review_handling=both` the two aggregate columns
above expand to four (`Assigned_self`, `Count_self`,
`Assigned_noself`, `Count_noself`), and each per-(instrument,
field) block emits twice in the same `_self` → `_noself`
order.

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

Both routes emit a `_IDENTITY | {"counts", "context"}` event
with the same payload shape:

```json
{
  "counts": {
    "rows": <body row count, header excluded>,
    "instruments": <chip selection size, 0 when none selected>
  },
  "context": {
    "self_review_handling": "include_self" | "exclude_self" | "both"
  }
}
```

The `context.self_review_handling` slot records the operator's
Self-review handling chip state on this download (PR #1642).
Unknown query-param values fall through to `include_self`
server-side, so the audit value always reflects what the file
actually contained.

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

**Implementation status.** Fully shipped as of 2026-05-30
(placeholder chip UI: PRs #1589 → #1603; persistence +
file-gen wiring: PRs #1626 → #1659). The chip-driven UX,
shape persistence (`data_shapes` table), and per-shape
`Download` button (backed by
`…/shapes/{id}/download.csv`) are all live. The outer
`Zip all` button on this card still renders
`aria-disabled="true"` (bundle integration is the
remaining follow-up — see "Out of scope" below).

### Two stacked chip rows

The card opens with **two `<p class="col-chip-row">` rows**
stacked vertically. The first row answers "what subset of
data are we looking at?", the second answers "what columns
go in the CSV?". Splitting them keeps the row scannable as
the operator narrows the scope and picks columns.

#### Scope row (top)

Three mutex chip groups + the empty-row drop chip + the
Self-review handling chip, separated by vertical pipes (`|`):

1. **Axis chip** — `Reviewer` and `Reviewee`, **mutually
   exclusive**. Clicking the off chip deselects whichever
   sibling axis was on. Rationale: the full
   `reviewer × reviewee` matrix is already downloadable via
   the By-instrument card; a row keyed by both leaves
   little to aggregate. (The `data-shaper-axis-chip="..."`
   attribute drives mount / unmount of the per-axis pool on
   the content row below.)
2. **Empty-row drop chip** — inline after the axis chips,
   **before** the Self-review handling chip. Two-state
   cycling pill (`All rows` ↔ `Rows with data`) shipped
   2026-05-30 (PR #1654, chip-controlled-drop slice).
   Persists per-shape on the
   `data_shapes.include_empty_rows` boolean column (see
   `spec/settings_inventory.md` §9.5). When `Rows with data`
   is selected, drops body rows whose `_Acc.is_empty()` on
   per-individual / per-tag-combo shapes; single-summary
   shapes always emit their one row regardless. For
   `self_review_handling="both"` the row drops only when
   **both** `_self` and `_noself` halves are empty. Carries
   `data-shaper-include-empty-rows-chip="data-shaper"` so
   the chips-lock-when-no-edit-mode CSS picks it up
   alongside the other scope-row chips.

   **Decision matrix.** With `self_review_handling`
   orthogonal — it just decides which assignments /
   responses feed `_Acc`:

   | Row scheme \ chip | `All rows` (default) | `Rows with data` |
   |---|---|---|
   | per_individual | no drop | drop if `_Acc.is_empty()` |
   | per_tag_combo | no drop | drop if `_Acc.is_empty()` |
   | single-summary | no drop | no drop (always one row, even if empty) |

3. **Self-review handling chip** — inline after the empty-
   row drop chip, before the first `|`. Three-state cycle
   (`Include self` → `Exclude self` → `Both` → …) shipped
   2026-05-30 (PR #1644). Persists per-shape on the
   `data_shapes.self_review_handling` column (see
   `spec/settings_inventory.md` §9.5). Drives the
   column-name suffix (`_self` / `_noself` / `_both`) on
   every aggregate column in the extract, the filename
   suffix on the download, and the audit-event
   `context.self_review_handling` slot. Carries
   `data-shaper-self-review-chip="data-shaper"` so the
   chips-lock-when-no-edit-mode CSS rule on
   `[data-shaper-chips-locked="true"]` greys it out
   alongside the rest of the scope-row chips.
4. **Instrument scope chip** — one per session instrument,
   labelled `#{N}: {short_label}` exactly like the
   By-instrument card. **Mutually exclusive** — one
   instrument at a time. Selecting an instrument also
   reveals its **response-field scope chips** in the next
   group; deselecting it hides them. With no instrument
   selected the (eventual) aggregate columns span every
   session instrument, matching the legacy "By reviewer" /
   "By reviewee" framings.
5. **Response-field scope chip** — one per response field
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
   selected column chips on the active shape. Cells size to
   their content; on overflow the row **wraps onto a second
   line** rather than scrolling horizontally (the table is
   flattened to flex-wrap on `<tr data-shape-preview-row>`,
   each cell stays `white-space: nowrap` so individual
   labels don't break mid-word). Empty-state placeholder
   (muted italic) reads "Pick chips above to compose this
   shape's columns" — keeps the table visible so the
   operator sees something to interact with.

   **Preview labels diverge from CSV headers.** The preview
   is a descriptive aid for what the operator selected, not
   a literal duplicate of the file. Identity columns surface
   with a space (``Reviewer Name`` / ``Reviewer Email`` /
   ``Reviewee Name`` / ``Reviewee Email``) while the CSV
   uses the no-space form (``ReviewerName`` etc.). Aggregate
   columns drop the Self-review handling chip suffix
   (``Mean`` rather than ``Mean_self``), and
   ``self_review_handling="both"`` emits a single aggregate
   block in the preview (one block per slot) rather than
   the side-by-side duplication the CSV ships. Source:
   ``compose_shape_preview_headers`` in
   ``app/services/extracts/data_shape_extract.py``; CSV
   generation continues to call ``_compose_header``
   directly from ``build_shape_rows``.

   **CSV-duplicated columns get a thick grey bottom edge
   under ``Self-review: Both``.** Each `<th>` carries
   `data-aggregate="true"` on aggregate columns (Assigned,
   Count, Mean, Median, Min, Max, Length, fan-out columns
   from List items / Discrete steps); identity columns
   (Name, Email, Tag-N) never do. CSS keys off the sub-
   card's ``data-shape-current-self-review-handling="both"``
   attribute to draw a 3px grey bar at the cell's bottom edge
   (matches the page chrome's active-tab marker pattern,
   drawn via ``box-shadow: inset`` so there's no layout
   shift). The marker flips live as the operator cycles the
   chip. Source: ``compose_shape_preview_aggregates``
   returns a parallel ``tuple[bool, ...]`` (same length as
   the headers) that drives the per-cell flag both on
   server render and through ``data-shape-column-aggregates``
   for the JS Cancel-restore path.

   **Saved vs. live self-review state on the sub-card.** Two
   attributes ride on each `.data-shape-card`:

   - ``data-shape-self-review-handling`` — the **saved**
     state (mirrors the persisted column). Server-rendered
     on saved cards; updated only when ``applySavedShapeAttrs``
     runs after a successful Save. The dirty-state gate
     (``hasUnsavedChanges``) reads this for its comparison.
   - ``data-shape-current-self-review-handling`` — the
     **live** chip state. Server-rendered to match the saved
     value initially; updated on every
     ``setShaperSelfReviewState`` call. The CSS duplicated-
     column marker keys off this attribute so chip cycles
     flip the visual immediately without touching the
     dirty-state gate.
2. An **action row** flushed to the right edge of the
   sub-card (`.data-shape-actions` carries
   `justify-content: flex-end`). The name input / display
   sits inline with the action buttons + `Download` —
   they're not split across rows or columns. Layout left ➝
   right within the right-anchored strip:
   - **Name input** (`data-shape-name`) — visible while the
     sub-card is in edit mode; collapses behind the saved-
     name span (`data-shape-name-display`) when not editing.
   - **`Save` / `Edit`** (`data-shape-save` /
     `data-shape-edit`) — single mode-toggle slot, only one
     button visible at a time. `Save` shows in edit mode +
     stays disabled until the active shape is **valid**
     (name non-empty + axis chip on + ≥1 column chip on);
     clicking it persists the name into the display span
     and **keeps the sub-card in edit mode** (per wiring
     decision: Save does not unselect). `Edit` shows in
     saved mode + always enabled.
   - **`Cancel`** (`data-shape-cancel`) — enabled only in
     edit mode. Abandons the in-progress edits and unselects
     the sub-card (flips it to saved mode). For saved sub-
     cards, re-renders the preview row from the persisted
     column headers (`data-shape-column-headers`) so
     transient unsaved-chip selections are visually dropped;
     chip visual state in the scope/content rows is **not**
     reverted (still open — see "Out of scope" below).
   - **`Delete`** (`data-shape-delete`) — disabled when this
     is the only sub-card in the stack (mirroring the
     Response Fields builder's always-present empty row).
     Otherwise removes the sub-card and transfers the
     selected state to a neighbour if necessary.
   - **`+Shape`** (`data-shape-add`) — clones a fresh blank
     sub-card immediately after this one, makes it the new
     selected target, and closes the previously-editing
     card (per the active-shape mutex).
   - **`Download`** (`data-shape-download`) — sits at the
     right-most end of the strip. Wired for **saved shapes**
     (those with a `data-shape-id`): JS sets
     `href="…/shapes/{id}/download.csv"` and
     `aria-disabled="false"` when a shape id is present.
     Renders disabled (`href="#"` + `aria-disabled="true"`)
     for unsaved (brand-new, never-persisted) sub-cards.

   Every button gates its enabled state on the active
   shape's validity via a single ``updateButtonStates(shape)``
   helper that runs on every chip toggle, name input,
   mode flip, and card spawn / delete.

The **always-present blank sub-card** on initial load gives
the operator an immediate edit target without requiring a
preceding "Add a shape" click — matching the Band-3
Response Fields builder's always-present empty row.

### Row-key contract

The **row identity** that each chip selection implies for the
file-gen pipeline. Symmetric across axes — swap
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

### Wiring decisions (resolved 2026-05-29, fully shipped 2026-05-30)

The placeholder UI shipped through #1589 → #1610 surfaced the
operator-facing chip vocabulary; the wiring slice (#1626 →
#1659) turned chip selections into persisted shapes + CSV
downloads + a chip-controlled drop of empty rows. The
decisions below pin the contract the slice honoured.

#### Persistence model

A new `data_shapes` table keyed on `(session_id,
name)` with `UNIQUE (session_id, name)` so the operator
can't save two shapes with the same name on the same
session. Per-session (not per-operator) — every operator
on the session sees the same shape library.

Columns (final, as of 2026-05-30):

| Column | Purpose |
|---|---|
| `id` | PK |
| `session_id` | FK to `review_sessions`, indexed |
| `name` | Operator-supplied name (non-empty after trim, unique per session) |
| `axis` | `"reviewer"` or `"reviewee"` — the selected axis chip |
| `instrument_id` | nullable FK to `instruments` — null when no instrument scope chip is on |
| `response_field_id` | nullable FK to `instrument_response_fields` — null when no field chip is on |
| `column_chip_slots` | JSON list of column-chip slot strings (e.g. `["reviewer:name", "reviewer:email", "reviewer:assigned", "reviewer:count", "reviewer:list-items"]`) — preserves chip-selection order so the preview-row order matches the CSV header order |
| `self_review_handling` | Self-review handling chip state — `include_self` (default) / `exclude_self` / `both`. Added 2026-05-30 by PR #1643. |
| `include_empty_rows` | Empty-row drop chip state — `True` (default, "All rows") / `False` ("Rows with data"). Added 2026-05-30 by PR #1654. |
| `created_by_user_id` | FK to `users` |
| `created_at` | timestamp |
| `updated_at` | timestamp (bumps on PATCH) |

The same columns drive both the persisted-shape rebuild
(when an operator clicks `✎` to re-edit) and the
file-generation pipeline.

#### Routes

Save-then-download — every download corresponds to a saved
shape; there's no inline / ephemeral download URL.

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/operator/sessions/{id}/extract-data/shapes` | Create a new shape from the current chip state. Body: `name`, `axis`, `instrument_id`, `response_field_id`, `column_chip_slots`. Returns the new `shape_id`. Validation errors (empty name, name conflict, empty column chips) return 422 with an inline error. |
| `PATCH` | `/operator/sessions/{id}/extract-data/shapes/{shape_id}` | Update an existing shape. Same body shape as POST; renaming clashes with another shape on the session ⇒ 422. |
| `DELETE` | `/operator/sessions/{id}/extract-data/shapes/{shape_id}` | Delete a shape. Idempotent — re-delete returns 204. |
| `GET` | `/operator/sessions/{id}/extract-data/shapes/{shape_id}/download.csv` | Stream the shape's CSV. Backs the `Download` button on each saved sub-card. |

All four go through `require_session_operator` per the rest
of the page. No new lifecycle gating — extracts work in
every state.

#### File naming

Each `Download` button serves `{code}_{slug(name)}.csv`,
where `slug(name)` uses the same alphanumeric-plus-underscore
sanitisation as `by_instrument_filename_slug`. Filename
collisions can't happen because the underlying name is
session-unique.

#### Audit events

Three new event types register against `EVENT_SCHEMAS`:

| Event type | Envelope | Notes |
|---|---|---|
| `session.data_shape_saved` | `_IDENTITY \| {"snapshot", "refs"}` | Fires on POST + PATCH. `snapshot` captures the shape's persisted columns (axis, instrument_id, response_field_id, column_chip_slots, self_review_handling, include_empty_rows, name); `refs.shape_id` carries the row's id. |
| `session.data_shape_deleted` | `_IDENTITY \| {"snapshot", "refs"}` | Fires on DELETE. `snapshot` captures the deleted row's columns so the audit trail can reconstruct what existed pre-delete. |
| `session.data_shape_extracted` | `_IDENTITY \| {"counts", "refs", "context"}` | Fires on the GET download route. `counts.rows` = body row count (header excluded); `refs.shape_id` carries which shape was extracted; `context.self_review_handling` records the chip state the download was generated under (PR #1643). |

#### Validation rules

* **Column chips required.** Save (the `✓` icon) stays
  `disabled` until at least one `data-shaper-col-chip`
  on the active shape is `aria-pressed="true"`.
* **Name required and unique per session.** The name
  input rejects whitespace-only submissions; server-side
  `UNIQUE (session_id, name)` constraint backs the
  client-side check.
* **Axis required.** A shape with no axis chip on can't
  save — without an axis there's no row identity to
  compose, and the row-key contract collapses (only the
  single summary row would render and the operator can't
  meaningfully name it).

#### Edit-icon behaviour

Clicking `✎` on a saved sub-card:

1. **Closes any other open sub-card.** Only one sub-card
   can be in edit mode at a time. If another sub-card was
   already in edit mode and has unsaved chip changes, the
   server-side state stays the way it is and the
   client-side chip selection silently switches — the
   transient unsaved selection is discarded. (Forcing a
   save / discard prompt is more friction than the
   placeholder-slice operator needs.)
2. **Restores the saved shape's chip state** into the
   scope row + content row by walking the row's `axis` →
   `instrument_id` → `response_field_id` → `column_chip_slots`
   chain and re-toggling the matching chips.
3. **Flips the sub-card's visual state** to "selected"
   via a `data-shape-selected` attribute the CSS gates on
   (see "Selected-sub-card visual cue" below).
4. The `+` icon also closes the currently-editing
   sub-card before spawning a new blank one. The new
   sub-card becomes the new selected/editing target.

#### Selected-sub-card visual cue

The sub-card currently in edit mode renders with its
border tinted to the same accent blue used for primary
buttons + selected chips (`var(--accent-blue)`). Concretely:

* Default sub-card border: `1px solid var(--color-border)`
  (existing).
* Selected sub-card border: `1px solid var(--accent-blue)`
  + a tighter / brighter `box-shadow` inset to lift the
  card out of the stack.

Driven by a single attribute (`data-shape-selected="true"`
or equivalent on the editing sub-card) so the JS that
manages "which sub-card is being edited" only flips one
attribute and the CSS handles the rest. `setActiveShape`
in the inline JS flips this attribute and the
`restoreShapeChipState` helper walks the saved shape's
attributes to re-press the matching chips when the
operator clicks `Edit` (see "Edit-icon behaviour" above).

#### Group-scoped semantics for tag-aggregate rows

The metadata cards' asymmetric dedupe rule carries over
for tag-aggregate rows on group-scoped instruments:

* **Reviewer-tag aggregate row × group-scoped field**
  → dedupe by `(reviewer-tag-combo, group_key, field_id)`.
  Multiple reviewers sharing the same tag combo, each
  reviewing the same group on the same field, contribute
  their distinct group answers; the fan-out copies
  within a single reviewer's group review collapse to one.
* **Reviewee-tag aggregate row × group-scoped field**
  → no dedupe. Each member-assignment carries its own
  copy of the group answer (from the save-time fan-out),
  and from the reviewee's perspective each (reviewer,
  field) cell is independent.

Same rule on per-individual rows (with `reviewer` /
`reviewee` substituted for the tag combo) and on the
single summary row (with the whole roster substituted).

### Out of scope (still — even after the wiring slice)

The wiring slice doesn't cover:

- **Cancel chip-state revert.** `Cancel` on a saved sub-card
  re-renders the preview row from persisted headers but does
  not restore the chip visual selections in the scope/content
  rows. Chip visual state stays at whatever the operator last
  toggled.
- **Column-chip drag-to-reorder + sort-icon click** inside
  the preview row. The chips currently render in
  chip-selection order; reorder is a follow-up.
- **Cross-session shape copy.** Saved shapes don't travel
  when the operator clones a session. Possible v2.
- **Per-operator privacy.** All operators on a session see
  every saved shape — no per-operator scoping.
- **Data shaper `Zip all` integration.** Each shape's
  `Download` button is wired; the outer `Zip all` button on
  the Data shaper card still renders `aria-disabled="true"`
  (bundle integration is a follow-up).

## `Token keys` card

Half-width card on the left, below the full-width `Data
shaper` card. **Conditional**: renders only when
`session.observers_enabled` is on — the tokens are the
deanonymization key for the observer-side Anonymized
output and have no other consumer today, so the chrome
matches the intro card's `token-keys` chip in being
gated on the same flag. The right column on this row is
intentionally empty so the card reads as a deliberate
half-width affordance under the full-width Data shaper.

| Field | Value |
|---|---|
| Heading | `Token keys` |
| Body copy | "Operator-side deanonymization key — one row per Reviewer + Reviewee with their per-session opaque token. Look up a token from an Anonymized observer download to recover the underlying name + email." |
| Button id | `extract-data-token-keys-download` |
| Button target | `/operator/sessions/{id}/export/participant_tokens.csv` |
| Filename | `{code}_participant_tokens.csv` |
| Columns | `Role`, `Name`, `Email`, `Token` |

**No chip row** — the card has a single fixed-shape
download. The matching `token-keys` chip on the intro card
drives bundle inclusion (`?tokens=0` on the responses-bundle
URL); this per-card button always ships the full mapping.

**Audit event.** `session.participant_tokens_extracted`
carries a `counts.rows` slot (reviewers + reviewees
combined, header-excluded).

**Token computation** mirrors the observer-side Anonymized
output: same `ParticipantTokenizer` (env salt mixed with
`session.created_at`), so a token here is byte-identical
to the corresponding token in any Anonymized `by_instrument`
download. Closes `guide/archive/observers_clean_up.md` item 15 (originally
planned as a paste-a-token widget on the Observers Setup
page).

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
- `guide/archive/extract_data.md` — shipped plan: landing
  rationale, open-question resolutions, and the wiring
  decisions for the chip-controlled-drop + self-review-
  handling slices (archived 2026-05-30).
