# Admin pages refine

**Opened:** 2026-10-14 · **Theme:** the Sys Admin pages, as the workspace
grows past its operators · **Related:** `spec/operator_ui_concept.md`,
`spec/permissions.md`, `spec/setup_pages.md` (the table this copies)

A standalone plan at the author's naming, in the shape of
`guide/archive/participant_info.md`: items close independently, each with
its own `### Doc impact` and `### Status`, checked by hand at its close.

**Why now.** Every sign-in creates a `users` row (`get_or_create_user`,
`app/web/deps.py`), so Sys Admin → Accounts' Workspace users table lists
every participant who ever opened a link. It renders every row with a
one-row toolbar (`sys_admin_users.html`), and `list_workspace_users`
assumes "tens of users". The author's target (2026-10-14) is **1,000
users signing in for one review**.

**The analogy** (author, 2026-10-14): the Setup pages' roster table
(`spec/setup_pages.md` "Preview tables", "The table toolbar", "The row
expander"). Category chips sit where the column chips do. No `Add new`:
the Invite by email card covers it.

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
`Reviewee`, `Observer`, `Owner`. It answers what the chips can't: what
an account does in sessions (author, 2026-10-14). Then a search box with
a `<datalist>` typeahead over email and name, then `Clear` (only when a
filter is active) and `Search`.

**Filtering and paging run on the server**, as the roster pages' do. At
1,000 rows, hiding rows in the browser would still render them all. The
chips, role, search and offset are query parameters, and the pager
reuses `build_pager` (`app/web/views/_pager.py`) and `_pager_cluster.html`
at the roster pages' 200-row page size.

Rejected: the author's first shape, *Operators · Admin · All users*,
because *All users* overlaps the other two and lumps two no-role kinds
together; browser-side filtering (the first draft), because it doesn't
scale; and the audit log's checkbox-and-pill filter (author, 2026-10-14).

### Semantics

- **Admins win.** An admin has operator access whatever its Operator
  flag says (`require_operator` passes either flag; `promote` sets only
  `is_sys_admin`), so it sits only under Admins. Your own row follows
  its chip like any other.
- **Counts are per chip over the whole table** and ignore the role and
  the search, so a chip says what it would add.
- **No chip on** shows "No accounts match the chips above."
- **The pager stays under a search or role filter**, unlike the roster
  pages' 500-row cap, since a role filter can match all 1,000 accounts
  (Codex on #3025). `?offset=` is clamped, never rejected.
- **A toolbar redirect keeps the view:** same chips, role, search and
  offset. A `?selected=<id>` whose row the chips would hide turns that
  row's chip on for that load only.
- **Session role matches on email**, case-insensitive, in any session,
  live or archived: a roster row (`Reviewer.email`,
  `Reviewee.email_or_identifier`, `Observer.email`), or for `Owner` a
  `session_operators` row. One account can match several roles.
- **Chip state lives in the URL,** defaulting to Operators and Admins,
  so a reload or a shared link shows the same view.

### Blast radius (measured)

Taken 2026-10-14 at `871ba085`.

- **Template:** `app/web/templates/operator/sys_admin_users.html`.
- **Service:** `list_workspace_users` (`app/services/users.py:76`),
  which reads every row and every `session_operators` row in Python.
  **Route:** `sys_admin_users` (`app/web/routes_operator/_sys_admin.py:220`).
- **Reused as-is:** `build_pager`, `_pager_cluster.html`,
  `preview_count_line`.
- **Session role:** three roster tables, each with an indexed email
  column (`grep -n "index=True" app/db/models/{reviewer,reviewee,observer}.py`).
- **Tests:** `tests/integration/test_sys_admin_users.py` (55 tests,
  `grep -c "def test_"`); no browser test touches the page
  (`grep -rln "sys-admin/users" tests/browser` → none).
- **Scale:** unmeasured. `_users_with_history` reads every distinct
  audit actor, and the audit table grows with every save. This item
  measures Accounts at 1,000 and 5,000 users before it closes, as
  `tools/bench_roster_scale.py` does for the roster pages.

### Status

- **Rung 1** (2026-10-14): the route passes the chips, since a
  template can't count; the ladder said "touches no route". It reads no
  new parameter. The pager waits for rung 2: over a list that still
  renders whole, it showed a false range (Codex on #3027). The chip rule is `app/web/views/_accounts.py`.
  The item's cumulative read diffs from `adc01b08`.

### PR ladder

1. **Scaffold.** The toolbar's two panes with the four chips (real
   labels and counts), the dropdown, the pager, the search box and
   `Clear` / `Search`, all inert. Touches no route.
2. **Server-side filter and pager.** Chip, role, search and offset
   parameters; per-chip counts in SQL; the typeahead; the redirect
   keeping the view. The toolbar stays, still single-row.
3. **Measure and close.** Accounts timed at 1,000 and 5,000 users with
   their audit rows, fixing what the numbers show. Specs, a
   browser-check section, and the item's `diff-reviewer` read.

### Definition of done

- Accounts lists 200 rows a page, Operators and Admins by default, with
  the Session role dropdown and search over email and name.
- A browser test drives the chips, the dropdown, the search and the pager.
- The 1,000- and 5,000-user timings are recorded in this item's `Status`.
- `## Doc impact` section present and current
- Every `### Doc impact` bullet checked by hand against the diff (`tools/close_check.py` reads only `segment_*` ids)
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; the file stays in `guide/` (an item close does not archive it)

### Open questions

- ~~Type of user dropdown~~: session roles (author, 2026-10-14).
- ~~Fourth chip's label~~: *Unused* (author, 2026-10-14); *Invited*
  doesn't fit, since an invite always creates an operator or admin row.

### Out of scope

- Selection and row actions: Item 2.
- Deleting accounts with history stays refused (author, 2026-10-14).

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

Selection works as on the roster pages: a checkbox per row, multi-select,
and the **row expander** injected beneath the selected row
(`spec/setup_pages.md` "The row expander"). It carries the selected
count and today's toolbar actions: Admit / Revoke, Promote / Demote
(where `can_manage_admins`), Remove from all sessions, and Delete behind
its confirm tick. The toolbar is retired. **Only actionable controls
render**, as with the roster pages' Inactivate / Activate: a control
shows only when it applies to every selected row.

**Role controls follow the row's chip** (author, 2026-10-14):

| Chip | Role controls |
|---|---|
| Operators | Revoke, Promote |
| Admins | Demote; never Revoke, which flips a flag the admin flag already overrides |
| Admins (super-admin) | none: config sets the tier, and sign-in restores it |
| No role, Unused | Admit; no Promote, so an admin is made in two steps (a change from today) |

Promote and Demote still need `can_manage_admins`. Remove from all
sessions and Delete keep today's gates, admins included (Delete: Unused
only; author, 2026-10-14).

### Semantics

- **All or nothing** (author, 2026-10-14). One refusal refuses the
  batch, naming the row and the reason, and nothing changes.
- **Guards judge the batch, not each row alone** (Codex on #3025 and
  #3026). Per-row guards (`still_owner`, `has_history`,
  `protected_super_admin`, and a new `not_operator` refusing Promote on
  a row with no role) run on every row. The set-level ones run
  against the state after the whole batch:
  - `last_admin`: two admins demoted or deleted together can't leave
    none;
  - `sole_owner`: two co-owners removed together can't orphan a session
    they share.

  Each check first **locks what it counts**: the affected sessions'
  owner rows `FOR UPDATE` in id order (as `_lock_owner_rows` does for
  Remove owner, `spec/permissions.md` §4.2), and the sys-admin rows for
  `last_admin`. Without the lock, two concurrent batches each see the
  other's target still present, and both commit. A new batch service
  function does this; the single-row functions stay.
- **One audit event per row,** under one correlation id.
- **Selection is page-local,** and changing the chips or the page clears
  it. Your own row can't be selected, as today.

### Blast radius (measured)

Taken 2026-10-14 at `871ba085`.

- Six single-row POST routes in `app/web/routes_operator/_sys_admin.py`
  (admit, revoke, promote, demote, remove-from-sessions, delete), each
  taking one `user_id`.
- `spec/permissions.md` §4.1; `docs/security_posture.md` (its row says
  "a single selected row and its own button"); `spec/operator_button_audit.md`
  (row 117 and its neighbours).
- No lock today in `app/services/users.py` (`grep -n "for_update"` →
  none); `app/services/session_owners.py` has `_lock_owner_rows`.

### PR ladder

1. **Scaffold.** Checkboxes allow several rows, and the expander renders
   beneath the selection with its count and controls, inert. The toolbar
   stays live.
2. **Bulk routes and the expander live.** The routes take a list of ids;
   the batch service locks, checks and applies all or nothing; the
   toolbar is retired. Specs, a browser-check section, and the item's
   `diff-reviewer` read.

### Definition of done

- Selecting several rows and revoking, demoting or deleting them is one
  request, refused whole when any guard refuses.
- A test shows two admins demoted in one batch refused by `last_admin`.
- A browser test drives a multi-row Revoke and a refused mixed Delete.
- `## Doc impact` section present and current
- Every `### Doc impact` bullet checked by hand against the diff (`tools/close_check.py` reads only `segment_*` ids)
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; with every item closed, plan moved to `guide/archive/` + index row

### Open questions

- ~~All or nothing?~~ All or nothing (author, 2026-10-14).
- ~~Promote straight from No role / Unused?~~ No (author, 2026-10-14).
- ~~Remove from all sessions on an admin?~~ Yes, as today (author,
  2026-10-14).

### Out of scope

- `Add new`: the Invite by email card covers it (author, 2026-10-14).
- The single-row `demote` and `remove_from_all_sessions` count without a
  lock today, so two concurrent single-row actions can race the same
  way. It predates this plan; fixing it is its own change.

### Doc impact

- `spec/permissions.md` — §4.1 states the bulk actions, their all-or-nothing guards and the locks (Item 2).
- `spec/operator_button_audit.md` — the toolbar rows become expander rows (Item 2).
- `docs/security_posture.md` — the Accounts row no longer says "a single selected row" (Item 2).
