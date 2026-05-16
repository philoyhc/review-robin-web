# Timezone display

How Review Robin Web decides which timezone every date / time is
**rendered** in. Storage is uniform — every timestamp is stored in
UTC — so this doc is only about display. The mechanics (the
canonical format, the `app/services/date_formatting.py` helpers
`format_datetime` / `format_date` / `timezone_label` /
`parse_local_datetime` / `format_datetime_local`, the
`SHOW_ZONE_TOKEN` switch) landed in Segment 18B; see
`guide/archive/segment_18B_date_and_time_settings.md` for that
history.

## Layers

Display timezone is chosen at two deliberate layers, over a third
notional one at the base:

1. **Workspace** — *notional*. There is no workspace-level
   timezone setting, and no workspace-level surface that needs
   one today. The workspace default is **UTC**. If a
   workspace-wide surface is ever added, it renders in UTC — a
   server's host timezone is a deployment accident, not a
   product choice.
2. **Operator** — each operator's default display timezone: the
   `display_timezone` key of `users.preferences`, edited on the
   **Date & time** card at `/operator/settings`. Per-operator and
   independent — each operator keeps their own
   (`spec/settings_inventory.md` §1). Left untouched, it follows
   the workspace default (UTC).
3. **Session** — each session's `display_timezone`
   (`sessions.display_timezone`), a field of the Create Session
   and Edit Session Details forms. Captured at create time as a
   **snapshot** of the creating operator's then-current default;
   may be deliberately overridden afterward. A snapshot, not a
   live link — changing the operator default later does not move
   existing sessions.

## Resolution order

`sessions.resolve_session_timezone(session)` resolves a session's
effective display zone:

    session.display_timezone  →  creating operator's default  →  UTC

The middle fallback is load-bearing only for legacy rows whose
`display_timezone` is NULL — since Segment 18B PR 4 / PR 5 the
Create and Edit forms always write a concrete zone, so new
sessions resolve at the first step. The operator default
resolves similarly: `users.preferences['display_timezone']` → UTC.

## Which timezone each surface shows

**Session-scoped surfaces render in the session's resolved zone.**
Every surface that belongs to a single session — and so has one
unambiguous zone — localises to it:

- **Operator session pages** — Session Home / Detail, Edit, the
  Setup pages (Reviewers / Reviewees / Relationships /
  Instruments), Operations pages. The session dependency
  (`require_session_operator` / `require_reviewer_in_session`)
  re-stamps `request.state.display_timezone` to the resolved
  session zone, which the `format_datetime` / `format_date`
  Jinja filters read.
- **Reviewer surfaces** — the review surface and the per-session
  rows of the reviewer dashboard.
- **Reviewer emails** — the `$deadline` / `$submitted_at` merge
  fields.
- **CSV extracts** — every per-session extract. Timestamps are
  ISO 8601 carrying the session zone's UTC offset (e.g.
  `2026-06-02T08:00:00+08:00`) — a precise, round-trip-safe
  machine format whose offset reflects the session zone.

**The sessions lobby** (`/operator/sessions`) lists many
sessions at once, so it cannot pick one session zone for its
timestamp columns. Created / Last Modified render in the viewing
operator's zone; a dedicated **Timezone** column (immediately
after Last Modified) names each row's own session zone as a raw
IANA id (e.g. `Asia/Singapore`).

**The Sys Admin audit-log viewer is the one deliberate
exception — UTC end-to-end.** A forensic surface correlating
events across sessions and operators reads most clearly in one
fixed zone; its "When" column header and its From / To date
filter are labelled `(UTC)`.

## Rendering format

- Date-times render bare as `YYYY-MM-DD HH:MM`, dates as
  `YYYY-MM-DD` — no trailing zone token. IANA reports a numeric
  offset for some zones and a letter code for others, so a
  uniform token is not possible; the token is instead available
  behind the `date_formatting.SHOW_ZONE_TOKEN` source switch
  (`spec/settings_inventory.md` §8.5).
- Where a *zone name* is shown to a person — the Settings and
  Session forms' live previews, the Session Details card's
  Timezone item, the reviewer-surface deadline — it is the CLDR
  long display name (e.g. `Australian Eastern Standard Time`),
  with the raw IANA id as the fallback. The sessions-lobby
  Timezone column is the exception: it shows the raw IANA id,
  since that column is a compact at-a-glance reference.

## See also

- `spec/settings_inventory.md` — §1 (operator settings), §2
  (per-session settings), §8.5 (the `SHOW_ZONE_TOKEN` switch).
- `spec/csv_contracts.md` — extract column shapes, including the
  ISO-8601-with-session-offset timestamp rule.
- `guide/archive/segment_18B_date_and_time_settings.md` — the
  segment that built this.
