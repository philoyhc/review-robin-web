# docs/

**Reference material about the running system.**

Answers the question: *how does X work today?* Subsystem
deep-dives plus a periodic implementation-status snapshot.
Authoritative for "what does the code currently do" — read
`status.md` first when picking up after a gap.

| File | Covers |
|---|---|
| `status.md` | Current implementation state + segment history. Updated at the end of each segment. |
| `authentication.md` | Easy Auth headers, `AuthenticatedUser`, `ALLOW_FAKE_AUTH`, identity resolution. |
| `database.md` | SQLAlchemy + Alembic conventions, dialect parity, where Postgres lives. |
| `imports.md` | CSV import format for reviewers / reviewees / assignments (operator-facing how-to). |
| `local_setup.md` | Developer how-to for running tests, migrations, and the dev server locally. |
| `deployment_dev.md` | Dev Azure App Service deployment notes (resource names, env vars, GRANT bootstrap, planned production flow). |
| `operations_runbook.md` | Day-to-day procedures for operating the deployed service (deploy, restart, logs, secrets). |
| `troubleshooting.md` | Symptom-driven diagnosis for the deployed dev slot. |
| `backup_restore.md` | Database backup / restore mechanism and data-retention notes. |
| `known_limitations.md` | Current scope limits and deferred items, stated plainly for a pilot. |
| `security_posture.md` | Authorization model, permission / destructive-action audit, identity trust model, CSRF posture, deferred hardening. |

Sibling folders:

- **`spec/`** — surface specifications and design intent (what
  the UI should look like).
- **`guide/`** — forward-looking plans, todos, segment-by-segment
  workplans.
