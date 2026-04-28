# Implementation status

**As of:** end of Segment 8 (2026-04-28)

This document is a periodic snapshot of what Review Robin Web actually
does today, vs. what is planned but not yet implemented. It is updated
at the end of each segment. Per-segment plans live in
`guide/segment_NN_*` and `guide/segment_NNA.md`.

For the full long-term plan see
`guide/low_intensity_workplan_review_robin_web.md`.

---

## Project timeline

| Date | Milestone |
|---|---|
| 2026-04-25 | GitHub repository created |
| 2026-04-26 | Azure subscription + App Service provisioned |
| 2026-04-27 | Postgres Flexible Server provisioned; Segments 1–4 shipped (skeleton, deploy, auth, data model) |
| 2026-04-28 | Segments 5–7 shipped (operator session MVP, imports + validation, assignment generation) |
| 2026-04-29 | Segment 8 shipped (reviewer surface MVP + roster status-filter retrofit) |

---

## Segments shipped

| Segment | What it added | Completed |
|---|---|---|
| 1 | Repository skeleton, `/health`, local dev install | 2026-04-27 |
| 2 | Azure App Service deployment via OIDC | 2026-04-27 |
| 3 | Microsoft Entra ID sign-in via Easy Auth | 2026-04-27 |
| 4 | 12-table schema + Alembic migration infra | 2026-04-27 |
| 5 | Postgres provisioning + migrate-on-deploy + operator session CRUD-lite | 2026-04-28 |
| 6 | Reviewer / reviewee CSV imports + setup validation | 2026-04-28 |
| 7 | FullMatrix + Manual assignment generation + roster Manage views | 2026-04-28 |
| 8 | Reviewer dashboard + review surface (save / submit / clear / cancel); active-only roster filter retrofit | 2026-04-29 |

Migration round-trips on both SQLite (every test session) and Postgres
(every PR via the `ci-postgres-migration` smoke job).

---

## Capabilities today

### Infrastructure & dev loop

