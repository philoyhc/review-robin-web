# Segment 12B — Audit-events export

> **Refreshed 2026-05-10 against the post-12A-3 codebase.**
> The original plan (renamed 2026-05-07 from
> `segment_12_export_audit_retention_mvp_plan.md`) described a
> larger Segment 12 covering response-data CSV / Excel exports
> plus retention. The response-data half shipped as **Segment
> 12A-1** (`guide/archive/segment_12A-1_export.md`, 5 PRs
> 2026-05-09) and **Segment 12A-3** (`guide/archive/segment_12A-3_export_import_updates.md`,
> 4 PRs 2026-05-10) — five live CSV downloads on the Extract
> Data card. The retention half folded into the existing
> Danger Zone affordances (Delete Data + Delete Session, per
> session and bulk on the Sessions lobby), which already
> preserve / pre-delete `audit_events` rows correctly.
>
> What's left in 12B is the smallest possible slice: **a
> sixth Extract Data tile that serves the per-session
> `audit_events` rows as a CSV download**. No retention-policy
> work, no cross-session aggregation, no scheduled purge — see
> "Out of scope" below.

**Status:** Planning. Sized 2026-05-10 (1 PR).
**Hard prerequisite:** Segment 11K (audit-event `detail`
schema convention) — shipped 2026-05-07. The export reads
against the canonical envelope.

## Goal

Add an **Audit log** download to the Extract Data card on
Session Home so an operator can pull the per-session audit
trail as a wide CSV for downstream analysis or
recordkeeping.

After this PR ships, the Extract Data card carries six live
tiles:

```
Reviewers       |  Session settings
Reviewees       |  Responses
Relationships   |  Audit log
                |  Zip all  (greyed out — deferred)
```

The card's `extract-data-grid` CSS already wraps row-major
in a 2-column grid; adding a sixth tile shifts the inert
Zip-all bundle into a 4th right-column row. Same shape as
PR 2 of 12A-3 except we're inserting one tile, not removing
one.

## Codebase-check notes (2026-05-10)

What 12A-1 / 12A-3 already shipped that 12B builds on:

- **Extract Data card** is fully wired (5 tiles + inert
  bundle); adding a 6th tile is a `_extract_data.py`
  edit + a route + a new extract service module.
- **Audit infrastructure** is mature:
  `app/services/audit.py` carries 61 `EVENT_SCHEMAS`
  registrations + the four canonical detail-envelope
  helpers (`audit.changes()` / `.snapshot()` / `.counts()`
  / `.set_changes()`). Every mutating service writes
  through `write_event(...)`. The `audit_events` table
  carries 10 columns (id / session_id / actor_user_id /
  event_type / severity / summary / detail / correlation_id
  / created_at) and is append-only in practice.
- **The retention story is already solved**: the existing
  `POST /sessions/{id}/delete-data` (Delete Data) preserves
  audit rows; `POST /sessions/{id}/delete` (Delete Session)
  + Sessions lobby bulk-delete explicitly delete audit
  events for the session before deleting the session row,
  so the `session.deleted` snapshot event captures identity
  and any historical investigation goes through the export
  before the operator clicks Delete.

What's still pre-12B:

- No `/export/audit-events.csv` route.
- No `serialize_audit_events()` extract service.
- No `session.audit_log_extracted` event registration.
- No "Audit log" row in
  `app/web/views/_extract_data.py`.

## Scope

### Audit-events CSV format

8 columns matching the canonical detail envelope and the
operator-meaningful slots. JSON-encoded `detail` column
preserves the typed envelope for downstream re-parse.

```
EventType,Severity,Summary,ActorEmail,CorrelationId,CreatedAt,DetailJson
```

| Column | Source | Notes |
|---|---|---|
| `EventType` | `event_type` | The 61-strong registered token (e.g. `reviewers.imported`). |
| `Severity` | `severity` | `info` (default) / `warning` / `error`. |
| `Summary` | `summary` | Human-readable one-liner the writer passes. |
| `ActorEmail` | `users.email` via `actor_user_id` | Joined-in; empty cell for system-emitted events without an actor (some lifecycle events). |
| `CorrelationId` | `correlation_id` | Indexed; carries the request's correlation id when available. |
| `CreatedAt` | `created_at` | ISO 8601 UTC. |
| `DetailJson` | `detail` | `json.dumps(detail, separators=(",", ":"), sort_keys=True)`. Empty cell if `detail` is None. |

