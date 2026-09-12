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

**Segment status — 2026-09-12.** Items 1 and 2 have both closed, and
**the segment stays open** on the author's instruction. Nothing moves to
`guide/archive/` until it closes; that is the rule for an item close and
it is also what an open segment means. Two things are on record as
candidate next items rather than as loose ends: whether the archived
sessions page should carry the bracket (19L.2 open question 2, closed
undecided), and whether the bulk expander's title and Tags rows should
merge (mocked up and declined, 19L.2 Decision).

**Item 3 opened 2026-09-12**, on the author's ruling that the archived
sessions page should follow the same conventions — which reversed 19L.2's
open question 2, closed hours earlier as undecided. The other candidate,
merging the bulk expander's title and Tags rows, stays declined.

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

### Open questions — closed 2026-09-12

1. ~~**What is the expression?**~~ **Answered twice**, and stated by the
   author on 2026-09-12 in the form that now governs:

   > Edge on both selected row(s) and action row; selected row no
   > additional infill; action row blue infill; action row should not
   > host any pills.

   Four clauses, and each is load-bearing: the rail runs on the row
   **and** the panel, or there is no bracket; the row takes **no** fill,
   which is the whole of the 19L.2 fix; the panel takes the blue the row
   gave up; and the panel's freedom to wear that blue is **conditional on
   it never rendering a pill**, since the fill is `--status-info-bg`'s own
   primitive. *Recorded here as the governing statement rather than
   paraphrased — the fourth clause is a constraint on future work, not a
   description of present work, and it is the one a paraphrase would
   drop.*

   The route there is worth keeping: the author first chose edge *and*
   fill from a rendered specimen board, and 19L.2 removed the fill once
   it was seen erasing every pill on the row. *The question was right to
   insist on a rendering; one rendering was not enough, because the board
   showed the candidates against each other and not against a row's own
   contents.*
2. ~~**Does select-all mark every row?**~~ **Yes, and the fifty-row
   worry is now moot rather than answered.** It was a worry about *fill*
   — fifty tinted rows reading as a new background. 19L.2 left no fill to
   tint with, and a rail at each end of an otherwise untouched row cannot
   become the page's background. **Confirmed by the author, 2026-09-12:
   "Correct."**
3. ~~**Does the marking become a shared primitive?**~~ **No — still
   lobby-local, and now for a better-evidenced reason.** It has one
   caller. The speculative second, the Rosters index, is recorded in
   `guide/new_ux_ideas.md` with the transfer question stated rather than
   assumed: the bracket was designed for one wide row in a tall table of
   *like* things, and a Rosters index is four *unlike* things where one
   action is Clear all. Promoting it now would export a primitive to a
   page whose requirements have not been established. **Confirmed by the
   author, 2026-09-12: "Local lobby."** Note this is *not* contradicted
   by 19L.3 below: the archived page adopting the same convention is a
   second caller inside the same lobby family, not a promotion of the
   class to a general primitive.
4. ~~**Does the panel keep its count-only title?**~~ **Yes, untouched** —
   the author's words, 2026-09-12. Out of scope at planning time and
   still out of scope: 19L.2 changed the panel's fill and gave it rails,
   and deliberately did not touch its copy.

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
  (Item 1). *Honoured, then superseded: Item 2 removed entry 2 outright
  on the author's instruction — session lobby work is segment work, not
  an idea awaiting pilot evidence — so a reader following this bullet
  today will find no entry 2 to inspect. The annotation existed; the
  entry it annotated does not. Left as written rather than rewritten,
  per* never rewrite intent.
- `docs/status.md` — row when the item closes (Item 1).

---

## Item 2 — the selected row's fill hides the pills it carries

### Opportunity

19L.1 gave the selected row an edge and a fill. The fill is
`--row-selected-bg`, which resolves to `--blue-pale` / `--blue-abyss` —
**the same primitives as `--status-info-bg`**, which backs both
`.pill-count` and `.pill-info` under `body.ui-v2` (one rule, two class
names, `base.html:3238`). A lobby row carries four to six of those:
Created by, Created, Deadline, Timezone, and one per tag. On a selected
row every one of them disappears.

