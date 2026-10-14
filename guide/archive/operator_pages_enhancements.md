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

### Status — closed 2026-10-09

Shipped as laddered: PR 1 #2919, PR 2 #2920, PR 3 #2921.

- **Scope added:** declining the leave prompt left `base.html`'s busy
  indicator armed until its 60 s give-up (Codex on #2919). It now stands
  aside while `window.rrwLeaveWillPrompt()` is true; Session Home sets
  the hook. The Instruments and Observers guards share the gap — Item 2.
- **Decisions confirmed at build:** the Owners confirm's text rides in
  an autoescaped `data-confirm` attribute, so no display name reaches
  the script; the middleware kept its `/owners/...` keep-list until PR 3
  went, so Quick Setup never relocked mid-ladder; `is_locked` is now
  `not is_available`.
- **Manifest:** the blast-radius grep needed "Quick Setup"/"Owners" and
  "Lock" on one line, so wrapped sentences escaped it. Builds and reads
  added `spec/audience_and_identity_model.md`, `spec/lifecycle.md`,
  `spec/rrw_functional_spec.md` and `guide/post_azure_todo_checklist.md`.
- **Reads:** a `spec-writer` verify pass per rung (1, 6 and 11 stale
  passages or comments) and one at close; one cumulative `diff-reviewer`
  read on `daa7b3b1..7d2f75d2` — no code defect, four stale spec
  passages, one weak test — plus a read of the delta after it, clean; the close pass found one more, `spec/session_home.md`'s wireframe label.
- **Owed to the browser:** the bfcache re-arm of the dirty guard has no
  test; `guide/things_to_check_in_browser.md` carries it.

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
- `spec/lifecycle.md` — Quick Setup's unavailable state drops "the Lock / Unlock toggle hidden" (PR 3).
- `spec/rrw_functional_spec.md` — the Session Home Owners bullet drops "guarded by its own Lock / Unlock" (PR 2); the Owners paragraph and the Quick Setup bullet drop their Unlock (PR 3).
- `guide/post_azure_todo_checklist.md` — item 5's Owners rows lose the lock rows and gain the confirm (PR 2).
- `README.md` — the Quick Setup line drops "behind a single Lock / Unlock toggle" (PR 3).
- `guide/things_to_check_in_browser.md` — a section per PR.
- `guide/todo_master.md` — delete this item's entry at close.

---

## Item 2 — Busy indicator stands aside on every leave prompt

### Opportunity

Item 1 taught `base.html`'s navigation busy indicator to stand aside
while a page will ask before it is left, through
`window.rrwLeaveWillPrompt()`. Only Session Home sets the hook. The two
older `beforeunload` guards — the Instruments page's dirty-card guard
(`instruments_index.html`, `_newModelWireNavGuard`) and the Observers
expander's cohort guard (`session_observers.html`) — don't, so declining
their prompt leaves the bar, the progress cursor and "Loading…" on an
idle page for 60 s, exactly the defect Codex found on #2919.

### Decision

Each guard sets `window.rrwLeaveWillPrompt` to the same predicate its
`beforeunload` handler reads, as Session Home's does: Instruments
`!_newModelIntentionalNav && <a dirty card>`, Observers
`!intentionalNav && cohortDirty`. One hook per page; neither page shares
Home, so there is no collision.

**Rejected:** a generic registry in `base.html` (each guard registers a
predicate, the indicator ORs them). Three pages, one guard each; a
registry is machinery for a case that doesn't exist.

### Semantics

- **When the hook is true** a link click or a form submit doesn't arm the
  bar. A confirmed leave loads without one, as on Home.
- **Each page's own deliberate exits** clear the predicate before
  navigating. The Observers panel's actions (submits, after their
  `confirm`) still arm the bar; Instruments' discard reload is a script
  `location.reload`, which never armed it.
- **Without JS** neither guard nor bar exists; unchanged.

### Judgment calls — decided

- Reuse the predicate the `beforeunload` handler reads, by hoisting it
  into a named function, rather than a second copy that could drift.
  (2026-10-09)

### Blast radius (measured)

Taken 2026-10-09 at `8372fa12`.

