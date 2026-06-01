# Segment 14B — Email infrastructure (send activation + backends)

> **Carved out of the original Segment 14 family (2026-05-11).**
> Renamed from `segment_14-1_email_infra.md`. Production
> hardening proper lives in **14A**
> (`guide/archive/segment_14A_production_hardening.md`); reminder
> cadence + auto-scheduled reminders live in **Segment 18G
> Part 3** (`guide/archive/segment_18G_scheduled_events.md`) — the
> former Segment 14C, consolidated into 18G on 2026-05-18.

The home for **all email *wiring* work** absorbed from the
formerly-broader Segment 11C Part 2. Per
`spec/email_infra_options.md`, the app's invitation, reminder,
and notification paths depend on a single internal interface
(`EmailTransport`) that one of several backend implementations
fulfills; this segment lights up the call sites and the
backends.

The functional spec is **`spec/email_infra_options.md`**. The
template-authoring side already shipped (Segment 11E,
`guide/archive/segment_11E_email_template_editor.md`) and the
audit-log column scaffolding shipped in **Segment 11C Part 2**
(PR #541, 2026-05-07 — Migration `c4f6a8b0d2e5`; plan archived at
`guide/archive/segment_11C_operations_consolidation.md`). With
those in place, this segment is "everything else email-related"
up to and including the downstream backend implementations
(Options B / C / D).

This file is a stub: each Part below names the absorbed scope at
sketch level. Detailed PR breakdowns get drafted at the time the
work starts.

## Status

**Planning.** Hard prerequisites:

- ✅ `EmailTransport` Protocol + `SmtpEmailTransport` +
  `transport_for(settings)` factory — Segment 11E PR 5.
- ✅ Operator credential storage + `/operator/settings` page —
  Segment 11E PRs 4 / 6.
- ✅ Editor-side template authoring (invitation / reminder /
  responses-received subject + body + cc + bcc + the per-session
  `responses_received_enabled` toggle) — Segment 11E.
- ✅ Consolidated Manage Invitations + Responses pages with the
  list-with-bulk-actions pattern — Segment 11C Part 1.
