# Operator pages enhancements

**Opened:** 2026-10-09 · **Theme:** small, self-contained improvements to the
operator pages, one item each, closing independently · **Related:**
`spec/session_home.md`, `spec/quick_setup_card_spec.md`,
`spec/session_owners.md`

A standalone plan at the author's naming, not a `segment_*.md`: items are
added as they come up and each closes on its own. `tools/close_check.py`
reads only `segment_*` files, so an item's `Doc impact` is checked by hand at
its close, as `guide/archive/browser_test.md`'s was.

New items go at the end, numbered on, in the item shape of
`guide/segment_plan_template.md`, each with its own `### Doc impact` and
`### Status`.

---

## Item 1 — One lock on Session Home

### Opportunity

Session Home has three cards with a Lock / Unlock, each holding its state
differently: the config card in the URL (`?editing=1`), Quick Setup in a
cookie (`qsu_{id}`), Owners in a cookie (`oou_{id}`). A middleware
(`app/main.py`, `reset_card_unlocks_on_navigation`) expires both cookies on
any request outside a keep-list. Mapped 2026-10-09, they interfere:

- A config **Save** relocks Quick Setup and Owners (`/config` is not on the
  keep-list).
- A Quick Setup or Owners post lands on Home without `?editing=1`, relocking
  the config card and **silently discarding unsaved config edits**.

Neither cookie guards anything the server doesn't. A Quick Setup replace
needs its own `confirm_replace` checkbox and availability comes from
lifecycle (`views/_quick_setup.py`), not the cookie. The owners routes don't
read theirs; the last owner's Remove is disabled and self-removal confirms.
The one accident the Owners lock still caught is a stray one-click Remove of
another owner.

### Decision

- **Retire the Quick Setup and Owners Lock / Unlock**: both cookies and their
  helpers in `routes_operator/_shared.py`, both `…/lock` routes, and the
  middleware with its keep-list regex. Reverses the 2026-09-23 ruling that
  added the Owners lock "against accidental edits".
- **Removing another owner asks first**, by `window.confirm`, as self-removal
  already does.
- **The config card warns before unsaved edits are lost**: a `beforeunload`
  guard while it is in edit mode and dirty, as in `instruments_index.html`
  and `session_observers.html`.
- **The config card keeps its Unlock** — an edit mode, not an accident guard.

**Rejected:** adding `/config` to the keep-list. It fixes the relock
asymmetry but keeps three mechanisms guarding nothing, and a regex in
`app/main.py` that mirrors two prefixes in `_shared.py` by hand.

### Semantics

- **Quick Setup.** Available (`is_editable` and no responses): live, no
  Unlock step. Unavailable: exactly today's locked render
  (`.quick-setup-body.locked`, inputs `disabled`). `is_locked` becomes
  `not is_available`; `show_lock_toggle` goes. `confirm_replace` still gates
  every replace.
- **Owners.** Always live. Remove of another owner confirms "Remove <name or
  email> as an owner of this session?"; without JavaScript it posts
  unconfirmed, as self-removal does. Self-removal and the last owner's
  disabled Remove are unchanged.
- **Stale cookies.** Session cookies with no expiry; nothing reads them once
  the code goes, so no clean-up route.
- **Dirty guard.** Fires on any navigation off Home while the card is in edit
  mode with `data-config-dirty="true"` — another card's submit, a link, a
  reload, closing the tab — with the browser's generic prompt. Not on the
  card's own Save, nor after Cancel or Lock. Typing a value back to its
  original stays dirty (the flag is never recomputed); accepted. No
  JavaScript, no guard, as today.

### Judgment calls — decided

- `beforeunload` over a confirm per form: covers every exit, links included,
  and has precedent. (2026-10-09)
- Retire `.lockable-body` (Owners only); keep `.quick-setup-body.locked` for
  the unavailable state. (2026-10-09)
- Delete the middleware with the last cookie, not leave it running over
  nothing. (2026-10-09)

### Blast radius (measured)

Taken 2026-10-09 at `3b8672bd`. `P` is
`qsu_|oou_|quick-setup/lock|owners/lock|quick-setup-lock-toggle|owners-lock-toggle|_UNLOCK_KEEP|_UNLOCK_COOKIE|reset_card_unlocks|_quick_setup_unlocked|_owners_unlocked|owners_unlocked|is_unlocked`.

| What | Count | Command |
|---|---|---|
| App files / hits | 7 / 37 | `grep -rlE "$P" app --include=*.py --include=*.html` (hits: `-rhcE`, summed) |
| Test files | 6 (5 integration, 1 browser) | `grep -rlE "$P" tests --include=*.py` |
| `show_lock_toggle` users | 2 app, 2 tests | `grep -rln "show_lock_toggle" app tests` |
| `.lockable-body` users | 1 template + `base.html` | `grep -rln "lockable-body" app/web/templates` |
| Live specs and root docs | 7 + `README.md` | `grep -rlE "qsu_\|oou_\|quick-setup/lock\|owners/lock\|Unlock.*(Quick Setup\|Owners)\|(Quick Setup\|Owners).*(Lock\|Unlock)" spec docs *.md`, less `archive/` |

