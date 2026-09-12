# Segment 19L — UX refinements

**Opened:** 2026-09-12 · **Theme:** small, independent operator-UI
refinements, each shipping on its own · **Related:**
`guide/new_ux_ideas.md`, `spec/ui_elements.md`, `spec/sessions_overview.md`

A log for **small UX items**. Each is self-contained, closes
independently, and is sized so that a reviewer can hold the whole change
in their head. The segment is deliberately open-ended: items are added as
they are noticed, in the shape 19J and 19K used.

**Items close independently**, so each carries its own `### Doc impact`
and `### Status`, and there is **no segment-level `## Doc impact`**.
`python3 tools/close_check.py 19L.1` reads Item 1's manifest.

**What belongs here.** A refinement to a surface that already ships:
a visual state, a copy fix, an affordance that is present but weak. Work
that adds a page, a card, or a navigation affordance is a segment of its
own and lands scaffold-first per `CLAUDE.md`. Work that is merely
*described* and not yet worth doing belongs in `guide/new_ux_ideas.md`;
an entry there graduates by becoming an item here.

---

## Item 1 — the lobby's selected row is marked only by its checkbox

### Opportunity

On the sessions lobby, ticking a row's checkbox injects an inline action
panel beneath it. **The only thing distinguishing the selected row from
its neighbours is that its own checkbox is ticked.** Measured at
`9aa1443c`, not recalled: the injected panel's `<td>` takes
`background: var(--surface-muted)`, and **no class is applied to the
source `<tr>` at any point** — the only `classList.add` in the lobby's
expander script targets an options element.

So the row-level selection signal is a ~13px control at the left edge of
a full-width row, with no fill, border, weight or rule marking the row
itself. That is adequate at the instant of clicking, and it degrades in
three conditions the lobby actively invites:

- **Bulk selection.** Two or more ticks open the `bulk-expander`, whose
  title states a **count** (*"N sessions selected"*) and never a list —
  so *which* rows are in that count is carried entirely by scattered
  checkbox states the operator must scan for.
- **A tall panel.** The expander carries name, code, deadline and tag
  fields plus an action row; it can push the source row toward or past
  the top of the viewport.
- **Selection restored without the click that created it**, where the
  operator never saw the act that produced the state.

The panel's intended action set includes **Purge and archive** and
**Delete**. Those buttons are disabled today and the expander is a
placeholder (its own comment: *"the action buttons are disabled; only the
selection-management buttons are wired"*), so this is **not a live safety
defect** — it is a weak link in a pattern that is about to carry
destructive actions, and one the app is likely to reuse. `guide/new_ux_ideas.md`
entry 1 proposes reusing exactly this fan-out for a consolidated Rosters
page holding *Clear all* and a replacing *Upload CSV*.

Fixing the marking **before** it is copied is cheaper than after, which
is the whole reason this is an item rather than a note.

### Decision

**A selected row carries a visual state of its own, at row level, legible
without reading and without the checkbox.** That much is settled. The
exact expression is **not** settled and is an open question below; what
is decided is the shape of the answer:

- it is **visual, not copy** — copy is read if it is read, and the
  operator this protects is the one moving fast enough not to finish a
  sentence (author, 2026-09-12);
- it is **on the row**, not only on the panel, so it survives the two
  being separated by scrolling;
- it works for **one row and for many**, since bulk selection is the case
  where the checkbox signal is weakest.

**The token vocabulary already models this**, which is the main reason to
expect the item to be small. `--selected-bg` (`--blue-strong` light /
`--blue-glow` dark) is the app's "you can act on this" shade, and
`--chip-selected-bg` (`--blue-pale` / `--blue-abyss`) is its **pale
companion for an element's interior** — the pair is already used together
on `.tag-chip.is-selected`, which takes the strong shade as a 2px edge
and the pale one as fill. A selected row wants the same semantic in a
row-shaped expression.

**Rejected: strengthening the copy instead** — a panel title that names
the selected sessions rather than counting them. It would help, and it is
not the ask: it fails for the fast operator, does nothing when the panel
has scrolled away from its row, and does not scale to a bulk selection of
twenty. Recorded because it is the cheaper change and someone will
propose it.

**Rejected: relying on `cursor: pointer` or hover** — the same argument
19J.7 already settled for pills and chips: invisible until the pointer is
on it, absent on touch, absent from every screenshot.

### Semantics

Per mechanism, at the boundaries. Lands in `spec/sessions_overview.md`'s
row-expander section and, if the marking becomes a reusable class, in
`spec/ui_elements.md` §10 beside the table primitives.

- **No selection.** No row carries the state; the table renders exactly
  as today.
- **One row.** That row carries it; the expander is injected beneath it.
- **Many rows.** *Every* selected row carries it, not just the last
  ticked — the bulk case is the one the item exists for.
- **Un-ticking.** The state clears with the tick, in the same event.
- **Select-all.** Every row on the page carries it. Whether that reads as
  useful signal or as noise at 50 rows is an open question below.
- **A re-render.** The lobby's table can re-render (filter, search, page
  turn). The state must either be re-derived from checkbox state on
  hydration or be absent — never stale. `spec/ui_elements.md` §10 already
  names what a re-render owes a table (`_rrwHydrateColToggles`,
  `_rrwHydrateFromCookies`); this joins that list or explains why not.
