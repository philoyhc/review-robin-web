# Segment 11C — Operations consolidation (Invitations + Responses) + outbox audit-log scaffolding

Stub. Implementation plan for consolidating the running-session
Operations work per `spec/operations_renew.md`. Sibling to
Segment 11B (Session Home rebuild); both pull forward the
operator-facing work originally bucketed in Segment 11A's #21
sweep.

This segment splits into **two parts**:

- **Part 1 — Consolidation.** Bring the running-session operator
  surfaces onto the right pages with the list-with-bulk-actions
  pattern and a single consolidated Manage Invitations table.
  No new send semantics — outbox rows continue to land at
  `status="queued"` exactly as they do today.
- **Part 2 — Outbox audit-log scaffolding (truncated).** Land the
  `email_outbox` columns + status / kind value-set widening that
  *all four* transport options in `spec/email_infra_options.md`
  will need (`error_message`, `from_address`, `backend`,
  `backend_message_id`, `delivered_at`, `payload_hash`,
  `correlation_id`; status enum widened to
  `{queued, sending, sent, failed}`; kind enum widened to include
  `responses_received`). **No wiring, no UI, no service-layer
  reads** — the columns sit inert until **Segment 14-1**
  (`guide/segment_14-1_email_infra.md`) lights up the actual send
  paths against this stable schema.

The original Part 2 scope (per-row Send, bulk-Send, Send-test-to-
me, the transport-ready chrome pill, the dispatch helper, the
audit events, and the responses-received submit-time enqueue) all
move to **Segment 14-1 Part A**; this guide retains only the
schema piece because it's coupled to the existing Outbox
schema-slice work Part 1 already touched, and shipping the
columns now decouples the wiring PRs from any Alembic churn.

The two parts ship independently. Part 1 already shipped (see
Status); Part 2 is unblocked once a small migration + model edit
PR is convenient to land. **14-1 hard-depends on Part 2's
schema** (the wiring there populates these columns) but not on
the order of any other 11C work.

The functional spec is **`spec/operations_renew.md`** for Part 1;
**`spec/email_infra_options.md`** is the spec for the broader
transport landscape Part 2's columns prepare for. The page
taxonomy + per-page contract summaries are in
**`spec/operator_ui_concept.md`** §5 and "Per-page contracts".
This guide is the implementation plan; reference those specs for
detail.

## Status

**Segment fully shipped.** **Part 1 shipped 2026-05-06** across
PRs **#490 → #491 → #492 → #493** (folded from the planned 5 PRs
into 4 — see "Proposed PR sequence (Part 1)" below for what
landed where). **Part 2 shipped 2026-05-07** in **PR #541** (PR
F: outbox audit-log scaffolding — Migration `c4f6a8b0d2e5` adds
the seven nullable audit-log columns + `correlation_id` index;
`EMAIL_OUTBOX_STATUSES` / `EMAIL_OUTBOX_KINDS` constants pin the
canonical value sets at the service layer; new
`tests/integration/test_email_outbox_schema.py` round-trips every
new column on both SQLite and the `ci-postgres` dialect). The
wiring formerly planned here moved to **Segment 14-1** (see
`guide/segment_14-1_email_infra.md`); the columns sit inert until
that segment lights up the actual send paths against this stable
schema.

## Gap against the spec

