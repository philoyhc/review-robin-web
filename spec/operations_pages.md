# Invitations & Responses — functional spec

Two Operations-row pages that together cover the running-session
work of engaging reviewers and tracking reviewee coverage:

- **Invitations** — reviewer-centric: who has been invited, who has
  responded, who needs nudging.
- **Responses** — reviewee-centric: per-reviewee coverage, surfacing
  under-served reviewees that the reviewer-centric view doesn't make
  visible.

Both render the same overall chrome shape: the **Workflow card** at
the top (per `spec/workflow_card.md`), then a full-width info card
with inline counters, then a table whose card opens with a two-pane
toolbar carrying the filter. Bulk-actions
(Create invites · Send invites · Send reminders) live on the
Workflow card's stepper — neither page body carries its own bulk
action bar.

## Page identity

| Page | Template | URL | Operations row position |
|---|---|---|---|
| Invitations | `session_invitations.html` | `/operator/sessions/{id}/invitations` | After Previews |
| Responses | `session_responses.html` | `/operator/sessions/{id}/responses` | After Invitations |

Operations row order:

```
Operations  [Assignments][Validate][Previews][Invitations][Responses][Extract data]
```

**Extract data** sits at the end of the strip because it is an
end-of-flow surface — operators reach for it once response data is in.

The dev-diagnostic Outbox page (`sys_admin_session_outbox.html`)
sits **outside the chrome** under the Sys Admin doorway at
`/operator/sys-admin/sessions/{id}/outbox`. Day-to-day operator work
shouldn't need it; pilot debugging and send-troubleshooting do.


**Documented in the Guide.** `/guide`'s **Watch progress** section
(`guide.html`, section key `watch_progress`) covers both pages: the
reviewer's-eye view and its eight lifecycle counters, the note that
invitation and reminder columns stay inactive until email sending is
switched on, and the reviewee-centric view with its
`Number of reviewees · With responses · Without responses` counters —
framed around the question the reviewer view cannot answer, which
reviewee is under-served.

## Why "Invitations" and "Responses"

Avoiding "Reviewers" and "Reviewees" as Operations tab labels —
those nouns already name the Setup tabs. The Setup tabs are about
configuring the rosters; the Operations tabs are about working with
them mid-session. Distinct nouns for distinct activities, no
disambiguation reliance on the row labels.

"Invitations" centers the page on the act of reaching out (with
follow-up reminders as a natural extension of the same activity).
"Responses" centers on what's coming back. Together they cover both
sides of the running-session conversation.

## Shared page shape

Both pages render the same four stacked regions, in order:

1. **Chrome** — two-row session chrome (top-nav with the active tab
   highlighted) + setup-status row.
2. **Workflow card** — full-width, per `spec/workflow_card.md`. Same
   ten-state cascade and five-stage stepper as on every other
   session-scoped page. The stepper carries the bulk-action
   affordances (Create invites · Send invites · Send reminders) so
   the page bodies stay focused on per-row inspection + targeted
   intervention.
3. **Info card** — full width, an inline middle-dot prose row of
   lifecycle / coverage counters. It was half of a `bottom-grid`
   whose other half was a filter card; 19P.5 rung 3 moved the filter
   into the table toolbar, and a `1fr 1fr` grid with one child is not
   a grid, so the wrapper went and the card is page width. Half width
   flush right was the alternative and was rejected: a counters card
   is a readout the eye sweeps, and eight pills in half a page wrap
   badly.
4. **Result table** — a single card that opens with the **two-pane
   toolbar** (§ *The table toolbar*), then the filtered row list, or
   an empty-state `.muted` message when no rows match. **The card and
   its toolbar render in every state**, including a search that
   matches nothing — the filter lives inside them now, so gating the
   card on having rows would take away the only way to clear a search
   that emptied the table.

**The result table is a roster-style table** on both pages. Each
carries the three facilities the Setup preview tables have, through
the same shared primitives rather than page-local copies:

- **Sortable headers** — `<table id="..."
  data-rrw-sortable="rrw-sort-{invitations|responses}-{session_id}">`
  over `<thead>` + `<tbody class="rrw-rows">`, with the cookie
  re-applied server-side so the first paint is already ordered.
  See `spec/sort_by_reviewee.md`.
