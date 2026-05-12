# Segment 15A — Pervasive friendly labels

**Status:** Plan rewritten 2026-05-12 (full refresh).
**Sizing:** ~3 PRs (Slice 4 dropped — see below).
**Depends on:** none. Schema + Settings-CSV round-trip already in
place; see "Already shipped" below. Lands cleanly any time after
the major refactor (merged 2026-05-09).
**Recommended order:** before 15B. The session-level label
resolver this segment introduces is consumed by every header /
preview that 15B's per-instrument assignments UI would otherwise
need to duplicate.

---

## Codebase audit (2026-05-12)

Confirmations and corrections from a read-through against the
current `main`:

- **No Save / Edit lock card on Reviewers / Reviewees /
  Relationships pages.** The Instruments-page Edit/Save state
  machine doesn't exist on these three. They carry only a
  `<div class="card lock">` that renders when
  `is_ready` and links to revert-to-draft. The "Edit X" links
  in their right-column CSV upload card are disabled
  placeholders (`title="Inline editing — coming soon"`).
  Slice 3 gates its editor on `is_ready` directly; no new lock
  card.
- **`InstrumentDisplayField.label` is round-tripped via Settings
  CSV today** at `session_config_io.py:357` (emit) and `:967`
  (apply). Slice 1 retires both: drop the `.label` row from
  `_display_field_rows` and silently ignore `.label` keys in
  the apply phase (tolerated on legacy import, dropped). This
  keeps the Settings CSV minimal and aligned with the
  resolver-only model.
- **Response Fields also has a `Friendly Label` column** on the
  Instruments page (`instruments_index.html:445`). This is the
  operator-typed *question text* (e.g. "How clearly do they
  explain ideas?") — per-instrument, not a session-wide
  rename. **15A does not touch this column**; it stays
  editable and continues to round-trip via Settings CSV
  (`instruments[N].response_fields[M].label`).
- **Two write paths for Display Field labels** in the current
  codebase: the bulk-save form at `/sessions/{id}/
  instruments/{instrument_id}/fields/save` (line 282 of the
  template) and the per-row endpoint
  `/display-fields/{df_id}/edit` (`_instruments.py:458`). Both
  call `instruments.update_display_field(..., label=...)`.
  Slice 2 drops `label` from both POST handlers; the
  underlying `update_display_field(label=...)` parameter stays
  for backward source compatibility but defaults to "" and
  becomes a no-op once the template stops sending it.
- **Reviewer-surface column headers resolve at view-build
  time**, not in the template. `review_surface.html:199` reads
  `header.label` where `header` is built by a view adapter in
  `app/web/views/`. Slice 2 must thread the resolver through
  the view-build step so the label flows in before the
  template renders.
- **Reviewer-tag labels are operator-surface-only.**
  `_VALID_DF_SOURCE_TYPES = {"reviewee", "pair_context"}` —
  `reviewer.*` is **never** a Display Field source. The
  Reviewers-page editor's three slots
  (`reviewer.tag_1` / `.tag_2` / `.tag_3`) only feed operator
  preview tables (Reviewers Setup, Assignments reviewer-tag
  block) and Email Previews; they never appear on the
  reviewer surface or inside an Instrument editor. Slice 2's
  reviewer-surface sweep only touches reviewee / pair_context
  labels.
- **`_DEFAULT_DISPLAY_LABELS` covers reviewee + pair_context
  only.** Slice 1's `_DEFAULT_LABELS` (its successor in
  `field_labels.py`) widens to the full 12-slot set including
  reviewer tags.

---

## Goal

Let operators rename a fixed set of session fields **once per
session** and have the friendly label flow through every
**display** surface that names those fields — operator preview
tables, Instrument editor Display Field rows, Email Previews,
and the reviewer surface. The underlying logic everywhere keeps
referring to the canonical machine names (Rule Builder, source
picker, CSV importers, validators, audit events).

### In-scope fields (12 slots max per session)

