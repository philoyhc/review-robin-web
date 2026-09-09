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
| **19I.1** | The filter strip rationalized, and search extended to tag contents | **Closed 2026-09-09** (3 PRs) |
| **19I.2** | Delete selected rows from the Operator actions card | **Closed 2026-09-09** (3 PRs, scaffold-first) |
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

### Status

**2026-09-09 — PR 1 landed** (Reviewers, Reviewees, Observers). Rungs
2 and 3 are open; the item does not close until the spec lands with
PR 3, so `close_check 19I.1` fails C3 until then and that is the
expected reading, not a drop.

**The ladder held.** Per-column matching, distinct tag values in each
page's suggestions, and the narrowed pick trigger, all inside the
three pages whose dropdown is already a status filter.
`filter_relationships_rows` and the templates' strip markup are
untouched — checked, not assumed: the diff contains no relationship
line and no template.

**A mutant proved nothing and had to be rebuilt.** The `Ethan` test
exists to reject one specific design — an *input-level* rule where an
input matching some tag value flips the whole search into exact mode.
The first mutant written against it merely reordered the union inside
`_matches_row` (tags checked before names), which is the same function
either way, and all fourteen tests passed. That is a mutant that
tested the test's patience rather than its substance. Rebuilt at the
right level — the filter deciding, before the row loop, whether the
needle is a known tag value and restricting to exact matches if so —
and the `Ethan` test fails, as it must.

**Fourth time in two days that an assertion or a mutant addressed the
wrong text**: 19H.1's wiring assertion satisfied by a JS selector
string, 19H.3's forbidding a substring that appeared in a comment,
19H.5's test premise that could not happen, and now this. The common
shape is that all four looked right when read and only failed when
run. Nothing here is a new lesson; the frequency is the finding.

**Decisions confirmed at build:**

- **The pick path checks the uncapped label set** (2026-09-09). The
  offered list is capped at 200 people, but an operator typing a label
  from memory is doing the same thing as picking it, so the check runs
  against every label the roster could have produced.
- **Tag options lead the list** (2026-09-09). Browsers filter a
  `<datalist>` and preserve document order, so leading with tags keeps
  the partition values visible when both halves match — and keeps them
  clear of the people cap entirely.

**Measured after:** the suite went 3054 → 3071 (14 unit tests on
predicates that had none, 3 page-level).

**2026-09-09 — PR 2 landed** (Relationships). The page now carries the
same strip as the other three: a Status dropdown, one search box
matching both sides of the pair plus the row's own pair-context tags,
one suggestion list with tags ahead of people. Rung 3 (the spec) is
what closes the item.

**The ladder held again.** No line of the other three pages' filters
or templates is in the diff, and nothing from Item 2 is. The shared
helpers PR 1 added (`_matches_row`, `_picked_label_handle`,
`_distinct_tag_options`) took the fourth page with no change, which is
the return on having cut them as helpers rather than inlining them
three times.

**The 22 `search_by` test references, resolved.** Counted per file
rather than in aggregate: 8 in `test_assignments_page_generate.py`,
which keeps its own side-picker and is Out of scope; 12 in
`test_relationships_page_filter.py`; 2 in
`test_relationships_page_mutate.py` (one bulk-redirect filter-carry,
kept and now carrying `status`). Of the filter file's 9 tests, one
pinned the dropdown markup and one pinned the `list=`-swapping script
— both gone with the mechanisms they described; one pinned that the
reviewer dimension does *not* match a reviewee, and is inverted, since
matching both sides is the point of the rung; the rest kept their
behavior and lost the parameter. 9 tests became 13.

**`RELATIONSHIPS_SEARCH_BY_OPTIONS` deleted, not kept with a
retirement comment.** The first cut left it in place, commented as
retired. Checked rather than assumed: nothing in `app/`, `tests/`,
`spec/` or `docs/` referenced it any more, and it was no longer
exported from `app/web/views/__init__.py`, so what remained was a
public-looking constant whose only reader was its own epitaph. The
history it carried is in the comment above `RELATIONSHIPS_STATUS_OPTIONS`,
where a reader of the live code will meet it.

**Six mutants, six kills** — one side matched instead of two; tags by
substring; the status filter skipped; the suggestion map keyed on
`person.id` alone; the Clear link ignoring status; people offered
ahead of tags. The `person.id` one is the judgment call below, and it
is the mutant most likely to have shipped: both roster tables start at
`id` 1, so a single-keyed map silently drops one side of every early
pair, and only a test seeding a colliding pair sees it.

