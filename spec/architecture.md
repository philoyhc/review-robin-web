# Architecture Notes

**Current as of 2026-08-18.** Domain entities, the three-layer
code split, and the conceptual data-model hierarchy. Per-page
surface behaviour lives in the surface specs (`spec/lifecycle.md`,
`spec/instruments.md`, `spec/assignments.md`,
`spec/participant_model.md`, `spec/session_home.md`, …); this file
stays at the architectural altitude and points to them.

Review Robin Web is organized around explicit domain entities:

- sessions
- reviewers
- reviewees
- observers
- relationships (per-pair context)
- instruments (+ their response / display fields)
- rule sets (per-instrument assignment rules)
- assignments
- responses
- invitations
- audit events
- extracts (CSV / ZIP data exports)
- retention actions (scheduled archive / delete — partially deferred)

**Participant-model context.** The domain has **four participant
roles** — operator, reviewer, reviewee, observer. The three
participant rosters (reviewers, reviewees, observers) are
per-session tables whose rows are matched to a signed-in user by
case-insensitive email; only email-identified rows confer access
(a confidential reviewee with a non-email identifier never reaches
their results surface, by construction). Both participant-facing
read surfaces are live:

- **Reviewee results** — `GET /me/sessions/{id}/results` renders a
  reviewee's own incoming results per instrument (raw / anonymized
  / summarized, per the per-instrument visibility policy) plus an
  Acknowledge gesture. Gated by `require_reviewee_in_session`
  (`app/web/deps.py`).
- **Observer collation** — observers view *collated* results across
  the session (not just their own). `observers` has a dedicated CRUD
  Setup page gated by `session.observers_enabled` and an
  `observers.cohort_rule` JSON column scoping each observer's view.
  `GET /me/sessions/{id}/collation` renders a per-instrument 3-row
  table (reviewer / reviewee aggregates + a conditional cohort-scoped
  CSV download). Gated by `require_observer_in_session`.

See `spec/participant_model.md`, `spec/visibility_policy.md`, and
`spec/audience_and_identity_model.md` for the full participant model.

## Three-layer split

The app is a server-rendered FastAPI + Jinja monolith with a strict
three-layer separation (mirrors CLAUDE.md "Architecture at a glance"):

1. **Route handlers** parse the request, resolve identity via
   dependencies, and call into services — no SQL, no business rules.
   Operator routes live in the `app/web/routes_operator/` package
   (split by feature area — `_lobby.py`, `_session_home.py`,
   `_settings.py`, the `_setup_*` slices, `_assignments.py`,
   `_operations.py`, `_instruments*.py`, `_extracts.py`,
   `_extract_data.py`, `_rehydrate.py`, `_workflow.py`,
   `_sys_admin.py`, …, with shared plumbing in `_shared.py`).
   Participant-facing routes live in `app/web/routes_reviewer/`
   under the `/me/` prefix (`_dashboard.py`, `_surface/`,
   `_summary.py`, `_results.py`, `_collation.py`, `_invite.py`).

2. **Service modules** (`app/services/*.py`) hold all business logic —
   querying, mutation, validation, lifecycle transitions, audit-event
   emission. Several are **packages split by concern**, each
   re-exporting its public surface via `__init__.py` so callers write
   the unqualified import unchanged:
   - `app/services/instruments/` — `_state.py`, `_display_fields.py`,
     `_response_fields.py`, `_band1.py`, `_band2.py`, `_pagination.py`,
     `_instrument_crud.py`, `_field_presets.py`.
   - `app/services/assignments/` — `_shared.py`, `_coverage.py`,
     `_self_review.py`, `_generate.py` (18O Track B carve).
   - `app/services/responses/` — `_core.py`, `_group_reconciliation.py`.
   - `app/services/rules/` — the pure rule engine (`engine.py`,
     `predicates.py`, `quotas.py`, `preview.py`, `fields.py`).
   Other notable services: `session_lifecycle.py`, `validation.py`,
   `visibility_policies.py`, `observers.py` / `observer_cohort.py`,
   `participant_tokens.py`, `audit.py`, the `extracts/` package, the
   `scheduled_events/` package, and `session_config_io/`.

