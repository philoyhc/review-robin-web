# CSV contracts — spec

**The column shapes and parsing rules that govern every CSV the
operator extracts or uploads.** The extracts and importers share a
small library of primitives and a strict round-trip guarantee.
Reviewers, Reviewees, Relationships, Observers and Settings each have an
extract and an importer; the byte-stability contract in §4 covers every
pair but Observers (see there for why).

When the code drifts from this spec, fix the code. Each extract
file pins its `HEADER` tuple as a module constant; each importer
calls `_missing_columns_issues` against the same names. Renaming
a column on either side is a deliberate spec edit.

Cross-references:

- **`app/services/extracts/`** — the extract modules (a module may
  hold a family of related extracts), plus `zip_bundle.py` and
  `responses_import.py`, and the shared
  `__init__.py` (`stream_csv`, `filename`).
- **`app/services/csv_imports.py`** — three roster importers
  (Reviewers, Reviewees, Observers) + the shared parsing primitives.
- **`app/services/relationships.py`** — the Relationships
  importer.
- **`app/services/session_config_io/`** —
  `serialize_session_config` ↔ `apply_session_config` (Settings
  round-trip). Split into `_serialize.py` (export) + `_apply.py`
  (import) + `_rows.py`, with `__init__.py` re-exporting the
  public surface.
- **`spec/settings_inventory.md`** §10 — which CSV carries each
  inventoried setting.

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
| Header row | Always present. First in every file except three that lead with a block above it: the Responses extract and the reviewer's own summary (a preamble, §2.4, §2.8) and each By-instrument file (a meta block, unless the operator turns it off; §6). |
| Empty trailing newline | Tolerated on read; emitted on write per Python defaults. |
| Filename convention | `{session_code}_{kind}.csv` via `extracts.filename(session, kind)`. E.g. `CS101_reviewers.csv`. |
| Size caps (import) | The four roster importers — Reviewers, Reviewees, Relationships, Observers — refuse a file over **1 MiB** (`MAX_BYTES`, "File too large (max 1024 KiB)") over **5,000 data rows** (`MAX_ROWS`, "Too many rows (max 5000)"), or with any cell — header or data — past the `csv` module's **131,072-character** field limit ("A cell is longer than 131,072 characters", which a file under `MAX_BYTES` can carry), each as a single blocking issue with no rows parsed. The Settings import is not capped. |
| Cell lengths (import) | Every string a roster importer writes is checked against its model column's declared `String(n)` — names, tags and friendly labels 255, emails 320, `ProfileLink` 2000 — and an over-long cell is a blocking issue on its row naming the column and both lengths (`cell_length_issues`); a cell past the parser's own field limit refuses the whole file instead (*Size caps*). A friendly label on a tag header (§1a) is checked against `session_field_labels.label` and refuses the file. The limits are read from the models, so they cannot drift from the schema; without the check SQLite stored the value and Postgres refused it at flush, a 500. The Settings import checks its own strings the same way (§3.3), a Data shaper shape name is held to its 255 in the service, and the single-row Add / Edit forms and the label editor hold the same limits (`spec/setup_pages.md`). |

The header row is the **contract** — every importer matches by
header name (case-sensitive), not by position. An extra column
the operator added in Excel is ignored; a missing required
column is a parse error.

### 1a. Friendly-label header suffix

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
  back to the built-in default — `Tag N`, or `Pair context N` for a
  pair-context slot). Clearing an already-unset
  slot is a no-op.
- **Export emits the suffix** when an override exists, bare
  otherwise (a slot on its default is never given a fabricated
  default-label suffix) — so download → edit → re-import is symmetric.
- **Observer tags are out of scope** (single `tag_1`, no
  friendly-label affordance).
- Handled by `app.services.field_label_csv` (`split_header` /
  `normalize_headers` on import, `labeled_header` on export).

---

## 2. Extracts (export contracts)

Each extract module declares a `HEADER: tuple[str, ...]` module
constant. The serialiser yields the header first, then one tuple
per row in a deterministic order so re-export of the same session
is byte-stable.

**No extract neutralises spreadsheet formulas.** Every cell, the
participant-typed response values included, is written verbatim
through `csv.writer`, so an operator opening an extract in a
spreadsheet sees a cell that starts with `=`, `+`, `-` or `@`
evaluated as a formula. The general fix, a guard on write that the
importer strips, would change this contract for every cell, so it is
deferred with the settings CSV's own guard
(`guide/deferred_consolidated.md`).

The Observers and Settings extracts are specified beside their
importers (§3.2b, §3.3).

### 2.1 Reviewers — `extracts/reviewers_extract.py`

| # | Column | Source | Notes |
|---|---|---|---|
| 1 | `ReviewerName` | `reviewer.name` | Required on import. |
| 2 | `ReviewerEmail` | `reviewer.email` | Required on import. Used by the cross-table identity check and by `relationships.csv`'s FK. |
| 3 | `ReviewerTag1` | `reviewer.tag_1` | Optional on import. Empty cell ⇒ NULL. |
| 4 | `ReviewerTag2` | `reviewer.tag_2` | Same. |
| 5 | `ReviewerTag3` | `reviewer.tag_3` | Same. |
| 6 | `ProfileLink` | `reviewer.profile_link` | Optional. Rendered as a clickable link on the reviewer surface when populated. Mirrors the Reviewees `ProfileLink` column. |
| 7 | `Status` | `reviewer.status` | `active` / `inactive`. Optional on import: blank/absent ⇒ `active`; any other value is a per-row error. |

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
| 6 | `ProfileLink` | `reviewee.profile_link` | Optional. Rendered as a clickable link on the reviewer surface when populated. |
| 7 | `Status` | `reviewee.status` | `active` / `inactive`. Optional on import: blank/absent ⇒ `active`; any other value is a per-row error. |

**Row order:** active rows first, then by `name`, then by
`email_or_identifier`.

### 2.3 Relationships — `extracts/relationships_extract.py`

The pair-context round-trip.

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

Analysis-facing per-session CSV — the consumer is an external
analyst. No operator-facing importer (responses are
reviewer-generated); the one reader is Rehydrate, through
`extracts/responses_import.py` (`spec/rehydrate.md`).

The file has two parts:

1. **Preamble** — one block per instrument: a row carrying the
   instrument's positional name (`instrument_1`, `instrument_2`,
   … by instrument order), then one `FieldKey, HelpText` row per
   response field (a field dictionary). A blank row separates the
   preamble from the table. A session with no instruments emits
   no preamble and no gap.