- **Three tag columns** with a `Show columns:` chip row above the
  table, per the pattern in `spec/setup_pages.md`, "Preview tables
  (shared toggle pattern)". The chip row sits in the **table card** —
  where every chip row in the app sits. A tag slot with nothing in it
  across the session's roster renders neither chip nor column.
- **`.table-scroll`** — both tables sit in the wrapper `base.html`
  provides, so ten columns overflow *inside* the card rather than
  scrolling the page sideways. The wrapper is load-bearing, not
  defensive: Invitations' natural width is 1496px against a ~1396px
  page cap, so without it the page scrolls sideways at every viewport
  up to 1920.

Neither page has the rosters' select column or bulk actions —
they are read-only monitoring surfaces, and nothing here mutates a
roster row.

### Lifecycle behavior

Both pages render content across all session lifecycle states, and
**neither carries a yellow `.card.lock` notice** — the Workflow card's
stepper already makes lifecycle state explicit, and a second
lifecycle explanation on the same page is redundant (see
`spec/operator_ui_concept.md` P4).

**The invitation gate is `validated` or `ready`, not `ready` alone.**
Create / Send invites and the Invitations page's per-row action
buttons are live from `validated` onward; the route-layer gate
(`_require_validated_or_ready` in
`app/web/routes_operator/_operations.py`) is the source of truth.
**Send reminders** keeps the stricter `ready`-only requirement —
reminders fire after the response window opens, not before.

---

## Invitations page

Reviewer-centric. The operator's working surface for monitoring +
nudging individual reviewers throughout the session.

### Info card — eight lifecycle counters

Opens with a `.muted` note on its own row, **above** the counters:

> Note: Invitation and reminder columns are inactive until email
> sending is switched on.

Four of the eight counters cannot move until Segment 14B ships email
delivery, and without the note a page of stuck counters reads as
broken rather than as not-yet-switched-on. **Retire this note with
14B** — `guide/segment_14B_email_infrastructure.md` lists it, and
`tests/integration/test_page_guidance.py` asserts it, so the
assertion fails when the claim stops being true.

This is deliberately *not* a `.page-guidance` card. Those are a Setup
page affordance for explaining a page's whole purpose; one sentence
about one card's own counters does not need the idiom, and spreading
it thin would weaken it where it does work.

Then a single inline middle-dot prose row carrying eight counters:

```
Eligible reviewers N · Invitations created M · Invitations sent K ·
Pending invitations P · Reminders sent R · Pending reminders Q ·
Completed reviews C · Incomplete reviews I
```

Each counter renders as a `.pill.pill-count` (or `.pill.pill-empty`
when the variant is "zero-is-good / nonzero-is-attention" and the
value is nonzero — applied to Pending invitations, Pending
reminders, and Incomplete reviews).

### The table toolbar

The table card opens with a **two-pane toolbar**
(`.table-card-toolbar.is-split`), the same primitive the four roster
pages and Assignments carry — `spec/setup_pages.md`, § *The table
toolbar*, states the shape once. The left pane says what the table is
showing: the `Show columns:` chip row, the pager cluster, and the
preview-count line. The right pane carries the **filter strip**, a
`GET` form whose submit is labeled **`Search`**.

Both panes are bare — card geometry without a card's border, fill or
padding, because they are regions of one card rather than two cards.

**The strip lived in a half-width `filter-card` beside the info card
until 19P.5 rung 3.** Five surfaces said `Search` — the four rosters
and Assignments — and these two said `Apply`; the minority renamed. The class went with them — they were
its only callers, and `session_validate.html`'s `severity-filter-card`
is a different token that a substring grep mistakes for a survivor.

The strip is:

- **Status `<select>`** — `all` plus the per-status options exposed
  by the route via `filter_status_options`.
- **Search `<input>`** — matches the reviewer's **name and email by
  substring** and their **`tag_1..3` by whole value**, unioned. That
  is the rosters' own rule (`_matches_row`), shared rather than
  re-invented: whole-value on tags keeps `Team A` from dragging in
  `Team A2`, while substring on a name is what makes a partial name
  useful. Matching runs against the status-filtered set.
