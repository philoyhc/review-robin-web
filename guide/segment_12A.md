# Segment 12A — Session export / import + data extraction (CSV)

Stub. Implementation plan covering two paired concerns that share
the same CSV vocabulary and the same Session Home anchor:

1. **Configuration export / import.** A round-trippable CSV that
   captures the user-inputted *configuration* of a review session
   (everything an operator typed into Setup). Export gives
   operators a sharable backup / template; import rehydrates a
   freshly-named session from that template. Configuration only
   — no people lists, no responses.
2. **Data extraction card.** The Session Home **Extract Data**
   card (currently a `placeholder_card` stub at
   `session_detail.html:187`) ships as a real card with five
   separate CSV downloads — Session settings, Reviewers,
   Reviewees, Assignments, Responses — plus a "Download all"
   zip bundle. Read-only; no import counterpart.

Both halves live in 12A because the configuration export is
already one of the five extracts, and the Extract Data card is the
natural anchor for it. Folding them avoids a second segment (the
prior "Segment 11H — Extract Data" placeholder in
`guide/todo_master.md`) and keeps one CSV vocabulary.

This is the smallest useful slice of Segment 12 (export / audit
retention / data-rehydration), pulled forward as **12A** so the
rest of Segment 12 (audit retention) can land on top.

## Status

Planning. Sized as **6 PRs** in dependency order:

1. **PR 1 — Config export.** Narrow contract; single source of
   truth on the CSV shape.
2. **PR 2 — Config import.** Consumes that exact shape.
3. **PR 3 — Reviewers + reviewees extract.** Two CSVs that
   round-trip with the existing per-entity upload flows.
4. **PR 4 — Assignments extract.** Round-trippable with the
   existing manual-assignments upload.