Measured against the five pill fills a lobby row can render — archived is
not among them, `routes_operator/_lobby.py:90` filters archived sessions
to their own page:

| light fill | count / info | Draft | Activated | Closed | vs card |
|---|---|---|---|---|---|
| `--blue-pale` (shipping) | 1.00 | 1.10 | 1.08 | 1.00 | 1.22 |
| `--gray-mist` | 1.01 | 1.11 | 1.09 | 1.01 | 1.24 |
| `--gray-soft` | 1.21 | 1.32 | 1.30 | 1.21 | 1.47 |
| `--blue-wash` | 1.12 | 1.02 | 1.04 | 1.12 | 1.09 |

WCAG 2.x relative luminance; under ~1.15 a pill has no visible boundary.
The deployed screenshot confirms it: *Local Operator*, both timestamps,
*GMT+8*, *TESTING* and *VALIDATED* all render as bare text, while *DRAFT*
keeps its amber at 1.10.

**The constraint that kills every alternative fill.** The six pale pill
fills occupy luminance 0.810–0.914; the card is 1.000. There is no room
above the band — `--blue-wash` at 0.915 lands on its ceiling, which is
why it reads as too faint — and today's `--blue-pale` sits at the band's
*floor*, so lightening it moves *through* Activated (0.876) and Draft
(0.893) rather than away from them. Only `--gray` #9ca3af clears every
pill, and at 2.54 against the card it stops reading as a highlight.

### Decision

**Remove the row fill entirely.** Put `--selected-bg` as a 6px inset
rail at **both** ends of the selected row, and carry the same pair of
rails through the injected expander row, so the selection and the panel
that acts on it read as one bracketed object.

The pill problem is then not traded but void: a selected row's pills sit
on `--surface-card` at exactly the ratios an *un*selected row's already
have. The signal moves to the rail, at **5.17** against the card in
light and **4.85** in dark — four to five times what any fill in this
palette reaches.

**`--row-selected-bg` is renamed, not retired.** Its two primitives move
to the expander panel as `--selection-panel-bg`, replacing
`--surface-muted` there. The panel holds no pills; what it holds is four
text inputs and up to seven buttons whose faces are `--surface-page`,
and against `--surface-muted` those faces score **1.09** — the same
invisibility, already shipping inside the panel, legible only by their
`--border-default` outline. On the blue they reach **1.22** light and
**1.41** dark. The token moves to the surface it suits and repairs a
defect on the way.

**Rejected — a grey fill** (`--gray-soft` / `--slate-deep`, worst pill
1.21 / 1.28). It works, and it was the recommendation until the fill was
questioned at all. It keeps a fill whose only job is to mark the row,
when a rail marks it four times better; and at 1.21 the pills are
*separated* from the row rather than contrasted against it.

**Rejected — caps.** A 2px rule above the row and below the panel closes
the bracket into a box, but costs 4px of height on selection. 19L.1
chose an inset shadow precisely so selection never reflows the table
under a pointer aimed at a destructive control. Author declined,
2026-09-12.

**Rejected — bordering the blue pill instead.** Every pill already
reserves `border: 1px solid transparent` (19J.7 rung 3), so a visible
border is free of layout cost — but it would make `.pill-count` the only
bordered pill in the app. Author declined, 2026-09-12.

