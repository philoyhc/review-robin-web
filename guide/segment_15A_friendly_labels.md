# Segment 15A — Pervasive friendly labels

**Status:** Plan refreshed 2026-05-12.
**Sizing:** ~3 PRs (Slice 4 dropped — see below).
**Depends on:** none. Schema + Settings-CSV round-trip already in
place (see "Already shipped — what's left for 15A" below). Lands
cleanly any time after the major refactor (merged 2026-05-09).
**Recommended order:** before 15B. The session-level label resolver
this segment introduces is consumed by every header / picker / tooltip
that 15B's per-instrument assignments UI would otherwise need to
duplicate.

---

## Already shipped — what's left for 15A

Pre-positioned in earlier segments, **inert until this segment**:

- **Schema.** `session_field_labels` table + `SessionFieldLabel`
  model landed in **Segment 13D PR 1** (commit / Alembic
  revision: `d81faacee836_segment_13d_pr1_session_field_labels`).
  Columns / indexes / unique constraint match Slice 1 below
  exactly — nothing to migrate.
- **Settings CSV round-trip.** `app/services/session_config_io.py`
  already serialises / parses / applies `field_labels.{source_type}.{source_field}`
  rows end-to-end (Segment 12A-3 PR 3 absorbed the apply half).
  `_VALID_FL_SOURCE_TYPES = {"reviewer", "reviewee", "pair_context"}`
  is locked in. Round-trip is byte-stable on existing exports;
  Slice 1's resolver introducing reads from the table doesn't
  change the export shape.

Still to land in 15A:

- **Slice 1** — `app/services/field_labels.py` resolver +
  `session_field_label.set` / `.cleared` audit emitters in
  `app.services.audit.EVENT_SCHEMAS`.
- **Slice 2** — Sweep hardcoded `"Tag 1"` / `"Tag1"` /
  `"Pair context N"` literals out of every **display-layer**
  surface (operator + reviewer column headers + previews).
  Logic-layer surfaces (Rule Builder, source picker, CSV docs,
  validators, audit logs) keep canonical names — see the
  "Display vs logic" section below.
- **Slice 3** — Per-page inline tag-label editors on Reviewers,
  Reviewees, Relationships (shape reshaped on 2026-05-12 — see
  Slice 3 below).

---

## Goal

Let operators rename `ReviewerTag1-3`, `RevieweeTag1-3`, and
`PairContext1-3` **once per session**, with the friendly label
flowing through every **display** surface that names those fields
— column headers (operator + reviewer) and the reviewer-surface
preview. The underlying logic continues to refer to the canonical
machine names everywhere — no rule, validator, audit emitter,
CSV importer, or operand sentence sees the friendly label.

`AssignmentContext1-3` is **out of scope** and `assignment_context`
is **not** a `source_type` this segment will accept. The
`Assignment.context` JSON column those keys lived on was retired
in Segment 15D PR 6b — the schema doesn't carry them anywhere
anymore. `_VALID_FL_SOURCE_TYPES` in `session_config_io.py`
already encodes this (`{"reviewer", "reviewee", "pair_context"}`).
The "widening to `assignment_context`" docstring note on the
`SessionFieldLabel` model is now a no-op and can be cleared in
the same PR that lights up the resolver.

---

## Display vs logic — sweep boundary

Friendly labels are a **display-layer** concern only. The
underlying logic everywhere keeps assuming the canonical
machine names. The same separation today's per-instrument
Display Field labels follow (operator-typed `label` for the
column header, `(source_type, source_field)` for the value
lookup) generalises to the session-wide rename.

**In scope (display layer — friendly label flows here):**

- Reviewer-surface review page tag / pair-context column
  headers (reviewer-facing display).
- Operator Setup-page table headers — `session_reviewers.html`,
  `session_reviewees.html`, `session_relationships.html`.
- Operator Assignments-page reviewer + reviewee tag column
  headers (`session_assignments.html`).
- Email Previews tag / pair-context columns + reviewer-surface
  preview reuse.
