# UX refinements

**Opened:** 2026-10-09 · **Theme:** look-and-feel refinements across the
app, one item each, closing independently · **Related:**
`spec/ui_elements.md`, `spec/instruments.md`

A standalone plan at the author's naming, not a `segment_*.md`, in the
shape of `guide/operator_pages_enhancements.md`: items are added as they
come up and each closes on its own. `tools/close_check.py` reads only
`segment_*` files, so an item's `Doc impact` is checked by hand at its
close.

New items go at the end, numbered on, in the item shape of
`guide/segment_plan_template.md`, each with its own `### Doc impact` and
`### Status`.

**Build order** (author, 2026-10-10): Item 3, then Item 2, then Item 1.
Item 1's PR 1 needs Item 2's fixed chip; Item 3 depends on neither, and
landing it first gets its edits to the Instruments template in before
the larger chip changes.

---

## Item 1 — Band 3 fields as chips

### Opportunity

The Instruments page's Band 3 starts every row on both sides with an
Active checkbox. On the left it sits beside a display-only pill with the
field's label, so a Display fields row is an on/off chip
(`spec/ui_elements.md` §9 type 1) split into two controls. Turning only
the left side into chips would leave the two columns looking different,
and the author ruled that the two sets should match (2026-10-09).

### Decision

Both sides become type 1 chips that wrap the existing checkbox:

- **Display fields:** the label pill becomes the chip and the checkbox
  column goes. ~~Name and Email keep the locked chip treatment.~~ Name
  and Email are fixed-on chips (Item 2, revised 2026-10-09).
- **Response fields:** the Active checkbox becomes a chip labeled with
  the field's name, mirrored live from the name box, left-aligned in its
  cell and capped at about the width of a "Comments  " chip. A longer
  name ends in "…" and shows in full on hover.

**Rejected** (each mocked up in a browser on 2026-10-09):

- a "Field 1, Field 2…" position chip, which renumbers on every move and
  clashes with the "Field N" default name;
- a fixed "Active" chip, "just a glorified checkbox" (the author);
- chips on the left only, which leaves the two columns unmatched.

### Semantics

- **The checkbox stays in the DOM**, visually hidden inside a
  `label.tag-chip`, the primitive Session Home's optional-tab chips use.
  Every script that reads or writes `.checked` is unchanged, including
  the branch Active cascade and the confirm before hiding a field that
  has responses.
- **An empty name box** labels its chip with the row's placeholder
  label, the same default the name box shows muted.
- **A locked card** stays inert as today; its chips show state and
  don't respond to clicks.
- **Fields a group row can't show** keep their disabled checkbox, and
  so show as fixed-off chips (Item 2).
