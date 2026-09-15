# Segment 19P — the expander revamp

**Opened:** 2026-09-14 · **Theme:** re-house selection-driven controls into the
Session Lobby's row-expander idiom, page by page · **Related:**
`guide/roster_expander_revamp_handoff.md`, `guide/new_ux_ideas.md` §1,
`spec/setup_pages.md`

Split out of 19O at 175 lines, when the Reviewers item outgrew the ~120-line
item budget: the work retires three cards, changes five specs and spans four
rungs across six pages. **19O keeps bug fixes**; this segment carries the
revamp.

**Items close independently**, so each carries its own `### Doc impact` and
`### Status`, and there is **no segment-level `## Doc impact`**.
`python3 tools/close_check.py 19P.1` reads Item 1's manifest.

**Items 2–4 are stubs.** They record the sequence and why, not a plan; each is
planned in full when it is taken up.

---

## Item 1 — Reviewers moves to the lobby's expander idiom

Pilot for `guide/roster_expander_revamp_handoff.md` — **Variant B on Reviewers**,
the presentation half of `guide/new_ux_ideas.md` §1, minus consolidation.

### Opportunity

The *"Operator actions"* card does two jobs — a filter strip **and** an action
row whose buttons act on rows selected below, with nothing marking which rows
those are. 19L solved this for the lobby; the roster pages never got it.

Separately, **three cards** hold whole-roster affordances away from the roster
they act on: `#upload-csv` and `.danger-zone` at the bottom, and the
`_field_labels_editor` card at the top, in the left column of `card-columns`.
The author's target: **retire all three** into a roster-level Unlock expander.

### Decision

**Variant B on Reviewers, targeted directly** — author's call, not staged
behind a shippable Variant A. B contains A, so the row expander still lands;
it simply is not a milestone of its own. Reuse `base.html`'s
`.session-expander*` / `tr.session-row-selected` rather than reinventing the
marking. The one-row roster index and its **Unlock** expander absorb all three
cards, which are then deleted.

*The trade:* staging A would leave a shipped fallback if B's surface is wrong.
Rung 1 answers that instead — the whole shape, inert, looked at before wiring.

**The expander renders each roster's own action set** — a helper taking an
action list, not one hard-coding it. Observers has a fourth action
(`cohort-rule`) and no labels editor, so a fixed list is the "list someone must
remember to extend" that 19N.1 inverted its test to escape.

**The Unlock gate extends the page's existing `edit_mode`**, not a ported
`?editing=`. `session_reviewers.html:14` already computes
`edit_mode = (edit_id is not none) or add_mode`; `:102` locks the actions card
and `:276` sets `selectable = not edit_mode and is_editable`. Unlock is a
second mode of the same shape.

