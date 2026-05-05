# Segment 12A — Session metadata export / import (CSV)

Stub. Implementation plan for a round-trippable CSV format that
captures the user-inputted *configuration* of a review session
(everything an operator typed into Setup) without including the
data-volume-heavy people lists (reviewers, reviewees, assignments).
The export side gives operators a sharable backup / template; the
import side rehydrates a freshly-named session from that template.

This is the smallest useful slice of Segment 12 (export / audit
retention / data-rehydration), pulled forward as **12A** so the rest
of Segment 12 can land on top.

## Status

Planning. Sized as **2 PRs** in dependency order — export first
(narrower contract, single source of truth on the CSV shape), import
second (consumes that exact shape).

## Why CSV (not JSON / YAML)

- Operators already work with CSVs for reviewer / reviewee imports;
  the muscle memory transfers.
- Three fixed columns (`field`, `value`, `data_type`) is line-noise-
  cheap to author by hand and trivially diffable.
- Excel-friendly: operators who maintain session templates in a
  spreadsheet can edit a row, re-export, and round-trip without a
  text editor.
- The `data_type` column is the structural escape hatch — values
  that need integer / decimal / bool / datetime / list parsing carry
  their type next to them, so the importer doesn't have to keep a
  parallel schema.

The CSV is **not** a general data-dump format. It captures
configuration only; reviewers / reviewees / assignments / responses
ship via their existing CSV upload flows or the response-extract
flow that the rest of Segment 12 covers.

## Scope

In:

- **Export** at `GET /operator/sessions/{id}/export-config.csv`
  (anchor: a "Download config" button on Session Home next to the
  existing "Extract Data" placeholder card, or on the Session
  Details card — pick one in PR 1). Streams a 3-column CSV with
  every user-inputted configuration field, in deterministic order.
- **Import** at `POST /operator/sessions/{id}/import-config` with
  a `file=…` multipart payload. Reads the CSV, validates every row,
  applies all mutations atomically, and 303s back to Session Home
  on success or the same page with a validation summary card on
  failure. Anchor: a "Import config" button on Session Home, gated
  to draft sessions only (locked sessions reject the upload at the
  service layer).
- New service module `app/services/session_config_io.py` with two
  pure functions: `serialize_session_config(session) -> list[Row]`
  and `apply_session_config(session, rows) -> ApplyResult`. Routes
  stay thin.
- Two audit events: `session.config_exported` and
  `session.config_imported`, both with `count` of fields written.
- `tests/integration/test_session_config_io.py` covers golden-path
  round-trip, partial / malformed CSV rejection, lifecycle gate,
  and the audit events.

Out (deferred):

- **Reviewers / reviewees / assignments.** These have their own
  upload flows on their respective Manage pages; the existing
  helpers stay the source of truth. The config export deliberately
  excludes them so a single template can drive multiple sessions
  with different cohorts.
- **Per-reviewer / per-reviewee state** (invitation tokens, sent
  timestamps, Response rows, audit events). Out of scope.
- **Session lifecycle state** (`status`, `deadline_closed_at`,
  `is_seeded` on RTDs). Lifecycle is owned by the activation /
  deadline / pause flow; the importer never writes these.
- **Operator-editable email templates.** Coming in Segment 11E
  (`email_template_overrides` JSON column on `ReviewSession`). When
  that ships, fold the column into the export schema as a follow-on
  one-liner.
- **Cross-session migration** (export from session A → import into
  session B at a different deployment). Today's contract assumes
  same schema version on both ends; cross-version is a Segment 12
  audit-retention concern.

## CSV format

### Three columns

```
field,value,data_type
```

- `field` — machine-readable dotted / bracketed key path (see
  "Key conventions" below). Stable across exports of the same
  session — round-tripping is exact.
- `value` — string representation of the value. Empty cell ⇒ `None`
  / unset / cleared on import.
- `data_type` — the value's parsing rule. One of:
  - `string`
  - `integer`
  - `decimal`
  - `boolean` — accepts `true`/`false` (case-insensitive) on import;
    emits lowercase on export
  - `datetime` — ISO-8601 with timezone offset (`2026-05-15T17:00:00+00:00`).
    Empty cell ⇒ `None`
  - `enum` — finite operator-set value (e.g.
    `assignment_mode = "FullMatrix" | "Manual"`); validated
    server-side against the enum at import time
  - `csv_list` — a comma-separated literal stored as a single Text
    column (today: `ResponseTypeDefinition.list_csv`)

