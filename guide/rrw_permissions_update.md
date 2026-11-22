# Review Robin: Owners and operators on a session

**Filed:** 2026-11-22, at the author's ask, for later action; not scheduled. **Model:** `applydesk/spec/permissions.md` §3 and §7, Apply Desk's per-exercise roles, which the author wants Review Robin to share.

## Why

Review Robin's sessions have **owners only**: every `session_operators` row is `role="owner"`, every owner may do everything, and `"manager"` is reserved in `SESSION_OPERATOR_ROLES` (`app/db/models/session_operator.py`) but never written. Apply Desk now separates the two, nested: every Owner is an operator; Owners alone add and remove people, change ownership and delete. The author wants one model across both apps (2026-11-22).

## The target, in Review Robin's words

- **Roles on a session:** *Owner* ⊇ *Operator*. One or more Owners, always.
- **Owners only:** add and remove operators; Make Owner; demote an Owner to operator (themself: *Step down*); transfer ownership; delete the session; purge and archive.
- **Operators and Owners:** everything else: setup, Operations, Validate, Extract, lobby rename and tags, Duplicate (the copy's Owner is whoever duplicates it), and leaving the session.
- **An Owner is demoted before removal**, never removed directly (Apply Desk ruling, 2026-11-22).
- **At least one Owner** under the lock `remove_owner` already takes (`_lock_owner_rows`).
- **Workspace tiers are unchanged**: Super-admin ⊇ Admin ⊇ Operator (`spec/permissions.md` §1); a sys-admin's *Adopt* makes them an **Owner**.

## What changes

1. **Data.** Write `role="operator"` (widen `SESSION_OPERATOR_ROLES`; decide whether `"manager"` goes or is renamed). Existing rows stay `"owner"`, so no session loses rights. A migration only if the tuple's rename needs one; there is no DB check.
2. **Gates.** Split `require_session_operator` (any row) from a new Owner gate, and move the Owner-only routes behind it: owners add/remove, delete, purge, archive. `spec/permissions.md` §2–§4 and `docs/security_posture.md`'s matrices follow.
3. **Services.** `app/services/session_owners.py` gains Make Owner, demote, transfer and leave beside `add_owner` / `remove_owner`; `last_owner` becomes "at least one Owner" across demote, step down and leave; remove refuses an Owner. New audit events, each registered in `EVENT_SCHEMAS`: `session.owner_demoted`, `session.operator_added`, `session.operator_removed`, `session.ownership_transferred`, `session.operator_left`.
4. **Session Home's Owners card** (`spec/session_owners.md` §2) becomes *Owners and operators*, with the per-row moves `applydesk/spec/permissions.md` §7 lists; Create's Owners card (§1) gains a role per staged row, or stays owners-only (to decide).
5. **The lobby** (`app/web/templates/operator/sessions_list.html`): *Created by* becomes *Your role* (*Owner* / *Operator*), sortable. It already lists only the sessions the viewer is on (`app/services/sessions.py`), as Apply Desk's now must. The tick panel's *Delete* and *Purge and archive* go live only when the viewer owns every ticked session.
6. **Accounts Management**: Revoke's `still_owner` / `sole_owner` guards read Owners, not rows.

## Open

- **Create**: name operators as well as owners there, or only owners, with operators added on Home.
- **`"manager"`**: drop it, or keep it reserved for a third role.

## When

After Apply Desk builds its model (its AD2 segment for owners and operators), so the cards and their copy are shared rather than invented twice. Plan it then as a segment (`guide/segment_plan_template.md`), with `spec/permissions.md`, `spec/session_owners.md` and `spec/audience_and_identity_model.md` §4b in its `Doc impact`.