**Also in scope: a missed margin reset.** `.session-expander-fields
label` (`base.html:2761`) sets display, gap, font and flex but no
margin, so `body.ui-v2 label`'s `margin: var(--space-3) 0 var(--space-1)
0` still reaches it per property. The panel's own rhythm is a 12px flex
gap; the label adds 12px more, giving **24px above the field row and
16px below**. Neither was chosen. `.exp-allow-delete` two rules away
already carries `margin: 0` with a comment naming this hazard; the field
label was missed. It is here rather than in its own item because it is
one declaration inside a rule this item is already editing, and the
author found it while inspecting this item's mockups.

**Rejected — merging the bulk panel's Tags label onto the title row.**
It would close the other half of what looked wrong (a title row
three-quarters empty beside a right-hugging field) and save a row of
height, but only the bulk expander can take it: the single expander's
fields row holds four boxes at flex-grow 3 / 2 / 2 / 3 across the full
width, leaving no half-row to lift the title into, so the two panels
would stop being structurally alike. Author declined after inspecting
both in the lobby, 2026-09-12.

### Semantics

- **No selection** — no rails anywhere, no panel. Unchanged.
- **One row** — rails on that row's first and last cells, and on the
  panel's single `colspan` cell, which is both first and last child and
  so takes both shadows in one declaration.
- **Several contiguous rows** — one tall bracket; the rows' own
  separator rules stay, because they are still distinct rows inside one
  selection.
- **Several scattered rows** — several brackets, only one containing the
  panel, which is anchored after the most recently ticked row still
  selected (`sessions_list.html:581`). Accepted as correct rather than
  worked around: two non-contiguous selections *are* two things.
- **A row whose panel is off-screen** — the rails still mark it; this is
  the case 19L.1 existed for and nothing here weakens it.
- **The archived page** — has its own expander with the same class names
  and no row marking at all. It must not pick up a blue panel and rails
  while its rows stay unmarked, so the lobby opts in by class.

### Judgment calls — decided

- **A new class, `session-expander-bracketed`, on the two lobby expander
  templates** rather than scoping by `#sessions-list-form`. Both work —
  the injected row does live inside that form — but a class names the
  intent, survives a form rename, and can be asserted. 2026-09-12.
- **The rail stays 6px**, the width 19L.1 landed after the author asked
  for 2×. Nothing measured argues for changing it, and a second width
  change in two days would be churn. 2026-09-12.
- **`--selection-panel-bg` is a new name, not a reuse of
  `--row-selected-bg` in place.** The role changed; a token that says
  *row* on a panel is how the two-tier system starts lying. Same two
  primitives, so `spec/color_tokens.md`'s count is unchanged.
  2026-09-12.
- **The panel becomes a pill-free zone by contract**, because its fill
  is `--status-info-bg`'s primitive. Recorded in the spec and guarded in
  the test rather than left to be rediscovered. 2026-09-12.

### Blast radius (measured)

Commands run at `31e2e5bd`, 2026-09-12:

- `grep -rn -- "--row-selected-bg" app/ spec/ tests/` — **6**:
  `base.html` ×3 (two declarations, one consumer), `spec/ui_elements.md`,
  `spec/sessions_overview.md`, `spec/color_tokens.md`.
- `grep -rln "session-expander" app/ spec/ tests/ docs/` — **5**:
  `base.html`, `operator/sessions_list.html`,
  `operator/sessions_archived.html`, `spec/sessions_overview.md`,
  `tests/integration/test_operator_sessions.py`.
- `grep -rln "session-row-selected" app/ spec/ tests/ docs/` — **5**:
  `base.html`, `operator/sessions_list.html`, `spec/ui_elements.md`,
  `spec/sessions_overview.md`, `tests/unit/test_lobby_row_selection.py`.
- `grep -c "session-expander-fields" app/web/templates/base.html` — **9**.

`sessions_archived.html` is the one the count would have missed: it
carries `session-expander session-expander-bulk`, the *same* classes as
the lobby's, with its own `refreshExpander()` and no row marking. A
class-free rule would have given it half a bracket.

### PR ladder

One rung. The fill removal, the rails and the panel repoint are a single
visual state — landing the rail without removing the fill would ship a
row wearing both, and removing the fill without the rail would ship a
selected row marked by nothing but its checkbox, which is the 19L.1
defect restored. The margin reset rides along because it edits a rule
inside the same block; it is separable and is called out in the PR body
so a reviewer can object to it on its own.

### Definition of done

- `body.ui-v2 tr.session-row-selected > td` no longer sets a background.
- Rails on `td:first-child` and `td:last-child`, both `--selected-bg`,
  both 6px, both inset shadows.
- `.session-expander-bracketed > td` carries both rails and
  `--selection-panel-bg`; the archived page's expander carries neither.
- `--row-selected-bg` is neither declared nor consumed in `app/`;
  the name survives only in the comment recording where it went.
