# Segment 19Y — More UX refinements

**Opened:** 2026-10-20 · **Theme:** UX refinements larger than a 19X
fix, one item each · **Related:** `guide/segment_19X_refinements.md`,
`spec/reviewer-surface.md`, `spec/instruments.md`

A standing home, like 19X, for refinements that need a plan of their
own: a stored setting, a new control, more than one rung (author,
2026-10-20). Items close independently; the segment closes when the
author says no more are coming.

## Item 1 — An instrument's intro picks its layout

### Opportunity

The author, 2026-10-20, with a screenshot of the instrument preview: the
intro's two columns (19T Item 17) put the heading and the "Who can see
what you wrote" card on the left and the help cards on the right. With
two one-line help cards the right column ends far above the left, and
the page reads lopsided; with long help text the same layout is right.
Which one fits depends on the instrument's help text, so the operator
should choose.

### Decision

The author's rulings, 2026-10-20: a per-instrument setting, switched by
a cycle chip (`spec/ui_elements.md` §9) beside the instrument card's
"Preview review instrument" heading, reading **Layout 1** / **Layout 2**,
so later layouts append to the cycle.

| Layout | Left column | Right column |
|---|---|---|
| **Layout 1** (the default) | heading, help cards | visibility |
| **Layout 2** (today's) | heading, visibility | help cards |

The author swapped the numbering the same day and made the new
arrangement the default, so every instrument, existing ones included,
moves to Layout 1 when PR 2 lands.

The chip repaints the preview at once and the card's Save stores it
(it rides `dfsave-<id>`, as Band 2's chips do). Stored as
`Instrument.intro_layout`, carried by the Settings CSV, Duplicate and
Replicate. Rejected: a session-wide setting (help length varies by
instrument); an automatic choice by help-text length (a threshold
guesses wrong, and the operator cannot see why).

### Semantics

- **Values.** `layout_1` (default; every existing instrument, so the
  migration changes what reviewers see) and `layout_2`, shown as
  "Layout 1" / "Layout 2"; each carries a `title` naming its arrangement. Any other stored or imported value is refused
  on import and reads as `layout_1` if found.
- **Narrow screens** (≤ 800px, one column): every layout stacks
  heading, visibility, help, as today (author, 2026-10-20), so the
  setting changes the wide view only.
- **Missing cards.** ~~No help cards: both layouts render the heading and
  visibility in one column, as today.~~ No help cards: Layout 1 keeps the
  heading left and visibility right; Layout 2 stacks them left (the
  author, 2026-10-20, at the close). No visibility rows: Layout 1's
  right column is empty and leaves the grid as the help column does today.
- **Where it shows.** The reviewer surface and the operator's preview,
  which render the same intro markup.
- **Audit.** No existing event fires for a layout-only Save, so a new
  setter `set_intro_layout` in `app/services/instruments/` writes
  `instrument.intro_layout_updated` (`audit.changes` + `refs`), registered
  in `EVENT_SCHEMAS`, and skips a no-op. It is display-only, like
  `instrument.column_widths_updated`: no lifecycle demotion.
- **Both Saves.** `dfsave-<id>` posts to `/fields/save` without JavaScript
  and the script re-points it at the JSON `/save`; both call the setter.

### Blast radius (measured)

Taken 2026-10-20 at `ea52fa8a`.

| What | Count | Command |
|---|---|---|
| Templates rendering the intro columns | 2 (+ `base.html` CSS) | `grep -rln "rs-intro-col" app/web/templates` |
| Code touches of the closest analog, `self_reviews_active` (models, instrument services, clone, CSV) | 8 files | `grep -rln --include=*.py "self_reviews_active" app/db app/services/instruments app/services/session_clone.py app/services/session_config_io` |
| Specs naming that analog | 5 live | `grep -rln "self_reviews_active" spec --exclude-dir=archive` |
| Instrument card Save routes (no-JS `/fields/save`, JSON `/save`) | 2 | `grep -nE 'instruments/\{instrument_id\}/(fields/)?save"' app/web/routes_operator/_instruments.py` |

### Status

**Closed 2026-10-20** in three PRs as laddered: #3170 (scaffold), #3171
(the setting, with the Settings CSV field moved in from PR 3 per Codex
on the plan), and the close.

- **What moved from the plan.** The scaffold chip shipped as the plain
  pill, not the cycle chip's fill (Codex on #3170: an inert chip
  shouldn't offer a click). One rule, `effective_intro_layout`, makes a
  stray stored value `layout_1` on the surface, the chip *and* the CSV
  export, so its backup still imports. A missing visibility card leaves
  Layout 1's right half empty: the grid keeps both columns, as it does
  today for a missing help column. With no help cards Layout 1 keeps
  the visibility card right rather than falling back to one column (the
  author, at the close, from a screenshot of the preview); the close PR
  carries that CSS change and took its own read. With neither a help
  nor a heading card, the visibility card keeps the left half (judgment
  call: nothing to sit beside).
- **Decisions confirmed at build.** The layout is a display setting: no
  lifecycle demotion, like `column_widths`. Locked, the chip is the
  plain pill, out of the tab order and `aria-disabled`. A Layout 2
  instrument is not the untouched default for the Settings import.
- **Reads.** One `diff-reviewer` read on the cumulative diff from
  `a727b148`: no correctness defect; seven smaller findings, all acted
  on in #3171 (the stray-value rule, tab order, the 800px gap,
  `autocomplete="off"`, browser tests for the no-help, no-heading and
  reviewer-surface branches, two Doc impact bullets).
  `spec-writer` at the close wrote the seven specs; its one flag is the
  missing-visibility-card wording above. A second read, on the close
  slice, caught an invalid `:not()` the no-help edit had left on the
  right-column hide rule (a 12px gap under no-help intros at ≤ 800px),
  an empty-row gap and two stale spec phrases; all fixed, with browser
  tests for the narrow no-help and no-heading-no-help cases.
- **Owed by the author:** the browser-check rows in
  `guide/things_to_check_in_browser.md`, including reshooting the Guide's
  preview screencap and its alt text.

### PR ladder

1. **PR 1 — scaffold.** The chip beside "Preview review instrument",
   inert ("Layout 1", no input). Must not touch storage or the intro.
2. **PR 2 — the setting.** Migration (`instruments.intro_layout`,
   not null, default `layout_1`), model, the chip live with a hidden
   input on `dfsave-<id>`, the setter and its event, both Saves, the
   intro's two arrangements on the reviewer surface and the preview,
   Duplicate, Replicate and the Settings CSV field (serialize, apply,
   refusal), so no landed rung stores a value a backup drops. Browser
   test: cycle, preview, save, reload, narrow order.
3. **PR 3 — specs, close.** `spec/roundtrip_coverage.md`, the specs
   below, browser-check rows; `spec-writer`; close.

### Definition of done

- An instrument at Layout 1 renders heading + help left and visibility
  right, and one saved at Layout 2 renders today's arrangement, on the
  reviewer surface and the preview (tests).
- A layout-only Save writes `instrument.intro_layout_updated` through
  both `/fields/save` and `/save` (tests).
- The setting survives Duplicate, Replicate and a Settings CSV round
  trip (tests).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19Y.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` 19Y entry updated to drop this item; the entry itself goes only when the segment closes

### Open questions

- None.

### Out of scope

- An automatic layout; a third layout (the chip's cycle leaves room).

### Doc impact

- `spec/instruments.md` — the layout chip on the instrument card and the stored field (Item 1).
- `spec/reviewer-surface.md` — the intro's two layouts (Item 1).
- `spec/ui_elements.md` — the intro columns' second arrangement (Item 1).
- `spec/settings_inventory.md` — `Instrument.intro_layout` (Item 1).
- `spec/csv_contracts.md` — the Settings CSV field (Item 1).
- `spec/roundtrip_coverage.md` — the field's round trip (Item 1).
- `spec/visibility_policy.md` — the visibility card's column follows the instrument's layout (Item 1; added at the PR 2 read).
- `app/web/templates/guide.html` — the preview screencap's alt text names the default layout (Item 1; added at the PR 2 read). <!-- doc-impact-waived: the alt text describes the image, so it changes with the author's reshoot of the screencap, owed as a row in guide/things_to_check_in_browser.md -->
- `guide/things_to_check_in_browser.md` — rows for the chip and both layouts (Item 1).
- `guide/todo_master.md` — the 19Y entry (Item 1).

## Item 2 — The help texts gather into one card

### Opportunity

The author, 2026-10-20, with mockups of the instrument preview: each
response field's help text is its own card, so an instrument with two
one-line help texts draws two slabs for what reads as one paragraph of
guidance. Item 1's Layout 1 sets the heading and help side by side with
the visibility card; the help belongs with the heading it explains.

### Decision

The author's rulings, 2026-10-20:

| Layout | Help texts |
|---|---|
| **Layout 1** | inside the heading (label / description) card, under the description: one row per field |
| **Layout 2** | all in one card in the right column |

Locked, a row reads **Label** — help text; unlocked, the label over its
textarea, as the separate cards' editors are today. Each field's ≡ in
Band 3 still shows or hides its row. Both use the normal card infill
(the author: "ignore the bicolor infill"), not the help-card tint.
Rejected: keeping a card per field (the opportunity), and a split
heading-plus-help-strip card (the mockup's two-tone fill).

### Semantics

- **Rows.** One per field whose ≡ is on and whose help text is set, in
  field order (today's `help_block_items`); the preview also needs the
  field selected into it, as today.
- **No rows.** Layout 1's heading card ends at its description; Layout
  2 draws no help card, and Item 1's no-help arrangements hold.
- **No heading card** (a lone untitled instrument; a locked preview
  with nothing in it): Layout 1's rows still form a card in the heading
  card's place, so the help never moves to the right.
- **Narrow** (≤ 800px): Layout 1 keeps the card whole — heading and
  help, then visibility (the author, 2026-10-20); Layout 2 stacks
  heading, visibility, help card, as today.
- **The layout chip** moves the rows between the two homes at once in
  the preview, unsaved edits in their textareas kept.
- **Elsewhere.** `.rs-help-card` stays the class of the lobby's
  first-run tiles and the Guide's callout; only the intro stops using
  it per field.

### Blast radius (measured)

Taken 2026-10-20 at `925efad3`.

| What | Count | Command |
|---|---|---|
| Templates drawing the intro's help | 2 (+ `base.html` CSS, 14 lines naming the help classes) | `grep -rln "rs-help-stack" app/web/templates`; `grep -c "rs-help-card\|rs-help-stack" app/web/templates/base.html` |
| Other `.rs-help-card` users, unchanged | 2 | `sessions_list.html`, `guide.html` |
| Python building the rows | 1 | `grep -rln --include=*.py "help_block_items" app` |
| Tests naming the help cards or stack | 5 | `grep -rln --include=*.py "rs-help-card\|rs-help-stack\|help_block_items\|data-help-card" tests` |
| Specs on the intro's help | 4 | `spec/reviewer-surface.md`, `spec/instruments.md`, `spec/ui_elements.md`; `spec/settings_inventory.md` (the `intro_layout` row's "help cards") |
| Prose naming the per-field help cards without the class (Codex on #3173) | 2 | the layout chip's titles (`app/web/views/_instruments.py` `INTRO_LAYOUT_CHOICES`), `Instrument.intro_layout`'s docstring |
| Theme-customizer samples mirroring the help editor (Codex on #3173) | 2 | `tools/_harness_common.py` (`ph-help-edit`), `tools/theme_customizer.gen.py` ("Help card with edit box") |

### Status

**Closed 2026-10-20** in two PRs as laddered: #3174 (both surfaces) and
the close.

- **What moved from the plan.** None of the intent. The preview's help
  card is its own lock region, so a locked card counts seven, not six.
  Locked, the preview skips a row whose ≡ is on but whose text is empty,
  as the reviewer surface always had (found at the read: the old
  per-field cards drew a bare label there too). Each row's textarea is
  named for its field (`aria-label`), which the old cards lacked. At
  the close the author added a rule parting Layout 1's heading from its
  rows (`--border-default`, as the Quick Setup slots are parted); rows
  alone in the card take none. That CSS rides the close PR.
- **Decisions confirmed at build.** Layout 1 is one grid row, heading
  card left and visibility right; the old row-span stack is gone.
  `.rs-help-card` keeps only the lobby's tiles and the Guide's callout.
- **Reads.** Two `diff-reviewer` reads. The first, on the cumulative diff from
  `2617ca09`: no correctness defect; five smaller findings, all acted
  on in #3174 (the empty row, the textarea's name, a stale CSS comment,
  two tests, and two Doc impact additions: `spec/color_tokens.md` and
  the screencap's alt text). Codex: no findings. The second, on the
  close slice (it reopened `app/` for the rule): no defect; four low
  findings, all acted on in #3175 (the rule's tie to §10 in
  `spec/ui_elements.md`, a test for the locked titled preview, the
  lock-dependent wording in `spec/instruments.md`, this count).
  `spec-writer` at the close wrote the five specs, the rule included;
  no code-versus-plan flag.
- **Owed by the author:** the browser-check rows in
  `guide/things_to_check_in_browser.md`; the Item 1 screencap reshoot
  now shows Item 2's rows, and its alt text says so.

### PR ladder

1. **PR 1 — both surfaces.** The reviewer surface renders the rows in
   the heading card (Layout 1) or one help card (Layout 2); the
   preview's `rebuildPreview` builds the same, locked and unlocked, and
   the chip re-homes them; CSS; the chip's titles and the model
   docstring say "help texts"; the theme-customizer's help-editor sample
   becomes a row in a normal card (regenerated); integration and browser
   tests. One PR so the preview never disagrees with the surface. Must
   not touch storage or the ≡ toggle's meaning.
2. **PR 2 — specs and close.** The specs below, browser-check rows;
   `spec-writer`; close.

### Definition of done

- A reviewer sees an instrument's help rows inside its heading card
  in Layout 1 and in one card in Layout 2; the preview shows the same,
  locked and unlocked, and ≡ toggles a row (tests).
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19Y.2` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` 19Y entry updated to drop this item; the entry itself goes only when the segment closes

### Open questions

- None (the infill and the narrow order ruled 2026-10-20).

### Out of scope

- The lobby's and the Guide's `.rs-help-card` uses; the help text's
  storage and its 1000-character limit.

### Doc impact

- `spec/reviewer-surface.md` — the help rows' home per layout (Item 2).
- `spec/instruments.md` — the preview's help rows, locked and unlocked (Item 2).
- `spec/ui_elements.md` — the help-card blockquote: the intro's help is rows in a card, not a card per field (Item 2).
- `spec/settings_inventory.md` — the `intro_layout` row says help texts, not help cards (Item 2; added at Codex's read of the plan).
- `spec/color_tokens.md` — `--card-help-*` no longer paints an Instruments-page slab; `.rs-help-card` is the lobby's and the Guide's (Item 2; added at the build read).
- `guide/things_to_check_in_browser.md` — rows for both layouts' help; the Item 1 screencap reshoot's alt text describes the rows, not help cards (Item 2; the alt-text note added at the build read).
- `guide/todo_master.md` — the 19Y entry (Item 2).

## Item 3 — Near-equal intro columns end level

### Opportunity

The author, 2026-10-20, with two screenshots of a locked Layout 1
preview: when the heading card and the visibility card end a few pixels
apart, the ragged bottom edge reads as a mistake; when they end a few
lines apart, it reads as two cards of different length, which is right.
The intro's columns keep their own heights today (`align-items: start`,
19T Item 17), so a near miss is never closed.

### Decision

The author's ruling, 2026-10-20: in lock / display mode, when the two
sides' bottom edges are within **one text line's height**, the shorter
side grows to end level with the taller; otherwise both keep their own
heights. **Layout 1:** the heading card against the visibility card.
**Layout 2:** the left column (heading card over visibility card)
against the help card. A shared script in `base.html`'s foot measures
each intro and sets `data-intro-snap`; CSS stretches the shorter side.
Rejected: always equal heights (the second screenshot, where the gap is
lines, keeps its own heights), and a pure-CSS rule (CSS cannot compare
two heights against a threshold).

### Semantics

- **Threshold.** The intro's computed `line-height` in pixels; a
  difference of zero needs nothing, one at or under the threshold snaps.
- **Which card grows.** The shorter side, its content staying at the
  top: Layout 1 either card; Layout 2 the visibility card (left shorter)
  or the help card (right shorter).
- **Where.** The reviewer surface (display) and a locked preview. An
  unlocked preview never snaps: its textareas change height as the
  operator types.
- **Not side by side.** Narrow (≤ 800px, one column), a missing card
  (no help rows in Layout 2, no heading card, no visibility card): no
  snap.
- **Re-measured** on load, on fonts loading, and whenever the intro or
  either compared side resizes (width, a rebuild, the layout chip, lock
  and unlock; a side can change with the intro's box unchanged, Codex on
  #3176), each time from the natural heights, so a snap never feeds its
  own measurement. The page also re-measures after lock, unlock and the
  chip, whose effect on any box may be nil.

### Blast radius (measured)

Taken 2026-10-20 at `6d7dac65`.

| What | Count | Command |
|---|---|---|
| Templates drawing the intro | 2 (+ `base.html` CSS and the new foot script) | `grep -rln "rs-intro-columns" app/web/templates` |
| Tests on the intro's arrangement | 4 integration, 1 browser | `grep -rln "rs-intro-columns\|intro_columns" tests --include=*.py` |
| Specs on the intro | 2 | `grep -rln "rs-intro-columns\|intro columns" spec` (`spec/reviewer-surface.md`, `spec/visibility_policy.md`) |

### Status

**Closed 2026-10-20** in two PRs: #3176 (the plan) and the build, specs
and close in one, as laddered.

- **What moved from the plan.** Codex on #3176: the observer watches
  both compared sides as well as the intro, since a side can resize
  with the intro's box unchanged; each pass is deferred a frame so the
  snap's own resize settles in one more pass. Layout 1 stretches both
  cards to their row; only the shorter visibly grows. Against the
  Semantics' missing-card bullet: Layout 2 with no heading card still
  snaps (the visibility card alone is its left side), and Layout 2
  without a visibility card does not (nothing would take the slack).
  The chip's re-measure was dropped: it only works unlocked.
- **Decisions confirmed at build.** `window.rrwLevelIntros` is the one
  entry point; the Instruments page calls it after lock and unlock. A
  pass clears, reads, then writes every intro it covers, one reflow
  however many instruments the reviewer surface draws. The tests nudge
  the shorter side's `min-height` to a set gap (6px near, a line and
  8px far) rather than craft content to a pixel.
- **Reads.** One `diff-reviewer` read on the build: no correctness
  defect; six smaller findings, all acted on before the PR opened (the
  Layout 2 visibility-card grow untested, the missing-card wording, the
  chip's no-op call, a reflow per intro per pass, five uncovered cases,
  `before` unchecked in two tests).
  `spec-writer` at the close wrote the three specs (a new intro-columns
  blockquote in `spec/ui_elements.md`); no code-versus-plan flag.
- **Owed by the author:** the browser-check rows in
  `guide/things_to_check_in_browser.md`.

### PR ladder

1. **PR 1 — build, specs, close.** The foot script, the CSS, browser
   tests for both layouts (near → level; lines apart → own heights;
   unlocked and narrow → own heights), the specs and checklist rows;
   one cumulative `diff-reviewer` read; `spec-writer`; close. One PR:
   a single mechanism on markup that already exists. Must not touch
   the intro's markup order or the layouts' arrangement.

### Definition of done

- Near-equal sides end level and far-apart sides keep their heights,
  in both layouts, on the reviewer surface and a locked preview; an
  unlocked or narrow preview never snaps (browser tests).
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19Y.3` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` 19Y entry updated to drop this item; the entry itself goes only when the segment closes

### Open questions

- None (the threshold and both layouts ruled 2026-10-20).

### Out of scope

- The unlocked preview; the Band 3 table and anything below the intro.

### Doc impact

- `spec/reviewer-surface.md` — the intro's near-equal columns end level (Item 3).
- `spec/ui_elements.md` — the intro columns primitive: the snap and its threshold (Item 3).
- `spec/instruments.md` — the locked preview snaps, the unlocked one does not (Item 3).
- `guide/things_to_check_in_browser.md` — rows for both layouts, near and far (Item 3).
- `guide/todo_master.md` — the 19Y entry (Item 3).

## Item 4 — The preview's response boxes don't resize

### Opportunity

The author, 2026-10-20: a long-text response field (Comments) in Band 2's
preview table keeps the app-wide vertical resize handle
(`body.ui-v2 textarea { resize: vertical }`), but a drag there persists
nowhere, so the handle promises a setting that does not exist.

### Decision

The author's ruling, 2026-10-20, on a recommendation: **no resize in
the preview**; the reviewer surface keeps its handle. The preview
already shows the reviewer's starting height: both size the box by the
same rule (`textarea_rows_for`, from `max_length` and the column
width). Rejected: a stored per-field height (a column, both Saves, the
Settings CSV, Duplicate and Replicate, an audit event, and a rule for
which wins when it disagrees with the derived rows) for a box the
reviewer can resize anyway.

### Semantics

- Only the preview table's response textareas (`buildResponseFieldPreviewCell`
  in `instruments_index.html`) take `resize: none`; the help and
  description boxes are real inputs and keep theirs (help: Item 5).
- The reviewer surface (`review_surface.html`) and the app-wide rule
  are unchanged.

### Blast radius (measured)

Taken 2026-10-20 at `7d9f1042`.

| What | Count | Command |
|---|---|---|
| Preview builder setting the handle | 1 line | `grep -n "resize: vertical" app/web/templates/operator/instruments_index.html` |
| Specs naming the textarea resize rule | 2 | `grep -n "resize" spec/ui_elements.md spec/reviewer-surface.md` (§ textarea rule; the field-type table) |

### Status

**Closed 2026-10-20** in two PRs: #3178 (the plan, with Item 5's) and
the build, specs and close in one, as laddered.

- **What moved from the plan.** Nothing.
- **Reads.** READS_LINE
- **Owed by the author:** the browser-check row in
  `guide/things_to_check_in_browser.md`.

### PR ladder

1. **PR 1 — build, specs, close.** `resize: none` on the preview's
   response textareas; a browser test (preview `none`, reviewer
   surface `vertical`); specs; checklist row; one `diff-reviewer`
   read; close. Must not touch the reviewer surface.

### Definition of done

- The preview's long-text response box has no resize handle; the
  reviewer surface's keeps one (browser test).
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19Y.4` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` 19Y entry updated to drop this item; the entry itself goes only when the segment closes

### Open questions

- None (ruled 2026-10-20).

### Out of scope

- A stored response-box height; the derived rows rule itself.

### Doc impact

- `spec/instruments.md` — the preview's response boxes take no resize handle (Item 4).
- `spec/ui_elements.md` — the textarea resize rule's one exception (Item 4).
- `guide/things_to_check_in_browser.md` — a row for the handle (Item 4).
- `guide/todo_master.md` — the 19Y entry (Item 4).

## Item 5 — A help text's edit box grows with its text

### Opportunity

The author, 2026-10-20, with two screenshots of an unlocked Layout 2
card: a long help text sits in a fixed 60px textarea behind a
scrollbar, so the operator edits it a few lines at a time while the
locked card shows it whole.

### Decision

The author's ruling, 2026-10-20: the help text's edit box grows with
its text. Its height is set to its content on build, on every
keystroke, and when its width changes (window, layout chip, column).
Judgment call: the box loses its resize handle and scrollbar
(`resize: none; overflow: hidden`), since its height now follows the
text and a drag would be undone by the next keystroke. Rejected: a
larger fixed height (still scrolls past it, and wastes space on a
one-line help).

### Semantics

- **Floor.** Today's 60px minimum stays; a short or empty help keeps it.
- **Ceiling.** None needed: `maxlength` 1000 bounds it.
- **Where.** The help rows' textareas (`buildResponseFieldHelpRows`),
  in either home (Item 2). The description box is not in scope.
- **Unsaved text** survives the re-fit: the fit reads the box, never
  rebuilds it.

### Blast radius (measured)

Taken 2026-10-20 at `7d9f1042`.

| What | Count | Command |
|---|---|---|
| Builder of the help textarea | 1 function | `grep -n "function buildResponseFieldHelpRows" app/web/templates/operator/instruments_index.html` |
| Its input handler | 1 | `grep -n "newModelHelpCardInput = " app/web/templates/operator/instruments_index.html` |
| Tests touching the help textarea | 1 browser file | `grep -rln "data-help-card-textarea" tests --include=*.py` |

### PR ladder

1. **PR 1 — build, specs, close.** The fit on build, input and width
   change; browser tests (long text shows whole, typing grows it,
   short text keeps the floor, a move between homes re-fits); specs;
   checklist row; one `diff-reviewer` read; close. Lands after Item 4.

### Definition of done

- An unlocked help box shows its whole text with no scrollbar, grows as
  the operator types, and keeps 60px for a short text (browser tests).
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19Y.5` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` 19Y entry updated to drop this item; the entry itself goes only when the segment closes

### Open questions

- None (ruled 2026-10-20).

### Out of scope

- The description box; the help text's 1000-character limit.

### Doc impact

- `spec/instruments.md` — the help row's edit box grows with its text (Item 5).
- `spec/ui_elements.md` — the textarea resize rule's second exception (Item 5).
- `guide/things_to_check_in_browser.md` — a row for the growing box (Item 5).
- `guide/todo_master.md` — the 19Y entry (Item 5).