5. **PR 5 — Responses extract.** New CSV shape (no import
   counterpart — operators don't upload responses).
6. **PR 6 — Extract Data card on Session Home.** Replaces the
   placeholder, wires all five downloads + the zip bundle, swaps
   the Quick Setup configuration-import slot's placeholder for
   the live PR 2 form.

PRs 3-5 are parallelizable once PR 1's serialization helpers
(`Row` shape, filename convention, audit event family) are in
place. PR 6 depends on 1-5.

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

The 3-column shape is **not** a general data-dump format — it's
configuration only. Reviewers / reviewees / assignments / responses
ship via the data-extraction CSVs (this segment) using their natural
per-entity column shapes, not the 3-column key/value shape.

## Scope

In:

### Configuration round-trip (PRs 1-2)

- **Export** at `GET /operator/sessions/{id}/export-config.csv`
  (anchor: the Session settings download button inside the Extract
  Data card on Session Home — see "Data extraction card" below).
  Streams a 3-column CSV with every user-inputted configuration
  field, in deterministic order.
- **Import** at `POST /operator/sessions/{id}/import-config` with
  a `file=…` multipart payload. Reads the CSV, validates every row,
  applies all mutations atomically, and 303s back to Session Home
  on success or to Home with a `?quick_setup_error=settings&quick_setup_reason=parse`
  flag on failure (so the GET render places a `.banner.banner-error`
  inside slot 4 — the same scoped-error pattern Segment 11J
  established for slots 1-3). Anchor: the configuration-import
  slot of the Quick Setup card (slot 4 — inert from Segment 11H,
  graduates in PR 6 of this segment). Gated at the service layer
  via `_require_editable`; on `ready` the slot's submit 303s with
  `quick_setup_reason=lifecycle` and the banner names the next
  move (Pause), matching the lock-toggle pattern 11J established.
- New service module `app/services/session_config_io.py` with two
  pure functions: `serialize_session_config(session) -> list[Row]`
  and `apply_session_config(session, rows) -> ApplyResult`. Routes
  stay thin.
- Two audit events: `session.config_exported` and
  `session.config_imported`, both with `count` of fields written.
- `tests/integration/test_session_config_io.py` covers golden-path
  round-trip, partial / malformed CSV rejection, lifecycle gate,
  and the audit events.

### Data extraction (PRs 3-6)

- **Five separate CSV downloads** anchored on the **Extract Data**
  card on Session Home, each with its own button + filename:
  - **Session settings** (`session-{code}-settings.csv`) — the
    same 3-column config CSV PR 1 ships.
  - **Reviewers** (`session-{code}-reviewers.csv`) — round-trips
    with the existing reviewer upload (`ReviewerName`,
    `ReviewerEmail`, `ReviewerTag1`, `ReviewerTag2`,
    `ReviewerTag3`).
  - **Reviewees** (`session-{code}-reviewees.csv`) — round-trips
    with the existing reviewee upload (`RevieweeName`,
    `RevieweeEmail`, `RevieweeTag1`-3, plus optional
    `ProfileLink` / per-session pair-context columns matching
    what the importer expects).
  - **Assignments** (`session-{code}-assignments.csv`) —
    round-trips with the existing manual-assignments upload
    (`ReviewerEmail`, `RevieweeEmail`, `IncludeAssignment` —
    plus `Instrument` once multi-instrument upload is in scope;
    today the export emits one assignment row per
    (assignment, instrument) tuple to keep responses joinable).
  - **Responses** (`session-{code}-responses.csv`) — new shape,
    one row per saved response, with the join keys denormalized
    so the file is human-readable without the other CSVs:
    `ReviewerEmail`, `RevieweeEmail`, `InstrumentName`,
    `InstrumentShortLabel`, `FieldKey`, `FieldLabel`, `Value`,
    `SavedAt`, `SubmittedAt`, `Version`. No import counterpart;
    operators don't upload responses.
- **"Download all" zip bundle** at
  `GET /operator/sessions/{id}/export.zip` containing all five
  CSVs at the filenames above. The card surfaces this as a single
  "Download all" button next to the per-file buttons.
- **No lifecycle gate.** Extraction is read-only and useful at
  every state — `draft` (sanity-check the config you typed),
  `validated`, `ready` (mid-flight responses snapshot), `closed`
  (final dataset). The Extract Data card stays interactive in
  every lifecycle state, including behind the yellow lock card —
  which by convention disables setup mutations only, not reads.
- **One service module per CSV**, each with a single
  `serialize_*(session) -> Iterable[Row]` function. They live
  alongside `session_config_io.py` (e.g.
  `app/services/extracts/{reviewers,reviewees,assignments,
  responses}_extract.py`) and import from it for the shared
  `Row` shape and CSV streaming helper. Routes stay thin.
- **Six audit events** (one per download, plus the bundle):
  `session.{settings,reviewers,reviewees,assignments,responses,
  bundle}_extracted`, all with detail
  `{"row_count": <int>}`. Audit-event detail-schema convention
  lands in Segment 11K; until then these match the simplest
  shape `audit_events.detail` already carries.

Out (deferred):

- **Reviewer / reviewee / assignment import via 12A.** Out — they
  already have their own upload flows on their Manage pages and
  on the Quick Setup card (Segment 11J). 12A's import half is
  configuration-only; the per-entity CSVs are extract-only. The
  one wrinkle: the file shapes match across both directions, so
  an operator can take a 12A reviewers extract and feed it back
  into the existing reviewer-upload flow on a different session
  without conversion. That's the round-trip we want.
- **Response import.** Operators don't upload responses; only
  reviewers create them via the response surface. No round-trip
  for the responses CSV.
- **Per-reviewer / per-reviewee state beyond the CSVs.** Invitation
  tokens, sent / opened timestamps, audit-event log. Out of scope
  — those are operator-internal records, not data the operator
  exports for downstream analysis. Audit-log export lands with the
  rest of Segment 12 (audit retention).
- **Session lifecycle state** (`status`, `deadline_closed_at`,
  `is_seeded` on RTDs). Lifecycle is owned by the activation /
  deadline / pause flow; the importer never writes these and the
  Session settings extract omits them.
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
- "Download config" anchor on Session Home: a temporary button on
  the Session Details card's footer in PR 1, retired in PR 6 when
  the Extract Data card subsumes it as the "Session settings"
  download row. PR 1 doesn't need to wait for PR 6 — operators can
  use the temporary button as soon as PR 1 ships.
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
- "Import config" form on Session Home: lives in the Quick Setup
  card's fourth slot (the Session settings slot — inert from
  Segment 11H, untouched by Segment 11J). PR 6 of this segment
  flips slot 4's `is_wired=False → True` and supplies a
  `wire_url` so the slot renders as a real `<input type="file">`
  + submit; no new anchor on Home. The visibility rule is the
  same body-greying lock pattern Segment 11J established for
  slots 1-3 (default-locked in every editable-conceivable state;
  Lock / Unlock toggle visible across `draft` / `validated` /
  `ready`; on `ready` unlocking is cosmetic and the importer
  rejects with a scoped `banner-error`).
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

### PR 3 — Reviewers + reviewees extract

**Goal.** Two CSV downloads matching the column shape of the
existing per-entity uploads, so an operator can extract from one
session and feed the file straight into another session's upload.

