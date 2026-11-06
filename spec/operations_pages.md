# Invitations & Responses — functional spec

Two Operations-row pages that together cover the running-session
work of engaging reviewers and tracking reviewee coverage:

- **Invitations** — reviewer-centric: who has been invited, who has
  responded, who needs nudging.
- **Responses** — reviewee-centric: per-reviewee coverage, surfacing
  under-served reviewees that the reviewer-centric view doesn't make
  visible.

Both render the same overall chrome shape: the **Workflow card** at
the top (per `spec/workflow_card.md`), then an info card with inline
counters under a heading (*Reviewers and invitations*, *Reviewees and
responses*), then a table whose card opens with a two-pane toolbar
carrying the filter. On Responses the info card is full width; on
Invitations it takes the left half of a `.bottom-grid` row, beside the
**Share the session link** card (the session's stable link and Copy
link). Bulk-actions
(Send invites · Send reminders) live on the
Workflow card's button row, disabled until 14G whatever `RRW_BULK_SEND`
says (findings L2; `spec/workflow_card.md`) — neither page body carries its own
bulk action bar. One reviewer's email goes out from the per-row buttons. Creating invites has no button of its own: Prepare creates
one invitation per eligible reviewer.

## Page identity

| Page | Template | URL | Operations row position |
|---|---|---|---|
| Invitations | `session_invitations.html` | `/operator/sessions/{id}/invitations` | After Validate |
| Responses | `session_responses.html` | `/operator/sessions/{id}/responses` | After Invitations |

Operations row order:

```
Operations  [Assignments][Validate][Invitations][Responses][Extract data]
```

**Extract data** sits at the end of the strip because it is an
end-of-flow surface — operators reach for it once response data is in.

The dev-diagnostic Outbox page (`sys_admin_session_outbox.html`)
sits **outside the chrome** under the Sys Admin doorway at
`/operator/sys-admin/sessions/{id}/outbox`. Day-to-day operator work
shouldn't need it; pilot debugging and send-troubleshooting do.

**There is no Previews tab.** The reviewer-surface preview and the
email previews are reached from the Invitations per-reviewer drill-in
("Review Progress card" and "Email previews" below), so the Invitations
table is their only picker. Three legacy GETs answer a permanent
**308**: `/operator/sessions/{id}/previews` and
`/operator/sessions/{id}/monitoring` to
`/operator/sessions/{id}/invitations`, and
`/operator/sessions/{id}/preview` to
`/operator/sessions/{id}/preview-surface/1`. The operator-side reviewer
surface itself is `spec/reviewer-surface.md`'s.


**Documented in the Guide.** `/guide`'s **Watch progress** section
(`guide.html`, section key `watch_progress`) covers both pages: the
reviewer's-eye view and its eight lifecycle counters, what the per-row
Send and Send reminder do (email one reviewer from the operator's own
mailbox) and that sending to everyone at once is off in favor of the
session link, and the reviewee-centric view with its
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

Both pages render the same four stacked regions, in order — plus, on
Manage Invitations only, a conditional notice between 2 and 3 when
`?no_match=` names an address no reviewer holds:

1. **Chrome** — two-row session chrome (top-nav with the active tab
   highlighted) + setup-status row.
2. **Workflow card** — full-width, per `spec/workflow_card.md`. Same
   ten-state cascade and single row of action buttons as on every
   other session-scoped page. The button row carries the bulk-action
   affordances (Send invites · Send reminders) so
   the page bodies stay focused on per-row inspection + targeted
   intervention.
3. **Info card** — full width, an inline middle-dot prose row of
   lifecycle / coverage counters. Full width because a counters card
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
  defensive: Invitations is wider than the page cap, so without it
  the page scrolls sideways at every viewport.

Neither page has the rosters' select column or bulk actions —
they are read-only monitoring surfaces, and nothing here mutates a
roster row.

### Lifecycle behavior

Both pages render content across all session lifecycle states, and
**neither carries a yellow `.card.lock` notice** — the Workflow card
already makes lifecycle state explicit, and a second
lifecycle explanation on the same page is redundant (see
`spec/operator_ui_concept.md` P4).

**The invitation gate: sending and regenerating from `validated`,
reminders `ready`.** Route and button agree, in
`app/web/routes_operator/_operations.py` (`spec/lifecycle.md` §3.3–§3.5;
the invitation services re-decide each gate under the session lock):