### Status

- **PR 1 (dirty guard)** built 2026-10-09 on main `daa7b3b1`, which is
  the base for PR 3's cumulative read. Four browser tests: a dirty card
  prompts, and an accepted prompt leaves and drops the edit; Save, Cancel
  and Lock leave without a prompt. The two prompt tests fail without the
  guard.
- **Scope added at PR 1 (Codex on #2919):** declining the prompt left
  `base.html`'s busy indicator armed for its 60 s give-up, since no load
  came to clear it. The indicator now stands aside while
  `window.rrwLeaveWillPrompt()` is true. The Instruments page and
  Observers guards have the same gap and don't set the hook yet; that is
  left for a later item.
- **PR 2 (Owners without a lock)** built 2026-10-09 on main `acec4255`.
  The keep-list in `app/main.py` keeps its `/owners/...` paths until
  PR 3, so an owner add or remove still leaves Quick Setup unlocked; only
  the cookie regex dropped `oou_`. The confirm's text rides in an
  autoescaped `data-confirm` attribute, so no display name reaches the
  script. The build found three docs the manifest missed:
  `spec/rrw_functional_spec.md`, `spec/quick_setup_card_spec.md`'s
  `oou_` aside, and `guide/post_azure_todo_checklist.md` item 5's rows;
  the `spec-writer` verify pass found a fourth, `spec/audience_and_identity_model.md`.

### PR ladder

1. **Dirty guard.** The `beforeunload` guard in `session_detail.html`, a
   browser test (dirty prompts, saved doesn't), the `spec/session_home.md`
   line. Touches neither lock.
2. **Owners without a lock.** Drops the `owners/lock` route, the `oou_`
   helpers, `owners_unlocked`, the card's toggle and `.lockable-body`; adds
   the confirm; drops `oou_` from the middleware regex; tests updated.
3. **Quick Setup without a lock; the middleware goes.** Drops the
   `quick-setup/lock` route, the `qsu_` helpers, `is_unlocked`,
   `show_lock_toggle` and the footer toggle; deletes the middleware and both
   regexes; tests updated.

PR 1 is independent; PR 2 precedes PR 3 so the middleware goes with the last
cookie. Each rung's specs are tagged in `Doc impact`. The cumulative
`diff-reviewer` read runs at PR 3, from the main SHA before PR 1 merged.

### Definition of done

- `grep -rnE "qsu_|oou_|_UNLOCK_KEEP|reset_card_unlocks" app tests` and
  `grep -rn "lockable-body" app spec` return nothing.
- A browser test shows a dirty config card prompts on leaving Home and a
  saved one doesn't; an integration test asserts Remove of another owner
  carries the confirm and the last owner's stays disabled.
- `guide/things_to_check_in_browser.md` has a section per PR.
- `### Doc impact` current, every bullet checked by hand (no `close_check`).
- `spec-writer` run against the doc-impact specs; flags adjudicated.
- `### Status` compacted; answered open questions collapsed.
- `guide/todo_master.md` entry deleted.

### Open questions

- None at planning.

### Out of scope

- The config card's Unlock (an edit mode; stays).
- The roster pages' Unlock panel (`_roster_lock_card.html`) and the
  Instruments page's per-card Lock / Unlock: different mechanisms.
- The Create page's Quick Setup and Owners cards: no lock today.

### Doc impact

- `spec/session_home.md` — the dirty-form guard (PR 1); the cards no longer list Lock / Unlock (PR 2, PR 3).
- `spec/session_owners.md` — §2 drops the Lock / Unlock bullet; Remove of another owner asks first (PR 2).
- `spec/permissions.md` — drops the `owners/lock` row and its notes (PR 2).
- `spec/ui_elements.md` — §1's busy indicator stands aside for a leave prompt (PR 1); §10's `.quick-setup-*` row drops `.lockable-body.locked` (PR 2) and the footer's Lock / Unlock (PR 3).
- `spec/quick_setup_card_spec.md` — the `oou_` aside goes (PR 2); drops "Lock state on navigation", the footer toggle and the locked-state copy; unavailable still grays (PR 3).
- `spec/settings_inventory.md` — drops the `oou_` (PR 2) and `qsu_` (PR 3) cookie rows.
- `spec/operator_button_audit.md` — drops rows 32 and 192 (Lock / Unlock); the Owners Remove row records the confirm (PR 2, PR 3).
- `spec/audience_and_identity_model.md` — the Owners card sentence drops "behind its own Lock / Unlock" (PR 2).
- `spec/rrw_functional_spec.md` — the Session Home Owners bullet drops "guarded by its own Lock / Unlock" (PR 2).
- `guide/post_azure_todo_checklist.md` — item 5's Owners rows lose the lock rows and gain the confirm (PR 2).
- `README.md` — the Quick Setup line drops "behind a single Lock / Unlock toggle" (PR 3).
- `guide/things_to_check_in_browser.md` — a section per PR.
- `guide/todo_master.md` — delete this item's entry at close.
