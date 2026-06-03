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
  audit events on every state transition; `archived` is a live
  off-ramp (`draft ⇄ archived`, written by `archive_session` /
  `unarchive_session`). The sessions lobby
  (`/operator/sessions`) was rebuilt in Segment 18A as a
  selection-aware inline row-expander: per-row rename, free-form
  tagging (with a click-to-filter tag strip), one-click clone
  (full-setup or config-shell), and "Purge and archive"
  (selective hard-delete of responses / rosters / audit log via
  `session_purge`, then archive). It also carries client-side
  search, sortable columns, and a dedicated
  `/operator/sessions/archived` child page.
- **Roster management.** Reviewer / reviewee / **Relationships**
  CSV imports with cross-table identity validation. A fourth
  optional roster — **Observers** — opts in per session via the
  `observers_enabled` toggle, with its own Setup page, Quick
  Setup slot, Extract Setup row, and Zip-all bundle member.
  Each Observer carries a **Cohort match rule** (`reviewer.tag1
  IS THE SAME AS observer.tag1`, multi-rule + AND/OR, authored
  per-observer on the Observers Setup page) that partitions
  the session's assignment rows into the pool the observer can
  see on the collation surface. Assignments are **always
  derived** post-15D: rule-based generation only
  (manual-row authoring retired in 15D PR 6a). Rule-based
  assignments are authored on the **Rule Builder page**
  (`/operator/sessions/{id}/assignments/rule-based-editor`) — a
  single-card surface paired with an Available Rulesets sidebar
  listing every visible RuleSet (5 seeds + caller-owned Personal).
  Generation runs through `app/services/rules/engine.py`
  (predicates / combinators / quotas / deterministic ordering); the
  engine consumes pair-context tags from the `relationships` table
  via an eager `pair_context_lookup` dict (15D PR 4). The
  Reviewers / Reviewees / Relationships preview tables share a
  per-slot column-visibility pattern — a "Show columns:" chip /
  pill row inside the "Fields with data" card (Segment 18E
  Part 1), each chip enabled iff the column has data, choice
  persisted per browser via `localStorage`. The Assignments page
  (Segment 13C) carries the same column-visibility chips plus a
  separate operator-actions card — a "Search by" dropdown,
  row-select checkbox column, and bulk include / exclude buttons.
  The Assignments preview carries the 12-column shape (Reviewer ·
  R Tag1..3 · Reviewee · E Tag1..3 · Pair1..3 · Include); the
  trailing Status / Include cell renders as a `pill-info` /
  `pill-empty` pill. See `spec/setup_pages.md` for the contract.
- **Instruments builder.** Per-instrument card with state-machine
  Display + Response Fields tables, Response Type Definitions
  catalog (10 seeded RTDs + operator-defined ones), live-preview
  pane, multi-instrument support. A second flavour —
  **group-scoped instruments** (Segment 13C), where one reviewer
  answer covers a whole group of reviewees — is authorable via
  `Add group instrument`; a group instrument requires a pinned
  rule before it can open. The **Replicate** button clones a
  card's content into a new instrument after the source.
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
- **Extract Setup card** on Session Home ships **five-or-six
  live CSV downloads** in a 2-column layout — left column for
  per-entity rosters (Reviewers / Reviewees / Relationships),
  right column for session-level outputs (Session settings /
  Responses, plus Observers when `observers_enabled` is on),
  plus a Zip-all row in the bottom-right slot that
  (Segment 18D) is now a real `{code}_bundle.zip` download of
  the whole porting set. Settings + Reviewers / Reviewees /
  Responses landed in Segment 12A-1 (2026-05-09); Relationships
  landed in Segment 12A-3 PR 1; the legacy Manual Assignments
  tile retired in 12A-3 PR 2 (assignments are derived post-15D —
  output, not input — and have no place in a porting bundle).
  The matching Settings importer landed in 12A-3 PR 3. The
  audit-events CSV download (Segment 12B) ships its route live
  but with no Extract Data tile — per industry best practice
  audit data sits behind an admin / diagnostics doorway, so the
  extract lives behind the Sys Admin gate (Segment 16C, the
  per-session audit-log viewer, shipped).
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

**Participant surfaces** — three audiences sharing the `/me/`
chrome and a role-navigator chip strip that lets multi-role
users swap between surfaces:

- **Reviewer** at `/me/sessions/{id}/{page}`. Multi-instrument
  session as paginated pages within one form; each page is one
  instrument's table of (reviewee × response field) cells. A
  group-scoped instrument (Segment 13C) renders one row per
  boundary-defined group — a single reviewer answer covers the
  whole group, counted once across reviewer state, monitoring,
  and the Extract Data CSV. Per-page status pills
  (`not_started` / `in_progress` / `complete` / `submitted`);
  Save persists the current page's dirty inputs, Submit commits
  the whole review session-wide. Numeric inputs validate range
  natively and step-grid via JS `setCustomValidity`; server-side
  `validate_value` is the authoritative backstop. Missing-required
  and invalid-value warnings render as their own full-width
  cards below the bottom-grid; Submit is a hard gate on
  missing required.
- **Reviewee** at `/me/sessions/{id}/results`. The reviewee's
  view of responses received about them, per the per-instrument
  Band 3 visibility policy (Raw / Anonymized / Summarized mode
  picked by the operator per instrument × per audience). An
  Acknowledge card at the foot stamps
  `reviewees.results_acknowledged_at` (idempotent). Live since
  W16 + W19.
- **Observer** at `/me/sessions/{id}/collation`. Per-instrument
  3-row tables — Row 1 distinct-reviewer headcount + shared
  aggregate over the observer's in-cohort assignment pool, Row
  2 distinct-reviewee headcount + same aggregate, Row 3
  conditional `Download CSV` button. Identification mode
  follows Band 3 (Raw / Anonymized rows / Anonymized summaries).
  Anonymized downloads swap reviewer / reviewee names for
  per-session opaque tokens (`R-a3f8b2c1` / `E-9d4e7f10` via
  `app/services/participant_tokens.py`); the operator-side
  deanonymization key ships as `participant_tokens.csv` from
  the Extract data tab's Token keys card. MVP shipped
  2026-06-02; partition refactor + Token keys 2026-06-03.

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
shipped and waiting to be wired up by **Segment 14B Part A**
(the email send-activation segment; renamed from 14-1 in the
14 → 14A / 14B / 14C split).

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
pytest                  # full suite (SQLite)
pytest -n auto          # same, parallelised across CPU cores
ruff check .            # lint (config in pyproject.toml)
alembic upgrade head    # local SQLite migration
alembic downgrade -1    # round-trip check
```

`pytest-xdist` provides `-n auto`; the SQLite `:memory:`
engine is per-process and tests roll back per-test, so the
workers stay isolated. The SQLite CI job runs `pytest -n auto`.

The SQLite test path builds its schema directly from the ORM
metadata (`Base.metadata.create_all`) rather than replaying the
migration chain — faster, and the chain is still exercised on
every PR by the `ci-postgres` job. Data-only migrations are
replayed in `tests/_sqlite_schema.py`.

CI runs the same `pytest` against a `postgres:16` service
container too (`ci-postgres` job) — the suite covers both
dialects on every PR. That job stays single-process: its
workers would otherwise share one Postgres database. It applies
the full Alembic migration chain.

## Project documents

Documentation is split across three folders, each with its own
README:

- **[`spec/`](spec/)** — surface specifications and design intent.
  See [`spec/README.md`](spec/README.md) for the full, current
  index — it covers the domain / architecture specs plus the
  per-page and per-feature specs (Setup pages, operations pages,
  the reviewer surface, rule-based assignment, group-scoped
  instruments, timezone display, the settings inventory, and more).
- **[`docs/`](docs/)** — reference material about the running
  system ([`docs/README.md`](docs/README.md)). Includes
  `status.md`, `authentication.md`, `database.md`, `imports.md`,
  `local_setup.md`, `deployment_dev.md`, plus the Segment 14A
  operations set (`operations_runbook.md`, `troubleshooting.md`,
  `backup_restore.md`, `known_limitations.md`,
  `security_posture.md`).
- **[`guide/`](guide/)** — forward-looking plans, segment
  workplans, todos ([`guide/README.md`](guide/README.md)).
  Shipped segment plans are in
  [`guide/archive/`](guide/archive/);
  [`guide/todo_master.md`](guide/todo_master.md) is the roadmap.

Top-level docs at the repo root: `CLAUDE.md` / `AGENTS.md` (kept
as byte-identical twins; AI-agent guidance),
`CONTRIBUTING.md`, `README.md` (this file).
