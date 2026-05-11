# Segment 16C — Richer audit views

> **Carved out of the original Segment 16 (2026-05-11).** The
> Sys Admin page + sys-admin role gate live in **16A**
> (`guide/archive/segment_16A_sys_admin_page.md` — shipped);
> user-role management + role delegation live in **16B**
> (`guide/archive/segment_16B_role_delegation.md` — shipped).

**Status:** Planning — stub created 2026-05-11, sized into
a six-PR ladder 2026-05-11 (PRs 1-3 MVP; PRs 4-6 post-MVP).
**Sizing:** 3 MVP PRs + 3 post-MVP PRs.
**Depends on:** **16A PR 1** (the sys-admin gate + chrome
scaffold). Otherwise independent — can stack with 16A
PRs 2-4 in parallel.

## Goal

Move the audit log from "CSV download + canonical envelope
schema in `spec/architecture.md`" to an **in-app viewer** with
filters, search, and entity drill-in. Functional spec §22
**"Richer audit views"** is the canonical scope ask —
`guide/codebase_assessment_11may.md` marks it ⚠️ "canonical
schema + CSV export shipped; operator-facing surface relocates
to Segment 16 Sys Admin".

Today's audit surface:

- ✅ 62 distinct event types registered under the canonical
  envelope (Segment 11K).
- ✅ Strict-mode test gate catches any drift.
- ✅ CSV download route shipped (12B PR 1) — 8 columns, JSON
  detail envelope in the trailing column.
- ◻ **No in-app viewer.** Operators can download the CSV and
  spreadsheet-search it, but the app itself doesn't surface
  the audit log on any page.

16C lives behind the Sys Admin gate from 16A — audit data is
sensitive (correlation IDs, actor emails, lifecycle history)
and follows the same "diagnostics doorway" placement that
moved the CSV download out of Extract Data into Sys Admin in
12B PR 2.

## PR ladder

MVP shipped in PRs 1-3 (per-session diagnostic-grade table
+ filters + envelope pretty-printer). PRs 4-6 are post-MVP
polish + workspace-level breadth.

### PR 1 — Per-session audit log table (~300 LOC)

**Why first.** The minimum-viable surface. Once this is up,
operators (well, sys-admins) can answer "what happened on
this session, in order?" without leaving the app.

**Ships.**

- New route `/operator/sessions/{id}/sys-admin/audit-log`
  behind `require_sys_admin`. Slotted into the new
  `routes_operator/_sys_admin.py` slice (16A PR 1).
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
- Template `operator/session_sys_admin_audit_log.html`.
  Table markup matches the v2 sweep conventions; severity
  cell uses the same chip styling as the Validate page
  (`spec/visual_style_rrw.md` "severity strip").
- **No filters yet.** "Filtered CSV" download not in this
  PR either — operators who need a CSV today already have
  the Extract Data path (well, the Sys Admin tile post-16A
  PR 3).

**Tests.**

- 403 for non-admin.
- Renders the 8 columns + keyset pagination for a session
  with seeded events.
- Pagination round-trip: page 1's last-cursor links to
  page 2; page 2's first row is older than page 1's last.

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
- New "Download filtered CSV" button reuses the existing
  `serialize_audit_events` + emits the same
  `session.audit_log_extracted` audit event. The filter
  state rides along as detail-envelope `context` slots so
  the audit row records what the operator queried for.
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

**Ships.**

- The envelope's `refs` slot already carries cross-entity
  int PKs (e.g. `refs.reviewer_id`, `refs.instrument_id`).
  Per-row anchors render alongside the detail rendering —
  "View reviewer" / "View instrument" / "View RuleSet"
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

**Ships.**

- New workspace-level route `/operator/sys-admin/audit-log`
  (no session id). Same chrome, same table, same filter
  strip — but scoped to every session the sys-admin can
  see.
- Filter strip gains a session-code dropdown / typeahead.
- Default date range "last 7 days" to keep the query
  bounded; operators can widen explicitly.
- Performance guard: query times measured on a fixture
  with N=10000 events per session × 50 sessions; if it
  bites, add an `(session_id, created_at)` composite index.

**Defer until either PR 4 ships or operator feedback
confirms cross-session search is a real need.**

### PR 6 (post-MVP) — Timeline / activity-stream on Session Home (~250 LOC)

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

- **16A Part 1** (the Sys Admin chrome) for Parts 1 / 2 / 3.
- **No** dependency for Part 4 (it lives on Session Home,
  operator-visible).

## Out of scope

- **Retention / purge tooling.** Out-of-band audit retention
  policy + automated purge of audit rows older than N days
  was scoped under Segment 12B but never landed there;
  unclaimed today. `guide/codebase_assessment_11may.md`
  Weakness #2 flags this as a likely Segment 14A / 16
  ride-along, but the scope hasn't been committed to either
  segment. Revisit during scoping.
- **Audit ingestion from outside the app** — institutional
  SIEM integration, syslog forwarding, etc. Lives in 14A's
  out-of-scope list and stays there.
- **Modifying audit rows** — audit events are append-only.
  No edit / delete affordances.

## Doc impact

When parts ship:

- `docs/status.md` timeline entry per Part.
- `guide/todo_master.md` updated.
- `spec/architecture.md` "Audit-event detail schema" picks up
  a "Rendering" subsection covering Part 1's pretty-printer.
- New `spec/sys_admin_page.md` (or similar) section absorbing
  the Sys Admin chrome's audit-log tab contract.

## Working notes

- _(placeholder for decisions during PR scoping)_
- Per-session vs workspace-level: ship Part 1 first; revisit
  Part 2 after operator feedback.
- Pagination: keyset on `id DESC` is the obvious call;
  confirm during scoping.
- Detail-JSON renderer: per-payload-shape pretty-printing vs
  a generic key/value dump. Lean per-shape — the canonical
  envelope's slots have semantic meaning that's lost in a
  flat dump.
- Severity colours: reuse the `severity` chip strip styling
  from the Validate page (`spec/validate_page.md`) for
  consistency.
