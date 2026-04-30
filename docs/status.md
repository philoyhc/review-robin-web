# Implementation status

**As of:** end of Segment 10B-1 (2026-04-30)

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
| 2026-04-29 | Segment 9.1 shipped (session activation lifecycle + per-instrument acceptance gates) |
| 2026-04-29 | Segment 9.2 shipped (per-reviewer invitations + dev outbox + token landing route) |
| 2026-04-29 | Segment 9.3 shipped (monitoring page + reminder send) |
| 2026-04-29 | Segment 9.4A shipped (page chrome + breadcrumbs + sessions list reshape + `/about`) |
| 2026-04-29 | Segment 9.4B shipped (session detail four-card restructure + inline validate-summary + Delete Data) |
| 2026-04-29 | Segment 9.4C shipped (Manage-page reshapes + instruments index + `/setupinvite` stub) |
| 2026-04-29 | Segment 9.5A shipped (`validated` lifecycle state + setup-mutation invalidation hooks) |
| 2026-04-30 | Segment 10A shipped (response-field builder + reviewer-surface loop-by-instrument refactor) |
| 2026-04-30 | Segment 10B-1 shipped (data-driven reviewer-surface render + display-field backfill) |

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
| 9.1 | Session activation lifecycle (draft↔ready), edit-lock, per-instrument open/close, response-window gates | 2026-04-29 |
| 9.2 | Invitation generation + dev email outbox + `/reviewer/invite/{token}` landing route | 2026-04-29 |
| 9.3 | Per-session monitoring page + per-row and bulk reminder send | 2026-04-29 |
| 9.4A | Global page chrome (app identity + user card + breadcrumb), `/about` stub, sessions list per-row Access/Delete + Create-new-session button | 2026-04-29 |
| 9.4B | Session detail four-card layout (Session / Session setup / Run Session / Danger zone), inline validate-summary card via `?validated=1`, `POST /delete-data` with `responses.deleted_all` audit event | 2026-04-29 |
| 9.4C | Reviewers / reviewees / assignments Manage pages with anchored Upload-CSV cards and disabled Edit buttons; Assign by Rules placeholder card; `/operator/sessions/{id}/instruments` index page; `/operator/sessions/{id}/setupinvite` stub; setup-table Manage buttons for Instruments and Set up invites enabled | 2026-04-29 |
| 9.5A | `validated` stored state in `SessionStatus` (between `draft` and `ready`); `GET ?validated=1` flips draft→validated when no errors; activation now requires `is_validated`; setup-mutating routes (reviewer/reviewee/assignment import + delete-all + assignment generate + session edit) flip validated→draft via dedicated `session.validated` / `session.invalidated` audit events; instrument open/close/visibility and `/delete-data` deliberately do not invalidate | 2026-04-29 |
| 10A | Consolidated `/operator/sessions/{id}/instruments` page: per-instrument card with friendly description, acceptance + visibility toggles, response-fields table (add / edit / delete / reorder, per-field help text + visibility), session-wide Instruments Settings card with bulk Open all / Close all toggles. Migration adds `help_text` (Text, NULL) and `help_text_visible` (Bool, default true) on `instrument_response_fields`. Reviewer surface refactors to loop-by-instrument with section heading from `Instrument.description` (fallback to system handle) and a per-field help block above each table. Empty-instrument validation now blocks activation. Description / field mutations invalidate `validated → draft` via `_invalidate_if_validated`; bulk accepting + per-instrument open/close/visibility deliberately do not invalidate. Body width bumped from 900px to 1400px globally with a `.table-scroll` overflow utility. | 2026-04-30 |
| 10B-1 | Backfill migration (`c2143bd329c7`) seeds three `InstrumentDisplayField` rows (`source_type='pair_context'`, `source_field='1'|'2'|'3'`, `label=''`, `order=0..2`, `visible=true`) on every existing instrument; destructive within that filter (operator-typed labels on those slots are not preserved across upgrade); operator-added `reviewee` rows left intact. `ensure_default_instrument` seeds the same three rows on new sessions. Reviewer surface renders pair-context values as separate columns sourced from the display-field rows (no longer inline in the identity cell); reviewee identity (name + email) is the always-first column, mandatory and non-toggleable. New service helpers `display_field_label(field)` and `display_field_value(field, assignment)` cover the seven D6 sources (`reviewee.tag_1/2/3`, `reviewee.profile_link`, `pair_context.1/2/3`); empty/NULL labels fall back to inferred strings. `profile_link` cells render as plain `<a>`. No operator UI yet (picker + bulk form land in 10B-2; preview route in 10B-3). No new audit events. | 2026-04-30 |

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
- **Manage-page reshape (Segment 9.4C)**: the reviewers, reviewees,
  and assignments Manage pages now render an always-present
  `<section id="upload-csv">` card with the existing import form;
  the Upload CSV button is `<a href="#upload-csv">` (no JS, no
  `<details>`, stateful via the URL fragment). Validation errors on
  POST re-render the Manage page itself — there is no longer a
  standalone `…/import` GET. The assignments page also carries an
  anchored `<section id="rules">` "Assign by Rules" placeholder
  (Rule editor — Segment 12) with a Cancel anchor that drops the
  fragment. **Edit Reviewers / Reviewees / Assignments** buttons
  render as disabled anchors (`<a class="btn disabled"
  aria-disabled="true">`) per the 9.4B disabled-affordance
  convention. New `/operator/sessions/{id}/instruments` index lists
  one card per instrument with the `accepting_responses` pill,
  Manage link to the per-instrument page, and disabled
  Add / Delete instrument buttons (Multi-instrument — Segment 13).
  New `/operator/sessions/{id}/setupinvite` is a stub (Email
  template editor — Segment 15). Session-detail Setup table Manage
  buttons for Instruments and Set up invites are now real links.