**Decisions confirmed at build:**

- **The suggestion map is keyed `(dimension, person.id)`**
  (2026-09-09). A reviewer and a reviewee can share a primary key;
  keyed on the id alone, one label overwrites the other.
- **The Clear link counts status as a filter** (2026-09-09). Matching
  the other three pages — without it an operator who narrows to
  Inactive has no one-click way back.
- **The `list=`-swapping inline script is gone, not repointed**
  (2026-09-09). It existed only to track the dropdown; with one
  datalist there is nothing to swap, and the page loses a script
  rather than gaining a no-op one.

**Measured after:** the suite went 3071 → 3083 (+12: 8 unit tests on
`filter_relationships_rows` and `relationships_search_options`, and
`test_relationships_page_filter.py` 9 → 13).

**2026-09-09 — PR 3 landed; Item 1 closes.** `spec/setup_pages.md`
gains a "Search matching and suggestions" subsection under the
Operator actions card: the per-column matching table, the
both-sides-plus-row-tags rule for Relationships, the pick-an-offered-
label trigger, and the suggestion contract (distinct values, built
from the unfiltered roster, tags first, two separate caps). The strip
bullet now states one shape for four pages. The stale justification —
"a relationship has no single status-vs-roster distinction worth a
filter" — is replaced by what the evidence actually showed: the filter
was missing rather than unwarranted, since the page has had a row
`status` since 15D and ships the buttons that set it.

**Two specs the plan did not name.** Grepping `Search by|search_by`
across `spec/` and `docs/` after the strip section was rewritten found
`spec/settings_inventory.md`'s URL-param row still documenting
`?search_by=` as a live Relationships parameter, and
`spec/operator_button_audit.md` row 140 still describing the
Relationships **Search** button as submitting a "Search by" dropdown.
Both are drift this item caused, so both are now `### Doc impact`
bullets rather than a later sweep's problem. Two further hits are
Assignments (`spec/operator_button_audit.md` row 71i,
`spec/archive/rule_based_assignment.md`), which keeps its side-picker
and is Out of scope, and one is a `docs/status.md` history row for 13C
that describes what shipped then and stays as written.

**The spec is written from the code, not from the plan.** Four claims
were checked against `app/` rather than carried over from this
document: Observers match on `display_name` (which may be unset) and
`email`, not `name`; Reviewees match on `email_or_identifier`;
Observers carry one tag slot where the others carry three; and
`is_filtered` includes status on all four routes, which is what makes
"status lifts the cap to 500" true rather than plausible. The first
two would have been wrong if written from the plan's prose.

**The `spec-writer` pass, adjudicated.** It verified every factual
claim in the new subsection against the code — the per-column table,
the both-sides rule, the dangling-FK behavior, the uncapped label set,
the ordering and both cap values, and `is_filtered` on all four routes
— and found no drift left live. Three flags, all accepted:

- Two British forms in prose written this morning (`parenthesised`,
  `recognised`), fixed. New prose is US per `CLAUDE.md`; the no-sweep
  rule protects *existing* prose, not text I wrote an hour ago.
- The pick path's paragraph never said, for Relationships, that the
  exact match is checked against **either** side — true in the code and
  one of the six mutants PR 2 killed, but a reader could take "both
  sides" as scoped to the substring table above it. One clause added.
  Filed as a completeness gap rather than an error, which is what it
  was, but the mutant it corresponds to is why it was worth closing.

**2026-09-09 — post-close follow-up: the help text.** Reported from
use the same day: the search boxes' placeholders still read "Reviewer
name or email" on three pages, which is the one line of the page that
tells an operator what to type. The item taught the boxes to read tag
columns and left the sign over them wrong — **no test could have caught
it**, because every assertion the item added is about what the search
*does*. Placeholders now read "<Entity> name, email or tag"
(Relationships already read "Name, email or tag" from rung 2), and a
new `tests/integration/test_setup_search_placeholders.py` pins the
search input's own placeholder on all four pages, located by the
`list=` that binds it to the page's datalist — a bare `"tag" in body`
would pass on the tag chips, the column headers and the label editor.
The Relationships Edit / Add pickers keep "Search name or email": they
resolve one person and do not search tags, which the same file pins so
a future sweep does not "fix" them into agreement.

