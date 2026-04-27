# Development Deployment Notes

## Azure resources

- Resource Group: `rg-review-robin-web-dev`
- Web App Name: `app-review-robin-web-dev`
- Default Domain: `app-review-robin-web-dev-a5c9f3gpfudaambf.southeastasia-01.azurewebsites.net`
- App Service Plan: `ASP-rgreviewrobinweblab-913a (F1: 1)`
- Operating System: `Linux`
- Runtime Stack: `Python 3.12`

## App startup

Startup command:

```bash
gunicorn -w 2 -k uvicorn.workers.UvicornWorker app.main:app
```

## CI/CD workflow

GitHub Actions workflow name:

- `.github/workflows/main_app-review-robin-web-dev.yml`

The workflow triggers on push to `main` (or via `workflow_dispatch`), builds the
app, and deploys to the App Service using OIDC federated credentials. The
client, tenant, and subscription IDs are stored as GitHub repository secrets
(`AZUREAPPSERVICE_CLIENTID_*`, `AZUREAPPSERVICE_TENANTID_*`,
`AZUREAPPSERVICE_SUBSCRIPTIONID_*`) — no publish profile is committed.

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