| `source_type`   | `source_field`(s)                                              | Slots |
| --------------- | -------------------------------------------------------------- | ----- |
| `reviewer`      | `tag_1`, `tag_2`, `tag_3`                                      | 3     |
| `reviewee`      | `name`, `email_or_identifier`, `tag_1`, `tag_2`, `tag_3`, `profile_link` | 6     |
| `pair_context`  | `1`, `2`, `3`                                                  | 3     |

`ReviewerName` and `ReviewerEmail` are **not** renamable —
they're operator-only data, never surfaced to reviewers or in
externally-facing displays, and the operator never needs an
alias to remember what they stand for in the session's context.

`AssignmentContext1-3` is **out of scope and unreachable**: the
`Assignment.context` JSON column was retired in Segment 15D PR
6b, and `_VALID_FL_SOURCE_TYPES` in `session_config_io.py`
already encodes `{"reviewer", "reviewee", "pair_context"}` only.

---

## Already shipped — what's left for 15A

Pre-positioned in earlier segments, **inert until this segment**:

- **Schema.** `session_field_labels` table + `SessionFieldLabel`
  model landed in **Segment 13D PR 1** (Alembic revision
  `d81faacee836_segment_13d_pr1_session_field_labels`).
  `source_type` / `source_field` are `VARCHAR(32)` /
  `VARCHAR(64)` with `UNIQUE (session_id, source_type,
  source_field)`. Generic enough for the 12-slot scope above —
  no migration.
- **Settings CSV round-trip.** `app/services/session_config_io.py`
  already serialises / parses / applies
  `field_labels.{source_type}.{source_field}` rows end-to-end
  (Segment 12A-3 PR 3 absorbed the apply half).
  `_VALID_FL_SOURCE_TYPES = {"reviewer", "reviewee",
  "pair_context"}` is locked in; the source-field allowlist is
  permissive (no enum gate), so the resolver and editors just
  start writing the new slots without touching the export
  shape.

Still to land in 15A:

- **Slice 1** — `app/services/field_labels.py` resolver +
  `session_field_label.set` / `.cleared` audit emitters +
  validator widening in `session_config_io.py` to accept the
  new reviewee source-fields (`name`, `email_or_identifier`,
  `profile_link`) + retire the
  `instruments[N].display_fields[M].label` Settings-CSV
  round-trip (the per-instrument override goes away — see
  "Display-Field label retirement" below).
- **Slice 2** — Sweep hardcoded literals out of every
  display-layer surface; flip the Instrument editor's
  `Friendly Label` column to read-only; thread the resolver
  through the reviewer-surface view-build step (not just the
  template).
- **Slice 3** — Per-page inline label editors above the
  Reviewers / Reviewees / Relationships tables. Gated by
  session lifecycle (`is_ready`) — the same control the page's
  existing `.card.lock` already uses to message "revert to
  draft to modify". There is **no** Save/Edit lock card on
  these pages today (the Instruments-page pattern doesn't
  apply); the friendly-label editor doesn't need one.

---

## Display vs logic — sweep boundary

Friendly labels are a **display-layer** concern only. The
underlying logic everywhere keeps assuming the canonical machine
names. Today's per-instrument Display Field labels already
follow this separation (operator-typed `label` for the column
header, `(source_type, source_field)` for the value lookup);
15A generalises the same idea to the session level.

### In scope — display layer

- **Operator preview tables** on the Setup pages —
  `session_reviewers.html`, `session_reviewees.html`,
  `session_relationships.html`. Column headers for the in-scope
  fields render the friendly label.
- **Operator Assignments-page tag columns** in
  `session_assignments.html` (reviewer-tag block + reviewee-tag
  block + pair-context block).
- **Email Previews** tag / pair-context columns + the
  reviewer-surface preview reuse.
