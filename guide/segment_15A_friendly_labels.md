# Segment 15A — Pervasive friendly labels

**Status:** Plan stub (2026-05-09).
**Sizing:** ~3-4 PRs.
**Depends on:** none. Lands cleanly any time after the major refactor
(merged 2026-05-09).
**Recommended order:** before 15B. The session-level label resolver
this segment introduces is consumed by every header / picker / tooltip
that 15B's per-instrument assignments UI would otherwise need to
duplicate.

---

## Goal

Let operators rename `ReviewerTag1-3`, `RevieweeTag1-3`, and
`PairContext1-3` **once per session**, with the friendly label
flowing through every header, picker, tooltip, and preview that
names those fields — not just the Display Field column where it
lives today.

(`AssignmentContext1-3` was originally listed as in-scope; the
2026-05-09 semantic clarification — see Slice 4 — establishes that
it's logic-bearing rather than display-only and probably doesn't
belong in a labels segment.)

---

## Why now

- `_DEFAULT_DISPLAY_LABELS` in
  `app/services/instruments/_display_fields.py:41-51` hardcodes the
  nine canonical labels (`Tag 1` / `Tag 2` / `Tag 3` per side, plus
  `Pair context 1-3`) — operators can override them only by adding
  the field as an `InstrumentDisplayField` and editing
  `InstrumentDisplayField.label`. That override is **per-instrument**
  and **invisible** anywhere else (Setup-page table headers, the
  Assignments page tag columns, Rule Builder operands).
- Reviewer tags don't appear in `_DEFAULT_DISPLAY_LABELS` at all —
  `app/web/templates/operator/session_assignments.html:184-186`
  carries the literal `"Tag1"` / `"Tag2"` / `"Tag3"` headings.
- `AssignmentContext1-3` is **categorically different** from
  `PairContext` and probably doesn't belong in this segment at all.
  PairContext is display-only info specific to a (reviewer,
  reviewee) pairing (e.g. "she was your student in NN1101");
  AssignmentContext is logic-bearing info about the assignment
  (e.g. "this is for the Award X category") that drives downstream
  rules, validation, or filtering. Logic-bearing fields aren't a
  labels concern — and most use cases are already derivable from
  reviewer + reviewee tags evaluated through the rule engine. See
  Slice 4 below.

---

## Approach

### Slice 1 — Schema + resolver helper (1 PR, ~150 LOC + migration)

New table `session_field_labels`:

```
id                  PK, autoincrement
session_id          FK sessions.id, ON DELETE CASCADE, indexed
source_type         VARCHAR(32) NOT NULL    # 'reviewer' | 'reviewee' | 'pair_context' | 'assignment_context'
source_field        VARCHAR(64) NOT NULL    # 'tag_1' | 'tag_2' | 'tag_3' | '1' | '2' | '3'
label               VARCHAR(255) NOT NULL
UNIQUE (session_id, source_type, source_field)
```

