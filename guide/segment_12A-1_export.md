# Segment 12A-1 — Session export (settings + reviewers + reviewees + assignments)

The first user-facing slice of Segment 12A
(`guide/segment_12A_export_and_import.md`). Ships **four CSV
downloads** off the Extract Data card on Session Home, no import
counterpart, no zip bundle, no responses CSV, no RuleSet JSON
portability. Those are 12A's later PRs — this slice exists to
land the export half of the round-trip in isolation so operators
can extract a session today even before the import side is wired.

## Goal

Give the operator four downloads on Session Home that together
capture everything they typed to set up the session:

- **Session settings** — every operator-typed configuration field
  in one CSV (the 12A "Scenario A" snapshot, minus the per-entity
  CSVs).
- **Reviewers** — the reviewer roster as a CSV that round-trips
  with the existing reviewer upload.
- **Reviewees** — same shape for reviewees.
- **Assignments** — manual assignment rows as a CSV that
  round-trips with the existing manual-assignments upload. **Only
  emitted on `assignment_mode == "manual"` sessions** — rule-based
  sessions surface the row disabled with an explanatory note (per
  12A Scenario A: "snapshot the inputs, never the outputs").

Read-only. No lifecycle gate — extraction is useful in `draft`
(sanity-check the config you typed), `validated`, `ready` (mid-
flight snapshot), and `closed` (final). The Extract Data card
stays interactive in every state, including behind the yellow
lock card (lock disables setup mutations only, not reads).

## Scope vs. the parent 12A plan

| 12A PR | In 12A-1? | Notes |
|---|---|---|
| PR 1 — Config (settings) export | ✅ | Renamed file / row order tightened — see "Differences from 12A" below. |
| PR 2 — Config import | ❌ | Deferred. 12A-1 ships export only. |
| PR 3 — Reviewers + reviewees extract | ✅ | Same column shapes as the existing importers. |
| PR 4 — Assignments extract | ✅ | Same `manual`-only gate as 12A. |
| PR 5 — Responses extract | ❌ | Deferred. Responses are reviewer-determined; they don't belong in the same "operator-typed config" cut and they're the largest CSV to size for streaming. |
| PR 6 — Wire Extract Data card + zip bundle | Partial | This segment flips four of the five `is_wired` rows live; the Responses row stays inert. Zip bundle is deferred to a follow-on slice. |
| PR 7 — RuleSet JSON export / import | ❌ | Workspace-scoped, anchored on the Rule Builder card — orthogonal to Session Home and gated on Segment 13A. |

After 12A-1 ships, the remaining 12A work is: the Responses
extract (PR 5), the import side (PR 2), the zip bundle (the
trailing half of PR 6), and the RuleSet JSON round-trip (PR 7).
Each of those can land as a self-contained follow-on; nothing in
12A-1 forecloses them.

## Differences from 12A

Three deliberate departures from the parent plan, all small:

1. **Filename convention.** Files use `{code}_{kind}.csv` (e.g.
   `CS101_reviewers.csv`, `CS101_settings.csv`) rather than 12A's
   `session-{code}-{kind}.csv`. Shorter; the `{code}_` prefix is
   enough to disambiguate downloads from different sessions
   sitting in a downloads folder. Centralised in
   `extracts.filename(session, kind)` so the convention is one
   string to change later if needed.
2. **Inert-but-coming columns are included on the settings CSV.**
   Per the parent plan's "snapshot the inputs" rule, 12A-1 also
   exports operator-typed columns that are scaffolded today but
   not yet wired by their owning segment — e.g.
   `instruments[N].sort_display_fields` (Segment 13B),
   `instruments[N].group_kind` (Segment 13C), and the
   `session_field_labels` overrides (Segment 15A). Reasoning: an
   operator who configures one of those settings on the session
   side after the owning segment lights up should not have to
   retype it on the next session just because the export shipped
   before the wire-up did. Once the owning segment ships, the
   row in this CSV is the same row the import would consume — no
   re-cut of the export needed. See "Settings CSV contents" for
   the full inert-but-included list and the rationale per row.
3. **Card state after this segment.** PR 6 of 12A flips all five
   Extract Data rows live in one shot. 12A-1 flips four (settings
   / reviewers / reviewees / assignments) and leaves the
   Responses row inert with its existing "Wired in Segment 12A
   PR 5" coming-in note. The bundle footer also stays inert.
   Operators see four working downloads; the two stragglers keep
   the same scaffolded affordance they have today.