- **The `<datalist>` offers `Name (email)` labels only.** Tag values
  are matchable but never suggested — a tag identifies too many rows
  to partition a list by. Matching a tag and suggesting one are
  separate questions, and the answer differs.
- **Clear / Search** — `Search` submits the form; `Clear` (visible
  only when a filter is active) is a link back to the unparameterised
  page. **These are the only things in the actions row** — the count
  line is a report, and reports belong in the left pane with the rest
  of what the table is showing.

Both carry the table card's `#<noun>-table-card` fragment, so
submitting or clearing a filter lands the reader on the table rather
than at the top of the page — the same landing target the pager takes
(`spec/ui_elements.md` §10, *Landing targets*).

**The preview-count line** sits in the **left pane**, at the top-left
of the table card and above the rows it counts, in
`.table-showing-hint` — the same helper and partial the four roster
pages and Assignments use (`spec/setup_pages.md`, "Preview tables").
**The whole left pane is gated on there being rows**, chips and pager
with it, which is where these three Operations pages differ from the
four rosters: there the pager and count line are included
unconditionally and self-guard. Pre-existing on all three and
preserved rather than aligned at 19P.5 — an empty pane and an absent
pane look the same, and changing it would alter what a no-match search
shows. The count line's noun here is
**`reviewers`**, not "invitations": this table is one row per
reviewer (`build_invitations_rows` iterates
`monitoring.per_reviewer_progress`).

**This page is paged, and a filtered view is uncapped.** An
unfiltered view pages at **200**, with the `.table-pager-cluster`
(`spec/ui_elements.md` §10) above and below the table and `?offset=`
clamped rather than rejected — the rosters' rules exactly, shared
through `views.build_pager` and `_page_operations_rows`.

**A filtered view stays uncapped here**, which is the one place these
two differ from the four Setup pages. Those carry a 500 filtered cap;
these have none, and adding one would take rows away from a filtered
view that shows them today. The pager is suppressed while a filter is
active either way, so the difference is visible only on a filter
matching more than 500 rows.

So the count line's **withheld clause is still unreachable here by
construction**: an unfiltered view says nothing (the ranges speak) and
a filtered one withholds nothing. What renders is `Showing 3
reviewers.`, or nothing at all.

**A filter that matches every row still reports**
(`Showing 1,240 reviewers.`) rather than rendering nothing: the
sentence and the pager read the same filter flag, so they cannot
disagree about which mode the page is in, and a filter that ran and
excluded nothing is worth saying.

### Table columns

| # | Column | Toggle? | Sort key | Content |
|---|---|---|---|---|
| 1 | Reviewer | — | `name` | Name + `<code>` email; name links to per-invitation detail page when an `Invitation` row exists |
| 2 | Tag1 | ✓ | `tag_1` | `data-col-toggle="tag-1"` / `class="tag-col tag-col-1"`; header label via `field_label_header(session, "reviewer", "tag_1")` |
| 3 | Tag2 | ✓ | `tag_2` | `data-col-toggle="tag-2"` / `class="tag-col tag-col-2"` |
| 4 | Tag3 | ✓ | `tag_3` | `data-col-toggle="tag-3"` / `class="tag-col tag-col-3"` |
| 5 | Email Status | — | `email_status` | Pill: `sent` / `queued` / `not sent` |
| 6 | Sent | — | `email_sent_at` | Timestamp pill, or `—` |
| 7 | Progress | — | `review_progress` | Pill: `submitted (D/T)` or `<state> (D/T)` where state is a per-invitation lifecycle label |
| 8 | Required<br>Fields | — | `required_fields` | Pill: `(D/T)` |
| 9 | Reminder | — | `last_reminder_at` | Timestamp pill, or `—` |
| 10 | (actions) | — | — | Per-row buttons — see below |

The tag columns sit at 2-4, between the identity column and the
status columns, so the canonical order matches the roster tables.