- Per-instrument Display Field cell headers — the existing
  per-instrument `InstrumentDisplayField.label` override stays
  the highest-priority source; the session-wide friendly label
  becomes the next-highest fallback before the canonical
  default.

On operator-facing display surfaces, render as
`{friendly_label} ({CanonicalName})` whenever an override is
in effect — operators see their rename plus the canonical name
in muted parens for orientation. On reviewer-facing surfaces,
render the friendly label alone (reviewers don't need the
canonical orientation).

**Out of scope (logic layer — canonical names stay):**

- Rule Builder operand pickers + `_render_*_sentence` helpers
  in `app/web/views/_rule_builder.py`. Predicate operands
  always read the canonical name.
- Display Field source picker on the Instruments edit page.
  The operator is picking *which underlying field* to add as a
  column; the picker shows canonical names. After adding, the
  per-instrument `label` lets them override the column header
  for that instrument; if blank, the resolver fills in the
  session-wide friendly label.
- CSV-import column-name documentation, header validation, and
  parse-error copy. Importers want the machine name
  (`RevieweeTag1`) so operators uploading files know which
  header to use.
- Validation error messages anywhere in the codebase.
- Audit-event payloads (`session_field_label.set` writes
  `source_type` + `source_field` + new `label`; the resolver
  is a render-time concern only).

---

## Why now

- `_DEFAULT_DISPLAY_LABELS` in
  `app/services/instruments/_display_fields.py:41-51` hardcodes the
  nine canonical labels (`Tag 1` / `Tag 2` / `Tag 3` per side, plus
  `Pair context 1-3`) — operators can override them only by adding
  the field as an `InstrumentDisplayField` and editing
  `InstrumentDisplayField.label`. That override is **per-instrument**
  and **invisible** anywhere else (Setup-page table headers, the
  Assignments page tag columns).
- Reviewer tags don't appear in `_DEFAULT_DISPLAY_LABELS` at all —
  `app/web/templates/operator/session_assignments.html:139-141`
  + the column headers a few lines below carry literal `"Tag1"` /
  `"Tag2"` / `"Tag3"` strings.
- `PairContext` is display-only info specific to a (reviewer,
  reviewee) pairing (e.g. "she was your student in NN1101"). Its
  three slots (`pair_context.1` / `.2` / `.3`) live on the
  `relationships` row post-15D and want operator-renamable
  headers on every surface that names them.

---

## Approach

### Slice 1 — Resolver helper (1 PR, ~150 LOC)

**No migration.** The `session_field_labels` table landed inert in
Segment 13D PR 1 with the exact shape this slice needs:

```
id                  PK, autoincrement
session_id          FK sessions.id, ON DELETE CASCADE, indexed
source_type         VARCHAR(32) NOT NULL    # 'reviewer' | 'reviewee' | 'pair_context'
source_field        VARCHAR(64) NOT NULL    # 'tag_1' | 'tag_2' | 'tag_3' | '1' | '2' | '3'
label               VARCHAR(255) NOT NULL
UNIQUE (session_id, source_type, source_field) -- uq_session_field_label
```

Why a table and not a JSON column on `ReviewSession`: per-row audit
events, easy listing, easier 14B-export read. The cardinality is
bounded (≤ 9 rows per session — three sources × three slot indexes),
so the row count stays small.

New service module `app/services/field_labels.py`:

```python
def resolve(session, source_type: str, source_field: str) -> str: ...
def all_labels(session) -> dict[tuple[str, str], str]: ...
def upsert(db, session, *, source_type, source_field, label, user, correlation_id) -> SessionFieldLabel: ...
def clear(db, session, *, source_type, source_field, user, correlation_id) -> None: ...
```

`resolve` reads session-wide friendly label → built-in default
(`_DEFAULT_LABELS` table moved here from `_display_fields.py`) →
fallback (`source_type:source_field`). One per-session dict
materialised per request via the existing per-request session
scope in `app/web/deps.py`.

