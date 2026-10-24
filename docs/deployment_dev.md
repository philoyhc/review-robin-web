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
  `rrw`, application user `rrw_app`. See `guide/archive/segment_05A.md` §3.1
  for the rationale.

### Database networking

Public access is enabled with a firewall allow-list:

- "Allow public access from Azure services and resources within Azure
  to this server" — **enabled** (the App Service reaches the DB this
  way; no VNet integration in dev).
- The developer's current public IP is added to the firewall list for
  one-off `psql` and Alembic runs from the developer machine. Office
  networks that block outbound 5432 will need to use Azure Cloud Shell
  / Cloud CLI instead — that's the verified working path today.

VNet integration and private endpoints are deferred infrastructure —
see `guide/deferred_consolidated.md` and `docs/security_posture.md`
("Deferred hardening").

## App startup

Startup command, once the slot resumes (step 3 of "Resuming the dev
slot" below; the dormant slot is still set to `app.main:app`):

```bash
gunicorn -w 2 -k uvicorn.workers.UvicornWorker cordware.main:app
```

## CI/CD workflow

GitHub Actions workflow name:

- `.github/workflows/main_app-review-robin-web-dev.yml`

**Dormant since 2026-06-03.** The workflow is `disabled_manually` on
GitHub, so it runs on neither push nor `workflow_dispatch`, and the slot
still serves a build from that date or earlier. All testing is on
localhost until the Azure work settles (author, 2026-10-21). **It is not
being revived** (author, 2026-10-24: one Azure host is enough): segment
21D's live check under real Easy Auth runs on the institutional
deployment's first release instead. Should the slot ever come back, bring
it back with "Resuming the dev slot" below, not by re-enabling the
workflow alone.

When enabled, the workflow triggers on push to `main` (or via
`workflow_dispatch`) and runs three jobs in order: **build → migrate →
deploy**.

1. **build** installs `requirements.txt` into a prebuilt `antenv/`
   virtualenv and packages `app/`, `cordware/` (the host, segment 21A),
   `alembic/`, `alembic.ini`,
   `requirements.txt`, `pyproject.toml` and `antenv/` into the deployment
   artifact, so App Service uses that venv rather than re-running the build.
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
cancelled mid-migrate or mid-deploy. This workflow serves only the
personal dev slot; production is not deployed from this repository
("Production deployment" below).

There is no startup-time migration hook in the app; that pattern is
fragile under concurrent deploys.

## Resuming the dev slot

Not planned (above): kept in case the slot is ever wanted again. The
slot has been dormant since 2026-06-03. Meanwhile segment 21
moved RRW under the Cordware host, at `/reviewrobin`
(`guide/archive/segment_21_domain_retrofit.md`, closed 2026-10-22).
`main` has moved on since then, so do these steps in order, in the
Azure portal and on GitHub, when Azure is available. Each step names the
change on `main` that makes it necessary; every one of them has landed.

1. **`APP_ENV`** (needed for 21C's guard): set it to a non-`local`
   value such as `dev`. Cordware refuses to start with `ALLOW_FAKE_AUTH`
   on and `APP_ENV` anything but `local`, so a deployed environment
   names itself, and keeps `ALLOW_FAKE_AUTH` `false`.
2. **Re-enable the workflow**: Actions → the workflow → *Enable workflow*,
   or `gh workflow enable main_app-review-robin-web-dev.yml`. Then
   dispatch it, or let the next push to `main` run it. Its migrate job
   brings the dev database from the June head up to the current one, and
   its deploy job runs only once that succeeds.
3. **Startup command** (needed since 21A's A2 removed `app.main:app`):
   once step 2's deploy job has succeeded, and not before, change it to
   `gunicorn -w 2 -k uvicorn.workers.UvicornWorker cordware.main:app`.
   The workflow does not set it. The June build the slot serves predates
   21A's A1 and has no `cordware.main`, so the new command set early
   would take the slot down, and a failed migrate would leave it down;
   the new build has no `app.main`, so between the deploy and this
   change the slot does not start. Make the change straight after the
   deploy.
4. **Easy Auth's excluded paths** (needed since 21D's D2 moved RRW to
   `/reviewrobin`): add `/reviewrobin/health` beside
   `/health` in `authsettingsV2` → `globalValidation.excludedPaths`, so
   both probes answer without sign-in. `/health` is the host's;
   `/reviewrobin/health` is RRW's.
5. **Check** `/health` and `/reviewrobin/health` unauthenticated. Then
   sign in through Easy Auth and reach the lobby. Then, if the
   institutional deployment has not already run it, run the live
   check 21D's plan owes, v0.8 §3's four behavior
   requirements under real Easy Auth
   (`docs/archive/cordware_repository_strategy_v0.8.md` §3):
   - **Deep links:** signed out, open a deep link such as
     `/reviewrobin/operator/sessions`; sign-in returns to it. Sign out
     (`/.auth/logout`, the host's) and sign in again from `/`, which
     redirects to `/reviewrobin/`.
   - **Probes:** both health paths answer `{"status": "ok"}`, signed
     out.
   - **Request handling:** a missing page such as
     `/reviewrobin/operator/no/such/page` shows RRW's own 404 page.
   - **Absolute URLs:** an invitation sent from the slot links to
     `https://<the slot's host>/reviewrobin/me/invite/…`. On the slot
     that host is its own `azurewebsites.net` name, so this shows the
     request's host and the mount carried through, not that a gateway's
     public name replaces the backend's: that half is stage 4's, behind
     the gateway.
6. **Record it:** clear this section's "dormant" note above, and set the
   segment 21 plans' dev-slot lines to done.

## Production deployment

Production is the **institutional Azure host**, provisioned but not yet
serving. It is not promoted through this slot: there is no
`dev → approve → production` pipeline and no staging slot to swap from.
Instead a chosen `main` commit, with CI green, is imported and released
privately, built on an unprivileged runner and migrated and deployed
from inside the institution's network. Its workflows, credentials,
approval gate and runbook are kept privately with the deployment, and
nothing in this repository can reach it. The last public statement of
that strategy is `docs/archive/cordware_repository_strategy_v0.8.md`
§5.

**One Azure host** (author, 2026-10-24): the dev slot is not revived for
the institutional release. Segment 21D's live check under real Easy
Auth runs on that release ("CI/CD workflow" above). This document stays
the record of the dormant slot, should it ever be wanted again.

## Environment variables

Set as **App Service App Settings** in deployed environments and
in `.env` for local development. All are read at process start —
restart the app after a change.

| Variable | Default | Purpose |
|---|---|---|
| `APP_ENV` | `local` | Environment name. Any value other than `local` activates the fail-fast startup checks (`validate_critical_settings`). |
| `CORDWARE_APPS` | unset | The applications the Cordware host mounts, comma-separated (`cordware/main.py`). Unset mounts every registered application (today only `reviewrobin`); an empty value runs the host alone, with its landing page and `/health`. |
| `DATABASE_URL` | local SQLite | Database connection string. Postgres in deployed environments — see "Database configuration" below. |
| `LOG_LEVEL` | `INFO` | Root log level for the structured-logging setup, which the Cordware host owns (`cordware/logging.py`, segment 21A). |
| `OPERATOR_EMAILS` | empty | Comma-separated operator allowlist (first-sign-in bootstrap). |
| `SYS_ADMIN_EMAILS` | empty | Comma-separated sys-admin (admin) allowlist. In a non-local environment, at least one of these two must be non-empty or the app refuses to boot. |
| `SUPER_ADMIN_EMAILS` | empty | Comma-separated **super-admin** allowlist — the protected top tier (Segment 18S). Derived, not stored; set **only** here. Optional (not part of the boot fail-fast). A super-admin can't be demoted/removed in-app and is the only actor who can promote/demote admins. |
| `OPERATOR_CONTACT_EMAIL` | unset | Optional contact address shown on the `/about` access card. |
| `ALLOW_FAKE_AUTH` | `false` | Local-only fake-identity escape hatch. **Must stay `false`** in any deployed environment. |
| `FAKE_AUTH_EMAIL` / `FAKE_AUTH_NAME` / `FAKE_AUTH_PRINCIPAL_ID` / `FAKE_AUTH_OPERATOR` / `FAKE_AUTH_SYS_ADMIN` / `FAKE_AUTH_SUPER_ADMIN` | dev values | Tune the fake identity; inert unless `ALLOW_FAKE_AUTH=true`. `FAKE_AUTH_SUPER_ADMIN` (default on) makes the local fake operator a super-admin. |
| `SMTP_ENCRYPTION_KEY` | unset | Fernet key encrypting operator SMTP passwords at rest. **Needed now**: the operator Settings page stores each operator's SMTP credentials, and saving them fails without a valid key (no transport sends mail yet; Segment 14B). Rotating it leaves stored passwords undecryptable, so operators re-enter theirs. |
| `SCHEDULED_OPERATIONAL_LEAD_HOURS` | `1` | Minimum lead time, in hours, between now and a scheduled activation set at save, and between now and each resolved auto-send fire moment (`spec/settings_inventory.md` §2). |
| `REVIEWER_NOTICE_MIN_HOURS` | `1` | Minimum `\|offset\|`, in hours, of each auto-send invite or reminder offset (`spec/settings_inventory.md` §2). |
| `REHYDRATE_ENABLED` | `false` | Opens the Rehydrate surface. Off by default and deferred; the test suite turns it on. |
| `AUDIT_STRICT_MODE` | `false` | When true, `audit.write_event` raises on a detail-shape violation. Tests enable it; production leaves it off. |

`APP_VERSION` also exists and is cosmetic: it labels the build in
the operator top bar and on the About page.

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

Key Vault references for App Settings are deferred infrastructure
(see `guide/deferred_consolidated.md`). Until then, rotate by updating
both secrets together.

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

The root endpoint `/` does not serve a JSON body. Once 21D is deployed it
302-redirects to `/reviewrobin/`, RRW's root, which sends a signed-in
operator to `/reviewrobin/operator/sessions` and anyone else to
`/reviewrobin/me`. `/health` is the host's liveness endpoint and
`/reviewrobin/health` is RRW's.

## Viewing logs

Three places to look when something goes wrong:

1. **GitHub Actions deployment log** — open the most recent run of the
   `Build and deploy Python app to Azure Web App - app-review-robin-web-dev`
   workflow on GitHub. Build failures, packaging issues, and Azure login
   problems show up here.
2. **App Service deployment log** — in the Azure Portal, open the
   `app-review-robin-web-dev` resource and go to
   *Deployment Center → Logs*. This shows what App Service did with the
   artifact (unpacking it, starting the container). No Oryx build runs:
   the package ships a prebuilt `antenv/`.
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
  `globalValidation.excludedPaths` so probes do not bounce through sign-in);
  `/reviewrobin/health` joins it when the slot resumes on a build with 21D
  (step 4 of "Resuming the dev slot").

To verify after a deploy (RRW's paths are under `/reviewrobin` once 21D
is deployed; on an older build, drop the prefix):

1. In a fresh browser, open
   `https://app-review-robin-web-dev-a5c9f3gpfudaambf.southeastasia-01.azurewebsites.net/reviewrobin/auth/me`
   — you should be redirected to Microsoft sign-in.
2. After sign-in, `/reviewrobin/auth/me` should return JSON with your
   `email`, `name`, `principal_id`, and `provider: "aad"`.
3. `/reviewrobin/auth/me/debug` renders the same identity as an HTML page
   plus the full raw claims list and a sign-out link (`/.auth/logout`, the
   host's) — useful for inspecting what Entra is sending for this tenant.
4. `curl https://.../health` and `curl https://.../reviewrobin/health`
   (unauthenticated) should still return `{"status": "ok"}`.

Application code consumes Easy Auth headers; do not enable `ALLOW_FAKE_AUTH`
in App Service configuration. See `docs/security_posture.md` for details.

## Operator / sys-admin allowlist bootstrap (Segment 16A)

Under the Option C strict-allowlist posture (16A PR 1), every
operator route gates on `users.is_operator OR users.is_sys_admin`.
A signed-in user with neither flag set is redirected to
`/me`. The persisted flags are seeded from two App
Service config env vars on first sign-in:

```
OPERATOR_EMAILS=alice@example.edu,bob@example.edu
SYS_ADMIN_EMAILS=alice@example.edu
```

Comma-separated, case-insensitive. Sys-admin implies operator at
the read-path predicate, so an email in `SYS_ADMIN_EMAILS` alone
also passes the operator gate.

**Super-admin (the protected top tier, Segment 18S)** is a third,
config-only list:

```
SUPER_ADMIN_EMAILS=admin@example.edu
```

Unlike the two above it is **derived, not stored** — `is_super_admin`
is computed from this list on every request, never persisted to a
column, so it can't be flipped in-app and needs no migration. A
super-admin self-heals to full admin rights on **every** sign-in
(so it also fixes an already-existing row, unlike the once-only
operator/sys-admin bootstrap below), is the only actor who can
promote/demote admins, and can't be demoted / revoked / removed
in-app. It's optional (not part of the boot fail-fast), but setting
it guarantees ≥1 protected admin. Local dev doesn't need it — with
`ALLOW_FAKE_AUTH=true`, `FAKE_AUTH_SUPER_ADMIN` (default on) makes the
fake operator a super-admin.

### First-sign-in only — the bootstrap doesn't re-apply

Once a `users` row exists for an email, the env vars are inert
for that row. Editing `OPERATOR_EMAILS` / `SYS_ADMIN_EMAILS` and
restarting the app does **not** promote (or demote) anyone who's
already signed in once. The persisted columns are the
authoritative source of truth after first sign-in. Ongoing
role changes go through the **in-app Sys Admin page**
(`/operator/sys-admin/users`, sys-admin only): invite a new
user by email, admit / revoke operator status, promote / demote
sys-admin, and remove a user — each audited, with a last-sys-admin
floor. (Shipped in Segment 16A; the earlier "PR 6 not yet shipped"
note is retired.)

If you change the env vars and need an *existing* principal to
pick up new flags — or want to fix roles straight from the
database — you have two manual escape hatches (the in-app Sys
Admin page is the normal path):

1. **Wiping the row usually fails.** `DELETE FROM users` does not
   cascade: `session_operators.user_id`,
   `sessions.created_by_user_id` and
   `audit_events.actor_user_id` reference `users.id` with no
   `ON DELETE`, so Postgres refuses the delete for any user who has
   owned or created a session or has an audit row. Use the `UPDATE`
   below instead.
2. **Flip the column directly.** Connect to the database and
   `UPDATE users SET is_sys_admin = true WHERE email = '<email>'`
   (or `is_operator`). Preserves session_operators rows; leaves no
   audit-event trail, unlike the in-app Sys Admin path, which
   writes one.

### First 16A deploy: backfill pre-existing user rows

The 16A PR 1 columns shipped inert in 13F PRs 1 + 2 with
`server_default=false`, so every `users` row that existed
**before** the 16A rollout carries `is_operator=False` and
`is_sys_admin=False`. The env-var bootstrap doesn't re-apply to
existing rows (per the rule above), so a workspace owner who
signed in to the dev slot before 16A will get bounced to
`/me` on their first post-16A sign-in even though
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

Use `UPDATE`, not `DELETE`, for this step: the foreign keys that
reference `users.id` have no `ON DELETE`, so a delete fails for any
user who owns or created a session or has an audit row. The UPDATE
leaves session membership intact.

### Local-dev mirror

The same gotcha applies to the local SQLite DB
(`review_robin_web.db`). If you signed in via fake auth before
landing 16A's `FAKE_AUTH_OPERATOR=True` default
(or before adding an email to `OPERATOR_EMAILS` in your `.env`),
your row sits with `is_operator=False` and you'll keep getting
bounced to `/me`. Easiest local fix is to delete the
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
