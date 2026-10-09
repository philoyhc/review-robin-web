# UX refinements

**Opened:** 2026-10-09 · **Theme:** look-and-feel refinements across the
app, one item each, closing independently · **Related:**
`spec/ui_elements.md`, `spec/instruments.md`

A standalone plan at the author's naming, not a `segment_*.md`, in the
shape of `guide/operator_pages_enhancements.md`: items are added as they
come up and each closes on its own. `tools/close_check.py` reads only
`segment_*` files, so an item's `Doc impact` is checked by hand at its
close.

New items go at the end, numbered on, in the item shape of
`guide/segment_plan_template.md`, each with its own `### Doc impact` and
`### Status`.

---

## Item 1 — Band 3 fields as chips

### Opportunity

The Instruments page's Band 3 starts every row on both sides with an
Active checkbox. On the left it sits beside a display-only pill with the
field's label, so a Display fields row is an on/off chip
(`spec/ui_elements.md` §9 type 1) split into two controls. Turning only
the left side into chips would leave the two columns looking different,
and the author ruled that the two sets should match (2026-10-09).

### Decision

Both sides become type 1 chips that wrap the existing checkbox:

- **Display fields:** the label pill becomes the chip and the checkbox
  column goes. Name and Email keep the locked chip treatment.
- **Response fields:** the Active checkbox becomes a chip labeled with
  the field's name, mirrored live from the name box, left-aligned in its
  cell and capped at about the width of a "Comments  " chip. A longer
  name ends in "…" and shows in full on hover.

**Rejected** (each mocked up in a browser on 2026-10-09):

- a "Field 1, Field 2…" position chip, which renumbers on every move and
  clashes with the "Field N" default name;
- a fixed "Active" chip, "just a glorified checkbox" (the author);
- chips on the left only, which leaves the two columns unmatched.

### Semantics

- **The checkbox stays in the DOM**, visually hidden inside a
  `label.tag-chip`, the primitive Session Home's optional-tab chips use.
  Every script that reads or writes `.checked` is unchanged, including
  the branch Active cascade and the confirm before hiding a field that
  has responses.
- **An empty name box** labels its chip with the row's placeholder
  label, the same default the name box shows muted.
- **A locked card** stays inert as today; its chips show state and
  don't respond to clicks.
- **Fields a group row can't show** keep their disabled state, shown as
  an `is-disabled` chip.

### Judgment calls — decided

- The cap is measured from the font, about 95px at the default size,
  rather than a fixed character count. (2026-10-09)
- The Min/Max/default boxes get a minimum width so the narrower name
  column doesn't clip them; the mockup clipped "2000" to "200".
  (2026-10-09)

### Blast radius (measured)

Taken 2026-10-09 at `2569876a`.

| What | Count | Command |
|---|---|---|
| Lines naming the display-field checkbox | 3 app; 1 test file, 1 spec | `grep -rn "data-new-model-df-active" app \| wc -l`; `grep -rl … tests spec` |
| Lines naming the response-field checkbox | 9 app; 6 test files | `grep -rn "data-new-model-rf-active" app \| wc -l`; `grep -rl … tests` |
| Rules and specs naming `rf-active-cell` | 1 CSS rule; 1 test file; 2 specs | `grep -rln "rf-active-cell" app tests spec` |

### PR ladder

1. **Display fields chips.** The label pill wraps the checkbox and the
   checkbox column goes. Name and Email take `is-locked`; group-hidden
   fields take `is-disabled`. A browser test toggles a field through its
   chip and checks the fill. `spec/instruments.md` (Display fields row
   list) updated.
2. **Response fields name chips.** The Active checkbox becomes a name
   chip, mirrored live, left-aligned and capped, with the bounds boxes'
   minimum width. A browser test renames a field and checks the chip
   follows, and toggles a field with responses to confirm the confirm
   still fires. `spec/instruments.md` (Response fields table) and
   `spec/ui_elements.md` (`rf-table`, `rf-active-cell`) updated. The
   item's cumulative `diff-reviewer` read runs here, from the main SHA
   before PR 1.

### Definition of done

- Both Band 3 columns start each row with a type 1 chip; no Band 3
  Active checkbox is visible.
- A test pins each side's toggle-through-chip, and the name chip's live
  mirror.
- `guide/things_to_check_in_browser.md` has a section per PR.
- `### Doc impact` current, every bullet checked by hand.
- `spec-writer` run against the doc-impact specs; flags adjudicated.
- `### Status` compacted.

### Open questions

- Should Name and Email show the plain "on" fill rather than the muted
  locked one? Decided by the author at PR 1, with the app-wide survey of
  fixed-value controls (2026-10-09) in hand.

### Out of scope

- The response row's other controls (+, ⑂, ↰ / ↳, R, ≡, ▲ ▼, X).
- Redesigning the response row so the name box moves out of it.

### Doc impact

- `spec/instruments.md` — Display fields rows are on/off chips (PR 1); the Response fields Active checkbox is a name chip (PR 2).
- `spec/ui_elements.md` — `rf-table` / `rf-active-cell` describe the name chip, its cap and the bounds minimum width (PR 2).
- `guide/things_to_check_in_browser.md` — a section per PR.
