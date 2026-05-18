# Operations runbook

Day-to-day procedures for operating the deployed Review Robin Web
service. Scoped to the current single Azure **dev** slot — there
is no production environment yet (see `docs/known_limitations.md`).

For the resource names, CI/CD pipeline, and first-time bootstrap,
see `docs/deployment_dev.md`. For symptom-driven diagnosis see
`docs/troubleshooting.md`.

## Deploying a change

Deployment is automatic: a push to `main` triggers the
`build → migrate → deploy` GitHub Actions workflow. There is no
manual step. `migrate` runs `alembic upgrade head` against Azure
Postgres; if it fails the `deploy` job is skipped, so the app is
never served against a stale schema.

To deploy without a code change (e.g. to pick up a config edit),
use the workflow's **Run workflow** (`workflow_dispatch`) button.

## Restarting the app

Azure Portal → App Service `app-review-robin-web-dev` →
**Restart**. Needed after changing an App Setting (env var) —
App Settings are read at process start.

## Health check

```text
GET https://<app>.azurewebsites.net/health  →  {"status": "ok"}
```

`/health` is excluded from Easy Auth, so it answers without
sign-in. A non-200 (or a timeout past the F1 cold-start window)
means the worker is not up — check the log stream.

## Viewing logs

Three streams, all described in `docs/deployment_dev.md` →
"Viewing logs": the GitHub Actions deploy log, the App Service
Deployment Center log, and the live Application **Log stream**.
Application logs are structured JSON (one object per line) — see
`app/logging_config.py`.

## Managing the operator / sys-admin allowlist

Access is gated on `users.is_operator` / `users.is_sys_admin`.
The `OPERATOR_EMAILS` / `SYS_ADMIN_EMAILS` App Settings seed
those columns **on a user's first sign-in only**. The full
procedure — including the first-deploy backfill and how to
promote an already-existing account — is in
`docs/deployment_dev.md` → "Operator / sys-admin allowlist
bootstrap".

In-app revoke UI is not yet shipped (Segment 16A PR 6); until
then, revoking access is a manual `UPDATE users SET is_operator
= false, is_sys_admin = false WHERE email = '…'`.

## Rotating secrets

`DATABASE_URL` lives in two places that must hold identical
values — the App Service App Setting and the GitHub Actions
`DATABASE_URL` secret. Rotate both together, then restart the
app. `SMTP_ENCRYPTION_KEY`, once email infrastructure lands
(Segment 14B), follows the same dual-location pattern. There is
no Key Vault indirection yet (deferred — see
`docs/security_posture.md`).

## Re-running a failed deploy

GitHub → **Actions** → the failed run → **Re-run failed jobs**.
Safe for transient failures (network, a one-off Azure login
blip). If `migrate` failed on a real schema problem, fix the
migration and push a new commit instead — don't just re-run.

## Backups and data

Database backups, restore, and data-retention details are in
`docs/backup_restore.md`.
