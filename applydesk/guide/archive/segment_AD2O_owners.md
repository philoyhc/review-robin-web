# Segment AD2O — Owners and operators

**Opened:** 2026-11-22 · **Theme:** an exercise's several Owners and their moves, the Lobby's *Your role*, and Home's *Owners and operators* card · **Related:** `applydesk/spec/permissions.md` §3, §7, §8, §9; `applydesk/guide/archive/segment_AD2M_admins.md`; `guide/rrw_permissions_update.md`

## Opportunity

`applydesk/spec/permissions.md` is the target contract (2026-11-22). Its exercise roles are half built:
- **Built:** the data holds several Owners (AD2M dropped the one-Owner index).
- **Card:** Home's *Operators* card still treats the exercise as having one Owner. Its *Make owner* is a handover, the old transfer.
- **Not built:**
  - Make Owner beside the others.
  - Demote and step down.
  - Leave.
  - The last-Owner guard.
  - Revoke refused for a sole Owner.
- **The Lobby's *Created by*** shows the Owners on record. §7 replaces it with *Your role*, and the author confirmed it belongs here (2026-11-22).
- **The panel's Owner-only actions** (*Purge and archive*, *Delete*) are live for everyone and refused by the server. §7 wants them to say which ticked exercises the viewer only operates.

## Decision

- **The moves** (§3 "The ownership moves"), each in `operators.py` under the exercise's row lock, each audited (§9):
  - **Make Owner:** an operator becomes an Owner beside the others (`exercise.owner_added`).
  - **Transfer:** today's `hand_over` (`exercise.ownership_handed_over`). It is renamed `transfer` and keeps its one-step guarantee.
  - **Demote:** an Owner makes another Owner, or themself (*Step down*), an operator (`exercise.owner_demoted`).
  - **Leave:** an operator takes themself off (`exercise.operator_left`).
  - **Remove:** stays an Owner's move, on operators only.
- **At least one Owner, always** (§8). Demote, step down and leave are refused if they would leave no Owner. The check is under the row lock, so two Owners demoting each other at once cannot both succeed.
- **Revoke** from the operator list is refused while the person is the only Owner of an exercise not archived (§8).
- **The card becomes *Owners and operators*:**
  - rows ordered Owners first;
  - each row offers only the viewer's moves (§7 table);
  - *Transfer ownership*, *Remove* and *Leave* ask first and are Outline-amber or Destructive; *Make Owner* and *Make operator* are Secondary.
- ***Your role*** replaces *Created by*: an *Owner* or *Operator* chip for the viewer, sortable as the other columns.
- **The tick panel follows the role:** *Purge and archive* and *Delete* are disabled unless the viewer owns every ticked exercise, and say which ones they only operate. The server's refusal stays.

Rejected: a separate `exercise_owner` table. Owner is a flag on the operator row; one row per person per exercise keeps Owner ⊇ Operator true by construction.

## Semantics

- **Last Owner:**
  - Demoting, stepping down or leaving as the only Owner is refused, saying to make another Owner or transfer first.
  - Transfer from the last Owner is allowed: it hands the role on.
