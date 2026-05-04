# Segment 11C — Operations consolidation (Invitations + Responses)

Stub. Implementation plan for consolidating the running-session
Operations work per `spec/operations_renew.md`. Sibling to
Segment 11B (Session Home rebuild); both pull forward the
operator-facing work originally bucketed in Segment 11A's #21
sweep.

The functional spec is **`spec/operations_renew.md`**. The page
taxonomy + per-page contract summaries are in
**`spec/operator_ui_concept.md`** §5 and "Per-page contracts".
This guide is the implementation plan; reference those specs for
detail.

## Status

Planning. Sized as ~3–5 PRs to land in dependency order; each
independently shippable.

## Scope

In:

- Build a new **Responses** Operations page (`session_responses.html`,
  `/sessions/{id}/responses`) — reviewee-centric coverage view with
  list-with-bulk-actions pattern: per-reviewee status (Complete /
  Adequate / At risk / No responses), filtering, selection, bulk
  reminder dispatch to non-responding reviewers, per-row drill-in.
- Rebuild **Invitations** (`session_invitations.html`,
  `/sessions/{id}/invitations`) as the consolidated reviewer-centric
  page: list-with-bulk-actions pattern absorbing what's currently
  split between the standalone Invitations page (sending, token
  rotation) and the Monitoring page (reviewer progress, reminders).
  The URL slug stays `/invitations`; templates and tests update.
- Add the **Responses** Operations row tab to `session_top_nav.html`
  in the position established by `spec/operator_ui_concept.md`:
  `Validate / Preview / Invitations / Responses / Outbox`.
- Restore **Outbox** as a chrome tab (currently reachable only from
  "View outbox" buttons on Invitations and Monitoring).
- Retire `session_monitoring.html`. Add a `/sessions/{id}/monitoring`
  → `/sessions/{id}/invitations` redirect to preserve any inbound
  bookmarks.
- Extract the shared list-with-bulk-actions pattern (filter strip,
  checkbox column, bulk action bar, per-row drill-in) into a small
  reusable convention or partial both pages instantiate.
- Single-source the reminder send-path so per-row + bulk reminders
  from either Invitations or Responses feed the same underlying
  email send.

Out:

- Operator-configurable "at-risk" thresholds on Responses. Land
  with app-default constants in one place; future enhancement.
- Live updating / auto-refresh — pages render snapshot data; a
  manual refresh affordance is the budget for this segment.
- Reading individual response content from these pages (that's the
  Extract Data flow, Segment 12).
- Real SMTP / production email — still deferred to Segment 15;
  reminder-send writes outbox rows in dev as today.

## Gap against the spec

| Spec requirement | Current state | Action |
|---|---|---|
| Invitations is reviewer-centric, list-with-bulk-actions | Old "Manage invitations" page: 3-count summary card + table; no bulk selection / no filters; reminders live on a separate Monitoring page | Rewrite |
| Responses page exists | Doesn't exist | New template + route |
| Operations row: Validate / Preview / Invitations / Responses / Outbox | Validate / Preview / Invitations / Monitoring (no Outbox tab; no Responses tab) | Add Responses + Outbox tabs; remove Monitoring |
| Monitoring URL preserved as redirect | 404s if removed cleanly | Add 303 redirect handler |
| Shared reminder send-path | Each call site composes its own send | Extract single helper; per-row, bulk-from-Invitations, bulk-from-Responses, drill-in-from-either all call it |
| List-with-bulk-actions pattern shared | New pattern for both pages | Implement once; both pages instantiate |

## Proposed PR sequence

**PR A — `/monitoring` redirect + chrome update.** Foundation: add
the `/sessions/{id}/monitoring` → `/sessions/{id}/invitations` 303
redirect; update `session_top_nav.html` `_ops_pages` to add
"Responses" and restore "Outbox" before the new pages exist (the
tabs would 404 if clicked, but other PRs land them quickly). Or
sequence the chrome change to land alongside PR B / C — TBD when
the work starts.

**PR B — List-with-bulk-actions pattern.** Extract the shared
filter / checkbox-column / bulk-action-bar / per-row drill-in
pattern. Land as a partial or set of partials; ship with no
behaviour change yet (no consumers).

**PR C — Invitations rewrite.** Migrate the existing
`session_invitations.html` to the new consolidated reviewer-centric
shape using the pattern from PR B. Absorbs the reminder action and
per-reviewer progress columns from Monitoring. Update tests pinned
to the old markup.

**PR D — Responses page.** New `session_responses.html` +
`/sessions/{id}/responses` route + the reviewee-centric coverage
service helpers. Bulk reminder dispatch shares the send-path with
Invitations.

**PR E — Retire `session_monitoring.html`.** Delete the template
and its dedicated route handler; the redirect from PR A keeps the
URL alive. Sweep tests + cross-references to drop Monitoring
mentions.

PR ordering can fold (e.g., A + B together, or D + E) depending on
risk appetite once implementation starts.

## Implementation pointers

- **Shared pattern.** First-cut implementation can inline the
  list-with-bulk-actions pattern in both pages. Extract to a partial
  once the shape settles. Don't over-engineer pre-extraction.
- **Reminder send-path.** Single function in
  `app/services/invitations.py` or a new
  `app/services/reminders.py`; takes a list of `(reviewer_id,
  reviewee_id_or_None)` tuples and writes outbox rows. All callers
  funnel through it.
- **Filter + selection state.** Page-local; not persisted across
  navigations. Implement via query params or simple form-based
  filter posts; no client-side state machine needed for the first
  cut.
- **Drill-in.** Side panel vs. sub-page is open. Side panel is
  gentler (operator stays in list context); sub-page allows more
  detail. Pick whichever fits more naturally with the codebase's
  existing patterns at implementation time.
- **At-risk thresholds.** Constants in one place
  (e.g. `app/services/responses.py::AT_RISK_THRESHOLDS`); future
  operator-configurable enhancement is then a small change to
  that one location.
- **The Outbox tab** is purely a chrome change — the page itself is
  already on v2 (PR #366); it just stops being a hidden destination
  and becomes a first-class Operations tab.

## Out of scope (cross-references)

- **Real SMTP / production email** — Segment 15.
- **Operator-editable email template editor** — Segment 11A
  remaining item (#24); independent of this segment.
- **Reading response content / extraction** — Segment 12.
- **Per-instrument or per-assignment level dashboards** — out of
  scope; if eventually wanted, would compose on top of the Responses
  page rather than replacing it.

## Test impact

PR C is the heaviest on test churn — every test that asserts on the
old Manage Invitations page markup or the old Monitoring page
markup will need updating or relocating. Plan to refresh those
assertions in the same PR. Search hits include
`tests/integration/test_invitations.py` and
`tests/integration/test_monitoring.py`.

PR E retires the Monitoring page entirely; any test file scoped
purely to the Monitoring page should be deleted (its coverage moves
into the new Invitations + Responses test files).
