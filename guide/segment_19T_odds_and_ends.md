# Segment 19T — Odds and ends

**Opened:** 2026-09-24 · **Theme:** small operator-UI adjustments the author
logs one at a time; items close independently · **Related:**
`spec/instruments.md`, `guide/archive/segment_19S_post_assessment.md`

A holding segment for small, unrelated adjustments, each an item with its own
`Doc impact` and `Status`. It closes when every item has.

---

## Item 1 — Instruments: the ✓ button, the blank row, the Band 3 split

**Logged 2026-09-24 on the author's instruction.**

### Opportunity

The Band 3 response-field rows on the Instruments page carry a ✓ whose job
is unclear. Its tooltip says "Save this response field to the pills +
preview", yet it saves nothing (`spec/instruments.md`: "Pure UX — nothing
persists across reload until the card-wide bulk Save runs").

Its enabled state is not tied to that job. A row with a pill greys ✓ out
until `data-row-pending` is set, and *any* keystroke sets that flag and
nothing but ✓ clears it (`instruments_index.html`,
`newModelRfRecomputeActionStates`). So a row typed and typed back offers ✓
with nothing to push.

Two smaller frictions sit beside it:
- **A blank row.** The template always renders a trailing empty "starter"
  row after the populated ones (`spec/instruments.md` Band 3), so the list
  never ends where the fields do.
- **The Band 3 split.** Visibility and Response fields split the band 1:1
  (`grid-template-columns: 1fr 1fr`), though the response-field rows carry
  far more controls.

### Decision

1. **✓ does two things and nothing else**:
   - on a row with no pill, it creates the field's pill in Band 2 and adds
     its column to the reviewer-surface preview;
   - on a row whose preview-bearing attributes differ from its pill, it
     updates the pill and the preview.

   It is **enabled only when a row meets one of those** and disabled
   otherwise. Toggling **R** (required) or **≡** (help text) never needs ✓,
   because both already update the preview live. **Save alone persists**;
   ✓'s tooltip stops saying "Save".
2. **No standing blank row.** The template renders only populated rows.
   **"+"** adds a blank row. **Cancel** (discard without saving) removes it,
   because the discard reload re-renders from persisted state. Deleting the
   last row leaves no rows rather than a blank one.
3. **Band 3 splits 2 : 3**: Visibility 2/5, Response fields 3/5
   (`grid-template-columns: 2fr 3fr`).

**Rejected: keeping the sticky pending flag and only renaming the tooltip.**
The flag answers "was this row touched", not "does this row differ from its
pill", which is the author's rule. A comparison is the only thing that greys
✓ again when an edit is typed back.

**Amendment (2026-09-24, the author, after rung 2).** It supersedes point 2's
single "+" and its last-row rule:
- **A "+" on every row** inserts a blank row directly below that row. It
  heads the row, before the name field, and X is the red `destructive`
  button, as in Band 1 (the author, after rung 2b). The single "+" under
  the list goes.
- **The last row cannot be deleted**: X is inactive while one row is left.
  So a card with no saved fields renders one blank row, or it would have
  no "+" at all.
- **Order follows the rows.** ✓ on a row inserted between A and B puts
  its pill between theirs (A, C, B), and Save persists the rows in row
  order. Today Save writes pill order and appends un-ticked rows last,
  and dragging a response pill leaves its row where it was. So a
  response-pill drag now also moves its row. The author accepts rows that
  catch up only on reload; the move is here because Save now reads row
  order, so without it Save would undo a drag.

### Semantics

- **"Differs"** compares the row's current values with what its pill and
  the preview show. Which attributes the pill carries versus which the
  preview reads from the row is measured in rung 2 (Open questions). R and ≡
  are excluded, since they already propagate on click.
- **A blank or invalid row** keeps ✓ disabled, as today: no name, or
  `newModelRfValidateShape` fails.
- **Zero rows.** (Superseded by the amendment: a card with none renders
  one blank row.) "+" must work with no row to clone. Today it clones the
  first row, so it will build from a `<template>` instead.
- **A "+" row left blank at Save** is already dropped: `serializeRow`
  returns `null` for a nameless row.
- **Cancel's enablement.** "+" is in the card's dirty-marking click list,
  so adding a row enables Cancel, and Cancel's reload removes the row.
- **Narrow widths.** The Band 3 grid has no media query today; 2 : 3 changes
  only the ratio.

### Judgment calls — decided

- ✓ keeps staging into `band2_state_snapshot` and marking the card dirty.
  That is not persisting, and Save still owns the write (2026-09-24).
