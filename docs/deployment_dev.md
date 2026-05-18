# Development Deployment Notes

## Azure resources

- Resource Group: `rg-review-robin-web-dev`
- Web App Name: `app-review-robin-web-dev`
- Default Domain: `app-review-robin-web-dev-a5c9f3gpfudaambf.southeastasia-01.azurewebsites.net`
- App Service Plan: `ASP-rgreviewrobinweblab-913a (F1: 1)`
- Operating System: `Linux`
- Runtime Stack: `Python 3.12`
- Database: Azure Database for PostgreSQL Flexible Server, **Burstable
  B1ms**, region **Southeast Asia**, Postgres **16**, 32 GB storage, HA
  disabled, default 7-day backup retention. Application database name
  `rrw`, application user `rrw_app`. See `guide/segment_05A.md` §3.1 for
  the rationale.

### Database networking

Public access is enabled with a firewall allow-list:

- "Allow public access from Azure services and resources within Azure
  to this server" — **enabled** (the App Service reaches the DB this
  way; no VNet integration in dev).
- The developer's current public IP is added to the firewall list for
  one-off `psql` and Alembic runs from the developer machine. Office
  networks that block outbound 5432 will need to use Azure Cloud Shell
  / Cloud CLI instead — that's the verified working path today.

VNet integration and private endpoints are deferred to Segment 14A (production hardening).

## App startup

Startup command:

```bash
gunicorn -w 2 -k uvicorn.workers.UvicornWorker app.main:app
```

## CI/CD workflow

GitHub Actions workflow name:

- `.github/workflows/main_app-review-robin-web-dev.yml`

The workflow triggers on push to `main` (or via `workflow_dispatch`) and
runs three jobs in order: **build → migrate → deploy**.

1. **build** packages `app/`, `alembic/`, `alembic.ini`, `requirements.txt`,
   and `pyproject.toml` into the deployment artifact.
2. **migrate** runs `alembic upgrade head` against Azure Postgres using
   the `DATABASE_URL` GitHub Actions secret. If migration fails, the
   workflow stops here and the deploy job is skipped — the app never
   ships against a stale schema.
3. **deploy** uses OIDC federated credentials to push the artifact to
   the App Service. The client, tenant, and subscription IDs are stored
   as GitHub repository secrets (`AZUREAPPSERVICE_CLIENTID_*`,
   `AZUREAPPSERVICE_TENANTID_*`, `AZUREAPPSERVICE_SUBSCRIPTIONID_*`) —
   no publish profile is committed.

> **Do not add a GitHub `environment:` to the `deploy` job** unless
> you also add a matching Azure AD federated identity credential.
> The OIDC subject claim GitHub presents changes from
> `repo:<owner>/<repo>:ref:refs/heads/main` to
> `repo:<owner>/<repo>:environment:<name>`; with no matching
> federated credential, `azure/login` fails with `AADSTS700213`.

The workflow declares a `concurrency` group so the whole
`build → migrate → deploy` pipeline is **serialized** — two pushes
close together (or a push plus a manual dispatch) queue rather
than running overlapping `alembic upgrade head` / deploys.
`cancel-in-progress` is false, so an in-flight run is never
cancelled mid-migrate or mid-deploy. A future production deploy
workflow will be a small delta on this file once the production
environment exists.

There is no startup-time migration hook in the app; that pattern is
fragile under concurrent deploys.

## Production deployment (planned)

There is **no production environment yet** — the app runs on a
single dev slot. The intended production flow, once the Azure
infrastructure is provisioned, is:

```text
main → deploy to dev → verify → manual approval → deploy/swap to production
```

Provisioning the production side (a production App Service or a
staging slot to swap from, a production Postgres server, a GitHub
`production` environment with required reviewers for the approval
gate, and its own OIDC credentials / `DATABASE_URL`) needs the
Azure portal and is tracked as deferred infrastructure — see
`docs/security_posture.md` → "Deferred hardening" and
`guide/deferred_infra.md`. The production deploy workflow is not
in the repository yet.