- **The reserved shade.** `tests/unit/test_reserved_shade.py` keeps
  `--blue-strong` / `--blue-glow` off anything **static**, and its own
  docstring says the scope is *the ambiguity, not the element type* — a
  `<tr>` has no dual nature, so the rule does not forbid this. But the
  guard resolves **tokens**, so whatever the expression uses must be
  checked against it rather than assumed past it.

### Judgment calls — decided

- **2026-09-12 — an item here rather than a `new_ux_ideas.md` entry.**
  It was recorded as entry 2 there first; the author's instruction to open
  this segment graduates it. The entry stays, annotated, rather than being
  deleted — the ideas file is where the reasoning was worked out.
- **2026-09-12 — the lobby first, not the roster pages.** The same
  weakness will exist anywhere the fan-out is reused, but the lobby is
  where it ships today and the only place it can be fixed without new
  scope.

### Blast radius (measured)

Taken at `9aa1443c`, before the first slice.

| What | Count | Command |
|---|---:|---|
| Lobby template lines | 850 | `wc -l < app/web/templates/operator/sessions_list.html` |
| `sessions-list-select-row` occurrences | 4 | `grep -c 'sessions-list-select-row' app/web/templates/operator/sessions_list.html` |
| Templates carrying that class | 1 | `grep -rln 'sessions-list-select-row' app/web/templates \| wc -l` |
| Tests naming the lobby's selection or expander | 1 | `grep -rln 'sessions-list-select-row\|session-expander' tests/` |
| Specs governing the lobby's table | 1 | `spec/sessions_overview.md` (of 11 files mentioning "lobby"; the rest cite it) |
| Classes applied to the source row today | **0** | `awk` over the expander script for `classList` / `insertBefore` |

**One template, one test file, one spec.** The narrowness is the case for
doing it now.

### PR ladder

One rung. This adds no page, card, or navigation affordance, so the
scaffold-first rule in `CLAUDE.md` does not apply; splitting it would
leave a half-marked row in `main`.

1. **PR 1 — the selected row carries a visual state.** Lands: the row
   marking in `sessions_list.html` and `base.html`, its re-render
   behaviour, the spec update, and a test that asserts the mechanism
   rather than the appearance (the suite has no JS runtime, so the guard
   states what it can and says so — the form 19K.2 used). **Must not
   touch:** the expander's action buttons, which are a placeholder and
   are not this item's business; the roster pages; the reserved-shade
   guard's filter.

### Definition of done

- A selected row is distinguishable from an unselected one **with the
  checkbox column covered**, in both themes.
- Every selected row is marked in a bulk selection, not only the last.
- The state is correct after a re-render, or its absence is deliberate
  and recorded.
- `tests/unit/test_reserved_shade.py` passes **unmutated** — the
  expression was checked against it, not exempted from it.
- The new guard is mutation-tested, and its limits are stated at its own
  definition.
- `.venv/bin/pytest` and `ruff check .` both pass in the agent container.
- **UI-visible: verify on the dev slot after deploy** — the suite cannot
  see a rendered colour.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19L.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

1. **What is the expression?** Candidates, none chosen: a pale fill
   (`--chip-selected-bg`'s row analogue); a left edge in `--selected-bg`,
   which echoes the chip's 2px edge without filling the row; a weight or
   rule change. Decided by rendering them, not by argument — the theme
   customizer exists for exactly this.
2. **Does select-all mark every row?** Semantically yes; at 50 rows it
   may read as noise rather than signal. Worth rendering before deciding.
3. **Does the marking become a shared primitive?** If the Rosters idea is
   ever built it needs the same thing. Naming it in `spec/ui_elements.md`
   §10 makes it reusable; leaving it lobby-local avoids designing for one
   speculative caller.
4. **Does the panel keep its count-only title?** Out of scope here, but
   the two decisions interact.

### Out of scope

- **The expander's disabled action buttons.** A placeholder, and wiring
  them is not a UX refinement.
- **Anything on the roster Setup pages.** `guide/new_ux_ideas.md` entry 1
  is gated on pilot evidence; this item must not become its first slice
  by stealth.
- **The panel's own styling**, which already carries `--surface-muted`
  and is not what is weak.

### Doc impact

- `spec/sessions_overview.md` — the row-expander section records what a
  selected row looks like, not only that ticking opens a panel (Item 1).
- `spec/ui_elements.md` — §10 gains the selected-row state if it becomes
  a named primitive, and records what a re-render owes it (Item 1).
- `guide/new_ux_ideas.md` — entry 2 annotated as graduated to 19L.1
  (Item 1).
- `docs/status.md` — row when the item closes (Item 1).