- **Page chrome (Segment 9.4A)** in `app/web/templates/base.html`:
  top-left "Review Robin Web App (version {num})" link to `/about`,
  breadcrumb trail rendered just below, top-right user card with
  "Signed in as ..." + Sign out. Per-page back-links are removed —
  the breadcrumb replaces them. Operator-page crumbs root at
  `Sessions → /operator/sessions`; reviewer-page crumbs root at
  `Reviewer → /reviewer`. Crumb factories live in
  `app/web/breadcrumbs.py`; the partial is
  `app/web/templates/_partials/breadcrumb.html`. Version string
  comes from `app.config.app_version` (`"dev"` for now;
  pipeline-driven version bumping is a Segment 14 concern).
- Card-based layout, monospace tabular code spans, severity pills
  (`error` / `warning` / `info`) for validation issues. All inline
  `<style>` in `base.html`. CSS framework / extraction is a Segment
  14 concern.

### Operator-facing app

| URL | What it does |
|---|---|
| `GET /` | service metadata |
| `GET /health` | unauthenticated `{"status": "ok"}` |
| `GET /about` | unauthenticated stub page; chrome's app-identity link target |
| `GET /me`, `/me/debug` | identity introspection |
| `GET /operator/sessions` | list of sessions where user is operator |
| `GET /operator/sessions/new` | create form |
| `POST /operator/sessions` | create + insert `SessionOperator` + audit + 303 |
| `GET /operator/sessions/{id}` | session detail in four cards (Session / Session setup / Run Session / Danger zone). `?validated=1` re-runs setup validation and renders an inline summary card with the Activate form when there are no blocking errors. |
| `GET /operator/sessions/{id}/edit` | edit form |
| `POST /operator/sessions/{id}/edit` | apply changes + audit |
| `POST /operator/sessions/{id}/delete` | delete session and all dependents (confirm; locked while `ready`) |
| `POST /operator/sessions/{id}/delete-data` | wipe every reviewer Response for the session; preserves setup; allowed in any status; emits `responses.deleted_all` audit event |
| `GET /operator/sessions/{id}/validate` | read-only setup validation deep-dive (Activate moved to the inline summary card on session detail) |
| `GET /operator/sessions/{id}/reviewers` | roster Manage view with anchored `#upload-csv` import card and disabled Edit Reviewers button |
| `POST /operator/sessions/{id}/reviewers/import` | parse + replace + audit; on validation errors re-renders the Manage page |
| `POST /operator/sessions/{id}/reviewers/delete-all` | delete every reviewer + cascade |
| `GET /operator/sessions/{id}/reviewees` | roster Manage view with anchored `#upload-csv` import card and disabled Edit Reviewees button |
| `POST /operator/sessions/{id}/reviewees/import` | parse + replace + audit; on validation errors re-renders the Manage page |
| `POST /operator/sessions/{id}/reviewees/delete-all` | delete every reviewee + cascade |
| `GET /operator/sessions/{id}/assignments` | hub (counts, mode pill, current pairs) with anchored `#upload-csv` manual-import card, anchored `#rules` Assign-by-Rules placeholder, and disabled Edit Assignments button |
| `POST /operator/sessions/{id}/assignments/full-matrix` | preview / save |
| `POST /operator/sessions/{id}/assignments/manual/import` | preview / save |
| `POST /operator/sessions/{id}/assignments/delete-all` | delete every assignment, clear mode |
| `POST /operator/sessions/{id}/activate` | flip session draft→ready (warn-and-acknowledge for non-blocking findings) |
| `POST /operator/sessions/{id}/revert` | flip session ready→draft (confirm checkbox; closes all instruments) |
| `GET /operator/sessions/{id}/instruments` | consolidated instruments page — session-wide Settings card (bulk Open all / Close all) + one card per instrument with friendly description, acceptance + visibility toggles, response-fields table (add / edit / delete / reorder, per-field help text + visibility), display-fields table (10B-1 seeded; picker UI lands in 10B-2). Add / Delete instrument disabled until Segment 13 |
| `GET /operator/sessions/{id}/setupinvite` | stub page — email-template editor lands in Segment 15 |
| `GET /operator/sessions/{id}/instruments/{instrument_id}` | legacy redirect — 303 to `/instruments` (back-compat for bookmarks; 10A) |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/edit` | edit friendly description (`Instrument.description`); audit `instrument.described`; invalidates `validated → draft` |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/fields` | add a response field; auto-derives `field_key` from label when blank; audit `instrument.field_added` |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/fields/{field_id}/edit` | edit a response field (label / required / validation / help text + visibility); audit `instrument.field_updated`; banner-warns when optional → required leaves existing reviewer rows incomplete |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/fields/{field_id}/delete` | delete a response field; cascade-confirm flow when responses exist; audit `instrument.field_deleted` |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/fields/{field_id}/move` | up / down reorder; repacks `0..N-1`; audit `instrument.fields_reordered` |
| `POST /operator/sessions/{id}/instruments/accepting/all-on` | bulk-open every instrument under the session; audit `instruments.bulk_accepting_responses` (ready-only, pre-deadline; deliberately does NOT invalidate `validated`) |
| `POST /operator/sessions/{id}/instruments/accepting/all-off` | bulk-close every instrument |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/open` | start accepting responses (requires session ready, pre-deadline) |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/close` | stop accepting responses (manual) |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/visibility` | toggle `responses_visible_when_closed` |
| `GET /operator/sessions/{id}/invitations` | per-reviewer invitation table (status / sent / opened) |
| `POST /operator/sessions/{id}/invitations/generate` | bulk-create invitations for assigned active reviewers (idempotent; ready-only) |
| `POST /operator/sessions/{id}/invitations/send-all` | write outbox row per pending invitation (ready-only) |
| `POST /operator/sessions/{id}/invitations/{iid}/send` | send a single invitation (rotates token; ready-only) |
| `POST /operator/sessions/{id}/invitations/{iid}/regenerate` | rotate token + reset to pending (ready-only) |
| `GET /operator/sessions/{id}/outbox` | dev-mode email outbox view for the session |
| `GET /operator/sessions/{id}/monitoring` | per-reviewer progress + reminder actions (ready-only for actions) |
| `POST /operator/sessions/{id}/invitations/{iid}/remind` | send a single reminder reusing the prior invitation URL (ready-only) |
| `POST /operator/sessions/{id}/monitoring/remind-incomplete` | bulk reminders to every incomplete reviewer (ready-only) |