| What | Count | Command |
|---|---|---|
| Templates with a `beforeunload` guard | 3 (Home done) | `grep -rln "addEventListener(.beforeunload" app/web/templates` |
| Pages setting the hook | 1 | `grep -rln "rrwLeaveWillPrompt =" app/web/templates` |
| Tests naming `beforeunload` | 3 + 1 unit | `grep -rln "beforeunload" tests --include=*.py` |
| Specs naming `beforeunload` | 5 | `grep -rln "beforeunload" spec/*.md` |

### Status — closed 2026-10-09

Shipped as planned in #2924. Each guard's predicate is hoisted into a
`willPrompt()` its `beforeunload` handler calls and exposes as the hook,
so the two cannot drift; the Observers one coerces `cohortDirty` to a
boolean, since `base.html` checks `=== true`. One `diff-reviewer` read:
no high or medium finding, two prose ones, fixed (§1 names the three
pages rather than claiming every guard; Instruments' discard reload is a
script reload and never armed the bar). The `spec-writer` pass on the
final state found no divergence and served as the close pass. Codex: no
findings.

### PR ladder

1. **The two hooks.** Both templates set `window.rrwLeaveWillPrompt`; a
   browser test per page: a dirty card or cohort, a link clicked, the
   prompt declined, and the bar still hidden past its 200 ms arming
   delay. `spec/ui_elements.md` §1 names the three pages. A code slice
   outside a ladder: it takes its own `diff-reviewer` read.

### Definition of done

- `grep -rln "rrwLeaveWillPrompt =" app/web/templates` lists three
  templates.
- A browser test per page fails without its hook.
- `spec/ui_elements.md` §1 states the exclusion for every leave prompt.
- `guide/things_to_check_in_browser.md` has the PR's section.
- `### Doc impact` current, every bullet checked by hand.
- `spec-writer` run against the doc-impact specs; flags adjudicated.
- `### Status` compacted; `guide/todo_master.md` entry updated.

### Open questions

- None at planning.

### Out of scope

- The guards themselves (when they fire, their wording) — unchanged.

### Doc impact

- `spec/ui_elements.md` — §1's busy-indicator exclusion names the Instruments and Observers guards beside Session Home's.
- `spec/instruments.md` — the nav-away guard's sentence notes the busy indicator stands aside.
- `guide/things_to_check_in_browser.md` — a section for the PR.

---

## Item 3 — Three chip types, one look each

### Opportunity

