# Review Robin Web

Web-based, structured review-cycle tool. Operators configure
reviewer / reviewee rosters and assignments, design per-instrument
response forms, send out invitations, and monitor reviewer
progress through a deadline. Reviewers fill out the per-instrument
forms via per-reviewer invitation links.

Built as a FastAPI + Jinja + SQLAlchemy monolith, deployed to
Azure App Service (Linux, Python 3.12) against an Azure Postgres
Flexible Server. Local dev runs against SQLite.

For the *why* — the class of problem RRW targets, the two
projects that shaped it (an Excel/VBA predecessor and
TEAMMATES), the constraints that made it look the way it does,
and the trade-offs it knowingly accepts — see
[`rrw_design_rationale.md`](rrw_design_rationale.md). For the
*how* — the working practice, read as a form of spec-driven
development: the three-layer document model, the segment plan as
the unit of work, which conventions are enforced by a failing
test, and where a human is still the verifier — see
[`rrw_sdd_in_practice.md`](rrw_sdd_in_practice.md). The six rules
every change is held to, extracted from that document's core
decisions with rationale and trade-off and nothing else, are
[`constitution.md`](constitution.md).

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
| `/operator/sessions` | Sessions lobby — selection-aware inline row-expander that edits a session's Name, Code, Deadline and Tags, free-form tagging (click-to-filter tag strip), one-click clone (full-setup or config-shell), client-side search, sortable columns, and **Purge and archive** (selective hard-delete of responses / rosters / audit log via `session_purge`, then archive). |
| `/operator/sessions/archived` | Archived sessions — the live off-ramp: any session that is not activated (`ready`) or already archived can be archived, and unarchiving restores it to `draft`. |
| `/operator/sessions/new` | Create a new session. |
| `/operator/settings` | **Operator Settings** — per-operator SMTP credentials (encrypted at rest) + display timezone. Honours `?return_to=<path>` so the user-menu link returns to the calling page. |
| `/operator/sys-admin` | Sys Admin chrome root (sys-admin-gated). |
| `/operator/sys-admin/sessions` | Admin Sessions Diagnostics — also hosts the per-session **Outbox** drill-in. |
| `/operator/sys-admin/sessions/{id}/outbox` | Inline per-session email outbox (sys-admin-gated). |
| `/operator/sys-admin/sessions/{id}/audit-log` | Per-session audit-log viewer with filter strip + per-row pretty-printer. |
| `/operator/sys-admin/users` | Workspace user / role management (three-tier operator ⊂ admin ⊂ super-admin, Segment 18S) — admit, revoke, promote, demote, remove, with super-admin-actor + protected-super-admin guards. |

#### Per-session pages

All under `/operator/sessions/{session_id}/`. The Setup row
covers configuration; the Operations row covers running the
session and pulling data out.

| URL suffix | Row | Surface |
|---|---|---|
| (root) | — | **Session Home** — Workflow / Next Action card, the **Session details** config card (name / code / deadline / timezone / per-session toggles `relationships_enabled` / `observers_enabled` + Owners, with a `last_owner` race guard via `SELECT ... FOR UPDATE`), Quick Setup card, and Danger Zone. Session-details config displays and edits **inline** via a `?editing=1` display↔edit swap; the standalone Edit page retired in 18R Item 4 (`/edit` 308-redirects here). |
| `reviewers` | Setup | **Reviewers** — per-row CRUD + bulk CSV import + bulk status flips. |
| `reviewees` | Setup | **Reviewees** — same shape; identifier may be email or opaque token. |
| `relationships` | Setup | **Relationships** — pair-context tags driving rule-engine cross-pair predicates. Tab gated by `relationships_enabled`. |
| `observers` | Setup | **Observers** — opt-in fourth roster, gated by `observers_enabled`. Each Observer carries a **Cohort match rule** (multi-predicate, AND/OR; e.g. `reviewer.tag1 IS THE SAME AS observer.tag1`) authored on this page. |
| `instruments` | Setup | **Instruments** — per-instrument card with Bands 1+2+3. Band 1 authors the assignment rule; Band 2 is the operator-side reviewer-surface preview; Band 3 hosts the Response Fields table with inline `data_type` + bounds. Group-scoped instruments (one reviewer answer per group of reviewees) are configured **on the card** — a group boundary + unit-of-review in Band 1, and the instrument opens with the session like any other. New instruments are added via **+Instrument** (the legacy `Add instrument` / `Add group instrument` buttons retired); **+Page break** inserts a reviewer-surface page break, and **Replicate** clones a card's content into a new instrument after the source. |
| `setup-invite` | Setup | **Email Template** — per-template (Invitation / Reminder / Responses-received) override of subject + body + CC + BCC, with the canonical merge tags (`$reviewer_name`, `$session_name`, `$deadline`, `$help_contact`, plus `$invite_url` on Invitation / Reminder and `$submitted_at` on Responses-received). |
| `assignments` | Operations | **Assignments** — per-instrument status table (counts, a self-review include checkbox per instrument, a Show filter, and an "Edit on Instruments page" link; the rule itself is authored on Band 1) + Assignments preview table (Reviewer · R Tag1..3 · Reviewee · E Tag1..3 · Pair1..3 · Include · Instrument; an empty tag slot renders no column). "Status" and "Search by" filters in the toolbar, row-select checkboxes, and bulk Inactivate / Activate in the row expander. |
| `validate` | Operations | **Validate** — find-and-fix surface with severity filter chip strip + per-issue Fix-on-Setup deep links. |
| `previews` | — | Retired Previews hub (19Q Item 1); no row, because it is no longer a tab — a permanent redirect to Invitations. |
| `invitations` | Operations | **Manage Invitations** — reviewer-centric table covering invitation status and review progress; each reviewer drill-in carries the three email previews and the door to the inert reviewer surface. |
| `responses` | Operations | **Responses** — reviewee-centric coverage view classifying each reviewee per `monitoring.AT_RISK_THRESHOLDS`. |
| `extract-data` | Operations | **Extract data** — response-data shaping pipeline (per-instrument lens cards + Data shaper) + Token keys deanonymization extract (`participant_tokens.csv`). |