- ~~Deleting the last row removes it outright.~~ Superseded by the
  amendment: the last row stays (2026-09-24).

### Blast radius (measured)

Taken 2026-09-24 at `b705245d`.

- **Template:** one file, `app/web/templates/operator/instruments_index.html`.
  - 41 references to `newModelRf` (`grep -c 'newModelRf'`);
  - the Band 3 grid at the `data-new-model-band3` div;
  - the trailing row under `Trailing empty row`;
  - `newModelRfAddRow`, `newModelRfDeleteRow` and
    `newModelRfRecomputeActionStates`.
- **Tests:** one file cites the row markup,
  `tests/integration/test_instrument_builder_routes.py`, with 5
  `data-new-model-rf-row` markers
  (`grep -rln 'data-new-model-rf-\|newModelRf' tests`).
- **Spec:** `spec/instruments.md`, three places: the band table, the
  "trailing empty starter row" sentence, and the ✓ row of the button table
  (`grep -n 'starter row\|✓\*\* button\|Visibility, Response fields'`).

### Status

**Closed 2026-09-24** (#2598, #2599, #2600, #2601; the capture in #2602).
The item's diff base was `de83af9d`, main before rung 1.

**What the ladder became.** Rungs 1 and 2 shipped as planned. The
author's amendment added rung 2b (per-row "+", the last row kept,
row-ordered ✓, Save and drag), then a follow-up moved "+" to the head of
the row and made X red. The close took Item 2's close with it.

**Decisions confirmed at build:**
- The open question: the preview read the name from the pill but type
  and bounds from the live row on every rebuild. So the pill now carries
  the pushed shape (`data-rf-*`), the preview reads it, and ✓ compares
  the row with it.
- A pill that ✓ creates starts selected, so its column joins the preview.
- The amber marker means "differs from the pill", valid or not.
- A successful Save syncs every paired pill to its row, since Save persists
  rows as typed and doesn't reload.
- R and ≡ stage for Save; ✓ is never needed for them.

**Defects on main, found in Chromium and fixed:**
- ✓ and X called `saveBand2State` from outside its closure, so X never
  removed a row that had a pill. They now reach it through
  `window.newModelStageBand2State`.
- R and ≡ alone never enabled Save.
- The first keystroke left ✓ off.

**Reads.** Three `diff-reviewer` reads:
- the cumulative read at rung 2 found Save-without-✓ staleness, the stale
  Guide capture and the marker, all fixed;
- rung 2b's read found stale prose;
- the "+" / X read found no defects, and its §6 note went to Doc impact.

### PR ladder

1. **The blank row and the split.** Drop the trailing row. "+" builds from
   a `<template>`. X on the last row removes it. Band 3 goes to
   `2fr 3fr`. Tests pin: no blank row renders, "+" works from zero rows,
   and the grid ratio. It must not touch ✓.
2. **✓ by comparison.** Measure the pill- versus row-borne attributes, then
   replace the pending flag with a comparison and reword the tooltip.
   Tests pin the enable rule's markup; Chromium drives the behavior. This
   is the item's last build rung, so `diff-reviewer` reads the cumulative
   diff from `b705245d`.
2b. **The amendment** (added 2026-09-24). Per-row "+", the last row kept,
   row-ordered ✓ and Save, and a pill drag that moves its row. It reopens
   `app/`, so it takes its own `diff-reviewer` read on its diff.
3. **Close.** `spec/instruments.md`, the browser checks, a `docs/status.md`
   row and `spec-writer`.

### Definition of done

- ~~No trailing blank row renders; "+" adds one from zero rows.~~ Only
  saved rows render, or one blank row when there are none. Each row's "+"
  inserts below it, and Cancel's reload removes an unsaved row.
- X is inactive on the only row left.
- ✓ places a new pill in row order; Save persists row order; a response-pill
  drag moves its row.
- ✓ is enabled only for a named, valid row with no pill or with
  preview-bearing values that differ from its pill; R and ≡ never enable it.
- Band 3 renders `grid-template-columns: 2fr 3fr`.
- `spec/instruments.md` states all of the above.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19T.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

- ~~Which attributes does the preview read from the pill, and which from
  the row?~~ The name from the pill; type and bounds from the row, until
  rung 2 moved them onto the pill (Status).

### Out of scope

- What ✓ does to persistence: Save's job, unchanged.
- The reviewer surface itself; only the builder's preview is touched.

### Doc impact

- `spec/instruments.md` — Band 3: no starter row except one blank row at
  zero fields; a "+" per row, at its head, inserting below; X in the red
  `destructive` role and inactive on the last row; the
  ✓ row's two purposes and enable rule; R / ≡ enabling Save; ✓, Save and a
  pill drag following row order; the 2 : 3 split (Item 1).
