# Email sending — architecture spec

How Review Robin sends email (invitations, reminders, future
notifications) from its Azure App Service deployment.

Segment 11E ships the pluggable-sender scaffolding the rest of this
document describes — `EmailTransport` Protocol +
`SmtpEmailTransport` concrete implementation + typed-stub
`GraphEmailTransport` placeholder + per-operator
`/operator/settings` page for SMTP credentials. This document is
the longer-term architectural target: **what the app needs in
place so that adding any single email backend is a scoped piece
of work, not a re-architecture of the invitation / reminder
paths.**

## Goals

- **Pluggable senders.** The app's invitation and reminder paths
  should not know which backend actually delivers the email. They
  call a single internal interface; one of several implementations
  fulfills the call.
- **Multiple supported backends, one at a time per deployment.**
  Different deployments may use different backends (institutional
  Graph for one customer, ACS for another, third-party for a
  third). The app should not require all backends to be
  configured; it should require *one*.
- **Easy migration between backends.** Moving a deployment from,
  say, ACS to Graph should be configuration work and a backend
  swap, not a code rewrite of the sending paths.
- **Auditable, idempotent send semantics.** Every send attempt is
  recorded; retries are safe; the operator can inspect what
  happened.

## Scope

In scope:

- **Option A** — SMTP relay (the existing path shipped in
  Segment 11E PR 5, generalised for production SMTP relay use as
  well as the dev local server).
- **Option B** — Microsoft Graph API with application permission
  (`Mail.Send`), scoped to a shared mailbox via Application Access
  Policy.
- **Option C** — Azure Communication Services (ACS) Email.
- **Option D** — Third-party transactional email service
  (SendGrid, Mailgun, Postmark, or similar), used as the
  canonical "third-party API" example.

Not in scope:

- Microsoft Graph with delegated permissions. The operator-
  token-based send doesn't support scheduled reminders without an
  operator session, which conflicts with the app's reminder
  workflow. (Distinct from the typed-stub `GraphEmailTransport`
  in `app/services/email_send.py` — that placeholder will become
  Option B's application-permission implementation, not the
  delegated one.)
- Logic Apps as an indirection layer. Adds operational complexity
  without enough payoff for this app's scope.

## Architecture

### The sender abstraction

The core of the design is a single internal interface —
`EmailTransport` — that the app's invitation, reminder, and
notification paths depend on. All call sites use this interface;
none knows which backend is in use.

Already shipped in `app/services/email_send.py` (Segment 11E
PR 5):

```python
@dataclass(frozen=True)
class EmailMessage:
    from_addr: str
    from_display_name: str | None
    to: str
    subject: str
    body: str
    cc: list[str]
    bcc: list[str]


@dataclass(frozen=True)
class SendResult:
    ok: bool
    error_message: str | None = None
    transport_response: str | None = None  # truncated raw provider response


class EmailTransport(Protocol):
    def send(self, msg: EmailMessage) -> SendResult: ...
```

The `EmailMessage` shape is transport-agnostic — no DB types in
the contract, no `ReviewSession` / `Reviewer`. The future send
dispatcher (Segment 14B Part A) builds a message from outbox +
session + reviewer rows and hands the transport a flat object.

A `health_check() -> HealthResult` method is a reasonable future
addition for an operator-facing diagnostics surface; not on the
Protocol today.

The interface is **synchronous from the app's perspective** — the
app calls `send()` and gets a result. Whether the underlying
backend is sync or async (some, like ACS, return a request ID and
deliver asynchronously) is the implementation's concern; the
implementation waits or polls as needed before returning to the
app.

For operations that need true asynchronous behavior (sending many
emails without blocking), the app uses a queue + worker pattern
*around* the synchronous interface, not by changing the interface
itself. See "Bulk sending and queueing" below.

### Backend implementations

Each backend is a separate implementation of `EmailTransport`:

- `SmtpEmailTransport` — connects to a configured SMTP relay.
  Shipped in 11E PR 5.
- `GraphEmailTransport` — uses Microsoft Graph API. Typed stub
  shipped in 11E PR 5; the application-permission flavour is
  Option B below.
- `AcsEmailTransport` — uses Azure Communication Services. Not
  yet implemented.