- `send-all`, `regenerate-all`, `{iid}/send` and `{iid}/regenerate`
  call `_require_validated_or_ready`. The Workflow card's **Send
  invites** renders in `validated` or `ready` once invitations exist and
  none has been sent (`send_invites_visible`,
  `app/web/views/_workflow_card.py`), so reviewers can be notified before
  activation. `regenerate-all` has no UI caller at all; it is reachable
  only by POSTing the route.
- `{iid}/remind` and `remind-incomplete` call `_require_ready` and
  answer **409** elsewhere. The Workflow card's **Send reminders**
  renders only when `is_ready` and an invitation has been sent. Reminders
  fire after the response window opens.
- `send-all` and `remind-incomplete` also answer **409** until 14G,
  whatever `RRW_BULK_SEND` says (findings L2, `spec/lifecycle.md` §3.5), their Workflow card
  buttons rendering disabled. **There is therefore no bulk email**:
  before activation the in-app ways to tell reviewers are the per-row
  Send and the session link below.
- The per-row buttons are disabled outside their gate, each with a hover
  title (Per-row action buttons).

---

## Invitations page

Reviewer-centric. The operator's working surface for monitoring +
nudging individual reviewers throughout the session.

### Info card — eight lifecycle counters

Opens with a `.muted` note on its own row, **above** the counters:

> Send and Send reminder email one reviewer from your own mailbox.
> Sending to everyone at once isn't available yet: share the session
> link instead.

Per-row Send and Send reminder deliver through the operator's own
mailbox (Per-row action buttons): the row's Email status turns `sent`
or `failed`, and the sent and reminded counters count a send. The note
states that and where bulk sending stands, and
`tests/integration/test_page_guidance.py` asserts it, above the
counters; the page must not claim a bulk send it does not offer.

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

**Two of these count different populations, and the row's arithmetic
does not close.** `Invitations created` counts **every** `Invitation`
row on the session; `Pending invitations` counts only the **sendable**
ones — `pending`, and the reviewer still assigned-and-active. A reviewer invited at an earlier Prepare and
since made ineligible keeps a row that the first counts, the second
does not, and the table below does not list. So `created 2 · sent 1 ·
pending 0` is a correct reading, not a bug.

`Pending invitations` counts what the send buttons act on deliberately:
it is a nonzero-is-attention pill, so a count the operator cannot act
on is worse than no count. `Invitations created` counts every row
because pruning stale invitations is deliberately deferred
(`guide/deferred_consolidated.md`) — a *sent* invitation is live in a
reviewer's inbox, and nothing yet distinguishes
one safe to delete.

### Share the session link card

Beside the info card, in the same `.bottom-grid.is-equal-height` row
(`spec/ui_elements.md` §10; stacked under 800 px), `#share-session-link`
gives the operator a way to reach every reviewer without bulk email. It
holds a title, a help line (only eligible, signed-in participants can
reach the session with the link, and only while it is open to receive or
view responses), the session's link in a read-only box, and **Copy
link**.

- **The link** is the session's one stable link for every reviewer,
  `/me/sessions/{public_id}` (`spec/rrw_functional_spec.md` §7.2),
  absolute through the host's public origin as invitation links are
  (`request.url_for("review_surface_default_position")`). It is gated at
  arrival by sign-in and the roster; a stranger meets a bare 404.
- **Copy link** uses the Clipboard API in a secure context, else the
  field's selection and `execCommand("copy")`. A status line beside the
  button reads "Link copied", or "Couldn't copy: select the link and
  copy it yourself." so a refused copy is not silent.
- The card carries no message text: the operator pastes the link into
  their own channel, such as an LMS.
