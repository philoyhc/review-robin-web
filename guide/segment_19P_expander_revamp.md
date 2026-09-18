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

**Item 4 is a stub.** It records the sequence and why, not a plan; it is
planned in full when it is taken up. Items 1-3 are closed; **Item 5 is planned
and open** (2026-09-17) and is not Item 4's work — it moves existing controls
into the toolbar and the expander, where Item 4 is a redesign that would add
selection where there is none.

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

### Status — closed 2026-09-16

**All six rungs landed and merged, plus a 5a the ladder did not have.**
The shape the item set out to prove — Reviewers' idiom survives contact
with the one roster page that does not match it — held. What follows is
intended versus done; the rungs' own reasoning lives in their commits
and, where it became contract, in `spec/`.

**Where the ladder was wrong, and why.**

- **Rung 1 acted on six POSTs, not the ladder's five.** The set was
  enumerated from the page rather than measured from the routes.
- **Rung 2 relaxed seven routes, not five.** `grep -c _require_editable`
  → 7 at the rung's start. `bulk-delete` was an enumeration slip;
  `import` was *structurally forced* — one `{% if %}` gates Upload and
  Danger Zone together, so `delete-all` could not become reachable on
  `ready` without Upload rendering beside it, and a rendered control the
  server refuses is the silent failure the rung existed to remove. Put
  to the author, who ruled it in. (Eight routes read the gate today;
  `cohort-rule` already did.)
- **Rung 2 also had to touch the shared lock card**, which the ladder
  did not see: unchanged, it would have read "cannot be modified while
  the session is ongoing" above a live roster. Solved with a `lock_when`
  parameter, leaving the other three pages byte-identical in behavior.
- **Rung 4's card held more than row actions** — Save / Cancel, a
  heading and an error slot — so retiring it meant building a *second*
  expander, the edit-row bar, not just the selection panel.
- **`.card-columns` retired at rung 5, not rung 4.** Rung 4 left the
  right column empty for one rung, deliberately and visibly, rather than
  reflowing twice.
- **Rung 5a is new.** Rung 5 made an unsaved cohort edit reachable and
  it was discarded silently by any selection change — verified against
  the column, which stayed `null` on every loss path. The author asked
  for a warning; it took Instruments' idiom verbatim (18R Item 2) and
  landed before rung 6 on the author's ruling.

**Decisions confirmed at build.**

- **Observers only view**, so the whole expander takes `not
  is_archived` and the routes relax to match. This is the item's real
  risk and its real finding: it makes Observers the first roster page
  whose mutating surface outlives `is_editable`, now a stated exception
  in `spec/lifecycle.md` §5 with a rule governing any second one.
- **The cohort editor belongs in the expander**, not a card and not the
  Unlock panel — it is selection-driven, so a card a grid away from the
  rows it acts on was the defect.
- **The empty left toolbar pane is intended**, not a gap: one fixed tag
  slot means no chips exist to toggle.
