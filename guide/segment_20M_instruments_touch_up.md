# Segment 20M — Instruments touch-up: where display fields sit

**Opened:** 2026-11-11 · **Theme:** an instrument's display fields can sit under the reviewee rather than in columns, Profile rides beside the name, and group rows sort by what they show · **Related:** `guide/archive/segment_20K_stacked_response_layout.md` (the response-side counterpart), `spec/reviewer-surface.md`, `spec/instruments.md`, `spec/sort_by_reviewee.md`

## Opportunity

20K's *Responses stacked* leaves the display fields as columns, so a stacked instrument still spends a column on each tag (Group, Team, Tutor) and one on Profile, a link the reviewer already reads as part of who the reviewee is (author's browser check, 2026-11-11). A group-scoped instrument shows its tags only as one bold line, with no other arrangement. And group rows sort by the boundary tags alone, while the cell shows every selected tag in Band 3 order: an operator who shows Tutor, or reorders the tags, sees a cell the order does not follow (`spec/sort_by_reviewee.md`, the group section).

## Decision

Four items, the mock-ups agreed 2026-11-11 (author):

1. **Profile beside the name.** When selected, Profile renders inline right after the reviewee's name in the identity cell — **View** for a web link, the muted ••• with the value on hover otherwise (`_partials/profile_value.html`, unchanged) — and takes no column, in every layout. In Band 3 it keeps its row, pinned after Email, with no ▲ ▼.
2. **A display-field layout chip**, a cycle chip (`spec/ui_elements.md` §9) right of Band 3's *Display fields* header, saved by the card's Save: *Across* (a column per field; today), *Stacked* (each field on its own line under the email, `Label: value`, the label muted), *Joined* (the values on one line under the email, comma-separated). Stacked and Joined drop the fields' columns.
3. **Group-scoped instruments** take the same chip, cycling *Joined* ↔ *Stacked* only. *Joined* is today's cell with the tag line no longer bold; *Stacked* puts the member names first, then each tag on its own `Label: value` line below them, styled as an individual row's.
4. **Group rows sort by the tags they show**: the values of the selected tag display fields, in Band 3 order, compared as a tuple (`TW01, Team 1, …` before `TW01, Team 2, …` before `TW45, …`). The Group header's asc / desc keeps reversing it.

**Rejected:**
- **Labels *Fields across* / *Fields stacked* / *Fields joined*** — too wide beside the header without widening the column (author).
- **A note on Profile's row** (*beside the name*) — the row needs none (author).
- **Keeping the bold tag line on group rows** — the group's lines take the individual styling in both modes (author).
- **Sorting group rows by boundary tags only** (today) — it disagrees with the cell as soon as a non-boundary tag is shown or the tags are reordered.

## Semantics

- **The setting** is a new `Instrument` column, `display_layout` (`across` | `stacked` | `joined`, default `across`), as 20K's `response_layout`: it invalidates a validated session when changed, writes `instrument.display_layout_set`, round-trips in the Settings CSV as `instruments[n].display_layout`, and is copied by Replicate and Duplicate. A stored value outside the cycle reads as `across`.
- **Group-scoped**: `across` reads as `joined` (a group row has no per-reviewee columns); the chip offers only *Joined* / *Stacked* and saves what it shows. Switching the instrument back to individual rows offers *Across* again, the stored value unchanged until the chip moves.
- **Sorting.** Stacked and Joined fields head no column, so they sort nothing; Reviewee still sorts by name. A sort entry naming a display field is kept but inert while the field heads no column, as 20K keeps response widths. Profile never heads a column, so a sort entry on it goes inert at Item 1.
- **Empty values**: Joined leaves an empty field out; Stacked skips its line. A group row with no selected tag keeps today's boundary-key fallback for its text and its sort.
- **Widths**: a display field's `df_<id>` width is kept but unused while it heads no column.
- **Unchanged**: the reviewee results and observer collation pages, every CSV export, Validate.

## Judgment calls — decided

- One setting serves both scopes, not a second column for group instruments: the scope already decides which values are legal.
- Profile's pin is a render rule, not a data change: Band 3 lists it after Email whatever its stored order, so the next reorder Save (which must name every unlocked field) stores it there (rung 2, 2026-11-12).
- Stacked labels use the display field's label (`display_field_label`), as the column header does.

## Blast radius (measured)

Taken 2026-11-11 at `933518e`.

| What | Count | Command |
|---|---|---|
| Templates touching Profile | 8 | `grep -rln "is_profile_link\|profile_link" app/web/templates \| wc -l` |
| Python files touching Profile | 26 | `grep -rln "profile_link" app --include=*.py \| wc -l` |
| Test files touching Profile | 37 | `grep -rln "profile_link\|is_profile_link" tests \| wc -l` |
| Files reading the group identity cell | 13 | `grep -rln "group_identity\|tag_line" app tests --include=*.py --include=*.html \| wc -l` |
| Group-row sort sites | 1 | `grep -rn "sorted(partitions)" app --include=*.py \| wc -l` |

Profile's 8 templates include the rosters, results and summary pages, which Item 1 leaves alone: only the reviewer surface and the Instruments preview move it.

## PR ladder

1. **Plan** (this file).
2. **Item 1 — Profile beside the name.** The reviewer surface and the Instruments page preview render Profile inline after the name and drop its column; Band 3 pins its row after Email with no ▲ ▼. Tests on the surface, the preview and the Band 3 row.
3. **Item 2 — the setting.** `display_layout` model, migration, the setter with its audit event and invalidation, Settings CSV, clone. Nothing renders it.
4. **Items 2–3 — the chip, scaffold-first.** The cycle chip right of Band 3's *Display fields* header, *Across* / *Stacked* / *Joined* on individual rows and *Joined* / *Stacked* on group rows, saved by the card's Save; the preview unchanged.
5. **Items 2–3 — the layouts.** Stacked and Joined on the reviewer surface and the preview, individual and group, the group tag line unbolded; tests for each.
6. **Item 4 — group sort by displayed tags.** `_collapse_group_rows` orders by the selected tag values in Band 3 order, with the boundary-key fallback; the preview's group order follows. Last build rung: `diff-reviewer` reads the cumulative diff.
7. **Close.**

## Definition of done

- Profile shows beside the reviewee's name, never as a column, on the reviewer surface and the Instruments page preview (author's browser check).
- An individual instrument shows its display fields across, stacked or joined, and a group instrument joined or stacked, as the chip says (`tests/integration/test_display_layout_surface.py`).
- Group rows sort by the selected tag values in Band 3 order, ascending and descending.
- `display_layout` survives a Settings CSV round trip and a Duplicate.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 20M` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

None.

## Out of scope

- The reviewee results and observer collation pages: they keep their display columns.
- Per-field placement (some fields across, some stacked): one layout per instrument.

## Doc impact

- `spec/reviewer-surface.md` — Profile beside the name; the Across / Stacked / Joined layouts and the group cell's two (Items 1–3).
- `spec/instruments.md` — the Band 3 *Display fields* chip; Profile's pinned row (Items 1–2).
- `spec/sort_by_reviewee.md` — group rows sort by the displayed tags in Band 3 order; stacked and joined fields and Profile sort nothing (Items 1, 2, 4).
- `spec/settings_inventory.md` — `Instrument.display_layout` (Item 2).
- `spec/csv_contracts.md` — `instruments[n].display_layout` in the Settings CSV (Item 2).
- `guide/todo_master.md` — the queue entry, deleted at close.
