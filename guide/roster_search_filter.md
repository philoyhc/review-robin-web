# Converting the roster search boxes to the lobby's filter box

**Investigation only — not planned, not scoped, no lift trigger.**
Asked 2026-09-20, after 19O Item 7 entry 15 renamed the Sessions lobby's
"search box" to **Filter** and gave it a typeahead. The question: what
would it take to do the same on the seven pages that still carry a
server-side `Search:` box, keeping their typeahead and their pre-filter
selectors.

The short answer is that the two controls are not the same control, and
the difference is not cosmetic. What follows is what the code actually
does, measured at `c65b7fa1`.

## What each one is today

|  | Sessions lobby | The seven roster / Operations pages |
|---|---|---|
| Where it runs | Browser, over rendered rows | Server, in Python |
| Submits | Nothing — keystroke-live | `GET ?q=…`, a full page load |
| Rows it can see | **Every** non-archived session | The **whole** roster, before paging |
| Rows it renders | All of them; no pager, no cap | 200 a page, or 500 when filtered |
| Typeahead | `<datalist>`, built from all rows | `<datalist>`, built from all rows |
| Pre-filters | Tag chip strip (AND/OR), client-side | `Status:` select, server-side |
| Matching rule | `rrwSessionFilterMatches` (JS) | `_matches_row` (Python) |

Both matching rules are the same rule: **substring on text columns,
whole value on tags**, unioned per column. The lobby's is a JavaScript
reimplementation of the Python one, which is worth saying plainly —
there are already two copies of this contract, and a conversion has to
decide which is canonical rather than quietly make a third.

## The finding that decides the shape

`app/web/routes_operator/_shared.py:504` says it in its own docstring:

> **Unfiltered is paged**: 200 rows a page … **Filtered is not.** The
> operator's own partition of the roster wins and a second one stacked
> on it is two mental models for one table, so a filtered view keeps the
> 500 cap it has always had and gets no pager.

So on a roster page, **filtering and paging are alternative modes**, and
the server chooses between them. The order is: load every row → sort →
filter → *then* cut the window (`_SETUP_DEFAULT_CAP = 200`,
`_SETUP_FILTERED_CAP = 500`).

The lobby can filter in the browser because **the browser has all the
rows** — `_lobby.py:79` loads every session and the template renders
every one, with no pager and no cap.

A roster does not. `csv_imports.MAX_ROWS = 5000`. A client-side filter
on an unfiltered roster page would be filtering **the 200 rows of the
current page**, not the roster. On a 1,000-row roster, typing a name
that exists would find nothing 80% of the time, and the operator would
have no way to tell that from the name being absent.

That is the whole problem. Everything below is downstream of it.

## What the typeahead would do to the wound

`filter_search_options` is built from **all** rows, not the window
(`_setup_reviewers.py:290` passes `all_reviewers`). So the `<datalist>`
already offers values from rows the current page does not hold — which
is correct today, because picking one submits and the server searches
the whole roster.

Under a client-side filter the same list would suggest a value and then
find nothing when the operator picked it. **The typeahead would become
the mechanism that demonstrates the bug**, which is worse than not
having one.

## Three ways out, and what each costs

**A — Send the whole roster to the browser.** Render all 5,000 rows and
filter them client-side, as the lobby does. Kills the pager, the two
caps and the mode switch; the filter then behaves exactly like the
lobby's. Costs: a 5,000-row table in the DOM on every roster page load,
against the 200 that ships today, and this is the app that just spent
19O Item 8 discovering its tables already overflow their cards at 14
columns. The row expander, the selection model, the sort primitive and
the column chips all operate on rendered rows, so all of them would be
doing so at 25× the scale. Nothing here has been measured at that size.

**B — Keep the server as the filter, make the box feel live.** Debounce
the input and re-fetch, replacing the table body. The operator gets
keystroke-live results over the *whole* roster, the pager and caps keep
working, the Python rule stays the single copy. Costs: a fetch path and
a partial-render endpoint per page where today there is a form GET; the
back button, the `#pager_anchor` fragment and the `Clear` link all
currently rely on the URL carrying `?q=`, so the URL has to keep being
updated or those regress.

**C — Filter the page, and say so.** Client-side filter over the
rendered window only, with the count line saying "12 of 200 on this
page". Cheapest by far, and honest, but it answers a different question
than the one an operator is asking — *is this person in the roster* —
and the 200-row page makes it the wrong answer most of the time on a
real roster.

**None of these is recommended here.** A is a performance question
nobody has measured; B is the only one that preserves what the control
means, and it is a bigger change than the phrase "convert the search
box to a filter box" suggests; C is cheap and wrong.

## Blast radius, if it ever is scoped

Counted at `c65b7fa1`:

- `grep -rl 'name="q"' app/web/templates/operator/ | wc -l` → **7**
  templates: the four rosters, Assignments, Invitations, Responses
- `grep -c "^def filter_" app/web/views/_filters.py` → **6** row filters
- `grep -c "_search_options" app/web/views/__init__.py` → **14** exported
  typeahead builders
- `grep -rln "filter-search\|reviewers-search-options" tests/ | wc -l` →
  **6** test files naming the control
- one JS rule (`rrwSessionFilterMatches`, `base.html`) and one Python
  rule (`_matches_row`, `_filters.py`), which a conversion must collapse
  or deliberately keep doubled

`spec/setup_pages.md` "Search matching and suggestions" states the
per-column rule for the seven surfaces and would govern any change.

## What is worth doing regardless

Two things are cheap, independent of the question asked, and do not need
this investigation to be adopted:

1. **The label.** The lobby's control was renamed because it filters
   rows rather than searching for them. The roster control genuinely
   *searches* — it re-queries the whole roster — so `Search:` is the
   right word there. Entry 15's rename was correctly scoped to the two
   lobby pages, and this investigation does not change that.
2. **The two matching rules.** They agree today by inspection and by a
   node test (`tests/integration/test_session_filter_rule.py`) that
   executes the JS copy. Nothing asserts the two agree *with each
   other*. That is a one-test gap, and it exists whether or not the
   rosters ever convert.

## Open questions, for whoever picks this up

1. **How large is a real roster?** Every option above is decided by it.
   5,000 is the CSV import ceiling, not an observed size; the pilot's
   own sessions are 154. If real rosters are in the low hundreds, option
   A stops being exotic and the investigation's conclusion changes.
2. **Is keystroke-live actually wanted**, or is the ask really "the
   control should look like the lobby's"? Option B buys the behaviour;
   restyling the card buys the appearance for almost nothing. They are
   different asks and the phrasing does not separate them.
3. **Which rule is canonical** if the two ever have to agree — Python,
   JS, or a shared definition compiled to both.
