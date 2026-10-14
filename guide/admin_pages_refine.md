# Admin pages refine

**Opened:** 2026-10-14 · **Theme:** the Sys Admin pages, as the workspace
grows past its operators · **Related:** `spec/operator_ui_concept.md`,
`spec/permissions.md`, `spec/setup_pages.md` (the table this copies)

A standalone plan at the author's naming, shaped like
`guide/archive/participant_info.md`: items close independently, each with
its own `### Doc impact` and `### Status`, checked by hand at its close.

**Item close lines.** Each item's done list ends with these:
- `## Doc impact` section present and current
- Every `### Doc impact` bullet checked by hand against the diff (`tools/close_check.py` reads only `segment_*` ids)
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; the file stays in `guide/` until every item has closed, then moves to `guide/archive/` + index row

**Why now.** Every sign-in creates a `users` row (`get_or_create_user`,
`app/web/deps.py`), so Accounts' Workspace users table lists every
participant who ever opened a link, one row each under a one-row
toolbar, and `list_workspace_users` assumes "tens of users". The
author's target (2026-10-14) is **1,000 users signing in for one
review**. The model is the Setup pages' roster table (`spec/setup_pages.md`
"Preview tables", "The table toolbar", "The row expander"), with
category chips where the column chips sit and no `Add new`, which the
Invite by email card covers.

---

## Item 1 — Find an account: category chips, search, paging

### Opportunity

At 1,000 rows the table is unreadable and slow to render. It has no
search, no paging, and nothing separating the accounts an admin manages
from the ones sign-in created.

### Decision

The Workspace users card becomes a Setup-style preview table with the
two-pane toolbar (`.table-card-toolbar.is-split`).

