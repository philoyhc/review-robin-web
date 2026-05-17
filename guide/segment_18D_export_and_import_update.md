# Segment 18D — Export and import update

> **Stub created 2026-05-12** as part of the Segment 18
> (Session lifecycle adjacencies) family. Siblings: **18A**
> (Sessions lobby enhancements — cloning / tagging /
> archiving, `guide/segment_18A_sessions_lobby_enhancements.md`)
> and **18C** (Retention / deletion workflow,
> `guide/archive/segment_18C_retention_deletion.md`).

**Stub. Sketch-level scope only.** Detailed PR breakdowns
get drafted when this segment is picked up.

## Goal

Bring the export / import surface into alignment with the
post-15C / post-15B session model. **Segment 12A-3** (PRs
#779 → #783, 2026-05-10) was the last full pass on this
surface; since then the data shape has moved on:

- **15C** (2026-05-12) introduced the per-operator
  RTD / RuleSet **library tier** above the per-session
  copies — `library_origin_id` provenance pointers on both
  `response_type_definitions` and `session_rule_sets`,
  plus `is_seeded` flags on each. The Settings CSV
  round-trip predates this column set and doesn't carry
  library-tier provenance.
- **15B** (upcoming) flips `instruments.rule_set_id` to
  load-bearing — each instrument carries its own RuleSet
  pointer. The Settings CSV's `instruments[N].rule_set_name`
  cell needs to round-trip *per-instrument* rather than
  via the pre-15B audit-log fallback in
  `session_config_io.py`.
- **15F** (upcoming) adds per-row inline edit on the
  Manage pages. The per-entity CSVs are still the only
  bulk-edit surface and stay the porting backbone, but
  the analytical "Responses" extract is overdue an
  `Instrument` flavour column once 13C ships group-scoped
  instruments.

This segment is the catch-up pass that picks up whichever
of those columns / flavours have shipped at the point of
scoping, and lands the round-trip parity work in one
coherent direction rather than dribbled across each
consumer segment.

## Why now

- **Round-trip parity drift.** Each segment that adds a
  column to a serialised entity (15C `is_seeded` /
  `library_origin_id`; 15B `instruments.rule_set_id`;
  13C group-scoping; 13F PR 5 retention overrides)
  expands the gap between what the export emits and what
  the importer accepts. Without a periodic catch-up
  segment, the Settings CSV stops round-tripping cleanly
  and the porting use case (Setup → Settings →
  Reviewers → Reviewees → Relationships into a fresh
  session) starts dropping fields.
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
- **Composes with 18A** (Session cloning). The cloning
  service in 18A copies entity-by-entity; the export /
  import surface in 18D defines the canonical
  per-entity payload shape. If 18A lands first it
  should be reviewed against the 18D parity goals so
  the two paths stay aligned.

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
RuleSet (post-15B)

**Goal.** When 15B has shipped, `instruments[N].rule_set_name`
moves from "audit-log fallback" to "live read off
`instruments.rule_set_id`" on export, and the importer
sets `instruments.rule_set_id` directly rather than
leaving it NULL.

Likely shape:

- Drop the pre-15B `_audit_log_rule_set_name` fallback
  in `session_config_io.py` once 15B is live (or guard
  it on a feature flag during the transition).
- Importer resolves `rule_set_name` against the
  destination session's `session_rule_sets` (Phase 2
  apply pass — needs the RuleSets to already exist in
  the session by the time the importer reaches the
  instruments rows).
- Cross-row validation: catch typo references with the
  same error shape today's importer uses for missing
  RTDs.

### Part 3 — Responses extract: `Instrument` flavour
column (post-13C)

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
(post-13F PR 5)

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
  (Settings CSV is per-version-tolerant — missing rows
  are accepted, unknown rows are rejected).

## Hard dependencies

- **15B** for Part 2 (per-instrument RuleSet writes).
- **13C** for Part 3 (group-scoped instrument flavours).
- **13F PR 5** for Part 5 (retention columns).
- Part 1 (library-tier provenance) and Part 4 (Zip-all)
  are unblocked today.

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
- **Pin order against the segment queue.** This segment
  should be picked up *after* the consumer segments
  (15B, 13C, 13F PR 5) it carries parity for, otherwise
  each part would ship inert and need re-touching when
  the consumer lands. Part 1 (library provenance) +
  Part 4 (Zip-all) can ship ahead of the others if
  there's a porting-UX reason to.
- **Versioning the Settings CSV.** Today the importer
  is per-version-tolerant via absence-handling. If 18D
  adds enough new rows it may be worth bumping a
  `version` cell at the top of the file for fast-fail
  on mismatched-shape uploads. Decide at scoping.
- **Library link vs clone on import.** The default
  proposed in Part 1 is "link by name match"; an
  alternative is "always clone, never link". The link
  default preserves library-side delete-cascade
  semantics (15C invariant #3 — session copies survive
  via `ON DELETE SET NULL`) and matches the
  auto-copy-on-create UX.