- **Session details card** displays the session's config (name / code / deadline / timezone / per-session toggles + Owners) and edits it **inline** via a `?editing=1` display↔edit swap — the standalone Edit page retired in 18R Item 4.
- **Quick Setup card** wires Reviewers / Reviewees / Relationships / Session settings slots (plus an Observers slot when `observers_enabled` is on) over the existing per-entity import pipelines, behind a single Lock / Unlock toggle. Two-column layout — Reviewers + Reviewees on the left, the rest on the right. One bottom-right Submit button runs every slot whose file is attached. Unlock state resets when the operator navigates away. The Settings slot posts to `/operator/sessions/{id}/import-config`, applying the 3-column Settings CSV via `apply_session_config`.
- **Danger Zone** — Delete data + Delete session, at the bottom-right of Home (moved off the retired Edit page).

The **Extract Setup card** (five-or-six live CSV downloads — per-entity rosters + session-level Settings / Responses, plus Observers when `observers_enabled`, with a Zip-all `{code}_setup.zip`) **relocated to the Extract data Operations page** in 18R Item 4; it is no longer a Session Home card. Audit data stays behind the Sys Admin gate rather than appearing on either operator-side extracts surface.

#### Session lifecycle

`draft → validated → ready` (Activated) `→ expired` (Closed) with edit-locks, deadline tracking, response-window gates, and audit events on every state transition. `archived` is a live off-ramp: `archive_session` accepts any state but `ready` (pause it first) and `archived`, and `unarchive_session` restores `archived → draft`. Setup mutations invalidate `validated → draft` automatically via `lifecycle.invalidate_if_validated`.

#### Assignment model

Assignments are **always derived** — rule-based generation only; manual-row authoring is not supported. Rules author per-instrument on **Band 1** of the Instruments page. Generation runs through `app/services/rules/engine.py` (predicates / combinators / quotas / deterministic ordering); the engine consumes pair-context tags from the `relationships` table via an eager `pair_context_lookup` dict.

### Participant surfaces

Three audiences share the `/me/` chrome and a role-navigator chip strip that lets multi-role users swap between surfaces.

| URL | Surface |
|---|---|
| `/me/sessions/{id}/{page}` | **Reviewer.** Multi-instrument session as paginated pages within one form; each page holds one or more instruments, split where the operator places a page break, and each instrument renders as a table of (reviewee × response field) cells. A group-scoped instrument renders one row per boundary-defined group — a single reviewer answer covers the whole group, counted once across reviewer state, monitoring, and the response extract. Per-page status pills (`not_started` / `in_progress` / `complete` / `submitted`); Save persists the current page's dirty inputs, Submit commits the whole review session-wide. Numeric inputs validate range natively and step-grid via JS `setCustomValidity`; server-side `validate_value` is the authoritative backstop. Missing-required and invalid-value warnings render as their own full-width cards below the bottom-grid; Submit is a hard gate on missing required. |
| `/me/sessions/{id}/results` | **Reviewee.** The reviewee's view of responses received about them, per the per-instrument Band 2 visibility policy (Raw / Anonymized / Summarized mode picked by the operator per instrument × per audience). An Acknowledge card at the foot stamps `reviewees.results_acknowledged_at` (idempotent). |
| `/me/sessions/{id}/collation` | **Observer.** Per-instrument 3-row tables — Row 1 distinct-reviewer headcount + shared aggregate over the observer's in-cohort assignment pool, Row 2 distinct-reviewee headcount + same aggregate, Row 3 conditional `Download CSV` button. Identification mode follows Band 2 (Raw / Anonymized rows / Anonymized summaries). Anonymized downloads swap reviewer / reviewee names for per-session opaque tokens (`R-a3f8b2c1` / `E-9d4e7f10` via `app/services/participant_tokens.py`); the operator-side deanonymization key ships as `participant_tokens.csv` from the Extract data tab's Token keys card. |

