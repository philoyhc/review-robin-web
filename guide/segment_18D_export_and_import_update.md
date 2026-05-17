# Segment 18D — Export and import update

> **Stub created 2026-05-12; swept 2026-05-17** against the
> shipped codebase. Siblings: **18A** (Sessions lobby
> enhancements — *shipped 2026-05-17*,
> `guide/segment_18A_sessions_lobby_enhancements.md`) and
> **18C** (Operator-triggered purge — *shipped 2026-05-17*,
> `guide/archive/segment_18C_retention_deletion.md`).

**Stub. Sketch-level scope only.** Detailed PR breakdowns
get drafted when this segment is picked up.

## Goal

Bring the export / import surface into alignment with the
post-15C / post-15B session model. **Segment 12A-3** (PRs
#779 → #783, 2026-05-10) was the last full pass on this
surface; since then the data shape has moved on:

- **15C** (shipped 2026-05-12) introduced the per-operator
  RTD / RuleSet **library tier** above the per-session
  copies — `library_origin_id` provenance pointers on both
  `response_type_definitions` and `session_rule_sets`,
  plus `is_seeded` flags on each. The Settings CSV
  round-trip predates this column set and doesn't carry
  library-tier provenance.
- **15B** (shipped 2026-05-13) made `instruments.rule_set_id`
  load-bearing — each instrument carries its own RuleSet
  pointer. The Settings CSV serialiser
  (`session_config_io/_serialize.py`) already reads
  `instrument.rule_set_id` live for the
  `instruments[N].rule_set_name` cell, **with** the pre-15B
  `_audit_log_rule_set_name` fallback retained for instruments
  still left un-pinned. Part 2 below is now a fallback-retirement
  + importer-parity audit rather than a fresh build.
- **15F** (shipped 2026-05-15) added per-row inline edit on
  the Manage pages. The per-entity CSVs are still the only
  bulk-edit surface and stay the porting backbone, but
  the analytical "Responses" extract is overdue an
  `Instrument` flavour column once 13C ships group-scoped
  instruments.

This segment is the catch-up pass that picks up whichever
of those columns / flavours have shipped at the point of
scoping, and lands the round-trip parity work in one
coherent direction rather than dribbled across each
consumer segment. As of the 2026-05-17 sweep its three live
consumers (15B / 15C / 15F) have all shipped — Parts 1, 2
and 4 are actionable now; Parts 3 and 5 remain blocked.

## Why now

- **Round-trip parity drift.** Each segment that adds a
  column to a serialised entity (15C `is_seeded` /
  `library_origin_id`; 15B `instruments.rule_set_id`;
  13C group-scoping; 13F PR 5 retention overrides — now
  an 18F Part 4 consumer) expands the gap between what the
  export emits and what the importer accepts. Without a
  periodic catch-up segment, the Settings CSV stops
  round-tripping cleanly and the porting use case (Setup →
  Settings → Reviewers → Reviewees → Relationships into a
  fresh session) starts dropping fields.
- **Library-tier provenance is genuinely new.** Pre-15C
  there was no library tier, so the Settings CSV
  serialised per-session RTDs / RuleSets in full and the
  importer recreated them from scratch on the
  destination. Post-15C the natural question is: should
  a Settings CSV import on a session whose operator
  already has a library entry of the same name **link**
  to the library (set `library_origin_id`) or **clone**
  (NULL + standalone)? That's a UX decision worth its
  own scoping pass.
- **Aligns with the shipped 18A cloning service.** 18A's
  `app/services/session_clone.py` (shipped 2026-05-17)
  deep-copies a session's config graph entity-by-entity;
  the export / import surface in 18D defines the canonical
  per-entity payload shape. 18D should be reviewed against
  `clone_session` so the two copy paths stay aligned (e.g.
  both treating `library_origin_id` provenance the same way).

## Scope (sketch)

The exact part list depends on which consumer segments
have shipped at scoping time; the items below are the
**candidate list** to triage at that point.

### Part 1 — Settings CSV round-trip: library-tier
provenance

**Goal.** Carry `library_origin_id` provenance through
the Settings CSV so a destination operator's RTDs /
RuleSets can be linked to their library entries on
import where the name matches.

Likely shape:

- New optional `LibraryName` column per RTD / RuleSet
  row group. Export writes the source operator's library
  entry's `name` when `library_origin_id` is set;
  destination importer matches by `(name, data_type)` on
  the destination operator's library and links via
  `library_origin_id`. Unmatched names fall back to
  per-session copies (today's behaviour).
- `session.settings_imported` audit envelope picks up a
  `library_links` count.
- Round-trip stability test: export → import → export
  produces byte-identical output on the same operator.

### Part 2 — Settings CSV round-trip: per-instrument
RuleSet — fallback retirement (15B shipped)

**Status (2026-05-17 sweep).** 15B shipped — the export
serialiser (`session_config_io/_serialize.py`) **already**
reads `instrument.rule_set_id` live for the
`instruments[N].rule_set_name` cell, and the importer
(`_apply.py`) already round-trips a `rule_set_name` cell.
The fresh-build framing of this Part is obsolete; what
remains is a cleanup audit.

**Goal.** Confirm full per-instrument RuleSet parity now
that 15B is live, and decide the fate of the transitional
fallback.

Remaining work:

- Audit the pre-15B `_audit_log_rule_set_name` fallback in
  `_serialize.py` — it still fires for instruments whose
  `rule_set_id` is NULL (never pinned). Decide: keep it as
  the genuine "un-pinned instrument" path, or retire it if
  post-15B every instrument is guaranteed pinned. Lean:
  keep, but re-document — it is no longer "pre-15B".
- Verify the importer sets `instruments.rule_set_id`
  directly (resolving `rule_set_name` against the
  destination session's `session_rule_sets` in the apply
  pass) rather than leaving it NULL, and that cross-row
  validation catches typo references with the missing-RTD
  error shape.

### Part 3 — Responses extract: `Instrument` flavour
column (blocked on 13C)

**Status (2026-05-17 sweep).** Still blocked — 13C has not
shipped, and the 13F re-sweep flagged `segment_13C` itself
as a **stale plan**: it builds group fanout on
`Assignment.context` JSON, a column retired in 15D PR 6b.
13C needs a re-scope before its group-scoped-instrument
shape is even defined, so this Part cannot be scoped until
then. The Responses extract HEADER carries no flavour
column today (`InstrumentName` / `InstrumentShortLabel`
only).

**Goal.** When 13C ships group-scoped instruments, the
Responses CSV gains a derived `Instrument.flavour` (or
similarly-named) column so downstream analysis can split
group-scoped answers from per-pair answers without
re-deriving from the schema.

Likely shape:

- Add the column to `responses_extract.serialize_responses`
  between `Instrument` and `Value`; HEADER count bumps
  20 → 21.
- Tests: assert flavour cell values for each Instrument
  type 13C introduces.
- No new audit event (extract is read-only).

### Part 4 — Zip-all bundle graduation

**Goal.** The inert "Zip-all" tile on the Extract Data
card (placeholder since 12A-3 PR 2) graduates to a real
bundle: zip of every per-entity CSV, scoped to the
session.

Likely shape:

- New `app/services/extracts/zip_bundle.py` that
  collects every shipped extract's CSV via the existing
  `stream_csv` helpers and streams them through an
  in-memory zip buffer.
- `GET /operator/sessions/{id}/export/bundle.zip`
  route.
- `session.bundle_extracted` audit event with a
  `counts` envelope (rows per CSV).
- Naming convention: `{code}_bundle.zip` matching the
  per-entity `{code}_{kind}.csv` pattern.
- Decide at scoping whether the bundle includes the
  Responses CSV (porting vs analysis mix — possibly
  two bundles: `*_porting.zip` and `*_analysis.zip`).

### Part 5 — Retention overrides CSV column
(blocked on 13F PR 5)

**Status (2026-05-17 sweep).** Still blocked — 13F PR 5
(`sessions.retention_exception` + `retention_overrides`)
has not shipped. Its consumer moved when 18C was re-scoped:
the retention *feature* is now **Segment 18F Part 4**
(scheduled / policy-driven retention), not 18C. This Part
stays valid — once the columns exist, the Settings CSV
should port them — but it should be sequenced after 18F
Part 4, not 18C.

**Goal.** When 13F PR 5 lands the
`sessions.retention_exception` Boolean +
`sessions.retention_overrides` JSON column, the Settings
CSV picks them up so a session's retention posture
ports along with its setup.

Likely shape:

- New `retention.exception` Boolean row and
  `retention.overrides_json` row in the Settings CSV
  serialisation.
- Importer round-trips them; cross-row validation on
  the JSON shape (response_days / audit_days /
  archived_days keys, each optional int).
- Skip on environments where 13F PR 5 hasn't landed
  (the Settings CSV importer is per-version-tolerant —
  missing rows are accepted, and unknown keys are silently
  ignored, `_apply.py:341`).

## Export part — detailed plan (2026-05-17)

The actionable scope of 18D splits cleanly into an **export
part** (planned here) and an **import part** (planned
separately). The export part is the read-out side: it lands
the Zip-all bundle and the Settings-CSV *export* additions,
and is shippable today against the post-15B/C/F codebase.

### Locked scope decisions

- **Covers** the Zip-all bundle (Part 4), the per-instrument
  `rule_set_name` fallback audit (Part 2), the **export
  leg** of library-tier provenance (Part 1) — the Settings
  CSV emits the `library_name` provenance cell now, inert
  until the import part lands the matching / linking logic —
  and the **two session-level export gaps** the 2026-05-17
  audit surfaced: `session.display_timezone` and
  `session.self_reviews_active` (see PR E2).
- **The two session-level gaps round-trip fully** (export +
  apply), unlike `library_name` — they are not inert. Both
  are live config a ported session needs and both are
  already preserved by `clone_session`, so the CSV path is
  just catching up to the clone path.
- **Zip-all bundle = one `{code}_bundle.zip`** containing all
  five operator-facing CSVs (Reviewers / Reviewees /
  Relationships / Responses / Settings). No porting/analysis
  split. The Sys-Admin-gated audit-events extract is not in
  the bundle.
- **No Settings-CSV `version` cell.** The importer stays
  per-version-tolerant via absence-handling (missing rows
  accepted). The export part adds no fast-fail machinery.
- **Out of the export part** (→ import-part plan): matching
  `library_name` to a destination operator's library and
  setting `library_origin_id`; `rule_set_name` typo
  cross-validation on apply; retention-column round-trip
  (Part 5, also blocked on 13F PR 5); the Responses flavour
  column (Part 3, blocked on 13C).

### PR E1 — Zip-all bundle graduation

Graduates the inert "Zip all" tile on the Extract Data card
(`is_wired=False`, `coming_in=...` today) to a real download.

- New `app/services/extracts/zip_bundle.py` —
  `build_session_bundle(db, review_session)` collects each of
  the five extract serialisers' CSV output, writes each as a
  `{code}_{kind}.csv` member into an in-memory
  `zipfile.ZipFile` (`ZIP_DEFLATED` over a `BytesIO`), and
  returns the zip bytes plus a per-CSV row-count dict.
- New route `GET /operator/sessions/{id}/export/bundle.zip`
  in `routes_operator/_extracts.py` (behind
  `require_session_operator`) — builds the bundle, emits the
  audit event, returns the bytes with
  `Content-Disposition: attachment; filename={code}_bundle.zip`.
- New audit event `session.bundle_extracted` — `counts`
  envelope, one key per CSV with its row count. Register in
  `audit.EVENT_SCHEMAS` (`_IDENTITY | {"counts"}`).
- `app/web/views/_extract_data.py` — flip the `bundle` row to
  `is_wired=True`, set `download_url`, drop `coming_in`.
- Tests: route returns a valid zip with the five expected
  members; `session.bundle_extracted` emitted with the
  per-CSV counts; the tile renders wired.

### PR E2 — Settings CSV export refresh

Three `session_config_io/_serialize.py` changes (with the
matching `_apply.py` round-trip for the two new session-level
rows), cohesive because they all close Settings-CSV export
gaps surfaced by the 2026-05-17 audit.

- **Close two session-level export gaps.** The audit found
  two live per-session columns the export silently drops —
  both copied by `clone_session`, so the CSV path is behind
  the clone path:
  - **`session.display_timezone`** (string) — without it an
    imported session loses its 18B per-session timezone and
    falls back to the importing operator's default. Emit it
    in `_session_rows`; `_apply.py` writes it back.
  - **`session.self_reviews_active`** (boolean) — load-bearing
    for generation (`assignments.py:542` gates self-review
    pairs on it). Without it an imported-then-Generated
    session produces a different assignment set. Emit + apply.
  - Both ride the existing `session.*` key namespace and the
    importer's `_apply_session_kv` fallback writer; neither
    is in the `{assignment_mode, status}` machine-derived
    ignore set.
- **`library_name` provenance cell.** For each
  `response_type_definitions[N]` and `session_rule_sets[N]`
  group, emit a `…library_name` key — the *library entry's*
  `name` resolved via `library_origin_id` (the session copy
  may have been renamed, so resolve the origin, not the
  copy's own name); empty when `library_origin_id` is NULL.
  This is the export leg only; the import part lands the
  link/clone logic. **No importer change is needed** for the
  inert column — the importer silently ignores unknown keys
  (`_apply.py:341`), so emitting `library_name` does not
  break the export → re-import round-trip.
- **`rule_set_name` fallback re-document (Part 2).** The
  `_audit_log_rule_set_name` fallback in `_serialize.py` is
  no longer "pre-15B" — post-15B it is the genuine *un-pinned
  instrument* path (instruments whose `rule_set_id` is NULL).
  Re-document its docstring accordingly; keep the function.
  Add a test pinning both branches: a pinned instrument reads
  `rule_set_id`, an un-pinned one falls back.
- Tests: round-trip stability — export → re-import → export
  is byte-identical on the same operator; `display_timezone`
  + `self_reviews_active` survive the round-trip; the
  importer accepts a CSV carrying `library_name` rows without
  error.

### Sequencing

PR E1 and PR E2 are independent — no ordering constraint.
Both are pure serialisation / route work; the underlying
tables already carry every column read. The import part
(library link/clone, validation) is planned after, and may
itself wait on a UX decision (link-by-name-match vs
always-clone — see Working notes).

## Hard dependencies

- **Parts 1, 2 and 4 are unblocked** as of the 2026-05-17
  sweep — 15B / 15C / 15F have all shipped, the Zip-all tile
  is still inert, and library provenance needs no consumer.
- **Part 3** is blocked on **13C**, which itself needs a
  re-scope first (its `Assignment.context` base column was
  retired in 15D PR 6b — see the 13F 2026-05-15 re-sweep).
- **Part 5** is blocked on **13F PR 5** (the retention
  columns); sequence it after **18F Part 4**, which now
  owns the retention feature.

## Out of scope

- **New entity exports.** This is a parity / catch-up
  segment for the existing five extracts; new entities
  (e.g. a separate Library extract) belong in their
  own segments.
- **Cross-session import** ("apply this Settings CSV
  to ten sessions at once"). 18D stays single-session
  on each leg of the round-trip.
- **Schema changes.** All work is at the
  serialisation / route layer; the underlying tables
  already carry every column 18D reads or writes.

## Doc impact

When parts ship:

- `docs/status.md` timeline entry per Part.
- `guide/todo_master.md` updated.
- `spec/settings_inventory.md` — Settings CSV row list
  updated to reflect Library / retention columns;
  Responses CSV row count bumped if Part 3 ships.
- `spec/architecture.md` — audit-event detail schema
  picks up `session.bundle_extracted` if Part 4 ships.
- `docs/imports.md` — Library-link semantics + the
  per-instrument RuleSet resolution rules documented
  for operator-facing porting.

## Working notes

- _(placeholder for decisions during PR scoping)_
- **Pin order against the segment queue.** As of the
  2026-05-17 sweep the picture has split. Parts 1, 2 and 4
  carry parity for already-shipped consumers (15C / 15B /
  15F) and can be picked up now — a worthwhile minimum
  scope. Parts 3 and 5 still carry parity for unshipped
  consumers (13C, 13F PR 5) and should wait, otherwise they
  ship inert and need re-touching. Cleanest: scope 18D as a
  **Parts 1 + 2 + 4** segment now, and fold Parts 3 / 5 in
  later (or hand them to 13C and 18F Part 4 as ride-along
  CSV work).
- **Versioning the Settings CSV — decided: no version
  cell.** The importer is already version-tolerant in both
  directions — missing rows are accepted, and unknown keys
  are silently ignored (`_apply.py:341`), not rejected. The
  export part adds new rows without a `version` cell or any
  fast-fail machinery; revisit only if a future shape change
  is genuinely incompatible rather than additive.
- **Library link vs clone on import.** The default
  proposed in Part 1 is "link by name match"; an
  alternative is "always clone, never link". The link
  default preserves library-side delete-cascade
  semantics (15C invariant #3 — session copies survive
  via `ON DELETE SET NULL`) and matches the
  auto-copy-on-create UX.
