# Segment 12A-2 — Session settings import

> **Superseded 2026-05-10 — absorbed into 12A-3** (see
> `guide/segment_12A-3_export_import_updates.md`). Under
> the locked sequence 13D-1 → 12C → 15D → 12A-3, the
> Settings importer ships as 12A-3 PR 1 alongside the
> Relationships per-entity export + import. This 12A-2
> plan is **kept as historical reference** for the
> contract / inclusion model / fallback rules / wipe-and-
> replace idempotency model — those carry over verbatim
> to 12A-3 PR 1's implementation. Read 12A-2 for the
> contract; read 12A-3 for the PR-by-PR delivery.

The import counterpart to **Segment 12A-1** (export, fully
shipped 2026-05-09 across 5 PRs: settings (#713), seeded-RuleSet
audit fallback (#716), rosters (#717), manual assignments
(#718), responses (#721) — see
`guide/archive/segment_12A-1_export.md`). Consumes the 3-column
`field,value,data_type` Settings CSV the export half produces
and rehydrates a fresh-named session into the same shape, so an
operator can hand a CSV to a colleague (or commit it to a repo
as a workflow template) and have the recipient reconstruct the
source-session configuration without retyping.

> **Naming.** This segment was previously bundled with the
> export half as "Segment 12A — Session settings import +
> export"; that umbrella has been split into 12A-1 (export, now
> shipped) and 12A-2 (import — this doc). The two halves share
> a CSV format but are independently shippable, with the export
> half useful in isolation as a backup / audit / template
> capture. Renamed 2026-05-09.

## Goal

A round-trippable CSV that captures the user-inputted
**configuration** of a review session — everything an operator
typed into Setup. Export gives operators a sharable backup /
template (12A-1, shipped); import rehydrates a fresh session
from that template (this segment). Configuration only — no
people lists, no responses.

The two import flows:

1. **Create New Session page** — a Settings CSV attached to the
   Quick Setup card alongside reviewers / reviewees / assignments
   uploads creates a fully-configured session in one click.
2. **Session Home Quick Setup card** — the existing-session
   "fill in the details" path; the operator unlocks Quick Setup
   on a draft / validated session and uploads any combination
   of the four slot files to refresh data.

Both flows share the same wipe-and-replace importer; the only
difference is which fallback rule applies to the operator-typed
session metadata fields (see "Import flows" below).

## Inclusion model — what the importer consumes

12A-1's settings CSV is a **snapshot of operator typing** — the
things the operator authored that they would otherwise have to
retype on the new session. The importer's job is to reverse the
serialiser and write each row back to its corresponding column
or table.

Inclusion test (paraphrased from the export plan): *if the
operator were setting up the new session from scratch, would
they have to retype this?*

- **Yes** → in the CSV; the importer writes it.
- **No (machine-derived from operator typing)** → not in the
  CSV; the importer doesn't recreate it. The new session
  re-derives via Validate / Activate / Generate.
- **No (system-emitted record / per-instance state /
  per-operator credential)** → not in the CSV.

**Snapshot the inputs, never the outputs.** Anything a machine
step derives — assignment rows from a RuleSet + roster,
validation reports, lifecycle state from Activate / Pause /
Close — is omitted from the export. The importer therefore
doesn't write those columns either; the operator re-runs the
corresponding step on the new session.

### Concretely, the importer rehydrates:

- **Session metadata the operator typed** — `name`, `code`,
  `description`, `deadline`, `help_contact`. The Settings CSV
  is a **fallback** for these fields, never an override: the
  importer applies a snapshot value only when nothing more
  authoritative is present (operator-typed value on Create New
  Session, or existing value on a session being filled in).
  See "Import flows" below for the two flows and how each
  resolves authority. `code` carries an additional rule: when
  the importer is using the snapshot's `code` (no operator-
  typed override and no existing destination code, on the
  Create New Session flow), it derives a fresh unique code by
  suffix — `{seed}_uploaded01`, `{seed}_uploaded02`, ... until
  the result clears the global uniqueness check.
- **Email-template overrides** — the 12 string keys + the
  `responses_received_enabled` boolean from
  `sessions.email_template_overrides`. Empty value cell ⇒ "use
  the default" (matches the live resolver semantics in
  `app.services.email_templates`).
- **Operator-defined response type definitions** — the
  `is_seeded=False` rows on `response_type_definitions`.
  Seeded RTDs are **not** in the CSV and the importer does
  not recreate them; they regenerate from
  `SEED_RESPONSE_TYPE_DEFINITIONS` on session create on the
  destination.