- `guide/post_azure_todo_checklist.md` — browser checks for the ✓ enable
  rule, a row's "+" and Cancel, the last row, row order through ✓ / Save /
  drag, R / ≡ alone enabling Save, and the split (Item 1).
- `app/web/static/guide/instrument-card-fields-and-visibility.png` — retaken
  with its `-dark` twin on the dev slot: the capture shows the 1 : 1 split
  and the blank row (Item 1).
- `spec/ui_elements.md` — §6's note puts a field builder's row delete / add
  on `.btn-icon.danger` / `.action`, but Band 1's X and now Band 3's are
  `btn destructive`: reconcile the note with the author's ruling (Item 1).
- `docs/status.md` — row when the item closes (Item 1).

---

## Item 2 — Instruments: `?editing` no longer locks the action rows

**Logged 2026-09-24 on the author's report.**

### Opportunity

With `?editing=<id>` in the URL, every card's Replicate, Delete,
+Instrument and +Page break, and the page-break ×, render disabled. The
tooltips say "Save or cancel … first", but neither gets the page out of
that state:
- Save is a fetch, with no reload;
- Cancel's discard reload re-adds `?editing` to keep the card unlocked;
- the in-page Lock leaves the URL alone.

The rule comes from 10D Slice 5 (`11c5a730`, 2026-05-02), when edit mode
was only the server's `?editing` and a form post silently lost unsaved
edits. It also held a mutual lock against the Response Type Definitions
row editor, which has since retired. 18R Item 2 then added the client lock
layer and the nav-away guard, but kept the rule. An in-page Unlock
never sets `?editing`, so the same unlocked card disables nothing that
way. `spec/instruments.md` states the rule for Replicate and +Instrument
("another instrument is being edited").

### Decision

**An open card no longer disables anything.** The disable conditions keep
only their other reasons: a session that can't be edited, the only
instrument, and the page-break placement rules. The nav-away guard
(`beforeunload` on a dirty card, 18R Item 2 PR 2) already warns before
these form posts discard unsaved edits. **Lock strips `?editing`** from
the URL with `history.replaceState`, so a reload lands locked.

**Rejected: disabling the four in-page while any card is unlocked.** That
keeps a rule the leave-page guard already covers, and it disables work
on clean cards too.

### Semantics

- A dirty card and a form post: the `beforeunload` confirm fires. Only the
  discard reload (Cancel, a dirty Lock) sets the intentional-nav flag. Save
  is a fetch and never leaves the page.
- The page-wide "one unlocked card" rule (Unlock on a second card) is
  untouched.

### Blast radius (measured)

Taken 2026-09-24 at `cdbc6c96`.
- `is_some_instrument_editing`: 1 view key (`app/web/views/_instruments.py`)
  and 3 template uses in `instruments_index.html`: the action-row disable,
  its title, and the page-break ×
  (`grep -rn is_some_instrument_editing app/`).
- `spec/instruments.md`: the Replicate / +Instrument disable lists
  (`grep -n "being edited" spec/instruments.md`);
  `spec/operator_button_audit.md` rows 54–55, "edit lock"
  (`grep -n "edit lock\|edit-lock" spec/operator_button_audit.md`). The
  second was missed at logging and found by the item's read.
- No test pins the rule (`grep -rn "open instrument edit" tests/`).

### PR ladder

1. **The fix.** Drop the editing condition and the view key; Lock strips
   `?editing`. Tests pin the enabled buttons under `?editing` and the
   strip. It takes a `diff-reviewer` read.
2. **Close**, together with Item 1's.

### Definition of done

- Under `?editing=<id>`, Replicate, Delete, +Instrument, +Page break and
  the page-break × render enabled, unless one of their other reasons
  applies.
