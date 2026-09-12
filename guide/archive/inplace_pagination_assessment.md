# In-place page turns on the roster tables — an assessment

**Written 2026-09-11 at `88f8849d`.** Not a plan and not a proposal: an
assessment written so the decision can be made from numbers rather than
from the phrase "several times the work", which is all `19J.8` said
about it when it rejected the idea.

Every figure below was produced by a command in one session against the
running app. The reproduction notes are at the end.

**The question is settled — see `Decision` below. Decided not worth
solving, 2026-09-11.** The measurement stands as the support for that
decision rather than as an open enquiry.

## The question

Turning a page on a roster table is a full navigation. Should it instead
fetch the next page and swap the table in place, leaving the rest of the
document untouched?

## Where it came from

19J.8's opportunity: *"using the pagination links reloads the whole
screen, usually forcing a jump to the top of the page. is there a way
to not have that?"*

That item shipped a landing anchor, which decides **where** the browser
stops. It cannot stop the screen from moving, because a navigation
always repaints from a new scroll position. Measured on a 556-row
Reviewers page at 1280×900, turning a page from the bottom strip moves
the viewport **9,221px**. A swap is the only change that removes the
movement rather than redirecting it.

## What a swap has to do

1. Ask the server for the next page's rows.
2. Replace the table body without touching the rest of the document.
3. Update both pager strips and the count line.
4. Push the new URL so Back works and the page is linkable.
5. Leave every behaviour attached to the table still working.

Items 1–4 are ordinary. **Item 5 is where the cost is**, and it is
measurable rather than a matter of taste.

## Measured: what a page turn costs today

A Reviewers page, 200 rows rendered, local SQLite:

| | 556-row roster | 5,000-row roster |
|---|---:|---:|
| whole response | 413,057 bytes | 416,382 bytes |
| the table | 194,894 bytes (47%) | 196,294 bytes (47%) |
| the search `<datalist>` | 19,359 bytes (5%) | 19,759 bytes (5%) |
| server round trip, median of 7 | **21 ms** | **116 ms** |

Two things worth reading off this.

**The response barely grows with the roster.** The page renders 200 rows
whatever the roster size, and the `<datalist>` is capped rather than
listing everyone — 556 rows and 5,000 rows produce responses within 1%
of each other. A swap would save the ~53% that is not the table, which
is real but is not the difference between fast and slow.

**The round trip is not the complaint.** 21 ms and 116 ms are not a
page that feels broken. The operator's objection was that the screen
moved, not that it waited. (The Invitations and Responses pages *are*
slow on large rosters — that is what 19J.4's busy indicator exists for —
but those are heavier queries, and a swap does not make a query faster.)

## Measured: what would break

`base.html` carries **620 lines of inline JavaScript in 7 blocks**. What
matters is whether each binds to the document (survives a DOM swap) or
to the elements themselves (dies with them):

| block | lines | what it does | survives a swap? |
|---|---:|---|---|
| 2 | 321 | sortable table headers | **yes** — see the correction below |
| 3 | 127 | column-visibility chips | **no** — binds per `[data-col-toggle]` |
| 4 | 29 | first-banner scroll | n/a — outside the table |
| 5 | 21 | delete-confirmation gate | n/a — outside the table card |
| 6 | 30 | theme toggle | n/a — chrome |
| 7 | 77 | navigation busy indicator | **yes** — delegated on `document` |

> **Corrected 2026-09-11, and the correction matters more than the
> original claim.** This table first read "one of five table-relevant
> blocks is delegated; the other four, about 500 lines, bind to elements
> and die with them" — and that was wrong about the largest of the four,
> wrong about which blocks are table-relevant at all, and therefore
> wrong by roughly 4× about the size of the work.
>
> Re-measured at `94aaa3b2` by reading each block rather than by reading
> the word `DOMContentLoaded`:
>
> - **Block 2 (321 lines, the sort) binds nothing.** Its headers call
>   `rrwSortHeaderClick(event, this)` through an inline `onclick`
>   attribute in the markup, so the handler arrives *with* any
>   re-rendered HTML and survives by construction. Its single
>   `addEventListener` is `document.addEventListener('DOMContentLoaded',
>   _rrwHydrateFromCookies)` — a one-time repaint of sort badges from
>   cookies, which a swap would need to re-call. That is one function
>   call, not 321 lines of re-homing. *Binding inside `DOMContentLoaded`
>   and binding to elements are different claims, and the first was
>   mistaken for the second.*
> - **Blocks 5 and 6 are not table-relevant.** `[data-delete-confirm]`
>   lives in the Operator actions and lock cards — in
>   `session_reviewers.html`, lines 196 / 649 / 696, against the table
>   card at 295–485 — and `.theme-toggle-opt` is chrome. A table swap
>   never touches either.
> - **Block 4 is delegated**, not load-time binding.
>
> **So exactly one block binds to elements inside the table card: block
> 3, the column chips, at 127 lines** — and even it sits *above* the
> table, so a table-body-only swap would leave it alone; only a
> card-level re-render breaks it. No block in this file uses
> property-style handlers (`el.onclick = …`), checked across all eight.
>
> The recommendation below — convert the element-bound blocks to
> delegation — still stands, but it is **one block, not four**, and its
> value is smaller in proportion. The original figure was carried from a
> regex over the word `DOMContentLoaded` instead of from reading the
> code, which is the failure this document elsewhere argues against.

The roster pages also carry per-page state a swap has to decide about:
row-selection checkboxes on five of seven pages, an inline edit mode on
four, and up to five `<form>` elements per page.