- **Azure App Service** (Linux, Python 3.12, gunicorn + uvicorn).
- **Azure Postgres Flexible Server** (Burstable B1ms, Pg 16, Southeast
  Asia). Public access with firewall allow-list ("Allow Azure
  services" + dev IP). VNet integration deferred to Segment 14.
- **Deploy on push to `main`** — three jobs: `build` → `migrate` →
  `deploy`. The `migrate` job runs `alembic upgrade head` against
  Azure Postgres before the App Service swap; deploy is skipped if
  migration fails.
- **CI on every PR**: SQLite pytest plus a `postgres-migration` smoke
  job that applies and round-trips migrations against a `postgres:16`
  service container.
- **Test infrastructure**: in-memory SQLite engine running real
  Alembic migrations once per session; per-test savepoint-based
  isolation so service-layer commits don't leak across tests;
  `make_client` factory for multi-user integration tests.
- **Documentation**: `docs/{authentication,database,imports}.md`,
  `deployment_dev.md` (incl. one-time Postgres GRANT bootstrap),
  segment plans in `guide/`.

### Authentication & permissions

- **Microsoft Entra ID via Azure Easy Auth** in deployed environments.
- **Local fake-auth fallback** (`ALLOW_FAKE_AUTH=true`) for offline
  development.
- **`AuthenticatedUser`** dataclass parses `X-MS-CLIENT-PRINCIPAL` and
  the simpler `X-MS-CLIENT-PRINCIPAL-{NAME,ID,IDP}` headers.
- **`get_or_create_user`** dependency creates a `User` row on first
  sign-in. We don't pre-provision.
- **`require_session_operator`** dependency gates every operator route
  on a `SessionOperator(user, session)` row — non-operators get **403**
  and never see another operator's session.
- **Diagnostic pages**: `/me` (JSON), `/me/debug` (HTML with the raw
  claims list and a sign-out link).

### UI / branding

- Inline-SVG favicon (bird emoji 🐦) defined in
  `app/web/templates/base.html`. Edit the emoji or the SVG markup
  in the `<link rel="icon">` data URI to change it; for a real
  graphic asset, mount `StaticFiles` and point `href` at
  `/static/favicon.png`.
- Topbar with sign-out link, monospace tabular code spans,
  card-based layout, severity pills (`error` / `warning` / `info`)
  for validation issues. All inline `<style>` in `base.html`. CSS
  framework / extraction is a Segment 14 concern.

### Operator-facing app

| URL | What it does |
|---|---|
| `GET /` | service metadata |
| `GET /health` | unauthenticated `{"status": "ok"}` |
| `GET /me`, `/me/debug` | identity introspection |
| `GET /operator/sessions` | list of sessions where user is operator |
| `GET /operator/sessions/new` | create form |
| `POST /operator/sessions` | create + insert `SessionOperator` + audit + 303 |
| `GET /operator/sessions/{id}` | session detail (counts, mode pill, links) |
| `GET /operator/sessions/{id}/edit` | edit form |
| `POST /operator/sessions/{id}/edit` | apply changes + audit |
| `POST /operator/sessions/{id}/delete` | delete session and all dependents (confirm) |
| `GET /operator/sessions/{id}/validate` | setup validation page |
| `GET /operator/sessions/{id}/reviewers` | roster Manage view |
| `GET /operator/sessions/{id}/reviewers/import` | upload form |
| `POST /operator/sessions/{id}/reviewers/import` | parse + replace + audit |
| `POST /operator/sessions/{id}/reviewers/delete-all` | delete every reviewer + cascade |
| `GET /operator/sessions/{id}/reviewees` | roster Manage view |
| `GET /operator/sessions/{id}/reviewees/import` | upload form |
| `POST /operator/sessions/{id}/reviewees/import` | parse + replace + audit |
| `POST /operator/sessions/{id}/reviewees/delete-all` | delete every reviewee + cascade |
| `GET /operator/sessions/{id}/assignments` | hub (counts, mode pill, current pairs) |
| `POST /operator/sessions/{id}/assignments/full-matrix` | preview / save |
| `POST /operator/sessions/{id}/assignments/manual/import` | preview / save |
| `POST /operator/sessions/{id}/assignments/delete-all` | delete every assignment, clear mode |

### Reviewer-facing app

| URL | What it does |
|---|---|
| `GET /reviewer` | dashboard: sessions where user has an active `Reviewer` row; per-session pill (`not started` / `in progress` / `submitted`) |
| `GET /reviewer/sessions/{id}` | review surface: editable table of assigned reviewees and Default Instrument fields; ?saved=ok / ?submitted=ok flash banners |
| `POST /reviewer/sessions/{id}/save` | upsert response cells (empty value deletes the row); 303 → surface with `?saved=ok` |
| `POST /reviewer/sessions/{id}/submit` | persist + validate required; 400 + warn-and-override on missing without acknowledge; else stamps `submitted_at` and 303 → surface with `?submitted=ok` |
| `POST /reviewer/sessions/{id}/clear` | delete every response for this reviewer in this session (confirm checkbox required); 303 → surface |

The Cancel link on the surface is just `<a>` back to `GET /reviewer/sessions/{id}` — no server-side state change.

### Sessions

- Create with name, code (unique per operator), description, deadline.
- Session creation **also synchronously creates the Default
  Instrument** with two seed response fields (`rating` integer 1–5
  required; `comments` long text optional). Operator-controlled
  instrument editing lands later (Segment 10); until then this
  placeholder is what the reviewer surface renders against. See
  `ARCHITECTURE.md` "Conceptual hierarchy."
- View detail with live counts of reviewers, reviewees, assignments,
  and the current `assignment_mode`.
- **Edit** name / code / description / deadline; changes recorded as
  `session.updated` with a `changes: {field: [old, new]}` map.
- **Delete** session — removes operators, reviewers, reviewees,
  instruments, assignments, invitations, and the session's audit
  events; a final `session.deleted` event with `session_id=None`
  survives in the global audit log. Requires explicit confirm
  checkbox.

### Reviewers & reviewees

- **CSV upload** with required `ReviewerName/ReviewerEmail` (or
  `RevieweeName/RevieweeEmail`); optional `Tag1/2/3` for future
  RuleBased; optional `PhotoLink` on reviewees.
- **One-shot replace** with explicit confirm checkbox when the session
  already has rows. CSV files cap at 1 MiB / 5000 rows. Unknown
  columns are silently ignored. UTF-8 with BOM tolerated.
- **Browseable Manage views** showing the saved rows in a table, with
  Replace CSV link.
- **Setup validation** page lists structural issues (no reviewers, no
  reviewees, duplicate emails) plus info-level placeholders for not-
  yet-implemented surfaces.
- **Cascade safety**: re-uploading a roster on a session with
  assignments deletes those assignments via ORM cascade. Operator
  sees a warning before they confirm. Audit event records the
  cascaded count.
- **Delete all** reviewers / reviewees from the roster Manage page
  with explicit confirm checkbox. Cascades to assignments. Audit
  events `reviewers.deleted_all` / `reviewees.deleted_all` record
  both the deleted count and the cascaded assignment count.

### Assignments

- **Hub page** at `/operator/sessions/{id}/assignments` with current
  count, mode pill, browseable Pairs table, and per-mode generation
  forms.
- **FullMatrix mode**: deterministic every-with-every; default
  excludes self-review (case-insensitive email/identifier match);
  preview shows total + coverage + the first 200 pairs; replace-all
  on confirm. Inactive reviewers and reviewees (rows whose `status`
  is anything other than `"active"`) are silently excluded; the
  audit `excluded_counts` records `inactive_reviewer` /
  `inactive_reviewee` keys when any are skipped.
- **Manual CSV mode**: required `ReviewerEmail`/`RevieweeEmail` (must
  exist in roster, and roster row must be active); optional
  `IncludeAssignment`, `PairContext1/2/3`, and
  `AssignmentContext1/2/3`. Re-upload pattern for preview-then-save
  (no draft table). Blocking errors for unknown / inactive roster
  references and duplicates. See `docs/imports.md` for the
  pair-vs-assignment-context distinction.
- **Default Instrument** auto-created per session (placeholder until
  Segment 8 ships real instruments).
- **`assignment_mode`** column on `sessions` records the strategy
  used; `Assignment.created_by_mode` records the same per row.
- **Delete all** assignments from the hub with explicit confirm.
  Reviewers and reviewees stay; `session.assignment_mode` clears
  back to `null`. Audit event `assignments.deleted_all`.

### Reviewer review surface

- **Identity matching**: an authenticated user is matched to
  `Reviewer` rows by case-insensitive email equality (`casefold()`
  both sides). Only `Reviewer` rows with `status == "active"` count.
- **Dashboard** at `/reviewer` lists the user's reviewer-sessions
  with per-session pill (`not started` / `in progress` /
  `submitted`) computed from the reviewer's `Response` rows.
- **Surface** at `/reviewer/sessions/{id}` renders an editable HTML
  table: one row per non-excluded assignment (`include = true`),
  one input per `InstrumentResponseField` on the Default Instrument
  (today: `rating` integer 1–5 required, `comments` long text
  optional). Pair-level context (`pair_context_1/2/3`) is shown
  alongside the reviewee; tags and `assignment_context_*` are
  hidden by default in this segment.
- **Save draft**: form post upserts `Response` rows. Empty value
  deletes the row, so the row's absence == empty answer. Never
  touches `submitted_at`.
- **Submit**: persists pending writes, then validates required
  fields. Missing-required-without-acknowledge re-renders the page
  at HTTP 400 with a warning card and an `acknowledge_missing`
  checkbox. Missing-required-with-acknowledge stamps `submitted_at`
  and writes audit. Editing a previously-submitted required field
  to empty deletes the row including its `submitted_at`, flipping
  the dashboard pill back to `in progress` next render.
- **Clear all**: confirm-checkbox-required action that deletes
  every `Response` row for this reviewer in this session. No
  partial undo; reviewers re-enter values from scratch afterward.
- **Cancel**: plain `<a>` link back to the surface; no DB write,
  no audit. Discards in-progress edits by re-fetching saved values.
- **Autosave is deferred** to a follow-on PR (vanilla JS layered
  over the same `/save` endpoint).
- **Per-Instrument open/close** (operator-controlled
  "stop accepting responses" gate, deadline-driven or manual)
  lands in Segment 9. Until then save / submit always work.

### Audit log

Every destructive operation writes an `audit_events` row with
`event_type`, `summary`, JSON `detail`, and a per-request `correlation_id`:

| event_type | When |
|---|---|
| `session.created` | new session |
| `session.updated` | edit form save (incl. `changes: {field: [old, new]}`) |
| `session.deleted` | session deletion (`session_id=None` in the row, original id in `detail`) |
| `reviewers.imported` | reviewer CSV save (incl. `cascaded_assignment_count`) |
| `reviewees.imported` | reviewee CSV save (incl. `cascaded_assignment_count`) |
| `reviewers.deleted_all` | delete-all from roster Manage view |
| `reviewees.deleted_all` | delete-all from roster Manage view |
| `assignments.generated` | FullMatrix or Manual save (incl. `mode`, `excluded_counts`) |
| `assignments.deleted_all` | delete-all from assignments hub |
| `responses.saved` | reviewer saves a draft (incl. `count`, `reviewer_id`) |
| `responses.submitted` | reviewer submits (incl. `count`, `missing_required_count`, `acknowledged_missing`) |
| `responses.cleared` | reviewer clears all their responses in a session |

`excluded_counts` is a generic map (`{"self_review": N,
"inactive_reviewer": M, ...}`) so RuleBased exclusions in Segment 12 can
plug in additional reasons without a schema change. Today's keys are
`self_review`, `inactive_reviewer`, `inactive_reviewee`.

---

## What's deliberately not yet there

| Capability | Lands in |
|---|---|
| Edit individual reviewer / reviewee / assignment rows (today: bulk operations only via CSV replace or delete-all) | Not yet planned; would slot before activation |
| Operator UI to flip `Reviewer.status` / `Reviewee.status` to inactive (filter is defensive today) | Not yet planned |
| Vanilla-JS autosave on top of the reviewer `/save` endpoint | Follow-on PR after Segment 8 |
| **Activation** (operator publishes the session, locks edits, opens to reviewers) | **Segment 9** |
| **Invitations & reminders** (email reviewers their links) | **Segment 9** |
| **Per-Instrument open/close** (deadline-driven or manual "stop accepting responses" gate) | **Segment 9** |
| **Instrument builder** (operator-editable response fields on the session's Instrument: add / edit / reorder / delete; field types beyond the seed pair) | **Segment 10** |
| **Export / audit retention** | **Segment 11** |
| **RuleBased assignment** | **Segment 12** |
| **Multi-instrument sessions** (more than one Instrument under a session) | **Segment 13** |
| **Production hardening** (Key Vault, VNet, soft-delete, full Postgres pytest matrix) | **Segment 14** |

---

## Architectural notes worth preserving

### FullMatrix is a (future) RuleBased preset

FullMatrix and Manual currently have parallel implementations, but the
storage model treats them uniformly: every assignment is a row in
`assignments` with `created_by_mode` as a string discriminator and
`Assignment.context` as JSON. Segment 12 RuleBased is expected to
introduce a generic generation framework; FullMatrix becomes the
simplest preset of that framework. The audit-detail shape
(`excluded_counts: {...}`) is already generic; Manual rows ship with
`excluded_counts: {}`. The only friction is one specific service
function name (`generate_full_matrix`) and one preview template.

### Replace-all everywhere

All destructive ops (CSV imports + assignment generation) follow the
same shape: explicit confirm checkbox when rows already exist; audit
event records old count, new count, and any cascaded downstream
deletions. No append/merge for now — defer until activation
constraints make it necessary.

### Single-instrument invariant

Every session has exactly one Instrument (`Default`) with seed
response fields, auto-created at session creation time. Every
assignment points at it. Multi-instrument operator UI lands in
Segment 13; until then the schema's per-instrument granularity is
real but unused. See `ARCHITECTURE.md` "Conceptual hierarchy."

### Pair-level vs assignment-level context

Manual CSV imports carry two distinct kinds of per-pair context
(`pair_context_*` and `assignment_context_*`), both stored on
`Assignment.context`. Pair-level is reviewer-facing informational
metadata; assignment-level is logic-engaging metadata that
RuleBased (Segment 12) will read. See `docs/imports.md` and
`ARCHITECTURE.md` "Pair-level vs assignment-level context."
