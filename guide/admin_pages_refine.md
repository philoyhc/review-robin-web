# Admin pages refine

**Opened:** 2026-10-14 · **Theme:** the Sys Admin pages, as the workspace
grows past its operators · **Related:** `spec/operator_ui_concept.md`,
`spec/permissions.md`, `spec/setup_pages.md` (the table this copies)

A standalone plan at the author's naming, not a `segment_*.md`, in the
shape of `guide/archive/participant_info.md`: items close independently,
each with its own `### Doc impact` and `### Status`. `tools/close_check.py`
reads only `segment_*` files, so an item's `Doc impact` is checked by
hand at its close.

**Why now.** Every person who signs in gets a `users` row
(`get_or_create_user`, `app/web/deps.py`), and the reviewer, reviewee
and observer pages sign people in. So Sys Admin → Accounts' Workspace
users table lists every participant who ever opened a link. Today it
renders every row in one table, with a one-row toolbar
(`sys_admin_users.html`), and `list_workspace_users` says it assumes
"tens of users". The author's target (2026-10-14) is **1,000 users
signing in for one review**.

**The analogy** (author, 2026-10-14): the Setup pages' roster table,
`spec/setup_pages.md` "Preview tables", "The table toolbar", "The row
expander". The four category chips go where the column chips sit, with
a filter strip, paging, and selection opening a row expander. There is
no `Add new`: the Invite by email card covers it.

---

## Item 1 — Find an account: category chips, search, paging

### Opportunity

At 1,000 rows the table is unreadable and slow to render. An admin
looking for one operator scrolls past every participant. It has no
search, no paging, and nothing separating the accounts an admin manages
from the ones sign-in created.

### Decision

The Workspace users card becomes a Setup-style preview table with the
two-pane toolbar (`.table-card-toolbar.is-split`).