- **Instrument editor's Display Fields table.** Today the
  table has a `Source` column (canonical name) and an editable
  `Friendly Label` column. **15A retires the per-instrument
  editable input but preserves both columns**: `Source` keeps
  its current cell, and `Friendly Label` becomes a read-only
  cell that auto-populates from `field_labels.resolve(...)`.
  The single source of truth for a Display Field's friendly
  label becomes the session-wide setting managed on the
  Reviewers / Reviewees / Relationships pages.
- **Per-instrument Display Field cell headers** (reviewer-
  surface preview + Email Previews reuse) follow the same
  resolver chain — they read the session-wide friendly label
  directly. No per-instrument override layer.
- **Reviewer surface** review page column headers (tag /
  pair-context / identity rows in the reviewee-context block).

### Out of scope — logic layer (canonical names stay)

- Rule Builder operand pickers + `_render_*_sentence` helpers
  in `app/web/views/_rule_builder.py`.
- Display Field source picker on the Instruments edit page —
  the operator is picking *which underlying field* to add as a
  column; the picker shows canonical names. The per-instrument
  override capability is retired in 15A (see Instrument editor
  bullet above), so the picker just controls
  `(source_type, source_field)`.
- CSV-import column-name docs, header validation, and
  parse-error copy. Importers want the machine name
  (`RevieweeTag1`).
- Validation error messages anywhere in the codebase.
- Audit-event payloads. `session_field_label.set` writes
  `source_type` + `source_field` + new `label`; the resolver is
  a render-time concern.

### Render shape — per surface

- **Operator preview tables (Reviewers / Reviewees /
  Relationships / Assignments / Email Previews).** Two-line
  header cell when a friendly label is in effect:

  ```
  Lab section
  RevieweeTag1
  ```

  Friendly label on top in the normal header weight; canonical
  name beneath as `.muted` subtext. When no friendly override
  is set, the cell stays single-line with the canonical-as-it-
  is-today rendering (`Tag 1`). This keeps operators oriented
  to the canonical name while picking up their own rename.
- **Instrument editor's Display Fields table.** Two columns:
  `Source` shows the canonical name (e.g. `RevieweeTag1`,
  `RevieweeName`), `Friendly Label` shows
  `field_labels.resolve(source_type, source_field)` as a
  read-only cell. No input box, no per-instrument override.
  Operators who want to rename navigate to the Reviewers /
  Reviewees / Relationships page and edit there; the change is
  picked up on next render of every Instrument that uses the
  field.
- **Reviewer surface.** Friendly label only, single-line. No
  canonical suffix. When no friendly is set, falls back to the
  built-in default (e.g. `Tag 1`, `Name`, `Email`); reviewers
  never see `(RevieweeTag1)` orientation text.

---

## Approach

### Slice 1 — Resolver + audit emitters + validator widening (1 PR, ~150 LOC)

**No migration.** `session_field_labels` is already in place
with the shape this slice needs.

New service module `app/services/field_labels.py`:

```python
def resolve(
    session, source_type: str, source_field: str
) -> str: ...
def all_labels(
    session,
) -> dict[tuple[str, str], str]: ...
def upsert(
    db, session, *,
    source_type: str, source_field: str, label: str,
    user, correlation_id,
) -> SessionFieldLabel: ...
def clear(
    db, session, *,
    source_type: str, source_field: str,
    user, correlation_id,
) -> None: ...
```

`resolve` reads session-wide friendly label → built-in default
(`_DEFAULT_LABELS` table moved here from `_display_fields.py`)
→ fallback (`source_type:source_field`). One per-session dict
materialised per request via the existing per-request session
scope in `app/web/deps.py`.

**Single resolver chain** for every display-layer callsite:

1. `field_labels.resolve(...)` (session-wide friendly)
2. Built-in default in `_DEFAULT_LABELS`
3. `f"{source_type}:{source_field}"` (last-resort fallback)

Per-instrument override removed from the chain. The
`InstrumentDisplayField.label` column stays in the schema
(no destructive migration) but Slice 2 stops reading it; the
cell header on every surface (operator preview tables,
Instrument editor's read-only Friendly Label column, reviewer
surface, Email Previews) reads from the session-wide resolver
only. A follow-on cleanup segment can drop the dead column
once the pilot confirms no surprises.