## Environment variables

Set as **App Service App Settings** in deployed environments and
in `.env` for local development. All are read at process start —
restart the app after a change.

| Variable | Default | Purpose |
|---|---|---|
| `APP_ENV` | `local` | Environment name. Any value other than `local` activates the fail-fast startup checks (`validate_critical_settings`). |
| `DATABASE_URL` | local SQLite | Database connection string. Postgres in deployed environments — see "Database configuration" below. |
| `LOG_LEVEL` | `INFO` | Root log level for the structured-logging setup. |
| `OPERATOR_EMAILS` | empty | Comma-separated operator allowlist (first-sign-in bootstrap). |
| `SYS_ADMIN_EMAILS` | empty | Comma-separated sys-admin allowlist. In a non-local environment, at least one of these two must be non-empty or the app refuses to boot. |
| `OPERATOR_CONTACT_EMAIL` | unset | Optional contact address shown on the `/request-access` page. |
| `ALLOW_FAKE_AUTH` | `false` | Local-only fake-identity escape hatch. **Must stay `false`** in any deployed environment. |
| `FAKE_AUTH_EMAIL` / `FAKE_AUTH_NAME` / `FAKE_AUTH_PRINCIPAL_ID` / `FAKE_AUTH_OPERATOR` / `FAKE_AUTH_SYS_ADMIN` | dev values | Tune the fake identity; inert unless `ALLOW_FAKE_AUTH=true`. |
| `SMTP_ENCRYPTION_KEY` | unset | Fernet key encrypting operator SMTP passwords at rest. Needed once email infrastructure (Segment 14B) is in use. |
| `AUDIT_STRICT_MODE` | `false` | When true, `audit.write_event` raises on a detail-shape violation. Tests enable it; production leaves it off. |

`APP_NAME`, `APP_VERSION`, and `DEBUG` also exist but are
cosmetic / dev-only.

## Database configuration

`DATABASE_URL` lives in two places, with identical values:

- **App Service App Setting** on `app-review-robin-web-dev` (consumed by
  the running app at request time).
- **GitHub Actions secret** `DATABASE_URL` on the repo (consumed by the
  `migrate` job at deploy time).

Format:

```text
postgresql+psycopg://rrw_app:<password>@<server>.postgres.database.azure.com:5432/rrw?sslmode=require
```

Key Vault references for App Settings are deferred to Segment 14
(production hardening). Until
then, rotate by updating both secrets together.

## First-time database bootstrap

This is a **one-time** step that has to run after the Flexible Server is
provisioned and the application user is created, but **before** the first
deploy's `migrate` job runs.

Postgres 15+ tightened the default privileges on the `public` schema:
non-owners no longer get `CREATE`. So a fresh `rrw_app` connecting to a
fresh `rrw` database can authenticate but cannot create the
`alembic_version` table, and the deploy workflow's `migrate` job fails
with:

```text
psycopg.errors.InsufficientPrivilege: permission denied for schema public
LINE 2: CREATE TABLE alembic_version (
```

Fix it once, from Azure Cloud Shell, connecting as the **Flexible Server
admin login** (not `rrw_app`) to the `rrw` database:

```bash
psql "host=<server>.postgres.database.azure.com port=5432 dbname=rrw user=<admin_user> sslmode=require"
```

Then run:

```sql
GRANT ALL ON SCHEMA public TO rrw_app;
GRANT ALL PRIVILEGES ON DATABASE rrw TO rrw_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT ALL ON TABLES TO rrw_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT ALL ON SEQUENCES TO rrw_app;
```

The first line is the one that unblocks `alembic upgrade head`. The
`ALTER DEFAULT PRIVILEGES` lines belt-and-brace future migrations that
add tables and sequences so the same error doesn't resurface.

