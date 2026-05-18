# Troubleshooting

Symptom-driven diagnosis for the deployed dev slot. For routine
procedures see `docs/operations_runbook.md`; for resource names
and the deploy pipeline see `docs/deployment_dev.md`.

## Deploy failed

| Where it failed | Likely cause | Fix |
|---|---|---|
| `build` job | packaging / dependency error; `requirements.txt` out of sync with `pyproject.toml` | Read the Actions build log; sync `requirements.txt`. |
| `migrate` job, `permission denied for schema public` | fresh Postgres — `rrw_app` can't create tables | One-time `GRANT` bootstrap — see `docs/deployment_dev.md` → "First-time database bootstrap". Then re-run failed jobs. |
| `migrate` job, other error | a broken migration | Fix the migration, push a new commit. Don't just re-run. |
| `deploy` job, Azure login | OIDC credential / secret problem | Check the `AZUREAPPSERVICE_*` repo secrets. |

`deploy` is skipped whenever `migrate` fails — that is by design,
not a separate failure.

## App returns 500 / error page

The app renders a friendly error page and never leaks a
traceback (Segment 14A PR 2). The traceback **is** logged: open
the Application **Log stream** and look for the
`"unhandled exception"` JSON record — it carries the path and
the full traceback. Reproduce locally with the same input if the
log isn't enough.

## Signed-in user bounced to `/request-access`

The user is authenticated but not on the operator/sys-admin
allowlist (`users.is_operator` / `is_sys_admin` both false). This
is expected for non-operators. If it's wrong for this user, the
usual cause is the **first-sign-in-only** bootstrap rule: editing
`OPERATOR_EMAILS` does not re-promote an account that already has
a `users` row. See `docs/deployment_dev.md` → "Operator /
sys-admin allowlist bootstrap" for the backfill `UPDATE`.

## App won't start after a config change

App Settings are read at process start, so a new env var only
takes effect after a **Restart**. If it still won't start and the
log stream shows a `ConfigurationError`, the PR 6a startup check
(`validate_critical_settings`) is refusing to boot — in a
non-local environment both `OPERATOR_EMAILS` and `SYS_ADMIN_EMAILS`
are empty. Set at least one and restart.

## Database unreachable

- From the running app: check the App Service `DATABASE_URL` App
  Setting and that the Postgres firewall still allows Azure
  services.
- From a developer machine: an office network that blocks
  outbound 5432 can't reach Postgres directly — use Azure Cloud
  Shell. CI is unaffected (it connects from GitHub runners).

## First request after idle is slow

The F1 (free) App Service plan has no Always On and cold-starts.
The first request after an idle period can take several seconds.
This is a plan limitation, not a bug — see
`docs/known_limitations.md`.

## Health check fails

`/health` not returning `{"status": "ok"}` means the worker is
not up. Check the Application Log stream for a startup
traceback; restart the app; if the last deploy's `migrate` step
failed, the app may be running an older revision.