**`_DEFAULT_LABELS` widens** to cover the new reviewee
identity slots (`name = "Name"`, `email_or_identifier = "Email"`,
`profile_link = "Profile"`) and the reviewer tag slots
(`reviewer.tag_1 = "Tag 1"` etc., which today aren't in
`_DEFAULT_DISPLAY_LABELS` at all).

Audit emitters: `session_field_label.set` / `.cleared`.
Register in `app.services.audit.EVENT_SCHEMAS` using the
canonical envelope (changes envelope for set, snapshot envelope
for cleared).

**Validator widening.** `_VALID_FL_SOURCE_TYPES` stays
`{"reviewer", "reviewee", "pair_context"}`. Add a parallel
source-field allowlist scoped per source type:

```python
_VALID_FL_SOURCE_FIELDS = {
    "reviewer":     {"tag_1", "tag_2", "tag_3"},
    "reviewee":     {"name", "email_or_identifier",
                     "tag_1", "tag_2", "tag_3", "profile_link"},
    "pair_context": {"1", "2", "3"},
}
```

`_parse_rows` validates each `field_labels.*` row against this
map; rows for `reviewer.name` etc. (out of scope) produce a
named parse error. This is the gate that keeps the
session_field_labels table aligned with the 12-slot intent —
the DB doesn't enforce it, the import does.

### Display-Field label retirement in Settings CSV

The `instruments[N].display_fields[M].label` row currently
emitted by `_display_field_rows` (`session_config_io.py:357`)
goes away in this slice. Two-part retirement:

- **Stop emitting** — `_display_field_rows` no longer appends
  the `.label` row. Existing exports without that row continue
  to import cleanly; new exports are simply shorter.
- **Tolerated on apply** — `_parse_rows` continues to recognise
  `instruments[N].display_fields[M].label` as a known key (so
  legacy Settings CSVs import without errors) but the apply
  phase silently drops the value. The model column stays in
  the schema as dead data; the resolver chain doesn't read it.

Response Fields' `.label` round-trip stays unchanged — it's
the per-instrument question text and is not a 15A concern.

### Slice 2 — Display-layer sweep (1 PR, ~20-25 callsites)

Touch only the display surfaces listed in the "In scope"
section above. The "Render shape — per surface" subsection is
the source of truth for what each cell looks like.

Key callsites:

- `app/services/instruments/_display_fields.py::display_field_label`
  — delegate to `field_labels.resolve` per the (3-step) chain
  above. Stops reading
  `InstrumentDisplayField.label` even when non-empty; the
  column is preserved in the schema as dead data pending a
  follow-on cleanup segment.
- Setup-page table headers — `session_reviewers.html`,
  `session_reviewees.html` (currently literal `"Tag 1"` /
  `"Tag 2"` / `"Tag 3"` for tags, and unstyled column headers
  for Name / Email / Photo), `session_relationships.html` for
  the pair-context columns.
- `session_assignments.html` reviewer + reviewee tag column
  headers (today: literal `"Tag1"` / `"Tag2"` / `"Tag3"` in two
  blocks plus a pair-context block).
- Email Previews + reviewer-surface preview — share the same
  view adapter as the operator tables; the adapter renders
  two-line for operator surfaces and friendly-only for the
  reviewer surface based on a `surface=` parameter. The
  reviewer surface resolves headers at **view-build time**
  (`review_surface.html:199` reads `header.label`, where
  `header` is built in `app/web/views/`) — the resolver call
  threads through the view-builder, not the template.
