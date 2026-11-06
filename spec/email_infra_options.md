# Email sending — architecture spec

How Review Robin sends email (invitations, reminders, future
notifications) from its Azure App Service deployment.

**The transport in use is delegated Microsoft Graph, on the
operator's click.** The operator's own token sends through
`POST /me/sendMail` inside the request that clicked, from the
operator's own mailbox (`cordware/spec/identity.md`, "Graph"). It is
`GraphEmailTransport` over the host's mailer, under the same
`EmailTransport` Protocol as `SmtpEmailTransport`, which stays for a
deployment outside Microsoft 365 (its per-operator settings on the
`users` table are edited by no page, `spec/settings_inventory.md` §1).
Nothing sends on a clock: a send needs an operator's token.

The rest of this document is the architectural target: **what the app
needs in place so that adding any single further email backend is a
scoped piece of work, not a re-architecture of the invitation /
reminder paths.** Options B–D below are alternatives, not built.

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

- **Delegated Graph** (in use): the signed-in operator's token and
  mailbox, on a click. Described under "The sender abstraction" and
  "Delegated Graph, as built".
- **Option A** — SMTP relay (the existing path, generalised for
  production SMTP relay use as well as the dev local server).
- **Option B** — Microsoft Graph API with application permission
  (`Mail.Send`), scoped to a shared mailbox via Application Access
  Policy.
- **Option C** — Azure Communication Services (ACS) Email.
- **Option D** — Third-party transactional email service
  (SendGrid, Mailgun, Postmark, or similar), used as the
  canonical "third-party API" example.

Not in scope:

- Sending on a clock. The delegated send needs an operator's token,
  so nothing mails without a click; a send that needs no operator
  session is Option B's, or another backend's.
- Logic Apps as an indirection layer. Adds operational complexity
  without enough payoff for this app's scope.

## Architecture

### The sender abstraction

The core of the design is a single internal interface —
`EmailTransport` — that the app's invitation, reminder, and
notification paths depend on. All call sites use this interface;
none knows which backend is in use.

Declared in `app/services/email_send.py`:

```python
@dataclass(frozen=True)
class EmailMessage:
    from_addr: str
    from_display_name: str | None
    to: str
    subject: str
    body: str
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    reply_to: str | None = None
    save_to_sent_items: bool = False  # Graph's saveToSentItems; SMTP has no Sent Items


@dataclass(frozen=True)
class SendResult:
    ok: bool
    error_message: str | None = None
    transport_response: str | None = None  # truncated raw provider response
    failure_kind: str | None = None  # the Graph transport's GraphError kind


class EmailTransport(Protocol):
    def send(self, msg: EmailMessage) -> SendResult: ...
```

The `EmailMessage` shape is transport-agnostic — no DB types in
the contract, no `ReviewSession` / `Reviewer`. The dispatcher
(`app/services/email_dispatch.py`) builds a message from an outbox
row and the operator's `SendOptions` and hands the transport a flat
object.

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
  Implemented.
- `GraphEmailTransport` — delegated Graph over the host's `Mailer`
  (`cordware.graph.mailer_for`): `POST /me/sendMail` with the
  operator's token, or `FakeMailer` under fake auth, which sends
  nothing. Implemented; see "Delegated Graph, as built". The
  application-permission flavour is Option B below.
- `AcsEmailTransport` — uses Azure Communication Services. Not
  yet implemented.
- `ThirdPartyApiEmailTransport` — uses a third-party service's
  API (typically one implementation per provider, but they share
  the same Protocol). Not yet implemented.

The factory `transport_for(settings) -> EmailTransport` (in
`email_send.py`) picks the SMTP implementation from the operator's
`EmailSettings.transport` field; only `"smtp"` is reachable. The
Graph transport is built per request from the request's mailer
(`graph_transport_for`), not from stored settings. The `"acs"` /
`"thirdparty"` slots are reserved.

### Delegated Graph, as built

- **Sender.** The operator's own mailbox, as Graph sends it; the app
  sets no From (`from_addr` is ignored).
- **Mailer.** `mailer_for(request)` returns `GraphMailer` with the
  request's delegated token, `FakeMailer` under fake auth, and raises
  `GraphError("no_token")` with none. A per-row send builds it before
  queueing anything, so with no token nothing is queued or rotated and
  the page says to reload.
- **No retry.** A `5xx` or a network failure may come after Graph
  accepted the message, so it is never retried. A `429` waits its
  `Retry-After` once, at most 5 s on a request (`graph.REQUEST_MAX_WAIT`),
  else fails `throttled` at once.
- **A definite refusal** is one of `email_dispatch.REFUSED_KINDS`
  (`unauthorized`, `forbidden`, `throttled`, `bad_response`): Graph
  returned before accepting. Only after one is the message known not to
  have gone out, so only then does a per-row Send restore the
  invitation's stamps (`invitation.send_reverted`). After a `5xx` or
  network failure the stamps stay and the row offers Send reminder,
  which reuses the link.