2. **Data table** — the 21-column long format below, one row per
   answer, inactive pairs' answers included (the analysis lenses read
   active pairs only; `spec/extract_data.md`).

| Block | Columns |
|---|---|
| Reviewer identity (5) | `ReviewerName`, `ReviewerEmail`, `ReviewerTag1`, `ReviewerTag2`, `ReviewerTag3` |
| Reviewee identity (5) | `RevieweeName`, `RevieweeEmail`, `RevieweeTag1`, `RevieweeTag2`, `RevieweeTag3` |
| Instrument (2) | `InstrumentName` (the positional id `instrument_{n}` — the operator's typed name is not exported), `InstrumentShortLabel` |
| Field context (3) | `FieldKey`, `FieldLabel`, `ResponseType` |
| Value (1) | `Value` (empty cell ⇒ reviewer cleared the field) |
| Self-review (1) | `SelfReview` — uppercase `TRUE` / `FALSE` per Excel idiom. Read from the assignment's stored `Assignment.is_self_review` column: on individual-scoped instruments a case-insensitive match of the reviewer's email against the reviewee's email-or-identifier (`FALSE` for a non-email identifier); on group-scoped instruments the whole-group rule (every member row of a group the reviewer belongs to on the session roster counts, even when a rule filtered out the reviewer's own row). |
| Lifecycle (3) | `SavedAt`, `SubmittedAt`, `Version` |
| Instrument flavour (1) | `InstrumentFlavour` — derived `per-reviewee` / `group-scoped`. **Appended last, not grouped with the other instrument columns**, so the preceding 20 column indices stay stable for analyst pipelines that read by position. |

An analyst joins a preamble help text to its data column via the
shared `FieldKey`.

`SavedAt` / `SubmittedAt` are ISO 8601 carrying the **session
zone's** UTC offset (e.g. `2026-06-02T08:00:00+08:00`), via
`date_formatting.iso_in_zone` — see `spec/timezone_display.md`.

**Streaming:** the data-table query uses `yield_per(1000)` cursor
streaming so large sessions don't materialise every Response
row in memory. Row order: `(reviewer.email,
reviewee.email_or_identifier, instrument.order, field.order)`, with
`id` breaking ties on the last two.

### 2.5 Audit events — `extracts/audit_events_extract.py`

No tile on the session pages. `GET /export/audit_log.csv` is
sys-admin only (`require_sys_admin`) and is reached from the
`Download CSV` button on the Sys Admin per-session audit-log page
(`/operator/sys-admin/sessions/{id}/audit-log`, linked from the
Sessions Diagnostics row). The button carries the page's filters —
`event_type` and `severity` (repeatable), `actor`, `from`, `to` — so
the file honors the page's active filter; with none the file holds
the whole log, and a filter that does not parse is a 422. The
`session.audit_log_extracted` event records the active filters in its
`context`.

| # | Column | Source | Notes |
|---|---|---|---|
| 1 | `EventType` | `event_type` | One of the registered types in `EVENT_SCHEMAS` (`app/services/audit.py`). |
| 2 | `Severity` | `severity` | `info` / `warning` / `error` (from the canonical envelope). |
| 3 | `Summary` | `summary` | Human-readable one-liner. |
| 4 | `ActorEmail` | LEFT JOIN through `actor_user_id` → `users.email`. Empty cell ⇒ system-emitted event with no actor. |
| 5 | `CorrelationId` | `correlation_id` | Request-scoped UUID. |
| 6 | `CreatedAt` | `created_at` | ISO 8601 in **UTC** (`...+00:00`); naive readbacks (SQLite) normalised to UTC for dialect-stable output. The audit log is the deliberate UTC exception (`spec/timezone_display.md`) — unlike the other per-session extracts, this column is *not* localised to the session zone. |
| 7 | `DetailJson` | `json.dumps(detail, separators=(",", ":"), sort_keys=True)` | Compact, key-sorted JSON. Empty cell when `detail is None`. |

**Row order:** `(created_at ASC, id ASC)`. **Streaming:**
`yield_per(1000)`.

### 2.8 Reviewer session summary — `extracts/responses_extract.py` (`serialize_reviewer_session_summary`)

The **per-reviewer** participation
record downloaded from
`GET /me/sessions/{id}/summary.csv` as
``{code}_my_responses.csv``. Gated on whole-session submission
— a partial reviewer redirects to the dashboard. Reviewers
get this download from the surface (and the dashboard's
Session column once Reviewer Status is `submitted`).

Same 21-column long-format header as §2.4. The file leads with
a per-instrument preamble + field dictionary for every
instrument the reviewer responded on and may read now (the visibility
rule in `spec/reviewer-surface.md` "Lifecycle gating"; rows of a
hidden instrument are left out too) — instruments they
weren't assigned to (or that they have no `Response` rows on)
are omitted, so the file is narrower than the unified
Responses CSV. A response field with `visible=False` is dropped from
both the preamble and the data rows, so the file matches the form the
reviewer saw. Group-scoped instruments collapse the same way
(one row per (this reviewer, instrument, group, field)).
Builds on the same `_response_row_tuple` as §2.4, so a
per-cell rename flows through to every file in this family.

### 2.9 Participant tokens — `extracts/participant_tokens_extract.py`

The operator-side deanonymization key. Downloaded from the Extract
data tab's `Token keys` card
(`GET /sessions/{id}/export/participant_tokens.csv`) and
included, under the same name, in the responses-bundle Zip-all
archive when `session.observers_enabled` is on (driven by the
intro card's `Token keys` chip — `?tokens=0` excludes).

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
reviewer + reviewee row count, header excluded).

---

## 3. Importers (input contracts)

### 3.1 Reviewers + Reviewees — `csv_imports.py`

Two functions: `parse_reviewer_csv(content: bytes) -> ParseResult`
and `parse_reviewee_csv(content: bytes) -> ParseResult`.

**Required columns:**

- Reviewers: `ReviewerName`, `ReviewerEmail`.
- Reviewees: `RevieweeName`, `RevieweeEmail`.

Missing-required → `ParseResult` carrying one `ValidationIssue`
per missing column, no rows. A blocked file saves nothing. The Setup
page's upload re-renders the page at **400** with the issue list in
the upload card; Quick Setup's slot 303s back to Session Home with
`?quick_setup_error=…`.

**Per-row validation** (every importer):

