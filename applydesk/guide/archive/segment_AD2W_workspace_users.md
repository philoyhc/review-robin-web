# Segment AD2W — Workspace users on Accounts Management

**Opened:** 2026-11-21 · **Theme:** Admin → Accounts Management's table as Review Robin's *Workspace users* · **Related:** `applydesk/guide/archive/segment_AD2A_foundations.md`, `applydesk/spec/applications.md`

## Opportunity

AD2A shipped Accounts Management's list as *Operators*: only people on the operator list, each with a *Revoke* button, the super-admin pinned as *(self)*. The author's browser check (2026-11-21) asked for Review Robin's table (`app/web/templates/operator/sys_admin_users.html`): everyone on record, filtered by chips and a role, ticked rows acted on together. Apply Desk's list hides everyone else on record (pending people, the revoked, Owners not on the list), and its per-row button doesn't scale past a handful.

## Decision

The card becomes **Workspace users**, laid out as Review Robin's (the author's rulings, 2026-11-21):

- **Above the table, two panes.** Left: the title *Workspace users* and *Show:* chips, *Operators*, *Admins*, *No role*, *Unused*, each with its count. Right: an *Exercise role* dropdown and a search box on one row, *Search* below.
- **Columns:** a checkbox (*(self)* in its place on the super-admin's row), *Email*, *Name*, *Unit*, *First sign-in*, *Operator*, *Admin*.
- **Ticked rows, one bar:** *Admit* and *Revoke* act on every ticked row, each audited as now. The per-row *Revoke* goes.
- **Unit and Admin are mostly dashes for now.** Apply Desk has neither a per-person Unit nor an Admin tier. *Unit* shows the institution's top line as a default pill for an operator, else blank. *Admin* shows *Super-admin* for the super-admin, else *no*. The *Admins* chip counts the super-admin.
- **Chips:**
  - *Operators*: on the list.
  - *Admins*: the super-admin.
  - *No role*: neither, with a history (ever admitted, or holding or having held an exercise grant).
  - *Unused*: none of that.

  *Operators* and *Admins* are on by default, as Review Robin's are.
- **Exercise role:** *Any*, *Owner of an exercise*, *Operator of an exercise*, *No exercise*.

- **The *Add an operator* card as Review Robin's *Invite by email*** (the author, 2026-11-21): one *Name or email* box that offers matches as you type, people on record first, then the institution's directory through Graph; *Cancel* and *Add* on the row below it. No *Search* button and no results table.

Rejected: keeping the per-row *Revoke* beside the checkboxes. Two ways to do one thing, and Review Robin retired its single-row toolbar for the bulk bar.

## Semantics

- **The super-admin's row is identity, not a list entry** (as AD2A's *(self)*). It shows under *Admins*. If they have a person row, that row shows once, marked *(self)*, never tickable. The server refuses them in a bulk post too (`said=self`).
- **Bulk admit and revoke:**
  - Each ticked person goes through `operators.admit` / `revoke` in one transaction.
  - A refusal for one person (already listed, not listed, self, gone) skips that person, not the batch.
  - The status line counts what changed and what was skipped.
  - A lost race is "changed", as now.
- **No `show` at all** means the default chips. An empty `show` means none, so the table says nothing matches.
- **Search** matches email or name, as the list's search does now.
- **First sign-in** is when the person was bound. A pending person shows *Not yet signed in*.

## Judgment calls — decided

- Unit shows the workspace default as a pill, not an editable field: Apply Desk has no Unit to set yet (author, 2026-11-21).
- The Accounts Overview card keeps its counts; the chips carry the per-category counts beside the table.

## Blast radius (measured)

Taken 2026-11-21 at `2ae5bd646`.