Everything else in 12A's PRs 1 / 3 / 4 carries over verbatim:
the 3-column `field,value,data_type` shape for the settings CSV,
the per-entity column shapes that match the existing importers,
the `manual`-only gate on assignments, and the per-download audit
events (`session.{settings,reviewers,reviewees,assignments}_extracted`,
each with `{"row_count": <int>}`).

## Settings CSV contents

Source of truth for the curation: `spec/settings_inventory.md`.
The cut is **everything the operator typed to set up this
session, minus the per-entity rosters and minus assignments
(which ride their own CSV when the mode is manual)**.

### §2 Per-session settings (`sessions` table)

User-typed and exported:

- `session.name` (string)
- `session.code` (string) — exported as the snapshot value.
  When the import side lands (12A PR 2), this row becomes a
  fallback per Scenario A — operator-typed values on Create New
  Session win. 12A-1 just emits it; the suffix-derivation rule
  is the importer's concern.
- `session.description` (string)
- `session.deadline` (datetime; ISO-8601 with offset, empty cell
  ⇒ no deadline)
- `session.help_contact` (string)

Excluded — not user-typed:

- `session.status` — lifecycle output. Every imported session
  lands back in `draft`; export omits.
- `session.assignment_mode` — system-set by whichever assignment
  generation path the operator runs. Snapshot consults it once at
  export time to decide whether to emit the assignments CSV;
  doesn't appear in the settings CSV.
- `session.created_by_user_id` — identity / provenance.

### §3 Email-template overrides

All 12 string keys + the boolean toggle, mirroring
`app.services.email_templates.OVERRIDE_KEYS`:

- `email_overrides.invitation.{subject,body,cc,bcc}` (string × 4)
- `email_overrides.reminder.{subject,body,cc,bcc}` (string × 4)
- `email_overrides.responses_received.{subject,body,cc,bcc}`
  (string × 4)
- `email_overrides.responses_received.enabled` (boolean; default
  `true` when absent)

Empty value cell ⇒ "use the default" (matches the live resolver's
`DEFAULT_*` fallback). Each key is exported even when the
operator left it at default — a row with an empty value is the
explicit "no override" signal.

### §4 Per-instrument settings (`instruments` table)

Keyed by 1-based position (`(Instrument.order, Instrument.id)`
order on export). User-typed and exported per instrument N:

- `instruments[N].name` (string, required)
- `instruments[N].short_label` (string)
- `instruments[N].description` (string)
- `instruments[N].order` (integer; emitted but typically
  derivable from N — the importer treats N as authoritative)
- `instruments[N].accepting_responses` (boolean)
- `instruments[N].responses_visible_when_closed` (boolean)

**Inert-but-included** (per the §"Differences from 12A" §2
note — operator-typed columns scaffolded today but not yet wired
by their owning segment):

- `instruments[N].sort_display_fields` (json) — operator-defined
  default sort spec (Segment 13B). Wired by 13B PR 2; until then,
  always serialises as the empty list `[]`. Included so once 13B
  lights up, sessions with operator-set sort defaults round-trip
  without an export-shape change.
- `instruments[N].group_kind` (enum: `tag_1` / `tag_2` / `tag_3`
  or empty for regular per-reviewee — Segment 13C). Wired by 13C
  PR 2 (creation flow) — until then, always serialises as empty.

Excluded — not user-typed:

- `instruments[N].deadline_closed_at` — auto-set when the
  deadline passes.