**Rejected: Observers last** (the handoff's order). The first three pages are
*identical* in action set, so they cannot falsify the render's shape — finding
on page four that it cannot express Observers means reworking three shipped
pages. Observers goes second, as 19P.2.

### Semantics

- **Arity is preserved verbatim.** `Edit` at exactly one row;
  `Inactivate / Activate / Delete` at one or more.
- **`Activate` / `Inactivate` render only where they are actionable**
  (2026-09-15, mockup). All-active selection offers `Inactivate`; all-inactive
  offers `Activate`; a **mixed** selection offers both. A control that would
  no-op on every selected row is not rendered — the arity rule above says *how
  many* rows an action takes, this says *which* actions that selection admits.
  Driven by each row's `status`, which the render already has.
- **The roster card's control toggles `Unlock` ↔ `Lock`.** Not `Done`: the
  panel is a lock state, and the label should name the state it moves to.
- **`Add` stays page-level**, and keeps its own `is_ready` gate
  (`session_reviewers.html:160`) — which this item does not touch. It renders
  as **`Add new`** in the table toolbar (2026-09-15). Tried in the expander and
  withdrawn: the expander exists only under a selection, so `Add` was reachable
  only after selecting a row it does not act on.
- **Routes are unchanged** — the three bulk routes, the upload POST and
  `delete-all` keep their URLs and hidden-form wiring.
- **No expander when the session is not editable.** One gate, `is_editable`
  (`:146`), matching what hides the action row today.
- **The expander anchors after the most recently ticked row still selected**,
  with DOM order only as fallback — `sessions_list.html:585`
  (`currentAnchor() || selected[selected.length - 1]`). 19L **settled** this
  rather than leaving it open; do not restate it as "the last selected row".
- **Unlock and row-selection are mutually exclusive** — that is the gate.

### Judgment calls — decided

- **2026-09-14.** Reviewers only; Observers next as 19P.2, so the divergence is
  proven before the mechanical pages are touched.
- **2026-09-14.** **No Variant-A milestone** — author's call. A shipped
  row-expander-only step would have to be un-shipped by B's index row two
  slices later, and the handoff's case for A standing alone assumes the cards
  stay, which here they do not.
- **2026-09-14.** All three cards are **deleted**, not hidden behind a flag —
  author's call, confirming what `guide/new_ux_ideas.md:67-76` already put in
  the roster row. A flag leaves two live surfaces for one action.
- **2026-09-14.** `.session-row-selected` is promoted past "**Not a general
  primitive**" (`spec/ui_elements.md:592`), which withheld the transfer and
  named a Rosters index as the speculative third caller — this is that caller.
  The edge it was not designed against (`new_ux_ideas.md:270-279`: *the row can
  sit above a tall panel or scroll off*) is live here, since Unlock is such a
  panel; rung 1 answers it on the dev slot, not in a test.
- **2026-09-15.** **Mockup before code**, after the revert: an HTML mockup on
  the app's own `base.html` tokens, iterated to seven versions with the author
  before a line of template was written. The four shape decisions below all
  came out of it, and each contradicts something rung 1 had already shipped.
- **2026-09-15.** **The roster index is a row of readouts, not a one-row
  table.** A `<table>` for a single row spends header chrome on nothing — and
  the cold read on the reverted build found the concrete cost: index row and
  expander in one table share `:first-child` / `:last-child` padding rules, so
  the two could not be spaced independently.
- **2026-09-15.** **Page guidance moves to the top, full width**, above the
  roster card, its prose in **two columns** when open. At full page width one
  measure runs ~150 characters. This takes it out of `.card-columns`, which is
  then empty on this page — reversing the blast-radius note below.
- **2026-09-15.** **The `Operator actions` card retires whole**, rather than
  keeping a filter strip. Its contents become a two-pane toolbar inside the
  preview-table card. Answers open question 1.
- **2026-09-14.** **No Download.** The handoff's Unlock panel has one; this page
  has none (`grep -cin 'download\|export'` → 0) — the roster CSV is on Extract
  data (`_extracts.py:108`). Adding it would be a new capability.

### Blast radius (measured)

At `46688cb`:

- `wc -l app/web/templates/operator/session_reviewers.html` → **728**;
  `grep -c operator-actions` → **5**; `grep -c edit_mode` → **19**.
- Cards retired: `#upload-csv` (`:624`), `.danger-zone` (`:690`) and the
  `_field_labels_editor` card (`:91`, 111 lines). The last sits inside
  `card-columns` (`:48`) — which **stays a two-column container**: page
  guidance shares that left `<div>` (`:49-78`) and remains. `spec/setup_pages.md:94`
  becomes "guidance alone on the left"; `.card-columns` itself is not removed,
  and `:78-91` argues at length that it must not be.
- `grep -oE 'formaction="[^"]*"' | sort -u | wc -l` → **3 / 3 / 3 / 4** and
  `grep -c 'setBtn('` → **4 / 4 / 4 / 5** across
  reviewers / reviewees / relationships / observers.
- `grep -c 'session-expander\|session-row-selected' base.html` → **18**;
  `#single-session-expander` (`sessions_list.html:185`) and `#bulk-expander`
  (`:243`) carry live `formaction`s — only the two `data-expander-delete`
  buttons (`:237`, `:285`) are `disabled`, a two-stage gate. The template's
  comment (`:182-184`) still calls them placeholders, **stale** since
  `d2c8671` — the handoff's error came from there, and rung 1 fixes it.
- `grep -rl 'reviewers/bulk-\|reviewers/delete-all\|danger-zone\|upload-csv'
  tests/ --include=*.py | wc -l` → **15**; narrowed to
  `reviewers/bulk-\|reviewers/delete-all` → **6**. Two of that six move —
  `test_reviewers_page_mutate.py`, `test_setup_danger_zone_delete_all.py`.
  `test_setup_selection_lifecycle.py` also moves and is **not** in either
  count: it parameterizes the page (`f".../{page}/bulk-delete"`), so no
  literal matches.
- Specs, by `grep -ci` on *danger zone* / *upload card* / *operator actions*:
  `setup_pages.md` **12/8/16** (the owner), `operator_button_audit.md`
  **12/0/28**, `operator_ui_concept.md` **7/2/3**, `ui_elements.md` 1/0/2,
  `rrw_functional_spec.md` 4/1/0 — all five are in the manifest.

### Status

**2026-09-15 — rung 1 shipped, was wrong, and was reverted.**

`#2393` and `#2394` landed the scaffold; `#2395` reverted both. `main` is
byte-identical to the pre-scaffold base (`3f7d5b6`), suite back to 3,955.
Nothing else had landed between, so the revert is clean.

**The Decision stands; its *surface* did not.** Variant B, the reuse of
`.session-expander*`, the three retired cards, the `edit_mode` gate and the
anchor rule are all unchanged. What the dev slot rejected was the shape the
plan had sketched around them, so the shape was re-agreed by **mockup** before
any further code. The ladder below is unchanged in sequence; rung 1's
*content* is now the mockup, and these five points are the diff:

1. **Roster index**: a row of readouts inside the card — `Reviewers roster:`
   + count, `Populated columns:` + one pill per column — with `Unlock` bottom
   right. Not the one-row table the ladder implied.
2. **Unlock panel**: two columns — upload left, tag labels over Danger Zone
   right.
3. **Page guidance**: top of the page, full width, two-column prose when open.
4. **`Operator actions`**: retired whole; its filter strip and `Add new` /
   `Search` become the right pane of a toolbar **inside the preview-table
   card**, with `Show columns:` and `Showing N of M` as the left pane.
5. **Status-aware `Activate` / `Inactivate`**, and `Unlock` ↔ `Lock`.

**Decisions confirmed at build:**

- **`Populated columns` counts are not free.** The Decision called them a
  re-house of the `col_data` the preview already computes; `views.chip_slots`
  returns a boolean **presence** map, so `Name (154)` needs its own query.
  `slot_row_count` / `tag_slot_counts` — counting twins of `slot_has_data` /
  `tag_slot_presence` — are rung 1's, and presence must derive from the counts
  rather than being a second query answering the same predicate.
- **The two confirms must agree.** The reverted build's replace confirm read
  *"replace the existing 0 reviewers and discard the existing 0 reviewer
  responses"* on an empty roster and dropped the assignments clause the live
  card names, while the Danger Zone confirm three elements away still named it.
  One panel, two accounts of the same destruction. Both confirms name the same
  losses and suppress a clause at zero, as the live cards already do.
- **The guidance summary is already specced as card-header type**
  (`spec/setup_pages.md:52-54`); rung 1 shipped it link-coloured. Conformance,
  not a new decision.

**2026-09-15 — rung 2 splits in two.** Author's call, after asking when
the search box moves. As written, rung 2 carried three independent
changes: the row-action wiring, the `Operator actions` retirement, and
point 3's guidance move. They split on a clean seam — **layout above the
table** versus **behavior in the table** — and the layout half is what
the search box rides on. So:

- **2a, the toolbar move.** Guidance to the top, full width. The filter
  strip moves into a toolbar inside the preview-table card — right pane
  the status / search controls and `Add new` / `Search`, left pane
  `Show columns:` and `Showing N of M`. **The card is not retired
  here**, only slimmed: it keeps the row-action row and the Add / Edit
  block. No row action is wired.
- **2b, the row actions and the retirement.** They move into the
  expander, and the card — by then holding nothing else — is deleted.

**The card cannot retire in 2a**, which the split's first draft had it
doing. It holds the **only live** `Edit` / `Inactivate` / `Activate` /
`Delete` controls and their `formaction`s; rung 1's expander copies are
all `disabled` until 2b. Retiring it first would remove four working
actions for a slice, and carrying them into the toolbar meanwhile would
reproduce the crowded strip this segment exists to undo, then move them
again. Slimming it costs one intermediate state and moves each control
exactly once.

Two things the ladder never named, found when the seam was cut:

- **The `Operator actions` card also holds the Add / Edit block** — a
  divider, a heading, the help line and Save / Cancel, rendered only in
  `edit_mode` (`session_reviewers.html`, `.operator-actions-divider`).
  It stays with the card through 2a and is rehomed when 2b deletes it:
  its own card in the same position, still `edit_mode`-only, because
  folding an editing form into a filter toolbar mixes two jobs in one
  strip.
- **`.card-columns` is left holding the tag-labels editor alone**, half
  width in the left column, from 2a until the Unlock rung deletes it.
  A known intermediate look (`spec/ui_elements.md` names the lone-card
  case for `.bottom-grid`), and the alternative is pulling the Unlock
  rung's deletion forward into a layout slice. In 2a it shares the
  container with the slimmed `Operator actions` card, so the lone-card
  state does not begin until 2b.

**What 2a's cold read caught, before ready** (the pre-ready gate working,
after `#2394`'s read landed post-merge):

- **A shared primitive redefined for one page.** `.table-card-toolbar` is
  used by **seven** templates; only Reviewers has panes. Turning the
  shared rule into a two-column grid made the other six templates' direct
  children grid items — Observers' toolbar holds the pager alone, which
  would right-align inside the *left half* instead of across the card.
  The grid now rides an `is-split` modifier. **The lesson generalizes to
  2b:** check the user count before editing a `base.html` class.
- **A gate that reached further than it looked.** `Add new` moved into
  the preview-table card, which is gated on the roster having rows — so a
  brand-new session had no way to add its first reviewer at all. Before
  the move `Add` sat in the always-rendered `Operator actions` card. Every
  gate on that card is now a gate on the filter and on `Add new`, which is
  the same trap as the zero-match `Clear`, one state over.
- **A lock that stopped reaching its target.** The filter greys out during
  an edit (15F PR 3) via `.operator-actions-card .operator-actions-main
  .is-locked`; the moved form is inside neither. The class shipped as
  decoration until a rule was addressed to its new home.
- **Two tests that could not fail** — one pinning a literal nothing emits,
  one reading a pane that renders empty on its own fixture. Both were the
  same root cause as `#2393`'s: asserting against a render not built to
  produce the thing asserted. The fixture now paginates, and `_markup()`
  strips the inline `<style>` block that satisfies any bare class-name
  `in html`.
- **Rejected:** the read called the `is_editable` wrapper on `Add` a new
  behavior change. It is pre-existing — `9ba9500:340` already wrapped it,
  and the unreachable `is_ready` branch inside it with it.

**2026-09-15 — the base rule lands BEFORE rung 2b.** Author's call.
Recorded here first as *"two for the close, not for a slice"*; promoted
because 2b moves four more live controls out of the same card, so the
trap would get its third chance before the close ever arrived. Ladder
gains rung **2a′**, below.

- **The filter-strip shape was declared in four scopes with no unscoped
  base** — `.filter-card`, `.operator-actions-card`, `.toolbar-right`
  and `.field-labels-actions` each restated the same six declarations,
  which is why moving the strip out of one card dropped two rules in
  two separate slices (`is-locked`, then `filter-actions`'
  `margin-top`). **Three of the four** are now one unscoped base
  narrowing **6 declarations between them, down from 49**.
  `.field-labels-*` **stayed out**, deliberately: different class
  names, a 3-up grid rather than a filter row, and only the
  `margin-top` value in common. Folding it in would be a second
  refactor wearing the first one's justification. It remains a private
  copy; if a third move ever loses a rule there, this is the note that
  predicted it.
- **`.operator-actions-card .operator-actions-buttons` is dead** — no
  template uses it, repo-wide. Pre-existing; still retires with the
  card in 2b.

**2a′'s cold read landed after the merge** (`#2403` merged on green
before it returned). Nothing defective shipped — the refactor is
behaviour-preserving, now proven over 7 pages / 44 elements rather than
6 / 37 — but two findings were real and are follow-up rather than
pre-merge:

- **Two of the base's five rules were inert.** `body.ui-v2 select` /
  `input[type="text"]` is (0,1,2)/(0,2,2) and outranked the unprefixed
  `.filter-row select` (0,1,1). It sets the *same* `width` and
  `box-sizing`, so nothing rendered differently — which is precisely
  why neither the parity check nor a reading caught it. Latent, not
  live: the day that global rule changes, all seven strips follow it.
  Prefixed, and `width` / `box-sizing` added to the guard.
- **The guard covered two of the three scopes** and could not see a
  *fourth* scope appearing, which is the only direction the four-copy
  shape ever grew from. Now enumerates every rule selecting the shape
  and requires each to be the base or a known scope.

**And its own cold read found the guard still weaker than claimed.**
The enumeration was a line-anchored regex, so it saw only the last
selector of a comma list split across lines — including, exactly, the
rule the same slice had just added. It had no vacuity guard, so
renaming the shape made it pass by matching nothing, and its closing
assertion was built from the set it compared against and could not
fail. Rewritten on a brace-to-brace parser with floors at both ends.
The parity tool had the same shape of hole: empty snapshots printed
"0 differences" and exited 0. Both now fail loudly, and the tool
reports **covered** pages rather than rendered ones — `assignments`
renders and carries no strip, so the honest figure was always 6 of 7,
never 7.