**Left as reported, not widened** (2026-09-09): the Reviewees box says
"email" where the column is `email_or_identifier`, so an analysis-only
roster of anonymous identifiers is under-described. That predates this
item and is a copy question of its own; noted here rather than folded
into a placeholder fix.

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
- `spec/settings_inventory.md` — the `?status=` / `?q=` URL-param row
  drops `?search_by=`, names all four pages, and renames the carried
  hidden field to `filter_status` (PR 3, added at build — see
  `### Status`).
- `spec/operator_button_audit.md` — row 140, the Relationships
  operator-actions **Search** button, no longer submits a "Search by"
  dropdown (PR 3, added at build).
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
- **Amended 2026-09-09, by the author**: the `Showing N of M` hint
  moves down with it. The second row carries all three inline and
  flush right — `Showing 22 of 154.` · `22 SELECTED` ·
  `☐ Yes, delete these` — leaving the first row to the controls
  alone. The three are one kind of thing (what the page is currently
  showing and what is currently picked); the buttons are another, and
  at a filtered width the mixed row was already wrapping mid-group.

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

- **Nothing selected** — **both** the confirmation checkbox and the
  Delete button are inactive (per the author, 2026-09-09), not the
  button alone. The gate is therefore two-stage: a selection enables
  the checkbox, ticking the checkbox enables the button. A tickable
  box with nothing to confirm invites the operator to confirm first
  and select second, which is the order that makes the count in
  "3 selected · ☐ Yes, delete these" arrive after its own
  confirmation.
- **Deselecting everything clears the tick**, it does not merely
  disable it (2026-09-09). A tick that survives deselection would
  re-arm the button the moment a *different* selection is made, so
  the operator's confirmation would attach to rows they never
  confirmed. Disable **and** uncheck; re-selecting starts the gate
  over.
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
- ~~**Ids not in this session** are ignored, not errors — the same
  posture `bulk_inactivate` takes.~~ **Wrong on both halves, corrected
  2026-09-09 at PR 2.** `bulk_inactivate` delegates to
  `roster_bulk.bulk_set_status`, which **raises** `not_in_session` —
  the plan cited a function as precedent for the opposite of what it
  does. `bulk_delete` raises too, and a delete has the stronger case
  for it: a silently skipped id is a row the operator asked to remove
  that is still there, unremarked.
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
- **The tick clears on *any* change of selection, not only on
  reaching zero** (2026-09-09). The author's rule is that the gate is
  inactive with nothing selected; this is that rule one step out.
  "Yes, delete these" names the selection as it stood when the box was
  ticked, so a selection that changes underneath a live tick has the
  operator confirming a set they did not confirm. Adding a fourth row
  to a ticked three is the cheap case, and the box simply re-ticks.
  **Flagged for confirmation on the PR 1 scaffold**, since it costs a
  click and the scaffold exists to settle exactly this.
- **The app-wide `data-delete-confirm` gate is extended, not
  bypassed** (2026-09-09). `base.html`'s script already pairs a
  checkbox to a button by key and is what the three existing
  destructive controls use. The selection stage goes in front of it —
  the page's existing selection-sync code, which already enables Edit
  / Inactivate / Activate, also drives the checkbox's `disabled` and
  clears it on empty — rather than a second, parallel gate. Two
  scripts deciding one button's `disabled` is the drift class this
  repo keeps paying for.

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

**Amended 2026-09-09**, at the author's instruction: PR 1 is not just
first in sequence, it is a **hold point**. The ladder stops after it
until the author has looked at the strip on the dev slot and confirmed
the shape. PR 2 does not start on a scaffold that has only been
asserted in tests — that is what scaffold-first is for, and a
destructive control is the last place to discover a layout argument
with the wiring already in.

To make that confirmation possible, PR 1 carries the **interaction**
as well as the layout: the selection → checkbox → button gate is live,
so the author can see the states they specified. What PR 1 does not
carry is any way to delete anything — no route, no service, and a
`Delete` that is a `type="button"` no-op. Inert means *cannot mutate*,
not *cannot move*; a permanently-disabled checkbox would show none of
what there is to confirm.

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

### Status

**2026-09-09 — PR 1 landed. The ladder is now held** at the author's
instruction until they have looked at the strip on the dev slot. PRs 2
and 3 do not start before that.

**What shipped:** the second row, carrying `Showing N of M`, the
selected-count pill and `☐ Yes, delete these` inline and flush right;
`Add new row` → `Add` (all 12 occurrences, including the three
comments that named the old label); a Destructive `Delete` between
`Add` and `Search`; and the two-stage gate, live. What did not ship is
any way to delete: no route (a POST to `/bulk-delete` 404s on all four
pages, asserted), no service, and a `Delete` that is a `type="button"`
with no `formaction`.

