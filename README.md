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

### Operator surface

Per-session pages are organised into a Setup row + an Operations
row, both anchored off Session Home in the per-session chrome.
A workspace-level **Operator Settings** page sits behind the
top-bar user menu (per-operator SMTP credentials + display
timezone), not in the per-session chrome.

#### Workspace pages

| URL | Surface |
|---|---|
| `/operator/sessions` | Sessions lobby — selection-aware inline row-expander with per-row rename, free-form tagging (click-to-filter tag strip), one-click clone (full-setup or config-shell), client-side search, sortable columns, and **Purge and archive** (selective hard-delete of responses / rosters / audit log via `session_purge`, then archive). |
| `/operator/sessions/archived` | Archived sessions — the live off-ramp for the `draft ⇄ archived` cycle. |
| `/operator/sessions/new` | Create a new session. |
| `/operator/settings` | **Operator Settings** — per-operator SMTP credentials (encrypted at rest) + display timezone. Honours `?return_to=<path>` so the user-menu link returns to the calling page. |
| `/operator/sys-admin` | Sys Admin chrome root (sys-admin-gated). |
| `/operator/sys-admin/sessions` | Admin Sessions Diagnostics — also hosts the per-session **Outbox** drill-in. |
| `/operator/sys-admin/sessions/{id}/outbox` | Inline per-session email outbox (sys-admin-gated). |
| `/operator/sys-admin/sessions/{id}/audit-log` | Per-session audit-log viewer with filter strip + per-row pretty-printer. |
| `/operator/sys-admin/users` | Workspace user / role management — admit, revoke, promote, demote, invite. |

#### Per-session pages

All under `/operator/sessions/{session_id}/`. The Setup row
covers configuration; the Operations row covers running the
session and pulling data out.

| URL suffix | Row | Surface |
|---|---|---|
| (root) | — | **Session Home** — Workflow card, Quick Setup card, Extract Setup card, Next Action card. |
| `edit` | — | **Session details** — name / code / deadline / timezone / per-session toggles (`relationships_enabled`, `observers_enabled`) + Owners section (add / remove with `last_owner` race guard via `SELECT ... FOR UPDATE`). |
| `reviewers` | Setup | **Reviewers** — per-row CRUD + bulk CSV import + bulk status flips. |
| `reviewees` | Setup | **Reviewees** — same shape; identifier may be email or opaque token. |
| `relationships` | Setup | **Relationships** — pair-context tags driving rule-engine cross-pair predicates. Tab gated by `relationships_enabled`. |
| `observers` | Setup | **Observers** — opt-in fourth roster, gated by `observers_enabled`. Each Observer carries a **Cohort match rule** (multi-predicate, AND/OR; e.g. `reviewer.tag1 IS THE SAME AS observer.tag1`) authored on this page. |
| `instruments` | Setup | **Instruments** — per-instrument card with Bands 1+2+3. Band 1 authors the assignment rule; Band 2 is the operator-side reviewer-surface preview; Band 3 hosts the Response Fields table with inline `data_type` + bounds. Group-scoped instruments (one reviewer answer per group of reviewees) are authorable via `Add group instrument`; a group instrument requires a pinned rule before it can open. The **Replicate** button clones a card's content into a new instrument after the source. |
| `setupinvite` | Setup | **Email Template** — per-template (Invitation / Reminder / Responses-received) override of subject + body + CC + BCC, with the canonical merge tags (`$reviewer_name`, `$session_name`, `$deadline`, `$help_contact`, plus `$invite_url` on Invitation / Reminder and `$submitted_at` on Responses-received). |
| `assignments` | Operations | **Assignments** — per-instrument status table (rule selection + self-review inclusion per instrument) + Assignments preview table (12-column shape: Reviewer · R Tag1..3 · Reviewee · E Tag1..3 · Pair1..3 · Include). "Search by" dropdown, row-select checkboxes, bulk include / exclude buttons. |
| `validate` | Operations | **Validate** — find-and-fix surface with severity filter chip strip + per-issue Fix-on-Setup deep links. |
| `previews` | Operations | **Previews** — Reviewer Experience Preview hub: tabbed email previews + iframed reviewer-surface card for an operator-picked reviewer. |
| `invitations` | Operations | **Manage Invitations** — reviewer-centric table covering both invitation status and per-reviewer review progress. |
| `responses` | Operations | **Responses** — reviewee-centric coverage view classifying each reviewee per `monitoring.AT_RISK_THRESHOLDS`. |
| `extract-data` | Operations | **Extract data** — response-data shaping pipeline (per-instrument lens cards + Data shaper) + Token keys deanonymization extract (`participant_tokens.csv`). |

#### Session Home cards

- **Quick Setup card** wires Reviewers / Reviewees / Relationships / Session settings slots (plus an Observers slot when `observers_enabled` is on) over the existing per-entity import pipelines, behind a single Lock / Unlock toggle. Two-column layout — Reviewers + Reviewees on the left, the rest on the right. One bottom-right Submit button runs every slot whose file is attached. Unlock state resets when the operator navigates away. The Settings slot posts to `/operator/sessions/{id}/import-config`, applying the 3-column Settings CSV via `apply_session_config`.
- **Extract Setup card** ships **five-or-six live CSV downloads** plus a Zip-all in a 2-column layout — left column for per-entity rosters (Reviewers / Reviewees / Relationships), right column for session-level outputs (Session settings / Responses, plus Observers when `observers_enabled` is on). The Zip-all row delivers `{code}_bundle.zip` over the whole porting set. Audit data sits behind the Sys Admin gate rather than appearing on either operator-side extracts surface.