| Spec requirement | Current state | Action | Part |
|---|---|---|---|
| Invitations is reviewer-centric, list-with-bulk-actions | Old "Manage invitations" page: 3-count summary card + table; no bulk selection / no filters; reminders live on a separate Monitoring page | Rewrite | 1 |
| Responses page exists | Doesn't exist | New template + route | 1 |
| Operations row: Validate / Preview / Invitations / Responses | Validate / Preview / Invitations / Monitoring (no Responses tab) | Add Responses tab; remove Monitoring. Outbox stays *outside* the chrome — reachable from a "View outbox" button on Manage Invitations only (it's a dev-diagnostic surface, not part of day-to-day Operations). | 1 |
| Monitoring URL preserved as redirect | 404s if removed cleanly | Add 303 redirect handler | 1 |
| Shared reminder send-path | Each call site composes its own send | Extract single helper; per-row, bulk-from-Invitations, bulk-from-Responses, drill-in-from-either all call it | 1 |
| List-with-bulk-actions pattern shared | New pattern for both pages | Implement once; both pages instantiate | 1 |
| Outbox carries CC / BCC at queue time | `email_outbox` has only `to_email` | Add `cc_emails` / `bcc_emails` (populated from 11E override JSON) | 1 |
| Outbox audit-log columns the spec's "Future-target additions" lists | Today's `email_outbox` lacks `error_message` + the future-target columns; status enum is `{queued, sent}`; kind set excludes `responses_received` | Add the columns nullable; widen the status / kind value-sets at the service layer. Inert scaffolding — populated by 14-1's wiring | 2 |
| Operator can Send / bulk-Send / test-Send from Invitations | No such affordances exist | **Moved to Segment 14-1 Part A**, which will hang the per-row + bulk + test-send affordances off the consolidated Manage Invitations table Part 1 ships | — |
| Transport-ready chrome pill | None | **Moved to Segment 14-1 Part A** | — |
| Reviewer-submit enqueues a responses-received outbox row when the per-session toggle is on | Submit handler doesn't enqueue anything for responses-received | **Moved to Segment 14-1 Part A** (reads the `responses_received_enabled` flag + calls `render_responses_received` — both shipped by Segment 11E PR 6) | — |

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

  All five data cells (Email Status / Email Sent / Review Progress /
  Required Fields / Last reminder) render their contents inside a
  `<span class="pill ...">`, not as plain text — the table reads as a
  sparkline of state at a glance rather than a wall of timestamps and
  parentheticals. Pill class follows the existing convention:
  `pill-count` for "good" / "filled" states (timestamp present, all
  required filled, `submitted`); `pill-empty` for "absent" / "not yet"
  states (`—`, `not started`, `in progress`, partial required, etc.).

- Add the **Responses** Operations row tab to `session_top_nav.html`
  in the position established by `spec/operator_ui_concept.md`:
  `Validate / Preview / Invitations / Responses`.
- The **Outbox** page (`session_outbox.html`) stays **out of the
  chrome** — it's a dev-diagnostic surface, not a day-to-day
  Operations tab. Reachable from a "View outbox" button on the
  consolidated Manage Invitations page only.
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

> **What shipped (2026-05-06).** 4 PRs:
> - **#490** — chrome only (Outbox tab restored). Subset of PR A.
> - **#491** — PR C + PR C-schema folded.
> - **#492** — PR D + PR E + the `/monitoring` redirect half of PR A folded; the redirect was deferred from #490 to here so operators didn't lose access to per-reviewer progress + bulk reminders in the window between Monitoring retirement and the Manage Invitations rewrite landing.
> - **#493** — follow-up beyond the original plan: dropped the Outbox tab from chrome (Outbox is dev-diagnostic, not day-to-day) and pillified the five Manage Invitations data cells.
>
> PR B (list-with-bulk-actions partial extraction) collapsed to a no-op — the shared reminder send-path was already converged on `invitations.send_reminder` / `send_reminders_to_incomplete`, and the user steered toward inlining the table pattern in PR C rather than pre-extracting (CLAUDE.md: "Don't add abstractions beyond what the task requires").

**PR A — `/monitoring` redirect + chrome update.** Foundation: add
the `/sessions/{id}/monitoring` → `/sessions/{id}/invitations` 303
redirect; update `session_top_nav.html` `_ops_pages` to add
"Responses" before the new page exists (the Responses tab would
404 if clicked, but later PRs land it quickly). Or sequence the
chrome change to land alongside PR B / C — TBD when the work
starts. (The Outbox page does **not** get a chrome tab — it stays
reachable via the "View outbox" button on Manage Invitations.)

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
- **Outbox stays unlisted in chrome.** The page itself is already
  on v2 (PR #366); the canonical entry point is the "View outbox"
  button on Manage Invitations. Operators don't need it for
  routine work — it's a dev-diagnostic / pilot-debugging surface.

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

## Part 2 — Outbox audit-log scaffolding

**Truncated from the original Send-activation scope.** This part
ships only the schema piece — the columns and value-set widening
that all four transport options in `spec/email_infra_options.md`
will need to write at send time. **No wiring, no UI, no
service-layer reads** — the new columns sit inert until **Segment
14-1 Part A** lights up the actual send paths against this
stable schema.

The trade is deliberate: shipping the schema move now decouples
the wiring PRs in 14-1 from any Alembic churn, and makes any of
the four transports (SMTP / Graph / ACS / third-party) a scoped
backend swap rather than a coupled schema + backend + UI change.

Hard prerequisites:

- **Part 1 PR C-schema** already shipped `cc_emails` /
  `bcc_emails` populated at queue time (Migration `b3d5e7f9a1c4`).
  Part 2 piles onto the same model file.
- No transport-layer prerequisites — Part 2 doesn't touch
  `EmailTransport` or `email_send.py`.

### Scope (Part 2)

In:

- **Outbox model + migration.** Add the following nullable
  columns to `email_outbox`, sourced from the spec's "Future-
  target additions" table (`spec/email_infra_options.md`
  "Audit log"):

  | Column | Type | Notes |
  |---|---|---|
  | `error_message` | `Text` (nullable) | Captured on failure. The 14-1 dispatch helper writes truncated transport errors here so the Outbox / Manage Invitations diagnostic surfaces can render them. |
  | `from_address` | `String(320)` (nullable) | The address actually sent from. Useful when comparing operator-set and deployment-default identities. |
  | `backend` | `String(32)` (nullable) | Which `EmailTransport` implementation handled the send (`smtp` / `graph` / `acs` / `thirdparty:sendgrid` / etc.). |
  | `backend_message_id` | `String(255)` (nullable) | The backend's identifier for the message, if any (Graph operation ID, ACS operation ID, third-party message ID, SMTP server queue ID). |
  | `delivered_at` | `DateTime(timezone=True)` (nullable) | When delivery confirmed (if backend reports — primarily Graph / ACS / third-party; SMTP typically doesn't populate this). |
  | `payload_hash` | `String(64)` (nullable) | Hash of `(to, subject, body)` for dedup detection. |
  | `correlation_id` | `String(128)` (nullable, indexed) | The app's deterministic identifier for "this send to this recipient at this intent" — `invitation:{session_id}:{reviewer_id}` / `reminder:{session_id}:{reviewer_id}:{n}` / `responses_received:{session_id}:{reviewer_id}:{submit_id}`. Mechanism for idempotent retry; populated by 14-1's enqueue path. Indexed because the dispatch helper looks rows up by it on retry. |

  All fields nullable on the existing rows so the migration is
  pure additive — no backfill, no defaults beyond the column
  defaults the model carries.

- **Status value-set widening.** `status` is a string column
  (no Alembic constraint to update); the canonical value set is
  documented at the service layer. New constant
  `EMAIL_OUTBOX_STATUSES = ("queued", "sending", "sent",
  "failed")` in `app/db/models/email_outbox.py` (or a sibling
  module) replaces the implicit two-value set. Service-layer
  consumers in 14-1 enforce the set; today's code only writes
  `"queued"` / `"sent"` and continues to do so.
- **Kind value-set widening.** Same pattern for `kind`:
  `EMAIL_OUTBOX_KINDS = ("invitation", "reminder",
  "responses_received")` — `responses_received` is the new
  member, written by 14-1 Part A's submit-time enqueue (formerly
  PR H of the original Part 2 scope). Today's code only writes
  `"invitation"` / `"reminder"`.
- **Module + column docstrings.** The `EmailOutbox` class
  docstring is updated to reflect the broader audit-log role and
  to point at `spec/email_infra_options.md` for the field
  semantics. Each new column gets a one-line comment.

Out (deferred to Segment 14-1 Part A):

- **`email_send_dispatch.py` helper** — read-row →
  build-`EmailMessage` → call-`transport.send` → persist-result.
  The first consumer of these new columns lives there.
- **Per-row Send button + bulk-Send + Send-test-to-me** on the
  consolidated Manage Invitations page.
- **Transport-ready chrome pill.**
- **`email.sent` / `email.send_failed` audit events** — emitted
  from the dispatch helper.
- **Reviewer-submit responses-received enqueue** + the
  `responses_received_email.queued` audit event.
- **`correlation_id` generation strategy.** The column lands here;
  the deterministic generation logic + idempotent-retry checks
  live in 14-1.
- **Bulk-send queue / worker.** Async dispatch is a 14-1 Part C
  concern.
- **Per-deployment from-identity defaults.** Env-var-backed
  deployment defaults supplementing per-operator settings — 14-1
  Part D.
- **Backends beyond SMTP** — 14-1 Parts F / G / H (Options B / C /
  D from the spec).

### Proposed PR sequence (Part 2)

**PR F — Outbox audit-log scaffolding.** Single PR.

- Alembic migration: add the seven nullable columns + the
  `correlation_id` index.
- `app/db/models/email_outbox.py`: add the `Mapped[X | None]`
  declarations + the `EMAIL_OUTBOX_STATUSES` /
  `EMAIL_OUTBOX_KINDS` constants. Update the class docstring +
  per-column comments.
- Tests:
  - `tests/integration/test_email_outbox_schema.py` (new) —
    persists every new column round-trip; the Alembic round-trip
    test in the dialect-agnostic suite picks up the new columns
    automatically.
  - A unit test on the canonical value-set constants pinning
    membership (so any future widening is a deliberate change).

No service-layer code reads or writes the new columns yet. The
existing invitation / reminder enqueue paths continue to write
`status="queued"`, `cc_emails` / `bcc_emails` from the editor
JSON, and nothing else.

### Implementation pointers (Part 2)

- **Pure additive migration.** All columns nullable; no defaults
  beyond column defaults; no backfill. Existing rows keep their
  current shape — the new columns just sit `NULL` until 14-1's
  dispatch helper writes to them.
- **`correlation_id` index.** Because the dispatch helper in
  14-1 will look up rows by `correlation_id` on idempotent retry,
  index the column at scaffolding time. SQLite + Postgres both
  honour the index with no extra ceremony.
- **Don't pre-emit constants from 14-1 here.** The
  `EMAIL_OUTBOX_STATUSES` constant is the value-set
  documentation, not the dispatch state machine. The state-
  transition rules ("`queued → sending → sent | failed`",
  per-row Send POST 409s on non-`queued`, etc.) belong in 14-1's
  dispatch helper — they're behaviour, not schema.
- **Status enum widening on SQLite.** `status` stays a `String`
  column; SQLite has no `ENUM` type to widen. Any future
  Postgres-only constraint widening lives with the dialect-
  specific work in Segment 14.

### Test impact (Part 2)

- One new test file —
  `tests/integration/test_email_outbox_schema.py` — covering the
  round-trip on each new column.
- The dialect-agnostic Alembic round-trip test (`ci-postgres`
  workflow's migrate-and-compare) picks up the new columns
  automatically.
- No churn on existing tests; the existing enqueue paths don't
  populate the new columns.
