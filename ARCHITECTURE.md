# Architecture Notes

Review Robin Web is organized around explicit domain entities:

- sessions
- reviewers
- reviewees
- instruments
- assignments
- responses
- invitations
- audit events
- exports
- retention actions

## Conceptual hierarchy

The shape of the data model is deliberate. From the operator's
perspective:

- **Session** is the top-level container. A session defines the
  *universe* of reviewers and reviewees and carries one assignment
  matrix that determines which reviewer-reviewee pairs are reviewed.
  The matrix is computed once per session — manually (Manual import)
  or via a deterministic preset (FullMatrix today, RuleBased in
  Segment 12).
- **Instruments** are the *response forms* attached to a session. A
  session has one or more instruments, each defining its own set of
  response fields. **Multi-instrument is Segment 13**; for now the
  model invariant is that every session has exactly one auto-created
  instrument (system handle `instrument_1`) with seed response
  fields. Operator-controlled editing of that instrument's response
  fields, per-field help text, and friendly description ships in
  Segment 10A; operator-configurable display columns (which reviewee
  tags and pair contexts appear on the reviewer surface alongside the
  response fields) and a read-only operator preview ship in
  Segment 10B.
- **Assignments** are `(session, reviewer, reviewee, instrument)`
  rows. They link the assignment matrix (the pair) to the response
  form (the instrument). The same `(reviewer, reviewee)` pair may
  appear in zero, one, or many instruments within a session,
  depending on how generation runs against each instrument.
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
  `description`; the system handle (`instrument_1`, `instrument_2`,
  …) is internal-only and never reviewer-visible.

Across instruments — a reviewer assigned on multiple instruments for
the same session sees one such tabular artifact per instrument,
stacked. Each table is independent: its own rows (assignments scoped
to that instrument), its own display columns, its own response
columns. The same `(reviewer, reviewee)` pair may appear in zero,
one, or many instruments depending on how generation ran. The
multi-table form ships under Segment 13 (multi-instrument); Segments
10A and 10B keep the invariant of exactly one instrument per session
but already render and configure as if N instruments were possible
(loop-by-instrument with N=1 today).

### Practical implications today

Because instrument editing has not shipped:

- `create_session` synchronously creates the Default Instrument and
  seeds it with two response fields (`rating`, integer 1–5,
  required; `comments`, long text, optional). See
  `app/services/instruments.py`.
- Every `Assignment` row points at that single Default Instrument,
  so the assignments matrix is effectively per-session in user-
  visible terms today.
- The reviewer surface (Segment 8) renders the Default Instrument's
  fields against each assigned reviewee.

When operator-controlled instrument editing lands (Segment 10):

- 10A introduces a consolidated `/operator/sessions/{id}/instruments`
  page with per-instrument cards: friendly description, response
  fields (add / edit / delete / reorder), per-field help text,
  per-field `help_text_visible` toggle, and the existing 9.1
  acceptance + visibility toggles. The 9.1 sub-page at
  `/instruments/{instrument_id}` is folded into the consolidated
  page; action POSTs keep the `{instrument_id}` segment in their
  path. The reviewer surface refactors to render section heading +
  help block + table per instrument, looping over an
  instruments-collection-of-one.
- 10B adds the display-fields picker (which reviewee tags and pair
  contexts appear as columns alongside the response fields) and a
  read-only operator preview at `/operator/sessions/{id}/preview`.

When multi-instrument lands (Segment 13):

- Operators can add more instruments under a session via the same
  consolidated page (the `Add instrument` and `Delete instrument`
  buttons that ship disabled in 9.4C light up).
- Assignment generation gains an instrument selector — different
  instruments can have different subsets of pairs.
- The reviewer surface stacks the per-instrument sections 10A
  already renders. Schema unchanged.

### Session lifecycle (Segment 9.1)

`ReviewSession.status` is the canonical lifecycle column. Active values
in 9.1 are `draft` and `ready`; `expired` and `archived` are reserved
in `app/services/session_lifecycle.py::SessionStatus` and not yet
written by any route. The column stays a `String(32)` — the value
set is enforced at the application layer, not via a DB CHECK
constraint.