The `data_type` column is **descriptive of the cell, not of any
underlying RTD's `data_type`**. Don't conflate the two: an RTD whose
`data_type=Integer` exports as `data_type=enum` for that cell because
the value `"Integer"` is one of a fixed set.

### Key conventions

Hierarchical keys, position-indexed (1-based, matching how the
reviewer surface and operator UI count pages):

- **Session-level** — flat `session.<column>`:
  - `session.name` (string, required)
  - `session.code` (string, required)
  - `session.description` (string)
  - `session.deadline` (datetime)
  - `session.assignment_mode` (enum: `FullMatrix` / `Manual` / empty)
- **Operator-defined RTDs** — keyed by `response_type` (the
  operator-typed name; unique within a session):
  - `rtds[<response_type>].data_type` (enum: `String` / `Integer` /
    `Decimal` / `List`)
  - `rtds[<response_type>].min` (decimal)
  - `rtds[<response_type>].max` (decimal)
  - `rtds[<response_type>].step` (decimal)
  - `rtds[<response_type>].list_csv` (csv_list)

  Seeded RTDs (`is_seeded=true`) are **not exported** — they're
  regenerated from `SEED_RESPONSE_TYPE_DEFINITIONS` in
  `app/services/instruments.py` on session creation, so the
  importer doesn't need to recreate them. If a future operator-
  edit-on-seeded path lands, fold it in as `rtds[<name>].overrides.*`.
- **Per-instrument** — keyed by 1-based position
  (`(Instrument.order, Instrument.id)` order on export):
  - `instruments[N].name` (string, required)
  - `instruments[N].short_label` (string)
  - `instruments[N].description` (string)
  - `instruments[N].order` (integer; emitted but typically derivable
    from N — the importer treats N as authoritative)
  - `instruments[N].accepting_responses` (boolean)
  - `instruments[N].responses_visible_when_closed` (boolean)
- **Per-display-field on each instrument** — 1-based position
  (`(InstrumentDisplayField.order, .id)` order):
  - `instruments[N].display_fields[M].source_type` (enum:
    `reviewee` / `pair_context`)
  - `instruments[N].display_fields[M].source_field` (string —
    e.g. `tag_1`, `profile_link`, `1`/`2`/`3`)
  - `instruments[N].display_fields[M].label` (string; empty ⇒
    inferred fallback per
    `instruments_service.display_field_label`)
  - `instruments[N].display_fields[M].visible` (boolean)
- **Per-response-field on each instrument** — 1-based position:
  - `instruments[N].response_fields[M].field_key` (string, required)
  - `instruments[N].response_fields[M].label` (string, required)
  - `instruments[N].response_fields[M].response_type` (string —
    references either a seeded RTD name from `instruments.py` or an
    operator-defined `rtds[<name>]` row exported earlier in the same
    file)
  - `instruments[N].response_fields[M].required` (boolean)
  - `instruments[N].response_fields[M].help_text` (string)
  - `instruments[N].response_fields[M].help_text_visible` (boolean)

`validation` JSON is **not exported** — it's derived from the RTD
on import via `validation_block_for_rtd`. Keeping it out of the CSV
removes a redundant source of truth.

`field_key` is the stable machine identifier for a response field.
The importer treats `(instrument_position, field_key)` as the upsert
key within an instrument's response-field list, so an operator
hand-editing the CSV can rename labels without losing field identity.

### Row order on export

Stable, deterministic, designed to read top-to-bottom like a setup
walkthrough:

1. Session-level rows (in column-definition order).
2. Operator-defined RTDs, sorted by `seed_order` then `response_type`.
3. Each instrument block in order:
   1. Instrument-level rows.
   2. Display fields for that instrument.
   3. Response fields for that instrument.

Pin the order in `serialize_session_config` and pin it again in a
unit test — diff-noise on re-export is what makes the CSV worth
maintaining as a template.

### Lifecycle gating on import