- **Author's corrections at rung 6**, both of which improved the design
  rather than patching it: the guidance card wanted `full_width=true`
  (rung 5), and the roster card wanted Reviewers' readouts — which then
  settled the gating (card always, panel conditionally), forced
  `views.observer_column_state` (the second caller
  `reviewer_column_state`'s docstring had been waiting for), and
  dissolved an empty-card problem the first draft had reasoned its way
  into. `Tag1` displays as `Tag` in all four display sites; the CSV
  column and the stored rule key are identifiers and did not move.

**What the build cost, and what it taught.**

Six cold reads, 63 findings, all upheld. Four were **live defects the
rungs shipped**: controls rendered on `ready` that opened nothing (rung
2 — the exact silent failure rung 2 existed to remove); two guards
deleted as card cleanup one rung after a cold read added them (rung 4);
`X` on the last rule cell permanently disabling `Save` (rung 5); and the
same `X` breaking the nav flag so `Save` raised "Leave site?" and Cancel
ate the save (rung 5a). **That control has bitten twice for one reason**
— `Save` rides *inside* the last rule cell, so removing it destroys and
recreates the button. Anything bound to `Save` is bound where `Save` is
built; `spec/setup_pages.md` says so now.

Three structural gaps closed, each found by shipping into it:

- **Python never parsed the app's JS.** A stray `}` killed this page's
  entire script and all 4,106 tests passed. Closed by
  `tests/integration/test_inline_scripts_parse.py` (`node --check` over
  every inline script on 13 pages), proven by breaking `base.html`'s.
- **Assertions read JS as text**, so one matched the *comment* explaining
  a class rather than the class. `_code()` strips comments inside
  `_builder()`.
- **The suite pinned no card's position.** All 4,131 existing tests
  passed with rung 6's two cards relocated, their container deleted and
  both redirects rewritten. `test_observers_unlock_panel.py` is that gap.

Two vacuity traps recurred and are worth naming for 19P.3: `base.html`
inlines the whole app's CSS and JS on every page, so `"bottom-grid" not
in body` is unfalsifiable; and a substring that occurs twice in one
script is satisfied by the innocent occurrence.

**Carried forward, not fixed here.** `loadEditorFromRule` sets
`tagSel.value` from `entry.operand_tag`; a literal-operator rule has
none, so the select lands at `selectedIndex === -1` and submits nothing,
while `_parse_cohort_rule_form` pads the parallel arrays at the *tail*
only — a restored multi-rule cohort mixing tag and literal operators can
submit a misaligned operand array. Pre-existing on `main`, but rung 5 is
what made multi-rule cohorts load at all, so it is newly reachable.

**At the close**, the spec pass found the register had missed the
Observers page's own body-layout item — the passage most directly
describing what moved — and had one rename recorded backwards
(`spec/setup_pages.md` already read `Tag`; the code had drifted). The
button audit gained a **Section 8.5**: the page had none, which was a
gap rather than a scoping choice, since that file audits every button on
the surface.

**Four counts of mine were wrong, and the pattern is the lesson.** Each
was corrected somewhere and not everywhere: eight routes read the gate
where a sibling sentence said seven; six POSTs carry `offset` where
`settings_inventory.md` said five — a figure this very Status block
already corrected as *"six POSTs, not the ladder's five"*; two cases
reach the fragment fallback where `ui_elements.md` said three, a
correction `setup_pages.md` had carried since 19P.1 rung 4a; and one
paragraph said *"the other three pages do not"* and then *"19P.2 carries
this to Observers"* four sentences later. **A count restated in two files
is two facts that can disagree**, and the close is where they do.

**And an insertion invalidated a citation.** Adding §8.5 to
`operator_button_audit.md` shifted every line after it, so
`setup_pages.md`'s `:306` pointed at the new section's preamble instead
of the Instruments Lock row. Cited by **row number** now, which is what
that file is indexed by and what an insertion does not move; the plan's
own bullet above carried the same stale reference and is fixed with it.
Line-number citations into a table are a liability the moment anyone
edits above them.


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
5a. **The unsaved-edit guard.** Not in the original ladder — added on the
   author's ruling once rung 5 made the loss reachable. The expander is rebuilt
   wholesale on every selection change, so an unsaved rule edit was discarded
   silently by untick, by a second tick and by every navigation. `confirm` on
   the paths that stay on the page (row checkbox, select-all, `Edit`, the three
   panel submits), `beforeunload` on the rest, wording verbatim from
   Instruments (18R Item 2).

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
- **No chip row reaches the rendered page** and the toolbar still
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

- `spec/setup_pages.md` — **`:77-80`** says the guidance macro's `full_width` argument is one **Reviewers** passes; Observers passes it since rung 5. **`:1363-1365`** puts the mixed-rule message *"between the rule cells and the Save button"*, and Save is now inline in the last rule cell, so the message renders after it. **`:1352-1354`** calls the cohort `Save` a **primary** button `disabled` *"when no observer is checked"* — the code has shipped `btn secondary` since before 19P and the predicate is now "until the rule is dirty". § *Per-row Edit / Add / bulk actions* `:932-958` says the landing contract is *"Reviewers only… the other three pages pass no offset, no fragment and no focus"* — false from rung 1. § *Observers page* § *Body layout* items 4 and 6 and § *Cohort match rule editor* re-describe the expander, the toolbar and the Unlock panel. **Three statements there are already wrong, found by this item's audit and predating 19P:** `:1329` says the editor *"reveals **inside the Operator actions card**"* (it is its own card), and `:1258` calls the cohort + actions pair *"a `.bottom-grid`"* (it is `.card-columns`; `.bottom-grid` holds upload + Danger Zone). The item-0 placement table is the only one of the three that is correct today (Item 2). **Rung 3 adds four more, none of them previously named:** § *Operator actions card* `:552` opens *"Reviewees, Relationships and Observers"* and `:574` says *"One shape on the three pages that carry this card"* — two now; its § item 2 **Action row** `:585-598` lists `Clear … Edit, Inactivate, Activate, Add and Delete … and finally the Search submit last` and scopes the exception to Reviewers alone; and § *Observers page* body-layout **item 5** `:1282` reads *"Preview table — always renders when observers exist (or when Add mode is active)"*, where the gate is now `observers or add_mode or total_row_count > 0 or not is_archived`. Doc impact named items 4 and 6, not 5. **Rung 4 adds three more:** `:908-916` scopes the Save/Cancel-in-an-expander-bar shape to Reviewers, true of Observers now too; `:105`'s item-0 placement table still reads *"`Operator actions` alone in the right"* for Observers, which also makes THIS document's claim that *"the item-0 placement table is the only one of the three that is correct today"* stale; and `:894-907`'s page-independent button-state table describes a confirm *"on the status row"*, `Add` as a selection-gated column and the status pair as enabled-by-arity — none of which holds on a page whose panel renders them by status.
- `spec/operator_button_audit.md` — **that file has no Observers Setup section**: §§6/7/8 are Reviewers / Reviewees / Relationships and the only Observers row in it is the nav tab (`:80`). So there are no Observers rows for the four row actions or the rename to move; what is actually owed is `:230` (row 125), *"The three other roster pages still read `Add`, and keep the rationale, until 19P.2–.4"* — two now, after rung 3 — and a decision at the close about whether this page gets a section at all. The earlier wording here promised edits to rows that do not exist; corrected at rung 3, when the first slice tried to act on it (Item 2). Its standing gate note — these controls are *absent, not disabled*, outside an editable session — keeps its shape but changes its predicate for this page alone (Item 2).
- `spec/operator_ui_concept.md` — the § *Setup pages* heading narrows again as Observers leaves the shared shape (Item 2).
- `spec/lifecycle.md` — §5 states that the four roster pages hide their mutating surface outside `is_editable`. Observers becomes a **stated exception**: its roster is editable to `archived`, because an observer row is a view grant rather than a participant in assignments or responses. This is the first page to diverge from that predicate, so §3.1's "nothing may use a narrower one" needs its mirror — nothing may use a *wider* one either, without saying why here (Item 2).
- `spec/settings_inventory.md` — § *URL state* gains Observers' `offset=`, `focus=` and row fragment. **Three rows go stale the moment rung 1 lands**: `:384` reads *"Reviewers only; the other three roster pages pass no offset"*, `:385` scopes `focus=<id>` to Reviewers, and `:379-381` list `edit_id=` / `add=1` / `selected=` as Reviewers / Reviewees / Relationships though Observers has had all three all along (Item 2).
- `spec/ui_elements.md` — **`:609`** (`.session-row-selected`) names the injectors as *"`sessions_list.html`, `sessions_archived.html` and now `session_reviewers.html`"* and says Reviewers is the page rendering both the expander and the bracketed variant: Observers is a fourth injector and a second such page since rung 4, and it is the line the builder's own comment cites. §10's landing-target entry adds Observers; the expander's two-column variant is a new shape worth naming. **§6 `:385` sites the roster `Delete` "between `Add` and `Search`" and scopes the exception to Reviewers** — false on Observers since rung 3, where the `Delete` is still in the card with nothing beside it; and `:613` attributes `.table-card-toolbar` to *"(19P.1, Reviewers)"* and describes the left pane as *"column chips, pager cluster, count line"*, where Observers has no chips. `:611` also carries the **"three cases"** miscount 19P.1 rung 4a corrected in `setup_pages.md` and 19P.2 rung 1 corrected in code — the delete case is not one of them (Item 2).
- `spec/rrw_functional_spec.md` — the roster-page description gains Observers alongside Reviewers (Item 2).
- **Rung 6 adds four, three of them falsified the moment it landed.** `spec/setup_pages.md:1258-1262` calls the cohort editor + Operator actions pair *"a `.bottom-grid`"* — already wrong (it was `.card-columns`, and this file already said so) and now wrong twice over, since `.bottom-grid` names the container rung 6 deleted; `:568-569` and `:763` both scope *"that class carries only the Upload + Danger Zone pair below the table"* to a layout Observers no longer has; and `:979-1002`'s *"There is nothing below the preview table"* section, written for Reviewers, is now true of this page too and should say so rather than being restated. `spec/lifecycle.md:351-356` says *"On Reviewees, Relationships and Observers it is the `.bottom-grid` those two cards sit in"* — two now, and the sentence's own point (same predicate, different container) is what changes. `spec/settings_inventory.md:383` scopes `?unlocked=1` to the *"Reviewers Setup page"*; the row's whole contract now holds on two pages, and Observers' version differs in one way worth stating — it has no labels editor, so the panel has two tenants, not three. **And two more the author's mid-rung corrections added:** the roster index row is a second-page feature now, so wherever `spec/` scopes it to Reviewers it wants the generalized rule stated once (*the index mirrors the columns the table renders*) rather than twice by page; and the Observers preview table's `Tag1` column header is now `Tag`. **That last one is a CLOSING, not an opening** — the first draft of this bullet had it backwards. `spec/setup_pages.md:1308` already reads `| 3 | Tag |`, so the CODE had drifted and the rename brings it back; what the close actually owes is the cohort label `Observer: Tag`, which the same rung moved in `_COHORT_OBSERVER_FRIENDLY` and which `:1310`'s example summary does not quote. **And the passage this register most conspicuously missed, found by the cold read: `spec/setup_pages.md:1284-1288`** — item 6 of the Observers page's own *Body layout*, stating the container, the position and the gate of the two cards this rung moved (*"a `.bottom-grid` pair below the table … Hidden whenever the session is not `is_editable`"*). Every clause is false of the code now, the `is_editable` half since rung 2. The citations above reach the cross-references from OTHER pages and the cohort-editor pair; none reached the page's own layout item (Item 2).
- **`spec/setup_pages.md` § *Cohort match rule editor* gains the unsaved-edit guard (rung 5a).** The section enumerates the editor's controls, the `Save` gate and the storage shape and says nothing about discarding: state that an unsaved rule edit prompts *"Discard unsaved changes?"* on the four in-page paths and raises the browser's unload warning on the rest. The sibling contract is already specced at `spec/instruments.md` § *Save / Lock interaction* and `spec/operator_button_audit.md` row 57, and both quote the same string, so this is a third site for one sentence rather than a new one — say it once and cite them (Item 2). <!-- cites: spec/instruments.md -->

---

## Item 3 — Reviewees and Relationships — closed 2026-09-17

### Opportunity

**Two pages still carry the pre-19P.1 shape, and one live defect with it.**

Measured 2026-09-16 on `origin/main` after Item 2 closed. Both render the
`Operator actions` card with the same seven controls (`Clear`, `Edit`,
`Inactivate`, `Activate`, `Add`, `Delete`, `Search`), a `.card-columns`
above the preview table and a `.bottom-grid` below it — the shape Reviewers
left at 19P.1 and Observers at 19P.2.

**The 821px landing defect is live on both.** Each has **four**
`_redirect_keeping_selection` call sites — `update`, the two bulk status
routes and `bulk-delete` — and **zero** anchors: `grep -c "anchor="
app/web/routes_operator/_setup_{reviewees,relationships}.py` → 0 and 0.
(`grep -c` on the helper name returns 5; the fifth is the import line.
The **fifth POST** needing the contract is `create`, which returns a
**bare** `RedirectResponse` — no selection, no filter, no offset, no
fragment — so it loses more than the other four and rung 1 *converts* it
rather than adding two kwargs. **Four** POSTs per page redirect bare and
correctly stay bare: `import`, `delete-all` and `field-labels`, plus
Reviewees' import reaching the shared handler.) `offset` appears twice in each module and reaches only the GET route
and the window helper, never a redirect — so a row action taken on page 2
answers with page 1 and lands at the top of the document.

**And they are the only pages keeping the spec's hedges alive.** 19P.1
committed to *"each item states its own page, and 19P.4's close does ONE
consolidating sweep"*; after this item there is no page left hedged.

### Decision

**Apply the idiom to both pages in one item, one rung per concern rather
than one rung per page.** Each rung lands the same change on both templates
in one commit.

Rejected: **a rung per page** — it is the same edit twice, and letting the
two drift apart by a rung is exactly the divergence 19P.1's spec cold read
spent fifteen findings on. Rejected: **deferring the landing fix** — it is four call sites plus one
conversion per page, and a defect the operator meets today.

**The divergence proof is done.** Item 2 took the idiom to the page that did
not fit; these two fit. So this item is a transcription with three named
differences, below, and its risk is drift rather than discovery.

### Semantics

- **The labels editor keeps Reviewers' two-homes solution, verbatim.** Both
  pages render `_field_labels_editor.html` once and both have a
  `.card-columns`, so they inherit the contract Reviewers settled: one
  include, two positions, on the exact complement of the panel's condition —
  inside the panel where it can render, in `.card-columns` where it cannot
  (locked, or mid-edit). This is the piece Observers had no equivalent of,
  so it is the only part of the move Item 2 did not rehearse.
- **The gate is `is_editable`, NOT Observers' `not is_archived`.** Observers
  earned the wider predicate because an observer row is a view grant —
  no assignments, no responses, no readiness rule. Reviewees and
  Relationships are the opposite on all three counts, so the exception does
  not transfer, and `spec/lifecycle.md` §5 already says a second claim on it
  needs its own stated reason. Stating this is the point: the risk is
  someone reading 19P.2 as a precedent.
- **Relationships' `Edit` acts on a pair, and can re-point it.** Its edit row
  carries `reviewer_pick` / `reviewee_pick` alongside `status`, so the row's
  identity is editable, not just its state. Arity is still exactly one row,
  and the expander needs no new affordance — but the edit-row bar sits under
  a row whose two identity cells are inputs, which is wider than anything
  Reviewers or Observers renders.
- **Both pages have column chips** (`data-col-toggle=` → 2 on Reviewees,
  1 on Relationships), so the toolbar's left pane is populated on both.
  Observers' deliberately-empty pane was its own case and does not recur.
- **Confirm keys stay unique per page.** `base.html` pairs a confirm to its
  button with a first-match `querySelector`, so each page's
  `data-delete-confirm` / `data-delete-btn` keys must remain distinct from
  its own others — the trap that made Item 1 wire and delete each card in
  one commit.

### Judgment calls — decided

- **One item, both pages, rung-by-concern.** 2026-09-16 — same edit twice;
  separate rungs invite drift.
- **The consolidating sweep moves to THIS item's close, not 19P.4's.**
  2026-09-16 — 19P.1 assigned it to 19P.4, but Item 4 is explicitly
  undecided and may become 19Q, and after this item no roster page keeps the
  old shape. A sweep owed by an item that may not exist is a sweep that does
  not happen.

### Blast radius (measured)

Commands run 2026-09-16 on `origin/main` at `907df01`.

- Templates: **742** and **710** lines (Reviewers 1,351, Observers 1,653) —
  the two simplest roster pages.
- Routes: nine each, eight mutating, all on `_require_editable` except
  `field-labels`; `_redirect_keeping_selection` → **5** call sites each.
- Tests hitting either Setup route: **67** files for Reviewees, **16** for
  Relationships. The Reviewees figure is larger than the page's own suite,
  because reviewees are a fixture for most of the app.
- **Eight spec documents, not the six first counted** — `ui_elements.md`
  and `rrw_functional_spec.md` were omitted, and the latter is not
  optional: it carried a `19P.3–.4` hedge, so it is inside the sweep's
  target set.
- **Shared code, omitted entirely from the first count.** `_handle_import`
  (`_shared.py`) carried the panel-open contract as `kind == "reviewers"`
  literals at two sites, so rung 4 had to edit a module three other slices
  read — and **Relationships does not use it at all**: its import handler
  is bespoke, with **two** in-place 400 paths where the shared one has
  one. Rung 4 was not one change applied twice.

### Status — closed 2026-09-17

**The ladder landed as planned, five rungs, none dropped or merged.** 1
the landing contract, 2 the toolbar, 3 the row expander and edit-row
bar, 4 the roster card and Unlock panel, 5 the specs and the close. The
`Operator actions` card renders on no roster page; nothing renders below
any preview table.

**Decisions confirmed at build.**

- The ladder's "five POSTs" was right by accident: four call sites, and
  the fifth POST (`create`) returned a bare `RedirectResponse`, so it is
  a conversion that also regains the filter round-trip.
- Both pages are sortable, unlike Observers, so the row-landing fallback
  carries two unresolvable-fragment cases here and one there.
- **Open question 2, answered at rung 3: no.** Relationships' edit-row
  bar needs nothing Reviewers' does not — measured in Chromium, the bar
  sits flush under its row at the same width on both pages.
- The guidance card moved at rung 4, not rung 2: the precedents disagree
  on when it goes, and Observers' siting matches this ladder.
- `_handle_import`'s two `kind == "reviewers"` literals **collapsed**
  rather than gaining a branch — it serves exactly two kinds and both
  have panels now.

**Two real defects, neither in any mutation table.**

- `relationship_column_state` counted two non-nullable integer FKs
  through `slot_row_count`, a TEXT predicate. Postgres refuses `integer
  <> character varying`; SQLite compares across types without a word, so
  the suite passed locally and `ci-postgres` went red. The FK readouts
  are gone — a non-nullable column's count is the roster total by
  construction — which makes the index's `none yet` branch reachable on
  Relationships and nowhere else.
- `_handle_import` still hardcoded `col_readouts = []` for Reviewees, so
  a failed import answered "Populated columns: none yet" over a roster
  it was displaying.

**One finding recurred at every rung, and it is the item's lesson: a
guard that proves less than it says.** Mutation survivors ran 3/10,
12/25 and 15/24 after first rounds that caught everything chosen — rung
4 shipped with no guard file at all — and four cold reads found 9, 12,
12 and 5 more on top, including both defects above and, at the close,
two contradictory sentences written in the same sweep. **A mutation
table proves what its author thought to mutate**, so the cold read is
the gate and not the table.

**Scope that moved.**

- **Rung 5a diverged from Doc impact deliberately.** The bullet asked
  for each page stated outright rather than by reference to Reviewers —
  right when a pointer led to a section describing a *different* shape.
  With all four identical it inverts, so `spec/setup_pages.md` gained
  one § *The roster card and the Unlock panel* and each page section
  keeps its own facts. No roster page points at a section describing a
  shape it does not have.
- **Three specs the plan never named** were falsified and added to Doc
  impact rather than fixed silently: `visual_style_rrw.md`,
  `color_tokens.md`, `lifecycle.md`. `email_template_editor.md` was on
  the owed list in error.
- **Rung 5c fixed one thing the item did not cause.**
  `session_reviewers.html` decided its Profile column from the rendered
  window where Reviewees reads a whole-roster flag — the surface 19I
  Item 12 rung 2 missed, because that sweep followed the chips and this
  column has none.

**Owed at rung 4, all discharged at rung 5c** — the two comment
placements, `.roster-readout-empty` (kept in four templates, decided and
recorded), the labels editor's `<section aria-labelledby>`, and
`guide.html`'s tag-label copy. The empty-filtered landing anchor needed
no fix: the empty state is inside the anchored table card on all four
pages.

### PR ladder

1. **The landing contract, both pages.** Four POSTs each gain `offset` and
   a fragment; `create` is **converted** from a bare redirect and gains the
   filter round-trip it never had, plus `focus=<id>`. The fallback script
   carries **two** cases here, not Observers' one — both tables ship
   `rrw-sortable` headers, so a row can move off the restored page under the
   operator's cookie sort as well as drop out of a filtered view. No layout
   change; this is the defect 19P.1 left behind.
2. **The toolbar.** The filter strip moves into the preview table's two-pane
   toolbar; the action row slims to `Clear` / `Add new` / `Search`. Chips
   join the left pane on both. The table card's gate widens to
   `... or total_row_count > 0 or is_editable` — otherwise the strip
   vanishes with the table in the two states that most need it. The
   guidance card stays half-width; it goes full width at rung 4 with
   `.card-columns`.
3. **The row expander + the edit-row bar.** `Edit` / `Inactivate` /
   `Activate` / `Delete`, the selected count and the delete confirm move into
   an injected panel; Save / Cancel move into a bracketed bar beneath the row
   being edited. The `Operator actions` card retires here.
4. **The Unlock panel.** The labels editor over the `Danger Zone` on the
   left, `Upload` on the right, `Lock` beneath the upload card — Reviewers'
   arrangement, both pages having its shape rather than Observers'. Carries
   the two-homes fallback and the `?unlocked=1` contract.
5. **Specs, the consolidating sweep, and the close.** Per-page sections for
   both, then the sweep that removes every *"until 19P.2–.4"* and restores
   one shared shape.

### Definition of done

- A row action on page 2 of a filtered roster returns to page 2 and lands on
  the acted-on row, asserted by route test, on **both** pages and all five
  POSTs each.
- The `Operator actions` card renders on **no** roster page:
  `grep -l "operator-actions-card" app/web/templates/operator/session_{reviewers,reviewees,relationships,observers}.html`
  → no matches. **`operator-actions-card`, not `operator-actions`** — the
  filter strip keeps the latter as `operator-actions-filter` after moving
  into the toolbar, so the looser grep is nonzero on pages that have already
  migrated and cannot reach 0. `session_assignments.html` renders the card
  too and is **not** a roster page, so it is excluded by name rather than by
  a `session_*` glob.
- `_field_labels_editor.html` renders in **exactly one of two homes** per
  request, on complementary conditions, asserted per page for each state.
  **Two `{% include %}` tags, one render** — Reviewers has exactly that
  (`session_reviewers.html:275` and `:598`), so "included once per page" is
  false of the precedent and would send a builder hunting for a structure
  the complement-condition layout cannot produce.
- No `.bottom-grid` on any roster page; nothing renders below any preview
  table.
- No spec sentence defers a roster shape to a future item:
  `grep -rnE "19P\.4|19P\.[0-9]–\.[0-9]" spec/` → 0, from **9**.
  **The check was re-aimed at rung 5a**, not quietly passed: it read
  `19P\.3\|19P\.4`, which matches every sentence *dating* the move as
  well as every one deferring to it, and the rewritten prose dates 19P.3
  exactly as it dates 19P.1's. With 19P.3 shipped, a forward reference is
  a range or a `19P.4`.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19P.3` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

1. ~~**Does the consolidating sweep land here or at 19P.4?**~~ **Answered:
   here.** Author's call at rung 5; the segment stays open for Item 4.
2. ~~**Does Relationships' edit-row bar need anything Reviewers' does
   not?**~~ **Answered at rung 3: no.** See Status.

### Out of scope

- **Item 4 (Invitations / Responses).** A different move — see its block.
- **`_field_labels_editor.html`'s markup** (`<div class="card">` with a bare
  `<h2>` where the panel's other tenants are `<section aria-labelledby>`).
  Owed since 19P.1, and this item makes it a three-page partial rather than
  fixing it; recorded in this segment's *Left for later* list.
- **`guide.html:174-177`**, which tells operators they edit tag labels
  "through the Reviewers, Reviewees and Relationships pages" and says nothing
  about Unlock. Recorded in the same list.

### Doc impact

- `spec/setup_pages.md` — per-page § *Body layout* for Reviewees and Relationships, each stated outright rather than by reference to Reviewers (the failure mode 19P.1 catalogued eight times); § *Operator actions card* **retires**, no page rendering it after this item; the § *Per-row Edit / Add / bulk actions* landing contract drops its page scoping; and the `.bottom-grid` / `.card-columns` sitings lose their last live referents (Item 3).
- `spec/operator_button_audit.md` — §§7 and 8 re-site their rows into the toolbar, the expander and the Unlock panel, as §6 and §8.5 already are; the gate note above §6 drops its per-page hedging, Observers' exception aside; and row 125's *"Reviewees and Relationships still read `Add`"* retires with the relabel (Item 3).
- `spec/operator_ui_concept.md` — § *Setup pages (Reviewees / Relationships) — shared shape* has no tenants left and retires into one shared description of all four pages (Item 3).
- `spec/settings_inventory.md` — § *URL state* rows for `offset=`, `focus=` and `?unlocked=1` widen to all four roster pages (Item 3).
- `spec/ui_elements.md` — `.session-row-selected`'s injector list gains the last two templates; `.table-card-toolbar`'s attribution becomes the roster pages rather than a list (Item 3).
- `spec/participant_model.md` — the Reviewees Setup page's description, the one spec outside the shared set that names it (Item 3).
- `spec/rrw_functional_spec.md` — the roster-page description stops naming exceptions and states one shape (Item 3).
- `spec/visual_style_rrw.md` — § *Width discipline*'s roster example and § *Danger-zone card uses* both scoped the move to Reviewers; **added at rung 5c**, found by the cold read, not named at planning time (Item 3).
- `spec/color_tokens.md` — the `.page-guidance` token argument scopes the full-width move to Reviewers; **added at rung 5c**, same finding (Item 3).
- `spec/lifecycle.md` — §5's *"what is hidden differs by page"* paragraph described a `.bottom-grid` no roster page renders any more; **added at the close**, found by `spec-writer`, not named at planning time (Item 3).
- `docs/status.md` — row for Item 3 as it lands (Item 3).

**Added mid-build, all honoured.** Rung 2's cold read found five
sentences this list had not named — `ui_elements.md`'s `Delete` siting
and `.table-card-toolbar` attribution, the button audit's Reviewees /
Relationships rows, and `operator_ui_concept.md`'s and
`setup_pages.md`'s `Operator actions` descriptions — all inside the
files above, and all swept at rung 5. Rung 3 added a sixth that was a
**question rather than a relabel**: §6's *"the checkbox is also
`required`"* is false of all four pages and forced (the expander's
confirm shares `<noun>-bulk-form` with `Inactivate` / `Activate`), so
rung 5b adjudicated the sentence rather than changing the markup.

