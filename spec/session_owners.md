# Session owners

Every session has one or more operator **owners** — the
`session_operators` rows with `role="owner"` that gate the
`require_session_operator` dependency (`spec/permissions.md` §2/§4.2).
Two pages let an operator manage the set, both built on the same
staging script and (mostly) the same service functions:

- **Create** (`/operator/sessions/new`) — names co-owners for a
  session that does not exist yet.
- **Session Home** (`/operator/sessions/{id}`) — its own card,
  `#owners-card`, edits the set of an existing session.

They look the same and save differently; §6 states the difference row
by row. `spec/permissions.md` §4.2 owns the gates, status codes and
audit events; this spec owns the two cards' shape and staging.

---

## 1. Create's Owners card

Template: `app/web/templates/operator/session_new.html`, `#session-owners`
— third card in the page's right-hand `.bottom-left` column, below Tags
(`spec/ui_elements.md` §10; `spec/operator_ui_concept.md` "Create new
session").

- **Table**: the creator's row first (Email / Name / Role "owner" /
  Added "—"), no Remove — a session always keeps its first owner. Rows
  staged below it carry a Remove.
- **Candidates**: `session_owners.new_session_owner_candidates` — every
  workspace operator (`is_operator OR is_sys_admin`) except the
  creator. No session exists yet, so there is no owner set to exclude
  beyond that.
- **Add owner** (`.btn.secondary`, `type="button"`) stages a row; it
  does not save. The card carries no Save of its own — its subtitle
  says owners are saved when the session is created.
- **Create session** (Primary) submits everything: the staged rows'
  hidden `owners` inputs are bound to `form="create-session-form"`.

### Save path

`_quick_setup.create_session` validates the whole staged list with
`session_owners.resolve_owners` **before** the session exists — one
address that is not a workspace operator is a 422 and nothing is
created. After `sessions.create_session` returns, `write_staged_owners`
calls `session_owners.set_owners(targets=[creator, *owner_targets])`,
which adds the co-owners (the creator is already the first owner from
`create_session` itself). Every event this produces — the session, each
Quick Setup slot, the tag write, one `session.owner_added` per
co-owner — shares one `correlation_id`.

`already_owner` cannot occur here: a duplicate or the creator's own
address collapses silently in `resolve_owners` / `set_owners` before
`add_owner` would raise it.

---

## 2. Session Home's Owners card

Template: `app/web/templates/operator/session_detail.html`,
`#owners-card` — a card of its own, half width, below the Danger Zone
card (`#danger-zone`) in Home's `.bottom-grid`, **outside** the Session
details card and its Lock / Unlock. `spec/session_home.md` places it in
the page's card list; this spec owns its contents.

- **Always visible, in every lifecycle state.** No `?editing=1`, no
  display/edit swap — the card renders one way, locked or not
  (`spec/session_home.md`'s Session details card is the surface that
  swaps; this one doesn't).
- **Table**: every current owner, Email / Name / Role / Added / a
  Remove per row, your own row included.
- **Candidates**: `session_owners.session_owner_candidates` — every
  workspace operator, **current owners included**: owners are staged
  in the table, so one removed there can be picked again before Save.
- **Save** and **Cancel**, both `.btn.secondary`, start rendered
  enabled (so the card works with no JavaScript) and are disabled by
  the gating script until the table or the picker's box changes.
  Cancel is `type="reset"` on the card's own form; the stager rebuilds
  the table on the `reset` event, and the gating script re-syncs a tick
  later.
- **Errors** are the card's own banner: a redirect back to
  `#owners-card`, `?owners_error=<code>` appended when there is one.
  Codes rendered: `already_owner`, `not_in_workspace`, `not_owner`,
  `owners_changed`, `last_owner`, `self_only`, else a generic "couldn't
  apply that change" naming the code.

---

## 3. The stager (shared partial)

`app/web/templates/operator/partials/_owners_stager_js.html`, included
by both pages. A card opts in with:

| Attribute | Meaning |
|---|---|
| `data-owners-stager` | marks the card |
| `data-owners-form="<id>"` | the form the staged rows' hidden inputs bind to |
| `data-owners-name="owners"` | the hidden input's `name` (default) |
| `data-owners-table` | the table element |
| `data-owners-email` | the picker's `<input type="email">` |
| `data-owners-add` | the Add-owner button |
| `data-owners-remove` | a row's Remove (absent on a fixed row — Create's creator) |
| `data-owners-self="<email>"` | the signed-in operator, so their own row's Remove asks first |

