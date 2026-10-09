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

Session Home has three cards with a Lock / Unlock. They hold that state in
three different places, and the differences make them interfere with each
other:

- **Session config** keeps it in the URL (`?editing=1`).
- **Quick Setup** keeps it in a cookie (`qsu_{id}`).
- **Owners** keeps it in a cookie (`oou_{id}`).

A navigation middleware (`app/main.py`, `reset_card_unlocks_on_navigation`)
expires both cookies on every request outside a keep-list of paths. The
mapping done on 2026-10-09 found these side effects:

- A config **Save** relocks Quick Setup and Owners, because `/config` is not
  on the keep-list.
- Any Quick Setup or Owners post lands on Home without `?editing=1`, so it
  relocks the config card.
- Doing that **silently discards unsaved config edits**. Nothing warns about
  a dirty form.

Neither cookie lock guards anything the server does not already guard.

- **Quick Setup.** A replace needs the card's own confirmation checkbox
  (`confirm_replace`). The card's availability comes from lifecycle
  (`views/_quick_setup.py`, `is_editable` and no responses), not from the
  cookie.
- **Owners.** The routes don't read the cookie. The last owner's Remove is
  disabled, and removing yourself already asks for confirmation.

The one accident the Owners lock still caught is a stray one-click Remove of
another owner. That is recoverable, but nothing asks first.

### Decision

- **Retire the Quick Setup and Owners Lock / Unlock.** This removes:
  - both cookies and their helpers in `routes_operator/_shared.py`;
  - both `…/lock` routes;
  - the navigation middleware and its keep-list regex.

  This reverses the author's 2026-09-23 ruling that added the Owners lock
  "against accidental edits".
- **Removing another owner asks first**, with a `window.confirm`, the same
  pattern the self-removal form already uses.
- **The config card warns before unsaved edits are lost.** A `beforeunload`
  guard runs while the card is in edit mode and dirty, and clears when the
  card's own form submits or is discarded. `instruments_index.html` and
  `session_observers.html` already use the same pattern.
- **The config card keeps its Unlock.** It is a display/edit mode switch,
  not an accident guard.

**Rejected:** keeping the cookie locks and adding `/config` to the
middleware's keep-list. That would fix the relock asymmetry but keep three
mechanisms guarding nothing, plus a regex in `app/main.py` that must mirror
two prefixes in `_shared.py` by hand.

### Semantics

- **Quick Setup.** When available (`is_editable` and no responses), the body
  is live with no Unlock step. When unavailable, it renders exactly as it
  does today when locked: the body greyed (`.quick-setup-body.locked`), file
  inputs `disabled`, and the checkbox inert. `is_locked` reduces to
  `not is_available` and `show_lock_toggle` goes. The replace checkbox still
  gates every replacing submit.
- **Owners.**
  - The card is always live.
  - **Remove another owner:** `confirm("Remove <name or email> as an owner
    of this session?")`. Without JavaScript it posts unconfirmed, as
    self-removal does today.
  - **Remove yourself:** unchanged.
  - **Last owner:** unchanged; still disabled.
- **Stale cookies.** Browsers holding a `qsu_` or `oou_` cookie keep sending
  it until the browser session ends; nothing reads it. These are session
  cookies with no expiry, so no clean-up route is needed.
- **Dirty guard.**
  - **When it fires:** on any navigation away from Home while the config
    card is in edit mode with `data-config-dirty="true"`. That covers a
    Quick Setup or Owners submit, a Workflow or Danger Zone post, a link, a
    reload or closing the tab.
  - **What the user sees:** the browser's generic prompt; browsers ignore
    custom text.
  - **When it doesn't fire:** on the card's Save submit, and after Cancel or
    Lock, which reset the form.
  - **Edge case:** typing a value back to its original leaves the card dirty,
    because the card's existing dirty flag is set on input and never
    recomputed. Accepted.
  - **Without JavaScript:** there is no dirty tracking, so there is no
    guard, as today.

### Judgment calls — decided

- `beforeunload` over a confirm on each form: it covers every exit, links
  included, in one place, and has repository precedent. (2026-10-09)
- Retire `.lockable-body`. Its only user is the Owners card, and
  `.quick-setup-body.locked` stays because the unavailable state still uses
  it. (2026-10-09)
- Delete the middleware in the rung that removes the last cookie, rather
  than leaving it running over nothing. (2026-10-09)

### Blast radius (measured)

Taken 2026-10-09 at `3b8672bd`. `P` is
`qsu_|oou_|quick-setup/lock|owners/lock|quick-setup-lock-toggle|owners-lock-toggle|_UNLOCK_KEEP|_UNLOCK_COOKIE|reset_card_unlocks|_quick_setup_unlocked|_owners_unlocked|owners_unlocked|is_unlocked`.