## Item 4 — Invitations and Responses — ~~a different move, not the same recipe~~ **retired 2026-09-17**

**Retired by the author, unbuilt.** Reasoning in `### Status` below.
What follows first is the **2026-09-14 stub** that raised the question,
body unchanged. Two things around it were edited at retirement and are
not part of it: this heading, and the closing line of the 2026-09-17
annotation below the stub, which now points here.

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

> **Annotated 2026-09-17 (Item 5).** "Nothing to re-house" was measured on
> *selection* machinery and is still true of that. It is not true of the pages:
> Item 5 re-houses their filter card into the table toolbar, so these two pages
> now take part of the idiom without taking selection. That also partly settles
> the sequencing premise above — the toolbar half of the idiom is carried to
> them before this item is taken up; what is left to judge is the expander
> half. The stub's container question is untouched.
>
> **Superseded the same day** — see `### Status` below.

### Doc impact

- `spec/operations_pages.md` — the two pages' row-level affordance, had the expander landed. <!-- doc-impact-waived: Item 4 retired unbuilt 2026-09-17; nothing shipped, so there is nothing to document. The section exists so `close_check.py 19P.4` reads a retirement rather than a gap -->

### Status — retired 2026-09-17, unbuilt

**The spec had already decided this.** `spec/operations_pages.md` §
*Out of scope for both pages* says, and said before this segment
opened: *"**Bulk-select rows for batch action.** Bulk send / remind
happens via the Workflow card's super-buttons (which act on every
eligible row session-wide); per-row buttons handle targeted
intervention. **No multi-select checkbox column on either table.**"*
An expander is the home for selection-driven actions; a page the spec
forbids selection on has none to home. That is the whole argument, and
it is stronger than the greps below, which only confirm the code
agrees.