- New module `app/services/extracts/__init__.py` defining a shared
  `Row = list[str]` (or per-extract `NamedTuple`) and a tiny
  `stream_csv(rows, fieldnames) -> Iterator[bytes]` helper that
  wraps `csv.writer` over a `StringIO` chunked to keep memory flat
  for sessions with thousands of reviewers.
- New module `app/services/extracts/reviewers_extract.py` with
  `serialize_reviewers(session) -> Iterable[Row]`. Column order
  matches the importer at `csv_imports.parse_reviewer_csv:138`:
  `ReviewerName`, `ReviewerEmail`, `ReviewerTag1`, `ReviewerTag2`,
  `ReviewerTag3`. Inactive reviewers are included with their
  current state (the importer treats them as inactive on the
  next session anyway); no special filter.
- New module `app/services/extracts/reviewees_extract.py` with
  `serialize_reviewees(session) -> Iterable[Row]`. Same shape:
  `RevieweeName`, `RevieweeEmail`, `RevieweeTag1-3`, plus any
  `pair_context_*` columns the per-session schema carries (read
  from the same place the importer reads them — single source of
  truth).
- Two new routes:
  - `GET /operator/sessions/{id}/export/reviewers.csv`
  - `GET /operator/sessions/{id}/export/reviewees.csv`
  Each streams `text/csv` with
  `Content-Disposition: attachment; filename="session-{code}-reviewers.csv"`
  (etc.). Each emits its own audit event
  (`session.reviewers_extracted`, `session.reviewees_extracted`)
  with `{"row_count": <int>}`.
- Tests:
  - Golden-fixture CSV pinning the byte-exact output for a
    populated session (one per extract).
  - **Round-trip test**: extract from session A → upload to
    session B via the existing `csv_imports.parse_reviewer_csv`
    + `save_reviewers` path → assert session B's reviewer set
    matches A's. Same for reviewees.
  - Empty-session case: header row only, no body rows;
    `row_count=0` in the audit.

### PR 4 — Assignments extract

**Goal.** Round-trippable CSV matching the manual-assignments
upload at `assignments.parse_manual_csv:166`.

- New module `app/services/extracts/assignments_extract.py` with
  `serialize_assignments(session) -> Iterable[Row]`. Column order
  matches the importer: `ReviewerEmail`, `RevieweeEmail`,
  `IncludeAssignment`. One row per assignment; emits
  `IncludeAssignment=true` for active assignments and `false`
  for inactive ones (so the upload round-trip preserves the
  active/inactive split exactly).
- **Multi-instrument shape.** When a session has multiple
  instruments, today's manual CSV implicitly applies one
  `Assignment` row to all instruments via `instrument_id`.
  PR 4 emits one row per (assignment, instrument) tuple with an
  `Instrument` column (matching the per-instrument label) so the
  output stays unambiguous; the upload-side `parse_manual_csv`
  already collapses repeated `(ReviewerEmail, RevieweeEmail)`
  pairs into one assignment, so the round-trip still works on the
  multi-instrument case. If the importer doesn't yet read an
  `Instrument` column, PR 4 ships the column anyway and the
  importer ignores it (forward-compatible — the multi-instrument
  upload is a Segment 13 concern).
- New route `GET /operator/sessions/{id}/export/assignments.csv`
  + audit `session.assignments_extracted` with `{"row_count":
  <int>}`.
- Tests:
  - Golden-fixture CSV.
  - Round-trip: extract from session A → upload to session B
    (with reviewers / reviewees pre-populated to match) →
    assignments match.
  - Multi-instrument session: N assignments × M instruments ⇒
    N×M rows in the output.

### PR 5 — Responses extract

**Goal.** A new CSV shape for response data — read-only, no
import counterpart. Designed for downstream analysis: each row
is self-contained (denormalized join keys) so an analyst can
open the file in Excel without joining against the other CSVs.

- New module `app/services/extracts/responses_extract.py` with
  `serialize_responses(session) -> Iterable[Row]`. Column order:
  `ReviewerEmail`, `RevieweeEmail`, `InstrumentName`,
  `InstrumentShortLabel`, `FieldKey`, `FieldLabel`, `Value`,
  `SavedAt` (ISO-8601), `SubmittedAt` (ISO-8601 or empty for
  saved-but-not-submitted), `Version`.
- One row per `Response` row in the database (already at
  `(assignment_id, response_field_id)` granularity per the
  unique-constraint at `app/db/models/response.py:19`). Order
  rows by `(ReviewerEmail, RevieweeEmail, instrument.order,
  response_field.order)` — deterministic, matches the reviewer
  surface's display order.