| Rule | Detection |
|---|---|
| Required cell present | Empty `ReviewerName` / `ReviewerEmail` / `RevieweeName` / `RevieweeEmail` → per-row error. |
| Email format | `_parse_email` rejects malformed strings on the email columns. Reviewees skip this check when the cell isn't an email (non-email identifier). |
| Within-file duplicates | Same `ReviewerEmail` / `RevieweeEmail` twice → per-row error on the second occurrence. |
| Cell length | A cell longer than its column (§1, *Cell lengths*) → per-row error naming the column, one per over-long cell. A row refused here, or by any check, does not reserve its email, so a later row with the same email is not reported as its duplicate. |
| Cross-roster identity | `check_cross_table_identity` rejects a row whose email is already held in **another roster under a different name**. Same email + same name is allowed and common — one person is often both reviewer and reviewee, which is the self-review case. Three-way: each roster is compared against the other two, observers included. |

**Optional columns:** any of `ReviewerTag1..3`, `RevieweeTag1..3`,
`ProfileLink` may be absent. An absent column is `None` for every
row; an empty cell is `None` for that row. The legacy `PhotoLink`
header is still accepted on import, indefinitely — `_profile_link`
in `app/services/csv_imports.py` reads `ProfileLink` first and falls
back to `PhotoLink`; a non-blank `ProfileLink` wins when a file
carries both. `Status` is
also optional — blank/absent ⇒ `active`; `active` / `inactive` only,
else a per-row error. The `*Tag1..3` columns may also carry a
`.<label>` friendly-label suffix (§1a).

**Save:** `save_reviewers(db, *, session, user, rows, filename,
correlation_id, field_labels_captured=None)` /
`save_reviewees(...)` (same keyword-only shape) wipe-and-replace within the session's
roster, then call `seed_display_fields_from_reviewees` for the
Reviewees side (idempotent display-field seeding off populated
`profile_link` / `tag_*` columns). The `field_labels_captured`
argument reconciles the tag friendly labels from the header (§1a):
upsert present, clear absent.

### 3.2 Relationships — `relationships.py`