Re-measured at retirement, after Item 5 had carried these pages the
toolbar half:

| | `session_invitations.html` | `session_responses.html` |
|---|---|---|
| `type="checkbox"` | 0 | 0 |
| `formaction` | 0 | 0 |
| `session-expander` | 0 | 0 |

**"Selection-driven" is doing the work in that sentence, and these
pages are not actionless.** Both include `next_action_card.html`
unconditionally, whose Workflow-card super-buttons post to
`/invitations/generate`, `/invitations/send-all` and
`/invitations/remind-incomplete` — session-wide mass actions, named as
the alternative in the very spec bullet above. Invitations also
carries **three per-row buttons** in a trailing `col-shrink` Actions
column: `Send`, `Send reminder`, `Regenerate`. Neither set is
selection-driven, which is why neither wants an expander: a
session-wide button belongs on the Workflow card that scopes it, and a
per-row button already sits on its own row, which is the placement an
expander exists to achieve.

**19P shipped two expander flavors, and the second does not change
the answer either.** Besides the JS-injected selection panel, all four
roster pages render a server-side **edit-row bar** — the same
`session-expander` classes, gated on `edit_id` / `add_mode` rather
than on selection, holding `Save` / `Cancel` for a row being edited.
Assignments and these two pages have no row editor: assignments are
regenerated rather than edited, and an invitation or a coverage row is
a readout, not a record with fields. So neither flavor has a tenant
here.

Giving these pages an expander would therefore mean inventing
selection **and** an activate / inactivate affordance neither has ever
offered, to carry a detail view that navigation already carries. The
stub reached the same measurement on 2026-09-14 and stopped one step
short; the author took the step, which also settles Item 5's
annotation that the expander half was "left to judge". **The container
question is answered by not needing one** — neither 19P Item 4 nor
19Q.

