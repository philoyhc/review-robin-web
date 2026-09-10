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
| **19I.3** | The delete surface told straight: lifecycle gate, copy that names what goes, and a Danger Zone that works | **Closed 2026-09-09** (3 PRs + a 2b) |
| **19I.4** | The two counts moved to where they read: the hint to the table, a denominator into the pill | **Closed 2026-09-09** (1 PR) |
| **19I.5** | The replace an operator could not make | **Closed 2026-09-09** (1 PR) |
| **19I.6** | The instruments a finished session could still lose | **Closed 2026-09-09** (3 PRs) |
| **19I.7** | The Assignments search reads the tag columns | **Closed 2026-09-09** (2 PRs) |
| **19I.8** | The Assignments page, told straight | **Closed 2026-09-09** (1 PR) |
| **19I.9** | The Assignments strip finishes the job | **Closed 2026-09-09** (3 PRs) |
| **19I.10** | One preview-count sentence across seven pages | **Closed 2026-09-10** (4 PRs) |
| **19I.11** | The roster table facility on Invitations and Responses | **Closed 2026-09-10** (7 PRs) |
| **19I.12** | One place for column selection, and one card fewer | **Open** — planned 2026-09-10 |

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

**The `spec-writer` pass found six things, all accepted — and the
sharpest was mine contradicting itself.**
`spec/operator_button_audit.md`'s three `Delete` rows carried
`` `<button type="button">` `` in the Element column while their own
Notes cell, which PR 3 rewrote, said the button "posts the bulk form
via `form=` + `formaction`" — something only a `type="submit"` does. I
updated the prose of a row and left its structured field at the PR 1
value, so the row disagreed with itself in adjacent cells. That is the
class of defect a reader trusts a table not to have.

The other five:

- **`§7` was an unresolvable pointer.** I wrote "the §7 pairing"
  meaning the audit's `### 7. Confirm-checkbox-gates-button standard`
  — but the same file also has `## Section 7 — Reviewees Setup`, and
  the reviewer read it that way. Two numbering schemes, one number:
  exactly the ambiguity 19G.5 rewrote elsewhere. Now named rather
  than numbered.
- **The audit's legend still defined Destructive as the confirm step
  inside `.card.danger-zone`** — false the moment this item put the
  role on a filter strip. `spec/ui_elements.md` was updated for that
  and the legend that decodes it was not.
- **The plan's own sharp edge never reached the spec.** Semantics said
  the select-all-versus-cap undercount was "worth stating in the spec
  rather than discovering", and I did not state it. A filtered set of
  600 renders 500, so select-all takes 500 and a delete leaves 100
  behind having looked complete. Now in the spec, with the
  `Showing N of M` hint named as what reveals the difference.
- **Three stale `Add new row` labels and a button-state table without
  `Delete`**, in passages neither PR's diff touched. Two of them —
  `spec/rrw_functional_spec.md` and `spec/operator_ui_concept.md` —
  are further specs the plan never named, now `### Doc impact`
  bullets. That makes **five** undeclared spec files across this
  segment; the pattern is that a rename or a new control ripples
  further than the section being edited, and only a term-grep finds
  the rest.
- **The Out-of-scope bullet the item falsified.**
  `spec/setup_pages.md` still listed "Per-row hard Delete" as a
  separate ask "if it surfaces in pilot feedback" — three sections
  above the account of the delete that shipped. Rewritten to what
  actually remains out of scope: a **row-local** ✕ affordance, which
  is the distinction the plan's own Out-of-scope section drew and the
  spec's did not.

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
  roster Delete (PR 1); the disabled-anchor callout's `Add new row`
  label follows the rename (PR 3).
- `spec/rrw_functional_spec.md` — the operator-actions card's button
  list gains `Delete` and the status row, and drops the old `Add new
  row` label (PR 3, added at build).
- `spec/operator_ui_concept.md` — the 15F shipped-surface paragraph
  names `Add` and the new `Delete` (PR 3, added at build).
- `spec/operator_button_audit.md` — the three roster sections' `Add new
  row` rows become `Add`, each gains a `Delete` row, and the `Search`
  rows stop describing a pill that has moved (PR 1, added at build —
  see `### Status`).
- `docs/status.md` — row at the close (PR 3).


---

## Item 3 — The delete surface told straight

### Opportunity

Three findings from the author on 2026-09-09, the day Item 2 closed. All
three are the same shape: the delete surface says something the app does
not do.

**1. Selection is offered where every mutation is refused.** The
templates gate row selection on `is_ready`, which is *only*
`status == "ready"`. Measured by rendering each status against a seeded
session and posting to `/bulk-delete`:

| status | actions card | row checkboxes | Delete button | POST |
|---|---|---|---|---|
| `draft` | yes | yes | yes | **303** |
| `validated` | yes | yes | yes | **303** |
| `ready` | yes | none | yes (dead) | 409 |
| `expired` | yes | **yes** | yes | **409** |
| `archived` | yes | **yes** | yes | **409** |

So an `expired` or `archived` session renders checkboxes and a live
Delete, and every action 409s. On `ready` the checkboxes are correctly
gone but the Delete button still renders — a control that can never
enable, because nothing can ever be selected.

**2. The confirmation does not name what it destroys.** The
selected-rows gate reads "Yes, delete these and discard their saved
responses"; the Danger Zone's reads "Yes, delete the existing
{N reviewers} and {M assignments}." Neither matches the Instruments
page, which has said the whole sentence since 13C: *"Yes, delete
**Instrument #1** and its associated assignments and reviewer
responses."* The author's instruction is to model both on that.

**3. The Danger Zone cannot delete a roster that has responses.**
`delete-all` calls `_require_response_loss_ack`, and **no roster
template sends `acknowledge_response_loss`** — the only match in
`app/web/templates` is `next_action_card.html`. So on a session with
any response the Danger Zone returns **400 with no path forward from
that page**. Found while wiring Item 2 PR 3 and reported rather than
fixed, since the Danger Zone was Out of scope there; the author has now
directed the change, and states the requirement plainly: the Danger
Zone must be able to delete a roster that has responses.

### Decision

**Gate the selection surface on `is_editable`, give both confirmations
the Instruments sentence, and let the Danger Zone's single tick carry
the acknowledgement.**

- **Lifecycle.** Row checkboxes, the selection-driven buttons and the
  Delete gate render only when `lifecycle.is_editable(...)` — `draft`
  or `validated`. `ready`, `expired` and `archived` get none of them.
  The author's rule, in their words: a `ready` session "is open for
  receiving responses and so the rows should not be editable", and
  `expired` / `archived` should not be either "since the thing is
  over".
- **Copy.** Where the delete will destroy assignments or responses,
  both confirmations name them, modelled on Instruments.
