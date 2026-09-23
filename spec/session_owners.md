# Session owners

Every session has one or more operator **owners** — the
`session_operators` rows with `role="owner"` that gate the
`require_session_operator` dependency (`spec/permissions.md` §2/§4.2).
Two pages let an operator manage the set, on the same service
functions:

- **Create** (`/operator/sessions/new`) — names co-owners for a
  session that does not exist yet. Add owner and Remove **stage** rows
  (the stager, §3), saved with **Create session**.
- **Session Home** (`/operator/sessions/{id}`) — its own card,
  `#owners-card`, edits the set of an existing session. **Each Add
  owner and Remove saves at once** (author's ruling, 2026-09-23, which
  retired the card's staged Save / Cancel).

They look alike and save differently; §6 states the difference row by
row. `spec/permissions.md` §4.2 owns the gates, status codes and
audit events; this spec owns the two cards' shape and staging.

---

## 1. Create's Owners card

Template: `app/web/templates/operator/session_new.html`, `#session-owners`
— second card in the page's right-hand `.bottom-left` column, below Tags;
the left column holds User interface settings over Quick Setup, so the
page approximates Session Home's placements (author's ruling,
2026-09-23; `spec/ui_elements.md` §10; `spec/operator_ui_concept.md`
"Create new session").

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
`#owners-card` — a card of its own, half width, above the Danger Zone
card (`#danger-zone`) in Home's `.bottom-grid`, **outside** the Session
details card and its Lock / Unlock. `spec/session_home.md` places it in
the page's card list; this spec owns its contents.

- **Always visible, in every lifecycle state.** No `?editing=1`, no
  display/edit swap — the card renders one way, locked or not
  (`spec/session_home.md`'s Session details card is the surface that
  swaps; this one doesn't).
- **Table**: every current owner, Email / Name / Role / Added / a
  **Remove** per row, your own included. Each Remove is its own form
  posting to `owners/{user_id}/remove` and saves at once. It is
  `disabled` when one owner remains; on your own row the form asks
  first (`window.confirm` on submit).
- **Add owner** (`.btn.secondary`, `type="submit"`) posts the picker's
  address (`target_email`, `required`) to `owners/add` and saves at
  once. Plain forms throughout, so the card needs no JavaScript.
- **Candidates**: `session_owners.session_owner_candidates` — workspace
  operators **not already owners**; adding one would only be refused
  `already_owner`. With none left the card says every workspace
  operator is already an owner.
- **No Save or Cancel**: nothing is staged, so there is nothing to
  save or undo.
- **Errors** are the card's own banner: a redirect back to
  `#owners-card`, `?owners_error=<code>` appended when there is one.
  Codes rendered: `already_owner`, `not_in_workspace`, `not_owner`,
  `last_owner`, `self_only`, else a generic "couldn't apply that
  change" naming the code.

---

## 3. The stager (shared partial)

`app/web/templates/operator/partials/_owners_stager_js.html`, included
by **Create only** — Session Home's card staged with it until the
2026-09-23 ruling (§2). A card opts in with:

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

Three rules, from Session Home's staged days (author's rulings,
2026-09-23), kept because they are harmless on Create where they never
trigger:

1. **The last owner's Remove is disabled** whenever one owner row
   remains, staged removals included.
2. **Removing your own row asks first** — a `confirm()` at the click;
   canceling keeps the row.
3. **The form's `reset` restores the rows it was rendered with.**

Rows are built with `createElement` + `textContent`, never `innerHTML`
— the email is operator-typed. Every add/remove dispatches a bubbling
`change`, so a card gating a Save on a change could see it; Create
ignores it. **The staging buttons ship `hidden`** and the
script un-hides them — without JavaScript they would do nothing.

**Without JavaScript**: the picker's `<input>` keeps its own `name`
and `form=`, so the one address typed there submits with **Create
session** — an address typed and never added is saved rather than
dropped.

---

## 4. Service functions

`app/services/session_owners.py`:

- **`resolve_owners(db, emails) -> list[User]`** — validates a whole
  list before anything is written: blanks skipped, case folded,
  duplicates collapsed, every address a workspace operator or raises
  `not_in_workspace` naming it. Create's, over the whole staged list.
- **`set_owners(db, targets) -> (added, removed)`** — replaces the
  whole owner set with `targets`; adds before it removes so the count
  never passes through zero; refuses an empty `targets`
  (`last_owner`); de-duplicates its own input. Create's only caller.