- Lock leaves the URL without `?editing`.
- `spec/instruments.md` drops "another instrument is being edited".
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19T.2` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

- None.

### Status

**Closed 2026-09-24** (#2603, closed with Item 1). It shipped as planned:
the fix and the log landed together. One `diff-reviewer` read found no
defect in the change. It found three gaps, all fixed in #2603:
- the test's +Page break check passed without the fix, and now pins it;
- `spec/operator_button_audit.md` was missing from Doc impact;
- the nav-guard comment and Semantics wrongly said Save sets the
  intentional-nav flag.

`spec-writer` at close raised two flags, both adjudicated:
- `spec/operator_button_audit.md` row 57 still described Lock as `?editing`
  and a disabled `<button>` under an edit lock. The close restated it.
- The spec never gave the page-break × an editing condition, so the Doc
  impact claim was dropped.

### Out of scope

- The legacy no-JS routes that redirect to `?editing`. They now only keep a
  card open.
- Ticking a card's Delete confirm checkbox marks the card dirty, because the
  tracker listens for `change` card-wide. So Delete on a clean card still
  gets the leave-page prompt. This predates the item; the read flagged it
  (2026-09-24).

### Doc impact

- `spec/instruments.md` — Replicate / +Instrument / Delete lose the "another
  instrument is being edited" condition; Lock strips `?editing` (Item 2).
- `spec/operator_button_audit.md` — the Replicate and Delete rows lose their
  "edit lock" gating; row 57 (Lock / Unlock) restated (Item 2).
- `guide/post_azure_todo_checklist.md` — browser check: Cancel, then Lock,
  leaves the action row live (Item 2).
- `docs/status.md` — row when the item closes (Item 2).

---

## Item 3 — Small fixes register

**Opened 2026-09-24 on the author's instruction.** A register item for
one-line fixes too small for an item of their own. It stays open for more
entries and closes when the author says. Each entry has the defect, the
fix and its PR, and the checks the ladder owes are the same per entry: a
test, a `diff-reviewer` read on any code, and Doc impact.

### Entry 1 — the Delete confirm checkbox dirtied the card

- **Defect.** The dirty tracker listens for `input` / `change` card-wide,
  and the Delete confirm checkbox sits inside the card. Ticking it enabled
  Save and Cancel with nothing to save. It also made Delete, a form post,
  trip the `beforeunload` "Leave site?" prompt on a clean card. Unticking
  didn't clear it. Found by Item 2's read. It predates 19T.
- **Fix.** The tracker's `input` / `change` handler skips targets inside
  `[data-delete-confirm]`. Chromium: ticking leaves the card clean with
  Delete live; a row edit still dirties it.

### Entry 2 — the Name and Email pills could be unselected

- **Defect** (the author, 2026-09-24). Name and Email are locked display
  fields, always shown on the reviewer surface: `update_display_field`
  refuses to hide them, and `_sync_display_field_visibility` skips them.
  But their Band 2 pills toggled like any other. Unselecting one dropped
  its preview column and enabled Save, while nothing changed on save or on
  the reviewer surface, and a reload showed the pill selected again. The
  pill never had a selection lock; its tooltip already read "pinned
  first".
- **Fix.** The view marks locked display fields (`locked`, from
  `is_locked_display_source`). Their pills carry `data-locked="true"`, a
  default cursor and an "Always shown — pinned first" tooltip, and
  `newModelToggleBand2Pill` ignores a click on one. Chromium: clicking
  Name or Email leaves both selected with Save off, while Tag 1 still
  toggles and its column goes. The author named Name; Email is locked by
  the same server rule, so it gets the same lock.
- **Its read found a defect in the fix.** Grouped mode disables and
  unselects the Email pill, since a group row has no email, and nothing
  re-selected it on the way back to Individual. The lock then blocked the
  click that used to restore it. `refreshPillStates` now re-selects a
  locked pill whenever it isn't disabled. Chromium: grouped, then
  Individual, brings Email back selected. The read's inline-style note is
  taken too: the pill's `style` goes, since `refreshPillStates` sets the
  cursor on load.

### Blast radius (measured)

Taken 2026-09-24 at `48b21d05`.
- Entry 1: one listener pair in `instruments_index.html`
  (`grep -n "addEventListener('change', markDirty" …`, 1 hit).

Taken 2026-09-24 at `eb4bdf23`, for entry 2:
- the display-pill markup and `newModelToggleBand2Pill`, in
  `instruments_index.html`;
- the Band 2 field dict in `app/web/views/_instruments.py`;
- `is_locked_display_source`, 2 locked sources
  (`grep -n "_LOCKED_DISPLAY_SOURCES" app/services/instruments/_display_fields.py`).

### Definition of done

- Every entry has its fix merged and a test that fails without it.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19T.3` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

### Open questions

- None.

### Status

**Open** (2026-09-24). Entries 1 and 2 are fixed. Entry 1's `diff-reviewer` read found
no defect: no other listener dirties the card from the checkbox, the
attribute sits only on checkboxes, Delete still enables, and the test fails
on the old template.

### Doc impact

- `spec/instruments.md` — Save-when-dirty: the Delete confirm checkbox
  doesn't count as an edit (Item 3, entry 1); the Name and Email pills
  are always selected and ignore clicks (Item 3, entry 2).
- `docs/status.md` — row when the item closes (Item 3).

