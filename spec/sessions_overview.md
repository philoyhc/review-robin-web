# Sessions Overview page — functional spec

The operator's lobby. Lists every session the signed-in user is
an operator on, surfaces a one-click affordance for creating a new
session, and provides a Danger Zone card for bulk-deleting drafts.

> Status: shipped. URL: `GET /operator/sessions`. Template:
> `app/web/templates/operator/sessions_list.html`. Bulk-delete
> handler: `POST /operator/sessions/delete-selected`.

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

A two-section page, single column:

```
┌─ <h1>Sessions</h1>          [ Create new session ] ┐  ← header strip
│                                                     │
│ ┌─ sessions table card (full width) ─────────────┐  │
│ │ Name | Code | Deadline | Created by | … |  ☐  │  │
│ │ …                                              │  │
│ └────────────────────────────────────────────────┘  │
│                                                     │
│                       ┌─ Danger Zone (½ width) ──┐  │
│                       │ Delete selected sessions │  │
│                       └──────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

The table and the Danger Zone card sit inside a single
`<form method="post">` so the per-row checkboxes submit with the
Danger Zone's destructive button. The Danger Zone is right-aligned
at half page width (`max-width: 50%; margin-left: auto;`); the
left half stays visually empty.

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

| # | Column | Source | Display |
|---|---|---|---|
| 1 | **Session Name** | `session.name` | `<a href="/operator/sessions/{id}">{name}</a>` — clicking the name lands the operator on Session Home. |
| 2 | **Session Code** | `session.code` | Inline `<code>` tag. |
| 3 | **Deadline** | `session.deadline` | `<span class="pill pill-info">{iso}</span>` when set, `<span class="muted">No deadline</span>` otherwise. ISO 8601 format. |
| 4 | **Created by** | `session.created_by_user.display_name` (falls back to `.email`) | Plain text. |
| 5 | **Created** | `session.created_at` | `YYYY-MM-DD`. |
| 6 | **Last Modified** | `session.updated_at` | `YYYY-MM-DD`. |
| 7 | *(unlabelled)* | `session.id` | Bulk-action select-row checkbox. |

The trailing column has `class="col-shrink"` (auto-narrow CSS).

### Row affordances

- **Name link** is the canonical row-click target. There is **no**
  per-row Delete button or Access button — both were retired in
  Segment 11D's lobby polish in favour of the bulk-delete path.
- **Select-row checkbox** carries:
  - `name="session_ids"` (array semantics — every ticked row
    submits its id)
  - `value="{{ session.id }}"`
  - `class="sessions-list-select-row"`
  - `aria-label="Select {name}"`

  Submitting the form with zero ticks is allowed — the bulk-delete
  handler 303-redirects back to the page as a no-op.

### Sort / filter / search

Out of scope. Sessions render in `created_at DESC` order; there's
no header-click sort, no search box, and no per-status filter.
Operators with many sessions are expected to navigate via the URL
bar / browser history. (Revisit if field feedback shows a
search/filter row helps.)

## Danger Zone card (bulk delete)

Sits below the table at half page width, right-aligned. CSS:
`max-width: 50%; margin-left: auto;`. Class: `card danger-zone`.
DOM id: `sessions-list-danger-zone`.

### Body

- **`<h2>Danger Zone</h2>`** at the top.
- A `form-help` paragraph explaining the destructive scope:
  > Tick the rows above, then submit here to delete the selected
  > sessions. Only draft sessions are eligible — anything Activated
  > stays in place. Each delete also removes its reviewers,
  > reviewees, instruments, assignments, invitations, and email
  > outbox rows.
- A confirm checkbox (`name="confirm" value="true" required`):
  > Yes, delete the selected sessions and all their data.
- A destructive submit button:
  > **[ Delete selected sessions ]** (`btn destructive`, `type="submit"`).

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

- **Form submission.** Browser-native — no JS dependency. The
  Danger Zone's submit button posts the entire form, including all
  ticked checkboxes inside the table card.
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

- Sort / filter / search affordances on the table.
- Per-row inline rename / edit (operators go to Session Home for
  that).
- Multi-operator session sharing UI (operator membership is
  currently set programmatically; there is no "Add operator"
  button on this page).
- Bulk export of session data — that lives on the per-session
  Extract Data card (Segment 12A).
- "Restore deleted session" — `delete_session` is a hard delete
  with a `session.deleted` audit row; no soft-delete, no undo.

## Implementation pointers

- **Route handlers** (`app/web/routes_operator.py`):
  - `list_sessions` — GET `/operator/sessions`.
  - `sessions_delete_selected` — POST `/operator/sessions/delete-selected`.
- **Template:** `app/web/templates/operator/sessions_list.html`.
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
