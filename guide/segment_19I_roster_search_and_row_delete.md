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

### Semantics

- **Empty search** — no-op, as today.
- **Multiple matches across columns** — a row matches if *any*
  searchable column contains the needle. No column weighting; this is
  a filter, not a ranking.
- **A typeahead pick** keeps today's behavior: text ending in
  `(handle)` exact-matches the handle. Because suggestions stay
  people-only, on Relationships the pick must now match **either**
  side's handle rather than the selected side's.
- **A typed value that ends in parentheses** is read as a handle pick
  and will not match a tag of the same text. Known edge, unchanged
  from today, and the reason tags stay out of the suggestions.
- **Observers** search one tag slot, not three. The predicate reads
  the columns the model has rather than assuming three.
- **Status on Relationships** filters on `Relationship.status`, the
  same `active` / `inactive` values `bulk_inactivate` writes.
- **Filters compose** — status and search both apply, as they do on
  the three pages that have both today.
- **Substring, as today** — a tag search matches any row whose tag
  *contains* the needle, the same rule name and handle already use.
  This is the consistent choice and it has a cost at partition scale;
  see Open questions.
- **The two Relationships datalists merge into one.** `search_by`
  currently swaps the input's `list=` between a reviewer list and a
  reviewee list; one list carries both. The
  `REVIEWERS_DATALIST_CAP` (200) applies to the merged list.

### Judgment calls — decided

- **Status filter, not a new "Pair status" label** (2026-09-09).
  Relationships rows carry the same two values under the same column
  name as the other three; a distinct label would imply a distinct
  concept.
- **Search matches the stored tag value, not the friendly label**
  (2026-09-09). The label names the column, the value is in the row;
  an operator searching "senior" is looking for rows, not for a column
  called something.

### Blast radius (measured)

At `6b4dc027`:

| What | Measured | Command |
|---|---|---|
| filter predicates | 4, one file (`app/web/views/_filters.py`) | `grep -n "^def filter_.*_rows" app/web/views/_filters.py` |
| call sites outside that file | 12, all in `app/`; **0 in tests** | `grep -rn "filter_reviewers_rows\|filter_reviewees_rows\|filter_observers_rows\|filter_relationships_rows" app/ tests/ --include=*.py` |
| `search_by` references | 59 in `app/`, 22 in `tests/` | `grep -rn "search_by" app/ tests/` |
| tag slots | reviewer 3, reviewee 3, relationship 3, **observer 1** | `grep -c "tag_[0-9]: Mapped" app/db/models/<m>.py` |
| specs to change | `spec/setup_pages.md` (the strip + the stale justification) | `grep -n "Search + filter strip" spec/setup_pages.md` |

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

1. **PR 1 — tags join the search on Reviewers, Reviewees, Observers.**
   No strip change, no `search_by` involvement; the three pages whose
   dropdown is already a status filter. Lands the operator-visible
   value first and at the lowest risk. Must not touch:
   `filter_relationships_rows`, the templates' strip markup, or the
   datalists.
2. **PR 2 — Relationships rationalized.** Status filter added,
   `search_by` retired, the two datalists merged, pair-context tags
   joined to the search. Must not touch: the other three pages'
   filters, or anything in Item 2.
3. **PR 3 — the spec.** `spec/setup_pages.md`'s strip section rewritten
   to one shape for four pages, with the stale justification removed
   rather than edited around.

### Definition of done

- Typing a tag value into any of the four search boxes filters to the
  rows carrying it, asserted per page.
- Relationships offers `All` / `Active` / `Inactive` and filters on it.
- Relationships' search matches either side's name or handle, and the
  page's own pair-context tags, with one merged people datalist.
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

- **Substring or whole-value match on tags?** The dropdown
  rationalization and the people-only typeahead are settled (author,
  2026-09-09). This one is opened *by* the partition motivation and is
  not settled. Substring is what name and handle do, so it is the
  consistent answer — but partitions are exactly where it misleads:
  searching `Team A` also brings in `Team A2` and `Team AB`, and an
  operator who believes they have isolated a partition has not. That
  matters most in combination with Item 2, where the next act may be
  a delete. Three candidates, none free: keep substring and rely on
  the `Showing N of M` hint; match a tag **whole-value**
  case-insensitively while names stay substring (precise, but two
  rules in one box); or offer the distinct values of a tag slot as a
  picker, which is the exact tool for partitioning and a larger change
  than this item. **Decided by the author before PR 1** — it changes
  what the operator gets, not just how it is built.

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
