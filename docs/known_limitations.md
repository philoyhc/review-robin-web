# Known limitations

The current shape of Review Robin Web, stated plainly so a pilot
isn't surprised. Most entries are deliberate scope decisions, not
bugs — they trace to the Segment 14A plan and
`guide/deferred_consolidated.md`.

## Deployment / infrastructure

The entries below describe the **personal Azure dev slot**, which is
still the only environment serving the app. The **NUS environment is
provisioned but not yet serving**: a P0V3 App Service, private
Postgres and Key Vault behind private endpoints, an Application
Gateway in front, and Log Analytics with Application Insights. It
waits on a runner VM and a production hostname
(`docs/nus_azure_status.md`). At cutover the F1 and public-database
entries stop applying; secrets stay plain App Settings until Key Vault
references are wired, and the app's logs reach Application Insights
only once diagnostics are pointed at it (`docs/deployment_nus.md` §3).

- **Single environment.** One Azure **dev** slot. There is no
  staging slot and no production environment; no manual-approval
  deploy gate. A push to `main` deploys straight to the dev slot.
- **F1 (free) App Service plan.** No Always On — the app
  cold-starts, so the first request after an idle period can
  take several seconds. Limited CPU/memory.
- **Public database access.** Postgres is reached over public
  access with a firewall allow-list; no VNet integration or
  private endpoints.
- **Secrets as plain App Settings.** `DATABASE_URL` (and later
  `SMTP_ENCRYPTION_KEY`) live as App Service App Settings and
  GitHub Actions secrets — no Key Vault indirection.
- **No Application Insights resource.** Logs are structured JSON
  and ingestible, but no APM resource is wired up yet.

## Authentication / access

- **Easy Auth required in deployment.** The app trusts Azure Easy
  Auth headers for identity; it has no fallback login. It must be
  served behind App Service Easy Auth (see
  `docs/security_posture.md`).
- **First-sign-in-only allowlist bootstrap.** `OPERATOR_EMAILS` /
  `SYS_ADMIN_EMAILS` seed access flags only on a user's first
  sign-in; editing them later does not re-promote an existing
  account. (Later changes are made in-app instead — the Sys Admin
  Accounts Management page admits / revokes / promotes / demotes /
  removes accounts since Segment 18S.)

## Functional scope

- **Email not yet wired — deliberately, until Azure is provisioned.**
  Invitation / reminder email delivery is Segment 14B; today the dev
  outbox records what *would* be sent. This is a decision
  (2026-09-05), not a gap waiting for attention: the dispatch leg
  needs an in-tenant sending identity that exists only once the
  institutional host is provisioned. Meanwhile email is optional —
  access is roster + sign-in, so the operator's own email pointing
  at the app URL covers invitations (the in-app Guide at `/guide`,
  "Give reviewers access"). What
  is genuinely missing is **targeted reminders** to reviewers who
  have not submitted; until 14B, chase them by hand from the
  Responses page's coverage view.
- **Scheduled sends wait for a Session Home visit.** Scheduled
  activation, invitations and reminders have no clock of their own:
  they fire when an operator next opens that session's Session Home,
  the only page that runs the scheduler
  (`app/web/routes_operator/_session_home.py`). A reminder set for
  09:00 goes out when an operator next looks, and nothing fires while
  nobody opens the page. A failed invitation or reminder pass is
  logged (`session.scheduled_event_failed`) and retried on the next
  visit; scheduled activation retries a fixed number of times, then
  stops.
  Until a clock-driven trigger lands after the Azure cutover
  (`guide/post_azure_todo_checklist.md` item 7), open Session Home at
  or after each scheduled time.
- **Reviewer answers are not autosaved.** The reviewer surface
  saves only when the reviewer presses Save or Submit, and it has
  no leave-page (`beforeunload`) guard, so navigating away (the
  Previous / Next page links included) or closing the tab loses
  unsaved answers without a prompt.
- **No automatic data expiry.** Nothing is purged on a schedule;
  retention is entirely operator-driven (see
  `docs/backup_restore.md`).
- **Restore is whole-database only.** No per-session restore;
  recovering one deleted session means a point-in-time restore
  of the entire server.

## Accessibility

- A **basic** pre-pilot accessibility pass was done on the
  reviewer response surface (Segment 14A PR 5) — not a full WCAG
  audit. Nothing since has audited the app as a whole, so the
  entries below are what has been measured, not a clean bill.
- **Text contrast clears AA normal (4.5:1) in both themes**, but for
  the three pairs below. `tests/unit/test_contrast_audit.py` sweeps
  every foreground/background pair the palette forms, in both
  themes, and fails on any new pair under AA. Details in
  `spec/color_tokens.md`, "The AA floor on text".
- **Three pairs are under AA and accepted** (author,
  2026-09-12, reviewing the panel). Each is a button label dipping
  **only while the pointer is on it**, where the control is
  comfortably legible at rest — not worth chasing:

  | Hover | At rest | Control |
  |---|---|---|
  | 3.19 | **7.09** | alert button, light |
  | 3.68 | **5.17** | primary button, light |
  | 3.95 | **4.83** | destructive button, light |

  The acceptance is conditional and the condition is checked, not
  trusted: each entry names the resting pair it rests on, and the
  suite fails if that pair stops clearing AA. Darken a button's
  resting fill and the hover exemption dies with it. They stay
  visible in the customizer's Contrast panel, marked with a dashed
  edge rather than red.
- **What the sweep cannot see.** A pair is found only where one
  rule sets both halves, the token names match (`--x-fg` /
  `--x-bg`), the background is a `--surface-*`, or the foreground
  is the one the `ON_FILL` map names. Text inheriting
  a background from a distant ancestor is invisible to all three
  and no static reading of the stylesheet will find it.
- **Not yet measured at all:** keyboard-only navigation end to
  end, screen-reader output, focus order, and non-text contrast
  beyond `--border-default` (3:1, 19C Item 8).

## Operational

- **No rehearsed restore drill.** Backup/restore is documented
  but untested on this deployment.
- **`requirements.txt` is hand-synced.** The deploy installs from
  `requirements.txt`, which must be kept in step with the runtime
  dependencies in `pyproject.toml`.
