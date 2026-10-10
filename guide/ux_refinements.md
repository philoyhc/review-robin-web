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

**Items 1–9 closed 2026-10-10.** The close's `spec-writer` pass found
the doc-impact specs current apart from five control words still naming
a checkbox or toggle and four ruling attributions in contract prose,
all fixed in the close.

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
    *Found at build (2026-10-10): the five weren't one width (R ≡ X
    ~31px, ▲ ▼ 36px), so all eight take 2rem, R and X's own.*
- **The name chip is the row's first column at every level** (author,
  2026-10-10). The Active checkbox moves one column right per branch
  level, into columns the glyph buttons share, so a chip there would
  widen every button column. The chip column stays put like the name
  box; the per-level indent moves to the buttons after it, and a branch
  bar runs down from the parent's + column. Rejected: the chip shifting
  per level (wide button gaps), and a chip column just before the name
  box (the same name twice, side by side).

### Blast radius (measured)

Taken 2026-10-09 at `2569876a`.

| What | Count | Command |
|---|---|---|
| Lines naming the display-field checkbox | 3 app; 1 test file, 1 spec | `grep -rn "data-new-model-df-active" app \| wc -l`; `grep -rl … tests spec` |
| Lines naming the response-field checkbox | 9 app; 6 test files | `grep -rn "data-new-model-rf-active" app \| wc -l`; `grep -rl … tests` |
| Rules and specs naming `rf-active-cell` | 1 CSS rule; 1 test file; 2 specs | `grep -rln "rf-active-cell" app tests spec` |

### Status — closed 2026-10-10

