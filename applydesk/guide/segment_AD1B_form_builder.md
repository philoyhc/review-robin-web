# Segment AD1B — ApplyDesk: the Form page, a working scaffold

**Opened:** 2026-11-12 · **Theme:** the application form builder on the operator's Form tab, every on-screen move working in the browser, nothing saved · **Related:** `applydesk/guide/segment_AD1_skeleton.md` (the placeholder this replaces), `applydesk/guide/todo_master.md` (rulings 3, 11; AD4 wires the form), `residentialapps/spec/residentialops_ui.md` (the columns), RRW's instrument designer (`app/web/templates/operator/instruments_index.html`: data types, bounds, Replicate)

## Opportunity

The Form tab is a placeholder: two static lists and an inert preview (AD1 iteration 5). The builder is the page operators will spend longest on, and its shape was not settled: a first mock-up after Google Forms (a floating tool strip, a settings panel) read as "trying too hard" (author, 2026-11-12). The author settled the card style through four mock-ups the same day, and widened "scaffold" to include movable UI elements: the page should work on screen before AD2 gives it a database, so the shape is judged by using it, not by reading it.

## Decision

**A column of cards in the Cordware style, every move working in the browser, nothing saved** (author, 2026-11-12):

1. **The form's own Title and Description**, a card at the top that cannot be deleted or moved; ~~or collapsed~~ it collapses like a card (author, iteration rung 4).
2. **One card per question or text block.** A form starts with one card, and its last card cannot be deleted.
3. **A card collapses and expands.** Collapsed, it shows its question and help text (or title and description) and a summary of its settings, and no controls. Expanded, it shows its fields and its buttons.
4. **Each card's own controls**: a type menu at its top right; a **Shown to reviewers / Not shown** toggle; along its bottom *Replicate*, *+ New*, *+ Section*, *+ Page break* and *Delete*.
5. **A handle on each card** to drag it, and to move it with the keyboard.
6. **No numbering**: a card's internal ID never shows.
7. **Three columns** after Residential: the cards in the left two-thirds, an **Outline** in the right third, kept in view; one column on a phone, the Outline below.

**Rejected:**
- **A Google Forms floating tool strip and settings panel**: "too close to Google Forms" (author). Each card carries its own buttons instead, as RRW's instrument cards do.
- **Visibility per section**: tried in the second mock-up; the author put it on **every card** ("there should be more states in the spec, but start with shown / not shown"). A section is a titled group.
- **Inert controls, as AD1's placeholders**: the author widened the scaffold to working moves; saving still waits.

## Semantics

- **Card types** (the type menu), each with its expanded fields under *Question* and *Help text*:

  | Type | Fields | Collapsed summary |
  |---|---|---|
  | String | Min length, Max length, Required | "String · 1 to 120 characters" |
  | Integer | Min, Max, Step, Required | "Integer · 1 to 6, step 1" |
  | Decimal | Min, Max, Step, Required | "Decimal · 0.00 to 5.00, step 0.01" |
  | List | Options (comma-separated, ~~with presets~~ (dropped at build: none were specified)), *Choose one / Choose any*, Required | "List · choose one · A, B, C" |
  | Photo | Ratio width : Ratio height, Required | "Photo · 4:5, kept 480 × 600" |
  | Title and Description | *Title* and *Description* in place of Question and Help text; nothing else | "display only" |

  An empty bound is left out of the summary ("Integer · up to 6"). Changing a card's type keeps its question, help text, visibility and Required, and shows the new type's fields empty.