- `instruments[N].rule_set_id` — selection of a per-session
  RuleSet snapshot (Segment 15B). Although the operator picks
  it, the value points at a `session_rule_sets` row that is
  itself a snapshot of operator typing in the Rule Builder. For
  cross-session export the RuleSet wants to travel as its own
  JSON (12A PR 7's surface) rather than as an FK that won't
  resolve on the destination. 12A-1 omits it; whichever PR
  brings session-scoped RuleSet portability online folds it in.

### §4.5 Per-session Response Type Definitions

Keyed by `response_type` (operator-typed name; unique within a
session). Only `is_seeded=False` rows are exported — seeded RTDs
regenerate from `SEED_RESPONSE_TYPE_DEFINITIONS` on session
create:

- `rtds[<response_type>].data_type` (enum: `int` / `decimal` /
  `short_text` / `long_text` / `list`)
- `rtds[<response_type>].min` (decimal)
- `rtds[<response_type>].max` (decimal)
- `rtds[<response_type>].step` (decimal)
- `rtds[<response_type>].list_csv` (csv_list)

Excluded — not user-typed:

- `is_seeded` / `seed_order` — system-emitted markers.
- `library_origin_id` — provenance pointer (Segment 15C). The
  per-session row is the source of truth; the link back to the
  library row is informational and doesn't survive a
  cross-deployment hop.

### Per-instrument display fields

Keyed by 1-based position
(`(InstrumentDisplayField.order, .id)` order on export). User-
typed:

- `instruments[N].display_fields[M].source_type` (enum:
  `reviewee` / `pair_context`)
- `instruments[N].display_fields[M].source_field` (string —
  e.g. `tag_1`, `profile_link`, `1`/`2`/`3`)
- `instruments[N].display_fields[M].label` (string; empty ⇒
  inferred fallback per `instruments_service.display_field_label`)
- `instruments[N].display_fields[M].visible` (boolean)

`validation` JSON is **not exported** — it's derived on import
from the RTD via `validation_block_for_rtd`.

### Per-instrument response fields

Keyed by 1-based position. User-typed:

- `instruments[N].response_fields[M].field_key` (string,
  required) — stable machine identifier; `(N, field_key)` is the
  upsert key on import so labels can be renamed without losing
  field identity.
- `instruments[N].response_fields[M].label` (string, required)
- `instruments[N].response_fields[M].response_type` (string —
  references either a seeded RTD name or an operator-defined
  `rtds[<name>]` row exported earlier in the same file)
- `instruments[N].response_fields[M].required` (boolean)
- `instruments[N].response_fields[M].help_text` (string)
- `instruments[N].response_fields[M].help_text_visible` (boolean)

### §9 Inert-but-included (Segment 15A friendly labels)

Per-session friendly-label overrides for tag / pair-context
fields. Wired by 15A Slice 1 (resolver) + Slice 3 (Settings
editor surface). Until then, the table is empty in every
session — exporting an empty section is a no-op, but pinning the
key shape now means a future 15A-equipped session round-trips
without an export-shape change.

Keyed by `(source_type, source_field)`:

- `field_labels.<source_type>.<source_field>` (string) — e.g.
  `field_labels.reviewer.tag_1` = `"Cohort"` overrides the
  `Tag1` heading on the Reviewer Setup page.

`source_type` accepts `reviewer` / `reviewee` / `pair_context`
(matching the 15A schema). `source_field` follows the same
convention as display-field keys (`tag_1` / `tag_2` / `tag_3`
for the tag sources; `1` / `2` / `3` for `pair_context`).

### Excluded from the settings CSV

All for the same reason — not operator-typed:

- §1 Operator-level settings (SMTP credentials, etc.) — per-
  operator, not per-session. Each operator configures their own
  under Operator Settings.
- §5 Reviewers / Reviewees — ride their own per-entity CSVs in
  this segment.
- §6 Personal RuleSets — workspace-scoped, not session-scoped.
  12A PR 7 owns RuleSet portability via JSON.
- §7 Browser-local UI state — cookies, localStorage, URL
  params. Cosmetic per-browser preferences.
- §8 Deployer-set environment configuration — bounds what the
  operator can do; the operator does not edit it.
- §9 `session_rule_sets` snapshots — session-internal copies
  derived from RuleSet editing. The RuleSet wants to travel as
  its own JSON.
- §9 `operator_response_type_definitions` — operator-library
  tier (operator-level, not per-session).
- Audit events — system-emitted record of derivations. Forensic
  audit is Scenario B's job (Segment 12B).
- Invitations + tokens, email outbox rows, reviewer responses,
  validation report state — all derived / system-emitted /
  reviewer-determined.

## Per-entity CSVs

Each matches the column shape of the existing importer so the
file feeds back through the upload flows on the Manage pages and
on Quick Setup without conversion.

### Reviewers — `{code}_reviewers.csv`

Columns (matching `csv_imports.parse_reviewer_csv`):

```
ReviewerName,ReviewerEmail,ReviewerTag1,ReviewerTag2,ReviewerTag3
```

One row per reviewer (active and inactive both included; the
importer treats inactive rows as inactive on the next session
anyway). Order: `(status DESC, name, email)` — active rows
first, then inactive, deterministic within each.

### Reviewees — `{code}_reviewees.csv`

Columns (matching the reviewee importer):

```
RevieweeName,RevieweeEmail,RevieweeTag1,RevieweeTag2,RevieweeTag3,ProfileLink
```

Plus any `pair_context_*` columns the per-session schema carries
(read from the same place the importer reads them). Same
ordering rule as reviewers.

### Assignments — `{code}_assignments.csv`

Columns (matching `assignments.parse_manual_csv`):

```
ReviewerEmail,RevieweeEmail,IncludeAssignment,Instrument
```

`IncludeAssignment` is `true` for active assignments and `false`
for inactive — preserves the active/inactive split exactly across
upload round-trip. `Instrument` carries the per-instrument label
(matching `_instrument_label`). One row per
(assignment, instrument) tuple — when a session has multiple
instruments, the same `(ReviewerEmail, RevieweeEmail)` pair
emits N rows.

**Conditional emission.** Per 12A Scenario A, the assignments
CSV is **only emitted when `session.assignment_mode == "manual"`**
— i.e. the operator typed the rows by hand. On a rule-based
session the route returns 404, and the Extract Data card row
renders disabled with the explanatory note: "Assignments derived
from RuleSet `<name>`; rule-based assignment export is part of
the upcoming RuleSet JSON portability segment. Run Generate on
the new session to materialise from the RuleSet there." (No
zip-bundle change here — bundles are out of scope for 12A-1.)