**Decided at build, 2a′:** the base is unscoped *except* its generic
`> label` rule, which takes a `body.ui-v2` prefix to outrank the global
`body.ui-v2 label` (0,1,2) — without it every label reverts to
`display: block` and un-stacks from its input, which also blockifies the
select. Measured, not reasoned: the first cut of the base shipped
without the prefix and a before/after computed-style diff across 6 pages
caught it. The prefix must **not** spread to the `.filter-status` /
`.filter-search` rules, where at (0,3,2) it would outrank
`.operator-actions-card`'s only narrowing. Both facts are now tests.

Also found: the slice's own comment and commit message claimed two-column
guidance prose that was never ported from the mockup. Implemented as a
macro opt-in (`guidance(full_width=true)`), since the other six placements
are half-width where two columns would be two ~30-character ribbons.

### PR ladder

*Sequence unchanged; rung 1's content is superseded by `### Status` above, and
rung 2 no longer leaves a filter strip behind — there is no card to leave it in.*

1. **Scaffold — the whole B surface, inert.** Bracket, row expander, one-row
   index and Unlock panel, with real copy and layout and no wiring; the three
   cards still present and still live. This is the slice that gets looked at
   on the dev slot before anything moves. Must not touch `spec/`.
2. **Wire the row actions.** They move into the expander, arity preserved,
   routes unchanged; the action row leaves the card, which keeps the filter
   strip. Must not touch `spec/`.
   *Split 2026-09-15 into **2a** (the toolbar move) and **2b** (the row
   actions); the "keeps the filter strip" clause is superseded — the card
   goes. See `### Status`.*
   * **2a′, inserted 2026-09-15 between them.** The filter-strip CSS
     becomes one unscoped base the three card scopes narrow. Pure
     refactor: no markup, no copy, no behavior — proved by a before /
     after computed-style diff over 6 pages (0 differences). It goes
     **before** 2b because 2b moves four more live controls out of
     `.operator-actions-card`, and the two rules already lost to that
     card's private copies were each found on the dev slot rather than
     by the suite. Touches `spec/` only via a Doc impact bullet; the
     §10 edit is still rung 4's.*