Why a table and not a JSON column on `ReviewSession`: per-row audit
events, easy listing, easier 14B-export read. The cardinality is
bounded (≤ 12 rows per session — three sources × four namespaces,
minus combinations that don't apply), so the row count stays small.

New service module `app/services/field_labels.py`:

```python
def resolve(session, source_type: str, source_field: str) -> str: ...
def all_labels(session) -> dict[tuple[str, str], str]: ...
def upsert(db, session, *, source_type, source_field, label, user, correlation_id) -> SessionFieldLabel: ...
def clear(db, session, *, source_type, source_field, user, correlation_id) -> None: ...
```

`resolve` reads operator override → built-in default
(`_DEFAULT_LABELS` table moved here from `_display_fields.py`) →
fallback (`source_type:source_field`). One per-session dict
materialised per request via the existing per-request session scope
in `app/web/deps.py`.

Audit emitters: `session_field_label.set` / `.cleared`. Register in
`app.services.audit.EVENT_SCHEMAS`.

### Slice 2 — Replace hardcoded literals at every callsite (1 PR, ~50 callsites)

Sweep:

- `app/services/instruments/_display_fields.py::display_field_label` —
  delegate to `field_labels.resolve` instead of the local
  `_DEFAULT_DISPLAY_LABELS` dict. The Display Field row's own
  `label` override stays the highest-priority source; the resolver
  becomes the fallback chain when that's blank.
- Setup-page table headers for Reviewers + Reviewees (currently
  literal `"Tag 1"` / `"Tag 2"` / `"Tag 3"`).
- `app/web/templates/operator/session_assignments.html:184-191` —
  reviewer + reviewee tag column headers.
- Display Field source picker on the Instruments page — already
  pulls from `_DEFAULT_DISPLAY_LABELS`; this slice just makes it
  session-aware.
- Rule Builder operand pickers + `_render_*_sentence` helpers in
  `app/web/views/_rule_builder.py` — predicate operands that name
  a tag.
- Reviewee + Pair Context columns in Email Previews + the reviewer-
  surface preview.

Out of scope: CSV-import column-name documentation and parse-error
copy. Those legitimately want the machine name (`RevieweeTag1`) so
operators uploading files know which header to use.

### Slice 3 — Settings-page editor (1 PR, ~200 LOC)

New "Field labels" subsection on `/operator/sessions/{id}/settings`
(or wherever the per-session settings card lands post-12A). One row
per `(source_type, source_field)`; operator types a label and Saves.
Default state = empty input with placeholder showing the built-in
default. Empty Save → clear (delete row) and re-display default.

Lifecycle gate: editing labels invalidates `validated` (same hook
used by every other setup mutation — calls
`lifecycle.invalidate_if_validated`). It does **not** require
edit-lock; labels are pure presentation.

### Slice 4 (optional, likely defer) — `AssignmentContext1-3`

**Semantic note (locked 2026-05-09).** `PairContext` is **display-
only** information about a specific reviewer ↔ reviewee pairing
that doesn't generalise across multiple individuals (e.g. "she was
your student in NN1101"). `AssignmentContext` is **logic-bearing**
information about the assignment (e.g. "this assignment is for
the Award X category" — drives downstream filtering, reporting,
or rule evaluation). The two are categorically different, not
just per-instrument vs. per-pair.

That difference flips the calculus on this slice:

- **Labelling** is the smaller half. The friendly-label resolver
  from Slice 1 generalises to `assignment_context` trivially —
  add it to the `source_type` enum and the Settings editor
  subsection picks it up.
- **Semantics** are the bigger half, and they're **out of scope
  for 15A**. Logic-bearing fields need their own infrastructure
  (rule-engine integration, validation, conditional rendering
  in the reviewer surface) that doesn't belong in a labels
  segment.
- **Likely unnecessary anyway.** Most logic-bearing-per-assignment
  cases (award category, purpose, creation method) are
  derivable from existing reviewer + reviewee tags evaluated
  through the rule engine. Spend the effort on a use case
  before introducing new columns.

Recommend: drop this slice from 15A. If a real use case for
logic-bearing per-assignment fields surfaces later, write a
dedicated plan for it (schema + rule-engine integration + UI)
rather than retrofitting the labels segment.

---

## Risks + open questions

- **Migration safety.** New table is purely additive with no
  backfill; SQLite + Postgres parity is exercised by the existing
  `ci-postgres` job.
- **Friendly-label reach.** The sweep in Slice 2 needs to be
  exhaustive — a single missed callsite leaves a stale `"Tag 1"`
  string in the UI that confuses operators who renamed it. A `grep`
  audit at the close of Slice 2 (`grep -rn '"Tag [0-9]"\|Pair
  context [0-9]'` across `app/`) is the gate.
- **Reviewer-side surface.** Reviewers don't see tag labels (tags
  are operator-only metadata). Confirm before the sweep that no
  reviewer template renders them — if they do, decide whether to
  expose the friendly label or to keep them operator-only.

---

## Critical files

- New: `app/services/field_labels.py`,
  `app/db/models/session_field_label.py`, Alembic migration.
- Touched: `app/services/instruments/_display_fields.py`,
  `app/services/audit.py` (EVENT_SCHEMAS),
  `app/web/views/_*.py` (column headers + picker labels),
  every operator template that names a tag or pair-context column,
  `app/web/templates/operator/session_settings.html` (new
  subsection).

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
