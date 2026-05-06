# Segment 11C — Operations consolidation (Invitations + Responses) + email send activation

Stub. Implementation plan for consolidating the running-session
Operations work per `spec/operations_renew.md`. Sibling to
Segment 11B (Session Home rebuild); both pull forward the
operator-facing work originally bucketed in Segment 11A's #21
sweep.

This segment splits into **two distinct parts**, each of which
is multiple PRs:

- **Part 1 — Consolidation.** Bring the running-session operator
  surfaces onto the right pages with the list-with-bulk-actions
  pattern and a single consolidated Manage Invitations table.
  No new send semantics — outbox rows continue to land at
  `status="queued"` exactly as they do today.
- **Part 2 — Send activation.** Wire Segment 11E's transport
  interface into the consolidated Manage Invitations page so
  queued outbox rows actually transition to `sent` / `failed`.
  Adds bulk-Send, Send-test-to-me, the transport-ready chrome
  pill, and the schema move that makes failure observable.

The two parts ship independently. Part 1 stays useful even if
Part 2 slips. Part 2 hard-depends on Part 1's Invitations
rewrite (PR C) and on Segment 11E PRs 4 + 5 (operator Settings
page + transport interface) being merged.

The functional spec is **`spec/operations_renew.md`**. The page
taxonomy + per-page contract summaries are in
**`spec/operator_ui_concept.md`** §5 and "Per-page contracts".
This guide is the implementation plan; reference those specs for
detail.

## Status

Planning. Sized as **~7 PRs** total (5 in Part 1 + 2 in Part 2);
each independently shippable.

## Gap against the spec

| Spec requirement | Current state | Action | Part |
|---|---|---|---|
| Invitations is reviewer-centric, list-with-bulk-actions | Old "Manage invitations" page: 3-count summary card + table; no bulk selection / no filters; reminders live on a separate Monitoring page | Rewrite | 1 |
| Responses page exists | Doesn't exist | New template + route | 1 |
| Operations row: Validate / Preview / Invitations / Responses / Outbox | Validate / Preview / Invitations / Monitoring (no Outbox tab; no Responses tab) | Add Responses + Outbox tabs; remove Monitoring | 1 |
| Monitoring URL preserved as redirect | 404s if removed cleanly | Add 303 redirect handler | 1 |
| Shared reminder send-path | Each call site composes its own send | Extract single helper; per-row, bulk-from-Invitations, bulk-from-Responses, drill-in-from-either all call it | 1 |
| List-with-bulk-actions pattern shared | New pattern for both pages | Implement once; both pages instantiate | 1 |
| Outbox carries CC / BCC at queue time | `email_outbox` has only `to_email` | Add `cc_emails` / `bcc_emails` (populated from 11E override JSON) | 1 |
| Outbox rows can move from queued → sent / failed | Today they're written `queued` and never re-touched | Wire 11E transport interface; widen status enum; capture `error_message` | 2 |
| Operator can Send / bulk-Send / test-Send from Invitations | No such affordances exist | Add per-row + bulk + test-send affordances | 2 |
| Transport-ready chrome pill | None | Compute from operator's `EmailSettings` | 2 |

---

## Part 1 — Consolidation

