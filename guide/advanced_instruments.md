# Advanced instruments — design record

Five items that rework the Instruments page's builder:
- **Item 3**: reordering on the Band 3 rows, with the response pills and ✓
  retired;
- **Item 4**: visibility edited in Band 2's card, freeing Band 3's left
  column;
- **Item 5**: display fields as a table in that column, so Band 2's pills
  retire entirely;
- **Item 1**: branching between response fields, with governed fields that
  are never required;
- **Item 2**: required governed fields.

**Logged 2026-09-24 and 2026-09-25 on the author's instruction. Being
built one item at a time:** Item 4 shipped first as 19T Item 7
(2026-09-26), ahead of Item 3 because it doesn't touch the pills, and
Item 5 as 19T Item 8 (2026-09-26), and Item 3 as 19T Item 9
(2026-09-26). Item 1 is planned as 19T Item 10 (2026-09-26); Item 2 is
not scheduled. This file keeps the
author's rulings and the measured cost, so the build can start from them.
When it is scheduled, it becomes a segment plan
(`guide/segment_plan_template.md`); until then its entry in
`guide/deferred_consolidated.md` Part C points here. It was logged as
response_field_branching.md and renamed once Item 3 widened it.

**Built in the order 3, 4, 5, 1, 2** (the author, 2026-09-25), and this file
is laid out in that order. The item numbers are the order they were
logged in, kept because other documents cite them:
- **3 before 1:** branching's order and visibility rules are simpler once
  order and on/off live only on the rows.
- **4 and 5 before 1:** Band 3's layout settles first, with display fields
  in the left column and response fields, where branches live, in the
  right. Item 5 takes the column Item 4 frees.
- **2 after 1:** Item 1 is built so that Item 2 relaxes a rule rather than
  reworks it ("Pre-positioning for Item 2").

## Item 3 — Reorder on the rows; retire the response pills

**Logged 2026-09-24 on the author's instruction. Shipped as 19T Item 9**
(closed 2026-09-26), after Items 4 and 5. The author's
2026-09-26 layout rulings — a table, full-size ▲ ▼, a ⑂ column held for
branching — are in that item's Decision.

### Opportunity

Band 2's response pills do more than their look suggests. Each carries:
1. the field's on/off (`visible`);
2. its order (a drag moves its row too, since 19T Item 1);
3. the preview column's label, width (`data-width`) and help text;
4. the R / ≡ mirrors;
5. the shape the preview shows (`data-rf-*`), pushed by ✓;
6. the saved-response count behind the "hide this field?" confirm.

Save already reads **Band 3 row order** (19T Item 1), so the rows own
order in all but the controls. The pills duplicate the rows, and
branching would have to keep the two in step.

### Decision (author, 2026-09-24)

1. **Up / down buttons on each response-field row**: two half-height
   buttons stacked vertically, together taking one button's space.
   *(Superseded 2026-09-26: full-size ▲ then ▼, like the row's other
   buttons — 19T Item 9's Decision.)* They
   sit at the end of the row, **before X**. Up is inactive on the top row,
   down on the bottom row. No drag.
2. **An "Active" checkbox at the row head**, bound to `visible`.
   Unchecking a field with saved responses keeps today's confirm. An
   inactive row stays editable **and is not dimmed**. It leaves the
   preview and the reviewer surface, exactly as an un-pinned pill does
   today.
3. **The response pills retire, and so does ✓.** The preview reads the
   rows directly and rebuilds when a row's shape is valid, so a half-typed
   bound never reaches it. This reverses 19T Item 1's ✓, and the author
   accepts that.
4. **The display-field pills are left to Item 5**, which makes them a
   table in Band 3's left column. (This decision first moved them into
   Band 3 as pills above Response fields; Item 4 superseded that on
   2026-09-25.)

**Rejected: whole-row drag.** Rows are full of inputs, so dragging a row
fights text selection and focus. Buttons work from the keyboard and are
testable.