**Driven in Chromium rather than asserted only.** The five gate states
were walked through on a seeded page: nothing selected (pill hidden,
box disabled, button disabled) → one row (pill `1 selected`, box
enabled, button still disabled) → ticked (button enabled) → a second
row selected (**tick cleared, button disabled again** — the judgment
call above, seen working) → all deselected (back to the start).
Clicking the armed `Delete` changed no URL and issued no POST.

**The browser found a defect the tests could not.** The three items
were on one line but the checkbox label's centre sat **4px** below the
other two. The first fix — zeroing the checkbox's UA margin — changed
nothing, because that margin was already `0`. Measuring computed
styles instead of guessing found the cause: the app's global
`label { margin-top: 12px }` gives the label a lopsided margin box
(12 over, 4 under), and a flex row centres the **margin box**. Zeroing
the label's margin closed it to 0px. No test would have caught this
and none reasonably could; it is exactly the class of thing a
scaffold-first slice exists to surface, one PR before anything
destructive is wired to it.

**Also measured:** the button row is one line at a 1440px viewport and
wraps to two at 1280px. Recorded rather than fixed — six controls in a
half-width card will wrap somewhere, and where is a question for the
author looking at it, not for me.

**A spec the plan did not name, and a gap it revealed.**
`spec/operator_button_audit.md` enumerates every operator button per
page: its three roster sections still said `Add new row`, described the
`Search` button as sitting "after the selection-driven buttons + pill",
and had no `Delete`. All three are drift this slice caused, so the file
is now a `### Doc impact` bullet. Recording it turned up a **pre-existing
gap that is not this item's to close**: the Observers page is absent
from that audit entirely — zero mentions — because the file is a dated
snapshot last re-derived before Observers shipped. So the Observers
`Delete` is real in the app and unrecorded there, and saying so is
better than quietly adding a fourth section under this item's name.

**A stale label assertion, updated not worked around**:
`test_operator_actions_card_renders_inert_buttons` (15F PR 2) pinned
`>Add new row</a>`; it now pins `>Add</a>` and `>Delete</button>`.

**Seven mutants, seven kills** — the hint left on the button row; the
Delete in the Secondary role; the Delete turned into a live submit
with a `formaction`; the gate shipped enabled; the Delete placed
before `Add`; the new CSS rule unscoped so it reaches all seven
`.filter-actions` templates; and a non-roster page gaining the row.

