# Segment 19I — Roster search and row deletion

**Opened:** 2026-09-09 · **Theme:** the four Setup roster pages —
finding rows, and removing them · **Related:**
`spec/setup_pages.md`, `guide/segment_19H_additional_refinements.md`
(the live small-refinements segment these two were too large for)

Two refinements the author raised together on 2026-09-09, both
about working with roster rows once they are in the app rather than
about getting them there. They are separate items because they close
independently and share no code; they are one segment because they
touch the same four pages and the same spec section, and landing them
apart would edit that section twice.

**Why not 19H.** That segment's admission rule is operator-facing
refinements found by using the app, which these are — but its shape is
a finite queue of small ones, five of which shipped in a day. Each of
these is multi-PR work across services, routes, templates and live
specs. Stretching 19H to hold them is how a scoped segment becomes a
standing home, which 19C already demonstrated and 19G retired.

Items close independently, so each carries its own `### Doc impact`
and `### Status` and there is no segment-level `## Doc impact`.

### Items

| Item | Covers | State |
|---|---|---|
| **19I.1** | The filter strip rationalized, and search extended to tag contents | Open — **planned** |
| **19I.2** | Delete selected rows from the Operator actions card | Open — **planned** |
| 19I.3+ | Admitted for further work on the roster pages' row-level surface. | Open — **empty** |

---

## Item 1 — The filter strip, rationalized and searching tags

### Opportunity

Two findings, reported 2026-09-09, and the second explains the first.

**The search box only matches name and handle.** All four roster
filters live in `app/web/views/_filters.py` and share one predicate,
`_matches_search` (case-insensitive substring). Tag columns hold the
data an operator most often wants to select on — a cohort, a tutor
group, a mentorship kind — and none of them is searchable. The pages
already *show* those columns and already let the operator rename them.

**At roster scale this is reachability, not convenience** (author's
motivation, 2026-09-09). The preview table is **capped at 200 rows,
lifted to 500 when a filter is applied** (`_SETUP_DEFAULT_CAP` /
`_SETUP_FILTERED_CAP`, `spec/setup_pages.md`). On a 1,000-row roster
the operator therefore *cannot see half of it*, and the only filters
that narrow the window are status — which does not partition anything
an operator thinks in — and a name they would have to already know.
**Tags are how such a roster is partitioned**: cohort, tutor group,
class. Searching them is what lets an operator bring one partition
into the window and work on it. Without it, rows past the cap are not
merely inconvenient to find; for a bulk action they are unreachable.

**And the four pages disagree about what the dropdown beside the box
is for.** Reviewers, Reviewees and Observers put a **Status** filter
there (`all` / `active` / `inactive`). Relationships puts a **Search
by** dropdown there instead (Reviewer / Reviewee — which side of the
pair the box matches) and offers no status filter at all.

`spec/setup_pages.md` records the reason: Relationships "substitutes a
**Search by** dropdown ... since a relationship has no single
status-vs-roster distinction worth a filter." **That is no longer
true, and the page itself contradicts it three times over:**
`Relationship.status` is an `active` / `inactive` column
(`app/db/models/relationship.py:64`); the page ships
`bulk-inactivate` and `bulk-reactivate` buttons that set it; and its
own "Fields with data" row surfaces a `Status` pill as soon as any row
is inactive. So the one page that can produce inactive rows is the one
page that cannot filter to them — a class-D drift (prose versus
behavior, `docs/unenforced_conventions.md`), found by eye.

### Decision

**One filter strip on all four pages: a Status dropdown, and a search
box that matches everything the page shows.**

- Relationships **gains the Status filter** the other three have,
  closing the gap above.
- `search_by` **retires.** The box matches both sides of the pair —
  each side's name and handle — instead of one side at a time.
- **Tag contents join the search** on all four: `tag_1..3` for
  reviewers, reviewees and relationships (pair context), `tag_1` for
  observers, which carries only one slot.