The per-instrument `InstrumentDisplayField.label` override stays
**above** the resolver in the priority chain — the resolver is
the per-instrument override's fallback when blank, not its
replacement. So the full chain on per-instrument display is:

1. `InstrumentDisplayField.label` (per-instrument override)
2. `field_labels.resolve(...)` (session-wide friendly)
3. Built-in default in `_DEFAULT_LABELS`
4. `f"{source_type}:{source_field}"` (last-resort fallback)

Surfaces that don't carry a per-instrument override (Setup-page
table headers, Assignments tag columns) collapse the chain to
2 → 3 → 4.

Audit emitters: `session_field_label.set` / `.cleared`. Register in
`app.services.audit.EVENT_SCHEMAS`.

### Slice 2 — Replace hardcoded literals at display-layer callsites (1 PR, ~20-25 callsites)

Sweep covers display-layer surfaces only. The "Display vs logic"
section above is the source of truth for what's in / out; this
list enumerates the in-scope callsites.

- `app/services/instruments/_display_fields.py::display_field_label`
  — delegate to `field_labels.resolve` instead of the local
  `_DEFAULT_DISPLAY_LABELS` dict. The per-instrument
  `InstrumentDisplayField.label` override stays the
  highest-priority source; the resolver becomes the next fallback
  before the canonical default.
- Setup-page table headers — `session_reviewers.html`,
  `session_reviewees.html` (currently literal `"Tag 1"` /
  `"Tag 2"` / `"Tag 3"`); `session_relationships.html` for the
  pair-context columns.
- `app/web/templates/operator/session_assignments.html:139-141`
  + the reviewer / reviewee tag column headers a few lines below.
- Reviewee + Pair Context columns in Email Previews + the
  reviewer-surface preview.

On operator-facing surfaces, render the table-header text as
`{friendly_label} ({CanonicalName})` whenever the resolver
returns an override (otherwise keep the canonical-only render).
Reviewer-facing surfaces render the friendly label alone.

A small view adapter in `app/web/views/_filters.py` (or a new
sibling) is the right home for the `(friendly, canonical)`
pair so templates stay shape-agnostic. The 13B sort-button
`aria-label` strings (e.g. `"Sort by Reviewer Tag1"`) follow
in the polish PR after Slice 3 — keeping them out of this
sweep.

Explicitly **not** swept (logic layer):

- `app/web/views/_rule_builder.py` operand sentences + pickers.
- The Display Field source picker on the Instruments edit page.
- CSV-import header docs / parse-error copy.
- Validation error messages and audit-event payloads.

### Slice 3 — Per-page inline editors (1 PR, ~200 LOC)

Shape reshaped on 2026-05-12. **Three editors, one per relevant
Setup page**, each scoped to that page's `source_type`:

- **Reviewers Setup page** edits `source_type="reviewer"`,
  `source_field` ∈ `{"tag_1","tag_2","tag_3"}`.
- **Reviewees Setup page** edits `source_type="reviewee"`,
  `source_field` ∈ `{"tag_1","tag_2","tag_3"}`.
- **Relationships Setup page** edits
  `source_type="pair_context"`, `source_field` ∈ `{"1","2","3"}`.

Shape: an **inline 3-cell row** sits immediately above each
table, captioned "Tag labels" (or "Pair-context labels" on
Relationships). Each cell renders as `Tag N: <input
placeholder="Tag N">` — placeholder text is the built-in default
from the resolver. A single Save button at the end of the row
commits all three cells in one POST. Empty input → clear the
override (delete row) and re-display the default placeholder.

The editor is **gated by the same Save / Edit lock card** the
page already carries for the table itself. While the page is
locked, the inputs render disabled and the Save button is
hidden — same disclosure pattern as the table rows below. While
unlocked, the inputs are editable alongside the table.

Lifecycle gate: editing labels invalidates `validated` (same
hook used by every other setup mutation — calls
`lifecycle.invalidate_if_validated`).

No "Field labels" subsection on `/operator/sessions/{id}/settings`
— labels live with the entities they describe.

