# Segment 18B — Date and time settings

> **Stub created 2026-05-15.** Sketch-level scope only; detailed
> PR breakdowns get drafted when this segment is picked up.
>
> The 18B segment number was previously held by "Session tagging
> + archiving", which was folded into 18A (Sessions lobby
> enhancements) on 2026-05-15. 18B is reused here for an
> unrelated, cross-cutting concern.

## Goal

Give the deployment (and possibly the operator) control over how
**dates and times are displayed**, and make the display
**consistent** across the app.

Today every timestamp is stored and displayed in **UTC** with no
timezone indicator, and the rendering is **inconsistent** — some
sites use a raw ISO-8601 string (`2026-05-15T10:00:00+00:00`),
others a `strftime("%Y-%m-%d %H:%M")`, others a bare
`strftime("%Y-%m-%d")`. An operator in UTC+8 reading "10:00" has
no cue it isn't their local time (this surfaced in conversation
2026-05-15 — the Setup-page Updated column reads UTC).

## Why now

- The Segment 15F Updated column made UTC-vs-local ambiguity
  visible on a high-traffic operator surface — the operator
  noticed timestamps "looked off" and it took a diagnosis pass to
  confirm it was UTC display, not a clock bug.
- There is **no timezone or date-format setting anywhere** —
  `app/config.py` has none, and no per-session or per-operator
  field exists.
- The rendering inconsistency is its own small debt: three-plus
  formats in flight (`isoformat()`, `%Y-%m-%d %H:%M`,
  `%Y-%m-%d`, `%Y-%m-%dT%H:%M` for the one datetime-local input).
  A shared display helper / Jinja filter would unify them.

## Audit — every date/time display site (2026-05-15)

All stored timestamps are UTC (SQLAlchemy `TimestampMixin`
`created_at` / `updated_at` use `server_default=func.now()`;
Postgres returns tz-aware UTC, SQLite naive). Deadlines are
operator-entered. Display sites:

### Operator templates

| Template | Field(s) | Current render |
|---|---|---|
| `sessions_list.html` | `deadline` | `.isoformat()` (pill) |
| `sessions_list.html` | `created_at`, `updated_at` | `.isoformat()` (pills) |
| `session_detail.html` | `created_at`, `updated_at`, `deadline` | `.isoformat()` (pills) |
| `session_edit.html` | `deadline` | `strftime('%Y-%m-%dT%H:%M')` into a `<input type="datetime-local">` |
| `session_edit.html` | owner `joined_at` | `strftime("%Y-%m-%d")` |
| `sys_admin_sessions.html` | `deadline`, `created_at`, `updated_at` | `.isoformat()` (pills) |
| `sys_admin_users.html` | `created_at` | `strftime("%Y-%m-%d")` |
| `sys_admin_session_audit_log.html` | `created_at` | `row.created_at_iso` — pre-formatted UTC by `_audit_log.py::_isoformat_utc` (naive → UTC then `.isoformat()`) |
| `instruments_index.html` | session `deadline` | `.isoformat()` (pill) |
| `instruments_index.html` | instrument `deadline_closed_at` | `.isoformat()` (`<code>`) |
| `session_invitations.html` | `email_sent_at`, `last_reminder_at` | `strftime("%Y-%m-%d %H:%M")` (pills) |
| `session_invitations_reviewer_detail.html` | `email_sent_at`, `last_reminder_at` | `strftime("%Y-%m-%d %H:%M")` |
| `session_responses.html` | `last_response_at` | `strftime("%Y-%m-%d %H:%M")` (pill) |
| `session_responses_reviewee_detail.html` | `last_response_at` | `strftime("%Y-%m-%d %H:%M")` |
| `session_reviewers.html` / `session_reviewees.html` / `session_relationships.html` | `updated_at` (Updated column, 15F) | `strftime("%Y-%m-%d %H:%M")` + `.isoformat()` as `data-sort-value` |
| `partials/_sys_admin_outbox.html` | `sent_at` | `strftime("%Y-%m-%d %H:%M")` |

### Reviewer templates