3. **Models** (`app/db/models/`) are SQLAlchemy 2.x declarative
   classes using `Mapped[]` / `mapped_column`. **No
   `sqlalchemy.dialects.postgresql` imports here** — Postgres-specific
   column types are deferred infrastructure.

A fourth seam — **`app/web/views/`** — holds view-shape adapters that
translate domain objects into the dataclasses / row tuples templates
iterate over (`_setup.py`, `_instruments.py`, `_validate.py`,
`_reviewee_results.py`, `_observer_collation.py`, `_workflow_card.py`,
…). Services stay business-logic-only, templates stay markup-only, and
anything in between (e.g. computing a status label from instrument
state) lives here.

## Conceptual hierarchy

The shape of the data model is deliberate. From the operator's
perspective:

- **Session** is the top-level container. A session defines the
  *universe* of reviewers and reviewees. It does **not** carry a
  single session-wide matrix — assignments are generated
  **per-instrument** (see below), so a session can carry several
  distinct assignment sets at once.
- **Instruments** are the *response forms* attached to a session. A
  session has one or more instruments, each defining its own set of
  response fields and display fields **and its own assignment rule**
  (`Instrument.rule_set_id` → a `session_rule_sets` row, or NULL for
  the synthetic Full Matrix default). The schema, services, and
  audit events are fully multi-instrument-aware
  (`Instrument.session_id`, `Instrument.order`, FK delete-orphan
  cascades, `create_instrument` / `delete_instrument` services with
  `instrument.created` / `instrument.deleted` events). Every
  session is auto-created with one instrument (system handle
  `Default`, operator-editable `description`); the operator's
  `Add an instrument` and `Delete this instrument` buttons are
  wired with mutual-exclusion + single-instrument-floor gates.
  See `spec/instruments.md`.
- **Rule sets** drive assignment generation. Each instrument's
  Band 1 either materialises one `session_rule_sets` row (when any
  Link carries filter / group rules) or leaves `rule_set_id=NULL`
  and inherits the synthetic **Full Matrix** default. The rule
  engine lives in `app/services/rules/` (`engine.py`,
  `predicates.py`, `quotas.py`, `preview.py`, `fields.py`) and is
  pure — it evaluates a rule set against the reviewer × active-
  reviewee universe and returns surviving pairs. The write-side
  caller (`app/services/assignments/`) materialises those pairs into
  `Assignment` rows. The per-instrument rule engine **has shipped**
  (through Wave 5); the earlier operator-side RuleSet *library* tier
  and standalone Rule Builder page were retired in Wave 5 — every
  rule now lives on its instrument's Band 1. See `spec/assignments.md`.
- **Assignments** are `(session, reviewer, reviewee, instrument)`
  rows (`session_id` is denormalised onto the row; the logical key is
  the reviewer × reviewee × instrument triple). Each row carries
  `include` (whether the reviewer sees this reviewee on their
  per-instrument page) and `is_self_review` (the persisted self-review
  classification). Group scoping is a computed collapse over the
  boundary tags rather than a stored column. The same
  `(reviewer, reviewee)` pair may appear in zero, one, or many
  instruments within a session, depending on how generation ran
  against each instrument's rule.
- **Responses** are `(assignment, response_field)` rows: the
  reviewer's answer to one field on one instrument for one assigned
  reviewee.

### Tabular response artifacts

The reviewer surface presents one **tabular response artifact** per
instrument the reviewer is assigned on. Within a single instrument:

- **Rows** are the assigned reviewees (one per `(reviewer, reviewee,
  instrument)` assignment).
- **Columns** are a fixed reviewee identity column (name, with email
  in smaller font beneath) followed by operator-configured **display
  fields** (`InstrumentDisplayField` rows — reviewee tags, pair
  contexts) and the instrument's **response fields**
  (`InstrumentResponseField` rows — the inputs the reviewer fills
  in).
- **Per-field help text** above the table explains each response
  field in plain prose; visibility is per-field via
  `InstrumentResponseField.help_text_visible`.
