# Extract data — new Operations tab + Session Home card split

> **Mostly shipped 2026-05-29 → 2026-05-30 (PRs #1565 →
> #1627).** Session Home card split + new **Extract data**
> Operations tab + per-instrument / reviewer-metadata /
> reviewee-metadata lenses + the full **Data shaper** (saved
> `data_shapes` with CRUD routes, file generation, Settings
> CSV round-trip, and Zip-all integration) all landed. Wiring
> lives in `app/web/routes_operator/_extract_data.py`,
> `app/services/data_shapes.py`,
> `app/services/extracts/data_shape_extract.py`,
> `app/services/extracts/zip_bundle.py`
> (`include_data_shapes`), and
> `app/services/session_config_io/{_serialize,_apply}.py`
> (`_data_shape_rows` + `_apply_data_shapes`).
>
> **Follow-on slice pending (proposed 2026-05-30):**
> three-way `Self-review handling` chip on the two metadata
> cards + Data shaper scope row. See *Self-review handling in
> summarizing extracts (proposed 2026-05-30)* below. Plan
> stays in `guide/` (not yet archived) until that slice
> lands.
>
> **Original stub header (created 2026-05-29):** Captures the
> plan to split the current Session Home "Extract data" card
> into two surfaces: a slimmed-down **Extract setup** card on
> Session Home (porting-shaped CSVs only), and a new
> **Extract data** tab in the Operations strip whose job is
> fine-grained shaping of the response data for offline
> analysis.

## Why this exists

The Session Home **Extract data** card today is a one-shape
download grid: one CSV per entity (Reviewers / Reviewees /
Relationships / Session settings / Responses) plus a Zip-all
bundle. It conflates two jobs:

1. **Setup data** — Reviewers / Reviewees / Relationships /
   Session settings. These are the things an operator
   originally uploaded (or could re-upload via Quick Setup).
   The natural use case is **portability**: clone a session,
   hand off to a colleague, archive a snapshot.
2. **Response data** — what reviewers produced during the
   session. The natural use case is **analysis**: pivot in
   Excel, load into pandas, slice by reviewer / reviewee /
   instrument.

Today's card serves (1) well — every row round-trips through
Quick Setup unmodified (18N PR 5 closed the last gap). It
serves (2) only at the single-shape level: one giant
denormalised Responses CSV. Operators who want to analyse
"what each reviewer said across all instruments", or "what
each reviewee got across all reviewers", end up doing the
pivot in Excel because the export forces them to.

Splitting the surface lets each side specialise: the card
stays focused on porting, and a dedicated **Extract data**
page handles response-data shaping with three lenses
(instrument / reviewer / reviewee).

The aim of the new page is **not analysis** — it's to **shape
the data so that offline analysis is easier**. No charts, no
in-app pivots. Just CSVs cut along the dimension the operator
asks for.

## Recommended end state

### Session Home — rename "Extract data" → "Extract setup"

The card stays where it is (right column of Session Home,
two-column internal layout). Its row list shrinks to the
porting-shaped CSVs only, and the column placement mirrors
Quick Setup's slot layout so the two cards read the same way:

```
Extract setup
  Reviewers         Relationships
  Reviewees         Session settings
                    Zip all  (the four CSVs above)
```

**Drop the Responses row.** It moves to the new tab. The
**Zip-all** row stays — but bundles **only the four setup
CSVs** (`{code}_setup.zip`). This matches the card's
repositioned purpose (porting / cloning) and aligns 1:1 with
the **Apply Settings CSV** input on Quick Setup: what the card
exports is exactly what Quick Setup can ingest.

The card stays interactive in every lifecycle state (no
lock-card wrap), same as today.

### Operations strip — new "Extract data" tab after "Responses"

```
Operations:  Assignments  Validate  Previews  Invitations  Responses  Extract data
```

Lives at `/operator/sessions/{id}/extract-data`. Behaves like
the other Operations pages (read-mostly, no lock card, breadcrumbs
via `operator_session_child("Extract data")`).

### Page interaction model

Two interaction shapes coexist on the page:

- **Per-lens configure + download.** The "By instrument" /
  "By reviewer" / "By reviewee" cards (below) are the
  fine-grained surface. Each card is configurable — the
  operator picks which entities to include, what shape they
  want (single CSV vs zip-of-N) — and clicks Download on that
  card to get exactly those files. The page is **the
  operator's data-shaping workbench**; each card produces a
  scoped download.
- **Top "Zip all" button.** A one-click shortcut that
  downloads every response-side CSV in a single archive
  (`{code}_responses.zip`). Members: unified `responses.csv`
  + bundle-only `reviewer_stats.csv` + `reviewee_stats.csv` +
  one `instrument_{n}.csv` per instrument sorted
  reviewee-first. This is the "I just want everything"
  affordance — operators who don't want to fiddle with
  per-lens configuration can take the full set with one
  click. Sits in the top-right of the page intro card so
  it's the first affordance the operator sees on entry.

The two shapes are complementary, not redundant. Zip-all is
the operator's "I trust the default; give me everything";
the per-lens cards are "I want it shaped a specific way."
Per-lens downloads stay independent — Zip-all doesn't
require any per-lens configuration first.

### Shipped today

- **Page layout**: 2-column grid of half-width cards, bottom-
  aligned via `align-items: end`.
  - **Left column (response data)**: `Extract all data` intro
    card (top) + `By instrument` lens (below).
  - **Right column (metadata)**: `Reviewer response metadata`
    + `Reviewee response metadata`.
  - **Full-width Data shaper** card below the grid (placeholder
    — see *Data shaper design* below).
- **Intro card** (`Extract all data`).
  - Body copy: "Configure what you need on the lens cards and
    download the specific files. Use **Zip all** to download all
    response files (as configured using the other cards) at once."
  - Chip row (all default-selected): `By instruments`,
    `Reviewer response metadata`, `Reviewee response metadata`,
    `Data shaper`. Each chip will scope which lens-shaped CSVs
    land in the top-level `Zip all` zip once wired.
  - Button: `Zip all` → `responses_bundle.zip` (unified
    Responses CSV + reviewer/reviewee stats + per-instrument
    long-format files).
- **By-instrument card**.
  - Chips: one per instrument (label = `#{n}: {short_label}`
    mirroring the Reviewer-surface heading, or bare `#{n}`
    when no short label) + cross-cutting toggles
    `Include metadata` + `All assignment rows`. All
    default-selected.
  - Button: `Zip all` → `by_instrument_bundle.zip` carrying
    one wide-format CSV per instrument, named
    `{code}_by_instrument_{slug}.csv`. Each CSV carries a
    **meta header** (instrument identity + per-field
    type/constraint rows + assignment count + pool /
    unit-of-review / self-review configuration; the latter
    three render rule fields as
    `<source_type>.<friendly label>`) + blank row + **wide
    data table** (one row per assignment, columns = identity
    + tags + one column per response field + SelfReview +
    SavedAt + SubmittedAt). Group-scoped instruments collapse
    the same way the unified Responses CSV does.
- **Reviewer / Reviewee response metadata cards**.
  - Heading + body copy explaining the data/metadata split:
    per-reviewer / per-reviewee response *data* is trivially
    reshaped from the By-instrument export via a spreadsheet
    sort or Power Query; these cards focus on *metadata
    about responses* (counts, aggregates per response field,
    against which instruments).
  - Chips (all default-selected): one chip per instrument
    (mirroring the By-instrument card's `#{n}: {short_label}`
    label, or bare `#{n}` when no short label) followed inline
    by `All reviewers` / `All reviewees`. The per-statistic
    chips (`Count`, `Mean`, `Median`, `Min`, `Max`, `Length`)
    retired — they moved into the per-(instrument, field)
    column blocks of the extract output where they apply
    by data type (see below).
  - Button: `Download` → `{code}_reviewer_metadata.csv` /
    `{code}_reviewee_metadata.csv` (a single CSV per card,
    so the button label drops the `Zip all` framing used on
    the other cards — nothing actually gets zipped here).
  - **Column shape** (Reviewer side; Reviewee side is
    symmetric, swapping `ReviewerName` / `ReviewerEmail` for
    `RevieweeName` / `RevieweeEmail`):
    - Always: `ReviewerName`, `ReviewerEmail`,
      `Assigned` (the count of reviewee × field cells the
      reviewer is supposed to fill in, scoped to the
      in-scope instruments), `Count` (those cells with a
      non-empty response).
    - Per selected instrument, per response field: one block
      named `#{N}: {short_label}.{field}.<metric>`. `{N}` is
      the instrument's 1-based **session** position (stable
      as chips toggle). Block columns always carry `.Assigned`
      + `.Count`; numeric fields (Integer / Decimal) add
      `.Mean`, `.Median`, `.Min`, `.Max`; string fields add
      `.Length` (sum of characters across non-empty
      responses).
  - **Row scoping**:
    - No instruments selected → only the two cross-instrument
      totals ship, scanning **every** session instrument so
      the totals stay meaningful.
    - `All reviewers` / `All reviewees` ON → every roster
      entry gets a row. OFF → only entries with at least
      one non-empty response in scope.
  - **Group-scoped instruments** fan responses across each
    member assignment at save time. The two sides handle that
    asymmetry differently:
    - **Reviewer side** — a reviewer fills one form per group,
      not one per member; the save layer copies the answer onto
      every member-assignment. So `Assigned` dedupes by
      `(reviewer, instrument, group_key)` (one count per group)
      and `Count` / per-field rollups dedupe by
      `(reviewer, group_key, field_id)` (one count per group
      answer, no matter how many members received the
      fan-out).
    - **Reviewee side** — from a reviewee's perspective there
      is exactly one cell per (reviewer, field) about them,
      so no dedupe is needed; each member-assignment counts on
      its own.
  - Query-string wiring on the button reuses the same
    `?instrument=<id>` (repeated) + `?all=0` shape the chip
    JS composes.
