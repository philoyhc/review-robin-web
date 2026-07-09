# Azure ask — Review Robin Web

Institutional-Azure wish list for hosting **Review Robin Web (RRW)**
as a sanctioned pilot, and (separately) what would additionally be
needed if adoption takes off.

Read alongside [`rrw_design_rationale.md`](rrw_design_rationale.md)
for the *why* — the short version is that RRW routes reviewers to
reviewees by rule, collects their structured judgment, and hands
back clean data. It authenticates through Entra ID via Azure App
Service Easy Auth, stays server-rendered (no separate frontend
build), and already runs successfully on a developer-owned
Southeast Asia Azure dev slot with the layout below. The pilot ask
is: *the same shape, but in an institutionally-sanctioned resource
group with an institutional sponsor and a workable data policy.*

---

## 1. Pilot ask — the minimum to move off the developer-owned dev slot

Everything below is already known to work in the current dev slot,
so nothing here is speculative. The pilot ask is to reproduce the
same shape under institutional ownership.

### 1.1 Sponsorship + governance

- **A named institutional owner** for the resource group, so
  billing, incident response, and lifecycle decisions have a
  home.
- **A workable data-classification decision** covering the
  categories the pilot will hold: reviewer + reviewee email
  addresses, tag/role metadata, structured reviewer responses
  (text and numeric), and an append-only audit log. Most of this
  looks like "restricted institutional data" rather than
  "confidential" — but the classification decision is IT's, not
  the developer's.
- **A written data policy** covering retention, deletion on
  request, and export. RRW writes a session `session.purged` /
  `session.archived` event on every purge or archive, and every
  mutating action lands an audit row — so retention rules can be
  operationalised, but IT needs to name them.
- **A cost cap.** The dev slot runs a Free-tier App Service Plan
  + Burstable B1ms Postgres (< USD $30 / month at current pricing
  in Southeast Asia). Pilot ask is a Basic / Standard-tier App
  Service (~USD $50-80/month) + the same Postgres tier — set a
  monthly ceiling of, say, USD $150 for pilot with an alert at
  75%.

### 1.2 Resources

Provision the same shape as the dev slot, in a new
institutionally-owned resource group:

| Resource | Type / tier | Notes |
|---|---|---|
| Resource Group | Standard | Southeast Asia (matches dev slot; lowest-latency to institution) |
| App Service Plan | **B1** or **S1** Linux | Pilot doesn't need P1v3; upgrade if adoption scales |
| App Service (Web App) | Linux, Python 3.12 runtime | Custom domain optional at pilot; App Service default domain is fine |
| App Service Authentication | **Enabled**, Entra ID identity provider | Same tenant as institution — no separate identity system |
| Azure Database for PostgreSQL Flexible Server | Postgres 16, **Burstable B1ms** or **B2s** | 32 GB storage, default 7-day backup retention |
| Key Vault | Standard | For the Postgres connection string + any SMTP credentials the pilot uses |
| Storage Account | Standard LRS | Only if IT wants deployment artifacts to land in institutional storage rather than GitHub |

### 1.3 Identity + auth

- **Register the App Service Authentication with the institution's
  Entra ID tenant.** RRW parses `X-MS-CLIENT-PRINCIPAL` headers
  that Easy Auth injects — no other identity plumbing is needed.
- **Decide the allowlist model.** RRW's own gate (`require_operator`)
  requires an operator's email to be on a workspace allowlist
  managed inside the app; there's no separate Entra group check.
  IT can leave RRW to manage its own allowlist, or add an
  outer Entra security group as an Easy Auth-level pre-filter.

### 1.4 Networking + secrets baseline

Modest ask — the dev slot uses public access with a firewall
allow-list, and that's acceptable for a low-population pilot. The
pilot ask is one small hardening step on secrets:

- **Move the `DATABASE_URL` App Setting to a Key Vault reference**
  rather than a plain App Setting. Assign the App Service a
  managed identity with `Get` on the Key Vault secret.
- **Postgres public access remains enabled**, with the firewall
  allow-list scoped to (a) "Allow Azure services" for the App
  Service, plus (b) the operator's IP for one-off `psql` /
  Alembic runs. Private networking is on the scale-up list, not
  the pilot ask.

### 1.5 Deployment

RRW deploys via GitHub Actions today, using OIDC federated
credentials — no long-lived Azure secrets in GitHub. The pilot ask
is to reproduce that setup:

- **Grant the RRW GitHub repository a federated credential**
  (workload identity) on an Entra app registration with
  `Contributor` on the pilot resource group. Configure GitHub
  environments so the credential only fires on `main` pushes to
  the pilot slot.
- The pipeline is `build → migrate → deploy`. **Migrations run
  against Azure Postgres before the App Service swap.** If
  migration fails, deploy is skipped — the app never ships
  against a stale schema.

### 1.6 Observability floor

- **Enable App Service log streaming and set the log-retention
  window** (30 days is plenty for pilot). RRW's structured JSON
  logs are already ingestion-ready if IT wants to point them at
  Application Insights or Log Analytics later; provisioning
  either is optional at pilot.

---

## 2. If adoption takes off — the scale-up ask

