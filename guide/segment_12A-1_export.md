# Segment 12A-1 — Session export (settings + reviewers + reviewees + assignments)

Ships **four CSV downloads** off the Extract Data card on Session
Home, capturing everything the operator typed to set up a
session:

- **Session settings** — every operator-typed configuration
  field in one CSV (session metadata, email-template overrides,
  per-session RTDs, instruments + their display / response
  fields, per-session RuleSets, per-session friendly-label
  overrides).
- **Reviewers** — the reviewer roster as a CSV that round-trips
  with the existing reviewer upload.
- **Reviewees** — same shape for reviewees.
- **Assignments** — manual assignment rows as a CSV that
  round-trips with the existing manual-assignments upload.
  **Only emitted on `assignment_mode == "manual"` sessions** —
  rule-based sessions surface the row disabled with an
  explanatory note ("snapshot the inputs, never the outputs" —
  rule-based assignments are derived from the RuleSet, which
  itself is in the settings CSV).

Read-only. No lifecycle gate — extraction is useful in `draft`
(sanity-check the config you typed), `validated`, `ready` (mid-
flight snapshot), and `closed` (final). The Extract Data card
stays interactive in every state, including behind the yellow
lock card (lock disables setup mutations only, not reads).

No import counterpart, no zip bundle, no responses CSV in this
segment — see "Out of scope" at the bottom.

## Inclusion rule

> *If the operator were setting up an equivalent new session
> from scratch, would they have to retype this?*
>
> - **Yes** → include in the export.
> - **No (machine-derived from operator typing)** → exclude.
> - **No (system-emitted record / per-instance state /
>   per-operator credential)** → exclude.

**Snapshot the inputs, never the outputs.** Anything a machine
step derives from operator typing — assignment rows from a
RuleSet + roster, validation reports from setup, lifecycle state
from Activate / Pause / Close, invitation tokens, the audit
log, reviewer responses — is omitted.

**Inert-but-coming columns are included.** Operator-typed
columns scaffolded today (per `spec/settings_inventory.md` §9)
but not yet wired by their owning segment are exported anyway
— e.g. `instruments[N].sort_display_fields` (Segment 13B's
target), `instruments[N].group_kind` (Segment 13C),
per-session `session_rule_sets` snapshots (Segment 15B), and
the `session_field_labels` overrides (Segment 15A). Reasoning:
an operator who configures one of those settings after the
owning segment lights up should not have to retype it on the
next session just because the export shipped before the
wire-up did. Until the owning segment lands, the corresponding
section serialises empty / default rows — exporting an empty
section is a no-op, but pinning the key shape now means
future-equipped sessions round-trip without an export-shape
change.

**Operator-level (workspace-scoped) settings are excluded.**
SMTP credentials, the operator-library RTDs
(`operator_response_type_definitions`, Segment 15C), and
operator-library RuleSets (`operator_rule_sets`) are
per-operator, not per-session — each operator configures their
own. Session-level copies (`response_type_definitions`,
`session_rule_sets`) **are** included; they're the
session-scoped state the operator built up for this particular
session.

## Round-trip readiness

The four CSVs this segment ships, plus the session-create-time
seed materialisation already in place on every deployment, plus
**either** a manual assignments CSV **or** a re-run of Generate
against an exported RuleSet, are sufficient to fully set up a
new session into a state where Validate is meaningful. Walking
through the validation rules in `app/services/validation.py` —
each row names where the requirement is captured:

| Validation rule | Severity | Captured in |
|---|---|---|
| `session.no_name` | error | `session.name` (settings CSV) |
| `session.no_code` | error | `session.code` (settings CSV) |
| `reviewers.empty` | error | reviewers CSV |
| `reviewers.duplicate_email` | error | reviewers CSV (importer rejects on upload) |
| `reviewees.empty` | error | reviewees CSV |
| `reviewees.duplicate_id` | error | reviewees CSV (importer rejects on upload) |
| `instruments.no_fields` | error | `instruments[N].response_fields[M].*` (settings CSV) |
| `instruments.no_display_fields` | warning | `instruments[N].display_fields[M].*` (settings CSV) |
| `assignments.no_mode` | warning | manual assignments CSV upload **or** rule-based Generate run on the destination |
| `email_template.no_help_contact` | info | `session.help_contact` (settings CSV) |

