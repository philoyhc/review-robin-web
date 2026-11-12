# Segment 20L — A row break after a response field

**Opened:** 2026-11-11 · **Theme:** an operator can end a reviewee's line after any response field, so later fields continue on a further line · **Related:** `guide/archive/segment_20K_stacked_response_layout.md` (the alternative, built and closed), `spec/reviewer-surface.md`, `spec/instruments.md`

**Status: set aside (author, 2026-11-12) — not archived.** Not needed for Review Robin, which shipped 20K; kept because a row break could serve ApplyDesk's reviews later. Picking it up starts from this plan.

## Opportunity

As 20K: the reviewer surface's one-row-per-reviewee table suits brief data points, not the substantial answers ApplyDesk's reviews ask for (author, 2026-11-11). The smallest change the author named: a "next row" after a chosen response field.

## Decision

**A per-response-field flag, *Next row after this field*.** With it set after *Score* (the author's mock-up, 2026-11-11):

- **The reviewee's first line** holds identity, display fields and the response fields up to the break, as today.
- **Each later line** carries its own column header row (*Comments* ↕) and then its inputs, spanning the response columns; the identity and display cells span all of the reviewee's lines.
- **Display fields never break** (author): the flag exists on response fields only, and a break never moves a display field.

**Rejected:**
- **Labels beside the inputs on later lines** — that is 20K's form; 20L keeps the author's mock-up. If both are built, 20L's later lines could adopt it.

## Semantics

- **Each reviewee becomes a group of rows**, which three parts of the page assume it is not:
  - **The shared column sort** (`base.html`, used by 13 templates) moves `tr`s of `tbody.rrw-rows`; it must move each reviewee's rows together — one `<tbody>` per reviewee, sorted as units — without changing the other 12 pages.
  - **Branching** finds a governed field within `closest("tr")`; it must look within the reviewee's group instead.
  - **Column widths** (`column_widths`, dragged on the Instruments page preview) assume one line of columns. A later line's fields share the response columns' total width evenly at first; per-line widths are deferred.
- **A later line's headers sort too**: sorting by *Comments* sorts the reviewee groups by that answer.
- **Group-scoped instruments** take the same treatment, one group of rows per group.
- **Unchanged:** answers, required and branching rules, completion counts, Validate, every CSV export, and the reviewee results and observer collation pages (out of scope).
- **The flag** is a new `InstrumentResponseField` column (`row_break_after`, default false), invalidates a validated session when changed, writes `instrument.response_row_break_set`, and round-trips in the Settings CSV. A break after the last response field does nothing and is not offered.

## Judgment calls — decided

- The flag lives on the field, not the instrument: the author's design breaks after a chosen field.
- **The control is a ¶ button at the end of each response field's row** in the instrument card's response-field list, just before the row's × (author, 2026-11-11). It is a *Toggle* in the row's glyph form, as the ⑂ branch button already is (`spec/operator_button_audit.md`, row #230): `btn rf-glyph` when on, `btn secondary rf-glyph` when off, `aria-pressed` either way. On means a row break after this field; it rides the card's Save like the row's other controls. The last response field's ¶ is disabled, since a break there does nothing.

## Blast radius (measured)

Taken 2026-11-11 at `0af35e9`.

| What | Count | Command |
|---|---|---|
| Reviewer surface template | 780 lines | `wc -l app/web/templates/reviewer/review_surface.html` |
| Templates using the shared sort it must change | 13 | `grep -rl "data-rrw-sortable" app/web/templates \| wc -l` |
| Branch-script row lookups to rescope | 1 | `grep -c 'closest("tr")' app/web/templates/reviewer/review_surface.html` |
| Python files reading `column_widths` | 16 | `grep -rl "column_widths" app --include=*.py \| wc -l` |
| Reviewer-surface and preview test files | 9 | `ls tests/integration tests/unit \| grep -c "reviewer_surface\|preview_surface"` |

## PR ladder

1. **Plan** (this file).
2. **The flag.** Model, migration (`sa.false()`), the service writer with its audit event, the Settings CSV row, and tests. Nothing renders it yet.
3. **The control, scaffold-first.** The ¶ toggle at the end of each response field's row, before its ×; the preview unchanged.
4. **Grouped rows in the sort.** The shared sort moves a reviewee's rows as one unit, with tests on a grouped table and the existing 12 unchanged. Lands before any page groups rows.
5. **The surface.** The broken rows on the reviewer surface and the operator preview, header rows for later lines, branching rescoped; tests for layout, sort, branching and Save across lines. Last build rung: `diff-reviewer` reads the cumulative diff.
6. **Close.**

## Definition of done

- A response field marked *Next row after this field* ends its reviewee's line; the following fields show on a further line under their own headers, on both the reviewer surface and the Instruments page preview (author's browser check).
- Sorting by any response field, on any line, keeps each reviewee's lines together; branching and Save work across lines.
- The flag survives a Settings CSV round trip.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 20L` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- Whether ApplyDesk needs it (author, when ApplyDesk's reviews are planned).
- Per-line column widths: deferred, or in this segment (author).

## Out of scope

- The reviewee results and observer collation pages: they keep one row per reviewee.
- An instrument-wide one-per-line layout (that is 20K).

## Doc impact

- `spec/reviewer-surface.md` — row breaks under *Per-instrument table*, and grouped-row sorting.
- `spec/instruments.md` — the per-field ¶ toggle.
- `spec/settings_inventory.md` — `InstrumentResponseField.row_break_after`.
- `spec/csv_contracts.md` — the flag in the Settings CSV.
- `spec/sort_by_reviewee.md` — the sort moves a reviewee's rows as one unit.
- `guide/todo_master.md` — the queue entry, deleted at close.
