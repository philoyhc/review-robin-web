# Azure provisioning list — Review Robin Web

**Purpose:** the concrete list of Azure resources to price in the
[Azure pricing calculator](https://azure.microsoft.com/en-us/pricing/calculator/)
so IT can quote hosting **Review Robin Web (RRW)** as a sanctioned
(sandboxed) institutional app.

This is the *shopping list*. Two siblings cover the other angles:

- **[`../azure_ask.md`](../azure_ask.md)** — the wish list + governance
  ask (sponsorship, data policy, cost cap) and the *why*.
- **[`azure_github_setup.md`](azure_github_setup.md)** — the step-by-step
  build runbook once the estimate is approved.

Read this one when you're sitting in the pricing calculator adding line
items.

---

## How to use this doc with the calculator

Each row in [§A](#a-billable-resources--the-estimate-line-items) is **one
line item** you add in the calculator. The columns give you:

- **Search term** — what to type in the calculator's "add product" box.
- **Tier / SKU** — the exact option to select.
- **Price knobs** — the fields that actually drive the number (vCores,
  storage GB, hours, capacity units). Everything else on the calculator
  card can stay at its default.

Fixed inputs for **every** row:

- **Region:** Southeast Asia (matches the current dev slot; lowest latency
  to the institution).
- **Currency / billing:** pick the institution's. Leave savings-plan and
  reserved-instance toggles **off** for the first pass — pay-as-you-go is
  the conservative number; revisit reservations only for the always-on
  compute (App Service, Postgres) once the tier is settled.
- **Hours:** compute resources run 24×7 → **730 hours/month**.

---

## Scope: build the estimate at one of two sizes

| Scope | What it is | Rows to include |
|---|---|---|
| **Sandbox / pilot (NPRD only)** | One environment, no WAF gateway. The literal "sandboxed app" ask. | Rows marked **Pilot** in §A |
| **Full sanctioned (PRD + NPRD)** | Two environments + the WAF gateway retained per IT policy (the corrected IT quote). | All rows in §A |

The `Scope` column in §A tells you which rows belong to each. Produce the
**Sandbox** estimate first — it's the decision-maker for whether to
proceed — then the **Full** estimate as the graduation target.

---

## A. Billable resources — the estimate line items

| # | Resource | Search term | Tier / SKU | Price knobs | Scope | Per-env qty |
|---|---|---|---|---|---|---|
| 1 | App Service Plan (compute) | **App Service** | Linux · PRD **P0V3** (Premium v3, 1 vCPU / 4 GiB) · NPRD **B2** (Basic, 2 vCPU / 3.5 GiB) | Instances ×1, 730 h/mo | Pilot (B2) + Full (adds P0V3) | 1 |
| 2 | PostgreSQL database | **Azure Database for PostgreSQL** → Flexible Server | **Burstable** · PRD **B2s** (2 vCore) · NPRD **B1ms** (1 vCore / 2 GiB) | Compute 730 h/mo · **Storage 32 GiB** · Backup 7-day (see note) · HA **off** | Pilot (B1ms) + Full (adds B2s) | 1 |
| 3 | Application Gateway (WAF) | **Application Gateway** | **WAF v2** | Gateway 730 h/mo · **Capacity Units ≈ 2** (pilot floor) | **Full only** — skip for sandbox | 1 (PRD) |
| 4 | Public IP (for the gateway) | **IP Addresses** | **Standard**, static | 1 address | **Full only** (pairs with row 3) | 1 (PRD) |
| 5 | Key Vault | **Key Vault** | **Standard** | Operations (few/mo — pennies) | Pilot + Full | 1 |
| 6 | Log Analytics / App Insights | **Azure Monitor** → Log Analytics | Pay-as-you-go | GB ingested/mo (small; first 5 GB free) | Pilot (optional) + Full | 1 |
| 7 | Storage Account *(optional)* | **Storage Accounts** | Standard · **LRS** · Hot | A few GB — pennies | Optional (see note) | 1 |
| 8 | App Configuration *(optional)* | **Azure App Configuration** | Free tier / Standard | Leave on Free → $0 | Optional | 1 |
| 9 | Communication Services — Email *(future)* | **Azure Communication Services** | Email | Per-email + per-GB (≈$0 at pilot) | Future (see note) | 1 |
| 10 | Azure Functions *(deferred)* | **Functions** | Consumption | Free grant covers pilot → $0 | Deferred (see note) | 1 |

### Per-row notes

1. **App Service Plan.** The compute tier is the app's home; there's no
   separate "Web App" charge — the Web App is free and rides on the plan.
   Runtime is **Linux, Python 3.12**. PRD uses **P0V3** (Premium v3, the
   corrected quote's tier — needed for VNet integration behind the
   gateway); NPRD uses **B2** (Basic is fine without a gateway). If IT
   wants PRD headroom, **P1V3** (2 vCPU / 8 GiB) is the next step up —
   price both and let them choose.
2. **PostgreSQL Flexible Server.** **Burstable** class, **Postgres 16**,
   **32 GiB** storage. Backup storage up to 100% of provisioned storage
   is included free; 7-day retention at pilot churn stays inside that
   grant, so backup adds ~$0. **HA off** at pilot — zone-redundant HA
   roughly doubles the compute line and is a scale-up decision. Sandbox
   can share PRD's B1ms sizing.
3. **Application Gateway (WAF v2).** **This is the single largest line in
   the estimate** — WAF v2 bills a fixed gateway hourly rate *plus*
   capacity units even when idle (order of a few hundred USD/month before
   traffic). It's retained *per IT policy* in the corrected quote, not
   because the app needs it (RRW's state-changing routes are all POST
   behind Easy Auth). **Skip it entirely for the sandbox estimate.** For
   the full estimate, start capacity units at ~2 (pilot traffic floor).
4. **Public IP.** Standard static IP the gateway fronts. Only exists if
   row 3 does. ~$3–4/month.
5. **Key Vault.** Holds the Postgres connection string (and later the
   Entra client secret + SMTP creds). Standard tier, priced per 10k
   operations — RRW reads a handful of secrets at boot, so this is
   effectively free but belongs on the estimate for completeness.
6. **Log Analytics / Application Insights.** The observability floor.
   Pay-per-GB ingested; RRW's structured JSON logs are light, and the
   monthly free-ingest grant likely covers pilot volume. Optional at
   sandbox scope; include it for the full estimate. WAF + Postgres
   diagnostic logs (full scope) add a little more ingest.
7. **Storage Account — optional.** RRW's application code needs **no**
   blob storage (verified: no `azure-storage` / blob dependency; CSV
   imports are parsed in-request, not persisted to blob). Include this
   line *only* if IT wants deployment artifacts to land in institutional
   storage rather than GitHub. Pennies either way.
8. **App Configuration — optional.** Key Vault + App Settings cover the
   pilot's config needs. Leave on the Free tier (→ $0) or omit; adopt
   later only if config sprawl justifies it.
9. **Communication Services (Email) — future.** RRW's email dispatch is
   queued but **not yet wired to a transport** (Segment 14B). Add this
   line only when the email path activates. At pilot volume the cost is
   ~$0. Alternative: Microsoft Graph send through the same tenant (no
   ACS line) — an open question for IT (see `azure_ask.md` §4).
10. **Azure Functions — deferred.** No function exists yet; the
    Consumption free grant covers a pilot regardless. Carry it as a $0
    placeholder or omit.

---

## B. Free / near-zero — include for completeness, they won't move the total

The calculator lets you add these, but they price at or near $0 at pilot
scale. Don't let them stall the estimate:

- **Virtual Network + subnets** — free (the VNet itself is free; only the
  gateway's public IP in it costs — row 4). Required only when the WAF
  gateway is in play (full scope).
- **System-assigned managed identity** — free. This is how the Web App
  reads Key Vault without a stored secret.
- **Federated credential (GitHub OIDC)** on the deployment identity —
  free. Replaces publish-profile secrets in CI.
- **Entra app registration** for Easy Auth — free.
- **Outbound bandwidth** — first 100 GB/month egress is free; RRW serves
  light server-rendered HTML, so egress stays negligible.
- **`/health` probe traffic** — trivial.

---

## C. Leave OUT of the estimate — deliberately not part of RRW's shape

Call these out so nobody pads the quote with services the app doesn't
use:

- **Azure SQL Database** — RRW is **Postgres-only**. The corrected quote
  already swapped Azure SQL → PostgreSQL Flexible Server; don't let an
  Azure SQL line creep back in.
- **Azure Cache for Redis** — no server-side cache tier; the app holds no
  session/cache state outside Postgres.
- **Azure Front Door / CDN** — server-rendered HTML, no static-asset CDN.
  (Front Door is an *alternative* to the App Gateway, not an addition —
  if IT ever prefers it, price one or the other, never both.)
- **Static Web Apps / separate frontend hosting** — there is no separate
  frontend build; the app is a FastAPI + Jinja monolith.
- **Container Registry (ACR)** — deploy is a **code push** via
  `azure/webapps-deploy` (Oryx build on the platform), not a container
  image, so no registry is needed.
- **Cognitive / AI services, Service Bus, Event Hubs** — not in RRW's
  architecture.

---

## D. Where the money actually is

At pilot scale the estimate is dominated by two rows, and everything else
is rounding error:

1. **Application Gateway WAF v2 (row 3)** — the largest single line *by a
   wide margin*, and it's a policy requirement rather than an app
   requirement. Producing the sandbox estimate **without** it is the
   fastest way to show the true minimum cost of running RRW.
2. **App Service Plan compute (row 1)** — P0V3 (PRD) is the second driver;
   B2 (NPRD) is modest.

PostgreSQL Burstable, Key Vault, Storage, App Configuration, Log
Analytics, and bandwidth together are small relative to those two.

---

## E. Suggested output: two saved estimates

Produce and save both in the calculator, then export/share the links:

1. **RRW — Sandbox (NPRD).** Rows 1 (B2), 2 (B1ms), 5, and optionally 6.
   No gateway, no public IP. This is the "can we just run it?" number and
   maps directly to `azure_ask.md` §1 (the pilot ask).
2. **RRW — Full sanctioned (PRD + NPRD).** All of §A: PRD (P0V3 + B2s +
   WAF v2 + public IP + Key Vault + Log Analytics) and NPRD (B2 + B1ms +
   Key Vault). This maps to `azure_github_setup.md`'s corrected-quote
   topology and to `azure_ask.md` §2 (scale-up).

Attach both to the IT conversation so the gateway's cost is visible as an
explicit policy choice rather than baked silently into a single figure.