- **A disabled checkbox shows on its chip whenever it is disabled**,
  including after load: `newModelRfRecomputeActionStates` disables a
  governed field's Active when its parent is unticked, and re-enables it
  after. The chip reads that from the input with a CSS rule on
  `label.tag-chip:has(> input:disabled)` (no edge, no pointer, and
  Item 2's lock glyph: the fixed-off look), so no script has to keep a
  class in step (Codex on #2930).

### Judgment calls — decided

- The cap is measured from the font, about 95px at the default size,
  rather than a fixed character count. (2026-10-09)
- The Min/Max/default boxes get a minimum width so the narrower name
  column doesn't clip them; the mockup clipped "2000" to "200".
  (2026-10-09)
- **Room for the chip comes from the rest of the row** (author,
  2026-10-10):
  - the type dropdown is capped at about the width of "Agreement  "
    (measured from the font, like the chip cap); its open list keeps its
    natural width;
  - the Min/Max/default boxes are shaved slightly, still wide enough to
    show "2000" unclipped;
  - +, ⑂ and ↰ / ↳ take the width of R, ≡, ▲, ▼ and X, which set the
    standard: `--rf-glyph-width` (2.25rem today, also the width of each
    empty `td.rf-slot`) becomes that button width.

### Blast radius (measured)

Taken 2026-10-09 at `2569876a`.

| What | Count | Command |
|---|---|---|
| Lines naming the display-field checkbox | 3 app; 1 test file, 1 spec | `grep -rn "data-new-model-df-active" app \| wc -l`; `grep -rl … tests spec` |
| Lines naming the response-field checkbox | 9 app; 6 test files | `grep -rn "data-new-model-rf-active" app \| wc -l`; `grep -rl … tests` |
| Rules and specs naming `rf-active-cell` | 1 CSS rule; 1 test file; 2 specs | `grep -rln "rf-active-cell" app tests spec` |

### PR ladder

1. **Display fields chips.** The label pill wraps the checkbox and the
   checkbox column goes. ~~Name and Email take `is-locked`; group-hidden
   fields take `is-disabled`.~~ Name and Email take Item 2's fixed-on
   chip, and the `:has(> input:disabled)` rule gives group-hidden fields
   the fixed-off look, glyph included (revised for Item 2; this rung
   follows Item 2). A browser test toggles a field through its
   chip and checks the fill. `spec/instruments.md` (Display fields row
   list) updated.
2. **Response fields name chips.** The Active checkbox becomes a name
   chip, mirrored live, left-aligned and capped, with the bounds boxes'
   minimum width. The row makes room per the 2026-10-10 judgment call:
   type dropdown capped, bounds boxes shaved, glyph buttons at the R
   button's width. A browser test renames a field and checks the chip
   follows, and toggles a field with responses to confirm the confirm
   still fires, and unticks a parent to check its governed fields'
   chips take the fixed-off look (no edge or pointer, lock glyph) and
   come back when it is ticked again. `spec/instruments.md` (Response fields table) and
   `spec/ui_elements.md` (`rf-table`, `rf-active-cell`) updated. The
   item's cumulative `diff-reviewer` read runs here, from the main SHA
   before PR 1.

### Definition of done

- Both Band 3 columns start each row with a type 1 chip; no Band 3
  Active checkbox is visible.
- A test pins each side's toggle-through-chip, and the name chip's live
  mirror.
- `guide/things_to_check_in_browser.md` has a section per PR.
- `### Doc impact` current, every bullet checked by hand.
- `spec-writer` run against the doc-impact specs; flags adjudicated.
- `### Status` compacted.

### Open questions

- ~~Should Name and Email show the plain "on" fill rather than the
  muted locked one?~~ Neither: they take Item 2's fixed-switch chip
  (author, 2026-10-09), so PR 1 follows Item 2.

### Out of scope

- What the response row's other controls (+, ⑂, ↰ / ↳, R, ≡, ▲ ▼, X)
  do. Only their widths change, per the 2026-10-10 judgment call.
- Redesigning the response row so the name box moves out of it.

### Doc impact

- `spec/instruments.md` — Display fields rows are on/off chips (PR 1); the Response fields Active checkbox is a name chip (PR 2).
- `spec/ui_elements.md` — `rf-table` / `rf-active-cell` describe the name chip, its cap, the type dropdown's cap, the bounds boxes' widths and the glyph-button width (PR 2).
- `guide/things_to_check_in_browser.md` — a section per PR.

---

## Item 2 — A fixed-switch chip

### Opportunity

A survey on 2026-10-09 found per-item controls held at a value while
the controls beside them stay live, shown three ways:

- Session Home's Relationships / Observers chips, once the tab holds
  data: `.tag-chip.is-locked`, a muted display-value fill;
- Band 3's Name and Email: ticked checkboxes, greyed out;
- the Visibility card's "You (reviewer)" × ongoing ("Raw responses")
  and "Reviewees" × ongoing ("—"): plain pills titled "Fixed", beside
  cycle chips.

`spec/ui_elements.md` §9's chip-types table has no row for a switch
that can't be changed, so each surface invented its own look.

### Decision

A fourth chip type, **Fixed**: a switch held at its value. It keeps the
full dark fill of its sibling chips (`--selected-bg` / `--selected-fg`),
drops the edge and the pointer, and carries a small lock glyph before
the label (`.tag-chip.is-fixed`). A switch fixed **off** is the off chip
with the same glyph; on Band 3 it is the chip whose checkbox is
disabled, so Item 1's `label.tag-chip:has(> input:disabled)` rule
carries the glyph rather than a class. The author's pick of four mocked-up
variants, 2026-10-09: lock glyph (chosen), hatched fill, dashed inner
ring, toned-down dark.

**Rejected:** the muted locked fill for a fixed "on". It reads as a
display, not a switch (the author). `.tag-chip.is-locked` stays for a
whole card's locked view.

Not in scope: Band 1's "Not set" link chips (`is-disabled`, struck
through) mean "unavailable", not "fixed", and keep their look.

### Semantics

- **Fixed is per item.** A card's lock still uses `is-locked`; a fixed
  chip on a locked card looks like any other locked chip.
- **The value still submits** where it does today: Session Home's
  hidden checkbox stays checked, the Visibility cells' hidden inputs
  keep their fixed values.
- **The tooltip says why** (today's titles: "The session has
  relationships, so the tab stays on.", "Fixed").
- **Contrast:** the glyph is `currentColor` on the audited
  `--selected-bg` / `--selected-fg` pair.

### Judgment calls — decided

- The glyph is a CSS mask in `currentColor`, not an emoji, so it
  follows the theme and the font. (2026-10-09)

### Blast radius (measured)

Taken 2026-10-09 at `2e0379b8`.

| What | Count | Command |
|---|---|---|
| Session Home chips taking `is-locked` | 4 (2 card-locked, 2 tab-holds-data) | `grep -n "tag-chip is-locked\|tag-chip{% if" app/web/templates/operator/session_detail.html` |
| `.tag-chip.is-locked` rules in `base.html` | 4 | `grep -n "tag-chip.is-locked" app/web/templates/base.html` |
| `b3_static_pill` / "Fixed" lines on Instruments | 5 | `grep -n "b3_static_pill\|title=\"Fixed\"" app/web/templates/operator/instruments_index.html` |
| Specs naming `is-locked` | 2 | `grep -rln "is-locked" spec` |

### Status

- **Built 2026-10-10** as one PR. `base.html` gains
  `.tag-chip.is-fixed` (the `--selected-bg` fill, no edge or pointer, a
  `::before` lock glyph masked in `currentColor`), allowlisted in
  `test_reserved_shade`. Session Home's tab-holds-data chips and the
  Visibility card's two `b3_static_pill` cells take it; the card-locked
  display chips stay `is-locked`. `test_band3_static_pills` now treats
  `is-fixed` as the one `tag-chip` that offers no click. A browser test
  compares each surface's fill with a live chip's and checks the glyph;
  both fail without the change.
- **Fixed off is half here:** the cold read found the fill ignored the
  box's state, so a `<label>` chip takes it only while ticked and an
  unticked one stays the off chip with the glyph. Band 3's disabled
  checkboxes (`:has(> input:disabled)`) still land with Item 1.
- **Reads:** one `spec-writer` verify and two `diff-reviewer` reads.
  The first two found specs and comments still saying the reserved shade
  never reaches an inert element; `spec/color_tokens.md` now records
  `is-fixed` as the one ruled exception (a Doc impact bullet the plan
  missed). The first cold read led to the Observers chip test and a
  `test_chip_edge` pin; the second, on those fixes, found the CSS split
  sound and three stale spec and plan lines.

### PR ladder

1. **The fixed chip, everywhere it applies — one PR** (revised
   2026-10-10, author: the split only kept slices small, and nothing
   depended on it).
   - `.tag-chip.is-fixed` in `base.html` (fill, glyph, no edge or
     pointer), allowlisted in `test_reserved_shade`,
     `tools/theme_customizer.html` regenerated. §9 gains the Fixed row.
   - Session Home's tab-holds-data chips move from `is-locked` to
     `is-fixed`.
   - The Visibility card's fixed cells: `b3_static_pill` renders a
     fixed chip; `test_band3_static_pills` updated.
   - A browser test compares the fill with a selected chip's and checks
     the glyph. The item's `diff-reviewer` read runs on this PR.
2. ~~**The Visibility card's fixed cells.**~~ Merged into rung 1.

Band 3's Name and Email take the fixed chip in Item 1's PR 1, after
this item.

### Definition of done

- §9 defines four chip types, Fixed among them, with a standard.
- Session Home's tab-holds-data chips and the two Visibility cells
  render as fixed chips; a test pins each.
- `guide/things_to_check_in_browser.md` has a section per PR.
- `### Doc impact` current, every bullet checked by hand.
- `spec-writer` run against the doc-impact specs; flags adjudicated.
- `### Status` compacted.

### Open questions

- ~~How does a fixed **off** look?~~ The off chip plus the lock glyph
  (author, 2026-10-09). It covers Band 3's group-hidden display fields
  (Item 1 PR 1) and a response field under a hidden parent (Item 1
  PR 2).

### Out of scope

- Band 1's "Not set" chips (above).
- Fixed values on buttons, selects and inputs (R, ⑂, a field's type,
  locked conditions, the Danger zone's paired checkbox, closed cells on
  the reviewer surface): not chips.

### Doc impact

- `spec/ui_elements.md` — §9's chip-types table gains Fixed; `is-locked` is the locked card's chip only.
- `spec/session_home.md` — the optional-tab chips are fixed once the tab holds data.
- `spec/instruments.md` — the Visibility editor's two fixed cells are fixed chips.
- `spec/color_tokens.md` — "Deliberate couplings" records `is-fixed` as the reserved shade's one inert exception (found at build).
- `guide/things_to_check_in_browser.md` — a section per PR.


---

## Item 3 — ↰ only joins a branch

### Opportunity

The author's intended behavior for Band 3's branch buttons (2026-10-10):

- **⑂** adds a branch below this field: the condition row and one
  field it governs.
- **↰** joins the branch above; with no branch above, it is off.
- **↳** detaches the field from its branch, ending the branch if it
  was the only field.

Checked against the code on 2026-10-10 at `4d993658`. ⑂ and ↳ match,
and a level-1 row's ↰ (`newModelRfNest`) already only joins ("It never
starts one (⑂ does)"). **A level-0 row's ↰ does more:** when the unit
directly above is a plain Integer, Decimal or List field,
`newModelRfJoin` makes that field a parent, adds an empty condition row
and moves this row under it ("Start a branch on the field above with
this field"). That is a second way to fork, overlapping ⑂.
`spec/instruments.md` ("Join (↰) and detach (↳)") documents it.

### Decision

↰ only joins. A level-0 row's ↰ is live only when a branch ends
directly above it, and it joins the deepest unlocked one at its level,
as today. With no branch above it is off, titled "No branch ends
directly above", in the wording of the level-1 ↰. ⑂ stays the only way
to start a branch.

**Rejected:** keeping ↰'s fork on a plain field above. It duplicates
⑂, and it forks the field *above* rather than the one whose button was
pressed.

### Semantics

- **The other off states stay**: the first field, a parent, a field
  with saved responses, an unnamed field, and a locked branch above.
- **The String-above title goes.** "The field above is String, so it
  can't have a branch" and "Name the field above first." only explained
  the fork path. A String field above has no branch, so it gets the
  new title.
- **Saved instruments are unaffected.** This is a builder control; no
  branch shape that was reachable before becomes unreachable, since ⑂
  then ↰ builds the same thing.

### Judgment calls — decided

- None yet.

### Blast radius (measured)

Taken 2026-10-10 at `4d993658`.

| What | Count | Command |
|---|---|---|
| Functions to change | 2 (`newModelRfSyncJoin`, `newModelRfJoin`) | `grep -n "newModelRfSyncJoin = \|newModelRfJoin = " app/web/templates/operator/instruments_index.html` |
| Tests pinning the fork path | 1 file (titles + `parent.setAttribute` assertion) | `grep -rln "Start a branch on the field above\|Joining a plain field" tests` |
| Browser tests driving ↰ | 1 file; it joins an existing branch, so it is unaffected | `grep -rln "data-new-model-rf-join" tests/browser` |
| Spec paragraphs | 1 | `grep -n "a new branch with an empty condition" spec/instruments.md` |

### Status

- **Built 2026-10-10** in one PR, as planned. `newModelRfSyncJoin`'s
  plain-unit-above branch becomes "No branch ends directly above", off;
  `newModelRfJoin` returns unless a branch ends above. The new-row
  template's ↰ title reads "Join the branch above". A browser test finds
  ↰ off under a plain Integer field, then on after ⑂, and joining; it
  fails without the change.
- **Found at build:** the blast radius missed a second test pinning the
  old path (`test_builder_adjustments_12a` counts `newModelRfSyncJoin`'s
  `set()` calls, 13 → 11) and a second spec (`spec/operator_button_audit.md`
  #245), both fixed; `spec/instruments.md` also gains ↰'s name condition.
- **Reads:** one `diff-reviewer` read (no behavior defects; stale
  comments, a redundant local, this record and a live guide line fixed)
  and a `spec-writer` verify pass (the two misses above).

### PR ladder

1. **↰ only joins.** `newModelRfSyncJoin` drops the plain-field-above
   branch and turns ↰ off with "No branch ends directly above";
   `newModelRfJoin` drops the new-branch block. The integration test's
   titles and fork assertion change to match; a browser test presses ↰
   below a plain Integer field and finds it disabled, then forks with ⑂
   and joins. `spec/instruments.md` updated. One code slice outside a
   ladder, so it takes its own `diff-reviewer` read.

### Definition of done

- A level-0 ↰ under a plain field is disabled with "No branch ends
  directly above"; under a branch it joins as before. A test pins each.
- `spec/instruments.md` no longer says ↰ starts a branch.
- `guide/things_to_check_in_browser.md` has a section for the PR.
- `### Doc impact` current, every bullet checked by hand.
- `spec-writer` run against the doc-impact specs; flags adjudicated.
- `### Status` compacted.

### Open questions

- None.

### Out of scope

- ⑂ and ↳, which match the intended behavior.
- Which branch ↰ joins when several end above it (the deepest, an
  earlier ruling, 19T Item 14).

### Doc impact

- `spec/instruments.md` — "Join (↰) and detach (↳)": ↰ joins a branch that ends directly above, and is off otherwise; ⑂ is the only way to start one.
- `spec/operator_button_audit.md` — row #245: ↰ joins the branch above and never starts one (found at build).
- `guide/things_to_check_in_browser.md` — a section for the PR.