- ✅ **Outbox audit-log column scaffolding** — Segment 11C Part 2
  (PR #541, 2026-05-07). Hard prerequisite for **Part A
  specifically** because Part A is the first call site that
  populates `error_message` / `correlation_id` / etc. Parts B+
  build on Part A.

Sized as **multiple Parts**, sketched below. Parts A → B → C →
D → E land in dependency order; Parts F → H are independent
backend swaps and ship as deployment demand dictates.

## Why a separate segment

The original Segment 11C Part 2 plan bundled three things:

1. The schema move (`error_message` + status enum widening +
   future-target columns).
2. The wiring (per-row Send button, dispatch helper, audit
   events, responses-received submit-time enqueue).
3. The implicit expectation that everything sits inside 11C,
   which is "Operations consolidation" — a UI segment, not a
   backend one.

Re-cutting along the schema / wiring / backend axis:

- **Schema** (#1) stays in 11C because it's coupled to 11C Part
  1's Outbox slice work; one Alembic file, one model edit.
- **Wiring + backends** (#2 + #3 + Options B / C / D from the
  spec) all land here because they share a transport
  abstraction, a dispatch helper, an audit-log read shape, and
  an operator-visible diagnostic surface — none of which is
  "consolidating Operations pages".

The truncated 11C ships fast (one migration + model edit). 14B
ships at its own pace, gated on deployment demand for each
backend.

## Parts

### Part A — SMTP send activation

**Goal.** Light up the existing per-operator SMTP path. Outbox
rows with `kind` ∈ {`invitation`, `reminder`, `responses_received`}
that 14B enqueues actually go out via the operator's configured
`SmtpEmailTransport`; failures land in the new
`error_message` column.

**Absorbed scope (formerly 11C Part 2 PRs F + G + H):**

- `app/services/email_send_dispatch.py` — read-row →
  build-`EmailMessage` → call-`transport.send` → persist-result
  helper. Refuses to dispatch when the initiating operator has
  no `EmailSettings` configured. Truncates the transport
  response into the audit-event detail.
- **Per-row Send button** on each invitation row of the
  consolidated Manage Invitations table — slots into the
  existing "Action" column. POSTs idempotent on
  `status="queued"` only; non-`queued` returns 409.
- **Bulk Send-all-queued** — selection-driven via the Part 1
  list-with-bulk-actions pattern; iterates rows synchronously
  inside the request. Async dispatch waits for Part C.
- **Send-test-to-me** affordance — composes a synthetic
  invitation addressed to the signed-in operator's email and
  pushes it through their transport. End-to-end verification
  the editor's Preview can't cover.
- **Transport-ready chrome pill** — green "SMTP configured"
  when the operator has Settings populated, grey "Configure
  SMTP" linking to `/operator/settings` when they haven't.
  Computed once per page load from the signed-in operator's
  `EmailSettings`.
- **Two new audit events:** `email.sent` (with the outbox row
  id, recipient, transport response truncation) and
  `email.send_failed` (with the outbox row id, error message).
- **Reviewer-submit responses-received enqueue.** When the
  reviewer-submit handler stamps `submitted_at`, it reads
  `email_templates.responses_received_enabled(session)` (Segment
  11E PR 6's helper); when `True` (the default), enqueues a
  single `email_outbox` row with `kind="responses_received"`,
  populated by `render_responses_received` (also 11E PR 6).
  Per-reviewer-per-session, not per-assignment. Emits
  `responses_received_email.queued` audit event with
  `{"reviewer_id": <int>, "assignment_count": <int>}`.

**Sketched PRs:**

- **PR A1 — Dispatch helper + per-row Send + Send-test-to-me +
  chrome pill + audit events.** The schema-stable wiring;
  populates the `error_message` / `from_address` / `backend` /
  `backend_message_id` / `delivered_at` columns 11C Part 2
  scaffolds. No bulk yet.
- **PR A2 — Bulk Send-all-queued.** Synchronous iteration over
  selected queued rows. The latency caveat for 200-reviewer
  sessions is acknowledged here (Part C is the async escape
  hatch).
- **PR A3 — Responses-received submit-time enqueue.** The
  `responses_received_email.queued` audit event lands here.

PR A1 + A2 can fold if the bulk handler stays small;
keeping them split protects rollback if bulk semantics need
reshuffling.

**Hard dependency:** Segment 11C Part 2 (the schema columns) —
✅ shipped.

### Part B — `correlation_id` strategy + idempotent retry

**Goal.** Generate deterministic `correlation_id` values on
enqueue; the dispatch helper checks existing rows on retry.

Ships:

- `correlation_id` populated on every enqueue across invitation
  / reminder / responses-received paths. Format examples in the
  spec: `invitation:{session_id}:{reviewer_id}` /
  `reminder:{session_id}:{reviewer_id}:{n}` /
  `responses_received:{session_id}:{reviewer_id}:{submit_id}`.
- Dispatch helper: when re-asked to send a `correlation_id`
  whose existing row is `sent`, skip; whose existing row is
  `queued`, retry; whose existing row is `failed`, retry.
- Tests pinning crash-mid-send safety: a `queued` row that the
  dispatcher restarts re-uses the same `correlation_id`.

**Hard dependency:** Part A.

### Part C — Bulk-send queue + background worker

**Goal.** Replace synchronous bulk dispatch with a queue +
worker pattern so a 200-reviewer Send-all doesn't block the
operator's request.

Ships:

- A queue mechanism (Azure Storage Queue, or a similar managed
  queue; choice doc'd at the time).
- A worker process consuming the queue and calling
  `EmailTransport.send()` per row.
- The bulk action enqueues N individual send jobs; UI returns
  "scheduled" immediately and polls the audit log for progress.
- Operator UI: a progress affordance on Manage Invitations
  showing the in-flight batch.

**Hard dependency:** Part A. Doesn't depend on B but pairs
naturally with idempotent retry.

### Part D — Per-deployment from-identity defaults

**Goal.** Some backends (ACS, third-party transactional) don't
naturally have per-operator credentials. Per-deployment defaults
land as env-var-backed configuration loaded at startup, used
when the operator's settings are blank or when the active
backend is intrinsically deployment-scoped.

Ships:

- Env var schema + `pydantic-settings` model for deployment
  defaults.
- `transport_for(settings)` extension to fall back to deployment
  defaults when per-operator settings are missing for the active
  backend.
- Documentation on which envs are required per backend.

**Hard dependency:** None on A/B/C, but lands before any
Option-B-or-later backend ships.

### Part E — Generalised Outbox diagnostic surface

**Goal.** The existing dev-mode Outbox page becomes the
operator-facing audit-log surface, reading the new columns
(`error_message`, `from_address`, `backend`,
`backend_message_id`, `delivered_at`, `payload_hash`,
`correlation_id`) regardless of which transport handled the row.

Ships:

- Outbox page rebuild reading the audit log generically.
- Per-row drill-in showing the transport response, the
  correlation chain (related rows by `correlation_id`), and
  delivery status.
- Cross-reference from Manage Invitations + Responses pages.

**Hard dependency:** Part A populates the columns; Part E
surfaces them.

### Part F — Option B (Microsoft Graph application permission)

Per `spec/email_infra_options.md` "Option B".

Ships:

- `GraphEmailTransport.send()` body — replaces 11E's
  `NotImplementedError` placeholder. MSAL token acquisition +
  `POST /users/{mailbox}/sendMail`.
- Token cache (per-process; refreshes on expiry).
- Mapping from `EmailMessage` to Graph's `Message` JSON.
- Error mapping: Graph error codes → `SendResult.error_message`
  + truncated `transport_response`.
- New env vars: `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`,
  `GRAPH_CLIENT_SECRET` (Key Vault), `GRAPH_SENDER_MAILBOX`.
- New runtime dependency: `msal` (+ `httpx` if not already
  promoted from dev to runtime).

**Hard dependencies:** Part A (so the dispatch helper exists)
and Part D (for the per-deployment env vars). Institution-side
prerequisites (app registration, Application Access Policy,
admin consent) are out of scope for the code work but the PR
description should link the deployment runbook entry.

### Part G — Option C (Azure Communication Services)

Per `spec/email_infra_options.md` "Option C".

Ships:

- New `AcsEmailTransport` class implementing the
  `EmailTransport` Protocol.
- ACS SDK (`azure-communication-email`) integration.
- Mapping from `EmailMessage` to ACS message format.
- Async-by-default delivery: the SDK returns an operation poll
  handle; the transport polls until terminal. Captured in
  `backend_message_id` / `delivered_at`.
- New env vars: `ACS_CONNECTION_STRING` (Key Vault),
  `ACS_SENDER_ADDRESS`.
- New runtime dependency: `azure-communication-email`.

**Hard dependencies:** Part A + Part D. Azure-side
prerequisites (ACS resource provisioned, Email Communication
Services resource linked, sending domain verified) are
deployment runbook items.

### Part H — Option D (third-party transactional)

Per `spec/email_infra_options.md` "Option D".

Ships:

- One concrete `ThirdPartyApiEmailTransport` per provider
  supported (or a generic transport parameterised by provider —
  the choice depends on which providers a deployment commits
  to).
- Provider SDK / API integration (`httpx` for direct API calls
  is the simplest path; some providers ship Python SDKs).
- Error mapping per provider.
- New env vars: `THIRDPARTY_PROVIDER`, `THIRDPARTY_API_KEY`
  (Key Vault), `THIRDPARTY_SENDER_ADDRESS`.

**Hard dependencies:** Part A + Part D. Recommendation per the
spec: pick one provider (likely SendGrid given Azure
marketplace integration) rather than supporting "any third
party".

## What's *not* in this segment

- **Reading inbound bounce / delivery webhooks.** Provider-side
  webhook plumbing for delivery confirmation, suppression list
  updates, etc. — useful future enhancement, separate scope.
- **Reading reviewer replies.** The reply-to header points at
  the operator's regular inbox; the app doesn't process replies.
- **Multi-backend simultaneous operation.** One backend per
  deployment; Parts F / G / H are deployment-time picks, not
  runtime-switchable.
- **Per-cohort body customization.** Stays at session level via
  the editor's overrides; per-cohort would be a future
  enhancement on the editor side.
- **Auto-scheduled reminder cadence.** When and how often to
  enqueue reminders for incomplete reviewers (cadence policy /
  time-of-day / per-reviewer dedup) lives in **Segment 18G
  Part 3** (the former Segment 14C). 14B's Part A enqueues the
  `kind="reminder"` rows on operator-triggered Send today;
  18G Part 3 is the scheduler that fires them automatically.

## Doc impact

When parts ship:

- Each Part's PR description names which spec items in
  `spec/email_infra_options.md` it lights up (the ◻ → ✅ flip in
  the spec's "Summary: what the app needs *before* any backend
  ships" checklist).
- `docs/status.md` timeline entries per Part landed.
- `guide/todo_master.md` upcoming list updated.
- `spec/email_infra_options.md` "Migration path" section steps
  (currently 1 → 6) crossed off as Parts ship; new entries
  added if a Part introduces a new architectural primitive
  (queue / worker pattern in Part C, the generalised diagnostic
  surface in Part E).

---

## Appendix — Participant-model email + magic-link tail (W20 / W21)

Two participant-model wiring items rest on this segment. They
previously tracked in `guide/archive/participant_model_remainder.md`;
filed here on 2026-06-01 because both are downstream of the
14B infrastructure and don't need a separate plan doc until
14B's prerequisites land.

### W20 — Reviewee / observer email notifications

Source: `guide/archive/participant_model_upgrade.md` §6.

The reviewee `/results` surface (W16, shipped) needs two
outbound emails:

- **Results-ready notice** — fires when the operator opens
  the after-release window (`responses_release_at` reached;
  the W14 anchor). Recipient: reviewee. Identification mode:
  email (reviewee must satisfy `is_email_identified` — the W8
  Validate warning surfaces non-deliverable identifiers up
  front).
- **Acknowledgement nudge** — fires N days after Results-
  ready when `reviewees.results_acknowledged_at` is still
  NULL. Cadence TBD; one or two nudges seems right.

Observer-side equivalents land at the same time (collation
surface W17, also tracked below in the Observers stub).

**Depends on:** 14B Part A (`email_outbox` writes against
`kind="reviewee_results_ready"` / `kind="reviewee_results_nudge"`
allowlist additions) + 14B Part D (templates in the editor
with operator overrides). The auto-scheduling cadence for
the nudge piggybacks on 18G Part 3's scheduler.

### W21 — Magic-link landing for reviewees / observers

Source: `guide/archive/participant_model_upgrade.md` §4.

Today the `invitations` table is **reviewer-keyed** — one row
per reviewer, with a token used for magic-link sign-in. The
participant-model upgrade adds two more identity types
(reviewee, observer) that need tokened landings too: an
emailed link in W20's notices that drops the recipient
directly onto their `/me/sessions/{id}/results` or
`/me/sessions/{id}/collation` page.

Three shapes for extending `invitations`:

1. **Polymorphic FK** — one `participant_type` discriminator
   column + nullable FKs (`reviewer_id` / `reviewee_id` /
   `observer_id`). Single table; one of the three FKs is
   non-null per row.
2. **Sibling tables** — `reviewee_invitations` +
   `observer_invitations` paralleling the existing
   `invitations` (which stays reviewer-only). More joins on
   token-lookup, simpler schema per row.
3. **Token-only discriminator** — one row per token, no FK;
   the token itself carries the participant identity. Most
   flexible but loses referential integrity.

**Design call pending.** No active implementation work on W21
until the shape is picked — the magic-link landing handler
+ the email-side embedding both depend on it. The choice
also drives whether `email_outbox.invitation_id` stays a FK
to `invitations` or generalises.

Once the shape is picked, the landing handler reuses the
existing `/auth/magic/{token}` flow (the reviewer side); the
new shapes light up the same flow with extra cases.
