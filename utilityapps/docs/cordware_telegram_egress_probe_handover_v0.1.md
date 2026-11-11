# Cordware — Telegram Outbound Connectivity Probe

**Implementation handover v0.1 — 11 November 2026**  
**Status:** Proposed; no Azure or repository changes made by this document.  
**Host:** `<cordware-host>` stands for the production host, and the Azure resource names are left out: this public repository names neither (filed 2026-11-11). The private deployment notes hold them.

## 1. Purpose and decisive test boundary

Determine whether the **running Cordware Azure App Service** can establish outbound HTTPS connectivity to Telegram Bot API at `https://api.telegram.org:443`, without modifying firewall rules or creating a Telegram bot.

**The probe must execute within the deployed App Service process, not in a GitHub-hosted Actions runner or Azure Cloud Shell.** Those environments have different outbound routes and a successful `curl` there would not answer the question.

This is an **on-demand diagnostic**, not a production notification feature, an account-linking flow, or a recurring health check. No Telegram credentials, user account linkage, database, storage table, or webhook are required.

## 2. Established environment

| Item | Confirmed observation |
|---|---|
| Repository | `https://github.com/philoyhc/review-robin-web` (development source) |
| Azure production domain | `https://<cordware-host>` |
| App Service | Cordware's production App Service |
| App Service public network access | Disabled |
| VNet integration subnet | The production VNet's app integration subnet |
| App traffic routed through VNet | `outboundRouting.applicationTraffic = true` |
| Default UDR | `0.0.0.0/0 → VirtualAppliance` (a central appliance) |
| App Service authentication | Azure Easy Auth v2; unauthenticated requests redirect to login |
| Existing Easy Auth exclusions | `/health`, `/reviewrobin/health`, `/residentialops/health`, `/supportlogs/health`, `/utilities/health` |
| Cloud Shell Telegram test | `https://api.telegram.org` yielded HTTP 302; **does not establish App Service egress** |
| SCM SSH from Cloud Shell | 403 `Ip Forbidden`; not usable for this diagnostic |
| Azure Firewall resources visible in subscription | Zero; central appliance policy not visible |

The route establishes a central network next hop, **not** that Telegram is blocked. No firewall change should be requested unless the App Service-origin test demonstrates a connectivity problem.

## 3. Recommended implementation: restricted, on-demand endpoint

Implement a tiny **temporary diagnostic route** inside existing `utilityapps/`, using its FastAPI mounting and template conventions; do not create a new Azure application.

Proposed route:

`GET /utilities/diagnostics/telegram-egress` — renders an explanation and a button; **does not automatically call Telegram on GET**.

`POST /utilities/diagnostics/telegram-egress/run` — performs exactly one HTTPS test and renders sanitized results.

Implementation can reside at `utilityapps/diagnostics/telegram_egress.py` (or adjacent module matching current conventions), registered through `utilityapps/main.py`. Do not add this as a permanent second utility on the Utilities index; it is an operator diagnostic preliminary to Telegram Test.

**Authorization:** require the existing Cordware **super-admin** role, following `utilityapps/email_check/routes.py` (`resolve_identity(request)` and `identity.is_super_admin`). Easy Auth remains enabled for these routes. **Do not add an Easy Auth `excludedPaths` entry** for the diagnostic. Require CSRF protection for the POST according to existing project conventions (or an explicitly documented same-origin Origin/Referer and CSRF-token mechanism); rate-limit repeated execution. Use `Cache-Control: no-store` on all diagnostic responses. Return a normal 403 for signed-in non-admins and 401/redirect for unauthenticated users as appropriate.

If the production deploy excludes `utilityapps/`, confirm its existing import/deployment path first. Observe repository import boundaries (`utilityapps` may import `cordware` helpers; no imports of `app` or `residentialapps`). Preserve the existing deployed database and migration setup.

### Exact network probe

From the running App Service Python process:

1. Execute a direct HTTPS GET to a fixed Bot API test endpoint using a deliberately **invalid, hard-coded token-shaped path**, e.g. `https://api.telegram.org/bot000000000:INVALID/getMe`. No actual bot token or user data is sent.
2. Verify standard TLS certificate validation and hostname matching; never disable TLS verification (`verify=False` is prohibited).
3. Use short bounded timeouts (e.g. 3 s connect, 7 s total/read), no retries on the initial on-demand probe, and do not follow HTTP redirects. Prefer an already installed HTTP client; avoid new dependencies if practical.
4. Read at most a small bounded response body (e.g. 4 KiB). Do not log complete response bodies or headers. If JSON is returned, report only whether it matches the Telegram Bot API error-envelope shape (`ok: false`, error code and short sanitized description). Do not treat an arbitrary HTTP status as definitive proof of reaching Telegram.
5. Do not accept a user-supplied hostname, URL, IP, token, or path. This is **not** a general-purpose URL tester, so there is no SSRF surface.
6. Record elapsed milliseconds and a coarse classification. Do not persist secrets, raw error bodies, or any user data.

The invalid-token endpoint is intentionally selected so the response can be identified as coming from Telegram's Bot API. A 401 response with Telegram's expected JSON error structure is **expected success for network connectivity**, even though authentication to the Bot API fails by design. This does **not** demonstrate the validity of a future bot token or successful `sendMessage` delivery.

### Sanitized result fields

- `outcome`: `TELEGRAM_REACHABLE`, `DNS_FAILURE`, `CONNECT_TIMEOUT`, `READ_TIMEOUT`, `TLS_FAILURE`, `NETWORK_ERROR`, `HTTP_INTERMEDIARY_OR_UNEXPECTED`, `OTHER_ERROR`.
- `http_status`: numerical status if received.
- `telegram_api_envelope`: boolean (parsed shape; best-effort only).
- `elapsed_ms`: approximate duration.
- `guidance`: one short, operator-friendly sentence.

Avoid displaying raw IP addresses, proxy response bodies, complete exception tracebacks, request headers or authentication cookies. Server-side logging should include only classification, elapsed time and a correlation ID, never the invalid-token path if it might later be replaced.

### Interpretation

| Observation | Interpretation / next action |
|---|---|
| HTTPS succeeds and response matches Telegram Bot API invalid-token JSON | **App Service to Telegram HTTPS egress is working at test time.** No new egress rule appears technically necessary for the API endpoint. |
| DNS lookup fails | Investigate App Service / VNet DNS configuration. Not yet evidence of a firewall egress block. |
| TCP connect timeout/refusal | Possible NSG, route, central firewall or transient network issue. Collect test time and correlation ID for IT. |
| TLS certificate or handshake failure | Possible TLS inspection / trust-chain issue; check network/security configuration. Do not turn off certificate verification. |
| HTML login/block page, HTTP redirect, or non-Telegram HTTP response | Possible proxy/firewall interception or unexpected service behavior; do not call this a pass. |
| HTTP response without expected JSON envelope | HTTPS path may be reachable, but Telegram origin not verified; investigate response metadata carefully without exposing sensitive content. |

A successful probe is **necessary but not sufficient** for the eventual Telegram integration: bot token provisioning, user-initiated Start, webhook ingress, callback validation, and actual message sending remain separate checks. Also, results show access at one point in time; firewall policies can change.

## 4. How GitHub Actions fits in

GitHub Actions is appropriate for **building, testing and deploying the diagnostic code via the existing RRW → private Cordware → Azure release/import workflow**. It is **not appropriate as the network probe execution environment** because a GitHub-hosted runner does not originate traffic from the App Service's integrated VNet subnet.

Recommended sequence:

1. Coding agent implements the feature and unit tests in the public `review-robin-web` repository under `utilityapps/`.
2. Merge through the normal review process; follow established import into the private Cordware deployment repository. Do not bypass the existing separation or connect the public source repository directly to institutional Azure.
3. Deploy through the existing private Cordware GitHub Actions pipeline; do not create new deployment credentials or a one-off Actions runner with elevated network access.
4. A signed-in super-admin opens `https://<cordware-host>/utilities/diagnostics/telegram-egress`, presses **Run probe**, and records the result.
5. If IT needs evidence, supply the timestamp (SGT and UTC), app name, destination `api.telegram.org:443`, classification, and correlation ID — not screenshots containing credentials or full logs.
6. Remove or disable the endpoint when the Telegram Test utility supersedes it. Prefer a feature flag default-off in production if temporary diagnostics are retained.

**Optional automation:** a workflow can *deploy* the code and print a manual verification checklist. Do not add an unauthenticated probe endpoint just so GitHub Actions can invoke it. A remote authenticated invocation would require separate, deliberate credential management and provides little benefit for this one-off check.

## 5. Security and operations constraints

- No firewall, route, VNet, NSG, SCM restrictions, App Service public access, or Easy Auth configuration changes.
- No bot token, Telegram chat ID, database, schema migration, Azure Table Storage or other new Azure resource.
- Do not store the result permanently; use minimal sanitized operational logging consistent with existing logging policy.
- Only super-admins may execute the test; prohibit automated repeated probing and use small timeouts.
- No user-configurable URL or arbitrary outbound destination.
- No adding a new Easy Auth exception: the later Telegram webhook exception is a **separate** requirement and must not be introduced in this deployment.
- Keep all existing routes and `/utilities/health` behavior intact; probe failures must not affect health checks or application startup.
- Validate that the deployed public domain resolves to the intended App Service through the current private ingress path; do not use SCM SSH or disable public-network restrictions to run this test.

## 6. Acceptance criteria for coding agent

- [ ] Diagnostic route is reachable at the stated path by an authenticated Cordware super-admin through the existing production domain.
- [ ] Non-admin cannot run it; unauthenticated caller cannot bypass Easy Auth.
- [ ] GET does not initiate the outbound request; a deliberate POST initiates one bounded attempt.
- [ ] An invalid-token Telegram Bot API JSON response is treated as a network **pass**, not an application authentication failure.
- [ ] DNS, timeout, TLS, interception/non-Telegram response and generic network failures are classified without stack traces or secret leakage.
- [ ] Unit tests mock the outbound HTTP client (no live Telegram dependency in CI), covering all success/failure categories.
- [ ] Timeout, certificate verification, fixed destination and CSRF safeguards are tested.
- [ ] Existing Utilities routes, host mounting, application import boundaries, and authentication conventions remain unchanged.
- [ ] GitHub Actions runs unit tests and follows the existing deployment workflow; no GitHub-hosted runner is presented as evidence of App Service egress.
- [ ] A clear human-readable result permits a yes/no decision on whether to approach the institution's IT about `api.telegram.org:443`.

## 7. Manual operator validation after deployment

1. Sign in at the Cordware production domain with super-admin access.
2. Navigate to `/utilities/diagnostics/telegram-egress`.
3. Click **Run probe** once.
4. Capture result category, elapsed time, and test timestamp.
5. If `TELEGRAM_REACHABLE`: proceed to Telegram bot setup and the later Telegram Test utility, without first requesting an egress exception.
6. If blocked or ambiguous: ask the institution's IT to inspect traffic from the **Cordware VNet integration subnet via the central egress appliance** to `api.telegram.org` on TCP 443, supplying the collected timestamp and result classification. Request a narrowly scoped FQDN-based allowance if supported by the network policy, rather than a broad internet exception.

## 8. Implementation note

The earlier user-facing Telegram Test utility is planned at `/utilities/telegramtest`, with its source under `utilityapps/telegram_test/` and an index entry after Email Address Checker. This probe is a **separate, disposable prerequisite**, and should not create that user-facing utility, register a Telegram bot, or add a webhook yet.