Import is gated to draft sessions: `status in {"draft", "validated"}`.
Locked / activated / paused sessions reject the upload with 409 and
a banner. The importer wipes-and-replaces (see "Idempotency model"),
which would silently destroy reviewer-typed responses on an active
session — the gate makes that impossible.

### Idempotency model

The importer is **wipe-and-replace** for everything it owns:

1. Validate every row (parse `data_type`, check enum membership,
   confirm RTD references resolve). Abort the whole transaction
   if any row is malformed; no partial application.
2. Update session-level fields in place.
3. For RTDs: upsert operator-defined rows by `response_type`;
   delete existing operator-defined rows not present in the CSV.
   Seeded rows are untouched.
4. For instruments: delete every existing instrument on the session
   then re-create from the CSV. Display fields and response fields
   cascade with the instrument they belong to (FK
   `ON DELETE CASCADE`).
5. Audit `session.config_imported` with `{"counts": {...}}` detail.

The wipe-and-replace cost is acceptable because:
- The lifecycle gate keeps Response rows (which have FKs to RFs)
  out of the picture; on a draft session there are no responses to
  cascade-delete.
- Reviewers / reviewees / assignments don't FK to instruments
  (assignments do via `instrument_id`, but the lifecycle gate keeps
  this clean — Segment 5/7 refresh assignments on the next mutation
  anyway).
- If we hit a session with assignments referencing about-to-be-
  deleted instruments, the importer 409s with a "this session has
  assignments; delete them first" message rather than silently
  cascading.

