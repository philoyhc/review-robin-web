# Deploying to the NUS Azure host — migration runbook

**Goal.** Move the *deployment target* from the personal Azure environment
to the institutional (**NUS**) Azure host, while **continuing to develop and
test on localhost exactly as today**. After NUS is verified and serving,
**retire** the personal Azure web app + resource group.

> **Status: plan.** NUS account/subscription is not finalized yet. Values
> below are placeholders (`<nus-…>`) to be filled once the account lands.
> This runbook mirrors the *working* dev setup documented in
> `docs/deployment_dev.md` — read that first; NUS is the same topology in a
> different subscription + tenant. Companion runbooks:
> `docs/azure_github_setup.md` (full greenfield Azure+GitHub setup),
> `docs/azure_provision.md` (SKU/pricing shopping list),
> `docs/cli_setup.md` (workstation CLIs), `guide/deferred_infra.md`
> (hardening deferred until a real deployment forces it).

---

## 0. End state at a glance

| Concern | Today | After this migration |
|---|---|---|
| Local dev loop | SQLite + `ALLOW_FAKE_AUTH=true` on localhost | **unchanged** |
| CI (GitHub Actions) | SQLite job + `ci-postgres` job | **unchanged** |
| Deploy trigger | push to `main` → personal Azure | push to `main` → **NUS Azure** |
| App Service | `app-review-robin-web-dev` (personal) | `<nus-webapp>` (NUS) |
| Postgres | personal Flexible Server | **NUS** Flexible Server |
| Sign-in tenant (Easy Auth) | personal Entra tenant | **NUS Entra tenant** |
| Deploy identity (OIDC) | SP in personal tenant | **SP/MI in NUS tenant** |
| Personal Azure | live | **deleted** (final step) |

**Nothing about the deploy-target change touches localhost or CI.** The
local loop reads `.env` (SQLite, fake auth) and never talks to Azure; CI
runs on GitHub runners against SQLite + a throwaway Postgres container. Only
the `deploy`/`migrate` path and the Azure/Entra resources move.

---

## 1. Decisions to lock before touching anything

Fill these in with NUS once the account is finalized — every later step
depends on them:

- [ ] **Ownership model.** Do you get a **subscription with Contributor**
  (you run the `az`/portal steps), or does **NUS IT provision** resources
  from tickets? This decides who does §3–§4. (See `azure_ask.md`.)
- [ ] **Subscription + Resource Group** name/region (NUS-approved region,
  e.g. Southeast Asia).
- [ ] **Resource names** — App Service, App Service Plan, Postgres server,
  DB name (`rrw`), app user (`rrw_app`). Suggest dropping the `-dev` suffix
  (e.g. `app-review-robin-web`, `rg-review-robin-web`).
- [ ] **Entra tenant** = the NUS tenant. Confirm you (or an NUS app admin)
  can **create an app registration** and grant **admin consent** there.
- [ ] **Sign-in audience** — single-tenant (NUS accounts only). Confirm the
  whitelist emails (`SYS_ADMIN_EMAILS` / `OPERATOR_EMAILS`) are NUS emails.
- [ ] **App Service Plan SKU** — move **off `F1`** (no Always On, cold
  starts) to at least **B1**; size per `docs/azure_provision.md`.
