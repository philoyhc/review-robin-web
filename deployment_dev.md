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

VNet integration and private endpoints are deferred to Segment 13.

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

There is no startup-time migration hook in the app; that pattern is
fragile under concurrent deploys.

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

Key Vault references for App Settings are deferred to Segment 13. Until
then, rotate by updating both secrets together.

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

## Known issues

- The workflow currently installs from `requirements.txt` rather than
  `pip install -e .[dev]`; keep `requirements.txt` in sync with the runtime
  dependencies in `pyproject.toml`.
- The app runs on the `F1` (free) App Service plan, which can cold-start
  slowly and has no Always On — the first request after idle may take a few
  seconds.