**Each row reads** (the 2026-09-24 mock-up): Active checkbox, +, name,
type, bounds, R, ≡, the up / down stack, X.

### Semantics

- **The row carries what the pill carried**, as data on the row: label,
  width, help text, and the saved-response count. The stager already
  sends `selected`, `required`, `help_text` and `width_px` per row, so
  the server doesn't change.
- **Preview order** is the display fields, then the active response rows,
  in row order.
- **Up / down** swap a row with its neighbor and restage. Save persists
  the order.
- **A column resize in the preview** writes the width onto the row.

### Cost (measured 2026-09-24 at `266d9b5c`)

- **Template:** `app/web/templates/operator/instruments_index.html`:
  - the response-pill markup and the ✓ handler;
  - the preview builder, the stager and the drop handler, which all read
    response pills;
  - the width and help-text writers;
  - Band 3's row head and tail.
- **Server:** none. `set_band2_state` in
  `app/services/instruments/_band2.py` already takes the rows in order.
  No migration.
- **Tests:** `tests/integration/test_instrument_builder_routes.py` and
  `tests/integration/test_chip_edge.py` name the Band 2 pills.
- **Specs:** `spec/instruments.md` (its "Per-field visibility lives on
  the Band 2 pill" section, Band 3, and the ✓ row) and
  `spec/operator_button_audit.md`.
- **The Guide:** both instrument captures, the preview and
  fields-and-visibility, need retaking on the dev slot.

### Shape of the build, when scheduled

About 4 PRs:
1. Move the pill state onto rows, with the preview reading rows. The UI
   is unchanged.
2. Add the up / down stack and the Active checkbox.
3. Retire the response pills and ✓. The display pills stay until
   Item 5.
4. Close: the specs, the Guide captures and the browser checks.

## Item 4 — Visibility in Band 2's card

**Logged 2026-09-25 on the author's instruction. Built 2026-09-26 as
19T Item 7** (#2623, #2624), ahead of Item 3. The build kept entry 3's
repaint, since Save doesn't reload the locked table, and kept Band 3's
`2fr 3fr` split for Item 5 to settle; the rest is as below.

### Opportunity

Visibility is authored in Band 3's table and previewed in Band 2's "Who
can see what you wrote (other than admin)" card: one setting in two
places, which 19T Item 3 entry 3 had to patch with a live repaint.

### Decision (author, 2026-09-25, taking the recommendations)

1. **One card in Band 2's intro grid.** Locked, it is exactly the
   reviewer's card. Unlocked, it is the editor: the four clickable cells
   become cycle chips, and the fixed cells stay plain labels. It uses the
   same locked / unlocked swap as the description box beside it.
2. **The Observers row shows only while unlocked**, below a thin divider,
   with a note: "Observers are shown here for setup only; reviewers don't
   see this row."
3. **Row labels:** "You" when locked; "You (reviewer)", "Reviewees" and
   "Observers" when unlocked. The heading stays the reviewer's.
4. **Band 3's left column is freed** for Item 5's display fields.
5. **The Guide text** changes in the build; the author retakes the two
   instrument captures.

**Rejected:** keeping Band 3's table with the repaint (one setting in
two places); Observers always on the card (no longer the reviewer's view).

### Semantics

- **Visibility needs no server change.** The hidden inputs keep
  `form="dfsave-<id>"`, and `/save` reads them wherever they sit.
  Entry 3's repaint retires, because the preview is now the editor.
- **The fixed cells stay labels:** Reviewers are shown raw responses while
  the session runs, and Reviewees see "—" then. Observers' "Session
  ongoing" still cycles only between "—" and "Anonymized summaries".
- **Item 4 alone leaves Band 3's left column empty**; Item 5 fills it,
  which is why the two are built back to back.

### Cost (measured 2026-09-25 at `19db0330`)

- **Template** (`app/web/templates/operator/instruments_index.html`):
  38 lines name the visibility editor
  (`grep -c 'data-new-model-vp-\|newModelCycleVisibilityCell\|b3_mode_cycle\|b3_static_pill'`).
- **View:** the card needs the clickable / fixed state and the Observers
  row. `build_reviewer_visibility_rows` also feeds the reviewer surface,
  so its output stays as it is, and the operator's extras come from
  `band3_visibility_by_instrument`, which is already in context.
- **Server:** none.
- **Tests:** 3 files name Band 3's visibility markup.
- **Specs:**
  - `spec/instruments.md`: Band 2, and Band 3's "Visibility + Response
    fields";
  - `spec/visibility_policy.md`: the Band 3 editor and Band 2 preview
    rows.
- **The Guide:** both instrument captures and their text.

### Shape of the build, when scheduled

About 3 PRs, scaffold-first (CLAUDE.md):
1. the unlocked card's layout, inert, with Band 3's table still in place;
2. the chips and hidden inputs wired into the card, with Band 3's table
   and entry 3's repaint removed;
3. the close.

## Item 5 — Display fields as a Band 3 table

**Built 2026-09-26 as 19T Item 8** (#2626–#2629). The build went as
below, and on the author's later rulings also made the name cells and the
locked Visibility card's modes display-only pills, compacted the rows, and
re-split Band 3 to one third / two thirds.

**Logged 2026-09-25 on the author's instruction. Built third, straight
after Item 4, into the column it frees.** Split out of Item 4, which
first carried it as a half.

### Opportunity

Display fields are chosen by Band 2 pills, ordered by drag. Once Item 3
retires the response pills, they are the last pills in Band 2, and
Item 4 leaves Band 3's left column empty beside Response fields.

### Decision (author, 2026-09-25)

**A table in Band 3's left column**, one row per display field, with
**no header row**. Each row, left to right:
1. **An Active checkbox** on every row. On Name and Email it is
   disabled: it shows whether the column is showing, and the operator
   cannot change it (the author, 2026-09-25).
2. **The display field**, by its session-wide friendly label.
3. **An up arrow button** and 4. **a down arrow button**, for ordering,
   on every row except Name and Email.

**Band 3's columns become one third and two thirds** (today `2fr 3fr`,
to `1fr 2fr`): the display-field table is narrower than the Visibility
table it replaces, and Response fields gain the width (the author,
2026-09-25).

**Changes show in Band 2's preview at once**, and **persist only through
the instrument card's Save**, as every other card edit does.

**Band 2's display pills retire**, and with Item 3's response pills
already gone, Band 2's pill row goes entirely.

**Not in the table:** friendly labels (session-wide, edited on the roster
pages; the author, 2026-09-25) and column width (a resize in the
preview, as today).

### Semantics

- **Rows are the populated display sources**, as the pills are today.
- **Name and Email** are always the first two rows, with a disabled
  checkbox and no arrows (19T Item 3 entry 2). Name's is always checked.
  Email's is checked in individual unit mode and unchecked in grouped,
  since a group row has no email.
- **Active** is `visible`: unchecking drops the column from the preview
  and, once saved, from the reviewer surface. In grouped mode the fields
  a group row can't show (Email, Profile, the pair-context fields, per
  `_is_selectable_in_group`) are unchecked and disabled, as their pills
  are today.
- **Up / down** swap a row with its neighbor. Up is inactive on the row
  just below Email, and down on the last row. An inactive row keeps its
  place and can still be moved.
- **The preview repaints on every check and every move**, and each marks
  the card unsaved, as a pill toggle does today.
- **Save persists** order through `display_field_order_snapshot` and
  `reorder_display_fields`, and selection through `selected_display_keys`.
  **No server change.**
- **Preview order:** the display rows in table order, then the active
  response rows in row order.

### Cost (measured 2026-09-25 at `19db0330`)

- **Template:** about 13 lines of
  `app/web/templates/operator/instruments_index.html` read the display
  pills (`data-locked`, `data-display-field-id`, and the non-response
  pill filters): `selectedPills`, the stager, `refreshPillStates` and the
  drag handlers.
- **View:** the Band 2 field dict already carries what a row needs:
  `locked`, `pinned`, `selectable_in_group`, `reorderable`.
- **Server:** none.
- **Tests:** 2 files name the Band 2 pills
  (`tests/integration/test_instrument_builder_routes.py`,
  `tests/integration/test_chip_edge.py`).
- **The re-split:** one style attribute, pinned by one assertion in
  `tests/integration/test_instrument_builder_routes.py` and one line of
  `spec/instruments.md` (Band 3's layout).
- **Specs:** `spec/instruments.md` (the chip row) and
  `spec/ui_elements.md` ("Label or control").
- **The Guide:** the instrument captures, retaken once with Item 4's.

### Shape of the build, when scheduled

About 4 PRs, scaffold-first:
1. the table in Band 3's left column, inert, beside the live pills, with
   the columns re-split to `1fr 2fr`;
2. checkbox and arrows wired, with the preview repainting and Save
   persisting;
3. the display pills retired;
4. the close.

## Item 1 — Branching, governed fields optional

**Planned as 19T Item 10** (2026-09-26), which records what Items 7–9
changed underneath these rulings and what is still to rule on.
**Logged 2026-09-24 on the author's instruction. Built fourth, on Items
3–5.**

Basic branching between an instrument's response fields: when a field's
answer satisfies a condition, the fields its branch governs can be
answered; otherwise they are unavailable for input. On the reviewer
surface they may still show, muted and inactive.

The author's mock-up, on Item 3's rows in Band 3's right column (Items 4
and 5):
- a **⑂** button on a row creates a branch below it, with one field
  inside;
- the branch opens with a condition row: *If the above* [operator]
  [value] *then show the below*, and an X that deletes the branch;
- the governed rows sit indented under a bar.

**The layout, settled 2026-09-26** over mock-ups on Item 3's table (19T
Item 9):
- **⑂ sits just after +**, in a column of its own: outline where a branch
  can be added (an Integer, Decimal or List field with none), **selected**
  (filled, like a pressed R) on a parent with a branch, and inactive on a
  String field.