### Scope (Part 1)

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

  **Consolidated table column spec:**

  | Column | Source | Notes |
  |---|---|---|
  | Reviewer | `Invitation.reviewer.name` (with email beneath) | First column. |
  | Email Status | derived from the latest *invitation* outbox row for this reviewer | Today: `queued` / `sent` (existing two-value enum). Part 2 widens this to `queued / sending / sent / failed` with the schema move; the column ships in Part 1, the broader value set in Part 2. |
  | Email Sent | latest invitation outbox row's `sent_at` | "—" when no row / never sent. |
  | Review Progress | computed across the reviewer's assignments | Format: `"{status} ({done}/{total})"` — e.g. `"Submitted (3/5)"`. |
  | Required Fields | computed across the reviewer's response fields | Format: `"({done}/{total})"`. |
  | Last reminder | latest *reminder* outbox row's `sent_at` for this reviewer | "—" when no row. |
  | Action | per-row affordances | Part 1: per-row "Send reminder" + drill-in to reviewer detail (token rotation moves here too if it isn't already). Part 2 adds: per-row "Send" button (when invitation row is `queued`). |

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
  outbox-enqueue helper. Reminders today already enqueue
  `status="queued"`; this work doesn't change that — it just funnels
  the call sites through one helper.
- **Outbox schema slice landing in Part 1:** add
  `cc_emails` / `bcc_emails` (Text, comma-separated) columns to
  `email_outbox`. Populated from the editor's CC / BCC override
  JSON (already stored in 11E) at queue time. Unused at send time
  until Part 2 wires the transport dispatch — but the storage is
  harmless and keeps the queue path shape-stable across the
  cutover.

Out of Part 1 (deferred to Part 2):

- Bulk-queue / bulk-Send action — bulk semantics arrive with the
  transport activation.
- Per-row "Send" button — only meaningful when the transport
  actually fires.
- Send-test-to-me affordance.
- Transport-ready status pill.
- `email.sent` / `email.send_failed` audit events (no sends happen
  yet).
- `error_message` column + widened status enum on `email_outbox`.

Out (cross-segment):

- Operator-configurable "at-risk" thresholds on Responses. Land
  with app-default constants in one place; future enhancement.
- Live updating / auto-refresh — pages render snapshot data; a
  manual refresh affordance is the budget for this segment.
- Reading individual response content from these pages (that's the
  Extract Data flow, Segment 12 / 12A).
- Per-reviewer / per-cohort body customization. Stays at session
  level via the editor's overrides; per-cohort would be a future
  enhancement on top.

### Proposed PR sequence (Part 1)

**PR A — `/monitoring` redirect + chrome update.** Foundation: add
the `/sessions/{id}/monitoring` → `/sessions/{id}/invitations` 303
redirect; update `session_top_nav.html` `_ops_pages` to add
"Responses" and restore "Outbox" before the new pages exist (the
Responses tab would 404 if clicked, but later PRs land it
quickly). Or sequence the chrome change to land alongside PR B / C
— TBD when the work starts.

**PR B — List-with-bulk-actions pattern + shared reminder
send-path.** Extract the shared filter / checkbox-column /
bulk-action-bar / per-row drill-in pattern. Land the single
reminder send-path helper here too — Invitations + Responses
bulk-reminder paths both funnel through it. Ship with no
behaviour change yet (no consumers).

**PR C — Invitations rewrite.** Migrate the existing
`session_invitations.html` to the new consolidated reviewer-
centric shape using the pattern from PR B. Ships the column spec
above. Absorbs the reminder action and per-reviewer progress
columns from Monitoring. Update tests pinned to the old markup.

**PR C-schema — Outbox `cc_emails` / `bcc_emails`.** Small Alembic
migration adding the two Text columns; queue-time population
wired into the existing `send_invitation` / `send_reminder`
helpers (read CC / BCC out of the session's
`email_template_overrides` JSON). Independent of PR C — can land
before or after; folding it into PR C is fine if the timing
aligns.

**PR D — Responses page.** New `session_responses.html` +
`/sessions/{id}/responses` route + the reviewee-centric coverage
service helpers. Bulk reminder dispatch shares the helper PR B
introduced.

**PR E — Retire `session_monitoring.html`.** Delete the template
and its dedicated route handler; the redirect from PR A keeps the
URL alive. Sweep tests + cross-references to drop Monitoring
mentions.

PR ordering can fold (e.g., A + B together, or D + E) depending
on risk appetite once implementation starts.

### Implementation pointers (Part 1)

- **Shared pattern.** First-cut implementation can inline the
  list-with-bulk-actions pattern in both pages. Extract to a
  partial once the shape settles. Don't over-engineer
  pre-extraction.
- **Reminder send-path.** Single function in
  `app/services/invitations.py` or a new
  `app/services/reminders.py`; takes a list of `(reviewer_id,
  reviewee_id_or_None)` tuples and writes outbox rows. All
  callers funnel through it.
- **Filter + selection state.** Page-local; not persisted across
  navigations. Implement via query params or simple form-based
  filter posts; no client-side state machine needed for the
  first cut.
- **Drill-in.** Side panel vs. sub-page is open. Side panel is
  gentler (operator stays in list context); sub-page allows more
  detail. Pick whichever fits more naturally with the codebase's
  existing patterns at implementation time.
- **At-risk thresholds.** Constants in one place
  (e.g. `app/services/responses.py::AT_RISK_THRESHOLDS`); future
  operator-configurable enhancement is then a small change to
  that one location.
- **Column-derivation queries.** The Email Status / Email Sent /
  Last reminder columns each need the latest outbox row of a
  given kind for a given reviewer. Land one helper that returns
  `dict[reviewer_id, OutboxSnapshot]` for both kinds in a single
  query rather than firing N queries per row. Same shape works
  for the Review Progress / Required Fields aggregates over
  assignments + responses.
- **The Outbox tab** is purely a chrome change — the page itself
  is already on v2 (PR #366); it just stops being a hidden
  destination and becomes a first-class Operations tab.

### Test impact (Part 1)

PR C is the heaviest on test churn — every test that asserts on
the old Manage Invitations page markup or the old Monitoring page
markup will need updating or relocating. Plan to refresh those
assertions in the same PR. Search hits include
`tests/integration/test_invitations.py` and
`tests/integration/test_monitoring.py`.

PR C tests pin the new column shape:
- Header order matches the spec.
- "Review Progress" cell renders `"{status} ({done}/{total})"`.
- "Required Fields" cell renders `"({done}/{total})"`.
- Each timestamp cell renders "—" when its underlying outbox row
  is absent.

PR C-schema gets an Alembic round-trip test that the new outbox
columns persist through a round-trip on both SQLite and Postgres.

PR E retires the Monitoring page entirely; any test file scoped
purely to the Monitoring page should be deleted (its coverage
moves into the new Invitations + Responses test files).

---

## Part 2 — Email send activation

Hard prerequisites: Part 1 PR C ships the consolidated Manage
Invitations page (Part 2 hangs the new affordances off it); Segment
11E PRs 4 + 5 ship the operator Settings page + the
`EmailTransport` Protocol / `SmtpEmailTransport`.

### Scope (Part 2)

In:

- **Outbox schema slice landing in Part 2:**
  - `error_message: Mapped[str | None]` (Text) on `email_outbox` —
    captured when a send fails so the Outbox page can surface the
    reason.
  - `status` enum widened from `{queued, sent}` to
    `{queued, sending, sent, failed}` (string column today;
    service-layer enforces the value set).
- **Transport dispatch helper** at
  `app/services/email_send_dispatch.py` that:
  - Reads a queued outbox row, builds an `EmailMessage` from it,
    invokes the operator's `EmailTransport.send(...)`, and writes
    back the result (`sent` / `failed` + `error_message`).
  - Refuses to dispatch if the initiating operator has no
    `EmailSettings` configured — surfaces an inline error rather
    than silently leaving the row queued.
- **Per-row Send button** on each invitation row of the
  consolidated Manage Invitations table (transitions a queued
  outbox row to `sent` / `failed` via the operator's configured
  `EmailTransport`). Slots into the table's "Action" column.
  Hidden when the row's status isn't `queued`. POSTs are
  idempotent on `status="queued"` only — clicking Send on a
  `sending`-state row returns 409.
- **Bulk Send-all-queued** action — selection-driven via the
  Part 1 list-with-bulk-actions pattern; iterates rows
  synchronously inside the request.
- **Send-test-to-me** affordance — composes a synthetic
  invitation message addressed to the signed-in operator's
  email and pushes it through their transport. Useful as an
  end-to-end verification step that the editor's Preview
  doesn't cover.
- **Transport-ready status pill** in the chrome status row:
  green "SMTP configured" when the operator has Settings
  populated, grey "Configure SMTP" linking to
  `/operator/settings` when they haven't.
- **Two new audit events:** `email.sent` (with the outbox row id,
  recipient, transport response truncation) and
  `email.send_failed` (with the outbox row id, error message).

Out (deferred):

- **Real SMTP service-account / shared mailbox** — out of scope;
  send-as-me uses the operator's own credentials per Segment 11E.
  A shared-mailbox model would be its own future segment.
- **Microsoft Graph backend.** Protocol + typed stub land in 11E;
  full Graph implementation (httpx, Entra scope grant, token
  cache) is a future segment.
- **Async / queued sending** — Part 2 dispatches synchronously
  inside the request. Async / background dispatch is a Segment
  15 concern.
- **Retries / backoff.** A failed row stays `failed`; the operator
  can reset / re-queue it manually. Retry logic is a Segment 15
  concern.

### Proposed PR sequence (Part 2)

**PR F — Schema + dispatch helper + per-row Send + test-send + chrome pill.**
Lands:
- The outbox schema move (`error_message`, expanded status enum).
- `app/services/email_send_dispatch.py` (the read-row →
  build-message → call-transport → persist-result helper).
- Per-row Send button on the Manage Invitations Action column.
- Send-test-to-me affordance on the page's bulk-action bar.
- Transport-ready chrome pill.
- `email.sent` / `email.send_failed` audit events.

No bulk yet — every queued row goes one at a time.

**PR G — Bulk Send-all-queued.** Adds the selection-driven bulk
action on top of the Part 1 list-with-bulk-actions pattern.
Iterates rows synchronously inside the request. For a
200-reviewer session this is on the edge of acceptable request
latency; if it bites, async dispatch is its own future PR. Note
this in the PR G description.

Folding F + G into one PR is fine if the bulk handler is small;
keeping them split protects rollback if bulk semantics need
reshuffling.

### Implementation pointers (Part 2)

- **Transport dispatch.** Keep the dispatch helper *thin*:
  - Read row → build `EmailMessage` → call `transport.send(msg)` →
    persist result. No retries, no exponential backoff in this
    segment.
  - Bulk Send iterates rows synchronously inside the request.
    Note the latency caveat in PR G's description.
  - Per-row Send POSTs are idempotent on `status="queued"` only
    — clicking Send on a `sending`-state row returns 409. The
    list-with-bulk-actions UI hides the per-row button when the
    row isn't queued.
- **Transport-ready pill.** Computed once per page load from the
  signed-in operator's `EmailSettings`; cached on the request if
  the chrome partial reads it on multiple pages. The pill links
  to `/operator/settings` when grey.
- **`error_message` truncation.** Cap stored `error_message` at
  a sensible length (e.g. 4 KB) so a verbose stack trace from a
  transport library doesn't bloat the column. The audit event's
  `transport_response` is similarly truncated.
- **Status enum widening on SQLite.** `status` is a string column
  today; the widening is a service-layer constant change with no
  Alembic constraint to update. Tests pin the new values.

### Test impact (Part 2)

PR F adds:
- `tests/integration/test_email_send_dispatch.py` — per-row Send,
  Send-test-to-me, "no transport configured" refusal, audit
  events emitted on success and failure, Manage Invitations
  table re-renders with the row in its new status post-Send.
- `tests/unit/test_email_send_dispatch.py` — outbox row state
  transitions (queued → sending → sent / failed); `error_message`
  populated on transport failure; idempotency of per-row Send.
- An Alembic round-trip test gains the new outbox column
  (`error_message`).

PR G adds bulk-Send coverage to the integration test file
(selection-driven bulk action over a mix of queued / non-queued
rows; non-queued rows are skipped, not 409'd, when reached via
the bulk path).