- The Workflow card's bulk-off line and its due prompts link to
  `#share-session-link`.

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
  separate questions, and the answer differs. A search equal to one of
  those labels exact-matches its email instead, by the rosters' rule
  (`spec/setup_pages.md` "Picking a person from the typeahead"): the
  trigger is "equals an offered label", so a tag like `Group (B)` still
  matches as a tag.
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
unconditionally and self-guard. The difference is kept: an empty
pane and an absent pane look the same, and aligning it would alter what
a no-match search shows. The count line's noun here is
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
| 1 | Reviewer | — | `name` | Name + email (`<code>`, a display pill when the reviewer is bound to a directory account, `spec/setup_pages.md` § *Bound addresses*); name links to the per-reviewer detail page on every row (Per-row drill-in) |
| 2 | Tag1 | ✓ | `tag_1` | `data-col-toggle="tag-1"` / `class="tag-col tag-col-1"`; header label via `field_label_header(session, "reviewer", "tag_1")` |
| 3 | Tag2 | ✓ | `tag_2` | `data-col-toggle="tag-2"` / `class="tag-col tag-col-2"` |
| 4 | Tag3 | ✓ | `tag_3` | `data-col-toggle="tag-3"` / `class="tag-col tag-col-3"` |
| 5 | Email Status | — | `email_status` | Pill: the latest invitation outbox row's status, or the literal `not sent` when there is none or the invitation is back at `pending` (a regenerate rotated its token), the same gate as the Invitation card's delivery pill. **Rendered, not enumerated**, so the model's `EMAIL_OUTBOX_STATUSES` can widen without a template edit; `sent` takes `pill-count`, everything else `pill-empty` |
| 6 | Sent | — | `email_sent_at` | Timestamp pill from `Invitation.sent_at`, or `—`; the *Invitations sent* counter counts these |
| 7 | Progress | — | `review_progress` | Pill: `<state> (D/T)`, where state is the reviewer's `not started` / `in progress` / `submitted`, the rule the reviewer's own pills follow (`spec/reviewer-surface.md` "Reviewer-status pill vocabulary"), so a new or changed answer after Submit reads `in progress` here too |
| 8 | Required<br>Fields | — | `required_fields` | Pill: `(D/T)` |
| 9 | Reminder | — | `last_reminder_at` | Timestamp pill, or `—`; a Regenerate clears it with the send, since a reminder on the old token reminded no one of the new one |
| 10 | (actions) | — | — | Per-row buttons — see below |

The tag columns sit at 2-4, between the identity column and the
status columns, so the canonical order matches the roster tables.

**Four headers are deliberately terse** — `Progress`, `Sent`,
`Reminder`, and `Required Fields` stacked onto two lines — so the table
fits its card at common desktop widths with the tag columns shown.