- **The typeahead stays people-only** (author, 2026-09-09).
  Suggestions remain `"Name (handle)"`; tags are searchable by typing,
  not by suggestion.

Retiring `search_by` is what makes pair-context tags fit. They belong
to the relationship row, not to either side, so under the old
dimension-scoped search there was no honest answer to which side they
were on — the alternative was a third dropdown value ("Pair context")
that would have made the Relationships dropdown even less like the
other three. Rationalizing removes the question instead of answering
it.

Rejected: **keeping `search_by` and adding tags as a third value.** It
preserves the inconsistency the author asked to rationalize, and it
asks the operator to know which axis a value lives on before they can
search for it — which is precisely what a search box exists to avoid.

Rejected: **tags in the typeahead.** The author's call, and it also
sidesteps a real hazard: a datalist pick whose text ends in parentheses
is exact-matched against the handle
(`_extract_filter_label_tail`), so a tag value containing parentheses
would silently be read as a handle pick.

### Decision — revised 2026-09-09

The Decision above stands except in two places, both reversed the same
day, before any code. The original text is left as written; this is
what replaces it and why.

**1. Tag values *do* join the typeahead** — reversing the fourth bullet
and the second rejection. The author's case: tags `TW01` … `TW55`, and
typing `TW2` should narrow the suggestions to the `TW2x` values.

The argument is the item's own motivation, seen from the other end.
**The typeahead is how an operator discovers what partitions exist.**
Without tag values in it, an operator must already know that `TW23` is
a value before they can filter to it — on a roster too large to read.
And because the list is built from **`all_reviewers`**, uncapped
(measured; see Blast radius), it can offer a partition whose rows are
currently past the 200/500 cap: the operator sees a group they cannot
see rows for, and picking it brings those rows into the window. That
is the reachability problem solved rather than mitigated.

The suggestions are the **distinct** tag values, not one per row — 55
options for `TW01` … `TW55`, against 1,000 for the people list.

**2. Matching is per column, not per input.** A first draft of this
revision proposed one rule — *an input that exactly equals a known
handle or tag value filters exactly, otherwise substring* — and it was
wrong in the worst available way. The author's counter-example:
typing `Ethan` should return every row whose **name** contains it. Under
that rule, if any tag value happened to be `Ethan`, the exact branch
would fire and **drop** Ethan Wong and Ethan Lim, keeping only rows
whose tag or handle is exactly `Ethan`. The same input would mean
different things on different rosters, decided by data the operator
cannot see — and it would pass every test written for it.

So the rule belongs on the column: **name and handle match by
substring; `tag_N` matches whole-value, case-insensitively; a row
matches if any column does.** `Ethan` returns the Ethans by name *and*
anyone tagged exactly `Ethan`; `Team A` no longer drags in `Team A2`,
because that is a tag and tags are whole-value.

Rejected with it: **prefix matching on tags**, the apparent middle
ground. `Team A` is a prefix of `Team A2`, so prefix reintroduces
exactly the failure whole-value removes.

**What this forces.** `_extract_filter_label_tail` fires today on *any*
input ending in `(…)`, which is the parens hazard the original
rejection named. It must fire only when the input **exactly equals one
of the labels the page offered** — data-driven in the safe direction,
since it can then only trigger on a string the app itself produced. A
tag like `Group (B)` falls through to per-column matching and
whole-value matches the tag.

### Semantics

- **Empty search** — no-op, as today.
- **Per-column matching, unioned** (revised 2026-09-09) — name and
  handle by **substring**, each `tag_N` by **whole value**,
  case-insensitive; a row matches if any column does. No weighting;
  this is a filter, not a ranking.
- **A people pick** keeps today's behavior — text of the form
  `Name (handle)` exact-matches the handle — but fires **only when the
  input exactly equals an offered label** (revised 2026-09-09), not on
  any input ending in parentheses. On Relationships the pick matches
  **either** side's handle rather than the selected side's.
