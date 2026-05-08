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
  audit events on every state transition. The sessions lobby
  (`/operator/sessions`) carries a Danger Zone bulk-delete
  affordance for ticked draft / validated sessions; deletion
  cascades reviewers / reviewees / instruments / assignments /
  invitations / email-outbox rows in one transaction.
- **Roster management.** Reviewer / reviewee CSV imports with
  cross-table identity validation; full-matrix, manual, and
  rule-based assignment generation. Rule-based assignments are
  authored on the **Rule Builder page**
  (`/operator/sessions/{id}/assignments/rule-based-editor`) — a
  single-card surface paired with an Available Rulesets sidebar
  listing every visible RuleSet (5 seeds + caller-owned
  Personal). Generation runs through `app/services/rules/engine.py`
  (predicates / combinators / quotas / deterministic ordering).
- **Instruments builder.** Per-instrument card with state-machine
  Display + Response Fields tables, Response Type Definitions
  catalog (10 seeded RTDs + operator-defined ones), live-preview
  pane, multi-instrument support.
- **Email template editor.** Per-template (Invitation / Reminder
  / Responses-received) override of subject + body + CC + BCC,
  with the canonical merge tags (`$reviewer_name`,
  `$session_name`, `$deadline`, `$help_contact`, plus
  `$invite_url` on Invitation / Reminder and `$submitted_at` on
  Responses-received). Per-field "Reset to default"; the
  renderer falls through to in-code defaults when nothing's
  overridden. A per-session "Send confirmation when a reviewer
  submits?" checkbox gates the responses-received auto-send.
- **Operator Settings page.** Per-operator SMTP credentials
  encrypted at rest. Honours `?return_to=<path>` so the chrome
  user-menu Settings link returns the operator to wherever they
  came from.
- **Quick Setup card** on Session Home wires Reviewers /
  Reviewees / Assignments / Session settings slots over the
  existing per-entity import pipelines, behind a single Lock /
  Unlock toggle. One bottom-right Submit button (next to Lock /
  Unlock) runs every slot whose file is attached; the
  Assignments slot's "Generate by rule" dropdown is populated
  with the full visible RuleSet list and routes through the
  rule-based engine on submit. Unlock state resets when the
  operator navigates away (per-route middleware in
  `app/main.py`). Settings slot stays inert pending Segment 12A
  PR 6.
- **Extract Data card** on Session Home renders the per-entity
  download row scaffold (settings / reviewers / reviewees /
  assignments / responses / bundle), inert until Segment 12A
  wires the download paths.
- **Operations pages.** Validate (find-and-fix surface with
  severity filter chip strip + per-issue Fix-on-Setup deep
  links), Reviewer Experience Preview hub (tabbed email
  previews + iframed reviewer-surface card for an
  operator-picked reviewer), Manage Invitations (consolidated
  reviewer-centric table absorbing the retired Monitoring
  page), Responses (reviewee-centric coverage view classifying
  each reviewee per `monitoring.AT_RISK_THRESHOLDS`). Outbox
  stays a dev-diagnostic surface reachable via the "View
  outbox" button on Manage Invitations.

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
`audit_events` row with a typed `event_type` + canonical
envelope `detail` (Segment 11K — see
[`spec/architecture.md`](spec/architecture.md#audit-event-detail-schema)).
The four envelopes (`changes` / `snapshot` / `counts` /
`set_changes`) plus identity slots and orthogonal slots
(`reason` / `refs` / `context`) are validated on write through
the `EVENT_SCHEMAS` registry in `app/services/audit.py` —
strict in tests, lenient in production. Setup mutations
invalidate `validated → draft` automatically via
`lifecycle.invalidate_if_validated`.

**Email send is queued, not sent.** Outbox rows stamp
`status="queued"`; the audit-log columns the dispatch helper
will write to (`error_message`, `from_address`, `backend`,
`backend_message_id`, `delivered_at`, `payload_hash`,
`correlation_id`) landed inert with Segment 11C Part 2. The
transport interface (`EmailTransport` Protocol +
`SmtpEmailTransport` + typed-stub `GraphEmailTransport`) is
shipped and waiting to be wired up by **Segment 14-1 Part A**
(the email send-activation segment).

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
  `session_home.md`, `sessions_overview.md`, `reviewer-surface.md`,
  `quick_setup_card_spec.md`, `setup_pages.md`,
  `rule_based_assignment.md`, `email_infra_options.md`.
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
