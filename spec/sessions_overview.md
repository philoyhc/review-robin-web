# Sessions Overview page — functional spec

The operator's lobby. Lists every session the signed-in user is
an operator on, surfaces a one-click affordance for creating a new
session, and (post Segment 18A) carries sortable columns, a tag
filter, a search box, per-row and bulk row-expanders for
rename / tag / clone / purge-and-archive / delete, and a sibling
archived-sessions child page.

> Status: shipped (Segment 18A rebuild). URL:
> `GET /operator/sessions`. Template:
> `app/web/templates/operator/sessions_list.html`. Archived child
> page: `GET /operator/sessions/archived` →
> `sessions_archived.html`. The lobby's POST handlers live in
> `app/web/routes_operator/_lobby.py`:
> `delete-selected` / `archive-selected` / `bulk-tags` /
> `unarchive-selected` / `delete-archived-selected` /
> `{id}/lobby-edit` / `{id}/clone`.

## Page identity

- **URL.** `/operator/sessions`. The operator's root page; reached
  via the top-bar identity link or by signing in. `/` redirects
  here for any authenticated operator.
- **Title.** `Sessions — Review Robin Web` (browser tab) +
  `Sessions` (page H1).
- **Body class.** `ui-v2` (no reviewer modifier — this is an
  operator-only surface).
- **Audience.** Authenticated users only. Reviewers never see this
  page (they land on `/r/...` URLs scoped to their assigned
  sessions).
- **Breadcrumb.** `operator_root()` → `[Sessions]` (single non-link
  crumb; this is the top of the operator chrome).

## Layout

A single-column page:

```
┌─ <h1>Sessions</h1>          [ Create new session ] ┐  ← header strip
│                                                     │
│ ┌─ tag-filter strip + Search card + Archive link ┐  │
│ │ …                                              │  │
│ └────────────────────────────────────────────────┘  │
│                                                     │
│ ┌─ sessions table card (full width) ─────────────┐  │
│ │ Name | Code | Created by | … | Status | Tags | ☐ │  │
│ │ …  (ticking a row opens an inline expander)    │  │
│ └────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

The table sits inside a single `<form method="post">` so the
per-row checkboxes submit with whichever expander button the
operator clicks (each button carries its own `formaction`). The
destructive bulk actions live in the row-expander, not a separate
Danger Zone card.

## Header strip

A flex row above the table.

- **`<h1>Sessions</h1>`** — page title, left-aligned.
- **`Create new session`** primary button — right-aligned, links to
  `/operator/sessions/new`. Rendered only when at least one session
  exists; the empty state has its own CTA.

## Empty state

When the operator owns zero sessions (no rows in
`sessions.list_for_user`), the page renders a single onboarding
card instead of the table:

> **You don't have any sessions yet.**
> Create a session to invite reviewers, build assignments, and
> collect responses.
>
> [ **Create new session** ]

The CTA links to `/operator/sessions/new`. The header's secondary
"Create new session" button is suppressed in this state so the
single primary CTA isn't duplicated.

## Sessions table

Full-width card. One row per session the caller operates on,
ordered by `created_at DESC` (most recent first).

### Columns

All non-checkbox columns are sortable (`rrw-sortable` header with
a `rrw-sort-btn`); see "Sort / filter / search" below.

| # | Column | Source | Display |
|---|---|---|---|
| 1 | **Session Name** | `session.name` | `<a href="/operator/sessions/{id}">{name}</a>` — clicking the name lands the operator on Session Home. |
| 2 | **Session Code** | `session.code` | Inline `<code>` tag. |
| 3 | **Created by** | `session.created_by_user.display_name` (falls back to `.email`) | `<span class="pill pill-count">{name}</span>`. |
| 4 | **Created** | `session.created_at` | `<span class="pill pill-count">{when}</span>`. `YYYY-MM-DD HH:MM` via `format_datetime`. |
| 5 | **Deadline** | `session.deadline` | `<span class="pill pill-info">{when}</span>` when set, `<span class="muted">No deadline</span>` otherwise. Rendered `YYYY-MM-DD HH:MM` via `format_datetime`. |
| 6 | **Timezone** | `resolve_session_timezone(session)` (the `session_timezone` Jinja global) | `<abbr class="tz-gmt">` showing the compact GMT-offset (e.g. `GMT+8`, via `gmt_offset_label`), with the full `GMT+8 Asia/Singapore` in the `title` hover tooltip. The lobby lists many sessions, so its per-row timestamp cells render in the *viewing operator's* zone; this column names each row's own resolved session zone. See `spec/timezone_display.md`. |
| 7 | **Status** | `session.status` | `<span class="pill pill-lifecycle-{status}">{label}</span>` — same lifecycle-tinted variants the session-home `session_setup_status_row.html` and the 16A Admin Sessions Diagnostics table use (draft / validated / ready / closed each carry distinct tints from `base.html`). The label is the human-readable form produced by the `lifecycle_label` Jinja filter. |
| 8 | **Tags** | `session_tags.tags_for_sessions` | One `pill pill-count` per tag, or a `muted` "No tags". Each row also carries a `data-tags` JSON attribute for the client-side tag filter. |
| 9 | *select-all checkbox* | `session.id` | Bulk-action select-row checkbox. The column **header** carries a select-all checkbox (see below). |

The main lobby table lists only non-archived sessions; archived
sessions move to `/operator/sessions/archived`.

The trailing column has `class="col-shrink"` (auto-narrow CSS).

### Row affordances

- **Name link** is the canonical row-click target — lands the
  operator on Session Home.
- **Row expander.** Ticking a single row's checkbox opens an
  inline expander row beneath it (the `single-session-expander`
  `<template>`) carrying editable Name / Code / Deadline / Tags
  fields plus action buttons: Save (POSTs `{id}/lobby-edit`),
  Cancel, Duplicate / Duplicate settings only (POST `{id}/clone`),
  Purge and archive (POST `archive-selected`), and a Delete button
  gated behind an "Allow delete" checkbox (POST `delete-selected`).
  Ticking two or more rows opens the `bulk-expander` instead — bulk
  tag add/remove (`bulk-tags`), bulk purge-and-archive, and a
  gated bulk Delete.
- **Select-row checkbox** carries:
  - `name="session_ids"` (array semantics — every ticked row
    submits its id)
  - `value="{{ session.id }}"`
  - `class="sessions-list-select-row"`
  - `aria-label="Select {name}"`

  Submitting the form with zero ticks is allowed — the bulk-delete
  handler 303-redirects back to the page as a no-op.

- **Select-all checkbox** sits in the select column's `<th>`
  header (`class="sessions-list-select-all"`, no `name` — it never
  submits). Clicking it toggles every row checkbox at once. Inline
  JS keeps it in sync with the rows: `checked` when every row is
  ticked, `indeterminate` on a partial selection, clear when none
  are — and any row-checkbox change re-derives that state.

### Sort / filter / search

Post Segment 18A the lobby carries all three:

- **Sortable columns.** The table is `data-rrw-sortable` with a
  per-column `rrw-sort-btn`; clicking a header sorts by that key.
  The chosen sort persists in the `rrw-sort-lobby` cookie (shared
  `rrw-sortable` primitive with the Setup preview tables), decoded
  server-side by `views.decode_cookie_sort_spec` /
  `apply_cookie_sort`. Default order is still `created_at DESC`.
- **Tag filter.** A `sessions-tag-filter` chip strip ("Show
  sessions tagged with:") with one `tag-chip` per tag in the
  lobby tag vocabulary, an AND/OR mode chip, and a clear chip.
  Client-side filtering against each row's `data-tags`.
- **Search.** A Search card with a free-text input matching name,
  code, or tag.

## Bulk delete (`delete-selected`)

The destructive bulk-delete surface lives in the row-expander
(single or bulk), not a standalone Danger Zone card. The Delete
button is gated behind an "Allow delete" checkbox
(`name="confirm" value="true"`) and POSTs to
`/operator/sessions/delete-selected`.

### Submission

`POST /operator/sessions/delete-selected` with form fields:
`session_ids: list[int]` (one per ticked checkbox) +
`confirm: "true"`.

#### Server behaviour

1. **Confirm gate.** Without `confirm == "true"` the request is
   rejected with `400 Bad Request` (matches the single-session
   `/sessions/{id}/delete` handler).
2. **Per-id filter.** For each id, the handler:
   - calls `sessions.get_for_user(db, user, id)` — returns `None`
     when the caller isn't an operator on that session.
   - calls `lifecycle.is_editable(...)` — returns `False` for
     Activated and reserved-state sessions.
   - skips silently on either miss.
3. **Delete loop.** For each surviving session, calls
   `sessions.delete_session(...)`, which cascades reviewers /
   reviewees / instruments / assignments / invitations /
   email_outbox rows + writes a `session.deleted` audit row.
4. **Redirect.** 303 to `/operator/sessions` (the list reloads
   without the deleted rows).

#### Lifecycle eligibility

The current `lifecycle.is_editable` returns `True` for `draft` and
`validated` sessions; `ready` (Activated) and the reserved
`expired` / `archived` states are not deletable through this
surface. Non-eligible ticks are silently dropped — there is no
flash banner today. (If field feedback shows operators are
confused, layer a `?skipped=N` flash on top.)

## Behaviours

- **Form submission.** The expander's action buttons post the
  enclosing form (including every ticked checkbox); each button
  carries its own `formaction` to route to the right handler.
- **Empty submission.** Clicking Delete with zero rows ticked sends
  an empty `session_ids` list; the handler iterates zero times and
  303s back. Acceptable as a UX no-op.
- **Concurrent deletes.** Each session's delete is a separate
  service-layer commit; partial completion is tolerated. If the
  process is killed mid-batch, only the un-deleted sessions remain
  on the next reload.
- **Self-delete.** An operator deleting every session they own
  lands on the empty-state page after the redirect (the create CTA
  takes them to `/operator/sessions/new`).

## Out of scope

- Multi-operator session sharing UI (operator membership is
  currently set programmatically; there is no "Add operator"
  button on this page).
- Bulk export of session data — that lives on the per-session
  Extract Data card (Segment 12A).
- "Restore deleted session" — `delete_session` is a hard delete
  with a `session.deleted` audit row; no soft-delete, no undo.

## Implementation pointers

- **Route handlers** (`app/web/routes_operator/_lobby.py`):
  - `list_sessions` — GET `/operator/sessions`.
  - `archived_sessions` — GET `/operator/sessions/archived`.
  - `sessions_delete_selected` — POST `/operator/sessions/delete-selected`.
  - `sessions_archive_selected` — POST `/operator/sessions/archive-selected`.
  - `sessions_bulk_tags` — POST `/operator/sessions/bulk-tags`.
  - `sessions_unarchive_selected` — POST `/operator/sessions/unarchive-selected`.
  - `sessions_delete_archived_selected` — POST `/operator/sessions/delete-archived-selected`.
  - `lobby_edit_submit` — POST `/operator/sessions/{id}/lobby-edit`.
  - `clone_session_submit` — POST `/operator/sessions/{id}/clone`.
- **Templates:** `app/web/templates/operator/sessions_list.html`,
  `sessions_archived.html`.
- **Services:** `app/services/session_tags.py`,
  `app/services/session_clone.py`, `app/services/session_purge.py`.
- **Sort plumbing:** `views.decode_cookie_sort_spec` /
  `apply_cookie_sort` (cookies `rrw-sort-lobby` / `rrw-sort-archived`).
- **Service layer** (`app/services/sessions.py`):
  - `list_for_user(db, user)` — drives the table.
  - `get_for_user(db, user, session_id)` — per-id permission
    check inside the bulk-delete loop.
  - `delete_session(db, *, review_session, user, correlation_id)` —
    cascades dependent rows + writes the `session.deleted` audit
    event.
- **Lifecycle gate:** `app/services/session_lifecycle.is_editable`.
- **Tests:** `tests/integration/test_operator_sessions.py`,
  `tests/integration/test_chrome_breadcrumbs.py` (header /
  checkbox markup assertions).