- Instrument editor's Display Fields table — convert the
  editable `Friendly Label` cell to a read-only cell rendering
  `field_labels.resolve(...)`. Drop the form input from
  `instruments_index.html` (line ~309). Two POST endpoints
  feed this column today and both stop accepting `label`:
  - `POST /sessions/{id}/instruments/{instrument_id}/fields/save`
    (bulk save) — drop the `label` field from the form-row
    payload.
  - `POST /sessions/{id}/instruments/{instrument_id}/display-fields/{df_id}/edit`
    (`_instruments.py:458`) — drop the `label` parameter.
  The `instruments.update_display_field(..., label="")`
  parameter stays for source compatibility but defaults to
  empty so `instrument.display_field_updated` audit events
  with a label-only change become unreachable from the UI.
  Keep the `Source` column rendering as today. **Response
  Fields' `Friendly Label` column stays editable** — it's
  per-instrument question text, not a session-wide rename.

New view-adapter helper (likely in `app/web/views/_filters.py`
or a new sibling) carries the `(friendly, canonical)` pair and
a render mode (`operator_two_line` vs `reviewer_friendly_only`)
so templates stay shape-agnostic.

**Explicitly not swept (logic layer):**

- `app/web/views/_rule_builder.py` operand sentences + pickers.
- Display Field source picker on Instruments edit.
- CSV-import header docs + parse-error copy.
- Validation error messages.
- Audit-event payloads.

The 13B sort-button `aria-label` strings (e.g. `"Sort by
Reviewer Tag1"`) follow in a polish PR after Slice 3; out of
Slice 2's blast radius.

### Slice 3 — Per-page inline editors (1 PR, ~250 LOC)

Three editors, one per relevant Setup page, each scoped to that
page's `source_type`:

- **Reviewers Setup page** — single 3-cell row above the table:
  `Tag 1` / `Tag 2` / `Tag 3`. Edits
  `source_type="reviewer"`.
- **Reviewees Setup page** — **two stacked rows** above the
  table, six inputs total. Top row: `Name` / `Email` / `Photo`
  (identity). Bottom row: `Tag 1` / `Tag 2` / `Tag 3`. Edits
  `source_type="reviewee"`.
- **Relationships Setup page** — single 3-cell row above the
  table: `Pair context 1` / `Pair context 2` / `Pair context
  3`. Edits `source_type="pair_context"`.

Each cell renders as `<label>Default: <input
placeholder="DefaultLabel"></label>` — placeholder text is the
built-in default from the resolver. A single Save button at the
bottom of the editor block commits all of that page's slots in
one POST (3 or 6 fields depending on page). Empty input → clear
the override (delete the row) and re-display the default
placeholder. Non-empty input → upsert.

**Lifecycle gating.** These three pages don't carry a
Save / Edit lock card today (that pattern lives on
Instruments). 15A doesn't add one. Instead the editor is
gated directly on `is_ready`:

- `is_ready == True` (session active or closed) — inputs
  render `disabled`, no Save button. The page's existing
  `<div class="card lock">` already messages
  "revert to draft to modify"; the editor block sits inside
  the same scope and matches that locked state.
- `is_ready == False` (draft / validated) — inputs editable,
  Save button visible.

Visually the editor block sits in a card-section above the
table inside the page's existing card frame. The Reviewees
two-row layout (identity row + tags row) shares one form +
one Save button.

**Lifecycle gate.** Editing labels invalidates `validated` via
`lifecycle.invalidate_if_validated`. Same hook every other
setup mutation calls.

**Audit.** Each per-slot change emits
`session_field_label.set` (or `.cleared` if the new value
empties an existing row). One audit event per modified slot per
Save — keeps the audit log readable when an operator renames
several at once.

**No Settings-page subsection.** Labels live with the entities
they describe.

### Slice 4 — dropped 2026-05-12

`AssignmentContext1-3` is out of scope. The
`Assignment.context` JSON column those keys lived on was
retired in **Segment 15D PR 6b** — the schema no longer carries
them anywhere. `_VALID_FL_SOURCE_TYPES` in
`session_config_io.py` already encodes the supported set. If a
real use case for logic-bearing per-assignment fields surfaces
later, it gets its own plan (schema + rule-engine integration +
UI) — not a retrofit onto the labels segment.

---

## Round-trip — Settings CSV only