- **A tag value containing parentheses** therefore matches its tag
  rather than being read as a handle pick. The edge the original
  Decision accepted is closed by the narrower trigger.
- **A partial tag value filters to nothing** unless it also hits a name
  or handle: `TW2` is not a whole tag value, so the table shows
  name/handle hits only, while the **suggestion list still narrows to
  `TW20` … `TW29`** for the operator to pick from. The list explores;
  the filter selects.
- **Observers** search one tag slot, not three. The predicate reads
  the columns the model has rather than assuming three.
- **Status on Relationships** filters on `Relationship.status`, the
  same `active` / `inactive` values `bulk_inactivate` writes.
- **Filters compose** — status and search both apply, as they do on
  the three pages that have both today.
- **Tag suggestions are the distinct values** of each slot, computed
  from the same uncapped list the people options come from. A row
  contributes its value once however many rows share it.
- **A tag slot holding free text** could contribute hundreds of
  distinct values. Tag suggestions are capped separately from people
  and are preferred when trimming: they are the partition, and there
  are normally few.
- **The two Relationships datalists merge into one.** `search_by`
  currently swaps the input's `list=` between a reviewer list and a
  reviewee list; one list carries both, plus the pair-context tag
  values. The `REVIEWERS_DATALIST_CAP` (200) applies to the people
  half.
- **A tag value equal to someone's handle** matches rows on both
  counts — a union, which is the least surprising answer and the one
  the author asked for in the `Ethan` case.

### Judgment calls — decided

- **Status filter, not a new "Pair status" label** (2026-09-09).
  Relationships rows carry the same two values under the same column
  name as the other three; a distinct label would imply a distinct
  concept.
- **Search matches the stored tag value, not the friendly label**
  (2026-09-09). The label names the column, the value is in the row;
  an operator searching "senior" is looking for rows, not for a column
  called something.
- **Tag suggestions are distinct values, not one option per row**
  (2026-09-09). 55 options against 1,000, and it makes the existing
  200-option cap stop binding for the half of the list that matters.
- **The people-pick trigger narrows to "equals an offered label"**
  (2026-09-09). It was "ends in parentheses", which cannot tell a tag
  from a label; the app knows what it offered, so let it check that
  instead of inferring from punctuation.

### Blast radius (measured)

At `6b4dc027`:

| What | Measured | Command |
|---|---|---|
| filter predicates | 4, one file (`app/web/views/_filters.py`) | `grep -n "^def filter_.*_rows" app/web/views/_filters.py` |
| call sites outside that file | 12, all in `app/`; **0 in tests** | `grep -rn "filter_reviewers_rows\|filter_reviewees_rows\|filter_observers_rows\|filter_relationships_rows" app/ tests/ --include=*.py` |
| `search_by` references | 59 in `app/`, 22 in `tests/` | `grep -rn "search_by" app/ tests/` |
| tag slots | reviewer 3, reviewee 3, relationship 3, **observer 1** | `grep -c "tag_[0-9]: Mapped" app/db/models/<m>.py` |
| specs to change | `spec/setup_pages.md` (the strip + the stale justification) | `grep -n "Search + filter strip" spec/setup_pages.md` |
| datalist source | **`all_reviewers`** — the full roster, before filter and before cap | `grep -n "reviewers_search_options(" -A 2 app/web/routes_operator/_setup_reviewers.py` |

**That last row is what made the 2026-09-09 reversal cheap**, and it
was measured before the reversal was agreed rather than assumed after.
The suggestion list is built from the complete in-memory roster, so
distinct tag values are a set comprehension over a list the route
already holds — no new query — and the list can name partitions whose
rows the cap currently hides.

**The 22 `search_by` references in tests are the item's real cost** —
retiring a parameter that three test files exercise
(`test_relationships_page_filter.py` and two others) means reading each
one to see whether it pins the dimension behavior (which goes) or the
search behavior (which stays and gains tags).

