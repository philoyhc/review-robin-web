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

> **Two errors in the paragraph above, left standing per *never rewrite
> intent* and corrected in `Status`.** (1) The edge is **1px**, not 2px —
> the rule has always been `inset 0 0 0 1px`; the figure was wrong in
> `base.html` and `spec/ui_elements.md` from 19J.7 and this plan
> inherited it. (2) The pair is **not** "used together on
> `.tag-chip.is-selected`": the edge sits on the bare `.tag-chip`
> selector and means *clickable*, carried selected or not, with only the
> fill gated on `.is-selected`. The reasoning the Decision rests on
> survives both — the vocabulary does model a strong edge plus a pale
> interior — but it is a resemblance, not a reuse. *Annotated here on
> 2026-09-12 because the correction had reached the specs, the test and
> `base.html` and stopped one document short: the failure this plan's own
> Status describes, happening to the plan.*

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

### Status — 2026-09-12 (item closed)

**Built as candidate D — edge *and* fill**, chosen by the author from a
rendered specimen board rather than from the plan's prose. The board
showed all four candidates in both the single and the bulk case, in both
themes, using the app's real tokens; candidate D was not one of the
plan's three, and was added to the board because it is what
`.tag-chip.is-selected` already does. *Open question 1 was answered by
producing the thing it asked for.*

**One spec the plan did not name.** `--chip-selected-bg` resolves to the
right primitives, and reusing it on a `<tr>` would have shipped without a
new token. It would also have meant a row silently inheriting a repoint
aimed at chips, which is the drift the two-tier system exists to stop. So
`--row-selected-bg` was added as its own role — same primitives today,
its own name — and `spec/color_tokens.md` gains a Tier-2 row and a
corrected count. The `Doc impact` manifest gained the bullet; recorded
here per *undeclared spec impact is the failure this section prevents*.

**Two of this repository's own guards made the change correct rather than
merely plausible**, both from 19K.7:

- the Tier-2 catalogue check failed the moment the token landed and again
  when only the row was added, because `spec/color_tokens.md` also states
  **80 primitives · 106 semantic** in prose — now 107. A catalogue that
  counts itself is harder to leave half-updated than one that only lists.
- the generated-tools check failed because `theme_customizer.html` and
  `theme_preview.html` are generated *from* `base.html`; both regenerated.
  A new token is invisible in the customizer until they are.

**The reserved-shade guard passed unmutated, which was the plan's
requirement, and the reason is worth keeping.** Reading it rather than
assuming: its selector filter is `pill` / `chip` / `btn-icon`, because its
subject is elements with a **dual nature** — the same shape that states a
fact in one place and offers a click in another. A `<tr>` has one nature,
and a selected row is precisely the thing the panel's actions will act
on, which is what `--selected-bg` means. So the shade is *correct* here,
not tolerated.

**Verified in Chromium, not asserted.** The suite has no JS runtime, so
the rendered page was driven directly through eight paths: at rest,
single tick, bulk tick, un-tick one, un-tick all, select-all, clear
select-all, and the computed style — `rgb(37, 99, 235) 3px inset` over
`rgb(219, 234, 254)`, which is `--selected-bg` over `--row-selected-bg`
exactly. Two further paths were driven because a code comment claimed
them: the expander's **Unselect all** (3 marked → 0) and **Unselect
others** (2 → 1). *A claim in a comment is a claim.*

**Select-all is the path that justified the placement.** It sets
`checked` programmatically and fires no row change events, so a listener
on the checkboxes would have missed it entirely — marking lives in
`refreshExpander()`, the one funnel every path already meets.

**No hydration, and that is a finding rather than a gap.** The plan's
Semantics asked what a re-render owes this state. Measured: the tag
filter and search set `style.display` rather than re-rendering, so a
filtered row keeps both its tick and its mark; and selection is not
persisted — the lobby's only `localStorage` key is
`rrw-lobby-tag-filter`. A server re-render returns unchecked boxes and an
unmarked table. Recorded in `spec/sessions_overview.md` with the
condition that would change it.

**8 mutations, 8 caught.** Marking removed from the funnel; clear/apply
order swapped; fill dropped; edge turned into a border; the dark token
declaration dropped; the dark token pointed at the light primitive; the
edge thinned below the chip's 2px; the fill repointed to
`--chip-selected-bg`. The guard states at its own definition what it
cannot do — it holds the mechanism, never that a row *becomes* marked.

**The `spec-writer` pass found one overstatement of mine and one false
number I had helped entrench.** Both are corrected above rather than
noted.

*Overstated:* the edge-and-fill pairing was described as "the pair
`.tag-chip.is-selected` already uses". It is not. A chip's edge sits on
the **bare `.tag-chip` selector** — every chip carries it, selected or
not, because that edge means *clickable*, which is 19J.7's entire point
— and only the fill is gated on `.is-selected`. The row gates **both**
halves on selection, since a row is not clickable by being a row. The
rendered look is the same; the mechanism is not, and "already uses"
claimed a reuse that does not exist.

*False, and older than this item:* **a chip's edge is 1px, not 2px.**
The rule has always been `inset 0 0 0 1px`, while `base.html`'s comment
and `spec/ui_elements.md` have both said 2px since 19J.7. This item's
first version of `test_the_row_style_carries_both_an_edge_and_a_fill`
then justified its own `>= 2` floor as *"the 2px a selected chip
carries"* — **restating the wrong figure in a third place, inside a test,
where it reads as verified.** The floor survives on its own reason (a
hairline on a full-width row reads as one of the table's rules, not as a
state); the premise did not. Both pre-existing statements corrected with
the discrepancy named, in a spec this manifest already commits to.

*The pattern is the one this repository keeps recording*, and this is its
sharpest instance yet: a number was wrong in two places, and the act of
writing a **new guard** put it in a third. A test that cites a figure it
does not check is not a check of that figure.

**Open questions 2 and 3 are left open, deliberately.** Whether
select-all marking fifty rows reads as signal or as a new background
wants a fifty-row render, which this item did not need. Whether the
marking becomes a shared primitive is answered *not yet*: it has one
caller, and the second is a speculative page in an ideas file.
Open question 4 (the panel's count-only title) was out of scope and
stays so.

**UI-visible: verify on the dev slot after deploy** — the suite cannot
see a rendered colour, and Chromium here rendered a file rather than the
deployed page.

### Doc impact

- `spec/sessions_overview.md` — the row-expander section records what a
  selected row looks like, not only that ticking opens a panel (Item 1).
- `spec/ui_elements.md` — §10 gains the selected-row state if it becomes
  a named primitive, and records what a re-render owes it (Item 1).
- `spec/color_tokens.md` — the Tier-2 catalogue gains `--row-selected-bg`
  and its count is corrected. Not named at planning time; added when the
  build chose a new role over reusing the chip's token (Item 1).
- `guide/new_ux_ideas.md` — entry 2 annotated as graduated to 19L.1
  (Item 1).
- `docs/status.md` — row when the item closes (Item 1).