## Measured: the precondition nobody has asked for

For the server to render just the rows, the rows have to be a template
of their own. They are not:

| page | table markup | in a partial? |
|---|---:|---|
| reviewers | 167 lines | no |
| reviewees | 170 lines | no |
| relationships | 180 lines | no |
| observers | 89 lines | no |
| assignments | 109 lines | no |
| invitations | 135 lines | no |
| responses | 78 lines | no |

**928 lines of table markup, inline in seven templates, none shared.**
Every one would have to be extracted into a partial before a fragment
endpoint could exist — a refactor with no user-visible change, landing
before any of the benefit does. It is the honest first rung and it is
the one most likely to be skipped under pressure.

## What the swap would actually buy

It removes the reload. It does **not** settle the question underneath.

Preserving scroll position across a swap means the viewport holds still
— and the operator is then looking at row ~390 of the new range rather
than row 201. "Do not move the screen" and "show me the start of the new
rows" are in tension, and no amount of engineering resolves it; someone
has to choose. A swap only makes the choice available without a
navigation.

Worth stating plainly: **if the answer is "hold the scroll position",
that can be had today without any of the above** — stash `scrollY` before
a pager click, restore it after load. A reload the operator cannot see
is indistinguishable from no reload.

## The alternatives, and what each buys

| | cost | removes the jump? | shows new rows from the start? |
|---|---|---|---|
| **Hold scroll across the reload** | a delegated listener and `sessionStorage`, under a day | yes | no — same position, new rows |
| **Sticky pager strip** | a CSS rule plus a scroll-shadow decision | no, but the control is always to hand | n/a |
| **Smaller pages** (200 → 50) | one constant, plus re-taking 19J.5's tests | shrinks it ~4× | yes |
| **In-place swap** | 7 partial extractions, ~500 lines of JS re-homed, a fragment endpoint per page, history handling | yes | your choice, at last |

## Recommendation

**Do not build the swap yet.** Not because it is wrong — it is the
right end state if page turning ever becomes the main way operators move
through a roster — but because the three cheap options have not been
tried, and one of them (hold the scroll) delivers the actual complaint
for a fraction of the cost. Build the swap when something needs it that
the cheap options cannot give: live-updating rows, or a page turn that
must not lose an in-progress edit.

If it is built, the first rung is the partial extraction, and it should
land on its own with no behaviour change, so that the swap rung is a
swap and not a rewrite.

**One thing to fix regardless:** ~~four of the five table-relevant script
blocks bind directly to elements.~~ **One block does** — the column
chips, 127 lines (corrected 2026-09-11; see §"what would break").
Converting it to delegation is still independently worth doing — it is
what makes the chip row survive *any* future re-render — but it is a
morning's work rather than a project, and it commits to nothing.

## Decision — 2026-09-11

**Not worth solving.** Decided by the author the day this was written,
and it turns on the operator's intent rather than on any number above.

Landing on the table card's top edge is fine when the link clicked was
the strip *above* the table: the screen barely moves, and starting the
new range from the card's boundary is what you wanted anyway. The one
case that is mildly jarring is a click on the **bottom** strip, which
does send the viewport back up. But an operator who turns a page and
then stays on it is almost always intending to read the new range from
its start — so the jump and the intent point the same way.

That is a firmer reason to stop than the cost tables are. The costs
argue for *not yet*, which invites the question to be re-opened every
few segments; this argues for **not at all** — build the swap only if
something else comes to need it (live-updating rows, or a page turn
that must not lose an in-progress edit), never to fix the scroll.

Unaffected by this: the fix the recommendation names as worth doing
either way. Converting ~~the four element-bound script blocks~~ **the one
element-bound block** to delegation never depended on the swap, and its
case was unchanged. **Shipped 2026-09-11 as Segment 19K Item 2** — the
column-visibility chips are now one delegated listener per event type on
`document`, with `window._rrwHydrateColToggles` restoring the operator's
columns after a re-render (`spec/ui_elements.md` §10).

*(The count correction is dated 2026-09-11 and was already made twice in
this file — in §"what would break" and in the recommendation above — and
still stood uncorrected here until 2026-09-12. Three sections, two
updated. Left visible rather than tidied: it is the same failure the
document's own corrections describe.)*

## Reproducing the numbers

Local SQLite, `ALLOW_FAKE_AUTH=true`, one session seeded from a CSV
(`ReviewerName,ReviewerEmail,ReviewerTag1`), and:

- **sizes** — fetch `/operator/sessions/1/reviewers?offset=200` and slice
  on `id="reviewers-table-card"`, `<table`, `</table>` and
  `<datalist>…</datalist>`;
- **timing** — seven `urllib` round trips to the same URL, median
  reported; the first is discarded by taking the median, not by warming;
- **scroll movement** — Chromium at 1280×900 via Playwright
  (`/opt/pw-browsers/chromium-1194/chrome-linux/chrome`): scroll the
  bottom pager into view, read `window.scrollY`, click the first range
  link, read it again;
- **script blocks** — regex over `base.html`'s `<script>` bodies for
  `addEventListener`, split on whether the receiver is `document` /
  `window` or an element variable;
- **table markup** — first `<table id="<noun>-table"` to the following
  `</table>` in each of the seven templates.

The numbers are a snapshot taken to inform one decision. Re-take them
rather than trusting them if the decision is made much later —
particularly the round trips, which are local SQLite and not Azure
Postgres.