Three rules, from Session Home (author's rulings, 2026-09-23),
harmless on Create where they never trigger:

1. **The last owner's Remove is disabled** whenever one owner row
   remains, staged removals included.
2. **Removing your own row asks first** — a `confirm()` at the click;
   canceling keeps the row.
3. **The form's `reset` restores the rows it was rendered with.**

Rows are built with `createElement` + `textContent`, never `innerHTML`
— the email is operator-typed. Every add/remove dispatches a bubbling
`change`, so a card gating its Save on a change (Session Home's) sees
it; Create ignores it. **The staging buttons ship `hidden`** and the
script un-hides them — without JavaScript they would do nothing.

**Without JavaScript**: the picker's `<input>` keeps its own `name`
and `form=`, so the one address typed there submits with the page —
with **Save** on Session Home, with **Create session** on Create — an
address typed and never added is saved rather than dropped.

---

## 4. Service functions

`app/services/session_owners.py`:

- **`resolve_owners(db, emails) -> list[User]`** — validates a whole
  list before anything is written: blanks skipped, case folded,
  duplicates collapsed, every address a workspace operator or raises
  `not_in_workspace` naming it. Used by Create (the whole staged list)
  and by `apply_owner_changes` (the additions only).
- **`set_owners(db, targets) -> (added, removed)`** — replaces the
  whole owner set with `targets`; adds before it removes so the count
  never passes through zero; refuses an empty `targets`
  (`last_owner`); de-duplicates its own input. Create's only caller.
- **`apply_owner_changes(db, original, wanted)`** — Session Home's
  save: applies the **difference** between `original`
  (`owners_original`, what the card was rendered with) and `wanted`
  (the table's current rows) to the owner rows **locked `FOR UPDATE`
  at write time**, not to a set resolved beforehand — see §6. Only the
  additions are validated (`resolve_owners`); an owner already in the
  table who has since lost operator status blocks nothing. **All or
  nothing**: the adds, removes and their audit events share one
  commit; a non-operator address, an empty result (`last_owner`), or a
  `SessionOperator` unique-constraint clash from a concurrent save
  (caught as `owners_changed`) rolls every change in the save back.
- **`add_owner` / `remove_owner`** — the single-target primitives the
  old `/owners/add` and `/owners/{user_id}/remove` routes call
  directly (§7); `apply_owner_changes` calls their private halves
  (`_insert_owner` / `_delete_owner`) instead, so its adds and removes
  share one lock and one commit rather than one each.

---

## 5. Routes

| Route | Gate | Lifecycle | Body |
|---|---|---|---|
| `POST /operator/sessions` (Create) | router-level `require_operator` (no session to own yet) | n/a | `owners` (repeated) |
| `POST /operator/sessions/{id}/owners/save` | `require_session_operator` | any state | `owners`, `owners_original` (both repeated) |
| `POST /operator/sessions/{id}/owners/add` | `require_sys_admin_or_session_operator` | any state | `target_email` |
| `POST /operator/sessions/{id}/owners/{user_id}/remove` | `require_session_operator` | any state | — |

Full gate/refusal/status-code/audit-event contract:
`spec/permissions.md` §4.2 and §5.

**The route is `owners/save`**, verb last, matching `owners/add` and
`instruments/{id}/fields/save` (`spec/architecture.md` "Route
conventions").

`session_owners_save` (`app/web/routes_operator/_session_home.py`)
redirects to `_owners_redirect_url`: `#owners-card` on success,
`?owners_error=<code>#owners-card` on a refusal. If the signed-in
operator is not among the owners afterward — they staged themselves
out and it saved — it redirects to `/operator/sessions` instead, since
Session Home is then a 404 for them.

---

## 6. Remove, as shipped — Create vs Session Home

| | **Create new session** | **Session Home** |
|---|---|---|
| **Where it shows** | On each staged co-owner row. The creator's row has none. | On every owner row, your own included. |
| **Element** | `<button type="button" class="chrome-link" data-owners-remove>`, built by the stager. | Same element and stager; each row's hidden `owners` input binds to the card's own `owners/save` form. A `<noscript>` per-row `<form>` to the old route sits beside it (§7), omitted on the last owner's row and your own. |
| **A click** | Takes the row out of the table. Nothing is written. | Takes the row out of the table. Nothing is written until **Save**. On your own row, a `confirm()` first; canceling keeps the row. |
| **Saved by** | Nothing on its own. **Create session** submits whatever rows remain. | The card's own **Save**, as changes against `owners_original`. |
| **Undo** | Pick the address again. Leaving the page discards all staging. | **Cancel** (`reset`) restores the rendered rows; picking the address again works too, before Save. |
| **Other unsaved edits** | Untouched — Remove never posts. | Untouched — Remove never posts either; every other staged row in the same table stays staged. |
| **Removing yourself** | Impossible: the creator's row carries no Remove. | Allowed while another row remains; confirmed at the click. Saving yourself out redirects to `/operator/sessions`. |
| **The last owner** | Cannot arise — the creator is always kept (`[creator, *staged]`). | Remove is client-side `disabled` with one row left; the server backstop is `apply_owner_changes` refusing an empty result (`last_owner`, the card's banner). |
| **Lifecycle** | No session yet. | Any state — neither the card nor `owners/save` carries a lifecycle gate. |
| **Who may** | The creator (whoever is filling the form). | Any owner, removing any owner, the creator included. |
| **A stale target** | Not applicable. | Silently a no-op through `owners/save` — a removal for an address no longer in the locked rows simply matches nothing. The `<noscript>` fallback (old route) still answers a stale target with `not_owner`. |
| **Audit** | None — a staged row that is removed was never written. | `session.owner_removed`, written only if Save commits, sharing the save's one `correlation_id` with any adds in the same submit. |
| **Confirmation** | None (nothing to confirm — no Remove on the one unremovable row). | The self-removal `confirm()` above; none removing another owner. |
| **Without JavaScript** | Nothing to remove — the buttons stay `hidden`; the email box submits one address. | The `<noscript>` fallback posts to the old per-row route and writes at once (§7). |

---

## 7. The old `/owners` routes — kept

`POST /owners/add` and `POST /owners/{user_id}/remove` are not retired.
Three things keep them live:

- **The `<noscript>` Remove** on Session Home's card (§6), for the
  no-JS path.
- **The relaxed self-add**: `owners/add` is one of the two routes a
  non-owner sys-admin may reach (`require_sys_admin_or_session_operator`),
  self-only — `self_only` refuses any other target for that caller.
  `tests/integration/test_operator_lobby_access_gate.py` pins it. No
  page posts there: Diagnostics **Manage** adopts through
  `POST /operator/sys-admin/sessions/{id}/adopt`, which calls
  `add_owner` directly.
- **`tests/integration/test_session_owners.py`**, which exercises them
  directly.

Their gates, refusals and audit events are unchanged
(`spec/permissions.md` §4.2): `owners/add` behind
`require_sys_admin_or_session_operator`, `owners/{user_id}/remove`
behind `require_session_operator`, neither carrying a lifecycle check
— the same as before Session Home's card gained its own Save.

---

## Cross-references

- `spec/permissions.md` §4.2 / §5 — gates, refusals, status codes, audit
  events.
- `spec/session_home.md` — where the Owners card sits among Home's
  other cards.
- `spec/operator_ui_concept.md` — Create page's card list.
- `spec/audience_and_identity_model.md` §4b — ownership as an identity
  concept.
- `spec/architecture.md` "Route conventions" — the `owners/save` /
  `fields/save` verb-last naming.
- `app/services/session_owners.py`, `app/web/routes_operator/_session_home.py`,
  `app/web/routes_operator/_quick_setup.py` — implementation.
- `app/web/templates/operator/partials/_owners_stager_js.html` — the
  stager script.
