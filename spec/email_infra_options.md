# Email sending — architecture spec

How Review Robin sends email (invitations, reminders, future
notifications) from its Azure App Service deployment.

The app currently sends via a development SMTP path used in
dev-mode and visible through the Outbox Operations page. This
document specifies the architecture needed to support a small set
of production-ready sending options, with a focus on what
*infrastructure and data structures the app should have in place
beforehand* so that adding any one option is a small, scoped piece
of work rather than a re-architecture.

## Goals

- **Pluggable senders.** The app's invitation and reminder paths
  should not know which backend actually delivers the email. They
  call a single internal interface; one of several implementations
  fulfills the call.
- **Multiple supported backends, one at a time per deployment.**
  Different deployments may use different backends (institutional
  Graph for one customer, ACS for another, third-party for a
  third). The app should not require all backends to be configured;
  it should require *one*.
- **Easy migration between backends.** Moving a deployment from,
  say, ACS to Graph should be configuration work and a backend
  swap, not a code rewrite of the sending paths.
- **Auditable, idempotent send semantics.** Every send attempt is
  recorded; retries are safe; the operator can inspect what
  happened.

## Scope

In scope:

- SMTP relay (the existing dev path, generalized for production
  SMTP relay use).
- **Option 1** — Microsoft Graph API with application permission
  (Mail.Send), scoped to a shared mailbox via Application Access
  Policy.
- **Option 3** — Azure Communication Services Email.
- **Option 4** — Third-party transactional email service (SendGrid,
  Mailgun, Postmark, or similar), used as the canonical "third-
  party API" example.

Not in scope:

- Microsoft Graph with delegated permissions (Option 2 from the
  earlier landscape review). The operator-token-based send doesn't
  support scheduled reminders without an operator session, which
  conflicts with the app's reminder workflow.
- Logic Apps as an indirection layer (Option 5). Adds operational
  complexity without enough payoff for this app's scope.

## Architecture

### The sender abstraction

The core of the design is a single internal interface — call it
`EmailSender` — that the app's invitation, reminder, and
notification paths depend on. All call sites use this interface;
none knows which backend is in use.

The interface is small. A reasonable shape:

- `send(email: Email) -> SendResult`
  - `Email` is a structured value containing: from address (with
    optional friendly name), to address(es), subject, body (plain
    + HTML), reply-to, in-reply-to / threading metadata if
    relevant, and a unique `correlation_id` the app supplies so
    sends can be traced.
  - `SendResult` returns: success/failure, backend's message ID
    (if returned), error details (if any), the timestamp, and
    enough metadata to record in the audit log.
- `health_check() -> HealthResult` (optional but useful)
  - Returns whether the configured backend is reachable and
    correctly configured. Used by the operator-facing
    "diagnostics" surface and during deployment validation.

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

Each backend is a separate implementation of `EmailSender`:

- `SmtpSender` — connects to a configured SMTP relay.
- `GraphMailSender` — uses Microsoft Graph API.
- `AcsMailSender` — uses Azure Communication Services.
- `ThirdPartyApiSender` — uses a third-party service's API
  (typically one implementation per third party, but they share
  the same interface).

A factory or DI registration picks the active implementation based
on configuration at app startup. Only one is active per
deployment; unused implementations are dormant code or excluded
from the build entirely if size matters.

### Configuration

Configuration is per-deployment, loaded from environment variables
or App Service application settings. A single `EMAIL_BACKEND`
variable selects the active backend (`smtp` | `graph` | `acs` |
`thirdparty:sendgrid` etc.); per-backend variables provide the
specific settings.

Configuration is read once at startup. Changes require a deploy
or a restart — no hot-reload of email settings.

The app also stores per-deployment "from identity" configuration
that is independent of which backend is in use:

- **Default from address** — the address the app sends as when no
  per-session override applies.
- **Default friendly name** — e.g., "Review Robin Notifications".
- **Default reply-to address** — typically the operator's address
  for the session, but configurable globally as a fallback.

These three values are operationally meaningful even when changing
backends, and live in their own configuration namespace so that
swapping backends doesn't lose them.

### Audit log (the data structure that makes sending observable)

Every send attempt — successful, failed, retried — is recorded in
a database table. This is the central data structure that makes
the email subsystem auditable, debuggable, and idempotent.