- **Operator options**, all off by default and per operator (the Email
  settings card, `spec/settings_inventory.md` §1), read by
  `send_options_for`: **Keep a copy in my Sent Items** (`saveToSentItems`),
  **Send a copy to myself** (the operator's address added to Bcc) and
  **Replies go to the session's Help contact**, which applies only when
  the session's Help contact is an email address. Reply-To is thus per
  operator and per session by that contact, not the operator's address.
- **Owner reports are the second kind of mail sent as the operator.**
  When an owner acts on a session, each *other* owner who opted in
  (`spec/session_owners.md` §8) is mailed from the acting owner's
  mailbox, through `mailer_for(request)` after the route has answered.
  No outbox row: the outbox is participant mail. The outcome is audited
  (`report.sent`, `report.send_failed`); a refusal or missing token is
  recorded and never reaches the action. The actor's Sent Items choice
  applies; Bcc to self and Reply-to do not, being about participant mail.
- **The SMTP transport sets Reply-To** too: `_build_message` writes the
  header from `EmailMessage.reply_to`, as Graph's `replyTo` (findings D8).
- **Send a test to me** (the composer, `spec/email_template_editor.md`)
  does not use the outbox.

### Configuration

Today's configuration is **per-operator**, not per-deployment —
a "send-as-me" identity model, with credentials on the `users`
table (encrypted at rest via Fernet, key from the
`SMTP_ENCRYPTION_KEY` env var). No page edits them: the
`/operator/settings` SMTP cards retired in segment 14C Item 1, once
the choice of sender narrowed to Microsoft Graph (as the operator or a
dedicated mailbox, `guide/email_and_scheduling.md`). The columns and
the transport stay for a deployment with an SMTP relay.

Per-deployment defaults are a future addition for backends that
don't naturally have a per-operator credential (Option C — ACS —
is the obvious example). The pattern that fits both today's per-
operator settings and tomorrow's per-deployment defaults:

- **Per-deployment defaults.** App-wide identity + transport
  selection, loaded from environment variables at startup. Used
  when an operator's settings are blank or when a backend is
  intrinsically deployment-scoped.
- **Per-operator overrides.** The existing `users.smtp_*` columns,
  with a form to edit them restored where send-as-me SMTP applies.
- **Per-session overrides.** CC / BCC live on the email-template
  editor, keyed by template. Reply-To comes from the session's Help
  contact through the operator's option (see "Delegated Graph, as
  built"); there is no separate reply-to override.

The dispatcher reconciles these layers when sending a given row.

### Audit log

Every send attempt is recorded in a database table. This is the
central data structure that makes the email subsystem auditable,
debuggable, and idempotent.

Today's `email_outbox` table is the audit log. Its shape:

| Field | Type | Notes |
|---|---|---|
| `id` | int | Primary key. |
| `session_id` | FK | Which session this send belongs to. |
| `reviewer_id` | FK | Which reviewer. Nullable for system emails, **and** once that reviewer's roster row is deleted — see below. |
| `invitation_id` | FK | Which invitation row this send is for. Nullable, on the same two grounds. |
| `kind` | enum | Canonical set `EMAIL_OUTBOX_KINDS` — `invitation`, `reminder`, `responses_received`. |
| `to_email` | text | The recipient. |
| `cc_emails` / `bcc_emails` | text, comma-separated | Populated from the editor's CC / BCC overrides at queue time. |
| `subject` | text | The merged subject. |
| `body` | text | The merged body. |
| `status` | enum | Canonical set `EMAIL_OUTBOX_STATUSES` — `{queued, sending, sent, failed}`. **Recorded** is `queued`: an enqueue path wrote the row. The dispatcher claims a `queued` row by a conditional update to `sending`, sends only a row it claimed, then stamps `sent` or `failed`. A row left `sending` by a request that died reads as such and is retried only by hand. **Recorded, sent and failed** are these three states; a recorded email is not a sent one. |
| `created_at` | timestamp | When the row was written. |
| `sent_at` | timestamp | When a transport sent the row; null until `sent`. |

**A row outlives its reviewer — except when the session goes.** Both FK
columns carry no `ON DELETE`, so the roster-delete and purge paths clear
them first (`invitations.detach_outbox`) and keep the row, because the
log is what it is for. Deleting the **session** is the exception: the
outbox cascades out with everything else it owns
(`spec/sessions_overview.md`). Each surviving row is self-contained —
`to_email`, `subject`, `body`, `sent_at`, `backend_message_id`,
`delivered_at` — so nothing about a sent email depends on the reviewer
row. **`reviewer_id IS NULL` with `sent_at IS NOT NULL` means: sent,
recipient since removed.**

`status` does not say so, and must not be made to. It carries delivery
state, and its vocabulary is the closed `EMAIL_OUTBOX_STATUSES` pinned by
`tests/integration/test_email_outbox_schema.py` — so a fifth "defunct"
member is a schema change with a test behind it, to say what two existing
columns already say.