- **Leave as an Owner:** refused; they step down first (§3).
- **Pending people** (not yet signed in) may be made Owner or receive a transfer, as they may be added. They reach nothing until bound.
- **An archived exercise** refuses every move (read-only until restored, #4142). Revoke's sole-Owner check counts only exercises not archived.
- **The super-admin and Admins** act on an exercise only through their own grants (AD2M). They adopt first.
- **After a move,** the viewer's grants are re-read (`gate.forget_viewer`). An Owner who leaves lands on the Lobby.

## Judgment calls — decided

- *Make operator* and *Step down* are one service call (`demote`). The card words it by whose row it is.
- *Your role* sorts Owner before Operator ascending.

## Blast radius (measured)

Taken 2026-11-22 at `3a965352b`.

| What | Count | Command |
|---|---|---|
| Modules and templates using `owner_labels` or *Created by* | 5 | `grep -rln "owner_labels\|Created by" applydesk/*.py applydesk/templates -r` |
| Callers of `hand_over` | 2 | `grep -rn "def hand_over\|hand_over(" applydesk/*.py` |
| Tests on the Operators card | 3 | `grep -rln "operators/.*owner\|_operators.html\|data-ops" applydesk/tests` |
| Tests naming *Created by* | 2 | `grep -rln "Created by" applydesk/tests` |

## Status — closed 2026-11-22

**The ladder held as planned:** plan #4143, scaffold #4144, moves #4145, wired #4146, then this close.

**Decisions confirmed at build:**
- **The last-Owner guard counts Owners who can act**, not every Owner grant. An Owner who can act is bound and either on the operator list or the super-admin, whose grants count unlisted (`counts_as_owner`).
  - A revoked or pending Owner doesn't keep an exercise running.
  - Demoting a non-acting Owner isn't held.
  - This narrows Semantics' "Pending people … reach nothing until bound": they may be Owners, but they don't count.
- **Revoke takes the exercise locks.** It locks each live exercise the person owns before counting. After its update it re-reads and re-locks what they now own. If it refuses, it puts the person's row back, so a bulk batch keeps nothing.
  - The guard holds only when the person being revoked counts as an Owner who can act.
- **Moves read `archived_at` under the row lock**, which archiving also takes.
- ***Step down* and *Leave* are refused on another person's row** (`not_self`).

**Where the Definition of done's tests landed:**
- Revoke: `applydesk/tests/test_owners.py`.
- The card's per-viewer moves and the Lobby's `data-owner`: `test_operators_card.py`.
- *Your role* rendering: `test_pages.py` and `test_gate.py`.

**Reads:**
- One cumulative `diff-reviewer` read of rungs 2–4, from base `3a965352b`, at rung 4. It found:
  - revoked and pending Owners counted toward the guard;
  - a non-acting Owner's demote was refused;
  - Revoke raced a Transfer;
  - *Step down* on another person's row gave the wrong message;
  - gaps in the card tests.
  Its bulk-Revoke deadlock finding was already handled by `db.is_busy`.
- Codex added four rounds on rung 3:
  - an unlisted super-admin Owner wasn't counted;
  - the archive check read a stale copy;
  - a pending co-Owner's revoke was held;
  - Revoke's re-check didn't lock the exercises it found.
  All were fixed in #4145.

**Left as found:** `routes_operator._ops_change` still comments on "the one-Owner index", which AD2M dropped. It's a stale code comment, for the next slice that edits that function.

## PR ladder

1. **PR 1 — this plan.**
2. **PR 2 — scaffold:**
   - Home's card retitled *Owners and operators*, each row showing its §7 moves as inert buttons, with real copy;
   - the Lobby's *Your role* column (read-only data, sortable);
   - the panel's Owner-only buttons with their role note, inert.
   - Must not change what any post does.
3. **PR 3 — the moves in the service:**
   - `make_owner`, `demote`, `leave` and `transfer`, with the last-Owner guard;
   - Revoke's sole-Owner check;
   - the audit events;
   - service tests.
4. **PR 4 — wired:**
   - the card's moves post and say how it went;
   - the panel's Owner-only buttons follow the role.
   - Last build rung: the cumulative `diff-reviewer` read.
5. **PR 5 — close.**

## Definition of done

- **Moves:** each move works and is audited. The last Owner can't be demoted, step down or leave, and two Owners demoting each other at once leave one (`applydesk/tests/test_owners.py`).
- **Revoke:** refused for a sole Owner of a live exercise (`applydesk/tests/test_admin_operators.py` or its successor).
- **The card** offers each viewer only their moves (`test_pages.py`).
- **The Lobby** shows and sorts *Your role*. The panel's Owner-only buttons are disabled for a set the viewer doesn't own (`test_lobby_actions.py`).
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD2O` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

None. The contract is `applydesk/spec/permissions.md` (2026-11-22). *Your role* in AD2O: the author, 2026-11-22.

## Out of scope

- **Purge:** waits for AD2D's stored applications.
- **Observers:** `applydesk/spec/permissions.md` §10.
- **Review Robin's matching change:** `guide/rrw_permissions_update.md`.

## Doc impact

- `applydesk/spec/permissions.md` — §3, §7, §8 and §9: the moves, *Your role*, the card, the guards and the audit events marked built.
- `applydesk/spec/applications.md` — the Lobby's *Your role* column and the panel's role-aware buttons; Home's *Owners and operators* card.
- `applydesk/spec/architecture.md` — the new audit events in the event list.
- `applydesk/guide/todo_master.md` — the AD2O queue entry deleted at close.
- `applydesk/guide/ad2_series.md` — an AD2O row pointing at this plan, then its archived copy.
- `applydesk/README.md` — the plan's index row, moved at close.