Filename: `{code}_audit_log.csv`. Ordering deterministic
(`created_at ASC, id ASC`).

The detail envelope (per `spec/architecture.md`
"Audit-event detail schema") is preserved as a JSON string
rather than denormalised into per-key columns, because:

1. Different `event_type`s carry different envelope keys;
   one-column-per-key produces a sparse table with hundreds
   of mostly-empty columns.
2. Analysts who want a specific key field can `json_extract`
   in SQLite or `json.loads` in pandas — the envelope shape
   is documented and stable post-11K.
3. Spreadsheet users who don't need the structured detail
   can ignore the column.

### Extract service

- New `app/services/extracts/audit_events_extract.py` with
  `serialize_audit_events(db, review_session) -> Iterable[Row]`.
  Pinned `HEADER` tuple in unit-test golden fixture.
  Streams via `yield_per(1000)` cursor (mirrors the
  Responses extract in 12A-1 PR 4) so memory stays flat on
  sessions with thousands of events.

### Audit-event registration

- New `session.audit_log_extracted` registered in
  `EVENT_SCHEMAS` (`_IDENTITY | {"counts"}`, mirrors the
  other `*_extracted` events from 12A-1 + 12A-3). The export
  route writes one of these per download — yes, including
  the act of exporting the audit log itself goes into the
  audit log. The next export captures the prior-export
  event (recursive but bounded by the export-pre-Delete
  workflow).

### Route

- New `GET /operator/sessions/{id}/export/audit-events.csv`
  in `app/web/routes_operator/_extracts.py`. Mirror of the
  Responses route — counts up front via a `count(*)` query
  so the audit event carries the row count without
  materialising the streaming generator. No lifecycle gate;
  matches the existing extracts.

### Extract Data tile

- New `"audit_log"` row in
  `app/web/views/_extract_data.py` between `relationships`
  and the bundle. Same `_entity_row` helper as #781 grey-
  out-on-empty: an empty session emits a header-only CSV
  but the operator typically has a few rows by the time
  they care, so the tile lights up almost immediately.
- `show_count = True` (mirrors the other entity rows) — the
  count surfaces inline next to the title.

### Layout

The Extract Data card stays a 2-column grid. Six tiles +
bundle = 7 entries. Row-major DOM order:

```
Reviewers       |  Session settings
Reviewees       |  Responses
Relationships   |  Audit log
                |  Zip all  (inert)
```

The bundle row sits alone in the 4th right-column slot;
the 4th left-column slot is empty. The existing CSS handles
empty grid cells gracefully (the layout collapses to one
column on narrow viewports).

## Out of scope

Each item is excluded *deliberately*; the rationale is
captured here so a future segment doesn't re-litigate.

