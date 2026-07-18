# RRW — Azure + GitHub Setup: Step-by-Step & Checklist

**Version:** 0.1 (draft)
**Scope:** Production (PRD) + Non-Production (NPRD) environments for Review Robin Web, per the corrected IT quote: App Service (P0v3 PRD / B2 NPRD), **PostgreSQL Flexible Server** (corrected from Azure SQL), Application Gateway WAF v2 (retained per policy), Storage, Key Vault, App Configuration, Functions (consumption), Communication Services (email).
**Audience:** Handoff to Claude Code. Items marked `[MANUAL]` need portal/human action (typically IT-controlled or requiring browser auth); everything else is scriptable via `az` CLI / GitHub CLI.
**Repo:** `philoyhc/review-robin-web`

---

## Phase 0 — Prerequisites & Conventions

- [ ] Confirm subscription access: which subscription, and what role you hold on it (need at least **Contributor** on the resource groups; **User Access Administrator** or IT assistance for role assignments in Phase 4)
- [ ] Confirm who controls Entra app registrations — self-service or IT-gated? `[MANUAL if gated]`
- [ ] Tooling installed locally: `az` CLI (logged in: `az login`), `gh` CLI (authenticated), `psql` client
- [ ] Naming convention — IT has assigned project acronym **NRRW**; all Azure-visible resource names use it:
  - Resource groups: `rg-nrrw-prd`, `rg-nrrw-nprd`
  - Plan/app: `asp-nrrw-prd`, `app-nrrw-prd` (and `-nprd` variants)
  - Postgres: `psql-nrrw-prd`, `psql-nrrw-nprd`
  - Key Vault: `kv-nrrw-prd` (globally unique — check availability)
  - Gateway: `agw-nrrw-prd`; VNet: `vnet-nrrw-prd`
  - Deployment identity (Phase 4): `id-nrrw-github-deploy`
  - GitHub repo name stays `review-robin-web` — repo naming is yours, not IT's; the OIDC subject strings reference the repo path and are unaffected
- [ ] Confirm with IT whether NRRW must appear in any *other* conventions (tag values, subscription/RG placement, cost-center codes)
- [ ] Region: **Southeast Asia** for everything (match the quote)
- [ ] Tags for cost tracking: `project=nrrw`, `env=prd|nprd` on every resource

> **Note:** The App Gateway requires a **VNet with a dedicated subnet** and a **public IP** — neither appears as a quote line (VNets are free; the public IP is ~$4/mo). Flag to IT so it doesn't surprise anyone.

---

## Phase 1 — Core Infrastructure (per environment; do NPRD first as rehearsal)

- [ ] Create resource group (`az group create`)
- [ ] Create App Service Plan — Linux, P0v3 (PRD) / B2 (NPRD)
- [ ] Create Web App on the plan — runtime stack per RRW (Python version pinned to match local dev)
  - [ ] Enable **HTTPS only**; set minimum TLS 1.2
  - [ ] Enable **system-assigned managed identity** (used for Key Vault access)
- [ ] Create **PostgreSQL Flexible Server** — Burstable B1ms/B2s, 32 GB, Southeast Asia
  - [ ] Set admin username/password → store immediately in Key Vault, nowhere else
  - [ ] Confirm backup retention (7 days default) and **PITR is enabled**
  - [ ] Networking: start with **public access + firewall rules** (no VNet integration on the quote). Add rules: (a) "Allow Azure services" ON *(coarse but simplest; revisit if IT objects)*, (b) your own IP for admin `psql` sessions
- [ ] Create Storage account (Standard LRS) — container(s) for RRW file needs
- [ ] Create Key Vault
  - [ ] Grant the Web App's managed identity **Key Vault Secrets User** (RBAC model)
  - [ ] Grant yourself Secrets Officer for setup
- [ ] Create App Configuration store (free/standard per quote) — optional to wire up on day one; Key Vault + app settings may suffice initially
- [ ] Create Communication Services + Email Communication Service; provision the Azure-managed domain (or connect custom domain later `[MANUAL — DNS]`)
- [ ] Function App (consumption) — **defer until there's an actual function**; nothing blocks on it