- **A branch and its parent are one ruled group**, one `<tbody>` with a
  rule under it and none inside it, so the table's rules separate groups,
  not rows.
- **The bar runs down from the parent's checkbox**, in the checkbox
  column. A governed row shifts one column right before the name: its
  checkbox sits in the + column and its + in the ⑂ column, under the
  parent's ⑂. It has no ⑂ of its own, since a branch can't nest.
- **From the field name onward every row aligns**, parent and governed
  alike, in the same boxes: name, type, bounds, R, ≡, ▲, ▼, X.
- **The condition row** starts after the bar: *If the above* [operator]
  [value] *then show the below*, with the branch's X in the X column.
- **Inside a branch** R is inactive (governed fields are never required
  here), ▲ is off on the first governed row and ▼ on the last, and ▲ ▼ on
  the parent moves the whole group.

**A branch is open** for an assignment when its parent is answered and
the answer satisfies the condition. Otherwise it is **closed**.

### Rulings (author, 2026-09-24)

*Order and the parent's on/off are restated for Item 3's rows (they were
first ruled on Band 2's pills, which Items 3 and 5 retire).*

**Structure**
- **One level.** No branch inside a branch, and a field inside a branch
  cannot itself be a parent.
- **One branch per parent.** ⑂ is disabled on a field that already has
  one.
- **More than one field per branch.** A row's "+" inside a branch adds
  another field to the branch.
- **The last field in a branch can't be deleted.** Deleting the branch
  (the condition row's X) deletes every field it governs.

**Order.** A branch's fields follow their parent in the rows, and in the
preview, and may be reordered among themselves with Item 3's up / down:
- up / down on a parent moves its whole branch;
- a governed row moves only within its branch, so up is inactive on a
  branch's first governed row and down on its last;
- no row can move into a branch.

**Conditions**
- **Integer / Decimal parents:** =, ≠, >, ≥, <, ≤ against a number.
- **List parents:** "is", taking one option or several comma-separated
  options, read as *any of*.
- **String fields can't be parents.**
- **An unanswered parent** closes its branch.

**Governed fields**
- **Never required in Item 1.** R is unavailable inside a branch, which
  keeps every required count static. Item 2 lifts this.
- **When the parent's answer stops satisfying the condition,** the
  governed inputs go inactive at once on the page. On save, the server
  deletes governed values whose branch is closed, so an orphaned answer
  never reaches an export.
- **Once responses exist,** on the parent or any governed field, the
  condition and the branch's membership lock. This matches today's
  type / bounds lock (`has_responses`).
- **Unchecking the parent's Active hides its whole branch** (Item 3's
  checkbox). A governed row's Active can't be checked while its parent's
  is off.
- **Exports:** a governed field that doesn't apply exports blank, as a
  skipped one does. The by-instrument extract's metadata block states
  each branch's condition. There is no N/A marker.

### Storage (recommended)

- A nullable `branch_parent_id` on `InstrumentResponseField`, set on
  each governed field: a self-referencing foreign key.
- The operator and value stored once, on the parent (`branch_op`,
  `branch_value`), since every field in a branch shares one condition.
- **One Alembic migration** adds the three columns. It must survive
  `ci-postgres`'s downgrade-and-upgrade round trip: drop the foreign key
  by its original name before the columns.
- **The settings CSV contract changes.** It gains
  `instruments[n].response_fields[m]` attributes for the parent's
  `field_key`, the operator and the value. The parent goes by
  `field_key`, since ids don't survive an export, as data shapes
  already refer to fields. `spec/csv_contracts.md` §3.3 changes with it.
- **Session clone** copies the columns itself, but must remap the parent
  id through the `response_field_map` it already builds.
- **Replicate instrument** copies column by column, so the new columns
  are added there by hand.

### Cost (measured 2026-09-24 at `550a1126`; the Builder row restated for Items 3–5)

**Today a cell has two states**, a `Response` row with a value or no
row, since saving a blank deletes the row. "Required" is a fixed
per-field flag, counted as a static number per instrument.
`spec/rrw_functional_spec.md` lists branching logic as out of scope, so
building it amends that line. No conditional-display concept exists to
extend. The nearest predicate code is the assignment-rule predicates,
which are string-only.

| Area | Where | What branching needs | Weight |
|---|---|---|---|
| Reviewer surface | `app/web/routes_reviewer/_surface/_context.py` (the cell builder), `app/web/templates/reviewer/review_surface.html` (the per-cell inputs), `app/web/routes_reviewer/_surface/_group_collapse.py` | The form is a reviewee × field grid, so a governed field is a column: inactive per cell, with new JS as the parent's value changes | Medium |
| Save rule | `app/services/responses/_core.py`: `save_draft`, `submit`, `_apply_upserts` | Store a governed value only when its branch is open; delete ones whose branch closed | Medium |
| Required counts | See Item 2 | **Untouched by Item 1**, since governed fields are never required | — |
| Builder | `app/web/templates/operator/instruments_index.html` (Item 3's Band 3 rows, the stager), `app/services/instruments/_band2.py` `set_band2_state` (whitelists keys; order is list index; new rows get ids mid-loop) | Branch rows and the condition row; up / down limits within a branch; the parent reference resolved by row before new ids exist | Medium |
| Copies and round-trips | `app/services/session_config_io/_serialize.py` and `_apply_instrument.py` (settings CSV), `app/services/session_clone.py`, `app/services/instruments/_instrument_crud.py` `replicate_instrument` | Every copy path learns the parent and the condition | Medium |
| Exports and summaries | `app/services/extracts/by_instrument_extract.py` (metadata block), `app/services/extracts/data_shape_extract.py` (`assigned` counts every assignment × field), `app/services/extracts/entity_stats_extract.py` | Averages and counts already skip absent values. The metadata block gains the condition. The `assigned` denominator can't tell not-applicable from skipped | Light |

### Pre-positioning for Item 2

Item 1 doesn't need any of these for itself, but each is what keeps
Item 2 a relaxation. They are cheap while Item 1 is being built, and a
rework afterwards.

1. **One branch-open function, in the service layer.** Item 1's save rule
   and the reviewer surface's inactive cells both call it. It lives in
   `app/services/responses/`, takes the parent field and the parent's
   answer, and is not written inline in a template or the view. Item 2's
   required checks and the rollups' Python path call the same function,
   so the surface, the save rule and the counts can't disagree.
2. **An "applicable fields for this assignment" helper** built on it,
   returning the fields a row can answer. Item 1 uses it to decide which
   cells are inactive. Item 2's blocks 1–5 filter their required set
   through it rather than each re-deriving the rule.
3. **The invariant "a closed branch holds no value"**, enforced in one
   writer path. Item 2 leans on it: a closed branch can't hold a stale
   answer that counts as present. Every writer goes through the same
   helper: save, submit, the group fan-out and the rehydrate import. That
   also makes Item 2's option (b), stored branch state, one more line in
   that helper rather than a hunt for writers.
4. **Unchecking a parent's Active writes `visible = False` onto its
   governed fields** rather than being computed at read time. The SQL
   rollups and `_instrument_fields_by_id` already filter on `visible`, so
   a hidden branch drops out of every count with no change in Item 1 and
   none in Item 2.
5. **`required` stays an ordinary column on governed fields**, held false
   by validation rather than by schema:
   - the builder disables R inside a branch;
   - `set_band2_state` refuses `required` on a governed field;
   - the settings-CSV importer rejects `required=true` on one with a
     clear error, not a silent drop.

   Item 2 then deletes three checks. No migration, and the CSV contract
   doesn't change again.
6. **Group-scoped instruments** are handled by the branch-open function
   from the start: the parent's answer is shared across a group row, so
   applicability is per group row. Item 2's Python rollup path then needs
   nothing new for groups.
7. **The monitoring parity fixtures gain a branched instrument in
   Item 1**, with an optional governed field. It pins that Item 1 leaves
   the counts unchanged, and Item 2 only has to flip `required` in the
   fixture.

### Shape of the build, when scheduled

About 7–8 PRs, as its own segment:
1. The plan.
2. Model, migration and service, with the branch-open function and the
   applicable-fields helper, every round-trip, and tests.
3. The builder as an inert scaffold, per the mock-up.
4. The builder wired.
5. The reviewer surface: inactive cells, live JS and the save rule's
   single writer path.
6. The export metadata.
7. The close, including the `spec/rrw_functional_spec.md` amendment.

## Item 2 — Required governed fields

**Logged 2026-09-24** (the author: "it would be interesting to solve the
required child field issue"). **Built last**, on Item 1, and needs no
migration.

**The rule:** a required governed field is required, and missing when
empty, only while its branch is open for that assignment. When the
branch is closed it is neither required nor missing, and Item 1's
invariant means it holds no value.

**And a required governed field needs a required parent** (Codex's review
of this record, 2026-09-24). An assignment with no required fields counts
as complete only when it has at least one response row: `row_count > 0`
in both rollups in `app/services/monitoring.py`. So with an optional,
unanswered parent, the branch closes, and an instrument whose only
required fields are governed could be submitted with zero rows. It would
then read as untouched: incomplete on the dashboards, and still
reminded. A required parent is answered at every submit, so there is
always a row. The builder offers R on a governed field only while its
parent's R is on, and turning the parent's R off clears it on the
branch; `set_band2_state` and the settings-CSV importer enforce the same.
**Rejected: a durable submission marker** on the assignment. It would fix
this for every instrument, but it changes what "complete" means in every
rollup and the parity oracle. A zero-row submit on an instrument with no
required fields at all already reads as untouched today; that predates
branching and stays out of scope.

**The blocks.** Everything that counts required fields as a fixed number
per instrument must count per assignment instead.

*In Python, each with the assignment's responses already in hand:*
1. **The submit gate:** `_compute_missing_required` in
   `app/services/responses/_core.py`. It judges the parent on the state
   after this save's changes, since the parent can change in the same
   submit.
2. **The per-row ✓/⚠ mark:** `compute_row_completion` in `_core.py`. It
   runs its own query for the field list, so it doesn't inherit block 1's
   fix.
3. **The reviewer page's "Required items completed N/M" pills:**
   `_group_completion` in `app/web/routes_reviewer/_surface/_status.py`.
   The total becomes a sum of each row's open required fields, instead of
   the required count × rows.
4. **The reviewer dashboard rollup:** `rollup_parts_from_assignments` in
   `_core.py`, per assignment instead of one static `required_ids`.
5. **The operator's warning when a field is made required:**
   `_count_now_missing_required` in
   `app/services/instruments/_response_fields.py`. It counts only
   assignments whose branch is open.

*In SQL, the real cost:*

6. **The reviewer-side rollup:** `_plain_instrument_parts` in
   `app/services/monitoring.py`. Missing is `required_total −
   present_required`, with `required_total` fixed per instrument.
   Evaluating the condition in SQL is the trap. The parent's answer is
   `Text`, and a numeric cast errors in Postgres on a bad value, which
   would take down the whole Responses page, while SQLite reads it as 0.
   Two ways out:
   - **(a) Route instruments with a required governed field down the
     existing Python path.** Group-scoped instruments already go that way
     (`Instrument.group_kind.is_(None)` keeps them out of the SQL). It's
     correct and cheap to build, and costs speed only for those
     instruments.
   - **(b) Store which branches are open,** as a table of (assignment,
     parent field) rows kept by Item 1's single writer path. The SQL
     joins it instead of evaluating anything. Conditions can't go stale,
     since they lock once responses exist.
7. **Reviewee-side coverage:** `per_reviewee_coverage` in
   `monitoring.py`. It's one query with no Python route today, so (a)
   means adding the reviewer side's split. It doesn't filter `visible`,
   a pinned asymmetry, but pre-positioning 4 already covers a hidden
   branch there because governed fields carry `visible = False`.
8. **The parity oracle:** `_per_reviewer_progress_python`,
   `_per_reviewee_coverage_python`, `_assignment_complete` and
   `tests/integration/test_monitoring_rollup_parity.py`. These change in
   the same PR as blocks 6–7, with the Item 1 fixture flipped to
   required.

*What follows, with tests of its own:*

9. **The Invitations and Responses pages, `summary_counts`, and the
   reminder emails** (`app/services/scheduled_events/_reminders.py`) all
   read the rollups. The test that matters: a reviewer whose only empty
   required field sits behind a closed branch is complete and is **not**
   reminded.
10. **The reviewer surface's markup:** the column header keeps its `*`,
    but a closed cell drops "(required)" from its label and its missing
    mark.
11. **Exports:** `RequiredFieldsAnswered*` counts only answers and stays
    correct. The data-shape extract's `assigned` denominator stays as
    Item 1 left it (optional).
12. **The Item 1 guards on `required`** (pre-positioning 5) are removed:
    the builder's R, `set_band2_state` and the settings-CSV importer. In
    their place goes the required-parent rule above, in the same three
    spots.

**Recommendation:** route (a) for blocks 6 and 7. Keep (b) in reserve in
case a large session with required governed fields proves slow. About
**2 PRs**, ordered so that each one deploys safely on its own (Codex's
review, 2026-09-24):
- **first**, the branch-open function wired into blocks 1–5 and 10, with
  Item 1's guards **still in place**, so no operator can yet mark a
  governed field required. The tests build required governed fields
  directly;
- **second**, the monitoring routing, the parity oracle and the reminder
  tests (6–9), **with block 12**. The guards come off in the same PR that
  teaches the rollups, so no deployed state counts a closed branch as
  missing.
