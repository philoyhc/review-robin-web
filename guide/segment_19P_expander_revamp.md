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

*Compacted at close, 2026-09-16. The running log this section carried
while the item was open is in the commits and the PR bodies; what
follows is intended-versus-done. Nothing above this section was
touched — Opportunity, Decision, Semantics, Judgment calls, Blast
radius and the PR ladder stand as written.*

**Shipped 2026-09-15/16 across 21 PRs, `#2393`–`#2414`.** The Reviewers
Setup page now renders: full-width guidance, a roster card whose
**Unlock panel** holds the tag-label editor, the Danger Zone and the
CSV upload card, and a preview table carrying the filter strip in its
own toolbar and the selection actions in an injected row expander.
Nothing renders below the table. `spec/setup_pages.md` § *Reviewers
page* is authoritative for the result; this section records how the
ladder got there and what it cost.

#### What the ladder became

| Planned | Shipped |
|---|---|
| rung 1 — scaffold | `#2393`/`#2394`, **reverted** by `#2395`, re-planned from a mockup, re-landed `#2397` |
| rung 2 — wire + retire | split **2a** (toolbar move), **2a′** (filter-strip base rule), **2b** (row actions + retirement, in three steps) |
| — | a **UI pass** between 3a and 3b, off the dev slot |
| rung 3 — Unlock | sliced **3a** labels, **3b** Danger Zone, **3c** upload |
| rung 4 — specs + close | three slices in one PR (`#2414`) |

**Rung 1 was reverted, and the Decision survived it.** `main` went back
byte-identical to `3f7d5b6`. Variant B, the `.session-expander*` reuse,
the three retired cards, the `edit_mode` gate and the anchor rule were
all unchanged — what the dev slot rejected was the *surface* the plan
had sketched around them. It was re-agreed by **mockup** before any
further code, and the mockup is the diff: a roster **index row** of
readouts rather than a one-row table; a two-column panel; guidance at
the top, full width; `Operator actions` retired whole rather than
slimmed; and status-aware `Activate` / `Inactivate`.

**Rung 2 split because the author asked when the search box moves.** As
written it carried three independent changes. The seam is *layout above
the table* versus *behaviour in the table*, and the layout half is what
the search box rides on. **The card could not retire in 2a** — it held
the only live `Edit` / `Inactivate` / `Activate` / `Delete` and their
`formaction`s, with rung 1's expander copies all `disabled` until 2b —
so 2a slimmed it and 2b deleted it, which moves each control exactly
once at the cost of one intermediate state.

