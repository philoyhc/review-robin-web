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

Sibling folders:

- **`spec/`** — surface specifications and design intent (what
  the UI should look like).
- **`guide/`** — forward-looking plans, todos, segment-by-segment
  workplans.