**Sweep gate for the 13B sort affordance.** Segment 13B PR 5
added `aria-label="Sort by Reviewer Tag1"` (and similar) strings
to the `↕` sort buttons on the Assignments table. Those names
are out of Slice 2's named sweep but should pick up the
friendly label too. Land them in a small polish PR after Slice 3
rather than expanding Slice 2's blast radius.

### Slice 4 — dropped 2026-05-12

`AssignmentContext1-3` is out of scope. The
`Assignment.context` JSON column those keys lived on was
retired in **Segment 15D PR 6b** — the schema no longer
carries them anywhere, and `_VALID_FL_SOURCE_TYPES` in
`session_config_io.py` already encodes `{"reviewer",
"reviewee", "pair_context"}` only. If a real use case for
logic-bearing per-assignment fields surfaces later, it gets
its own dedicated plan (schema + rule-engine integration +
UI) — not a retrofit onto the labels segment.

---

## Risks + open questions

- **Migration safety.** Not applicable — schema landed inert in
  13D PR 1 and the CI-Postgres job has been round-tripping the
  table since.
- **Friendly-label reach.** The sweep in Slice 2 needs to be
  exhaustive across the *display-layer* surfaces named above —
  a single missed callsite leaves a stale `"Tag 1"` string in
  a column header that confuses operators who renamed it. A
  `grep` audit at the close of Slice 2 lists every hit; the
  reviewer triages each into "display layer (sweep)" or "logic
  layer (intentionally canonical)" using the boundaries in the
  "Display vs logic" section. Expect Rule Builder + the source
  picker + CSV-import error copy + a few validation-error
  helpers to remain canonical and that's the desired state.
- **Reviewer-side surface — closed 2026-05-12.** Reviewers do not
  see operator tag metadata; reviewer-side templates render no
  tag column. Sweep stays operator-only.
- **13B aria-labels.** Sort-button `aria-label` strings added in
  Segment 13B PR 5 (`"Sort by Reviewer Tag1"` etc.) are not in
  Slice 2's named sweep; they're picked up in a polish PR after
  Slice 3 to keep the Slice 2 blast radius small.

---

## Critical files

- New: `app/services/field_labels.py` (Slice 1 resolver).
- Touched (Slice 1):
  `app/services/instruments/_display_fields.py` (delegate
  `display_field_label` to the resolver), `app/services/audit.py`
  (`EVENT_SCHEMAS` registrations for `session_field_label.set` /
  `.cleared`), `app/db/models/session_field_label.py` (clear the
  `assignment_context` docstring note now that Slice 4 is dropped).
- Touched (Slice 2 — display layer only):
  `app/services/instruments/_display_fields.py` (delegate
  `display_field_label` to the resolver per the chain above),
  `app/web/views/_*.py` (column-header view adapters; new
  `(friendly, canonical)` pair helper for the operator
  `Friendly (Canonical)` render), and the operator templates
  that name a tag or pair-context column
  (`session_assignments.html`, `session_reviewers.html`,
  `session_reviewees.html`, `session_relationships.html`,
  Email Previews + reviewer-surface preview).
  **Not touched:** `app/web/views/_rule_builder.py`,
  `app/web/templates/operator/session_rule_builder.html`, the
  Display Field source picker on the Instruments edit page,
  any CSV-import error copy, or any audit-event payload.
- Touched (Slice 3):
  `app/web/templates/operator/session_reviewers.html`,
  `session_reviewees.html`, `session_relationships.html`
  (inline 3-cell editor row above each table), the routes that
  back those pages (POST handler for the label form, gated by
  the existing Save / Edit lock).

---

## Verification

- `pytest -q` green on SQLite + `ci-postgres`.
- `ruff check .` green.
- New tests:
  - `tests/integration/test_field_labels_routes.py` — set / clear /
    re-set, lifecycle invalidation hook, audit emitters.
  - Header-rendering assertions in existing setup-page tests
    (Reviewers / Reviewees / Assignments) confirming the override
    appears.
- `grep` audit at Slice 2 close (callsite sweep gate).
