# Segment AD2M — Admins, and adopting an exercise

**Opened:** 2026-11-22 · **Theme:** the Admin tier between Operator and super-admin, and *adopt* as the one way an Admin or the super-admin takes up an exercise · **Related:** `applydesk/spec/permissions.md`, `spec/permissions.md` §4.1, `spec/audience_and_identity_model.md` §4

## Opportunity

Apply Desk has two workspace roles: Operator, and the super-admin derived from Cordware's config. Two things follow from that:
- The Admin pages are the super-admin's alone, so nobody else can admit operators or read Exercises Diagnostics.
- The super-admin reaches every exercise without holding any role on it (`gate.viewer` returns `operates=None`), so changes they make there leave no Owner or operator on record.

The author ruled on 2026-11-22 (`applydesk/spec/permissions.md` §10):
- build the Admin tier now;
- the super-admin adopts an exercise, as an Admin does.

## Decision

- **Admin** is a stored flag, `person.is_admin`, after Review Robin's `is_sys_admin`.
  - **Granted and taken away:** only the super-admin Promotes and Demotes, on Accounts Management.
  - **Nesting:** an Admin is an Operator (Super-admin ⊇ Admin ⊇ Operator). Every gate reads `may_operate or is_admin`.
  - **Reach:** `/admin/…` is for Admins and the super-admin. Admins admit and revoke operators. Promote and Demote stay the super-admin's.
- **Adopt** makes an Admin or the super-admin an **Owner** of an exercise. It is one audited step (`exercise.adopted`), taken from Exercises Diagnostics' *Manage*, Review Robin's name for the same step.
  - *Manage* on a row adopts when the viewer holds no role there, then opens Home. It asks first, saying they will become an Owner.
  - Where the viewer already operates or owns the exercise, *Manage* just opens Home.
  - Adopting an exercise they only operate makes them an Owner.
- **The super-admin loses implicit reach.** Their `operates` becomes their grants, as anyone's. The Lobby then lists only what they own or operate (§7), and an exercise they hold no role on is a 404 until they adopt it.
- **More than one Owner, in the data only.** Adopting adds an Owner beside the existing one, so the one-Owner index goes. Reads that assumed one Owner (`owner_of`, the Operators card, `owner_labels`) learn to read several.
  - The card's new moves (Make Owner, demote, step down, leave) stay with AD2O.
  - The *Owners and operators* card stays with AD2O.

Rejected: adopting as an operator first and as an Owner once AD2O lands. The spec says adopt makes an Owner, and an adopter who cannot manage people cannot fix what they adopted to fix.

## Semantics

- **Promote:**
  - requires the person to be bound (a pending person cannot be an Admin);
  - also puts them on the operator list if they are not on it;
  - refused for the super-admin's own row, as every action on it is.