**Session status overrides instrument acceptance.** Activation
(`draft → ready`) flips every instrument's `accepting_responses` to
`true`. Revert (`ready → draft`) flips them all back to `false` in the
same transaction and emits a single `session.reverted_to_draft` audit
event (no per-instrument close events on the revert path). Existing
`Response` rows are preserved untouched on revert; the reviewer surface
returns to read-only.

The reviewer write-path predicate
`session_lifecycle.session_accepts_responses(session, instrument)`
gates `save`/`submit`/`clear`. Saving requires all of: session is
`ready`, the assignment's instrument has `accepting_responses=true`,
and `now() < session.deadline`. The session deadline auto-closes the
instrument lazily — the first reviewer or operator request that
observes the deadline has passed sets `accepting_responses=false`,
stamps `Instrument.deadline_closed_at`, and emits a single
`instrument.closed reason=deadline` audit event per instrument.

While `status == ready`, every operator setup-mutation endpoint
(session edit/delete, roster import + delete-all, assignment generate
+ delete-all) returns **HTTP 409**. The corresponding GET pages render
read-only banners. Operators must revert to draft to make further
setup changes; if any `Response` rows already exist, response-loss
acknowledgment (`acknowledge_response_loss=true`) is required on
operations that would invalidate them.

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

`/reviewer/invite/{token}` requires Easy Auth sign-in (no magic-link
anonymous access — that's deferred to Segment 16). The route looks up
the invitation by token hash, refuses with **403** + a dedicated page
if the signed-in user's email doesn't match the invitation's reviewer
email, and otherwise stamps `opened_at` once and 303s to
`/reviewer/sessions/{id}`.

The `email_outbox` table (Segment 9.2) is the dev-mode replacement
for SMTP. Rows synchronously flip `queued → sent` when the operator
clicks Send. Real SMTP / production email is deferred to Segment 15;
the outbox table itself stays useful for debugging in any environment.

### Monitoring + reminders (Segment 9.3)

`/operator/sessions/{id}/monitoring` renders a session-level summary
(assigned / invited / opened / submitted / incomplete) and a
per-reviewer table with progress counts, invitation status, and a
per-row "Send reminder" button. Per-reviewee progress is intentionally
deferred.

A reviewer is **incomplete** iff their session pill is anything other
than `submitted` — i.e. any of "never opened", "opened but not
submitted", or "submitted-with-warn-override that still has missing
required" classify them as incomplete. Bulk
`/monitoring/remind-incomplete` and per-row `/invitations/{iid}/remind`
target this set.

Reminders **reuse the URL from the most recent invitation outbox row**
verbatim — the token is **not** rotated, so the reviewer's previously
delivered link keeps working. When no prior invitation outbox row
exists for an invitation (operator never sent the original), the
reminder action falls back to `send_invitation` (mints a fresh token,
writes a `kind='invitation'` row); the operator's intent always lands
as a deliverable message in one click. `Invitation.last_reminder_at`
stamps every successful reminder. There is no throttle. Bulk reminders
emit a single `reminders.sent` audit event with `detail.count` and the
list of invitation/reviewer ids.

### Pair-level vs assignment-level context

Manual CSV imports may carry two kinds of per-pair context, both
stored in `Assignment.context` JSON:

- **`pair_context_1/2/3`** is informational metadata (e.g. "morning
  interview", "room A"). Displayed alongside the reviewee in the
  reviewer surface. Never read by assignment-generation logic.
- **`assignment_context_1/2/3`** is logic-engaging context (e.g.
  "panel-1", a category code). Read by RuleBased rules in Segment
  12. Hidden from reviewers; deliberately excluded from the Segment
  10B `InstrumentDisplayField` picker so the reviewer-facing /
  logic-engaging distinction is preserved. (Pair contexts go in the
  picker; assignment contexts do not.)

CSV columns are `PairContext1/2/3` and `AssignmentContext1/2/3`.

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
  surfaced to the operator before they confirm.
- Materialise rather than virtualise: FullMatrix generates concrete
  Assignment rows rather than implying them, so downstream features
  query one uniform table regardless of mode.