| Template | Field(s) | Current render |
|---|---|---|
| `reviewer/dashboard.html` | session `deadline` | `.isoformat()` |
| `reviewer/review_surface.html` | session `deadline` | `.isoformat()` |
| `reviewer/review_surface.html` | `submitted_at` | `strftime("%Y-%m-%d %H:%M")` |

### Service / view layer (non-template formatting)

| Site | Purpose | Current render |
|---|---|---|
| `email_templates.py::_deadline` | `$deadline` merge field | `strftime("%Y-%m-%d")` |
| `email_templates.py` (responses-received) | `$submitted_at` merge field | `strftime("%Y-%m-%d %H:%M %Z")` — the only site that prints a tz token |
| `views/_audit_log.py::_isoformat_utc` | audit viewer cell + filter param round-trip | naive → UTC, `.isoformat()` |
| `extracts/responses_extract.py` | CSV `saved_at` / `submitted_at` | `.isoformat()` |
| `extracts/audit_events_extract.py` | CSV `CreatedAt` | `_isoformat_utc` |
| `session_config_io.py` | settings-CSV deadline export | `.isoformat()` |
| `audit.py` | audit-detail JSON datetime values | `.isoformat()` |

### Date *input* sites (parsing, not display — in scope for consistency)

- `session_edit.html` deadline `<input type="datetime-local">` →
  parsed by `routes_operator/_session_home.py` /
  `_quick_setup.py` via `datetime.fromisoformat`.
- `sys_admin_session_audit_log.html` from/to `<input type="date">`
  filter → parsed by `views/_audit_log.py` via
  `date.fromisoformat`.

## Scope (sketch)

### Part 1 — Display timezone + a shared formatting helper

- A **deployment timezone** setting (env var in `app/config.py`,
  e.g. `DISPLAY_TIMEZONE`, default `UTC`). Possibly later a
  per-operator override — confirm at scoping whether per-deploy
  is enough for the pilot.
- A single **Jinja filter / helper** (e.g. `format_datetime` /
  `format_date`) that takes a stored UTC datetime, converts to
  the display timezone, and renders one canonical format. Every
  template display site above migrates to it.
- Decide the canonical formats: one for date-time, one for
  date-only. Include an unambiguous timezone token (or label the
  column) so "10:00" is never read as the wrong zone.
- The extract / audit-JSON sites stay **ISO-8601 UTC** — machine
  formats shouldn't localize. Audit viewer: decide whether the
  on-screen cell localizes while the CSV stays UTC.

### Part 2 — Input consistency (post-MVP / fold-in)

- The deadline `datetime-local` input is implicitly local-to-the-
  browser; reconcile it with the chosen display timezone so an
  operator entering "5 PM" gets "5 PM" in the display zone.

## Hard dependencies

- **None.** This is a cross-cutting display change; it touches
  templates + a config setting + one helper module.

## Out of scope

- **Per-reviewer timezone.** Reviewers see the session deadline;
  a per-reviewer tz is over-engineering for the pilot.
- **Localized date *formats* per locale** (DD/MM vs MM/DD via
  `Accept-Language`). Pick one canonical format; i18n is a much
  larger separate concern.
- **Changing stored values.** The DB stays UTC; this is a
  display-layer change only.

## Doc impact

When parts ship:

- `docs/status.md` timeline entry.
- `guide/todo_master.md` updated.
- `spec/settings_inventory.md` — new deployment (and/or
  per-operator) timezone setting row; note the canonical display
  format.
- `spec/visual_style_rrw.md` / `spec/ui_elements.md` — document
  the canonical date-time render + the Jinja filter.
- Any spec that quotes a timestamp example refreshed to the
  canonical format.

## Working notes

- _(placeholder for decisions during PR scoping)_
- **Per-deploy vs per-operator timezone.** A single deployment
  serves one institution in one timezone — per-deploy is likely
  enough. Per-operator only matters for multi-region operator
  teams; defer unless pilot feedback asks for it.
- **`isoformat()` sites are the ugliest** (`2026-05-15T10:00:00+00:00`
  in a pill) — they're the priority migration targets even before
  the timezone work, purely on legibility.
- **`%Z` already in use** on the `$submitted_at` merge field —
  decide whether the canonical format always carries a tz token
  or whether the column header / label carries it instead.