Cross-references each piece of operator typing relies on are
also covered:

- **RTD references on response fields.**
  `instruments[N].response_fields[M].response_type` resolves to
  either a seeded RTD name (auto-materialised from
  `SEED_RESPONSE_TYPE_DEFINITIONS` on session create) or a
  `rtds[<name>]` row exported earlier in the same CSV. The
  importer fails loudly if a name doesn't resolve.
- **RuleSet references on instruments (post-15B).**
  `instruments[N].rule_set_name` resolves to either a seeded
  RuleSet (auto-materialised from `SEEDS` /
  `SEEDED_RULE_SETS` on session create) or a
  `session_rule_sets[N].*` block exported earlier in the same
  CSV. Same fail-loud rule.

### Manual-mode round-trip

For sessions where `assignment_mode == "manual"`:

1. Operator imports settings CSV → reviewers CSV → reviewees
   CSV in any order.
2. Operator imports assignments CSV last (the importer
   resolves reviewer / reviewee emails against the now-
   populated rosters and resolves the `Instrument` column
   against the now-populated instruments).
3. Validate is meaningful — all errors above are addressable
   with what's been imported.

### Rule-based-mode round-trip

For sessions where `assignment_mode == "rule_based"`:

1. Operator imports settings CSV → reviewers CSV → reviewees
   CSV in any order. The settings CSV's `session_rule_sets[N]`
   blocks rehydrate every operator-authored RuleSet the source
   session had; seeded RuleSets are already present on the
   destination from the session-create-time materialisation.
2. Operator runs Generate. **Post-15B**, the engine reads each
   `instruments.rule_set_id` (set during the settings-CSV import
   from the `instruments[N].rule_set_name` reference) and runs
   per-instrument. **Pre-15B**, the operator selects a RuleSet
   from the picker — the picker reads the same union of seeds +
   session_rule_sets, so any RuleSet the source session used is
   selectable on the destination.
3. Validate is meaningful.

### Pre-15B / pre-15C transient gap (closed by PR 1a for seeded RuleSets)

Today (pre-15B), `instruments.rule_set_id` is inert and
`session_rule_sets` is empty. Today's rule-based generation
selects a single workspace-tier RuleSet (`operator_rule_sets`)
per session-wide Generate run; that selection lives only in the
audit log.

**PR 1a (below) closes this gap for the seeded-RuleSet case.**
At export time, the serialiser reads the latest
`assignments.generated` audit row, resolves
`refs.rule_set_id` against `operator_rule_sets`, and — when the
matching row is a seed (`is_seed=True`) — stamps that seed's
name into every instrument's `instruments[N].rule_set_name`
cell. The destination's session-create-time
`materialise_seed_rule_sets` (Segment 15C Slice 1) materialises
the same-named seed into `session_rule_sets`, so the
name-based reference resolves locally without any
workspace-tier portability.

**Personal-library RuleSets remain out of scope.** PR 1a
explicitly does not stamp `rule_set_name` for non-seed
(`is_seed=False`) audit refs — those rules live in the
operator's workspace library and don't travel with a
per-session export. A rule-based session that used a Personal
RuleSet exports an empty `rule_set_name` cell on every
instrument, and the destination operator picks a RuleSet from
their own library on re-Generate. Personal-library
portability is a separate concern (workspace-scoped, anchored
on Operator Settings + Rule Builder) — its own future segment.

