# Response-field branching — design record

**Logged 2026-09-24 on the author's instruction. Not scheduled:** there is
no immediate plan to build it. This file keeps the author's rulings and
the measured cost, so the build can start from them. When it is
scheduled, it becomes a segment plan (`guide/segment_plan_template.md`);
until then its entry in `guide/deferred_consolidated.md` Part C points
here.

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

## Rulings (author, 2026-09-24)

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
- **An unanswered parent** leaves its branch unavailable.

**Governed fields**
- **Never required, in the first version.** R is unavailable inside a
  branch. That keeps every required count static; see "Cost" below.
- **When the parent's answer stops satisfying the condition,** the
  governed inputs go inactive at once on the page. On save, the server
  deletes governed values whose condition fails, so an orphaned answer
  never reaches an export.
- **Once responses exist,** on the parent or any governed field, the
  condition and the branch's membership lock. This matches today's
  type / bounds lock (`has_responses`).
- **Unselecting the parent's pill hides its whole branch.** A governed
  field can't be shown while its parent is hidden.
- **Exports:** a governed field that doesn't apply exports blank, as a
  skipped one does. The by-instrument extract's metadata block states
  each branch's condition. There is no N/A marker in the first version.

## Storage (recommended)

- A nullable `branch_parent_id` on `InstrumentResponseField`, set on
  each governed field.
- The operator and value stored once, on the parent, since every field
  in a branch shares one condition.
- The settings CSV refers to the parent by `field_key`, as data shapes
  already refer to fields.
- Session clone remaps the parent id through the `response_field_map`
  it already builds for data shapes.

## Cost (measured 2026-09-24 at `550a1126`)

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
| Save rule | `app/services/responses/_core.py`: `save_draft`, `submit`, `_apply_upserts` | Store a governed value only when its condition holds; delete ones that no longer hold | Medium |
| Required counts | `_core.py`: `_compute_missing_required`, `compute_row_completion`, `rollup_parts_from_assignments`. `app/web/routes_reviewer/_surface/_status.py`: `_group_completion`. `app/services/monitoring.py`: `_plain_instrument_parts` and `per_reviewee_coverage`, SQL with a Python parity oracle feeding Invitations, Responses and reminders | **Untouched in the first version**, because governed fields are never required. Required governed fields would make every one of these per-row | Heavy, deferred |
| Builder | `app/web/templates/operator/instruments_index.html` (Band 3 rows, the pill drag, the stager), `app/services/instruments/_band2.py` `set_band2_state` (whitelists keys; order is list index; new rows get ids mid-loop), `app/web/views/_instruments.py` (the Band 2 dict) | Branch rows and the condition row; drag limits; the parent reference resolved by row before new ids exist | Medium |
| Copies and round-trips | `app/services/session_config_io/_serialize.py` and `_apply_instrument.py` (settings CSV), `app/services/session_clone.py` (copies columns automatically, so the parent id needs remapping), `app/services/instruments/_instrument_crud.py` `replicate_instrument` (explicit kwargs) | Every copy path learns the parent and the condition | Medium |
| Exports and summaries | `app/services/extracts/by_instrument_extract.py` (metadata block), `app/services/extracts/data_shape_extract.py` (`assigned` counts every assignment × field), `app/services/extracts/entity_stats_extract.py` | Averages and counts already skip absent values. The metadata block gains the condition. The `assigned` and required-answered denominators can't tell not-applicable from skipped | Light |

## Shape of the build, when scheduled

About 7–8 PRs, as its own segment:
1. The plan.
2. Model, migration and service, with every round-trip and tests.
3. The builder as an inert scaffold, per the mock-up.
4. The builder wired.
5. The reviewer surface: inactive cells, live JS and the save rule.
6. The export metadata.
7. The close, including the `spec/rrw_functional_spec.md` amendment.

**Required governed fields** would be a later segment of their own: the
rollups, the parity oracle and the reminder counts.