`parse_relationship_csv(content, *, reviewers: list[Reviewer],
reviewees: list[Reviewee])` resolves the two FK columns against the
already-loaded session rosters — **the roster rows themselves, not
lists of strings**; the parser keys them by `normalize_email` and
returns the resolved FK ids so the save step need not look them up
again. `ReviewerEmail` matches `reviewers.email`; **`RevieweeEmail`
matches `reviewees.email_or_identifier`**, so a reviewee carrying a
non-email identifier (`spec/participant_model.md`'s *"confidential /
opaque identifiers"*) resolves here too — `normalize_email` lower-cases it like
any other key, so `ANON-007` and `anon-007` are one identity.

Required: `ReviewerEmail`, `RevieweeEmail`. Optional:
`PairContextTag1..3`, `Status`. The `PairContextTag1..3` columns may
carry a `.<label>` friendly-label suffix (§1a);
`save_relationships(..., field_labels_captured=…)` reconciles them.

**Per-row validation:**

| Rule | Detection |
|---|---|
| Required cell present | Empty `ReviewerEmail` / `RevieweeEmail` → per-row error. |
| FK resolution | `ReviewerEmail` not in session's reviewers → per-row error. Same for `RevieweeEmail`. |
| Within-file duplicates | Same `(ReviewerEmail, RevieweeEmail)` pair twice → the second occurrence is rejected **when the first one parsed**. Detection is on the *resolved* pair, so two spellings of one address collide, and the error names the row the survivor is on. A first occurrence that fails a later check reserves nothing, so a valid second occurrence is kept instead of being reported as a duplicate of a row that never parsed. |
| Status value | `Status` must be `active` or `inactive`, **case-insensitively and ignoring surrounding whitespace** (`  ACTIVE  ` is accepted); empty or absent defaults to `active`. |
| Cell length | A `PairContextTag1..3` cell longer than 255 → per-row error naming the column (§1, *Cell lengths*); checked before the pair is reserved. |

**A row yields at most one issue, except for length.** The checks run
in the order of the table above and each one `continue`s; the last,
cell length, reports every over-long tag cell on the row. So a row
with both cells blank reports `ReviewerEmail` only, and a row naming an unknown reviewer *and*
an unknown reviewee reports the reviewer only. Clearing a file with
several problems per row can therefore take more than one upload.

**Per-row detection, all-or-nothing save.** The table says where an
error is *attached*; it does not mean valid rows import while bad ones
are skipped. Every issue the parser raises is `Severity.error`, so
`ParseResult.is_blocked` is true if any row failed, and **all three
callers refuse the whole file** — the Relationships card
(`_setup_relationships.py`), Quick Setup's slot (`_quick_setup.py`) and
the rehydrate path (`session_rehydrate.py`, which raises rather than
redirecting). A file with one bad row saves nothing, so `ParseResult`
carrying both rows and issues is a report, not a partial import.

**Roster status is not checked.** A row naming an `inactive` reviewer or
reviewee resolves and imports exactly as an active one does: the parser
filters no status and all three callers pass the unfiltered rosters. The
saved relationship's own `Status` comes from the CSV cell, never from
the roster member's. Whether a pair naming a soft-deleted member *should*
import is an open product question, not a documented
intent.

**Save:** `save_relationships(db, *, session, user, rows, filename,
correlation_id, field_labels_captured=None)` wipe-and-replace,
then call `seed_display_fields_from_assignments` — **named for
assignments, but it reads `relationships.tag_N`**; the name is kept
because renaming it buys a reader nothing and costs every caller.

### 3.2b Observers — `csv_imports.py`

`parse_observer_csv(content: bytes) -> ParseResult`
and `save_observers(db, *, session, user, rows, filename,
correlation_id)`.

**Required columns:** `ObserverEmail`.
**Optional columns:** `ObserverName`, `ObserverTag1`, `Status`,
`CohortRule` (a compact-JSON `cohort_rule` payload). The importer reads
back both columns the extract emits, so observer status and cohort rule
both round-trip.

**Per-row validation:**

| Rule | Detection |
|---|---|
| Required cell present | Empty `ObserverEmail` → per-row error. |
| Email format | `_parse_email` rejects malformed strings. |
| Within-file duplicates | Same `ObserverEmail` twice → second occurrence rejected. |
| Cell length | `ObserverEmail`, `ObserverName` or `ObserverTag1` longer than its column → per-row error naming the column (§1, *Cell lengths*). |
| Cross-roster identity | As §3.1 — `check_cross_table_identity` with `kind="observers"`, against the reviewer and reviewee rosters. A row with no `ObserverName` is skipped: `Observer.display_name` is nullable and its column optional, and a missing name is not a different one. One person may be an observer and a reviewer; the check blocks only two names on one mailbox. |
| `Status` value | Blank/absent → `active`; `active` / `inactive` only, else per-row error. |
| `CohortRule` shape | Non-blank cell must be valid JSON **and** pass `CohortRuleSet.model_validate` → per-row error otherwise. Blank cell → `cohort_rule = NULL`. |

**Save:** `save_observers(...)` wipe-and-replace within the session's
observer roster. Emits `observers.imported` audit event on success.
Bulk delete: `delete_all_observers(db, *, review_session, user,
correlation_id)` — emits `observers.deleted_all`.

**Extract counterpart:** `app/services/extracts/observers_extract.py`. The extract uses the same column shape as the importer. The `GET /operator/sessions/{id}/export/observers.csv` route emits a `session.observers_extracted` audit event. The Extract Setup card renders the Observers tile conditionally when `observers_enabled=True`; the Zip-all bundle includes `{code}_observers.csv` on the same gate.

### 3.3 Settings — `session_config_io/` (two-phase apply)

The Settings CSV is **different in shape from the roster CSVs**:
instead of a flat record-per-row table, it's a `(field, value,
data_type)` triple per row covering every per-session setting in
one file.

**Header:** `field,value,data_type` (lowercase, always three cols).

**Row shape:**

```
session.name,Spring Review,string
session.deadline,2026-06-01T08:00:00+08:00,datetime
email_overrides.invitation.subject,Please review your assigned reviewees,string
instruments[1].name,Default,string
instruments[1].display_fields[1].source_type,reviewee,enum
session_rule_sets[1].description,…,string
data_shapes[0].name,By reviewer,string
```

The dotted / bracketed `field` paths route each row to a parser
that knows its target. Every list bracket is an **ordinal**, never
a name: `session_rule_sets[N]` counts the session's rule sets in `id`
order and carries the name in its own `.name` row. Ordinals are
1-based except `data_shapes[N]`, which counts from 0. The one keyed
bracket is `instruments[N].view_policies[<audience>]`. The export
writes the third column, `data_type`, in lowercase (`string`, `datetime`, `boolean`,
`integer`, `decimal`, `json`, `enum`). The import also accepts
`csv_list`, which the export never writes, matches the column
case-insensitively and allows it blank; any other value is an error on
its row. Beyond that check the column is not read — each `field` path
parses its value as its own type. See `serialize_session_config` for the
sections (session-level → email templates → instruments
→ session RuleSets → data shapes → session tags) and their
canonical ordering. **Friendly labels are not a Settings
section** — the roster CSV headers are their sole carrier (§1a); see
the round-trip notes below.

**Two-phase apply contract:**

1. **Phase 1 — Parse + validate every row.** Collect every error
   into `ApplyResult.errors`. One bad row doesn't mask the next.
   No DB writes. An error's row number counts the non-blank rows
   below the header. A row with fewer than three cells refuses the
   file, but as an error on its row like the others
   (`session_config_io.split_rows`): the rest of the file is still
   validated (`validate_session_config`), so the report names every
   short row beside every other error. Quick Setup reports it
   before the replacement gates, as it does any malformed file, and
   Rehydrate fails its settings step with it. A blank or absent
   required value is an error naming its path: a `session_rule_sets`
   `name`, an instrument's `name`, a display field's `source_type`,
   and a response field's `field_key`, `label` and `response_type`.
   Three keys phase 2 writes as unique are errors when repeated: a `session_rule_sets` name (§4 item 7), a
   `data_shapes` name among the shapes phase 2 writes (those with a
   name and a known axis), and a response field's `field_key` within
   its instrument. Each is an `ApplyError` naming the first
   occurrence, not a database error. A repeated session tag is
   deduplicated and a repeated `view_policies[<audience>]` block
   merges, so neither is an error. A fractional Min, Max or Step on an
   `Integer` response field is an error too, as on Band 2
   (`spec/instruments.md`, the Bounds rules). So is a value longer
   than the column it lands in (a data-shape name or `field_key` over
   255 characters, a `short_label` over 32), read from each column's
   declared length; a session tag over 64 is refused by the tag rules.
   Only values phase 2 writes are checked: a *fill-blanks* `session.*`
   key (below) only where the destination is blank, and a data shape
   only when it is written, as for the duplicate-name rule.
2. **Phase 2 — Apply the typed plan.** Wipe-and-replace within
   the affected section (e.g. all instruments for a session, which
   also deletes every assignment and response in it).
   `session_rule_sets` is the exception: an upsert by name that
   deletes the rows the CSV omits (§4 item 7).
   Atomic transaction. On any apply error, raise; the caller's
   transaction handler rolls back.

If phase 1 finds errors, phase 2 is **not attempted** — the
`ApplyResult` carries `errors` and the route surfaces them.

`apply_session_config` is the inverse of `serialize_session_config`.

**`apply_session_config` does not commit — every caller must.** It
flushes and returns. `get_db` then closes without committing, so an
uncommitted apply is *rolled back* while the route returns a success
redirect. Both in-tree callers commit for themselves:
`_run_quick_setup_settings`, the helper the three upload routes share,
after a successful apply; and `session_rehydrate`, all-or-nothing at
the end of its own run. **A third caller that does not commit
reproduces the defect silently**, which is why the requirement is
stated here rather than left to the two call sites.

The integration fixture shares a transaction with the app, so a
flushed row reads exactly like a committed one and a commit releasing
a savepoint fires no `after_commit`; the test that pins the commit
spies on `Session.commit` as a **class** attribute.

#### Settings CSV — apply precedence

Every non-tag field on the Create form also appears in this CSV
(tags follow below), and
`POST /operator/sessions` always applies the bundle *after* creating
the session, so the file runs last. `_apply_session_metadata` then
resolves each field by one of **two rules** — *fill-blanks* for
operator-typed identity (`name`, `code`, `description`, `deadline`,
`help_contact`), where the form wins **only where it was filled in**;
and *force-apply* for every other config key it writes
(timezone, the schedule anchors and offsets, the two UI toggles and
the keys the form does not carry), where the CSV wins. `assignment_mode`
and `status` are a third case, **defensively ignored on import** as
machine-derived. `spec/settings_inventory.md` §10 carries the field
lists.

Fill-blanks is therefore not "the form always wins" for all five:
`name` and `code` are `required` on the Create form, so the CSV can
never reach them, but `description`, `deadline` and `help_contact` are
optional — submit any of them blank and the bundle fills it. That is
the rule working as written (`if existing not in (None, ""): continue`),
not a precedence a caller can choose.

**Session tags are neither, and the Create page's box wins by
ordering.** A typed tag is operator-typed identity, so the form should
win — but `_apply_session_tags` is **wipe-and-replace with no
section-presence flag**, which has two consequences worth stating
plainly:

- a bundle carrying **no** `session_tags[]` rows is indistinguishable
  from one asking for none, so it **clears** the session's tags; and
- the applier is shared with `POST /sessions/{id}/import-config` on an
  *existing* session, where that wipe is the pinned round-trip
  behavior.

So the rule is delivered by **running the box's `set_tags` after the
settings block**, not by narrowing the applier for one caller. An
empty box writes nothing at all — calling `set_tags` with an empty set
would be a replace, and would drop what the CSV had just applied. **The
same empty `tags=` means the opposite on the lobby's row expander**,
where it clears the session's tags, so the emptiness rule belongs to
the create route and not to `set_tags`; a later refactor funnelling
both surfaces through one helper has to keep both meanings. The
write also runs on the **failed-upload redirect**, so a create that
bails out at an earlier Quick Setup slot still keeps the typed tag; a
slot that failed wrote no tags and a slot that never ran cannot have,
so that path is still "after the settings CSV" in the only sense that
matters.
Create is therefore immune to the wipe above; `import-config` on an
existing session is **not**, and that remains an open hazard rather
than a solved one.

**Imported tags are normalized exactly as typed ones are** — tags are
lower case everywhere. Each `session_tags[]`
value goes through `session_tags.normalize_tag`: lowercased, trimmed,
and two spellings of one tag collapse to one row. A blank or
whitespace-only value is skipped; one longer than the 64-character
column is a **parse error**, so the whole bundle is refused with a
message rather than reaching the insert raw. **Rows already stored
with capitals are not migrated**: they stay until something rewrites them, and saving Session
Home's details card is one such thing, since its Tags field writes
through `set_tags`.

**The import enforces the schedule ordering chain** (findings G22,
ruled 2026-10-06): Start ≤ End ≤ Release-from < Release-until, on the
values the session would hold after the apply, refused in the parse
phase with the details card's messages (`spec/lifecycle.md` §8.2.7).
A pair the file supplies neither side of is not checked. Every
consumer also guards itself, for a session saved before the check:
`is_response_release_window_open` returns `False` unless the session
`is_expired` **whatever the anchors say**, a `responses_release_until` before its anchor leaves the
window permanently shut rather than early-open, scheduled activation
fires only from `validated` and otherwise takes a one-shot audited
skip, and past-deadline reminders are skipped with an audit event. The
route's check is an interactive-path courtesy, not a correctness
boundary.

**Round-trip notes:**

- **`field_labels.*` is not a Settings key, and a bundle carrying
  one still imports.** Friendly labels round-trip through the roster
  CSV headers (§1a) as the sole carrier, so the export emits no
  `field_labels.*` row. One that arrives on input must fall through to
  the unknown-key **silent ignore** on apply — no error, the label
  dropped, and re-exporting the roster recovers it in the header.
  Dropping the tolerance would make every older bundle fail to import
  for a row that carries nothing.
- **A retired `rtds[…]` row is silently ignored on import, and that is
  unconditional.** The per-session response-type table is gone and the
  export emits no `rtds[` row, but an older bundle may carry them. They
  land on the same unknown-key ignore as any other unrecognized path,
  so such a bundle imports with the rows dropped rather than failing.
- **A default sort and column widths travel by field position.**
  `Instrument.sort_display_fields` and
  `column_widths` name fields by id, and an import creates new ones, so
  the export writes positions instead: a sort entry's
  `display_field_id` becomes `display_field`, the 1-based `m` of the
  field's `display_fields[m]` rows (`{"display_field": 2, "dir":
  "desc"}`), and a width key `df_<id>` / `rf_<id>` becomes `df@<m>` /
  `rf@<m>`, `m` counting that instrument's `display_fields[m]` or
  `response_fields[m]` rows respectively. The import maps each back to
  the field it creates. The Group sentinel (`"display_field_id": -1`)
  and width keys that are not `df_` / `rf_` keys (`identity`) ride as
  they are. On export, a `df_` / `rf_` key or sort entry whose id is not
  one of the instrument's fields is dropped. On import, an entry whose
  position names no created field (or is not an integer) is dropped, as
  are an older bundle's id-keyed entries, which name the source
  session's fields, and a second sort entry naming a field, or the Group
  sentinel, already named.
- **A retired `instruments[n].responses_visible_when_closed` row is
  accepted and dropped.** The column is
  gone and the export no longer writes the row; an older bundle that
  carries it imports without it.
- **A retired `instruments[n].view_policies[…].observer_tag` row is
  accepted and dropped.** The column is gone; an older bundle that
  carries the row imports without it, rather than failing on an
  unknown attribute.
- **A retired reviewer visibility mode imports as off.** The
  `peer_reviewer` audience's after-release cell no longer offers
  `Summarized` (`aggregated` + `deidentified`); an older bundle
  carrying exactly that pair has it cleared to off before the cell
  check runs, rather than refusing the whole apply. Any other illegal
  cell is still refused.
- **`instruments[n].order` is informational.** Apply ignores the `order`
  cell — **the `[n]` number is authoritative**, not the rows' place in
  the file. Each instrument is stored at its 0-based rank among the
  file's numbers (`[1]`, `[2]` → 0, 1; `[0]`, `[3]` → 0, 1), as the app
  numbers its own. The export writes the block's 0-based position
  rather than the stored value, which a session imported before
  2026-10-05 holds 1-based, so the cell always round-trips. To reorder
  instruments, renumber their blocks.
- **`instruments[n].display_fields[m].label` is a dead column.** The
  export does not emit it, a `label` row from an older bundle is
  tolerated and silently dropped on import, and the model column is
  always restored empty. The column stays in the schema as dead data;
  the import tolerance is what keeps an older bundle importable.

**Response-field branching** adds four
`instruments[n].response_fields[m]` attributes:

| Attribute | Carries | On |
|---|---|---|
| `branch_parent` | the parent field's `field_key` within the same instrument — ids don't survive an export | a governed field |
| `branch_op` | the condition operator token: `eq` / `ne` / `gt` / `ge` / `lt` / `le` (Integer / Decimal, one box) or `is` / `is_not` (List); or, for a range, one of the four tokens `in_inc` / `in_exc` / `out_inc` / `out_exc` | the parent |
| `branch_value` | the condition's number, List options comma-separated, or — for a range token — `low to high` | the parent |
| `branch_mode` | what the condition does: `require` (the governed fields are required while it holds, else optional), or blank or `show` (the governed fields show only while it holds; exported blank). `show` reads exactly as blank, anywhere. Any other value is refused by name; `require` on a field with no branch is an orphan, refused as a lone `branch_value` is | the parent |

**A range's `branch_value`** is exactly two plain numbers joined by
`" to "`, low strictly below high (`parse_range`,
`app/services/responses/_branching.py`); each end is a plain decimal
(`DECIMAL_PATTERN`, an exponent allowed), neither blank nor non-finite.
A cell that doesn't parse is refused
by name — `range_error`'s messages name the end at fault ("The range's
low end needs a number.", "…high end needs a number.", "The range's low
end must be below its high end.") rather than a generic shape complaint.
**Import stores the canonical form**: each end stripped of surrounding
whitespace around the one separator (`canonical_condition_value`), so a
hand-spaced `2 to  4` round-trips as `2 to 4` and doesn't later read as a
changed condition to the lock on an answered branch. **A negative low
end starts the cell with `-`** (`-5 to -1`); the settings CSV has no
formula guard for any cell (`guide/deferred_consolidated.md`). Unlike a
lone `-5`, which a spreadsheet reads as a number, such a cell can come
back from a spreadsheet round trip as an error value; the import then
refuses it by name.

**Checked at parse time, before anything is applied**
(`session_config_io/_apply_parse.py`'s `_branch_errors`, run against the
same rules the builder enforces — `spec/instruments.md` § "Branching
between response fields"): an unknown `branch_parent`, a String parent,
a branch that isn't one ruled group, or a condition that doesn't fit its
parent's type is refused with a named error, and the whole apply fails —
never applied with the branch silently dropped. A `branch_parent` may
name a governed field, two levels deep at most; a third level is
refused by name. **A required governed
field needs an active required field outside any branch elsewhere in
the instrument** (a visible field under a `require`
parent counts as required governed) — refused by name otherwise, the
same rule `branch_structure_errors` applies to Save. A lone `branch_value`
with no operator and no governed field is refused the same way, rather
than stored as an orphaned condition. `branch_op` is also checked against the known tokens as it's
read, before any row is created. **A hidden parent hides its whole
branch on import too**, a branch inside it included — a governed field
imported visible under a hidden parent
could never be answered, so import applies the same Active cascade the
builder's Save does.

### 3.4 What's not an importer

- **Assignments.** A materialized derivative of the rule engine,
  the roster and the relationships — no operator-facing CSV
  importer.
- **Responses.** Reviewer-generated; no operator-facing importer.
  Rehydrate reads a responses extract back (§2.4).
- **Audit events.** System-emitted; no importer.

---

## 4. Round-trip stability contract

The Reviewers, Reviewees, Relationships and Settings pairs are
**byte-stable** on round-trip:
`serialize(session) → write to file → read file → apply to
session → serialize` yields a byte-identical CSV.

**Observers is not claimed here.** It has a wired
importer and an extract, and `Status` and `CohortRule` both read back — but
whether the pair is *byte*-stable has not been established, so it is
outside this contract rather than inside it by assumption. Stating the gap
is the point: a guarantee that quietly omits one pair is how a round-trip
regression goes unnoticed.

Concrete guarantees the importers + serialisers maintain:

1. **Deterministic row order.** Active rows first, then by the
   first sort key documented per extract. Every `session_rule_sets`
   row emits, in `id` order.
2. **Deterministic field order.** Section ordering is pinned in
   `serialize_session_config`'s docstring.
   `test_section_ordering_is_deterministic` asserts a byte-identical
   re-export and the order of the first three sections; the later
   sections are pinned by the docstring alone.
3. **Encoding parity.** UTF-8 in, UTF-8 out. BOM stripped on
   read, never emitted on write.
4. **Datetime normalisation.** Naive readbacks (SQLite without
   tzinfo) are normalised to UTC, then converted to the session's
   resolved display zone, and serialised as ISO 8601 carrying that
   zone's offset (`date_formatting.iso_in_zone`) — precise,
   dialect-stable, and round-trip-safe (any ISO 8601 offset parses
   back). The audit-events extract is the exception: it stays in
   UTC (`spec/timezone_display.md`).
5. **Vocabulary normalisation.** The `data_type` column is matched
   **case-insensitively**, so a file written with capitalised tokens
   (`String`, `DateTime`) must validate identically to the
   documented lowercase ones — otherwise a hand-edited or older
   bundle fails on a cell whose meaning is unambiguous. A response
   field's `data_type` value (`instruments[n].response_fields[m].data_type`)
   is matched the same way, ignoring surrounding spaces: `integer`,
   `INTEGER` and `Integer` all import as the model value `Integer`,
   which serialise emits. A blank value imports the default response
   field's type and bounds, not the row's own; any other value than
   `String`, `Integer`, `Decimal` or `List` is an error.
6. **Empty-string handling.** A `null` cell in storage is an
   empty CSV cell on serialise; an empty CSV cell on parse is
   `None`. No `"None"` strings, no `"null"` strings.
7. **Every `session_rule_sets` row is emitted, and re-importing one
   cannot collide.** Nothing seeds a rule set on session create, so every
   row is operator-authored and there is no seeded set to filter. Apply is
   an **upsert by name**: a row whose name already exists in the
   destination is updated, and rows the CSV omits are deleted — so
   `uq_session_rule_set_session_name` is **unreachable from this path**,
   whether the target is the source session itself or another that already
   carries the name.
   **The one case that could reach the constraint is a bundle naming the
   same rule set twice**, because apply adds per row without flushing
   between them. The parse phase rejects that bundle before phase 2 runs —
   a `duplicate session_rule_sets name` error, so nothing is written.
   Pinned by
   `tests/unit/test_session_rule_set_reimport.py::test_two_rows_sharing_a_name_are_rejected_before_any_write`,
   which fails if the cross-row check is removed — named rather than
   numbered, because an ordinal rots the moment a case is added or dropped.

The round-trip is asserted by `tests/unit/test_apply_session_config.py`,
`tests/unit/test_session_config_io.py`,
`tests/unit/test_data_shapes_settings_roundtrip.py` and
`tests/integration/test_settings_csv_instrument_order.py`, with per-entity
round-trip tests in `tests/integration/test_extracts_*.py`.

---

## 5. Shared parsing primitives

`app/services/csv_imports.py` exposes the helpers every importer
shares. Public surface:

| Helper | Role |
|---|---|
| `decode_csv(content, source, *, max_bytes=MAX_BYTES) -> tuple[str \| None, ValidationIssue \| None]` | UTF-8 decode + BOM strip. Single function so every importer gets identical encoding behaviour. Returns a structured issue rather than raising on the two operator-facing failures — file too large, not valid UTF-8 — so a caller renders them like any other validation problem; `source` names the import for the message and the log line. `max_bytes` is overridable so a caller with a different ceiling need not fork the helper. |
| `_read_dict_rows(text, source) -> tuple[rows \| None, fieldnames, field_labels, ValidationIssue \| None]` | `csv.DictReader` wrapper (blank lines skipped). Normalizes the header first — a labelable tag column's `.label` suffix (§1a) is stripped to its canonical name, and the captured `(source_type, source_field) → label` map comes back as `field_labels` — so rows key by the bare column name. A file with no header row, more than `MAX_ROWS` data rows, a header friendly label longer than `session_field_labels.label` (255; the issue names the column, e.g. `ReviewerTag1`), or a file the `csv` module refuses to parse (chiefly a cell past its 131,072-character field limit, which a file under `MAX_BYTES` can carry) returns `rows=None` and one blocking issue. |
| `_missing_columns_issues(fieldnames, required, source)` | Returns one `ValidationIssue` per missing required column. Called at parse time, before per-row iteration. |
| `_cell(row, key)` | Stripped string read; returns `""` when key absent. |
| `_none_if_blank(row, key)` | `None` when cell is empty / whitespace-only, else the stripped string. The canonical "optional cell" reader. |
| `cell_length_issues(row, model, headers, *, source, row_number)` | One blocking issue per cell longer than the `model` column it lands in; `headers` maps each row attribute to its CSV column. Used by all four roster parsers (§1, *Cell lengths*). |
| `_parse_email(value, *, strict, source, row_number, field)` | Email validation with row-context error message. Used by the reviewer, reviewee and observer parsers on their `*Email` columns. **`strict` decides the non-email case**: reviewers and observers pass `strict=True`, so a cell that is not an address is rejected; reviewees pass `strict=False`, which accepts a cell with **no `@`** as an opaque identifier but still requires `EMAIL_RE` of anything containing one, so `foo@` is caught rather than imported. **Not** used by the Relationships importer, which performs no format validation at all: a malformed `ReviewerEmail` there fails FK resolution and is reported as *"Unknown reviewer"* rather than as a bad address. |
| `check_cross_table_identity(db, *, session_id, rows, kind)` | Cross-roster guard for a parsed CSV — rejects a row whose email another roster already holds under a different name. `kind` is `"reviewers"` / `"reviewees"` / `"observers"`; anything else raises, rather than returning `[]` and reporting success for an import it never checked. |
| `cross_table_identity_conflict(db, *, session_id, kind, identifier, name)` | The single-row form, for the create / edit services, so the rule has one home and every write path reaches it. Returns the `(roster label, name)` of a holder that disagrees, or `None`. **Any** disagreement is a conflict: a mailbox that already holds two names is not satisfied by matching one of them. |
| `is_comparable_identity(identifier, name)` | Whether a pair can disagree with another at all — an identifier with no `@`, or a row with no name, cannot. One predicate for the importers, the services and the Validate rules. |

---

## 5a. Setup templates (starter, demo, full sets)

Three generic template sets an operator downloads **before any
session exists**. The starter and demo sets carry the same four
roster files and differ only in their rows; the full set
carries two of those four, at a realistic class size.

Routes: `GET /templates/starter.zip`, `GET /templates/demo.zip`,
`GET /templates/full.zip` → `app/web/routes_templates.py`. Generator:
`app/services/setup_templates.py`. Download filenames:
`review-robin-setup-templates.zip`, `review-robin-demo-session.zip`,
`review-robin-sample-rosters-154.zip`.

| Set | Rows | Job | Offered from |
|---|---|---|---|
| **starter** | one per file | *Edit this* — the format, with one example row to replace | Guide "Create and set up a session" card; lobby first-run card |
| **demo** | six students, twelve pairs, two observers | *Watch this work* — a populated session to walk through | Guide "Sample session" card |
| **full** | 154 people in each of two files | *Try this at scale* — a class-sized roster, no configuration | Guide "Sample session" card |

**Members.** The starter and demo sets carry `reviewers.csv`,
`reviewees.csv`, `relationships.csv`, `observers.csv`. The full set
carries only `reviewers.csv` and `reviewees.csv`, with **no
relationships, observers or settings file, and no round-trip test**:
it has no pairing rule to make Full Matrix on 154 people affordable
(23,716 assignments), so a session built from it pairs everyone with
everyone until the operator sets a rule.

**The full set's cohort.** Eleven tutorial groups of fourteen
(`TW01`–`TW11`), each split into teams of 5 / 5 / 4 numbered across
the class (`Team 1`–`Team 33`), so a team's number names its group.
Six tutors each take two groups, except the last, who takes one.
`operator@example.edu` is among the 154 because it is the default
`FAKE_AUTH_EMAIL` — signed in locally under `ALLOW_FAKE_AUTH`, the
operator is also a reviewer and reviewee of a session built from this
set. Only reviewees carry a `ProfileLink`, a placeholder under
`example.edu`.

**No set carries a `settings.csv`, and none is needed.** A new
session is seeded with a default instrument
(`ensure_default_instrument`) whose new-model rule defaults to Full
Matrix, so the roster files alone carry a session to `validated` —
asserted end-to-end by the demo set's round-trip test below (the
full set has none; see Members). A settings file
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
and its three siblings. A column added to an extract reaches every
set carrying that file with no edit to the generator, and
`tests/unit/test_setup_templates.py` asserts the identity (not
equality) of each tuple. Headers are derived; rows are where a set
differs, each one a column-name → cell mapping checked against its
header in both directions: a missing column raises rather than
emitting a short row, and a cell for a column the header lacks fails
the test. The starter and demo rows are hand-authored; the full
set's are generated from fixed name lists with no randomness, so
the file is the same on every request either way. All three sets are
the same generator with different inputs — every structural test
runs against all three, parameterised.

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
`PairContextTag1.Interest Group`, and the reviewee equivalents. Each
set brings its own labels (`TemplateSet.labels`, default `LABELS`).
The starter and demo sets leave Tag 3 bare on both rosters, so those
two sets show labelling as per column and optional; the full set
labels all three tag columns (`Tutor` / `Group` / `Team`). The suffix
grammar is the one thing about roster CSVs an operator cannot guess,
and a template that demonstrates it teaches more than one that
avoids it.

The consequence is live: on import a labelled header **sets** that
slot's override (`field_labels.apply_import`), so
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
Extract Data: neither reaches an operator who wants the templates
while creating the session.

---

## 6. Surface mapping

| Surface | Direction | Service | Spec |
|---|---|---|---|
| Extract Setup card — Reviewers tile | Out | `serialize_reviewers` | `spec/session_home.md` §2 |
| Extract Setup — Reviewees tile | Out | `serialize_reviewees` | same |
| Extract Setup — Relationships tile | Out | `serialize_relationships` | same |
| Extract Setup — Observers tile (when `observers_enabled`) | Out | `serialize_observers` | same |
| Extract Setup — Settings tile | Out | `serialize_session_config` (via `_session_config_csv`) | same |
| Extract Setup — Zip all tile | Out | `build_setup_bundle` — a zip of the Reviewers, Reviewees, Relationships and Settings CSVs, plus `{code}_observers.csv` when `observers_enabled` (`GET /export/bundle.zip`, filename `{code}_setup.zip`) | same |
| Extract data tab — Zip all button | Out | `build_responses_bundle` — always the unified Responses CSV; plus, for each intro chip that is on, the files that card's own button downloads under the same names and as the card is configured: the By-instrument CSVs (`?by_instrument=0` omits), the Reviewer and Reviewee metadata CSVs (`?reviewer_metadata=0` / `?reviewee_metadata=0`), every saved Data shape's CSV (`?data_shapes=0`) and, when `observers_enabled`, `{code}_participant_tokens.csv` (`?tokens=0`); each card's own query rides as `?{flag}.{param}` (`spec/extract_data.md`, Extract all data card) (`GET /export/responses_bundle.zip`, filename `{code}_responses.zip`) | `spec/extract_data.md` |
| Extract data tab — Data shaper Zip all button | Out | `build_data_shapes_bundle` — every saved Data shape's CSV, each named and built as its own Download (`GET /export/data_shapes_bundle.zip`, filename `{code}_data_shapes.zip`; 404 with no saved shape). Row order: per-individual rows active first, then name, email / identifier, id; per-tag-combo rows by their tag values in chip order | `spec/extract_data.md` |
| Extract data tab — By-instrument Zip all button | Out | `build_by_instrument_bundle` — a zip of one wide-format CSV per instrument (`GET /export/by_instrument_bundle.zip`, filename `{code}_by_instrument.zip`; members named `{code}_by_instrument_{slug}.csv` where `{slug}` comes from the instrument's short label or the `Instrument_{session_seq}` fallback). Each member starts with a key/value meta block (instrument identity + per-response-field type/constraint rows + assignment count + pool / unit-of-review / self-review configuration) + blank row + wide data table (one row per assignment, columns = identity + tags + one per response field + SelfReview/SavedAt/SubmittedAt), rows sorted by `RevieweeName`, `ReviewerName`, `RevieweeEmail`, `ReviewerEmail`, then assignment id. | `spec/extract_data.md` |
| `GET /export/responses.csv` | Out | `serialize_responses` — no tile links it; the same file rides in the Extract data tab's Zip all | §2.4 |
| Sys Admin per-session audit-log page — Download CSV | Out | `serialize_audit_events` (`GET /export/audit_log.csv`) | §2.5 |
| Reviewer summary — "Download my responses (CSV)" | Out | `serialize_reviewer_session_summary` (`GET /me/sessions/{id}/summary.csv`) | `spec/reviewer-surface.md` "Per-session summary" |
| Reviewers Setup page — Upload CSV | In | `parse_reviewer_csv` + `save_reviewers` | `spec/setup_pages.md` |
| Reviewees Setup page — Upload CSV | In | `parse_reviewee_csv` + `save_reviewees` | same |
| Relationships Setup page — Upload CSV | In | `parse_relationship_csv` + `save_relationships` | same |
| Observers Setup page — Upload CSV | In | `parse_observer_csv` + `save_observers` | same |
| Quick Setup Reviewers / Reviewees / Relationships slots, and Observers when `observers_enabled` | In | same as per-page Upload — Quick Setup is a thin shell over the per-entity primitives | `spec/quick_setup_card_spec.md` |
| Quick Setup Settings slot | In | `apply_session_config` | same |
| Guide + lobby first-run card — Download setup templates | Out | `build_zip(starter)` — a zip of four generic roster templates, headers derived from the extracts' `HEADER` tuples, one row each (`GET /templates/starter.zip`). Session-independent; see §5a. | §5a |
| Guide "Sample session" card — Download sample session data | Out | `build_zip(demo)` — the same four files populated with a two-group cohort (`GET /templates/demo.zip`). Reaches `validated` through Quick Setup with no configuration; see §5a. | §5a |
| Guide "Sample session" card — Download the full-size sample rosters | Out | `build_zip(full)` — `reviewers.csv` and `reviewees.csv`, the same 154 people in each, tagged Tutor / Group / Team (`GET /templates/full.zip`, filename `review-robin-sample-rosters-154.zip`). No relationships, observers or settings file; see §5a. | §5a |

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

   **A roster replace destroys more than the roster.**
   `relationships` holds `ondelete="CASCADE"` foreign keys to both
   rosters, so re-uploading Reviewers or Reviewees deletes every pair
   naming a removed row, alongside the assignments and responses that
   already cascaded. The operator is told **before** the upload, not
   after: the confirmation names each kind it will destroy, and the
   `reviewers.imported` / `reviewees.imported` audit event counts them
   in `cascaded_relationships` beside `cascaded_assignments`
   (`spec/architecture.md` § *Audit-event detail schema*).
   Relationships' own replace has no further cascade — it *is* the
   leaf — except that a pair it moves to another pair-context group
   gives up its group answer copy (`spec/assignments.md` "Group-scoped
   fan-out").

3. **Two-phase parse + apply (Settings).** Parse everything,
   collect every error, then apply or rollback, so one submit
   reports every error rather than playing whack-a-mole.
   `ApplyResult.errors` carries the whole report; the Quick Setup
   Settings slot shows its first five at most (fewer when quoted values make them long) and a count of the rest
   (`spec/quick_setup_card_spec.md`, "Result reporting").

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