**`Progress` and `Required Fields` are counted in SQL for
per-reviewee instruments**, rather than by loading a
reviewer's assignments and tallying them. A reviewer's work on
**group-scoped instruments, and any instrument with a required governed
field or a require-mode branch** (see "What these pages cost to
render" below), is still tallied in Python and added to that — both
columns can be the sum of the two halves.

One thing this table does *not* say: a `required` response field that
is not `visible` is excluded from **both columns**, because the
reviewer is never shown it and so cannot answer it. `Required Fields`
loses it from both halves — `required_done` is `required_total` minus
what is missing, so hiding a field the reviewer had *already* answered
drops the done count with the total. `Progress` only ever loses it
from the numerator: that column is completed assignments over assigned
ones, and no field flag moves an assignment count. The `Coverage`
column on Responses counts the same field, for the opposite reason —
see below.

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

Send and Regenerate are available once the session is prepared
(`validated` or `ready`, `_require_validated_or_ready`, 409), so an
invitation can go out ahead of opening; a reviewer who follows it early
reaches the pre-open page. Send reminder is `ready`-only
(`_require_ready`, 409). Outside its gate a button renders disabled, and
**says why in its hover title**: Send and Regenerate, "Available once the
session is prepared"; Send reminder, "Available once the session is
activated", or "This reviewer has finished" on a complete row.

**Send and Send reminder deliver the email.** Each queues the row, then
claims and sends it in the same request through the signed-in operator's
delegated Graph mailbox (`spec/email_infra_options.md`, "Delegated Graph,
as built"), stamping the outbox row `sent` or `failed` with its reason and
writing `email.sent` / `email.send_failed`. The mailer is built first, so
with **no Microsoft token** nothing is queued or rotated and the page says
to reload. The operator's Email settings (Keep a copy in my Sent Items, Send a copy
to myself, and Replies go to the session's Help contact when it is an
address; `spec/settings_inventory.md` §1) apply. The route redirects to Invitations with `?email=` and, on a
failure, `&kind=` (the Graph failure kind); a notice atop the page reads
the result (`views.row_send_notice`):

| `email=` | Notice |
|---|---|
| `sent` | "Sent from your mailbox." |
| `failed` | "The email was not sent." plus the kind's copy; a `5xx` or network failure says it may or may not have gone |
| `superseded` | "The email was not sent: its link was regenerated first. Send it again." A Regenerate fails the invitation's still-queued rows, so a queued send never goes out with the dead link |
| `already_sent` | "Not sent again: this invitation was already sent, or is being sent." |

**Send also has a server-side eligibility gate**, which the button's
visibility rule does not express. The route refuses with **409** when the reviewer is not
`invitations.is_reviewer_eligible_for_invitation` — active, with at
least one `include=True` assignment — the same test the two bulk send
paths apply, so all three agree by construction rather than by three
queries happening to match. The gate is reachable only by a direct
POST or a stale tab, because the table renders the button only for
rows it lists and it lists only eligible reviewers. Under the session lock the service
also refuses an invitation no longer `pending` — a double click, a
stale tab — and the page says *"Not sent again: this invitation was
already sent, or is being sent."* (`?email=already_sent`): each Send
mints a new token, so a second one would kill the first link (findings
L1, 2026-11-06).

**A refused send is put back** (findings M1). The invitation is stamped
before the Graph call; if Graph refuses it outright (a 401, a 403, a
429 not waited out, another 4xx: `email_dispatch.REFUSED_KINDS`), the stamps the
send wrote (`status` / `sent_at`, or `last_reminder_at`) return to what
they were, so the row offers the same action again. After a `5xx` or a
network failure the message may have arrived, so the stamps stay and the
row offers Send reminder, which reuses the link, as the notice's "it may
or may not have gone" warns. Only stamps still holding
what the send wrote go back, so an open of the link or a Regenerate in
the meantime stands; `invitation.send_reverted` records the restore.

**Send reminder carries the same gate**: a reminder
carries the invite link, and an inactive reviewer must not be sent it,
so `/remind` also answers **409** for a reviewer who is not
`is_reviewer_eligible_for_invitation`. The bulk and scheduled reminder
paths already exclude them, through `monitoring.per_reviewer_progress`.

### Per-row drill-in

The reviewer name is a link to a per-**reviewer** detail page,
`/operator/sessions/{session_id}/invitations/reviewers/{reviewer_id}`.
**The link renders for every row, whether or not an invitation
exists.** The page is keyed on the reviewer because the reviewer is its
subject: the invitation supplies one optional field, while the reviewer
supplies the heading, the email, the breadcrumb and the row match.
The email under the heading reads as the table's cell does, a pill when the
reviewer is bound to a directory account; the reviewee drill-in's likewise.
The invitation-keyed URL
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
- **Sent** — the send timestamp or an em-dash, from
  `Invitation.sent_at`. Beside it, where the latest invitation outbox
  row carries a delivery state other than `sent`, that state renders as
  its own pill. The two are **gated independently**: the date on
  `sent_at`, the state on `Invitation.status` being past `pending`, so
  a rotated token reports nothing about the previous token's delivery
  and a send with no delivery date still reports its state. The value
  set is the model's `EMAIL_OUTBOX_STATUSES` and is **rendered, not
  enumerated**, so widening it needs no change here.
- **Last reminder** — the timestamp or an em-dash, from
  `Invitation.last_reminder_at`, which a Regenerate clears with the send
  date.

Both timestamps read the `Invitation` row rather than the outbox, so
they survive a reviewer leaving the table. The em-dash means *no date*,
not *no invitation* — the top line already answers that.

Below them, a **five-state** URL region:

| State | Copy |
|---|---|
| A URL was issued and its token is current | `Invitation URL (last issued):` + the URL |
| A URL was issued, then the token regenerated | `The invitation link was regenerated. The new link has not been sent yet, and the earlier link no longer works.` |
| Invitation exists, never sent | `No invitation URL has been issued yet.` |
| No invitation, reviewer eligible | Points at **Prepare session** on the Workflow card, and says an open session must revert to draft first |
| No invitation, reviewer **not** eligible | Says **Prepare session** will skip them, and names the two remedies |

The last two are distinct because `generate_invitations` selects active
reviewers with at least one included assignment: telling an ineligible
reviewer's operator to re-run the creator sends them to something that
cannot reach that reviewer — the card would stay `not created` however
often they ran it.

The creator is **Prepare**, and the eligible row carries the revert
caveat because `prepare_visible` is
`(is_draft and not is_setup_empty) or is_validated`: an open session
cannot run it.

"Issued" is the accurate verb for the second row: `generate_invitations`
discards the raw token, so a URL exists only once an invitation has been
**sent**. The first row shows that link built again from its token, as a
reminder would send it (`invitations.current_invite_url`, findings C1);
it differs from the one in the reviewer's inbox only if the app's host
or prefix has changed since.

#### Review Progress card

Renders only when the reviewer has a table row with at least one
assignment. Carries the row's progress fields, and a
`.card-action-row` at its foot with **Open reviewer surface**
(Secondary role), which opens
`/operator/sessions/{id}/preview-surface/1?reviewer_email=…` in a **new
tab** — the reviewer's own surface, inert, with their saved responses.

#### Email previews

Below the detail cards — two for a reviewer the table does not list, three when the
conditional Review Progress card renders — one full-width region renders the **Invitation**,
**Reminder**, and **Responses received** email tabs for this reviewer. The
active tab is selected by `?email=<kind>`; sibling links retain the reviewer
detail URL and end in `#email-previews`, so changing tabs returns to the
region rather than the top of the page. Each tab uses the same renderer as
its eventual send path, with a placeholder invitation URL where previewing
must not mint or rotate a real token.

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
whole value, with the `<datalist>` offering `Name (email-or-identifier)`
labels only and a search equal to one of them exact-matching that
handle. The count line's noun is **`reviewees`** — one row per reviewee,
from `monitoring.per_reviewee_coverage`. This page **pages** on the
same terms as Invitations: 200 rows to a page unfiltered, a filtered
view uncapped and without a pager, so only the filter branch of the
count line ever fires.

### Table columns

| # | Column | Toggle? | Sort key | Content |
|---|---|---|---|---|
| 1 | Reviewee | — | `name` | Name + email-or-identifier (`<code>`, a display pill when bound, as Invitations' Reviewer cell); name links to per-reviewee detail page |
| 2 | Tag1 | ✓ | `tag_1` | `data-col-toggle="tag-1"` / `class="tag-col tag-col-1"`; header label via `field_label_header(session, "reviewee", "tag_1")` |
| 3 | Tag2 | ✓ | `tag_2` | `data-col-toggle="tag-2"` / `class="tag-col tag-col-2"` |
| 4 | Tag3 | ✓ | `tag_3` | `data-col-toggle="tag-3"` / `class="tag-col tag-col-3"` |
| 5 | Coverage | — | `coverage_state` | Pill: `complete` / `adequate` / `at risk` / `no responses` |
| 6 | Reviewers<br>completed | — | `reviewers_done` | Pill: `D/T` (filled count vs. total) or `—` when total is 0 |
| 7 | Last response | — | `last_response_at` | Timestamp pill, or `—` |

`Reviewers completed` is stacked onto two lines for the same reason
Invitations stacks `Required Fields`: a narrower table that fits its
card. It sorts on completion percentage, on the same
terms as the Invitations progress columns above.

### Coverage state definitions

Operator-meaningful summaries computed in `app/services/monitoring.py`
(`per_reviewee_coverage`, classified by `_classify_coverage`). The unit
is the reviewee's **included assignments**, one per reviewer ×
instrument, not distinct reviewers. An assignment is complete when it
has a response row and every required field on its instrument carries a
non-empty, submitted answer (an instrument with no required field counts
any row). Coverage is the fraction of assignments complete:

- **complete** — every included assignment is complete.
- **adequate** — partial coverage at or above
  `AT_RISK_THRESHOLDS["adequate_fraction"]` (0.5).
- **at risk** — partial coverage below that threshold. Coverage is the
  only input; the deadline plays no part.
- **no responses** — no included assignment is complete yet.

These are guidance, not enforcement. The operator decides what to
do; the coverage state helps them prioritize.

**Counted in SQL**, in one aggregate over the session's
assignments rather than a per-assignment read; the states and the
threshold are those above. Two differences from the Invitations side
are deliberate, and both are pinned by
`tests/integration/test_monitoring_rollup_parity.py`: this page counts
an assignment complete only when it also carries a `submitted_at`, so a
saved draft is progress to a reviewer and not yet coverage to a
reviewee; and it counts every `required` field whether or not it is
`visible`, so a field the operator has made inactive still weighs on
coverage — except a hidden field a require-mode branch governs, which
`required_field_ids` never owes, so it weighs on neither page. A reviewer with `status` other than
`active` is dropped from Invitations and still counted here.

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
  any session-scoped page, once 14G turns bulk on) or from a per-row
  Send reminder button on the Invitations page, the same underlying
  email send happens.
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
- **Bulk-select rows for batch action.** Bulk send / remind belongs to
  the Workflow card's super-buttons (which act on every eligible
  row session-wide, and are off until 14G); per-row buttons
  handle targeted intervention.
  No multi-select checkbox column on either table.