- [ ] **Networking policy** — is public-access-with-firewall acceptable, or
  does NUS mandate **VNet integration / private endpoint / App Gateway +
  WAF**? This drives the **migrate-job reachability** decision (§5, called
  out because it's the sharpest gotcha).
- [ ] **Custom domain?** An `nus.edu.sg` subdomain + managed TLS cert, or
  ship on the default `*.azurewebsites.net` hostname.
- [ ] **Data carry-over?** Start NUS with a clean database, or migrate
  existing data from personal Postgres (§8).

---

## 2. What stays the same (do NOT change)

- **Localhost.** `.env` with `ALLOW_FAKE_AUTH=true` + SQLite; `uvicorn
  app.main:app --reload`. Untouched.
- **CI workflows** `.github/workflows/ci.yml` + `ci-postgres.yml`. Untouched.
- **App code + migrations.** No code change is required to change hosts —
  everything is configuration (App Settings + secrets + the deploy
  workflow's target name).

---

## 3. Azure side — provision the NUS environment

Mirror the dev topology (`docs/deployment_dev.md` → "Azure resources") in the
NUS subscription. Can run in parallel while personal Azure keeps serving.

- [ ] **Resource Group** `<nus-rg>` in the approved region.
- [ ] **App Service Plan** — Linux, **B1+** (Always On capable).
- [ ] **Web App** `<nus-webapp>` — runtime **Python 3.12**; startup command:
  ```bash
  gunicorn -w 2 -k uvicorn.workers.UvicornWorker app.main:app
  ```
  Turn **Always On** on; enable **App Service logs → Application logging
  (Filesystem)** so Log stream is populated.
- [ ] **Azure Database for PostgreSQL — Flexible Server** — Postgres **16**,
  region, SKU (**B1ms+**), storage, backup retention. Then create:
  - application database **`rrw`**
  - application user **`rrw_app`** (record its password for `DATABASE_URL`).
- [ ] **DB networking** — per the §1 policy decision:
  - *Public + firewall* (simplest, matches dev): enable "Allow Azure
    services…", add your admin IP for one-off `psql`. **But see §5** for how
    the GitHub-hosted `migrate` job reaches it.
  - *Private endpoint / VNet* (if NUS mandates): the App Service reaches the
    DB via VNet integration; the `migrate` job then needs a network path in
    (self-hosted runner / manual run) — again §5.
- [ ] **(Optional, if NUS policy)** App Gateway + WAF, private endpoints,
  Key Vault for secrets — see `guide/deferred_infra.md` §1. Not required to
  ship; add when NUS policy requires.

---

## 4. Azure side — Easy Auth (sign-in) in the NUS tenant

Sign-in must move to the **NUS Entra tenant** so students/operators log in
with NUS MS365 accounts.

- [ ] **App registration** in the NUS Entra tenant for the web app:
  - Redirect URI: `https://<nus-webapp>.azurewebsites.net/.auth/login/aad/callback`
    (and the custom-domain callback if used).
  - API permissions: `openid`, `profile`, `email` (delegated); **grant admin
    consent** (may require an NUS Entra admin).
  - Single-tenant (NUS only).
- [ ] **App Service Authentication (Easy Auth V2)** on `<nus-webapp>`:
  - Require authentication; unauthenticated → 302 to Entra.
  - Identity provider = the NUS app registration above.
  - **Token store: enabled** (app needs the rich `X-MS-CLIENT-PRINCIPAL`).
  - **Excluded path `/health`** (`authsettingsV2 → globalValidation.excludedPaths`)
    so probes don't bounce through sign-in.
- [ ] Verify (§7) that `/auth/me` returns your NUS identity with
  `provider: "aad"`.

> The app already consumes Easy Auth headers (`app/auth/identity.py`); no
> code change. **Never** set `ALLOW_FAKE_AUTH=true` in App Settings.

---

## 5. Azure side — the migrate-job reachability gotcha ⚠️

The pipeline's **`migrate` job runs `alembic upgrade head` from a
GitHub-hosted runner**, which is **not** inside Azure. Whether that runner
can reach the NUS Postgres depends on the §1 networking choice:

- **Public + firewall:** GitHub runners have **dynamic egress IPs**, so a
  narrow allow-list won't admit them. Today's dev setup works because the DB
  is reachable from the runner; NUS may be locked down. Options, pick one:
  1. **Self-hosted GitHub runner** inside the NUS network/VNet for the
     `migrate` job (cleanest under private networking).
  2. **Run migrations out-of-band** (not in the pipeline): `az webapp ssh`
     into the App Service (which *can* reach the DB) and run `alembic upgrade
     head`, or run it from **Azure Cloud Shell**, then let the pipeline do
     build → deploy only.
  3. **Temporarily widen** the DB firewall for the migrate step (fragile;
     avoid for anything but a one-off).
- **Private endpoint / no public access:** options **(1)** or **(2)** only —
  a GitHub-hosted runner cannot reach a private DB.

**Decide this before the first NUS deploy**, because it may change the
`migrate` job (self-hosted runner label, or removing the job and documenting
a manual migration step). Whatever you choose, keep the invariant: **schema
is migrated before the new code serves** (no startup-time migration hook).

---

## 6. GitHub side — identity, secrets, workflow

Three things move: the **OIDC deploy identity**, the **secrets' values**, and
the **workflow's target app name**.

### 6.1 OIDC federated deploy identity (NUS tenant)

The `deploy` job authenticates with `azure/login@v2` via **OIDC federated
credentials** (no publish profile). Recreate this in NUS:

- [ ] Create an **app registration / service principal** (or a user-assigned
  managed identity) **in the NUS tenant**.
- [ ] Assign it **Contributor** (or **Website Contributor**) on `<nus-rg>` /
  `<nus-webapp>`.
- [ ] Add a **federated credential** on it for this repo:
  - subject `repo:philoyhc/review-robin-web:ref:refs/heads/main`
  - audience `api://AzureADTokenExchange`
  - **If you add a GitHub `environment:`** (recommended, §6.3), add a
    *second* federated credential with subject
    `repo:philoyhc/review-robin-web:environment:<env-name>` — otherwise
    `azure/login` fails with `AADSTS700213` (see `docs/deployment_dev.md`).

### 6.2 Update the GitHub repository secrets

Update the **values** of the existing three OIDC secrets (keep the names to
avoid editing the workflow's `secrets.*` references), plus `DATABASE_URL`:

| Secret | New (NUS) value |
|---|---|
| `AZUREAPPSERVICE_CLIENTID_BE4891FDE16B4522926171BF7D1D779F` | NUS deploy app-reg **client id** |
| `AZUREAPPSERVICE_TENANTID_3B9A113C68284F578982060D01073DFE` | **NUS tenant id** |
| `AZUREAPPSERVICE_SUBSCRIPTIONID_4290DEED4C5F409AB737C5CF65DC8A20` | **NUS subscription id** |
| `DATABASE_URL` | `postgresql+psycopg://rrw_app:<pw>@<nus-server>.postgres.database.azure.com:5432/rrw?sslmode=require` |

> The GUID-suffixed secret names are just names; reusing them keeps the
> workflow untouched. (If you prefer clearer names, rename the secrets **and**
> update the `secrets.*` references in the workflow in the same PR.)

### 6.3 Update the deploy workflow

Edit `.github/workflows/main_app-review-robin-web-dev.yml` (consider renaming
the file to `deploy_nus.yml` and updating the `name:`):

- [ ] `app-name:` → `<nus-webapp>` (in the `deploy` job).
- [ ] Update the workflow `name:` + header comment off the `-dev` app.
- [ ] Reflect the §5 migrate decision (self-hosted `runs-on:` label, or
  drop the `migrate` job in favour of a documented manual step).
- [ ] **(Recommended)** add a GitHub **`environment: nus`** with **required
  reviewers** to gate production deploys — and add the matching federated
  credential (§6.1). This is the "manual approval before production" gate
  sketched in `docs/deployment_dev.md` → "Production deployment (planned)".

> **Parallel-safe cutover option:** instead of editing the live workflow in
> place, add a **second workflow** (`deploy_nus.yml`) triggered by
> `workflow_dispatch` that targets NUS with the NUS secrets. Deploy + verify
> NUS manually first; only once green, flip the `on: push` trigger to the NUS
> workflow and retire the personal one (§9). This never disturbs the working
> personal deploy while you validate NUS.

---

## 7. App Settings (config) on the NUS Web App

Set as **App Service → Configuration → Application settings** (mirror
`docs/deployment_dev.md` → "Environment variables"). All read at process
start — restart after changes.

| Setting | NUS value |
|---|---|
| `APP_ENV` | `production` (any non-`local` value activates fail-fast startup checks) |
| `DATABASE_URL` | same NUS connection string as the GitHub secret (identical value in both places) |
| `SYS_ADMIN_EMAILS` | NUS sys-admin email(s), comma-separated |
| `OPERATOR_EMAILS` | NUS operator email(s), comma-separated |
| `OPERATOR_CONTACT_EMAIL` | contact shown on `/request-access` (optional) |
| `ALLOW_FAKE_AUTH` | **`false`** (must never be true in a deployed env) |
| `LOG_LEVEL` | `INFO` |
| `SMTP_ENCRYPTION_KEY` | Fernet key (only once email infra is in use) |
| `AUDIT_STRICT_MODE` | `false` |

> In a non-`local` `APP_ENV`, the app **refuses to boot** unless at least one
> of `SYS_ADMIN_EMAILS` / `OPERATOR_EMAILS` is non-empty (`validate_critical_settings`).
> Get the whitelist right or the app won't start.

---

## 8. First-time database bootstrap (one-time, on NUS Postgres)

Postgres 15+ denies non-owners `CREATE` on `public`, so `rrw_app` can't
create `alembic_version` until granted. Run **once**, as the **Flexible
Server admin login** (not `rrw_app`), against the `rrw` DB (from Azure Cloud
Shell) — identical to `docs/deployment_dev.md` → "First-time database
bootstrap":

```sql
GRANT ALL ON SCHEMA public TO rrw_app;
GRANT ALL PRIVILEGES ON DATABASE rrw TO rrw_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO rrw_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO rrw_app;
```

**Optional — carry data across.** If you must preserve existing data rather
than start clean:

- `pg_dump` the personal `rrw` DB → `pg_restore` into the NUS `rrw` DB (run
  the GRANT above first; restore as a role with rights). Match Postgres 16 on
  both ends.
- Or, for session-level data only, use the app's own **Extract** (download
  CSVs on personal) → **Rehydrate** (rebuild on NUS) per session.
- Then run `alembic upgrade head` (or let the pipeline's migrate step) so the
  schema is current.

---

## 9. Cutover sequence (recommended order)

1. **Provision NUS** (§3) — parallel; personal still serving.
2. **NUS Easy Auth** app registration + config (§4).
3. **NUS App Settings** (§7), incl. `DATABASE_URL` + whitelist.
4. **DB GRANT bootstrap** (§8); optional data carry-over.
5. **NUS OIDC identity** + RG role + federated credential (§6.1).
6. **Deploy to NUS out-of-band first** — the parallel `deploy_nus.yml` via
   `workflow_dispatch` (§6.3), so nothing on personal is disturbed.
7. **Verify NUS** (§10) end-to-end, including a real smoke-test session.
8. **Custom domain / DNS** if used (§1).
9. **Flip the trigger:** make the NUS workflow the `on: push` deploy; disable
   the personal one. `main` now ships to NUS.
10. **Retire personal Azure** (§11).

---

## 10. Verification checklist (on NUS, before flipping the trigger)

- [ ] `GET https://<nus-webapp>.../health` → `{"status": "ok"}` (unauth).
- [ ] `GET /auth/me` → 302 to **NUS** Microsoft sign-in; after sign-in,
  returns your NUS `email` / `name` / `provider: "aad"`.
- [ ] A **whitelisted** NUS email lands on the **Sessions lobby**; a
  non-whitelisted one is bounced to `/request-access`.
- [ ] `migrate` (or manual migration) applied cleanly — `alembic_version` is
  at head on the NUS DB.
- [ ] Full smoke test: create a session → CSV-import a couple of
  reviewers/reviewees → build an instrument → **Prepare** → **Activate** →
  sign in as a reviewer → submit → **Release** → view results → **Extract**.
- [ ] App Service **Log stream** shows gunicorn/uvicorn output (logging on).

---

## 11. Retire the personal Azure environment (final step)

Only after NUS is verified and serving as primary:

- [ ] Confirm `main` deploys to NUS and NUS is healthy for a few days.
- [ ] **Disable the personal deploy** — remove its `on: push` trigger (or
  delete the personal workflow file).
- [ ] **Delete personal Azure resources** — web app, App Service Plan,
  Postgres Flexible Server, then the **resource group**
  `rg-review-robin-web-dev` (deleting the RG removes everything in it).
- [ ] **Delete the personal Entra app registrations** — both the Easy Auth
  app and the OIDC deploy SP for the personal tenant.
- [ ] **Remove/rotate stale GitHub secrets** if you created NUS-specific new
  ones rather than updating in place.
- [ ] **Docs:** mark `docs/deployment_dev.md` as superseded (or repoint it at
  NUS), and update `docs/status.md` / `docs/architecture.md` topology notes.

---

## 12. Who does what (you vs NUS IT)

Depends on the §1 ownership decision. Typical split when NUS grants you a
subscription with Contributor:

- **You:** §3 provisioning (portal/`az`), §4 Easy Auth config, §6 GitHub
  secrets + workflow, §7 App Settings, §8 GRANT, §9–§11.
- **NUS IT / Entra admin:** subscription + RG + role assignment, **admin
  consent** on the Easy Auth + OIDC app registrations, any mandated
  networking (VNet / private endpoint / App Gateway / WAF), custom-domain DNS
  + cert, firewall policy. Track these asks in `azure_ask.md`.

---

## 13. Open questions to resolve with NUS

- Do we get a subscription (self-serve) or ticket-based provisioning?
- Networking posture — public+firewall vs private endpoint/VNet? (Drives §5.)
- Who can create + admin-consent app registrations in the NUS tenant?
- Custom domain under `nus.edu.sg`, or default hostname?
- Any mandated WAF / App Gateway / logging/monitoring standards?
- Data carry-over required, or clean start on NUS?