#### Session lifecycle

`draft → validated → ready` (Activated) with edit-locks, deadline tracking, response-window gates, and audit events on every state transition. `archived` is a live off-ramp (`draft ⇄ archived`, written by `archive_session` / `unarchive_session`). Setup mutations invalidate `validated → draft` automatically via `lifecycle.invalidate_if_validated`.

#### Assignment model

Assignments are **always derived** — rule-based generation only; manual-row authoring is not supported. Rules author per-instrument on **Band 1** of the Instruments page. Generation runs through `app/services/rules/engine.py` (predicates / combinators / quotas / deterministic ordering); the engine consumes pair-context tags from the `relationships` table via an eager `pair_context_lookup` dict.

### Participant surfaces

Three audiences share the `/me/` chrome and a role-navigator chip strip that lets multi-role users swap between surfaces.

| URL | Surface |
|---|---|
| `/me/sessions/{id}/{page}` | **Reviewer.** Multi-instrument session as paginated pages within one form; each page is one instrument's table of (reviewee × response field) cells. A group-scoped instrument renders one row per boundary-defined group — a single reviewer answer covers the whole group, counted once across reviewer state, monitoring, and the response extract. Per-page status pills (`not_started` / `in_progress` / `complete` / `submitted`); Save persists the current page's dirty inputs, Submit commits the whole review session-wide. Numeric inputs validate range natively and step-grid via JS `setCustomValidity`; server-side `validate_value` is the authoritative backstop. Missing-required and invalid-value warnings render as their own full-width cards below the bottom-grid; Submit is a hard gate on missing required. |
| `/me/sessions/{id}/results` | **Reviewee.** The reviewee's view of responses received about them, per the per-instrument Band 3 visibility policy (Raw / Anonymized / Summarized mode picked by the operator per instrument × per audience). An Acknowledge card at the foot stamps `reviewees.results_acknowledged_at` (idempotent). |
| `/me/sessions/{id}/collation` | **Observer.** Per-instrument 3-row tables — Row 1 distinct-reviewer headcount + shared aggregate over the observer's in-cohort assignment pool, Row 2 distinct-reviewee headcount + same aggregate, Row 3 conditional `Download CSV` button. Identification mode follows Band 3 (Raw / Anonymized rows / Anonymized summaries). Anonymized downloads swap reviewer / reviewee names for per-session opaque tokens (`R-a3f8b2c1` / `E-9d4e7f10` via `app/services/participant_tokens.py`); the operator-side deanonymization key ships as `participant_tokens.csv` from the Extract data tab's Token keys card. |

### Lifecycle + audit

Every mutating service writes an `audit_events` row with a typed `event_type` + canonical envelope `detail` (see [`spec/architecture.md`](spec/architecture.md#audit-event-detail-schema)). The four envelopes (`changes` / `snapshot` / `counts` / `set_changes`) plus identity slots and orthogonal slots (`reason` / `refs` / `context`) are validated on write through the `EVENT_SCHEMAS` registry in `app/services/audit.py` — strict in tests, lenient in production.

### Email send

Email send is **queued, not sent**. Outbox rows stamp `status="queued"`; the audit-log columns the dispatch helper will write to (`error_message`, `from_address`, `backend`, `backend_message_id`, `delivered_at`, `payload_hash`, `correlation_id`) sit inert on the row. The transport interface (`EmailTransport` Protocol + `SmtpEmailTransport` + typed-stub `GraphEmailTransport`) is shipped but not yet wired up to the dispatch helper.

For the latest snapshot of what's shipped vs. pending, see [`docs/status.md`](docs/status.md).

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
  the reviewer surface, assignments, instruments, timezone
  display, the settings inventory, and more).
- **[`docs/`](docs/)** — reference material about the running
  system ([`docs/README.md`](docs/README.md)). Includes
  `status.md`, `authentication.md`, `database.md`, `imports.md`,
  `local_setup.md`, `deployment_dev.md`, plus the operations
  set (`operations_runbook.md`, `troubleshooting.md`,
  `backup_restore.md`, `known_limitations.md`,
  `security_posture.md`).
- **[`guide/`](guide/)** — forward-looking plans, segment
  workplans, todos ([`guide/README.md`](guide/README.md)).
  Shipped segment plans live in
  [`guide/archive/`](guide/archive/);
  [`guide/todo_master.md`](guide/todo_master.md) is the
  roadmap;
  [`guide/deferred_until_pilot_feedback.md`](guide/deferred_until_pilot_feedback.md)
  is the parking lot for scoped-but-paused product work waiting
  on pilot feedback, and
  [`guide/deferred_infra.md`](guide/deferred_infra.md) is the
  same for infrastructure / platform work.

Top-level docs at the repo root: `CLAUDE.md` / `AGENTS.md` (kept
as byte-identical twins; AI-agent guidance),
`CONTRIBUTING.md`, `README.md` (this file).