**2a′ was promoted out of the close.** The filter-strip shape was
declared in four scopes with no unscoped base, which is why moving the
strip dropped a rule in two separate slices. Three of the four are now
one base narrowing **6 declarations, down from 49**;
`.field-labels-*` stayed out deliberately (different class names, a
3-up grid, only `margin-top` in common — folding it in would be a
second refactor wearing the first one's justification).

**Rung 3 was sliced on each card's route shape, measured before
cutting.** `delete-all` and `field-labels` both 303; the import
**re-renders in place** on a failure, with its issue list inside the
card the panel absorbs — so the import went last and carries the
panel's start-open work. Each slice **wires and deletes its own card in
one commit**, because `sync` resolves a confirm's button by first-match
`querySelector`: two live keys on one page gate the wrong button.

#### Decisions confirmed at build

- **`Populated columns` counts are not free.** The Decision called them
  a re-house of `col_data`; `views.chip_slots` returns a *presence*
  map, so the counts needed their own query (`slot_row_count`), and
  presence now derives from the counts rather than asking the same
  predicate twice.
- **One panel must not give two accounts of one destruction.** Both
  confirms name the same losses and suppress a clause at zero.
- **The labels editor is one include in two positions**, not a copy:
  the panel where it can render, `.card-columns` on the exact
  complement. The panel is *suppressed* rather than disabled on a
  locked session, because a locked page must carry no `Save labels`
  anywhere — but it must still let an operator **read** the labels, and
  the roster readouts do not cover that (they pill only columns that
  hold data). Rejected: a read-only display in the roster card
  (net-new UI, wants the slot), and dropping the locked view (would
  have meant rewriting a test that encodes a deliberate rule).
- **`.card-columns` survives**, contrary to the rung-3 cut table, which
  3a falsified without saying so and 3c confirmed. It is that fallback
  home's container; removing it would widen the locked-state editor
  from half the page to full.
- **The partial replaced the scaffold's hand-copy, not the reverse** —
  it already took every parameter and brought a dirty-check the copy
  lacked. Measured in Chromium: `.field-labels-actions` and
  `.unlock-col-actions` compute identically, so no rule followed the
  markup.
- **The Danger Zone's roster-count gate stays**, and for a worse reason
  than first recorded: the route does *not* refuse an empty delete-all
  (it answers 303 and writes "Deleted all 0 reviewers"), but
  `_delete_all` invalidates a `validated` session before counting, so
  an ungated one demotes to `draft` while deleting nothing.
- **Both panel buttons right-align.** Unlike 3a's swap, `.btn-pair` and
  `.unlock-col-actions` do *not* compute alike (16px/flex-start vs
  8px/flex-end), so this was a choice: one alignment for the panel.

#### Scope that moved

- **A row action landed at the top of the document** — measured at
  **821px** of jump. Fixed in the UI pass by naming the acted-on row.
  Found while building it and worse: `offset` was carried by **none**
  of the 17 `_redirect_keeping_selection` call sites, so an action on
  page 2 answered with page 1 and no anchor could resolve. Reviewers
  only; the helper's new parameters default to today's behaviour, so
  the other three pages are untouched — **and still carry the defect.**
- **No-JS reachability**, raised by 19P.1's own cold read and
  independently by Codex as a P2. Rung 3 put all three cards behind a
  panel opened only by an inline handler. Fixed with a `<noscript>`
  link to `?unlocked=1`, restoring the empty-roster import and the
  ability to read the cards — *not* the replace path, which the
  confirm-pairing script has gated since before this segment.
- **A `.confirm-label` defect 3c introduced**, found only in a
  screenshot: moving a label onto the class brought `display: flex`
  with it, detaching the closing "." from its pill by 12px (4px after
  wrapping the sentence, which is the pill's own margin).

#### What this item kept getting wrong, for 19P.2–.4 to read

Three failure modes recurred often enough to be the item's real
lesson, and every one of them will be available again on the next page.

1. **A needle that matches something the page renders anyway.** Six
   times. `base.html` inlines the whole app's CSS and JS on every
   response, so `scrollIntoView`, `danger-zone`, `bottom-grid` and the
   page's own prose all match page-wide — one assertion passed against
   a CSS *comment*, and `assert "disabled" in card` is satisfied by
   `aria-disabled="true"`. One was created while fixing another; one
   was committed inside the test whose docstring is about the trap. The
   sixth aimed it at the **test suite** instead of the page: a
   uniqueness claim from grepping for a literal string that a sibling
   test reached through a helper. **Measure the needle against a real
   response before writing the assertion.**
2. **A page's spec falsified by a change to a page it merely cites.**
   Eight sentences defined one roster page as "the same shape as"
   another; a grep for the changed page finds none of them.
3. **A confident sentence that is simply false.** Seven distinct ones
   across the item: the route that "would refuse" an empty delete-all;
   "the only assertion in the suite"; "the macro takes no arguments";
   "closing the panel is the Lock control's job and nothing else's";
   `?focus=` "puts the caret in its name field" (it only relocates the
   pager window — a mechanism that does not exist, described in two
   files); the lock card's "different neighbour"; and, inside the note
   recording this very lesson, "every hedge names the item that will
   remove it". **Four of the seven shipped in two or three places
   each, and three outlived a correction applied to one copy** — the
   Lock claim and the neighbour claim were each fixed in one file and
   left standing in another, caught only by a second reader.

   The spec cold read found **fifteen**, ten of them plain errors about
   one page rather than artifacts of specifying it mid-migration; the
   close pass then found **four more**, three in the files the first
   read had not covered. Neither count was reachable by any test: the
   suite was green at 4,049 throughout.

Also worth carrying: **a mutation that edits more than the rule under
test inflates the number it exists to measure.** A `str.replace` with
no count hit three `{% endblock %}`s and reported 2 failures where the
honest answer was 1.

#### Left for later, deliberately

- **19P.2 (Observers)** owes: the `offset`/anchor fix, and the same
  `_field_labels_editor` absence its Decision already names.
- **19P.4's close** owes the consolidating sweep that un-hedges the
  per-page spec wording — see the note above Item 2.
- **The partial's markup**: `_field_labels_editor.html` renders `<div
  class="card">` with a bare `<h2>` while the panel's other two tenants
  are `<section aria-labelledby>`, so one of three regions is
  unlabelled. Closing it means editing a partial three templates share.
- **`guide.html:174-177`** tells operators they edit tag labels
  "through the Reviewers, Reviewees and Relationships pages", which on
  Reviewers now means clicking Unlock first, and says nothing about it.
- **`.confirm-label` should stop using `gap` for what is really the
  checkbox's margin**, which would make the sentence wrappers
  unnecessary. It changes a primitive four pages render, so it was
  recorded rather than done.
- **The dev slot's open question**: whether the Danger Zone's amber
  framing reads well inside the panel's own frame.

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
   *3a amended the middle clause: the `_field_labels_editor` card is **not**
   deleted. It has two homes — the panel, and its old one on the
   complement of the panel's condition — because a locked page must still
   show the labels while carrying no "Save labels". See `### Status`.*
   *Sliced 2026-09-15 into **3a** (labels), **3b** (Delete-all) and **3c**
   (Upload), cut on each route's response shape — see `### Status`. Each
   slice wires its control and deletes its old card together; 3c also
   owes the panel a server-rendered start-open state, which the ladder
   never named.*
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
- ~~`grep -c 'id="upload-csv"\|danger-zone' session_reviewers.html` → 0, and the
  `_field_labels_editor` include appears **once**, inside the Unlock panel~~ —
  **both halves falsified, deliberately, and annotated at 3c's close rather
  than quietly missed.** Measured at rung 3's end: the grep is **5** and the
  include appears **twice**. Neither is drift. `danger-zone` stayed because it
  is the only reach for the amber warning framing three sibling pages keep
  (3b); `id="upload-csv"` travelled with the card because it costs nothing and
  is the card's identity in this page's tests (3c); the second include is 3a's
  locked-state fallback home, on the exact complement of the panel's condition,
  which is one include in two positions rather than a duplicate. The criterion
  was written assuming "moved into the panel" meant "the old strings are gone",
  and three slices each found a reason that was too strong. The partial does
  still survive as a file and is re-used, not duplicated — that half holds.
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
- `spec/lifecycle.md` — **added 2026-09-15 by rung 3b's cold read, and this file is on NO existing bullet. Widened by 3c.** `:347` and `:401` both say "the mutating-card grid (Upload, Danger Zone) is hidden" when a session freezes. The gate behaviour is unchanged, but the stated home of **both** named cards is now wrong, not just the Danger Zone's: 3c moved the Upload card into the Unlock panel too, and **the grid itself no longer exists on Reviewers**. So the sentence names a container that is gone and two cards that are elsewhere. §5 is where `operator_ui_concept.md:267` points for this card (Item 1).
- `spec/visual_style_rrw.md` — **added 2026-09-15 by the same read:** `:262` sites the Danger Zone "at the bottom-right of the page (or in the bottom row of a `.bottom-grid`)", which rung 3b falsifies. The only existing bullet for this file names `:79`, and that bullet says in as many words that the blast-radius grep missed the file once already — so it missed a second line in it. Also price at rung 4: if the amber framing is ever dropped inside the panel, `:241` and `spec/ui_elements.md:188-195` become false of Reviewers as a matter of pixels, not placement (Item 1).
- `spec/setup_pages.md` — **added 2026-09-15 by the UI pass's cold read:** `:861-865` states the row-action redirect contract for all four pages — it "preserves the row selection (`?selected=`) and the active search / status filter". On Reviewers it now also carries `offset=` and a `#reviewer-row-<id>` fragment, and `:644`'s delete redirect carries `offset=` and `#reviewers-table-card`. Stated per page, since the other three are unchanged (Item 1).
- `spec/ui_elements.md` — **added 2026-09-15 by the same read:** §10 states the landing contract as `#<noun>-table-card` with `scroll-margin-top` on the card. There are now three targets and **none of them is a card**: `#<noun>-table-card` (the pager and the filter strip), `#<noun>-row-editor` on the add `<tr>`, and `#<noun>-row-<id>` on any row, both at 88px. Corrected 2026-09-15 — an earlier version of this bullet named the editor card, which has since been retired. `tr.row-action-target` and `.roster-card`'s own `scroll-margin-top` are new `base.html` primitives and §10 is where those are recorded. Supersedes the earlier bullet's "state the landing contract once, for both" — it is for three (Item 1).
- `spec/ui_elements.md` — **added 2026-09-15:** `:592` says `.session-row-selected` is "not a general primitive" and "deliberately not promoted". The UI pass applies it to a server-rendered EDIT row on a Setup page — a row that is not selected at all. The existing bullet covers the page transfer (lobby → Setup); this is the **semantic** one, selection → edit state, and §6/§10 should say which meanings the class now carries (Item 1).
- `spec/settings_inventory.md` — **added 2026-09-15:** `?unlocked=1` is URL-borne UI state with no entry anywhere. §2.5 indexes browser-local UI state and is already on this list for the labels editor's position; the panel's open state belongs beside it, including that it is set by the labels redirect and dropped by Search / Clear / the pager (Item 1).
- `spec/setup_pages.md` — **added 2026-09-15 by rung 3's slicing; 3c shipped the behaviour, so rung 4 states it rather than predicts it.** The Unlock panel needs a stated **start-open** contract, because the CSV import re-renders the page in place on a parse / confirm / ack failure and its issue list renders inside the card the panel absorbs. A panel that always ships collapsed hides the errors — verified in Chromium both ways, and invisible to the suite. As shipped the contract has **two** halves: the in-place re-render sets `panel_open` server-side, and every control that lives in the panel redirects with `?unlocked=1` (labels save, delete-all, and a successful import). State it as one rule about the panel, not three about the controls (Item 1).
- `spec/visual_style_rrw.md` — **added 2026-09-15 by rung 2b step 3's cold read, and NOT found by the blast-radius grep** (which read five files; this was not one). § *Width discipline* (`:79`) names *"Reviewers / Reviewees / Relationships: the friendly-label editor (left) + Operator actions card (right) pair"* as the canonical half-width pairing. Step 3 makes that false for Reviewers, which now has one tenant in the container. The lesson is the grep's, not the sentence's: a manifest measured by grepping a chosen file list misses the files not chosen (Item 1).
- `spec/operator_button_audit.md` — **added 2026-09-15 by the same read:** rows **128 / 129** (`:231-232`, Reviewers Save / Cancel) say the pair is *"shown below the divider in Edit/Add mode"*. There is no divider on Reviewers after step 3 and the pair is in a card of its own, so the *"move to the expander"* bullet above does not cover these two — they moved somewhere else. Also, `:231` gives that `Save` the **Primary** role while the template renders `btn secondary`, identically on all four roster pages: pre-existing and not this item's to fix, but rung 4 is re-reading these exact rows (Item 1).
- `spec/ui_elements.md` — `.session-expander*` and `tr.session-row-selected` stop being lobby-only, and §6's `.btn.destructive` note stops siting the roster Delete "between `Add` and `Search`". **Added 2026-09-15:** §10 gains the preview-table toolbar's two bare panes — card geometry, no border, fill or padding — which `:637` already distinguishes from `.card-columns` and now needs a name of its own (Item 1).
- `spec/operator_button_audit.md` — **added 2026-09-15 by rung 2a's cold read:** row **125** (`:227`) states the Reviewers `Add` label *and* the reason it is short — *"`Add` and `Delete` must both fit this row"*. Rung 2a renames the shipped label to `Add new` and dissolves that constraint (Delete leaves for the expander, so the two are no longer on one row), so the cell and its rationale sentence are both stale. `spec/setup_pages.md` says the same thing twice more — `:241` and `:536` list `Add` in the Operator-actions control set, and `:543` repeats the one-row rationale. A **rename**, which the bullet above covers only as a move (Item 1).
- `spec/ui_elements.md` — **added 2026-09-15 by rung 2a′:** §10's layout-primitive table gains the filter strip. It was three private per-card copies and is now one unscoped base (`.filter-row`, `.filter-row > label`, `.filter-actions`) with three named narrowings, which is what §10 exists to record. Names the `body.ui-v2` prefix on the generic label rule as load-bearing specificity, not scoping (Item 1).
- **Two forward references that define OTHER pages by pointing at Reviewers — added 2026-09-15 by rung 3c's cold read, and missed by the bullet below.** `spec/setup_pages.md:926` (Reviewees § Body grid) reads *"Same two-column shape as Reviewers — Upload card on the left, Danger Zone on the right"*, and `:961` (Relationships) says the same of Reviewers / Reviewees. Reviewers now renders no `.bottom-grid`, no Upload card below the table and no Danger Zone on the right, so both sentences send a reader to a section that describes an Unlock panel and tell them it is the Reviewees contract. **Why the bullet below missed them:** that grep looked for the card — `#upload-csv`, "Upload Reviewers" — and these two lines name it only as part of a shape borrowed from another page. A page's spec can be falsified by a change to a page it merely cites. Rung 4 should state the two layouts outright rather than by reference, since Reviewers is now the odd one out (Item 1).

- **The Upload card's stated home, three files — added 2026-09-15 by rung 3c.** Each says where this card sits, and 3c moved it: `spec/operator_button_audit.md:223` (row 35) ends *"Sits **below** the preview table"*; `spec/setup_pages.md:894` lists it as **"Left:"** in the page's bottom row; `spec/operator_ui_concept.md:266` describes it as item 5, a card *"anchored at `#upload-csv`"*. The anchor and the `is_editable` gate both survive unchanged — what moved is the container, from a `.bottom-grid` that Reviewers no longer renders at all into the Unlock panel's right column. Found by grepping the three spec folders for the card, not by a cold read; the blast-radius grep at rung 3's slicing looked for `#upload-csv` as a **fragment target** and so missed every line that names the card in prose (Item 1).

- `spec/ui_elements.md` — **added 2026-09-15 by rung 3c:** `.confirm-label` is `display: flex`, so a confirm that interleaves pills with prose must keep its sentence inside **one** child element or each bare text run becomes its own flex item and takes the 8px `gap` with it (measured: the closing "." sat 12px off the pill, 4px after wrapping, that 4px being the pill's own margin). Nothing states this, and the class is reached by four pages. Either §6's confirm entry says it, or the class stops using `gap` for what is really the checkbox's margin — the second is the better fix and is out of scope for a slice about the import card (Item 1).

- `spec/ui_elements.md` — **added 2026-09-15:** §10 states the `#<noun>-table-card` fragment as the **pager's** contract (*"the route supplies the id, the pager never derives it"*). The filter strip's controls now take the same anchor, and entering edit mode takes a second one, `#<noun>-row-editor`. **Corrected 2026-09-15:** the reason recorded here was "because the editor is split across two cards" — it no longer is. The editor card was retired, so `#<noun>-row-editor` is an **add-mode-only id on the `<tr>` itself**, `Edit` builds `#<noun>-row-<id>` from the id it already has, and there is no card in the contract at all. §10 states the landing targets as they are, not as they were. `spec/setup_pages.md` § *Search + filter strip* describes the strip with no landing behavior at all (Item 1).
- `spec/rrw_functional_spec.md` — the Danger Zone and Upload card descriptions at §§ around `:1044`, `:1111`, `:1113` retire (Item 1).
- `guide/roster_expander_revamp_handoff.md` — dated annotation recording the four claims 19O.4 falsified (Item 1).
- `spec/color_tokens.md` — `:425` and `:448` describe `.page-guidance` as *"the `What this page is for` disclosure on every Setup page"* and argue its anchoring; the token set is unchanged, but the Reviewers placement the argument assumes is not, so the sentence is re-sited (Item 1).

- `spec/settings_inventory.md` — §2.5's *Surface → Edit* line (`:140-141`) sites the labels editor as an "Inline editor card **above the data table** on `/operator/sessions/{id}/reviewers`"; that is the position this item moves, stated per page. **Amended 2026-09-15 by 3a:** on Reviewers it is now TWO positions, not one — inside the Unlock panel where the panel can render, in its old home where it cannot (locked, or mid-edit) — so the line states the condition, not just a place (Item 1).

- `spec/csv_contracts.md` — its one editor mention (`:77`) is non-positional, and the friendly-label **header grammar** it owns is untouched by where the control renders (Item 1). <!-- doc-impact-waived: deliberate exclusion — the mention is non-positional and the header grammar is untouched by where the control renders -->

---

> **Segment-level commitment, made at 19P.1's close (2026-09-16).
> Author's call.** 19P.1 specified Reviewers while the other three
> roster pages still carry the old shape, so nine spec files now state
> the layout **per page** — "Reviewees / Relationships do X, Reviewers
> does Y, until 19P.2–.4". That hedging is *accurate*: the four pages
> genuinely differ today. It is also temporary scaffolding, and it
> cost something measurable — five of the fifteen findings in 19P.1's
> spec cold read were over-claimed or mis-stated divergence, the kind
> of error a mid-migration sentence invites.
>
> **So: each item states its own page, and 19P.4's close does ONE
> consolidating sweep** that removes every "until 19P.2–.4" and
> restores a single shared shape. The alternative — holding the spec
> until all four pages moved — was considered and declined: it would
> leave a substantially rebuilt page undocumented for three more
> items, and it would not have prevented the other ten findings, which
> were plain errors about one page rather than artifacts of the split.
>
> The sweep's scope is the nine files in Item 1's `### Doc impact`,
> plus `docs/status.md`. **Finding them: `grep -rn "19P\." spec/ docs/`
> — 58 lines at 19P.1's close.** They are two different kinds and the
> sweep must not treat them alike:
>
> - **10 name `19P.2` / `.3` / `.4`.** These are the temporary ones —
>   a sentence that says "until 19P.2–.4" is definitionally spent once
>   that item lands, and the sweep deletes the hedge.
> - **48 say only "since 19P.1".** These are dated history, and most
>   are *correct to keep* — "the `Add` label was shortened until 19P.1
>   dissolved the constraint" stays true forever. The sweep reads each
>   one and keeps it unless it is hedging rather than dating.
>
> Counted, because the first version of this note asserted that every
> hedge named the item that would remove it. It does not — 48 of 58
> do not — and a sweep run on that assumption would have missed them.

---

## Item 2 — Observers, the divergence proof

### Opportunity

Observers is the only roster page that does **not** match Reviewers, which is
why it is second and not fourth: Reviewees and Relationships are identical in
action set and arity, so they cannot falsify the idiom. Measured differences —
an extra row action (`cohort-rule`, 5 routes to Reviewers' 4), a per-observer
**cohort match rule editor** with no equivalent anywhere else, a `Cohort`
column, **no** `_field_labels_editor`, **no** column chips at all (one fixed
tag slot), and a page that 404s unless `session.observers_enabled`.

It also still carries the defect 19P.1 fixed only for Reviewers: **no row
action passes `offset` or a fragment**, so an action taken on page 2 answers
with page 1 and lands at the top of the document.

And the cohort editor is in the wrong place for what it does: its own empty
state reads *"Select observers in the table below…"*, yet it renders two
containers above those rows — the complaint this segment exists to answer.

### Decision

**Apply the Reviewers idiom, and put the cohort editor in the row expander**
beside `Edit`. Agreed by mockup (seven iterations on the app's own tokens,
2026-09-16, built by transforming the real rendered page).

Rejected: **leaving the cohort editor in a card** — it is selection-driven, so
a card a grid away is the defect, not the layout. Rejected: **the Unlock
panel** — that panel holds roster-wide controls; a per-row rule is not one.

The shape, as agreed:

- **Expander, two columns.** Left: the cohort label, its rule builder, and
  `Save` **inline immediately after the last rule cell's `X`** (anchored to
  the final `X`, so it trails the list as rules are added). Right: the
  selected count, the delete confirm and `Edit` / `Inactivate` / `Delete`,
  **all inline, top-aligned, flush right**.
- **The cohort label is not a card heading.** It takes the Instruments rule
  builder's Link 1 idiom — `<h3>` at `font-weight: normal`, `margin: 0 0 12px`,
  flex with an 8px gap (`instruments_index.html`, `new_model_rule_list`), whose
  gap seats a state pill inline if this editor ever wants one.
- **`Save` is disabled until the rule is dirty**, and sized to the selects:
  measured 29 / 28.9 / **36.9**px, so it takes the `X`'s `4px 8px` padding and
  inherits the rule row's 4px flex gap rather than carrying a margin — the two
  gaps then match by construction rather than by a tuned value.
- **Toolbar asymmetry accepted.** The left pane renders empty on this page —
  no column chips exist, and the pager appears only past one page. Consistency
  with Reviewers wins over filling it. The filter's button row is **`Clear` /
  `Add new` / `Search` only**; row actions live in the expander.
- **Unlock panel: `Upload Observers` left, `Danger Zone` right**, with `Lock`
  at the foot of the right-hand stack under the Danger Zone — the same
  relationship Reviewers has (Lock under the card that stack holds).

### Semantics

- **The gate collision is resolved by relaxing the routes, not by splitting the
  container.** Author's ruling, 2026-09-16: **observers only view.** They never
  appear in assignments, never produce responses, and no readiness rule
  references them — so freezing their roster at Activate buys nothing, and the
  whole expander takes the looser `not is_archived` gate.

  **This is a behavior change, not a layout one**, and it is the item's real
  risk. Today `create` / `update` / `bulk-inactivate` / `bulk-reactivate` all
  call `_require_editable`, so a relaxed template without relaxed routes would
  render controls the server answers 409 to — the exact silent failure
  `spec/lifecycle.md` names. The routes move to `_require_not_archived`
  together with the template.

  **The codebase already agreed twice.** `observers_cohort_rule_save` has used
  `_require_not_archived` since it was written; and `observers_delete_all`
  alone among the four roster pages has **no response-loss acknowledgement**,
  exempted at 19I Item 3 on the measured ground that *"nothing references an
  observer, so deleting the roster destroys no assignment and no response"* —
  requiring one *"asked the operator to accept a loss that cannot occur"*. That
  is this ruling's argument, already made in the narrowest place it applies.
  The first of the two carries the reasoning in its docstring — *"cohort rules govern which parts of response data observers see,
  not the response data or roster shape"*. The ruling extends that from the
  rule to the roster, on the ground that an observer roster is a view grant
  either way.

  **What makes it safe, checked rather than assumed:** no validation rule
  mentions observers, so the roster never gates `draft → validated`;
  `require_observer_in_session` re-reads `Observer.status == "active"` on every
  request, so an inactivate mid-session revokes access at once rather than
  leaving a stale grant; and `invalidate_if_validated` is a no-op outside
  `validated`, so nothing demotes a running session.
- **Mixed selections keep today's behavior**: the builder resets to its blank
  default and `#observers-cohort-mixed-message` explains that saving replaces
  every selected observer's rule. Author's call, 2026-09-16 — good enough, and
  it ships with the move rather than after it.
- **The dirty snapshot is re-taken on every expander rebuild**, because the
  expander re-renders client-side on every selection change. Taken once — as
  the tag-label editor safely does, never rebuilding — it would leave `Save`
  enabled against an unchanged rule or disabled against a changed one.
- **`Save` writes one rule to every selected observer**, unchanged from today
  (`observers_cohort_rule_save` applies the editor's rule to every id in
  `observer_ids`). **What changes is where it lands.** It redirects like any
  row action, and once the editor is *inside* the expander a top-of-document
  landing throws the operator away from the rows they were just ruling on — the
  same 821px defect rung 1 fixes, on the one control whose surface moved into
  the table. So the cohort save takes the same contract: keep `offset`, return
  to `#observer-row-<id>` of the first selected row. Rung 1 gives it that for
  free **only if** the cohort route is included in the fix; it is a fifth POST
  and easy to miss when the other four are the obvious set.
- **The page is unreachable without `observers_enabled`** (404 via
  `require_observers_enabled_session`), so every rung inherits a gate Reviewers
  has no equivalent of.

### Judgment calls — decided

- **2026-09-16.** `.card-columns` **retires on this page**, unlike Reviewers.
  It survived there only as the tag-label editor's locked-state fallback home;
  Observers has no such editor, so once the cohort card leaves, the container
  has no tenant at all.
- **2026-09-16.** The expander's columns do not share a bottom edge; the
  builder is taller. Accepted — top-flush was the author's call, and aligning
  them would anchor `Save` to a button row it has no relationship with.
- **2026-09-16.** The `offset`/anchor fix lands **first and alone**, before any
  layout moves. It is owed from 19P.1, is independent of the shape, and a
  landing bug is far easier to see on a page that has not just been rearranged.

### Blast radius (measured)

Commands and counts, 2026-09-16, `226c600`:

- `wc -l app/web/templates/operator/session_observers.html` → **858** (Reviewers 1,342)
- `wc -l app/web/routes_operator/_setup_observers.py` → **707** (Reviewers 738)
- Routes: **5 POST** row/bulk actions + index + import + create + update.
  `cohort-rule` is the one Reviewers lacks; `field-labels` is the one it has.
- `grep -c 'setBtn(' session_observers.html` → **5**; `grep -c 'data-col-toggle=' → **0**;
  `grep -c '_field_labels_editor' → **0**
- `grep -rl observers tests/ --include=*.py | wc -l` → **45** (reviewers 160)
- The cohort editor is ~95 lines of builder markup plus ~180 lines of its own JS.

### Status

**Rung 1 — landed.** Every row action on Observers keeps the pager
`offset` and returns to the row it acted on.

**Six POSTs, and it is a different set from the ladder's five, not a
bigger one.** The ladder counted the five row/bulk POSTs
(`bulk-inactivate`, `bulk-reactivate`, `bulk-delete`, `cohort-rule`,
`delete-all`). Rung 1 covers `create` and `update` as well, and defers
`delete-all` to rung 2, where its gate moves. `cohort-rule` is in both
counts — the plan flagged it twice as the easy one to miss, and it was
not missed.

`_row_action_anchor` lifted from `_setup_reviewers.py` into `_shared.py`
with a `noun` kwarg — the fourth roster page will want it too. Its
docstring said "all three" cases leave the fragment unresolvable; the
generic count is **two** (a delete redirects to the table card, so the
fallback returns on its first line), and **one** on this page, which has
no sortable table. Two copies of the miscount survived the lift:
`session_reviewers.html`'s own comment, corrected here; and
`spec/ui_elements.md:611`, now on rung 7's Doc impact.

Four things the ladder did not name, all in scope because without them
the rung does not work:

- **`Add` carried a bare `?add=1`,** so an add from a filtered view
  rendered an unfiltered page whose hidden `filter_*` fields held
  defaults, which the create redirect faithfully honored. The filter was
  lost at the navigation, not at the POST.
- **`Add` and `Edit` both landed at the top of the document.** Carrying
  the filter fixes what the add page *shows*, not where it *arrives*.
  `Add` now names `#observers-row-editor` (a new id on the add row, as
  Reviewers has); `Edit`'s script now builds `#observer-row-<id>` from
  the id it already has, which is also what makes the edit row's
  `row-action-target` live rather than dead markup.
- **A delete's `offset` was unguarded on both pages.** The parametrized
  offset test structurally cannot cover a delete: the row it acts on is
  gone, so there is nothing for the anchor assertion to name.
- **A create's `offset` was unguarded** for the mirror reason — there is
  no row id until the POST returns. Through the UI it can only be `0`
  today, since `Add` carries the filter but not the page; the wiring is
  what a future `Add` that keeps the page would ride on.

Verified in Chromium (the suite has no layout engine): an `Inactivate`
on row 11 of page 2 lands the row at **88px** from the viewport top,
scrollY 642 → 1051. With the filter reading `active`, the same action
drops the row out of the view, the fragment does not resolve, and the
fallback puts the table card at **16px** instead of leaving the operator
at the top of the document. `Edit` on row 41 of 60: scrollY 2052 →
2564, edit row at **88px**, and the row is the editor. `Add` from the
foot of the roster: scrollY 2920 → 637, add row at **88px** — without
the fragment that navigation landed at 0.

Guards: `tests/integration/test_observers_row_landing.py`, 16 tests,
20/20 mutations caught. Suite 4,049 → 4,065.

**Cold read** (`diff-reviewer`, 11 findings, all upheld): the two
surviving mutations above, the "one case not two" miscount in the page
comment, two stale claims in `_shared.py` docstrings I had just written
("this was its last copy"; "Only Reviewers does today"), the contradicting
Reviewers comment, the half-done `Add` fix, four spec lines missing from
Doc impact, a mis-scoped assertion message, a US-spelling slip, and the
"six not five" claim above, whose stated reason was wrong.

**Rung 2 — landed.** Seven routes, not five. The count was measured at
the start of the rung, not assumed: `grep -c _require_editable
_setup_observers.py` → 7. `bulk-delete` was an enumeration slip;
`import` was the ruling recorded in rung 2's text above.

Three template gates moved with them — `_show_actions_slot`, the
`observers-bulk-form` shell, and the `.bottom-grid`. After the move
`is_editable` appears nowhere in `session_observers.html`; the page's
predicate is `is_archived` throughout, which is what keeps page and
route agreeing by construction rather than by two lists kept in step
(the property 19I.3 established, re-established at the new predicate).

**The lock card was the thing the ladder did not see coming.**
`_roster_lock_card.html` is shared by all four roster pages and gated on
`not is_editable`, so on `ready` it would have rendered *"The observers
cannot be modified while the session is ongoing"* directly above a live
roster. Its gate is now a parameter (`lock_when`, defaulting to the old
predicate); Observers passes `is_archived`. The other three pages render
byte-identically. A consequence worth naming: Observers no longer
renders a revert form anywhere, because the one state it still locks in
is `archived`, where that form is correctly absent already — so
`test_the_slug_each_page_renders_is_the_one_under_test` covers three
pages now, not four. The route still honours the `observers` slug, and
the route-level test still covers all four — so `_REVERT_RETURN_TO`'s
`observers` entry, added at 19H.6 rung 1 and re-justified in this item's
rung 1, is now unreachable from the UI one rung after it was added.
Kept as defence in depth; named here because rung 1's Status still
presents it as a live fix.

Verified in Chromium across the three frozen states. `ready` and
`expired`: no lock card, 3 checkboxes, bulk form, `Delete`, upload card
and Danger Zone all present, and an `Inactivate` through the UI lands
the row reading **INACTIVE** with still no lock card. `archived`: lock
card present, every one of those controls absent, and the three rows
still **readable** — the relaxation did not turn `archived` into a
blank page. An import on `ready` replaced the roster 3 → 1.

Guards: **41 new test cases, 17 dropped by the re-aiming, +24 net**
(4,065 → 4,089). Most are the seven mutators parametrized across
`ready` / `expired` (accepts, `== 303`) and `archived` (still 409s),
plus the whole-surface render, the editor pair below, and the lock
card's absence on a live session and survival on `archived`. Seventeen
existing **test cases** were re-aimed rather than deleted —
`LOCKED_STATES`, `FROZEN_PAGES` and `REFUSES_AT` carry the divergence as
data, so the three unchanged pages keep asserting the old contract in
the same tests.

**16/16 mutations caught.** Thirteen re-tighten one gate alone back to
`_require_editable`: all seven routes plus `cohort-rule` (which already
had the looser gate and must keep it), the three template gates, the
`lock_when` argument, and the partial's default. The `lock_when` one had
to be re-run — deleting the kwarg broke the `{% with %}` syntax, so its
35 failures proved a template error rather than a lost gate; re-run as a
valid re-tightening it fails 4. Three more came out of the cold read and
probe the **upper** bound, which nothing had: the `.bottom-grid` gate
loosened to render on `archived`, and the editor predicate both put back
to `is_ready` and removed outright.

**Cold read** (`diff-reviewer`, 11 findings). It confirmed all three
safety claims in Semantics against the code, and found nothing else
caching a frozen roster. Two findings were **defects, not prose**:

- **`Add` and `Edit` were dead controls on `ready`** — the exact failure
  this rung exists to remove, shipped by it. `_render_observers_page`
  discarded `edit_id` / `add_mode` under `if is_ready`, correct while
  `create` / `update` took `_require_editable` and the page could not
  save. The rung relaxed those routes and the buttons above them and
  left the predicate behind, so both rendered on `ready` and opened
  nothing. Now `is_archived`, the same predicate the buttons read.
- **A rejected save on `ready` lost the operator's typing.** Same root
  cause: the error-render path re-renders with `add_mode=True`, which
  was then dropped, and the error banner is scoped to `{% if edit_mode %}`
  — so a mistyped email answered 400 with a bare roster page, no values
  and no reason.

Neither was reachable by the mutation pass, which only re-tightened
gates, and neither was exercised by the Chromium check: it covered
checkboxes, bulk form, Delete, upload, Danger Zone and an Inactivate,
and never Add or Edit. Both are covered now: on `ready` and `expired`
the `Add` link opens a real add editor and `Edit` navigates to
`#observer-row-<id>` and opens one; on `archived` neither renders; and a
rejected save on `ready` comes back with the editor open, the typed
value intact and the reason shown.

A third finding was **coverage removed rather than replaced**: the
re-aiming dropped Observers from
`test_the_upload_and_danger_zone_cards_go_when_frozen`, and the
replacement asserted only the two bulk ids — so loosening `.bottom-grid`
to render Upload and Danger Zone on `archived`, over routes that 409,
passed the whole suite. Bracketed now by asserting every control absent
on `archived` that the live-session test asserts present.

The rest was prose, all of it written in this rung: "byte-identically"
(above), a comment claiming two readers of `is_editable` that do not
exist, a stale `is_ready` header comment, a test docstring saying
"through `archived`" where it means "until", a rename comment a blanket
search-and-replace had turned into *"the name is `FROZEN_PAGES` and the
alias is gone"*, and the count labels above.

**One open question the cold read raised, not decided here.**
`_quick_setup.py:637` writes observer rows via `csv_imports.save_observers`
and still refuses on `ready`. This rung's scope is the Setup-Observers
page, so it is untouched — but the ruling it rests on is about the
*entity*, not the page, and the two now disagree: the same CSV accepts at
`/observers/import` and refuses at `/quick-setup/observers` on the same
session. Quick setup is a draft-time wizard by its own contract, so this
may be right as it stands. **Author's call, and it belongs to whoever
owns quick setup rather than to this item.**


### PR ladder

1. **The `offset` / anchor fix — land where Reviewers lands.** Every row
   action keeps the pager `offset` and returns to the row it acted on:
   `#observer-row-<id>` for the first acted-on row, `#observers-table-card`
   where the action leaves no row (a delete), `tr.row-action-target` at 88px so
   the row sits second from the top with a neighbour for context, `?focus=<id>`
   on a create (a new row appends past the end, so the fragment alone names a
   row the response never rendered), and the fallback script for the two cases
   a fragment cannot resolve — a row the filter excludes, a row moved by the
   cookie sort. No layout change; this is the defect 19P.1 left behind.
2. **The gate relaxation.** `create` / `update` / `bulk-inactivate` /
   `bulk-reactivate` **and `delete-all`** move from `_require_editable` to
   `_require_not_archived`, and the template's `_show_actions_slot` follows, so
   the roster is editable on `ready` and `expired`.

   **Seven routes, not five — measured 2026-09-16 at the start of the rung.**
   `grep -c _require_editable _setup_observers.py` → 7. Two were never
   enumerated above. `bulk-delete` is an enumeration slip: rung 4 moves
   `Delete` into the expander, so it is already inside *"the whole expander
   takes the looser gate"*. `import` is a real widening, and a forced one —
   `session_observers.html:863` gates Upload and Danger Zone with **one**
   `{% if is_editable %}`, so `delete-all` cannot become reachable on `ready`
   without the upload card rendering beside it, and a rendered control the
   server 409s is exactly the silent failure this rung exists to remove.
   **Author's ruling, 2026-09-16: import relaxes too** — same principle, and
   the alternative leaves an operator on `ready` able to delete every observer
   and unable to upload a replacement, re-adding them only one at a time. The
   `Definition of done`'s "five relaxed routes" reads **seven** from here. A **behavior** rung,
   landing before any layout moves so that a regression here is not hidden
   inside a rearrangement — and so the expander later inherits one gate rather
   than reconciling two. Delete-all keeps its other two gates untouched: it
   still renders only on a non-empty roster and still 400s without the confirm.
   The three other roster pages are untouched: this argument is about
   observers, not about rosters.
3. **Toolbar.** Filter strip into the table card's toolbar, split panes, button
   row narrowed to `Clear` / `Add new` / `Search`. The `Operator actions` card
   is **slimmed, not retired** — it still holds the only live row actions.
4. **Row expander.** The four row actions move in; the card retires; the
   cohort card stays where it is, untouched.
5. **The cohort editor into the expander.** The divergence proof proper: two
   columns, the Link 1 label idiom, `Save` inline and dirty-gated, per-control
   gating, mixed-selection behavior preserved. `.card-columns` retires here.
6. **Unlock panel.** `Upload` + `Danger Zone` into the roster card; `Lock` at
   the stack's foot; nothing below the table. **Both moved controls' redirects
   gain `?unlocked=1`** — Observers' delete-all currently returns to a bare URL,
   and 19P.1 rung 3b shipped exactly that omission and had to fix it after the
   fact: a control inside the panel must not close the panel it was used from.
7. **Specs and the close.**

### Definition of done

- A row action taken on page 2 of a filtered roster returns to page 2, landing
  on the acted-on row, asserted by route test — **for all five POSTs**,
  `cohort-rule` included.
- `grep -c 'data-col-toggle=' session_observers.html` → 0 and the toolbar still
  renders `is-split`, asserted — the empty left pane is intended, not a bug.
- The expander renders **in full** on `ready` and `expired` and **not at all**
  on `archived`, asserted across all five states — and each of the **seven**
  relaxed routes (`delete-all` and `import` included — see rung 2) accepts on
  `ready` where it previously answered 409, asserted per route so a
  template-only relaxation fails.
- `delete-all` on `ready` still 400s without the confirm and still renders only
  on a non-empty roster — the relaxation moves one gate, not three.
- `Save` renders `disabled` on arrival and after every selection change,
  asserted on a rebuilt expander, not just the first render.
- A mixed selection renders the blank builder **and** the mixed-rule message.
- `.card-columns` and `.bottom-grid` are both absent from the rendered page.
- Verified in Chromium: the expander at two and at three rule rows, and the
  panel's start-open state on a failed import.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19P.2` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

1. ~~**How does the expander gate per control on a `ready` session?**~~
   **Answered 2026-09-16 by the author:** it does not — observers only view, so
   the looser `not is_archived` gate applies to the whole expander and the
   routes relax to match. See Semantics.
2. ~~**Does the relaxation reach `Delete all observers` too?**~~ **Answered
   2026-09-16 by the author: yes**, folded into rung 2. It destroys view grants
   and nothing else, and withholding it would let an operator inactivate every
   observer one selection at a time while the button that does exactly that
   stayed dark — a distinction with no reason the operator could see.

### Out of scope

- **Per-box `(Multiple values)`.** Today's whole-rule signature cannot say
  *which* field differs; labelling individual boxes needs per-field comparison
  across the selected rows. Recorded in `guide/deferred_consolidated.md`.
- **The other two roster pages.** 19P.3.
- **The three wrong spec lines this item's audit found** are fixed at this
  item's close, not before — see Doc impact.

### Doc impact

- `spec/setup_pages.md` — § *Per-row Edit / Add / bulk actions* `:932-958` says the landing contract is *"Reviewers only… the other three pages pass no offset, no fragment and no focus"* — false from rung 1. § *Observers page* § *Body layout* items 4 and 6 and § *Cohort match rule editor* re-describe the expander, the toolbar and the Unlock panel. **Three statements there are already wrong, found by this item's audit and predating 19P:** `:1329` says the editor *"reveals **inside the Operator actions card**"* (it is its own card), and `:1258` calls the cohort + actions pair *"a `.bottom-grid`"* (it is `.card-columns`; `.bottom-grid` holds upload + Danger Zone). The item-0 placement table is the only one of the three that is correct today (Item 2).
- `spec/operator_button_audit.md` — the Observers rows for the four row actions move to the expander; the cohort `Save` gains its dirty-gate and its new home; the `Add` → `Add new` rename reaches this page. Its standing gate note — these controls are *absent, not disabled*, outside an editable session — keeps its shape but changes its predicate for this page alone (Item 2).
- `spec/operator_ui_concept.md` — the § *Setup pages* heading narrows again as Observers leaves the shared shape (Item 2).
- `spec/lifecycle.md` — §5 states that the four roster pages hide their mutating surface outside `is_editable`. Observers becomes a **stated exception**: its roster is editable to `archived`, because an observer row is a view grant rather than a participant in assignments or responses. This is the first page to diverge from that predicate, so §3.1's "nothing may use a narrower one" needs its mirror — nothing may use a *wider* one either, without saying why here (Item 2).
- `spec/settings_inventory.md` — § *URL state* gains Observers' `offset=`, `focus=` and row fragment. **Three rows go stale the moment rung 1 lands**: `:384` reads *"Reviewers only; the other three roster pages pass no offset"*, `:385` scopes `focus=<id>` to Reviewers, and `:379-381` list `edit_id=` / `add=1` / `selected=` as Reviewers / Reviewees / Relationships though Observers has had all three all along (Item 2).
- `spec/ui_elements.md` — §10's landing-target entry adds Observers; the expander's two-column variant is a new shape worth naming. `:611` also carries the **"three cases"** miscount 19P.1 rung 4a corrected in `setup_pages.md` and 19P.2 rung 1 corrected in code — the delete case is not one of them (Item 2).
- `spec/rrw_functional_spec.md` — the roster-page description gains Observers alongside Reviewers (Item 2).

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