What the stub was really pointing at survives elsewhere. The two
detail pages are thin — `session_responses_reviewee_detail.html`
renders **no** field the table row does not, and the reviewer page
adds exactly one, the last-issued invitation URL — and growing them is
named in Item 5's *Out of scope*. The author's two held row-link asks
(Item 5's open questions 1 and 2) are the live thread, and they are
**navigation, not selection**, so nothing here blocks them.

---

## Item 5 — The three Operations tables get the roster toolbar

### Opportunity

`base.html:1693-1701` already names this gap: seven templates share
`.table-card-toolbar`, four roster pages opted into the `is-split`
modifier one at a time across 19P.1-3, and **the three that stay
unsplit are Assignments, Invitations and Responses**.

So an operator who has learned the roster pages meets different table
furniture in three other places:

| | Assignments | Invitations / Responses |
|---|---|---|
| Search card | **lone** child of a `bottom-grid`, `.grid-right` | **paired** with the info card in one `bottom-grid` |
| Submit label | `Search` | **`Apply`** |
| Count line | below the toolbar, outside it | below the toolbar, outside it |
| Selection controls | in the search card | none — no checkboxes |

All three search cards are **half width** (`base.html:1284-1286`;
`spec/operations_pages.md:75` for the pair). Lone against paired is
what decides where each card can go.

Assignments also still carries the pre-19P arrangement: `setBtn(` ×3,
`row-select` ×4, `formaction` ×3, **zero** expander — its `Inactivate`
/ `Activate` and `0 selected` readout in a card in the page's corner,
away from the rows they act on. The defect 19P exists to fix.

Reported by the author, 2026-09-17, page by page.

### Decision

**Apply the roster recipe where it fits and stop there.** Assignments
gets both halves — the split toolbar *and* the expander — because it
has selection. Invitations and Responses get the toolbar only, because
they have no selection to re-house; their rows stay links.

`Apply` becomes `Search`. Two labels for one control is the drift, and
`Search` wins because it is what four roster pages and Assignments
already say — the minority renames.

**Rejected: a shared toolbar partial.** The panes differ per page
— Assignments has a `Search by` select the other six lack, the four
rosters carry `Add new` (button-audit rows 125/132/139/165) and these
three do not — so it would take a parameter list longer than the markup
it saves. The shared thing is the CSS, and it already exists. `Clear` is not one of the differences — all three render it on the
rosters' own conditional (`session_invitations.html:94-97`).

**Rejected: giving Invitations and Responses selection** to make the
recipe uniform. That was Item 4's question when this was written;
Item 4 retired on 2026-09-17 having answered it *no*, so the rejection
now stands on its own rather than deferring; this item
moves controls and renames a button, and adds no capability.

### Semantics

- **Moving the filter card settles the info card's width in the same
  rung.** They are the two children of one `bottom-grid`
  (`session_invitations.html:25,65`), so moving one strands the other
  in a `1fr 1fr` grid. **Full width, rejecting half width flush
  right** — the author's choice in the same situation on 2026-09-10
  (`session_assignments.html:168-172`), but for an *actions* card, a
  control the eye seeks; a counters card is a readout the eye sweeps,
  and eight pills in half a page wrap badly.
- **Assignments' `bottom-grid` empties entirely**, the operator-actions
  card being its only child, so the grid goes too. That 2026-09-10 call
  is about this same card, so removing it honours the call rather than
  reversing it.
- ~~**`filter-card` is not retired** — `session_validate.html` uses it
  and is out of scope.~~ **Wrong, corrected at rung 3.** Validate
  carries `severity-filter-card`, a different class token; a substring
  grep counted it as a caller. Invitations and Responses were the
  class's only tenants, so it retires with them.
- **Two counts, gating differently — do not conflate them.** The
  *preview-count line* renders in every lifecycle state; the
  *selected-count pill* is inside `{% if can_edit %}`
  (`session_assignments.html:243-247`), and `spec/assignments.md` "The
  page's lifecycle surface" puts it in the selection-driven half —
  "the count itself is not in this card". The template comment at
  `:176-184` is looser than the spec and is not the contract. So search
  and `Clear` stay reachable on a `ready` session; the pill goes to the
  expander with its buttons, still `can_edit`.
- **The preview-count line moves into `toolbar-left`**, under the
  pager, where the roster idiom puts it
  (`session_reviewers.html:743`) and where
  `spec/rrw_functional_spec.md:1114` and `spec/ui_elements.md:626` say
  it belongs. (`spec/operator_ui_concept.md:92` was cited here too and
  is struck: it describes the two-pane toolbar but never mentions the
  count line.) All three render it
  just outside the toolbar today (`session_assignments.html:325`,
  `:130`, `:108`); `tests/unit/test_pager.py` pins its order with the
  pager.
- **The operator-actions card is gated on `can_edit`** (rung 1, not
  planned). It never was: 19I Item 8 kept it renderable in every state
  because the *search* was in it and `spec/assignments.md` requires the
  read-only half to survive every state. With the search in the toolbar
  — which renders unconditionally — the rule is met better than before,
  and what would be left on a locked session is an empty box. Rejected:
  leaving it ungated until rung 2 deletes it, which ships that box for
  one rung.
- **Search and a page turn land identically.** The roster form is a
  `GET` to `<base>#{{ pager_anchor }}`, and a `GET` submission replaces
  the query while leaving the fragment alone. Same anchor on all three.

### Judgment calls — decided

- **One item, not two** (2026-09-17). Assignments' scope is larger, but
  the toolbar move is one recipe applied three times and the rename is
  a cross-page decision; splitting puts one decision in two documents.
- **`Search`, not `Apply`** (2026-09-17). Five surfaces against two.
- **The pager does not move.** It already renders below the chips on
  all three; what changes is that the pair becomes the toolbar's *left
  pane* rather than its only content.

### Blast radius (measured)

Commands run 2026-09-17 on `origin/main` at `65f66ca`.

- Templates: `session_assignments.html` (581 lines),
  `session_invitations.html` (298), `session_responses.html` (221).
- `grep -rn "Apply" app/web/templates/ | grep -v "^.*#"` → the label
  ships **4** times: the two filter cards in scope,
  `_preview_picker.html:48` (button-audit row 72, label on its own line
  so `>Apply<` misses it) and `sys_admin_session_audit_log.html:168`
  (`Apply filters`). Only the two are renamed — see Out of scope.
- `grep -rln "filter-card" app/web/templates/` → **4**
  (`session_validate.html` and `base.html` stay). **Wrong — a
  substring grep.** Validate's token is `severity-filter-card`;
  scanning `class="…"` by token gives **2**, both in scope, so the
  class retires at rung 3 (found by the rung-3 cold read).
- `grep -rln "operator-actions-card" app/web/templates/` → **2**
  (`session_assignments.html`, `base.html`) — retirable after rung 1,
  to be confirmed rather than assumed.
- `grep -rln "sessions/{.*}/<page>\|/<page>\"" tests/` → assignments
  **59** files, invitations **13**, responses **6**. One pins the label
  being renamed: `tests/integration/test_invitations.py:944` asserts
  `">Apply</button>" in actions`.
- `grep -rn "Apply" spec/ docs/` (the skill's rename sweep) →
  `spec/rrw_functional_spec.md:1311` §9.9 states "Filter card — Status
  dropdown + free-text search + Apply / Clear", naming both the card
  being dissolved and the label.
- Governing specs: `spec/operations_pages.md` for Invitations and
  Responses, **`spec/assignments.md`** for Assignments — its "Assignments
  operator page" § is what rungs 1-2 falsify.

### Status — closed 2026-09-17

**Landed as planned**, four rungs across five PRs — #2434 carried the
plan and no rung, then #2435 rung 1, #2436 rung 2, #2437 rung 3, and
this close as rung 4. All seven table
pages carry `.table-card-toolbar.is-split`; Assignments took the
expander too; `Apply` is `Search`; `.grid-right`,
`.operator-actions-card` and `.filter-card` are all retired.

**Four decisions the plan did not carry**, each recorded in
`Semantics` or `Doc impact` above: the `can_edit` gate on Assignments'
card (rung 1); deleting Scope 2's last two rules once the card lost
its form (rung 1); rendering only the actionable status button, which
is a **behaviour change** and not a move (rung 2); and lifting the
table card out of `{% if rows %}` on Invitations and Responses,
because a search matching nothing would otherwise take away the only
way to clear it (rung 3). Assignments already rendered its card in
every state — what rung 1 had to fix there was a toolbar `<div>`
spanning both branches of `{% if not pair_sample %}`, which is the
same restructure meeting the same conditional from the other side.

**Three defects the rungs shipped and a cold read caught.** An
unclosed `<div>` on Assignments' no-match page, from a toolbar opening
above `{% if not pair_sample %}` and closing inside its `else`. A
missing capture-phase sort guard — `_rrwApplySort` slices
`tbody.children` with the injected panel among them, measured at row
30 of 31. And one root cause behind two more: the roster idiom assumes
a selectable row is a **visible** row, which this page's client-side
`Show` filter breaks, stranding the panel after a hidden row and
leaving `colSpan` stale on a chip toggle. Fixed by restoring the
invariant, not by patching the anchor.

**The lesson is one level up from Item 3's.** That item's was *a
mutation table proves what its author thought to mutate*. This one:
**a guard written in answer to a cold read still needs its own.** The
test added to pin the retired `.filter-card` rule collected lines
ending in `{`, so a one-line rule walked past it and the mutation
restoring `.filter-card form { margin: 0; }` survived — the same
defect the rung-2 cold read had already flagged in
`test_roster_expander.py`'s twin, copied across without noticing it
had a second half. Both now read the stylesheet brace to brace through
one parser. Adjacent: the blast radius's `filter-card` line was wrong
(a substring grep counting `severity-filter-card` as a caller) and had
been restated twice before anyone re-ran it, and the Responses twin of
the count-line test passed vacuously by splitting the page at the
first of twelve `</form>`s.

**The close's own cold read found four false sentences and four
inconsistencies**, which is the same rate every rung of this item ran
at and worth recording as the shape of the work rather than as a
mishap. The four: `.session-row-selected`'s funnel is named
`render()` on **four** of the seven pages and `renderPanel()` on
Observers, not `refreshExpander()` on six; `operator_ui_concept.md`
claimed an `Assignments preview` `<h2>` that no template renders and
that `spec/assignments.md` correctly denies **500 lines away in the
same commit**; the expander carries *two* buttons on a mixed
selection, not "one"; and its `M` is the **visible** rows, not the
rendered window — the roster contract's phrase, borrowed onto the one
page whose client-side filter is exactly what makes it wrong. Three
specs also gave three different orders for one filter strip, none of
them the DOM's (`Status:` → `Search by:` → search → `Clear` →
`Search`).

**Two left open for the author**, both pre-existing and named rather
than fixed: Assignments' `Clear` renders on `{% if filter_q %}` while
`_assignments.py:202` counts status in `is_filtered`, so a status-only
filter leaves the page visibly filtered with no way to clear it
(Reviewers uses `{% if filter_status != "all" or filter_search %}`);
and the three Operations pages gate the **whole left pane** on a
has-rows conditional (`rows` on two, `pair_sample` on Assignments)
where the four rosters include the partials unconditionally and let
them self-guard. Aligning either changes what
a no-match search shows, which is more than this item's move.

### PR ladder

1. **Assignments: the split toolbar.** Search, `Search by`, `Clear` and
   the submit into `toolbar-right`; chips, pager and the preview-count
   line into `toolbar-left`. The selection controls and the selected
   count stay put, so the page stays coherent — they reach the bulk
   form through `form=` + `formaction`
   (`session_assignments.html:252-262`), not through the GET form being
   moved. **Not "no behavior change":** the form gains the
   `#{{ pager_anchor }}` landing, and `base.html:1448`'s
   `.operator-actions-card ... label.filter-search { flex: 4 }` stops
   applying once the strip leaves the card, shifting the field ratios.
   Both intended; neither is nothing. For one rung the emptied card
   sits in the page corner holding `0 selected` and two buttons — a
   dev-slot look.
2. **Assignments: the expander.** `Inactivate` / `Activate` and the
   selected-count pill into the injected row, per 19P.1-3 rung 4. The
   `bottom-grid`, `operator-actions-card` **and `.grid-right`** go if
   nothing else uses them — `.grid-right` has exactly one caller
   (`base.html:1301-1305`), so this rung leaves the rule dead.
3. **Invitations and Responses: the split toolbar, the rename, and the
   full-width info card.** All three on both pages, because the grid
   leaves them inseparable. The preview-count line joins `toolbar-left`
   here too.
4. **The close.** `spec/operations_pages.md` (§*Filter card* on both
   pages, the body-shape line, and the count line's placement),
   `spec/rrw_functional_spec.md` §9.9 / §9.10, `spec/ui_elements.md`'s
   `.table-card-toolbar` row (four pages → seven), the button-audit
   `Apply` rows 85 / 91, and `docs/status.md`.

### Definition of done

- `grep -rn "Apply" app/web/templates/operator/session_invitations.html
  app/web/templates/operator/session_responses.html` → 0. (Not
  `>Apply<` across all templates: that pattern misses
  `_preview_picker.html:48`, so it would pass with an `Apply` submit
  still shipping.)
- `tests/integration/test_invitations.py:944` asserts the new label.
- All seven table toolbars carry `.table-card-toolbar.is-split`, and
  `base.html`'s note naming the three exceptions is rewritten or gone.
- Assignments' selection controls render in the injected expander row
  and nowhere else; `grep -c "operator-actions-card"
  app/web/templates/operator/session_assignments.html` → 0.
- On Invitations and Responses the info card is the full width of the
  page in every state.
- The search and `Clear` still render on a `ready` session on all three
  pages (19I Item 3's rule), asserted per page — **and the
  selected-count pill still does not**, per `spec/assignments.md`.
- The preview-count line renders inside `toolbar-left` on all three;
  `tests/unit/test_pager.py`'s order assertion still passes.
- Looked at in Chromium, light and dark, at 1280px and phone width.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19P.5` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

1. **The two Invitations row links** — to a per-reviewer summary page,
   and to the reviewer surface showing their responses. **Held by the
   author, 2026-09-17** pending a fuller description; the layout lands
   first. Two facts found while asking: the row already links to
   `/invitations/{id}/detail` from the reviewer's name
   (`session_invitations.html:182`), and
   `/operator/sessions/{id}/preview-surface/{n}?reviewer_email=`
   (`app/web/routes_operator/_preview_surface.py:113`) already renders
   the reviewer surface with saved responses prefilled
   (`app/web/routes_reviewer/_surface/_context.py:298`), read-only via
   `preview_mode`.
2. **Does Responses want the same links**, having its own
   `/responses/{reviewee_id}/detail`? Author's call, after 1.

### Out of scope

- **Selection on Invitations and Responses** — was Item 4's question;
  Item 4 retired 2026-09-17 having answered it *no*, and
  `spec/operations_pages.md` § *Out of scope for both pages* had
  already said so. Out of scope here either way.
- **The thin 11C detail pages themselves.** Growing
  `session_invitations_reviewer_detail.html` past its scaffold is its
  own work; this item does not touch it.
- **`session_validate.html`'s filter card.** Same class, different
  page, no table toolbar to move into.
- **The other two `Apply` buttons** — `_preview_picker.html:48` and
  `sys_admin_session_audit_log.html:168` (`Apply filters`). Neither
  sits in a table toolbar, and the ask was to harmonize these three
  pages with Assignments, not to sweep the word. Named because the
  rename grep finds them.

### Doc impact

- `spec/operations_pages.md` — the three pages' table-toolbar shape: the split panes, what sits in each, and the `Search` label (Item 5).
- `spec/ui_elements.md` — §10's layout primitives: `.table-card-toolbar.is-split` now covers all seven table pages, not four; the `.bottom-grid > .grid-right` row documents a rule rung 2 deleted; the `.session-row-selected` row counts six templates injecting panels and names them all roster pages, where Assignments is now a seventh and an Operations page, with `render()` for a funnel rather than `refreshExpander()`; and `.col-chip-row.is-grouped` is a new primitive (Item 5).
- `spec/operator_button_audit.md` — the `Apply` rows become `Search`; Assignments' `Inactivate` / `Activate` rows move to the expander; rows 71i / 71j and §11.5's preamble still put `Search` / `Clear` in the operator-actions card, which 19P.1-3 rewrote to "Table toolbar (was Operator actions)" for the same move (Item 5).
- `spec/assignments.md` — the Assignments page's controls and where they render, including which half the selected-count pill belongs to, and § *The split is per-half, not per-card*, whose premise (the search inside the card) rung 1 removed (Item 5).
- `spec/operator_ui_concept.md` — Assignments' body shape still reads "→ an operator-actions search / bulk card, half width and flush right →" (Item 5).
- `spec/rrw_functional_spec.md` — §9.9's "Filter card — Status dropdown + free-text search + Apply / Clear" for the two pages; §1106-1114's two-pane toolbar now covering seven pages; and §1230-1238's "Operator-actions card", which still lists the status filter, the search box and the Search-by dropdown alongside the bulk controls (Item 5).
- `docs/status.md` — row when the item lands (Item 5).

---

## Item 6 — The Invitations row opens a reviewer page that does not wait for an invitation

### Opportunity

Reported by the author, 2026-09-17, from the detail page on a `draft`
session.

**The table's rows do not depend on invitations; its links do.**
`build_invitations_rows` iterates `monitoring.per_reviewer_progress`,
whose row set is `_assigned_active_reviewers` — active reviewers with
an included assignment — and consults no `Invitation`. But
`session_invitations.html:207` wraps the name in
`{% if row.invitation %}`, so before **Create invites** the page is a
list of names that go nowhere.

**The page they cannot reach adds one field** the table row does not,
the last-issued invitation URL (measured at Item 4's retirement).
**What would make it worth opening already exists**: the preview
surface renders that reviewer's own surface, inert under
`preview_mode`, **with their saved responses** — verified by seeding
one, which no test does. Reachable today only from the Previews hub.

### Decision

**Re-key the route to the reviewer, render the link always, and put
the reviewer's surface one click from it.**
`/invitations/reviewers/{reviewer_id}` replaces
`/invitations/{invitation_id}/detail`; the name links unconditionally;
the Review Progress card gains a preview-surface link opening in a
**new tab**.

- **Rejected: keeping the invitation key** and gating the link. The
  invitation is not the subject of the page: it supplies one field
  (`most_recent_invitation_url`), while the reviewer it is looked up
  from supplies the row match, the `<h1>`, the email, the breadcrumb
  label and the template's `reviewer` slot. Keying on the field
  rather than the subject is what makes the link conditional.
- **Rejected: a second route** for the un-invited case. One page, one
  key; the invitation becomes an optional field on it.
- **Deferred to Item 7: moving the Previews hub's email previews
  here.** That retires a chrome tab and needs its own Opportunity —
  Item 7's stub holds what has been decided. Author's call,
  2026-09-17: Item 6 first, Item 7 after seeing it, **so Item 6 must
  not make the retirement harder** (§ *Semantics*).

### Semantics

- **Old URLs 308 to the new shape** where an invitation exists, so a
  bookmark survives. `_require_invitation_in_session` stays for the
  three per-row POSTs, which are genuinely invitation-keyed.
- **No invitation is a normal state.** `invite_url` resolves to `None`.
  ~~The template already renders *"No invitation URL has been issued
  yet."* — written for an unsent invitation, true unchanged for an
  absent one.~~ **Overturned at rung 2a**: it is *not* true unchanged.
  The two states differ, and conflating them is what the author
  reported from the dev slot. The absent case now names the action
  instead; the URL line keeps its original meaning for an invitation
  that exists but has never been sent.
- **The reviewer-scoped lookup is hoisted, not copied.**
  `_require_reviewer_in_session` lives in `_setup_reviewers.py`, a
  sibling slice. Two rules push it to `_shared.py` and neither is a
  spec prohibition: `spec/architecture.md` § *Three-layer split* calls
  `_shared.py` "the preferred shape" for a lookup two routes need, and
  the ban on slice-to-slice imports is `CLAUDE.md`, filed in
  `docs/unenforced_conventions.md` §2.2 as a convention **with no
  check**.
- **A new tab is the existing contract.**
  `spec/operator_ui_concept.md:197` already says this route is
  *"opened in a new tab"*; `_preview_picker.html:80` is the shipped
  precedent. It also disposes of back-navigation: the detail page
  stays in the first tab.
- **The surface shows responses an instrument is configured to hide.**
  `preview_mode` forces `accepting=True`, so
  `responses_visible_when_closed` is bypassed. Deliberate operator
  affordance, author's call 2026-09-17.
- **The re-key widens who can reach the no-row page; it does not
  create it.** Every table row is an active reviewer with an included
  assignment, so the Review Progress card's gate never fails *from the
  table*. But deactivating a reviewer leaves their invitation alone,
  so the old invitation-keyed URL already reached this page from a
  bookmark — measured on the pre-re-key commit: 200, no card. What
  changes is the set: any reviewer in the session, including one that
  never had an invitation. The page renders with no cards and so no
  surface link, which is right. Rung 1 pins both ways off the table,
  inactive and unassigned.
- **Forward compatibility with Item 7: this item adds no coupling to
  the Previews hub.** The link goes straight at `/preview-surface` and
  always passes a resolvable email. The two that already exist are
  enumerated in Item 7's stub, § *What Item 6 leaves for it*, which
  owns them.

### Judgment calls — decided

All 2026-09-17.

- **`/invitations/reviewers/{reviewer_id}`, not `/reviewers/{id}`** —
  the latter collides with the Setup roster namespace, and the page
  belongs to the Invitations tab.
- **308, not 303** — permanent, method-preserving, and what
  `/preview` → `/preview-surface/1` already does.
- **Banner copy replaced, not conditionalized.** One neutral sentence
  is true from both entry points; two variants is a branch to keep
  right.
- **The surface link is `btn secondary`** — the canonical Secondary
  role (`spec/ui_elements.md` §6), matching `_preview_picker.html:79`
  for the same destination.

### Where the link goes

Decided up front, 2026-09-17, as the condition for setting the
scaffold rule aside.

- **A `.card-action-row` at the foot of the Review Progress card**,
  after the scaffold note — right-flushed, `--space-3` above it. Not
  inline in the stats line (it is a `.btn`, not prose) and not beside
  the `<h2>` (this page has no heading-row action idiom).
- **Because that is where the same button already sits.**
  `_preview_picker.html:78-82` puts `Open full preview` — the same
  destination — in a right-flushed card action row on the Previews
  hub. Matching it means one button in two places looks like one
  button, which is the drift Item 5 spent a rung undoing for
  `Apply` / `Search`.
- **`.card-action-row` gains a second caller**, having had exactly one
  since 11F. It lives in `base.html` and is **not** in
  `spec/ui_elements.md` §10; the second caller is what makes it worth
  recording, so the manifest picks it up.
- **Labeled `Open reviewer surface`**, not `Open full preview`. The
  hub's label carries the word this item is neutralizing in the
  banner, and from here the operator is inspecting rather than
  previewing. **This leaves two labels for one destination**, which is
  a known cost and not a drift: Item 7 either retires the hub, which
  dissolves it, or keeps it and settles the pair. Recorded rather than
  discovered.
- **The card's scaffold note is now half false** — *"Per-assignment
  and per-response detail will land in a future segment"* — since the
  link reaches exactly that. Rung 2 rewords it; it does not survive
  the thing it was promising.

### Blast radius (measured)

Commands run 2026-09-17 on `origin/main` at `0587ca8`.

- `grep -rn "invitations/{{ .*}}/detail" app/web/templates/` → **1**
  (`session_invitations.html:208`) — the only inbound link in the app.
- `grep -rln "invitations/.*detail" tests/ --include=*.py` → **1**
  (`test_invitations.py`), carrying **3** URL-bearing sites —
  `:675-676`, `:689`, `:704` — under one test from `:680`.
- `grep -rlnE "invitations/\{(invitation_id|iid|inv_id)\}/detail" spec/ docs/`
  → **2 live** (`spec/operations_pages.md:310`, `docs/status.md:825`)
  plus **2 dated 11C rows** kept as history. The placeholder is spelled
  three ways, so a single-spelling grep finds one of the two.
- `grep -rln "preview-surface" app/web/templates/` → **1**
  (`_preview_picker.html`); `… spec/ docs/` → **5**; `… tests/` → **6**.
- `spec/operator_button_audit.md` §13 → **5** rows (84, 85, 86, 87,
  87a), `Source: session_invitations.html`. The new link ships on
  `session_invitations_reviewer_detail.html`, which the audit does not
  cover at all — see `Doc impact`.
- Tests asserting the preview surface renders a **saved response**:
  **0**, across all six files above.

### Status

**The ladder became four rungs, not three.** Rung 2a was added after the
author found the Invitation card on the dev slot reporting
`Email Status: not sent · Email Sent: — · Last reminder: —` for a
reviewer with **no invitation at all**, under a chrome pill reading
`Invitations: NOT CREATED`. Not a regression rung 1 introduced: rung 1
made the state *reachable from the table*, and the card had always
derived its email status from the outbox, which falls back to
"not sent" when there is nothing to send.

Decisions confirmed at build:

- **Three facts, not one.** Invitation created / email sent / reminder
  sent are separate, and the card reports all three. Author's words,
  2026-09-17: *"Top line to report whether the Invite has been created /
  Bottom line to report when the Email has been sent (if at all), and
  when was the Last reminder was sent (if at all)."*
- **The em-dash means "no date", not "no invitation"** — author's
  correction of a first fix that hid the whole line.
- **Both lines read `invitation`, not `row`.** `sent_at` and
  `last_reminder_at` are columns on `Invitation`; `row` is
  `_assigned_active_reviewers`, so reading it lost both facts for an
  invited-then-deactivated reviewer. Found by re-reading the code after
  the copy was settled, and the reason the card could report "not sent"
  with nothing to send.
- **`No invitation URL has been issued yet.` stays**, and is not
  redundant with "not created": `generate_invitations` discards the raw
  token, so the URL exists only once an invitation has been *sent*.
- **Mutation testing found the dates line half-unpinned.** No test sent
  a reminder, so two mutants survived; `test_detail_page_dates_line_reports_a_sent_reminder`
  closes it.
- **And one of that run's "caught" verdicts was false.** The mutant for
  the URL region rewrote `{% elif %}` to a second `{% else %}`, which
  is a Jinja syntax error: every render failed, so the red told us
  nothing about the assertions. A genuine two-branch collapse left the
  suite green. Caught by `diff-reviewer`, not by the harness that was
  supposed to catch it — **a mutant that breaks the template is not a
  mutant**, and a mutation run is only worth its weakest verdict.
  `test_detail_page_url_region_has_three_states_not_two` pins all three
  states now, and the runner gained a parse gate that reports such a
  mutant `INVALID` instead of `CAUGHT` — which immediately exposed a
  *second* false verdict in the same original run. The corrected run is
  nine mutants, all parseable, all caught.
- **The card told an ineligible reviewer's operator to press a button
  that cannot reach them.** `generate_invitations` selects active
  reviewers with an included assignment — the same predicate that makes
  `row` None here — so *Create invites* would have left the card at
  `not created` however often it was pressed. The guidance now branches
  on eligibility. Found by Codex on rung 2a's PR; the population is the
  one rung 1 made reachable, which is why nothing earlier caught it.
- **Rung 2b, built 2026-09-18.** OQ3 and OQ5 landed as planned. Two
  things worth keeping:
  - **The chrome pill and the card do not disagree after a failed
    send.** Chrome counts outbox rows with `status == "sent"`
    (`views/_setup.py:204`), so a failed row leaves it `NOT SENT` while
    the card reads `Email sent: <time> · failed`. Two true readings of
    one event; the card's pill is what explains the chrome's. Recorded
    in the template so it is not "fixed" later.
  - **The mutation runner stranded a mutant again**, this time because
    it was piped through `head -3`: stdout closed, the next print
    raised, the loop died mid-iteration, and the surviving mutant then
    failed the full suite as though the change were broken. The runner
    now snapshots every target up front and restores in `finally` with
    a tree-clean assertion. Second time this segment a tree-mutating
    runner has cost a diagnosis — the first was a 120s timeout.
- **Two claims in the same rung said more than the code did**, the
  failure mode this segment keeps returning to: the template comment
  claimed the card and the table show "one fact in two places" (false
  for `Email sent` after a Regenerate — different sources), and a test
  comment claimed the card reports no email status "at all" from an
  assertion scoped to a block that could not contain one. Both
  corrected; the regenerate divergence became open question 4.

### PR ladder

**Three slices as planned; four as built** — rung 2a was added mid-build
(see `### Status`). **The scaffold-first rule is set aside for this item**
(author, 2026-09-17) on the condition that the link's placement is
decided up front rather than iterated on the dev slot — it is, in
§ *Where the link goes* above. `CLAUDE.md` asks for an inert scaffold
so a page's *shape* can be agreed before logic attaches; this item
adds no page and no card, and the destination already ships, so a
disabled link would show a reviewer less than a working one.

1. **Re-key the route.** `/invitations/reviewers/{reviewer_id}`,
   `_require_reviewer_in_session` hoisted to `_shared.py`, the old URL
   308ing where an invitation exists, the table's link unconditional.
   **The invitation is resolved by reviewer, not taken from the
   path**: `most_recent_invitation_url` takes `invitation_id=` and
   `InvitationsRow.invitation` already carries the row via
   `monitoring._invitations_by_reviewer`. Plus a test for the state
   the re-key newly makes reachable — a typed URL for an inactive or
   unassigned reviewer. **No card on the page changes.**
2. **The surface link and its destination's copy.** The
   `.card-action-row` and its anchor; the scaffold note reworded; the
   neutral banner on the preview surface; and the test that saved
   responses render there. **Does not touch the Previews hub.**
2b. **The three answered open questions' surfaces.** Un-suppress the
   dropped-fields notice on the preview surface (OQ3), and give the
   Invitation card a delivery-state slot whose values derive from
   `EMAIL_OUTBOX_STATUSES` (OQ5) rather than a hardcoded set —
   `constitution.md` II. **Does not touch `regenerate_token`**: that is
   OQ4, and bundling an invitation-lifecycle fix into a page slice is
   what `CLAUDE.md` "Don't bundle independent changes" names.
3. **The close.** Docs per the manifest at the end of this item.

**OQ4 ships outside this item.** `regenerate_token` clearing
`last_reminder_at` changes the Manage Invitations Reminder column and
the reminder scheduler's view, neither of which this item owns. It also
needs a second half the card cannot supply: after a regenerate the
outbox still holds the previous URL, so `invite_url` is a **dead link**
until the new token is sent, and the card should fall back to *"No
invitation URL has been issued yet."* Both halves belong with invitation
lifecycle — 19Q Item 2, or its own slice. Author's call on placement.

### Definition of done

- `grep -c "{% if row.invitation %}" app/web/templates/operator/session_invitations.html` → 0, and a reviewer with no `Invitation` row reaches the page from the table and sees `Invite: not created` (rung 2a; this bullet named `No invitation URL has been issued yet.` until that rung separated the two states).
- `GET .../invitations/{invitation_id}/detail` 308s to the reviewer URL, pinned by a test.
- The surface link carries `target="_blank"` and `rel="noopener"`, and points at `/preview-surface/1?reviewer_email=`, not `/previews`.
- It renders as `Open reviewer surface` in a `.card-action-row` that is the **last child** of the Review Progress card, and the card's scaffold note no longer promises per-response detail as future work.
- A test asserts a **saved response value** renders on the operator preview surface — the gap this item found.
- The preview-surface banner no longer opens with `Preview` nor claims the page's content is a preview.
- Looked at in Chromium, light and dark, at 1280px and phone width, from both entry points.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19P.6` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

All five answered by the author, 2026-09-17/18; collapsed to their
answers. Three created work — see rung 2b and the note beneath it.

1. **Does the Responses detail page get the same treatment?** No —
   already reviewee-keyed, and a reviewee has no surface to link to.
2. **Item 7's shape** — retire the Previews hub. Became 19Q Item 1.
3. **Should the preview surface stop suppressing the dropped-fields
   notice?** **Un-suppress.** Same argument that justified rewriting
   the banner, one element down: 18K PR 5 suppressed it when this
   surface was pre-launch-only, and rung 2 gave it a second purpose.
   Rung 2b.
4. **Should the app reconcile what Regenerate leaves behind?**
   **Yes — `regenerate_token` clears `last_reminder_at` too.** It
   already clears `sent_at` and `opened_at`; the third stamp was an
   oversight, not a decision. An invitation-lifecycle fix rather than
   a card fix, so it ships on its own (see the note below).
5. **Where does a failed send show on the drill-in?** **On the
   Invitation card**, which reports email delivery state with `failed`
   among its values. Rung 2b.

### Out of scope

- **The Previews hub, all of it.** Item 7's question. This item adds a
  second door to the preview surface and closes none.
- **Growing the detail page past its scaffold.** Named in Item 5's
  *Out of scope*, still unowned.
- **`_operations.py:944-945`'s stale docstring** — it claims the
  Responses detail surface lists the reviewers assigned to the
  reviewee, and the template renders no such list. Found by Item 4's
  cold read and written down nowhere in `guide/` until this line.
  Left for whoever grows that page.

### Doc impact

- `spec/operations_pages.md` — the **Invitations** § *Per-row drill-in* (`:307`, not the Responses one at `:385`): the new URL, the unconditional link, the surface link in the Review Progress card, and the Invitation card's three reported facts — `Invite: created / not created`, the two date slots, and the three-state URL region (Item 6).
- `spec/reviewer-surface.md` — § *Operator preview mode*: the banner copy it quotes verbatim, and "reached from the Previews hub picker card" becoming one entry point of two (Item 6).
- `spec/preview_hub.md` — the preview surface gains a second entry point (Item 6).
- `spec/operator_ui_concept.md` — `:102` and `:367`, the two passages naming the picker button as the way in. Not `:197`, which this item leaves alone (Item 6).
- `spec/operator_button_audit.md` — the surface link's row, label `Open reviewer surface`, role Secondary. **Which section is an open question**: §13's `Source:` is `session_invitations.html` and this button ships on the drill-in page, which the audit does not cover (Item 6).
- `spec/ui_elements.md` — §10 gains `.card-action-row`, which ships in `base.html` and is absent from the primitives table. This item is its second caller since 11F, which is what makes it worth naming (Item 6).
- `docs/status.md` — the route-table row for the detail page, and the item row when it lands (Item 6).

**Not committed to:** `spec/architecture.md`. Its § *Three-layer split*
already prescribes `_shared.py` for a `_require_*_in_session` helper,
so the hoist changes nothing it says. <!-- cites: spec/architecture.md -->

---

## Item 7 — Should the Previews hub become the reviewer page? — **stub, author's call**

**Not planned. Sequenced behind Item 6 by the author, 2026-09-17**:
*"Item 6 first, then Item 7 after I've seen it. If we do 7, it will
likely involve retiring the preview page."* This block exists to hold
the decisions that conversation reached, so Item 6's references to
"Item 7" resolve to something and so the reasoning is not re-derived.

**No `### Doc impact` yet, deliberately.** There is nothing committed
to change until the item is planned, and a pre-waived bullet written
to satisfy `close_check.py` is the failure mode `segment-plan`'s own
skill warns about. It arrives with the plan.

### What is on the Previews hub, measured 2026-09-17

`session_previews.html` is **40 lines** and includes three things:
`next_action_card.html` (shared chrome), `_preview_picker.html` and
`_email_preview_region.html`.

| | What it is |
|---|---|
| "Previewing as" | `<input>` + `<datalist>` typeahead, Apply, and a `Prev` / `Next` / `Random` row |
| "About this reviewer" | count line, name, email, assigned-reviewee count and first three names |
| "Open full preview" | the reviewer surface, `target="_blank"` (`_preview_picker.html:80`) |
| Email preview region | that reviewer's **Invitation** / **Reminder** / **Responses received** emails, all three `is_shipped=True` (`views/_previews.py:296-320`) |

**All four are per-reviewer.** Nothing on the page is session-level,
which is the whole argument for the move: a per-reviewer page is where
per-reviewer things belong, and Item 6 builds one.

### When each door is open — measured 2026-09-17

The author's question, and the answer is not what it looks like: **the
two doors do not open at the same time, and one of them never closes.**

`/preview-surface/1?reviewer_email=` returns **200 in every state
measured**, including before Prepare — pages come from
`_pages_for_session`, which walks *instruments*, not assignments, and a
session has one from creation. So the route is not the gate; the
**doors** are.

| | picker (Previews) | drill-in link (Invitations) |
|---|---|---|
| roster imported, not generated | ✓ | — |
| after Prepare | ✓ | ✓ |
| after Create invites | ✓ | ✓ |
| reviewer inactive | ✓ | — |
| active, all assignments excluded | ✓ | — |

`build_preview_picker_context` (`views/_previews.py:145-151`) selects
**every** `Reviewer` in the session — no status filter, no assignment
filter. The Invitations table is `_assigned_active_reviewers`, so its
link needs an **active** reviewer with an **included** assignment.

**Three reviewers the hub reaches and the drill-in cannot**, and the
first is not an edge case:

1. **Before Prepare.** Roster imported, nothing generated. This is the
   hub's stated purpose — *"spot-check what they get before activating
   the session"* (`session_previews.html`) — and it is exactly the
   *when*, not *what*, objection below, now with a measurement behind
   it.
2. **An inactive reviewer.**
3. **An active reviewer whose assignments are all excluded.**

So **retiring the hub loses reach, not just a page**, unless Item 7
also widens the drill-in's gate — which means changing what the
Invitations table lists, and that row set is a monitoring concept
(`per_reviewer_progress`), not a roster. That is the real cost to
weigh, and it was invisible until this was measured.

### The case for, and the case against

**For.** The Invitations table is a **better reviewer picker than the
picker**: search, three chip-toggled tag columns, sortable headers,
pagination and a status column, against a datalist and three buttons.
The only thing the picker does that the table cannot is `Random`.

**Against, and it is the real objection.** The two surfaces differ in
*when*, not in *what*. Previews is *check before you launch*;
Invitations is *watch what is happening*. Pre-launch nobody reaches
for a tab called Invitations, and Item 6 does not change that — it
only makes the destination reachable. Either that is accepted and the
Workflow card's stepper carries people there, or something is renamed.

### The three candidate fates

1. **Retire the tab.** Everything moves; Operations goes from six tabs
   to five. Author's stated lean, 2026-09-17, and the one this stub
   is named for.
2. **Keep the email previews**, lose only the surface link. Smallest
   change, least payoff — and it leaves the per-reviewer content split
   across two pages, which is the defect.
3. **Keep it as a fast "pick anyone" shortcut** that redirects into the
   per-reviewer page. Preserves the pre-launch front door and `Random`,
   at the cost of a page whose only content is a picker.

### What Item 6 leaves for it

**Two couplings, not one.**

1. **The preview surface resolves its reviewer through the hub's own
   view builder.** `_resolve_preview_reviewer`
   (`app/web/routes_operator/_preview_surface.py:67`) calls
   `views.build_preview_picker_context`, whose docstring is *"Hydrate
   the Previews-page reviewer picker."* Retiring the page leaves that
   builder orphaned and still load-bearing for a route that survives.
   **This is the larger coupling** and the one that decides how much
   work a retirement actually is.
2. **A 303 back to the hub**, in `preview_surface` itself
   (`_preview_surface.py:121-130` — *not* in the resolver, which only
   returns `None`). It fires on an unresolved `?reviewer_email=` and
   on a session with zero reviewers.

**Item 6 adds neither.** Its link points straight at
`/preview-surface`, never through `/previews`, and always passes a
resolvable email — precisely so this item stays open.

Prose couplings are a third, smaller class: the module and helper
docstrings in `_preview_surface.py`, and the hub references in
`spec/preview_hub.md`, `spec/reviewer-surface.md`,
`spec/operator_ui_concept.md` and `spec/role_navigator.md`. Counted
when this item is planned, not before.

### Open questions

1. **Which fate**, per above. Author's, after Item 6 is on the dev slot.
2. **Does Responses get the symmetric treatment?** Its detail page is
   already reviewee-keyed, so it needs no re-key, and a reviewee has
   no surface of their own — so the symmetry may be nominal. Answer
   after 1.
3. **Naming.** If the tab retires, does *"Invitations"* still describe
   a page you use before any invitation exists? Only live under fate 1.