Once 15B + 15C ship, every RuleSet the source session used is
either a seed (regenerated on the destination) or in the
source session's `session_rule_sets` table (exported into the
Settings CSV's `session_rule_sets[N]` block), and PR 1a's
audit-log lookup becomes unnecessary — the per-instrument
column is the source of truth. PR 1a's logic stays in the
serialiser as a fallback for any session whose
`instruments.rule_set_id` is still NULL post-15B (e.g.
sessions that haven't been re-Generated since 15B shipped).

## Filename convention

Every download is `{code}_{kind}.csv` — e.g.
`CS101_settings.csv`, `CS101_reviewers.csv`. The `{code}_`
prefix is enough to disambiguate downloads from different
sessions sitting in a downloads folder. Centralised in
`extracts.filename(session, kind)` so the convention is one
string to change later if needed.

## Settings CSV contents

Source of truth for the curation: `spec/settings_inventory.md`.
The cut is **everything the operator typed to set up this
session, minus the per-entity rosters and minus assignments
(which ride their own CSV when the mode is manual)**.

### Per-session settings (`sessions` table — §2)

User-typed and exported:

- `session.name` (string)
- `session.code` (string) — exported as the snapshot value.
  When an import side eventually lands, this row is a fallback:
  operator-typed values on Create New Session win, and the
  importer derives a fresh code by suffix on collision. 12A-1
  just emits it.
- `session.description` (string)
- `session.deadline` (datetime; ISO-8601 with offset, empty cell
  ⇒ no deadline)
- `session.help_contact` (string)

Excluded — not user-typed:

- `session.status` — lifecycle output. Every imported session
  lands back in `draft` once the import side ships.
- `session.assignment_mode` — system-set by whichever assignment
  generation path the operator runs. Snapshot consults it once
  at export time to decide whether to emit the assignments CSV;
  doesn't appear in the settings CSV itself.
- `session.created_by_user_id` — identity / provenance.

### Email-template overrides (§3)

All 12 string keys + the boolean toggle, mirroring
`app.services.email_templates.OVERRIDE_KEYS`:

- `email_overrides.invitation.{subject,body,cc,bcc}` (string × 4)
- `email_overrides.reminder.{subject,body,cc,bcc}` (string × 4)
- `email_overrides.responses_received.{subject,body,cc,bcc}`
  (string × 4)
- `email_overrides.responses_received.enabled` (boolean; default
  `true` when absent)

Empty value cell ⇒ "use the default" (matches the live
resolver's `DEFAULT_*` fallback). Each key is exported even when
the operator left it at default — a row with an empty value is
the explicit "no override" signal.

### Per-instrument settings (`instruments` table — §4)

Keyed by 1-based position (`(Instrument.order, Instrument.id)`
order on export). User-typed and exported per instrument N:

- `instruments[N].name` (string, required)
- `instruments[N].short_label` (string)
- `instruments[N].description` (string)
- `instruments[N].order` (integer; emitted but typically
  derivable from N — the importer treats N as authoritative)
- `instruments[N].accepting_responses` (boolean)
- `instruments[N].responses_visible_when_closed` (boolean)

**Inert-but-included** (per the inclusion rule above —
operator-typed columns scaffolded today but not yet wired by
their owning segment):

- `instruments[N].sort_display_fields` (json) — operator-defined
  default sort spec (Segment 13B). Always serialises as the
  empty list `[]` until 13B's operator UI ships. Included so
  once 13B lights up, sessions with operator-set sort defaults
  round-trip without an export-shape change.
- `instruments[N].group_kind` (enum: `tag_1` / `tag_2` /
  `tag_3`, or empty for the regular per-reviewee flavour —
  Segment 13C). Always serialises as empty until 13C's creation
  flow ships.
- `instruments[N].rule_set_name` (string) — reference into the
  per-session RuleSet store (`session_rule_sets`, Segment 15B).
  **Resolves by name, not by id**: on the destination side the
  name must match either (a) a seeded RuleSet auto-materialised
  on session create from `SEEDS` in
  `app/services/rules/seeds.py` (post-15C Slice 1; renamed to
  `SEEDED_RULE_SETS` by that slice per the symmetry with
  `SEEDED_RESPONSE_TYPE_DEFINITIONS`), or (b) a non-seeded
  RuleSet defined in the same CSV's `session_rule_sets[N].*`
  blocks. The importer fails loudly if a referenced name
  doesn't resolve. Empty cell ⇒ "no RuleSet currently selected"
  (the initial state for every existing instrument). Resolution
  at export time:
  - **Post-15B** (per-instrument selection wired): read from
    `instruments.rule_set_id` → look up the matching
    `session_rule_sets.name`.
  - **Pre-15B** (column inert): the cell is always empty.
    Today's session-wide rule-based selection lives only in the
    audit log (`assignments.generated` event's
    `refs.rule_set_id` pointing at `operator_rule_sets`); the
    export does **not** synthesise a per-instrument cell from
    it. This is a transient gap — see "Round-trip readiness"
    for the operator workflow it implies.

Excluded — not user-typed:

- `instruments[N].deadline_closed_at` — auto-set when the
  deadline passes.

### Per-session Response Type Definitions (`response_type_definitions` — §4.5)

Per-session RTDs are the **session-level** RTD store — the
source of truth for `instrument_response_fields.response_type_id`.
Keyed by `response_type` (operator-typed name; unique within a
session via `uq_rtd_session_name`). Only `is_seeded=False`
rows are exported — seeded RTDs regenerate from
`SEED_RESPONSE_TYPE_DEFINITIONS` on session create on the
destination side, so re-emitting them would either be a no-op
or a conflict. Operator-typed:

- `rtds[<response_type>].data_type` (enum: `int` / `decimal` /
  `short_text` / `long_text` / `list`)
- `rtds[<response_type>].min` (decimal)
- `rtds[<response_type>].max` (decimal)
- `rtds[<response_type>].step` (decimal)
- `rtds[<response_type>].list_csv` (csv_list)

Excluded — not user-typed:

- `is_seeded` / `seed_order` — system-emitted markers.
- `library_origin_id` — provenance pointer back to the
  operator-library row this per-session copy was cloned from
  (Segment 15C). The per-session row is the source of truth;
  the link back to the workspace library is informational and
  doesn't survive a cross-deployment hop.

The **operator-library RTD tier**
(`operator_response_type_definitions`, Segment 15C) is **not**
exported — it's a per-operator workspace concept, orthogonal to
"this session's settings".

### Per-instrument display fields

Keyed by 1-based position
(`(InstrumentDisplayField.order, .id)` order on export).
User-typed:

- `instruments[N].display_fields[M].source_type` (enum:
  `reviewee` / `pair_context`)
- `instruments[N].display_fields[M].source_field` (string —
  e.g. `tag_1`, `profile_link`, `1`/`2`/`3`)
- `instruments[N].display_fields[M].label` (string; empty ⇒
  inferred fallback per
  `instruments_service.display_field_label`)
- `instruments[N].display_fields[M].visible` (boolean)

`validation` JSON is **not exported** — it's derived from the
referenced RTD via `validation_block_for_rtd` on import.

### Per-instrument response fields

Keyed by 1-based position. User-typed:

- `instruments[N].response_fields[M].field_key` (string,
  required) — stable machine identifier; `(N, field_key)` is
  the upsert key on import so labels can be renamed without
  losing field identity.
- `instruments[N].response_fields[M].label` (string, required)
- `instruments[N].response_fields[M].response_type` (string —
  references either a seeded RTD name or an operator-defined
  `rtds[<name>]` row exported earlier in the same file)
- `instruments[N].response_fields[M].required` (boolean)
- `instruments[N].response_fields[M].help_text` (string)
- `instruments[N].response_fields[M].help_text_visible`
  (boolean)

### Per-session RuleSets (`session_rule_sets` — Segment 15B target)

Per-session snapshot copies of RuleSets — the session-level
RuleSet store. Each row is a complete snapshot of a rule tree
the operator built up in the Rule Builder for this session.
Inert today (the table landed schema-only in Segment 13D PR 2);
populated by Segment 15B Slice 2 once per-instrument selection
wires it up. Included on export per the inclusion rule
(operator-typed; will be in active use by 15B).

**Seeded RuleSets are excluded** by the same logic that
excludes seeded RTDs: they auto-materialise on session create
from a code constant
(`SEEDED_RULE_SETS` in `app/services/rules/seeds.py`, landing
in Segment 15C Slice 1) via `materialise_seed_rule_sets(db,
session)` — the mirror of `ensure_default_response_type_definitions`.
Re-emitting them would either be a no-op or a name conflict on
the destination side. Identified at export time by name-match
against the `SEEDED_RULE_SETS` constant, mirroring how seeded
RTDs are identified by `is_seeded=True`. (If a future
operator-edit-on-seeded path lands, fold it in as
`session_rule_sets[<name>].overrides.*` — same escape hatch
the parent doc reserves for the RTD side.)

Keyed by 1-based position (`session_rule_sets.id` order on
export, restricted to non-seeded rows). User-typed:

- `session_rule_sets[N].name` (string, required)
- `session_rule_sets[N].description` (string)
- `session_rule_sets[N].combinator` (enum: `ALL_OF` / `ANY_OF`
  / `PIPELINE`)
- `session_rule_sets[N].exclude_self_reviews` (boolean)
- `session_rule_sets[N].seed` (integer)
- `session_rule_sets[N].rules_json` (json) — the full rule
  tree, schema validated against `RuleSetSchema` in
  `app/schemas/rules.py`. The rule tree is recursive
  (composites contain rules; predicates are nested operator /
  operand structures), so it travels as a single JSON cell
  rather than as flat per-rule rows. The CSV's `data_type=json`
  escape handles the embedded JSON string.

`instruments[N].rule_set_name` (per-instrument settings, above)
references rows in this section by **name**, not by position or
DB id. The same name resolution covers seeded RuleSets, which
are not exported but materialise on the destination session
from the `SEEDS` constant under their stable canonical names.
**Name uniqueness within a session is enforced** at the schema
level by `uq_session_rule_set_session_name` (Segment 13A-2),
mirroring the parallel `uq_rtd_session_name` on
`response_type_definitions`. The export contract relies on this
invariant for the name-based reference to resolve unambiguously.

Excluded — not user-typed:

- `library_origin_id` — provenance pointer back to the
  operator-library RuleSet this snapshot was cloned from
  (Segment 15C). Same logic as the RTD `library_origin_id`:
  doesn't survive a cross-deployment hop.

The **operator-library RuleSet tier**
(`operator_rule_sets` + `rule_set_revisions`, §6) is **not**
exported by this segment. Operator-library RuleSets are
workspace-scoped, visible across every session the operator
runs; the right home for their portability is a workspace-level
import / export surface (anchored on the Rule Builder card),
not Session Home's Extract Data card. Out of scope here.

### Per-session field-label overrides (`session_field_labels` — Segment 15A target)

Per-session friendly-label overrides for tag / pair-context
fields. Inert today (table landed schema-only in 13D PR 1);
wired by 15A Slice 1 (resolver) + Slice 3 (Settings editor
surface). Included per the inclusion rule.

Keyed by `(source_type, source_field)`:

- `field_labels.<source_type>.<source_field>` (string) — e.g.
  `field_labels.reviewer.tag_1` = `"Cohort"` overrides the
  `Tag1` heading on the Reviewer Setup page.

`source_type` accepts `reviewer` / `reviewee` / `pair_context`
(matching the 15A schema). `source_field` follows the same
convention as display-field keys (`tag_1` / `tag_2` / `tag_3`
for the tag sources; `1` / `2` / `3` for `pair_context`).

### Excluded from the settings CSV

- §1 Operator-level settings — SMTP credentials and friends.
  Per-operator, not per-session.
- §5 Reviewers / Reviewees — ride their own per-entity CSVs in
  this segment.
- §6 Operator-library RuleSets (`operator_rule_sets`) —
  workspace-scoped; portability lives on a separate surface.
- §7 Browser-local UI state — cookies, localStorage, URL
  params. Cosmetic per-browser preferences.
- §8 Deployer-set environment configuration — bounds what the
  operator can do; the operator does not edit it.
- §9 `operator_response_type_definitions` — operator-library
  tier (per-operator, not per-session).
- Audit events — system-emitted record of derivations. Forensic
  audit is a separate segment's concern.
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

Plus any `pair_context_*` columns the per-session schema
carries (read from the same place the importer reads them).
Same ordering rule as reviewers.

### Assignments — `{code}_assignments.csv`

Columns (matching `assignments.parse_manual_csv`):

```
ReviewerEmail,RevieweeEmail,IncludeAssignment,Instrument
```

`IncludeAssignment` is `true` for active assignments and
`false` for inactive — preserves the active/inactive split
exactly across upload round-trip. `Instrument` carries the
per-instrument label (matching `_instrument_label`). One row
per (assignment, instrument) tuple — when a session has
multiple instruments, the same `(ReviewerEmail, RevieweeEmail)`
pair emits N rows.

**Conditional emission.** The assignments CSV is **only emitted
when `session.assignment_mode == "manual"`** — i.e. the
operator typed the rows by hand. On a rule-based session the
route returns 404, and the Extract Data card row renders
disabled with the explanatory note: "Assignments derived from
RuleSet `<name>`; the RuleSet is in the settings CSV. Run
Generate on the new session to materialise from it." (No zip
bundle in this segment — see "Out of scope".)

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

- `app/services/session_config_io.py` —
  `Row = NamedTuple("Row", [("field", str), ("value", str),
  ("data_type", str)])` and `serialize_session_config(session)
  -> list[Row]`. Pure function; no DB writes. Section ordering
  is pinned in a unit test (see "Tests" below).
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
template work for the route handlers themselves; the card
render work happens in the view adapter (next).

## Card wire-up

The Extract Data card already exists with all five rows
scaffolded inert (Segment 11H PR B; current state visible at
`app/web/views/_extract_data.py`). 12A-1 extends
`build_extract_data_context` to:

- Flip `is_wired=True` on the Settings, Reviewers, Reviewees,
  and Assignments rows; supply `download_url` from the four
  routes above.
- Update each row's `filename` to the new `{code}_{kind}.csv`
  convention.
- On the Assignments row: when `session.assignment_mode !=
  "manual"`, leave `is_wired=False` and replace the
  `coming_in` string with the rule-based explanatory note
  ("Assignments derived from RuleSet `<name>`; …"). The DOM
  contract is unchanged — the card already renders disabled
  rows that way.
- Leave the Responses row inert and the bundle footer inert
  with their existing `coming_in` strings (those are out of
  scope for this segment — see "Out of scope" below).

No partial / macro / dataclass changes — 11H PR B is the source
of truth for the card's DOM contract.

## Audit

Four new audit event types, registered in `EVENT_SCHEMAS` per
the strict-mode test gate:

- `session.settings_extracted` — detail `{"row_count": <int>}`.
- `session.reviewers_extracted` — detail `{"row_count": <int>}`.
- `session.reviewees_extracted` — detail `{"row_count": <int>}`.
- `session.assignments_extracted` — detail `{"row_count":
  <int>}`.

All emitted from within the route handler after the
`StreamingResponse` is built (the row count is known at
serialise time — the export iterates the rows once for the
audit count, then again for the stream). Read paths emit
single-event audits per project convention; no per-row diffs.

## CSV format

The settings CSV uses a 3-column key/value/data-type shape:

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
instruments[1].rule_set_name,Cross-cohort fanout,string
session_rule_sets[1].name,Cross-cohort fanout,string
session_rule_sets[1].combinator,PIPELINE,enum
session_rule_sets[1].rules_json,"{...}",json
field_labels.reviewer.tag_1,Cohort,string
…
```

`data_type` values (descriptive of the cell, not of any
underlying RTD's `data_type`):

- `string`
- `integer`
- `decimal`
- `boolean` — accepts `true`/`false` (case-insensitive) on
  import; emits lowercase on export
- `datetime` — ISO-8601 with timezone offset
  (`2026-05-15T17:00:00+00:00`); empty cell ⇒ `None`
- `enum` — finite operator-set value (e.g.
  `combinator = "ALL_OF" | "ANY_OF" | "PIPELINE"`); validated
  server-side against the enum at import time
- `csv_list` — a comma-separated literal stored as a single
  Text column (today: `ResponseTypeDefinition.list_csv`)
- `json` — JSON-encoded structured value; used for
  `sort_display_fields` and `session_rule_sets[N].rules_json`.
  The CSV `value` cell carries the JSON string with the
  standard CSV double-quote escapes.

The per-entity CSVs use their natural wide-row shapes — see
"Per-entity CSVs" above.

### Row order on the settings CSV

Stable, deterministic, designed to read top-to-bottom like a
setup walkthrough:

1. Session-level rows (name → code → description → deadline →
   help_contact).
2. Email-template override rows (invitation → reminder →
   responses_received, with subject → body → cc → bcc →
   enabled inside each kind).
3. Operator-defined RTDs, sorted by `seed_order` then
   `response_type`.
4. Each instrument block in order (`(Instrument.order,
   Instrument.id)`):
   1. Instrument-level rows (including `rule_set_name`
      reference if any).
   2. Display fields for that instrument.
   3. Response fields for that instrument.
5. Per-session RuleSets, in `session_rule_sets.id` order
   (matches the 1-based position used by
   `instruments[N].rule_set_id` references).
6. Field-label overrides (sorted by `(source_type,
   source_field)`).

Pinned in `serialize_session_config` and pinned again in a unit
test — diff-noise on re-export is what makes the CSV worth
maintaining as a template.

## PR sequence

Sized as **4 PRs** in dependency order. PRs 2 + 3 are
independent of each other and parallel-shippable once PR 1's
shared helpers are in place. PR 1a follows PR 1 — same module,
small additive change to the serialiser.

### PR 1 — Settings export + shared helpers

- `app/services/session_config_io.py` with `Row`,
  `serialize_session_config(session)`, and the per-section
  helpers (session, email overrides, RTDs, instruments,
  display fields, response fields, session RuleSets, field
  labels).
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
    fully-populated session
    (`tests/fixtures/extracts/settings.csv`).
  - Integration test for the route (auth, audit emission, 404
    on unknown session, no lifecycle gate).
  - Inert-but-included sections: empty
    `sort_display_fields`, empty `group_kind`, empty
    `session_rule_sets` table, empty `session_field_labels`
    table all emit the expected default rows / no rows
    respectively.
  - Seeded RuleSet exclusion: a session whose
    `session_rule_sets` rows are all seeded (name-matches
    against `SEEDED_RULE_SETS`) emits no rows in the
    `session_rule_sets[N].*` block; an operator-authored
    RuleSet alongside seeded ones emits exactly the
    operator-authored row, with its 1-based position
    counted against the non-seeded subset.

### PR 1a — Capture seeded-RuleSet selection from the audit log

**Goal.** Close the pre-15B rule-based-mode export gap (see
"Round-trip readiness" → "Pre-15B / pre-15C transient gap")
for the **seeded-RuleSet case only**. After this PR, a
rule-based session that used a seed (Full Matrix /
Intra-group / Cross-group / Same group, different role /
Three reviewers per reviewee) round-trips its RuleSet
selection through the export → re-Generate flow on the
destination.

**Scope simplification.** This PR explicitly **assumes the
RuleSet in use is a seeded one**. Personal-library RuleSets
(`operator_rule_sets` rows with `is_seed=False`) are out of
scope — the export emits an empty `rule_set_name` cell when
the audit log points at a Personal RuleSet, and the destination
operator picks a RuleSet from their own library on re-Generate.
Personal-library portability is a separate concern (workspace-
scoped) and lands in its own future segment.

**Change.**

- New helper in `app/services/session_config_io.py`:
  ``_audit_log_rule_set_name(db, review_session) -> str | None``.
  Looks up the latest `assignments.generated` audit row for
  ``review_session.id``, reads ``refs.rule_set_id``, joins
  against ``operator_rule_sets``. Returns the row's ``name``
  if ``is_seed=True``; returns ``None`` for non-seed (Personal)
  hits, missing audit rows, missing RuleSet rows, or anything
  else off the happy path.
- Adjust `_instrument_rows` to fall back to the audit-log
  helper when ``Instrument.rule_set_id`` is NULL:
  - **Post-15B** (column populated): existing behaviour —
    resolve `rule_set_id` against `session_rule_sets`.
  - **Pre-15B** (column NULL): consult
    ``_audit_log_rule_set_name``; stamp the resolved name on
    every instrument's `rule_set_name` cell. NULL on every
    instrument when the audit-log fallback returns ``None``
    (matching today's empty-cell behaviour for sessions
    without a rule-based generate).
- Memoise the lookup once per `serialize_session_config`
  call so a multi-instrument export hits the audit table only
  once.

**Tests.**

- Rule-based session that used a seeded RuleSet: every
  instrument's `rule_set_name` cell is stamped with the seed's
  name (e.g. `"Full Matrix"`). Round-trip a Settings CSV from
  such a session through the import side (when 12A-2 lands)
  and assert the destination's instruments resolve to the
  matching seed materialised by `materialise_seed_rule_sets`.
- Rule-based session that used a Personal RuleSet: every
  instrument's `rule_set_name` cell is empty (PR 1a
  intentionally doesn't capture Personal RuleSets — see Scope
  simplification above).
- Manual session: `rule_set_name` cells are empty (no
  `assignments.generated` audit row with a `rule_set_id`).
- Sessions with no `assignments.generated` audit row at all
  (operator never ran Generate): `rule_set_name` cells are
  empty.
- Multi-instrument session: every instrument shares the same
  resolved `rule_set_name` value (today's session-wide
  generate stamps every instrument identically). Asserts the
  helper is called once per export.
- Post-15B forward compatibility: when an instrument has
  `rule_set_id` populated, that takes precedence over the
  audit-log fallback. (Hand-construct the precondition since
  15B's UI hasn't shipped — directly write `rule_set_id` on
  the model and assert the per-instrument resolution wins.)

**Audit / EVENT_SCHEMAS.** No new audit events. PR 1a is a
pure read-side change.

### PR 2 — Reviewers + reviewees extract

- `app/services/extracts/reviewers_extract.py` +
  `reviewees_extract.py`.
- Two new routes (`/export/reviewers.csv`,
  `/export/reviewees.csv`).
- Two new audit events registered in `EVENT_SCHEMAS`.
- Card wire-up: flip both rows live; update filenames to the
  new `{code}_{kind}.csv` convention.
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
  sessions; on rule-based sessions render the row disabled
  with the explanatory note instead.
- Tests:
  - Golden-fixture CSV.
  - Round-trip: extract from session A → upload to session B
    (with reviewers / reviewees pre-populated to match) →
    assignments match.
  - Multi-instrument session: N assignments × M instruments
    ⇒ N×M rows.
  - Rule-based session: route returns 404; card row renders
    disabled with the rule-based note (assert by inspecting
    the `ExtractDataRow` returned by
    `build_extract_data_context`).

## Out of scope

Each item below is a self-contained follow-on; nothing in
12A-1 forecloses it.

- **Configuration import.** The settings CSV PR 1 ships is
  designed to round-trip — a future import-side segment can
  consume the exact shape this PR produces. The
  `field_key`-based upsert key on response fields, the
  `data_type` column as a parsing rule, and the position-based
  `rule_set_id` reference all exist for that future round-trip.
- **Responses extract.** The largest extract by row count, the
  one that needs streaming under production load, and the only
  one with no import counterpart. Defer until the streaming
  shape is sized against production data.
- **Zip bundle (`/export.zip`).** Without the responses extract
  the bundle would be incomplete; ship them together when
  responses lands.
- **Operator-library RuleSet portability** — workspace-scoped
  import / export of `operator_rule_sets` rows, anchored on
  the Rule Builder card. Orthogonal to Session Home's Extract
  Data card; gated on the Rule Builder segment shipping.
  RuleSets travel as JSON (recursive rule trees don't flatten
  to a wide CSV cleanly), so the file format is different from
  the four CSVs this segment produces. **This is also the
  natural home for closing the pre-15B rule-based-mode round-
  trip gap** (see "Round-trip readiness" — synthesising a
  per-instrument `rule_set_name` cell from the audit log + a
  JSON sidecar of the workspace-tier RuleSet).
- **Operator-library RTD portability** — same shape as
  operator-library RuleSet portability; lives on the operator
  Settings or RTD library surface, not on Session Home.
- **Cross-deployment / cross-version round-trip.** Today's
  contract assumes same schema version on both ends. A future
  `# version: 1` comment line at the top of each CSV is the
  natural extension when cross-version becomes a concern.
- **Forensic audit export.** The audit log + email outbox +
  invitation send timestamps + reviewer responses snapshot. A
  separate segment's job; complementary to this one (this one
  captures the inputs; that one captures what happened to
  them).