3. **Wire Unlock and retire the three cards.** Upload, Delete-all and the
   friendly labels move into Unlock; `#upload-csv`, `.danger-zone` and the
   `_field_labels_editor` card are deleted; the gate extends `edit_mode`.
   Must not touch `spec/`.
4. **The specs, last** — after the cold readers, so the pre-push `spec-writer`
   pass is the final word; the ordering 19O.3's close left untested. **The
   shared-shape problem is this rung's:** `setup_pages.md:47` and `:525` state
   one shape for all **four** pages; `operator_ui_concept.md:258` states one for
   the **three** roster Setup pages. This item changes one, so rung 4 states
   **two** shapes in each — Reviewers' and the others' — naming 19P.2 next.

### Definition of done

- The rendered page carries the bracket class and an expander node beneath the
  anchor row, asserted server-side. *No JS runtime in the suite, so tests assert
  the mechanism — classes, markup, routes — not appearance; 19L stated the same
  limit (`archive/segment_19L_ux_refinements.md:207-209`).*
- `Edit` enabled at exactly one row, the other three at one or more, asserted.
- `grep -c 'id="upload-csv"\|danger-zone' session_reviewers.html` → 0, and the
  `_field_labels_editor` include appears **once**, inside the Unlock panel —
  the partial survives as a file (Reviewees and Relationships still include it)
  and is re-used there, not duplicated.