Field labels round-trip exclusively through the Settings CSV
that `session_config_io.py` already emits / consumes. **No
changes to per-entity CSVs** (Reviewers / Reviewees /
Relationships); their header rows stay canonical so importers
that key on `RevieweeTag1` etc. continue to work.

### Why Settings CSV, not per-entity

- Field labels are session-level config (12 rows max), not
  per-row data. Per-entity CSVs are row-oriented; embedding
  column-metadata in row-data forces awkward encodings
  (parenthetical headers, sidecar columns, metadata rows) that
  don't round-trip cleanly through Excel.
- The plumbing already exists end-to-end via 12A-3 PR 3. 15A
  widens the source-field allowlist (Slice 1) and starts
  populating the rows (Slice 3); the export shape stays
  byte-stable.
- One file to coordinate, not three. Settings CSV is already
  the one-stop shop for porting a session across deployments
  (session.name, deadline, instruments, RTDs, rule sets, email
  overrides). Field labels join the same file.
- 14B (eventual bundled session export) reads Settings CSV as
  the canonical config source. Keeping labels there means the
  bundle Just Works.

### What the operator sees in CSV

Settings-CSV row shape (no change from today, just new keys):

```
field_path                              ,value             ,data_type
field_labels.reviewee.name              ,Student name      ,string
field_labels.reviewee.tag_1             ,Lab section       ,string
field_labels.pair_context.1             ,Module reference  ,string
```

Per-entity CSVs unchanged — `RevieweeTag1` still names that
column in `reviewees.csv`. An operator wanting to see their
rename map while editing per-entity files in Excel opens
`settings.csv` alongside, or glances at the operator UI.

### Mitigation if self-documentation becomes a pain point

The pilot may surface a real need for per-entity CSVs to carry
the friendly labels too (e.g. mailing the CSVs around without
also mailing settings.csv). If so, the right follow-on is a
**read-only commented header line** at the top of per-entity
CSVs that names the friendly labels — additive, never parsed
on import, never affects round-trip. Out of scope for 15A.

---

## Risks + open questions

- **Migration safety.** Not applicable — schema landed inert in
  13D PR 1 and the `ci-postgres` job has been round-tripping
  the table since.
- **Sweep reach.** Slice 2 needs to cover every display-layer
  callsite named above. A `grep` audit at Slice 2 close lists
  every hit; the reviewer triages each into "display layer
  (sweep)" or "logic layer (intentionally canonical)" using the
  boundaries in the "Display vs logic" section. Expect Rule
  Builder + source picker + CSV-import error copy + a few
  validation helpers to remain canonical — that's the desired
  state.
- **Reviewer-side surface.** Reviewers see the reviewer-surface
  review page only; they don't see operator preview tables.
  Sweep covers the reviewer-surface column headers (per-
  instrument Display Field cells) — the friendly label
  resolver flows through `display_field_label` so the same
  callsite handles both surfaces.
- **13B aria-labels.** Sort-button `aria-label` strings added
  in Segment 13B PR 5 (`"Sort by Reviewer Tag1"` etc.) follow
  in a polish PR after Slice 3 to keep Slice 2's blast radius
  small.
- **`InstrumentDisplayField.label` retired as a render
  source.** Slice 2 stops reading the column even when
  non-empty; the resolver chain collapses to session friendly
  → built-in default → fallback. The column stays in the
  schema as dead data — no destructive migration, no
  backward-compat shim. Existing rows that carry an override
  silently lose effect on the next render. Acceptable because
  there's no production-pilot data yet; the Instrument editor
  no longer exposes the input so the override path is
  unreachable post-15A. A follow-on cleanup segment can drop
  the column once the pilot confirms no surprises.
- **Audit-emitter retirement.**
  `instrument.display_field_updated` no longer fires for
  changes to `label` (the change-set will be empty for a
  label-only edit because the column isn't editable
  anymore). Other Display-Field mutations (`source_type`,
  `source_field`, `visible`, `order`) keep their existing
  audit emissions.

