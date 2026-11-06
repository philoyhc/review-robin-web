# Known limitations

The current shape of Review Robin Web, stated plainly so a pilot
isn't surprised. Most entries are deliberate scope decisions, not
bugs — they trace to the Segment 14A plan and
`guide/deferred_consolidated.md`.

## Deployment / infrastructure

Review Robin has served from the institutional Azure tenant since
2026-10-31, mounted under the Cordware host and deployed from a private
repository that keeps the host's procedures (`docs/deployment.md`). The
personal dev slot is dormant, its notes archived with the deployment
(2026-11-02). Re-read 2026-11-01 (segment 20A):
the dev slot's F1 plan, public database, plain-setting secrets and
missing log workspace no longer describe the service, and are struck.

- **Single environment.** One production environment, with no staging
  slot. A release is dispatched by hand from the private repository, and
  production takes no push from here. (The dormant dev slot's push
  workflow was deleted 2026-11-02.)
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

- **Email goes out one row at a time.** Per-row Send and Send
  reminder send from the operator's own mailbox through delegated
  Microsoft Graph (segment 14F). Bulk sends refuse, and scheduled
  invites and reminders only prompt, until segment 14G
  (`guide/segment_14G_scheduled_email.md`).
  Email stays optional: access is roster + sign-in, so the session
  link on Invitations (Share the session link), or the operator's own
  email pointing at the app URL, covers invitations (the in-app Guide
  at `/guide`, "Give reviewers access"). Chase non-submitters with the
  per-row `Send reminder` on Invitations, or from the Responses page's
  coverage view.
- **Scheduled email only prompts.** RRW's clock (segment 14E) runs
  scheduled activation, the release window and the review's end with
  nobody looking (`spec/lifecycle.md` §8.3). With `RRW_SCHEDULED_SEND`
  off, as deployed, the invite and reminder offsets time a due prompt
  on the Workflow card and a Due pill in the lobby instead of a send,
  cleared by sending or by *Mark as done* (`spec/workflow_card.md`).
  Scheduled activation retries a fixed number of times, then stops.
- **Reviewer answers are not autosaved.** The reviewer surface
  saves only when the reviewer presses Save or Submit, and it has
  no leave-page (`beforeunload`) guard, so navigating away (the
  Previous / Next page links included) or closing the tab loses
  unsaved answers without a prompt.
- **No automatic data expiry.** Nothing is purged on a schedule;
  retention is entirely operator-driven (see
  `docs/operations_runbook.md`).
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