If the operator wants merge semantics later (e.g. "import only the
new RTDs without touching the existing instruments"), that's a
follow-on `?mode=merge` query parameter; the wipe-and-replace path
stays the default because it's the only one with a clean
"the CSV is the source of truth" mental model.

## Proposed PR sequence

### PR 1 — Export

**Goal.** A CSV that round-trips to itself shape-wise. No import
yet; an operator can download but not upload.

- New module `app/services/session_config_io.py`:
  - `Row = NamedTuple("Row", [("field", str), ("value", str),
    ("data_type", str)])`.
  - `serialize_session_config(session: ReviewSession) -> list[Row]` —
    the only function the route consumes.
  - Internal helpers for each section (session, RTDs, instruments).
- New route `GET /operator/sessions/{id}/export-config.csv`:
  - Operator-only; gated through the existing per-session
    permission check.
  - Streams `text/csv` with `Content-Disposition:
    attachment; filename="{session.code}-config.csv"`.
  - Writes an audit `session.config_exported` event with detail
    `{"row_count": len(rows)}`.
- "Download config" anchor on Session Home (location TBD — propose
  the Session Details card's footer; revisit at PR review time).
- Unit tests on `serialize_session_config` for each row class +
  one golden-fixture test that pins the byte-exact output for a
  fully-populated session.
- Integration test for the route (auth, audit emission, 404 on
  unknown session).

### PR 2 — Import

**Goal.** Upload the CSV PR 1 produced and rehydrate a fresh-named
session into the same shape.

- `apply_session_config(session: ReviewSession, rows: list[Row]) ->
  ApplyResult` in the same module. Returns
  `ApplyResult(counts, errors)` so the route can render a
  validation summary on failure.
- Two-phase implementation:
  1. **Parse + validate** — convert every cell per its `data_type`
     column into a typed value; build a structured plan (session-
     level kvs, RTD upserts, instrument trees). Collect every error
     before reporting; one bad row doesn't mask the next.
  2. **Apply** — inside a single DB transaction, write the plan.
     If any apply step fails (FK violation, RTD reference unknown),
     roll back and surface the error.
- New route `POST /operator/sessions/{id}/import-config`:
  - Lifecycle gate (`status in {"draft", "validated"}`).
  - Multipart `file` upload; reject empty / non-CSV up front.
  - On success: 303 → Session Home with a `?config_imported=ok`
    flash (or a per-session toast — match whatever the existing
    upload flows do; check `session_reviewers.html` for the
    convention).
  - On validation error: re-render Session Home with a
    `.banner.banner-warning` enumerating the errors.
- "Import config" form on Session Home (file input + submit
  button). Anchor + visibility decision: hide on
  `status not in {"draft", "validated"}`.
- Audit `session.config_imported` with detail
  `{"counts": {"session": 1, "rtds": 3, "instruments": 2,
  "display_fields": 6, "response_fields": 8}}` (real numbers per
  import).
- Tests:
  - Round-trip: `serialize → file → parse → apply → serialize`
    is byte-identical.
  - Malformed `data_type` column rejected per row.
  - Unknown RTD reference in `response_fields[].response_type`
    rejected with a "no such RTD on this session: X" error
    pointing at the offending row.
  - Lifecycle gate (`status="ready"` ⇒ 409).
  - Conflict path: session has assignments referencing a not-in-
    CSV instrument ⇒ 409, no rows written.

## Implementation pointers

- **CSV parsing.** Use `csv.DictReader` (stdlib). Don't introduce
  a new dependency.
- **Datetime formatting.** Use `datetime.isoformat()` on export and
  `datetime.fromisoformat()` on import; both round-trip ISO-8601
  with timezone offsets faithfully on Python 3.12.
- **Boolean parsing.** Lowercase normalize, accept `{"true",
  "false"}` only; reject anything else with an explicit error
  rather than silently treating as falsy.
- **Empty cell semantics.** Empty `value` cell ⇒ `None` for nullable
  columns; reject for `nullable=False` columns with a per-row error.
- **RTD reference resolution.** When applying response-field rows,
  resolve `response_type` against:
  1. Operator-defined RTDs already upserted in this same import
     (already in the DB after PR 2's RTD pass).
  2. Seeded RTDs from `SEED_RESPONSE_TYPE_DEFINITIONS`.
  Both come from the session's `response_type_definitions`
  collection. Fail-loud if neither matches.
- **Field-key uniqueness.** Within an instrument, `field_key` must
  be unique across response fields. The importer enforces this
  during validate; a duplicate `field_key` in two
  `instruments[N].response_fields[M]` rows for the same N is a
  parse error.
- **Display-field source enum.** `source_type` is one of a small
  fixed set (`reviewee`, `pair_context`). Validate against the
  same enum the operator UI uses (the seven-source enumeration
  spec'd in `spec/architecture.md` and seeded via
  `instruments_service.display_field_value`).
- **Setup-mutation invalidation.** Import mutates session +
  instruments + RTDs + display / response fields. Each underlying
  service helper (`update_session`, `create_instrument`, etc.)
  already calls `lifecycle.invalidate_if_validated()`; calling them
  in turn from `apply_session_config` keeps the validated → draft
  flip free. The importer doesn't bypass them.

## Out of scope (cross-references)

- **Reviewer / reviewee / assignment CSVs** — existing per-table
  upload flows on the Manage pages. See Segment 6 / 7. The config
  CSV deliberately omits them.
- **Operator-editable email templates** — Segment 11E. When
  `email_template_overrides` ships, fold its key path into the
  export schema as a follow-on patch.
- **Audit retention / response extract** — rest of Segment 12.
  This segment's `apply_session_config` writes a single
  `session.config_imported` audit event; per-row diff is not
  emitted (would balloon the event log).
- **Cross-deployment / cross-version** — assumes same app version
  on both ends. A future schema-versioned wrapper (`# version: 1`
  comment line at the top of the CSV) is the natural extension
  but not in scope here.

## Test impact

- Two new test files —
  `tests/unit/test_session_config_io.py` (round-trip,
  per-row-type parsing, error collection) and
  `tests/integration/test_session_config_io_routes.py` (auth,
  lifecycle gate, multipart upload, audit events).
- One golden fixture under `tests/fixtures/` — a `.csv` of a
  fully-populated session that pins the byte-exact serialization.
  Future contract changes to the CSV shape have to deliberately
  update the fixture, which is the cheapest place to discuss
  them.
- No changes to the existing reviewer/reviewee/assignment test
  suites — those flows stay untouched.

## Doc impact

- `docs/status.md` gains a timeline entry per PR.
- `guide/todo_master.md` adds Segment 12A under **Upcoming**
  before PR 1 ships; moves to **Done** under the existing
  Segment 11 / Resolved siblings once PR 2 lands.
- `spec/architecture.md` may want a one-liner under "Data import /
  export" pointing at the CSV shape; verify on PR 1 review.
- No spec doc for the CSV shape itself — this guide doubles as
  the spec until the format proves stable across two or three
  consumers; promote then.
