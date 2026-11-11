# Cordware Telegram Smoke-Test Utility — Implementation Handover v0.2

**Status:** Proposed implementation specification; repository-specific update to v0.1  
**Date:** 2026-11-10  
**Audience:** Coding agent / Cordware maintainers  
**Host:** `<cordware-host>` stands for the production host, which this public repository does not name (added on import, 2026-11-11)  
**Purpose:** Prove that a signed-in Cordware user can connect a personal Telegram account, receive a test notification from an Azure-hosted backend, and follow a link from that notification to a Cordware web application on a phone.

## 1. Objective and boundaries

Build **Telegram Test** as the **second tool inside the existing Cordware Utilities application**. Its canonical user-facing URL is **`https://<cordware-host>/utilities/telegramtest`** (trailing-slash redirect or alias acceptable). Its development source belongs in **`philoyhc/review-robin-web` → `utilityapps/`**, alongside Email Address Checker. Do **not** create a fifth host application, separate FastAPI mount, or independent deployment.

Build a **small, self-contained smoke-test utility** within the Cordware development environment. It is **not** a production notification service, Telegram chatbot, or standalone mobile app. It should exercise the end-to-end path:

1. User signs in to the utility using the existing Cordware authentication mechanism (Microsoft Entra ID where applicable).
2. User initiates Telegram linking from the utility.
3. User opens the designated Telegram bot and presses **Start**.
4. Backend reliably binds the **private Telegram chat ID** to the authenticated Cordware user.
5. User returns to the utility, sees **Connected**, and sends a test notification to **their own** Telegram account.
6. Telegram message contains a concise description and a **URL button** leading to a Cordware app.
7. On phone, tapping the button opens the URL in Telegram's in-app browser or a phone browser; Cordware authenticates/authorizes the user and preserves the intended destination.
8. User can unlink Telegram; subsequent test-send attempts fail safely.

**Primary deliverable:** A working vertical slice, including UI, endpoints, persistence, configuration, automated tests, and a short operator runbook. Reuse existing Cordware patterns rather than creating a parallel auth or infrastructure stack.

**Non-goals:** Bulk messaging, automated app-event notifications, scheduling, delivery queues, cross-user messaging, user-facing notification templates, read receipts, SMS/WhatsApp/Teams, Telegram Mini Apps, Telegram Login, native Android/iOS apps, and an interactive bot beyond `/start` and `/help`.

## 2. Repository and deployment discovery (must be first)

The target repository is **https://github.com/philoyhc/review-robin-web** (`main`); the target package is **`utilityapps/`**. The existing Utilities application is mounted at **`/utilities`**, via registry factory `utilityapps.main:create_app`. Confirm the current checkout still agrees before making changes.

Before editing code, inspect the target repository and document:

- Existing Cordware authentication/session handling and canonical **immutable user identifier** (prefer Entra object ID **with tenant context**, or the platform's existing stable user principal key; do **not** use display name/email alone).
- App/module routing and configuration patterns; current Azure hosting/deployment setup and available inbound HTTPS routes.
- Current database, migration tooling, secret storage, RBAC conventions, structured logging, testing and CI.
- Existing links to Cordware apps and whether paths can be restored after Entra sign-in.
- Which repo is the authorized private deployment/configuration location; **never commit real bot tokens** or institution-specific secrets to a public repository.

Implement in the existing stack. Avoid new Azure resources if current hosting can serve both webhook and sender. If the repository cannot be identified or no authentication is available, deliver a minimal isolated prototype **with explicit limitations**, not a mock identity binding presented as secure production-ready functionality.

## 2A. Verified repository integration points (main branch, inspected 2026-11-10)

The following are **existing code**, not proposed new framework:

| Existing path | What the agent should do |
|---|---|
| `utilityapps/main.py` | Add `telegram_test.routes.router` to the existing `create_app()` factory, after `email_check_router`. Preserve the factory and mount. |
| `utilityapps/routes_home.py` | Index route already renders `utilities/index.html`; likely no backend change. |
| `utilityapps/templates/utilities/index.html` | Add a second `<li>` **after** Email Address Checker, with the exact label **Telegram Test**. Preserve the existing list and layout. |
| `utilityapps/templates/utilities/base.html` | Reuse current styling, responsive viewport, favicon and footer; avoid parallel UI chrome. |
| `utilityapps/web.py` | Use `url()`/`url_path()` for mount-aware URLs; the app is mounted under `/utilities`. Do not hardcode the prefix twice. |
| `utilityapps/email_check/routes.py` | Reference for route-level authorization, `resolve_identity(request)`, `APIRouter`, `TemplateResponse`, and no-store response headers. Do **not** copy super-admin-only access automatically without deciding policy. |
| `cordware/identity.py` | Reuse the shared trusted Easy Auth identity; use `(tenant_id, principal_id)` as a stable account key where present. No email/username-only bindings. |
| `utilityapps/spec/utilities.md` | Update index/tool pages and integration contract; preserve import boundaries. |
| `utilityapps/README.md` | Update tool inventory and operational notes. |
| `utilityapps/tests/` | Add tests using existing host-building fixtures and conventions. |

**Recommended new module:** `utilityapps/telegram_test/` with `__init__.py`, `routes.py`, `service.py`, `telegram_api.py`, and a persistence adapter as needed. Put its templates in `utilityapps/templates/telegram_test/`; add specification in `utilityapps/spec/telegram_test.md` and operator instructions under `utilityapps/docs/` or `guide/` according to local conventions. These filenames are proposals, not assertions that they exist.

**Important existing constraint:** `utilityapps/spec/utilities.md` currently specifies **“Utilities has none”** concerning its database and says the factory opens no database. Telegram account linkage requires durable state, and in-memory process-local state will not suffice on a multi-instance Azure deployment or across restarts. The coding agent must explicitly choose an approved durable storage owner, migration and deployment strategy, and update the contract before presenting the utility as deployable. Prefer reusing existing platform facilities if permitted rather than silently introducing a new database. Avoid importing Review Robin's `app` package to borrow its models: the existing import-boundary tests forbid `utilityapps -> app` and `utilityapps -> residentialapps`.

**Public-repository boundary:** `review-robin-web` is the **public development source**; do not embed real institutional secrets, tenant-specific operational records, production Telegram chat IDs, or private Azure deployment configuration. The Cordware private import/deploy pipeline should pick up the runtime module under `utilityapps/` (per the existing README); verify its inclusion of any new migrations and config before rollout. This handover does not authorize direct code edits in the private Cordware repository.

**Webhook authentication exception:** Azure Easy Auth normally protects Cordware pages. The Telegram webhook cannot sign in through Entra; **explicitly allow** the narrow webhook route through the hosting auth layer, while keeping all other Telegram Test endpoints protected. Validate Telegram's webhook secret header in application code. Verify that the authentication bypass is path-scoped and supported by the actual deployment (not a broad `/utilities/*` exemption). If the Azure front door cannot safely exempt this route, use a dedicated ingress/relay with the same security properties rather than pretending a protected webhook works.

**Authorization decision:** The screenshot shows an administrator-oriented Utilities index, but the index itself has no route grant and Email Address Checker is super-admin-only. Decide whether this self-linking smoke test is restricted to super-admins/testers or open to any authenticated user. For an initial rollout, **super-admin/tester-only** is the conservative default; implement an explicit server-side guard and document any expansion. In no case should the index's visibility be treated as authorization.

## 3. Architecture

```text
Authenticated Cordware user
     |  (Connect Telegram)
     v
Smoke-test UI --authenticated API--> issue short-lived one-time link token
     |                                   |
     +-- https://t.me/<bot>?start=<token> |
                 |                        |
             User taps Start              |
                 |                        |
                 v                        v
Telegram bot webhook --verify secret--> validate/consume token
                                          |
                                 persist user <-> private chat ID
                                          |
Smoke-test UI --authenticated POST /test-send
                                          |
                               Telegram Bot API sendMessage
                                          |
                       Telegram message + HTTPS URL button
                                          |
                              Cordware app login/deep link
```

A single platform-level Telegram bot is enough. Store bot token server-side only. Webhook ingestion and message sending should be backend operations: **no browser-to-Telegram API calls**.

## 4. User interface / functional requirements

Create the **Telegram Test** page under existing **Cordware Utilities**. Add a second entry directly **after Email Address Checker** on the Utilities index, with link `{{ url('/telegramtest') }}` and a concise description such as “Connect your Telegram account and send yourself a test notification with a link to Cordware.” The index remains the existing informational tool list; the Telegram Test page independently enforces authorization. Use the shared `utilities/base.html` chrome, responsive styling and index/footer navigation. Do not create a new application tile on the Cordware host landing page.

Use **`GET /utilities/telegramtest`** as the desired canonical public entry point; support a trailing slash without breaking the URL or mounts. Do not expose the tool globally by accident. Its core states:

| State | UI / allowed action |
|---|---|
| Not connected | **Connect Telegram** and short instructions |
| Pending | **Open Telegram bot** link, expiry indication, **Cancel**, **Refresh status** (or safe polling) |
| Connected | Confirmation, optional Telegram display handle if available, **Send test message**, **Disconnect** |
| Error / expired | Clear reason and **Try again** |

The connected UI should contain:

- Optional test-message text field (safe default; impose a conservative character limit, e.g. 500).
- **Target Cordware URL** selector using a server-side allowlist of configured, environment-appropriate routes (initial suggestions: `https://<cordware-host>/`, `https://<cordware-host>/utilities/`, and an existing, verified Review Robin route if enabled), rather than accepting arbitrary user-controlled external URLs. Support at least one real reachable Cordware destination.
- **Send test** button, disabled until connected; response shows API acceptance or failure, timestamp, and sanitized diagnostic status. Do not claim that the Telegram user viewed the message.
- **Disconnect** action (invalidate/delete binding); do not imply this blocks the Telegram bot itself. A disconnected user can still have the bot chat in Telegram.

When the user taps **Connect Telegram**, generate a high-entropy single-use token (e.g. 32 random bytes, base64url without padding), persist only its secure hash, and construct `https://t.me/<bot_username>?start=<token>`. Telegram start payloads are limited to **64 URL-safe characters** (`A–Z`, `a–z`, `0–9`, `_`, `-`). Use a brief expiry, e.g. **10 minutes**, and revoke any previous pending token for that user. A token is a **binding challenge**, not an authenticated session or Cordware login credential.

On successful `/start <token>` from a private chat, acknowledge inside Telegram (e.g. “Telegram connected. Return to Cordware to send a test notification.”). The Cordware UI updates after a status refresh or bounded polling.

## 5. Data model (adapt to existing database)

Minimum persisted state:

**`telegram_links`**

| Field | Notes |
|---|---|
| `principal_id` + `tenant_id` (or canonical platform user key) | Unique; derived only from authenticated session |
| `telegram_chat_id` | Store as a 64-bit-safe integer or decimal string; unique for private links |
| `telegram_user_id` | Optional 64-bit-safe Telegram ID; useful for consistency checks |
| `telegram_username` | Optional display-only metadata; mutable, not identity |
| `linked_at`, `updated_at` | UTC timestamps |
| `status` | `active` / `disabled`, or delete on disconnect |

**`telegram_link_challenges`**

| Field | Notes |
|---|---|
| `token_hash` | Unique, never store/print raw token |
| `principal_id`, `tenant_id` | Identity owning challenge |
| `expires_at`, `created_at`, `consumed_at` | UTC timestamps |
| `status` | Pending / consumed / cancelled / expired; atomic consumption |

Optional **`telegram_test_sends`** record: principal ID, time, configured destination key, Telegram message ID, outcome, error class, request correlation ID. Do **not** retain raw message text or bot token in telemetry. Apply retention appropriate to smoke-test data.

A chat must not silently become bound to multiple Cordware identities. On attempted conflicting linkage, reject and show a clear remediation path (disconnect through the prior authenticated account or admin cleanup); do not automatically reassign. Re-linking the same Telegram chat to the same user is idempotent. Consider explicit confirmation if an already-linked user tries to replace their chat.

## 6. API contract (illustrative; match app conventions)

| Method | Endpoint | Auth | Behavior |
|---|---|---|---|
| `GET` | `/utilities/telegramtest/status` | Authorized tester | Return connected/pending status and safe metadata |
| `POST` | `/utilities/telegramtest/connect` | Authorized tester | Create challenge and return Telegram deep link / expiry |
| `POST` | `/utilities/telegramtest/cancel` | Authorized tester | Cancel own pending challenge |
| `POST` | `/utilities/telegramtest/send-test` | Authorized tester | Send only to own linked private chat; validate message and selected destination |
| `POST` | `/utilities/telegramtest/disconnect` | Authorized tester | Disconnect own Telegram linkage |
| `POST` | `/utilities/telegramtest/webhook` | Telegram secret header | Process permitted Telegram updates, especially private `/start <token>` |

All user-facing API requests require existing CSRF protections/session validation as appropriate, and server-side authorization to access developer utilities. Derive `principal_id` exclusively from the server-validated session, **never from request body**. The test sender must not accept arbitrary `chat_id` or recipient principal IDs.

The webhook is intentionally unauthenticated by Cordware login, but must check Telegram's configured `X-Telegram-Bot-Api-Secret-Token` header using a constant-time comparison, reject malformed/oversized payloads, and process only private chat updates for linking. Its URL should be HTTPS. Configure `setWebhook` with `secret_token` and preferably `allowed_updates=["message"]`. Do not rely on obscurity of the webhook path as authentication. Implement idempotency for retried updates and atomic single-use challenge consumption. Avoid logging incoming `/start` tokens.

## 7. Telegram operations

**Bot provisioning (one-time, human/operator action):**

1. Create a bot with official `@BotFather`; record bot username and bot token.
2. Configure secret environment values (below).
3. Deploy an HTTPS webhook route.
4. Set webhook via Bot API `setWebhook` with a random `secret_token` and the deployed route. Verify via `getWebhookInfo`.
5. Ensure only **one active webhook consumer** owns the bot token. Telegram cannot simultaneously use webhook delivery and long polling (`getUpdates`) for the same bot.

**Registration:** Parse `/start <token>` only in `chat.type="private"`; validate token syntax, hash, look up pending challenge, check expiry and ownership of the challenge via the stored principal, and bind the update's private `chat.id` to that principal atomically. The sender is not asked to type any Telegram ID. Ignore unsolicited `/start` without a token or respond with help instructions; never bind on username or phone number.

**Message sending:** Call `POST https://api.telegram.org/bot<token>/sendMessage` from the backend with JSON:

```json
{
  "chat_id": 123456789,
  "text": "Cordware test notification: your Telegram link is working.",
  "reply_markup": {
    "inline_keyboard": [[
      { "text": "Open Cordware", "url": "https://<configured-cordware-host>/<approved-path>" }
    ]]
  }
}
```

Example uses a **placeholder** chat ID and URL; the actual request uses stored recipient chat ID and server-generated configured HTTPS URL. Prefer an inline URL button rather than putting a bare URL into arbitrary message text. No `web_app`/Mini App mechanism is needed. For this smoke test, never construct a login-bypass link or access-bearing token. URL destination must be trusted and separately authorized by Cordware.

**Failures:** Handle network timeouts, Telegram API `ok:false`, 429 with `retry_after`, bot-blocked / chat-not-found errors (often 403/400), and 5xx. Use bounded retry/backoff for transient failures; avoid duplicate messages where result is ambiguous (Telegram `sendMessage` does not give application-level exactly-once delivery). For a smoke test, a clear one-attempt outcome plus diagnostic reporting is acceptable; do not build a general queue prematurely. Clearly distinguish **accepted by Telegram API** from **delivered to device**, **read**, or **URL opened**; only API acceptance is directly observable here.

## 8. Environment and security configuration

Illustrative names; conform to the existing convention:

```dotenv
TELEGRAM_BOT_USERNAME=<bot_username_without_at>
TELEGRAM_BOT_TOKEN=<secret_from_BotFather>
TELEGRAM_WEBHOOK_SECRET=<random_secret>
TELEGRAM_WEBHOOK_PUBLIC_URL=https://<cordware-host>/utilities/telegramtest/webhook
TELEGRAM_ALLOWED_TARGETS_JSON=<server_side_configured_destination_map>
TELEGRAM_SMOKE_TEST_ENABLED=false
```

- Use Azure App Service settings or Key Vault references, never frontend variables, committed `.env` values, logs, or client responses.
- Restrict tool access via existing dev/admin authorization; a feature flag alone is not access control.
- Rate-limit challenge creation, webhook attempts, and test sends (for example per-user 5/minute and conservative Telegram API limits; adjust after testing).
- Ensure environments are distinct: production and test should preferably have **separate bots** and credentials so test traffic cannot be confused with live organizational alerts.
- Do not send sensitive personnel/case/application content to Telegram. Smoke-test messages should be generic, and the link should not expose sensitive data via query parameters.
- Treat Telegram as an external messaging processor: obtain appropriate institutional/organizational approval before real-user deployment. Allow consent and easy disconnection.
- Test URL handling in Telegram's **in-app browser** and in an external browser; do not promise that a normal inline URL button forces Chrome/Safari. The Entra login flow must remain usable and return to the intended app route.

## 9. End-to-end acceptance criteria

**A. Happy path**

1. An authorized user can load the tool signed into Cordware; initial status is disconnected.
2. Clicking Connect generates a functioning Telegram deep link.
3. Pressing Start in the user's Telegram private chat links that Telegram chat to exactly that authenticated Cordware identity.
4. Status changes to Connected without manual entry of a chat ID.
5. Clicking Send Test produces a Telegram message in the linked account with the selected Cordware URL button.
6. On an Android and/or iPhone as available, tapping the button opens the intended Cordware route. If not authenticated, the user signs in; the destination is restored afterward (if supported by app auth design; otherwise record this as an explicit limitation to resolve before claiming end-to-end success).
7. Disconnect prevents subsequent sends and leaves no active mapping.

**B. Security and failure cases**

- Expired, cancelled, malformed and replayed start tokens do not link accounts.
- `/start` in a Telegram group does not link any user.
- Concurrent webhook callbacks cannot double-consume one token.
- A Telegram chat already linked to another Cordware identity cannot be silently taken over.
- An ordinary user cannot send to anyone else's chat or submit a hand-picked destination URL.
- Unauthenticated UI API calls and webhook calls with incorrect secrets are rejected.
- Repeated Send clicks cannot cause uncontrolled message bursts.
- Bot blocked / nonexistent chat is reported clearly; token and chat IDs are not exposed in browser logs or error details.
- Stale callbacks after disconnect cannot re-enable a deleted link.

**C. Automated tests**

- Unit tests: token generation and expiry; hash matching; URL allowlist; message construction; status transitions; rate limits.
- Integration tests (mock Telegram API): valid webhook, invalid secret, expired/replayed challenge, linking conflicts, success/failure sends and 429 response handling.
- Manual E2E on real Telegram bot + real phone: link, receive, tap URL, authenticate, arrive at target route, disconnect.

## 10. Deliverables for coding agent

1. Working **Telegram Test** page at `/utilities/telegramtest`, linked as the **second tool** on `/utilities/`, and corresponding backend services/routes inside `utilityapps/`.
2. Database migrations (or existing repository persistence mechanism) plus rollback guidance.
3. Telegram adapter isolated behind a small interface (e.g. `sendMessage`, `setWebhook` handled operationally, `processStartUpdate`) for later reuse.
4. `.env.example` / deployment configuration reference **without real secrets**.
5. Operator runbook: BotFather setup; configure Azure settings; register/inspect webhook; verify HTTPS; execute E2E; rotate/revoke bot token; reset stuck links.
6. Automated tests and a concise PR summary specifying known limitations, routes, schema changes, and verification results.
7. A short follow-on note explaining how the smoke-test linking and send adapter could be extracted into a future shared notification service **without implementing that broader service now**.

## 11. Recommended implementation sequence

1. Inspect repo, choose existing auth, storage, routing, authorization and deploy patterns; document decisions.
2. Add configuration and persistent link/challenge model.
3. Implement secure create/status/disconnect APIs and simple UI.
4. Implement webhook parsing, security checks, token consumption and private chat binding.
5. Implement test sender and approved destination URL button.
6. Add negative-path tests, logging, rate limits and secret management.
7. Provision test bot and webhook; run the real-device end-to-end smoke test; document actual outcomes and browser behaviour.

**Definition of done:** A real authenticated user can self-link Telegram and cause an end-to-end Telegram notification with a functioning Cordware link, without a manually supplied chat ID, without exposing the bot token, and without allowing cross-user sends. A successful Telegram API response alone is **not** sufficient to claim the full test passed: the clickable mobile web-app route must be verified.

## 12. Official references

- Telegram bots and BotFather: https://core.telegram.org/bots
- Bot deep linking and `/start`: https://core.telegram.org/bots/features#deep-linking
- Bot API (`sendMessage`, `setWebhook`, `getWebhookInfo`, `InlineKeyboardMarkup`): https://core.telegram.org/bots/api
- Telegram bot FAQ: https://core.telegram.org/bots/faq

---

**Open decisions (do not block implementation):** Tool access policy (super-admin only versus any signed-in user); persistence choice given Utilities currently has no database; first allowlisted Cordware URL beyond the Utilities index; separate bot per environment. Repository, module ownership, public URL and list placement are **decided**. Resolve against repository conventions and record decisions in the PR rather than adding parallel infrastructure.