- **Audit-events purge / retention policy.** The Delete
  Session flow on Session Home + Sessions lobby already
  hard-deletes `audit_events` rows for the deleted session
  via the explicit pre-delete pattern in
  `app/services/sessions.py`. Per-session retention beyond
  that (e.g. "delete audit events older than 90 days while
  the session lives") has no operator demand today. If
  pilot feedback flips that, it lands in its own segment
  with proper retention-policy + scheduled-job design.
- **Cross-session / workspace-level audit page.** The
  per-session tile covers the standard
  "what-happened-to-this-session" investigation. The
  forensic case (e.g. "who deleted session X?" after the
  session row is gone) is harder to cover — the audit
  events for the deleted session were also deleted at
  session-delete time. A workspace-level audit page would
  require changing the cascade pattern, which lives in
  Segment 14 / 15 territory.
- **JSON Lines variant.** The CSV-with-JSON-encoded-detail
  format covers both the spreadsheet and programmatic
  cases (`pd.read_csv(...).assign(detail=lambda d:
  d.DetailJson.apply(json.loads))`). A second route /
  service for JSON Lines is feature creep without a clear
  consumer.
- **Filter UI / dedicated Audit Log page.** Operators who
  want to slice by event_type / severity / date range
  download the CSV and filter in their tool of choice. A
  table-view + filter UI is more code than the current
  pilot demand justifies.
- **Importer half.** Audit events are system-emitted, not
  operator-typed; there is no porting use case. The CSV
  stays download-only (mirrors the Responses CSV).

## PR sequence (1 PR)

### PR 1 — Audit-events extract + Extract Data tile

- `app/services/extracts/audit_events_extract.py` —
  `serialize_audit_events()` extract service with `HEADER`
  + `yield_per(1000)` streaming. Joins `audit_events` to
  `users` for the `ActorEmail` column.
- `session.audit_log_extracted` registered in
  `EVENT_SCHEMAS`.
- `GET /operator/sessions/{id}/export/audit-events.csv`
  route in `_extracts.py`. Counts up front; emits the
  audit event with row count; streams via `stream_csv`.
- New `"audit_log"` row in `_extract_data.py` between
  `relationships` and the bundle. Uses the existing
  `_entity_row` helper for grey-out-on-empty parity.
- Tests:
  - **Unit** (`tests/unit/test_audit_events_extract.py`):
    header pinned; per-row shape with all columns including
    JSON-encoded detail; ordering deterministic
    (`created_at ASC, id ASC`); ActorEmail empty for events
    with `actor_user_id IS NULL`; `detail=None` collapses
    to empty cell.
  - **Integration**
    (`tests/integration/test_extracts_audit_events_route.py`):
    route auth + filename + audit emission with row count;
    non-operator rejection (mirrors the other extract route
    tests).
  - **Scaffold** (existing
    `tests/integration/test_extract_data_scaffold.py`):
    update DOM-order + tile-count assertions for the new
    6-tile shape.
- Doc updates:
  - `README.md` — Extract Data blurb shifts from "five
    live CSV downloads" to "six live CSV downloads", names
    the new Audit log tile.
  - `spec/settings_inventory.md` §10 — coverage table
    gains an Audit log row noting it's analytics-only (no
    import counterpart, like Responses).

## Test impact

- Round-trip tests are not applicable — audit events are
  system-emitted, no importer.
- Lifecycle: no gating; the route returns whatever rows
  exist regardless of session state.
- Empty-session: header-only CSV; tile renders `aria-disabled`
  via the existing grey-out-when-empty pattern (#781).

## Doc impact

- `README.md` — Extract Data blurb (six live downloads).
- `spec/settings_inventory.md` §10 — Audit-events row in
  the CSV coverage table (analytics-only, no round-trip).
- `docs/status.md` — new Project timeline row + Segments
  shipped row + new Operator URL row for `/export/audit-events.csv`.
- `guide/todo_master.md` — Done entry under Segment 12;
  drop 12B from the Upcoming numbered queue.
- `guide/segment_12B_audit_retention.md` (this file) →
  `guide/archive/` after the PR lands.

## Related context

- **Segment 11K** (audit-event detail schema) — shipped
  2026-05-07. Pins the canonical envelope shape that the
  CSV's `DetailJson` column preserves. Spec at
  `spec/architecture.md` "Audit-event detail schema".
- **Segment 12A-1** (`guide/archive/segment_12A-1_export.md`)
  — established the per-entity export pattern this segment
  extends; the Responses extract in particular is the
  closest cousin (streamed via `yield_per`, no import
  counterpart).
- **Segment 12A-3** (`guide/archive/segment_12A-3_export_import_updates.md`)
  — locked the post-12A-3 Extract Data card layout that
  this PR extends with one tile.

## Notes for the implementing agent

- The `audit_events.actor_user_id` FK is nullable (some
  lifecycle events are system-emitted). The `users` join
  must be a LEFT JOIN.
- `audit_events.session_id` FK is nullable too — but the
  per-session export filters `WHERE session_id = ?`, so
  null-session events are excluded by design.
- `correlation_id` is plain text; some events (early ones)
  may not carry it. Empty cell is fine.
- The route does NOT need a confirmation banner or
  lifecycle gate — it's a read-only download.
- Recursion: writing the `session.audit_log_extracted`
  event for a download means the *next* download includes
  that event. That's a feature (the audit log captures
  who downloaded the audit log when), not a bug. Bounded
  by operator behaviour — they typically download once
  before Delete.