- **Data shaper** (full-width, below the grid). Placeholder
  UI shipped; persistence and file generation deferred.
  - Heading + body copy describing the generalised builder.
  - **Two stacked chip rows** at the top of the outer card:
    a **scope row** (top) and a **content row** (one row
    below). Splitting them keeps the row reading scannable
    as the operator composes a shape — the scope row
    answers "what subset of data are we looking at?", the
    content row answers "what columns go in the CSV?".

    **Scope row** carries three mutex chip groups separated
    by `|`s:

    1. Two **mutually exclusive** axis-selector chips
       (`Reviewer`, `Reviewee`).
    2. **Mutually exclusive per-instrument scope chips**
       (always visible, one per session instrument, labelled
       `#{N}: {short_label}` like the By-instrument card).
    3. **Mutually exclusive response-field scope chips** for
       the currently-selected instrument (chip text = the
       field's friendly label). The response-field section
       swaps contents when the operator switches instruments
       (and its leading `|` hides when no instrument is
       selected, so the row doesn't carry an orphan pipe).

    All three mutex groups follow the same rationale: the
    Data shaper is for fine-grained shape composition, so
    "one at a time" focus reads more naturally than
    multi-select. The full `reviewer × reviewee` matrix is
    already downloadable via the By-instrument card, and
    cross-instrument summaries already live on the metadata
    cards — those broader cuts don't belong here. With no
    instrument scope chip selected the aggregates span every
    session instrument — matching the legacy "By reviewer" /
    "By reviewee" general-data framings; selecting one
    scopes the aggregates to that instrument, and selecting
    a response field narrows further to that single
    instrument-field cell.

    **Content row** carries the per-axis chip pool — mounted
    by the JS into a single `<span
    data-shaper-relevant-chips>` slot. The pool has two
    sub-groups separated by `|`:
    1. **Identification chips** — Name / Email / Tag 1-3
       (per-axis-entity). The three tag chips render the
       **session-friendly labels** for those slots
       (operator renames via the Setup pages), falling back
       to the built-in `Tag 1` / `Tag 2` / `Tag 3` defaults
       when no override is set.
    2. **Aggregate data chips** — `Assigned` / `Count` |
       `Mean` / `Median` / `Min` / `Max` / `Length` |
       `List items` / `Discrete steps` (mirrors the Reviewer
       / Reviewee response metadata cards' aggregate column
       vocabulary, with `Assigned` leading per that card's
       column order, a `|` after `Count` separating the
       field-independent totals from the standard
       field-scoped statistics, and a trailing `|` before
       the fan-out chips. Each `|` hides when nothing to
       its right would render, so the row never carries an
       orphan separator — and List fields specifically only
       show the trailing pipe before `List items`, never
       the post-Count one). The
       field-scoped aggregates (`Mean`, `Median`, `Min`,
       `Max`, `Length`, `Discrete steps`) **only render when
       a response field is selected** — without a specific
       field there's no value vector to summarise.
       `Assigned` and `Count` stay visible always
       (field-independent). Once a response field is picked,
       the field-scoped chips filter to the ones **relevant
       to that field's data type**:
       - Numeric (Integer / Decimal) fields surface
         `Mean`, `Median`, `Min`, `Max`.
         - Numeric fields with a finite, small (≤12)
           number of discrete values — i.e. `min`, `max`,
           and `step` defined and `(max - min) / step + 1
           ≤ 12` — additionally surface a **`Discrete
           steps`** chip after `Max` (separated by another
           `|`). Selecting it emits one preview-row
           column per step value (e.g. an Integer
           1..5/step 1 yields the five columns `1` `2`
           `3` `4` `5`). The step values are pre-computed
           server-side and stitched into the field chip's
           `data-shaper-field-discrete-steps` CSV.
       - String fields surface `Length`.
       - **List fields** swap the numeric / string
         aggregates for a single **`List items` chip** —
         clicking it emits one preview-row column per
         option (the JS reads the option CSV from the
         active field chip's
         `data-shaper-field-list-options` at render time).
         Same shape as the `Discrete steps` chip — a
         single chip that fans into N preview columns.
       - Other types surface neither — just `Assigned` and
         `Count`.

       Selected chips that get hidden by a data-type swap
       (or by the operator deselecting the response field)
       auto-deselect so the preview row stays consistent.
  - **Preview-row empty state**: each Data shape sub-card's
    preview table seeds a muted-italic placeholder cell
    ("Pick chips above to compose this shape's columns")
    whenever no column chips are selected on the active
    shape — keeps the table visible so the operator has an
    obvious affordance to work with.
  - **Name ↔ Email chip coupling** (UI behaviour shipped;
    underlying row-key semantics described below — wiring
    pending).
    - Email can stand alone — it's a unique identifier on
      its own.
    - Name cannot stand alone — selecting `Reviewer Name` /
      `Reviewee Name` auto-selects the matching `Email`
      chip; deselecting `Email` while `Name` is on cascades
      the deselect to `Name`. Rationale: people share
      names, so `Name` alone isn't a sound row key.

### Row-key semantics — for the wiring slice

The shipped chip-toggle behaviour is purely client-side; the
**row identity** semantics each combination implies live
here as the contract the file-gen slice must honour.

For a given axis (Reviewer or Reviewee — symmetric
behaviour, swap `reviewer` ↔ `reviewee` throughout):

| Chip selection on the active shape | Row identity of the produced CSV |
|---|---|
| `Name` + `Email` selected (Name implies Email, so this is the same as "Name selected") | **One row per individual** — every reviewer / reviewee on the session gets its own row. |
| Only `Email` selected (no `Name`) | **One row per individual** — Email is the canonical unique identifier. The `Name` column simply isn't emitted. |
| Only some subset of tag chips (`Tag 1`, `Tag 2`, `Tag 3` — any combination) — no `Name` / `Email` | **One row per distinct tag-combination** — the rows are aggregates of the individuals sharing the selected tag values. With three tag chips on, the row key is the (Tag 1, Tag 2, Tag 3) tuple; with one, it's that one tag's value. |
| Nothing selected (neither identification nor tag chips) | **A single summary row** across every reviewer / reviewee on the session — the aggregate columns are computed across the whole roster. |
| Both `Name` / `Email` **and** tag chips selected | `Name` / `Email` wins for row identity — **one row per individual**. The tag chips emit additional identification columns on each row but don't roll up. |

Aggregate columns (`Assigned`, `Count`, `Mean`, `Median`,
`Min`, `Max`, `Length`) compute against the chosen row key:

- Per-individual rows → aggregate over that individual's
  in-scope responses.
- Per-tag-combo rows → aggregate over every individual
  sharing that tag combination's responses.
- Single summary row → aggregate over the whole roster's
  in-scope responses.

The instrument scope chip + response-field scope chip on the
top axis row narrow what "in-scope responses" means: with no
instrument chip selected, the aggregates span every session
instrument; selecting one narrows to that instrument;
selecting a response field narrows further to that specific
field. The aggregate-chip data-type filter (numeric chips
for numeric fields, `Length` for string fields, only
`Assigned` / `Count` for other types) follows the same
field-data-type rules the Reviewer / Reviewee response
metadata cards already use.
  - **Data shape sub-card stack** below the axis row — one
    sub-card per shape. One always-present blank shape card
    on initial load (matches the band-3 response-field
    builder's always-present-empty-row pattern, so the
    operator has an immediate edit target). Each sub-card
    carries:
    - **Preview row** — `width: auto` `<thead>` whose cells
      mirror the currently-selected column chips. Toggling a
      column chip on / off adds / removes a `<th>` in the
      currently-active shape card.
    - **Action row** — flushed right inside the sub-card.
      The name input / display sits inline with the
      buttons: `Save` / `Edit` (mode-toggle slot — `Save`
      shown in edit mode, `Edit` in saved), `Cancel`,
      `Delete`, `+Shape`, and `Download` at the rightmost
      end. `Save` stays
      disabled until the active shape is valid (name
      non-empty + axis chip on + ≥1 column chip on);
      clicking it persists the name but **keeps the
      sub-card in edit mode** (Save does not unselect).
      `Cancel` is enabled only in edit mode and abandons
      the in-progress edits + unselects the sub-card.
      `Delete` is disabled when the sub-card is the only
      one in the stack. `+Shape` always enabled, closes
      the currently-editing card before spawning. The
      whole row's disabled states refresh via a single
      `updateButtonStates(shape)` helper on every chip
      toggle / name input / mode flip / card spawn or
      delete. `Download` stays `aria-disabled` until the
      file-gen wiring slice.
  - Button: placeholder `Zip all` (`href="#"`,
    `aria-disabled`) at the bottom of the outer card.
  - **Out of scope in this slice** (lands separately):
    column-chip drag-reorder + sort-icon click on the preview
    row; per-session persistence of saved shapes; the
    file-generation pipeline; audit events.

### Data shaper design

The Data shaper is a generalised engine for composing custom
data shapes. The shipped placeholder card holds the heading
+ a preview-table stub; the full design below lands across
the next slices.

**Mental model.** Each *shape* = one CSV. The columns of the
CSV are composed by selecting **column chips** that name each
column. A shape is rendered as one **Data shape card** (a
full-width card *inside* the outer Data shaper card). One
Data shape card per shape. Multiple shapes per Data shaper
(operator clicks the `+` icon to add another below).

**Axis chip row (top of the Data shaper card).** Three
**axis-selector chips** — `Reviewer`, `Reviewee`,
`Instrument` — followed by a vertical pipe (`|`). All axis
chips default to **unselected**. Selecting an axis surfaces
its **relevant column chips** to the right of the `|` (the
list of relevant chips per axis remains to be determined —
this is the open design question for the next slice). The
operator picks column chips to compose the shape; toggling
the axis off hides its chips and removes the corresponding
columns from the active shape.

Multiple axes can be on at once — the relevant chip row
concatenates the selected axes' chips left-to-right.

**Data shape card (full-width, inside the Data shaper card).**
One per shape. Layout, top to bottom:

1. **Preview row** — the selected column chips render as the
   header row of the CSV being built. Flush-left, `width:
   auto`; each column sized to its header. (The placeholder
   table shipped today is the stub for this row.) Sort-icon
   per column (visual today; click + drag-reorder wiring
   follows).
2. **Edit box** for the shape's name + **tick icon** (save the
   sequence under the typed name) + **X icon** (delete this
   shape) + **+ icon** (add a new blank Data shape card below
   this one).

On save: the edit box collapses to the saved name as plain
text, and the tick icon flips to an **edit icon** (clicking
it restores the edit box so the operator can rename).

**Operator's mental loop.** Toggle axes → pick column chips
→ see the preview-row header update live → name and save the
shape → click `+` to start a new one. The end state is a
stack of named Data shape cards, each describing one CSV
that ships in the Data shaper's `Zip all` zip — and, when
the intro card's `Data shaper` chip is selected, in the
top-level `Zip all` too.

**Open design questions for the next slice.** All five
resolved 2026-05-29 — see *Data shaper — open design
questions* below for the full answers; the placeholder
prompts that lived here have been removed.

### Data shaper — open design questions (resolved 2026-05-29)

1. **Relevant column chips per axis.**
   - **Reviewer**: `Name`, `Email`, `Tag 1`, `Tag 2`, `Tag 3`
     (rendered with their session-friendly labels where set)
     + the per-reviewer aggregate chips (`Count`, `Mean`,
     `Median`, `Min`, `Max`, `Length` — same vocabulary as the
     Reviewer response metadata card).
   - **Reviewee**: same shape as Reviewer (`Name`, `Email`,
     three tags + the six aggregate chips). For group-scoped
     instruments the row identity is the **composed group
     name** from `_compose_group_identity` — one row per group
     identity is enough; no per-member fan-out at this layer.
   - **Instrument**: `Short label`, response-field labels (one
     chip per response field defined on the instrument), and
     per-field aggregate chips (same six).
   - More axis-relevant chips may surface later — the slice
     ships with the above as the v1 set.

2. **Per-axis vs cross-axis aggregates — confirmed.** The
   *axes* drive grouping (one row per unique combination of
   selected axes' identity chips); the aggregate chips drive
   the value columns. Example: with `Reviewer` selected as
   the only axis, each row = one reviewer; columns = on a
   per-instrument basis, aggregate data (e.g. mean / min /
   max response value on a numeric response field, mean /
   min / max response length for a string field, etc.).

3. **Persistence — per-session only.** Saved shapes live on
   the session, not on the operator. Every operator with
   access to the session sees the same shape library. No
   cross-session copy in v1.

4. **`Zip all` membership — N CSVs, one per shape.** The Data
   shaper card's `Zip all` produces one CSV per saved shape,
   named after the shape. The top-level intro-card `Zip all`
   folds those same CSVs in when the intro card's
   `Data shaper` chip is selected.

5. **Empty-state behaviour — block the save.** A Data shape
   card with no column chips selected is not savable. The
   tick icon stays disabled (or surfaces an inline error)
   until at least one column chip is on.

### Data shaper — wiring decisions (resolved 2026-05-29)

The placeholder UI shipped through #1589 → #1610. The
**wiring slice** ahead turns chip selections into persisted
shapes + CSV downloads; the decisions below pin the
contract that slice must honour. Full table form lives in
`spec/extract_data.md` "Wiring decisions"; this section is
the design-question equivalent.

1. **Persistence — per-session, name-unique.** A new
   `data_shapes` table keyed on `(session_id, name)`
   with `UNIQUE (session_id, name)` so the operator can't
   save two shapes with the same name on a session. Per-
   session library (every operator on the session sees the
   same shapes); no per-operator scoping.

2. **Routes — save-then-download.** `POST` /
   `PATCH` / `DELETE` against
   `/operator/sessions/{id}/extract-data/shapes/{shape_id}`
   for save / update / delete, then `GET
   .../{shape_id}/download.csv` for the per-shape extract.
   No ephemeral download URL — every download corresponds
   to a saved shape.

3. **Audit events.** Three new event types register
   against `EVENT_SCHEMAS`:
   `session.data_shape_saved` (snapshot + refs.shape_id),
   `session.data_shape_deleted` (snapshot + refs.shape_id),
   `session.data_shape_extracted` (counts.rows +
   refs.shape_id).

4. **Filename — `{code}_{slug(name)}.csv`.** Same
   alphanumeric-plus-underscore slug as
   `by_instrument_filename_slug`. Collisions impossible
   thanks to the session-unique name constraint.

5. **Validation.** Name required (non-empty after trim).
   Server-side `UNIQUE` constraint backs the client-side
   check. Save (`✓`) stays disabled until at least one
   column chip is on AND axis is picked AND name is
   non-empty.

6. **Edit-icon — full chip-state restore.** Clicking
   `✎` on a saved sub-card loads its axis /
   instrument / response-field / column-chip selections
   into the scope + content rows, flips the sub-card
   into edit mode (visual cue: border tinted to the same
   accent-blue used for primary buttons + selected
   chips), and closes any other open sub-card.

7. **Active-shape mutex.** Only one sub-card can be in
   edit mode at a time. Clicking `✎` on another saved
   card silently switches the editable target — the
   previously-editing card's transient chip selection
   (if any) is discarded, not auto-saved. The placeholder-
   slice operator doesn't need a save / discard prompt at
   this seam.

**Group-scoped semantics for tag-aggregate rows.** Carries
over the asymmetric dedupe rule the metadata cards already
use:

- Reviewer-tag aggregate row × group-scoped field →
  dedupe by `(reviewer-tag-combo, group_key, field_id)`.
- Reviewee-tag aggregate row × group-scoped field → no
  dedupe; each member-assignment counts.

Same rule applies on per-individual rows (with
`reviewer` / `reviewee` substituted for the tag combo)
and on the single summary row (with the whole roster
substituted).

### Self-review handling in summarizing extracts (proposed 2026-05-30)

Self-review rows in Review Robin are **always materialised**
at Generate time — the legacy `SessionRuleSet.exclude_self_reviews`
column is vestigial (the engine hardcodes `False` regardless,
backfill migration `d2e4f6a8c1b3` flattened every row to
`False`, and `_create_band1_rule_set` writes `False` on every
save; see `spec/assignments.md` "Self-review policy" + the
`_band1.py:146-167` healing-on-save block). Whether
self-review rows then count as *active* turns on two layers:

1. **`ReviewSession.self_reviews_active`** (session-level
   toggle, defaults `True`). When `False`, every newly-
   materialised self-review `Assignment` lands with
   `include=False` so the reviewer surface never shows it.
2. **Per-row `Assignment.include` flip** on the Assignments
   page. The operator can flip individual self-pairs (or
   any pair) on/off post-Generate without re-running it.

Whether the reviewer then **submitted** a response on an
active self-review row is a third independent layer
downstream of both.

What the summarizing extracts still lack is a fourth,
orthogonal, **extract-time** control: given the self-review
responses that exist on `include=True` rows, fold them into
aggregates or not. This section captures the proposal for
that control.

**Three-way chip, always surfaced (state-machine over data).**
The `Self-review handling` chip is **always present** on the
two metadata cards + the Data shaper scope row whenever any
response data exists at all — but which of its three states
is operator-selectable depends on what kind of data exists
in scope:

| Data state in scope | Chip behaviour |
|---|---|
| **Both self-review and non-self-review responses present** | Full three-way chip, all three states selectable. Operator picks `Include self` / `Exclude self` / `Both`. |
| **Only non-self-review responses present** (no included-and-answered self-review rows) | Chip surfaces with `Exclude self` pre-selected and **locked** — the operator can see what state the file will ship in but can't switch to `Include self` (would emit empty) or `Both` (would emit one empty block). |
| **Only self-review responses present** (every non-self pair is `include=False` or unanswered — pathological, but valid) | Chip surfaces with `Include self` pre-selected and **locked**, same rationale. |
| **No responses present at all** | The whole card / shape has nothing to export; chip irrelevant. |

The chip's tri-state is computed server-side from the
included-row response pool, scoped the same way the
aggregates are (the active card's instrument scope, the
active shape's instrument + response-field + axis scope).
Toggling another scope chip may change the data state and
therefore the chip's locked / unlocked status; the JS
re-derives it on every scope-chip change so the UI doesn't
drift.

**Column-name + filename suffixes always present.** The
`_self` / `_noself` suffix lands on every aggregate column
**regardless of whether the chip was operator-selectable or
locked** — so the CSV schema is stable for downstream
consumers (a pandas script doesn't have to inspect the
session config to know what kind of pool the column
represents). Same goes for the filename suffix.

When it appears, the chip has three mutually exclusive
states:

| State | Aggregate behaviour | Column-name suffix | File-name suffix |
|---|---|---|---|
| **Include self** | Fold self-review responses into the row's `Count` / `Mean` / `Median` / `Min` / `Max` / `Length` exactly as today. | `_self` on every aggregate column. | `_self` appended before the extension. |
| **Exclude self** | Drop self-review responses from the row's aggregates. `Assigned` also drops the self-pair cells so the denominator stays honest. | `_noself` on every aggregate column. | `_noself` appended before the extension. |
| **Both** | The response-data column block is **duplicated** — first an include-self block (columns suffixed `_self`), then an exclude-self block (columns suffixed `_noself`), so a single CSV side-by-sides both views. Only selectable when both kinds of data exist in scope. | Both suffixes coexist in the same row. | `_both` appended before the extension. |

`Assigned` and `Count` are **part of the duplicated
response-data column block** (they're scoped by self / no-self
just like `Mean` / `Median` / `Min` / `Max` / `Length` — the
denominator and the cell-count both change between the two
pools), so they take the same `_self` / `_noself` suffix as
the field-scoped aggregates. Only the **identity columns**
(`ReviewerName`, `ReviewerEmail`, tag columns) carry no
suffix — they describe the row, not the response pool.

**Cards affected.**

- **Reviewer response metadata card** — chip in the existing
  chip row, separated by `|`. State drives the column suffix
  + filename suffix on `{code}_reviewer_metadata.csv`.
- **Reviewee response metadata card** — same shape on
  `{code}_reviewee_metadata.csv`.
- **Data shaper** — chip in the **scope row**, after the
  response-field group, separated by `|`. State persists
  on the `DataShape` row (new column) so the operator's
  choice survives navigation + re-download + Settings CSV
  round-trip.
- **By-instrument card** — *not affected by the chip*. That
  CSV is wide-format raw (one row per assignment with a
  per-row `SelfReview` `TRUE` / `FALSE` column already);
  offline filtering is trivial. Adding the chip there would
  duplicate machinery the per-row column already serves.
  (The pre-2026-05-30 By-instrument extract hardcoded
  `SelfReview = FALSE` for group-scoped rows. That bug was
  fixed in PR 3 of `guide/archive/self_review_consolidate.md`
  — the extract now reads the canonical
  `Assignment.is_self_review` column, which carries the
  whole-group rule per `spec/assignments.md` § *Self-review
  policy*.)

**Self-review classification.** The aggregate-fold rule —
which responses count as self-review for the chip's
"include / exclude / both" decision — reads the canonical
`Assignment.is_self_review` column. The column is the source
of truth post-consolidation; every write path keeps it
current via `recompute_self_review_classification`, and the
canonical rule is documented in `spec/assignments.md` §
*Self-review policy* (per-row email match on individual-
scoped instruments; whole-group rule on group-scoped — every
row in a group whose reviewer is a member counts, not just
the `(R, R)` cell).

**Audit event payload.** The `_extracted` events grow a
`context.self_review_handling` scalar slot
(`include_self` / `exclude_self` / `both`) on the canonical
detail envelope. `EVENT_SCHEMAS` entries updated; on
sessions where the chip didn't render and so wasn't
exercised, the slot defaults to `include_self` so the
recorded value still reflects what the file actually
contained.

**Persistence (Data shaper only).** New column
`data_shapes.self_review_handling TEXT NOT NULL DEFAULT
'include_self'` with a check constraint or enum-equivalent
covering the three states. Alembic migration. `DataShape`
model + `DataShapePayload` schema pick up the new field.
`app/services/data_shapes.py` `create_shape` / `update_shape`
plumb it through.

**Settings CSV round-trip.** New key
`data_shapes[N].self_review_handling` in `_data_shape_rows`
+ `_apply_data_shapes`. One round-trip test case per state.

**Resolved clarifying questions (2026-05-30).**

1. **`Assigned` (and `Count`) on `Exclude self` / `Both`
   rows — part of the duplicated block.** `Assigned` and
   `Count` are scoped by self / no-self alongside the
   field-scoped aggregates, so they take the same suffix and
   participate in the `Both` duplication. On `Both` the file
   carries `Assigned_self`, `Count_self`, …, then
   `Assigned_noself`, `Count_noself`, …
2. **Filename suffix on `Both` — `_both`.** Same shape as
   the other two states; the suffix tells a downstream
   consumer at a glance which pool the file represents
   without opening it.
3. **Default state when the chip appears (operator-
   selectable case) — `Include self`.** Matches today's
   behaviour on sessions that already have self-review rows,
   so existing workflows + previously-saved Data shapes
   don't shift silently. The `data_shapes` migration
   defaults to `include_self` for the same reason.

**Still open — flag for follow-up.**

4. **Per-individual rows on the Data shaper.** When the
   shape's row identity is per-individual (Name / Email
   selected), a row's "self-review contribution" is the
   response that individual entered on their own
   self-review. The straightforward read is: the three-way
   chip controls whether that one cell folds into the row's
   aggregates — same rule as the metadata cards, applied to
   the per-individual scope. But the per-individual case
   has a wrinkle that needs more thought (does a row whose
   only response is their own self-review still surface on
   `Exclude self`? as an empty row? not at all? what about
   the `Count` denominator on that case?). Per-tag-combo
   and single-summary rows aggregate across multiple
   individuals so the rule applies pool-wide there — those
   are the unproblematic cases. Revisit before the Data
   shaper side of the slice starts.

### Self-review handling — gap analysis (refreshed 2026-05-30 post-consolidation)

The 5-PR self-review consolidation slice closed
2026-05-30 (`guide/archive/self_review_consolidate.md`,
PRs #1633 → #1637). Refreshing the chip plan against the
codebase as it stands now identifies the precise remaining
gap.

**Foundation — shipped.** Everything the chip's
classification rule + bug-fix scope needed is now in place:

* `Assignment.is_self_review` is the canonical column for
  "is this assignment row a self-review" — written at every
  write path, recomputed at every edit trigger, gated by
  the post-regenerate continuous-gate invariant. The chip
  reads the column directly; no on-the-fly computation
  needed. (`spec/assignments.md` § *Self-review policy*.)
* The latent `by_instrument_extract.py:436` `SelfReview =
  FALSE` hardcode on group-scoped rows retired (PR 3 of
  the consolidation slice). The wide-format extract now
  reads the column; the bug-fix admonition in the
  By-instrument card bullet earlier in this section is the
  history note.

**Remaining gap — 2-3 small PRs.** All chip / route / file-
gen / persistence wiring is still TBD. None of the four
target call sites currently reads / honors a
`self_review_handling` value (verified via grep across
`entity_metadata_extract.py`, `data_shape_extract.py`,
`routes_operator/_extracts.py`, `routes_operator/_extract_data.py`,
`db/models/data_shape.py`, `services/data_shapes.py`,
`session_config_io/{_serialize,_apply}.py`, and the
`session_extract_data.html` template).

#### PR A — Metadata-card chip + filtered extracts

**Scope.** Wires the chip on the Reviewer / Reviewee
response metadata cards + the matching CSV downloads.
No schema change (chip state is one-shot, lives only in
the query string).

**Files.**

* `app/services/extracts/entity_metadata_extract.py` —
  `build_reviewer_metadata(db, review_session, *,
  instrument_ids, all_reviewers)` → grow a
  `self_review_handling: Literal["include_self",
  "exclude_self", "both"] = "include_self"` parameter.
  Per-axis aggregate construction filters the response
  pool by `Assignment.is_self_review` (`include_self` →
  no filter; `exclude_self` → `WHERE NOT
  is_self_review`; `both` → run twice, emit two blocks).
  Column headers gain the `_self` / `_noself` suffix per
  the always-emit rule. Identity columns
  (`ReviewerName`, `ReviewerEmail`, tag columns) keep no
  suffix. `Assigned` and `Count` carry the suffix
  alongside `Mean` / `Median` / `Min` / `Max` / `Length`
  (Q1 resolution). Symmetric edits for
  `build_reviewee_metadata`.
* `app/web/routes_operator/_extracts.py:379-423` (reviewer
  route) + `_extracts.py:426-462` (reviewee route) —
  parse `?self_review_handling=` query param
  (default `include_self`); pass through to the builder;
  derive the filename suffix (`{code}_reviewer_metadata{_suffix}.csv`);
  the data-state preflight runs a cheap server-side query
  for in-scope (instrument-filtered) `include=True`
  responses split by `is_self_review` to decide which
  state is selectable; the response includes a header
  carrying the chip's data-state for the JS to pick up
  on re-derivation (or pre-render in the initial Jinja
  pass — see template).
* `app/services/audit.py:655-660` — both metadata-event
  `EventSchema`s grow the orthogonal `context` slot;
  emit `context={"self_review_handling": <value>}`. (No
  schema-key add needed — `context` is part of the
  canonical envelope set.)
* `app/web/templates/operator/session_extract_data.html` —
  per-card chip row gains a three-way `Self-review
  handling` chip (state machine over the data, locked /
  selectable arms per the table earlier in this section).
  Initial render computes the chip's state server-side
  via the same preflight as the route. JS re-derives on
  every instrument scope-chip toggle so the locked /
  selectable status doesn't drift; the Download button
  href picks up the chip's value.

**Tests.**

* `tests/unit/test_entity_metadata_extract.py` (or new) —
  per state: `include_self`, `exclude_self`, `both`,
  asserting column shapes + aggregates on a session with
  a known self-review pair.
* `tests/integration/test_extracts_reviewer_metadata_route.py` /
  `_reviewee_metadata_route.py` — assert the filename
  suffix per state; the chip-locked data-states
  (only-self / only-non-self / both kinds present);
  audit-event `context.self_review_handling` slot.

**Sized at ~250-400 LOC.**

#### PR B — Data shaper schema + canonical write/read plumbing

**Scope.** Lands the persistence + file-gen surface for
the Data shaper's per-shape chip state. The UI wiring
rides PR C.

**Files.**

* New Alembic migration — `ALTER TABLE data_shapes ADD
  COLUMN self_review_handling TEXT NOT NULL DEFAULT
  'include_self'` + a check constraint (or app-layer
  validation) covering the three valid values. Migration
  picks a fresh hex-id revision.
* `app/db/models/data_shape.py` — `self_review_handling:
  Mapped[str]` field added next to the existing 4
  operator-facing columns.
* `app/schemas/data_shapes.py` (or wherever
  `DataShapePayload` lives) — `self_review_handling:
  Literal["include_self", "exclude_self", "both"] =
  "include_self"` validator added; `extra="forbid"`
  preserved.
* `app/services/data_shapes.py` — `create_shape` /
  `update_shape` plumb the field through; validation
  errors raise `DataShapeValidationError` consistent with
  the existing axis-validation path.
* `app/services/extracts/data_shape_extract.py` —
  `build_shape_rows(db, review_session, shape)` reads
  `shape.self_review_handling` and applies the same
  three-state rule the metadata extracts use. The
  preview-row helpers + `compose_shape_header` emit the
  `_self` / `_noself` suffixes per shipped rule. The
  per-individual wrinkle (Q4 in this section) is the
  one open contract — for PR B, keep the conservative
  interpretation (per-individual rows surface even when
  their only response is the now-excluded self-review,
  with an empty value cell), and pin the final decision
  in a `Q4 RESOLUTION NEEDED` paragraph in the file's
  module docstring so the next contributor sees it.
* `app/web/routes_operator/_extract_data.py` — `GET
  /sessions/{id}/extract-data/shapes/{shape_id}/download.csv`
  derives the filename suffix from
  `shape.self_review_handling`; audit event
  `session.data_shape_extracted` gains `context.
  self_review_handling`.
* `app/services/audit.py:648-650` — `data_shape_extracted`
  `EventSchema` adds `context` to its envelope.
* `app/services/session_config_io/_serialize.py` —
  `_data_shape_rows` emits a new
  `data_shapes[N].self_review_handling` row per shape.
* `app/services/session_config_io/_apply.py` —
  `_DataShapeSpec` gains the field; `_apply_data_shape_kv`
  parser routes the new key; default value
  `include_self` when the key is absent (import from a
  pre-PR-B Settings CSV stays clean).

**Tests.**

* `tests/unit/test_data_shape_model.py` — column default
  + non-null assertion.
* `tests/unit/test_data_shapes_service.py` — CRUD with
  each of the three states; validation rejects unknown
  strings.
* `tests/unit/test_data_shape_extract.py` — per-state
  shape coverage including the `both` column-block
  duplication.
* `tests/unit/test_data_shapes_settings_roundtrip.py` —
  round-trip the new key for each state.
* `tests/integration/test_data_shapes_routes.py` —
  POST/PATCH accept the field; download.csv emits the
  filename suffix.

**Sized at ~400-600 LOC.**

#### PR C — Data shaper UI chip + scope-row wiring

**Scope.** Adds the chip to the Data shaper scope row +
JS state-machine over the persisted column.

**Files.**

* `app/web/templates/operator/session_extract_data.html` —
  scope row grows a `Self-review handling` chip after the
  response-field group, separated by `|`. The chip is a
  three-state pill cluster (or a single pill that cycles
  through the three states; pick whichever reads more
  naturally — both have precedent in the existing chip
  vocabulary). On render: the server passes
  `shape.self_review_handling` per sub-card; the JS
  reflects it. On `Edit` of a saved card,
  `restoreShapeChipState` syncs the chip; on save,
  `persistShape` includes the chip value in the payload;
  on chip toggle, `rebuildPreviewRow` re-derives the
  preview headers with the new suffixes (data-state
  preflight runs client-side from a server-pre-computed
  per-(instrument, field) `has_self / has_noself` map
  passed as `data-shape-self-review-data-state` JSON).
  Filename suffix picked up via the existing
  `data-shape-id`-driven Download anchor (server route
  already returns the suffix; PR B). The chip carries
  the same lock-when-no-edit-mode behaviour as the
  existing scope chips (the
  `data-shaper-chips-locked="true"` attribute on the
  outer card already covers it via the CSS rule shipped
  in #1638).
* `app/web/routes_operator/_extract_data.py` — page
  context grows the per-(instrument, field) self-review
  data-state map for the JS preflight; PATCH/POST
  response includes the saved `self_review_handling`
  + the updated `column_headers` so the front-end
  preview can re-render the suffixed header row.

**Tests.**

* `tests/integration/test_data_shapes_routes.py` — page-
  render carries the chip + its initial state; saved
  shapes render the chip in the correct state per
  persisted column.

**Sized at ~300-500 LOC.**

#### Open question still to resolve before PR B

**Q4 — per-individual rows on the Data shaper.** The
straightforward read is: the chip controls whether the
individual's self-review cell folds into their aggregates,
same rule as the metadata cards. The wrinkle is what
happens when the individual has *only* their self-review
response — does the row surface on `Exclude self`? as
empty? Or does it drop entirely? PR B can ship the
conservative version (row surfaces; `Count`/`Mean`/etc.
empty; `Assigned_noself` honest about there being zero
non-self pairs assigned to that individual on this
instrument scope), and a later micro-PR can switch to
"drop the row entirely on `Exclude self`" if that's
preferred. The doc-only resolution should pin this
before PR B starts.

#### Sequencing

* **PR A is independent.** Metadata-card chip can land
  first or last; no schema change, no dependence on PR B.
* **PR B before PR C.** UI can't read a column that
  doesn't exist. PR B lands the column; PR C wires the
  UI. PR B's UI surface stays inert until PR C ships
  (saved shapes write `include_self` per the default;
  existing behaviour preserved).
* **Q4 resolved before PR B starts.** Either a doc-only
  follow-up to this section (preferred) or a one-line
  decision pinned at the top of PR B's plan.

#### Blast radius

* PR A: ~250-400 LOC across 4 files + 2 test files.
* PR B: ~400-600 LOC across 7 files + 5 test files.
* PR C: ~300-500 LOC across 2 files + 1 test file.

The slice closes when all three PRs ship + this section
moves into `guide/archive/extract_data.md`.

### The three lenses on the new page (legacy framing)

The original plan called these "By instrument / By reviewer /
By reviewee". As shipped, the by-reviewer / by-reviewee
lenses retired and the cards became **Reviewer response
metadata** / **Reviewee response metadata** (metadata, not
data — see the rationale above). The by-instrument lens
stayed and is fully wired today. The table below remains for
historical context.

| Lens | Shape | Use case |
|---|---|---|
| **By instrument** | One CSV per instrument; rows = (reviewee × reviewer) pairs for that instrument; columns = response fields side-by-side. Plus a "All instruments unified" download that matches today's `responses.csv`. | "How did everyone score on this rubric?" Cross-reviewer comparison on one instrument. |
| **By reviewer** | One CSV per reviewer; rows = every response that reviewer made; columns include instrument / reviewee / field / value. Plus a per-reviewer summary roll-up (one row per reviewer, completion + counts). | "What did this reviewer produce?" Individual reviewer audit / coaching. |
| **By reviewee** | One CSV per reviewee; rows = every response made *about* that reviewee; columns include reviewer / instrument / field / value. Plus a per-reviewee summary roll-up (one row per reviewee, aggregated counts / averages where numeric). | "What did everyone say about this reviewee?" Feedback packet for the reviewed person. |

Each lens offers:

- A **single combined download** (one CSV across all instruments / reviewers / reviewees in that lens) for analyst-tool ingestion.
- A **per-entity zip** (one CSV per instrument / reviewer / reviewee) for human-readable handoff.

Self-review / group-scoped semantics carry over from the
existing `responses.csv`:

- `SelfReview` flag stays available in every lens.
- Group-scoped instruments collapse to one row per
  (reviewer × group × field), same as today's
  `serialize_responses_for_instrument`.

### What the new page does NOT do

- **No charts, no aggregates beyond simple roll-ups.** Means
  (averages, counts, completion %) only when they're cheap
  CSV columns. No histograms, no rendered tables-as-images.
- **No row-level filtering UI.** Operators get whole-session
  cuts along three axes; finer slicing happens offline. (If
  operator demand surfaces later, a future iteration can add
  filters; the stub deliberately leaves them out to keep the
  first version small.)
- **No exports of audit / lifecycle metadata.** Audit log
  download already lives at Sys Admin per industry best
  practice (`docs/status.md` Segment 16A notes); the new
  page stays response-data only.

## Open design questions (resolved 2026-05-29)

1. **Per-reviewer / per-reviewee single CSV vs zip of CSVs —
   one big CSV.** The single-CSV shape ships; the
   zip-of-N-per-reviewer or per-reviewee handoff use case
   belongs to the eventual Participant model (each
   participant fetches their own data through the
   participant surface), not to a bulk-CSV download here.

2. **Numeric roll-ups.** Resolved on the metadata cards
   directly — `Count`, `Mean`, `Median`, `Min`, `Max`,
   `Length` all ship as toggleable chips. The Data shaper
   inherits the same vocabulary for its aggregate column
   chips.

3. **Group-scoped reviewee semantics — one row per group
   identity.** The composed name from
   `_compose_group_identity` is sufficient; no
   "by group member" fan-out at this layer.

4. **The Zip-all on Session Home post-split — settings
   only.** The Session Home Extract-setup card's `Zip all`
   bundles just `settings.csv` (the Reviewers / Reviewees /
   Relationships rows ship as individual downloads, not in
   the home bundle). Response-data zips live on the new
   Extract data page.

5. **Settings.csv stays on Session Home — yes.** It's the
   round-trippable surface Quick Setup ingests, so it
   belongs in the home Extract setup card.

## Blast radius (rough estimate, pre-execution)

- **New page surface** — `app/web/routes_operator/_extract_data.py`
  (new), `app/web/templates/operator/session_extract_data.html`
  (new), `app/web/views/_extract_data_page.py` (new — view-shape
  adapter). Three new files, maybe ~500-800 LOC total.
- **Existing card rename** — `app/web/views/_extract_data.py`
  (rename internal vars / strings to "Extract setup"; drop the
  Responses row; rewire bundle to four CSVs),
  `app/web/templates/operator/partials/_extract_data_card.html`
  (rename, drop responses row), `app/web/templates/operator/
  session_detail.html` (include path stays if file is renamed
  in place).
- **Top nav** — `app/web/templates/operator/partials/
  session_top_nav.html` (add the new tab + extend `_ops_pages`).
- **Bundle builder** — `app/services/extracts/zip_bundle.py`
  (drop responses from the home bundle; add new bundles for
  the response-data page lenses).
- **Tests** — likely 6-10 new tests (each lens × single vs zip
  × happy path; plus a few permission / lifecycle tests).
- **Spec docs** — `spec/session_home.md` (rename card),
  potentially a new `spec/extract_data.md` (or fold into an
  existing operator-page spec) for the new page.

Estimate: **3-4 PRs**:

1. Rename the Session Home card to **Extract setup**; drop
   the Responses row from it; rewire the Zip-all bundle to
   four CSVs. (Mechanical; no new routes.)
2. Add the new **Extract data** tab + route stub; render an
   empty page with the three-lens skeleton + tile placeholders.
3. Wire the **by-instrument** lens (mostly re-uses
   `serialize_responses_for_instrument`).
4. Wire the **by-reviewer** + **by-reviewee** lenses
   (new serialisers; reuse the response query / group-scope
   collapsing machinery).

PR 1 is independent of 2-4 and can land first to clean up
the Session Home surface.

## Sequencing

- **Independent of the queued schedule.** Doesn't block or
  depend on URL remodel / 14B / 19 / 20.
- **Best after URL remodel.** If URL remodel lands first,
  any internal links from the new page to the reviewer
  surface ship with `/me/` prefixes from day 1.
- **Independent of the participant model.** The new page is
  operator-only; nothing in it presumes reviewee or observer
  identities.
- **Independent of 14B.** No email surface; no outbox
  interaction.

## Risk acceptances

- **Operators who scripted against the Zip-all bundle
  expecting Responses inside.** Beta-state → no real scripts
  → break cleanly. The new page exports the same data
  shaped better; the responses Zip-all button is the direct
  replacement.
- **Filename change: ``{code}_bundle.zip`` →
  ``{code}_setup.zip``.** Same rationale — beta-state, no
  scripts to break. The new ``{code}_responses.zip`` covers
  the response-data side.
- **URL shape collisions.** `extract-data` as a tab slug
  doesn't collide with existing routes
  (`/operator/sessions/{id}/extract-data` is unused per
  `grep`).
- **Card vs page name confusion.** "Extract setup" (card on
  Home) vs "Extract data" (Operations tab) — distinct enough
  that the operator won't conflate them. The card label
  carries the setup-portability framing; the tab label
  carries the analysis-shaping framing.

## Done when

- Session Home card label reads **Extract setup**; its row
  list is Reviewers / Reviewees / Relationships / Session
  settings / Zip-all-of-four; the Responses row is gone.
- A new **Extract data** tab appears in the Operations strip
  between Responses and the end of the strip.
- The Extract data page surfaces three lens sections
  (by instrument / by reviewer / by reviewee) with at least
  a single CSV per lens and (recommended) a zip-of-N
  per-entity bundle per lens.
- Group-scoped collapsing and the `SelfReview` flag carry
  over to the new lenses.
- Existing `/operator/sessions/{id}/export/responses.csv`
  route stays live (the by-instrument unified CSV redirects
  here or reuses the same serialiser); operators with
  pre-existing direct-URL habits don't 404.
- Full suite passes (existing extracts tests unchanged;
  new tests added for the new lenses).
- `guide/extract_data.md` → `guide/archive/` per the
  segment-closeout convention; `spec/session_home.md`
  updated for the card rename; a new spec doc (or section)
  covers the page if not already.

## Related context

- `app/web/views/_extract_data.py` — the current Session
  Home card view adapter (becomes "Extract setup").
- `app/web/routes_operator/_extracts.py` — existing CSV
  routes (`/sessions/{id}/export/{kind}.csv`); new routes
  may reuse these or sibling-mount under
  `/sessions/{id}/extract-data/...`.
- `app/services/extracts/responses_extract.py` — existing
  serialisers: `serialize_responses` (unified),
  `serialize_responses_for_instrument` (by-instrument lens
  is mostly this), `serialize_reviewer_session_summary`
  (already wired for the reviewer-side surface; by-reviewer
  operator lens reuses the same shape).
- `spec/session_home.md` — Session Home page spec; the card
  rename lands here.
- `guide/url_remodel.md` — landing this first means internal
  links in the new page ship with the future-correct URL
  prefix on day 1.