- **Demote:**
  - clears `is_admin` and keeps them on the operator list;
  - refused for the last Admin only when no super-admin is configured (Review Robin's fallback, `spec/permissions.md` §4.1).
- **Revoke an Admin from the operator list:** refused. Demote first.
- **No super-admin configured:** any Admin may Promote and Demote.
- **Adopt:**
  - is idempotent: adopting an exercise you already own changes nothing and audits nothing;
  - requires a row in the database (a sample exercise not yet seeded cannot be adopted, and says so);
  - an Admin who is later demoted keeps the Owner rows they adopted. Their grants stand, as an operator's do when revoked.
- **Exercises Diagnostics' *Owners* column and `owner_labels`** name every Owner, comma-separated.
- **Tests and local runs:** `conftest.py` seeds the sample exercises, so the fake super-admin owns them in the ordinary way, as Local Operator does after `python -m applydesk.seed`.

## Judgment calls — decided

- Admin is a column on `person`, not a role table. It nests as Review Robin's does and needs no join.
- Accounts Management's *Admin* column reads *Super-admin*, *Admin* or *no*. The *Admins* chip counts Admins with the super-admin.
- The last Admin is never demoted, a super-admin configured or not, as spec §8 and Review Robin's `last_admin` say; the plan's "only with none configured" yielded to the spec (2026-11-22, cold read).
- A super-admin's row is protected from Revoke, Promote and Demote, whoever acts, as Review Robin's `protected_super_admin` (2026-11-22, cold read).
- The seed acts as `Actor(platform=True)`, the one actor with every exercise; a signed-in super-admin, bound or not, reaches only their grants (2026-11-22, cold read).
- Rungs 3 and 4 land as one PR: the cold read's fixes span both (2026-11-22).

## Blast radius (measured)

Taken 2026-11-22 at `0de2e6a0a`.

| What | Count | Command |
|---|---|---|
| Modules reading `is_super_admin` | 6 (`allowlist`, `gate`, `operators`, `seed`, `team`, `web`) | `grep -rln "is_super_admin" applydesk/*.py` |
| Implicit reach | 2 lines (`gate.py:61`, `:86`) | `grep -n "operates=None\|operates is None" applydesk/*.py` |
| Test files opening an exercise's pages | 56, of which 5 seed | `grep -rln "operator/exercises/" applydesk/tests \| wc -l` |
| Migrations | 4; this adds one | `ls applydesk/alembic/versions` |

## Status

Closed 2026-11-22. Intended versus done:
- **Ladder:** the plan and the spec's rulings (#4130), the scaffold (#4131), then rungs 3 and 4 as one PR (#4132), and this close. The two build rungs went together because the cold read's fixes spanned both.
- **Done as decided,** plus these decisions confirmed at build (Judgment calls):
  - the last Admin is never demoted, whoever acts;
  - a super-admin's row is protected;
  - the seed is `Actor(platform=True)`, the only actor that holds every exercise;
  - *Manage* keeps Review Robin's name and adopts after a confirm.
- **Found in the build:** a handover whose actor's Owner row had just moved still promoted its target. It is now refused (rung 4).
- **Reads:**
  - One cumulative `diff-reviewer` read of rungs 2–4 found 1 high, 4 medium and 7 low findings, all acted on in #4132. The high one: *Manage*'s confirm sat in the title block.
  - Codex found one deadlock: two Admins demoting each other. Fixed by locking every Admin row first, and `db.lost_a_race` now reads a Postgres deadlock.
  - `spec-writer` at the close rewrote `permissions.md` §2–§10, `applications.md` and `architecture.md`.
- **Left for AD2O:**
  - Module docstrings and copy that still say "the Owner": `operators.py`, `routes_admin.py`, `team.py`, `_operators.html`, the Lobby's *Created by* title.
  - The Owner-only refusals' wording.
- **Owed:** the author's browser check of Promote, Demote and *Manage*.

## PR ladder

1. **PR 1 — this plan**, with the spec's rulings (`applydesk/spec/permissions.md`).
2. **PR 2 — scaffold.** Accounts Management gains *Promote* and *Demote* in the bulk bar, inert and saying they are not built yet, and the page's copy names Admins. Exercises Diagnostics' *Manage* keeps opening Home. Must not touch: gates and data.
3. **PR 3 — Admins.**
   - The `is_admin` column and its migration (round-tripped on Postgres).
   - Promote and Demote in `operators.py`, with their guards and audit.
   - `gate.viewer` reads Admins, `/admin` admits them, and the bulk bar is wired.
4. **PR 4 — Adopt.**
   - Drop `uq_exercise_one_owner` (migration).
   - The reads that assumed one Owner learn to read several.
   - `operators.adopt`, the Diagnostics action, and the super-admin's implicit reach removed.
   - The `conftest` seed, and the Lobby listing only what the viewer owns or operates. Last build rung: the cumulative `diff-reviewer` read.
5. **PR 5 — close.**

## Definition of done

- An Admin reaches `/admin`, admits and revokes operators, and cannot Promote. The super-admin Promotes and Demotes, and each change is audited (`test_operator_list.py`, a new `test_admins.py`).
- The super-admin with no role on an exercise gets a 404 on its pages, and its Lobby row is absent. After *Adopt*, both work, and `exercise.adopted` is recorded (`test_gate.py`).
- An exercise with two Owners lists both on Diagnostics and in `owner_labels`.
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD2M` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

None open. The author ruled on Admins, adopt and observers on 2026-11-22.

## Out of scope

- **AD2O:** the *Owners and operators* card, Make Owner, demote, step down, leave and transfer between several Owners, *Your role* in the Lobby, and Owner-only delete (`applydesk/guide/todo_master.md`).
- **Observers:** pre-positioned in the spec, built later.
- **Review Robin:** its update is `guide/rrw_permissions_update.md`.

## Doc impact

- `applydesk/spec/permissions.md` — §2's Admin built; §5 adopt built; §6 the reach columns; §9 the new events built.
- `applydesk/spec/applications.md` — "Who reaches what", Admin → Accounts Management (Admin column, chips, Promote and Demote), Exercises Diagnostics (*Manage* adopting, *Owners*), the Operator Lobby (only what the viewer owns or operates).
- `applydesk/spec/architecture.md` — the module map: `operators.py`'s promote, demote and adopt; `gate.py`'s Admin.
- `applydesk/guide/todo_master.md` — the queue entry deleted at close.
- `applydesk/README.md` — the plan's index row, moved at close.