| What | Count | Command |
|---|---|---|
| Modules reaching the list | 1 (`routes_admin.py`) | `grep -rln "admin/operators\|allowlist\." applydesk --include=*.py` |
| Templates | 2 (`admin/operators.html`, `base.html`) | `grep -rln "admin/operators" applydesk/templates` |
| Specs | 2 (`applications.md`, `architecture.md`) | `grep -rln "Accounts Management\|admin/operators" applydesk/spec` |
| Test files | 4; `test_operator_list.py` holds 9 tests | the first command, `--include=test_*.py` |

## Status

Closed 2026-11-21. Intended versus done:

- **The ladder held**, as #4119 (plan), #4120 (scaffold), #4121 (chips, role, search), #4122 (the Add card) and #4123 (the bulk bar). One addition: the author asked mid-build for the Add card as Review Robin's *Invite by email*, which became rung 4.
- **A column the plan did not foresee:** *First sign-in* needed its own record, because a directory pick is bound before it ever signs in. `person.first_signed_in_at` (migration `ad2w1firstsignin`) is stamped once at the first sign-in and audited as `person.signed_in`. Existing rows take their own sign-in binding.
- **Codex at rungs 3 and 4:**
  - the stamp audited;
  - the backfill limited to a person's own binding;
  - repeated suggestion labels numbered;
  - listed people left out before the search's limit.
- **One cumulative cold read at rung 5**, from `2ae5bd646`. Nothing blocking was found. Fixed:
  - the Overview's count;
  - the bulk bar keeping the view;
  - the 1,000 cap and ID order;
  - *Unit* for operators only;
  - the per-row Revoke route, with no caller left, removed.
- **Decided at build:**
  - *No role* includes anyone who ever acted, as Review Robin's history rule, so only someone who never signed in is *Unused*;
  - the chips are checkbox labels, so they submit without script.
- **Owed:** the author's browser check of the finished page.

## PR ladder

1. **PR 1 — this plan.**
2. **PR 2 — scaffold.** Lands the two-pane toolbar, the new columns over everyone on record, the checkbox column and the bulk bar. Chips, role, search and the bar are inert, with "… is not built yet". Rows are real; the per-row *Revoke* stays until PR 4. Must not touch `operators.py`.
3. **PR 3 — chips, role and search wired.** Adds `allowlist.accounts(…)` (a category per person, the counts, the role filter) and a view of rows.
4. **PR 4 — the Add card as Review Robin's.** A JSON suggestions route under `/admin/` (the super-admin's), the typeahead box, *Cancel* and *Add*; *Add* admits the person picked, as *Admit* does now. Replaces a working card, so it lands wired, not as a scaffold.
5. **PR 5 — the bulk bar wired.** Bulk *Admit* / *Revoke*, the self refusal, the status line; the per-row *Revoke* removed. Cumulative cold read from PR 2's base.
6. **PR 6 — close.**

## Definition of done

- Accounts Management's table shows the seven columns over everyone on record; the chips and *Exercise role* filter it; search matches email or name (`test_operator_list.py`).
- *Add an operator* suggests on-record and directory matches as one types and admits the pick with *Add*; *Cancel* clears it (`test_operator_list.py`, a browser test).
- Bulk *Admit* / *Revoke* change each ticked row once, audited, skipping refusals; the super-admin's row cannot be ticked or acted on (`test_operator_list.py`).
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD2W` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

None open. The author settled the columns, the bulk bar, Unit and Admin, and the chips on 2026-11-21.

## Out of scope

- A per-person Unit and an Admin tier: Apply Desk has neither; a later segment may add them.
- Review Robin's invite of an address the directory does not hold: *Add* takes a pick, as *Admit* does now.
- Review Robin's other bulk actions (*Promote*, *Demote*, *Set unit*, *Delete*, *Remove from all sessions*): no counterpart yet.

## Doc impact

- `applydesk/spec/applications.md` — the Admin bullet's Accounts Management: Workspace users, its chips, role filter and bulk bar.
- `applydesk/spec/architecture.md` — the `allowlist.py` row: the accounts listing and bulk changes.
- `applydesk/guide/todo_master.md` — the queue entry deleted at close.
- `applydesk/README.md` — the plan's index row, moved at close.
