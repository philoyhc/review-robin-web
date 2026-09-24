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

### Semantics

- **"Differs"** compares the row's current values with what its pill and
  the preview show. Which attributes the pill carries versus which the
  preview reads from the row is measured in rung 2 (Open questions). R and ≡
  are excluded, since they already propagate on click.
- **A blank or invalid row** keeps ✓ disabled, as today: no name, or
  `newModelRfValidateShape` fails.
- **Zero rows.** "+" must work with no row to clone. Today it clones the
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
- Deleting the last row removes it outright; "+" is the one way to get a
  blank row (2026-09-24).

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

**2026-09-24, rung 1.** The item's diff base is `de83af9d`, main before
rung 1; the ladder's `b705245d` was the measuring tree. Chromium found two
defects on main, both in rung 1's path:
- **X threw.** `saveBand2State` is local to the Band 2 closure, while ✓
  and X call it from a later `<script>`. The `ReferenceError` left a row
  that has a pill in place and skipped ✓'s pending-flag clear. It is now
  reached through `window.newModelStageBand2State`, and X removes the row
  before staging, so the row is not staged back.
- **X is live on a blank row.** Without a standing row, a "+" row needs
  a way out besides Cancel.

**Rung 2.** The measurement answered the open question: the pill carried
the name, R, ≡, help text and width, but the preview re-read type and
bounds from the row on every rebuild. So the pill now carries the pushed
type and bounds (`data-rf-*`), and the preview reads them from there.
✓ compares the row's name, type and the bounds that type shows against the
pill, and the row's amber marker follows ✓. A pill ✓ creates starts
selected, so the column joins the preview, as the Decision says. R and ≡
stage through the window handle, so Save enables on its own.

Carried from rung 1: on main, toggling R or ≡ alone leaves Save disabled.
R's stage call sits behind a `typeof` guard that is always false, and
neither button is in the dirty-tracking click list. Also, the first
keystroke leaves ✓ off, because the inline recompute runs before the card's
pending listener. Rung 2 removes that listener.

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
3. **Close.** `spec/instruments.md`, the browser checks, a `docs/status.md`
   row and `spec-writer`.

### Definition of done

- No trailing blank row renders; "+" adds one from zero rows; Cancel's
  reload removes it.
- ✓ is enabled only for a named, valid row with no pill or with
  preview-bearing values that differ from its pill; R and ≡ never enable it.
- Band 3 renders `grid-template-columns: 2fr 3fr`.
- `spec/instruments.md` states all three.
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

- `spec/instruments.md` — Band 3: no starter row, and "+" adds one; the ✓
  row states the two purposes and the enable rule; the 2 : 3 split (Item 1).
- `guide/post_azure_todo_checklist.md` — browser checks for the ✓ enable
  rule, "+" / Cancel and the split (Item 1).
- `docs/status.md` — row when the item closes (Item 1).