- **Instruments + their display fields + response fields** —
  the full question schema.
- **Per-session RuleSets** — the non-seeded rows on
  `session_rule_sets`. Seeded RuleSets are not in the CSV and
  regenerate from `SEEDS` (`app/services/rules/seeds.py`) via
  `materialise_seed_rule_sets` on the destination side
  (Segment 15C Slice 1).
- **Per-instrument RuleSet selection** —
  `instruments[N].rule_set_name` resolves on the destination
  to either a seeded RuleSet (auto-materialised on session
  create) or a non-seeded `session_rule_sets[N]` row defined
  earlier in the same CSV. The importer fails loudly if a
  referenced name doesn't resolve. **Pre-15B / pre-15C apply
  semantics:** mirroring 12A-1 PR 1a's seeded-only export
  fallback, today's importer **validates** that the name
  resolves but does **not** write `Instrument.rule_set_id` —
  the column is universally NULL pre-15B, and Personal-library
  RuleSets are out of scope for both halves of 12A. Once 15B
  + 15C ship, the importer flips to writing the FK; the apply
  rule changes in lockstep with the export-side fallback being
  retired.
- **Per-session field-label overrides** — the rows on
  `session_field_labels` (Segment 15A target — inert today;
  exporter emits no rows; importer is a no-op until the table
  is populated).

### The importer skips:

- `session.assignment_mode` — auto-set by the next assignment
  generation path. Snapshot consults it once at *export* time
  to decide whether to bundle the manual assignments CSV vs.
  rely on the RuleSet rehydration; not written on import.
- `session.status` — every imported session lands in `draft`;
  the operator re-runs Validate / Activate.
- **Rule-based assignment rows** — derived. The importer
  rehydrates the RuleSet; the operator runs Generate.
- **Validation report state** — derived. Re-run Validate.
- **Invitations + tokens** — derived from the roster + the
  Generate Invitations action.
- **Email outbox rows** — derived from send actions.
- **Reviewer responses** — reviewer-determined work; not
  operator-authored.
- **Audit events** — system-emitted.
- **Operator SMTP credentials** — per-operator (each operator
  configures their own under Operator Settings).
- **Browser-local UI state** — cookies, localStorage, URL
  params. Cosmetic per-browser preferences.

## Import flows (in scope this segment)

The Settings CSV import lives on the **existing Quick Setup
card** — no new entry point. Quick Setup already runs in two
contexts; both pick up the new Settings slot (slot 4) the same
way once PR 2 of this segment graduates it to live. Slot 4
accepts a **single Settings CSV** (the 3-column config shape
12A-1 ships) — not a zip, not the per-entity files. Roster
CSVs go in slots 1 and 2; assignments CSVs go in slot 3 (or
the operator picks a RuleSet from slot 3's dropdown). The slot
stays single-purpose, matching the rest of the card.

The same **fallback rule** applies in both contexts:

> Apply the snapshot's `session.name` / `session.code` *only*
> when nothing more authoritative is present (operator-typed
> values on Create New Session, or existing values on a
> session being filled in). Same logic extends to
> `session.description`, `session.deadline`, and
> `session.help_contact`.

1. **Create New Session page (Quick Setup attached to the
   form).** Operator types name / code (some / all / none) +
   the optional metadata fields, and attaches files to Quick
   Setup slots 1-4. The single "Create session" button creates
   the session and dispatches each slot's payload through the
   existing per-slot pipeline. Operator-typed form fields
   *win*; the Settings CSV's `session.*` fields fill in
   anything the operator left blank. `code` carries the
   suffix-derivation rule (`{seed}_uploaded01`,
   `{seed}_uploaded02`, ...) when the snapshot's `code` is the
   source.
   - Slots 1-3 (reviewers / reviewees / assignments-or-rule)
     are already wired (PR #635).
   - Slot 4 (Settings) graduates to live in PR 2 of this
     segment.
2. **Session Home Quick Setup card (existing-session fill).**
   Operator hits an existing session's Home page, unlocks
   Quick Setup, and uses any combination of slots 1-4 to
   refresh data. The destination session's existing metadata
   *always* wins; the Settings CSV's `session.*` fields are
   read-and-ignored. The wipe-and-replace shape (instruments,
   RTDs, display fields, response fields, email-template
   overrides, per-session RuleSets, field labels) still
   applies to everything else the Settings CSV carries.
   Lifecycle gate stays `status in {"draft", "validated"}` per
   the original plan; targets `POST /operator/sessions/{id}/import-config`.

For both flows the rest of the snapshot's content (instruments,
RTDs, display fields, response fields, email-template overrides,
per-session RuleSets, field labels) is **wipe-and-replace** —
those are the "shape" the Settings CSV owns end-to-end. The
fallback rule applies only to the operator-typeable session
metadata, where there's a meaningful "did the operator type
this on the destination?" question to answer.

### Future features (out of scope this segment)

Both items below build on the in-scope flows and can land later
without re-architecting them:

- **Multi-file / zip-aware Settings slot.** Extend slot 4 to
  also accept (a) a single zip carrying the full per-kind
  bundle (config + roster + assignments) or (b) a multi-file
  selection of those same loose files, with filename-based
  dispatch. Useful for the "operator hands a colleague a
  single file" workflow. Today's slot stays single-purpose
  (Settings CSV only); the operator who has a full bundle
  uses slots 1-4 individually.
- **Sessions lobby "Create from snapshot" button.** A
  shortcut that bypasses the Create New Session form: the
  operator drops a snapshot zip and the server creates a
  fresh session whose name / code / metadata come from the
  snapshot's values (with `code` suffix-derivation on
  collision). Folds in cleanly once the multi-file slot
  exists; same dispatch chain.

