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
- **Roster management.** Reviewer / reviewee / **Relationships**
  CSV imports with cross-table identity validation. Assignments
  are **always derived** post-15D: rule-based generation only
  (manual-row authoring retired in 15D PR 6a). Rule-based
  assignments are authored on the **Rule Builder page**
  (`/operator/sessions/{id}/assignments/rule-based-editor`) — a
  single-card surface paired with an Available Rulesets sidebar
  listing every visible RuleSet (5 seeds + caller-owned Personal).
  Generation runs through `app/services/rules/engine.py`
  (predicates / combinators / quotas / deterministic ordering); the
  engine consumes pair-context tags from the `relationships` table
  via an eager `pair_context_lookup` dict (15D PR 4). The
  Reviewers / Reviewees / Relationships / Assignments preview
  tables share a per-slot column-visibility pattern — right-flushed
  checkbox row above each table, default ticked iff the column has
  data, choice persisted per browser via `localStorage`.
  Assignments preview carries the 12-column shape (Reviewer · R
  Tag1..3 · Reviewee · E Tag1..3 · Pair1..3 · Include); the trailing
  Status / Include cell renders as a `pill-info` / `pill-empty`
  pill. See `spec/setup_pages.md` for the contract.
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
  Reviewees / **Relationships** / Session settings slots over the
  existing per-entity import pipelines, behind a single Lock /
  Unlock toggle. The card uses a two-column layout — Reviewers +
  Reviewees on the left, Relationships + Session settings on the
  right (Post-Segment 15 clean up, 2026-05-10). One bottom-right
  Submit button (next to Lock / Unlock) runs every slot whose
  file is attached. Unlock state resets when the operator
  navigates away (per-route middleware in `app/main.py`). The
  Settings slot graduated to live in Segment 12A-3 PR 4 and
  posts to `/operator/sessions/{id}/import-config`, applying
  the 3-column Settings CSV via `apply_session_config`.
- **Extract Data card** on Session Home ships **five live CSV
  downloads** in a 2-column layout — left column for
  per-entity rosters (Reviewers / Reviewees / Relationships),
  right column for session-level outputs (Session settings /
  Responses), with the inert Zip-all row in the bottom-right
  slot. Settings + Reviewers / Reviewees / Responses landed
  in Segment 12A-1 (2026-05-09); Relationships landed in
  Segment 12A-3 PR 1; the legacy Manual Assignments tile
  retired in 12A-3 PR 2 (assignments are derived post-15D —
  output, not input — and have no place in a porting bundle).
  The matching Settings importer ships in 12A-3 PR 3.
  Audit-events download (Segment 12B PR 1) ships the route
  live but **without an Extract Data tile** — per industry
  best practice audit data sits behind an admin / diagnostics
  doorway rather than alongside everyday data exports, so the
  tile relocates to the Sys Admin page when Segment 16 ships.
- **Operations pages.** Validate · **Assignments** · Previews ·
  Invitations · Responses (Assignments moved into the Operations
  row in 15D PR 6a). Validate is the find-and-fix surface
  (severity filter chip strip + per-issue Fix-on-Setup deep
  links). Assignments hosts the Assignment Rule card +
  Self-reviews bulk toggle + the Assignment pairs preview
  table. Previews is the Reviewer Experience Preview hub
  (tabbed email previews + iframed reviewer-surface card for an
  operator-picked reviewer). Manage Invitations is a consolidated
  reviewer-centric table that absorbed the retired Monitoring
  page. Responses is the reviewee-centric coverage view
  classifying each reviewee per `monitoring.AT_RISK_THRESHOLDS`.
  Outbox stays a dev-diagnostic surface reachable via the "View
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