**Four headers are deliberately terse** — `Progress`, `Sent`,
`Reminder`, and `Required Fields` stacked onto two lines. The tag
columns pushed the table 140px past its card at 1440px; narrowing
these four recovered 172px and it fits exactly. Renaming the
`Regenerate` button to `Regen` was measured as an alternative and
rejected — it closed 31px of the remaining 36, leaving a hairline
scroll, and cost a button label to do it.

**The two progress columns sort by completion percentage, not the
raw done count.** Totals differ per row, so "3 done" orders nothing
an operator would recognize. A row with nothing to do (total 0)
carries an empty `data-sort-value`; both the server-side
`apply_cookie_sort` and the client comparator place empty last
regardless of direction, so the two halves cannot disagree about
where those rows land.

### Per-row action buttons

Rendered in the rightmost (unlabelled) column when an `Invitation`
row exists:

- **Send** — visible when the invitation is `pending` (not yet
  sent). POSTs to `/operator/sessions/{session_id}/invitations/{id}/send`.
- **Send reminder** — visible when the invitation is past `pending`.
  Disabled when the row is complete (`not row.is_incomplete`).
  POSTs to `/operator/sessions/{session_id}/invitations/{id}/remind`.
- **Regenerate** — always visible when an invitation row exists.
  POSTs to `/operator/sessions/{session_id}/invitations/{id}/regenerate`.

**Send** and **Regenerate** are live from `validated` onward.
**Send reminder** stays `ready`-only — reminders fire after the
response window opens, not before. All three render `disabled`
outside their allowed state.

### Per-row drill-in

The reviewer name is a link to a per-**reviewer** detail page,
`/operator/sessions/{session_id}/invitations/reviewers/{reviewer_id}`.
**The link renders for every row, whether or not an invitation
exists.** The page is keyed on the reviewer because the reviewer is its
subject: the invitation supplies one optional field, while the reviewer
supplies the heading, the email, the breadcrumb and the row match.
The pre-19P.6 invitation-keyed URL
(`.../invitations/{invitation_id}/detail`) is a permanent **308** to
the reviewer URL, so bookmarks survive.

Because the route takes a reviewer, it reaches reviewers the
Manage Invitations table does not list — an inactive one, or one whose
assignments are all excluded. Those pages render without the Review
Progress card, which is correct: that card's data is the table row.

#### Invitation card

Reports **three facts, separately**, because they are independent and
conflating them was a defect (an operator saw `Email Status: not sent`
for a reviewer who had no invitation at all):

- **Invite** — `created` / `not created`, from the existence of the
  `Invitation` row.
- **Email sent** — the send timestamp or an em-dash, from
  `Invitation.sent_at`. Where the latest invitation outbox row carries
  a delivery state other than `sent`, that state renders beside the
  timestamp. The value set is the model's `EMAIL_OUTBOX_STATUSES`
  and is **rendered, not enumerated**, so widening it needs no change
  here.
- **Last reminder** — the timestamp or an em-dash, from
  `Invitation.last_reminder_at`.

Both timestamps read the `Invitation` row rather than the outbox, so
they survive a reviewer leaving the table. The em-dash means *no date*,
not *no invitation* — the top line already answers that.

Below them, a three-state URL region:

| State | Copy |
|---|---|
| A URL was issued | `Invitation URL (last issued):` + the URL |
| Invitation exists, never sent | `No invitation URL has been issued yet.` |
| No invitation, reviewer eligible | Points at **Create invites** on the Workflow card |
| No invitation, reviewer **not** eligible | Says **Create invites** will skip them, and names the two remedies |

The last two are distinct because `generate_invitations` selects active
reviewers with at least one included assignment: telling an ineligible
reviewer's operator to press **Create invites** sends them to a button
that cannot reach that reviewer.

"Issued" is the accurate verb for the second row: `generate_invitations`
discards the raw token, so a URL exists only once an invitation has been
**sent**.

#### Review Progress card

Renders only when the reviewer has a table row with at least one
assignment. Carries the row's progress fields, and a
`.card-action-row` at its foot with **Open reviewer surface**
(Secondary role), which opens
`/operator/sessions/{id}/preview-surface/1?reviewer_email=…` in a **new
tab** — the reviewer's own surface, inert, with their saved responses.

