# Response-field branching — design record

**Logged 2026-09-24 on the author's instruction. Not scheduled:** there is
no immediate plan to build it. This file keeps the author's rulings and
the measured cost, so the build can start from them. When it is
scheduled, it becomes a segment plan (`guide/segment_plan_template.md`);
until then its entry in `guide/deferred_consolidated.md` Part C points
here.

Two items, built in order:
- **Item 1**: branching, with governed fields that are never required;
- **Item 2**: required governed fields.

Item 1 is built so that Item 2 relaxes a rule rather than reworks it;
"Pre-positioning for Item 2" says how.

## The idea

Basic branching between an instrument's response fields: when a field's
answer satisfies a condition, the fields its branch governs can be
answered; otherwise they are unavailable for input. On the reviewer
surface they may still show, muted and inactive.

The author's mock-up (Band 3 of the Instruments page):
- a **⑂** button on a row creates a branch below it, with one field
  inside;
- the branch opens with a condition row: *If the above* [operator]
  [value] *then show the below*, and an X that deletes the branch;
- the governed rows sit indented under a bar.

**A branch is open** for an assignment when its parent is answered and
the answer satisfies the condition. Otherwise it is **closed**.

## Item 1 — Branching, governed fields optional

### Rulings (author, 2026-09-24)

**Structure**
- **One level.** No branch inside a branch, and a field inside a branch
  cannot itself be a parent.
- **One branch per parent.** ⑂ is disabled on a field that already has
  one.
- **More than one field per branch.** A row's "+" inside a branch adds
  another field to the branch.
- **The last field in a branch can't be deleted.** Deleting the branch
  (the condition row's X) deletes every field it governs.

**Order.** A branch's fields follow their parent, in the rows and in the
Band 2 pills, and may be reordered among themselves:
- dragging the parent's pill moves the whole branch;
- a governed pill moves only within its branch;
- no outside pill can be dropped into a branch.

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
- **Unselecting the parent's pill hides its whole branch.** A governed
  field can't be shown while its parent is hidden.
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

### Cost (measured 2026-09-24 at `550a1126`)

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
| Builder | `app/web/templates/operator/instruments_index.html` (Band 3 rows, the pill drag, the stager), `app/services/instruments/_band2.py` `set_band2_state` (whitelists keys; order is list index; new rows get ids mid-loop), `app/web/views/_instruments.py` (the Band 2 dict) | Branch rows and the condition row; drag limits; the parent reference resolved by row before new ids exist | Medium |
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
4. **Hiding a parent writes `visible = False` onto its governed fields**
   rather than being computed at read time. The SQL rollups and
   `_instrument_fields_by_id` already filter on `visible`. So a hidden
   branch drops out of every count with no change in Item 1 and none in
   Item 2.
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
required child field issue"). It builds on Item 1 and needs no
migration.

**The rule:** a required governed field is required, and missing when
empty, only while its branch is open for that assignment. When the
branch is closed it is neither required nor missing, and Item 1's
invariant means it holds no value.

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
    the builder's R, `set_band2_state` and the settings-CSV importer.

**Recommendation:** route (a) for blocks 6 and 7. Keep (b) in reserve in
case a large session with required governed fields proves slow. About
**2 PRs**:
- the branch-open function wired into blocks 1–5, with 10 and 12;
- the monitoring routing, the parity oracle and the reminder tests
  (6–9).