After this, re-run the failed workflow (Actions → the failed run →
*Re-run failed jobs*) and the `migrate` job applies cleanly.

## Verifying the database is reachable

From a network with outbound 5432 open (e.g. a home network or Azure
Cloud Shell):

```bash
psql "host=<server>.postgres.database.azure.com port=5432 dbname=rrw user=rrw_app sslmode=require"
```

Office networks that block 5432 outbound will need Azure Cloud Shell /
Cloud CLI for ad-hoc psql sessions. CI and the deploy workflow are
unaffected — they connect from GitHub Actions runners.

## Health check

Once a deployment finishes, verify the app is up:

```text
https://app-review-robin-web-dev-a5c9f3gpfudaambf.southeastasia-01.azurewebsites.net/health
```

Expected response:

```json
{"status": "ok"}
```

The root endpoint `/` returns service metadata pointing at `/health` and `/docs`
and is useful for a quick sanity check in a browser.

## Viewing logs

Three places to look when something goes wrong:

1. **GitHub Actions deployment log** — open the most recent run of the
   `Build and deploy Python app to Azure Web App - app-review-robin-web-dev`
   workflow on GitHub. Build failures, packaging issues, and Azure login
   problems show up here.
2. **App Service deployment log** — in the Azure Portal, open the
   `app-review-robin-web-dev` resource and go to
   *Deployment Center → Logs*. This shows what App Service did with the
   artifact (Oryx build, container start).
3. **Application log stream** — in the Azure Portal, open the App Service and
   go to *Monitoring → Log stream* for live runtime output (gunicorn /
   uvicorn worker logs, Python tracebacks). For this to be populated, ensure
   *Monitoring → App Service logs → Application logging (Filesystem)* is
   turned on.

## Authentication

Azure App Service Authentication ("Easy Auth") V2 is enabled on the dev app.

- **Restrict access:** Require authentication.
- **Unauthenticated requests:** HTTP 302 → Microsoft (Entra ID).
- **Token store:** enabled (so the app receives the rich
  `X-MS-CLIENT-PRINCIPAL` header with claims).
- **Excluded paths:** `/health` (set on `authsettingsV2` →
  `globalValidation.excludedPaths` so probes do not bounce through sign-in).

To verify after a deploy:

1. In a fresh browser, open
   `https://app-review-robin-web-dev-a5c9f3gpfudaambf.southeastasia-01.azurewebsites.net/me`
   — you should be redirected to Microsoft sign-in.
2. After sign-in, `/me` should return JSON with your `email`, `name`,
   `principal_id`, and `provider: "aad"`.
3. `/me/debug` renders the same identity as an HTML page plus the full raw
   claims list and a sign-out link (`/.auth/logout`) — useful for inspecting
   what Entra is sending for this tenant.
4. `curl https://.../health` (unauthenticated) should still return
   `{"status": "ok"}`.

Application code consumes Easy Auth headers; do not enable `ALLOW_FAKE_AUTH`
in App Service configuration. See `docs/authentication.md` for details.

## Operator / sys-admin allowlist bootstrap (Segment 16A)

Under the Option C strict-allowlist posture (16A PR 1), every
operator route gates on `users.is_operator OR users.is_sys_admin`.
A signed-in user with neither flag set is redirected to
`/request-access`. The persisted flags are seeded from two App
Service config env vars on first sign-in:

```
OPERATOR_EMAILS=alice@example.edu,bob@example.edu
SYS_ADMIN_EMAILS=alice@example.edu
```

Comma-separated, case-insensitive. Sys-admin implies operator at
the read-path predicate, so an email in `SYS_ADMIN_EMAILS` alone
also passes the operator gate.

### First-sign-in only — the bootstrap doesn't re-apply