- `ThirdPartyApiEmailTransport` — uses a third-party service's
  API (typically one implementation per provider, but they share
  the same Protocol). Not yet implemented.

The factory `transport_for(settings) -> EmailTransport` (in
`email_send.py`) picks the active implementation based on the
operator's `EmailSettings.transport` field at send time. Today
only `"smtp"` is reachable; the `"graph"` / `"acs"` /
`"thirdparty"` slots are reserved for the future implementations.

### Configuration

Today's configuration is **per-operator**, not per-deployment —
Segment 11E PR 4 adopted the "send-as-me" identity model with
credentials stored on the `users` table (encrypted at rest via
Fernet, key from the `SMTP_ENCRYPTION_KEY` env var). The operator
configures their own host / port / username / password / display
name on `/operator/settings`.

Per-deployment defaults are a future addition for backends that
don't naturally have a per-operator credential (Option C — ACS —
is the obvious example). The pattern that fits both today's per-
operator settings and tomorrow's per-deployment defaults:

- **Per-deployment defaults.** App-wide identity + transport
  selection, loaded from environment variables at startup. Used
  when an operator's settings are blank or when a backend is
  intrinsically deployment-scoped.
- **Per-operator overrides.** The existing `users.smtp_*` columns
  + `/operator/settings` page. Used when send-as-me semantics
  apply.
- **Per-session overrides.** Reply-to, CC / BCC live on the
  email-template editor (Segment 11E PR 2), keyed by template.

The `transport_for` factory and the future send dispatcher
reconcile these layers when picking the backend + identity for a
given send.

### Audit log

Every send attempt is recorded in a database table. This is the
central data structure that makes the email subsystem auditable,
debuggable, and idempotent.

Today's `email_outbox` table is the audit log. Its current shape
(post-Segment 9.2 + Segment 11C Part 1's `cc_emails` /
`bcc_emails` slice):

| Field | Type | Notes |
|---|---|---|
| `id` | int | Primary key. |
| `session_id` | FK | Which session this send belongs to. |
| `reviewer_id` | FK | Which reviewer (nullable for system emails). |
| `invitation_id` | FK | Which invitation row this send is for (nullable). |
| `kind` | enum | `invitation`, `reminder`; `responses_received` member added by Segment 11C Part 2. |
| `to_email` | text | The recipient. |
| `cc_emails` / `bcc_emails` | text, comma-separated | Populated from the editor's CC / BCC overrides at queue time (Segment 11C Part 1). |
| `subject` | text | The merged subject. |
| `body` | text | The merged body. |
| `status` | enum | `queued`, `sent` today; widened to `{queued, sending, sent, failed}` at the service layer by Segment 11C Part 2. |
| `created_at` | timestamp | When the row was written. |

**Segment 11C Part 2 (truncated)** lands the audit-log columns
the production send path will write at send time, as inert
schema scaffolding — no wiring, no service-layer reads. The
columns are populated by **Segment 14B Part A** when the
dispatch helper goes live:

- `error_message` (Text, nullable) — captured on failure so the
  Outbox / Manage Invitations diagnostic surfaces can render the
  reason.
- `from_address` (String 320, nullable) — the address actually
  sent from. Useful when comparing operator-set and deployment-
  default identities.
- `backend` (String 32, nullable) — which `EmailTransport`
  implementation handled the send (`smtp` / `graph` / `acs` /
  `thirdparty:sendgrid` / etc.).
- `backend_message_id` (String 255, nullable) — the backend's
  identifier for the message, if any (Graph operation ID, ACS
  operation ID, third-party message ID, SMTP server queue ID).
- `delivered_at` (timestamp, nullable) — when delivery confirmed
  (if backend reports — primarily Graph / ACS / third-party).
- `payload_hash` (String 64, nullable) — hash of `(to, subject,
  body)` for dedup detection.
- `correlation_id` (String 128, nullable, indexed) — the app's
  deterministic identifier for "this send to this recipient at
  this intent." Mechanism for idempotent retry; populated by
  14B's enqueue path.

Records are written *before* the send is attempted (status
`queued`), updated *after* with the outcome. This pattern means
crashes mid-send leave a `queued` record that can be reconciled
on next startup or by a periodic sweeper.

