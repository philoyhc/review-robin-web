# Segment 16C — Richer audit views

> **Carved out of the original Segment 16 (2026-05-11).** The
> Sys Admin page + sys-admin role gate live in **16A**
> (`guide/segment_16A_sys_admin_page.md`); user-role management
> + role delegation live in **16B**
> (`guide/segment_16B_role_delegation.md`).

**Stub. Sketch-level scope only.** Detailed PR breakdowns get
drafted when this segment is picked up.

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

## Scope (sketch)

### Part 1 — Audit log viewer (read-only, per-session)

**Goal.** A paginated, filterable HTML table of `audit_events`
rows for one session, rendered on a new Sys Admin sub-page.

Likely shape:

- New route under the Sys Admin chrome (16A) — e.g.
  `/operator/sessions/{id}/sys-admin/audit-log` — rendering a
  table of the same 8 columns the CSV download exposes
  (`EventType` / `Severity` / `Summary` / `ActorEmail` /
  `CorrelationId` / `CreatedAt` / `DetailJson`) plus a
  per-row "Show detail" expander.
- Pagination via keyset on `id DESC` (newer first); default
  page size ~50.
- Filter strip: by event type (dropdown of registered types),
  by severity (info / warning / error), by actor email
  (typeahead), by date range. URL params persist filter
  state.
- Detail-JSON pretty-printer: the canonical envelope renders
  as a small definition list (key / value pairs) instead of a
  raw JSON dump. Per-payload-shape (`changes` / `snapshot` /
  `counts` / `set_changes`) the renderer formats the
  envelope's specific slots.
- "Download filtered CSV" button reuses the existing
  `serialize_audit_events` with the same filter set applied.

### Part 2 — Cross-session audit search (workspace-level)

**Goal.** A workspace-level Sys Admin sub-page that searches
across every session the operator can see.

Likely shape (deferred — confirm need after Part 1):

- New route — e.g. `/operator/sys-admin/audit-log` (no
  session id) — same table shape as Part 1, scoped to every
  session the sys-admin can access.
- Filter strip gains a session-code dropdown.
- Performance gate: the workspace-level view runs against a
  per-actor projection (or just scans `audit_events` with a
  date-range default of "last 7 days") to keep query times
  reasonable.

### Part 3 — Entity drill-in (post-MVP)

**Goal.** From an audit row, jump to the affected entity
(session / reviewer / reviewee / instrument / etc.).

Likely shape:

- The canonical envelope's `refs` slot already holds the
  affected entity IDs; the viewer reads those and renders
  per-row "View reviewer" / "View instrument" anchors that
  deep-link into the operator chrome.
- Audit rows whose entities have since been deleted render
  the anchor as a disabled "(deleted)" suffix.

### Part 4 — Timeline / activity-stream view (post-MVP)

**Goal.** A reverse-chronological "what happened on this
session in the last week?" view on Session Home itself
(operator-visible, not sys-admin-only), summarising the
most-recent N audit events in human-friendly prose.

Likely shape (deferred — confirm need with operator
feedback before scoping):

- Small "Recent activity" card on Session Home (operator-
  visible, not gated to sys-admin).
- Per-event summariser maps the event_type + envelope to a
  one-line human-readable string (e.g. `"Alice activated the
  session"` / `"Bob uploaded 47 reviewers"`).
- Deep-link from the summary to the full audit row in 16C
  Part 1's viewer.

Distinct from Part 1: Part 1 is the diagnostic-grade table
with raw envelope + filters; Part 4 is the friendly
prose-summarised stream operators actually skim.

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