---

## Critical files

- **New:** `app/services/field_labels.py` (Slice 1 resolver).
- **Touched (Slice 1):**
  `app/services/instruments/_display_fields.py` (move
  `_DEFAULT_DISPLAY_LABELS` → `_DEFAULT_LABELS` in
  `field_labels.py` and widen with reviewer-tag slots;
  delegate `display_field_label`), `app/services/audit.py`
  (`EVENT_SCHEMAS` registrations for `session_field_label.set`
  / `.cleared`), `app/services/session_config_io.py`
  (`_VALID_FL_SOURCE_FIELDS` map + `_parse_rows`
  source-field validation; **retire
  `instruments[N].display_fields[M].label` emit in
  `_display_field_rows` + tolerate-and-drop on apply**),
  `app/db/models/session_field_label.py` (clear the
  `assignment_context` docstring note).
- **Touched (Slice 2 — display layer only):**
  `app/web/views/_*.py` (column-header view adapter taking a
  `surface=` mode; reviewer-surface view-builder threads the
  resolver into `group.display_fields` so the template's
  `header.label` flows correctly), and the templates that name
  a tag / pair-context / identity column —
  `session_assignments.html`, `session_reviewers.html`,
  `session_reviewees.html`, `session_relationships.html`,
  Email Previews, `reviewer/review_surface.html`. The
  Instrument editor's `Display Fields` table is touched
  separately (`instruments_index.html` lines ~287-318 +
  `app/web/routes_operator/_instruments.py` — both the
  bulk-save endpoint and `instrument_edit_display_field`): the
  `Friendly Label` column flips from an editable input to a
  read-only resolver-backed cell, and both POST handlers stop
  accepting `label`. **Not touched:**
  `app/web/views/_rule_builder.py`,
  `session_rule_builder.html`, Display Field source picker on
  Instruments edit, the **Response Fields** `Friendly Label`
  column on `instruments_index.html` (per-instrument question
  text — stays editable), CSV-import error copy, audit-event
  payloads (other than the `instrument.display_field_updated`
  label-only edit path which becomes unreachable).
- **Touched (Slice 3):**
  `app/web/templates/operator/session_reviewers.html`
  (3-cell editor row above the table),
  `session_reviewees.html` (two stacked rows above the table,
  six inputs total: identity row + tags row),
  `session_relationships.html` (3-cell editor row above the
  table), plus the routes that back these pages
  (`app/web/routes_operator/_setup_rosters.py` — new
  per-page POST handler for the label form, gated on
  `is_ready`). No new Save / Edit lock card on these
  pages — they don't have one today and 15A doesn't add one.

---

## Verification

- `pytest -q` green on SQLite + `ci-postgres`.
- `ruff check .` green.
- New tests:
  - `tests/unit/test_field_labels_resolver.py` — chain
    semantics (session friendly > built-in default > fallback)
    and `_DEFAULT_LABELS` coverage for all 12 slots. Includes
    a pin that an existing non-empty
    `InstrumentDisplayField.label` is no longer consulted.
  - `tests/integration/test_field_labels_routes.py` — set /
    clear / re-set per page, lifecycle invalidation,
    `is_ready` gating (inputs disabled when ready; editable
    when draft/validated), audit emitters.
  - `tests/integration/test_settings_csv_drops_df_label.py` —
    pin that `_display_field_rows` no longer emits the `.label`
    row, and that an import containing legacy
    `instruments[N].display_fields[M].label` rows succeeds
    without writing the value.
  - `tests/integration/test_settings_csv_field_labels_roundtrip.py`
    — round-trip via Settings CSV for the new reviewee
    identity slots (Name / Email / Photo). Should round-trip
    byte-stable.
  - Header-rendering assertions in existing setup-page tests
    (Reviewers / Reviewees / Relationships / Assignments)
    confirming the override appears in the two-line operator
    render and the friendly-only reviewer render.
- `grep` audit at Slice 2 close (callsite sweep gate).