Once a `users` row exists for an email, the env vars are inert
for that row. Editing `OPERATOR_EMAILS` / `SYS_ADMIN_EMAILS` and
restarting the app does **not** promote (or demote) anyone who's
already signed in once. The persisted columns are the
authoritative source of truth after first sign-in; revocation
goes through the in-app workspace user-list UI (16A PR 6, not
yet shipped).

If you change the env vars and need an existing principal to pick
up the new flags before PR 6 ships, you have two manual escape
hatches:

1. **Wipe the row.** Connect to the database as `rrw_app` and
   `DELETE FROM users WHERE email = '<email>'`. The next sign-in
   recreates the row and runs the bootstrap. **⚠ Any
   `session_operators` rows attached to this user cascade-delete**
   — the user loses session access until re-added.
2. **Flip the column directly.** Connect to the database and
   `UPDATE users SET is_sys_admin = true WHERE email = '<email>'`
   (or `is_operator`). Cheaper than a wipe; preserves
   session_operators rows; no audit-event trail (which the 16A
   PR 6 in-app path will emit).

### First 16A deploy: backfill pre-existing user rows

The 16A PR 1 columns shipped inert in 13F PRs 1 + 2 with
`server_default=false`, so every `users` row that existed
**before** the 16A rollout carries `is_operator=False` and
`is_sys_admin=False`. The env-var bootstrap doesn't re-apply to
existing rows (per the rule above), so a workspace owner who
signed in to the dev slot before 16A will get bounced to
`/request-access` on their first post-16A sign-in even though
their email is in `SYS_ADMIN_EMAILS`.

One-time backfill for that pre-existing-account case, in this
order:

1. **Set App Service config first.**
   - `OPERATOR_EMAILS=<comma-separated emails>`
   - `SYS_ADMIN_EMAILS=<comma-separated emails>`
   - Restart the app. Future *new* sign-ins from these emails
     bootstrap automatically; the env-vars-first ordering means
     anyone signing in for the first time hits the bootstrap path
     immediately.

2. **Deploy the 16A PRs** (push to `main`; the GitHub Actions
   workflow runs `migrate` then `deploy`). Wait for both jobs to
   finish.

3. **Backfill the pre-existing rows.** From Azure Cloud Shell:

   ```bash
   psql "host=<server>.postgres.database.azure.com port=5432 \
     dbname=rrw user=rrw_app sslmode=require"
   ```

   Sanity-check the current state:

   ```sql
   SELECT email, is_operator, is_sys_admin
   FROM users
   WHERE email = ANY('{philoyhc@gmail.com}'::text[]);
   ```

   For each row that's there with both flags `false`, run:

   ```sql
   UPDATE users
   SET is_operator = true, is_sys_admin = true
   WHERE email = 'philoyhc@gmail.com';
   ```

   If the row doesn't exist yet, the env-var bootstrap will fire
   on first sign-in — no UPDATE needed.

4. **Sign in.** The gate now passes via `is_sys_admin`.

Prefer `UPDATE` over `DELETE` for this step: a delete cascades to
the user's `session_operators` rows and orphans them from any
sessions they own. The UPDATE leaves session membership intact.

### Local-dev mirror

The same gotcha applies to the local SQLite DB
(`review_robin_web.db`). If you signed in via fake auth before
landing 16A's `FAKE_AUTH_OPERATOR=True` default
(or before adding an email to `OPERATOR_EMAILS` in your `.env`),
your row sits with `is_operator=False` and you'll keep getting
bounced to `/request-access`. Easiest local fix is to delete the
SQLite file and re-run `alembic upgrade head`:

```powershell
Remove-Item review_robin_web.db
alembic upgrade head
```

## Known issues

- The workflow currently installs from `requirements.txt` rather than
  `pip install -e .[dev]`; keep `requirements.txt` in sync with the runtime
  dependencies in `pyproject.toml`.
- The app runs on the `F1` (free) App Service plan, which can cold-start
  slowly and has no Always On — the first request after idle may take a few
  seconds.