- Upload, delete-all and the label save each fire from inside Unlock,
  asserted by route.
- `edit_mode`-style locking: with Unlock open the preview renders
  non-selectable, asserted server-side.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19P.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

1. ~~**Does the filter card shrink** once it holds no actions?~~ **Answered
   2026-09-15 by mockup:** it does not shrink, it goes. The filter strip becomes
   the right pane of a toolbar inside the preview-table card.

### Out of scope

- **Consolidating the four pages.** `guide/new_ux_ideas.md` §1; unchanged.
- **A shippable Variant A.** Declined above; B contains it.
- **The other three rosters.** Observers is 19P.2 and proves the divergence.
- **New capabilities** — including **Download**, per the judgment call above.

### Doc impact

- `spec/setup_pages.md` — § *Shared body shape* items 4 and 6 and its `.card-columns` table row (`:94`, which sites the tag-label editor in the left column), § *Operator actions card*, § *Deleting the selected rows*, § *Per-row Edit / Add / bulk actions*, the Reviewers § *Body grid* and § *Implementation pointers* re-describe the expander and the Unlock panel. The two bottom-card sections lose their **card** description; their **route contract** — `confirm` / `confirm_replace` / `acknowledge_response_loss`, the failure modes, the three-state wording — is preserved verbatim, only re-homed. **Added 2026-09-15 by the mockup:** item 0 calls the guidance card *"a **half-width card**"* (`:52`) and the page's row of the `.card-columns` table (`:94`) sites *every* card above the preview table in that container — on Reviewers the guidance becomes **full width above the container** and `.card-columns` then has no tenant, so that row states the container is absent on this page. The § *Operator actions card* section retires rather than shrinking, and the preview-table section gains the two-pane toolbar that replaces it (Item 1).
- `spec/operator_button_audit.md` — the Reviewers actions-strip rows move to the expander; rows **105 / 106** (`:220-221`, the tag-label Cancel / Save labels) and rows **35 / 37** (`:223`, `:233`, whose cells site the button "below the preview table") are **re-sited into Unlock, not retired** — their routes and destructive role survive; the `> Upload and Danger Zone buttons — must be absent, not disabled` gate (`:211`) is reframed around an Unlock panel rather than two cards; and the `.btn.destructive` "outside a danger zone" sentence (sibling of `ui_elements.md:368`) is restated for the expander (Item 1).
- `spec/operator_ui_concept.md` — the shared Setup shape (`:258`, stated for the **three** roster pages) changes at items 3, **4** (`:265`, the leftmost checkbox column "drives the operator-actions selection" — after this it drives the injected expander), 5 and 6, and gains the roster index row. **Added 2026-09-15:** the one-sentence body shape at `:92` spells the container out — *"one `.card-columns` holding guidance and the friendly-label editor on the left, the **Operator actions card** on the right"* — and `:264` states that pair as the container's right-hand half; both describe a layout this item removes from Reviewers, so each states the two shapes rung 4 already owes (Item 1).
- `spec/ui_elements.md` — `.session-expander*` and `tr.session-row-selected` stop being lobby-only, and §6's `.btn.destructive` note stops siting the roster Delete "between `Add` and `Search`". **Added 2026-09-15:** §10 gains the preview-table toolbar's two bare panes — card geometry, no border, fill or padding — which `:637` already distinguishes from `.card-columns` and now needs a name of its own (Item 1).
- `spec/operator_button_audit.md` — **added 2026-09-15 by rung 2a's cold read:** row **125** (`:227`) states the Reviewers `Add` label *and* the reason it is short — *"`Add` and `Delete` must both fit this row"*. Rung 2a renames the shipped label to `Add new` and dissolves that constraint (Delete leaves for the expander, so the two are no longer on one row), so the cell and its rationale sentence are both stale. `spec/setup_pages.md` says the same thing twice more — `:241` and `:536` list `Add` in the Operator-actions control set, and `:543` repeats the one-row rationale. A **rename**, which the bullet above covers only as a move (Item 1).
- `spec/ui_elements.md` — **added 2026-09-15 by rung 2a′:** §10's layout-primitive table gains the filter strip. It was three private per-card copies and is now one unscoped base (`.filter-row`, `.filter-row > label`, `.filter-actions`) with three named narrowings, which is what §10 exists to record. Names the `body.ui-v2` prefix on the generic label rule as load-bearing specificity, not scoping (Item 1).
- `spec/ui_elements.md` — **added 2026-09-15:** §10 states the `#<noun>-table-card` fragment as the **pager's** contract (*"the route supplies the id, the pager never derives it"*). The filter strip's controls now take the same anchor, and entering edit mode takes a second one, `#<noun>-row-editor`, because the editor is split across two cards. §10 should state the landing contract once, for both. `spec/setup_pages.md` § *Search + filter strip* describes the strip with no landing behavior at all (Item 1).
- `spec/rrw_functional_spec.md` — the Danger Zone and Upload card descriptions at §§ around `:1044`, `:1111`, `:1113` retire (Item 1).
- `guide/roster_expander_revamp_handoff.md` — dated annotation recording the four claims 19O.4 falsified (Item 1).
- `spec/color_tokens.md` — `:425` and `:448` describe `.page-guidance` as *"the `What this page is for` disclosure on every Setup page"* and argue its anchoring; the token set is unchanged, but the Reviewers placement the argument assumes is not, so the sentence is re-sited (Item 1).