- `.session-expander-fields label` declares `margin: 0`.
- `tests/unit/test_lobby_row_selection.py` asserts the new mechanism and
  states what it cannot see.
- `.venv/bin/pytest` green; `ruff check .` clean.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 19L.2` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` records intended vs done
- `docs/status.md` row added

### Open questions — closed 2026-09-12

The author ran the dev slot (local host), reported *"Session Lobby checks
out,"* and then answered each question directly.

1. ~~**Does a scattered selection read as clutter on a fifty-row
   lobby?**~~ **No — author, 2026-09-12: "It's fine."** *An earlier
   version of this block closed the question on the general pass alone
   and said so, noting that nothing established a fifty-row scattered
   selection had actually been exercised. The author's direct answer
   replaces that hedge, and the hedge is left on the record here because
   the two are different grades of evidence and the file should not
   pretend it always had the better one.*
2. ~~**Should the archived page follow?**~~ **Yes — author, 2026-09-12:
   "Archive page should follow the same conventions."** *This reverses
   what this block said hours earlier.* It had closed **undecided**, on
   the reasoning that the dev-slot pass covered the lobby and said
   nothing about a different page, so the divergence 19L.2 deliberately
   created should stand until someone looked at it. That was the right
   call on the evidence then available and the wrong answer: the author
   had a convention in mind, not a per-page verdict. **Opened as Item 3**
   rather than folded in here, because 19L.2 has closed and its Status is
   a record of what shipped.
3. ~~**Does the rail alone hold a lone selected row whose panel is
   off-screen?**~~ **No problem — author, 2026-09-12: "It's fine."**

### Out of scope

- **The archived page's expander** — see open question 2; it keeps
  `--surface-muted` and no rails.
- **Merging the bulk panel's title and Tags rows** — declined above;
  recorded here rather than in `guide/deferred_consolidated.md` because
  it was decided against, not deferred.
- **Any change to a pill token.** The point of this item is that none is
  needed.

### Status — 2026-09-12 (item closed)

**Landed as planned, in one rung.** Fill removed, rails at both ends,
the bracket carried through the panel by opt-in class, the token renamed
onto the panel, and the label margin reset. Suite 3,857 → 3,862 (the
rewritten guard went from 5 tests to 10); `ruff` clean.

**Decisions confirmed at build:**

- The opt-in class was the right call and the blast radius proved why.
  `sessions_archived.html` carries `session-expander
  session-expander-bulk` — *the same two classes as the lobby's bulk
  panel* — with its own `refreshExpander()` and no row marking at all.
  A rule on `.session-expander` would have given that page the closing
  half of a bracket with no opening half. Nothing in the plan's first
  four grep lines would have surfaced it; the fifth did.
- The rename left `spec/color_tokens.md`'s count at **107**, as a rename
  should. Confirmed by regenerating both theme pages, which report
  "107 semantic".

**A stale figure found and fixed, not introduced.** 19L.1 doubled the
edge from 3px to 6px in `base.html` and in the guard's floor, and left
**both** `spec/ui_elements.md` and `spec/sessions_overview.md` saying
3px. It survived a day because the guard asserted `>= 2` — *a range
cannot pin a figure*. Both specs are corrected here (they were being
rewritten anyway), and
`test_the_spec_and_the_stylesheet_agree_on_the_rail_width` now reads the
shipped width and requires the spec's stated width to equal it. This is
the same lesson 19L.1's own Status recorded one item earlier, arriving
by a different door: last time a test restated a wrong number, this time
a test permitted a range and let two documents drift inside it.

**Mutation testing: 8 run, 7 caught, 1 escaped and fixed.** Dropping the
right rail; the two rails set to different widths; the panel losing its
class; the row fill restored; the margin reset removed; the pill-free
warning deleted; the rail thinned back to 3px (caught by the new
spec-agreement guard, which is the drift above reproduced deliberately).

**The escape is worth naming.** Reverting the panel's background from
`--selection-panel-bg` to `--surface-muted` — undoing *half of this
item* — passed all ten tests. Every guard checked the rails; not one
checked the interior. The panel's fill is not decoration: it is where
the row's retired fill went, and it is what lifts the panel's own
inputs and buttons off 1.09 against their background. An assertion was
added and the mutation now fails. **The pattern: a test suite written
around the striking half of a change will pass the half nobody
photographed.**