Not part of the pilot ask. Listed here so the pilot resource group
can be sized with future headroom in mind, and so IT can plan the
approval path if RRW graduates beyond pilot.

### 2.1 Environment separation

- **A staging slot (or a separate staging App Service).** Turn
  the deploy flow into
  `main → dev → verify → staging → manual-approve → production`.
- **A production Postgres Flexible Server** distinct from the
  staging one, so migration rollouts can bake on staging first.

### 2.2 Network hardening

- **VNet integration for the App Service** + **private endpoints
  for Postgres**, dropping public database access entirely.
  Remove "Allow Azure services" and remove the operator IP from
  the firewall list.
- **Azure Front Door or Application Gateway with WAF** in front
  of production, primarily for DDoS resistance and standard
  request-shape rules; RRW's own routes are all POST for
  state-changing actions, so app-layer CSRF risk is low but WAF
  earns its keep at scale.

### 2.3 Secret + credential hardening

- **Every App Setting containing a secret becomes a Key Vault
  reference**, not just `DATABASE_URL`. Includes SMTP credentials
  once the email dispatch path is wired.
- **Rotate the OIDC federated credential** on a scheduled cadence
  and gate production deploys on a manual approval in the
  GitHub `production` environment.

### 2.4 Database posture

- **Move Postgres off the Burstable tier** to General Purpose D2s
  or larger, depending on the largest observed cohort. Pilot dev
  has run comfortably at ~1,500 reviewers × ~1,500 reviewees
  through the rule engine on B1ms; larger cohorts want more RAM.
- **Enable HA** (zone-redundant) for production Postgres.
- **Extend backup retention beyond the default 7 days** to
  whatever the institutional data policy names (30 days is a
  common floor for institutional records).
- **Point-in-time restore playbook** — the capability is already
  there; the pilot ask needs a documented restore runbook and
  one rehearsed drill before production traffic lands.

### 2.5 Observability

- **Provision an Application Insights resource** and wire its
  connection string to the App Service. RRW's logs already
  carry `correlation_id` on every request; Application Insights
  gives IT the search + dashboard surface for them.
- **A dashboard covering the four operational signals:** request
  volume, request-error rate, database CPU / connections, and
  audit-log write rate. RRW already emits audit rows on every
  mutation, so a "did anything happen in the last hour?" pane
  is a cheap early-warning surface.
- **Alerting on:** deploy failure, migration failure, App Service
  restart loop, Postgres storage > 80%.

### 2.6 Delegated admin

- **A workspace admin group** distinct from the individual
  operator. Today RRW has one workspace sys-admin (the developer);
  adoption introduces multiple sanctioned operators from
  different administrative units.
- **A named security contact** and a **named cost owner**
  separate from the developer, so incident routing and billing
  escalation don't route through a single person.

### 2.7 Compliance + review cadence

- **Quarterly (or annual) IT security review** — the app already
  writes an append-only audit log, has documented CSRF and
  identity trust models (`docs/security_posture.md`), and its
  `ALLOW_FAKE_AUTH` footgun is off in every deployed environment
  by construction. What IT would add at scale is a periodic
  attestation.
- **Data subject access + deletion request handling** — the
  operator-triggered purge (`session_purge` service) already
  supports selective hard-delete of a session's responses /
  rosters / audit log. What IT would add is the intake path.

---

## 3. What RRW brings to this conversation

Not asks — statements of what already exists on the app side, so
IT sees what it doesn't need to arrange:

- **Identity + auth handled by Easy Auth** — RRW doesn't ship a
  login form or password store. Sign-in is Entra ID.
- **Audit log on every mutating action** — schema-validated
  `audit_events` rows with a typed detail envelope; suitable for
  compliance / incident review out of the box.
- **Deterministic migrations** on both SQLite (tests) and
  Postgres 16 (deployed), round-tripped in CI on every PR — no
  schema surprises at deploy time.
- **Confirmation gates on every destructive operator action** and
  scoped permissions on every operator route — see
  `docs/security_posture.md` §5.6 + §5.7 for the audit tables.
- **Structured JSON logs with correlation IDs** — already
  ingestion-ready for Application Insights or Log Analytics.
- **Documented runbooks** at `docs/operations_runbook.md`,
  `docs/troubleshooting.md`, `docs/backup_restore.md`,
  `docs/known_limitations.md`, and `docs/security_posture.md`.
- **A `/health` endpoint** returning `{"status": "ok"}` for
  platform probes, deliberately excluded from Easy Auth so it
  doesn't bounce through sign-in.

---

## 4. Open questions for IT

- **Data classification** — restricted institutional data, or
  something more sensitive? Drives the network + backup posture.
- **Retention policy** — how long should completed sessions'
  responses + audit rows live? Drives the backup + purge cadence.
- **Custom domain** at pilot, or is the App Service default
  domain (`app-*.azurewebsites.net`) acceptable until scale-up?
- **SMTP path** — RRW's email dispatch is queued but not yet
  wired to a transport (Segment 14B). When it activates, does
  IT prefer SMTP relay through the institutional mail
  infrastructure, or Microsoft Graph via the same tenant?
- **Which resource group naming convention** does IT use for
  sanctioned pilot workloads?