- **Section heading** is the instrument's operator-editable
  `description`; the system handle (`Default` on the auto-created
  instrument; operator-chosen on any future ones) is internal-only
  and never reviewer-visible.

Across instruments — a reviewer assigned on multiple instruments for
the same session sees one such tabular artifact per instrument,
stacked. Each table is independent: its own rows (assignments scoped
to that instrument), its own display columns, its own response
columns. The same `(reviewer, reviewee)` pair may appear in zero,
one, or many instruments depending on how generation ran. The
reviewer-surface render path loops by instrument. Per-instrument
assignment generation (each instrument runs its own Band 1 rule)
has shipped; a group-scoped instrument collapses its per-member
rows into one card per group at render time.

### Practical implications today

The operator-controlled instrument layer + Setup-page surface
have shipped end-to-end. For URL-by-URL ship-state and the
authoritative "what works today" list, read **`docs/status.md`**
("Capabilities today" + "What's deliberately not yet there").

- Session creation auto-seeds one instrument (system handle
  `Default`) with two response fields (`rating` integer 1–5
  required, `comments` long text optional). Display fields are
  seeded lazily from import data, not on session creation (see
  "Lazy display-field seeding" below). See
  `app/services/instruments/_instrument_crud.py`
  (`ensure_default_instrument`).
- Response fields carry a plain `data_type` (String / Integer /
  Decimal / List) plus bounds and an optional `list_options` string.
  The former per-session **Response Type Definitions** table +
  `_rtds.py` slice retired 2026-05-26; a small set of operator-facing
  quick-fill list presets (`instruments/_field_presets.py`) replaced
  the RTD catalogue.
- `/operator/sessions/{id}/instruments` is the single consolidated
  page for everything per-instrument: All Instrument Status card +
  one card per instrument (identity + Bands 1/2/3 — the assignment
  rule, response fields, display fields — acceptance + visibility
  toggles, live preview). See `spec/instruments.md` for the
  per-section contract.
- The reviewer surface renders one tabular artifact per instrument
  in DOM order, with section heading from `Instrument.description`
  (fallback to handle) and a per-field help block above each table.
- Schema + services + operator UI are multi-instrument-aware
  (`create_instrument`, `delete_instrument`, FK cascades; the
  `Add an instrument` and `Delete this instrument` buttons).