**What the guards cannot do**, stated at their own definition: there is
no JavaScript runtime, so nothing proves a row *becomes* bracketed when
ticked; and nothing here sees a rendered colour. Every contrast ratio in
this item is from the plan's measurements, not from a check.

**The `spec-writer` pass found one defect, and it is mine twice over.**
`spec/sessions_overview.md` pointed at *"`spec/ui_elements.md` §6"* for
the pill-free-zone condition. §6 is Buttons; the `.session-row-selected`
entry is in §10, Layout primitives. Worse, **I repeated the same wrong
number in the brief I gave `spec-writer`** — describing the edit as "the
`.session-row-selected` table row in §6" — so the agent was handed my
error as a premise and caught it anyway, and said so. The citation now
**names the primitive instead of the section**, because a section number
is precisely the kind of reference that drifts as sections are added.

*Two items running, two stale cross-references, both of them numbers
standing in for names.* 19L.1's was a pixel width restated in three
places; this one is a section index. The repo's own habit of quoting
identifiers rather than positions is the defence, and it was not applied
here.

**Open questions 1-3 stay open**, all three being dev-slot questions —
scattered selections on a fifty-row lobby, whether the archived page
should follow, and whether two rails ~900px apart hold a lone selected
row whose panel is off-screen.

**UI-visible: verify on the dev slot after deploy.**

### Doc impact

- `spec/ui_elements.md` — the `.session-row-selected` row is rewritten:
  no fill, rails at both ends, the bracket through the panel, and the
  panel's pill-free-zone condition (Item 2).
- `spec/sessions_overview.md` — the row-expander section records the
  bracket and the panel's new fill (Item 2).
- `spec/color_tokens.md` — `--row-selected-bg` becomes
  `--selection-panel-bg`; same primitives, count unchanged (Item 2).
- `guide/new_ux_ideas.md` — entry 2 removed entirely: session lobby work
  is segment work, not an idea awaiting evidence, and the entry has been
  superseded twice over (Item 2).
- `docs/status.md` — row when the item closes (Item 2).

---

## Item 3 — the archived page did not follow the lobby out of 19L.2

### Opportunity

19L.2 gave the sessions lobby a selection bracket and deliberately kept
it off `sessions_archived.html`, whose expander carries **the same two
class names** (`session-expander session-expander-bulk`) from its own
script and whose rows have never been marked at all. An unscoped rule
would have given that page the closing half of a bracket with no opening
half, so the lobby opted in by class instead.

That was correct as a mechanism and wrong as an outcome. The two pages
are siblings — the archived page is reached from the lobby's *Go to
Archive*, renders the same table shape, and injects a bulk panel of the
same construction — and they now select differently. **The author's
ruling, 2026-09-12: *"Archive page should follow the same
conventions."***

The gap is narrow because 19L.2 built for it without meaning to: the
opt-in class exists, the CSS behind it exists, and the archived page's
`refreshExpander()` is the same shape as the lobby's, anchor and
tick-order included.

### Decision

**Adopt the lobby's convention wholesale on the archived page**: mark
selected rows with `session-row-selected` from that page's own
`refreshExpander()`, and add `session-expander-bracketed` to its
expander template.

**No new CSS.** Every rule this needs shipped in 19L.2 — the rails, the
panel fill, the opt-in class. This item is a template class and a
JavaScript function.

**Rejected — generalising the marking into a shared primitive.** Item 1's
open question 3 asked exactly this and the author answered *"Local
lobby"* on the same day. A second caller inside the same lobby family is
not the general primitive that question declined; promoting the class to
`spec/ui_elements.md` as a reusable layout primitive is still not done,
and the Rosters transfer question in `guide/new_ux_ideas.md` still stands
unanswered.

