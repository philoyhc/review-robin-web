# docs/

**Reference material about the running system.**

Answers the question: *how does X work today?* Subsystem
deep-dives plus a periodic implementation-status snapshot.
Authoritative for "what does the code currently do" — read
`status.md` first when picking up after a gap.

| File | Covers |
|---|---|
| `status.md` | Current implementation state + segment history. Updated at the end of each segment. |
| `quickstart.md` | **Operator manual** — a simple end-to-end walkthrough for a colleague running their first review (create → CSV-import rosters → set up → activate → share the app link → monitor → release results). Assumes the app is hosted/running on Azure; reflects that email + magic-link invitations aren't enabled yet (participants reach the app via a link you broadcast, then sign in). Carries marked slots for screen captures. |
| `architecture.md` | Cloud / deployment topology (App Service + Postgres + Key Vault + Monitor + Storage behind Easy Auth), a rendered diagram, and the provisioned-resource cost table. The infra companion to `spec/architecture.md` (which covers the app's domain layering). |
| `database.md` | SQLAlchemy + Alembic conventions, dialect parity, where Postgres lives. |
| `local_setup.md` | Developer how-to for running tests, migrations, and the dev server locally — including a **Running in a GitHub Codespace** section (absorbed from the retired `codespace_setup.md`: SQLite + fake auth, port forwarding, optional Postgres parity + devcontainer). |
| `deployment_dev.md` | Dev Azure App Service deployment notes (resource names, env vars, GRANT bootstrap, planned production flow). |
| `deployment_nus.md` | **Migration runbook** — moving the deploy target from personal Azure to the institutional (NUS) host while keeping localhost + CI unchanged, then retiring personal Azure. Comprehensive GitHub-side (OIDC federated identity, secrets, workflow target) + Azure-side (provisioning, NUS Entra Easy Auth, DB bootstrap, the migrate-job network gotcha) checklists, cutover order, and verification. |
| `operations_runbook.md` | Day-to-day procedures for operating the deployed service (deploy, restart, logs, secrets). |
| `troubleshooting.md` | Symptom-driven diagnosis for the deployed dev slot. |
| `backup_restore.md` | Database backup / restore mechanism and data-retention notes. |
| `known_limitations.md` | Current scope limits and deferred items, stated plainly for a pilot. |
| `security_posture.md` | Authorization model (three-tier operator/admin/super-admin), permission / destructive-action audit, the identity subsystem (Easy Auth headers, `AuthenticatedUser`, `ALLOW_FAKE_AUTH`, diagnostic routes — absorbed from the retired `authentication.md`), CSRF posture (full write-up), deferred hardening. |
| `azure_provision.md` | Pricing-calculator shopping list — the concrete Azure resources (SKU + price knobs) to estimate for a single sandboxed pilot, sized to carry a ~1,500-reviewer review. Companion to `../azure_ask.md`. |
| `azure_github_setup.md` | 8-phase Azure + GitHub setup runbook for the **forward-looking PRD / NPRD scale-up** (a `v0.1 draft`) — *not* the current plan, which is the single-pilot `deployment_nus.md` / `azure_provision.md`. Handoff from IT quote to an App Service + Postgres + Key Vault + App Gateway topology behind Easy Auth; carries a banner scoping it against the pilot. |
| `cli_setup.md` | Companion to `azure_github_setup.md` — CLIs needed on your workstation, shell-choice notes for Windows, one-time auth setup, plus WSL2 setup on Windows 11 and connectivity tests to run before Phase 1. (Absorbed the former `cli_setup_notes.md` scratch fixes: the WSL "not a real error" note, clone-before-identity-check, `az login` before B.5, and the `PG_SERVER`/`MY_IP` definitions in B.9.4.) |

Sibling folders:

- **`spec/`** — surface specifications and design intent (what
  the UI should look like).
- **`guide/`** — forward-looking plans, todos, segment-by-segment
  workplans.
