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
| Specs on the intro's help | 3 | `spec/reviewer-surface.md`, `spec/instruments.md`, `spec/ui_elements.md` |

### PR ladder

1. **PR 1 — both surfaces.** The reviewer surface renders the rows in
   the heading card (Layout 1) or one help card (Layout 2); the
   preview's `rebuildPreview` builds the same, locked and unlocked, and
   the chip re-homes them; CSS; integration and browser tests. One
   PR so the preview never disagrees with the surface. Must not touch
   storage or the ≡ toggle's meaning.
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
- `guide/things_to_check_in_browser.md` — rows for both layouts' help (Item 2).
- `guide/todo_master.md` — the 19Y entry (Item 2).