**Rejected — sharing one script between the two pages.** They have
diverged deliberately: the lobby has single *and* bulk expanders, editable
fields, a purge-options block and a duplicate action; the archived page
has one bulk panel with Unarchive and Delete. Factoring a common selection
module is a larger change than this item, and would be the kind of
abstraction-for-a-second-caller that Item 1's question 3 warned about.
Duplicating ~10 lines of marking is the cheaper mistake to unwind.

### Semantics

- **No selection** — unchanged; no rails, no panel.
- **One or more rows** — each selected row takes rails at both ends; the
  panel, anchored after the most recently ticked row still selected,
  takes both rails and `--selection-panel-bg`.
- **Select-all** — the archived page's select-all sets `checked`
  programmatically and fires no row `change` events, exactly as the
  lobby's does. The marking must therefore live in `refreshExpander()`,
  which both its handlers already call, and not on the row checkboxes.
- **The panel must render no pill.** Its fill is `--status-info-bg`'s
  primitive. The archived panel's title is `<strong>N</strong> sessions
  selected` in plain text today, and must stay that way.
- **The page's own pills are unaffected**, because the rows take no fill
  — which is the point of the 19L.2 design and the reason this item is
  safe to apply to a page whose every row carries four `.pill-count`s and
  a grey `.pill-lifecycle-archived`.

### Judgment calls — decided

- **Duplicate `markSelectedRows` rather than extract it.** Ten lines
  against a shared module between two scripts that have deliberately
  diverged. 2026-09-12.
- **The archived page's `<template>` gains the class in markup**, as the
  lobby's two did, rather than having the script add it after cloning —
  same mechanism on both pages, and greppable. 2026-09-12.

### Blast radius (measured)

Commands run at `2d51c18e`, 2026-09-12:

- `grep -n "session-expander\|refreshExpander\|archived-list-select-row" app/web/templates/operator/sessions_archived.html`
  — **13** hits in the one template: a `<template id="archived-bulk-expander">`,
  its `<tr class="session-expander session-expander-bulk">`, and a
  `refreshExpander()` with the same `currentAnchor()` / `tickOrder`
  shape as the lobby's.
- `grep -n 'class="pill' app/web/templates/operator/sessions_archived.html`
  — **9**: four `.pill-count` per row (Created by, Created, Archived,
  Timezone) plus one per tag, and a `.pill-lifecycle-archived`. None is
  inside the expander.
- `grep -rln "session-row-selected" app/ spec/ tests/` — **5**, none of
  them the archived page.
- CSS needed: **0 new rules.**

### PR ladder

One rung. A class and a function; splitting it would ship a page that
marks rows under a panel that does not close the bracket, or the reverse.

### Definition of done

- `sessions_archived.html`'s expander `<tr>` carries
  `session-expander-bracketed`.
- Its `refreshExpander()` calls a `markSelectedRows()` that clears every
  row before marking the selected set.
- No CSS added to `base.html`.
- A guard covers the archived page, and the 19L.2 guard that asserts the
  archived page does **not** carry the class is updated rather than
  deleted — its reason has changed, and a test that silently disappears
  takes its reason with it.
- `.venv/bin/pytest` green; `ruff check .` clean.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19L.3` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

1. **Does the archived page want the single-row expander too?** It has
   only a bulk panel today, so a lone selected row gets a panel headed
   *"1 sessions selected"* — a pre-existing wrinkle this item does not
   touch. Decided by the author if it grates.

### Out of scope

- **Extracting a shared selection module** — rejected above.
- **Promoting `.session-row-selected` to a general layout primitive** —
  Item 1 question 3 declined it and this item does not reopen it.
- **The archived panel's copy**, including the *"1 sessions selected"*
  plural. Pre-existing; open question 1.

### Status — 2026-09-12 (item closed)

**Landed as planned, in one rung, and it was as small as the blast
radius said.** A class on the archived page's `<template>`, a ten-line
`markSelectedRows()`, and the call to it placed before
`refreshExpander`'s empty-selection early return. **Zero new CSS rules**
— 19L.2's were already written against the opt-in class, which is the
whole reason this item was cheap.

**Decisions confirmed at build:**

- The duplication is ten lines, as estimated. The two scripts remain
  separate.
