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
  Segment 11).
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

When multi-instrument lands (Segment 12):

- Operators can add more instruments under a session and define
  per-instrument response fields.
- Assignment generation gains an instrument selector — different
  instruments can have different subsets of pairs.
- The reviewer surface stacks (or tabs) sections per instrument the
  reviewer is assigned on for that reviewee. Schema unchanged.

### Pair-level vs assignment-level context

Manual CSV imports may carry two kinds of per-pair context, both
stored in `Assignment.context` JSON:

- **`pair_context_1/2/3`** is informational metadata (e.g. "morning
  interview", "room A"). Displayed alongside the reviewee in the
  reviewer surface. Never read by assignment-generation logic.
- **`assignment_context_1/2/3`** is logic-engaging context (e.g.
  "panel-1", a category code). Read by RuleBased rules in Segment
  11. Hidden from reviewers by default; can become reviewer-visible
  when an operator opts in via `InstrumentDisplayField` (Segment 12).

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