- **Live updates.** Pages render snapshot data on each request. A
  navigation re-renders; auto-refresh is out of scope.
- **Cross-session views.** Both pages are scoped to a single
  session per P1 of `spec/operator_ui_concept.md`.

---

## What these pages cost to render

Both pages summarize every assignment in the session: Invitations rolls
up per reviewer (`monitoring.per_reviewer_progress`), Responses rolls up
per reviewee (`monitoring.per_reviewee_coverage`) **and** calls
`monitoring.summary_counts` for one number, `incomplete_count`, which
runs the reviewer-side pass a second time.

**For a per-reviewee instrument with no required governed field or
require-mode branch, neither rollup reads response rows at all** — both count
in SQL and return one row per person, and `per_reviewee_coverage` is
that and nothing else in that case. The paragraph after this one is the
exception: `per_reviewer_progress` still reads the response rows of
*group-scoped* assignments and any instrument with a **required
governed field or a require-mode branch**, and
loads those assignments themselves;
`per_reviewee_coverage` gains the same second path for the latter
(`_python_routed_coverage`). What the aggregate path may not do is
materialize a row per assignment — its count is a `func.count`, not a
`len()` over loaded objects — and the measure that catches a regression
there is **ORM instances loaded**, not queries: an implementation that
issues few queries can still build every `Assignment` and `Response` in
the session as an object (`docs/performance.md`).