## Routes

Four new routes, all GET, all operator-only via the existing
per-session permission check:

- `GET /operator/sessions/{id}/export/settings.csv`
- `GET /operator/sessions/{id}/export/reviewers.csv`
- `GET /operator/sessions/{id}/export/reviewees.csv`
- `GET /operator/sessions/{id}/export/assignments.csv` — 404
  on rule-based sessions

Each streams `text/csv` via `StreamingResponse(stream_csv(rows),
media_type="text/csv")` with `Content-Disposition: attachment;
filename="{code}_{kind}.csv"`. Each emits its own audit event
(`session.{settings,reviewers,reviewees,assignments}_extracted`)
with detail `{"row_count": <int>}`.

## Service modules

Following 12A's split:

- `app/services/session_config_io.py` — `Row = NamedTuple("Row",
  [("field", str), ("value", str), ("data_type", str)])` and
  `serialize_session_config(session) -> list[Row]`. Pure
  function; no DB writes. Section ordering is pinned in a unit
  test (see "Tests" below).
- `app/services/extracts/__init__.py` — shared
  `stream_csv(rows, fieldnames) -> Iterator[bytes]` over a
  chunked `csv.writer`, plus `filename(session, kind) -> str`
  centralising the `{code}_{kind}.csv` convention.
- `app/services/extracts/reviewers_extract.py` —
  `serialize_reviewers(session) -> Iterable[Row]`.
- `app/services/extracts/reviewees_extract.py` —
  `serialize_reviewees(session) -> Iterable[Row]`.
- `app/services/extracts/assignments_extract.py` —
  `serialize_assignments(session) -> Iterable[Row]`. Raises a
  domain error (caught by the route as a 404) when
  `session.assignment_mode != "manual"`.

Routes import these and stay thin (parse request → call
service → wrap in `StreamingResponse` → emit audit). No
template work for the route handlers themselves; the card render
work happens in the view adapter (see next).

## Card wire-up

The Extract Data card already exists with all five rows scaffolded
inert (Segment 11H PR B; current state visible at
`app/web/views/_extract_data.py`). 12A-1 extends
`build_extract_data_context` to:

- Flip `is_wired=True` on the Settings, Reviewers, Reviewees, and
  Assignments rows; supply `download_url` from the four routes
  above.
- Update each row's `filename` to the new `{code}_{kind}.csv`
  convention.