---

## Phase 2 — Database Setup

- [ ] Connect as admin (`psql`) and create the application database: `CREATE DATABASE rrw;`
- [ ] Create least-privilege application role:
  ```sql
  CREATE ROLE rrw_app LOGIN PASSWORD '<generated>';
  GRANT CONNECT ON DATABASE rrw TO rrw_app;
  -- after schema exists / in migrations:
  GRANT USAGE ON SCHEMA public TO rrw_app;
  GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO rrw_app;
  ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO rrw_app;
  ```
- [ ] Store `rrw_app` connection string in Key Vault as `rrw-db-connection`
- [ ] Web App setting `DATABASE_URL` = Key Vault reference: `@Microsoft.KeyVault(SecretUri=...)`
- [ ] Verify from a local machine that the app role can connect and the admin role is **not** used by the app
- [ ] Decide migration mechanism (Alembic / raw SQL runner) and where migrations run — see Phase 6

> **Future-proofing (silent):** the server can host additional databases with disjoint roles at no cost. Nothing to do now; just don't grant `rrw_app` server-level privileges.

---

## Phase 3 — Identity: Entra App Registration + Easy Auth

- [ ] Create app registration for RRW `[MANUAL if IT-gated]`
  - [ ] **Multi-tenant** (accounts in any organizational directory) — per RRW's existing design
  - [ ] Redirect URI: `https://<app-hostname>/.auth/login/aad/callback` (add the custom/gateway domain later too)
  - [ ] Create client secret → Key Vault (`rrw-aad-client-secret`); set expiry reminder (max 24 mo)
- [ ] Configure **Easy Auth** on the Web App:
  - [ ] Provider: Microsoft; client ID + secret (Key Vault reference)
  - [ ] Issuer: `https://login.microsoftonline.com/common/v2.0`
  - [ ] Restrict access: **Require authentication**; unauthenticated → HTTP 302 login redirect
  - [ ] **Exclude a health-check path** (e.g. `/healthz`) from auth — the App Gateway probe (Phase 5) must reach it anonymously
- [ ] Port RRW's **tenant allowlist / issuer validation** middleware config (the `tid` claim check) — app-level, from existing RRW code; confirm the allowlist source (env var / App Config)
- [ ] Test login round-trip from an allowed tenant and rejection from a disallowed one (personal MSA, etc.)

---

## Phase 4 — GitHub Integration (deploy via OIDC — no publish-profile secrets)

- [ ] Create the deployment identity: either a **user-assigned managed identity** or an app registration used only for CI
- [ ] Add **federated credentials** on it for GitHub OIDC:
  - Issuer: `https://token.actions.githubusercontent.com`
  - Subject (PRD): `repo:philoyhc/review-robin-web:environment:production`
  - Subject (NPRD): `repo:philoyhc/review-robin-web:environment:staging`