`per_reviewer_progress` keeps one Python path, for **group-scoped
instruments and any instrument with a required governed field or a
require-mode branch** ("route (a)"; a require-mode
parent's governed fields are required while its condition holds,
whatever their stored `required`): a group counts once per group, and the key
is Python's `strip()` over reviewee tags or an active `Relationship`,
which SQL's `TRIM` does not reproduce; an instrument with a required
governed field is routed here because the condition it must be judged
against is stored as `Text`, and evaluating it in SQL would need a
numeric cast that errors in Postgres on a bad value and reads as 0 on
SQLite. That half is bounded by these instruments' assignments — it
prefetches only their response rows and eager-loads only their
reviewees — so a session with none of them never enters it, and one
where every instrument qualifies gains nothing from the rewrite.
`per_reviewee_coverage`'s Python half is the same trade for the
reviewee side: a per-reviewee instrument that needs it still loads its
assignments and responses as ORM rows, the accepted cost of route (a);
route (b), a stored open-branch table the SQL could join instead,
stays in reserve.

The Assignments, Invitations and Responses pages are **flat in the
roster**: the query count does not move with the roster size. The
per-size query counts are in `docs/performance.md`,
Finding 2.

**Flat is the contract; the figures are the reading.** A legitimately
added query moves a number without breaking anything, so the guards in
`tests/integration/test_monitoring_prefetch.py` pin the flatness and
the ORM-row bound, not the figures. A change that makes any page's
query count grow with the roster breaks the contract, and its figures
are re-taken there.

**Paging must not change the query count**: the slice is applied after
every row is built.

Production Postgres pays a network round trip per query, so **the query
count is the portable number and local wall times are a floor, not a
ceiling.**

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
  `app/services/monitoring.py` (`AT_RISK_THRESHOLDS`,
  `_classify_coverage`); `app/web/views/_responses.py` only carries the
  state. Future operator configuration of the threshold becomes a small
  change to that one location.