- **Empty values.** A `null` `Response.value` (the reviewer
  cleared the field) emits an empty cell. A reviewer who never
  saved any value for a field has no `Response` row and so emits
  no row in the CSV — the absence of a row signals "no response
  recorded" by itself. This keeps the CSV row count equal to
  `len(responses)` and makes "responses received" a one-line
  count from the file.
- **Numeric / list values.** Integer / decimal values export as
  their `Response.value` Text representation (already
  serialization-stable from the reviewer surface). List-type
  responses export as the same comma-separated literal the
  database stores. No type column on the responses extract — if
  a downstream consumer needs typing, they join against the
  Session settings extract on `FieldKey`.
- New route `GET /operator/sessions/{id}/export/responses.csv`
  + audit `session.responses_extracted` with `{"row_count":
  <int>}`.
- Streams the CSV from a yielding generator so a session with
  100k responses doesn't OOM the worker (`StreamingResponse`
  + a tuned chunk size; verify under integration test by
  asserting the response is `chunked` and not buffered).
- Tests:
  - Golden-fixture CSV.
  - Empty session (no responses): header row only.
  - Numeric / decimal / list response types each round-trip
    through their `Response.value` text representation
    correctly.
  - Saved-but-not-submitted vs. submitted: the
    `SubmittedAt` column distinguishes them.
  - Multi-instrument session: rows from all instruments
    interleaved per the deterministic order.

### PR 6 — Wire Extract Data card downloads + zip bundle

**Goal.** Flip the five Extract Data rows + zip-bundle footer
from inert (Segment 11H PR B scaffold state) to live, retire
the temporary "Download config" button PR 1 placed on Session
Details, and graduate Quick Setup's slot 4 (configuration-
import placeholder) to its live form.

**Depends on Segment 11H PR B**, which ships the inert Extract
Data card scaffold (`_extract_data_card.html` partial,
`extract_data_row` macro, `ExtractDataRow` dataclass +
`views.build_extract_data_context`). PR 6 only flips
`is_wired=True` and supplies `download_url` per row; no markup
changes.

- **No partial / macro / dataclass changes.** 11H PR B is the
  source of truth for the card's DOM contract. PR 6 extends
  `views.build_extract_data_context` to populate
  `download_url` per row from the routes shipped in PRs 1
  and 3-5:
  - Settings row → `/operator/sessions/{id}/export-config.csv`
    (PR 1).
  - Reviewers / Reviewees rows → the routes from PR 3.
  - Assignments row → the route from PR 4.
  - Responses row → the route from PR 5.
  - "Download all" footer → the new `/export.zip` route this
    PR adds.
- The
  `responses.session_response_count(session)` helper is
  already present from 11H PR B; PR 6 doesn't add it.
- New route `GET /operator/sessions/{id}/export.zip` streaming
  a zip with all five CSVs at the canonical filenames. Use
  `zipfile.ZipFile(..., mode="w")` over a `BytesIO` for
  small-to-medium sessions; revisit chunked streaming if the
  responses CSV proves too big for a 30s App Service request
  budget at production scale (track in `docs/status.md` as a
  Segment 14 follow-up). Audit `session.bundle_extracted` with
  `{"row_counts": {"settings": ..., "reviewers": ..., ...}}`.
- Quick Setup configuration-import slot (slot 4): graduate from
  the inert state 11H PR A shipped. Per 11H's seam contract,
  this is one adapter change in
  `views.build_quick_setup_context(session)`: flip slot 4's
  `is_wired=True` and supply
  `wire_url="/operator/sessions/{id}/import-config"` (the
  route PR 2 shipped). The slot then renders as a live `<form
  action="…/import-config" method="post"
  enctype="multipart/form-data">` with the same file input +
  submit shape as slots 1-3 and the same inline confirmation
  banner pattern Segment 11J established (cookie-driven lock
  state via `qsu_{session_id}`, banner-warning above the submit
  form on populated session, scoped `.banner.banner-error` via
  `?quick_setup_error=settings&quick_setup_reason={parse|lifecycle|needs_confirm}`
  on rejection, mandatory `.btn.alert` Cancel returning to a
  clean URL with the slot fragment).
- Retire the temporary Session Details "Download config"
  button from PR 1 — its place is taken by the Session settings
  row in the new Extract Data card (already rendered by 11H,
  flipped live by this PR).
- Tests:
  - Card renders five download rows on a populated session
    with the right counts.
  - Card renders five download rows on an empty session with
    zero counts (still functional — empty CSVs are valid).
  - Lock state on `ready` / `closed`: card stays interactive
    (extraction is read-only).
  - Zip bundle round-trip: download → unzip → each member CSV
    matches the per-file extract byte-for-byte.
  - Configuration-import slot Quick Setup integration:
    upload via the slot 303s through PR 2's import path; lock
    states gate per the existing slot rules.

