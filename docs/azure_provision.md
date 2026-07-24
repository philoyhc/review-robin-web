# Azure provisioning list — Review Robin Web

**Purpose:** the concrete list of Azure resources to price in the
[Azure pricing calculator](https://azure.microsoft.com/en-us/pricing/calculator/)
so IT can quote hosting **Review Robin Web (RRW)** as a sanctioned
**sandboxed pilot** on institutional Azure.

**One environment, sized to cope.** This is a single sandboxed pilot —
not a PRD/NPRD split. But it is provisioned so that a real review with up
to **~1,500 reviewers** could run on it without re-provisioning: the tiers
below carry that load, and the two elastic pressure valves
([§B](#b-headroom-for-1500-reviewers--the-pressure-valves)) absorb a
deadline-day crush.

This is the *shopping list*. Two siblings cover the other angles — but
**both describe the broader two-environment (PRD + NPRD) topology**, not
this single sandbox. Read their SKUs and PRD/NPRD split as the *scale-up
graduation target*, and this doc's single-environment sizing as the pilot
you actually provision first:

- **[`../azure_ask.md`](../azure_ask.md)** — the wish list + governance
  ask (sponsorship, data policy, cost cap) and the *why*; its §1 is the
  pilot ask, §2 the scale-up.
- **[`azure_github_setup.md`](azure_github_setup.md)** — the step-by-step
  build runbook for the sanctioned PRD/NPRD deployment, once the estimate
  is approved.

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

## What "1,500 reviewers" actually demands

Size to the *shape* of the load, not the headline number:

- **1,500 is the roster, not the concurrency.** A review runs over a
  window of days or weeks. Reviewers sign in, read, think, and submit a
  structured form — they are not all online at once.
- **Peak is a fraction of the roster.** Even a deadline day rarely puts
  more than low-hundreds of reviewers active in the same hour, and only
  low-tens of *simultaneous* in-flight requests at any instant.
- **The requests are cheap.** RRW is a server-rendered FastAPI + Jinja
  app: plain `<form>` GET/POST, no media, no heavy compute, no
  client-side build. A request is a couple of indexed Postgres queries
  and an HTML render.
- **Data volume tracks the *assignment fan-out*, not the reviewer count.**
  Each instrument's assignments are the (reviewer × reviewee) pairs its
  Band 1 link rules select. For a **sparse** pattern — each reviewer
  covering a bounded set of reviewees (a handful each) — 1,500 reviewers
  land in the low hundreds of thousands of rows across assignments,
  response fields, and audit: megabytes, comfortably inside the tiers
  below. But RRW's **default is Full Matrix** (untouched Band 1 → *every*
  reviewer/reviewee pair; `app/services/assignments/_generate.py`), so a
  symmetric roster left on the default — say 1,500 reviewers all reviewing
  1,500 reviewees — is ~2.25 M assignments for a *single* instrument,
  before response-field and audit fan-out. That is a different order of
  magnitude. **The 1,500-reviewer sizing here assumes a bounded
  per-reviewer assignment count; a dense Full-Matrix at that roster size
  should be load-tested first and likely wants General Purpose Postgres
  (row 2's escalation path), not Burstable.**
- **The app is stateless.** There is no in-process session store; all
  state lives in Postgres (verified — no `SessionMiddleware`, no in-memory
  cache tier). That means the App Service can **scale out horizontally**
  safely, which is the pressure valve for a deadline-day surge.

Net: the sizing drivers are (a) enough App Service CPU + worker headroom
for the peak *request rate*, with elastic scale-out on standby, and
(b) enough Postgres burst CPU + connection budget for concurrent submits.
Both are comfortably met by the tiers in §A.

---

## A. Billable resources — the estimate line items

| # | Resource | Search term | Tier / SKU | Price knobs | Status |
|---|---|---|---|---|---|
| 1 | App Service Plan (compute) | **App Service** | Linux · **P0V3** (Premium v3, 1 vCPU / 4 GiB) | 1 instance × 730 h/mo (price the surge at +1 → 2 instances; see §B) | Core |
| 2 | PostgreSQL database | **Azure Database for PostgreSQL** → Flexible Server | **Burstable B2s** (2 vCore / 4 GiB) | Compute 730 h/mo · **Storage 32 GiB** · Backup 7-day (see note) · HA **off** | Core |
| 3 | Key Vault | **Key Vault** | **Standard** | Operations (few/mo — pennies) | Core |
| 4 | Log Analytics / App Insights | **Azure Monitor** → Log Analytics | Pay-as-you-go | GB ingested/mo (small; first 5 GB free) | Core |
| 5 | Application Gateway (WAF) | **Application Gateway** | **WAF v2** | Gateway 730 h/mo · Capacity Units ≈ 2 | **Only if IT policy requires** — see note |
| 6 | Public IP (for the gateway) | **IP Addresses** | **Standard**, static | 1 address | Only if row 5 is included |
| 7 | Storage Account *(optional)* | **Storage Accounts** | Standard · **LRS** · Hot | A few GB — pennies | Optional (see note) |
| 8 | Communication Services — Email *(future)* | **Azure Communication Services** | Email | Per-email + per-GB (≈$0 at pilot) | Future (see note) |

### Per-row notes

1. **App Service Plan.** The app's home; there's no separate "Web App"
   charge — the Web App is free and rides on the plan. Runtime is
   **Linux, Python 3.12**. **P0V3** (Premium v3) is the pick: it carries
   the steady load *and* unlocks the two things a 1,500-reviewer surge
   needs — **autoscale** (automatic scale-out on a load rule) and
   **deployment slots**. (Basic B-tier is cheaper and *can* be scaled out
   manually to at most 3 instances, but it **can't autoscale or
   slot-swap** — only Premium reacts to a deadline-day CPU/request spike
   automatically.) If steady load ever
   sits high, **P1V3** (2 vCPU / 8 GiB) is the in-place step up — no
   migration, just a plan resize.
2. **PostgreSQL Flexible Server.** **Burstable B2s**, **Postgres 16**,
   **32 GiB** storage (the tier minimum — already far more than the data
   needs). Burstable is the *right* class for this workload: RRW's load
   is bursty form submits, which is exactly what CPU-credit accrual is
   built for. **HA off** at pilot. Backup storage up to 100% of
   provisioned storage is included free, so 7-day retention adds ~$0.
   *Connection-budget note:* the app uses SQLAlchemy's default pool
   (~15 connections per worker process), so keep the gunicorn worker
   count modest and remember that scaling the App Service out multiplies
   pooled connections against the Burstable connection ceiling. If a
   surge ever pushes past that ceiling, the answer is **General Purpose
   D2ds_v5** (more RAM → higher connection cap) — a scale event, not the
   pilot provision.
3. **Key Vault.** Holds the Postgres connection string (and later the
   Entra client secret + SMTP creds). Standard tier, priced per 10k
   operations — RRW reads a handful of secrets at boot, so this is
   effectively free but belongs on the estimate for completeness.
4. **Log Analytics / Application Insights.** The observability floor.
   Pay-per-GB ingested; RRW's structured JSON logs are light, and the
   monthly free-ingest grant likely covers pilot volume — a few $/mo at
   most.
5. **Application Gateway (WAF v2) — conditional.** **This is the single
   largest line if included** — WAF v2 bills a fixed gateway hourly rate
   *plus* capacity units even when idle (order of a few hundred USD/month
   before traffic). RRW does **not** need it functionally: its
   state-changing routes are all POST behind Easy Auth, reachable only by
   authenticated tenant users. Include this row **only if institutional
   policy mandates a WAF in front of web apps**. The default sandbox
   posture is *no gateway* — App Service default hostname behind Easy
   Auth, with App Service **access restrictions** limiting inbound to
   campus IP ranges. Price the estimate both ways if the policy is
   unclear, so the gateway's cost is a visible, explicit choice.
6. **Public IP.** Standard static IP the gateway fronts. Only exists if
   row 5 does. ~$3–4/month.
7. **Storage Account — optional.** RRW's application code needs **no**
   blob storage (verified: no `azure-storage` / blob dependency; CSV
   imports are parsed in-request, not persisted to blob). Include this
   line *only* if IT wants deployment artifacts to land in institutional
   storage rather than GitHub. Pennies either way.
8. **Communication Services (Email) — future.** RRW's email dispatch is
   queued but **not yet wired to a transport** (Segment 14B). Add this
   line only when the email path activates. At pilot volume the cost is
   ~$0. Alternative: Microsoft Graph send through the same tenant (no
   ACS line) — an open question for IT (see `azure_ask.md` §4).

---

## B. Headroom for 1,500 reviewers — the pressure valves

Neither of these adds a *fixed* line to the estimate; they're the
in-place levers that let the single environment ride out a surge. Provision
the tiers that *enable* them (P0V3 in row 1) and they're available on
demand:

- **App Service autoscale-out.** Premium v3 adds instances on a CPU or
  request-count rule during a deadline day, then scales back. **Plan and
  price the surge at +1 instance (2 total)** — two P0V3 instances
  comfortably cover the peak request rate this workload produces; the
  platform ceiling is higher (up to 3+) if a spike ever demands it. You
  only pay for the extra instance-hours while they run, so the
  calculator's steady 1-instance figure is the baseline and the surge adds
  a bounded, temporary increment. Because the app is stateless this is
  safe — any instance can serve any request.
- **Postgres compute resize.** Burstable → same-tier bump, or
  Burstable → General Purpose, is a near-online resize if the DB ever
  becomes the bottleneck. Nothing to pre-pay; it's the escalation path,
  not the provision.

For a hard worst-case estimate, add **one extra P0V3 instance-month** (the
+1 surge instance running the whole month) as a "sustained surge"
contingency line and label it as such — matching the +1 autoscale rule
above, so baseline + contingency = the 2-instance ceiling you priced.

---

## C. Free / near-zero — include for completeness, they won't move the total

- **Virtual Network + subnets** — free (only needed if the WAF gateway in
  row 5 is included; the VNet itself is free, only its public IP costs).
- **System-assigned managed identity** — free. This is how the Web App
  reads Key Vault without a stored secret.
- **Federated credential (GitHub OIDC)** on the deployment identity —
  free. Replaces publish-profile secrets in CI.
- **Entra app registration** for Easy Auth — free.
- **Outbound bandwidth** — first 100 GB/month egress is free; RRW serves
  light server-rendered HTML, so egress stays negligible even at
  1,500 reviewers.

---

## D. Leave OUT of the estimate — deliberately not part of RRW's shape

Call these out so nobody pads the quote with services the app doesn't
use:

- **Azure SQL Database** — RRW is **Postgres-only**. Don't let an Azure
  SQL line creep in.
- **Azure Cache for Redis** — no server-side cache tier; the app holds no
  session/cache state outside Postgres.
- **Azure Front Door / CDN** — server-rendered HTML, no static-asset CDN.
  (Front Door is an *alternative* to the App Gateway, not an addition — if
  IT ever prefers it, price one or the other, never both.)
- **Static Web Apps / separate frontend hosting** — no separate frontend
  build; the app is a FastAPI + Jinja monolith.
- **Container Registry (ACR)** — deploy is a **code push** via
  `azure/webapps-deploy` (Oryx build on the platform), not a container
  image, so no registry is needed.
- **Cognitive / AI services, Service Bus, Event Hubs** — not in RRW's
  architecture.

---

## E. Where the money is, and what to output

At this sizing the estimate is dominated by:

1. **Application Gateway WAF v2 (row 5)** — *if* policy requires it, it's
   the largest line by a wide margin, and it's a policy requirement rather
   than an app requirement. The fastest way to show RRW's true minimum is
   to price the estimate **without** it first.
2. **App Service P0V3 (row 1)** — the core always-on compute; the second
   driver, and modest.

PostgreSQL Burstable B2s, Key Vault, Log Analytics, Storage, and
bandwidth together are small relative to those two.

**Output:** one saved calculator estimate covering §A rows 1–4 (core) at
steady state, plus a labelled **"+WAF"** variant (rows 5–6) and a labelled
**"+surge"** contingency line (one extra P0V3 instance-month, §B). Attach
it to the IT conversation so the gateway's cost and the surge contingency
are both visible as explicit choices rather than baked silently into a
single figure.
