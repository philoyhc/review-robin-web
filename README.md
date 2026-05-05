# Review Robin Web

Web-based, structured review-cycle tool. Operators configure
reviewer / reviewee rosters and assignments, design per-instrument
response forms, send out invitations, and monitor reviewer
progress through a deadline. Reviewers fill out the per-instrument
forms via per-reviewer invitation links.

Built as a FastAPI + Jinja + SQLAlchemy monolith, deployed to
Azure App Service (Linux, Python 3.12) against an Azure Postgres
Flexible Server. Local dev runs against SQLite.

## What's in the app today

**Operator surface** — Setup, Operations, Settings tabs in the
chrome:

- **Session lifecycle.** `draft → validated → ready` (Activated)
  with edit-locks, deadline tracking, response-window gates, and
  audit events on every state transition.
- **Roster management.** Reviewer / reviewee CSV imports with
  cross-table identity validation; full-matrix and manual
  assignment generation.
- **Instruments builder.** Per-instrument card with state-machine
  Display + Response Fields tables, Response Type Definitions
  catalog (10 seeded RTDs + operator-defined ones), live-preview
  pane, multi-instrument support.
- **Email template editor.** Per-template (Invitation / Reminder)
  override of subject + body + CC + BCC, with five canonical
  merge tags (`$reviewer_name`, `$session_name`, `$deadline`,
  `$help_contact`, `$invite_url`). Per-field "Reset to default";
  the renderer falls through to in-code defaults when nothing's
  overridden.
- **Operator Settings page.** Per-operator SMTP credentials
  encrypted at rest. Honours `?return_to=<path>` so the chrome
  user-menu Settings link returns the operator to wherever they
  came from.
- **Operations pages.** Validate (errors / warnings / info pill
  rows), Reviewer Experience Preview, Manage Invitations,
  Monitoring, Outbox.

**Reviewer surface** — `/reviewer/sessions/{id}/{page}`:

- Multi-instrument session as paginated pages within one form;
  each page is one instrument's table of (reviewee × response
  field) cells.
- Per-page status pills (`not_started` / `in_progress` /
  `complete` / `submitted`) plus per-row submitted timestamps.
- Save persists the current page's dirty inputs; Submit commits
  the whole review session-wide.
- Numeric inputs validate range natively and step-grid via JS
  `setCustomValidity`; server-side `validate_value` is the
  authoritative backstop.
- Missing-required and invalid-value warnings render as their
  own full-width cards below the bottom-grid; Submit is a hard
  gate on missing required.

**Lifecycle + audit.** Every mutating service writes an
`audit_events` row with a typed `event_type` + `detail` JSON.
Setup mutations invalidate `validated → draft` automatically via
`lifecycle.invalidate_if_validated`.

**Email send is queued, not sent.** Outbox rows stamp
`status="queued"`. The transport interface (`EmailTransport`
Protocol + `SmtpEmailTransport` + typed-stub `GraphEmailTransport`)
is shipped and waiting to be wired into Manage Invitations
(Segment 11C PR F).

For the latest snapshot of what's shipped vs. pending, see
[`docs/status.md`](docs/status.md).

## Local development

```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows PowerShell/CMD
pip install -e .[dev]
alembic upgrade head
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/health` and expect:

```json
{"status":"ok"}
```

To sign in locally, set `ALLOW_FAKE_AUTH=true` plus
`FAKE_AUTH_EMAIL` / `FAKE_AUTH_NAME` in your `.env` (see
`.env.example`). In Azure, Easy Auth supplies the identity
headers instead — see [`docs/authentication.md`](docs/authentication.md).

To configure SMTP credentials from the operator Settings page,
also set `SMTP_ENCRYPTION_KEY` (a Base64-urlsafe-encoded
32-byte Fernet key — generate via
`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).
The key only matters when an operator actually saves SMTP
credentials; tests / dev that don't touch the Settings page can
skip it.

## Tests + lint

```bash
pytest                  # full suite (SQLite, ~12s)
ruff check .            # lint (config in pyproject.toml)
alembic upgrade head    # local SQLite migration
alembic downgrade -1    # round-trip check
```

CI runs the same `pytest` against a `postgres:16` service
container too (`ci-postgres` job) — the suite covers both
dialects on every PR.

## Project documents

Documentation is split across three folders, each with its own
README:

- **[`spec/`](spec/)** — surface specifications and design intent
  ([`spec/README.md`](spec/README.md)). Includes `architecture.md`,
  `functional_spec.md`, `assumptions.md`, `operator_ui_concept.md`,
  `session_home.md`, `reviewer-surface.md`, `email_infra_options.md`.
- **[`docs/`](docs/)** — reference material about the running
  system ([`docs/README.md`](docs/README.md)). Includes
  `status.md`, `authentication.md`, `database.md`, `imports.md`,
  `local_setup.md`, `deployment_dev.md`.
- **[`guide/`](guide/)** — forward-looking plans, segment
  workplans, todos ([`guide/README.md`](guide/README.md)).
  Shipped segment plans are in
  [`guide/archive/`](guide/archive/);
  [`guide/todo_master.md`](guide/todo_master.md) is the roadmap.

Top-level docs at the repo root: `CLAUDE.md` / `AGENTS.md` (kept
as byte-identical twins; AI-agent guidance),
`CONTRIBUTING.md`, `README.md` (this file).