### Empty-state copy

When no rows match a filter: `No reviewers match the current
filter.` When no reviewers are assigned yet at all: `No reviewers
assigned yet — generate assignments before activating the
session.`

---

## Responses page

Reviewee-centric. Surfaces coverage from the reviewee's perspective
and identifies under-served reviewees that the Invitations page
doesn't make visible.

### Info card — three coverage counters

A single inline middle-dot prose row:

```
Number of reviewees N · With responses M · Without responses O
```

`With responses` renders as `.pill.pill-count`; `Without responses`
renders as `.pill.pill-empty` when nonzero (the "zero-is-good"
variant).

### The table toolbar

Same shape as the Invitations toolbar and the same two panes: Status
`<select>` + Search `<input>` + Clear / `Search` in the right pane,
chips + pager + count line in the left, and the same matching rule —
reviewee name and email-or-identifier by substring, `tag_1..3` by
whole value, with the `<datalist>` offering `Name (email)` labels
only. The count line's noun is **`reviewees`** — one row per reviewee,
from `monitoring.per_reviewee_coverage`. This page **pages** on the
same terms as Invitations: 200 rows to a page unfiltered, a filtered
view uncapped and without a pager, so only the filter branch of the
count line ever fires.

### Table columns

| # | Column | Toggle? | Sort key | Content |
|---|---|---|---|---|
| 1 | Reviewee | — | `name` | Name + `<code>` email-or-identifier; name links to per-reviewee detail page |
| 2 | Tag1 | ✓ | `tag_1` | `data-col-toggle="tag-1"` / `class="tag-col tag-col-1"`; header label via `field_label_header(session, "reviewee", "tag_1")` |
| 3 | Tag2 | ✓ | `tag_2` | `data-col-toggle="tag-2"` / `class="tag-col tag-col-2"` |
| 4 | Tag3 | ✓ | `tag_3` | `data-col-toggle="tag-3"` / `class="tag-col tag-col-3"` |
| 5 | Coverage | — | `coverage_state` | Pill: `complete` / `adequate` / `at risk` / `no responses` |
| 6 | Reviewers<br>completed | — | `reviewers_done` | Pill: `D/T` (filled count vs. total) or `—` when total is 0 |
| 7 | Last response | — | `last_response_at` | Timestamp pill, or `—` |

`Reviewers completed` is stacked onto two lines for the same reason
Invitations stacks `Required Fields`: it drops the table's natural
minimum from 1031px to 962px, which fits the card from 1280 up.
`Reviewers completed` sorts on completion percentage, on the same
terms as the Invitations progress columns above.

### Coverage state definitions

Operator-meaningful summaries computed by the view adapter:

- **complete** — all assigned reviewers have responded.
- **adequate** — partial coverage above an app-default threshold.
- **at risk** — partial coverage below threshold (or session
  deadline approaching with low coverage).
- **no responses** — zero reviewers have responded for this
  reviewee.

These are guidance, not enforcement. The operator decides what to
do; the coverage state helps them prioritize.

### Per-row drill-in

The reviewee name is a link to a per-reviewee detail page
(`/operator/sessions/{session_id}/responses/{reviewee_id}/detail`)
showing the per-reviewer response status for this reviewee.

### No per-row action buttons

Responses currently has no Actions column. Reminder targeting at a
single-reviewee or selected-reviewee granularity is out of scope for
this iteration — the Workflow card's **Send reminders** super-button
fires reminders to every incomplete reviewer across the session.

### Empty-state copy

When no rows match a filter: `No reviewees match the current
filter.` When no reviewees are assigned yet at all: `No reviewees
assigned yet — generate assignments before activating the
session.`

---

## Cross-page interactions

- **Reminder send-path is shared.** Whether the operator triggers a
  reminder from the Workflow card (Send reminders super-button on
  any session-scoped page) or from a per-row Send reminder button on
  the Invitations page, the same underlying email send happens.
  Implementation does not duplicate the send logic.