## Implementation pointers

- **One CSV vocabulary, two shapes.** PRs 1-2's configuration CSV
  is the 3-column key/value/data-type shape. PRs 3-5's per-entity
  extracts are wide CSVs whose column order matches the existing
  per-entity importers (so reviewer / reviewee / assignment files
  round-trip with the upload flows on the Manage pages and on
  Quick Setup). Don't try to unify the two shapes — they serve
  different purposes and the per-entity round-trip is what makes
  the extracts useful.
- **Filename convention.** Every download is
  `session-{session.code}-{kind}.csv` (or `.zip` for the bundle).
  The session code is operator-typed and stable; using the
  numeric `session.id` would be opaque. Centralise the filename
  in a helper (`extracts.filename(session, kind)`) so every
  route reaches for the same string.
- **Streaming.** Wrap each extract route's body in
  `StreamingResponse(stream_csv(rows), media_type="text/csv")` to
  keep memory flat on large sessions. The responses extract is
  the one that matters at production scale; the others are
  small enough that streaming is just consistency.
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

- **Reviewer / reviewee / assignment import via 12A.** Existing
  per-table upload flows on the Manage pages and on Quick Setup
  (Segment 11J) stay the source of truth. 12A's per-entity CSVs
  are extract-only; they reuse the importers' column shapes
  precisely so an operator can feed them back through those
  existing upload flows without conversion.
- **Operator-editable email templates** — Segment 11E. When
  `email_template_overrides` ships, fold its key path into the
  export schema as a follow-on patch.
- **Audit retention / audit-log export** — rest of Segment 12.
  This segment's importer writes a single
  `session.config_imported` audit event; the extracts each emit
  one event per download. Per-row diffs are not emitted (would
  balloon the event log).
- **Audit-event `detail` schema convention** — Segment 11K. The
  extract audit events here use the simplest
  `{"row_count": <int>}` shape; if 11K lands first, fold its
  convention in.
- **Cross-deployment / cross-version** — assumes same app version
  on both ends. A future schema-versioned wrapper (`# version: 1`
  comment line at the top of each CSV) is the natural extension
  but not in scope here.
- **Segment 11H (Extract Data) as a separate segment.** Folded
  into 12A by this plan; remove its entry from
  `guide/todo_master.md` "Upcoming" when PR 6 lands.

## Test impact

- New unit tests per extract module —
  `tests/unit/test_session_config_io.py` (round-trip,
  per-row-type parsing, error collection),
  `tests/unit/test_reviewers_extract.py`,
  `tests/unit/test_reviewees_extract.py`,
  `tests/unit/test_assignments_extract.py`,
  `tests/unit/test_responses_extract.py`.
- Integration test files per route surface —
  `tests/integration/test_session_config_io_routes.py` (auth,
  lifecycle gate, multipart upload, audit events) and
  `tests/integration/test_extracts_routes.py` (auth, audit events,
  zip bundle, Extract Data card render).
- One golden fixture per extract under `tests/fixtures/extracts/`
  — `.csv` files for a fully-populated session. Future contract
  changes to any CSV shape have to deliberately update the
  fixture, which is the cheapest place to discuss them.
- **Round-trip integration tests** for the per-entity extracts:
  upload from session A → extract → re-upload to session B →
  assert state matches. These pin the contract that the extracts
  feed the existing importers without conversion.
- No changes to the existing reviewer / reviewee / assignment
  upload tests — those flows stay untouched.

## Doc impact

- `docs/status.md` gains a timeline entry per PR.
- `guide/todo_master.md`:
  - Adds Segment 12A under **Upcoming** before PR 1 ships;
    moves to **Done** under the existing Segment 11 / Resolved
    siblings once PR 6 lands.
  - **Removes the standalone "Segment 11H — Extract Data"
    entry** from "Upcoming" (folded into 12A by this plan).
  - Updates the "Open question on Segment 12 scope" footer:
    with Extract Data folded in, Segment 12 narrows to
    audit-retention only, gated on Segment 11K.
- `guide/segment_11J_quick_setup_card.md` — the configuration-import slot's
  graduation step (PR 6) is now pinned; update 11J's
  "Interaction with Segment 12A" section to point at PR 6 by
  name when 12A lands.
- `spec/architecture.md` — one-liner under "Data import /
  export" pointing at the CSV shapes; verify on PR 1 review.
- No spec doc for the CSV shapes themselves — this guide doubles
  as the spec until the format proves stable across two or three
  consumers; promote then.