Shipped in two PRs as laddered (#2936, #2937).

- **PR 1:** each display field is a `label.tag-chip` around its hidden
  checkbox; the checkbox column is gone. Name and Email are fixed,
  read off the disabled box (`label.tag-chip:has(> input:disabled)`), so
  the same rule covers a field a group row can't show.
- **PR 2:** each response row starts with its name chip around the
  hidden Active box, relabeled from the typed name; bars start under the
  parent's +; every row button is `--rf-glyph-width` (2rem), the type
  column `8.5rem`, the bounds floor `3.5rem`, the chip capped at 8em.
- **Added at build (author, 2026-10-10, on Codex's #2936 finding):** a
  locked card's Band 3 chips read as plain display pills, keyed on
  `data-instrument-locked`.
- **Reads:** two `spec-writer` verifies and one cumulative
  `diff-reviewer` read; it found a pending row keeping a stale chip
  label (fixed, with a test) and prose and test gaps, all fixed. Codex
  found the locked-card look above.
- **Browser checks passed** (the author, 2026-10-10).

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
- `spec/operator_button_audit.md` — §9c: each Band 3 row carries its field's chip (PR 1, PR 2; found at build).
- `spec/rrw_functional_spec.md` — the Band 3 bullet names the name chip (PR 2; found at build).
- `spec/reviewer-surface.md` — the dropped-fields notice names the row's name chip (PR 2; found at build).
- `app/web/templates/guide.html` — the Guide's Band 3 sentence says to click a field's chip; its screencaps are the author's to retake (PR 2; found at build).
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

### Status — closed 2026-10-10

Shipped in one PR. `.tag-chip.is-fixed` (the `--selected-bg` fill, no
edge or pointer, a masked lock glyph) on Session Home's tab-holds-data
chips and the Visibility card's two fixed cells; a `<label>` chip takes
the fill only while its box is ticked, so fixed off stays the off chip
with the glyph. **Reads:** one `spec-writer` verify, two `diff-reviewer`
reads; `spec/color_tokens.md` was found missing from Doc impact and now
records `is-fixed` as the reserved shade's one inert exception.
**Browser checks passed** (the author, 2026-10-10).

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

- §9 defines four chip types, Fixed among them, with a standard (five
  since Item 7).
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

## Item 3 — ~~↰ only joins a branch~~ (reversed, 2026-10-10)

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

### Status — closed 2026-10-10 (reversed)

Shipped as planned in one PR (↰ off under a plain field; the blast
radius missed `test_builder_adjustments_12a` and
`spec/operator_button_audit.md` #245, both fixed), then **reversed the
same day** by the author: ⑂ adds a field row and ↰'s fork doesn't, which
the Decision's "duplicates ⑂" missed. The restore put the fork back on
Item 1's layout, keeping ↰'s name condition, and rode in #2941 with
Item 5. **Reads:** two `diff-reviewer` reads and two `spec-writer`
verifies, one of each on the first PR and on the restore. The restore's
found lines Item 3 had changed that it hadn't put back (the
`guide/README.md` row, `guide/todo_master.md`, the post-Azure
checklist's Item 10, a template comment, Item 3's Doc impact and
Definition of done), the String-or-unnamed off states missing from the
specs, and a title and a bar class no test pinned; all fixed in the
restore. **Browser checks passed** (the author, 2026-10-10).

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
- `spec/instruments.md` no longer says ↰ starts a branch. *(Reversed
  2026-10-10: it says so again.)*
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

- `spec/instruments.md` — "Join (↰) and detach (↳)": ↰ joins a branch that ends directly above, and is off otherwise; ⑂ is the only way to start one. *(Reversed 2026-10-10: ↰ starts one on a plain number or List field again.)*
- `spec/operator_button_audit.md` — row #245: ↰ joins the branch above and never starts one (found at build). *(Reversed 2026-10-10.)*
- `guide/things_to_check_in_browser.md` — a section for the PR.

---

## Item 4 — The Guide's Instruments section catches up

### Opportunity

Items 1–3 changed what Band 3 looks like and what ↰ does, and the
Guide's Instruments section (`/guide`, `app/web/templates/guide.html`)
still showed checkboxes and described the pre-chip card. The author
revised the section and retook its screencaps (`Guide_v5a.docx`,
2026-10-10) once the behaviors settled.

### Decision

Take the author's revision as written, with three factual fixes the
check found (author may veto on the PR): the Visibility cells that can't
change "carry a lock" (Item 2), not "are plain labels"; ↰'s branch-start
condition spelled out, and ⑂'s new field named; one run-on sentence
(the bounds one) split. Alt text rewritten for the four new figure pairs.
**Rejected:** rescaling the wider captures here (no image tool in the
container); the author can retake them at the usual width.

### Semantics

- The collapsed-bar figure is unchanged; the other four pairs are
  replaced under the same filenames, so no reference moves.

### Judgment calls — decided

- None.

### Blast radius (measured)

Taken 2026-10-10 at `b2065e3c`: one template section
(`grep -n "Build the form (Instruments)" app/web/templates/guide.html`),
eight PNGs in `app/web/static/guide/`, no spec quotes the Guide text
(`grep -rln "plain labels" spec docs` finds none).

### Status — closed 2026-10-10

Shipped in two PRs: the section (#2940), then the fields and branching
captures retaken at the usual ~1755px width (#2942). The author accepted
the three wording fixes plus a fourth from the cold read (Name and Email
"aren't optional"); the branching pair keeps Rating at 1–5 as a separate
example. **Reads:** three `diff-reviewer` reads, finding the Email
claim, a chip line in the alt text and the capture scale, all fixed.
**Browser checks passed** (the author, 2026-10-10).

### PR ladder

1. **The section and its captures.** `guide.html`'s Instruments section,
   the eight PNGs, and the browser check.
2. **The retake** (added at build). The fields and branching pairs at
   the usual width.

### Definition of done

- The Guide's Instruments section matches the app after Items 1–3.
- `guide/things_to_check_in_browser.md` has a section for the PR.
- `### Status` compacted.

### Open questions

- ~~Retake the wider pairs or rule a third scale?~~ Retaken at ~1755px
  (author, 2026-10-10).

### Out of scope

- The rest of the Guide.

### Doc impact

- `guide/things_to_check_in_browser.md` — a section for the PR.

---

## Item 5 — A level-1 row's ↰ starts a branch too

### Opportunity

The author, 2026-10-10, on a screencap: Comments, a level-1 field under
Rating in Familiarity's branch, can't use ↰ to start a branch on Rating.
A level-0 row's ↰ can do this on the field above it (Item 3's reversal),
but a level-1 row's ↰ (`newModelRfNest`) only joins a branch that
already ends above it ("It never starts one (⑂ does)"). So the second
way to fork, which adds no new field row, stops at level 0.

### Decision

A level-1 row's ↰ works as a level-0 row's does, one level down: when
the field directly above it in its branch has a branch, it joins it at
level 2; when that field is a named plain Integer, Decimal or List field,
it starts a branch on it, with an empty condition and this row as its
only field. **Rejected:** leaving level 1 join-only, which keeps ⑂'s
extra row as the only way to branch there.

### Semantics

- **Off states**, titled as at level 0: the branch's first field ("The
  first field in a branch can't join a branch"), a String field above,
  an unnamed field above, and, as today, a parent, an unnamed row, and
  a locked branch. An answered field above locks the shared branch, so
  it is covered by the last.
- **Depth:** the new branch is at level 2, the limit; a level-2 row has
  no ↰.
- **Saved instruments are unaffected:** ⑂ on the field above, then ↰,
  already built the same shape.

### Judgment calls — decided

- The server render carries `nest_target` as `"join"` / `"start"` /
  None plus `nest_first`, so the first paint matches the script.

### Blast radius (measured)

Taken 2026-10-10 at `c738dbaa`.

| What | Count | Command |
|---|---|---|
| Script functions | 2 (`newModelRfSyncNest`, `newModelRfNest`) | `grep -n "newModelRfSyncNest = \|newModelRfNest = " app/web/templates/operator/instruments_index.html` |
| View flag | 1 (`nest_target`, `app/web/views/_instruments.py`) | `grep -rn "nest_target" app --include=*.py --include=*.html` |
| Tests pinning the join-only title | 1 file | `grep -rln "No branch inside this branch ends directly above" tests` |
| Spec paragraphs | 2 (`spec/instruments.md`, `spec/operator_button_audit.md` #245) | `grep -rn "No branch inside this branch\|joins the branch inside its own" spec` |

### Status — closed 2026-10-10

Shipped in one PR (#2941). **Found at build:** a level-1 row's ↰ didn't
follow edits to the field above it; the row script now resyncs the next
field in the branch, and the browser test fails without it. One
`diff-reviewer` read and one `spec-writer` verify, neither finding a
defect. **Browser checks passed** (the author, 2026-10-10).

### PR ladder

1. **↰ starts a branch at level 1.** `newModelRfSyncNest` and
   `newModelRfNest`, the view's `nest_target`, the template's title; an
   integration test for each title and a browser test that starts,
   saves, detaches and refuses under a String. `spec/instruments.md` and
   `spec/operator_button_audit.md` #245. One code slice outside a
   ladder, so it takes its own `diff-reviewer` read.

### Definition of done

- A level-1 ↰ under a plain number or List field starts a branch on it
  and saves at level 2; under a String it is off with its reason. A test
  pins each.
- `guide/things_to_check_in_browser.md` has a section for the PR.
- `### Doc impact` current, every bullet checked by hand.
- `spec-writer` run against the doc-impact specs; flags adjudicated.
- `### Status` compacted.

### Open questions

- None.

### Out of scope

- A third level, which stays refused.

### Doc impact

- `spec/instruments.md` — "Join (↰) and detach (↳)": a level-1 row's ↰ starts a branch on a plain number or List field above it in its branch, as a level-0 row's does.
- `spec/operator_button_audit.md` — row #245: the level-1 ↰'s start path and off states.
- `guide/things_to_check_in_browser.md` — a section for the PR.

---

## Item 6 — The dead Response Fields Help table goes

### Opportunity

A sweep for checkboxes that switch something on or off (2026-10-10)
found `instruments_index.html`'s `response_fields_help_table` macro, a
"Response Fields Help" table with a Show checkbox per field. Nothing
calls it; the builder's ≡ button replaced it. Its row scripts
(`addRow`, `deleteRow`, `_showOrHideEmptyState`) have no caller either.

### Decision

Delete the macro and the three scripts (the author, 2026-10-10).
**Rejected:** also deleting the block's other uncalled scripts
(`moveRow`, `_refreshOrderColumn`, `syncGroupByInclude`), which the
ruling didn't name; they are recorded under Out of scope.

### Semantics

- No behavior changes: nothing rendered the macro. The live ≡ button
  saves `help_text_visible` in each row of the Band 2 payload
  (`app/services/instruments/_band2.py`); `help_text_visible_ids`, the
  dead checkbox's name, is read by nothing.

### Judgment calls — decided

- None.

### Blast radius (measured)

Taken 2026-10-10 at `c8343bf3`.

| What | Count | Command |
|---|---|---|
| Callers of the macro | 0 | `grep -rn "response_fields_help_table" app` |
| Callers of the three scripts | 0 outside each other | `grep -n "addRow(\|deleteRow(\|_showOrHideEmptyState(" app/web/templates/operator/instruments_index.html` |
| Live spec mentions | 0 (`spec/archive/` only) | `grep -rln "Response Fields Help" spec docs` |

### Status — closed 2026-10-10

Shipped in one PR (#2943): 160 lines deleted, no test changes. One
`diff-reviewer` read; its one finding (the Semantics line misnamed what
≡ posts) was fixed.

### PR ladder

1. **Delete it.** One code slice outside a ladder, so it takes its own
   `diff-reviewer` read.

### Definition of done

- `grep -rn "rfhelp" app` finds nothing; the suite passes unchanged.
- `### Status` compacted.

### Open questions

- None.

### Out of scope

- `moveRow`, `_refreshOrderColumn` and `syncGroupByInclude` in the same
  script block, also uncalled; a later cleanup if wanted.

### Doc impact

- None: no live spec or doc names the table.

---

## Item 7 — The Assignments status table's checkboxes become chips

### Opportunity

The 2026-10-10 checkbox sweep: the Assignments page's Per-instrument
status table still has two checkboxes of the kind Band 3 dropped. A
**Show** column's checkbox filters the preview table, and the **Self
review** cell's checkbox (beside a count pill) bulk-flips the
instrument's self-review rows, with a third, indeterminate state when
some are in and some out.

### Decision

The author's ruling (2026-10-10):

- **The instrument's name is the filter**, an on/off chip; the Show
  column goes.
- **Self review is an on/off chip, "Include N self reviews"**, N the
  included rows, replacing the count pill: dark when all are in, light
  when none, amber when some.
- **Type is a display pill.**

**Rejected:** "Show N pairs" for the Self review chip, the first
wording: the box doesn't filter anything, it changes who reviews whom,
so "Show" would read as the filter beside it.

### Semantics

- **Mixed:** the box is unticked, so a click includes them all, as the
  checkbox's did. A dark chip's click excludes them all.
- **No counted rows** (no overlaps, or every self-review row has an
  inactive side): "—", no chip. "Excluded by rule" is unchanged.
- **Locked session:** the box is disabled, so the chip reads fixed
  (`label.tag-chip:has(> input:disabled)`), amber if mixed.

### Judgment calls — decided

- "review" for N = 1. The partial state is a fifth row in
  `spec/ui_elements.md` §9's chip table, not a new class: `pill-empty`
  already gives a `tag-chip` its amber.

### Blast radius (measured)

Taken 2026-10-10 at `c8343bf3`.

| What | Count | Command |
|---|---|---|
| Template | 1 (`session_assignments.html`) | `grep -rln "data-filter-instrument" app` |
| Tests pinning the old cells | 4 files (3 needed edits) | `grep -rln "data-filter-instrument\|data-self-review-instrument\|data-self-review-count" tests` |
| Specs | 5 | `grep -rln "Self review checkbox\|Show checkbox\|filter checkbox\|self-review toggle" spec` |

### Status — closed 2026-10-10

Shipped in one PR (#2944); no view change was needed. **Reads:** three
`diff-reviewer` reads and one `spec-writer` verify. They found stale
prose (five `spec/assignments.md` passages, `README.md`, docstrings, the
Guide's alt text) and an accessibility gap: the box keeps
`indeterminate` so a screen reader hears "mixed", and its name carries
the chip's text. All fixed in the PR. The Guide's `assignments-page`
pair was retaken by the author (`Guide_v5d`, #2947). **Browser checks
passed** (the author, 2026-10-10).

### PR ladder

1. **The chips.** Template, three tests, a browser test of both
   chips, the specs. One code slice outside a ladder, so it takes its
   own `diff-reviewer` read; `spec-writer` because it touches `spec/`.

### Definition of done

- The status table has no checkbox in sight and no Show column; a test
  pins each chip and the three fills.
- `guide/things_to_check_in_browser.md` has a section for the PR.
- `### Doc impact` current; `spec-writer` flags adjudicated.
- `### Status` compacted.

### Open questions

- ~~The Guide's screencap retake~~ Retaken by the author (`Guide_v5d`, 2026-10-10).

### Out of scope

- The preview table's own row checkboxes (selection for bulk actions).

### Doc impact

- `spec/assignments.md` — "Per-instrument status table": the Instrument, Type and Self review columns; Show removed.
- `spec/ui_elements.md` — §9: the on/off chip with a partial state.
- `spec/operator_ui_concept.md` — the Assignments status card.
- `spec/operator_button_audit.md` — the status table's controls are chips.
- `spec/rrw_functional_spec.md` — the Per-instrument status card.
- `guide/things_to_check_in_browser.md` — a section for the PR.
- `README.md` — the `assignments` route row.
- `app/web/templates/guide.html` — the Assignments figure's alt text (found at build).

---

## Item 8 — The Instruments card's self-review checkbox becomes a chip

### Opportunity

The 2026-10-10 checkbox sweep: under Link 3, a "Self reviews" heading
sits over a checkbox labeled "Exclude if the individual reviewed is the
reviewer" (or the group sentence). It is a two-way choice, each side a
positive one, drawn as a checkbox.

### Decision

The author's ruling (2026-10-10): a cycle chip where the heading was,
**"Include self reviews" / "Exclude self reviews"**, and under it the
line **"A self review is where the individual reviewed is the
reviewer"** (on a group unit, "…where the reviewer is in the group
being reviewed"). The show/hide behavior stays: the divider, chip and
line are hidden while any Link is not set. **Rejected:** an on/off chip
reading "Exclude self reviews", which would make including them look
like the absence of a setting.

### Semantics

- The chip wraps the same hidden `exclude_self_reviews` box, so the save
  path, `resolve_exclude_self_reviews` and the import are unchanged.
- Both scripts that clear the box (any Link back to not set; Link 3
  Individual → Group) also rename the chip, through
  `newModelSyncSelfReviewChip`.

### Judgment calls — decided

- The line takes the old label's two-sentence swap on Link 3, so it
  stays a whole sentence in each mode.
- The box's accessible name is what its tick means, "Exclude self
  reviews", so a screen reader's "not checked" reads true; the cost is
  that while the chip shows "Include self reviews" the name doesn't
  contain the visible text (WCAG 2.5.3). Item 7's chip, whose label
  doesn't flip, keeps its visible text as its name.

### Blast radius (measured)

Taken 2026-10-10 at `c8343bf3`.

| What | Count | Command |
|---|---|---|
| Template | 1 block + 2 script sites | `grep -n "exclude_self_reviews" app/web/templates/operator/instruments_index.html` |
| Tests pinning the heading and labels | 3 | `grep -n "def test_self_review_c" tests/integration/test_instrument_builder_routes.py` |
| Specs | 5 | `grep -rln "Self reviews\*\* checkbox\|Link 3 checkbox\|exclusion checkbox\|Exclude if the" spec` |

### Status — closed 2026-10-10

Shipped in one PR (#2945). **Found at build:** Band 3's locked-card rule
reaches Band 1's lock region and faded "Include self reviews" as if
off; a cycle chip is exempt (`:not(.is-selected)`), pinned by a browser
test. The box's accessible name is what its tick means, with
`autocomplete="off"`. **Reads:** two `diff-reviewer` reads and one
`spec-writer` verify; the second read found only wording. The Guide's
`instrument-card-assignment-rule` pair was retaken by the author
(`Guide_v5d`, #2947). **Browser checks passed** (the author, 2026-10-10).

### PR ladder

1. **The chip.** Template, the three tests, a new browser test, the
   specs. One code slice outside a ladder, so it takes its own
   `diff-reviewer` read; `spec-writer` because it touches `spec/`.

### Definition of done

- The chip renders and cycles; a saved exclusion reopens as "Exclude
  self reviews"; the line follows Link 3. A test pins each.
- `guide/things_to_check_in_browser.md` has a section for the PR.
- `### Doc impact` current; `spec-writer` flags adjudicated.
- `### Status` compacted.

### Open questions

- ~~The Guide's screencap retake~~ Retaken by the author (`Guide_v5d`, 2026-10-10).

### Out of scope

- The Assignments page's self-review chip (Item 7).

### Doc impact

- `spec/instruments.md` — "Self-review exclusion": the chip and its line.
- `spec/ui_elements.md` — §9's cycle standard and §10's `.col-divider` row name the chip.
- `spec/rrw_functional_spec.md` — §8.6 and §9.6 name the chip.
- `spec/assignments.md` — the Link 3 control is a chip.
- `spec/settings_inventory.md` — `exclude_self_reviews` is written by the chip.
- `app/web/templates/base.html` — the locked-card fade spares a cycle chip (found at build).
- `guide/things_to_check_in_browser.md` — a section for the PR.

---

## Item 9 — The Email Template page's send-on-submit checkbox becomes a chip

### Opportunity

The 2026-10-10 checkbox sweep: the Email Template page's Responses received tab
carries a checkbox, "Send this confirmation when a reviewer submits.",
with a help line under it ("Default is on. Uncheck to suppress …").
Both choices are positive ones, drawn as a checkbox.

### Decision

The author's ruling (2026-10-10): remove the checkbox and its help
line; under the "Responses received email" heading, a cycle chip,
**"Send response confirmation" / "Don't send response confirmation"**.
**Rejected:** placing the chip inside the heading, which would fold a
control into the card's title.

### Semantics

- The chip wraps the same `name="enabled"` box (default on), so the
  route, the stored override and the reset-by-re-checking are unchanged.
- The box's `change` already enables the composer's Save.

### Judgment calls — decided

- The box's name is what its tick means ("Send response confirmation")
  with `autocomplete="off"`, as Item 8's chip.

### Blast radius (measured)

Taken 2026-10-10 at `c8343bf3`.

| What | Count | Command |
|---|---|---|
| Template | 1 (`session_setupinvite.html`) | `grep -rln 'name="enabled"' app/web/templates` |
| Tests pinning the checkbox | 1 file, 2 tests | `grep -n "Send this confirmation" tests/integration/test_email_template_editor.py` |
| Specs | 2 | `grep -rln "Send this confirmation" spec` |

### Status — closed 2026-10-10

Shipped in one PR (#2946). **Reads:** two `diff-reviewer` reads and one
`spec-writer` verify; they found the page's name ("Email Template", not
"Emails"), a browser test that didn't wait for the save's reload, and
stale spec lines, all fixed. Codex found an older browser check still
naming the old checkbox, fixed. **Browser checks passed** (the author,
2026-10-10).

### PR ladder

1. **The chip.** Template, the two tests plus one for the off state, a
   browser test, the specs. One code slice outside a ladder, so it
   takes its own `diff-reviewer` read; `spec-writer` because it touches
   `spec/`.

### Definition of done

- The chip renders, cycles and saves; a test pins each state.
- `guide/things_to_check_in_browser.md` has a section for the PR.
- `### Doc impact` current; `spec-writer` flags adjudicated.
- `### Status` compacted.

### Open questions

- None.

### Out of scope

- The Invitation and Reminder tabs, which have no such control.

### Doc impact

- `spec/email_template_editor.md` — the Responses received tab's control is a chip.
- `spec/operator_ui_concept.md` — the Email Template composer paragraph.
- `spec/ui_elements.md` — §9's cycle standard and form-control list name the chip.
- `guide/things_to_check_in_browser.md` — a section for the PR.


---

## Item 10 — The Guide's "Reading the controls" card

### Opportunity

The app's buttons, pills, chips and delete guards each follow one rule
(`spec/ui_elements.md` §6, §9, §4's delete-confirm standard), but
nothing tells an operator those rules exist. A first-time operator
meets five chip types and five button colors with no key to them.

### Decision

A card on `/guide`, under "What Review Robin Web does", that samples
each button role, each chip type and the delete guard on the app's own
classes, in two columns: Buttons and Checkbox guards on the left, Pills
and chips on the right (author, 2026-10-10, from a mockup). **Every chip
sample works**, since a chip's edge says "click me" and a sample that
ignored the click would teach the opposite; button samples are spans,
since a button's look is the lesson and a sample that acted would need
somewhere to go; they take no pointer or hover tint, so they don't
promise a click. *(Reversed by the author on the merged card, rung 3:
the samples take their role's hover, and R is one live Toggle.)* Rejected: screenshots of the controls, which go stale
the moment a role's tokens move, where live classes follow it.

### Semantics

- Rung 1 ships every sample inert; the click behavior below is rung 2's.
- Operators only (author): `GuideSection("controls", OPERATOR)`.
- Nothing posts. The guard's button is `type="button"` on the app-wide
  `data-delete-confirm` pairing; the chips' boxes sit in no form.
- Some of a set: a click on faint or amber turns all on, on solid blue
  all off (as Item 7). Cycle: the box's name is what its tick means
  (as Item 8). Not set: amber, then "All", "Filter using tags" and back
  to "Not set" (as the Band 1 link chips cycle).
- Fixed: a `<label>` around a checked, disabled box, so a click
  changes nothing.

### Blast radius (measured)

Taken 2026-10-10 at `879069ac`.

- `app/web/templates/guide.html`, `app/web/views/_guide.py`
  (`SECTIONS`), `app/web/templates/base.html` (`.guide-controls-*`,
  five planned at the stamp; six built, seven after the cold read), `tools/theme_customizer.html` (regenerated).
- `tests/integration/test_guide_scaffold.py` (`SECTION_HEADINGS`), one
  new browser test (rung 2).
- `grep -rln "guide-controls" spec/` → none; §6 and §9 gain a line.

### Status — in progress

**The ladder split in two** (Codex on #2949, citing `CLAUDE.md`
"scaffold-first"): the mockup was not a landed slice, so #2949 became
the inert scaffold and the chip script, the guard pairing and the
browser test moved to rung 2. Rung 1's reads covered the wired card,
so rung 2 restores what they read. Between the two, rung 1's chip
samples carried the edge but did nothing, a temporary break of §9's
edge-means-clickable rule that rung 2 ends. **Reads (rung 1):** one `spec-writer` verify
(the Not set sample didn't cycle back; the Delete row and locked-card
note overclaimed) and one `diff-reviewer` read ("dark is on" is false
in dark theme, so the copy says solid blue and pale; the Not set
sample's label is the real "Filter using tags"; the guard copy hedged
to "most"; the CSS block split a comment). **Found, left for their own
change:** Operator Settings' "Clear all settings" is destructive with
no checkbox, against §4's delete-confirm standard; and a Band 1 link
chip rendered already set doesn't gain `pill-empty` when cycled back to
"Not set", so it turns faint rather than amber. Both are filed as
stubs in `guide/todo_master.md`. A second read of the fixes found "pale" untrue
in dark theme too (now "faint"); §9's Fill column still says
dark/light, for the close's `spec-writer`. A third read, of
that fix, found only plan and register wording, fixed. A read of the
split found only wording (fixed in #2949). **Reads (rung 2):** one
`diff-reviewer` read, finding a stale "inert" browser check and a
missing theme and keyboard check (fixed), and that the real Band 1
link chips take no Enter or Space, though the sample does (filed as a
stub).

### PR ladder

1. **The scaffold** (#2949). The card with its real copy and layout,
   every sample inert, the CSS, `SECTIONS`, the scaffold test and the
   §6 / §9 lines. ~~The card and its wiring in one PR~~ (split, above).
2. **The wiring** (#2950). The chip script, the guard's `data-delete-confirm`
   pairing, the "try it" copy, `tests/browser/test_guide_controls.py`,
   and §9's "every switchable sample working", with the click checks in
   `guide/things_to_check_in_browser.md`. Takes its own `diff-reviewer`
   read.
3. **The button samples** (#2951; author, 2026-10-10). Hover, one live
   R (the Decision's note), and a tooltip on every sample saying what it
   is and, for a control, what a click does. Takes its own `diff-reviewer` read.

### Definition of done

- The card renders for an operator, after "What Review Robin Web does";
  `test_guide_scaffold.py` lists it.
- `tests/browser/test_guide_controls.py` drives every chip sample and
  the guard (rung 2).
- `guide/things_to_check_in_browser.md` has a section for the PR.
- `### Doc impact` current; `spec-writer` flags adjudicated.
- `### Status` compacted.

### Open questions

- None. Title "Reading the controls", live chips and operators only
  were the author's (2026-10-10).

### Out of scope

- Icon buttons, the in-page view tabs and the lifecycle badges beyond
  one Draft pill.
- A Guide screencap of the card: the card is live markup.

### Doc impact

- `spec/ui_elements.md` — §6 and §9 note that the Guide's "Reading the controls" card samples every role and chip type, so a new one is added there too.
- `guide/things_to_check_in_browser.md` — a section for the PR.

---

## Item 11 — Retire the filled-amber button

### Opportunity

`.btn.danger-solid` (Alert, filled amber) is the loudest button the app
has: on Session Home's Workflow card, **Archive session** outweighs the
red-outline **Delete** it sits near in meaning, though archiving is
recoverable and deleting isn't. The Guide's "Reading the controls" card
(Item 10) shows the inversion side by side.

### Decision

Retire the filled amber (author, 2026-10-10). Its recoverable callers
take the amber outline (`.btn.alert`); **Regenerate & prepare**, which
deletes saved responses, takes Destructive; a **Cancel** beside one of
them takes Secondary, so the proceed button stays the louder of the
pair. Rejected: keeping the fill on the Workflow card only, where the
card hosts a series of main actions; the author chose one fewer role
over that case.

### Semantics

- `.btn.alert` widens from lock-card recovery to *serious but
  recoverable*, lock-card recovery included; it keeps the
  **Outline-amber** name. "Alert" retires with the fill.
- Six roles become five: Primary, Secondary, Destructive, Outline-amber,
  Toggle.
- `--btn-alert-bg`, `-fg`, `-border`, `-bg-hover` retire with the rule;
  the `--btn-amber-*` tokens `.btn.alert` reads are unchanged.

### Judgment calls — decided

- Validate's error-banner **Cancel** (no proceed button beside it) takes
  Secondary too, so the page's two Cancels match (2026-10-10).
- The Guide card's **Archive session** row goes: it was the role's
  sample (2026-10-10).

### Blast radius (measured)

Taken 2026-10-10 at `2af9c113`.

- `grep -rc "danger-solid"` → 6 buttons in 4 operator templates
  (`partials/next_action_card.html` 2, `session_validate.html` 1,
  `session_extract_data.html` 1, `sessions_list.html` 2), plus
  `guide.html` 1 and `base.html` 2 rules.
- Cancels to Secondary: `session_validate.html:35`, `:62`;
  `partials/next_action_card.html:103`.
- `--btn-alert-*`: 14 lines in `base.html`; `spec/color_tokens.md`
  (4 rows and two mentions); `tools/_harness_common.py` (contrast pair,
  two harness buttons); `tools/theme_customizer.gen.py` (2).
- Tests: `test_extract_data_scaffold.py:529` (class assertion),
  `test_cascade_ties.py:67` (class list).
- Specs naming the role: `ui_elements.md` (3), `operator_button_audit.md`
  (6 rows), `workflow_card.md` (2), `extract_data.md` (1),
  `session_home.md:560`, `visual_style_rrw.md:11` ("six"); `CLAUDE.md`
  / `AGENTS.md` list the six roles.

### PR ladder

1. **The swap.** Every call site, the Cancels, the CSS and tokens, the
   regenerated customizer, the harness, the two tests, the Guide row,
   the specs and the twins. No scaffold: no new page, card or
   affordance. One code slice outside a ladder, so it takes its own
   `diff-reviewer` read; `spec-writer` because it touches `spec/`.

### Definition of done

- `grep -rn "danger-solid\|--btn-alert-" app/ tools/*.py tests/ spec/`
  finds nothing outside a retirement note.
- `tests/unit/test_contrast_audit.py` and
  `tests/unit/test_generated_tools_are_current.py` pass.
- `guide/things_to_check_in_browser.md` has a section for the PR.
- `### Doc impact` current; `spec-writer` flags adjudicated.
- `### Status` compacted.

### Open questions

- None. The Cancel and Regenerate rulings were the author's
  (2026-10-10).

### Out of scope

- The two defects filed from Item 10 (`guide/todo_master.md` stubs).
- Restyling `.btn.alert` itself.

### Doc impact

- `spec/ui_elements.md` — §6: five roles; the Alert row goes; Outline-amber reads "serious but recoverable"; the hover list and the delete-confirm note lose `.danger-solid`.
- `spec/operator_button_audit.md` — rows 153, 154, 203, 209, 221 and 69 take their new roles; the two Cancels take Secondary.
- `spec/workflow_card.md` — Archive session and Regenerate & prepare take their new roles.
- `spec/extract_data.md` — the Archive card's button is Outline-amber.
- `spec/session_home.md` — the Closed row's Archive session is Outline-amber.
- `spec/color_tokens.md` — the four `--btn-alert-*` rows retire.
- `spec/visual_style_rrw.md` — "six canonical `.btn` roles" becomes five.
- `CLAUDE.md` — the role list drops Alert [filled amber]; `AGENTS.md` copied.
- `guide/things_to_check_in_browser.md` — a section for the PR.