**Left pane: four type 1 (on/off) chips** (`spec/ui_elements.md` "Five
chip types") where the Setup pages put their column chips. The pager
cluster and the count line follow them. The four sets are disjoint, so
every row is under exactly one chip:

| Chip | Rows | Default |
|---|---|---|
| Operators (N) | operator, not admin | on |
| Admins (N) | admin or super-admin | on |
| No role (N) | neither, with history: Delete refused (`spec/permissions.md` §4.1) | off |
| Unused (N) | neither, no history: Delete allowed (label: author, 2026-10-14) | off |

**Right pane: the filter strip**, in the roster pages' order. First a
**Session role** dropdown (where they put Status): `Any`, `Reviewer`,
`Reviewee`, `Observer`, `Owner`. Then a search box with a `<datalist>`
typeahead over email and name, then `Clear` (only when a filter is
active) and `Search`. The dropdown answers what the chips can't: what an
account does in sessions (author, 2026-10-14).

**Filtering and paging run on the server**, as the roster pages' do.
At 1,000 rows, hiding rows in the browser would still render them all.
The chips, search and offset are query parameters, and the pager reuses
`build_pager` (`app/web/views/_pager.py`) and `_pager_cluster.html` at
the roster pages' 200-row page size.

Rejected alternatives:
- **The author's first shape, *Operators · Admin · All users*:** *All
  users* overlaps the other two and lumps two no-role kinds an admin
  treats differently.
- **Browser-side filtering** (this plan's first draft): it doesn't scale.
- **The audit log's checkbox-and-pill filter:** the author chose type
  1 chips instead (2026-10-14).

### Semantics

- **Admins win.** An admin has operator access whatever its Operator
  flag says (`require_operator` passes either flag; `promote` sets only
  `is_sys_admin`), so it sits only under Admins. Your own row follows
  its chip like any other.
- **Counts are per chip over the whole table** and ignore the search,
  so a chip says what it would add.
- **No chip on** shows the empty state, "No accounts match the chips
  above."
- **The pager stays while a search or role filter is active**, unlike
  the roster pages, which drop it and cap a filtered view at 500. A role
  filter can match all 1,000 accounts, and a cap would leave half of them
  out of reach (Codex on #3025). It pages the filtered set, and the count
  line says what the filter matched. `?offset=` is clamped, never
  rejected.
- **A toolbar redirect keeps the view.** It returns to the same chips,
  search and offset. A `?selected=<id>` whose row the chips would hide
  turns that row's chip on for that load only, so an action never makes
  its own result vanish.
- **Session role matches on email**, case-insensitive, in any session,
  live or archived. `Reviewer`, `Reviewee` and `Observer` mean a row on
  that roster (`Reviewer.email`, `Reviewee.email_or_identifier`,
  `Observer.email`); `Owner` means a `session_operators` row. One account
  can match several roles. The dropdown narrows the chips; it doesn't
  replace them, and the chip counts ignore it as they ignore the search.
- **Chip state lives in the URL,** with Operators and Admins as the
  default when no chip parameter is given. A reload or a shared link
  shows the same view.

### Blast radius (measured)

Taken 2026-10-14 at `871ba085`.

- **Template:** `app/web/templates/operator/sys_admin_users.html`, one
  table.
- **Service:** `list_workspace_users` (`app/services/users.py:76`),
  which today reads every row and every `session_operators` row in
  Python. **Route:** `sys_admin_users` (`app/web/routes_operator/_sys_admin.py:220`).
- **Reused as-is:** `build_pager`, `_pager_cluster.html`,
  `preview_count_line`.
- **Session role:** three roster tables, matched by email, each with an
  indexed email column (`grep -n "index=True" app/db/models/{reviewer,reviewee,observer}.py`).
- **Tests:** `tests/integration/test_sys_admin_users.py` (55 tests,
  `grep -c "def test_"`). No browser test touches the page
  (`grep -rln "sys-admin/users" tests/browser` → none).
- **Scale:** unmeasured. `_users_with_history` reads every distinct
  audit actor, and the audit table grows with every save.
  `tools/bench_roster_scale.py` measures the roster pages; this item
  measures Accounts at 1,000 and 5,000 users before it closes.

### PR ladder

1. **Scaffold.** The toolbar's two panes with the four chips (real
   labels and counts), the pager, the search box and `Clear` / `Search`,
   all inert. The table still lists every row. Touches no route.
2. **Server-side filter and pager.** Chip, search and offset
   parameters; per-chip counts in SQL; the typeahead; the redirect
   keeping the view. The current toolbar stays, still single-row.
3. **Measure and close.** Accounts timed at 1,000 and 5,000 users with
   their audit rows, fixing what the numbers show. Specs and a
   browser-check section. Last build rung: takes the item's
   `diff-reviewer` read.

### Definition of done

- Accounts lists 200 rows a page, Operators and Admins by default, with
  search over email and name and the Session role dropdown.
- A browser test drives the chips, the dropdown, the search and the pager.
- The 1,000- and 5,000-user timings are recorded in this item's `Status`.
- `## Doc impact` section present and current
- Every `### Doc impact` bullet checked by hand against the diff (`tools/close_check.py` reads only `segment_*` ids)
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; the file stays in `guide/` (an item close does not archive it)

### Open questions

- ~~What the *Type of user* dropdown filters~~: session roles (any /
  reviewer / reviewee / observer / owner), author, 2026-10-14.
- ~~The fourth chip's label~~: *Unused*, author, 2026-10-14. *Invited*
  didn't fit, since an invite always creates an operator or admin row.

### Out of scope

- Selection and row actions: Item 2.
- Deleting accounts with history stays refused (author, 2026-10-14:
  leave Alice as is).

### Doc impact

- `spec/operator_ui_concept.md` — the Accounts entry describes the chips, search and pager (Item 1).
- `spec/settings_inventory.md` — the URL parameters the Accounts table reads (Item 1).

---

## Item 2 — Act on accounts: selection and the row expander

### Opportunity

The toolbar acts on one row at a time and sits above a table that will
hold a thousand. Clearing out unused accounts, or revoking a cohort of
operators, is one round trip per account.

### Decision

Selection works as on the roster pages: a checkbox per row, multi-select,
and the **row expander** injected beneath the selected row
(`spec/setup_pages.md` "The row expander"). The expander carries the
selected count and the actions the current toolbar has: Admit / Revoke,
Promote / Demote (where `can_manage_admins`), Remove from all sessions,
and Delete behind its confirm tick. The toolbar is retired.

**Only actionable controls render**, as with the roster pages'
Inactivate / Activate. For example, Revoke shows only when every
selected row is an operator. Delete is live only when every selected
row passes its guards.

### Semantics

- **All or nothing** (author, 2026-10-14). One refusal refuses the
  batch, naming the row and the reason, and nothing changes. This matches
  Quick Setup's "files uploaded together land together".
- **Guards judge the batch, not each row alone** (Codex on #3025).
  Per-row guards (`still_owner`, `has_history`, `protected_super_admin`)
  run on every row. Set-level invariants run against the state *after*
  the whole batch, in one transaction:
  - `last_admin`: demoting or deleting two admins can't leave none;
  - `sole_owner`: removing two co-owners from all sessions can't
    orphan a session they share.

  A new service function applies the batch and checks it before commit.
  The single-row functions stay as they are.
- **One audit event per row,** under one correlation id, so the log
  still reads per account.
- **Selection is page-local,** as on the roster pages, and changing the
  chips or the page clears it.
- **Your own row can't be selected,** as today.

### Blast radius (measured)

Taken 2026-10-14 at `871ba085`.

- Five single-row POST routes in `app/web/routes_operator/_sys_admin.py`
  (admit, revoke, promote, demote, remove-from-sessions) plus delete.
  Each takes one `user_id`.
- `spec/permissions.md` §4.1 and `docs/security_posture.md` (its row
  says "a single selected row and its own button").
- `spec/operator_button_audit.md` lists the toolbar's buttons
  (row 117 and its neighbours).

### PR ladder

1. **Scaffold.** Checkboxes allow several rows, and the expander
   renders beneath the selection with its count and controls, inert.
   The toolbar stays live.
2. **Bulk routes and the expander live.** The routes take a list of
   ids with all-or-nothing guards, and the toolbar is retired. Specs,
   a browser-check section, and the item's `diff-reviewer` read.

### Definition of done

- Selecting several rows and revoking, demoting or deleting them is one
  request, refused whole when any row's guard refuses.
- A browser test drives a multi-row Revoke and a refused mixed Delete.
- `## Doc impact` section present and current
- Every `### Doc impact` bullet checked by hand against the diff (`tools/close_check.py` reads only `segment_*` ids)
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; with every item closed, plan moved to `guide/archive/` + index row

### Open questions

- ~~All or nothing, or apply where allowed?~~ All or nothing, author,
  2026-10-14.

### Out of scope

- `Add new`: the Invite by email card covers it (author, 2026-10-14).

### Doc impact

- `spec/permissions.md` — §4.1 states the bulk actions and their all-or-nothing guards (Item 2).
- `spec/operator_button_audit.md` — the toolbar rows become expander rows (Item 2).
- `docs/security_posture.md` — the Accounts row no longer says "a single selected row" (Item 2).