The lobby's AND/OR and Select all / Clear all chips wear the off look of
a tag filter chip (light fill, accent edge), so they read as two
unselected filters. A survey on 2026-10-09 found the same mismatch on
Extract: three two-state chips ("All reviewers ↔ Reviewers with
responses" and its reviewee and assignment-row siblings) flip light and
dark as if one of two valid choices were "off". `spec/ui_elements.md` §9
names the lobby chips' fill but sets no rule for chips that aren't
on/off.

### Decision

The author's taxonomy (2026-10-09), each type with one look:

1. **On/off.** Selected dark, not selected light; the label doesn't
   change. Standard: the Reviewers page's column chips.
2. **Cycle.** Every state is a positive choice, so the chip is always
   dark and the label names the state. A deliberate "off" is one such
   state. Standard: Extract's Data shaper "All rows ↔ Rows with data".
3. **Cycle with an unset state.** One state means "not configured yet"
   and takes the amber `pill-empty` fill; the others are dark. Standard:
   the Instruments page's Band 1 link chips.

Applied:

- **Lobby AND/OR and Select all / Clear all** (and the Archived page's
  Select all / Clear all) become type 2: always dark. Select all / Clear
  all is the edge case whose label names the next click, accepted.
- **Extract's three "All … ↔ … with responses/data" chips** become type
  2: always dark, the state still carried by `aria-pressed`.
- **The Instruments Visibility cells stay as they are**: type 2, with
  "—" a deliberate off and so a positive state.

**Rejected:** a light "off" for type 3 alongside amber "unset". The
author's ruling: a deliberate off is a positive state, so it is type 2.

### Semantics

- **Type 2 state** stays where each chip keeps it today (the lobby's
  `localStorage` mode, Extract's `aria-pressed` and stored key); only
  the fill changes.
- **The edge** (`spec/ui_elements.md` §9's reserved shade) is unchanged
  on every chip.
- **Contrast:** the dark fill is `--selected-bg` / `--selected-fg`,
  already audited on `.tag-chip.is-selected`.

### Judgment calls — decided

- Lobby chips take the type 2 look in CSS (the `.tag-mode-chip` and
  `.pill-tag-clear` rules take `--selected-bg` / `--selected-fg`)
  rather than an `is-selected` class, which the lobby's script would
  have to keep from toggling off. (2026-10-09)

### Blast radius (measured)

Taken 2026-10-09 at `49dabecb`.

| What | Count | Command |
|---|---|---|
| Files naming the two lobby chip classes | 4 app, 2 tests, 1 spec | `grep -rln "tag-mode-chip\|pill-tag-clear" app tests spec` |
| Extract chips with `data-label-on` | 3 | `grep -n "data-label-on=" app/web/templates/operator/session_extract_data.html` |
| Tests and specs naming those chips | 2 tests, 1 spec | `grep -rln "data-label-on\|all-reviewers\|Reviewers with responses" tests spec` |

### Status

Closed 2026-10-09. Shipped as planned in two PRs, #2926 and #2927.

- **PR 1 (#2926):** the two lobby chip rules merged into one taking
  `--selected-bg` / `--selected-fg`, allowlisted in
  `test_reserved_shade`. A browser test compares each lobby and Archived
  chip's fill with a selected tag chip's in both labels.
- **PR 2 (#2927):** one `setPressed` helper serves the Extract chips'
  click toggle and `localStorage` restore, keeping `is-selected` on for
  any chip with both `data-label-on` and `data-label-off`. A browser test
  clicks each chip off, reloads, and finds it still dark. Both tests fail
  without their change.
- **Diverged from the ladder:** rung 1's `test_chip_edge` update wasn't
  needed, because the edge rule didn't change.
- **Reads:** one cumulative `diff-reviewer` read (base `f9534903`) found
  no code defects and four low prose and comment findings. Three were
  fixed in #2927; the fourth is the divergence above. A follow-up read on
  the fix commit found two wording gaps, also fixed. The PR 2
  `spec-writer` pass caught that the Data shaper chip keeps
  `aria-pressed="true"`, and the wording was fixed. The close
  `spec-writer` pass found all three doc-impact specs current and dropped
  a provenance date from §9's lead-in.
- **Two ways to carry type 2 state, kept** (author's ruling,
  2026-10-09). The Extract page-level chips use `aria-pressed`; the
  Data shaper chip uses a data attribute and stays pressed. A code
  comment at each says so.

### PR ladder

1. **The taxonomy and the lobby.** `spec/ui_elements.md` §9 states the
   three types; `base.html` gives `.tag-mode-chip` and `.pill-tag-clear`
   the dark fill; `test_chip_edge` / `test_reserved_shade` updated; a
   lobby browser test or integration assertion pins the fill.
2. **Extract's three chips.** (Also `spec/extract_data.md`'s "is-selected
   + aria-pressed driving the visual state" line, which the PR 1
   `spec-writer` pass flagged as false for cycle chips once this lands.)
   Both paths that set their fill keep
   `is-selected` on while flipping `aria-pressed` and the label: the
   click toggle and the load-time restore from `localStorage` (Codex on
   #2923 — the restore toggles the class too). A test reloads with a
   stored off value and finds the chip dark. `spec/extract_data.md` says
   they are type 2. The item's cumulative `diff-reviewer` read runs here,
   from the main SHA before PR 1.

### Definition of done

- `spec/ui_elements.md` §9 defines the three chip types with a standard
  each.
- The lobby AND/OR and Select all / Clear all chips, the Archived page's
  Select all / Clear all, and Extract's three two-state chips render
  dark in every state; a test pins each.
- `guide/things_to_check_in_browser.md` has a section per PR.
- `### Doc impact` current, every bullet checked by hand.
- `spec-writer` run against the doc-impact specs; flags adjudicated.
- `### Status` compacted; `guide/todo_master.md` entry updated.

### Open questions

- None at planning.

### Out of scope

- Chips already matching their type: column chips (1), Data shaper and
  Self-review cycles (2), Band 1 link chips (3), Visibility cells (2).
- Extract's radio-like axis and field chips: one-of-many selection is
  type 1 per chip; unchanged.
- The `btn secondary` AND/OR on Observers and Instruments: buttons, not
  chips.

### Doc impact

- `spec/ui_elements.md` — §9 states the three chip types; the lobby chips' `--surface-muted` fill becomes the type 2 dark fill (PR 1); Extract's three chips join the type 2 list (PR 2).
- `spec/sessions_overview.md` — the tag filter's mode and clear chips are type 2 (PR 1).
- `spec/extract_data.md` — the three empty-row-drop chips are type 2, always dark (PR 2).
- `guide/things_to_check_in_browser.md` — a section per PR.


---

## Item 4 — Observers: one Save for the row and its cohort rule

### Opportunity

On the Observers page, `Add` and `Edit` open the row editor
(`/observers/create`, `/observers/{id}/update`: email, name, tag,
status), but the cohort rule is set elsewhere: only the selection
expander's builder reaches `/observers/cohort-rule`, and only for saved
rows. A new observer cannot get a rule until its row exists, and editing
one means two saves in two places (author, 2026-10-12, with screenshots).

### Decision

The author's ruling, 2026-10-12:

- **One editor.** In add and edit mode the row editor shows the cohort
  builder beneath it, loaded with the observer's rule (empty on `Add`),
  and **one Save** submits both.
- **Savable, or Save is disabled.** A non-blank email and no half-filled
  rule cell (a field chosen without an operand, or the reverse). The
  rule is **optional**: an empty builder saves an observer with no rule,
  who sees nothing (`spec/setup_pages.md` "Cohort match rule editor").
- **The selection expander keeps its builder** for applying one rule to
  several observers at once. *(Amended below.)*
- **Amended 2026-10-12, the author's ruling at rung 3:** selecting rows
  shows no builder; the expander keeps the count and its row actions.
  `Edit` on **one** row opens the row editor above (row and rule, one
  Save); `Edit` on **several** opens the builder alone for all of them,
  the rows staying read-only, its Save applying one rule to each
  (`/observers/cohort-rule`). One editing surface, as `Add new`'s.

Rejected: making a rule required on every save. An imported observer
without one could not have a typo in its name fixed until it was given
a rule.

### Semantics

- **One write.** `create_observer` / `update_observer` take the rule and
  write it in their own commit, emitting `observer.cohort_rule_assigned`
  beside their own event under one correlation id. The rule is validated
  (`CohortRuleSet`) before anything is written, so a bad rule re-renders
  the editor with the operator's values and an error, as a bad email does.
- **Unchanged rule, no event.** An edit that leaves the rule as stored
  writes no rule event; an emptied builder on an observer with a rule
  clears it.
- **Gate** `not is_archived`, as every Observers route.
- **Half-filled cells** are refused by the server too (400 re-render), so
  the disabled Save is a convenience, not the guard.

### Judgment calls — decided

- Save is gated on validity, not on a change: Cancel already discards.
  In the several-row editor (rung 4) it also waits for a change: over
  differing rules the builder arrives empty, and a live Save would clear
  them all in one click — the job the expander's dirty gate did. The
  change is to the form, not to what the rule means: touching `AND`/`OR`
  or adding a blank cell enables Save, which is also the deliberate way
  to clear differing rules in one go (the note says Save replaces them
  all). A meaning-based gate would leave no way to do that.
- The rule's builder is the expander's, not a second copy: one macro,
  `cohort_builder(form_id)`, rendered in both places until rung 4 left
  the row editor its only home.
- The row editor's field select leads with a blank `Choose a field`
  (2026-10-12, rung 3): the default cell was a complete rule (first tag
  preselected), so an untouched `Add` would have saved a rule the
  operator never chose. A blank cell is dropped; all blank is no rule.

### Blast radius (measured)

Taken 2026-10-12 at `ddd589d3`.

- Routes: `app/web/routes_operator/_setup_observers.py` (`create`,
  `update`, `_parse_cohort_rule_form` reused).
- Service: `app/services/observers.py` (`create_observer`,
  `update_observer`; each ends in one `db.commit()`).
- Template: `app/web/templates/operator/session_observers.html` — the
  builder `<template>` renders only `if not edit_mode` today.
- Tests: `grep -rln "observers/create\|observers_create\|observers_update" tests --include=*.py | wc -l` → 10;
  `grep -rln "cohort-rule\|cohort_rule_field" tests --include=*.py` → 8 files.

### Status — closed 2026-10-12

Shipped in four rungs (#2987 plan, #2988 scaffold, #2989 the write and
the gate, #2990 `Edit` opens the editor); rung 4 was added by the
author's amendment at rung 3. The author's browser check passed
2026-10-12.

- **Diverged from the plan:** the selection expander lost its builder
  (the amendment); `Edit` is live at any arity, one row opening the row
  editor and several the builder alone, which posts
  `/observers/cohort-rule` and waits for a change. The row editor took
  over the page's leave guard (`rrwLeaveWillPrompt`).
- **Built:** `cohort_builder(form_id, blank_field)`, one macro;
  `create_observer` / `update_observer` take the rule, validated before
  any write, committed with the row (`observer.cohort_rule_assigned`
  under one correlation id, none when unchanged, never demoting
  `validated`); blank cells dropped, half-filled ones refused (400
  re-render); `CohortRule` refuses a typed operator with no value under
  every writer; `same_cohort_rule` the one comparison (NULL and an empty
  set alike); `views.rule_edit_state` the several-row editor's state
  (Codex on #2990: it had been computed in the route).
- **Reads:** one cumulative `diff-reviewer` read from `af77fa0b` at rung
  4 and a focused re-read of its fixes, plus one of the Codex fix. They
  found a stale key loading into a *disabled* option (left out of the
  submission, so a rename cleared the rule: high), the several-row Save
  live over differing rules, NULL vs an empty set compared three ways,
  `Edit` dropping the filter and page, a rejected save not arming the
  leave guard, `+` copying a stale option, and stale prose. All fixed;
  the form-based several-row gate kept as a judgment call.
- **Found after merge:** #2991's CI caught a timing race in a rung-4
  browser test (Save read once, before the `setTimeout` re-check); the
  test now waits, fixed there.
- **`spec-writer` at close:** one edit — the several-row editor's
  "different cohort rules" note reads the stored rules, so a rejected
  save shows it too (`spec/setup_pages.md`, the `rule_edit_state`
  change).

### PR ladder

1. **This plan.** Prose only.
2. **Scaffold.** In add and edit mode the builder renders under the edit
   row, loaded with the rule, its cells form-associated to the edit form;
   the routes ignore them, and Save keeps today's behavior.
3. **The write and the gate.** The services take the rule; the routes
   parse it; Save disables until savable; tests, a browser-check
   section. ~~Specs and the cumulative read~~ move to rung 4.
4. **Edit opens the editor** (added 2026-10-12, the amendment above).
   The expander drops its builder; `Edit` on several rows opens the
   builder alone for them. Specs, a browser-check section, and the
   item's `diff-reviewer` read on the cumulative diff from rung 2's base
   (`af77fa0b`).

### Definition of done

- Adding an observer with a rule, editing a rule from the row editor, and
  clearing one by emptying the builder each save in one POST, by test;
  a half-filled cell answers 400 with the editor re-rendered, by test.
- Save disabled while unsavable, by a browser test.
- No builder in the selection expander; `Edit` on several rows opens the
  builder alone and saves one rule to each, by test.
- `guide/things_to_check_in_browser.md` has a section per code rung.
- `### Doc impact` current, every bullet checked by hand.
- `spec-writer` run against the doc-impact specs; flags adjudicated.
- `### Status` compacted; `guide/todo_master.md` entry updated.

### Open questions

- None open.

### Out of scope

- ~~The selection expander's bulk builder, beyond sharing its template.~~
  In scope since the amendment.
- Observer CSV import's `CohortRule` column.

### Doc impact

- `spec/setup_pages.md` — the Observers row editor carries the cohort builder and one Save; "Cohort match rule editor" names both places it appears.
- `spec/operator_button_audit.md` — the row editor's Save covers the rule; its disabled state.
- `spec/ui_elements.md` — `.row-expander-body.is-split` serves the row editor; the leave-guard hook names it (added at rung 4).
- `spec/sessions_overview.md` — the "Discard unsaved changes?" string no longer has an Observers user (added at rung 4).
- `spec/settings_inventory.md` — the `cohort_rule` row: "no rule" is NULL or an empty `rules` list (added at rung 4).
- `spec/csv_contracts.md` — `CohortRule`: a typed operator needs a value (added at rung 4; Codex on #2989).
- `guide/things_to_check_in_browser.md` — a section per code rung.
