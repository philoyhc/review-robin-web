# Segment 20K — One response field per line on the reviewer surface

**Opened:** 2026-11-11 · **Theme:** an instrument can lay its response fields out one per line, each labeled beside its input, for reviews that ask for substantial answers · **Related:** `guide/segment_20L_response_row_break.md` (the alternative, written for comparison, set aside), `spec/reviewer-surface.md`, `spec/instruments.md`

**Status: closed 2026-11-12.** See `## Status` below.

## Opportunity

The reviewer surface is a table: one row per reviewee, one column per response field. That suits Review Robin's original case, a few brief data points about many reviewees. ApplyDesk's reviews are often the other shape: substantial answers about each applicant, where a long text box squeezed into a column is the wrong form (author, 2026-11-11).

## Decision

**A per-instrument layout setting: *Responses across* (today, the default) or *Responses stacked*.** With *Responses stacked* (mock-up agreed 2026-11-11):

- **The table keeps one row per reviewee.** Identity and display fields keep their columns; every response field moves into a single *Responses* cell.
- **Inside that cell, one line per response field:** the label on the left, the input on its right. No extra header rows.
- **Each field's constraint** (*1-5, steps of 1*, *0-2000 char*) sits just under its label, left-aligned with it, in the muted helper style. The summary line above the table, which lists the same constraints, is not shown in this layout.
- **The label column's width is adjustable**, like every other column (author, 2026-11-11): the operator drags it on the Instruments page preview, and the text wraps within that width. Until set, it is as wide as its longest label or constraint.
- **Two box widths, never one per field** (author, 2026-11-11). **A width is computed only where it is calculable**; any field whose width is not is a text box (author, 2026-11-11):
  - **Text boxes** (every String field, short or long, and any number field missing a bound, or a Decimal field missing its step) take the response column's width. That column — every text box at once — takes the width the table's other columns leave: it is the table's last column, and a last column has no drag handle (author, 2026-11-11), so the label column's is the layout's only one, never one per box.
  - **Compact boxes** (list fields, Integer fields with both bounds, and Decimal fields with both bounds and a step) share one computed width: the widest need among them. A number needs the whole digits of its wider bound (min or max, sign included), plus a point and as many decimal places as its step carries: min 0, max 10, step 0.25 needs `10.00`, five characters, where `numeric_column_ch_width`'s digit span counts only the bounds' own digits (author, 2026-11-11). A list needs its longest choice plus the dropdown arrow. Bounds and step are optional (`app/services/instruments/_band2.py`): a number field missing a bound, or a Decimal field with no step (its decimal places are then open), has no width to compute, so it is a text box (author, 2026-11-11). An Integer field needs no step for this: its values are whole. The compact width is never narrower than 3 digits (author, 2026-11-11: a single-digit box is too cramped to click and read) and never wider than the response column.

**Rejected:**
- **Wrapping the label column at a fixed cap** — the author prefers it adjustable like the others.
- **Header rows above each line** — the author's ask was labels beside the inputs.

## Semantics

- **One row per reviewee is what keeps this cheap.** Branching (a governed field finds its parent within the row, `closest("tr")`), the shared column sort (it moves rows of `tbody.rrw-rows`) and per-row Save all keep working unchanged.
- **Sorting by a response field goes**, since it has no column header; sorting by reviewee and by display fields stays. A sort cookie naming a response field is ignored.
- **Response-field column widths** (`rf_<id>` in `column_widths`) are kept but unused while the layout is *Responses stacked*, and the preview offers no drag handle on a response box; switching back restores them. The label column's width is a new key, `stack_label`, in the same JSON (`stack_input` is accepted too, but nothing sets it since the response column's handle went) — `set_column_widths` accepts them, `repoint_widths` already keeps keys it does not re-point, and the Settings CSV carries `column_widths` as it is.
- **Group-scoped instruments** take the same layout, one cell per group.
- **Unchanged:** answers, required and branching rules, completion counts, Validate, every CSV export, and the reviewee results and observer collation pages (read only; out of scope).
- **The setting** is a new `Instrument` column (`response_layout`, `columns` | `stacked`, default `columns`), invalidates a validated session when changed (it changes what reviewers see), writes `instrument.response_layout_set`, and round-trips in the Settings CSV as `instruments[n].response_layout`.

## Judgment calls — decided