- **Danger Zone.** One tick, carrying `acknowledge_response_loss` as a
  hidden field where responses exist — the same shape Item 2 PR 3
  settled for the strip, and which the author has confirmed ("one tick
  to cover both acknowledgements is fine").

Rejected: **gating on `draft` alone**, which is how the author first
put finding 1. `validated` is editable — `_require_editable` allows it,
`invalidate_if_validated` exists precisely to handle a roster edit
there, and eight bulk routes already work on it. Draft-only would
disable a surface that works today, on all five buttons rather than
just Delete. Put to the author, who confirmed draft and validated are
both fine.

Rejected: **leaving the Danger Zone's 400 as a separate item.** It is a
one-line template fix on the surface this item is already rewriting the
copy of, and leaving a destructive control unreachable while editing
its label would be the worse trade.

Rejected: **a second acknowledgement checkbox** on either surface,
settled in Item 2 and re-confirmed here.

### Semantics

- **`is_editable` is the single gate**, replacing `not is_ready` at
  every selection-surface site. It is what the server enforces
  (`_require_editable`), so UI and route agree by construction rather
  than by two lists being kept in step.
- **The Danger Zone keeps its own gate.** It is already hidden on
  `ready` — correct, per the author — and this item does not widen it
  to `expired` / `archived` beyond what the lifecycle gate implies;
  see Out of scope.
- **Copy is conditional on what exists, not on the entity.** A delete
  that takes assignments says assignments; one that takes responses
  says both. A roster with neither says neither. The counts come from
  the session for the Danger Zone (which deletes everything) and from
  `cascade_counts` for the strip (which knows its selection) — the
  strip cannot know its selection at render time, so it renders from
  the session-wide answer and the route holds the exact gate, as
  Item 2 established.
- **Observers and Relationships never name responses**, on either
  surface: nothing references them, so neither delete can reach one.
  Item 2 proved this from the model graph; this item must not
  re-introduce the claim through the Danger Zone's copy.
- **The `ready` Delete button goes** with the rest of the selection
  surface, rather than being left as a permanently disabled control.

### Judgment calls — decided

- **`is_editable`, not a new predicate** (2026-09-09). The rule the
  author described *is* `is_editable`; inventing
  `is_selection_enabled` would be a second name for one idea and a
  second thing to keep in step.
- **The Danger Zone's hidden ack mirrors the strip's** (2026-09-09).
  Same mechanism, same reasoning, and a reader who has seen one
  recognises the other.

### Blast radius (measured)

At `c03f279f`:

| What | Measured | Command |
|---|---|---|
| `is_ready` uses in the four roster templates | 6 / 6 / 7 / 6 = **25** | `grep -c is_ready app/web/templates/operator/session_{reviewers,reviewees,observers,relationships}.html` |
| templates using `is_ready` at all | **11** | `grep -rln "is_ready" app/web/templates/ \| wc -l` |
| routes passing `is_ready` to a template | **7** | `grep -rn '"is_ready"' app/web/routes_operator/*.py \| wc -l` |
| existing `is_editable` callers | **9** | `grep -rn "is_editable" app/ --include=*.py --include=*.html \| wc -l` |
| Danger Zone confirm labels to rewrite | **4** | `grep -rn 'data-delete-confirm="delete-all"' app/web/templates/operator/session_*.html` |
| tests naming `delete-all` | **7 files** | `grep -rln "delete-all" tests/ --include=*.py` |
| tests touching `is_ready` / `"ready"` | **28 files** | `grep -rln 'is_ready\|status = "ready"' tests/ --include=*.py` |

**The 11-versus-4 gap is the number to respect.** `is_ready` gates far
more than selection — lock cards, label editors, upload forms — and on
seven of those templates it is the *right* gate. This item changes it
only where it guards the selection surface on the four roster pages,
and must not sweep.

**`assignment_count` is already in context on Reviewers and Reviewees
only** (`grep -rn '"assignment_count"' app/web/routes_operator/_setup_*.py`
→ 2). Observers and Relationships would need it added, or their copy
written without an assignment clause — decided at build from what
their deletes actually cascade to, which per Item 2 is nothing.

### PR ladder

1. **PR 1 — the lifecycle gate.** `is_editable` replaces `not is_ready`
   at the selection sites on the four roster pages; the `ready` Delete
   button goes with them. A per-status test matrix replaces the
   measurement above. Must not touch: the confirm copy, the Danger
   Zone, or `is_ready` anywhere it guards something else.
2. **PR 2 — the copy, both surfaces, and the Danger Zone's
   acknowledgement.** The Instruments sentence on the strip and the
   Danger Zone; the hidden `acknowledge_response_loss` that makes
   `delete-all` reachable on a session with responses. Must not touch:
   the lifecycle gate, or the routes' own contracts.
3. **PR 3 — the spec.** `spec/setup_pages.md`'s delete and
   Danger Zone accounts state the lifecycle gate and the copy rule;
   `spec/lifecycle.md` gains the editable-surface consequence if it
   does not already carry it.

### Status

**2026-09-09 — PR 1 landed** (the lifecycle gate). `is_editable`
replaces `not is_ready` at the selection sites on all four roster
pages, and the mutating controls — Edit, Inactivate, Activate, Add,
Delete, the selected-count pill and the delete gate — render only where
they can act. Clear, Search and the `Showing N of M` hint stay: reading
a finished session's roster is legitimate and hiding it would be a
safety gain of nothing.

**Observers turned out to be a deliberate exception, and the plan did
not know it.** Its checkboxes are gated `not is_archived` rather than
`not is_ready`, with a comment at the site saying why: they **drive the
cohort rule editor**, which `spec/setup_pages.md` documents as
intentionally living past `ready` so it stays usable mid-session. A
blanket sweep to `is_editable` would have broken that surface to fix a
different one. So Observers changed only where the plan's argument
applies — the bulk *card* — and its checkboxes keep their looser gate.

**No existing test needed changing**, on any of the four pages, which
is the reassuring half of a 28-file blast radius.

**Seven mutants; six died and the seventh exposed my own assertion.**
Narrowing Observers' checkboxes to `is_editable` — the exact mistake
the paragraph above avoids — passed everything, because the test
asserted the bare string `observer-select`, which also appears in the
page's own `querySelectorAll(".observer-select")`. That is **19H.1's
trap verbatim**, four items later: an assertion satisfied by a JS
selector rather than by markup. Re-pinned on
`<input type="checkbox" class="observer-select"` and the mutant now
dies. The frozen-page assertions had the same hazard in the other
direction and were tightened with it.

**Sixth vacuous assertion in four days.** The tally is not the point;
the shape is, and it is always the same one — a substring that reads
like the thing but also occurs somewhere the change does not touch.

**Measured after:** the suite went 3152 → 3193 (+41, all in
`tests/integration/test_setup_selection_lifecycle.py`, five statuses ×
four pages plus the exceptions).

**2026-09-09 — PR 2 landed** (the copy, and the Danger Zone made
reachable). Both confirmations now name what goes, modelled on the
Instruments sentence: the strip reads "Yes, delete these and their
associated assignments and reviewer responses", the Danger Zone names
the counts. `delete-all` carries the acknowledgement on the same single
tick, so **the defect that opened finding 3 is closed**: a session with
responses can have its roster deleted, asserted by posting exactly what
the rendered form carries rather than fields invented by the test.

**The copy needed a third state the finding did not name.** A roster
whose rows carry assignments loses them even with no response saved,
and the old label said nothing. Two flags rather than one, so the
sentence is true in all three cases.

**Observers' gate was dropped, not satisfied.** `delete_all_observers`
required `acknowledge_response_loss` for a loss that cannot happen —
nothing references an observer. Feeding it a hidden field would have
made the button work while leaving the operator agreeing to a fiction;
the requirement is gone and the now-dead parameter with it.
Relationships never had the gate, so it needed nothing.

**A latent bug of my own, found by a comparison rather than a test.**
`_shared.py` builds its **own** context for the CSV-import error
render — a second render path this plan's blast radius missed — and it
never carried `delete_discards_responses`, which Item 2 PR 3 added. No
test failed, because **Jinja's `Undefined` is falsy in `{% if %}`**: the
label silently took its no-loss branch on that page for as long as the
key had existed. Only `roster_response_count`, which is *compared*
rather than tested, raised an error and exposed the older omission. A
test now pins that page. The lesson is not "add the key" — it is that a
missing context flag is invisible to every boolean the template makes
of it, so the render path count is the thing to measure, and I measured
templates instead.

**Seven mutants, seven kills**: the hidden ack removed; the ack shipped
unconditionally; the response clause dropped from the Danger Zone
label; the strip label reverted to the Item 2 wording; an Observers
label promising to delete responses; Observers' false gate restored;
and the import-error path losing its keys again.

**Measured after:** the suite went 3193 → **3209** (+16: 14 in the new
Danger Zone file and 2 for the import-error path, which is
parametrised over both cascading pages — I wrote +1 before running it,
and the run is what the number comes from).

**2026-09-09 — PR 2b: the open question, closed from the rule rather
than by waiting.** The Upload and Danger Zone cards shared the
`not is_ready` gate the selection surface had, so both rendered on
`expired` and `archived` while `/import` and `/delete-all` returned
409. The author's stated principle — draft and validated edit, the rest
do not, "since the thing is over" — is a rule about editing, and both
of these are edits. Asked twice and left open; deciding it from what
they had already said beat closing the item around a known hole.

**And the tightening trap fired in the other direction.** The new
assertion `"danger-zone" not in body` failed on a *template comment*
describing the shape `.danger-zone` — prose, not markup. That is
19H.3's lesson exactly ("an assertion that fails on prose explaining a
rule is one somebody deletes"), reached this time by writing the loose
assertion first. Re-pinned on `class="card danger-zone"`.

**Measured after:** the suite went 3209 → **3241** (+32, the Upload /
Danger Zone matrix across four pages × five statuses).

**2026-09-09 — PR 3 landed; Item 3 closes.** `spec/lifecycle.md` §5
now states the `is_editable` gate for the whole mutating surface —
cards *and* the roster pages' selection controls — with Observers'
checkbox exception named, and corrects the section's own claim that
the grid hides "while session is `ready`". `spec/setup_pages.md`
carries the three-state copy table, the selection gate, and a Danger
Zone account that says plainly what was broken and what the hidden
field fixes.

**A gap the fix created, written into the spec rather than left to be
found.** The lock card that explains why setup is locked is keyed to
`ready` alone. So on `expired` and `archived` the mutating cards are
now absent with nothing saying why — the page went from wrong and
talkative to correct and silent. Recorded in `spec/lifecycle.md` §5 as
a known gap and in Out of scope above, rather than quietly widening
this item into a copy surface nobody asked for.

**2026-09-09 — `spec-writer` flags adjudicated, all seven accepted.**
The pass ran after the item's PR had merged, so they land as a
follow-up.

**The worst was mine, and it was a sentence I widened rather than
wrote.** `spec/lifecycle.md` §5 has always opened "On Setup pages
(Reviewers / Reviewees / Relationships / **Instruments**)…", and I
rewrote the paragraph under that heading to say the gate is
`is_editable` and the page "now offers what `_require_editable` will
accept and nothing else". False for Instruments in **both**
directions: it has no Upload or Danger Zone card to hide (zero matches
in `instruments_index.html`), and its mutations gate on
`_can_edit_instrument`, which is `not is_ready`. I inherited a
slightly loose list and made a precise false claim out of it — the
failure mode is editing a paragraph without re-reading the sentence
that scopes it.

**And that is a finding, not just a correction:** instrument structure
is still mutable on `expired` and `archived`, which is exactly the gap
this item closed for the roster pages. Recorded in §5 and reported;
not fixed, because it is a different surface with its own gate and
nobody has reported it.

**Three more passages stated the fixed defect as current fact**, none
of them touched by the item's own spec pass: `setup_pages.md`'s
"Shared body shape" still said the button row "renders inert" on
`is_ready` — it is now *absent*, which is a different claim, not a
looser one; the Observers body-layout bullets still said `is_ready`;
and the Implementation pointers still described the Upload / Danger
Zone conditional as `{% if not is_ready %}`, three sections below the
account of why that was wrong.

**Two more undeclared spec files**, the segment's fifth and sixth:
`spec/operator_ui_concept.md` and `spec/operator_button_audit.md`, now
`### Doc impact` bullets. Every item in this segment has found at least
one, always the same way — a term-grep after the named files are done,
never the named files themselves.

**One overstatement corrected**: the Danger Zone and the strip share
the three-state *rule*, not the sentence — one names counts, the other
says "these". "The same sentence" is the kind of claim a reader goes
to verify word-for-word and does not find.

### Definition of done

- Row checkboxes, the selection buttons and the Delete gate render on
  `draft` and `validated` only — asserted per status, all five.
- A POST to `/bulk-delete` on a non-editable session still 409s, and
  the page no longer offers the control that produces it.
- The Danger Zone's Delete-all **succeeds** on a session with
  responses, asserted end to end — the defect that opened finding 3.
- Both confirmations name assignments and responses where the delete
  destroys them, and name neither on Observers / Relationships.
- The four `delete-all` forms and the four strips agree on the
  sentence.
- `ruff check .` and `pytest -q -n auto` pass.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19I.3` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- ~~**Whether the Danger Zone should also hide on `expired` /
  `archived`.**~~ **Answered 2026-09-09 from the author's own rule, not
  by waiting.** They gave the principle for rows — draft and validated
  edit, `ready` is receiving responses, `expired` and `archived` are
  over — and an import and a delete-all are edits, so the principle
  reaches them without a new decision. Both cards were rendering on
  `expired` and `archived` while both routes 409'd: the same defect as
  the row selection, one card down the page. Put to the author twice
  and left standing; resolving it from what they had already said beat
  shipping the item with a known hole in it.
- None outstanding.

### Out of scope

- **`is_ready` where it guards anything else** — lock cards, friendly-
  label editors, upload forms, and the seven non-roster templates. A
  correct gate for a different question.
- **The CSV replace-roster confirm**, which destroys assignments and
  responses on the same pages and has its own copy. Named because the
  grep finds it; changing it is a third surface and nobody has
  reported it.
- **Undo**, still. Nothing in this app has it.
- **A lock card for `expired` / `archived`** (found at PR 2b,
  2026-09-09). The yellow lock card that explains *why* setup is
  locked is keyed to `ready` alone, so on the other two frozen states
  the mutating cards are simply absent with nothing saying why. The
  page is now correct and silent, where before it was wrong and
  talkative. A copy surface of its own, and nobody has reported it;
  recorded in `spec/lifecycle.md` §5 as a known gap so the next reader
  of that section meets it.

### Doc impact

- `spec/setup_pages.md` — the "Deleting the selected rows" and Danger
  Zone accounts state the `is_editable` gate on the selection surface
  and the copy rule for both confirmations (PR 3).
- `spec/lifecycle.md` — the five-state table records that the
  selection surface is offered only in the two editable states (PR 3).
- `spec/operator_ui_concept.md` — the Upload and Danger Zone bullets
  drop the lock-card gate for `is_editable` (PR 3 follow-up, added at
  build — see `### Status`).
- `spec/operator_button_audit.md` — a lifecycle note above the roster
  button tables: outside the editable states these controls are absent,
  not disabled (PR 3 follow-up, added at build).
- `docs/status.md` — row at the close (PR 3).


---

## Item 4 — The two counts, where they read

### Opportunity

The author piloted moving the `Showing N of M` hint out of the
operator-actions strip and above the preview table, then asked for a
second change with it: expand the selected-count pill from
`N selected` to `N of M selected`.

Measured on the pilot render: the hint sat at `x≈1010`, flush right in
the strip; the table it describes starts at `x≈58`. Roughly 950px, and
across a card boundary, between a number and the rows it counts.

### Decision

**Move the hint to the preview-table card's top-left, and give the
pill its own denominator — the rendered window.**

The two changes are one idea, which is why they arrived together.
Moving the hint costs something the spec leans on: it is what tells an
operator that select-all took the **rendered window** rather than the
whole match (600 matching rows render 500, so a delete leaves 100
behind looking complete). Sitting beside the selected-count and the
delete gate, the hint was half of that sentence. **The pill's new
denominator is the other half, relocated into the strip**: `4 of 4
selected` beside `Showing 4 of 12` above the table says the same thing
with two numbers instead of one adjacency.

`M` is the **rendered window**, not the roster, because that is what
select-all can reach. The roster total would read as reassurance where
the window reads as a warning.

Rejected: **keeping a copy in both places**, which is what the pilot
shipped to be looked at. Two identical numbers 80px apart read as an
oversight, not a choice.

Rejected: **moving the hint and leaving the pill alone**, which is the
literal first half of the ask. It spends the adjacency and buys
nothing back.

### Semantics

- The hint renders only when the cap or a filter has trimmed the list;
  `Showing 6 of 6` is noise. Unchanged by the move.
- The pill is hidden at zero, so `0 of 0 selected` is a placeholder the
  operator never sees; it exists so the server-rendered markup and the
  JS agree on the format.
- `M` tracks the rendered checkboxes, so it follows the filter: filter
  to four rows and select-all reads `4 of 4 selected` even on a
  twelve-row roster.

### Judgment calls — decided

- **`M` is the window, not the roster** (2026-09-09). The window is
  what select-all reaches, and the number exists to expose a gap
  rather than paper over it.

### Blast radius (measured)

At `e6462def`: 4 templates (the hint in two places each, plus one JS
line), 1 `base.html` rule, 3 spec passages — the status-row item, the
"Preview tables" opener and the select-all caveat; I wrote 2 and the
diff has 3. No route or service change
— both numbers were already in the render context.

### PR ladder

1. **One PR.** Splitting the hint's move from the pill's denominator
   would land a state where the move's cost is paid and nothing has
   bought it back.

### Definition of done

- The hint renders above the table on all four pages and nowhere in
  the strip, asserted both ways.
- The pill reads `N of M selected` with `M` the rendered window,
  verified in a browser since the text is JS-set.
- `ruff check .` and `pytest -q -n auto` pass.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19I.4` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Status

**2026-09-09 — landed in one PR.**

**A test of mine claimed three things and pinned two.**
`test_the_status_row_carries_all_three_and_the_button_row_none`
(Item 2) asserted the hint's *absence from the button row* and never
its *presence in the status row* — so moving the hint out of that row
entirely broke nothing and the suite stayed green. The name said
"all three". Renamed to what it actually checks, and the hint's new
home is pinned properly in a new file, both ways round.

**Seventh vacuous assertion in four days**, and the first whose
give-away was in its own name. The others hid behind a substring; this
one advertised a claim it never made.

**Verified in Chromium**: one hint copy at `x=58` (was `x≈1010`), and
the pill reading `1 of 4` → `2 of 4` → `4 of 4 selected` as rows are
checked and select-all fires.

**Measured after:** the suite went 3241 → **3257** (+16, the new
`test_setup_showing_hint.py`).

**2026-09-09 — `spec-writer` flags adjudicated, all four accepted.**

**Both stale passages were prose I wrote earlier in this same
segment.** `spec/rrw_functional_spec.md` still put the hint in the
status row — a sentence I added in **Item 2's** adjudication, false one
item later. `spec/lifecycle.md` §5 listed `Showing N of M` among "the
read-only half of the strip" — mine from **Item 3**, false the moment
Item 4 moved it to a different card. Every item in this segment has
found undeclared stale spec text; this is the first time the stale text
was recent enough to be my own, which sharpens the pattern from "the
plan under-names files" to "a location claim goes stale the next time
anything moves, and prose that names a location is the prose to grep
for."

**The plan's own blast radius was wrong.** It said 2 spec passages; the
diff touches 3. Corrected in place rather than left, since the count is
the thing the section exists to be trusted on.

**And the caveat paragraph changed scale mid-sentence.** It opened on
the 600-matching/500-rendered case and then illustrated the two-number
pairing with a fresh `4 of 12`. Both are producible, so it was not
wrong — just a re-orientation the reader has to do for no reason. Now
one scale throughout: `Showing 500 of 600` against `500 of 500
selected`. The same edit removed a "this row" that named a row the
passage no longer sits in.

### Open questions

- None.

### Out of scope

- **The Assignments, Invitations and Responses pages**, which have
  their own `Showing N of M`. Same class, different surface, and
  nobody has reported them.

### Doc impact

- `spec/setup_pages.md` — the status-row description loses the hint and
  gains the pill's `N of M` format; "Preview tables" gains the hint's
  new home; the select-all caveat is rewritten around the two numbers.
- `spec/rrw_functional_spec.md` — the operator-actions bullet stops
  putting the hint in the status row and names the pill's format
  (added at build — see `### Status`).
- `spec/lifecycle.md` — §5's read-only-half list drops the hint, which
  now lives in the preview-table card (added at build).
- `docs/status.md` — row at the close.

## Item 5 — The replace an operator could not make

### Opportunity

Reported from use (2026-09-09): *"I tried uploading a new roster to
replace an existing one, in a session with assignments already, though
back in draft mode"* — and got **400 Bad request**, "Existing reviewer
responses will be discarded; tick 'acknowledge response loss' to
proceed". There is no such tick on the page, and never has been.

This is the **third surface** carrying the same defect, and the second
found by an operator rather than by a sweep. Item 3 fixed it on the
Danger Zone's `delete-all`: the route had required
`acknowledge_response_loss` since it was written and no template ever
sent it. The Upload card's replace is the same route-side requirement
against the same silent form. Measured — `_require_response_loss_ack`
has 7 call sites; the import path accounted for 3 of them
(`_setup_reviewers.py`, `_setup_reviewees.py` via the shared handler,
`_setup_observers.py` with its own), and **not one of their forms
carried the field**.

The route an operator takes to get here is the *documented* one.
Editing a started session means reverting it to `draft`; the roster is
then editable and the Upload card is on screen. So the block lands
exactly where the workflow sends them, and offers nothing to do about
it — a dead end, not a warning.

### Decision

**Send the acknowledgement from the tick that is already there, and
make that tick name the responses.** The Upload card's confirmation is
one checkbox; where the roster carries responses, a hidden
`acknowledge_response_loss` field rides with it and the label gains a
third clause:

> Yes, replace the existing `3 reviewers` and delete the
> `1 assignment` and `2 reviewer responses`.

Identical in mechanism to the Danger Zone fix (Item 3) and to the
selected-rows delete (Item 2) — one tick, hidden field, label naming
what goes. Three surfaces with one confirmation idea between them is
the point; a fourth variation would not be.

**Observers' import loses the gate outright**, as its `delete-all` did
in Item 3. Nothing references an observer, so replacing that roster
destroys no assignment and no response. Requiring the operator to
accept a loss that cannot occur was the wrong requirement, not a
missing field, and Relationships never had it.

Rejected: **a second checkbox for the response loss.** It is the
alternative Item 2 already rejected on the strip, for the same reason —
two ticks to say one thing, on a card sized for one.

Rejected: **dropping the requirement on the import path** and letting
the replace proceed silently. The loss is real and irreversible (a
submitted response is deleted, not soft-deleted — measured in Item 2),
and the Danger Zone had just been fixed the other way. Making the same
loss loud on one card and silent on the one beside it is worse than
either choice made twice.

### Semantics

- The clause and the hidden field are both conditional on
  `roster_response_count > 0`, so a session with no answers sees the
  label it saw before and posts the fields it posted before.
- The count is the **session's** responses, not the roster's, because
  that is what the route's gate asks: `_require_response_loss_ack`
  calls `lifecycle.session_has_responses`. The replace clears the whole
  roster, so on Reviewers and Reviewees the two counts coincide.
- Observers' card keeps its `confirm_replace` tick — a replace still
  destroys the observer roster — and never names a response, because
  its import cannot reach one.
- The parse-error re-render is the same context, so a blocked upload
  redisplays the same label rather than losing the clause.

### Judgment calls — decided

- **The clause reads "reviewer responses" on both pages** (2026-09-09),
  including Reviewees, matching the Danger Zone and the Instruments
  card. The answers are the reviewers' whichever roster is being
  replaced; "reviewee responses" would name a thing that does not
  exist.
- **`roster_response_count` is reused, not renamed** (2026-09-09).
  Item 3 added it to the page context for the Danger Zone; the Upload
  card sits on the same page and asks the same question.

### Blast radius (measured)

At `9e0e8f9e`: 2 templates (the Reviewers and Reviewees upload
labels), 1 route module (`_setup_observers.py`, losing its gate and
the now-dead parameter and import), 1 spec section, 1 new test file.
No service change and no new context key — `roster_response_count`
has been in all four pages' context since Item 3.

- `grep -rn "_require_response_loss_ack(" app/ | wc -l` → 7 call
  sites; 3 on the import path.
- `grep -rn 'name="acknowledge_response_loss"' app/web/templates/` →
  before: 7 hits — the four selected-rows strips (Item 2), the two
  Danger Zones (Item 3) and `next_action_card.html` — and **none in an
  upload form**.
- Relationships' import was checked and has no gate to remove.

### PR ladder

1. **One PR.** The templates and the observers route are one
   correction; landing the label without the hidden field would
   describe a loss the operator still cannot accept, and landing the
   field without the label would let the replace through unannounced.

**No scaffold slice.** `CLAUDE.md`'s scaffold-first rule is for a new
page, card or navigation affordance. This adds a clause to a label on
a card that has been there since Segment 09.

### Status

**2026-09-09 — landed in one PR, as planned.**

**The blast radius held**, with one addition the plan did not name:
the parse-error re-render. `_shared.py`'s import handler builds its
own context, and Item 3 had already been bitten there —
`delete_discards_responses` was missing from it and **nothing failed**,
because Jinja's `Undefined` is falsy in `{% if %}`. So the new tests
pin the label on that path too, not only on the GET.

**A test helper that worked on the GET page and not on the error
page.** `_upload_form` located the Upload card by seeking
`/reviewers/import"` in the body. On the error render the page chrome
carries `?return_to=/operator/sessions/1/reviewers/import` in a
header link, which precedes every `<form>` on the page — so the seek
landed in the header and found no form before it. Rewritten to walk
the forms and take the one whose *opening tag* posts to the import
route. Worth recording because the helper was not wrong on the case
it was written for; it was wrong on the case the new test added.

**Five mutations, five kills** — the hidden field removed, the
response clause removed, the clause made unconditional, the Observers
gate put back, and `roster_response_count` zeroed on the error
render. No vacuous assertion this round, the first clean run in four
days.

**The Quick Setup finding was wrong twice, and is withdrawn.**

First pass: the two `acknowledge_response_loss=None` call sites in
`_quick_setup.py` looked like the defect. They are not — they sit in
the create-session handler, where the session is made in the same
request, so `existing > 0` is false and the gate is never reached.

Second pass (recorded here at the time as the *real* finding): the
Session Home card's form omits `acknowledge_response_loss`, and a
POST to `/quick-setup/reviewers` on a session with responses
redirects to `quick_setup_reason=needs_confirm`. **That is also
wrong, and wrong in the way this item exists to warn about.** I
posted directly to the route. The card cannot make that request:
`views.build_quick_setup_context` sets
`is_available = is_draft(...) and not has_responses`, and
`is_locked = True if not is_available else not is_unlocked` — so on
a session with responses the body renders `.locked`, **every file
input carries `disabled`**, the Lock / Unlock toggle is suppressed
so the lock cannot be lifted, and the description reads *"Quick
Setup is locked because this session already holds reviewer
responses from a prior activation. Use the individual Setup pages
to make changes."* Measured on a rendered page at `acf74a85`, with
the unlock cookie set, so the cookie path is covered too. The
behaviour is deliberate and has been tested since Segment 11J
(`test_quick_setup_unavailable_when_responses_exist_even_on_draft`).

**Item 5's own test docstring names the mistake I then made.** It
says the tests post *exactly what the rendered form carries*, because
inventing a field the page does not offer proves the route works
while leaving the operator stuck. The inverse is just as false:
posting a request the page cannot make proves a defect that no
operator can reach. I applied the rule to the fix and not to the
finding.

**One thing the retraction turns up in Item 5's favour.** That lock
copy tells the operator to *"use the individual Setup pages"* — which,
until Item 5 landed, was advice to a dead end: those pages returned
400 on precisely this session. Item 5 made the card's own instruction
true.

**Measured after:** the suite went 3257 → **3267** (+10, the new
`test_setup_import_response_loss.py`).

**`spec-writer` (2026-09-09): no drift found**, every claim in the new
section checked against the templates, `_shared.py`, both route
modules and the tests. **One flag it did not raise, adjudicated
against myself.** Its own summary described the error path as one
that *repeats* `roster_response_count`; my sentence said the page
re-renders "from the same context". "Same" implies a shared build,
which is exactly the impression that made Item 3's omission feel
impossible — the handler builds that context itself, key by key.
Rewritten to say so, and to name the omission as the evidence.

**Not verified here:** the Azure dev slot. The browser pass on the
sandbox covered the reported flow end to end — a `draft` session with
3 reviewers, 1 assignment and 2 responses, the label reading *"Yes,
replace the existing 3 reviewers and delete the 1 assignment and 2
reviewer responses"*, and the upload replacing the roster without an
error.

### Definition of done

- The reported flow succeeds: a session with responses, reverted to
  `draft`, replaces its Reviewers roster from the page's own form —
  asserted by posting **exactly the fields the rendered form carries**.
- The label names the response count when there is one and says
  nothing about responses when there is not, asserted both ways.
- Observers' import replaces its roster on a session full of responses
  and destroys none of them.
- Every new assertion mutation-checked.
- `ruff check .` and `pytest -q -n auto` pass.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19I.5` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- ~~**The Quick Setup card on Session Home is a fourth surface**~~ —
  **withdrawn 2026-09-09, it is not.** See the retraction in
  `## Status`. The card is force-locked whenever the session carries
  responses, in `draft` as much as anywhere else, and says so; the
  route gate I reproduced is defense-in-depth the card cannot reach.

### Out of scope

- ~~**The Quick Setup card's replace**~~ — struck 2026-09-09: there
  is no defect there to scope in or out. See `## Status`.
- **Relationships' import**, which has no response-loss gate to fix.
- **`_quick_setup.py`'s two `acknowledge_response_loss=None` call
  sites** in the create-session handler. Checked and correct: the
  session is created in the same request, so `existing > 0` is false
  and the gate is never reached.

### Doc impact

- `spec/setup_pages.md` — new section for the Upload card's replace
  gate beside the Danger Zone's, recording the same two gates, the
  label's response clause, and Observers' import losing the
  requirement (Item 5).
- `docs/status.md` — row at the close (Item 5).

## Item 6 — The instruments a finished session can still lose

### Opportunity

Item 3 gated the roster pages on `is_editable` because they offered
row selection and a live Delete on `expired` and `archived`, where
every mutating route returned 409. The Instruments page has the same
lifecycle gap with the **opposite and worse** outcome: the routes do
not refuse.

`_require_instrument_editable` (`app/web/routes_operator/_shared.py`)
gates on `_can_edit_instrument`, which is `not lifecycle.is_ready(...)`.
So the whole instrument surface is protected exactly while the session
is collecting and stops being protected the moment collection **ends** —
which is when the data has become the record.

Measured at `3f2df04c`, one session per state, two instruments so the
`is_only_instrument` rule does not confound the button, an assignment
and one submitted response:

| state | lock card | Delete buttons rendered | route | delete outcome |
|---|---|---|---|---|
| `draft` | no | 3 live | permits | deletes — correct |
| `validated` | no | 3 live | permits | deletes — correct |
| `ready` | **yes** | 0 live, 3 permanently disabled | **409** | blocked — correct |
| `expired` | **no** | **3 live** | **permits** | **deletes** |
| `archived` | **no** | **3 live** | **permits** | **deletes** |

`Instrument` cascades `assignments` → `responses`, both
`delete-orphan`, so on `expired` and `archived` the delete took the
assignment and the **submitted response** with it: measured
`assignments_left=0 responses_left=0` from a seeded 1 and 1. The
description edit lands the same way (`desc_changed=True` on both).

**The page offers this, not just the route.** The Delete buttons on
those two states render `type="submit"` behind nothing but the confirm
tick — checked because Item 5's retraction is the standing reminder
that a route defect the page cannot reach is not a defect. This one
the page can reach.

No test asserts the current permissive behaviour on either state; the
gap was never pinned, which is why it survived Item 3.

### Decision

**One predicate, `is_editable`, for the routes and the page, plus a
lock card on the two states that gain the silence.**

`_can_edit_instrument` becomes `lifecycle.is_editable(review_session)` —
`draft` or `validated` — which corrects all **24**
`_require_instrument_editable` call sites at once, and is the same
predicate `_require_editable` already enforces on every roster route.
The page's `can_edit` follows it, so page and route agree by
construction rather than by two lists kept in step (Item 3's phrasing,
and its reason).

**The lock card is extended, not invented.** `ready` already renders
`<div class="card lock">` with *"The instruments cannot be modified
while the session is ongoing. Revert the session to draft if you wish
to modify anything."* and an inline revert form. `expired` and
`archived` get the same card with the state's own recovery verb, both
of which exist in the service layer:

- `expired` → `revert_session_to_draft` accepts `expired` as a
  starting state, so the card carries the **same inline revert form**
  `ready`'s does.
- `archived` → `unarchive_session` is `archived → draft`, but it is
  surfaced only as bulk-unarchive in the archived-sessions lobby
  (`sessions_archived.html`). That card **names the path without
  offering the control**, rather than inventing a second unarchive
  affordance on a Setup page.

Rejected: **gating only the destructive routes** (delete, replicate)
and leaving description edits open on the two closed states. There is
no principle that splits them, and Item 3 settled that the page and
the route answer to one predicate.

Rejected: **leaving `archived` mutable** on the argument that the
operator owns their own data. The delete is irreversible — no
soft-delete column, no snapshot, measured in Item 2 — and `archived`
is the state whose whole purpose is to be the record. An operator who
genuinely wants to edit an archived session has a path: unarchive it,
which is a deliberate act that says so.

### Semantics

- `is_editable` is `draft` **or** `validated`, so `validated` keeps
  every instrument control it has today; this narrows `expired` and
  `archived` only.
- A `validated` session is invalidated by instrument mutations exactly
  as now — `invalidate_if_validated` at the service entry points is
  untouched.
- The routes answer **409**, the same code and the same guard as
  today; only the predicate widens. The page is the courtesy, the
  route is the guarantee.
- Read stays open on all five states: the page renders, cards expand,
  the preview surface and the extracts are unaffected. Reading a
  finished instrument set is legitimate.
- The lock card renders once per page, above the cards, where
  `ready`'s does — not per instrument.

### Judgment calls — decided

- **`expired`'s card carries the revert form; `archived`'s does
  not** (2026-09-09). Revert already accepts `expired`, so the
  control is truthful there. Unarchive lives in the lobby, and a
  Setup page is not where a session comes back from the archive.
- **The gate moves in `_can_edit_instrument`, not at the 24 call
  sites** (2026-09-09). The call sites are already correct — they
  ask "is this editable"; the helper answered the wrong question.

### Blast radius (measured)

At `3f2df04c`:

- `grep -rn "_require_instrument_editable(" app/web/routes_operator/` →
  **24** call sites: `_instruments.py` 18, `_instruments_band2.py` 3,
  `_instruments_pagination.py` 3. **None change** — the helper does.
- `_can_edit_instrument` — 1 definition (`_shared.py:385`), 1 caller.
- `grep -c "is_ready" app/web/templates/operator/instruments_index.html`
  → **18**, of which the ones gating *mutation* move to `can_edit`;
  the rest guard other things and must be read individually.
- `app/web/views/_instruments.py:716-717` — `is_ready` /
  `can_edit = not is_ready`, the page's half of the same mistake.
- 2 specs: `spec/instruments.md` (the "409 once the session is
  `is_ready`" sentence at §"All three call…") and `spec/lifecycle.md`
  §5, which lists Instruments among the editable surfaces.

### PR ladder

1. **PR 1 — the lifecycle gate, route and page together.**
   `_can_edit_instrument` becomes `is_editable`; the view's `can_edit`
   stops deriving from `is_ready`; the template's mutation gates
   follow `can_edit`. A per-status matrix test replaces the
   measurement above, asserting both the route's 409 and the page's
   absent controls. Landing these together is deliberate — gating the
   route alone would leave live buttons that 409, which is the shape
   Item 3 existed to remove. Must not touch: the lock card, the copy,
   or `is_ready` where it guards something other than mutation.
2. **PR 2 — the lock card on `expired` and `archived`.** The existing
   `card lock` extended to the two states, with `expired` carrying the
   inline revert form and `archived` naming the lobby path. Must not
   touch: the gate.
3. **PR 3 — the spec.** `spec/instruments.md`'s gate sentence and
   `spec/lifecycle.md` §5's editable-surface list.

**No scaffold slice.** `CLAUDE.md`'s scaffold-first rule is for a new
page, card or navigation affordance. This extends a card the page
already renders on `ready` to two more states; the shape is agreed
because it is already on screen. Recorded here because the rule was
considered rather than skipped.

### Status

**2026-09-09 — PR 1 landed. PRs 2 and 3 outstanding.**

**The ladder held**, with one boundary adjustment. PR 1 was scoped to
"must not touch the copy", and could not keep to it: the disabled
controls' `title` attributes read *"Revert to draft to add or delete
instruments."* under an `is_ready` branch. Widening the gate without
touching them would have left an `archived` operator told to revert —
a path `revert_session_to_draft` refuses, since it accepts only
`ready` and `expired`. So PR 1 adds `lock_action` to the view (the
recovery path out of each locked state) and composes the same
sentences from it. Shipping a knowingly false tooltip to protect a
slice boundary is the wrong trade; the lock **card** copy is
untouched and stays PR 2's.

**Eighth vacuous assertion, and the second caught by mutation rather
than by reading.** `test_the_card_lock_toggle_is_disabled_on_every_locked_state`
asserted `"disabled" in anchor` — satisfied by `aria-disabled="true"`
alone, so reverting the *class* gate changed nothing and the test
still passed. Now asserts the two gates apart. The related
near-miss: an earlier draft of the `?editing=` test checked
`'data-instrument-locked="false"' in page`, which `base.html`'s
inline CSS selectors make true on every page; it failed on `ready`
(where the behaviour was already correct), which is what exposed it.
**Both were mine, written this session, in the item whose whole
subject is a control that says one thing and does another.**

**`lock_action` was unpinned when first written** — blanking it
passed all 3290 tests. Two tests now hold it, including that
`archived` is never told to revert.

**Eight mutations, eight kills** after the two test fixes: the route
gate, the view's `can_edit`, the template's add/delete gate, the
Lock/Unlock class gate, its `aria-disabled` gate,
`editing_instrument_id`, a blanked `lock_action`, and `archived`
given the revert wording.

**No existing test broke** — 3267 → 3295, every new test additive.
That is the finding, not a convenience: nothing pinned the permissive
behaviour, which is why the gap survived Item 3's sweep of the same
class.

**Verified in Chromium** across four seeded sessions (two instruments,
an assignment and a submitted response each):

| state | live Delete buttons | Unlock | lock card | disabled title |
|---|---|---|---|---|
| `draft` | 2 | enabled | no | none |
| `ready` | 0 | disabled | **yes** | "Revert to draft…" |
| `expired` | 0 | disabled | **no** | "Revert to draft…" |
| `archived` | 0 | disabled | **no** | "Unarchive this session…" |

The two `no`s in the lock-card column are **PR 2's deliverable**: the
page now correctly offers nothing on those states and does not yet
say why. That silence is the gap Item 3 named on the roster pages,
and it is deliberate for one slice, not an oversight.

**Not verified here:** the Azure dev slot.

---

**2026-09-09 — PR 2 landed. PR 3 (the spec) outstanding.**

The lock card now covers all three locked states. `ready`'s sentence
is untouched; `expired` and `archived` get their own, each naming the
way out that state actually has.

**Both ways out were measured through the route, not assumed from the
service.** `revert_session_to_draft` accepts `ready` and `expired`,
and the `/revert` route delegates with no lifecycle precondition of
its own — posted and confirmed 303 → `draft` from both. From
`archived` it answers **409**, which is why that branch offers no
form: a revert button there would be the dead control Item 3 removed
from the roster pages.

**The archived branch's link was nearly a finding against itself.**
The card sends the operator to `/operator/sessions/archived` to
unarchive, and a first browser check found **no Unarchive control on
that page**. It is inside a `<template>` — the bulk-action expander
the lobby's JS clones once rows are selected — so it is absent from
the DOM until then. Re-checked by actually ticking a row: the control
appears and is enabled. The instruction is true. Recorded because the
first measurement said otherwise, and shipping on it would have been
this item's own defect committed while fixing it.

**Five mutations, five kills**: the card re-gated on `is_ready`,
`archived` given the revert form, the `expired` copy reverted to
"ongoing", the lobby link dropped, and `is_archived` forced False.

**Verified in Chromium**, including driving the flow rather than
reading the markup:

| state | card | revert form | lobby link |
|---|---|---|---|
| `draft` | no | — | — |
| `ready` | yes | yes | no |
| `expired` | yes | yes | no |
| `archived` | yes | **no** | **yes** |

The `expired` card's revert was clicked through end to end: the
button is disabled until the confirm tick, the post lands on `draft`,
and the lock card disappears.

---

**2026-09-09 — PR 3 landed. Item 6 closed.**

`spec/lifecycle.md` §5 and `spec/instruments.md` now describe the
`is_editable` gate and the three-state lock card. Two of the edited
passages were **my own prose from Item 3**, false one item later —
the same pattern every item in this segment has turned up.

**A pre-existing spec error, corrected on the way.** The
add-instrument route was documented as `is_ready` → **400** *"Cannot
add instruments to an active session"*. Measured across all five
states: it has always raised **409** through the shared gate, with
that gate's own message. Predates Segment 19I.

**`spec-writer`: three findings, all verified before acting, all
adjudicated.**

1. **Undeclared doc impact — `spec/sort_by_reviewee.md`.** Its Sort-cell
   sentence said *"the instrument's `is_ready` lock applies"*. That
   was accurate until PR 1: Band 2 is `inert` unless the card is
   unlocked, and `editing_instrument_id` is forced `None` whenever
   `can_edit` is false — so moving `can_edit` to `is_editable`
   silently brought `expired` and `archived` under the lock.
   Confirmed by render: `unlocked_cards` is 1 on `draft` /
   `validated` and 0 on all three locked states. **Item 6 made this
   stale and the plan had not named the file** — bullet added to
   `### Doc impact` per the plan convention, and the sentence
   rewritten to describe the mechanism rather than a predicate it
   never read directly.
2. **`spec/lifecycle.md` §3.1 named the wrong gate for two
   surfaces**, both predating Item 6 and both verified by grep:
   instrument CRUD calls `_require_instrument_editable` (18 sites in
   `_instruments.py`, 0 calls to `_require_editable`), and the
   email-template editor calls **no** lifecycle gate at all — which
   §5 of the same file has always said, so the two passages
   contradicted each other. Fixed while in the sentence: leaving it
   would have meant implicitly endorsing it in the same pass.
3. **The Assignments page has this item's defect, unfixed.** Its
   routes gate on `_require_editable` (`is_editable`) while
   `session_assignments.html` still disables its controls on
   `is_ready` alone — so on `expired` and `archived` it offers live
   controls the routes refuse. Verified. That is the *dead-control*
   shape Item 3 removed from the rosters, not this item's
   destructive one, and it is a different surface: **reported, not
   fixed** — see "Out of scope".

**Not verified here:** the Azure dev slot. PRs 1 and 2 changed
templates; PR 3 changed only prose.

---

**Measured after:** the suite went 3295 → **3310**.

**CI caught a break my local gate could not see.** The new lock-card
test imported its fixtures as
`from tests.integration.test_instruments_lifecycle_gate import ...`,
and `postgres` failed collection with `ModuleNotFoundError: No module
named 'tests'`. It passed locally because I run
`.venv/bin/python -m pytest`, and `python -m` puts the working
directory on `sys.path`; CI runs the bare `pytest`, which does not.
Reproduced locally by switching invocation, which is now the gate:
**`.venv/bin/pytest`, not `python -m pytest`.**

The repo's convention was already there and I missed it — helpers are
shared through a `_`-prefixed module imported relatively
(`from ._full_matrix import ...`), which works because
`tests/integration/__init__.py` makes the package. Mine was the only
absolute `from tests.` import in the suite. Fixed by extracting
`tests/integration/_instrument_states.py` and importing it relatively
from both files, so the two test modules no longer depend on each
other either.

**Not verified here:** the Azure dev slot.

### Definition of done

- The per-status matrix asserts, for all five states, the route's
  status **and** whether the page offers the control — both ways
  round, so neither half can drift.
- A delete attempt on `expired` and on `archived` leaves the
  instrument, its assignment and its response in place, asserted by
  count.
- `draft` and `validated` keep every instrument control, asserted.
- The lock card renders on `ready`, `expired` and `archived` and not
  on `draft` / `validated`; `expired`'s carries the revert form and
  `archived`'s does not, asserted.
- Every new assertion mutation-checked.
- `ruff check .` and `pytest -q -n auto` pass.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19I.6` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- **Whether `archived` should be read-only for *everything* on this
  page, including the collapse / expand and sort state.** This item
  says no — those are per-viewer display state, not session data —
  but the author may want an archived session to render frozen. Not
  blocking: the gate lands either way.

### Out of scope

- **The other Setup surfaces on `expired` / `archived`.** Item 3
  already gated the four roster pages; nothing else was measured as
  permissive here, and a sweep is not what this item is.
- **Response-Type Definitions** beyond what the shared helper already
  covers. The three RTD call sites move with `_can_edit_instrument`
  and get no separate treatment.
- **A general "finished session" read-only mode** across the operator
  UI. That is a design, not a fix, and belongs in
  `guide/deferred_consolidated.md` if the author wants it.
- **The Assignments page's dead controls on `expired` / `archived`**
  (found by `spec-writer` at this item's close, 2026-09-09). Its
  routes gate on `_require_editable` while
  `session_assignments.html` disables on `is_ready` alone, so it
  offers controls the routes refuse — Item 3's shape, on a surface
  neither Item 3 nor Item 6 covered. Reported for the author to
  scope; fixing it here would widen the item past the page it names.
- **The four roster pages' missing lock card on `expired` /
  `archived`** (Item 3's own "Out of scope", still open). Instruments
  now has one and they do not, so the two surfaces differ until they
  catch up — recorded in `spec/lifecycle.md` §5.

### Doc impact

- `spec/instruments.md` — the gate sentence changes from "409 once the
  session is `is_ready`" to the `is_editable` rule, and the page's
  lock-card states are recorded (Item 6).
- `spec/lifecycle.md` — §5's editable-surface account gains
  Instruments under the same `is_editable` rule as the rosters;
  §3.1's list of `_require_editable` callers loses instrument CRUD
  and the email-template editor, neither of which calls it
  (Item 6).
- `spec/sort_by_reviewee.md` — **added at build**, not named at
  planning time: the Sort-cell lock sentence described an
  `is_ready` lock, and Item 6 brought `expired` and `archived`
  under it. See `### Status` (Item 6).
- `docs/status.md` — row at the close (Item 6).

## Item 7 — The Assignments search cannot see the tags

### Opportunity

The author, on closing Item 6: *"There's also a search box there that
probably can do with a similar treatment, though in this case, there's
more reason to segregate by reviewers vs reviewees; but at least allow
search/partition by name, email substring, and tags whole."*

**Two of the three asks are already shipped.** Measured at `42c21a04`
against a session with one pair — reviewer `Ana Lim /
ana@example.edu / Team A / Cohort 1`, reviewee `Ben Ord /
ben@example.edu / Team B`:

| query | `search_by` | result |
|---|---|---|
| `Ana` | `all` | matches |
| `ana@` | `all` | matches |
| `Ben` | `reviewee` | matches |
| `Ana` | `reviewee` | 0 — correctly scoped |
| `Team A` | `all` | **0** |
| `Cohort 1` | `all` | **0** |
| `Team B` | `all` | **0** |

So name and handle already match by substring, and the
reviewer/reviewee segregation the author asked for **already exists**
as a `Search by:` select (`all` / `reviewer` / `reviewee`,
`_SEARCH_BY_VALUES` in `_assignments.py`). What is missing is the
third: **the six tag columns are invisible to this search**, exactly
the gap Item 1 closed on the four roster Setup pages.

The page also has no typeahead — the roster pages gained one in Item 1
(distinct tag values, then `"Name (handle)"` people labels) — and its
placeholder reads `Name or email`, which is honest today and will not
be once tags match.

### Decision

**Teach the existing search the tag columns, keeping the rule Item 1
settled: text by substring, tags by whole value.** `search_by` already
scopes which side is matched, and tags belong to the reviewer and the
reviewee individually, so scoping falls out for free — `Team A` under
`Reviewers` matches reviewers tagged `Team A` and nothing else. That
is the segregation the author wanted, and it is already built.

Rejected: **a separate tag control** (a second select, or a `tag:`
prefix). Item 1 rejected the equivalent on the roster pages and the
reason holds harder here, where a `Search by:` select already occupies
that slot: two controls to express one filter, on a row that is
already a pair.

Rejected: **matching tags by substring**, for Item 1's reason —
whole-value is what keeps `Team A` from dragging in `Team A2`.

### Semantics

- Tag match is **whole value**, case- and surrounding-whitespace-
  insensitive; text stays substring. Per column, unioned, as Item 1.
- `search_by=reviewer` matches the reviewer's name, handle **and**
  `tag_1..3`; `reviewee` the reviewee's; `all` either side.
- A row whose reviewer or reviewee FK does not resolve is matched on
  the side that does, as Relationships does (Item 1).
- The `Showing N of M` hint and `PAIR_PREVIEW_LIMIT = 200` are
  unchanged. **Note the roster pages lift their cap to 500 when a
  filter is applied and this page does not** — out of scope here, but
  it means a tag matching more than 200 pairs renders 200 with the
  hint saying so.

### Judgment calls — decided

- **The `Search by:` select is not touched** (2026-09-09). It already
  segregates, and adding tags does not change what the three options
  mean.

### Blast radius (measured)

At `42c21a04`:

- `_apply_pair_search` (`app/services/assignments/_coverage.py:256`) —
  1 definition, **2 call sites** (`count_pairs`, `list_pairs`), plus a
  re-export in `app/services/assignments/__init__.py`. The whole
  change lands in that one function.
- `Reviewer.tag_1..3` and `Reviewee.tag_1..3` — 6 columns, already on
  the models; no migration.
- 1 template line (the placeholder), 1 spec.

**The architectural wrinkle, and the item's real risk.** The roster
pages filter **in Python**, over a loaded list, through
`views/_filters.py::_matches_row` — the function that *is* Item 1's
rule. Assignments filters **in SQL**, because `count_pairs` and the
200-row cap both run in the query. So the rule cannot simply be
reused: it has to be expressed a second time as SQL predicates, and
two expressions of one rule drift. See "Open questions".

### PR ladder

1. **PR 1 — the rule in SQL, plus the conformance test.** Tag
   predicates added to `_apply_pair_search`, and a test that runs the
   *same* table of cases against both `_matches_row` and the SQL path
   so a future edit to either shows up as a disagreement. Must not
   touch: `search_by`, the cap, the `Showing` hint.
2. **PR 2 — the placeholder and the spec.** `Name or email` becomes
   accurate; `spec/assignments.md` gains the matching rule pointing at
   `spec/setup_pages.md`'s account rather than restating it.

**No typeahead slice.** Adding one here is a new affordance on a page
that has never had it, and the author asked for matching, not
suggestions. Recorded in "Out of scope".

### Status

**2026-09-09 — landed in two PRs, as laid out.**

**The open question is closed by the author**, whose constraint was
*"Don't change what the count mean."* That settles it for the
duplicate-plus-conformance-test: `count_pairs` and the cap run in
the query, so the rule is expressed a second time in SQL and one
table of cases runs against both paths.

**An instrument partition was raised and set aside** (author,
2026-09-09): *"Partitioning by instruments over a large roster will
do very little since there will always only be a few distinct
instruments."* Measured before the decision, and worth keeping
because the measurement outlived the feature:
`_instrument_label` returns `short_label`, falling back to
`Instrument_{id}` — the stored `name` is *"a pure internal handle"*
and appears **nowhere** on the page, so the obvious implementation
(match `Instrument.name`) would have matched a string no operator
can see. Also found: the per-instrument `Show` checkboxes already
filter by instrument, **client-side over the rendered window**, so
they show a partial view on a session past the 200-row cap and
never move the count.

`spec-writer` caught that only *one* of those two was recorded. The
`Show`-checkbox finding went into the new Search-matching section;
the label finding did not, and this Status claimed both had. It is
now recorded where it belongs — the status table's Instrument-column
row, which read *"Short label or full name"* and was itself stale,
since `name` has not been in the label chain for some time. The
false claim is the thing worth keeping here: a Status entry
asserting a doc edit that was never made is the same defect class as
a page offering a control its route refuses.

**Mutation testing found the empty-term guard unpinned**, and then
found my first attempt to pin it *also* passed with the guard gone:
an empty term makes the name predicate `ILIKE '%%'`, which matches
every row whatever the tags do, so at `count_pairs` level the guard
is invisible. Asserted on `_tag_matches`, where it lives. Sixth
unpinned behaviour caught this way in the segment.

**Two of my tests asserted premises the fixture does not hold.**
`_assignment_states.seed_session_with_assignment` (written for Item
8) seeds a **self-review** row whose reviewee is the same person as
the reviewer and carries the same `Team A` tag. So `Team A` matches
under both scopes, and matches *both* pairs under `reviewer`, which
suppresses the `Showing N of M` hint. Rewritten against measured
counts — `Cohort 1` and `Team B` are the clean one-sided pairs —
and the shared-tag case gets its own test, because *scoping is per
side, not per person* is a real rule that only a self-review row
makes visible.

**Six mutations, six kills**: predicates dropped, whole-value
weakened to substring, the empty-term guard removed, the reviewee
side matched against the reviewer's columns, `tag_2` / `tag_3`
dropped, and the placeholder reverted.

**Measured after:** the suite went 3338 → **3382**.

**Not verified here:** the Azure dev slot. PR 2 changes one
placeholder string; the matching itself is exercised through the
route in the tests.

### Definition of done

- Each of the seven measured cases above asserted, including the two
  that must stay 0 (`Ana` under `reviewee`, and a `Team A2`-style
  near-miss that whole-value must exclude).
- The conformance test pins the SQL path and `_matches_row` to the
  same answers.
- Every new assertion mutation-checked.
- `ruff check .` and the **bare** `pytest -q -n auto` pass.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19I.7` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- **Whether to express the rule twice or unify the two search paths.**
  PR 1 as laid out duplicates it (SQL here, Python there) and pins
  both with one test. The alternative — moving Assignments to the
  view-layer filter — would unify the rule but changes what the count
  and the cap mean, since both currently run in SQL. **Recommend the
  duplicate-plus-conformance-test**, and record the unification as
  deferred; the author decides if that reads wrong.

### Out of scope

- **A typeahead / `<datalist>` on this page.** New affordance, not
  asked for. If it lands later it should reuse Item 1's two-part list.
- **The filtered cap.** The roster pages lift 200 → 500 under a
  filter; this page stays at 200. Same class, different constant, and
  nobody has reported it.
- **The Invitations and Responses pages**, which have their own
  searches. Not measured here.

### Doc impact

- `spec/assignments.md` — the search account gains the tag rule and
  points at `spec/setup_pages.md` "Search matching and suggestions"
  for the shared per-column rule rather than restating it (Item 7).
- `docs/status.md` — row at the close (Item 7).

## Item 8 — The Assignments page, told straight

### Opportunity

Found by `spec-writer` at Item 6's close and confirmed by render: the
Assignments page's lifecycle signalling is wrong in **both**
directions, and it is the last operator surface in this segment's
sweep that has not been corrected.

Measured at `42c21a04`, one pair per session, posting
`bulk-inactivate` to test the route:

| state | operator-actions card (search **and** bulk) | row checkboxes | bulk route |
|---|---|---|---|
| `draft` | present | 1 | 303 ✓ |
| `validated` | present | 1 | 303 ✓ |
| `ready` | **absent entirely** | 0 | 409 ✓ |
| `expired` | present | 1 | **409** ✗ |
| `archived` | present | 1 | **409** ✗ |

The template gates the whole card on `{% if not is_ready %}` while the
five mutating routes gate on `_require_editable` (`is_editable`). The
two disagree on three of five states:

- On **`expired` / `archived`** the page offers row checkboxes and live
  bulk Inactivate / Activate that every route refuses — Item 3's
  dead-control shape, on the surface Item 3 did not cover.
- On **`ready`** it goes the other way and hides the **search** along
  with the controls. Item 3 settled that the read-only half of the
  strip stays in every state, because reading a finished session is
  legitimate; this page removes the only way to find a row.

### Decision

**One predicate for the mutating half, and the read-only half in every
state** — Item 3's rule, applied to the surface it skipped.

The selection-driven controls (row checkboxes, bulk Inactivate /
Activate, the bulk form they post to) render only while `is_editable`,
which is what the five routes already enforce. The `Search by:`
select, the search box, Clear and `Showing N of M` render always.

Rejected: **gating the whole card on `is_editable`**, the smaller
diff. It would fix the dead controls and keep the `ready` regression —
an operator looking at an activated session still could not find a
row.

Rejected: **leaving `ready` alone** on the grounds that nobody
reported it. The page is the one surface where an operator goes to
check who is assigned to whom mid-session, which is exactly when the
session is `ready`.

### Semantics

- `is_editable` is `draft` or `validated`; this both narrows
  `expired` / `archived` and restores the search on `ready`.
- The routes are untouched — they already answer 409. The page is the
  courtesy; the route is the guarantee.
- A lock card is **not** added here. The four roster pages still lack
  one on `expired` / `archived` (Item 3's open gap, recorded in
  `spec/lifecycle.md` §5); adding one to Assignments alone would make
  a third inconsistent surface. See "Out of scope".

### Judgment calls — decided

- **The read-only half returns on `ready` as part of this item**
  (2026-09-09), rather than being split out. It is the same one-line
  gate: separating them would mean touching the same condition twice.

### Blast radius (measured)

At `42c21a04`: 1 template (`session_assignments.html`, **7** `is_ready`
uses — each read individually, since some may guard non-mutating
things as they did on the Instruments page), 1 view for the context
flag, 0 route changes (`_assignments.py` already calls
`_require_editable` at 5 sites), 1 spec.

### PR ladder

1. **One PR.** Route and page must agree in the same commit, as in
   Item 6 PR 1: gating one without the other leaves a state the other
   contradicts.
2. **The spec** rides with it — `spec/assignments.md` is small here and
   the change is one paragraph.

### Status

**2026-09-09 — landed in one PR, as planned.**

**The ladder held**, and the self-review toggle joined the mutating
half once measured: its route gates on `_require_editable` like the
other four, so line 97's `is_ready` was the same mistake in
miniature. Its title needed Item 6's `lock_action` for the same
reason — widening the gate without it would have told an `archived`
operator to revert, which `revert_session_to_draft` refuses.

**Two fixture faults, both caught by the tests failing rather than
passing.**

1. The self-review checkbox renders only when
   `block.self_review_total > 0`, so a roster of distinct people
   leaves it off the page entirely — my first fixture asserted on a
   control that was never there. Fixed by seeding a self-review row
   (`is_self_review=True`) alongside the ordinary pair. Had the
   assertion been written the other way round (`"disabled" in …`
   over an empty list) it would have **passed vacuously**; `assert
   boxes` is what caught it.
2. Adding that row broke the route test's
   `select(Assignment.id).…one()`, which then found two.

**The vacuous check I nearly shipped in the plan.** While measuring,
`"operator-actions-card" in body` read as true on every state — the
string appears **15 times** in `base.html`'s inline CSS. The item's
table counts the rendered `<div>` instead, and the test module says
so at the top of its constants.

**Five mutations, five kills**, including the smaller diff the
Decision rejected: gating the whole card on `can_edit` fixes the dead
controls and keeps the `ready` regression, and six tests fail on it.
That the tests distinguish the two designs is the point.

**Verified in Chromium** across all five states, and the `ready`
search **driven**, not just rendered:

| state | search | `Search by:` | row boxes | select-all | bulk | self-review |
|---|---|---|---|---|---|---|
| `draft` | yes | yes | 2 | yes | yes | live |
| `validated` | yes | yes | 2 | yes | yes | live |
| `ready` | yes | yes | 0 | no | no | disabled, "Revert to draft…" |
| `expired` | yes | yes | 0 | no | no | disabled, "Revert to draft…" |
| `archived` | yes | yes | 0 | no | no | disabled, "Unarchive this session…" |

On `ready`: 2 rows → search `Ben` → 1 row, hint `Showing 1 of 2.`,
Clear → 2 rows.

**Measured after:** the suite went 3310 → **3338**.

**`spec-writer`: six confirmations and three findings, each verified
before acting.**

1. **My own new prose was loose.** `spec/lifecycle.md` said the
   self-review toggle "moves with the mutating half" — behaviourally
   right, structurally misleading: it **disables in place** where the
   bulk controls **disappear**, because the row it sits in is a status
   table that reads in every state. Rewritten to say which manner.
2. **Undeclared doc impact — two files.** `spec/setup_pages.md` and
   `spec/operator_ui_concept.md` both described the roster lock card
   as "the same pattern the Instruments **and Assignments** pages
   use". Item 8's new text says Assignments has no lock card, so
   those lines now contradicted it — and `operator_ui_concept.md`
   already contradicted *itself*, since its P4 records that the three
   post-Operations pages retired their `.card.lock` notices.
   `session_assignments.html` carries a comment saying the same. Both
   corrected; bullets added to `### Doc impact` per the plan
   convention.
3. **A false route and false button labels, one paragraph below the
   text this item edited.** `spec/assignments.md`'s "Bulk-set
   Include" named `POST /assignments/include` taking
   `include=true|false`, with buttons `Include selected` /
   `Exclude selected`. Verified: **no such route exists**, and
   neither label appears in any template — the real routes are
   `bulk-inactivate` / `bulk-activate` over the helper the section
   correctly named. Corrected, since the section describes the very
   card this item changed.

**One thing `spec-writer` reported that measurement overturned.** It
flagged that `spec/setup_pages.md` and `operator_ui_concept.md`
contradict the "no lock card" claim — which is right — but the
underlying question is whether Assignments renders one, and
`grep -c "card lock" session_assignments.html` returns **1**. That
single match is inside a comment recording the card's *retirement*.
The claim stands; the check that looked like it disproved it was
counting a comment. Recorded because it is the same shape as this
item's own vacuous-check finding, one layer up.

**Not verified here:** the Azure dev slot.

### Definition of done

- A per-status matrix asserts, for all five states, the route's status
  **and** what the page offers, both halves, both ways round.
- The search box, `Search by:` select and Clear render on all five
  states, asserted.
- Row checkboxes and the bulk form render only on `draft` /
  `validated`, asserted.
- Every new assertion mutation-checked.
- `ruff check .` and the **bare** `pytest -q -n auto` pass.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19I.8` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- None. The rule is Item 3's, already settled and twice applied.

### Out of scope

- **A lock card on Assignments.** The roster pages still have none on
  `expired` / `archived`; Instruments gained one in Item 6. Adding a
  third variant before the rosters catch up would widen the
  inconsistency rather than close it. The rosters' gap is the one to
  fix first.
- **The filtered cap** and **the typeahead** — Item 7's "Out of scope",
  same reasons.

### Doc impact

- `spec/assignments.md` — the page's lifecycle account states the
  `is_editable` gate on the selection surface and that the read-only
  half renders in every state (Item 8).
- `spec/lifecycle.md` — §5's surface list gains Assignments alongside
  the rosters and Instruments (Item 8).
- `spec/setup_pages.md` and `spec/operator_ui_concept.md` — **added
  at build**, not named at planning time: both said the roster lock
  card follows "the same pattern the Instruments **and Assignments**
  pages use", which this item's new prose contradicts. See
  `### Status` (Item 8).
- `docs/status.md` — row at the close (Item 8).

## Item 9 — The Assignments strip finishes the job

### Opportunity

The author, after exercising Item 7's search against a large mock
roster: *"my sense is that the search/partition is most useful for
isolating the assignments attached to an individual, whether reviewer
or reviewee; less so for the tags (too many rows identified)"*.

Two gaps follow from that use, and a third was found measuring them.

**1. No typeahead, and the search cannot be completed without one.**
The four roster pages gained a `<datalist>` in Item 1; this page has
none (`grep -c "<datalist>"`: reviewers 1, reviewees 1,
relationships 4, observers 1, **assignments 0**). Isolating *this*
Ana rather than every Ana is exactly what a completed handle does and
partial substring cannot.

**2. No status filter, on the page whose own buttons set the status.**
`Assignment.include` is the boolean the strip's **Inactivate** /
**Activate** buttons flip, and rows with `include=False` already
render dimmed — the state is visible and **unfilterable**. Measured:
no `filter_status`, no `include=` filter anywhere in
`session_assignments.html`. So an operator can bulk-inactivate fifty
rows and have no way to list them back.

**3. A typeahead cannot ship without the picked-label rule.**
Measured at `b4724e16` — submitting a label as-is returns **nothing**:

| term | `search_by` | rows |
|---|---|---|
| `Ana Lim (ana@example.edu)` | `reviewer` | **0** |
| `Ana Lim (ana@example.edu)` | `all` | **0** |
| `Ana Lim` | `reviewer` | 2 |

`%Ana Lim (ana@example.edu)%` is a substring of no name and no
email. So the rule that turns a picked label into an exact handle
match is not polish — without it, clicking a suggestion empties the
table.

### Decision

**Three controls in the roster's own shape: `Status:`, `Search by:`,
`Search:` with a typeahead.**

The status filter is `Assignment.include`, offered as All / Active /
Inactive — the vocabulary the page's buttons already use.

**The `Search by:` select stays.** It was proposed for replacement on
the reasoning that a typeahead makes the reviewer/reviewee partition
redundant. It does not:
`csv_imports.check_cross_table_identity` documents that *"the person
is both reviewer and reviewee, common in peer review"*, so a picked
label under `all` returns **both** the reviews that person must write
and the reviews written about them. Those are different operational
questions — chasing a late reviewer, versus checking a reviewee's
coverage — and only the select separates them. Confirmed with the
author 2026-09-09.

The typeahead offers **name / handle labels only, both sides in one
list**. Tags are excluded from the list (not from matching): the
author's measurement is that a tag identifies too many rows to be a
useful partition here, where the roster pages' tags partition a
roster of people. **Tag *matching* is untouched** — it costs three
ORed comparisons per side and the Item 7 conformance table already
protects it; removing it would be churn with a regression risk and no
gain.

One list rather than one per side, because `search_by` is a select
the operator can change without a reload — a per-side list would need
JS, and the picked handle resolves against whichever side
`search_by` allows anyway.

Rejected: **swapping the select for the status filter**, the author's
first proposal, for the both-sides reason above.

Rejected: **tags in the datalist**, per the measurement that prompted
this item.

### Semantics

- Status is `all` (anything unrecognised falls through, as the
  rosters do), `active` → `include is True`, `inactive` →
  `include is False`.
- **Status composes into `Showing N of M`**, as it does on the roster
  pages (`views/_filters.py` header: *"Filters compose: status +
  search"*). `N` becomes the pairs matching **both** filters; `M`
  stays every pair in the session. This is the one place the item
  touches the count, and it is the rosters' own reading of the same
  sentence rather than a new one — flagged because the author's Item
  7 constraint was that the count keep its meaning.
- **The column chips stay unfiltered.** `col_data_sample` is built
  from an unfiltered `list_pairs` precisely so a search never flips a
  chip; the status filter must not reach it either.
- A picked label exact-matches the **handle**, case-insensitively, on
  whichever side `search_by` allows. Detection is
  `_picked_label_handle` against the **uncapped** label set, so a
  label past the display cap that the operator types from memory is
  still recognised, and it requires an `@` in the tail — a tag value
  like `Group (B)` is not a handle.
- An unpicked term matches as Item 7 left it: name / handle by
  substring, tags by whole value.

### Judgment calls — decided

- **The pick rule runs in Python, not SQL** (2026-09-09).
  `_picked_label_handle` is pure string work over a list of labels
  and touches no database, so it runs in the route before the query
  and only the resulting *predicate* differs. Unlike the tags, there
  is no second copy of the rule to keep in step.
- **Labels come from the whole roster, capped only for display**
  (2026-09-09), matching Item 1: the detection set is uncapped, the
  rendered list is not.

### Blast radius (measured)

At `b4724e16`:

- `count_pairs` / `list_pairs` — **4 call sites**, all in
  `_assignments.py`; **2 of them deliberately unfiltered** (the chip
  sample) and must stay so.
- `_apply_pair_search` — 1 definition, 2 call sites.
- `_filters.py` — `_picked_label_handle`,
  `_extract_filter_label_tail`, `_reviewer_labels`,
  `_reviewee_labels` all exist and are reused; one new builder.
- The page loads **counts only** today
  (`existing_reviewer_count` / `existing_reviewee_count`), so the
  labels need `list_reviewers` / `list_reviewees` — both already in
  `_coverage.py`.
- 1 template (`filter-row` gains a select and a `<datalist>`), 1
  spec.

### PR ladder

1. **PR 1 — the status filter.** `include` filtering through
   `count_pairs` / `list_pairs`, the `Status:` select, the chip
   sample left unfiltered. Self-contained and useful alone. Must not
   touch: the search.
2. **PR 2 — the typeahead and the picked-label rule.** The label
   builder, the `<datalist>`, and the exact-handle predicate. Must
   not touch: the status filter, tag matching.
3. **PR 3 — the spec.**

### Status

**2026-09-09 — landed in three PRs, as laid out.**

**The swap question was settled by the author before the build**:
the `Search by:` select stays, because
`check_cross_table_identity` documents that the same person is
routinely both reviewer and reviewee, so a picked label under `all`
returns both the reviews they must write and the reviews about them.

**Two latent traps in the page, both found rather than reasoned
about.**

1. `col_data_sample` was aliased to `pair_sample` whenever no search
   was active, to skip a second query. Filtering `pair_sample` by
   status would have silently filtered the **column chips** too. The
   condition now covers both filters.
2. Naming the route parameter `status` shadowed the module-level
   `status` import, and the page died with
   `AttributeError: 'str' object has no attribute 'HTTP_200_OK'`.
   Found by running it. It is `filter_status` with a `status` alias,
   so the URL is unchanged.

**The datalist quietly gutted four existing sort assertions, and
that is the finding of this item.** `test_assignments_sort.py`
compares where names appear in the document; the new `<datalist>`
renders **before** the table and is sorted alphabetically, so
`find()` began returning its hits. **One test failed loudly — the
descending one. The three ascending ones would have passed whatever
order the table was in.** All five are now scoped to the table and
mutation-checked: removing or inverting the sort fails three of
them, where before the fix the ascending one survived both.

The lesson generalises past this page: **a test that locates content
by position in a whole rendered document is one new element away
from proving nothing**, and the element that breaks it need not be
near the thing under test.

**Three of my own assertions proved nothing until fixed.** The chip
test matched `data-col-chip`, an attribute that does not exist,
comparing `[] == []`; two pick tests called the service directly
with a label the *route* resolves, so they tested a path the
operator never takes. Rewritten to assert the enabled chip set (and
that it is non-empty), and to exercise the pick through the route
as well as the predicate.

**Nine mutations, nine kills** across the two code PRs: the status
filter never applied, active/inactive swapped, the chip sample
inheriting the filter, the route-level normalisation dropped, the
sort removed, the sort inverted, and the pick predicate's three
paths.

**Two process failures worth recording, both mine.**

- A mutation loop ran `git checkout -- app/` while PR 2's app edits
  were **uncommitted** and deleted them; the tests survived (they
  live under `tests/`), so the file passed in isolation before the
  run and failed after. The same mistake was made earlier in this
  segment on a roster template. The guard is to commit before
  mutating, which PR 1 did and PR 2 did not.
- The gate was chained as `ruff && pytest | tail`, and a pipe makes
  the exit status `tail`'s — so a failing suite still satisfied the
  `&&` and a red commit was pushed. Exit codes are captured, not
  piped, from here.

**Measured after:** the suite went 3382 → **3403**.

**`spec-writer` adjudicated, 2026-09-09.** It confirmed the status
mapping table, the `Showing N of M` composition, the chips ignoring
both filters, the `REVIEWERS_DATALIST_CAP` cap, and the
excluded-side `sa_false()` rule against the code. Three flags:

1. **Acted on.** The new prose said `include=False` "already dims a
   row". It does not, and never did: the `<tr>` carries only
   `data-row-instrument`, and the Include cell's pill swaps
   `pill-info` → `pill-empty`, a warning-coloured badge
   (`base.html:2867`). I had copied the claim from
   `spec/assignments.md`'s own older Columns paragraph, so the error
   was pre-existing and my line propagated it. Both are corrected,
   the older one with a dated note — a fix on a line the item was
   editing anyway, not a sweep.
2. **Noted, not acted on.** The suite does not exercise the *pure*
   one-sided `allowed == []` → `sa_false()` branch: the shared
   fixture seeds Ana Lim on both sides, so
   `assignments_picked_handles` always returns both handles and the
   scoping test exercises the narrowing, not the empty case. Correct
   by reading; unasserted end-to-end. Recorded rather than fixed
   because the fixture is shared and reshaping it to cover this
   would weaken the self-review coverage it was added for.
3. **Noted, not acted on.** `spec/operator_ui_concept.md:120` still
   lists the Rule column retired 2026-05-26, and does not mention
   the `Status:` select or the typeahead. Pre-existing drift in a
   doc Item 9 does not commit to; already a standing open item.

**Not verified here:** the Azure dev slot. Both PRs changed the
template.

### Definition of done

- Status filters to exactly the `include` value, asserted for all
  three options, and `all` returns everything.
- The chip sample is **not** filtered by status or search, asserted —
  the reason it exists.
- A picked label returns that person's rows and **not** a
  same-prefix handle's (`ana@` vs `ana2@`), asserted both ways.
- A picked label scoped to `reviewer` returns only the pairs that
  person reviews, asserted against a session where they are on both
  sides.
- A tag value in the search box still matches (Item 7 untouched), and
  is **absent** from the datalist.
- `Showing N of M` reflects both filters, asserted.
- Every new assertion mutation-checked.
- `ruff check .` and the **bare** `pytest -q -n auto` pass.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19I.9` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- None. The swap question was put to the author and settled: the
  select stays.

### Out of scope

- **Invitations and Responses**, which `_filters.py` already has
  builders for (`invitations_search_options` /
  `responses_search_options`) and whose templates may have the same
  gap. The author is taking those next as their own work; this item
  does not pre-empt it.
- **Retiring tag matching here.** Kept deliberately — see Decision.
- **The filtered cap** (200, unlifted) — Item 7's "Out of scope",
  unchanged.

### Doc impact

- `spec/assignments.md` — the Search matching section gains the
  typeahead and the picked-label rule; a new note records the status
  filter and that the chip sample stays unfiltered (Item 9).
- `docs/status.md` — row at the close (Item 9).

## Item 10 — one preview-count sentence across seven pages

### Opportunity

The author, reading the Assignments page after Item 9: the
`Showing first N of M unique pairs.` line is in the right place but
"the styling seems slightly different from the version in the
rosters", and the page also carries a second, separate
`…and X more not shown.` below the table.

Both observations are correct, and measuring the seven preview
pages found the divergence is wider than styling:

| Page | Notice | Position | Class | Capped? |
|---|---|---|---|---|
| Reviewers / Reviewees / Relationships / Observers | `Showing N of M.` | top-left of table card | `.muted .table-showing-hint` | 200 / 500 |
| Assignments | `Showing N of M.` | filter row, flush right | `.muted` | — |
| Assignments | `Showing first N of M unique pairs.` | top-left of preview card | `.form-help` | 200 (`PAIR_PREVIEW_LIMIT`) |
| Assignments | `…and X more not shown.` | below the table | `.form-help` | — |
| Invitations / Responses | `Showing N of M.` | filter row, flush right | `.muted` | **none** |

Three findings, all measured rather than reasoned about:

1. **The styling difference is real and has a cause.**
   `.table-showing-hint` (`base.html:1392`) sets only a margin, so
   the text inherits body size; `.form-help` (`base.html:2618`) sets
   `font-size: var(--fs-small)`. The Assignments line renders
   *smaller* than the rosters'.
2. **Invitations and Responses have no row budget at all.**
   `rows = views.filter_*_rows(all_rows, …)` with no slice
   (`_operations.py:320`, `:628`). They render every matching row,
   however many. So `Showing first N of M` would be false there — N
   always equals M.
3. **The roster sentence already conflates two things.**
   `total_row_count = len(all_reviewers)` — the *unfiltered* total —
   but `displayed_row_count = len(filtered[:cap])`
   (`_setup_reviewers.py:139-145`, `:196`). Filter 1,240 to 3 and it
   says `Showing 3 of 1,240`, a filter report; cap 300 to 200 and it
   says `Showing 200 of 300`, a cap report. One sentence, two
   meanings. Appending "; X more not shown" to it unconditionally
   would be **wrong** in the filter case: rows excluded by a filter
   are not withheld, they do not match.

### Decision

One sentence, one position (top-left of the table card), one class,
on all seven pages — with the clauses varying so each branch stays
true:

| State | Sentence |
|---|---|
| Capped, unfiltered | `Showing first 200 of 1,240 reviewers; 1,040 more not shown.` |
| Capped, filtered | `Showing first 500 of 900 matching reviewers; 400 more not shown.` |
| Filtered, under cap | `Showing 3 of 1,240 reviewers.` |
| Unfiltered, under cap | *(nothing rendered)* |

In every branch **M is the pool the numerator was drawn from**, and
the word `matching` appears exactly when M is the matching count
rather than the whole roster. The `; X more not shown` clause
appears **only when the cap actually bit**.

Both decisions were put to the author (2026-09-09) and settled:

- **Invitations and Responses stay uncapped.** Rejected: adding the
  rosters' 200/500 cap. It would have made the `first …` branch
  reachable there and the seven pages uniform, and it is low-risk
  (measured: neither template contains a checkbox or a bulk action,
  so nothing can silently act on a hidden row) — but it is a
  behaviour change on two read-only monitoring pages, and the author
  chose not to buy uniformity with one. Consequence: only the
  filter branch ever fires on those two.
- **M = matching rows in the capped branch.** Rejected: keeping M as
  the whole roster always. `first 500 of 1,240` when only 900 match
  overstates what the filter left, and the withheld count would be
  computed against the wrong denominator.

Rejected for the shape itself: **two separate lines** (a filter
count where it is now, plus a cap line top-left). Most precise, but
it is the bottom-of-table duplication this item exists to remove,
relocated.

### Semantics

Per boundary, for the helper that composes the sentence:

- **`shown == matching == total`** — nothing renders. Preserves
  today's rule (`test_setup_showing_hint.py:146`): `Showing 6 of 6`
  is noise.
- **`shown == matching < total`** (filtered, under cap) — filter
  branch, no `first`, no withheld clause.
- **`shown < matching == total`** (capped, unfiltered) — cap branch,
  M is the total, no `matching` word.
- **`shown < matching < total`** (capped *and* filtered) — cap
  branch, M is the matching count, `matching` word present. **No
  existing test covers this state**; verified by reading all 30
  `Showing` sites in `tests/`. `test_reviewers_page_filter.py:195`
  looks like it does but seeds `status=active` against 600 active
  rows, so total == matching == 600 and the two readings coincide.
- **Zero matches** — the no-match message already owns that state
  (`session_assignments.html:309`); the count line does not render.
  Assignments today renders `Showing 0 of 1`
  (`test_assignments_page_generate.py:240`) from the filter-row
  span, which this item removes; the assertion moves to the new
  line's absence plus the no-match copy.
- **Noun per page** — `reviewers`, `reviewees`, `relationships`,
  `observers`, `assignments`; **Invitations says `reviewers`** and
  **Responses says `reviewees`**, because those tables are one row
  per reviewer and per reviewee respectively (verified:
  `build_invitations_rows` iterates `per_reviewer_progress`,
  `build_responses_rows` iterates `per_reviewee_coverage`).
- **Thousands separators** — kept, as Assignments already does
  (`"{:,}".format`), and extended to the roster numbers, which
  currently render bare.

### Judgment calls — decided

- **`.table-showing-hint` is the survivor**, not `.form-help`. The
  author named the rosters as the reference ("different from the
  version in the rosters"), and the hint is a statement about the
  table, not help text for a form control.
- **The count leaves `.filter-actions` on three pages**
  (Assignments, Invitations, Responses). `Clear` and `Apply` stay —
  they are actions; the count is a report, and the author's rule is
  that it always sits top-left.
- **The helper returns the composed string, not parts.** The
  branching is the contract; splitting it across a view helper and a
  Jinja `{% if %}` chain would put half the rule in a template,
  which `spec/architecture.md` reserves `app/web/views/` for.

### Blast radius (measured)

```
grep -rln "Showing" app/web/templates/                    → 8 files (7 pages + base.html)
grep -rln "table-showing-hint" app/web/templates/         → 5 files (4 rosters + base.html)
grep -rn "Showing" tests/ --include=*.py | wc -l          → 30 (11 files; ~9 are comments)
grep -rn "more not shown" app/ tests/ spec/ docs/         → 1 (session_assignments.html only)
```

Route modules carrying the context keys: `_setup_reviewers.py`,
`_setup_reviewees.py`, `_setup_relationships.py`,
`_setup_observers.py`, `_assignments.py`, `_operations.py` (two
handlers) — 6 files.

Specs describing the hint: `spec/setup_pages.md` (6 sites),
`spec/assignments.md` (3), `spec/operations_pages.md` (2),
`spec/lifecycle.md` (2), `spec/rrw_functional_spec.md` (1).
`spec/preview_hub.md:119` matches the grep but is an unrelated use
of the word.

### PR ladder

1. **The helper, the shared partial, and the four roster pages.**
   Establishes the contract on the pages that already have both the
   cap and the class, so the diff is copy + call-site only.
2. **Assignments.** Three notices collapse to one: the filter-row
   span and the below-table line go, the top-left line adopts the
   helper and the roster class. Must not touch the search, the
   status filter, or the chip sample.
3. **Invitations and Responses.** The count moves from the filter
   row to the top-left of the table card, noun `reviewers` /
   `reviewees`. No cap added — filter branch only. Must not touch
   the datalists (both already render them).
4. **Spec + `docs/status.md` row.**

### Status

**2026-09-09 — rungs 1 and 2 landed as laid out; 3 and 4 open.**

- **PR 1** (#2254) — `views.preview_count_line`,
  `partials/_preview_count_line.html`, the four roster pages.
- **PR 2** (#2255) — Assignments: the three notices become one.

**The plan's blast radius held.** Seven templates, six route
modules, ~30 test sites; nothing outside that list needed touching.

**Two findings from the build, both about tests rather than code.**

1. **The capped-and-filtered branch was untested, as the plan
   predicted, and the gap was invisible.**
   `test_filtered_cap_lifts_to_500` reads as though it covers it,
   but `status=active` matches all 600 of its rows, so the matching
   set and the roster are the same number. Any wrong-denominator
   bug would have shipped green. PR 1 adds a 600/550/500 case and
   asserts the two *wrong* numbers are absent, not merely that the
   right one is present.
2. **An assertion of mine matched a CSS comment, not markup.**
   `"Showing" not in actions`, scoped to everything above the
   Assignments preview card, failed — because `base.html` inlines
   `Apply (with optional Clear + "Showing N of M" counter)` in a
   comment. Scoped to the rendered `.filter-actions` row now. The
   same trap as Item 9's `operator-actions-card` assertion, in a
   different disguise: a substring search over a whole rendered
   document matches the app's own prose about itself.

**Decisions confirmed at build:**

- **`truncated_count` retired outright** (2026-09-09). Once the
  below-table line went, nothing read it; the helper derives the
  withheld count. `matching_count` left the Assignments template
  context for the same reason, though the local stays — it feeds
  the helper.
- **The no-match branch renders no count line** (2026-09-09). The
  Assignments preview card gates the table on `pair_sample`, and
  the count line sits inside that gate, so a search matching
  nothing shows only `No assignments match the search.` The
  assertion that pinned `Showing 0 of 1` now pins the line's
  absence. This is a real behaviour change, not just copy.
- **`base.html`'s `.filter-card` comment is left for PR 3**
  (2026-09-09). It names the counter that Invitations and
  Responses still render in their filter row; it goes stale when
  rung 3 moves theirs, not before.

**Mutations:** 10 on PR 1, 6 on PR 2, all killed. Both PRs
committed before their mutation run — the guard Item 9 established
after `git checkout -- app/` deleted uncommitted work twice.

**2026-09-10 — rungs 3 and 4 landed; the item closes.**

- **PR 3** (#2257) — Invitations and Responses; the count leaves
  `.filter-actions` on the last two pages, and `base.html`'s
  `.filter-card` comment is corrected where it actually went stale.
- **PR 4** — the five specs and the `docs/status.md` row.

**All seven pages verified as a set, not page by page:**
`grep -rn 'class="muted">Showing' app/web/templates/` returns
nothing, and all seven templates include the partial.

**One behaviour change fell out of the helper on rungs 2 and 3**, and
is recorded in the spec rather than left to be rediscovered: the old
per-page guards rendered a count whenever a filter was *active*, so a
search matching every row still printed `Showing 5 of 5.`. The helper
returns `None` when nothing was narrowed — Item 4's rule.

**`close_check` note adjudicated (2026-09-10).** It reported
`_operations touched; not in manifest: spec/validate_page.md,
spec/preview_hub.md`. Neither describes the count line —
`preview_hub.md:119` is an unrelated use of the word "Showing", and
`validate_page.md` never mentions it. The note flags specs that
mention the touched module, not the changed behaviour; no bullet
added.

**`spec-writer` adjudicated, 2026-09-10.** It verified every claim
in the five specs against the code — the four branches and their
wording, the three cap regimes, the per-page nouns, the
uncapped-by-construction reading of Invitations and Responses, the
`.form-help` / `.table-showing-hint` font-size claim, and the
select-all worked example's arithmetic — and found **no drift**.

One **omission** it raised, verified and acted on: the "a filter
matching nothing renders no count line" rule was stated only in
`spec/assignments.md`, which read as though that page were special.
It is not — all seven gate the whole preview card on the row list
and fall through to a "No … match the current filter." message
(`session_reviewers.html:311` `{% if reviewers or add_mode %}` …
`{% elif total_row_count > 0 %}`, and the same shape on the rest).
The rule now sits once in `spec/setup_pages.md` with the note that
it is the template's doing and not the helper's — the helper
returns `Showing 0 of 5 …` if it is ever called on that state — and
the Assignments paragraph points at it.

**Mutations:** 10 (PR 1) + 6 (PR 2) + 5 (PR 3) = **21, all killed**.

**Measured:** the suite went 3403 → 3425 (PR 1) → 3426 (PR 2) →
3430 (PR 3).

**Not verified here:** the Azure dev slot. Seven templates changed
across the three code rungs — a line moved between cards on three of
them, which the suite can only check as text.

### Definition of done

- One helper composes all four branches, unit-tested at each
  boundary including `shown < matching < total`, which nothing
  covers today.
- All seven pages render the line top-left of the table card in
  `.table-showing-hint`; asserted per page, scoped to the card.
- `…and X more not shown.` appears nowhere in `app/`.
- No count renders in `.filter-actions` on any of the seven.
- The quiet case still renders nothing (`Showing 6 of 6` absent).
- Every new assertion mutation-checked.
- `ruff check .` and `.venv/bin/pytest -q -n auto` pass.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19I.10` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- None. Both decisions were put to the author and settled before the
  ladder was cut.

### Out of scope

- **Adding a cap to Invitations or Responses.** Decided against
  above; recorded here so a later reader does not read the
  uncapped filter branch as an oversight.
- **The 200 / 500 split versus Assignments' flat 200.** Three pages
  keep one rule and one keeps another; unifying the *caps* is a
  behaviour change this item does not make. Recorded in
  `guide/deferred_consolidated.md` if it survives review.
- **The four roster pages' missing lock card** on `expired` /
  `archived` — Item 3's open gap, untouched.
- **Tags columns and column sort on Invitations / Responses** —
  raised by the author 2026-09-09 while rung 3 was pending, and
  measured rather than estimated, but **not decided**. If it goes
  ahead it is its own item, not a widening of this one.
  - *Tags are free.* `InvitationsRow.reviewer` and
    `ResponsesRow.reviewee` are the full ORM objects, so `tag_1/2/3`
    are already in the template's hands: no service, query or view
    change, just columns.
  - *Sort is nearly free to build.* The `data-rrw-sortable`
    primitive is declarative — the roster route wiring is a key
    set, a `getattr` resolver and one
    `decode_cookie_sort_spec` + `apply_cookie_sort` pair, ~15
    lines. The wrapper rows need a resolver that reaches
    `row.reviewer.name` rather than the rosters' one-liner.
  - *Sort is cheap to run.* Timed in Chromium against the shipped
    JS: **1,000 rows ≈ 22-26 ms**, 2,000 ≈ 43-61 ms, 5,000 ≈
    102-227 ms per click.
  - *The page is the expensive part, and already is.* Uncapped
    render, measured on SQLite in the agent container: **1,000
    rows → 669 ms / 1.1 MB (Invitations), 840 ms / 0.86 MB
    (Responses)**; 2,000 rows → 1,207 ms / 2.1 MB and 1,463 ms /
    1.5 MB. Sort adds ~3% to what the page already pays. The open
    question these numbers raise is not sort but **whether these
    two pages should stay uncapped at all** — which Item 10 asked
    and the author answered "yes" for the count line's sake, on a
    page that was not then known to cost a second and a megabyte.

### Doc impact

- `spec/setup_pages.md` — the "Showing N of M" hint section gains
  the four-branch sentence and the `matching` wording (Item 10).
- `spec/assignments.md` — the count line replaces the filter-row
  span and the below-table line; `unique pairs` becomes
  `assignments` (Item 10).
- `spec/operations_pages.md` — the muted "Showing N of M." note
  moves out of the button row to the top-left of the table, and the
  noun becomes `reviewers` / `reviewees` (Item 10).
- `spec/lifecycle.md` — the two sites naming the hint's position in
  the filter row (Item 10).
- `spec/rrw_functional_spec.md` — the one site describing where the
  hint sits (Item 10).
- `docs/status.md` — row at the close (Item 10).

## Item 11 — the roster table facility on Invitations and Responses

### Opportunity

The author, after Item 10 put one count sentence on all seven
preview pages: *"What would it take to include the same tag column
display, tag selection, sort, etc., facility in Invitations as in
Reviewers? Similarly for Responses and Reviewees?"*

Measuring the two pairs decomposed "the same facility" into four
independent parts with very different costs:

| Facility | Reviewers | Invitations | To port |
|---|---|---|---|
| Tag columns rendered | 3, labelled by the shared `field_label_header` macro | — | **Template only** |
| Column-visibility chips | chip row + CSS + **55 lines of inline JS** | — | See below |
| Column sort | `data-rrw-sortable` + `<thead>` + `<tbody class="rrw-rows">` + 8 annotated `<th>` + ~15 lines of route wiring | — | **Table restructure first** |
| Search matches tags | tags whole-value (Item 1) | name / email only | extend the filter + its datalist |
| Status filter | yes | yes | already there |
| Row select + bulk delete | yes | — | not applicable — read-only pages |
| 200 / 500 cap | yes | **none** | decided against in Item 10 |

Three findings shape the work more than the line counts do.

1. **Tags are already in the template's hands.**
   `InvitationsRow.reviewer` and `ResponsesRow.reviewee` are the full
   ORM objects, so `tag_1..3` need no service, query or view change.
2. **The column-visibility mechanism is duplicated four times**, not
   three as first counted — `session_reviewers`, `session_reviewees`,
   `session_relationships` and `session_assignments`, the last under a
   different storage key (`rrw-assignment-col-visibility`, which is
   why a grep for `tag-visibility` missed it). ~~55-line IIFEs on
   three pages and a 46-line variant on Assignments, **211 lines**~~
   — **corrected at build, 2026-09-10: all four blocks are identical
   and the total is 224 lines, 56 from each.** The original figures
   came from a measurement whose anchor walked back to an inner
   `forEach(function` rather than the IIFE opener, so it under-counted
   every block and mis-described Assignments as a variant. Plus four
   near-identical CSS blocks. Porting as-is makes it six copies. The
   two page-specific values are the storage key and the table id;
   everything else is the same code.
3. **Neither target page can take the sort primitive as it stands.**
   `session_invitations.html` and `session_responses.html` have **no
   `<thead>`, no `<tbody>` and no table `id`** — the tables are
   `<table><tr>…headers…</tr>{% for %}<tr>…`. The primitive requires
   all three, so sort begins with a structural change to each table.

### Decision

**Extract the column-visibility mechanism into a shared primitive
first, then port.** It follows the shape `data-rrw-sortable` already
proves in this codebase: declarative markup plus one implementation
in `base.html`. Rung 1 is worth landing even if the rest never
happens — it retires 211 duplicated lines and converts four pages
with no visible change.

Rejected: **copying the IIFE a fifth and sixth time.** It is the
cheaper diff and the wrong one; the mechanism is already the most
duplicated JS in the app, and two more copies would put a
five-way edit behind any future change to it.

Rejected: **generalising the chips into a server-rendered control**
(a form + a persisted per-user setting). The state is a per-browser
display preference, `localStorage` is where the app already keeps
those (`spec/settings_inventory.md`), and a round-trip per toggle
would be worse than the thing it replaced.

**Observers stays out**, at the author's instruction (2026-09-10).
It carries a single `tag_1` and no chip mechanism, so "the same as
the rosters" was never true of it; folding it in would mean deciding
what a one-tag chip row means, which is a different question.

### Semantics

- **Storage keys do not change.** The four existing keys stay
  exactly as they are, because renaming one silently resets every
  operator's saved column state on that page. The primitive reads
  the key from the markup instead of hard-coding it.
- **Slot names stay page-local.** The rosters use `tag-1..3` and
  `profile`; Assignments uses `rt1..3` / `et1..3` / `p1..3`. The
  primitive must not assume a vocabulary — it toggles
  `col-hidden-{slot}` on the table for whatever slot the chip names.
- **A chip with no data is disabled, not hidden**, and its column is
  hidden — today's behaviour, preserved.
- **A stored key naming a slot the page no longer has** is ignored,
  as today (the loop reads chips and consults storage, never the
  reverse).
- **Sort on an uncapped page.** Invitations and Responses render
  every matching row. The client-side sort reorders the DOM in
  place; measured in Chromium against the shipped JS, **1,000 rows
  ≈ 22-26 ms**, 2,000 ≈ 43-61 ms, 5,000 ≈ 102-227 ms per click.
  Against a page that already costs 669-840 ms to render and ~1 MB
  of HTML at 1,000 rows, sort adds ~3%.
- **Cookie-backed order.** The rosters persist the sort spec in a
  cookie and re-apply it server-side so the first paint lands in the
  chosen order. These two pages need the same, which means a
  sort-key resolver that reaches **through the wrapper**:
  `InvitationsRow.reviewer.name`, not `getattr(row, key)` as the
  rosters can use.
- **Tag search.** Reviewers matches `tag_1..3` by **whole value**
  (Item 1) while name and email match by substring; the two target
  pages must adopt the same rule rather than inventing a third, and
  their datalists must not offer tag values as suggestions (Item 9's
  finding: a tag identifies too many rows to partition by).

### Judgment calls — decided

- **Rung 1 converts all four existing pages**, not just the three
  that share the 55-line form. Leaving Assignments on its own
  variant would keep two mechanisms alive and lose most of the point.
- **The primitive lives in `base.html`** beside the sort JS, not in
  a new static file. `app/web/static/` is deliberately not a general
  asset pipeline (`CLAUDE.md`), and the sort primitive sets the
  precedent.
- **Reviewers' profile column stays un-hideable.** It renders
  `profile-col` but has no chip, where Reviewees has both. That
  asymmetry predates this item and is not its to settle; noted so a
  reader does not read the extraction as having dropped something.

### Blast radius (measured)

```
grep -rhoE '"rrw-[a-z-]*visibility"' app/web/templates/operator/*.html | sort -u
    → 4 keys (reviewer / reviewee / relationship tag-visibility, assignment col-visibility)
grep -rn "col-hidden" app/web/templates/operator/*.html
    → 4 CSS blocks + 4 JS toggle sites
IIFE line counts (corrected 2026-09-10): 56 each × 4 → 224
    the pre-build figures (55/55/55/46 → 211) came from a bad anchor; see Opportunity
grep -c '<th' on the target tables → invitations 7, responses 4
grep -c '<thead>' → invitations 0, responses 0        (the sort blocker)
```

Templates: 6 (four to convert, two to extend) + `base.html`.
Routes: `_operations.py` (two handlers) for the sort wiring.
Views: `_filters.py` (`filter_invitations_rows`,
`filter_responses_rows`, and both `*_search_options`).

Specs describing what changes: `spec/setup_pages.md` (the chip
pattern), `spec/operations_pages.md` (both pages' columns and
filter cards), `spec/settings_inventory.md` (lines 391-394 list all
four storage keys and their surfaces), `spec/sort_by_reviewee.md`
(the sort primitive's surface list, mirrored at
`settings_inventory.md:385`).

### PR ladder

1. **Extract the column-visibility primitive** into `base.html`;
   convert all four existing pages to it. Storage keys unchanged, no
   visible change. Must not touch the two target pages.
2. **Structure + sort on Invitations and Responses** — `<thead>`,
   `<tbody class="rrw-rows">`, a table `id`, `data-rrw-sortable`,
   annotated headers with `data-sort-value` cells, and the route
   wiring with a wrapper-aware resolver. No new columns yet.
3. **Tag columns + chips on both**, through the rung-1 primitive.
4. **Tag matching in both searches**, plus the datalist rule.
5. **Specs + `docs/status.md` row.**

Rungs 2-4 are independently shippable and each leaves both pages
coherent; rung 1 stands alone.

### Status

**2026-09-10 — rung 1 landed as laid out.**

The primitive lives in `base.html` beside the sort one; all four
pages converted; **-224 template lines, +130 in `base.html`**.
Storage keys, slot vocabularies and per-page CSS unchanged, as the
Semantics required.

**The plan's own line count was wrong and is corrected above.** The
duplication is 224 lines from four identical blocks, not 211 from
three-plus-a-variant. Same bad anchor, twice: the measurement that
produced 211 walked `rindex("(function")` back to an inner
`forEach(function`, and the *first* attempt at the removal used the
same anchor and cut nine lines off the top of each block, leaving
orphaned openers. Caught by grepping the templates for leftovers
rather than by the suite, which would not have noticed.

**`git checkout -- <file>` destroyed uncommitted work again**, on
`session_reviewers.html`, during the mutation run — the third time
this segment, and the first where the guard ("commit before
mutating") had already been written down by me and then not
followed. Everything after that point was committed before any
mutation.

**Two hazards of the extraction itself, both found by running it:**

1. `test_reviewers_profile_link.py` asserted `"profile-col" not in
   body` over the whole document, so it failed the moment
   `base.html` mentioned the class in a comment. Scoped to the
   table — which is what the test's own name claims — and bounded at
   `</table>`, since a slice to end-of-document still catches
   `base.html`'s trailing scripts.
2. **The primitive's own explanatory sketch is shipped inside every
   rendered page.** Written with real ids and slot names it is
   indistinguishable from markup to any unscoped assertion — the
   same trap, created by the fix for the trap. It now uses
   placeholders, pinned by a test.

**Verified in Chromium**, which the suite cannot do: Reviewers'
three chips with the empty `tag_3` disabled and its column hidden,
a toggle writing `{"tag-1":false,"tag-2":true}` (disabled slot
correctly absent) and surviving reload; and Assignments' three chip
rows / nine slots / one key — the shape that actually exercises the
grouping — with one click per group hiding its column and all nine
states riding in one key. No page errors on either.

**Mutations:** 5, all killed — a fifth copy of the toggle, a renamed
storage key, a table losing its key attribute, the sketch reverting
to real names, and the primitive deleted from `base.html`.

**Measured:** the suite went 3430 → **3464** (34 structural
assertions added).

**Not verified here:** the Azure dev slot.

**2026-09-10 — rung 2 landed as laid out.**

Both tables gained the shape the sort primitive needs (`id`,
`<thead>`, `<tbody class="rrw-rows">`), annotated headers, a
`data-sort-value` per cell, and the route re-applies the cookie so
the first paint is already ordered.

**Two decisions the plan did not anticipate:**

- **The progress columns sort by completion percentage, not the raw
  done count.** Totals differ per row, so "3 done" orders nothing an
  operator would recognise. `_completion_pct` returns `None` when
  there is nothing to do and the template emits an empty
  `data-sort-value` for the same state — measured first:
  `apply_cookie_sort` collapses `""` to `None` and the client
  comparator returns `null`, and **both sort it last regardless of
  direction**, so the two halves cannot disagree about where those
  rows land.
- **Two existing tests asserted `<th>Label</th>` verbatim** and broke
  on the sort button. Rewritten to match each label against its sort
  key inside `<thead>`, pinning both facts.

**The new tests' first draft was vacuous, and only a failure exposed
it.** Both builders default to `order_by(email)`
(`monitoring._assigned_active_reviewers`, `per_reviewee_coverage`),
and the seed's emails matched its names — so every name-ascending
assertion would have passed with the sort doing nothing. The seed now
uses emails in reverse name order. A second hole in the same file:
`client.cookies` persists, so the "unsorted" fetch taken *after* a
sorted one still carried the cookie; it is taken first now.

**The same hole appeared in the browser check.** Name-descending
happens to equal the default email order on both pages, so reloading
in that state could not distinguish "the server re-applied the
cookie" from "the server did nothing". Re-checked in the
**ascending** state, where the orders differ: Invitations reloads
Alpha/Bravo/Charlie against a default of Charlie/Bravo/Alpha, and
Responses Delta/Echo against Echo/Delta. No page errors on either.

**Mutations:** 4, all killed — the resolver reduced to the rosters'
plain `getattr`, the route dropping `apply_cookie_sort`, the
percentage becoming the raw count, and the tbody losing its class.

**Measured:** the suite went 3464 → **3472**.

**Not verified here:** the Azure dev slot.

**2026-09-10 — rung 3 landed as laid out, and cheaply.**

Three sortable tag columns and a `Show columns:` chip row per page,
through the primitive rung 1 extracted. **Template-only on the data
side**, exactly as the plan predicted: both row types already carry
the ORM object, so no service, query or view changed. Each page keeps
its own slot → column-class mapping, because the primitive
deliberately knows no slot vocabulary. Two new storage keys.

**The structural test now covers six chip pages rather than four** —
the two joined *through* the primitive, which is what extracting it
was for.

**A mutation survived, and it was the same hole for the third time in
this file.** Deleting the resolver's entire tag branch failed
nothing: the seed's tag values (Team X/Y/Z against Charlie/Bravo/
Alpha) happened to order identically to the **email default**, so a
resolver returning `None` for every row left the rows where the
assertion expected them. Responses had the same defect, unmutated
and unnoticed.

The seed now sets `tag_1` to an order matching **neither** the email
default nor the name sort:

    email default : Charlie, Bravo, Alpha
    name asc      : Alpha, Bravo, Charlie
    tag_1 asc     : Bravo, Alpha, Charlie

The pattern is worth naming, because it has now cost three rounds:
**when the fixture's natural order coincides with the order under
test, the test asserts nothing.** It is invisible in review — the
assertion reads correctly — and only a mutation finds it.

**Verified in Chromium** on both pages: the empty `tag_3` renders a
disabled chip with its column already hidden, clicking that chip does
nothing, hiding `tag_1` persists (`{"tag-1":false,"tag-2":true}` —
the disabled slot correctly absent) and survives reload. The run also
incidentally proves the two keys do not cross-contaminate: Responses
opened with `tag_1` visible after Invitations had hidden its own. No
page errors.

**Mutations:** 7 run. Six killed first time — a shared storage key, a
chip row losing its table pointer, the CSS mapping dropped, the empty
slot's chip rendering enabled, and two more below. The seventh (the
resolver's tag branch) survived, was fixed as above, and is now killed
along with its Responses twin and the valid-key set.

**Measured:** the suite went 3472 → **3481**.

**Not verified here:** the Azure dev slot.

**2026-09-10 — a rung 3 regression, found by the author and fixed.**

The three tag columns pushed the Invitations table past its
container. Measured in Chromium rather than eyeballed, this was **not
a small-screen problem**: the page caps at ~1396px and the table was
**1496px**, so it overflowed at every width up to 1920 and scrolled
the whole document sideways. Responses had the same defect above
~1150px of content — the author asked me to check it, and was right
to.

| Viewport | Invitations | Responses |
|---|---|---|
| 1024 | over by 556 | over by 91 |
| 1280 | over by 300 | fits |
| 1440 | over by 140 | fits |
| 1920 | over by 100 | fits |

**Fixed two ways, both measured before choosing:**

- Both tables now sit in `.table-scroll`, which `base.html` already
  provides and two other templates already use. Ten columns on a
  capped page will outgrow someone's screen whatever the headers say;
  the overflow belongs inside the card.
- Four Invitations headers narrowed — `Review Progress` →
  `Progress`, `Last reminder` → `Reminder`, `Email Sent` → `Sent`,
  and `Required Fields` **stacked onto two lines** rather than
  shortened (the author's call). Table 1496 → 1324, which fits the
  card exactly at 1440+.

**`Regenerate` → `Regen` was measured and rejected.** The author
proposed it; on its own it saved 32px of a 140px overflow, and after
the headers were narrowed it closed 31px of the remaining 36 —
leaving a 5px hairline scroll, worse than either outcome.
`Email Sent` → `Sent` closes the same gap exactly and costs no button
label.

**The lesson for the ladder:** rung 3 was verified functionally (do
the chips hide the right columns?) and not dimensionally (does the
table still fit?). Adding columns to a table is a layout change, and
the Chromium pass should have measured width against the container,
not only behaviour. Rungs 4+ measure both.

**Measured:** the suite is unchanged at 3481 — the fix is layout, and
the new assertions replace edited ones.

**2026-09-10 — rung 4 landed as laid out.**

Both filters now call the rosters' own `_matches_row`, so the rule is
shared rather than a third variant: name and handle by substring,
`tag_1..3` by whole value, unioned. Rung 3 made the tags visible; a
value typed into the search still returned nothing until this.

**The datalist half needed no change.** Both option builders already
emit only `Name (handle)` labels, so no tag value was ever offered as
a suggestion — the plan committed to a rule the code already kept. It
is pinned by a test rather than left to coincidence, because rung 4 is
exactly what makes tags matchable, and **matching a tag and suggesting
one are different questions**: Item 9's finding, that a tag identifies
too many rows to partition by.

**Tests went where the rule already lives.**
`tests/unit/test_roster_search_filters.py` holds this rule for the
four roster filters and did not cover these two; seven cases added
there rather than in a new file.

**Mutations:** 4, all killed — each filter reverted to substring-only,
tags matching by substring instead of whole value, and the datalist
starting to offer tag values.

**Measured:** the suite went 3481 → **3488**.

**Not verified here:** the Azure dev slot. No template changed in this
rung, so there is nothing new to look at.

**2026-09-10 — the author asked for one more header stack.**
`Reviewers completed` on Responses, on the same terms as
`Required Fields`: measured 1031px → **962px** of natural minimum,
which fits the card from 1280 up and scrolls inside it at 1024.
Mutation-checked (un-stacking fails the header test). Suite
unchanged at 3488.

**2026-09-10 — rung 5 landed, and found two things the four spec
files got wrong.**

The five specs the manifest names were edited as committed. Two
corrections came out of writing them, neither of which the plan
anticipated:

- **`spec/setup_pages.md` claimed the Observers preview shares the
  visibility-toggle pattern.** It does not and never did —
  `session_observers.html` has no `data-col-toggle` at all. The
  sentence was in the file's opening paragraph, which this rung was
  rewriting anyway to generalize the pattern; corrected rather than
  left, since a reader sent to look for chips on Observers finds
  none.
- **`spec/setup_pages.md`'s `localStorage` list was already
  incomplete** before this item: it named the three Setup keys and
  omitted `rrw-assignment-col-visibility`, which is the same grep
  blind spot that made the plan under-count the duplication at
  planning time. It now lists all six.

**One code change in a spec rung**, declared rather than smuggled:
`base.html`'s primitive comment still recited the **211 / 55 / 46**
figures the Status block corrected on 2026-09-10. A comment that
ships inside every rendered document is a poor place to leave a
number the plan has already retracted, so it now says 224 / 56.
Nothing executable changed.

**`close_check 19I.11` exits 0.** Its one note — `_operations`
touched, `spec/validate_page.md` and `spec/preview_hub.md` not in
the manifest — is a package-level false positive: both are
Operations-row siblings whose routes share the package, and neither
describes anything this item changed. Adjudicated, no bullet added.

**`spec-writer` found one flag, and it was real.** Nothing in the
five files was wrong about Item 11, but `spec/setup_pages.md`'s
**Reviewers** column table marked the Profile column `✓` under
`Toggle?` — and Reviewers has no profile chip and no
`col-hidden-profile` rule, only the three tag chips. The same file
said so correctly six hundred lines earlier, in the shared-pattern
section, so it contradicted itself; the stale `✓` dates to
2026-06-01 and is unrelated to this item. Verified against the
template before believing it (the previous `spec-writer` flag this
segment was false), then fixed in both places — the row now reads
`—` and the shared-pattern bullet states the asymmetry outright.

This is the third rung running in which the **Reviewers profile
column** has needed a note. The Judgment call above predicted a
reader would misread it as something the extraction dropped; the
spec had in fact been claiming a chip that never existed.

### Definition of done

- One column-visibility implementation in `base.html`; no page
  carries its own copy. Asserted by a grep-shaped test, not by
  reading.
- The four existing pages behave identically before and after rung
  1, including which chips are disabled and what persists.
- Both target tables sort on every annotated column, and the chosen
  order survives a reload (cookie applied server-side).
- Tag columns render on both, labelled through
  `field_label_header`, with chips that hide them.
- A tag value typed into either search matches whole-value, and is
  **absent** from the datalist.
- Every new assertion mutation-checked.
- `ruff check .` and `.venv/bin/pytest -q -n auto` pass.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19I.11` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- None blocking. The author settled the two that mattered on
  2026-09-10: extract the primitive rather than copy it, and leave
  Observers alone for now.

### Out of scope

- **Observers** — see Decision.
- **Capping Invitations / Responses.** Decided against in Item 10
  and unchanged here, though rung 2 makes the pages more inviting to
  use at scale: measured, they already cost ~669-840 ms and ~1 MB of
  HTML at 1,000 rows, and 1.2-1.5 s and 1.5-2.1 MB at 2,000. If the
  author revisits the cap, that is its own item.
- **Row selection and bulk actions** on the two pages. They are
  read-only monitoring surfaces; nothing there mutates.
- **Reviewers' un-hideable profile column** — see Judgment calls.

### Doc impact

- `spec/setup_pages.md` — the column-visibility chip pattern becomes
  a shared primitive rather than a three-page one; its description
  generalises (Item 11).
- `spec/operations_pages.md` — Invitations and Responses gain tag
  columns, the chip row, sortable headers and tag matching in
  search (Item 11).
- `spec/settings_inventory.md` — two new `localStorage` keys in the
  table at §`localStorage`, and a note that the existing four are
  deliberately unchanged by the extraction (Item 11).
- `spec/sort_by_reviewee.md` — the sort primitive's surface list
  gains the two pages (Item 11).
- `docs/status.md` — row at the close (Item 11).

---

## Item 12 — one place for column selection, and one card fewer

### Opportunity

The author, after Item 11 put the chip row on Invitations and
Responses (2026-09-10):

> *"I actually like the way Invitations and Responses do the tag
> selection for display in table above the table itself, rather than
> in a separate card, as in Reviewers, Reviewees, Relationships. In
> addition, the "Fields with data:" status counts are not absolutely
> critical, since it's not like you can set up a roster without the
> display fields, while the selection chips already double for
> indicating whether there's data."*

Both halves check out, and measuring them turns one preference into
two separable findings.

**Six chip surfaces, three placements.** Item 11 gave Invitations and
Responses their chip row *inside the table card*, immediately above
the preview-count line and the rows it governs. The three roster pages
put theirs *inside the "Fields with data" card*, which sits in the
right-hand stack of the `.card-columns` container — above the preview
table and separated from it by the whole Operator actions card.
Assignments has a third arrangement again: three grouped chip rows in
a card of their own, the left half of a `bottom-grid`. So the newest
surfaces are the ones whose control sits with the thing it controls.

**The pills are all but redundant with the chips — with one
exception, and it has already been replaced.** Read against the
services rather than assumed:

| Page | Pills the card renders | Covered by a chip? |
|---|---|---|
| Reviewers | `Name`, `Email` whenever any row exists; one per non-empty `tag_1..3` | tags yes; the two identity pills say only "the roster is non-empty" |
| Reviewees | the same, plus `PhotoLink` | yes — Reviewees has a `profile` chip |
| Relationships | `Reviewer`, `Reviewee`; one per non-empty `PairContextTag{n}`; **`Status`, when any row is `inactive`** | tags yes; **`Status` has no chip** |

`ReviewerName` / `ReviewerEmail` are appended by
`reviewer_fields_with_data` on `has_any` alone
(`app/services/assignments/_coverage.py:31`) — they are required
columns, so their pills are a row-count proxy for a count the chrome
status strip already carries. The author's *"you can't set up a roster
without the display fields"* is exactly this, and it is true in code.

The Relationships `Status` pill is the one real signal, and **Item 1
of this segment already replaced it twice.** Item 1's own Opportunity
cited this pill as evidence that the page can produce inactive rows
and could not filter to them; it then gave Relationships the Status
dropdown (`RELATIONSHIPS_STATUS_OPTIONS`, `active` / `inactive`) that
the other three pages had. The preview table's Status column is also
sortable (`data-sort-key="status"`). So "are any rows inactive?" is
answerable two ways on that page without the pill.

**And one of the three routes' context keys is already dead
elsewhere.** The Assignments page builds `fields_with_data`
(`_assignments.py:326`) and no template reads it — found and left
alone at 19H.5's close, 2026-09-09.

### Decision

**Move the chip row into the table card on all three roster pages,
matching Invitations and Responses exactly — chips, then the
preview-count line, then the table — and retire the "Fields with
data" card, its four route context keys, and the
`friendly_fields_with_data` adapter that now has no consumer.**

Nothing replaces the pills. The Relationships `Status` signal is not
rebuilt anywhere, because Item 1 already built its replacement; this
item's job is to stop rendering a third route to the same fact.

Rejected: **keeping the card and moving only the chips.** It leaves a
card whose whole content is two pills naming required columns and a
third for a fact the filter strip answers better — a card that exists
because it used to hold something. Retiring it is the point, not a
side effect.

Rejected: **moving the pills into the table card too**, above or
below the chips. That is the same information in a new place; the
question the author asked is whether it earns a place at all, and
measured against the chips it does not.

Rejected: **a `Status` chip on Relationships** to carry the retired
pill's one unique signal. Status is not a hideable column — every
relationship has one, and `spec/setup_pages.md` says so — so a chip
there would be a badge wearing a control's clothes.

~~**Assignments keeps its chip card** (see Open questions). Its three
grouped rows and its `bottom-grid` partner make the move a different
layout question from the rosters' one-row case, and the author named
three pages.~~ — **overtaken by the amendment below.**

### Decision — amended 2026-09-10, before rung 1

The author extended the ask on reading the plan, in three parts. The
Decision above stands; these add to it.

**1. Assignments moves too.** The Open question is answered: *"Yes,
include Assignments."* Four pages gain the table-card placement, not
three, and all five preview surfaces then agree. Its `bottom-grid`
partner, the operator-actions card, keeps its half and widens.

**2. A tag slot with no data renders nothing at all** — *"For all
cases, don't bother showing any chips for tags that don't have any
data at all."* This retires the **disabled chip**, a rule that has
stood since Segment 18E Part 1: today an empty slot renders a struck,
`aria-disabled` chip and its column is hidden but present in the DOM.
The rule applies to **all six** chip surfaces, the two Operations
pages included, because a rule that holds on four of six is not a
rule.

Measured before choosing how: **the disabled chip is what hides the
empty column.** `base.html`'s primitive branches on
`chip.classList.contains("is-disabled")` and calls `apply(slot,
false)`; nothing else stamps `col-hidden-{slot}`. Delete the chip
alone and the empty column becomes *visible*. And a page whose three
slots are all empty renders no chips at all, where the primitive
early-returns on `!chips.length` — so the columns would all appear.
So the chip cannot simply be dropped; the **column goes with it**.

**3. The `Assignments preview` heading goes.** It is the only `<h2>`
on a preview-table card anywhere — measured across all seven pages,
the other six table cards are headerless — and the card sits directly
under a page whose chrome already says what it is.

Rejected for part 2: **keeping the column and stamping
`col-hidden-{slot}` server-side** on the table's class attribute.
It preserves today's DOM and needs no new template gating, but it
ships three empty `<td>`s per row for nothing — on pages measured at
~1 MB of HTML at 1,000 rows (Item 11) — to hide them again in CSS.
Not rendering is the honest form of "there is no data here".

### Decision — amended again 2026-09-10: "no data" is roster-wide

The author, reading the consequence the amendment above had accepted:

> *"Oh, that's a key point — no data should apply to whole roster,
> not just the bit that is showing, inheriting the original function
> of the card."*

Taken, and it is the better rule for a reason the plan had not
measured: **today's per-render scan is wrong on every one of the six
pages, and was already wrong before this item.**

| Page | How the chip's has-data flag is computed today | Wrong when |
|---|---|---|
| Reviewers / Reviewees / Relationships | `reviewers \| selectattr("tag_1")` over `reviewers = capped` — the **filtered and 200/500-capped** display list | a filter is active, or the populated row is past the cap |
| Invitations / Responses | `rows \| selectattr(...)` over the **filtered** set (uncapped, Item 10) | a filter is active |
| Assignments | `col_data_sample`, deliberately **unfiltered** — *"so an active search never flips a chip"* — but `list_pairs` defaults to `limit=PAIR_PREVIEW_LIMIT`, so it is **capped at 200** | the populated row is past 200 |

So a 1,240-row roster whose `tag_3` is populated only from row 900
renders a struck "no data" chip today, and after part 2 of the first
amendment would have rendered **no column at all** — silently
dropping data the operator imported. That is the defect the author's
correction prevents, and it turns the change from a rule alignment
into a fix.

Assignments is the near-miss worth naming: it already reaches for the
unfiltered set, so somebody had this thought once, and the cap on
`list_pairs` quietly took half of it back.

**The mechanism already exists.** `app/services/_queries.py
::slot_has_data` answers exactly this question — one indexed
`LIMIT 1` per slot, non-`NULL` and non-empty — and it is what
`reviewer_fields_with_data` and friends are built from. Its own
docstring names the "Fields with data" pills as its first caller, so
the chips are inheriting the card's function through the card's own
primitive. Query cost per render: 3 slots on Reviewers,
Relationships, Invitations and Responses; 4 on Reviewees (the
`profile` chip); 9 on Assignments. Against pages already measured at
669-840 ms (Item 11), negligible.

**`active_only` is preserved, not rationalized.** Assignments'
pair-context group counts only `active` relationships today
(`{% if rel and rel.status == "active" %}`), matching the rule
engine's view, while the Relationships page's own chips count every
row. `slot_has_data(..., active_only=True)` exists for exactly this
and keeps the two answers different on purpose. Making them agree is
a separate question and not this item's.

Rejected: **"the page's own unfiltered row set"** as the scope for
Invitations and Responses, rather than the session's roster. It is
the closer analogue of what those two pages are *about* — assigned,
active reviewers — but it is a second rule, and the author asked for
the card's function, which was roster-wide. Accepted consequence: on
Invitations a reviewer-tag chip can appear for a column blank in
every visible row, when the tag is populated only on unassigned
reviewers. A chip for an empty column is a smaller error than a
missing column for a populated one.

### Semantics

- **Empty roster.** The chip row is gated on rows today
  (`{% if reviewers and not edit_mode %}`) and stays so; the table
  card renders its existing empty state. Nothing renders where the
  card used to be, rather than an empty card.
- **`edit_mode`.** The chip row hides while a row is being added or
  edited, as today — an operator mid-edit should not be able to hide
  the column they are typing into. Preserved verbatim, not
  re-derived.
- ~~**A slot with no data** still renders a disabled, struck chip whose
  column starts hidden.~~ **Amended 2026-09-10: a slot with no data
  renders neither chip nor column.** No `<th>`, no `<td>`, no chip —
  the same shape Reviewers already uses for its Profile column
  (`{% if show_profile_link %}`). No table on any of the six pages
  uses `colspan`, so dropping a column needs no other arithmetic.
- ~~**"No data" means the rows the table is showing**, which is
  today's rule on all six pages and is left alone.~~ **Reversed by
  the author, 2026-09-10** — see "Decision — amended again" below.
  **"No data" means the whole roster**, answered by a query, not by
  scanning the rendered rows. The chips inherit the retired card's
  function along with its place on the page.
- **A stored `localStorage` entry naming an absent slot is ignored**,
  as today: the primitive iterates chips and consults storage, never
  the reverse. So hiding Tag2, then importing a roster without it,
  then importing one with it again, restores the saved state.
- **The CSV-import error path** (`_shared.py`) re-renders these
  templates with a filter/cap context; it drops the
  `fields_with_data` key with the rest.
- **`localStorage` keys, slot names and per-page CSS are untouched.**
  This is a move, not a rewire — the chip markup and its
  `data-col-toggles-for` pointer travel intact, so no operator's
  saved column state resets.
- **Observers** has neither card nor chips today and gains neither.
- **The three `*_fields_with_data` services stay**, and after the
  second amendment they are joined by a per-slot presence helper over
  the same `slot_has_data` primitive. `display_source_presence`
  (`_coverage.py:104`) already unions all three for the Instruments
  page. Only the *view adapter* (`friendly_fields_with_data`, which
  maps CSV names to pill labels and has nothing to say about
  presence) and the *card* retire.

### Judgment calls — decided

- **Chips go above the preview-count line**, not below, because that
  is where Invitations and Responses put them and the whole item is
  about the five pages agreeing.
- **`friendly_fields_with_data` is deleted, not left dead.**
  Segment 19H Item 5 shipped it on 2026-09-09 — one day before this
  item — and its per-surface label table has no other consumer once
  the card goes. Leaving it is the "mechanise badly" the constitution
  names; the git history keeps it if it is ever wanted back.
- **Assignments' dead `fields_with_data` key goes in the same rung**
  as the three live ones. It is the same symbol and the same removal,
  and leaving one dead copy behind is how the next reader concludes
  the key is still live. Declared here rather than smuggled, since
  strictly it is a fourth page's change.
- **The `Show columns:` label stays.** It is what the two Operations
  pages render, and a chip row with no lead-in reads as a pill row.

Added with the 2026-09-10 amendment:

- **The primitive's `is-disabled` branch retires with the chips it
  served.** Once no page renders a disabled chip it is unreachable
  code with no test, which is the shape the constitution's "retire
  rather than mechanise badly" names. `persist()` loses its
  `is-disabled` skip for the same reason. Git keeps both if a future
  caller wants the state back.
- **Assignments' chip rows keep their three groups** when they move.
  The move is about *where* the control sits, not how it is grouped —
  `Show reviewers:` / `Show reviewees:` / `Show relationships:` name
  three different sources and collapsing them would lose that.
- **A group whose slots are all empty renders no row at all**, label
  included, rather than a bare `Show reviewees:` with nothing after
  it. Only Assignments can hit this, having three groups.

Added with the second 2026-09-10 amendment:

- **The presence flags move from Jinja to the route layer.** Six
  templates currently compute them with `selectattr` over whatever
  list they were handed, which is how all six came to disagree with
  the roster. A query per slot is the smaller and more honest
  mechanism, and it puts the answer where the page's other
  service-derived context already lives.
- **One presence helper, not six call sites of `slot_has_data`.**
  Each page needs the same shape — `{slot: bool}` for an entity —
  and six hand-rolled loops is how the previous divergence started.
- **`col_data_sample` retires with the scan it fed.** Its whole
  purpose was to give Assignments' chips an unfiltered view; a query
  does that better, and keeping a second 200-row fetch per render to
  answer a question nine `LIMIT 1`s answer would be paying for the
  old bug.

### Blast radius (measured)

```
grep -rln "Fields with data" app/web/templates            → 3
grep -rn  '"fields_with_data"' app/web/routes_operator/*.py → 5
    (_setup_reviewers, _setup_reviewees, _setup_relationships,
     _shared error path, _assignments — the last one dead)
grep -rn  "friendly_fields_with_data" app/ --include=*.py  → 6
    (1 def, 1 export, 1 __all__, 3 call sites — all retiring)
grep -rln "fields_with_data\|Fields with data" tests/ --include=*.py → 2
    (test_field_label_rendering.py: 10 hits; test_page_guidance.py: 1)
grep -rln "Fields with data" spec/ docs/                   → 6
grep -rln "col-chip-row" app/web/templates/operator        → 7
    (6 toggle pages + session_extract_data.html, which reuses the
     class for layout only and carries no data-col-toggles-for)
```

Templates: 3. Routes: 4 files. Views: `_setup.py` (one adapter
retires). Services: **none** — `display_source_presence` keeps all
three helpers alive.

**Amendment, measured 2026-09-10:**

```
grep -n "<h2>" on all seven preview pages
    → "Assignments preview" (session_assignments.html:304) is the
      only <h2> on a preview-table card; the other six are headerless
grep -rn "Assignments preview" app/ tests/ spec/
    → 1 template, 4 assertions in test_assignment_routes.py
      (:264, :439, :495, :503), 2 specs (assignments.md:533,
      operator_ui_concept.md:120)
grep -rn "is-disabled" tests/ --include=*.py
    → 4 chip assertions to invert: test_assignment_routes.py:577-578,
      test_import_routes.py:620, :712 (and :623, already a negative)
grep -c "colspan" on the six chip tables → 0 each
```

Templates rise 3 → 6 (Assignments joins the move; Invitations and
Responses join the empty-slot rule) plus `base.html` for the
primitive's retired branch.

**Second amendment, measured 2026-09-10:**

```
grep -n "has_tag_1 =|has_r_tag_1 =" over the six chip templates
    → 6 sites, all Jinja selectattr over a list the route handed in
_setup_reviewers.py:147  reviewers = capped     (filtered + 200/500)
_assignments.py:218      col_data_sample = assignments.list_pairs(db, id)
_coverage.py             list_pairs(..., limit: int = PAIR_PREVIEW_LIMIT)
    → the "unfiltered" sample is capped at 200
grep -rn "def slot_has_data" app/services/  → 1 (_queries.py:46)
```

Slots to answer per render: 3 (Reviewers, Relationships, Invitations,
Responses), 4 (Reviewees, + `profile`), 9 (Assignments). Routes
touched rises to 6 files — the four already named plus
`_operations.py` for the two Operations pages.

Specs describing the card: `spec/setup_pages.md` (six places — the
`.card-columns` layout row, "Shared body shape" item 3, the chip
row's stated location, the two per-page repeats, the Relationships
stats card, and the Observers "no pill row" note),
`spec/operator_ui_concept.md` (three), `spec/rrw_functional_spec.md`
(the Stats info card bullet), `spec/visual_style_rrw.md` (one
example), `spec/operations_pages.md` (one sentence written on
2026-09-10 that this item falsifies: *"these pages have no 'Fields
with data' card to hold it"* stops distinguishing anything once no
page has one), `docs/status.md` (the Relationships route-table row).

### PR ladder

1. **Move the chip row** into the table card on all three pages,
   above the preview-count line. The "Fields with data" card stays,
   pills only — which is what it was before Segment 18E. Visible
   change, nothing removed, fully reversible.
2. **Retire the card**: the three template blocks, the four route
   context keys (Assignments' dead one included), and
   `views.friendly_fields_with_data`.
3. **Specs + `docs/status.md` row.**

Rung 1 is worth landing alone: it is the half the author asked for
first, and it leaves the pages coherent whether or not rung 2
follows. Rung 2 is the removal, and separating it means the diff that
*deletes* is not also the diff that *moves* — the two are reviewed
against different questions.

Not split per page: the three edits are the same edit, and a reviewer
who models one models all three.

**Amended ladder (2026-09-10).** The original rungs stand; the ask
grew, so rung 1 widens, a rung is inserted, and the last two shift
down.

1. **Move the chip row** into the table card — now on **four** pages
   (the three rosters and Assignments), above the preview-count line
   — and drop the `Assignments preview` heading in the same slice,
   since it is the same card and the same question about what a
   preview card carries. The "Fields with data" card stays, pills
   only. Nothing removed from the data path; fully reversible.
2. ~~**Empty slots stop rendering**~~ — **split by the second
   amendment into rungs 2 and 3 below.**
2. **The has-data flags become roster-wide.** One presence helper
   over `slot_has_data`, computed in the routes and passed in; the
   six templates stop scanning their row lists; `col_data_sample`
   retires. **Nothing visible changes except that chips stop lying** —
   the disabled chip still renders, now for the right slots. This is
   the bug fix, and it is testable against the behavior it replaces:
   a tag past the cap and a tag behind a filter each flip a chip
   today.
3. **Empty slots stop rendering** — no chip, no column — on all six
   chip surfaces, and `base.html` loses the `is-disabled` branch that
   hid them. Must not touch the card or its context keys.
4. **Retire the card**: the three template blocks, the four route
   context keys (Assignments' dead one included), and
   `views.friendly_fields_with_data`.
5. **Specs + `docs/status.md` row.**

Rungs 2 and 3 are split because they answer different questions.
Rung 2 asks *is this flag right?* and can be checked against the
behavior it replaces. Rung 3 asks *what should a corrected flag
render?* and is the one place where a wrong move makes an empty
column **appear** rather than vanish. Landed together, a column that
vanishes gives no way to tell which of the two changes decided it.

### Status

**2026-09-10 — rung 1 landed as the amended ladder laid out.**

Four pages moved their chip row into the preview-table card, above
the count line, and the `Assignments preview` heading is gone. All
six chip surfaces now agree. **Template-only**; no route, service or
view changed.

**Assignments cost more than the three rosters put together**, as
expected but for one reason the plan had not named: its chip card
was the left half of a `bottom-grid`, so removing it would have left
the operator-actions card rendering at half width in a `1fr 1fr`
grid. The grid is unwrapped and that card is full width. Its flags,
its `col_groups` and its three chip rows travelled together, so the
computation now sits next to its only use instead of a hundred lines
above it.

**A test-anchor problem, four times over.** Four assertions in
`test_assignment_routes.py` used the string `Assignments preview` as
a proxy for "the preview card rendered" — the heading this rung
retires. Repointed to `id="assignments-table"` (presence) and to
`data-col-toggles-for="assignments-table"` (top of the card), both
of which say what the tests actually meant.

**The heading assertion was wrong at both ends, and a mutation found
each.** `test_no_preview_card_carries_a_heading` first sliced from
the chip row, so a heading placed *above* the chips — exactly where
the retired one sat — fell outside it; the mutation that restored
`<h2>Assignments preview</h2>` survived. Widened to start at the
card's own `<div class="card">`, and it survived **again**: the
slice ended at `src.index("</table>")`, the **first** table in the
file, which on Assignments is the per-instrument status table near
the top. So the slice ran backwards and was empty, and the assertion
held whatever the card contained. This is the segment's recurring
defect in a new costume — **an assertion that reads correctly and
tests nothing** — and once more only a mutation exposed it.

**Mutations:** 6, all killed after the fix above — the Reviewers
chips moved back above the pill row, the Assignments heading
restored, its three group labels dropped, the Responses chips moved
below the count line, an `<h2>` added to the Reviewers preview card,
and the Reviewees profile chip deleted.

**Verified in Chromium** at 1440 and 1024 on all four pages: the
chip row is inside the table card and precedes the table, no card
carries an `<h2>`, and the page never scrolls sideways. Toggling
still hides the right column, writes the right key
(`{"rt1":false,"rt2":true,"et1":true,"p1":true}` on Assignments —
four live slots, disabled ones correctly absent) and survives a
reload; a disabled chip still refuses, which rung 3 will retire. No
page errors.

**Measured against the pre-change template, not assumed** (Item 11's
lesson): at 1024 the Assignments table is 964px inside a 944px card,
**and it is 964/944 on `main` too**. The 20px overflow is
pre-existing — Assignments never got the `.table-scroll` wrapper
Item 11 gave Invitations and Responses. Reported, not fixed: it is
independent of this move, and widening the rung to carry it is the
bundling `CLAUDE.md` warns against.

**Also removed:** the empty `<script></script>` that Item 11's
extraction left in `session_assignments.html`. Zero-risk, and it is
the same block this rung is editing.

**Measured:** the suite went 3488 → **3503**.

**Not verified here:** the Azure dev slot.

**2026-09-10 — rung 2 landed as the amended ladder laid out, and the
bug it predicted is real.**

`tag_slot_presence` (`app/services/_queries.py`, beside
`slot_has_data`) answers `{"tag_1": bool, …}` over the session's
rows; `views.chip_slots` re-keys it to each page's own slot names
(`tag-1…`, `rt1…`, `et1…`, `p1…`); six routes pass one `col_data`
map and six templates read a flag instead of computing one. No
template computes a has-data flag any more.

**Demonstrated live, not only asserted.** 250 reviewers, only #249
carrying `tag_1`, rendered against the same SQLite file from a
worktree at `origin/main` and from this branch:

| | `tag-1` chip |
|---|---|
| `origin/main` | `is-disabled` — struck, "No data in this column" |
| this branch | `is-selected` |

The tagged row is past the 200-row cap and does not render on either.
So the pre-item page was striking out a column the roster holds, and
under rung 3 it would have dropped that column entirely.

**A defect this rung created and this rung fixes.** The Reviewees
Photo *column* was gated on `reviewees | selectattr("profile_link")`
— the displayed rows — while its *chip* had just gone roster-wide. A
photo living only past the cap would light the chip and leave the
column out: a control wired to nothing. Both read
`col_data["profile"]` now, pinned by a test that fails if either
half reverts. **Reviewers' profile column keeps its display-list
scan** and is not inconsistent with anything, because that page has
no profile chip (Item 11's asymmetry, corrected in the spec at Item
11's close).

**`col_data_sample` retires**, and with it the second unfiltered
200-row `list_pairs` fetch Assignments ran on every filtered render.
Item 9's comment on it was half-right — the sample was deliberately
unfiltered, and still carried `list_pairs`' default
`limit=PAIR_PREVIEW_LIMIT`.

**The vacuity guards were themselves vacuous at first.** Each new
test asserts the tagged row did *not* render, so that a seed which
accidentally shows it cannot pass. Written as `"Bravo" not in body`
they failed on the search box's `<datalist>`, which lists every
roster member by name and handle. Scoped to `<tbody class="rrw-rows">`.
That is the unscoped-substring trap for the **fourth** time in this
segment.

**Mutations:** 7, all killed — the helper returning `False`
throughout; the Reviewers route reverted to scanning its capped
display list (fails the cap *and* the filter test, which is the
bug); `active_only` dropped from the pair-context group; a
`chip_slots` off-by-one in slot names; the profile chip reading a
tag column; the Invitations route dropping `col_data`; and the Photo
column reverted to its display-list scan.

**Verified in Chromium:** chips read `tag-1:live, tag-2:disabled,
tag-3:disabled` on the 250-row seed, toggling persists
(`{"tag-1":false}` — disabled slots correctly absent) and survives
reload, and a filter down to one row leaves `tag-1` live. No page
errors. Render is ~26 ms steady on that page; a paired before/after
on timing was not taken, so "negligible" here rests on the absolute
figure and on the fact that the rung removes a 200-row query from
Assignments while adding three to nine indexed `LIMIT 1`s.

**Measured:** the suite went 3503 → **3513**.

**Not verified here:** the Azure dev slot.

**2026-09-10 — rung 3 landed as the amended ladder laid out.**

A slot with no data anywhere in the roster now renders neither chip
nor column, on all six surfaces. `base.html` lost the `is-disabled`
branch and its `persist()` skip. Verified in Chromium against a
sparse seed: Reviewers shows two chips, Reviewees and Relationships
one each, Assignments four across its three groups — and **zero
struck chips anywhere**.

**The semantic the plan did not name, found by reading the
templates rather than by a failure.** The roster pages render tag
**inputs** in add / edit mode. Gate those on presence and an empty
tag can never be filled in — the only way a tag stops being empty is
someone typing into it. `show_tag[n]` is therefore
`edit_mode or col_data["tag-n"]`, the same override the Photo column
has always carried, and header and cell counts stay equal in both
modes because one expression gates both. Verified in the browser:
add mode renders no chip row, three tag columns and three tag
inputs.

**Two mutations survived the first pass, for opposite reasons.**

1. **Assignments rendering an empty group's label row.** Nothing in
   the suite looked at the group labels, so `Show reviewees:` with
   no chips after it passed everything. A test now seeds reviewer
   tags only and asserts the other two rows are gone.
2. **`base.html` regaining the `is-disabled` branch changed no
   rendered page.** The branch is *behaviorally* dead once no page
   emits a disabled chip, so no integration test can reach it. Pinned
   structurally instead, over the IIFE's source.

**A CSS rule that looked dead and is not.** `.tag-chip.is-disabled`
stays in `base.html`: `instruments_index.html` renders that class
for its Band 1 link chips, a different mechanism. Deleting it with
the branch would have silently unstyled the Instruments page. Its
comment now says which caller keeps it alive.

**The unscoped-substring trap, twice more — fifth and sixth in this
segment.** `"tag-col-3" not in body` matched each page's own
`col-hidden-tag-3` CSS rule, which is dead but harmless and stays;
`"is-disabled" not in body` matched **the `base.html` comment
written to explain the retirement**. Both scoped.

**And a slice that ran backwards, again.** Three tests took
`body[body.index("<table id=") : body.index("</table>")]`, which
finds the **first** `</table>` in the page — on Assignments the
per-instrument status table near the top. The slice was empty and
every assertion over it held vacuously. Same defect as rung 1's
heading assertion, in three new places; all now pass the start
offset.

**Tests updated rather than deleted.** Six existing tests asserted
the disabled-chip contract. `test_assignments_sort` had asserted all
seven sort keys render "even when the data is sparse" — now split:
the four unconditional keys, the three tag keys absent on an untagged
seed, and a **new test** giving one slot data so its column, header
and sort key all come back. Without that pair the first half would
pass just as well if tag columns had been deleted outright.

**Mutations:** 9, all killed after the two fixes above — chips
rendering for empty slots; columns rendering for empty slots;
`edit_mode` no longer overriding the gate; the all-empty chip row
rendering anyway; the Assignments empty group rendering; `base.html`
regaining the branch; and Invitations' columns rendering
regardless of data.

**Verified in Chromium** at 1440 and 1024 on all four pages:
**header count equals cell count on every page and viewport** — the
structural risk of gating `<th>` and `<td>` separately — no struck
chips, no page-level horizontal scroll, toggling still persists
(`{"rt1":true,"rt2":false,"et1":true,"p1":true}`) and survives
reload. Assignments still overflows its card by 20px at 1024, which
is the pre-existing defect reported at rung 1 and unchanged here.
No page errors.

**Measured:** the suite went 3513 → **3518**.

**Not verified here:** the Azure dev slot.

**2026-09-10 — rung 4 landed, and took one more thing with it than
the plan expected.**

The card is gone from all three Setup pages, along with its four
route context keys (Assignments' dead one included) and
`views.friendly_fields_with_data` with both its lookup tables.
**-372 lines against +137**, of which the app is -214/+43.

**The plan's Semantics were wrong about which services survive.**
They said the three `*_fields_with_data` services stay because
`display_source_presence` unions all three — but that union is over
the **assignments module's** three (`reviewer_`, `reviewee_`,
`assignment_`), and `relationships.fields_with_data` is not among
them. The Relationships route was its only caller, so it lost that
and retired too: another 45 lines and an `__all__` entry. Caught by
grepping for callers after the route edit rather than by trusting
the plan's own sentence.

**The pills' one surviving contract moved rather than died.** Seven
tests covered them. Three said *the thing naming a tag column
outside the table header reads the operator's friendly label, not
the raw CSV name* — still true, of the chip now, and **nothing
asserted that of a chip**. Rewritten against the chips rather than
deleted. The other four were Segment 19H Item 5's, pinning
`_SURFACE_LABELS` — the per-surface map that let one CSV column
(`RevieweeEmail`) read `Email` on one page and `Reviewee` on
another. Chips never name an identity column, only tag and profile
slots, which resolve through the renamable-slot path; the map had no
caller left and retired with the function.

**A layout test counted the cards.**
`test_the_roster_pages_put_every_top_card_in_one_column_container`
asserted a four-element source order through the pill card. The
contract — one `.card-columns`, the whole left column then the whole
right — is unchanged; only the membership is. Three now. Verified in
Chromium: one container, `[2, 1]` cards per column, at 1440 and
1024, no page scroll.

**The unscoped-substring trap, a seventh time.** `"ReviewerTag1" not
in body` failed because the Upload card's CSV-header help lists the
raw column names, quite correctly. The retired pill assertions were
scoped by their own markup (`<span class="pill pill-count">…`); the
chip ones have to say so explicitly.

**Verified in Chromium**: no page renders `Fields with data`, and
the **CSV-import error path still renders its chips** — the path
rung 2 wired specially, and the one most easily forgotten, since it
re-renders the same template from a different function.

**Mutations:** 5, all killed — the card restored; the chip label
replaced by the raw CSV name on Reviewers and on Relationships; the
profile chip losing its label; and the operator-actions card leaving
the `.card-columns` stack.

**Measured:** the suite went 3518 → **3515** — the only rung in this
item to *lose* tests, and correctly: seven pill tests became three
chip tests plus one asserting no template builds the card again.

**Not verified here:** the Azure dev slot.

**2026-09-10 — two Assignments refinements from the author, after
rung 4.**

1. **The three chip groups share one row.** The labels stay — the
   nine slots come from three sources — but each group is now a
   `.chip-group` inline-flex box inside a single `.col-chip-row`, so
   a narrow viewport wraps **between** groups instead of stranding a
   label at the end of a line with its chips on the next. Measured
   with all nine slots populated: one line at 1440, two at 1280 and
   1024, groups never split.
2. **The search card is half width, flush right again.** Rung 1 made
   it full width because unwrapping the `bottom-grid` would otherwise
   have dropped a lone child into the *left* column. The grid is back
   with one child and a new `.grid-right` (`grid-column: 2`).
   Measured: width ratio 0.49 of the grid, 0px from its right edge,
   at 1440 / 1280 / 1024.

**A test broke on a class it does not care about.**
`test_assignments_lifecycle_gate` matched the card by its whole
`class` attribute, so adding `grid-right` failed five parametrised
cases about lifecycle states. Loosened to the class name.

**And the Chromium pass surfaced the `.table-scroll` gap again,
much worse than rung 1 measured it.** This was the first seed with
**all nine** tag slots populated — 14 columns — and the table is
**1508px inside a 1360px card**, pushing the document to 1566 at a
1440 viewport. So Assignments now scrolls the whole **page**
sideways, not just overflows its card by 20px as rung 1 recorded.

Established as **not** this change's doing before reporting it: the
overflowing element is `#assignments-table` itself, and neither
change touches the table — one edits a `<p>` above it, the other a
card in a different container. Still reported rather than folded in,
same as at rung 1: `.table-scroll` is a one-line fix using the
primitive Item 11 already applied to Invitations and Responses, and
it is the author's call whether it rides here or lands on its own.

**Mutations:** 3, all killed — the groups split back into three
rows, the `.chip-group` wrapper dropped, and `grid-right` removed
from the card.

**Measured:** the suite went 3515 → **3516**.

**Not verified here:** the Azure dev slot.

**2026-09-10 — the `.table-scroll` gap closed, at the author's
instruction.**

Reported at rung 1 and again above; the author asked for it. One
wrapper on the Assignments preview table, the primitive Item 11
already gave Invitations and Responses.

**Before and after on the same database**, nine tag slots populated,
14 columns, table 1508px:

| Viewport | before | after |
|---|---|---|
| 1440 | document 1566 vs client 1440 — **page scrolls** | document 1440, wrapper scrolls |
| 1280 | page scrolls | document 1280, wrapper scrolls |
| 1024 | page scrolls | document 1024, wrapper scrolls |

The table is still 1508px wide; the overflow is now inside the card,
which is the whole point. Nine of the fourteen columns can be hidden
by the chips above it — but the operator has to be able to see them
before deciding to.

**The test I wrote first claimed something I had not measured.** It
asserted all six chip tables carry the wrapper, "so the rule is all
six". Three do not: the Setup rosters never had it, and running the
test said so. They measure 1324px inside a 1360px card and fit, so
the rule is the three Operations tables — which is what the test now
says, with the roster figure recorded as the reason for their
absence.

**Mutations:** 2, both killed — the wrapper removed from Assignments
and from Invitations.

**Measured:** the suite went 3516 → **3519**.

**Not verified here:** the Azure dev slot.

### Definition of done

- All **six** chip surfaces render the chip row inside the table
  card, immediately above the preview-count line. Asserted
  structurally, not by reading.
- No preview-table card carries an `<h2>`; `grep -rn "<h2>" ` over
  the seven pages returns nothing inside a table card.
- **A slot with no data anywhere in the roster produces no chip and
  no column**, on all six pages, and `base.html` contains no
  `is-disabled` branch.
- **A slot populated only outside the rendered rows still produces
  its chip and column** — pinned twice, once past the 200-row cap and
  once behind an active filter, because those are the two ways the
  pre-item behavior got it wrong.
- No template computes a has-data flag with `selectattr`; the six
  read one context key each.
- A page whose slots are *all* empty renders no chip row, and its
  table still renders its remaining columns correctly.
- No template renders `Fields with data`; no route builds a
  `fields_with_data` context key; `friendly_fields_with_data` is
  gone from `app/web/views/`.
- `display_source_presence` and the three `*_fields_with_data`
  services still pass their own tests — the Instruments page is
  untouched.
- Column visibility still persists per page under the same
  `localStorage` keys, verified in Chromium on all three pages
  (the suite cannot).
- **Measured dimensionally as well as functionally** — Item 11's
  lesson: the roster tables gain no columns here, but the table card
  gains a row above them, so the check is that nothing reflows into
  an overflow.
- Every new assertion mutation-checked.
- `ruff check .` and `.venv/bin/pytest -q -n auto` pass.
- `### Doc impact` section present and current
- `python3 tools/close_check.py 19I.12` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `### Status` records intended vs done
- `docs/status.md` row added

### Open questions

- ~~**Does Assignments move too?**~~ **Answered by the author,
  2026-09-10: yes.** Recorded in the amended Decision; the
  recommendation to leave it was not taken.
- None outstanding.

### Out of scope

- **Observers** — no card and no chips today, so neither the move nor
  the empty-slot rule reaches it. Item 11 already settled that a
  one-tag chip row is a different question.
- **`session_extract_data.html`** — reuses `.col-chip-row` for
  layout with no toggle behavior behind it; not a chip surface.
- **The per-entity row count.** It is not in these cards (the chrome
  status strip carries it) and this item does not move it.
- **Reviewers' un-hideable Profile column** — Item 11's judgment
  call, corrected in the spec at Item 11's close, unchanged here.

### Doc impact

- `spec/setup_pages.md` — retire "Shared body shape" item 3 (the pill
  row); restate the chip row's location as the table card; update the
  `.card-columns` layout row, the Reviewers / Reviewees / Relationships
  repeats, the Relationships stats-card section, and the Observers
  "no pill row" note; **and retire the disabled-chip rule** — the
  empty-column bullets in "Preview tables (shared toggle pattern)"
  now describe a slot that renders nothing (Item 12).
- `spec/operator_ui_concept.md` — the Setup-pages shared-shape list
  loses its Info card item, the two prose mentions of the pill row go
  with it, and the Assignments body shape at §120 loses its separate
  chips card (Item 12).
- `spec/rrw_functional_spec.md` — the "Stats info card" bullet in the
  four-Setup-pages shape (Item 12).
- `spec/visual_style_rrw.md` — the card is cited as a live example of
  a page-level info card; pick a live one or drop the line (Item 12).
- `spec/operations_pages.md` — the sentence explaining that
  Invitations and Responses have no "Fields with data" card to hold
  their chip row stops distinguishing them once no page has one
  (Item 12).
- `spec/assignments.md` — the body-shape list names the
  **Assignments preview** card by its heading, and the
  column-visibility chips card moves into the table card (Item 12).
- `docs/status.md` — the Relationships route-table row describes the
  stats card, plus the Item 12 close row (Item 12).