- On the Assignments row: when `session.assignment_mode !=
  "manual"`, leave `is_wired=False` and replace the `coming_in`
  string with the rule-based explanatory note ("Assignments
  derived from RuleSet `<name>`; …"). The DOM contract is
  unchanged — the card already renders disabled rows that way.
- Leave the Responses row inert with its existing
  `coming_in="Wired in Segment 12A PR 5"`.
- Leave the bundle footer inert with its existing
  `coming_in="Wired in Segment 12A PR 6"`.

No partial / macro / dataclass changes — 11H PR B is the source
of truth for the card's DOM contract.

## Audit

Four new audit event types, registered in `EVENT_SCHEMAS` per
the strict-mode test gate:

- `session.settings_extracted` — detail `{"row_count": <int>}`.
- `session.reviewers_extracted` — detail `{"row_count": <int>}`.
- `session.reviewees_extracted` — detail `{"row_count": <int>}`.
- `session.assignments_extracted` — detail `{"row_count": <int>}`.

All emitted from within the route handler after the
`StreamingResponse` is built (the row count is known at
serialise time — the export iterates the rows once for the
audit count, then again for the stream). Read paths emit
single-event audits per project convention; no per-row diffs.

## CSV format

The settings CSV uses the 3-column `field,value,data_type`
shape from 12A. Carry-over verbatim:

```
field,value,data_type
session.name,Mid-semester peer review,string
session.code,CS101-2026S,string
session.deadline,2026-05-15T17:00:00+00:00,datetime
email_overrides.invitation.subject,,string
email_overrides.responses_received.enabled,true,boolean
rtds[Likert5].data_type,int,enum
rtds[Likert5].min,1,decimal
rtds[Likert5].max,5,decimal
instruments[1].name,Peer evaluation,string
instruments[1].accepting_responses,true,boolean
instruments[1].sort_display_fields,[],json
field_labels.reviewer.tag_1,Cohort,string
…
```

`data_type` values (descriptive of the cell, not of any
underlying RTD's `data_type`): `string` / `integer` / `decimal`
/ `boolean` / `datetime` / `enum` / `csv_list` / `json`. The
`json` type is new vs. 12A — needed for `sort_display_fields`
which serialises a list of dicts. `boolean` accepts
`true`/`false` (case-insensitive) on import; emits lowercase
on export. `datetime` is ISO-8601 with timezone offset; empty
cell ⇒ `None`.

The per-entity CSVs use their natural wide-row shapes — see
"Per-entity CSVs" above.

### Row order on the settings CSV

Stable, deterministic, designed to read top-to-bottom like a
setup walkthrough:

1. Session-level rows (name → code → description → deadline →
   help_contact).
2. Email-template override rows (invitation → reminder →
   responses_received, with subject → body → cc → bcc → enabled
   inside each kind).
3. Operator-defined RTDs, sorted by `seed_order` then
   `response_type`.
4. Each instrument block in order (`(Instrument.order,
   Instrument.id)`):
   1. Instrument-level rows.
   2. Display fields for that instrument.
   3. Response fields for that instrument.
5. Field-label overrides (sorted by `(source_type,
   source_field)`).

Pinned in `serialize_session_config` and pinned again in a unit
test — diff-noise on re-export is what makes the CSV worth
maintaining as a template.

## PR sequence

Sized as **3 PRs** in dependency order. PRs 2 + 3 are
independent of each other and parallel-shippable once PR 1's
shared helpers are in place.

### PR 1 — Settings export + shared helpers

- `app/services/session_config_io.py` with `Row`,
  `serialize_session_config(session)`, and the per-section
  helpers (session, email overrides, RTDs, instruments, display
  fields, response fields, field labels).
- `app/services/extracts/__init__.py` with `stream_csv` +
  `filename(session, kind)`.
- New route `GET /operator/sessions/{id}/export/settings.csv`.
- Audit `session.settings_extracted` registered in
  `EVENT_SCHEMAS`.
- Card wire-up: flip the Settings row live in
  `build_extract_data_context`. Update its `filename` to
  `{code}_settings.csv`.
- Tests:
  - Unit per row class on `serialize_session_config` (one test
    per section).
  - Golden-fixture test pinning the byte-exact output for a
    fully-populated session (`tests/fixtures/extracts/
    settings.csv`).
  - Integration test for the route (auth, audit emission, 404
    on unknown session, no lifecycle gate).
  - Inert-but-included sections: empty `sort_display_fields`,
    empty `group_kind`, empty `field_labels` block all emit the
    expected default rows / no rows respectively.

### PR 2 — Reviewers + reviewees extract

- `app/services/extracts/reviewers_extract.py` +
  `reviewees_extract.py`.
- Two new routes (`/export/reviewers.csv`, `/export/reviewees.csv`).
- Two new audit events registered in `EVENT_SCHEMAS`.
- Card wire-up: flip both rows live; update filenames to the new
  `{code}_{kind}.csv` convention.
- Tests:
  - Golden-fixture CSV per extract.
  - Round-trip: extract from session A → upload to session B
    via the existing `csv_imports.parse_reviewer_csv` +
    `save_reviewers` path → assert session B's reviewer set
    matches A's. Same for reviewees.
  - Empty-session case: header row only; `row_count=0` in the
    audit.

### PR 3 — Assignments extract (manual-only)

- `app/services/extracts/assignments_extract.py` with the
  `assignment_mode == "manual"` gate.
- New route `/export/assignments.csv` returning 404 on
  rule-based sessions.
- Audit `session.assignments_extracted` registered in
  `EVENT_SCHEMAS`.
- Card wire-up: flip the Assignments row live on manual
  sessions; on rule-based sessions render the row disabled with
  the explanatory note instead.
- Tests:
  - Golden-fixture CSV.
  - Round-trip: extract from session A → upload to session B
    (with reviewers / reviewees pre-populated to match) →
    assignments match.
  - Multi-instrument session: N assignments × M instruments ⇒
    N×M rows.
  - Rule-based session: route returns 404; card row renders
    disabled with the rule-based note (assert by inspecting the
    `ExtractDataRow` returned by `build_extract_data_context`).

## Out of scope (carried in 12A's later PRs)

- **Responses extract.** Deferred to 12A PR 5 — the largest
  extract by row count, the one that needs streaming under
  production load, and the only one with no import counterpart.
- **Zip bundle (`/export.zip`).** Deferred to the trailing half
  of 12A PR 6. Without the Responses extract the bundle would
  be incomplete; ship them together.
- **Configuration import (`POST /operator/sessions/{id}/import-config`)
  + Quick Setup slot 4 graduation.** Deferred to 12A PR 2 + the
  Quick Setup-side half of PR 6. The settings CSV PR 1 of this
  segment ships is the exact shape PR 2 will consume — the
  round-trip test lands when PR 2 does.
- **RuleSet JSON export / import.** Deferred to 12A PR 7,
  workspace-scoped, gated on Segment 13A.
- **Cross-deployment / cross-version round-trip.** Same
  schema-version assumption on both ends; a future
  `# version: 1` comment line at the top of each CSV is the
  natural extension but not in scope here.

## Doc impact

- `docs/status.md` gains one timeline entry per PR.
- `guide/todo_master.md` adds Segment 12A-1 under **Upcoming**
  before PR 1 ships; moves to **Done** once PR 3 lands. The
  parent Segment 12A entry stays put — its remaining PRs
  (Responses extract, import, zip bundle, RuleSet portability)
  ship after.
- `guide/segment_12A_export_and_import.md` gains a "Status
  (2026-05-09)" note at the top pointing at this segment as the
  shipped export half, plus a one-liner per affected PR
  ("Settings export shipped in 12A-1 PR 1 — this PR is now the
  import half only", etc.).
- `spec/architecture.md` — one-liner under "Data import /
  export" pointing at the four CSV shapes; verify on PR 1
  review.
- No spec doc for the CSV shapes themselves — this guide doubles
  as the spec until the format proves stable across two or three
  consumers; promote then.

## Test impact

- New unit tests:
  - `tests/unit/test_session_config_io.py` (round-trip per row
    class, section ordering, inert-but-included defaults).
  - `tests/unit/test_reviewers_extract.py`,
    `tests/unit/test_reviewees_extract.py`,
    `tests/unit/test_assignments_extract.py`.
- New integration tests:
  - `tests/integration/test_extracts_routes.py` (auth, audit
    events, manual-only gate on assignments, no lifecycle gate
    on any of the four).
- Golden fixtures under `tests/fixtures/extracts/`:
  `settings.csv`, `reviewers.csv`, `reviewees.csv`,
  `assignments.csv`. Future contract changes have to
  deliberately update each fixture.
- Round-trip tests for the per-entity extracts: extract from
  session A → re-upload to session B → assert state matches.
  These pin the contract that the extracts feed the existing
  importers without conversion.
