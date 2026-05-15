# Segment 18B — Date and time settings

> **Stub created 2026-05-15.** Sketch-level scope only; detailed
> PR breakdowns get drafted when this segment is picked up.
>
> The 18B segment number was previously held by "Session tagging
> + archiving", which was folded into 18A (Sessions lobby
> enhancements) on 2026-05-15. 18B is reused here for an
> unrelated, cross-cutting concern.

## Goal

Two linked goals:

1. **Standardize the format.** Replace the three-plus ad-hoc
   render formats in flight today with one canonical date-time
   format and one date-only format, applied through a single
   shared helper so every display site is consistent.
2. **Build central local-vs-UTC display infra.** One place —
   config-driven, not per-template — decides whether a given
   timestamp renders in the deployment's **local timezone** or in
   **UTC**. Every display site reads that decision through the
   shared helper, so the choice is made once and applied
   everywhere.

Why the local-vs-UTC decision has to be *central* rather than
sprinkled per template: it must stay consistent, and it matters
most for **business-critical timestamps — above all the session
deadline.** A reviewer or operator misreading a deadline by the
UTC offset (e.g. treating an 18:00 UTC+8 deadline as 18:00 UTC)
can miss it entirely. The deadline is the timestamp where an
ambiguous zone has real consequences, so it drives the design.

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

### Part 1 — Central display infra: timezone decision + shared helper

The core of the segment — the central place that owns both the
format and the local-vs-UTC decision.

- A **deployment timezone** setting (env var in `app/config.py`,
  e.g. `DISPLAY_TIMEZONE`, default `UTC`) plus a **display-mode**
  decision (render in `DISPLAY_TIMEZONE` local time, or render
  UTC). Whether that's one setting (the timezone, with `UTC`
  meaning "no conversion") or two is a scoping call; either way
  the decision lives in **one** config-backed place.
- A single **Jinja filter / helper** (e.g. `format_datetime` /
  `format_date`) that takes a stored UTC datetime, applies the
  central timezone decision, and renders one canonical format.
  Every template display site in the audit above migrates to it
  — no template makes its own zone or format choice.
- Decide the canonical formats: one for date-time, one for
  date-only. The render **always carries an unambiguous timezone
  token** (or the surrounding label does) so a value is never
  read against the wrong zone — non-negotiable for the deadline.
- **Deadline-first.** The deadline display sites (Session Home /
  reviewer surface / sessions list / instruments page / the
  `$deadline` email merge field) are the highest-stakes
  consumers; verify them first and make sure the zone token is
  present wherever a deadline shows.
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
