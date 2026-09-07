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
> `bulk-delete` / `bulk-archive` / `bulk-tags` /
> `bulk-unarchive` / `bulk-delete-archived` /
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
┌─ <h1>Sessions Lobby</h1> ───────────────────────────┐
│                                                     │
│ ┌─ Sessions ─────────┐ ┌─ Search ─────────────────┐ │
│ │ counts + tag chips │ │ [search box]             │ │
│ │                    │ │ [Cancel] [Add new        │ │
│ │                    │ │  session] [Rehydrate]    │ │
│ │                    │ │ [Go to Archive]          │ │
│ └────────────────────┘ └──────────────────────────┘ │
│                                                     │
│ ┌─ sessions table card (full width) ─────────────┐  │
│ │ Name | Code | Created by | … | Status | Tags | ☐ │  │
│ │ …  (ticking a row opens an inline expander)    │  │
│ └────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

The two half-width cards render in **every** state; the table is
replaced by the first-run card when there are no live sessions.
**Below 800px they stack, `Search` under `Sessions`** — the app's
established two-column collapse point, shared with `.page-grid` and
`.bottom-grid`. Side by side on a narrow page the Search card is the
one that suffers: its four buttons wrap into a ragged block and the
input shrinks to a stub. `Sessions` stays first because it is the
page's summary and the actions read as what you do about it.

The table sits inside a single `<form method="post">` so the
per-row checkboxes submit with whichever expander button the
operator clicks (each button carries its own `formaction`). The
destructive bulk actions live in the row-expander, not a separate
Danger Zone card.

## Header

- **`<h1>Sessions Lobby</h1>`** — page title, left-aligned, on its
  own line.

*(Until 2026-09-07 this was a flex strip pairing the title with a
right-aligned `Create new session` Primary, rendered only when at
least one session existed. Both the button and the strip are gone:
the create affordance is now the Search card's `Add new session`,
present in every state — see "Lobby states" below.)*

## Empty state — the first-run card

When the operator has **zero non-archived sessions**, the page
renders an onboarding card (`id="lobby-first-run"`) **below the
`Sessions` and `Search` cards**, in place of the table and the
bulk-action form. *(Before the 2026-09-07 standardisation the two
cards went with the table, so this card was the whole page. See
"Lobby states" below.)*

The card carries, in order:

1. **`You don't have any sessions yet`** — card `<h2>`, in the
   ordinary card-header style, no trailing period (2026-09-07).
2. **A one-sentence definition of a session**, standing on its own
   directly under the header: *"A **session** is one review round
   with its own people, form, dates, and results."* It sits here
   rather than inside the first tile (where it was until
   2026-09-07) because it is what all four tiles are about — it
   belongs to the card, not to stage one — and it lets the first
   tile open on an instruction like the other three.
3. The four stages of a session, as a `.subcard-row` of four
   equal-width **`.card.rs-help-card`** tiles (§10 and §4 of
   `spec/ui_elements.md`): **Set up a session**, **Prepare and
   activate**, **Give reviewers access**, **Download responses**.
   They carry the app's existing help-card look rather than one of
   their own — a row of tiles inside a card is explaining
   something, which is what those semantics already say.

   The row is `.stepped`, so a muted **`→`** sits between each pair:
   these are four stages in order, not four parallel options. Three
   arrows, never a trailing fourth. They are `aria-hidden` (reading
   order already carries the sequence) and hide below 900px, where
   the row wraps and a horizontal arrow would point at nothing.

   *Changed 2026-09-07 — was a three-item `<ol>`.* A list is read
   top-to-bottom and its last item is read least; the stage an
   operator most wants reassurance about before committing is
   getting the data back out, so it should not be the one that
   trails off the bottom. Four tiles of equal width and equal
   height say "four ordinary stages" where a numbered list says
   the fourth is furthest away. The fourth stage is new copy, not
   a re-cut of the three.

   Each tile is a table-of-contents entry for one `/guide`
   section; the card is not a second account of the workflow.
   The two sides no longer share headings **verbatim** — the card
   is read by someone who has not yet made a session and the Guide
   by someone already inside one, so "Set up a session" pairs with
   the Guide's "Create and set up a session", "Prepare and
   activate" with its "Prepare and launch" (the tile takes the
   lifecycle transition's own name, `Activate`, which is the word
   on the button the operator will press), and "Download
   responses" with the broader "Close, release, and share
   results". The pairing is pinned as an explicit mapping in
   `tests/integration/test_lobby_first_run_card.py`
   (`CARD_STEP_TO_GUIDE_SECTION`), so renaming a heading on either
   side without its partner still fails.
4. A muted line linking to
   **`/guide?return_to=/operator/sessions`**. This link is why the
   card exists (Segment 19E): `/guide` is the canonical operator
   documentation, and the chrome link alone is easy to miss on a
   first visit. It is byte-identical to the chrome's own Guide
   link on this page, so tests distinguish the two by counting.

**The card has no CTA of its own** (2026-09-07): standardisation
left it and the Search card offering the same destination in the same
state under two different names, so the card names that button rather
than competing with it — one way to start a session, one name for it.