## Triggered actions on import

The Settings slot doesn't just write fields — it plugs into
the **existing Quick Setup chain** so the operator doesn't
have to re-do the post-load clicks. Quick Setup's
`quick_setup_submit_all` already dispatches reviewers →
reviewees → assignments in order; PR 2 plugs slot 4
(Settings) into the same chain in front:

1. **Apply session-level config** from slot 4 — write
   `name` / `description` / `deadline` / `help_contact` per
   the fallback rule, and replace `email_template_overrides`
   from the reconstructed dict.
2. **Apply RTDs + instruments + display fields + response
   fields + per-session RuleSets + field labels** from
   slot 4's config CSV (wipe-and-replace).
3. **Save reviewers** from slot 1 (existing behaviour).
4. **Save reviewees** from slot 2 (existing behaviour).
5. **Materialise assignments** from slot 3 (existing
   behaviour — manual CSV save *or* rule-based engine
   evaluation against the just-saved roster).

The chain **stops at assignments**. Validate, Activate,
Generate Invitations, and Send are explicitly *not* fired on
import — they sit on the lifecycle progression and require
operator decisions the import can't authoritatively make (the
new roster's validation outcome may differ from the source
session's; the deadline may be in the past; the email-template
tweaks may need a second pass before the operator is ready to
send). Each of those is one operator click away on Session
Home; the import shouldn't anticipate them.

Per-step failures surface the same way slot failures do today:
the importer 303s back to Session Home with a slot-scoped
`?quick_setup_error=…&quick_setup_reason=…` flag and a
`.banner.banner-error` rendered inside the offending slot.
Upstream slots that already succeeded are *not* rolled back —
the operator picks up where the failure happened, mirroring
Quick Setup's per-slot dispatch ordering.

## Settings CSV format reference

The importer reads the 3-column shape 12A-1 produces. Keeping
the format reference in this doc means the import side has a
single source of truth for cell parsing without bouncing back
to the export plan; the format itself is shared.

### Three columns

```
field,value,data_type
```

- `field` — machine-readable dotted / bracketed key path (see
  "Key conventions" below). Stable across exports of the same
  session — round-tripping is exact.
- `value` — string representation of the value. Empty cell ⇒
  `None` / unset / cleared on import.
- `data_type` — the value's parsing rule. One of:
  - `string`
  - `integer`
  - `decimal`
  - `boolean` — accepts `true`/`false` (case-insensitive) on
    import; emits lowercase on export
  - `datetime` — ISO-8601 with timezone offset
    (`2026-05-15T17:00:00+00:00`). Empty cell ⇒ `None`
  - `enum` — finite operator-set value (e.g.
    `combinator = "ALL_OF" | "ANY_OF" | "PIPELINE"`); validated
    server-side against the enum at import time
  - `csv_list` — a comma-separated literal stored as a single
    Text column (today: `ResponseTypeDefinition.list_csv`)
  - `json` — JSON-encoded structured value; used for
    `instruments[N].sort_display_fields` and
    `session_rule_sets[N].rules_json`. The CSV `value` cell
    carries the JSON string with the standard CSV
    double-quote escapes.

