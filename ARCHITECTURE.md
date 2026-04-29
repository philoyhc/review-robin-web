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
  response fields. **Multi-instrument is a planned future** (Segment
  12); for now the model invariant is that every session has exactly
  one auto-created `Default` instrument with seed response fields.
  When operator-controlled instrument editing lands, that default
  becomes the starting point operators rename / extend / replace.
- **Assignments** are `(session, reviewer, reviewee, instrument)`
  rows. They link the assignment matrix (the pair) to the response
  form (the instrument). The same `(reviewer, reviewee)` pair may
  appear in zero, one, or many instruments within a session,
  depending on how generation runs against each instrument.
- **Responses** are `(assignment, response_field)` rows: the
  reviewer's answer to one field on one instrument for one assigned
  reviewee.

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

When multi-instrument lands (Segment 13):

- Operators can add more instruments under a session and define
  per-instrument response fields.
- Assignment generation gains an instrument selector — different
  instruments can have different subsets of pairs.
- The reviewer surface stacks (or tabs) sections per instrument the
  reviewer is assigned on for that reviewee. Schema unchanged.

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

### Pair-level vs assignment-level context

Manual CSV imports may carry two kinds of per-pair context, both
stored in `Assignment.context` JSON:

- **`pair_context_1/2/3`** is informational metadata (e.g. "morning
  interview", "room A"). Displayed alongside the reviewee in the
  reviewer surface. Never read by assignment-generation logic.
- **`assignment_context_1/2/3`** is logic-engaging context (e.g.
  "panel-1", a category code). Read by RuleBased rules in Segment
  11. Hidden from reviewers by default; can become reviewer-visible
  when an operator opts in via `InstrumentDisplayField` (Segment 13).

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
