# Segment 18B — Date and time settings

> **Planned 2026-05-15.** Scoping decisions locked (see "Locked
> decisions" below); PR ladder drafted. Detailed per-PR
> breakdowns get finalised when the segment is picked up.
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

## Locked decisions (2026-05-15 scoping)

1. **Setting scope — per-session, two-tier.** Each session
   carries its own display timezone. A **deployment-wide
   default** is inherited by every new session and can be
   **overridden per session**. Mirrors the 15C library /
   per-session-copy pattern (default → per-session copy).
2. **Surfaces — two cards.** The deployment default is edited on
   a card on the operator Settings page (`/operator/settings`);
   the per-session override is edited on a card on the Session
   Edit page (`/operator/sessions/{id}/edit`), next to the
   deadline field.
3. **New-session default — deployment default zone.** A session
   created today inherits the configured deployment timezone;
   the operator only touches the per-session card to deviate.
4. **Card controls timezone only.** The date-time and date-only
   *formats* are standardized in code (goal 1, decision 7) — not
   operator-configurable. The cards expose only the timezone
   choice.
5. **Full IANA timezone picker.** The card is a dropdown of IANA
   zone names (e.g. `Asia/Singapore`, `UTC`), not a binary
   local/UTC toggle — so a session can be pinned to any zone.
6. **Reviewer surface — always an explicit zone token.**
   Reviewer-facing dates (above all the deadline) render in the
   session's configured zone **and always carry a visible zone
   abbreviation** (see decision 7), so a reviewer physically
   elsewhere is never left guessing.
7. **Canonical formats.**
   - Date-only: `YYYY-MM-DD` (e.g. `2026-05-15`).
   - Date-time: `YYYY-MM-DD HH:MM` in 24-hour time, followed by
     the resolved zone's abbreviation — e.g. `2026-05-15 17:00
     SGT`. The zone abbreviation is part of the date-time render
     everywhere (not delegated to a surrounding label).
   - The abbreviation is typically three letters (`SGT`, `EST`),
     but is whatever the zone's standard abbreviation is — a few
     zones use four letters (`AEDT`) or a numeric offset; see
     the working note on `%Z`.

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

## Data model

- **Deployment default timezone.** A workspace-scoped setting,
  DB-persisted so the `/operator/settings` card can edit it (an
  env var alone wouldn't be operator-editable). Either a
  single-row settings table or a typed key/value row — this is
  the first workspace-scoped setting in the app, so the table
  shape is a small design call at PR time. An env var can seed
  the initial value on a fresh deployment; default `UTC`.
- **Per-session override.** New nullable column
  `sessions.display_timezone` (IANA zone-name string; `NULL` =
  inherit the deployment default). New sessions are stamped with
  the deployment default at create time, so the column is rarely
  NULL in practice — but `NULL`-means-inherit stays meaningful.
- **Resolution order:** `sessions.display_timezone` → deployment
  default → `UTC`. The shared helper resolves this once per
  render. Session-less surfaces (cross-session sessions lobby,
  sys-admin pages) resolve to the deployment default.
- All migrations additive / nullable, no backfill — the 13D/13E
  playbook.

## Plan (PR ladder)

Three PRs. PR 1 is independently shippable and delivers goal 1
(format standardization) on its own; PRs 2-3 layer the timezone
infra (goal 2).

### PR 1 — Canonical format + shared display helper

- Add `format_datetime` / `format_date` Jinja filters (+ a
  plain-Python helper for the email / service paths) in one new
  module — the canonical formats from decision 7
  (`YYYY-MM-DD HH:MM <ZONE>` / `YYYY-MM-DD`).
- The helper takes a stored UTC datetime and, **at this stage**,
  formats it in UTC with an explicit `UTC` token appended — so
  every site is immediately unambiguous even before the timezone
  infra lands.
- Migrate every template + service display site in the audit
  above to the helper. The `isoformat()` pill sites are the
  ugliest and the priority.
- **Not touched:** the CSV extracts + audit-detail JSON — those
  stay ISO-8601 UTC (machine formats don't localize).
- No schema change. May split 1a (helper + operator templates) /
  1b (reviewer templates + email merge fields) if the diff is
  large.

### PR 2 — Deployment default timezone + `/operator/settings` card

- The workspace-default-timezone data model (above) + an
  `/operator/settings` card with the full IANA timezone picker.
- The shared helper grows timezone resolution: it converts the
  UTC value into the deployment default zone before formatting,
  and the zone token reflects the resolved zone.
- Audit event `workspace.display_timezone_set` (changes
  envelope), registered in `EVENT_SCHEMAS`.
- After this PR every operator + reviewer surface renders in the
  deployment zone with a correct token.

### PR 3 — Per-session timezone override + Session Edit card

- `sessions.display_timezone` column + migration; new sessions
  stamped with the deployment default on create.
- A card on the Session Edit page with the IANA picker + an
  "inherit deployment default" affordance.
- The helper's resolution order becomes session → deployment →
  UTC; every render with a session in scope uses the session
  zone.
- Audit event `session.display_timezone_set` (changes envelope).
- **Deadline-first verification.** Re-check every deadline
  display site — Session Home, reviewer surface, sessions list,
  instruments page, and the `$deadline` / `$submitted_at` email
  merge fields — carries the right zone + token.

### Post-MVP — input consistency

The deadline `<input type="datetime-local">` on Session Edit is
implicitly browser-local; reconcile it with the session's
configured zone so an operator entering "5 PM" gets "5 PM" in the
session zone, not the browser's. Likewise the audit-log
`<input type="date">` filter. Deferred — confirm need once the
display side is in operators' hands.

## Hard dependencies

- **None strictly required.** Cross-cutting display change —
  templates + a workspace setting + a `sessions` column + one
  helper module.
- **Surface precedents already exist:** `/operator/settings`
  shipped in Segment 11E (the deployment-default card joins it);
  the Session Edit page gained the Owners card in 16B (the
  per-session card joins it next to the deadline field).

## Out of scope

- **Per-operator timezone.** The setting is per-session (with a
  deployment default), not per-operator — an operator viewing a
  session sees that session's zone, not their own preference.
  Considered at scoping and dropped.
- **Per-reviewer timezone.** Reviewers see the session's zone
  (with an explicit token); a per-reviewer preference is
  over-engineering for the pilot.
- **Operator-configurable date *format*.** The cards control the
  timezone only; the date-time / date-only formats are fixed in
  code.
- **Localized date *formats* per locale** (DD/MM vs MM/DD via
  `Accept-Language`). One canonical format; i18n is a much
  larger separate concern.
- **Changing stored values.** The DB stays UTC; this is a
  display-layer change only.

## Doc impact

When parts ship:

- `docs/status.md` timeline entry.
- `guide/todo_master.md` updated.
- `spec/settings_inventory.md` — the new workspace-default
  timezone setting + the `sessions.display_timezone` column +
  the two cards; note the canonical display format.
- `spec/sessions_overview.md` / a Session Edit spec — the
  per-session timezone card.
- `spec/visual_style_rrw.md` / `spec/ui_elements.md` — document
  the canonical date-time render + the Jinja filter; refresh any
  quoted timestamp example to the canonical format.
- `spec/architecture.md` — the two new audit events.

## Working notes

- _(placeholder for decisions during PR scoping)_
- **Workspace-settings table shape.** This is the app's first
  workspace-scoped (vs per-operator / per-session) setting.
  Decide at PR 2 scoping: a single-row `workspace_settings`
  table vs a typed key/value table. Lean single-row table —
  simplest, and a second workspace setting is not on the horizon.
- **`isoformat()` sites are the ugliest** (`2026-05-15T10:00:00+00:00`
  in a pill) — priority migration targets in PR 1, legibility
  alone.
- **`%Z` already in use** on the `$submitted_at` merge field —
  decision 7 makes the zone abbreviation part of the canonical
  date-time format, so this becomes consistent rather than a
  one-off. `%Z` on a `zoneinfo`-aware datetime yields the zone
  abbreviation directly; verify it for the target zones at PR 2,
  since a few zones surface a numeric offset (`+08`) rather than
  a letter code depending on the tz database.
- **IANA picker UX.** A raw `<select>` of ~350+ IANA zones is
  unwieldy; consider a shortlist of common zones + a searchable
  control, or a `<datalist>` (the Segment 15F relationship-picker
  pattern). Decide at PR 2.