The `data_type` column is **descriptive of the cell, not of
any underlying RTD's `data_type`**. Don't conflate the two: an
RTD whose `data_type=Integer` exports as `data_type=enum` for
that cell because the value `"Integer"` is one of a fixed set.

### Key conventions

Hierarchical keys, position-indexed (1-based, matching how the
reviewer surface and operator UI count pages):

- **Session-level** — flat `session.<column>`. Per the
  inclusion model, `session.assignment_mode` and
  `session.status` are excluded — assignment_mode is auto-set
  by the next Generate run, and status always lands back in
  `draft`. `session.name` and `session.code` are **fallback
  values**, applied only when nothing more authoritative is
  present (operator-typed values on Create New Session, or
  existing values on a session being filled in); see "Import
  flows" above. The same fallback semantics extend to
  `session.description` / `session.deadline` /
  `session.help_contact`.
  - `session.name` (string)
  - `session.code` (string; **fallback / seed** — see Import
    flows)
  - `session.description` (string)
  - `session.deadline` (datetime)
  - `session.help_contact` (string)
- **Email-template overrides** — flat keys mirroring
  `app.services.email_templates.OVERRIDE_KEYS` plus the
  `responses_received_enabled` toggle. Each is exported even
  when the operator left it at default; an empty `value` cell
  means "use the default" on import (matches the live
  resolver: missing / empty override falls through to
  `DEFAULT_*`). The export collapses three on-disk states
  (`None`, empty string, key-absent in
  `email_template_overrides`) into the same empty cell — the
  importer treats them all as "key absent in dict" on apply.
  Acceptable lossy collapse; an operator who literally wants an
  empty subject line is not a workflow we support.
  - `email_overrides.invitation.subject` (string)
  - `email_overrides.invitation.body` (string)
  - `email_overrides.invitation.cc` (string)
  - `email_overrides.invitation.bcc` (string)
  - `email_overrides.reminder.subject` (string)
  - `email_overrides.reminder.body` (string)
  - `email_overrides.reminder.cc` (string)
  - `email_overrides.reminder.bcc` (string)
  - `email_overrides.responses_received.subject` (string)
  - `email_overrides.responses_received.body` (string)
  - `email_overrides.responses_received.cc` (string)
  - `email_overrides.responses_received.bcc` (string)
  - `email_overrides.responses_received.enabled` (boolean;
    default `true` when absent)
- **Operator-defined RTDs** — keyed by `response_type` (the
  operator-typed name; unique within a session via
  `uq_rtd_session_name`):
  - `rtds[<response_type>].data_type` (enum: `int` / `decimal`
    / `short_text` / `long_text` / `list`)
  - `rtds[<response_type>].min` (decimal)
  - `rtds[<response_type>].max` (decimal)
  - `rtds[<response_type>].step` (decimal)
  - `rtds[<response_type>].list_csv` (csv_list)

  Seeded RTDs (`is_seeded=true`) are **not in the CSV** —
  they're regenerated from `SEED_RESPONSE_TYPE_DEFINITIONS`
  on session create on the destination. If a future operator-
  edit-on-seeded path lands, fold it in as
  `rtds[<name>].overrides.*`.
- **Per-instrument** — keyed by 1-based position
  (`(Instrument.order, Instrument.id)` order on export):
  - `instruments[N].name` (string, required)
  - `instruments[N].short_label` (string)
  - `instruments[N].description` (string)
  - `instruments[N].order` (integer; informational on import —
    the importer overwrites `Instrument.order` with N, the
    1-based CSV position. The cell is exported for human
    readability and self-describing-format reasons; a
    hand-edited CSV that disagrees with N is silently
    normalised to N)
  - `instruments[N].accepting_responses` (boolean)
  - `instruments[N].responses_visible_when_closed` (boolean)
  - `instruments[N].sort_display_fields` (json; default `[]`
    — Segment 13B target)
  - `instruments[N].group_kind` (enum: `tag_1` / `tag_2` /
    `tag_3` or empty — Segment 13C target)
  - `instruments[N].rule_set_name` (string — name reference,
    resolves against either a seeded RuleSet auto-materialised
    on session create or a `session_rule_sets[N]` block in
    the same CSV)
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
  - `instruments[N].response_fields[M].field_key` (string,
    required)
  - `instruments[N].response_fields[M].label` (string,
    required)
  - `instruments[N].response_fields[M].response_type` (string
    — references either a seeded RTD name or an
    operator-defined `rtds[<name>]` row exported earlier in
    the same file)
  - `instruments[N].response_fields[M].required` (boolean)
  - `instruments[N].response_fields[M].help_text` (string)
  - `instruments[N].response_fields[M].help_text_visible`
    (boolean)