- Placing the call *before* the early return is load-bearing, not
  stylistic: after it, un-ticking the last row removes the panel and
  leaves that row still bracketed. It has its own guard.

**The 19L.2 guard was rewritten, not deleted.** It asserted that the
archived page did **not** carry the class, and that assertion is now
false. Its reason — the class is the gate — is still true, so the test
keeps its name and its explanation and flips what it expects, with the
history written into the docstring. *A guard that vanishes takes its
reason with it, and the next reader wondering why the bracket is opt-in
at all would have had nothing to read.*

**Mutation testing: 5 run, 5 caught.** The marking call removed; the
call moved after the early return; the opt-in class dropped from the
template; the clear-sweep turned into a second apply; a `.pill-count`
rendered inside the panel.

**That last mutation is the author's fourth clause made executable.**
*"Action row should not host any pills"* was stated as part of the
design in Item 1's answer; it now fails a test on **both** pages, by
scanning every `<template>` carrying the opt-in class. Before this it
lived in a comment beside the token and in prose — true in both places
and checked in neither.

**A planned doc target did not exist.** The manifest committed to "the
archived-sessions child page section" of `spec/sessions_overview.md`.
There is no such section: that page is named only in the status block
and the implementation pointers. The behaviour is recorded inline in the
lobby's own passage instead, the bullet is corrected to say so, and the
absence is stated in the spec rather than pointed at — *a draft of this
edit had written "see the archived child page below", which would have
been the same dangling cross-reference `spec-writer` caught one item
ago, reintroduced by the person who had just fixed it.*

**Not a promotion of `.session-row-selected` to a general primitive.**
Item 1's question 3 declined that on the same day (*"Local lobby"*).
Two callers in one surface family is not generality, and
`spec/ui_elements.md` now says so explicitly rather than leaving
"exactly one caller" to rot.

**The `spec-writer` pass found four things; one of them is the third
instance of this session's recurring failure, and the sharpest.**

Three were small and are fixed: `spec/sessions_overview.md`'s bullet
still attributed the mechanism to *"19L.1, restyled by 19L.2"* while its
body described 19L.3 at length; its sentence explaining *why* the bracket
is opt-in had gone elliptical once both pages carried the class, where
`spec/ui_elements.md`'s parallel sentence still said it plainly; and that
entry still opened *"a selected row on the sessions lobby"*, correcting
itself only three sentences later.

The fourth was **undeclared doc impact**. `guide/new_ux_ideas.md` carried
two clauses this item falsified — *"the archived page injects the same
panel without it"* and *"the archived sessions page — which injects the
same classes and marks no rows — still renders that way"* — and the
manifest did not name the file, so nothing would have caught it.

*Both clauses were written four commits earlier, by me, in a commit
titled "bring entry 1's account of the lobby up to date" — whose entire
purpose was fixing exactly this kind of staleness in exactly this file.*
They were true when written and false two items later. **The lesson is
not "check that file"; it is that a statement of present fact about
another surface acquires a maintenance obligation the moment it is
written, and the manifest is the only place that obligation can be
recorded.** The bullet is added above, after the fact, which is the
weaker version of having declared it.

**UI-visible: verify on the dev slot after deploy** — the suite has no
JavaScript runtime and cannot see a rendered colour.

### Doc impact

- `spec/sessions_overview.md` — the note saying the archived page
  deliberately does *not* carry the opt-in class is corrected, and its
  selection behaviour recorded (Item 3). *Planned as "the archived child
  page section"; there is no such section in this spec — the page is
  named only in the status block and the implementation pointers — so the
  behaviour is stated inline in the lobby's own passage and the absence
  of a section is said out loud rather than pointed at.*
- `spec/ui_elements.md` — the `.session-row-selected` entry's "lobby-local"
  wording gains its second caller, without promoting it to a primitive
  (Item 3).
- `guide/new_ux_ideas.md` — entry 1's account of the lobby expander said
  the archived page injects the panel *without* the opt-in class and
  marks no rows. Both clauses corrected (Item 3). *Not named at planning
  time; added when `spec-writer` found them — see `Status`.*
- `docs/status.md` — row when the item closes (Item 3).