- **Photo's kept size** follows the ratio: 600 px on the longer side (4:5 → 480 × 600; 1:1 → 600 × 600).
- **Visibility** is per card: *Shown to reviewers* or *Not shown*; a new card is *Not shown*, the side that hides. Later states belong in the spec (Open questions).
- **Sections and page breaks.** *+ Section* inserts a section card (a title, collapsible, its own buttons less *Replicate*); *+ Page break* a dashed divider with *Remove*. Both can always be removed; neither counts toward "the last card".
- **Where things land.** *+ New* inserts a String card right after the card; *Replicate* a copy of it (a field card only); *+ Section* and *+ Page break* after it. A new card opens expanded.
- **The last card.** *Delete* is disabled, with a reason in its title, while one question or text card is left. No confirmation step (author).
- **Reordering.** Dragging a handle moves the card among the others (sections and page breaks included; the form's Title card stays first). A focused handle moves its card with ↑ and ↓.
- **Load state.** Every card loads collapsed, except a form with a single card, which opens it. Several cards can be open at once.
- **Outline** lists sections, cards and page breaks in order, each card's visibility as a chip, and the counts; a click scrolls to the card. It follows every change.
- **Preview** shows the form as an applicant sees it, page by page, built from the cards on screen; ~~*Back to editing* returns~~ in a new tab since iteration rung 4, showing the sample form when it cannot reach the builder that opened it.
- **Nothing is saved.** A reload restores the sample form; the placeholder banner says so, and *Save* is disabled until AD2.

## Judgment calls — decided

- **Cards render on the server, moves happen in one inline script** (no framework, as RRW's designer): a new card clones a `<template>` the server rendered from the same macro, so markup lives in one place.
- **Each card carries every type's fields**, the inactive ones hidden, as RRW's instrument rows do; switching type swaps what shows without a round trip.
- **A new card is *Not shown*** to reviewers: the safer side until the operator says otherwise.
- **The blank exercise** (`n5wg8tjr3e`) shows its Title card and one empty String card, expanded.
- **Applicant pages keep their sample lists** (`SHOWN_TO_REVIEWERS`, `NOT_SHOWN_TO_REVIEWERS`) until AD4 renders a stored form; the builder's sample form carries the same questions. *(At build: it carries most of them and adds others; the two meet at AD4.)*

## Blast radius (measured)

Taken 2026-11-12 at `666cf88`.

| What | Count | Command |
|---|---|---|
| The Form template replaced | 1 file, 31 lines | `wc -l applydesk/templates/applydesk/operator/_form.html` |
| Scripts in ApplyDesk templates today | 1 (the bar, in `base.html`) | `grep -rln "<script" applydesk/templates` |
| Form tests to rewrite | 2 of 33 in `test_pages.py` | `grep -n "def test.*form" applydesk/tests/test_pages.py` |
| ApplyDesk browser tests | 0 | `ls applydesk/tests` |

## Status

Building. Base `73d4230` for the cumulative read.
- Rung 2: the page and its cards. The form's sample cards (`sample_data.SAMPLE_FORM`), one macro per kind (`operator/_form_cards.html`), and one inline script for collapse, the type menu, the toggles, the summaries and the Outline; *+ New*, *Replicate*, *+ Section*, *+ Page break*, *Delete* and the handle render, inert until rung 3. A Title and Description card shows no Required chip. Summaries are computed twice, `card_summary` for the first render and the script after an edit; a Chromium test replays `test_form.SUMMARY_CASES` and every sample card through the script (rung 3).
- Rung 3: the moves. *+ New*, *+ Section* and *+ Page break* clone the server's own macros from `<template>`s, *Replicate* the card itself; *Delete* keeps the last field card; dragging listens on the document, since moving the card in the page ends a pointer capture; ↑ and ↓ on a focused handle; Preview builds from the cards. A string question with a maximum of 200 or fewer characters previews as one line, longer or unbounded as a box. The cumulative read (1 read, 13 findings) led to: a bad maximum no longer breaking Preview; the kept size rounding half up on both sides; an Outline click leaving Preview; the Outline unnumbered (Decision 6); a type change resetting *Choose one*; handles and toggles named after their card, arrow-key moves announced; presets dropped from the plan. Left as notes: drag has no Escape or auto-scroll; `.seg` and `.btn-toggle` are ApplyDesk's own controls, beside RRW's roles.
- Iteration rung 4 (author, 2026-11-12): Preview in a new tab and the title card collapsing (Decision 1, Semantics). The tab reads the builder through `window.opener`, kept on purpose so a reload picks up later edits; both tabs are the same origin behind the same gate. A tab opened without an opener (middle-click) says it shows the sample form. Its read: 9 findings, all prose, tests or nits, acted on.

## PR ladder

1. **Plan** (this file), its README row and roadmap row.
2. **The page and its cards.** The sample form as cards (every type, sections, a page break); the Title card; the columns; collapse and expand; the type menu swapping fields; *Required*, visibility and *Choose one / any*; collapsed summaries that follow edits; the Outline rendered. Tests: every type renders; a Chromium test collapses, expands, switches type and sees the summary follow.
3. **Moves.** *+ New*, *Replicate*, *+ Section*, *+ Page break*, *Delete* and the last-card rule; drag and keyboard reordering; the Outline following every change; Preview. Chromium tests for each. Last build rung: `diff-reviewer` reads the cumulative diff.
4. **Iteration rungs**, as the author's browser checks ask.
5. **Close.**

## Definition of done

- Every type's card renders collapsed and expanded with the fields and summary in the table above (test).
- In Chromium: collapse, expand, type switch, the summary following an edit, add, replicate, section, page break, delete, the last card's disabled *Delete*, drag and keyboard reorder, the Outline following, Preview (tests).
- The author has used the page locally and approved it.
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD1B` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **Visibility beyond shown / not shown**: the further states belong in the spec (author: "there should be more states in the spec"); which, and when (author).
- **`close_check.py` reads only RRW's `guide/`**, as AD1 found: this close is checked by hand unless the tool learns ApplyDesk's folder (author).

## Out of scope

- **Saving** the form, and checking it on the server (bounds that make sense, lists with options): AD2 gives the database, AD4 the form's storage and versioning (`applydesk/guide/todo_master.md`, roadmap).
- **The applicant's side**: filling the form in, and the photo field's own cropper (`applydesk/docs/photo_field_design.md`), come with AD4.
- **Conditional questions** and answer validation beyond the bounds.

## Doc impact

- `applydesk/spec/applications.md` — the Form tab's page: cards, types, visibility, moves, nothing saved (rungs 2–3).
- `applydesk/guide/segment_AD1_skeleton.md` — the Form row of the URL map points here (rung 2).
- `applydesk/guide/todo_master.md` — ruling 12: the photo type is in the MVP, an exception to ruling 3; the AD1B roadmap row, deleted at close (rung 1).
- `applydesk/README.md` — this plan's row (rung 1).
