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
| `rehydrate.md` | **Shipped (Segment 18P Group 2).** Rebuilds a live draft session from a complete set of extract CSV files — same settings, populations, and repopulated responses — via the **Rehydrate** button in the lobby search-card row and the dedicated `/operator/sessions/rehydrate` page (Validate → Rehydrate). |
| `authentication.md` | Easy Auth headers, `AuthenticatedUser`, `ALLOW_FAKE_AUTH`, identity resolution. |
| `database.md` | SQLAlchemy + Alembic conventions, dialect parity, where Postgres lives. |
| `imports.md` | CSV import format for reviewers / reviewees / assignments (operator-facing how-to). |
| `local_setup.md` | Developer how-to for running tests, migrations, and the dev server locally. |
| `codespace_setup.md` | Running the suite and the dev server from a GitHub Codespace (SQLite + fake auth, no external services); the Easy-Auth caveat; optional Postgres-parity and devcontainer. Companion to `local_setup.md`. |
| `deployment_dev.md` | Dev Azure App Service deployment notes (resource names, env vars, GRANT bootstrap, planned production flow). |
| `operations_runbook.md` | Day-to-day procedures for operating the deployed service (deploy, restart, logs, secrets). |
| `troubleshooting.md` | Symptom-driven diagnosis for the deployed dev slot. |
| `backup_restore.md` | Database backup / restore mechanism and data-retention notes. |
| `known_limitations.md` | Current scope limits and deferred items, stated plainly for a pilot. |
| `security_posture.md` | Authorization model, permission / destructive-action audit, identity trust model, CSRF posture, deferred hardening. |
| `azure_provision.md` | Pricing-calculator shopping list — the concrete Azure resources (SKU + price knobs) to estimate for a single sandboxed pilot, sized to carry a ~1,500-reviewer review. Companion to `../azure_ask.md`. |
| `azure_github_setup.md` | 8-phase Azure + GitHub setup runbook for the sanctioned PRD / NPRD deployment. Handoff from IT quote to a working App Service + Postgres + Key Vault + App Gateway topology behind Easy Auth. |
| `cli_setup.md` | Companion to `azure_github_setup.md` — CLIs needed on your workstation, shell-choice notes for Windows, one-time auth setup, plus WSL2 setup on Windows 11 and connectivity tests to run before Phase 1. |

Sibling folders:

- **`spec/`** — surface specifications and design intent (what
  the UI should look like).
- **`guide/`** — forward-looking plans, todos, segment-by-segment
  workplans.