### Lifecycle + audit

Every mutating service writes an `audit_events` row with a typed `event_type` + canonical envelope `detail` (see [`spec/architecture.md`](spec/architecture.md#audit-event-detail-schema)). The four envelopes (`changes` / `snapshot` / `counts` / `set_changes`) plus identity slots and orthogonal slots (`reason` / `refs` / `context`) are validated on write through the `EVENT_SCHEMAS` registry in `app/services/audit.py` — strict in tests, lenient in production.

### Email send

Email is **recorded, not sent**. The invitation and reminder paths write each outbox row `queued` and flip it to `sent` with no transport call, and a reviewer's submit queues the responses-received confirmation and leaves it `queued`; stamping `queued` until a transport really sends is work awaiting Azure (`guide/post_azure_todo_checklist.md` item 8). Six of the audit-log columns the dispatch helper will write to (`error_message`, `from_address`, `backend`, `backend_message_id`, `delivered_at`, `payload_hash`) sit inert on the row; `correlation_id` is already stamped and read back by scheduled reminders. The transport interface (`EmailTransport` Protocol + `SmtpEmailTransport` + typed-stub `GraphEmailTransport`) is shipped but not yet wired up to the dispatch helper.

For what is still to be built, see [`guide/todo_master.md`](guide/todo_master.md); for what shipped and when, the archived segment plans indexed in [`guide/archive/README.md`](guide/archive/README.md).

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
headers instead — see [`docs/security_posture.md`](docs/security_posture.md).

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

**Browser tests** (`tests/browser/`, plan `guide/archive/browser_test.md`)
serve the app live with fake auth and drive it with Chromium through
Python Playwright, a dev dependency pinned to the minor whose
Chromium build the web sandbox ships. They skip, saying why, when no
Chromium is installed; run `python -m playwright install chromium`
once to enable them locally. The SQLite CI job installs Chromium and
sets `RRW_REQUIRE_BROWSER=1`, which turns that skip into a failure.
`tests/integration/test_inline_scripts_parse.py` needs `node` on PATH
and skips without it. CI's `ubuntu-latest` runners have `node`, but no
switch turns that skip into a failure, so read the skip list rather than
just the exit code.

CI runs the same `pytest` against a `postgres:16` service
container too (`ci-postgres` job) — the suite covers both
dialects on every PR. That job stays single-process: its
workers would otherwise share one Postgres database. It applies
the full Alembic migration chain, and leaves out `tests/browser/`.

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
  `security_posture.md`, `database.md`,
  `local_setup.md`, `deployment_dev.md`, plus the operations
  set (`operations_runbook.md`, `troubleshooting.md`,
  `backup_restore.md`, `known_limitations.md`).
- **[`guide/`](guide/)** — forward-looking plans, segment
  workplans, todos ([`guide/README.md`](guide/README.md)).
  Shipped segment plans live in
  [`guide/archive/`](guide/archive/);
  [`guide/todo_master.md`](guide/todo_master.md) is the
  open-work list; and
  [`guide/deferred_consolidated.md`](guide/deferred_consolidated.md)
  is the parking lot for all scoped-but-not-scheduled work —
  product slices paused on pilot feedback (Part A), deferred
  infrastructure / platform hardening (Part B), and off-roadmap
  future possibilities (Part C).

Top-level docs at the repo root: `CLAUDE.md` / `AGENTS.md` (kept
as byte-identical twins; AI-agent guidance),
`CONTRIBUTING.md`,
[`rrw_design_rationale.md`](rrw_design_rationale.md) (the *why*
behind RRW's design — problem framing, the Review Robin (VBA) +
TEAMMATES lineage, core decisions, and stated trade-offs),
[`rrw_sdd_in_practice.md`](rrw_sdd_in_practice.md) (the *how* —
RRW's working practice read against spec-driven development:
plan on the way in, spec on the way out, conventions as failing
tests, a separate reader, a human verifier of last resort),
[`constitution.md`](constitution.md) (the six binding rules distilled
from that document's §6 — decision, rationale, trade-off, and stop),
[`new_project_practices_setup.md`](new_project_practices_setup.md)
(the procedure an agent runs to carry this practice into a *new*
repository on the same stack: `tools/practice_kit.py` exports the
practice's files, the document says how each is adapted and verified),
[`azure_ask.md`](azure_ask.md) (the original institutional-Azure ask,
answered differently and kept as a record; its retirement is queued in
`guide/post_azure_todo_checklist.md`),
`README.md` (this file).