Suggested schema (adapt to existing conventions):

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key. The app's `correlation_id` for the send. |
| `session_id` | FK | Which session this send belongs to. Nullable for system emails. |
| `reviewer_id` | FK | Which reviewer (if applicable). Nullable for ops-to-operator emails. |
| `kind` | enum | `invitation`, `reminder`, `confirmation`, `system`, etc. |
| `to_address` | text | The recipient. |
| `from_address` | text | The address actually sent from. |
| `backend` | text | Which `EmailSender` implementation handled the send. |
| `backend_message_id` | text | The backend's identifier for the message, if any. |
| `status` | enum | `pending`, `sent`, `failed`, `bounced`, `delivered`, etc. |
| `error_code` | text | Backend-specific error code, if any. |
| `error_message` | text | Human-readable error, if any. |
| `attempted_at` | timestamp | When the send was attempted. |
| `delivered_at` | timestamp | When delivery confirmed (if backend reports). |
| `payload_hash` | text | Hash of (to + subject + body) for dedup detection. |

Records are written *before* the send is attempted (status
`pending`), updated *after* with the outcome. This pattern means
crashes mid-send leave a `pending` record that can be reconciled
on next startup or by a periodic sweeper.

### Idempotency

The app's invitation and reminder paths must be safe to retry. The
audit log's `payload_hash` and `correlation_id` are the mechanisms:

- Before sending, the app generates a deterministic
  `correlation_id` for "this specific send to this specific
  recipient at this specific intent" (e.g.,
  `invitation:{session_id}:{reviewer_id}`).
- If a record with the same `correlation_id` already exists with
  status `sent`, the send is skipped.
- If a record exists with status `pending` (probably from a crash),
  the send is *retried* with the same `correlation_id`, replacing
  the old record's outcome.
- For reminders, the `correlation_id` includes a sequence component
  (`reminder:{session_id}:{reviewer_id}:{n}`) so each scheduled
  reminder is a separate idempotent operation.

This makes the entire send pipeline crash-safe and retry-safe
without backend-specific logic.

### Bulk sending and queueing