Items still deliberately deferred (see `docs/status.md` "What's
deliberately not yet there" for the canonical list): reviewer-
dashboard per-instrument grouping and response-field type changes
after creation (data-migration concern).

### Session lifecycle

`ReviewSession.status` is the canonical lifecycle column. **Five
states are live**: `draft`, `validated`, `ready`, `expired`, and
`archived`. `expired` is written by `expire_session` (the Workflow
card's **Close session** button, `ready → expired`); `archived` by
`archive_session` / `unarchive_session`. No `SessionStatus` value is
purely reserved today. The column stays a `String(32)` — the value
set is enforced at the application layer (the `SessionStatus` enum in
`app/services/session_lifecycle.py`), not via a DB CHECK constraint.

**`spec/lifecycle.md` is the single source of truth** for the state
machine — the transitions (`mark_validated`, `activate_session`,
`invalidate_session` / `invalidate_if_validated`,
`revert_session_to_draft`, `expire_session`, `archive_session` /
`unarchive_session`), the route-layer gates, the per-instrument
open/close model, and the UI lock-card pattern. The paragraphs below
are the original write-path narrative kept for architectural context;
where they and `spec/lifecycle.md` diverge, the lifecycle spec wins.

**Session status overrides instrument acceptance.** Activation
(`validated → ready`, `activate_session`) flips every instrument's
`accepting_responses` to `true`. Revert (`ready → draft`,
`revert_session_to_draft`) and Close (`ready → expired`,
`expire_session`) flip them all back to `false` in the same
transaction — revert emits a single `session.reverted_to_draft`
audit event (no per-instrument close events on that path). Existing
`Response` rows are preserved untouched on revert and on close; the
reviewer surface returns to read-only.

The reviewer write-path predicate
`session_lifecycle.session_accepts_responses(session, instrument)`
gates `save`/`submit`/`clear`. Saving requires all of: session is
`ready`, the assignment's instrument has `accepting_responses=true`,
and `now() < session.deadline`. The session deadline auto-closes the
instrument lazily — the first reviewer or operator request that
observes the deadline has passed sets `accepting_responses=false`,
stamps `Instrument.deadline_closed_at`, and emits a single
`instrument.closed reason=deadline` audit event per instrument.

Setup is open only while the session is **editable** — `draft` OR
`validated` (`is_editable`). Once the session leaves that band
(`ready` / `expired` / `archived`), every operator setup-mutation
endpoint (session edit/delete, roster import + delete-all, instrument
CRUD, assignment generate + delete-all) returns **HTTP 409** via the
`_require_editable` route gate in
`app/web/routes_operator/_shared.py`. The corresponding GET pages
render read-only banners. Operators must revert to draft to make
further setup changes; if any `Response` rows already exist,
response-loss acknowledgment (`acknowledge_response_loss=true`) is
required on operations that would invalidate them.

### Invitations + dev outbox (Segment 9.2)

`Invitation` rows are operator-issued, per-reviewer access tokens. The
DB stores only `sha256(token)` in `Invitation.token_hash` — the raw
token is shown to the operator at outbox-write time (and persisted in
the `email_outbox.body` so the operator can re-copy the link). Sending
an invitation always rotates the token, so a previously delivered URL
becomes stale.

State machine: `pending` → `sent` → `opened`. Generate is idempotent
(operator-paced, no auto-trigger on activation). All invitation
actions require `session.status == "ready"` (409 otherwise) so the
emailed link never points at a draft session.

`/me/invite/{token}` requires Easy Auth sign-in (no magic-link
anonymous access — that's deferred to Segment 16A). The route looks up
the invitation by token hash, refuses with **403** + a dedicated page
if the signed-in user's email doesn't match the invitation's reviewer
email, and otherwise stamps `opened_at` once and 303s to
`/me/sessions/{id}`.

The `email_outbox` table (Segment 9.2) is the dev-mode replacement
for SMTP. Rows synchronously flip `queued → sent` when the operator
clicks Send. Real SMTP / production email is deferred to Segment 14B;
the outbox table itself stays useful for debugging in any environment.

### Reminders (Segment 9.3; monitoring surface reshaped in 11C / 15E)

The standalone `/operator/sessions/{id}/monitoring` page retired in
Segment 11C Part 1 — its reviewer-progress view consolidated into the
**Invitations** Operations page (reviewer-centric) and its
reviewee-coverage view into the **Responses** page
(reviewee-centric); see `spec/operations_pages.md`. The legacy
`/monitoring` URL redirects to
`/operator/sessions/{id}/invitations` to preserve bookmarks.

A reviewer is **incomplete** iff their session pill is anything other
than `submitted` — i.e. any of "never opened", "opened but not
submitted", or "submitted-with-warn-override that still has missing
required" classify them as incomplete. The Workflow card's **Send
reminders** stepper action (Segment 15E) targets every incomplete
reviewer session-wide; the Invitations page's per-row **Send
reminder** button (`POST /operator/sessions/{id}/invitations/{iid}/remind`)
targets one reviewer.

Reminders **reuse the URL from the most recent invitation outbox row**
verbatim — the token is **not** rotated, so the reviewer's previously
delivered link keeps working. When no prior invitation outbox row
exists for an invitation (operator never sent the original), the
reminder action falls back to `send_invitation` (mints a fresh token,
writes a `kind='invitation'` row); the operator's intent always lands
as a deliverable message in one click. `Invitation.last_reminder_at`
stamps every successful reminder. There is no throttle. Bulk reminders
emit a single `reminders.sent` audit event with `detail.count` and the
list of invitation/me ids.

### Pair-level context

Per-pair context (three `tag_N` slots — e.g. "morning interview",
"room A", "panel-1") lives on the first-class **`relationships`**
table — one row per `(session_id, reviewer_id, reviewee_id)`
triple, seeded in **Segment 13E PR 2** and lit up by the
Relationships Setup page in **Segment 15D PR 2**. Each row
carries:

- `tag_1`, `tag_2`, `tag_3` — free-form per-pair labels.
- `status` — `active` / `inactive`. Defaults to `active`.

**Two consumers, one source:**

- **Reviewer surface.** Displayed alongside the reviewee via
  `InstrumentDisplayField` rows of `source_type='pair_context'`
  and `source_field='1'|'2'|'3'`. Render-time lookup
  (`display_field_value(field, assignment)`) reads off the
  relationship row matching the assignment's `(reviewer_id,
  reviewee_id)` pair.
- **Rule engine.** The `pair_context.tag1` / `pair_context.tag2`
  / `pair_context.tag3` predicate field names (Segment 15D PR 3)
  read via an eager
  `relationships.pair_context_lookup(db, session_id) -> dict`
  pre-built once per `engine.evaluate` call (15D PR 4). This
  dodges N×M re-queries — the dict is `{(reviewer_id,
  reviewee_id): Relationship}` and the predicate evaluator runs
  single-pass.

CSV columns on the Relationships extract / importer are
`ReviewerEmail`, `RevieweeEmail`, `PairContextTag1`,
`PairContextTag2`, `PairContextTag3`, `Status` (round-trip via
`app/services/extracts/relationships_extract.py` ↔
`app/services/relationships.py`).

#### Legacy pre-15D shape (retired)

Pre-15D, pair-level context lived on an `Assignment.context`
JSON column carrying both `pair_context_1/2/3` (informational,
shown to reviewers) and `assignment_context_1/2/3` (logic-
engaging, hidden from reviewers). The column was dropped in
**15D PR 6b**; the `assignment_context_*` family retired
entirely (it had no production data and never landed an
operator UI). Migration `e43454fceb1c` (15D PR 5) backfilled
existing JSON `pair_context_*` values into `relationships`
rows before the column drop.

#### Lazy display-field seeding (2026-05-01, item #14)

`InstrumentDisplayField` rows are seeded **lazily** from import
data, never unconditionally on session creation. This avoids the
data-loss-by-illusion shape where reviewers saw three blank
`Pair Context` columns on full-matrix sessions because the legacy
default seed assumed manual mode would always populate them.

- `ensure_default_instrument` and `create_instrument` create no
  display-field rows.
- After a successful reviewees CSV import, `save_reviewees` calls
  `seed_display_fields_from_reviewees`, which adds a row for any
  reviewee column (`profile_link`, `tag_1/2/3`) with at least one
  populated value across the imported set. Idempotent —
  re-importing reviewees does not duplicate rows.
- After a successful relationships CSV import,
  `save_relationships` calls `seed_display_fields_from_assignments`
  (the legacy-named helper now reads from `relationships.tag_N`
  per the 15D rewrite), which adds a `pair_context_N` row for any
  slot with at least one populated value across the session's
  relationships. Sessions without populated pair-context slots
  are a no-op.
- Reviewee Name and Email are not display fields; they're
  rendered by the hardcoded reviewee-identity column in
  `review_surface.html`. The Display Fields card on the
  Instruments page surfaces only the configurable extras.

The `dfedd22a38da` migration (2026-05-01) cleans up legacy
unconditional seeds — for every existing instrument, drops
`pair_context_N` rows whose slot is unpopulated. Rows whose
slot has data (including operator-typed labels) are preserved.

## Audit-event detail schema

`AuditEvent.detail` is a free-form `JSON` column, but every new
write composes from a small set of named envelopes plus a few
orthogonal slots. Emitters pick the envelope that fits the
event's nature; mixing two payload envelopes in one event is a
smell that reads as the event trying to do two things at once.

The convention is enforced by the typed helpers in
`app/services/audit.py` (`audit.changes(...)` /
`audit.snapshot(...)` / `audit.counts(...)` /
`audit.set_changes(...)`). The Pydantic write-validation gate
shipped in Segment 11K PR 8 catches drift back into the old
idiosyncratic shapes — strict mode (flipped on in tests) raises
`AuditDetailValidationError` on any registered-but-malformed
event.

### Identity slots (top-level, almost always present)

```jsonc
{
  "session_id": <int | null>,
  "session_code": "<str | null>",
  // … plus exactly one payload envelope, see below …
}
```

`session_id` mirrors the FK column; including it in `detail`
costs ~6 bytes per row and saves the audit-export consumer a
join. `session_code` is the operator-typed stable identifier;
including it stabilises bookmarks and search ("show me every
event for code 'CS101'") without joining against `sessions`.

For events whose FK column is null because the session row is
gone (`session.deleted`), top-level identity slots are absent
and identity lives inside the `snapshot` envelope on
column-mirror keys (`id` / `code`) instead.

### Payload envelopes (pick one)

#### `changes` — scalar-key updates

```jsonc
{
  "changes": {
    "name": ["old", "new"],
    "deadline": ["2026-05-01T00:00:00+00:00", "2026-05-15T00:00:00+00:00"],
    "help_contact": [null, "support@x.edu"]
  }
}
```

For `session.updated`, `instrument.field_updated`,
`email_template.updated`, `operator_email_settings.updated`.
Each value is a `[old, new]` two-tuple; `null` is allowed on
either side. No nested keys (use `set_changes` if you're
mutating a collection). Datetime / date values are serialised
to ISO-8601 strings by the helper.

#### `snapshot` — full-state capture

```jsonc
{
  "snapshot": {
    "id": 17,
    "name": "Final Review",
    "code": "FR2026",
    "deadline": "2026-06-01T00:00:00+00:00",
    "status": "draft"
    // … every column at the moment of the event …
  }
}
```

For events where the row is the subject — `session.created`,
`session.deleted`, `instrument.deleted`, `reviewer.deleted`.
Snapshot keys mirror DB column names; nested objects are
allowed (e.g. `snapshot.instruments` on `session.deleted`).

#### `counts` — aggregate ops

```jsonc
{
  "counts": {
    "reviewers": 8,
    "reviewees": 13,
    "assignments": 104
  }
}
```

For bulk operations — `assignments.generated`,
`reviewers.imported`, `reviewees.imported`,
`responses.deleted_all`, `responses.cleared`. All values are
non-negative integers.

#### `set_changes` — collection mutations

```jsonc
{
  "set_changes": {
    "added":   [{ "key": "tag_1", "label": "Department" }],
    "removed": [{ "key": "tag_old", "label": "Legacy" }],
    "updated": [{ "key": "tag_2", "changes": { "label": ["A", "B"] }}]
  }
}
```

For events that mutate a collection of children —
`instrument.display_fields_saved`,
`instrument.response_fields_saved`. Each entry in `added` /
`removed` is a flat dict (no nested envelopes). `updated`
entries carry their own `changes` sub-dict (same shape as the
top-level `changes` envelope; one level of nesting only).

### Orthogonal slots (combine freely with any envelope)

#### `reason` — top-level string

```jsonc
{ "reason": "operator_revert", "snapshot": { … } }
```

For events triggered by a known cause: invalidation
(`reason: "setup_mutation"`), revert
(`reason: "operator_revert"`), cascade close
(`reason: "deadline"` / `"manual"`). Free-form `str`; emitters
pick from a small documented set per event family rather than
typing freely.

#### `refs` — cross-entity reference IDs

```jsonc
{ "refs": { "instrument_id": 7, "reviewer_id": 42 } }
```

For events whose subject isn't the session itself — when an
event scoped to a session is *about* a child entity (an
instrument, a reviewer, a response field). Keys end in `_id`
and values are integer PKs. The audit-export consumer reads
this to thread cross-entity rows together without re-joining
through every event's bespoke detail shape.

#### `context` — descriptive scalar metadata

```jsonc
{ "context": { "mode": "full_matrix", "filename": "manual.csv" } }
```

For events that carry descriptive scalars that are part of the
audit story but don't fit any payload envelope or other slot —
`assignments.generated`'s `mode` (`"full_matrix"` /
`"manual"`), `csv_imports`' `filename`,
`email_template.updated`'s `template`,
`session.activated`'s `prev_status` and `override_warnings`,
`instruments.bulk_accepting_responses`'s `target`. Keys are
short identifiers; values are `str`, `int`, or `bool` (no
nesting, no lists). `refs` stays int-PKs only and `counts`
stays non-negative-int only — `context` is the slot for
everything else that's a single scalar describing the *how*
or *from where* of the event.

`context` is small by design: if a key list reaches more than
4-5 entries, the event is probably trying to do two things at
once and should split.

### Empty-detail case

For events that need no payload (rare but legal, e.g. a
"viewed" event), `detail = None` is correct. Don't write
`detail = {}` — the model column is nullable; `None` is the
canonical "no payload" marker.

### Worked examples

| Event type | Envelope(s) | Canonical detail |
|---|---|---|
| `session.created` | `snapshot` | `{"session_id": 17, "session_code": "CS101", "snapshot": {"id": 17, "code": "CS101", "name": "Final Review"}}` |
| `session.updated` | `changes` | `{"session_id": 17, "session_code": "CS101", "changes": {"name": ["Spring", "Spring v2"]}}` |
| `session.deleted` | `snapshot` (no top-level identity) | `{"snapshot": {"id": 17, "code": "CS101", "name": "Final Review"}}` |
| `session.invalidated` | `reason` (no payload) | `{"session_id": 17, "session_code": "CS101", "reason": "setup_mutation"}` |
| `instrument.closed` | `reason` + `refs` | `{"session_id": 17, "session_code": "CS101", "refs": {"instrument_id": 7}, "reason": "deadline", "context": {"deadline": "2026-06-01T00:00:00+00:00"}}` |
| `assignments.generated` | `counts` + `context` | `{"session_id": 17, "session_code": "CS101", "counts": {"assignments": 104, "pairs": 13, "instruments": 8, "replaced": 0}, "context": {"mode": "full_matrix"}}` |
| `responses.saved` | `refs` + `counts` | `{"session_id": 17, "session_code": "CS101", "refs": {"reviewer_id": 42}, "counts": {"saved": 5, "validation_errors": 0}}` |
| `instrument.display_fields_saved` | `set_changes` + `refs` | `{"session_id": 17, "session_code": "CS101", "refs": {"instrument_id": 7}, "set_changes": {"added": [], "removed": [], "updated": [...]}}` |
| `session.owner_added` | `snapshot` + `refs` | `{"session_id": 17, "session_code": "CS101", "refs": {"target_user_id": 42}, "snapshot": {"user_id": 42, "email": "bob@example.edu", "role": "owner"}}` |
| `session.activation_scheduled` | `changes` | `{"session_id": 17, "session_code": "CS101", "changes": {"scheduled_activate_at": [null, "2026-06-01T09:00:00+00:00"]}}` |
| `session.scheduled_activation_skipped` | `reason` + `context` | `{"session_id": 17, "session_code": "CS101", "reason": "not_validated", "context": {"scheduled_at": "2026-06-01T09:00:00+00:00", "status_at_fire": "draft"}}` |
| `session.scheduled_activation_retry` / `_failed_persistent` | `reason` + `context` | `{"session_id": 17, ..., "reason": "<repr(exc)>", "context": {"scheduled_at": "...", "attempt": 1}}` |
| `session.invite_schedule_updated` / `session.reminder_schedule_updated` | `changes` | `{"session_id": 17, ..., "changes": {"invite_offsets": [null, ["-P1D", "-PT2H"]]}}` |
| `session.scheduled_invites_fired` | `counts` + `context` | `{"session_id": 17, ..., "counts": {"sent": 12}, "context": {"anchor_at": "2026-06-01T09:00:00+00:00", "offset_index": 0, "offset": "-P1D", "scheduled_at": "2026-05-31T09:00:00+00:00", "actual_fired_at": "2026-05-31T09:00:42+00:00"}}` |
| `session.scheduled_invites_skipped` | `reason` + `context` | `{"session_id": 17, ..., "reason": "not_prepared" \| "invitations_not_created", "context": {"anchor_at": "...", "offset_index": 0, "offset": "-P1D", "scheduled_at": "..."}}` |
| `session.scheduled_reminders_fired` | `counts` + `context` | Same shape as `scheduled_invites_fired`, anchored on `deadline`. |
| `session.scheduled_reminders_skipped` | `reason` + `context` | `reason ∈ {"not_ready", "no_invitations", "outside_response_window"}`; same context keys. |

**Observer roster events** (registered in `EVENT_SCHEMAS` as part
of the participant-model Phase 1 work — PR #1706):

| Event type | Envelope(s) |
|---|---|
| `observer.created` | `snapshot` (+ identity) |
| `observer.updated` | `changes` + `refs` (+ identity) |
| `observer.bulk_inactivated` / `.bulk_reactivated` | `snapshot` (+ identity) |
| `observers.imported` | `counts` + `context` (+ identity) |
| `observers.deleted_all` | `counts` (+ identity) |

The `observer.created` and `observers.imported` events emit
in `app/services/observers.py` and `app/services/csv_imports.py`
respectively, following the same per-row / bulk-replace pattern
as the `reviewer.*` / `reviewers.*` family.

### Cutover

Rows written **before 2026-05-07** use legacy per-emitter
shapes (each event family had its own idiosyncratic dict
layout — see `git log app/services/audit.py` and the
pre-migration emitters for the historical shapes). The
canonical convention applies to every new write from PR 1 of
Segment 11K (2026-05-07) onward; existing rows are not
rewritten, since the audit log is append-only.

The `audit_events.created_at` timestamp is the cutover
boundary the audit-export consumer (Segment 12B) reads to
decide which shape to interpret.

## Access-control invariants

- **Operator lobby gate** — `GET /operator/*` is gated by
  `require_operator` / `require_session_operator` in
  `app/web/deps.py`. A user's membership in **any participant
  roster** (reviewer, reviewee, or observer) never confers
  operator access; only `users.is_operator`, a `session_operators`
  row, or an elevated role does. This invariant is pinned by a
  regression test in
  `tests/integration/test_operator_lobby_access_gate.py`.

- **Three-tier role model (Segment 18S).** The admin surface is a
  strict, nested hierarchy: **super-admin ⊇ admin ⊇ operator**.
  `users.is_operator` and `users.is_sys_admin` (admin) are stored
  columns; **super-admin is derived, never stored** —
  `app/auth/roles.py::is_super_admin` tests case-insensitive
  membership in the deployer-config `SUPER_ADMIN_EMAILS`. Gates
  treat admin as implying operator; a super-admin self-heals to
  `is_sys_admin = is_operator = True` on every sign-in
  (`deps.py::_reassert_super_admin`). Admins add/revoke operators;
  super-admins add/revoke admins; the super-admin tier moves only in
  Azure App Settings. See `spec/audience_and_identity_model.md` §4.

- **Per-session owner delegation.** The session creator becomes the
  inaugural `session_operators` row (`role="owner"`); additional
  owners are added/removed by current owners, guarded by a
  last-owner floor, and audited via `session.owner_added` /
  `session.owner_removed`.

- **Participant gates** — `require_reviewee_in_session` /
  `require_observer_in_session` gate the reviewee results and
  observer collation routes; `require_reviewer_in_session` gates the
  reviewer write-path. All three match the signed-in user's email
  (case-insensitive) against the session roster and require the row
  to be `active`.

## Implementation principles

- Keep routes thin.
- Put business logic in services.
- Use explicit schemas at application boundaries.
- Keep authentication separate from authorization.
- Treat audit events as domain records, not ordinary logs.
- Keep the reviewer tabular surface isolated from the rest of the
  frontend complexity.
- Replace-all over append/merge for destructive operator workflows,
  with explicit confirm checkboxes and audit trails. Cascade effects
  (e.g. assignments deleted when a reviewer roster is replaced) are
  surfaced to the operator before they confirm. The one deliberate
  exception is assignment **regeneration**, which reconciles rather
  than replaces — inserting newly eligible pairs, dropping orphaned
  ones, and leaving matched pairs (and their saved responses)
  untouched. See `spec/reconciling_regeneration.md`.
- Materialise rather than virtualise: the rule engine (including the
  synthetic Full Matrix default) generates concrete Assignment rows
  rather than implying them, so downstream features query one uniform
  table regardless of instrument rule or group scoping.