**A count that surprises, recorded before it bites:** `0` tests call
the filter predicates directly. Every existing assertion about
filtering goes through a rendered page, so the unit-level behavior of
these four functions is currently unpinned.

### PR ladder

**Amended 2026-09-09** by `### Decision — revised`: tag values now
join the suggestions, so PR 1 touches the datalists it was originally
told not to. The rung boundaries are unchanged — three roster pages,
then Relationships, then the spec — and the struck clause is left
visible rather than edited away.

1. **PR 1 — tags join the search *and the suggestions* on Reviewers,
   Reviewees, Observers.** Per-column matching (substring on name and
   handle, whole-value on `tag_N`); distinct tag values added to each
   page's datalist; the people-pick trigger narrowed to "equals an
   offered label". No strip change, no `search_by` involvement; the
   three pages whose dropdown is already a status filter. Lands the
   operator-visible value first and at the lowest risk. Must not
   touch: `filter_relationships_rows`, the templates' strip markup,
   ~~or the datalists~~ (struck 2026-09-09 — the datalists are now
   part of this rung).
2. **PR 2 — Relationships rationalized.** Status filter added,
   `search_by` retired, the two datalists merged **and carrying
   pair-context tag values**, pair-context tags joined to the search
   under the same per-column rule. Must not touch: the other three
   pages' filters, or anything in Item 2.
3. **PR 3 — the spec.** `spec/setup_pages.md`'s strip section rewritten
   to one shape for four pages, with the stale justification removed
   rather than edited around, and the per-column matching rule and the
   suggestion contract stated.

### Definition of done

- Typing a **whole** tag value into any of the four search boxes
  filters to the rows carrying it, asserted per page.
- Typing a **partial** name still returns every row whose name
  contains it, and is not narrowed by a tag that happens to equal the
  input — the `Ethan` case, asserted directly.
- Each page's suggestion list offers the **distinct** tag values
  alongside the people, including values whose rows fall past the
  display cap.
- A tag value containing parentheses matches its tag rather than being
  read as a handle pick.
- Relationships offers `All` / `Active` / `Inactive` and filters on it.
- Relationships' search matches either side's name or handle, and the
  page's own pair-context tags, with one merged datalist.
- No `search_by` remains in `app/`.
- The four predicates gain direct unit tests, since today they have
  none.
- `ruff check .` and `pytest -q -n auto` pass.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19I.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- ~~**Substring or whole-value match on tags?**~~ **Answered
  2026-09-09, by the author: whole-value on tags, substring on names,
  unioned.** The question was opened by the partition motivation and
  closed by two cases the author supplied — `TW01` … `TW55` for the
  suggestions, and `Ethan` for the matching. Both are recorded in
  `### Decision — revised 2026-09-09`, along with the one-rule proposal
  the `Ethan` case killed. The third candidate the question listed —
  a distinct-value picker — arrived instead as tag values *in the
  typeahead*, which is that idea at the size this item can carry.
- None outstanding.

### Out of scope

- **The Assignments, Invitations and Responses filter strips.** They
  share the `.filter-actions` row but not the roster search contract,
  and nobody has reported them. Named because they are four of the
  seven templates the shared class touches.
- **Ranking or highlighting matches.** A filter, not a search engine.

### Doc impact

- `spec/setup_pages.md` — the "Search + filter strip" section states
  one strip shape for all four pages: a Status filter and a search box
  matching names, handles and tag contents, with the Relationships
  `Search by` dropdown and its justification retired (PR 3).
- `docs/status.md` — row at the close (PR 3).

---

## Item 2 — Delete selected rows

### Opportunity

Each of the four roster pages can delete its **whole** roster from the
Danger Zone, and can select individual rows — the checkboxes, the
per-page bulk form and the `selected_ids` round-trip all exist, and
**eight routes already use them** (`bulk-inactivate` and
`bulk-reactivate`, on all four pages). What no page can do is delete
the rows the operator just selected. An operator who imported one
wrong row must either fix it by hand or delete the roster and
re-import it.

