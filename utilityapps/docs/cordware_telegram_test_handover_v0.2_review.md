# Telegram Test handover v0.2 — review note

**Reviews:** `utilityapps/docs/cordware_telegram_test_handover_v0.2.md` ("the handover")  
**Date:** 2026-11-11  
**Status:** Recommendations for the author; nothing here is decided until a segment plan adopts it.  
**Read against:** `utilityapps/` on `main`, `utilityapps/spec/utilities.md`, `cordware/identity.py`, `docs/security_posture.md` and the deployment as the author describes it.

## 1. Link by polling for v1, not by webhook

The webhook (handover §2A "Webhook authentication exception", §6, §7) is the riskiest part, and a smoke test does not need it.

- **Its cost.** It needs inbound posts from Telegram through the host's ingress, a path-scoped Easy Auth exclusion and a secret header.
- **The contract it meets.** `utilityapps/spec/utilities.md` says a tool with a materially different trust boundary becomes its own mount. A route that takes unauthenticated posts from the internet is one.
- **Instead:** **Refresh status** on a pending link calls Telegram's `getUpdates` once, server-side. It looks for a private-chat `/start <token>` and confirms the offset it read.
  - Production runs a single process, so one process polls. That meets Telegram's one-consumer rule (handover §7 step 5).
  - Nothing comes in, so there is no auth exemption.
  - A dev bot works on localhost with no public URL.
- **Later.** Move to a webhook only if this grows into a notification service (handover §10 item 7's note).

This drops §2A's webhook exception, the `webhook` row of §6, §7 steps 3–4 and `TELEGRAM_WEBHOOK_*` from §8. The single-use token, its expiry, private-chat-only binding and conflict refusal (§4, §5, §7 "Registration") stand unchanged.

## 2. Ask for egress and approval first

Two external dependencies could block the work for longer than the code takes. Raise both before the build starts.

- **Egress.** The host's outbound traffic is filtered. Graph is proved from it; `api.telegram.org` is not. Ask for the allow rule, and probe from the host before rung 3.
- **Approval.** Telegram is an external messaging processor; the handover's §8 already calls for institutional approval before real users. For a super-admin-only test, record who agreed and when.

## 3. Keep the link in memory, and say so

Utilities has no database (`utilityapps/spec/utilities.md`, "Utilities has none"). A durable store would need four things:

- a Postgres role and database;
- a migration chain for `utilityapps`;
- an import-pipeline change;
- a rewrite of that contract.

That is heavy for a test that one super-admin uses. Cordware runs a **single process**, so process memory holds a link for as long as the process lives. A restart forgets it, and re-linking takes about 30 seconds.

The handover rules memory out because of multiple instances and restarts (§2A). Cordware has one process, and a restart is acceptable if the page says what it costs. Record it as a known limitation, and put durable storage in the follow-on note.

## 4. Smaller recommendations

- **Access: super-admin only**, the handover's conservative default (§2A). Move `require_super_admin` out of `utilityapps/email_check/routes.py` into a shared Utilities module rather than copying it.
- **CSRF.** "Existing CSRF protections" (§6) means Easy Auth plus `SameSite=Lax`, with no tokens (`docs/security_posture.md`, "CSRF posture"). The new form posts fit it as they stand.
- **Identity.** Key the link on `(tenant_id, principal_id)` from `cordware/identity.py`, never on email. Both are there, and the fake-auth path supplies both.
- **Settings.** The factory "reads no setting" today, so the bot token and username change that contract. Supply them as App Service settings with Key Vault references. The page shows *Not configured* when either is missing, which replaces a separate `TELEGRAM_SMOKE_TEST_ENABLED` flag.
- **Destinations.** Use a fixed server-side list: the host landing page, `/utilities/` and `/reviewrobin/`. Skip a JSON setting for v1 (§8's `TELEGRAM_ALLOWED_TARGETS_JSON`); the form submits a key, never a URL.
- **Phone sign-in.** Which browser a URL button opens is the user's Telegram setting, not Cordware's: Android *Settings → Chat Settings → In-App Browser*; iPhone *Settings → Data and Storage → Open Links in*.
  - **The phone's own browser** (the author's phone, 2026-11-11): sign-in happens where a Microsoft or Cordware session may already exist, under the tenant's usual policies.
  - **Telegram's in-app browser:** Entra may meet the tenant's conditional access or MFA, and its session is separate from the phone's browser, so the user signs in again.
  - **User instructions** should say which to expect, and that turning the in-app browser off gives the smoother sign-in.
  - Treat §9 A6 as the real test. Try both settings and record which browser opened and what sign-in asked for.
  - Easy Auth normally returns to the requested page after sign-in, which covers "preserve the intended destination".
- **Bots.** Use separate dev and production bots (§8). Polling makes the dev bot usable on localhost.
- **Rate limits.** One link challenge and one send per few seconds per user, in memory, is enough for one super-admin. Telegram's 429 `retry_after` is reported, not retried.

## 5. Suggested ladder: segment U3

Scaffold first (CLAUDE.md, "Consequential UI lands scaffold-first"):

1. **Scaffold.** The index's second entry, *Telegram Test*, and the page with each state's card as a static placeholder.
2. **Settings and adapter.** Settings, a Telegram adapter (`get_updates`, `send_message`) and a fake for tests; *Not configured* when unset.
3. **Linking.** Connect, Refresh (link by polling) and Cancel, with the §9 B token cases as tests.
4. **Sending.** Send test and Disconnect, with the §9 B send cases.
5. **Runbook.** The runbook (BotFather, settings, the phone test, token rotation) and the follow-on note: webhook, durable storage, extraction into a notification service.

The egress and approval asks (§2) run alongside rungs 1–2.

## 6. What this changes in the handover's open decisions

| Open decision | Recommendation |
|---|---|
| Tool access | Super-admin only |
| Persistence | Process memory, a stated limitation |
| Webhook auth exemption | None needed: polling |
| First allowlisted URL beyond the index | `/reviewrobin/` |
| Separate bot per environment | Yes: dev and production |
