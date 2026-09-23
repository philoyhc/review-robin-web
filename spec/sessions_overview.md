# Sessions Overview page — functional spec

The operator's lobby. Lists every session the signed-in user is
an operator on, surfaces a one-click affordance for creating a new
session, and carries sortable columns, a tag filter, a search box,
per-row and bulk row-expanders for
rename / tag / clone / purge-and-archive / delete, and a sibling
archived-sessions child page.

> URL:
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
  `Sessions Lobby` (page H1).
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
│ ┌─ Sessions ─────────┐ ┌─ Filter ─────────────────┐ │
│ │ counts + tag chips │ │ [filter box + typeahead] │ │
│ │                    │ │ [Clear] [Add new         │ │
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
**Below 800px they stack, `Filter` under `Sessions`** — the app's
established two-column collapse point, shared with `.page-grid` and
`.bottom-grid`. Side by side on a narrow page the Filter card is the
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
  own line. **The header carries no button.** The page's one create
  affordance is the Filter card's `Add new session`, which renders in
  every state — see "Lobby states" below.

## Empty state — the first-run card

When the operator has **zero non-archived sessions**, the page
renders an onboarding card (`id="lobby-first-run"`) **below the
`Sessions` and `Filter` cards**, in place of the table and the
bulk-action form — the two cards render in every state, so this card
is never the whole page. See "Lobby states" below.

The card carries, in order:

1. **`You don't have any sessions yet`** — card `<h2>`, in the
   ordinary card-header style, no trailing period.
2. **A one-sentence definition of a session**, standing on its own
   directly under the header: *"A **session** is one review round
   with its own people, form, dates, and results."* It belongs to
   the card rather than to the first tile, because it is what all
   four tiles are about — and keeping it out of the tile lets the
   first tile open on an instruction like the other three.
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

   **Four tiles, not a numbered list.** A list is read
   top-to-bottom and its last item is read least; the stage an
   operator most wants reassurance about before committing is
   getting the data back out, so it must not be the one that
   trails off the bottom. Four tiles of equal width and equal
   height say "four ordinary stages" where a numbered list says
   the fourth is furthest away.

   Each tile is a table-of-contents entry for one `/guide`
   section; the card is not a second account of the workflow.
   **Three of the four headings match the Guide's verbatim** —
   "Prepare and activate", "Give reviewers access" and "Download
   responses". The one divergence is the first, and it is
   deliberate: the card is read by someone who has not yet made a
   session, so its tile says "Set up a session", while the Guide
   section it points at covers creating one as well and is headed
   "Create and set up a session". The pairing is pinned as an
   explicit mapping in
   `tests/integration/test_lobby_first_run_card.py`
   (`CARD_STEP_TO_GUIDE_SECTION`) rather than collapsed to a
   string comparison, so renaming a heading on either side without
   its partner still fails.
4. A muted line linking to
   **`/guide?return_to=/operator/sessions`**. This link is why the
   card exists: `/guide` is the canonical operator
   documentation, and the chrome link alone is easy to miss on a
   first visit. It is byte-identical to the chrome's own Guide
   link on this page, so tests distinguish the two by counting.

**The card has no CTA of its own.** It and the Filter card would
otherwise offer the same destination in the same state under two
different names, so the card **names** the Filter card's button rather
than competing with it — one way to start a session, one name for it.

The naming happens **once**, in the **Set up a session** tile, where it
belongs to the stage it describes. Repeating it in the muted line three
lines below is not emphasis.

Item 4's muted line also carries the **setup-template download**
(`GET /templates/starter.zip`) — four generic
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

**One create affordance in this state, and it is the Filter card's.**
`Add new session` stays active in the empty lobby on purpose — with
`Rehydrate` it is one of the two ways *out* of one — so the first-run
card must not carry a second button to the same place. A difference in
weight is not enough to stop two names for one action confusing a
first-time operator.

> **`Go to Archive` is unconditional, and must stay so.** It renders in
> every lobby state, including one holding nothing. Gate it on the
> populated branch and an operator who archives every session loses
> their only in-app route to `/operator/sessions/archived` — the
> `N archived` stats pill goes with it, and their sessions are still
> there and unreachable.
> `test_lobby_first_run_card.py::test_an_all_archived_lobby_keeps_the_route_to_the_archive`
> pins that state.

## Lobby states — one shape, three fillings

The `Sessions` and `Filter` cards render on **every** lobby, so an
operator learns one page rather than two — neither card belongs inside
the populated branch, where it would vanish with the table. What varies
is which Filter controls are live:

| Lobby holds | `Sessions` card | Filter box + Clear | `Add new session` · `Rehydrate` · `Go to Archive` |
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

The first-run card renders **below** the two cards whenever there
are no live sessions — including the only-archived case, per the
trigger above (zero non-archived, not "never had one").

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
- **Tags have four write surfaces, two of them off this page.** The
  lobby's two — the row expander's `{id}/lobby-edit` and the toolbar's
  `bulk-tags` — were the only ones until 19S Item 6 put a **Tags box on
  the Create page**, so a session can be born tagged, and 19S Item 9
  put a **Tags field on Session Home's details card**. The box, the
  field and the row expander all write through `session_tags.set_tags`,
  a whole-set replace, so none of them is additive — only the toolbar's
  `bulk-tags` is, through `add_tag` / `remove_tag`. **The surfaces are
  gated differently, deliberately**: the lobby edits tags in any
  lifecycle state, while Session Home's field rides the details card's
  edit window and `/config` refuses anything but draft and validated —
  the lobby stays the any-state surface. Where a create also carries a
  settings CSV, the typed box wins: `POST /operator/sessions` calls
  `set_tags` **after** the staged Quick Setup uploads, of which the
  settings bundle is the last — and on a *failed* upload too, so a
  bailed-out create does not silently discard what was typed.
  `spec/csv_contracts.md` § *Settings CSV — apply precedence*
  owns that rule, and both meanings of an empty box.
- **Purging unlinks the email outbox.** Both purge modes delete rows
  that `email_outbox` references — invitations under either, reviewers
  under `rosters` — so each clears those foreign keys before the delete
  and keeps the outbox rows, which are the email audit log.
  `spec/setup_pages.md` § *What a delete takes with it* owns that
  contract; `spec/email_infra_options.md` § *Audit log* owns the
  column-level detail.
- **The archived-sessions page has one panel, not two.** Its
  `archived-bulk-expander` `<template>` opens on **any** selection of one
  or more rows — the lobby's count-keyed switch between a single and a
  bulk template has no counterpart there, so a lone archived row gets the
  bulk panel. Its actions are Unselect all, Unarchive
  (`bulk-unarchive`), a **disabled** Download placeholder with no route
  behind it, and a Delete gated behind "Yes, delete"
  (`bulk-delete-archived`). Its heading is the bulk phrasing at every
  count, so one selected row reads *"1 sessions selected"*. Whether that
  wants singular copy or the lobby's second template is undecided and
  recorded in `guide/archive/new_ux_ideas.md` entry 2; the contract here is what
  ships.
- **Selected rows are marked.** Every selected row carries
  `session-row-selected`, styled in `base.html` as a **rail at each end
  and no fill** — `--selected-bg` as a 6px inset shadow on
  `td:first-child` and the mirror of it on `td:last-child`.
  Both rails are inset shadows rather than borders, so selecting a row
  does not change its height and reflow the table under the pointer.
  The bracket has no top or bottom cap for the same reason: caps would
  cost 4px of height on selection.

  **No fill.** A row fill resolves to the same primitives that back
  `.pill-count` and `.pill-info` — one rule under `body.ui-v2` — so it
  erases every pill the row carries, and a lobby row carries four to
  six of them (Created by, Created, Deadline, Timezone, one per tag)
  plus a Validated status pill. No replacement fill escapes the
  problem: the six pale pill fills occupy relative luminance
  0.810–0.914 against a 1.000 card, leaving no clearance above the band
  and only a too-dark clearance below. The rails carry the whole signal
  instead, at roughly 5.2 against the card in light and 4.9 in dark,
  where no fill in this palette reaches 2.6.

  **The panel closes the bracket.** The injected expander row carries
  `session-expander-bracketed`, which gives its single `colspan` cell
  both rails — the cell is first and last child at once — and fills it
  with `--selection-panel-bg`. The panel renders no pills, so the shade
  is safe there; see `.session-row-selected` in `spec/ui_elements.md`
  §10 Layout primitives for the pill-free-zone condition that creates.

  **The bracket is opt-in by class, never by `.session-expander`
  alone.** The archived-sessions page injects a panel carrying the same
  `session-expander` class names from its own script, so an unscoped
  rule would style both pages at once. Both pages must opt in —
  archived rows take the same `session-row-selected` marking from their
  own `refreshExpander()`, and the archived bulk panel carries the same
  opt-in class — so a selection brackets identically on each. *The two
  scripts stay separate on purpose — the archived page has **one** panel,
  the bulk one, for any selection; the lobby has two, a single-row
  template with editable fields and purge options and a bulk one — so the
  marking function is duplicated rather than shared.*

  The archived-sessions page has no section of its own in this spec, so
  its selection behaviour is recorded here rather than pointed at.

  The class is applied in `refreshExpander()`, which is the one funnel
  every selection path meets: a row tick, a select-all (which sets
  `checked` programmatically and fires no row events), and the
  expander's own Unselect-all / Unselect-others buttons (which fire
  synthetic ones). Each pass clears the class from every row before
  applying it to the selected set, so no un-tick can leave a stale mark.

  **No hydration is needed, which is a property of the page rather than
  an omission.** The tag filter and search hide rows with
  `style.display` rather than re-rendering them, so a filtered row keeps
  its checkbox state and its marking; and selection is not persisted
  (the lobby's only `localStorage` key is `rrw-lobby-tag-filter`), so a
  server re-render returns unchecked boxes and an unmarked table. If
  selection ever becomes restorable, the marking has to be restored with
  it.
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

The lobby carries all three:

- **Sortable columns.** The table is `data-rrw-sortable` with a
  per-column `rrw-sort-btn`; clicking a header sorts by that key.
  The chosen sort persists in the `rrw-sort-lobby` cookie (shared
  `rrw-sortable` primitive with the Setup preview tables), decoded
  server-side by `views.decode_cookie_sort_spec` /
  `apply_cookie_sort`. Default order is still `created_at DESC`.
  A sort with rows selected drops the injected panel and re-anchors
  it from the shared `rrw:sorted` signal (19O Item 4); the mechanism
  is in `spec/ui_elements.md` under `.session-row-selected`. Because
  the re-anchor rebuilds the panel from the row's rendered cells, and
  **this panel is editable**, a sort with an unsaved edit in it first
  asks *"Discard unsaved changes?"* — the same string Instruments and
  the Observers cohort editor use (`spec/setup_pages.md`
  § *The cohort rule builder*). Declining cancels the sort outright, so
  the panel, the edit and the row order are all left as they were.
- **Tag filter.** A `sessions-tag-filter` chip strip ("Show
  sessions tagged with:") with one `tag-chip` per tag in the
  lobby tag vocabulary, an AND/OR mode chip, and a clear chip.
  Client-side filtering against each row's `data-tags`.
**It is a filter, not a search** (author's ruling, 2026-09-19; 19O Item
7 entry 15). It hides rows already rendered, live on every keystroke,
and never queries or navigates — so there is nothing to submit and no
Search button is missing. Headed `Search` with a `Cancel` beside it
until that ruling, which is the shape the drawing above used to show.

**What it matches — per column, unioned.** A row is kept when *any* of
its columns matches:

| Column | Rule |
|---|---|
| Session name | substring, case-insensitive |
| Session code | substring, case-insensitive |
| Session tags | **whole value**, case- and surrounding-whitespace-insensitive |

The same three rules `spec/setup_pages.md` states for the roster and
operations filters, and for the same reasons: substring on a name makes
a partial name useful, whole value on a tag keeps `team a` from
dragging in `team a2`. Until 19O Item 7 entry 15 this concatenated the
three into one string and matched a substring of *that*, so the tag
rule did not hold here.

The rule is `rrwSessionFilterMatches` in `base.html`, shared with the
Archived page rather than copied to it, and executed — not merely
parsed — by `tests/integration/test_session_filter_rule.py`.

**What the typeahead offers.** A `<datalist>` of the distinct tag
values first, then the session names and codes, built by
`views.sessions_filter_options`. Tags lead because browsers filter a
`<datalist>` in document order. Two caps, kept separate so a long
session list cannot crowd the tags out: `SEARCH_TAG_OPTIONS_CAP` on the
tag half, `SESSIONS_DATALIST_CAP` on the session half — the latter
counted in **sessions**, each contributing up to two options, so a
capped session never keeps one spelling of its identity and loses the
other.

**Names and codes are offered as themselves**, not as the
`"Name (handle)"` label the roster surfaces use. That label works there
because the server exact-matches the parenthesized handle when the
input equals one it offered; a client-side per-column filter cannot,
so the label would be a suggestion that matches nothing. A value
offered as a tag is not offered again as a name or code.

**An empty result names the Archive.** The lobby is given non-archived
sessions only, so an empty filter is ambiguous between *no such
session* and *it is archived*. The no-match row says so and links
through. The Archived page does not reciprocate — its operator arrived
from the lobby, and its own empty-page copy already says where its rows
come from.

- **Filter.** A Filter card with a free-text input matching name,
  code, or tag. Its right-flushed `.sessions-action-buttons` row
  carries **Clear**, **Add new session**
  (`/operator/sessions/new` — the label names the noun, because the
  lobby is the one page where "new *what*" is not obvious from
  context), **Rehydrate** (`/operator/sessions/rehydrate`) — **gated off by
default**: `rehydrate_enabled` ships false, so the button does not render
and the route 404s in every lobby state, independently of the
state-dependence described above (`spec/rehydrate.md`), and **Go
  to Archive** (`/operator/sessions/archived`). Which of these are
  live depends on the lobby state — see "Lobby states" above. **Rehydrate** rebuilds a
  live draft session from a complete set of extract CSV files — see
  `spec/rehydrate.md`.

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
     `ready` (Activated), `expired` and `archived` sessions.
   - skips silently on either miss.
3. **Delete loop.** For each surviving session, calls
   `sessions.delete_session(...)`, which cascades reviewers /
   reviewees / instruments / assignments / invitations /
   email_outbox rows + writes a `session.deleted` audit row.
4. **Redirect.** 303 to `/operator/sessions` (the list reloads
   without the deleted rows).

#### Lifecycle eligibility

`lifecycle.is_editable` returns `True` for `draft` and `validated`
sessions; `ready` (Activated), `expired` and `archived` sessions are
not deletable through this surface. Non-eligible ticks are silently
dropped — there is no flash banner. (If field feedback shows operators
are confused, layer a `?skipped=N` flash on top.)

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
  Extract Setup card, on the Extract data Operations tab.
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
- **Lifecycle gate:** `is_editable` in `app/services/session_lifecycle.py`.
- **Tests:** `tests/integration/test_operator_sessions.py`,
  `tests/integration/test_chrome_breadcrumbs.py` (header /
  checkbox markup assertions).