The gap is narrower than it looks and deeper than it looks at once.
Narrower, because selection is solved: a Delete is a third button on a
form that already posts. Deeper, because **no per-entity delete
service exists at all** — `app/services/reviewers.py` has `create`,
`update`, `bulk_inactivate`, `bulk_reactivate` and no delete. Deletion
lives only as the four `delete_all_*` functions, which funnel into one
`_delete_all` helper.

### Decision

**A `Delete` button on the Operator actions row, and a
`bulk-delete` route per page reusing `_delete_all`'s shape narrowed to
the selected ids.**

`_delete_all` already does the whole job: invalidate a validated
session, count the assignments that will cascade, `db.delete(row)` per
row against the FK cascade, one audit event, commit. A selected-rows
delete is that with `WHERE id IN (…)`. The cascade semantics are
therefore inherited rather than invented, which is the argument for
this shape over a fresh service.

**Placement and layout, per the author (2026-09-09):**

- `Delete` sits **after `Add`** on the action row, in the
  **Destructive** role (outline red, `spec/ui_elements.md` §6).
- `Add new row` shortens to **`Add`** to make room — 12 occurrences
  across the four templates.
- The **selected-count moves to a second row**, and an inline
  **confirmation checkbox** joins it there.

That last part is the design, not decoration. The count and the gate
belong together because the gate is *about* the count: "3 selected"
beside "☐ Yes, delete these" is a sentence, where a checkbox on the
button row would be a control with no stated object.

Rejected: **putting Delete in the Danger Zone** with the roster
delete. It is a selection action and every other selection action is
on this card; an operator who has just ticked three rows should not
have to find a different card, and the Danger Zone's control is
roster-wide and reads that way.

Rejected: **a `confirm()` dialog instead of the checkbox.** The repo
uses `confirm()` for discarding *unsaved edits* (19H.2), where there is
nothing to show; here there is a count, and a checkbox beside it can
say what will happen. It also keeps the destructive gate in the DOM,
where a test can see it.

### Semantics

- **Nothing selected** — Delete stays disabled, like the other
  selection buttons.
- **Selected but unconfirmed** — the route rejects with 400, the same
  shape `delete-all` uses for its missing confirm. The client also
  keeps the button disabled until the box is ticked; the server check
  is the one that counts.
- **Responses exist** — `_require_response_loss_ack`
  (`app/web/routes_operator/_shared.py:213`) applies, exactly as it
  does to `delete-all`. Deleting one reviewer discards that reviewer's
  responses as surely as deleting all of them.
- **The count can be exact here, and should be.** `delete-all` can only
  warn that responses will be lost; a selected delete knows which rows
  and can say how many responses they carry. Same gate, better
  sentence.
- **A validated session** is invalidated, via
  `lifecycle.invalidate_if_validated`, as `_delete_all` does.
- **Ids not in this session** are ignored, not errors — the same
  posture `bulk_inactivate` takes.
- **After deleting**, the operator returns to the page with the active
  filters preserved and the selection empty (the deleted rows cannot
  be re-selected).
- **Lifecycle** — gated by `_require_editable`, as every mutating
  roster route is.
- **Select-all selects the *rendered* rows**, not the whole roster:
  the JS reads `document.querySelectorAll(".reviewer-select")`, which
  is the filtered-and-capped window. That is the right behavior for
  the partition workflow Item 1 exists to enable — filter to a tag,
  select all, act — and it carries one sharp edge worth stating in the
  spec rather than discovering: **the cap can be smaller than the
  partition.** A tag matching 600 rows renders 500 (the filtered cap),
  so select-all takes 500 and a delete leaves 100 behind, having
  looked complete. The confirmation therefore states the **selected**
  count, never the match count, and the existing `Showing N of M`
  hint is what tells the operator the two differ.

### Judgment calls — decided

- **One route per page, not a shared one** (2026-09-09). It matches
  the eight bulk routes already there; a shared route would need the
  entity in the path or body and would be the only roster mutation
  shaped that way.