The dispatcher writes `error_message` (on `failed`), `from_address`
(the operator's address) and `backend` (`graph`) at send time.
`backend_message_id`, `delivered_at` and `payload_hash` are inert
schema scaffolding that nothing writes (Graph's `202 Accepted` returns
no id).
`correlation_id` is already in use: scheduled reminders stamp it
(`reminder:{session_id}:{reviewer_id}:{offset_index}`) and read it back
to skip a reviewer already reminded at that offset
(`app/services/scheduled_events/_reminders.py`). The stamp is written
with the row, in the same commit, through `send_reminder`'s
`outbox_correlation_id`, so a later rollback cannot lose the stamp
and re-queue the reminder:

- `error_message` (Text, nullable) — captured on failure; the Outbox
  and Invitations surfaces render the reason.
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
  this intent." Mechanism for idempotent retry.

Records are written *before* the send is attempted (status
`queued`), claimed (`sending`), and updated *after* with the outcome.
A crash mid-send leaves a `sending` record for a person to reconcile.

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

**Bulk sending is built but off.** Send all, Remind incomplete and
the Workflow card's Send invites render disabled until 14G, whatever
`RRW_BULK_SEND` says (findings L2; `docs/deployment.md`), and their routes answer `409`.
One message per request stays live as per-row Send and Send reminder.
A paced, batched bulk send (14G) is what will make the flag mean something again. The fallback is
the session link (`spec/operations_pages.md`, "Share the session
link").

### Threading and reply handling

If reviewer responses can include replies to invitation /
reminder emails (questions, accommodation requests), the app
should:

- Set a meaningful **Reply-To** header on outbound emails (the
  session's Help contact, when it is an address and the operator has
  chosen it).
- Not attempt to receive or process replies. This is out of scope
  for the app; replies route to the operator's regular inbox.

`EmailMessage.reply_to` carries it at the `EmailTransport` interface
level. The Graph transport sends it as `replyTo` and the SMTP transport as a
Reply-To header (findings D8).

---

## Per-backend specifics

Each section below describes what the app needs *in addition to*
the shared infrastructure above to support that backend.

### Option A — SMTP relay

**Status.** Implemented — `SmtpEmailTransport` in
`app/services/email_send.py`, with per-operator credentials
encrypted at rest via Fernet. No page edits them (see Configuration).

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
465. The app sets no port of its own: a blank
port leaves the credentials incomplete, so nothing sends
(`operator_settings.get_email_settings`). The operator picks
STARTTLS (usual on 587) or implicit SSL (usual on 465) through the
`smtp_encryption` setting.

**Required configuration.**

Today (per-operator on `users` table; no page populates them since
segment 14C Item 1):

- `smtp_host`, `smtp_port`, `smtp_username`,
  `smtp_password_encrypted`, `smtp_encryption`,
  `smtp_from_display_name`, and `smtp_transport` (always `smtp`, the
  only transport `transport_for` reaches).

Future per-deployment defaults (env vars / App Service settings):
none required today; operator-level credentials are sufficient.

**Required app infrastructure.** Both pieces are in place.

- SMTP client — `smtplib` from stdlib.
- Secure credential storage — `cryptography.fernet` keyed off
  the `SMTP_ENCRYPTION_KEY` env var. App Service application
  settings are encrypted at rest; for higher-sensitivity
  deployments, Azure Key Vault reference is preferred for the
  Fernet key.

**Implementation work to add.** None for the basic path; no send path
uses this transport today (delegated Graph is the one in use).

**Considerations.**

- SMTP doesn't return a message ID until after submission; the
  audit log's `backend_message_id` field may be empty or
  contain the SMTP server's queue ID.
- SMTP delivery confirmation (delivered vs. bounced) typically
  requires receiving and parsing bounce messages, which is out
  of scope for this spec. The audit log's `delivered_at`
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

**Status.** Not implemented. `GraphEmailTransport` in
`app/services/email_send.py` is the *delegated* flavour (see "Delegated
Graph, as built"); this option is the application-permission
alternative, which sends without an operator session.

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

- A Microsoft Authentication Library (MSAL) client. Python:
  `msal` package — new runtime dependency.
- Token acquisition and caching. Tokens last ~1 hour; the app
  should cache and refresh them rather than acquiring per-send.
- HTTP client capable of calling Microsoft Graph endpoints —
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

- An application-token mailer beside `GraphMailer` (MSAL token
  acquisition, `POST /users/{mailbox}/sendMail`); the message mapping
  and error mapping in `cordware/graph.py` and `GraphEmailTransport`
  are reusable.

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

- Azure Communication Services SDK
  (`azure-communication-email`) — new runtime dependency.
- HTTP client for SDK operations (the SDK handles this).

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

- The provider's SDK, or `httpx` for direct API calls.
- Or, if going via SMTP, the existing `SmtpEmailTransport`
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

## What the app needs before a backend ships

One `EmailTransport` Protocol, one implementation per backend,
chosen by configuration; one backend per deployment. Invitation,
reminder and notification logic call only `EmailTransport.send()`,
so adding a backend is one class plus its configuration, and
switching backends is a configuration change.

What is pending, and the order it lands in, is plan content: it lives
in `guide/` (`guide/email_and_scheduling.md`).
