# Segment 11C — Operations consolidation (Invitations + Responses) + email send activation

Stub. Implementation plan for consolidating the running-session
Operations work per `spec/operations_renew.md`. Sibling to
Segment 11B (Session Home rebuild); both pull forward the
operator-facing work originally bucketed in Segment 11A's #21
sweep.

**Also picks up the send-activation half of Segment 11E's email
work** — 11E ships the editor, the operator Settings page, and the
SMTP transport interface in a "ready but unwired" state; 11C wires
that interface to per-row + bulk Send and test-send affordances on
the consolidated Manage Invitations page so outbox rows actually
transition from `queued` to `sent` / `failed`.

The functional spec is **`spec/operations_renew.md`**. The page
taxonomy + per-page contract summaries are in
**`spec/operator_ui_concept.md`** §5 and "Per-page contracts".
This guide is the implementation plan; reference those specs for
detail.

## Status

Planning. Sized as **~6 PRs** to land in dependency order (5
operations-consolidation PRs already specced + 1 send-activation
PR added on top); each independently shippable.

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
- **Wire the Segment 11E SMTP transport** into the Manage Invitations
  page:
  - Per-row Send button on each invitation row (transitions a
    `queued` outbox row into a real send via the operator's
    configured `EmailTransport`).
  - Bulk Send-all-queued action (selection-driven via the
    list-with-bulk-actions pattern PR B ships).
  - Per-page "Send test to me" affordance — composes a synthetic
    invitation message addressed to the signed-in operator's
    email and pushes it through their transport. Useful as an
    end-to-end verification step that the editor's Preview
    doesn't cover.
  - Transport-ready status pill in the chrome status row: green
    "SMTP configured" when the operator has Settings populated,
    grey "Configure SMTP" linking to `/operator/settings` when
    they haven't.
- **Outbox schema additions** to support the new send semantics:
  - `error_message: Mapped[str | None]` (Text) on `email_outbox` —
    captured when a send fails so the Outbox page can surface the
    reason.
  - `status` enum extended from `{queued, sent}` to
    `{queued, sending, sent, failed}` (string column today; service-
    layer enforces the value set).
  - `cc_emails` / `bcc_emails` (Text — comma-separated) on
    `email_outbox`. Populated from the editor's CC / BCC override
    JSON (already stored in 11E) at queue time.
- **Two new audit events:** `email.sent` (with the outbox row id,
  recipient, transport response truncation) and `email.send_failed`
  (with the outbox row id, error message).

Out:

- Operator-configurable "at-risk" thresholds on Responses. Land
  with app-default constants in one place; future enhancement.
- Live updating / auto-refresh — pages render snapshot data; a
  manual refresh affordance is the budget for this segment.
- Reading individual response content from these pages (that's the
  Extract Data flow, Segment 12 / 12A).
- Microsoft Graph backend. Segment 11E lands the typed stub; the
  full implementation (httpx against `/me/sendMail`, Entra
  `Mail.Send` scope grant, token cache) is its own future segment.
- Per-reviewer / per-cohort body customization. Stays at session
  level via the editor's overrides; per-cohort would be a future
  enhancement on top.

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

**PR F — Email send activation.** Hard prerequisite: Segment 11E
ships first (the editor, the operator Settings page, and
`app/services/email_send.py`'s `EmailTransport` Protocol +
`SmtpEmailTransport`). PR F:

- Adds the outbox schema columns described in Scope (`error_message`,
  expanded `status`, `cc_emails` / `bcc_emails`).
- Wires `transport_for(settings)` from 11E into a new
  `app/services/email_send_dispatch.py` that:
  - Reads a queued outbox row, builds an `EmailMessage` from it,
    invokes the operator's `EmailTransport.send(...)`, and writes
    back the result (`sent` / `failed` + `error_message`).
  - Refuses to dispatch if the initiating operator has no
    `EmailSettings` configured — surfaces an inline error rather
    than silently leaving the row queued.
- Adds the per-row Send + bulk Send-all-queued + Send-test-to-me
  affordances on the rebuilt Manage Invitations page (PR C
  framework).
- Adds the transport-ready chrome pill.
- Emits `email.sent` / `email.send_failed` audit events.

PR ordering can fold (e.g., A + B together, or D + E) depending on
risk appetite once implementation starts. **PR F sequencing**:
land it after PR C at the earliest (it consumes PR C's Manage
Invitations rebuild); 11E PRs 4 + 5 (Settings page + transport
interface) must already be merged. Folding F into D or E isn't
recommended — they touch different surfaces.

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
- **PR F transport dispatch.** Keep the dispatch helper *thin*:
  - Read row → build `EmailMessage` → call `transport.send(msg)` →
    persist result. No retries, no exponential backoff in this
    segment; a failed row stays `failed` and the operator can
    reset / re-queue it manually. Retry logic is a Segment 15
    concern.
  - Bulk Send iterates rows synchronously inside the request. For
    a 200-reviewer session this is on the edge of acceptable
    request latency; if it bites, async dispatch is its own
    future PR. Note in the PR F description.
  - Per-row Send POSTs are idempotent on `status="queued"` only
    — clicking Send on a `sending`-state row returns 409. The
    list-with-bulk-actions UI hides the per-row button when the
    row isn't queued.
- **PR F transport-ready pill.** Computed once per page load from
  the signed-in operator's `EmailSettings`; cached on the request
  if the chrome partial reads it on multiple pages. The pill links
  to `/operator/settings` when grey.

## Out of scope (cross-references)

- **Real SMTP service-account / shared mailbox** — out of scope;
  send-as-me uses the operator's own credentials per Segment 11E.
  A shared-mailbox model would be its own future segment.
- **Microsoft Graph backend.** Protocol + typed stub land in 11E;
  full Graph implementation (httpx, Entra scope grant, token
  cache) is a future segment.
- **Async / queued sending** — PR F dispatches synchronously inside
  the request. Async / background dispatch is a Segment 15 concern.
- **Reading response content / extraction** — Segment 12 / 12A.
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

PR F adds new tests:
- `tests/integration/test_email_send_dispatch.py` — per-row Send,
  bulk Send-all-queued, Send-test-to-me, "no transport configured"
  refusal, audit events emitted on success and failure.
- `tests/unit/test_email_send_dispatch.py` — outbox row state
  transitions (queued → sending → sent / failed); `error_message`
  populated on transport failure; idempotency of per-row Send.
- An Alembic round-trip test gains the new outbox columns
  (`error_message`, `cc_emails`, `bcc_emails`).