- **`Add`, not `+ Add` or `Add row`** (2026-09-09). The author asked
  for `Add`; the adjacent buttons are single verbs (`Edit`,
  `Activate`) and this joins them.

### Blast radius (measured)

At `6b4dc027`:

| What | Measured | Command |
|---|---|---|
| existing bulk routes to mirror | 8 (2 × 4 pages) | `grep -rn "bulk-inactivate\|bulk-reactivate" app/web/routes_operator/_setup_*.py` |
| `bulk_inactivate` service functions | 4 | `grep -rn "def bulk_inactivate" app/services/` |
| `delete_all_*` service functions | 4, one shared `_delete_all` | `grep -rn "def delete_all_" app/services/` |
| per-row delete services today | **0** | `grep -rn "def delete_reviewer\|def delete_reviewee\|def delete_observer\|def delete_relationship" app/services/` |
| `Add new row` occurrences | 12 (3 / 3 / 4 / 2) | `grep -rn "Add new row" app/web/templates/` |
| templates using `.filter-actions` | **7** — the four roster pages plus Assignments, Invitations, Responses | `grep -rln 'class="filter-actions"' app/web/templates/operator/` |

**The seven is the number to respect.** `.filter-actions` is a shared
class defined once in `base.html`; moving the selected-count onto a
second row must not reflow the three pages that are not in scope. That
argues for a new class for the second row rather than a change to
`.filter-actions` itself.

### PR ladder

1. **PR 1 — the layout, inert.** `Add new row` → `Add`; a disabled
   `Delete` in the Destructive role after it; the selected-count moved
   to its own second row with the confirmation checkbox beside it. No
   route, no service — the button does nothing. Scaffold-first per
   `CLAUDE.md`: the shape of a destructive control is worth agreeing
   before it can destroy anything, and the second row is a layout
   change across four pages that the other three `.filter-actions`
   users must not feel.
2. **PR 2 — the service.** `delete_selected` per entity, narrowing
   `_delete_all`, with its audit event registered in `EVENT_SCHEMAS`.
   Tested directly; nothing calls it yet.
3. **PR 3 — the route and the wiring.** `bulk-delete` per page, the
   confirm and response-loss gates, the button enabled. Must not
   touch: the Danger Zone, or Item 1's filters.

### Definition of done

- Selecting rows, ticking the box and pressing Delete removes exactly
  those rows and returns to the page with filters intact.
- Delete is disabled with nothing selected, and the route rejects an
  unconfirmed post.
- With responses present, the acknowledgement is required and names
  the number of responses at stake.
- The three non-roster `.filter-actions` pages render unchanged —
  asserted, not assumed.
- Each new emitter's `event_type` is registered in `EVENT_SCHEMAS`.
- Verified in a browser at both themes: the Destructive role, the
  second row, and the disabled states.
- `ruff check .` and `pytest -q -n auto` pass.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19I.2` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- **Whether Relationships needs the response-loss gate at all.**
  Deleting a relationship row removes pair context, not a response.
  Decided at PR 2, from what the cascade actually reaches — not
  assumed either way here.

### Out of scope

- **Undo.** Nothing in this app has it, and a destructive action that
  advertises reversibility it does not have is worse than one that
  does not.
- **Deleting from the preview table row itself** (a per-row ✕). The
  selection mechanism already exists and a second affordance for the
  same act would need its own justification.
- **The Danger Zone.** Untouched; roster-wide delete stays where it is.

### Doc impact

- `spec/setup_pages.md` — the action row documents `Add`, the
  Destructive `Delete`, and the second row carrying the selected-count
  and its confirmation checkbox; the delete semantics and the
  response-loss gate are stated beside the existing Danger Zone
  account (PR 1, PR 3).
- `spec/ui_elements.md` — the Destructive role's site list gains the
  roster Delete (PR 1).
- `docs/status.md` — row at the close (PR 3).