### Idempotency

The app's invitation and reminder paths must be safe to retry. The
audit log's `payload_hash` and `correlation_id` are the
mechanisms:

- Before sending, the app generates a deterministic
  `correlation_id` for "this specific send to this specific
  recipient at this specific intent" (e.g.,
  `invitation:{session_id}:{reviewer_id}`).
- If a record with the same `correlation_id` already exists with
  status `sent`, the send is skipped.
- If a record exists with status `queued` (probably from a
  crash), the send is *retried* with the same `correlation_id`,
  replacing the old record's outcome.
- For reminders, the `correlation_id` includes a sequence
  component (`reminder:{session_id}:{reviewer_id}:{n}`) so each
  scheduled reminder is a separate idempotent operation.

This makes the entire send pipeline crash-safe and retry-safe
without backend-specific logic.

### Bulk sending and queueing

For bulk operations (operator clicks "send invitations to all 80
selected reviewers"), the app should not block the operator's
request on 80 sequential sends. Two options:

- **Background job queue.** The bulk action enqueues 80 individual
  send jobs; a worker process consumes the queue and calls
  `EmailTransport.send()` for each. The operator's UI gets a
  "scheduled" response immediately and can poll the audit log to
  show progress.
- **Inline batch with progress.** The bulk action runs the sends
  inline but reports progress to the operator's UI in real time
  (server-sent events, websocket, or polling). Simpler but ties
  the operator's session to the duration of the batch.

The queue approach is the right answer for this app's scale and
ergonomics. Implementation detail beyond this spec, but the
pattern's existence is a prerequisite the app should have in
place *before* any bulk-send operator workflow ships.

### Threading and reply handling

If reviewer responses can include replies to invitation /
reminder emails (questions, accommodation requests), the app
should:

- Set a meaningful **Reply-To** header on outbound emails (the
  operator's address by default; configurable per session).
- Not attempt to receive or process replies. This is out of scope
  for the app; replies route to the operator's regular inbox.

The reply-to header is set at the `EmailTransport` interface
level, not per backend.

---

## Per-backend specifics

Each section below describes what the app needs *in addition to*
the shared infrastructure above to support that backend.

### Option A — SMTP relay

**Status.** Concrete implementation shipped in Segment 11E PR 5
(`SmtpEmailTransport` in `app/services/email_send.py`). Operator-
facing UI on `/operator/settings`; per-operator credentials
encrypted at rest via Fernet.

**What it is.** The app connects to a configured SMTP server
with credentials and submits the email. The SMTP server can be:

- An institutional SMTP relay (if the institution provides one
  and permits app-level credentials).
- An authenticated SMTP service from a third party (most
  third-party email services offer SMTP as well as API).
- A local development SMTP server.

**Note on Azure outbound SMTP.** Microsoft blocks outbound SMTP
on port 25 from Azure data centers since 2017. SMTP relay use
must go through an authenticated relay service on port 587 or
465. The app's SMTP implementation defaults to authenticated
submission on port 587 with STARTTLS; port 465 with implicit SSL
is also supported via the `smtp_encryption` setting.

**Required configuration.**

Today (per-operator on `users` table, populated via
`/operator/settings`):

- `smtp_host`, `smtp_port`, `smtp_username`,
  `smtp_password_encrypted`, `smtp_encryption`,
  `smtp_from_display_name`.

Future per-deployment defaults (env vars / App Service settings):
none required today; operator-level credentials are sufficient.

**Required app infrastructure.**

- ✅ SMTP client — `smtplib` from stdlib.
- ✅ Secure credential storage — `cryptography.fernet` keyed off
  the `SMTP_ENCRYPTION_KEY` env var. App Service application
  settings are encrypted at rest; for higher-sensitivity
  deployments, Azure Key Vault reference is preferred for the
  Fernet key.

**Implementation work to add.** None for the basic path.
**Segment 14B Part A** wires the existing transport into the
Manage Invitations send path against the audit-log columns
**Segment 11C Part 2** scaffolds.

**Considerations.**

- SMTP doesn't return a message ID until after submission; the
  audit log's future `backend_message_id` field may be empty or
  contain the SMTP server's queue ID.
- SMTP delivery confirmation (delivered vs. bounced) typically
  requires receiving and parsing bounce messages, which is out
  of scope for this spec. The audit log's future `delivered_at`
  field will not be populated by this backend.
- Deliverability depends entirely on the SMTP server's
  reputation and DNS configuration (SPF, DKIM, DMARC for the
  from-domain). The app does not configure these; they are the
  responsibility of whoever owns the relay and the from-domain.
- Many institutional Microsoft 365 tenants block basic SMTP AUTH
  by default (Security Defaults / Conditional Access). When
  the operator's *Add a sign-in method* dialog doesn't list "App
  password," this backend is not reachable in their tenant —
  Options B–D are the alternatives.

---

### Option B — Microsoft Graph (application permission)

**Status.** Typed stub shipped in 11E PR 5
(`GraphEmailTransport` in `app/services/email_send.py`). The
class exists so `transport_for` can dispatch on
`settings.transport == "graph"` once the body of the
implementation lands.

**What it is.** The app authenticates to Microsoft Entra
(Azure AD) as a registered application, gets a token with
`Mail.Send` application permission, and calls
`POST /users/{mailbox}/sendMail` on the Graph API. The mailbox
is a real M365 mailbox (typically a shared service mailbox like
`review-robin@institution.edu`), and the institution's
Application Access Policy scopes the app's permission to that
one mailbox.

**Required configuration.**

Per-deployment (env vars / App Service settings):

- `GRAPH_TENANT_ID` — the institution's Entra tenant ID.
- `GRAPH_CLIENT_ID` — the registered app's client ID.
- `GRAPH_CLIENT_SECRET` — the registered app's secret. Should be
  stored in Key Vault, not plain App Service settings.
- `GRAPH_SENDER_MAILBOX` — the mailbox the app sends from.

**Required app infrastructure.**

- ◻ A Microsoft Authentication Library (MSAL) client. Python:
  `msal` package — new runtime dependency.
- ◻ Token acquisition and caching. Tokens last ~1 hour; the app
  should cache and refresh them rather than acquiring per-send.
- ◻ HTTP client capable of calling Microsoft Graph endpoints —
  `httpx` (already a transitive dev dep, would promote to
  runtime).

**Required institutional setup (not the app's work, but
prerequisite).**

- App registered in the institution's Entra tenant.
- `Mail.Send` application permission granted with admin consent.
- Application Access Policy scoping the permission to the
  chosen sender mailbox. Without this scoping, the app
  technically has permission to send as *any* mailbox in the
  tenant; with it, scoped to one. This is the conversation with
  IT.
- Sender mailbox provisioned (a real M365 mailbox, possibly a
  shared mailbox).
- DNS auth for the sending domain (SPF, DKIM, DMARC) — already
  in place for institutional mail.

**Implementation work to add.**

- Replace the `NotImplementedError` body of
  `GraphEmailTransport.send()` with the MSAL token acquisition +
  Graph POST.
- Mapping from `EmailMessage` to Graph's `Message` JSON schema
  (CC / BCC live on `ccRecipients` / `bccRecipients`).
- Error mapping (Graph error codes → `SendResult.error_message`
  + truncated `transport_response`).

**Considerations.**

- The send call returns 202 Accepted on success; Graph delivers
  asynchronously. The future `backend_message_id` field may not
  be available immediately.
- Sent items are saved to the sender mailbox's Sent folder by
  default. To suppress, set `saveToSentItems: false` in the
  request body. Whether to suppress is a deployment-level
  choice; saving to Sent gives institutional auditors visibility
  but generates clutter in a high-volume mailbox.
- The friendly-name From (the display name reviewers see) can
  be set via the message's `from` field, but the actual sender
  remains the configured mailbox. Spoofing the operator's
  address as the apparent sender is not supported by this
  backend.
- Graph throttles aggressively at high volumes. The bulk-send
  worker should respect 429 responses with exponential backoff.

---

### Option C — Azure Communication Services Email

**Status.** Not implemented.

**What it is.** A first-party Azure service designed for
transactional email. The app provisions an ACS resource and an
Email Communication Services resource in its own Azure
subscription, verifies a sending domain, and calls the ACS Email
SDK to send messages.

**Required configuration.**

Per-deployment (env vars / App Service settings):

- `ACS_CONNECTION_STRING` — the ACS resource connection string.
  Should be stored in Key Vault.
- `ACS_SENDER_ADDRESS` — the verified sender (e.g.,
  `noreply@notifications.review-robin.app`).

**Required app infrastructure.**

- ◻ Azure Communication Services SDK
  (`azure-communication-email`) — new runtime dependency.
- ◻ HTTP client for SDK operations (the SDK handles this).

**Required Azure setup (the app's own subscription, not
institutional).**

- An ACS resource provisioned.
- An Email Communication Services resource linked to the ACS
  resource.
- A sending domain verified (either an Azure-managed domain
  like `*.azurecomm.net`, or a custom domain like
  `notifications.review-robin.app` with DNS records the
  operator configures).
- For production: a request to Microsoft Support to raise the
  default 100/day sandbox limit.

**Implementation work to add.**

- New `AcsEmailTransport` class implementing the
  `EmailTransport` Protocol.
- ACS SDK integration.
- Mapping from `EmailMessage` to ACS's email message format.
- Polling for delivery status if needed (ACS sends are async;
  the SDK provides operation polling).
- New `transport_for` dispatch slot for
  `settings.transport == "acs"`.

**Considerations.**

- ACS does not let you spoof a from address; the from address
  must be on a verified sending domain. The operator's
  institutional email cannot be the From; their address can be
  the Reply-To.
- Cost is per-email plus per-byte; cheap at typical volumes
  (well under a cent per message), but not free.
- Custom-domain verification requires DNS configuration; an
  Azure-managed domain skips this but produces a less
  professional-looking from address.
- ACS handles SPF/DKIM signing for verified domains;
  deliverability is generally good without further work.

---

### Option D — Third-party transactional email

**Status.** Not implemented.

**Examples.** SendGrid, Mailgun, Postmark, Resend, AWS SES.

**What it is.** The app uses a third-party service's API (or
SMTP) to deliver mail. The third party handles DNS auth,
deliverability, suppression lists, bounce handling.

**Required configuration.**

Per-deployment (env vars / App Service settings):

- `THIRDPARTY_API_KEY` — the service's API key. Key Vault.
- `THIRDPARTY_SENDER_ADDRESS` — the verified sender on that
  service.
- `THIRDPARTY_PROVIDER` — which provider, if multiple are
  supported (e.g., `sendgrid`, `mailgun`, `postmark`).

**Required app infrastructure.**

- ◻ The provider's SDK, or `httpx` for direct API calls.
- ◻ Or, if going via SMTP, the existing `SmtpEmailTransport`
  with the third-party's SMTP credentials — no new code needed.

**Required third-party setup (the app's own account).**

- Account with the chosen provider.
- A verified sending domain or a single verified sender
  address.
- DNS records configured per the provider's instructions
  (typically SPF + DKIM CNAME records).

**Implementation work to add.**

- One `EmailTransport` implementation per provider supported,
  or a generic `ThirdPartyApiEmailTransport` parameterised by
  provider.
- Provider SDK / API integration.
- Error mapping per provider.

**Considerations.**

- Each provider has its own API quirks; supporting "any third
  party" is more work than supporting one specific third party.
  Recommend committing to one (most likely SendGrid given
  Azure marketplace integration).
- Inbound parse / webhook features of these services (delivery
  events, bounce notifications) are useful future enhancements
  but out of scope for the basic sending path.
- Free tiers exist (typically 100/day) but real deployments
  will pay.
- Third-party deliverability is generally excellent; this is
  often the highest-deliverability option.
- Some institutions are uncomfortable with review
  communications routing through a third party. Worth a
  conversation with IT before committing.

---

## Summary: what the app needs *before* any backend ships

The infrastructure that supports any of the four backends, common
to all. ✅ = shipped, ◻ = pending.

1. ✅ **The `EmailTransport` Protocol** with a structured
   `EmailMessage` value type and a `SendResult` return type.
2. ✅ **A factory or DI registration** that selects the active
   implementation from configuration (`transport_for(settings)`).
3. ◻ **The audit log table extensions** described above —
   `cc_emails` / `bcc_emails` shipped in Segment 11C Part 1;
   `error_message` + the future-target columns (`from_address` /
   `backend` / `backend_message_id` / `delivered_at` /
   `payload_hash` / `correlation_id`) and the widened status /
   kind value-sets land in **Segment 11C Part 2** as inert
   schema scaffolding. **Segment 14B Part A** is the first call
   site that writes to them.
4. ◻ **A `correlation_id` strategy** for idempotent sends
   across invitation, reminder, and other kinds — Segment 14B
   Part B.
5. ◻ **A bulk-send queue / worker pattern** for operator-
   triggered batch operations — Segment 14B Part C.
6. ◻ **Per-deployment from-identity configuration** as a
   complement to the per-operator settings already in place —
   Segment 14B Part D.
7. ✅ **Secrets management** via App Service settings, with Key
   Vault references for credentials and tokens
   (`SMTP_ENCRYPTION_KEY` env var; per-operator passwords
   encrypted at rest).
8. ◻ **An operator-visible diagnostic surface** — the existing
   Outbox concept, generalised to read from the audit log
   regardless of backend — Segment 14B Part E.

With these in place, adding any one of Options B–D is a scoped
piece of work: implement one `EmailTransport` class, add its
configuration, deploy. Switching between backends is a
configuration change. Supporting multiple deployments on
different backends works out of the box.

What the app does *not* need before any backend ships:

- Backend-specific code paths in the invitation, reminder, or
  notification logic. Those call only `EmailTransport.send()`.
- A way to talk to multiple backends simultaneously. One backend
  per deployment is the design.

## Migration path

Segment 11E PR 5 already ships the `EmailTransport` Protocol +
`SmtpEmailTransport` concrete implementation. Adding any other
backend is a parallel implementation; switching deployments to
use it is a configuration change.

A reasonable sequence:

1. ✅ **Sender abstraction + SMTP backend** — Segment 11E PR 5.
2. ✅ **Operator credential storage** — Segment 11E PR 4.
3. ◻ **Outbox audit-log column scaffolding** — Segment 11C
   Part 2. Inert; populated at send time by Step 4. Lands the
   columns (`error_message` + future-target additions) and the
   widened status / kind value-sets so the wiring in Step 4
   doesn't have to ship Alembic churn alongside its logic
   changes.
4. ◻ **Manage Invitations send activation (SMTP)** — Segment
   14B Part A. First call site for the existing
   `transport_for` factory; first writer of Step 3's columns.
   Per-row Send + bulk Send + Send-test-to-me + dispatch helper
   + chrome pill + audit events + responses-received submit-
   time enqueue.
5. ◻ **`correlation_id` strategy + idempotent retry** — Segment
   14B Part B.
6. ◻ **Bulk-send queue + background worker** — Segment 14B
   Part C.
7. ◻ **Per-deployment from-identity defaults** — Segment 14B
   Part D.
8. ◻ **Generalised Outbox diagnostic surface** — Segment 14B
   Part E.
9. ◻ **Add Option C (ACS)** as the first non-SMTP backend (no
   IT cooperation needed, can be done unilaterally) — Segment
   14B Part G. Use it for early production deployments and
   testing.
10. ◻ **Add Option B (Graph)** when an institutional deployment
    is ready to pursue it — Segment 14B Part F. The IT
    conversation runs in parallel with the code work.
11. ◻ **Add Option D (third-party)** if a specific deployment
    requires it or as a fallback for institutions where
    neither ACS nor Graph fits — Segment 14B Part H.

Steps 9–11 are independent; do them in whatever order
deployments demand.

## Doc impact

`spec/operator_ui_concept.md`:

- The Outbox Operations page description gets a small update:
  the page is currently dev-mode SMTP-only, will generalise to
  a backend-agnostic diagnostic surface showing recent sends
  from the audit log.

`spec/operator_ui_concept.md` "Per-page contracts":

- The Outbox page gets a layout contract update once the
  generalised diagnostic surface is designed.

Future segment specs:

- Each backend implementation that ships is its own engineering
  ticket but doesn't need its own functional spec — this
  document is the source of truth for what each backend
  requires.