### Reviewer-facing app

| URL | What it does |
|---|---|
| `GET /reviewer` | dashboard: sessions where user has an active `Reviewer` row; per-session pill (`not started` / `in progress` / `submitted`) |
| `GET /reviewer/invite/{token}` | invitation token landing — Easy Auth required, email-match check, stamps `opened_at`, 303 to surface |
| `GET /reviewer/sessions/{id}` | review surface: editable table of assigned reviewees and Default Instrument fields; ?saved=ok / ?submitted=ok flash banners |
| `POST /reviewer/sessions/{id}/save` | upsert response cells (empty value deletes the row); 303 → surface with `?saved=ok` |
| `POST /reviewer/sessions/{id}/submit` | persist + validate required; 400 + warn-and-override on missing without acknowledge; else stamps `submitted_at` and 303 → surface with `?submitted=ok` |
| `POST /reviewer/sessions/{id}/clear` | delete every response for this reviewer in this session (confirm checkbox required); 303 → surface |

The Cancel link on the surface is just `<a>` back to `GET /reviewer/sessions/{id}` — no server-side state change.

### Sessions

- Create with name, code (unique per operator), description, deadline.
- Session creation **also synchronously creates the Default
  Instrument** with two seed response fields (`rating` integer 1–5
  required; `comments` long text optional) and three seed display
  fields (`pair_context_1/2/3`, `visible=true`, `label=''`). Operator
  edits both kinds via the consolidated `/instruments` page (10A
  added the response-field builder + friendly description; 10B-1
  added the data-driven display-field render; 10B-2 will add the
  display-field picker UI). See `ARCHITECTURE.md` "Conceptual
  hierarchy."
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
- **Browseable Manage views** showing the saved rows in a table,
  with an anchored `Upload CSV` card on the same page (no separate
  `…/import` GET) and a disabled `Edit Reviewers` / `Edit Reviewees`
  button reserved for the future inline-edit pattern.
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
  table per instrument (today: N=1, the Default Instrument) with a
  section heading from `Instrument.description` (fallback to the
  system handle) and a per-field help block above the table for
  fields whose `help_text_visible` is true. Each table row is one
  non-excluded assignment (`include = true`); columns are reviewee
  identity (name + email_or_identifier, always-first, mandatory)
  followed by the instrument's visible `InstrumentDisplayField`
  rows (10B-1 — sourced from `pair_context_1/2/3` today; 10B-2 will
  let the operator add `reviewee.tag_1/2/3` / `reviewee.profile_link`
  via a per-instrument picker), then the response-field inputs in
  stored order, then a row-level submitted-status indicator. Empty
  / NULL display-field labels fall back to inferred strings from
  the D6 helper. `profile_link` cells render as plain `<a href>`.
  `assignment_context_*` is deliberately excluded from the surface
  per the pair-vs-assignment-context distinction.
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
- **Lifecycle gating (Segment 9.1)**: reviewer save / submit / clear
  return **HTTP 403** unless the session is `ready`, the assigned
  instrument is `accepting_responses`, and `now() < session.deadline`.
  When the gate is closed, the surface renders read-only; saved values
  are hidden unless the operator turns on
  `responses_visible_when_closed` on the per-instrument sub-page.
  Deadline closure is observed lazily on every reviewer GET/POST and
  on the per-instrument operator page; the first observer flips
  `accepting_responses=false`, stamps `deadline_closed_at`, and emits
  one `instrument.closed reason=deadline` audit event.

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
| `responses.deleted_all` | operator-driven Delete Data on session detail (`detail.deleted_count`); allowed in any session status, including `ready` |
| `session.activated` | operator flips session draft→ready (`detail.override_warnings`) |
| `session.reverted_to_draft` | operator flips session ready→draft (`detail.closed_instrument_ids`, `response_count_at_revert`) |
| `instrument.opened` | operator manually re-opens a closed instrument |
| `instrument.closed` | manual or lazy-deadline close (`detail.reason ∈ {manual, deadline}`) |
| `instrument.described` | operator edits the friendly description (`detail.description: [old, new]`) |
| `instrument.field_added` | operator adds a response field (`detail.field_key`, `label`, `response_type`, `required`, `validation`, `help_text`, `help_text_visible`) |
| `instrument.field_updated` | operator edits a response field (`detail.changes: {key: [old, new]}` for each changed key only) |
| `instrument.field_deleted` | operator deletes a response field (`detail.snapshot`, `cascaded_response_count`) |
| `instrument.fields_reordered` | up/down move (`detail.old_order`, `detail.new_order` as `field_key` lists) |
| `instruments.bulk_accepting_responses` | bulk Open all / Close all (`detail.target`, `detail.changed_instrument_ids`); not duplicated as per-instrument open / close events |
| `invitations.generated` | bulk-create invitations on a ready session (`detail.count`, `detail.invitation_ids`, `detail.reviewer_ids`) |
| `invitation.sent` | outbox row written + invitation flipped to `sent` |
| `invitation.opened` | first valid token follow with matching email |
| `invitation.regenerated` | per-row token rotation + reset to `pending` |
| `reminders.sent` | batch reminder send (`detail.count`, `detail.invitation_ids`, `detail.reviewer_ids`, `detail.fell_back_count`) |

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
| **Real SMTP email backend** (production sending, not the dev outbox) | **Segment 15** |
| **Display-fields picker** (operator UI to add / remove / order / toggle visibility / label-override the seven D6 sources on a per-instrument card; row-level + bulk forms; four new audit events) | **Segment 10B-2** |
| **Operator preview route** (`GET /operator/sessions/{id}/preview` — read-only render of the reviewer surface with synthetic rows, disabled inputs, banner; works in any session status) | **Segment 10B-3** |
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

Every session has exactly one Instrument (system handle `Default`,
operator-editable `description`) with seed response fields and seed
`pair_context_1/2/3` display fields, auto-created at session
creation time via `ensure_default_instrument`. Every assignment
points at it. The reviewer surface and the operator's `/instruments`
page already loop over instruments (today: N=1) so multi-instrument
support (Segment 13) is purely an enable-the-Add/Delete-buttons
change. See `ARCHITECTURE.md` "Conceptual hierarchy."

### Pair-level vs assignment-level context

Manual CSV imports carry two distinct kinds of per-pair context
(`pair_context_*` and `assignment_context_*`), both stored on
`Assignment.context`. Pair-level is reviewer-facing informational
metadata; assignment-level is logic-engaging metadata that
RuleBased (Segment 12) will read. See `docs/imports.md` and
`ARCHITECTURE.md` "Pair-level vs assignment-level context."