**Measured after:** the suite went 3088 → 3106 (+18: the scaffold
file's 18 tests, of which 16 are the four-page parametrisation).

**2026-09-09 — PR 2 landed** (the service). `delete_selected` on all
four roster services, each a thin caller of a new
`roster_bulk.bulk_delete` beside the existing `bulk_set_status` — the
same consolidation 19B's S5 made for the status flips, taken at the
point the second copy would have been written rather than after the
fourth. Nothing calls it yet; the route is PR 3.

**The plan cited a function as precedent for the opposite of what it
does.** Semantics said unknown ids are "ignored, not errors — the same
posture `bulk_inactivate` takes", and `bulk_inactivate` delegates to
`bulk_set_status`, which **raises** `not_in_session`. Struck and
corrected rather than quietly followed: `bulk_delete` raises too, and a
delete has the stronger case, since a silently skipped id is a row the
operator asked to remove that is still there and unremarked. A test
pins that the valid ids in a refused call are **not** deleted, and
deliberately does not roll back first — rolling back would make the
assertion pass whatever the code did.

**The open question is answered from the model graph, then from
behavior.** `Assignment` carries FKs to `reviewers` and `reviewees` and
nothing else; `Observer` and `Relationship` have no ORM children. So
Reviewers and Reviewees cascade to assignments and their responses
(and a reviewer's invitations) by `delete-orphan`, and Observers and
Relationships destroy nothing — which is the answer to whether
Relationships needs the response-loss gate. Asserted rather than
reasoned: a test deletes an observer and a pair-context row beside a
live assignment carrying four responses and finds all four intact.

**The exact counts are real.** `cascade_counts` counts assignments and
responses for *the selected rows*, not the session, so the PR 3
confirmation can name a number `delete_all` could never produce. A
mutant that counted session-wide kills two tests.

**A vacuous assertion of my own, caught by mutation.** The audit test
asserted "one event per call, not one per row" while deleting **one**
row — where the two are the same number, so the sentence pinned
nothing, and a per-row mutant passed. Rewritten to delete two rows with
different cascade sizes; it now also pins that the counts are summed
across the selection rather than the last row's. That is the fifth
assertion in three days that read correctly and tested nothing.

**Seven mutants, seven kills** (after the rebuild above): unknown ids
skipped rather than refused; the refusal moved after the deletes;
the cascade counted session-wide; a phantom cascade column on
`Relationship`; session scoping dropped from the row query; lifecycle
invalidation skipped; and one audit event per row.

**Measured after:** the suite went 3106 → 3120 (+14, all in
`tests/unit/test_roster_bulk_delete.py`).

**2026-09-09 — PR 3 landed; Item 2 closes.** Four `bulk-delete`
routes, both gates, the button wired. The scaffold's inert assertions
were **moved forward rather than deleted**: the test that pinned
`Delete` as having no route behind it now pins the `formaction` that
does, and the four 404 tests became one that pins the checkbox
actually posting with the bulk form — a `name`/`form` pair whose
absence would look identical and submit nothing.

**One checkbox, not two — a departure from the plan's reading of its
own gate, and the reason is layout.** Semantics said
`_require_response_loss_ack` applies "exactly as it does to
`delete-all`", which on that surface means a *second* checkbox. The
strip the author confirmed at PR 1 has room for one. So the
acknowledgement rides with the single tick: where the selected page's
rows can carry responses, the label reads "Yes, delete these and
discard their saved responses" and a hidden
`acknowledge_response_loss` accompanies it. The route still requires
both fields and still refuses without the tick that carries them.
**Flagged to the author** — the alternative (a second box, gated
behind the first) is a layout change to a strip they had just signed
off, which is not a change to make silently.

**A pre-existing defect found while wiring this, and deliberately not
fixed.** `delete-all` requires `acknowledge_response_loss`, and **no
roster template ever sends it** — one match across `app/web/templates`,
in `next_action_card.html`. So on a session with responses, the Danger
Zone's "Delete all reviewers" returns 400 with no path forward from
that page. The Danger Zone is explicitly Out of scope for this item and
the fix is not a line of this diff, so it is reported rather than
folded in.

**The gate says something false unless it is scoped twice.** The
acknowledgement is rendered from a session-wide answer, because the
page cannot know the selection at render time. Rendered on *all four*
pages that read "and discard their saved responses" beside an
Observers or Relationships delete, which destroys no response — the
placeholder defect again, one item later. The context key is now
`delete_discards_responses`, literal `False` on those two pages, and a
test asserts the copy never appears there **even on a session full of
responses**.

**Eight mutants, eight kills**: the confirm gate accepting anything
truthy; the confirm gate removed; the response gate asking the session
instead of the selection; the response gate skipped; the redirect
carrying the deleted ids back; the checkbox losing its `form=` so the
tick never posts; the response-aware label shipped unconditionally;
and the lifecycle gate dropped.

**Driven end to end in Chromium.** Filtered to a tag, selected rows 1
and 3 of 3, ticked, pressed Delete: landed back on
`?status=all&q=Shared` with **no** `selected=`, those two rows gone and
the third still there — and the whole roster confirmed the other two
untouched. Then, with a saved response present, the label read "Yes,
delete these and discard their saved responses" on Reviewers and
Reviewees, read plain on Observers and Relationships, and the delete
went through.

**Measured after:** the suite went 3120 → 3152 (+32: 32 route tests,
with the scaffold file's 18 unchanged in count).

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

- ~~**Whether Relationships needs the response-loss gate at all.**~~
  **Answered at PR 2, 2026-09-09: it does not — and neither do
  Observers.** From the model graph rather than intuition: `Assignment`
  carries FKs to `reviewers` and `reviewees` and to nothing else, and
  `Observer` and `Relationship` have no ORM children at all. So
  `Reviewer` / `Reviewee` → `assignments` → `responses` cascade by
  `delete-orphan` (plus a reviewer's `invitations`), while deleting an
  observer or a pair-context row destroys no assignment and no
  response. Asserted from behaviour rather than read off the model
  file: a test deletes an observer and a relationship beside a live
  assignment carrying four responses and finds all four intact.
- None outstanding.

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
- `spec/operator_button_audit.md` — the three roster sections' `Add new
  row` rows become `Add`, each gains a `Delete` row, and the `Search`
  rows stop describing a pill that has moved (PR 1, added at build —
  see `### Status`).
- `docs/status.md` — row at the close (PR 3).