- **Reminder content lives on the Email Template Setup page**, not
  on these Operations pages. These pages trigger sends; the content
  (subject, body, merge tags) is configured at setup time.

---

## What these pages do not do

- **Read response content.** The operator does not read individual
  reviewer responses from these pages. Response content is for
  Extract Data; the Operations pages show *whether* responses
  exist, not *what* they say.
- **Edit assignments or rosters.** Cannot move reviewers around,
  reassign reviewees, or change instruments. That's Setup work; if
  the operator needs to do it mid-session, they Revert to draft via
  the Workflow card and go to the Setup pages.
- **Modify email content.** Reminder and invitation emails are
  edited on the Email Template Setup page. These pages send
  whatever the templates produce.
- **Bulk-select rows for batch action.** Bulk send / remind happens
  via the Workflow card's super-buttons (which act on every eligible
  row session-wide); per-row buttons handle targeted intervention.
  No multi-select checkbox column on either table.
- **Live updates.** Pages render snapshot data on each request. A
  navigation re-renders; auto-refresh is out of scope.
- **Cross-session views.** Both pages are scoped to a single
  session per P1 of `spec/operator_ui_concept.md`.

---

## What these pages cost to render

Both pages read every response row in the session: Invitations rolls up
per reviewer (`monitoring.per_reviewer_progress`), Responses rolls up
per reviewee (`monitoring.per_reviewee_coverage`) **and** calls
`monitoring.summary_counts` for one number, `incomplete_count`, which
runs the reviewer-side pass a second time.

**Every rollup reads the session's response rows in one query, never
one assignment at a time.** `responses_service.responses_by_assignment`
loads them once and both rollups read from it. The query count must
stay **linear in the roster**, not quadratic in it — a per-assignment
read is quadratic, and on a 200 × 200 roster that is the difference
between hundreds of queries and tens of thousands. The budget, measured
through the real routes (SQLite, in-process, one render each):

| roster | assignments | Assignments | Invitations | Responses |
|---|---:|---:|---:|---:|
| 25 × 25 | 625 | 43 | 84 | 84 |
| 50 × 50 | 2,500 | 43 | 134 | 134 |
| 100 × 100 | 10,000 | 43 | 234 | 234 |
| 200 × 200 | 40,000 | 43 | 434 | 434 |

Roughly two queries per reviewer plus a constant, from the per-reviewer
assignment and field lookups that remain. Assignments stays **flat at
43 at every size** — its `LIMIT 200` and its indexes are what hold it
there, so a change that drops either belongs in this table.

**Paging must not change any of these counts**: the slice is applied
after every row is built.

These are SQLite figures at roughly 0.2 ms per query. Production
Postgres pays a network round trip per query, so **the query count is
the portable number and the wall times are a floor, not a ceiling.**

## Implementation pointers

- View-shape adapters in `app/web/views/_invitations.py` and
  `app/web/views/_responses.py` own the per-row projection + the
  info-card counter aggregation. Routes stay thin.
- Per-row and Workflow-card reminder send-paths share their
  underlying implementation in `app/services/invitations.py` —
  single source of truth for "send reminder email."
- Filter parsing lives in `app/web/views/_filters.py` so the
  Invitations and Responses pages reuse the same Status / Search
  contract — and the same `_matches_row` the four roster filters use,
  rather than a third variant of it.
- **Sort wiring** is in `app/web/routes_operator/_operations.py`:
  a per-page valid-key set plus an `_invitations_sort_value` /
  `_responses_sort_value` resolver passed to
  `views.apply_cookie_sort`. Unlike the rosters, these resolvers
  cannot be a plain `getattr` — the row is a wrapper, so identity
  and tag keys reach **through** it
  (`InvitationsRow.reviewer.name`, `ResponsesRow.reviewee.tag_1`).
- **Column visibility** is the shared `base.html` primitive; each
  template supplies only the chip markup and a scoped `<style>`
  mapping its slots to column classes. See `spec/setup_pages.md`.
- "At risk" thresholds and coverage-state definitions on the
  Responses page are computed in one place in
  `app/web/views/_responses.py`. Future operator configuration of
  the threshold becomes a small change to that one location.