## Doc impact

- `docs/status.md` gains one timeline entry per PR.
- `guide/todo_master.md` adds Segment 12A-1 under **Upcoming**
  before PR 1 ships; moves to **Done** once PR 3 lands.
- `spec/architecture.md` — one-liner under "Data import /
  export" pointing at the four CSV shapes; verify on PR 1
  review.
- No spec doc for the CSV shapes themselves — this guide
  doubles as the spec until the format proves stable across
  two or three consumers; promote then.

## Test impact

- New unit tests:
  - `tests/unit/test_session_config_io.py` (round-trip per row
    class, section ordering, inert-but-included defaults
    including empty `session_rule_sets` and empty
    `session_field_labels`).
  - `tests/unit/test_reviewers_extract.py`,
    `tests/unit/test_reviewees_extract.py`,
    `tests/unit/test_assignments_extract.py`.
- New integration tests:
  - `tests/integration/test_extracts_routes.py` (auth, audit
    events, manual-only gate on assignments, no lifecycle
    gate on any of the four).
- Golden fixtures under `tests/fixtures/extracts/`:
  `settings.csv`, `reviewers.csv`, `reviewees.csv`,
  `assignments.csv`. Future contract changes have to
  deliberately update each fixture.
- Round-trip tests for the per-entity extracts: extract from
  session A → re-upload to session B → assert state matches.
  These pin the contract that the extracts feed the existing
  importers without conversion.