For bulk operations (operator clicks "send invitations to all 80
selected reviewers"), the app should not block the operator's
request on 80 sequential sends. Two options:

- **Background job queue.** The bulk action enqueues 80 individual
  send jobs; a worker process consumes the queue and calls
  `EmailSender.send()` for each. The operator's UI gets a
  "scheduled" response immediately and can poll the audit log to
  show progress.
- **Inline batch with progress.** The bulk action runs the sends
  inline but reports progress to the operator's UI in real time
  (server-sent events, websocket, or polling). Simpler but ties
  the operator's session to the duration of the batch.

The queue approach is the right answer for this app's scale and
ergonomics. Implementation detail beyond this spec, but the
pattern's existence is a prerequisite the app should have in place
*before* any bulk-send operator workflow ships.

### Threading and reply handling

If reviewer responses can include replies to invitation/reminder
emails (questions, accommodation requests), the app should:

- Set a meaningful **Reply-To** header on outbound emails (the
  operator's address by default; configurable per session).
- Not attempt to receive or process replies. This is out of scope
  for the app; replies route to the operator's regular inbox.

The reply-to header is set at the `EmailSender` interface level,
not per backend.

---

## Per-backend specifics

Each section below describes what the app needs *in addition to*
the shared infrastructure above to support that backend.

### SMTP relay

**What it is.** The app connects to a configured SMTP server with
credentials and submits the email. The SMTP server can be:

- An institutional SMTP relay (if the institution provides one and
  permits app-level credentials).
- An authenticated SMTP service from a third party (most
  third-party email services offer SMTP as well as API).
- A local development SMTP server (the existing dev-mode Outbox
  path).

**Note on Azure outbound SMTP.** Microsoft blocks outbound SMTP on
port 25 from Azure data centers since 2017. SMTP relay use must
go through an authenticated relay service on port 587 or 465. The
app's SMTP implementation should default to authenticated submission
on port 587 with TLS.

**Required configuration:**

- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`,
  `SMTP_USE_TLS`.
- The default from address (per the shared from-identity config).

**Required app infrastructure:**

- An SMTP client library appropriate to the language. (The
  existing dev path likely already has this.)
- A way to securely store SMTP credentials in App Service
  configuration. App Service application settings are encrypted at
  rest; for higher-sensitivity deployments, Azure Key Vault
  reference is preferred.

**Implementation work to add:**

- The `SmtpSender` implementation of `EmailSender`.
- Configuration loader for SMTP-specific settings.
- TLS verification, error mapping (SMTP error codes →
  `SendResult.error_code`).

**Considerations:**

- SMTP doesn't return a message ID until after submission; the
  audit log's `backend_message_id` may be empty or contain the
  SMTP server's queue ID.
- SMTP delivery confirmation (delivered vs. bounced) typically
  requires receiving and parsing bounce messages, which is out of
  scope for this spec. The audit log's `delivered_at` will not be
  populated by this backend.
- Deliverability depends entirely on the SMTP server's reputation
  and DNS configuration (SPF, DKIM, DMARC for the from-domain).
  The app does not configure these; they are the responsibility of
  whoever owns the relay and the from-domain.

---

### Option 1 — Microsoft Graph (application permission)

**What it is.** The app authenticates to Microsoft Entra (Azure
AD) as a registered application, gets a token with `Mail.Send`
application permission, and calls `POST
/users/{mailbox}/sendMail` on the Graph API. The mailbox is a
real M365 mailbox (typically a shared service mailbox like
`review-robin@institution.edu`), and the institution's
Application Access Policy scopes the app's permission to that one
mailbox.

**Required configuration:**

- `GRAPH_TENANT_ID` — the institution's Entra tenant ID.
- `GRAPH_CLIENT_ID` — the registered app's client ID.
- `GRAPH_CLIENT_SECRET` — the registered app's secret. Should be
  stored in Key Vault, not plain App Service settings.
- `GRAPH_SENDER_MAILBOX` — the mailbox the app sends from.

**Required app infrastructure:**

- A Microsoft Authentication Library (MSAL) client appropriate to
  the language (Python: `msal`; .NET: `Microsoft.Identity.Client`;
  etc.).
- Token acquisition and caching. Tokens last ~1 hour; the app
  should cache and refresh them rather than acquiring per-send.
- HTTP client capable of calling Microsoft Graph endpoints.

**Required institutional setup (not the app's work, but
prerequisite):**

- App registered in the institution's Entra tenant.
- `Mail.Send` application permission granted with admin consent.
- Application Access Policy scoping the permission to the chosen
  sender mailbox. Without this scoping, the app technically has
  permission to send as *any* mailbox in the tenant; with it,
  scoped to one. This is the conversation with IT.
- Sender mailbox provisioned (a real M365 mailbox, possibly a
  shared mailbox).
- DNS auth for the sending domain (SPF, DKIM, DMARC) — already in
  place for institutional mail.

**Implementation work to add:**

- The `GraphMailSender` implementation of `EmailSender`.
- MSAL-based token acquisition with caching.
- Mapping from the `Email` value to Graph's `Message` JSON
  schema.
- Error mapping (Graph error codes → `SendResult.error_code`).

**Considerations:**

- The send call returns 202 Accepted on success; Graph delivers
  asynchronously. The `backend_message_id` may not be available
  immediately.
- Sent items are saved to the sender mailbox's Sent folder by
  default. To suppress, set `saveToSentItems: false` in the
  request body. Whether to suppress is a deployment-level choice;
  saving to Sent gives institutional auditors visibility, but
  generates clutter in a high-volume mailbox.
- The friendly-name From (the display name reviewers see) can be
  set via the message's `from` field, but the actual sender remains
  the configured mailbox. Spoofing the operator's address as the
  apparent sender is not supported by this backend.
- Graph throttles aggressively at high volumes. The bulk-send
  worker should respect 429 responses with exponential backoff.

---

### Option 3 — Azure Communication Services Email

**What it is.** A first-party Azure service designed for
transactional email. The app provisions an ACS resource and an
Email Communication Services resource in its own Azure
subscription, verifies a sending domain, and calls the ACS Email
SDK to send messages.

**Required configuration:**

- `ACS_CONNECTION_STRING` — the ACS resource connection string.
  Should be stored in Key Vault.
- `ACS_SENDER_ADDRESS` — the verified sender (e.g.,
  `noreply@notifications.review-robin.app`).

**Required app infrastructure:**

- Azure Communication Services SDK for the app's language.
- HTTP client for SDK operations (the SDK handles this).

**Required Azure setup (the app's own subscription, not
institutional):**

- An ACS resource provisioned.
- An Email Communication Services resource linked to the ACS
  resource.
- A sending domain verified (either an Azure-managed domain like
  `*.azurecomm.net`, or a custom domain like
  `notifications.review-robin.app` with DNS records the operator
  configures).
- For production: a request to Microsoft Support to raise the
  default 100/day sandbox limit.

**Implementation work to add:**

- The `AcsMailSender` implementation of `EmailSender`.
- ACS SDK integration.
- Mapping from the `Email` value to ACS's email message format.
- Polling for delivery status if needed (ACS sends are async; the
  SDK provides operation polling).

**Considerations:**

- ACS does not let you spoof a from address; the from address must
  be on a verified sending domain. The operator's institutional
  email cannot be the From; their address can be the Reply-To.
- Cost is per-email plus per-byte; cheap at typical volumes (well
  under a cent per message), but not free.
- Custom-domain verification requires DNS configuration; an
  Azure-managed domain skips this but produces a less
  professional-looking from address.
- ACS handles SPF/DKIM signing for verified domains; deliverability
  is generally good without further work.

---

### Option 4 — Third-party transactional email (SendGrid / Mailgun / Postmark / similar)

**What it is.** The app uses a third-party service's API (or SMTP)
to deliver mail. The third party handles DNS auth, deliverability,
suppression lists, bounce handling.

**Required configuration:**

- `THIRDPARTY_API_KEY` — the service's API key. Key Vault.
- `THIRDPARTY_SENDER_ADDRESS` — the verified sender on that
  service.
- `THIRDPARTY_PROVIDER` — which provider, if multiple are
  supported (e.g., `sendgrid`, `mailgun`, `postmark`).

**Required app infrastructure:**

- The provider's SDK (Python, .NET, etc.).
- Or, if going via SMTP, the existing SMTP infrastructure with
  the third-party's SMTP credentials.

**Required third-party setup (the app's own account):**

- Account with the chosen provider.
- A verified sending domain or a single verified sender address.
- DNS records configured per the provider's instructions
  (typically SPF + DKIM CNAME records).

**Implementation work to add:**

- One `EmailSender` implementation per provider supported, or a
  generic `ThirdPartyApiSender` parameterized by provider.
- Provider SDK integration.
- Error mapping per provider.

**Considerations:**

- Each provider has its own API quirks; supporting "any third
  party" is more work than supporting one specific third party.
  Recommend committing to one (most likely SendGrid given Azure
  marketplace integration).
- Inbound parse / webhook features of these services (delivery
  events, bounce notifications) are useful future enhancements but
  out of scope for the basic sending path.
- Free tiers exist (typically 100/day) but real deployments will
  pay.
- Third-party deliverability is generally excellent; this is
  often the highest-deliverability option.
- Some institutions are uncomfortable with review communications
  routing through a third party. Worth a conversation with IT
  before committing.

---

## Summary: what the app needs *before* any backend ships

The infrastructure that supports any of the four backends, common
to all:

1. **The `EmailSender` interface** with a structured `Email` value
   type and a `SendResult` return type.
2. **A factory or DI registration** that selects the active
   implementation from configuration.
3. **The audit log table** with the schema described above.
4. **A `correlation_id` strategy** for idempotent sends across
   invitation, reminder, and other kinds.
5. **A bulk-send queue/worker pattern** for operator-triggered
   batch operations.
6. **From-identity configuration** (default from address, friendly
   name, reply-to) independent of the backend.
7. **Secrets management** via App Service settings, with Key Vault
   references for credentials and tokens.
8. **An operator-visible diagnostic surface** (the existing
   Outbox concept, generalized) that shows recent sends from the
   audit log, regardless of backend.

With these in place, adding any one of the four backends is a
scoped piece of work: implement one class, add its configuration,
deploy. Switching between backends is a configuration change.
Supporting multiple deployments on different backends works
out of the box.

What the app does *not* need before any backend ships:

- Backend-specific code paths in the invitation, reminder, or
  notification logic. Those call only `EmailSender.send()`.
- A way to talk to multiple backends simultaneously. One backend
  per deployment is the design.

## Migration path

The current dev-mode SMTP path becomes the first `SmtpSender`
implementation, generalized to support production SMTP relays as
well as the dev local server. Adding any other backend is then a
parallel implementation; switching deployments to use it is a
configuration change.

A reasonable sequence:

1. **Stand up the shared infrastructure** (interface, audit log,
   queue, configuration, diagnostic surface). This is the bulk
   of the engineering work.
2. **Migrate the existing dev-mode SMTP** to the new
   infrastructure as `SmtpSender`. Verify the dev workflow still
   works end-to-end.
3. **Add ACS** as the first production backend (no IT cooperation
   needed, can be done unilaterally). Use it for early production
   deployments and testing.
4. **Add Graph** when an institutional deployment is ready to
   pursue it. The IT conversation runs in parallel with the code
   work.
5. **Add a third-party** option if a specific deployment requires
   it or as a fallback for institutions where neither ACS nor
   Graph fits.

Steps 3–5 are independent; do them in whatever order deployments
demand.

## Doc impact

UI concept doc:

- The Outbox Operations page description gets a small update: the
  page is currently dev-mode SMTP-only, will generalize to a
  backend-agnostic diagnostic surface showing recent sends from
  the audit log.

`spec/operator_map.md`:

- The Outbox page gets a layout contract update once the
  generalized diagnostic surface is designed.

Future segment specs:

- Each backend implementation that ships is its own engineering
  ticket but doesn't need its own functional spec — this document
  is the source of truth for what each backend requires.