- **Per-session RuleSets** — keyed by 1-based position
  (`session_rule_sets.id` order, restricted to non-seeded
  rows). Name-uniqueness within a session is enforced by
  `uq_session_rule_set_session_name` (Segment 13A-2), so
  `instruments[N].rule_set_name` resolves unambiguously.
  - `session_rule_sets[N].name` (string, required)
  - `session_rule_sets[N].description` (string)
  - `session_rule_sets[N].combinator` (enum: `ALL_OF` /
    `ANY_OF` / `PIPELINE`)
  - `session_rule_sets[N].exclude_self_reviews` (boolean)
  - `session_rule_sets[N].seed` (integer)
  - `session_rule_sets[N].rules_json` (json — full rule tree;
    schema validated against `RuleSetSchema` in
    `app/schemas/rules.py`). The export emits `[]` for a
    RuleSet with no rules authored yet (see
    `_session_rule_set_rows` in
    `app/services/session_config_io.py`); the importer accepts
    `[]` as the no-rules default and writes it through to
    `SessionRuleSet.rules_json` unchanged.
- **Per-session field-label overrides** — keyed by
  `(source_type, source_field)` (Segment 15A target — inert
  today):
  - `field_labels.<source_type>.<source_field>` (string)

`validation` JSON is **not** in the CSV — the importer derives
it from the RTD via `validation_block_for_rtd`. Keeping it
out removes a redundant source of truth.

`field_key` is the stable machine identifier for a response
field. The importer treats `(instrument_position, field_key)`
as the upsert key within an instrument's response-field list,
so an operator hand-editing the CSV can rename labels without
losing field identity.

### Lifecycle gating on import

Import is gated to draft / validated sessions:
`status in {"draft", "validated"}`. Locked / activated / paused
sessions reject the upload with 409 and a banner. The importer
wipes-and-replaces (see "Idempotency model"), which would
silently destroy reviewer-typed responses on an active session
— the gate makes that impossible.

### Idempotency model

The importer is **wipe-and-replace** for everything it owns:

1. Validate every row (parse `data_type`, check enum
   membership, confirm RTD references resolve, confirm
   `rule_set_name` references resolve, confirm name uniqueness
   within `session_rule_sets[N]` rows). Abort the whole
   transaction if any row is malformed; no partial application.
2. Update session-level fields in place per the **fallback
   rule**: apply each `session.*` row only when nothing more
   authoritative is present (operator-typed value on Create
   New Session; existing value on a session being filled in).
   See "Import flows" for the two flows. `session.code`
   carries the additional suffix-derivation rule when the
   snapshot value is the source. `session.assignment_mode` and
   `session.status` are *never* written even if a stray row
   carries them — the export excludes them, and the importer
   ignores them defensively.
3. Replace `sessions.email_template_overrides` JSON in place
   with the dict reconstructed from the `email_overrides.*`
   rows. Empty value cells map to "key absent" in the dict
   (matches the resolver's "fall through to `DEFAULT_*`"
   semantics). The `responses_received_enabled` boolean is
   written into the same dict under the canonical
   `app.services.email_templates.RESPONSES_RECEIVED_ENABLED_KEY`.
4. For RTDs: upsert operator-defined rows by `response_type`;
   delete existing operator-defined rows not present in the
   CSV. Seeded rows are untouched.
5. For instruments: delete every existing instrument on the
   session then re-create from the CSV. Display fields and
   response fields cascade with the instrument they belong to
   (FK `ON DELETE CASCADE`).
6. For per-session RuleSets: upsert non-seeded rows by `name`;
   delete existing non-seeded rows not present in the CSV.
   Seeded rows are untouched. Resolve every
   `instruments[N].rule_set_name` to either a seeded RuleSet
   (auto-materialised by `materialise_seed_rule_sets` on
   session create) or a row freshly upserted in this same
   pass.
7. For field labels: upsert by `(source_type, source_field)`;
   delete existing rows not present in the CSV.
8. Audit `session.settings_imported` with `{"counts": {...}}`
   detail. Naming mirrors the 12A-1 export-side events
   (`session.{settings,reviewers,reviewees,assignments,responses}_extracted`)
   so the verb pair reads cleanly in the audit log.

