# Segment 16C — Richer audit views

> **Archived 2026-05-11.** PRs 1-3 (the MVP) shipped 2026-05-11
> as PRs **#860 / #861 / #863**. PRs 4 + 5 + 6 (all post-MVP)
> carved out into `guide/deferred_until_pilot_feedback.md` —
> same scope, awaiting a real operator ask before they justify
> the build cost.
>
> Carved out of the original Segment 16 (2026-05-11). The
> Sys Admin page + sys-admin role gate live in **16A**
> (`guide/archive/segment_16A_sys_admin_page.md` — shipped);
> user-role management + role delegation live in **16B**
> (`guide/archive/segment_16B_role_delegation.md` — shipped).

## What shipped (2026-05-11)

- **PR 1 (#860)** — per-session audit log child page at
  `/operator/sys-admin/sessions/{id}/audit-log`. Reachable
  from the Sessions Diagnostics row's Audit log link
  (migrated from direct-CSV). New
  `audit.list_events_for_session` reader + view adapter +
  template with severity pills + keyset pagination on
  `id DESC`. CSV route gate tightened to `require_sys_admin`.
- **PR 2 (#861)** — filter strip + filtered CSV download.
  `AuditFilters` dataclass, shared `_apply_filters` helper,
  URL-param state (event_type / severity / actor / from / to),
  filter-aware Download CSV button, `session.audit_log_extracted`
  audit event grows a `context` slot recording the filter set
  on filtered extracts. Bonus follow-on commit constrained
  the table layout (`table-layout: fixed`, per-column widths,
  `overflow-wrap: anywhere`) so the JSON detail column wraps
  rather than horizontally bloating the table.
- **PR 3 (#863)** — per-row `<details>` expander +
  per-shape pretty-printer. New `format_audit_detail` view
  adapter mapping each canonical envelope into structured
  sections (changes / snapshot / counts / set_changes /
  reason / refs / context / fallback). Raw JSON sits in a
  nested `<details>` for inspection.

## What didn't ship (deferred)

- **PRs 4 + 5 + 6** all moved to
  `guide/deferred_until_pilot_feedback.md` — entity drill-in
  (deep-link `refs.*_id` to the relevant operator page) +
  cross-session workspace audit search (new top-nav tab,
  no-session viewer) + Session Home Recent activity card
  (per-event prose summariser). All three are well-scoped
  post-MVP slices whose value depends on operator behaviour
  we haven't seen yet.

**Sizing (historical):** 3 MVP PRs (shipped) + 3 post-MVP
(all deferred).
**Depends on:** **16A** (shipped) — the Sys Admin chrome,
the workspace Sessions Diagnostics surface, and the
`require_sys_admin` dependency in `app/web/deps.py`.

## Goal

Move the audit log from "CSV download + canonical envelope
schema in `spec/architecture.md`" to an **in-app viewer** with
filters, search, and entity drill-in. Functional spec §22
**"Richer audit views"** is the canonical scope ask —
`guide/archive/codebase_assessment_11may.md` marks it ⚠️ "canonical
schema + CSV export shipped; operator-facing surface relocates
to Segment 16 Sys Admin".

Today's audit surface:

- ✅ 62 distinct event types registered under the canonical
  envelope (Segment 11K).
- ✅ Strict-mode test gate catches any drift.
- ✅ CSV download route shipped (12B PR 1) at
  `GET /operator/sessions/{id}/export/audit_log.csv` — 8
  columns, JSON detail envelope in the trailing column.
- ✅ Sys Admin chrome + Sessions Diagnostics workspace table
  shipped (16A PRs 1-6). Each row currently exposes
  three actions: **Details** (→ `/edit`), **Outbox** (→
  child page), **Audit log** (→ direct CSV download).
- ◻ **No in-app viewer.** Operators / sys-admins can
  download the CSV and spreadsheet-search it, but the app
  itself doesn't surface the audit log on any page.

16C lives behind the Sys Admin gate from 16A — audit data is
sensitive (correlation IDs, actor emails, lifecycle history)
and follows the same "diagnostics doorway" placement that
moved the CSV download out of Extract Data into Sys Admin in
12B PR 2.

## PR ladder

MVP shipped in PRs 1-3 (per-session diagnostic-grade table
+ filters + envelope pretty-printer). PRs 4-6 are post-MVP
polish + workspace-level breadth.

### PR 1 — Per-session audit log child page (~350 LOC)

**Why first.** The minimum-viable in-app surface. Mirrors
the Outbox child-page pattern (16A PR #847) — Sessions
Diagnostics row's existing "Audit log" link migrates from
"direct CSV download" to "open the viewer page; download
button lives inside."

**Surface migration.**

- Sessions Diagnostics row's `Audit log` link
  (`sys_admin_sessions.html:59`) flips from
  `/operator/sessions/{id}/export/audit_log.csv` to the new
  child page `/operator/sys-admin/sessions/{id}/audit-log`.
- **CSV download lives only inside the child page** as a
  `Download CSV` button in the page header / action row.
  One entrypoint per Diagnostics row, deeper actions
  inside — same convention as Outbox.
- CSV route (`GET /operator/sessions/{id}/export/audit_log.csv`)
  stays at its current URL so existing bookmarks /
  programmatic consumers don't break. Its gate tightens
  from `require_sys_admin_or_session_operator` to
  `require_sys_admin` since session operators no longer
  have any UI affordance pointing at it (the operator-
  facing surface retired with 12B PR 2 → 16A PR 4).
  Bookmarked URLs that relied on the relaxed gate will
  now 403; reachable on a fresh request via the Diagnostics
  → child-page → Download CSV path.

**Ships.**

- New route
  `GET /operator/sys-admin/sessions/{session_id}/audit-log`
  in `app/web/routes_operator/_sys_admin.py` (the same
  slice that owns the Outbox child page). Gated on
  `require_sys_admin`.
- Read service `audit.list_events_for_session(db, session,
  *, cursor=None, limit=50)` returning the 8-column
  projection the CSV exporter already shapes
  (`EventType` / `Severity` / `Summary` / `ActorEmail` /
  `CorrelationId` / `CreatedAt` / `DetailJson`). Reuses the
  existing LEFT-JOIN-`users` plumbing from
  `serialize_audit_events`.
- View adapter `views.build_audit_log_rows(events) ->
  AuditLogRowsContext`. Dataclass shape mirrors the CSV
  serialisation; the JSON detail column stays raw in this
  PR (PR 3 pretty-prints).
- Keyset pagination on `id DESC` (newer first). Default
  page size 50. `?cursor=<id>` URL param.
- Template `operator/sys_admin_session_audit_log.html`
  matching the Outbox child-page chrome (`sys_admin_top_nav`
  partial + breadcrumb + section heading). Action row at
  the top: `Download CSV` (Primary Outline) +
  `← Back to Sessions Diagnostics` (chrome-link).
- Severity cell uses the same chip styling as the Validate
  page (`spec/visual_style_rrw.md` "severity strip").
- **No filters yet** — PR 2.

**Tests.**

- Diagnostics row's `Audit log` link points at the new
  child page, not the CSV.
- 403 for non-admin on the child page.
- 403 for non-admin on the CSV route (was 200 for session
  operators pre-PR; the relaxed-gate test in
  `test_outbox_sys_admin_relax.py` needs updating /
  retiring).
- Renders the 8 columns + keyset pagination for a session
  with seeded events.
- Pagination round-trip: page 1's last-cursor links to
  page 2; page 2's first row is older than page 1's last.
- `Download CSV` button on the child page hits the same
  route as before, emits the same
  `session.audit_log_extracted` audit event.

### PR 2 — Filter strip + filtered CSV download (~250 LOC)

**Ships.**

- Filter form on the audit-log page — event type (multiselect
  dropdown of registered types from `EVENT_SCHEMAS`),
  severity (info / warning / error checkboxes), actor email
  (typeahead `<input list>` + `<datalist>`), date range
  (from + to date inputs).
- URL params persist filter state
  (`?event_type=session.activated&severity=info,warning&actor=…&from=2026-05-01&to=2026-05-11`)
  so bookmarks + back/forward stay deterministic.
- `audit.list_events_for_session` grows an `AuditFilters`
  parameter; filters compose with the keyset cursor.
- `Download CSV` button on the child page becomes filter-
  aware: it points at the existing CSV route with the same
  query string carried over, so the downloaded CSV honours
  the filter strip. `serialize_audit_events` grows the same
  `AuditFilters` parameter (or accepts a pre-filtered query
  builder — decide at scoping).
- `session.audit_log_extracted` detail-envelope grows a
  `context` slot recording what the operator queried for.
- Filter strip lives in a half-width left card; the audit
  table sits below it (or right of it on wide screens
  via `.bottom-grid`). Lock the layout at scoping time.

**Tests.**

- Each filter narrows the result set in isolation;
  combined filters AND together.
- URL-param round-trip: query string round-trips into
  rendered filter state and back.
- Filtered CSV download honours the same filter set;
  audit-event detail carries the filter context.

### PR 3 — Detail-JSON pretty-printer + per-row expander (~300 LOC)

**Ships.**

- Per-row "Show detail" expander revealing the canonical
  envelope contents inline, rendered per payload-shape
  rather than as raw JSON:
  - `changes` envelope → a small `<dl>` of column /
    `before → after` rows.
  - `snapshot` envelope → a `<dl>` of key / value pairs.
  - `counts` envelope → a stat row ("47 rows added · 3
    rejected").
  - `set_changes` envelope → `added` / `removed` pills.
- Envelope-aware view adapter
  `views.format_audit_detail(event_type, detail) ->
  AuditDetailRender`. Per-envelope renderer functions
  registered against a small dispatch dict; default
  fallback is a sorted-keys `<dl>`.
- Progressive enhancement: the expander is a `<details>`
  element so it works without JS; inline JS adds smooth
  collapse.

**Tests.**

- Each of the four canonical envelope shapes renders via
  its expected per-shape branch (one fixture event per
  shape).
- Unknown / non-canonical detail (legacy rows from
  pre-11K era) falls through to the generic renderer
  without crashing.

### PR 4 (post-MVP) — Entity drill-in (~200 LOC)

> **Carved out 2026-05-11 to** `guide/deferred_until_pilot_feedback.md`.
> Section retained here for historical context.

**Ships.**

- The envelope's `refs` slot already carries cross-entity
  int PKs (e.g. `refs.reviewer_id`, `refs.instrument_id`,
  `refs.target_user_id` from 16B PR 2). Per-row anchors
  render alongside the detail rendering — "View reviewer"
  / "View instrument" / "View RuleSet" / "View user"
  deep-linking into the relevant operator-page surface.
- Deleted entities render as a disabled `(deleted)` suffix
  rather than a broken link. The viewer checks for row
  existence via cheap `EXISTS` queries batched per
  page-load.
- Per-entity URL builder
  `views.audit_ref_url(ref_key, ref_id, session) -> str`
  centralises the routing so anchors stay consistent with
  the operator chrome.

**Defer until PRs 1-3 ship and operator feedback confirms
the drill-in is worth the additional surface.**

### PR 5 (post-MVP) — Cross-session audit search (~250 LOC)

> **Carved out 2026-05-11 to** `guide/deferred_until_pilot_feedback.md`.
> Section retained here for historical context.

**Ships.**

- New workspace-level route `/operator/sys-admin/audit-log`
  (no session id). Same chrome, same table, same filter
  strip — but scoped to every session the sys-admin can
  see, plus workspace-scoped events
  (`workspace.operator_admitted` / `.operator_revoked` /
  `sys_admin.role_promoted` / `.role_demoted` from 16A
  PR 6) which have no `session_id`.
- Sys Admin top nav grows a third tab ("Audit log")
  alongside Sessions Diagnostics + Accounts Management.
- Filter strip gains a session-code dropdown / typeahead.
- Default date range "last 7 days" to keep the query
  bounded; operators can widen explicitly.
- Performance guard: query times measured on a fixture
  with N=10000 events per session × 50 sessions; if it
  bites, add an `(session_id, created_at)` composite index.

**Defer until either PR 4 ships or operator feedback
confirms cross-session search is a real need.**

### PR 6 (post-MVP) — Timeline / activity-stream on Session Home (~250 LOC)

> **Carved out 2026-05-11 to** `guide/deferred_until_pilot_feedback.md`.
> Section retained here for historical context.

**Ships.**

- New "Recent activity" card on Session Home rendering
  the most recent N (default 10) audit events for the
  session, summarised as one-line prose
  (e.g. `"Alice activated the session"` /
  `"Bob uploaded 47 reviewers"`).
- Per-event summariser `views.summarise_audit_event(event)
  -> str` mapping event_type + envelope → human-readable
  prose. Backed by a per-event-type dispatch dict;
  unknown / new event_types fall through to a generic
  `"<event_type> by <actor>"` formatter.
- Operator-visible — **not** gated to sys-admin. The
  timeline summarises operator-visible state changes
  (activation, deadline shifts, roster uploads) that
  every operator on the session should see.
- Deep-link from each summary line to the corresponding
  row in the PR 1 viewer (sys-admin-gated; non-sys-admin
  operators see the prose but the deep-link is absent or
  disabled).

**Defer until PRs 1-3 ship + operator feedback confirms
the prose summariser is worth the maintenance burden.**

## Hard dependencies

- **16A** (shipped) — Sys Admin chrome, the workspace
  Sessions Diagnostics surface, `require_sys_admin`
  dependency.
- **No** dependency for PR 6 (it lives on Session Home,
  operator-visible).

## Out of scope

- **Retention / purge tooling.** Out-of-band audit retention
  policy + automated purge of audit rows older than N days
  was scoped under Segment 12B but never landed there;
  unclaimed today. `guide/archive/codebase_assessment_11may.md`
  Weakness #2 flags this as a likely Segment 14A / 16
  ride-along, but the scope hasn't been committed to either
  segment. Revisit during scoping.
- **Audit ingestion from outside the app** — institutional
  SIEM integration, syslog forwarding, etc. Lives in 14A's
  out-of-scope list and stays there.
- **Modifying audit rows** — audit events are append-only.
  No edit / delete affordances.

## Doc impact

When PRs ship:

- `docs/status.md` timeline entry per PR.
- `guide/todo_master.md` updated.
- `spec/architecture.md` "Audit-event detail schema" picks up
  a "Rendering" subsection covering PR 3's pretty-printer.
- `spec/sessions_overview.md` or a new
  `spec/sys_admin_page.md` — Sessions Diagnostics row's
  per-row action set (Details / Outbox / Audit log) gains
  a note that Audit log opens the child viewer (post-PR 1).

## Working notes

- _(placeholder for decisions during PR scoping)_
- **Surface placement.** Per-session viewer reachable from
  the Sessions Diagnostics row's existing `Audit log`
  link, which migrates from direct-CSV to the new child
  page. CSV download lives only inside the child page
  (decided 2026-05-11, matches Outbox precedent).
- **CSV route gate.** Tightens from
  `require_sys_admin_or_session_operator` to
  `require_sys_admin` once the operator-facing entry
  point retires. Bookmarked URLs that relied on the
  relaxed gate will 403.
- Per-session vs workspace-level: ship PR 1 first; revisit
  PR 5 after operator feedback.
- Pagination: keyset on `id DESC` is the obvious call;
  confirm during scoping.
- Detail-JSON renderer: per-payload-shape pretty-printing vs
  a generic key/value dump. Lean per-shape — the canonical
  envelope's slots have semantic meaning that's lost in a
  flat dump.
- Severity colours: reuse the `severity` chip strip styling
  from the Validate page (`spec/validate_page.md`) for
  consistency.