- `spec/settings_inventory.md` — §2.5's *Surface → Edit* line (`:140-141`) sites the labels editor as an "Inline editor card **above the data table** on `/operator/sessions/{id}/reviewers`"; that is the position this item moves, stated per page (Item 1).

- `spec/csv_contracts.md` — its one editor mention (`:77`) is non-positional, and the friendly-label **header grammar** it owns is untouched by where the control renders (Item 1). <!-- doc-impact-waived: deliberate exclusion — the mention is non-positional and the header grammar is untouched by where the control renders -->

---

## Item 2 — Observers, the divergence proof

**Not yet planned.** Second, deliberately, and not fourth. Observers is the only
roster that differs: **4** `formaction` targets and **5** `setBtn(` lines against
3 and 4 on the other three, an extra row action (`cohort-rule`), and **no**
`_field_labels_editor` — so its Unlock panel is missing that half of the right
column rather than rendering it blank.

Reviewers / Reviewees / Relationships are *identical* in action set and so
cannot falsify the expander's shape. Proving it on Reviewers and then Observers
tests both ends in two items; leaving Observers until last risks reworking
three shipped pages. 19N.1 paid for the same mistake — a blast radius that
counted callers could not falsify the claim it was making, and took three
verification passes to close.

---

## Item 3 — Reviewees and Relationships

**Not yet planned.** Mechanical once Items 1 and 2 land, and measurably so:
both match Reviewers exactly on action set (3 / 3) and arity (4 / 4), and both
carry a labels editor. Likely one item, possibly one PR each.

The one watch-item is Relationships: its rows are reviewer→reviewee **pairs**
and its labels are *pair-context*, so its `Edit` acts on a pair, not a person.

---

## Item 4 — Invitations and Responses — a different move, not the same recipe

**Not yet planned, and its container is undecided.** It sits here to be
sequenced, not to claim the segment: whether it becomes 19P Item 4 or **19Q**
is settled after the four rosters land, when there is evidence about how well
the idiom travels. Author's call, 2026-09-14.

**It is also not the same work.** Measured on `session_invitations.html`
(298 lines) and `session_responses.html` (221): **zero** `operator-actions`
cards, **zero** `formaction`s, **zero** `setBtn(` lines, **zero** selection
checkboxes. Their `<thead>` buttons are column sorts, and each row carries a
single link to a detail page (`session_invitations_reviewer_detail.html`,
`session_responses_reviewee_detail.html`).

So there is **nothing to re-house**. The roster revamp moves existing controls;
here the equivalent move is a redesign — replacing *navigate to a detail page*
with *select a row, see its detail in the expander* — which would add selection
where none exists and make two detail pages redundant or secondary.

That may well be right, and it is the same principle (put the thing beside the
row it belongs to). But it is a **new capability**, so it needs its own
Opportunity and its own decision about the two detail pages, and it should not
inherit the roster items' "re-houses, adds nothing" justification — which is
also the argument for letting it become its own segment if the rosters show the
idiom does not carry.