| What | Count | Command |
|---|---|---|
| App files touching the two locks | 7 | `grep -rlE "$P" app --include=*.py --include=*.html` |
| Hits in those files | 37 | `grep -rhcE "$P" app --include=*.py --include=*.html` (summed) |
| Test files | 6 (5 integration, 1 browser) | `grep -rlE "$P" tests --include=*.py` |
| `show_lock_toggle` users | 2 app, 2 tests | `grep -rln "show_lock_toggle" app tests --include=*.py --include=*.html` |
| `.lockable-body` users | 1 template + `base.html` | `grep -rln "lockable-body" app/web/templates` |
| Specs and root docs naming the toggles or cookies | 7 + `README.md` | `grep -rlE "qsu_\|oou_\|quick-setup/lock\|owners/lock\|Unlock.*(Quick Setup\|Owners)\|(Quick Setup\|Owners).*(Lock\|Unlock)" spec docs *.md` |

The app files are `app/main.py`, `routes_operator/_shared.py`,
`routes_operator/_quick_setup.py`, `routes_operator/_session_home.py`,
`views/_quick_setup.py`, `partials/_quick_setup_card.html` and
`session_detail.html`. The test files are
`test_quick_setup_card.py`, `test_quick_setup_new_session.py`,
`test_quick_setup_scaffold.py`, `test_session_detail_restructure.py` and
`test_session_home_owners_card.py` under `tests/integration/`, plus
`tests/browser/test_owners_card.py`.

### PR ladder

1. **PR 1 — the dirty-form guard.**
   - **Lands:** the `beforeunload` guard on the config card in
     `session_detail.html`, a browser test that a dirty card prompts and a
     saved one doesn't, and the `spec/session_home.md` line.
   - **Must not touch:** either lock.
2. **PR 2 — Owners without a lock.**
   - **Lands:**
     - removes the `owners/lock` route, the `oou_` helpers and
       `owners_unlocked`;
     - removes the card's toggle and `.lockable-body` (template and
       `base.html`);
     - adds the confirm on removing another owner;
     - updates the integration and browser tests;
     - drops `oou_` from the middleware regex, which then guards `qsu_`
       only.
   - **Specs:** `session_owners.md`, `permissions.md`,
     `operator_button_audit.md`, and the `oou_` row of
     `settings_inventory.md`.
3. **PR 3 — Quick Setup without a lock, and the middleware goes.**
   - **Lands:**
     - removes the `quick-setup/lock` route, the `qsu_` helpers,
       `is_unlocked` and `show_lock_toggle`;
     - removes the card's footer toggle;
     - deletes the middleware and both regexes from `app/main.py`;
     - updates the tests.
   - **Specs and docs:** `quick_setup_card_spec.md` (the "Lock state on
     navigation" paragraph goes), `session_home.md`, the `qsu_` row of
     `settings_inventory.md`, `operator_button_audit.md` and `README.md`.

PR 1 is independent of the other two. PR 2 comes before PR 3 so that the
middleware is deleted with the last cookie. The cumulative `diff-reviewer`
read runs at PR 3, on the diff from the main SHA before PR 1 merged.

### Definition of done

- `grep -rnE "qsu_|oou_|_UNLOCK_KEEP|reset_card_unlocks" app tests` returns
  nothing.
- `grep -rn "lockable-body" app` returns nothing.
- A browser test shows that a dirty config card prompts on leaving Home and
  a saved one does not.
- An integration test asserts that removing another owner renders a
  confirm and that removing the last owner stays disabled.
- `spec/quick_setup_card_spec.md` has no "Lock state on navigation"
  paragraph, and `spec/settings_inventory.md` has no `qsu_` / `oou_` rows.
- `guide/things_to_check_in_browser.md` has a section per PR.
- `### Doc impact` present and current, and every bullet checked by hand
  (no `close_check` for this file).
- `spec-writer` run against the doc-impact specs; flags adjudicated.
- `### Status` compacted to intended versus done; answered open questions
  collapsed.
- `guide/todo_master.md` entry deleted.

### Open questions

- None at planning.

### Out of scope

- **The config card's Unlock.** It is an edit mode, not a guard, and it
  stays.
- **The roster pages' Unlock panel (`_roster_lock_card.html`) and the
  Instruments page's per-card Lock / Unlock.** These are different
  mechanisms and read differently.
- **The Create page's Quick Setup and Owners cards.** They carry no lock
  today.

### Doc impact

- `spec/session_home.md` — the dirty-form guard (PR 1); the cards no
  longer list Lock / Unlock (PR 2, PR 3).
- `spec/session_owners.md` — §2 drops the Lock / Unlock bullet; Remove of
  another owner asks first (PR 2).
- `spec/permissions.md` — drops the `owners/lock` row and its notes (PR 2).
- `spec/quick_setup_card_spec.md` — drops "Lock state on navigation" and
  the toggle in the footer and the locked-state copy; unavailable still
  greys (PR 3).
- `spec/settings_inventory.md` — drops the `qsu_` and `oou_` cookie rows
  (PR 2, PR 3).
- `spec/operator_button_audit.md` — drops rows 32 and 192 (Lock / Unlock);
  the Owners Remove row records the confirm (PR 2, PR 3).
- `README.md` — the Quick Setup line drops "behind a single Lock / Unlock
  toggle" (PR 3).
- `guide/things_to_check_in_browser.md` — a section per PR.
- `guide/todo_master.md` — delete this item's entry at close.