- [ ] Role assignment: grant it **Website Contributor** scoped to each `rg-rrw-*` (or just the Web Apps) `[MANUAL if you lack User Access Administrator]`
- [ ] In GitHub repo settings:
  - [ ] Create **environments** `production` and `staging`; on `production`, enable required reviewer (you) so PRD deploys need a click
  - [ ] Environment variables: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_WEBAPP_NAME` (no secrets needed — that's the point of OIDC)
- [ ] Workflow `.github/workflows/deploy.yml`:
  - [ ] Trigger: push to `main` → deploy `staging`; manual approval gate (environment protection) → deploy `production`. (Or: tag-based PRD deploys — decide and record.)
  - [ ] Jobs: checkout → setup Python (pinned) → install deps → **run tests** → `azure/login@v2` (OIDC) → `azure/webapps-deploy@v3`
  - [ ] Concurrency group so parallel deploys queue rather than race
- [ ] First deploy to NPRD from a branch; verify app boots, `/healthz` returns 200, login works
- [ ] First PRD deploy through the approval gate

> This mirrors the DBR lesson: deployment is `git push` + CI, never a manual upload. Keep `clasp push`-style manual paths out of the runbook entirely.

---

## Phase 5 — Application Gateway (WAF v2) in Front

- [ ] Create VNet `vnet-nrrw-prd` with dedicated subnet `snet-agw` (≥ /26)
- [ ] Create public IP (Standard, static)
- [ ] Create App Gateway WAF v2:
  - [ ] Backend pool → the Web App (App Service backend target)
  - [ ] Backend settings: HTTPS, **pick hostname from backend target** ON (App Service needs correct host header)
  - [ ] Health probe → `/healthz` (the auth-excluded path from Phase 3); confirm 200
  - [ ] WAF policy: start **Detection** mode; review logs for a week; switch to **Prevention** `[decision point]`
- [ ] Custom domain: DNS CNAME/A to the gateway public IP `[MANUAL — DNS via IT]`
  - [ ] TLS certificate on the gateway listener (App Service managed certs don't apply here — source cert from IT / Key Vault) `[MANUAL likely]`
  - [ ] Add the custom domain to the Entra app registration's redirect URIs and to Easy Auth allowed external redirect URLs
- [ ] **Lock the Web App to the gateway**: App Service → Access Restrictions → allow only the gateway's subnet (service endpoint) or its public IP; deny all else. *(Without this, the WAF is decorative — users could bypass it via `app-nrrw-prd.azurewebsites.net`.)*
- [ ] End-to-end test: custom domain → gateway → Easy Auth login → app; direct `azurewebsites.net` access returns 403
- [ ] NPRD: per IT's answer, either mirror a minimal gateway or skip and access the NPRD app directly (access-restricted to campus IPs if desired)

---

## Phase 6 — Migrations & Data Operations

- [ ] Migration zero committed to repo; migrations run **before** app deploy in the workflow (separate job, OIDC login, connection via Key Vault-sourced string) — or manually via `psql` for the first cut `[decision point: automate now or later]`
- [ ] Rehearse locally first: Docker Postgres (existing setup guide) → NPRD → PRD, in that order, always
- [ ] Document the restore runbook: server-level PITR restores to a **new server**; note the steps to extract/reconnect. Ten minutes of writing now, an hour saved under stress later.

---

## Phase 7 — Observability & Guardrails

- [ ] Enable Application Insights on the Web App (basic tier ≈ free at RRW volumes; not on the quote but negligible — flag to IT only if they audit line items)
- [ ] Diagnostic settings: App Gateway WAF logs + Postgres logs → Log Analytics (mind retention costs; 30 days is plenty)
- [ ] Alerts (email to you): Web App down (health probe), Postgres storage > 80 %, WAF blocked-request spike
- [ ] **Budget alert** on each resource group at the quoted monthly figure — catches provisioning drift and surprises
- [ ] Key Vault secret expiry alerts (the client secret in Phase 3 *will* expire; make future-you find out a month early, not at 9 am on a review deadline)

---

## Phase 8 — Verification Checklist (definition of done)

- [ ] `git push` to main → tests run → staging deploys with zero manual steps
- [ ] PRD deploy requires explicit approval and succeeds via OIDC (no publish profiles or PATs anywhere)
- [ ] App reachable **only** via the gateway domain; direct App Service hostname blocked
- [ ] Login enforced on every path except `/healthz`; disallowed tenants rejected
- [ ] App connects to Postgres as `rrw_app` (least privilege), connection string sourced from Key Vault, no secrets in repo or App Service settings in plaintext
- [ ] PITR verified conceptually (runbook written); backup retention confirmed
- [ ] Alerts fire to your inbox (test one)
- [ ] NPRD mirrors PRD topology closely enough that a rehearsed change behaves identically

---

## Open decisions to settle before/while executing

1. **PRD deploy trigger:** environment-approval on main, or tag-based releases?
2. **WAF mode:** how long in Detection before Prevention?
3. **Postgres network posture:** "Allow Azure services" vs. enumerated App Service outbound IPs (tighter, but IPs change on scale events — revisit only if IT flags it)
4. **Migrations in CI** from day one, or manual for the first releases?
5. **NPRD gateway:** required by policy or skippable?
6. **App Configuration store:** adopt now or leave dormant until config sprawl justifies it?
