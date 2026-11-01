# Known limitations

The current shape of Review Robin Web, stated plainly so a pilot
isn't surprised. Most entries are deliberate scope decisions, not
bugs — they trace to the Segment 14A plan and
`guide/deferred_consolidated.md`.

## Deployment / infrastructure

Review Robin has served from the institutional Azure tenant since
2026-10-31, mounted under the Cordware host and deployed from a private
repository that keeps the host's procedures. The personal dev slot is
dormant (`docs/deployment_dev.md`). Re-read 2026-11-01 (segment 20A):
the dev slot's F1 plan, public database, plain-setting secrets and
missing log workspace no longer describe the service, and are struck.

- **Single environment.** One production environment, with no staging
  slot. A release is dispatched by hand from the private repository, and
  production takes no push from here. (The dormant dev slot's push
  workflow is disabled in GitHub's settings.)
- **Production lags `main`.** It runs one imported RRW commit, so a
  merge here reaches it only with the next import and release.
- **No APM.** Logs are structured JSON, and no Application Insights SDK
  is wired in, so there are no traces or per-request metrics beyond
  what the host's platform collects.

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

- **Email not yet wired.** No invitation, reminder or confirmation is
  delivered: the outbox records what *would* be sent, and marks
  invitations and reminders `sent` as it does. Sending is Segment 14B,
  and waits on the choice of sender: Microsoft Graph as the operator
  who clicks, or as a dedicated mailbox (`guide/email_and_scheduling.md`).
  Meanwhile email is optional —
  access is roster + sign-in, so the operator's own email pointing
  at the app URL covers invitations (the in-app Guide at `/guide`,
  "Give reviewers access"). Reminders can already be targeted — the
  per-row `Send reminder` on Invitations, and the Workflow card's
  `Send reminders` to every reviewer who has not submitted — but like invitations they are
  recorded, not delivered; until 14B, chase non-submitters by hand
  from the Responses page's coverage view.
- **Scheduled sends wait for an operator page view.** Scheduled
  activation, invitations and reminders have no clock of their own:
  they fire when an operator next opens that session's Session Home,
  one of its Operations pages (Validate, Assignments, Invitations,
  Responses), or the Sessions lobby (`spec/lifecycle.md` §8.3). A
  reminder set for 09:00 goes out when an operator next looks, and
  nothing fires while nobody opens those pages. A failed invitation or reminder pass is
  logged and audited (`session.scheduled_event_failed`) and retried on the next
  visit; scheduled activation retries a fixed number of times, then
  stops.
  Until a clock-driven trigger lands
  (`guide/post_azure_todo_checklist.md` item 7), open the lobby or
  Session Home at or after each scheduled time.
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
  the two pairs below. `tests/unit/test_contrast_audit.py` sweeps
  every foreground/background pair the palette forms, in both
  themes, and fails on any new pair under AA. Details in
  `spec/color_tokens.md`, "The AA floor on text".
- **Two pairs are under AA and accepted** (author,
  2026-09-12, reviewing the panel). Each is a button label dipping
  **only while the pointer is on it**, where the control is
  comfortably legible at rest — not worth chasing:

  | Hover | At rest | Control |
  |---|---|---|
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