- **`add_owner` / `remove_owner`** — the single-target primitives
  behind `owners/add` and `owners/{user_id}/remove`, and so behind
  Session Home's card: each validates, writes one row and its audit
  event, and commits. `remove_owner` locks the owner rows
  `FOR UPDATE` before counting, so two concurrent removes cannot leave
  a session ownerless (`last_owner`).

---

## 5. Routes

| Route | Gate | Lifecycle | Body |
|---|---|---|---|
| `POST /operator/sessions` (Create) | router-level `require_operator` (no session to own yet) | n/a | `owners` (repeated) |
| `POST /operator/sessions/{id}/owners/add` | `require_sys_admin_or_session_operator` | any state | `target_email` |
| `POST /operator/sessions/{id}/owners/{user_id}/remove` | `require_session_operator` | any state | — |

Full gate/refusal/status-code/audit-event contract:
`spec/permissions.md` §4.2 and §5.

Both per-action routes redirect to `_owners_redirect_url`:
`#owners-card` on success, `?owners_error=<code>#owners-card` on a
refusal — except `last_owner` on remove, a bare 409 (the card disables
that Remove, so only a direct POST or a concurrent remove reaches it),
and **removing yourself**, which redirects to `/operator/sessions`
since Session Home is then a 404 for you.

---

## 6. Remove, as shipped — Create vs Session Home

| | **Create new session** | **Session Home** |
|---|---|---|
| **Where it shows** | On each staged co-owner row. The creator's row has none. | On every owner row, your own included. |
| **Element** | `<button type="button" class="chrome-link" data-owners-remove>`, built by the stager. | `<button type="submit" class="chrome-link">` in its own `<form>` per row, posting to `owners/{user_id}/remove`. |
| **A click** | Takes the row out of the table. Nothing is written. | Deletes the owner row at once. On your own row, a `confirm()` first; canceling posts nothing. |
| **Saved by** | Nothing on its own. **Create session** submits whatever rows remain. | Itself. |
| **Undo** | Pick the address again. Leaving the page discards all staging. | Add the owner back with **Add owner** — they are a candidate again. |
| **Other unsaved edits** | Untouched — Remove never posts. | None to lose: the card holds nothing unsaved, and the details card is a separate form. |
| **Removing yourself** | Impossible: the creator's row carries no Remove. | Allowed while another owner remains; confirmed at the click; redirects to `/operator/sessions`. |
| **The last owner** | Cannot arise — the creator is always kept (`[creator, *staged]`). | Remove renders `disabled`; a direct POST is a bare **409** (`last_owner`), the owner rows locked `FOR UPDATE` while counting. |
| **Lifecycle** | No session yet. | Any state — neither the card nor the route carries a lifecycle gate. |
| **Who may** | The creator (whoever is filling the form). | Any owner, removing any owner, the creator included. A non-owner sys-admin must adopt first. |
| **A stale target** | Not applicable. | `not_owner`: a 303 back with the card's banner. |
| **Audit** | None — a staged row that is removed was never written. | `session.owner_removed`, a snapshot of the row, with its own correlation id. |
| **Confirmation** | None (nothing to confirm — no Remove on the one unremovable row). | The self-removal `confirm()` above; none removing another owner. |
| **Without JavaScript** | Nothing to remove — the buttons stay `hidden`; the email box submits one address. | Works: plain forms. The self-removal confirm is skipped. |

---

## 7. `owners/add` beyond the card

Besides Session Home's Add owner, `owners/add` is one of the two routes
a non-owner sys-admin may reach (`require_sys_admin_or_session_operator`),
**self-only** — `self_only` refuses any other target for that caller.
`tests/integration/test_operator_lobby_access_gate.py` pins it. No page
posts there for that purpose: Diagnostics **Manage** adopts through
`POST /operator/sys-admin/sessions/{id}/adopt`, which calls `add_owner`
directly. Neither per-action route carries a lifecycle check
(`spec/permissions.md` §4.2).

---

## Cross-references

- `spec/permissions.md` §4.2 / §5 — gates, refusals, status codes, audit
  events.
- `spec/session_home.md` — where the Owners card sits among Home's
  other cards.
- `spec/operator_ui_concept.md` — Create page's card list.
- `spec/audience_and_identity_model.md` §4b — ownership as an identity
  concept.
- `app/services/session_owners.py`, `app/web/routes_operator/_session_home.py`,
  `app/web/routes_operator/_quick_setup.py` — implementation.
- `app/web/templates/operator/partials/_owners_stager_js.html` — the
  stager script (Create).