- Per instrument, not per session: a session can mix a brief rating instrument and a long-answer one.
- **The control is a cycle chip** (`spec/ui_elements.md` §9), like the *Layout 1* / *Layout 2* chip, saved by the card's Save as that chip is (author, 2026-11-11). It labels the layout in force: *Responses across* / *Responses stacked* — proposed labels, the author to confirm at rung 3.
- **Its place:** the *Preview review instrument* heading's row: the heading, the *Layout* chip, the new *Responses* chip, then **↻ Refresh sample**, which stays last because it is hidden while the card is locked, so the chips don't shift (author, 2026-11-11).
- Two widths, not one (author, 2026-11-11): compact boxes sized to the widest need, so a 1-5 rating is not a page-wide box; one shared compact width, so the compact boxes still line up. Computed at render in the view layer: nothing stored, nothing in the Settings CSV.

## Blast radius (measured)

Taken 2026-11-11 at `0af35e9`.

| What | Count | Command |
|---|---|---|
| Reviewer surface template | 780 lines | `wc -l app/web/templates/reviewer/review_surface.html` |
| Places that render it | 3 (reviewer route, operator preview, views) | `grep -rln "review_surface.html" app --include=*.py` |
| Python files reading `column_widths` | 16 | `grep -rl "column_widths" app --include=*.py \| wc -l` |
| Templates using the shared sort | 13 | `grep -rl "data-rrw-sortable" app/web/templates \| wc -l` |
| Reviewer-surface and preview test files | 9 | `ls tests/integration tests/unit \| grep -c "reviewer_surface\|preview_surface"` |

## Status

Closed 2026-11-12. PRs **#3803 → #3807** (rungs 2–5 and a fix after the author's browser check); plan #3800, #3802.

**Intended vs done:**
- **Rung 4** wrote the layout twice: the Instruments page preview is built by its own script, not by `review_surface.html` (the plan's "one template" was wrong; corrected in the ladder).
- **Rung 5** shipped one drag handle, the label column's (`stack_label`), not two: the response column is the table's last, and a last column has none (author's browser check). `stack_input` is still accepted and honored, but nothing sets it, and the preview's next Save drops a saved one. With both saved, the Responses `<col>` holds them (Codex on #3806).
- **The width rule** counts decimal places from the step or the lower bound (steps count from it), and the sign with the wider bound's whole part.

**Reads:** one `diff-reviewer` read of the cumulative diff (`9d99fdf..`) at rung 5 found one real defect (compact number boxes stretched on the reviewer surface: `body.ui-v2 input[type=number]` outranked the compact rule, and the preview's inline style hid it) and four small ones; all fixed in rung 5, the real one pinned by a browser test on the surface. A second read of #3807 found stale comments and a saved `stack_input` with no control; both fixed there.

## PR ladder

1. **Plan** (this file).
2. **The setting.** Model, migration (`sa.text("'columns'")` default, round-trips on Postgres), the service writer with its audit event, the Settings CSV row, and tests. Nothing renders it yet.
3. **The control, scaffold-first.** The *Responses* chip on the *Preview review instrument* row, after the *Layout* chip and before **↻ Refresh sample**; wired to the setting through the card's Save; the preview still shows columns.
4. **The surface.** The *Responses stacked* rendering on the reviewer surface (with the operator's *Preview as reviewer*, one template) and on the Instruments page preview, which its own script builds, so the layout and the compact width are written twice; constraints under labels, the summary line hidden, and the compact width (a view helper with its unit tests); tests for layout, branching and Save in the stacked cell.
5. **The widths.** A drag handle on the preview's label column (the response column, the table's last, has none: author, 2026-11-11), the `stack_label` key through `set_column_widths`, and the reviewer surface honoring it. Last build rung: `diff-reviewer` reads the cumulative diff.
6. **Close.**

## Definition of done

- An instrument set to *Responses stacked* shows each response field on its own line, label and constraint on the left, on both the reviewer surface and the Instruments page preview (author's browser check).
- Branching, required marks and Save behave as in columns (`tests/integration/test_reviewer_surface_*`).
- The label and response column widths survive a reload and a Settings CSV round trip.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 20K` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- The chip's labels: *Responses across* / *Responses stacked*, as shipped (author, at the close, 2026-11-12).

## Out of scope

- The reviewee results and observer collation pages: they keep columns.
- Per-field placement within a line (that is 20L's row break).

## Doc impact

- `spec/reviewer-surface.md` — the *Responses stacked* layout under *Per-instrument table*.
- `spec/instruments.md` — the layout control and the label width.
- `spec/settings_inventory.md` — `Instrument.response_layout`; the `stack_label` and `stack_input` width keys.
- `spec/csv_contracts.md` — `instruments[n].response_layout` in the Settings CSV.
- `guide/todo_master.md` — the queue entry, deleted at close.
