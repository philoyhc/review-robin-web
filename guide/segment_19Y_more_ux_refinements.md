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
- **Missing cards.** No help cards: both layouts render the heading and
  visibility in one column, as today. No visibility rows: Layout 1's
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
- `guide/things_to_check_in_browser.md` — rows for the chip and both layouts (Item 1).
- `guide/todo_master.md` — the 19Y entry (Item 1).
