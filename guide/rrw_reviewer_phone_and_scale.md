# Review Robin's reviewer surface: phones, and a scale answer (with Apply Desk)

**Investigation, 2026-11-23, against RRW `main` at `eb275acf9` (#4169).**
Written in Cordware's `guide/` while RRW's `main` was busy with Apply
Desk's AD2 series, and moved here at `31fecbe33` (author, 2026-11-23).
Both items are RRW work, and §3 is the scale's part in Apply Desk. The
mockups are `guide/rrw_scale_mockup.html` (the reviewer's side) and
`guide/rrw_scale_builder_mockup.html` (Band 3); open them in a browser.

## 1. The reviewer surface on a phone

**A plan already exists:** RRW's `guide/rrw_mobile_responsive.md`
(assessment, 2026-11-12, at `3e47ce9d`, written here first and moved).
Its verdict was "feasible, and cheap for participants", in six rungs:
1. the viewport tag on participant pages only;
2. the response table as cards under 640 px;
3. the rest of the reviewer surface;
4. the dashboard, summary, results and collation as cards;
5. 44 px touch targets;
6. a 390 px browser test as the guard.

Operator pages stay desktop-first.

**Re-checked at `eb275acf9`: none of it is built, and the plan still
holds.**
- `app/web/templates/base.html` still has no viewport tag. Only
  `error.html` has one, so every participant page still lays out at about
  980 px and shrinks to fit a phone.
- `base.html` still has its 23 `@media` rules, none of which fire on a
  phone for the same reason.
- Eight commits have touched `reviewer/` or `base.html` since `3e47ce9d`.
  None changes the plan's shape. Its rung 2 builds on 20K's *Responses
  stacked*, which is still the layout to turn into cards.
- The plan is not queued: no segment, and no row in RRW's
  `guide/todo_master.md`.

**Recommended next step:** open it as a segment, with
the plan's six rungs as its ladder. Rung 1, about 10 lines, makes every
participant page legible on its own and could land first. The scale in §2
sits well with rung 2: in a phone card a scale takes the card's full
width, which is where it is easiest to use.

## 2. A scale answer for numeric response fields

**The ask (author, 2026-11-23).** A numeric response field bound by a Min
and a Max shows as a horizontal line with a circle that drags and snaps
to each allowed value. For example, Integer 1 to 5 with Step 1 has five
snapping points. The mockup shows it on the reviewer surface (desktop and
phone) and in its variants.

**What exists today.** `app/web/templates/reviewer/_response_control.html`
renders an Integer or Decimal field as `<input type="number">`:
- `min` and `max` are native attributes;
- the step sits in `data-rs-step`, anchored at Min and checked by script;
- an Integer with a blank Step steps by 1.

The bounds are stored in the field's `validation` JSON
(`app/db/models/instrument_field.py`) and travel in the Settings CSV as
`instruments[n].response_fields[m]` attributes (`spec/csv_contracts.md`).
Nothing like a slider exists anywhere in RRW.

**Settled with the author (2026-11-23):**
1. **Opt-in per field.** No existing field changes.
2. **Up to 11 points it snaps**, a visible stop at each allowed value.
3. **Three optional labels**: start, middle and end. No other text.
4. **Numbers always shown.** A scale is always a number; a scale of words is a List.

5. **A mode, not a type.** The value a scale submits is a plain Integer or
   Decimal, and everything downstream keys off `data_type`: validation,
   branching conditions, the Settings and instrument CSVs, collation, and
   Apply Desk's result derivations. As a mode, only the reviewer's control
   and one setting change.
6. **A slide always shows its number box**, for an exact value.
7. **A scale requires a Step.** A Decimal field without one cannot be a
   scale.

**How the mockup behaves:**
- **When a field is a scale:** an Integer or Decimal field set by the
  operator to answer as a scale, with both a Min and a Max. Without both
  bounds the setting is unavailable, and the box stays.
- **Up to 11 points it snaps:** points = (Max − Min) / Step + 1. A stop
  shows at each point, numbered.
- **Snap or slide depends only on the number of points**, not the type:
  a Decimal 0 to 1 with Step 0.1 has 11 points, and snaps.
- **Past 11 points it slides.**
  - The line shows no stops, and numbers only Min, the midpoint and Max.
  - The circle follows the finger smoothly. The value still lands on the
    field's Step: a 0–100 field submits whole numbers, and a Step of 0.1
    submits tenths.
  - A readout above the circle shows the value while dragging or
    focused, and the value also sits beside the line.
  - On release the circle settles on its value's spot.
- **Answering:**
  - Unanswered until chosen: no circle, "Not answered" beside it. A native
    `<input type="range">` always holds a value, so the control is custom.
  - Click or tap a point, or drag the circle.
  - *clear* empties the answer.
  - A closed session shows the scale dimmed, and it cannot be changed.
- **Keyboard and screen readers:**
  - The arrow keys move one step, and the first press on an empty scale
    picks Min.
  - Page Up and Page Down move ten steps on a slide.
  - Home and End jump to Min and Max; Delete clears.
  - It is announced as `role="slider"` with `aria-valuetext`, for
    example "4 of 1 to 5", or "not answered".
- **What it submits:** the same value under the same name as the box,
  so the server, validation, saving and branching need no change.

**Is the slide feasible? Yes, with one honest limit.**
- **The limit:** on a phone, a 300 px line holding 101 points gives each
  point about 3 px, so a finger lands near a value, not on it. The
  readout shows where it landed, and the arrow keys fix it exactly.
- **Every slide carries a number box** (settled above). Typing moves the
  circle and sliding fills the box, for when the exact value matters (for
  example 1,450 on a 1,000–2,000 field).
- **No Step:** a scale requires one (settled above), so every scale has
  points to count.

**Choosing it in Band 3** (the builder mockup,
`guide/rrw_scale_builder_mockup.html`, reconstructed from a screenshot of
an instrument card on RRW `main` at `5f3b0ac02`):
- **The Type menu gains two entries, each just after its number type**
  (author, 2026-11-23): *Integer*, *Integer (scale)*, *Decimal*,
  *Decimal (scale)*. *Integer (scale)* saves as an Integer with the
  scale mode, and *Decimal (scale)* as a Decimal with it. They read as
  types to the operator, but nothing downstream sees a new type.
- **A scale row takes a second line** (the author's idea), under its
  Name, Type and bounds:
  - **On it:** three optional label boxes, *Start*, *Middle* and *End*,
    then, on the same line, what the reviewer will get, for example
    *5 points · snaps* or *101 points · slides, with a box*. The line
    wraps only where the screen is too narrow for it.
  - **What it leaves alone:** Min, Max and Step keep Band 3's present
    boxes and widths, and a row that is not a scale is one line, as now.
- **A row that cannot be a scale yet** keeps Band 3's existing pending
  state: the amber left edge, its reason as the tooltip and on its
  second line, and the preview keeping its last valid shape. The reasons:
  - *A scale needs a Step.*
  - *A scale needs a Min and a Max.*
  - *Max must be above Min.*
  - *Whole numbers only.*
  - *Max must be Min plus a whole number of Steps.*
- **Choosing *Integer (scale)* on a row with no Step** fills a
  Step of 1.
- **Band 2's preview** draws the scale, and its constraint line adds
  "as a scale".

**What building it would touch in RRW:**
- **A per-field setting**, the scale mode, chosen from Band 3's Type menu
  as above.
  - It is stored as new keys in the field's `validation` JSON, so no
    migration is needed: the mode, the three optional labels, and for a
    slide whether it carries the box.
  - It is exported as new `response_fields[m]` attributes in the Settings
    CSV. That changes `spec/csv_contracts.md`,
    `spec/settings_inventory.md` and `spec/instruments.md`.
- **The control itself:**
  - It is a progressive enhancement of today's number box. The server
    still renders `<input type="number">`, and a small script turns it
    into the scale, so without script the box remains (RRW's practice).
  - CSS goes in `base.html`.
  - It works in both layouts: *Responses across*, where a snapping scale
    needs about 26 px a point and a labelled one at least 260 px; and
    *Responses stacked*, at full width. It works in group mode.
- **Where else an answer shows:** the summary, results and collation
  pages show the number, and need no scale.
- **Apply Desk:** its gates set up the same two types (§3).
- **Tests:**
  - a browser test of click, drag, keyboard and clear, for both a snap
    and a slide;
  - a test that a field missing a bound stays a box;
  - Settings CSV round-trip of the new attributes.

**Size:** one item of a segment. A scaffold rung (the control on a
hard-wired field, for the author's browser check) comes first, then the
setting, then the CSV and specs.

**Open questions (author):** none left on the design. The builder
mockup's layout is the last thing for the author to look at.

## 3. Apply Desk: a scale on a gate in Review Robin

**The ask (author, 2026-11-23).** When an operator sets up a gate that
runs in Review Robin, they can choose *Integer (scale)* and *Decimal
(scale)* for a response field and set them up as Band 3 does.

**What exists today** (RRW `main` at `edf86c06c`):
- **The editor:** the Process page's gate card has a *Response fields*
  card, a row per field with *Label*, *Key* (read-only), *Type*, Min, Max
  and Step, *Required* and *Help*
  (`applydesk/templates/applydesk/operator/_process_cards.html`;
  `applydesk/spec/applications.md`, *Response fields*).
- **The menu:** Integer, Decimal, List, String (`FIELD_TYPES` in
  `applydesk/stages.py`).
- **The store:** a `gate_field` row (`GateField` in `applydesk/models.py`)
  with `type`, `min`, `max`, `step`, `options`, `required` and `help`.
- **The handoff:** the gate's Settings CSV writes each field as
  `instruments[1].response_fields[m].*` rows, with `data_type` mapped from
  `type` (`applydesk/handoff.py`).
- **What reads the type:** 18 checks in `extract.py`, `stages.py` and
  `handoff.py`, and 9 in `sample_data.py` (`grep -rn "type ==\|type in
  (\|ALLOWED\[" applydesk/*.py`). Among them, `ALLOWED` decides which
  derivations a result may use: Mean, Median, Lowest, Highest and Sum for
  a number.

**The design:**
- **The same menu as Band 3:** Integer, Integer (scale), Decimal, Decimal
  (scale), List, String.
- **Stored as the number type plus a flag.** `type` stays `integer` or
  `decimal`, so results derive, extract and hand off as now. A scale
  field's results take the number derivations.
  - `gate_field` gains a scale flag and the three optional labels.
  - That is a migration on Apply Desk's own chain (`applydesk/alembic/`).
  - Its save (`applydesk/process_save.py`) checks them.
- **Setting it up:** choosing a scale type adds Band 3's second line to
  the row:
  - the *Start*, *Middle* and *End* label boxes;
  - after them, what evaluators will get, such as *5 points · snaps*.

  Integer (scale) with no Step fills a Step of 1.
- **A field that cannot be a scale yet:**
  - its row shows Band 3's reasons (§2);
  - it is a problem on the Outline, as *No field chosen* already is;
  - the gate cannot be sent with it.
- **The handoff** writes the scale's attributes with the field's other
  rows, under the names Review Robin's Settings CSV gives them (§2).
  `data_type` stays Integer or Decimal.
- **Once the gate's session opens**, the field locks as every field does
  today, the scale with it.
- **Results come back as numbers**, so pulling them changes nothing.

**Order:**
- Review Robin's scale item lands first. Apply Desk's handoff has
  attributes to send only once Review Robin's Settings CSV reads them.
- Until then Apply Desk does not offer the two types.
- Apply Desk's part is then one item: AD6 (*Assessment in Review Robin*)
  if it is still open, else its own.

**Out of scope:** the applicant Form's questions. They are answered in
Apply Desk, not Review Robin, and have their own types.

## Doc impact of the move (done 2026-11-23)

The move applied what this section asked: a re-check line in
`guide/rrw_mobile_responsive.md`; the phone segment and the scale item
as stubs in `guide/todo_master.md`; the scale on a gate in
`applydesk/guide/todo_master.md`. `applydesk/spec/applications.md`
changes only when §3 builds, and Cordware's copies are deleted.
