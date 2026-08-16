# Deploying to the NUS Azure host — migration runbook

**Goal.** Move the *deployment target* from the personal Azure environment
to the institutional (**NUS**) Azure host, while **continuing to develop and
test on localhost exactly as today**. After NUS is verified and serving,
**retire** the personal Azure web app + resource group.

> **Status: plan.** NUS PRD resources are now provisioned (project **NRRW**,
> subscription `sub-nrrw-prd-reviewrobinweb`, RG `rg-nrrw-prd-compute-01` —
> see §1). A couple of resource names + credentials remain to confirm before
> the first deploy. A manual test workflow (`deploy_nus.yml`) ships with this
> plan but is **not wired to run automatically** — see §6.4.
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

## 1. What NUS has provisioned — and what's left to decide

NUS has provisioned the **PRD** resources (project **NRRW**). Known values:

| Item | Value |
|---|---|
| Subscription | `sub-nrrw-prd-reviewrobinweb` |
| Resource Group | `rg-nrrw-prd-compute-01` |
| Region | Southeast Asia |
| Cloud admin account | `admazclhc` |
| App Service | **Premium V3 (P0V3)** — 1 vCPU / 4 GB / 250 GB, Linux (Always On capable) |
| PostgreSQL | Flexible Server, **Burstable B2S** (2 vCores), Premium SSD, 32 GiB, LRS |
| Key Vault | provisioned — secrets can live here (Key Vault references via managed identity) |
| Storage Account | Block Blob, GPv2, LRS, Hot, 10 GB — **this is the Segment 18Q blob store** (`guide/segment_18Q_blob.md`) |
| Monitoring | Azure Monitor — Log Analytics + Application Insights |

Naming convention observed: `<type>-nrrw-prd-<purpose>-01`.

Still to confirm / decide before the first deploy:

- [x] **Region** — Southeast Asia.
- [x] **SKUs** — App Service **Premium V3 P0V3**; Postgres **Burstable B2S**
  (both comfortably above the dev `F1` / `B1ms`).
- [ ] **Exact resource names** for the Web App and the Postgres server — the
  CSV leaves those "Custom name" cells blank. Likely
  `app-nrrw-prd-reviewrobinweb-01` / `psql-nrrw-prd-reviewrobinweb-01`;
  **confirm the real provisioned names** before filling `NUS_WEBAPP_NAME`
  and `NUS_DATABASE_URL` (§6.2).
- [ ] **DB name + app user** — create `rrw` + `rrw_app` on the B2S server.
- [ ] **Ownership** — do you have Contributor on `rg-nrrw-prd-compute-01`, or
  does NUS IT run the portal steps? (The `admazclhc` admin account suggests
  IT-managed; confirm what you can do yourself.)
- [ ] **Entra tenant** — the NUS tenant; confirm you (or an NUS admin) can
  **create app registrations** and grant **admin consent**.
- [ ] **Networking** — public-access-with-firewall vs **private
  endpoint / VNet**? Drives the migrate-job reachability decision (§5).
- [ ] **Custom domain** under `nus.edu.sg`, or the default
  `*.azurewebsites.net` hostname?
- [ ] **Whitelist** — `SYS_ADMIN_EMAILS` / `OPERATOR_EMAILS` = NUS emails.
- [ ] **Data carry-over** — clean start on NUS, or migrate from personal
  Postgres (§8)?

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
- [ ] **Already provisioned alongside the app — use them, don't re-create:**
  - **Key Vault** — put `DATABASE_URL` / `SMTP_ENCRYPTION_KEY` here and wire
    the App Settings as **Key Vault references** through the Web App's
    managed identity, removing plaintext secrets from App Settings (the
    direction `guide/deferred_infra.md` §1 anticipated). Optional for the
    first deploy; recommended before go-live.
  - **Storage Account** (Block Blob, GPv2) — this is the **Segment 18Q blob
    store**; once NUS is confirmed, 18Q Phase 0 wires to it
    (`guide/segment_18Q_blob.md`). Not needed for the app to run.
  - **Azure Monitor** (Log Analytics + Application Insights) — point App
    Service diagnostics + application logging here.
- [ ] **(Optional, if NUS policy)** App Gateway + WAF, private endpoints —
  see `guide/deferred_infra.md` §1. Add when NUS policy requires.

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

### 6.2 Add NUS-scoped GitHub secrets + a variable

The personal deploy stays live during testing (§6.3–§6.4), so the NUS deploy
needs its **own** secrets rather than overwriting the personal ones. Add
these repository **secrets**:

| Secret | Value |
|---|---|
| `NUS_AZURE_CLIENT_ID` | NUS deploy app-reg **client id** (§6.1) |
| `NUS_AZURE_TENANT_ID` | **NUS tenant id** |
| `NUS_AZURE_SUBSCRIPTION_ID` | **NUS subscription id** (for `sub-nrrw-prd-reviewrobinweb`) |
| `NUS_DATABASE_URL` | `postgresql+psycopg://rrw_app:<pw>@<nus-server>.postgres.database.azure.com:5432/rrw?sslmode=require` |

…and one repository **variable** (not sensitive — it's just a name):

| Variable | Value |
|---|---|
| `NUS_WEBAPP_NAME` | the provisioned Web App name (e.g. `app-nrrw-prd-reviewrobinweb-01` — confirm) |

`deploy_nus.yml` (§6.4) reads exactly these four secrets + one variable.
Keeping them NUS-scoped means the personal deploy's own secrets are
untouched, so both pipelines can run side by side during cutover.

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

> **Parallel-safe cutover — this plan takes this path.** Rather than editing
> the live workflow in place, it adds a **second, manual workflow**
> `deploy_nus.yml` (§6.4) that targets NUS via the NUS-scoped secrets and runs
> only on `workflow_dispatch`. Deploy + verify NUS by hand first; only once
> green do you flip `main`'s `on: push` deploy to NUS and retire the personal
> one (§9, §11). The personal deploy is never disturbed while you validate.

### 6.4 The temporary test workflow — `.github/workflows/deploy_nus.yml`

Shipped with this plan. **It is `workflow_dispatch`-only** — there is
deliberately **no `push` trigger**, so merging it changes nothing and deploys
nothing; it runs only when you manually dispatch it from the **Actions** tab.
Same build → migrate → deploy shape as the personal workflow, but:

- authenticates + targets NUS via the **NUS-scoped secrets** +
  `vars.NUS_WEBAPP_NAME` (§6.2), so it coexists with the personal deploy;
- adds a **`run_migrate`** dispatch input (default `true`) so you can **skip
  the migrate job** and run `alembic upgrade head` out-of-band when the NUS
  DB isn't reachable from a GitHub-hosted runner (§5);
- uses its own `concurrency` group, independent of the personal pipeline.

**To test a NUS deploy — when you're ready, which is *not now*:**

1. Finish §3–§4 (resources + Easy Auth) and §6.1–§6.2 (identity + the four
   `NUS_*` secrets + `NUS_WEBAPP_NAME`).
2. Actions → **Deploy to NUS Azure (manual test)** → *Run workflow* →
   optionally untick `run_migrate` → *Run*.
3. Verify per §10.

Until those prerequisites exist the workflow just sits idle. **Adding the
file starts nothing** — a `workflow_dispatch` workflow never runs on its own.
At final cutover, either promote it to the `on: push` deploy (and retire the
personal workflow) or fold its steps back into the primary workflow.

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

### 7.1 Seed the first admin (operator + admin rights)

Authorization gates on `is_operator OR is_sys_admin`, and **sys-admin implies
operator**, so **one setting seeds a full-rights admin** — no DB surgery:

1. Set the App Setting **`SYS_ADMIN_EMAILS=<admin@nus.edu.sg>`** (the exact
   institutional email that person signs in with; case-insensitive).
   `OPERATOR_EMAILS` is then optional — sys-admin already passes the operator
   gate and additionally unlocks the **Sys Admin** page.
2. **Restart** the app so it reads the setting.
3. That person **signs in once** with that email. On **first sign-in** the
   bootstrap stamps `is_sys_admin = true` on their new `users` row
   (`app/web/deps.py` → `get_or_create_user`). They land on the Sessions
   lobby (not `/request-access`) with the Sys Admin link present.

> **Order matters — set it *before* their first sign-in.** The bootstrap
> fires **only** on first sign-in; once a `users` row exists the env var is
> **inert** (adding/removing an email never changes an existing row). If they
> already signed in first, fix it from Azure Cloud Shell — prefer `UPDATE`
> over `DELETE` (a delete cascades their `session_operators`):
>
> ```sql
> UPDATE users SET is_operator = true, is_sys_admin = true
> WHERE email = '<admin@nus.edu.sg>';
> ```

Additional operators can then be onboarded the same way (each fires on *that*
person's first sign-in) or from the in-app Sys Admin page. Full mechanics +
the first-16A-deploy backfill case: `docs/deployment_dev.md` → "Operator /
sys-admin allowlist bootstrap."

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
