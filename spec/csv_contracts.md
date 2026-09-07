# CSV contracts — spec

**The column shapes and parsing rules that govern every CSV the
operator extracts or uploads.** Multiple extract paths and five
import paths share a small library of primitives and a strict
round-trip guarantee on the five main roster-shaped pairs
(Reviewers, Reviewees, Relationships, Observers, Settings).
Observers has both a wired importer and an extract (W13, PR #1755);
its tile is conditionally shown on the Extract Setup card when
`observers_enabled`.

When the code drifts from this spec, fix the code. Each extract
file pins its `HEADER` tuple as a module constant; each importer
calls `_missing_columns_issues` against the same names. Renaming
a column on either side is a deliberate spec edit.

Cross-references:

- **`app/services/extracts/`** — five extract modules + the shared
  `__init__.py` (`stream_csv`, `filename`).
- **`app/services/csv_imports.py`** — two roster importers
  (Reviewers, Reviewees) + the shared parsing primitives.
- **`app/services/relationships.py`** — the Relationships
  importer.
- **`app/services/session_config_io/`** —
  `serialize_session_config` ↔ `apply_session_config` (Settings
  round-trip). Split into `_serialize.py` (export) + `_apply.py`
  (import) + `_rows.py`, with `__init__.py` re-exporting the
  public surface.
- **`spec/settings_inventory.md`** §10 — coverage table for the
  five extracts.

---

## 1. CSV envelope (every file)

The envelope is the same shape on both sides — Python `csv.reader`
/ `csv.writer` defaults with one explicit choice:

| Concern | Choice |
|---|---|
| Encoding | UTF-8. Files with a BOM are tolerated by `decode_csv` (BOM stripped on read). |
| Delimiter | Comma. |
| Quoting | Python `csv.QUOTE_MINIMAL` — values containing comma, quote, or newline are double-quoted. |
| Line endings | `\r\n` on write (Python `csv` default); `\r\n` or `\n` accepted on read. |
| Header row | Always present, always first. |
| Empty trailing newline | Tolerated on read; emitted on write per Python defaults. |
| Filename convention | `{session_code}_{kind}.csv` via `extracts.filename(session, kind)`. E.g. `CS101_reviewers.csv`. |

The header row is the **contract** — every importer matches by
header name (case-sensitive), not by position. An extra column
the operator added in Excel is ignored; a missing required
column is a parse error.

### 1a. Friendly-label header suffix (Segment 19C Item 1)

The operator-definable friendly labels for the nine renamable tag
slots — `ReviewerTag1..3`, `RevieweeTag1..3`, `PairContextTag1..3`
— round-trip through the **roster CSV header** as the **sole
carrier**. A tag column may carry its label as a suffix after the
**first** period:

```
ReviewerTag1.Tutor        → reviewer.tag_1, friendly label "Tutor"
PairContextTag1.Mentor of  → pair_context.1, friendly label "Mentor of"
ReviewerTag1               → reviewer.tag_1, no suffix (see below)
```

- **First-period split, labelable columns only.** Only those nine
  tag columns are split, and only on the first period — so a label
  may itself contain periods (`RevieweeTag2.Dept. Head`). Every
  other column (identity, `Status`, unknown) passes through
  unchanged, even if it contains a period.
- **Import writes `session_field_labels`** (via `field_labels`), the
  same store the per-page label editor uses — the header is a fourth
  write path, not a new store.
- **Bare header, or an absent tag column, CLEARS that slot's label.**
  A roster import is **wipe-and-replace** (`save_reviewers` &c.
  delete-and-reload the whole roster), so the uploaded file is the
  complete truth: a tag column with no suffix is the label analogue
  of a NULL tag value, and clears any existing override (resolving
  back to the built-in `Tag N` default). Clearing an already-unset
  slot is a no-op.
- **Export emits the suffix** when an override exists, bare
  otherwise (a slot on its default is never given a fabricated
  `Tag N` suffix) — so download → edit → re-import is symmetric.
- **Observer tags are out of scope** (single `tag_1`, no
  friendly-label affordance).
- Handled by `app.services.field_label_csv` (`split_header` /
  `normalize_headers` on import, `labeled_header` on export).

---

## 2. Five extracts (export contracts)

Each extract module declares a `HEADER: tuple[str, ...]` module
constant. The serialiser yields the header first, then one tuple
per row in a deterministic order so re-export of the same session
is byte-stable.

### 2.1 Reviewers — `extracts/reviewers_extract.py`

| # | Column | Source | Notes |
|---|---|---|---|
| 1 | `ReviewerName` | `reviewer.name` | Required on import. |
| 2 | `ReviewerEmail` | `reviewer.email` | Required on import. Used by the cross-table identity check and by `relationships.csv`'s FK. |
| 3 | `ReviewerTag1` | `reviewer.tag_1` | Optional on import. Empty cell ⇒ NULL. |
| 4 | `ReviewerTag2` | `reviewer.tag_2` | Same. |
| 5 | `ReviewerTag3` | `reviewer.tag_3` | Same. |
| 6 | `PhotoLink` | `reviewer.profile_link` | Optional. Rendered as a clickable link on the reviewer surface when populated. Mirrors the Reviewees `PhotoLink` column (W11, PR #1756). |
| 7 | `Status` | `reviewer.status` | Segment 18P PR C. `active` / `inactive`. Optional on import: blank/absent ⇒ `active`; any other value is a per-row error. |

**Row order:** active rows first (`status='active'`), then by
`name`, then by `email`. Deterministic.

### 2.2 Reviewees — `extracts/reviewees_extract.py`

| # | Column | Source | Notes |
|---|---|---|---|
| 1 | `RevieweeName` | `reviewee.name` | Required. |
| 2 | `RevieweeEmail` | `reviewee.email_or_identifier` | Required. Mirrors the rosters-CSV header even though the underlying column is `email_or_identifier` (non-email cohorts still use this header). |
| 3 | `RevieweeTag1` | `reviewee.tag_1` | Optional. |
| 4 | `RevieweeTag2` | `reviewee.tag_2` | Optional. |
| 5 | `RevieweeTag3` | `reviewee.tag_3` | Optional. |
| 6 | `PhotoLink` | `reviewee.profile_link` | Optional. Rendered as a clickable link on the reviewer surface when populated. |
| 7 | `Status` | `reviewee.status` | Segment 18P PR C. `active` / `inactive`. Optional on import: blank/absent ⇒ `active`; any other value is a per-row error. |

**Row order:** active rows first, then by `name`, then by
`email_or_identifier`.

### 2.3 Relationships — `extracts/relationships_extract.py`

Shipped 12A-3 PR 1. The pair-context round-trip.

| # | Column | Source | Notes |
|---|---|---|---|
| 1 | `ReviewerEmail` | `reviewer.email` (FK) | Required. Resolved against the session's reviewers on import. |
| 2 | `RevieweeEmail` | `reviewee.email_or_identifier` (FK) | Required. Resolved against the session's reviewees on import. |
| 3 | `PairContextTag1` | `relationship.tag_1` | Optional. Consumed by the rule engine's `pair_context.tag1` predicate. |
| 4 | `PairContextTag2` | `relationship.tag_2` | Same → `pair_context.tag2`. |
| 5 | `PairContextTag3` | `relationship.tag_3` | Same → `pair_context.tag3`. |
| 6 | `Status` | `relationship.status` | Lowercase `active` / `inactive`. Defaults to `active` when omitted on import. |

**Row order:** active first, then by reviewer email, then by
reviewee identifier.

### 2.4 Responses — `extracts/responses_extract.py`

Shipped 12A-1 PR 4 + #781 polish; preamble + positional
instrument naming added in Segment 18D. Analysis-facing per-session
CSV — the consumer is an external analyst, not the app. No import
counterpart (responses are reviewer-generated, not
operator-uploaded).

The file has two parts:

1. **Preamble** — one block per instrument: a row carrying the
   instrument's positional name (`instrument_1`, `instrument_2`,
   … by instrument order), then one `FieldKey, HelpText` row per
   response field (a field dictionary). A blank row separates the
   preamble from the table. A session with no instruments emits
   no preamble and no gap.
2. **Data table** — the 21-column wide format below.

| Block | Columns |
|---|---|
| Reviewer identity (5) | `ReviewerName`, `ReviewerEmail`, `ReviewerTag1`, `ReviewerTag2`, `ReviewerTag3` |
| Reviewee identity (5) | `RevieweeName`, `RevieweeEmail`, `RevieweeTag1`, `RevieweeTag2`, `RevieweeTag3` |
| Instrument (2) | `InstrumentName` (the positional id `instrument_{n}` — the operator's typed name is not exported), `InstrumentShortLabel` |
| Field context (3) | `FieldKey`, `FieldLabel`, `ResponseType` |
| Value (1) | `Value` (empty cell ⇒ reviewer cleared the field) |
| Self-review (1) | `SelfReview` — uppercase `TRUE` / `FALSE` per Excel idiom. Computed via `is_self_review(reviewer, reviewee)` (case-insensitive email match; `FALSE` for non-email reviewee identifiers). |
| Lifecycle (3) | `SavedAt`, `SubmittedAt`, `Version` |
| Instrument flavour (1) | `InstrumentFlavour` — derived `per-reviewee` / `group-scoped` (Segment 13C / 18D). Appended last so the original 20-column indices stay stable for existing analyst pipelines. |

An analyst joins a preamble help text to its data column via the
shared `FieldKey`.

`SavedAt` / `SubmittedAt` are ISO 8601 carrying the **session
zone's** UTC offset (e.g. `2026-06-02T08:00:00+08:00`), via
`date_formatting.iso_in_zone` — see `spec/timezone_display.md`.

**Streaming:** the data-table query uses `yield_per(1000)` cursor
streaming so large sessions don't materialise every Response
row in memory. Row order: `(reviewer_id, reviewee_id,
instrument.order, field.order)`.

### 2.5 Audit events — `extracts/audit_events_extract.py`

Shipped 12B PR 1. No operator-facing tile (relocates to Sys Admin
under Segment 16A); the route `GET /export/audit_log.csv` is
live.

| # | Column | Source | Notes |
|---|---|---|---|
| 1 | `EventType` | `event_type` | One of the registered types in `EVENT_SCHEMAS` (`app/services/audit.py`). |
| 2 | `Severity` | `severity` | `info` / `warning` / `error` (from the canonical envelope). |
| 3 | `Summary` | `summary` | Human-readable one-liner. |
| 4 | `ActorEmail` | LEFT JOIN through `actor_user_id` → `users.email`. Empty cell ⇒ system-emitted event with no actor. |
| 5 | `CorrelationId` | `correlation_id` | Request-scoped UUID. |
| 6 | `CreatedAt` | `created_at` | ISO 8601 in **UTC** (`...+00:00`); naive readbacks (SQLite) normalised to UTC for dialect-stable output. The audit log is the deliberate UTC exception (`spec/timezone_display.md`) — unlike the other per-session extracts, this column is *not* localised to the session zone. |
| 7 | `DetailJson` | `json.dumps(detail, sort_keys=True)` | Empty cell when `detail is None`. |

**Row order:** `(created_at ASC, id ASC)`. **Streaming:**
`yield_per(1000)`.

### 2.6 Entity stats — `extracts/entity_stats_extract.py`

Shipped 18H Part 3. Two **bundle-only** CSVs — a Reviewer stats
file and a Reviewee stats file — added to the Zip-all bundle.
They are deliberately **not** offered as individual downloads and
have **no importer**: the round-trippable Reviewers / Reviewees
CSVs keep that role, and adding stats columns to them would break
the importer contract. The module exposes `build_entity_stats`
(not a streaming serialiser); it returns both header-led row lists
in one pass.

Each carries the plain roster shape (§2.1 / §2.2 columns) plus
aggregate response-activity columns, every metric reported as a
**Draft / Submitted** pair (`submitted_at` unset vs set). Only
responses with a non-empty value count. A group-scoped
instrument's fanned-out answer counts once per group for the
field / char metrics on the reviewer side; both member reviewees
are still credited under `RevieweesReviewed*`.

Reviewer stats extra columns: `RevieweesReviewedDraft/Submitted`
(distinct reviewees with ≥1 non-empty response),
`FieldsAnsweredDraft/Submitted`,
`RequiredFieldsAnsweredDraft/Submitted`,
`StringResponseCharsDraft/Submitted` (sum of `len(value)` over
`String`-typed fields). Reviewee stats extra columns:
`ReviewersDraft/Submitted` (distinct reviewers) plus the same
three field / char pairs.

### 2.7 Per-instrument responses — `extracts/responses_extract.py` (`serialize_responses_for_instrument`)

Shipped 18H Part 2. **Bundle-only** sibling files to the unified
Responses CSV — one ``{code}_instrument_{n}.csv`` per instrument,
named positionally to match the ``instrument_{n}`` vocabulary
used in §2.4's preamble and ``InstrumentName`` column. No
individual download tile; no importer.

Same 21-column long-format header as §2.4, so an analyst can
concatenate the per-instrument files and reconstruct the unified
file. Each file carries a single-instrument preamble (its field
dictionary), a blank-row gap, the header, then data rows scoped
to that instrument. **Sort order:** ``(RevieweeName → ReviewerEmail
→ field.order)`` — the reviewee-centric reading order. Group-scoped
instruments collapse the fan-out (one row per (reviewer, group,
field)) and post-sort by the composed group identity so a group's
rows cluster together.

### 2.8 Reviewer session summary — `extracts/responses_extract.py` (`serialize_reviewer_session_summary`)

Shipped 17B Phase 2 PR B. The **per-reviewer** participation
record downloaded from
`GET /me/sessions/{id}/summary.csv` as
``{code}_my_responses.csv``. Gated on whole-session submission
— a partial reviewer redirects to the dashboard. Reviewers
get this download from the surface (and the dashboard's
Session column once Reviewer Status is `submitted`).

Same 21-column long-format header as §2.4. The file leads with
a per-instrument preamble + field dictionary for every
instrument the reviewer responded on — instruments they
weren't assigned to (or that they have no `Response` rows on)
are omitted, so the file is narrower than the unified
Responses CSV. Group-scoped instruments collapse the same way
(one row per (this reviewer, instrument, group, field)).
Builds on the same `_response_row_tuple` factored out in §2.7
so a per-cell rename flows through to every file in this
family.

### 2.9 Participant tokens — `extracts/participant_tokens_extract.py`

Shipped 2026-06-03 as the operator-side deanonymization key.
Downloaded from the Extract data tab's `Token keys` card
(`GET /sessions/{id}/export/participant_tokens.csv`) and
included in the responses-bundle Zip-all archive when
`session.observers_enabled` is on (driven by the intro
card's `Token keys` chip — `?tokens=0` excludes).

**No importer**: this CSV is a one-way reference, not a
round-trippable shape. Sibling `reviewers.csv` /
`reviewees.csv` keep their importer-compatible columns.

**Columns**: `Role`, `Name`, `Email`, `Token`. One row per
Reviewer + Reviewee on the session; reviewers block first
(active rows first, then by name + email), then reviewees
(same order rule). The token is computed by
`app/services/participant_tokens.py::ParticipantTokenizer`
— same chain the observer-side Anonymized
`by_instrument` CSV uses, so a token here is byte-identical
to its counterpart in any Anonymized download for the same
session. Audit event:
`session.participant_tokens_extracted` (`counts.rows` =
reviewer + reviewee row count, header excluded). Closes
`guide/archive/observers_clean_up.md` item 15.

---

## 3. Five importers (input contracts)

### 3.1 Reviewers + Reviewees — `csv_imports.py`

Two functions: `parse_reviewer_csv(content: bytes) -> ParseResult`
and `parse_reviewee_csv(content: bytes) -> ParseResult`.

**Required columns:**

- Reviewers: `ReviewerName`, `ReviewerEmail`.
- Reviewees: `RevieweeName`, `RevieweeEmail`.

Missing-required → `ParseResult` carrying one `ValidationIssue`
per missing column, no rows. The route 303s back with a
banner-error.

**Per-row validation** (every importer):

| Rule | Detection |
|---|---|
| Required cell present | Empty `ReviewerName` / `ReviewerEmail` / `RevieweeName` / `RevieweeEmail` → per-row error. |
| Email format | `_parse_email` rejects malformed strings on the email columns. Reviewees skip this check when the cell isn't an email (non-email identifier). |
| Within-file duplicates | Same `ReviewerEmail` / `RevieweeEmail` twice → per-row error on the second occurrence. |
| Cross-table identity | `check_cross_table_identity` rejects a Reviewer + Reviewee with the same email (would break the self-review predicate). |

**Optional columns:** any of `ReviewerTag1..3`, `RevieweeTag1..3`,
`PhotoLink` may be absent. An absent column is `None` for every
row; an empty cell is `None` for that row. `Status` (18P PR C) is
also optional — blank/absent ⇒ `active`; `active` / `inactive` only,
else a per-row error. The `*Tag1..3` columns may also carry a
`.<label>` friendly-label suffix (§1a).

**Save:** `save_reviewers(db, session, rows)` /
`save_reviewees(...)` wipe-and-replace within the session's
roster, then call `seed_display_fields_from_reviewees` for the
Reviewees side (idempotent display-field seeding off populated
`profile_link` / `tag_*` columns). The `field_labels_captured`
argument reconciles the tag friendly labels from the header (§1a):
upsert present, clear absent.

### 3.2 Relationships — `relationships.py`

`parse_relationship_csv(content, *, reviewer_emails,
reviewee_identifiers)` resolves the two FK columns against the
already-loaded session rosters. Required: `ReviewerEmail`,
`RevieweeEmail`. Optional: `PairContextTag1..3`, `Status`. The
`PairContextTag1..3` columns may carry a `.<label>` friendly-label
suffix (§1a); `save_relationships(..., field_labels_captured=…)`
reconciles them.

**Per-row validation:**

| Rule | Detection |
|---|---|
| Required cell present | Empty `ReviewerEmail` / `RevieweeEmail` → per-row error. |
| FK resolution | `ReviewerEmail` not in session's reviewers → per-row error. Same for `RevieweeEmail`. |
| Within-file duplicates | Same `(ReviewerEmail, RevieweeEmail)` pair twice → second occurrence rejected. |
| Status value | `Status` must be `active` / `inactive` (lowercase) or empty (defaults to `active`). |

**Save:** `save_relationships(db, session, rows)` wipe-and-replace,
then call `seed_display_fields_from_assignments` (legacy-named
helper that reads from `relationships.tag_N` post-15D PR 6b).

### 3.2b Observers — `csv_imports.py`

Shipped PR #1706. `parse_observer_csv(content: bytes) -> ParseResult`
and `save_observers(db, session, rows, *, user, correlation_id)`.

**Required columns:** `ObserverEmail`.
**Optional columns:** `ObserverName`, `ObserverTag1`, `Status`,
`CohortRule` (Segment 18P PR B — a compact-JSON `cohort_rule` payload;
PR C — the `Status` the extract already emitted is now read back).

**Per-row validation:**

| Rule | Detection |
|---|---|
| Required cell present | Empty `ObserverEmail` → per-row error. |
| Email format | `_parse_email` rejects malformed strings. |
| Within-file duplicates | Same `ObserverEmail` twice → second occurrence rejected. |
| `Status` value | Blank/absent → `active`; `active` / `inactive` only, else per-row error (18P PR C). |
| `CohortRule` shape | Non-blank cell must be valid JSON **and** pass `CohortRuleSet.model_validate` → per-row error otherwise. Blank cell → `cohort_rule = NULL`. |

**Save:** `save_observers(...)` wipe-and-replace within the session's
observer roster. Emits `observers.imported` audit event on success.
Bulk delete: `delete_all_observers(db, session, *, user,
correlation_id)` — emits `observers.deleted_all`.

**Extract counterpart:** `app/services/extracts/observers_extract.py` (W13, PR #1755). The extract uses the same column shape as the importer. The `GET /operator/sessions/{id}/export/observers.csv` route emits a `session.observers_extracted` audit event. The Extract Setup card renders the Observers tile conditionally when `observers_enabled=True`; the Zip-all bundle includes `{code}_observers.csv` on the same gate.

### 3.3 Settings — `session_config_io/` (two-phase apply)

The Settings CSV is **different in shape from the roster CSVs**:
instead of a flat record-per-row table, it's a `(field, value,
data_type)` triple per row covering every per-session setting in
one file.

**Header:** `field,value,data_type` (lowercase, always three cols).

**Row shape:**

```
session.name,Spring Review,String
session.deadline,2026-06-01T08:00:00+08:00,DateTime
email_overrides.invitation.subject,Please review your assigned reviewees,String
rtd.Long_text.data_type,Long_text,String
instruments[1].name,Default,String
instruments[1].display_fields[1].source_type,reviewee,String
session_rule_sets[Personal: Custom rule].description,…,String
data_shapes[1].name,By reviewer,String
```

The dotted / bracketed `field` paths route each row to a parser
that knows its target. See `serialize_session_config` for the
sections (session-level → email templates → RTDs → instruments
→ session RuleSets → data shapes → session tags) and their
canonical ordering. **Friendly labels are no longer a Settings
section** — see the round-trip notes below.

**Two-phase apply contract:**

1. **Phase 1 — Parse + validate every row.** Collect every error
   into `ApplyResult.errors`. One bad row doesn't mask the next.
   No DB writes.
2. **Phase 2 — Apply the typed plan.** Wipe-and-replace within
   the affected section (e.g. all RTDs for a session, all
   instruments, all `session_rule_sets` rows minus seeded copies).
   Atomic transaction. On any apply error, raise; the caller's
   transaction handler rolls back.

If phase 1 finds errors, phase 2 is **not attempted** — the
`ApplyResult` carries `errors` and the route surfaces them.

`apply_session_config` is the inverse of `serialize_session_config`.

**Round-trip notes:**

- **`field_labels.*` retired from the Settings CSV (Segment 19C
  Item 1).** Friendly labels now round-trip through the roster CSV
  headers (§1a) as the sole carrier. Settings no longer serializes
  them; a legacy `field_labels.*` row in an old bundle falls through
  to the unknown-key **silent-ignore** on apply (like the retired
  `rtds[` keys) — no error, label dropped, re-export to recover it in
  the roster header.
- **`instruments[n].order` is informational.** Apply ignores the `order`
  cell — **1-based CSV row position is authoritative**. To reorder
  instruments, reorder their row blocks in the file.
- **`instruments[n].display_fields[m].label` is a dead column.** It is no
  longer serialized (retired 15A); a legacy `label` row is tolerated and
  silently dropped on import, and the model column is always restored
  empty.

### 3.4 What's not an importer

- **Assignments.** Materialised derivative post-15D — no operator-
  facing CSV importer. The `manual` CSV path in `assignments.py`
  survives as a dev-diagnostic helper for test fixtures only.
- **Responses.** Reviewer-generated; no operator-facing importer.
- **Audit events.** System-emitted; no importer.

---

## 4. Round-trip stability contract

The four roster-shaped pairs (Reviewers, Reviewees,
Relationships, Settings) are **byte-stable** on round-trip:
`serialize(session) → write to file → read file → apply to
session → serialize` yields a byte-identical CSV.

Concrete guarantees the importers + serialisers maintain:

1. **Deterministic row order.** Active rows first, then by the
   first sort key documented per extract. Seeded RTDs and seeded
   RuleSets always emit in install order.
2. **Deterministic field order.** Section ordering pinned in
   `serialize_session_config`'s docstring + a golden-fixture
   unit test.
3. **Encoding parity.** UTF-8 in, UTF-8 out. BOM stripped on
   read, never emitted on write.
4. **Datetime normalisation.** Naive readbacks (SQLite without
   tzinfo) are normalised to UTC, then converted to the session's
   resolved display zone, and serialised as ISO 8601 carrying that
   zone's offset (`date_formatting.iso_in_zone`) — precise,
   dialect-stable, and round-trip-safe (any ISO 8601 offset parses
   back). The audit-events extract is the exception: it stays in
   UTC (`spec/timezone_display.md`).
5. **Vocabulary normalisation.** RTD `data_type` accepts both
   lowercase tokens (`long_text`) and capitalised model values
   (`Long_text`) on import; serialise emits the capitalised
   form. (12A-3 PR 3 fix.)
6. **Empty-string handling.** A `null` cell in storage is an
   empty CSV cell on serialise; an empty CSV cell on parse is
   `None`. No `"None"` strings, no `"null"` strings.
7. **Seeded entries are not re-emitted.** Seeded RTDs and seeded
   RuleSets auto-materialise on session create, so the export
   filters them out (re-emitting would either no-op or trip
   `uq_session_rule_set_session_name`).

The round-trip is asserted by
`tests/integration/test_apply_session_config.py::test_round_trip_byte_stable`
and per-entity round-trip tests in
`tests/integration/test_extracts_*.py`.

---

## 5. Shared parsing primitives

`app/services/csv_imports.py` exposes the helpers every importer
shares. Public surface:

| Helper | Role |
|---|---|
| `decode_csv(content: bytes) -> str` | UTF-8 decode + BOM strip. Single function so every importer gets identical encoding behaviour. |
| `_read_dict_rows(text: str)` | `csv.DictReader` wrapper with empty-line tolerance. |
| `_missing_columns_issues(fieldnames, required, source)` | Returns one `ValidationIssue` per missing required column. Called at parse time, before per-row iteration. |
| `_cell(row, key)` | Stripped string read; returns `""` when key absent. |
| `_none_if_blank(row, key)` | `None` when cell is empty / whitespace-only, else the stripped string. The canonical "optional cell" reader. |
| `_parse_email(value, *, field, row_number)` | Email validation with row-context error message. Used on `ReviewerEmail`, `RevieweeEmail` (when the cell is an email), and `ReviewerEmail` / `RevieweeEmail` in the Relationships importer. |
| `check_cross_table_identity(db, session_id, rows, *, side)` | Cross-table guard — rejects a Reviewer with the same email as a Reviewee in the same session. |

---

## 5a. Setup templates (starter + demo sets)

Two generic template sets an operator downloads **before any
session exists**. Both carry the same four roster files and differ
only in their rows.

> Status: shipped (Segment 19E rungs 4–5). Routes:
> `GET /templates/starter.zip`, `GET /templates/demo.zip` →
> `app/web/routes_templates.py`. Generator:
> `app/services/setup_templates.py`. Filenames:
> `review-robin-setup-templates.zip`,
> `review-robin-demo-session.zip`.

| Set | Rows | Job | Offered from |
|---|---|---|---|
| **starter** | one per file | *Edit this* — the format, with one example row to replace | Guide "Create and set up a session" card; lobby first-run card |
| **demo** | six students, twelve pairs, two observers | *Watch this work* — a populated session to walk through | Guide "Sample session" card |

**Members.** `reviewers.csv`, `reviewees.csv`,
`relationships.csv`, `observers.csv`.

**Neither set carries a `settings.csv`, and none is needed.** A new
session is seeded with a default instrument
(`ensure_default_instrument`) whose new-model rule defaults to Full
Matrix, so the roster files alone carry a session to `validated` —
asserted end-to-end by the round-trip test below. A settings file
would also be the one artefact here that could not be derived: it
is a `field,value,data_type` dump of a whole live session rather
than a row-shaped roster, so there is no `HEADER` to take and its
content would have to be authored.

**The demo set's round trip is the acceptance test.** Download →
Quick Setup submit-all → Prepare → `validated`, through the real
import path rather than a fixture
(`tests/integration/test_setup_template_download.py`). The test
asserts the submit redirect carries no `quick_setup_error` flag,
because a silently-skipped slot would still let the session
validate on the remaining rosters. A second test asserts the roster
counts and that assignments outnumber the reviewers — `validated`
alone would be satisfied by a one-pair session, and the demo set
exists so the Assignments page, the Responses grid and observer
collation have something in them.

**Derived, not authored.** Each member's header *is* the extract's
own `HEADER` tuple, held by reference — `reviewers_extract.HEADER`
and its three siblings. A column added to an extract reaches both
sets with no edit to the generator, and
`tests/unit/test_setup_templates.py` asserts the identity (not
equality) of each tuple. Rows are the authored part, and each is a
column-name → cell mapping checked against its header in both
directions: a missing column raises rather than emitting a short
row, and a cell for a column the header lacks fails the test. The
two sets are the same generator with different inputs — every
structural test runs against both, parameterised.

**One scenario, scaled.** Symmetrical peer review — students
reviewing each other inside a tutorial group. The starter set is
one pair in group `TW01` with their tutor observing; the demo set
is two groups of three (`TW01`, `TW02`) with both tutors observing,
and **every student appears as both reviewer and reviewee**, since
a demo whose rosters were disjoint would teach the wrong shape and
make self-review exclusion invisible. `relationships.csv` names
only addresses the rosters define, and carries pair context on the
group that has one and not the other, so the column does not read
as required. No pair is a self-pair: self-review is a session
toggle, not something a roster encodes. Every address is
`example.edu`, so nothing could reach a real person once sending is
switched on. Addresses are derived from names
(`"Alex Student"` → `alex.student@example.edu`) rather than written
per row, so a name and its address cannot drift apart across files.

**Worked friendly labels in the headers.** The templates carry
`<Column>.<label>` suffixes (§1a) as examples:
`ReviewerTag1.Tutor`, `ReviewerTag2.Group`,
`PairContextTag1.Interest Group`, and the reviewee equivalents. Tag
3 is left bare on both rosters, so the set shows labelling as per
column and optional. The suffix grammar is the one thing about
roster CSVs an operator cannot guess, and a template that
demonstrates it teaches more than one that avoids it.

The consequence is live: on import a labelled header **sets** that
slot's override (`field_labels.apply_captured_labels`), so
uploading a template unedited renames the session's tag columns to
*Tutor* / *Group* / *Interest Group*. That is the intended lesson —
the operator edits labels alongside rows. The same mechanism in
reverse means a **bare** tag header *clears* an override, mirroring
how an absent tag value re-imports as NULL; so an operator whose
session already has the names they want should export that
session's own roster rather than start from a template. The Guide's
card states both directions.

**Observer tags carry no suffix**, because they are outside the
nine-column labelable set by design (§1a). The tutor's role travels
as the cell *value* instead. A suffix there would not split on
import and the whole cell would read as an unknown column name,
losing the tag silently — so a test round-trips every generated
header cell through `field_label_csv.split_header` and asserts it
comes back as its column plus its expected label.

**No audit event.** The extract routes write one because they export
a session's real roster; this exports nobody's data, and
`audit_events` rows are session-scoped. Authentication is required
all the same — every surface in the app is behind sign-in.

**Surfaces.** Offered from the two places that render before a
session exists: the Guide's "Create and set up a session" card
(`spec/operator_ui_concept.md`) and the lobby first-run card
(`spec/sessions_overview.md`). Not offered from the Workflow card or
Extract Data — both were considered and rejected, since neither can
reach an operator who wants the templates while creating the session
(`guide/archive/segment_19E_operator_onboarding.md` → Judgment calls).

---

## 6. Surface mapping

| Surface | Direction | Service | Spec |
|---|---|---|---|
| Extract Data card — Reviewers tile | Out | `serialize_reviewers` | `spec/session_home.md` §2 |
| Extract Data — Reviewees tile | Out | `serialize_reviewees` | same |
| Extract Data — Relationships tile | Out | `serialize_relationships` | same |
| Extract Data — Responses tile | Out | `serialize_responses` | same |
| Extract Data — Settings tile | Out | `serialize_session_config` (via `_session_config_csv`) | same |
| Extract Setup — Zip all tile | Out | `build_setup_bundle` — a zip of the four setup CSVs above (`GET /export/bundle.zip`, filename `{code}_setup.zip`; renamed 2026-05-29 from the original "session bundle" per `guide/archive/extract_data.md`) | same |
| Extract data tab — Zip all button | Out | `build_responses_bundle` — a zip of the unified Responses CSV plus the two bundle-only entity-stats CSVs and one `instrument_{n}.csv` per instrument (`GET /export/responses_bundle.zip`, filename `{code}_responses.zip`; split out from the original session bundle 2026-05-29) | `guide/archive/extract_data.md` |
| Extract data tab — By-instrument Zip all button | Out | `build_by_instrument_bundle` — a zip of one wide-format CSV per instrument (`GET /export/by_instrument_bundle.zip`, filename `{code}_by_instrument.zip`; members named `{code}_by_instrument_{slug}.csv` where `{slug}` comes from the instrument's short label or the `Instrument_{N}` fallback). Each member starts with a key/value meta block (instrument identity + per-response-field type/constraint rows + assignment count + pool / unit-of-review / self-review configuration) + blank row + wide data table (one row per assignment, columns = identity + tags + one per response field + SelfReview/SavedAt/SubmittedAt). | `guide/archive/extract_data.md` |
| `GET /export/audit_log.csv` | Out | `serialize_audit_events` | Sys Admin → Sessions Diagnostics per-row "Audit log" link (`guide/archive/segment_16A_sys_admin_page.md` PR 4 — shipped) |
| Reviewer summary — "Download my responses (CSV)" | Out | `serialize_reviewer_session_summary` (`GET /me/sessions/{id}/summary.csv`, Segment 17B Phase 2 PR B) | `spec/reviewer-surface.md` "Per-session summary" |
| Reviewers Setup page — Upload CSV | In | `parse_reviewer_csv` + `save_reviewers` | `spec/setup_pages.md` |
| Reviewees Setup page — Upload CSV | In | `parse_reviewee_csv` + `save_reviewees` | same |
| Relationships Setup page — Upload CSV | In | `parse_relationship_csv` + `save_relationships` | same |
| Quick Setup Slot 1–3 (Reviewers / Reviewees / Relationships) | In | same as per-page Upload — Quick Setup is a thin shell over the per-entity primitives | `spec/quick_setup_card_spec.md` |
| Quick Setup Slot 4 (Settings) | In | `apply_session_config` | same |
| Guide + lobby first-run card — Download setup templates | Out | `build_zip(starter)` — a zip of four generic roster templates, headers derived from the extracts' `HEADER` tuples, one row each (`GET /templates/starter.zip`). Session-independent; see §5a. | §5a |
| Guide "Sample session" card — Download sample session data | Out | `build_zip(demo)` — the same four files populated with a two-group cohort (`GET /templates/demo.zip`). Reaches `validated` through Quick Setup with no configuration; see §5a. | §5a |

---

## 7. Implementation principles

1. **`HEADER` is the contract.** Each extract module pins a
   `HEADER: tuple[str, ...]` and the importer matches by header
   name. A column rename is a deliberate spec edit, not an
   accident. The starter templates (§5a) consume the same tuples,
   so they are a third reader of that one contract rather than a
   second source of truth.

2. **Wipe-and-replace, never merge.** Every importer replaces
   the section it owns within one transaction. Merge semantics
   would require per-row diffing the operator has no way to
   audit; replace is cleaner and matches the operator's mental
   model ("re-upload the file = re-set the state").

3. **Two-phase parse + apply (Settings).** Parse everything,
   collect every error, then apply or rollback. The operator
   sees the full validation report on a single submit rather
   than playing whack-a-mole.

4. **Streaming where it matters.** Responses + audit-events
   extracts use `yield_per(1000)` cursor streaming. Other
   extracts read into memory — roster sizes are bounded.

5. **Deterministic row order.** Every extract's row order is
   pinned in the module docstring and exercised by a unit test.
   Operators bisecting "what changed" across two snapshots
   benefit from the diff being clean.

6. **No header-position matching.** Operators add columns in
   Excel without thinking; the importer ignores extras. The
   importer matches required columns by name; missing-required
   surfaces as a parse-time error.