**Left pane: four type 1 (on/off) chips** (`spec/ui_elements.md` "Five
chip types") where the Setup pages put column chips, then the pager and
the count line. The sets are disjoint, so every row is under one chip:

| Chip | Rows | Default |
|---|---|---|
| Operators (N) | operator, not admin | on |
| Admins (N) | admin or super-admin | on |
| No role (N) | neither, with history: Delete refused (`spec/permissions.md` §4.1) | off |
| Unused (N) | neither, no history (label: author, 2026-10-14) | off |

**Right pane: the filter strip**, in the roster pages' order: a
**Session role** dropdown where they put Status (`Any`, `Reviewer`,
`Reviewee`, `Observer`, `Owner`; what an account does in sessions,
which the chips can't say), a search box with a `<datalist>` typeahead
over email and name, then `Clear` (while a filter is active) and
`Search`.

**Filtering and paging run on the server**, as the roster pages' do:
hiding rows in the browser would still render all 1,000. Chips, role,
search and offset are query parameters; the pager reuses `build_pager`
and `_pager_cluster.html` at 200 rows a page.

Rejected: *Operators · Admin · All users* (the author's first shape),
because *All users* overlaps the others and lumps two no-role kinds;
browser-side filtering, which doesn't scale; the audit log's
checkbox-and-pill filter (author, 2026-10-14).

### Semantics

- **Admins win.** An admin has operator access whatever its Operator
  flag says (`require_operator` passes either flag; `promote` sets only
  `is_sys_admin`), so it sits only under Admins. Your own row too.
- **Counts are per chip over the whole table**, ignoring role and
  search. No chip on shows "No accounts match the chips above."
- **The pager stays under a filter**, unlike the roster pages' 500-row
  cap: a role can match all 1,000 (Codex on #3025). `?offset=` clamps.
- **A toolbar redirect keeps the view** (chips, role, search, offset). A
  `?selected=<id>` whose row the chips would hide turns its chip on for
  that load only.
- **Session role matches on email**, case-insensitive, in any session:
  a roster row, or for `Owner` a `session_operators` row.
- **Chip state lives in the URL**, defaulting to Operators and Admins.

### Blast radius (measured)

Taken 2026-10-14 at `871ba085`.

- `sys_admin_users.html`; `list_workspace_users` (`app/services/users.py:76`,
  all rows in Python); route `sys_admin_users` (`_sys_admin.py:220`).
  Reused: `build_pager`, `_pager_cluster.html`, `preview_count_line`.
- Session role reads three indexed email columns (`grep -n "index=True"
  app/db/models/{reviewer,reviewee,observer}.py`).
- `tests/integration/test_sys_admin_users.py` (55, `grep -c "def test_"`);
  no browser test (`grep -rln "sys-admin/users" tests/browser`).
- Scale unmeasured (`_users_with_history` reads every audit actor):
  timed at 1,000 and 5,000 before close, as `tools/bench_roster_scale.py`.

### Status

- **Rung 1** (2026-10-14): the route passes the chips (a template can't
  count; the rung said "touches no route") but no new parameter, and no
  pager: over a list still rendered whole it showed a false range (Codex
  on #3027). The item's cumulative read diffs from `adc01b08`.
- **Rung 2** (2026-10-14): the category rule moved to SQL in
  `app/services/account_listing.py`, which replaced
  `list_workspace_users`. Decided at build: a chip submits on change,
  while the role and search wait for `Search`; a blank `show` keeps
  "every chip off" distinct from the default; `Clear` keeps the chips;
  the count line shows only when one page holds everything, since the
  pager stays under a filter; a `?selected=` row lands on its own page.

### PR ladder

1. **Scaffold.** The two panes: four chips (real labels and counts),
   the dropdown, the search box and `Clear` / `Search`, all inert.
2. **Server-side filter and pager.** Chip, role, search and offset
   parameters; per-chip counts in SQL; the typeahead; the pager; the
   redirect keeping the view. The toolbar stays single-row.
3. **Measure and close.** Timed at 1,000 and 5,000 users with their
   audit rows; specs, a browser-check section, the item's read.

### Definition of done

- Accounts lists 200 rows a page, Operators and Admins by default, with
  the Session role dropdown and search over email and name.
- A browser test drives the chips, the dropdown, the search and the pager.
- The 1,000- and 5,000-user timings are recorded in this item's `Status`.
- The item close lines (top of this plan).

### Open questions

- ~~Dropdown~~: session roles; ~~fourth chip~~: *Unused*, not *Invited*,
  since an invite always makes an operator or admin (author, 2026-10-14).

### Out of scope

- Selection and row actions: Item 2. Deleting accounts with history
  stays refused (author, 2026-10-14).

### Doc impact

- `spec/operator_ui_concept.md` — the Accounts entry describes the chips, search and pager (Item 1).
- `spec/settings_inventory.md` — the URL parameters the Accounts table reads (Item 1).

---

## Item 2 — Act on accounts: selection and the row expander

### Opportunity

The toolbar acts on one row at a time above a table that will hold a
thousand. Clearing out unused accounts, or revoking a cohort of
operators, is one round trip per account.

### Decision

Selection works as on the roster pages: multi-select and the **row
expander** (`spec/setup_pages.md`), carrying the count and today's
actions, Delete behind its confirm tick. The toolbar is retired. **Only actionable controls render**, as with the roster pages'
Inactivate / Activate: a control shows only when it applies to every
selected row.

**Role controls follow the row's chip** (author, 2026-10-14):

| Chip | Role controls |
|---|---|
| Operators | Revoke, Promote |
| Admins | Demote; never Revoke, which flips a flag the admin flag already overrides |
| Admins (super-admin) | none: config sets the tier, and sign-in restores it |
| No role, Unused | Admit; no Promote, so an admin is made in two steps (a change from today) |

Promote and Demote need `can_manage_admins`. Remove from all sessions
and Delete keep today's gates (author, 2026-10-14): Delete needs no
sessions and no history, so it reaches Unused rows and never-used
operators and admins, never super-admins (Codex on #3028).

### Semantics

- **All or nothing** (author, 2026-10-14). One refusal refuses the
  batch, naming the row and the reason; nothing changes.
- **Guards judge the batch** (Codex on #3025, #3026). Per-row guards
  (`still_owner`, `has_history`, `protected_super_admin`, and a new
  `not_operator` refusing Promote on a row with no role) run on every
  row. Set-level ones run on the state after the batch: `last_admin`
  (two admins demoted or deleted together can't leave none) and
  `sole_owner` (two co-owners removed together can't orphan a shared
  session).
- **Each set-level check locks what it counts** (owner rows `FOR UPDATE`
  in id order, as `_lock_owner_rows`, §4.2; the sys-admin rows), else
  two concurrent batches both commit. A new batch service function.
- **One audit event per row,** under one correlation id.
- **Selection is page-local**; changing the chips or the page clears
  it. Your own row can't be selected, as today.

### Blast radius (measured)

Taken 2026-10-14 at `871ba085`.

- Six single-row POST routes in `_sys_admin.py`, each one `user_id`.
- `spec/permissions.md` §4.1, `docs/security_posture.md`,
  `spec/operator_button_audit.md` (row 117 and its neighbors).
- No lock in `app/services/users.py` (`grep -n "for_update"` → none).

### PR ladder

1. **Scaffold.** Checkboxes allow several rows; the expander renders
   beneath the selection with its count and controls, inert. The toolbar
   stays live.
2. **Bulk routes and the expander live.** The routes take a list of ids;
   the batch service locks, checks and applies all or nothing; the
   toolbar is retired. Specs, a browser-check section, the item's read.

### Definition of done

- Selecting several rows and revoking, demoting or deleting them is one
  request, refused whole when any guard refuses.
- A test shows two admins demoted in one batch refused by `last_admin`.
- A browser test drives a multi-row Revoke and a refused mixed Delete.
- The item close lines (top of this plan).

### Open questions

- ~~All or nothing?~~ Yes. ~~Promote from No role?~~ No. ~~Remove from
  all sessions on an admin?~~ Yes (author, 2026-10-14).

### Out of scope

- The single-row `demote` and `remove_from_all_sessions` count without a
  lock today, so two concurrent single-row actions can race the same
  way. It predates this plan; fixing it is its own change.

### Doc impact

- `spec/permissions.md` — §4.1 states the bulk actions, their all-or-nothing guards and the locks (Item 2).
- `spec/operator_button_audit.md` — the toolbar rows become expander rows (Item 2).
- `docs/security_posture.md` — the Accounts row no longer says "a single selected row" (Item 2).

---

## Item 3 — Invite card half width, a cycle chip, an Overview stub

### Opportunity

The Invite by email card spans the page for one field and a checkbox,
and nothing on Accounts summarizes the workspace (author, 2026-10-14).

### Decision

The Invite card takes the **left half** and a new **Overview** card the
right, at the same height: `.page-grid` (`spec/ui_elements.md` §10),
whose cells stretch, not `.bottom-grid`, which keeps natural heights.
Overview is a **stub**, a heading and one line saying what it will
hold, until its content is decided.

*Also invite as sys-admin* becomes a **cycle chip**, `Invite as
operator` ↔ `Invite as sys-admin` (every state a positive choice, so
always solid). The author called it type 2; by the "Five chip types"
table's order it is the third, cycle. It wraps the same
`invite_as_sys_admin` box, so the route and service don't change; it
renders only where `can_manage_admins`; `Cancel` resets it.

### Status

- **Rung 1** (2026-10-14): Overview wears `.card.placeholder`, the
  spec's scaffold treatment. The reads found `spec/ui_elements.md` and
  `spec/session_home.md` owed bullets (below).
- **Rung 1a** (2026-10-14, author): the chip and `Cancel` / `Invite` share
  one row, chip top-left, the pair flush right and wrapping as a unit
  (`.card-action-row` with a new `.card-action-lead`).

### PR ladder

1. **Layout, chip and stub.** The grid, the chip with its label script
   (on `change` and the form's `reset`), and the static Overview card.
   No route change.
2. **Overview content**, once decided.

### Definition of done

- The Invite and Overview cards sit side by side at equal height and
  stack below 800px.
- Ticking the chip posts `invite_as_sys_admin=true`, as the box did.
- The item close lines (top of this plan).

### Open questions

- **What Overview shows**: counts per kind of account, at least
  (author, 2026-10-14). Author decides before rung 2.

### Doc impact

- `spec/permissions.md` — rows naming *Also invite as sys-admin* name the chip (Item 3).
- `spec/operator_button_audit.md` — rows 112–113: Cancel before Invite, flush right beside the chip, and Cancel resets the chip, not a checkbox (Item 3).
- `docs/security_posture.md` — the invite guard names the chip (Item 3).
- `spec/operator_ui_concept.md` — the Accounts entry gains the Overview card (Item 3).
- `spec/ui_elements.md` — §10's `.page-grid` row lists Accounts (equal height, the author's ruling) and its `.card-action-row` row lists the invite card and `.card-action-lead`, §9's form-control chips list the invite chip, and §4's `.card.placeholder` note names Overview while it is a stub, one with no action button to disable (Item 3).
- `spec/session_home.md` — "Placeholder cards" no longer says no live page uses the class (Item 3).
