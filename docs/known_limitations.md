# Known limitations

The current shape of Review Robin Web, stated plainly so a pilot
isn't surprised. Most entries are deliberate scope decisions, not
bugs — they trace to the Segment 14A plan and
`guide/deferred_consolidated.md`.

## Deployment / infrastructure

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
- **Text contrast: fixed 2026-09-12 (19K.7).** This entry used to
  say `--text-muted` failed WCAG AA. That was true when it was
  written and the token was real; 19C Item 6 renamed the palette
  and it became `--text-dim`, which nothing updated here — so the
  name went stale while the fault stayed live, at **2.31:1**
  against the darkest light surface, roughly half the 4.5:1 AA
  asks. Every token in the Text cluster now clears AA against
  every background it is paired with, in both themes.
  `--text-dim` is retired into `--text-subtle` (which moved to
  `#616874`); `--text-link` moved in dark (4.22 → 5.53); the
  decorative uses that kept the old value — dividers, a resize
  grip — moved to `--decor-muted` and are outside the text floor
  by rule, WCAG 1.4.3 governing text. Details in
  `spec/color_tokens.md`, "The AA floor on text".
- **Contrast: the palette clears AA normal in both themes** as of
  2026-09-12 (19K.10). `tests/unit/test_contrast_audit.py` sweeps all
  73 foreground/background pairs the palette forms, in both themes,
  and every one meets 4.5:1 except the three accepted below. The last
  four were a single root cause — white on `--blue-glow` in dark, the
  reserved "you can act on this" shade — and closed together by
  inverting the foreground rather than moving the fill: dark
  `--btn-primary-fg`, `--selected-fg` and `--text-on-accent` took
  `--ink`, giving **5.33** at rest and **6.98** for the hover that had
  been the worst pair in the palette at 2.54.

  That follows the pattern the palette already used: `--text-on-amber`
  is `--white` in light and `--ink` in dark, as is `--btn-alert-fg`,
  because the dark alert fill is bright. The accent family had been the
  outlier. Details in `spec/color_tokens.md`, "The AA floor on text".

- **Three further pairs are under AA and accepted** (author,
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
  edge rather than red — a panel that stops showing what it has
  excused is how an excuse outlives its reason.
- **What the sweep cannot see.** A pair is found only where one
  rule sets both halves, the token names match (`--x-fg` /
  `--x-bg`), the background is a `--surface-*`, or the foreground
  is one of the two the `ON_FILL` map names. Text inheriting
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