The wipe-and-replace cost is acceptable because:
- The lifecycle gate keeps Response rows (which have FKs to
  RFs) out of the picture; on a draft / validated session
  there are no responses to cascade-delete.
- Reviewers / reviewees / assignments don't FK to instruments
  (assignments do via `instrument_id`, but the lifecycle gate
  keeps this clean — Segment 5/7 refresh assignments on the
  next mutation anyway).
- If we hit a session with assignments referencing
  about-to-be-deleted instruments, the importer 409s with a
  "this session has assignments; delete them first" message
  rather than silently cascading.

If the operator wants merge semantics later (e.g. "import only
the new RTDs without touching the existing instruments"),
that's a follow-on `?mode=merge` query parameter; the
wipe-and-replace path stays the default because it's the only
one with a clean "the CSV is the source of truth" mental
model.

## Status

Planning. Sized as **2 PRs** in dependency order:

1. **PR 1 — Importer service + route.** Narrow contract;
   single source of truth on the apply path. Operator can hit
   the route directly with a multipart upload but no Quick
   Setup-side affordance until PR 2.
2. **PR 2 — Quick Setup slot 4 graduation.** Flips slot 4
   from inert (Segment 11H scaffold state) to a live form
   pointed at PR 1's route, in both Quick Setup contexts
   (Create New Session + Session Home).

PR 2 is gated on PR 1 (it only wires up what PR 1 ships).

### PR 1 — Importer service + route

**Goal.** Upload the CSV 12A-1 produced and rehydrate a
fresh-named session into the same shape.

- `apply_session_config(db, session, rows) -> ApplyResult` in
  `app/services/session_config_io.py` (extending the module
  12A-1 PR 1 introduced for the export-side serialiser).
  Returns `ApplyResult(counts, errors)` so the route can
  render a validation summary on failure.
- Two-phase implementation:
  1. **Parse + validate** — convert every cell per its
     `data_type` column into a typed value; build a structured
     plan (session-level kvs, RTD upserts, instrument trees,
     RuleSet upserts, field-label upserts). Collect every
     error before reporting; one bad row doesn't mask the
     next.
  2. **Apply** — inside a single DB transaction, write the
     plan in the order specified by "Idempotency model"
     above. If any apply step fails (FK violation, RTD
     reference unknown, RuleSet name reference unknown), roll
     back and surface the error.
- New route `POST /operator/sessions/{id}/import-config`:
  - Lifecycle gate (`status in {"draft", "validated"}`) via
    the existing `_require_editable` helper.
  - Multipart `file` upload; reject empty / non-CSV up front.
  - On success: 303 → Session Home with a
    `?config_imported=ok` flash.
  - On validation error: 303 → Session Home with
    `?quick_setup_error=settings&quick_setup_reason=parse`
    so the GET render places a `.banner.banner-error` inside
    slot 4 — the same scoped-error pattern Segment 11J
    established for slots 1-3.
  - On `ready` / `closed`: 303 with
    `quick_setup_reason=lifecycle` and a banner naming the
    next move (Pause / revert), matching the lock-toggle
    pattern.
- Audit `session.settings_imported` registered in
  `EVENT_SCHEMAS` per the strict-mode test gate, with detail
  shape `_IDENTITY | {"counts"}` to match the
  `session.{kind}_extracted` family. Counts per import are
  real numbers, e.g. `{"session": 1, "rtds": 3,
  "instruments": 2, "display_fields": 6, "response_fields": 8,
  "session_rule_sets": 1, "field_labels": 0}`.
- Tests:
  - **Two round-trip contracts**, both pinned in
    `tests/integration/test_extracts_round_trip.py`:
    1. **Byte-stable re-export from the same session.**
       `serialize_session_config(A)` → file →
       `apply_session_config(A)` →
       `serialize_session_config(A)` is byte-identical.
    2. **State-equivalent extract-import-extract across two
       sessions.** Take session A's CSV, apply to a fresh
       session B (different name / code), re-export B,
       and assert the row stream — modulo the `session.name`
       + `session.code` fallback rule — equals A's. Pins the
       contract that the export and import halves stay in
       lockstep on the CSV format.
  - Malformed `data_type` column rejected per row (every value
    of the cell-data-type set: `string` / `integer` /
    `decimal` / `boolean` / `datetime` / `enum` / `csv_list` /
    `json`).
  - Unknown RTD reference in
    `response_fields[].response_type` rejected with a "no
    such RTD on this session: X" error pointing at the
    offending row.
  - Unknown RuleSet name reference in
    `instruments[N].rule_set_name` rejected with a "no such
    RuleSet on this session: X" error. Pre-15B: validate-only,
    no `Instrument.rule_set_id` write — confirm the apply step
    leaves the column NULL on success and surfaces the lookup
    error on miss.
  - `rules_json` accepts `[]` (empty rule tree) and round-trips
    without diffing.
  - Lifecycle gate (`status="ready"` ⇒ 409).
  - Conflict path: session has assignments referencing a
    not-in-CSV instrument ⇒ 409, no rows written.

### PR 2 — Quick Setup slot 4 graduation

**Goal.** Flip Quick Setup's configuration-import slot
(slot 4 — inert from Segment 11H, untouched by Segment 11J)
to its live form. After this PR, the operator uses the slot
the same way they use slots 1-3.

- One adapter change in
  `views.build_quick_setup_context(session)`: flip slot 4's
  `is_wired=True` and supply
  `wire_url="/operator/sessions/{id}/import-config"` (the
  route PR 1 shipped). The Quick Setup card template
  (`app/web/templates/operator/partials/_quick_setup_card.html`)
  already routes wired slots through the
  `{% elif slot.is_wired %}` branch — no template change
  needed; flipping the flag swaps slot 4 from the inert
  `<input type="file" disabled>` shape into a live file
  input wired to the submit-all form via the `form="…"`
  attribute, identical to slots 1-2. The
  `{# Inert slot (slot 4 — Settings, until Segment 12A
  PR 6 wires it) #}` comment in the template's `{% else %}`
  branch is stale post-rename and gets refreshed in this PR
  to point at 12A-2 PR 2 (or removed once slot 4 graduates,
  since the inert branch will only serve future not-yet-wired
  slots).
- Same inline confirmation banner pattern Segment 11J
  established (cookie-driven lock state via
  `qsu_{session_id}`, banner-warning above the submit form on
  populated session, scoped `.banner.banner-error` via
  `?quick_setup_error=settings&quick_setup_reason={parse|lifecycle|needs_confirm}`
  on rejection, mandatory `.btn.alert` Cancel returning to a
  clean URL with the slot fragment).
- Tests:
  - Slot 4 renders as a live form on draft / validated
    sessions; lock toggle works as on slots 1-3.
  - Upload via the slot 303s through PR 1's import path;
    success flash + error banners surface in the right slot.
  - Lock states gate per the existing slot rules.
  - The Create New Session page picks up slot 4 the same way
    once flipped (the Quick Setup card is shared across the
    two contexts).

## Implementation pointers

- **CSV parsing.** Use `csv.DictReader` (stdlib). Don't
  introduce a new dependency.
- **Datetime parsing.** Use `datetime.fromisoformat()`; it
  round-trips ISO-8601 with timezone offsets faithfully on
  Python 3.12.
- **Boolean parsing.** Lowercase normalize, accept
  `{"true", "false"}` only; reject anything else with an
  explicit error rather than silently treating as falsy.
- **JSON parsing.** Use `json.loads`; the `data_type=json`
  cell carries an embedded JSON string (the `value` cell
  carries the canonical `sort_keys=True` shape the export
  emits).
- **Empty cell semantics.** Empty `value` cell ⇒ `None` for
  nullable columns; reject for `nullable=False` columns with
  a per-row error.
- **RTD reference resolution.** When applying response-field
  rows, resolve `response_type` against:
  1. Operator-defined RTDs already upserted in this same
     import (already in the DB after the RTD pass).
  2. Seeded RTDs from `SEED_RESPONSE_TYPE_DEFINITIONS`.
  Both come from the session's `response_type_definitions`
  collection. Fail-loud if neither matches.
- **RuleSet name reference resolution.** Mirror of RTD
  resolution: resolve `instruments[N].rule_set_name` against
  either an upserted non-seeded `session_rule_sets` row from
  this same import, or a seeded `session_rule_sets` row
  materialised on session create. Fail-loud if neither
  matches.
- **Field-key uniqueness.** Within an instrument, `field_key`
  must be unique across response fields. The importer
  enforces this during validate; a duplicate `field_key` in
  two `instruments[N].response_fields[M]` rows for the same N
  is a parse error.
- **Display-field source enum.** `source_type` is one of a
  small fixed set (`reviewee`, `pair_context`). Validate
  against the same enum the operator UI uses (the
  seven-source enumeration spec'd in `spec/architecture.md`
  and seeded via `instruments_service.display_field_value`).
- **Setup-mutation invalidation.** The importer mutates
  session + instruments + RTDs + display / response fields +
  session RuleSets + field labels. Each underlying service
  helper (`update_session`, `create_instrument`, etc.)
  already calls `lifecycle.invalidate_if_validated()`;
  calling them in turn from `apply_session_config` keeps the
  validated → draft flip free. The importer doesn't bypass
  them.

## Out of scope (cross-references)

- **Reviewer / reviewee / assignment import.** Existing
  per-table upload flows on the Manage pages and on Quick
  Setup (Segment 11J) stay the source of truth. 12A-1's
  per-entity CSV extracts already round-trip with those
  importers without conversion.
- **Settings export + per-entity CSV exports** (reviewers /
  reviewees / manual assignments). All shipped as Segment
  12A-1 (PRs #713, #716, #717, #718) — see
  `guide/archive/segment_12A-1_export.md`.
- **Responses extract.** Shipped as Segment 12A-1 PR 4 (#721,
  2026-05-09). Independent downstream-analysis use case — not
  part of the round-trip / porting contract this segment
  rehydrates.
- **Zip bundle.** Deferred follow-on of the 12A-1 export track
  (single `/export.zip` covering all CSVs); orthogonal to the
  import side, which always reads a single Settings CSV per
  upload.
- **Operator-library RTD / RuleSet portability** —
  workspace-scoped (per-operator across sessions), anchored
  on Operator Settings + Rule Builder. Orthogonal to Session
  Home's Settings CSV; lives on a separate import / export
  surface and travels as JSON (recursive rule trees don't
  flatten to a wide CSV cleanly). When that lands, fold its
  reference into Operator Settings docs, not here.
- **Operator-editable email templates** — Segment 11E
  shipped; the 12 override keys + `responses_received_enabled`
  are part of the CSV format.
- **Audit retention / audit-log export** — Segment 12B. This
  segment's importer writes a single
  `session.settings_imported` audit event; per-row diffs are
  not emitted (would balloon the event log).
- **Audit-event `detail` schema convention** — Segment 11K
  (shipped). The import audit event uses the canonical
  envelope shape.
- **Cross-deployment / cross-version** — assumes same app
  version on both ends. A future schema-versioned wrapper
  (`# version: 1` comment line at the top of the CSV) is the
  natural extension but not in scope here.

## Test impact

- Extends `tests/unit/test_session_config_io.py` with apply-
  side cases per row class — bidirectional symmetry with the
  serialiser tests already shipped in 12A-1 PR 1.
- New `tests/integration/test_extracts_settings_import_routes.py`
  covering auth, lifecycle gate, multipart upload, audit
  event, success / error redirect chains.
- One golden fixture under `tests/fixtures/extracts/` —
  `settings.csv` for a fully-populated session — already
  shipped by 12A-1 PR 1 (or its follow-on PR adding the
  fixture). The round-trip test reads from this fixture, so
  contract changes have to deliberately update it.
- **Round-trip integration tests** (two contracts, both in
  `tests/integration/test_extracts_round_trip.py`):
  1. Byte-stable re-export from the same session
     (`extract → apply → extract` is identical).
  2. State-equivalent extract-import-extract across two
     sessions (`extract(A) → apply(B) → extract(B)` matches
     `extract(A)` modulo the `session.name` / `session.code`
     fallback rule).
  Together these pin the contract that the export and import
  halves stay in lockstep on the CSV format. The Responses
  CSV (12A-1 PR 4) is intentionally **not** part of the
  round-trip — it serves the independent downstream-analysis
  use case and has no import counterpart.

## Doc impact

- `docs/status.md` gains a timeline entry per PR.
- `guide/todo_master.md`:
  - Move Segment 12A-2 from **Upcoming** to **Done** under
    "Segment 12" once PR 2 lands. (The Upcoming entry +
    plan-doc pointer were retitled by the rename PR that
    accompanied this doc.)
- `guide/archive/segment_12A-1_export.md` — once 12A-2 PR 1 lands,
  collapse the "Out of scope — Configuration import"
  reference into a one-line "Companion segment 12A-2 ships
  the import side; round-trip pinned in
  `tests/integration/test_extracts_round_trip.py`" pointer.
- `spec/architecture.md` — extend the "Data import / export"
  one-liner to mention the 12A-2 import surface alongside
  12A-1's export.
- No spec doc for the CSV shape itself — this guide doubles
  as the spec until the format proves stable across two or
  three consumers; promote then.