The naming happens **once**, in the **Set up a session** tile, where it
belongs to the stage it describes. A closing sentence in the muted line
repeated it three lines later; that was removed the same day, because
saying it twice on one card is not emphasis.

Item 4's muted line also carries the **setup-template download**
(`GET /templates/starter.zip`, Segment 19E rung 4) — four generic
roster templates the operator can fill in before creating a
session. This card and the Guide card are the two surfaces that
render before any session exists, which is why both offer it;
contract in `spec/csv_contracts.md` §5a. The download therefore
leaves with the card: an operator who has a session gets templates
from the Guide.

**Trigger.** Emptiness of the template's `sessions` list — the
non-archived subset of `sessions.list_for_user` — **not** "has
never had a session". An operator who archives everything sees the
card again, which is intended: they are back at the start. No
"has-ever-had" state is tracked.

**Superseded 2026-09-07, twice, and the second time settles it.** The
rule was that this state shows a single create affordance. Standardising
the lobby broke it: the Search card's `Add new session` stays active in
the empty lobby on purpose — with `Rehydrate` it is one of the two ways
*out* of one — so the page briefly offered the same destination twice,
under two names, distinguished only by weight. Removing the first-run
card's own CTA restores the rule rather than abandoning it: **one create
affordance in this state, and it is the Search card's.** What the first
version got wrong was assuming a weight difference was enough to keep
two names for one action from confusing a first-time operator.

> **Known gap — closed 2026-09-07 by the standardisation below.**
> `Go to Archive` used to live in the Search card *inside the populated
> branch*, so an operator who archived every session lost their only
> in-app route to `/operator/sessions/archived`, and the `N archived`
> stats pill disappeared with it. Their sessions were still there and
> unreachable. Both cards now render in every state and the button is
> unconditional, so the count and the route survive.
> `test_lobby_first_run_card.py::test_an_all_archived_lobby_keeps_the_route_to_the_archive`
> pins the state that used to strand them.

## Lobby states — one shape, three fillings

**Standardised 2026-09-07.** The `Sessions` and `Search` cards render on
**every** lobby, so an operator learns one page rather than two. Before
this the whole two-card row sat inside the populated branch and vanished
with the table. What varies is which Search controls are live:

| Lobby holds | `Sessions` card | Search + Cancel | `Add new session` · `Rehydrate` · `Go to Archive` |
|---|---|---|---|
| Live sessions (± archived) | counts + tag filter | **active** | active |
| Nothing at all | counts, all `0` | **inert** | active |
| Only archived sessions | counts, `N archived` | **inert** | active |

The last two rows are the same shape by design — there is nothing live
to search in either — and they differ in what the counts say and in
whether `Go to Archive` leads anywhere populated. `Go to Archive` is
**always active**, including on a lobby holding nothing: an empty
archive page is a better answer than a dead control, and it is one fewer
rule to reason about.

**Inert controls render as `<span class="btn … disabled"
aria-disabled="true">`, not disabled anchors.** `a.btn.disabled` in
`base.html` sets `opacity: 0.5` and `cursor: not-allowed` but **not**
`pointer-events: none`, so a disabled anchor still navigates. A span
cannot be clicked or focused. Same shape as the reserved
`.nav-tab disabled` tabs in `spec/ui_elements.md` §6.

The first-run card still renders **below** the two cards whenever there
are no live sessions — including the only-archived case, per the rung 3
trigger (zero non-archived, not "never had one").

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
  Purge and archive (POST `bulk-archive`), and a Delete button
  gated behind a "Yes, delete" checkbox (POST `bulk-delete`).
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
  code, or tag. Its right-flushed `.sessions-action-buttons` row
  carries **Cancel**, **Add new session**
  (`/operator/sessions/new`; renamed from `Add new` 2026-09-07 —
  the lobby is the one page where "new *what*" is not obvious from
  context), **Rehydrate** (`/operator/sessions/rehydrate`), and **Go
  to Archive** (`/operator/sessions/archived`). Which of these are
  live depends on the lobby state — see "Lobby states" above. **Rehydrate** rebuilds a
  live draft session from a complete set of extract CSV files — see
  `spec/rehydrate.md` (Segment 18P Group 2).

## Bulk delete (`bulk-delete`)

The destructive bulk-delete surface lives in the row-expander
(single or bulk), not a standalone Danger Zone card. The Delete
button is gated behind a "Yes, delete" checkbox
(`name="confirm" value="true"`) and POSTs to
`/operator/sessions/bulk-delete`.

### Submission

`POST /operator/sessions/bulk-delete` with form fields:
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
  - `sessions_delete_selected` — POST `/operator/sessions/bulk-delete`.
  - `sessions_archive_selected` — POST `/operator/sessions/bulk-archive`.
  - `sessions_bulk_tags` — POST `/operator/sessions/bulk-tags`.
  - `sessions_unarchive_selected` — POST `/operator/sessions/bulk-unarchive`.
  - `sessions_delete_archived_selected` — POST `/operator/sessions/bulk-delete-archived`.
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
