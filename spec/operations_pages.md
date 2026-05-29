# Invitations & Responses — functional spec

Two Operations-row pages that together cover the running-session
work of engaging reviewers and tracking reviewee coverage:

- **Invitations** — reviewer-centric: who has been invited, who has
  responded, who needs nudging.
- **Responses** — reviewee-centric: per-reviewee coverage, surfacing
  under-served reviewees that the reviewer-centric view doesn't make
  visible.

Both render the same overall chrome shape: the **Workflow card** at
the top (per `spec/workflow_card.md`), then an info card with
inline counters, then a filter card, then a table. Bulk-actions
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

The **Extract data** tab landed 2026-05-29 as a skeleton page
(per `guide/extract_data.md`); per-lens download wiring follows
in subsequent PRs. The tab sits at the end of the strip
because it's an end-of-flow surface — operators reach for it
once response data is in.

The dev-diagnostic Outbox page (`sys_admin_session_outbox.html`)
sits **outside the chrome** under the Sys Admin doorway at
`/operator/sys-admin/sessions/{id}/outbox`. Day-to-day operator work
shouldn't need it; pilot debugging and send-troubleshooting do.

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
3. **Info card + filter card** — two half-width cards in a
   `bottom-grid`. The info card on the left renders an inline
   middle-dot prose row of lifecycle / coverage counters; the filter
   card on the right is a `GET` form (Status `<select>` + Search
   `<input>` with a `<datalist>` for autocomplete). Apply submits;
   Clear is a link back to the bare URL.
4. **Result table** — single-card containing the filtered row list,
   or an empty-state `.muted` message when no rows match.

### Lifecycle behavior

Both pages render content across all session lifecycle states. Per
the Workflow-card-as-Operations-chrome rollout, the previous yellow
`.card.lock` "session must be Activated" notice retired here —
the Workflow card's stepper makes lifecycle state explicit. 18F
Part 1 split the previous Activate super-button into a dedicated
**Prepare session** button (Generate + Validate) and a solo
**Activate session** button; 18F Part 2 then relaxed the
invitation gate so Create / Send invites work from
`validated`, not only `ready`. The Invitations page follows the
same gate: per-row action buttons are live from `validated`
onward; the underlying route-layer gate
(`_require_validated_or_ready` in
`app/web/routes_operator/_operations.py`) is the source of
truth. **Send-reminders** keeps the stricter `ready`-only
requirement.

---

## Invitations page

Reviewer-centric. The operator's working surface for monitoring +
nudging individual reviewers throughout the session.

### Info card — eight lifecycle counters

A single inline middle-dot prose row carrying eight counters:

```
Eligible reviewers N · Invitations created M · Invitations sent K ·
Pending invitations P · Reminders sent R · Pending reminders Q ·
Completed reviews C · Incomplete reviews I
```

Each counter renders as a `.pill.pill-count` (or `.pill.pill-empty`
when the variant is "zero-is-good / nonzero-is-attention" and the
value is nonzero — applied to Pending invitations, Pending
reminders, and Incomplete reviews).

### Filter card

- **Status `<select>`** — `all` plus the per-status options exposed
  by the route via `filter_status_options`.
- **Search `<input>`** — autocompletes against
  `filter_search_options` (reviewer name or email), matched against
  the filtered status set.
- **Apply / Clear** — Apply submits the form; Clear (visible only
  when a filter is active) is a link back to the unparameterised
  page.
- A muted "Showing N of M." line appears alongside the buttons when
  a filter is active.

### Table columns

| Column | Content |
|---|---|
| Reviewer | Name + `<code>` email; name links to per-invitation detail page when an `Invitation` row exists |
| Email Status | Pill: `sent` / `queued` / `not sent` |
| Email Sent | Timestamp pill, or `—` |
| Review Progress | Pill: `submitted (D/T)` or `<state> (D/T)` where state is a per-invitation lifecycle label |
| Required Fields | Pill: `(D/T)` |
| Last reminder | Timestamp pill, or `—` |
| (actions) | Per-row buttons — see below |

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

**Send** and **Regenerate** are live from `validated` onward
(18F Part 2 gate relaxation). **Send reminder** stays
`ready`-only — reminders fire after the response window opens,
not before. All three render `disabled` outside their allowed
state.

### Per-row drill-in

The reviewer name is a link to a per-invitation detail page
(`/operator/sessions/{session_id}/invitations/{invitation_id}/detail`)
showing the reviewer's full engagement history.

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

### Filter card

Same shape as the Invitations filter card: Status `<select>` +
Search `<input>` against `filter_search_options` (reviewee name or
email) + Apply / Clear / "Showing N of M." muted note.

### Table columns

| Column | Content |
|---|---|
| Reviewee | Name + `<code>` email-or-identifier; name links to per-reviewee detail page |
| Coverage | Pill: `complete` / `adequate` / `at risk` / `no responses` |
| Reviewers completed | Pill: `D/T` (filled count vs. total) or `—` when total is 0 |
| Last response | Timestamp pill, or `—` |

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

## Implementation pointers

- View-shape adapters in `app/web/views/_invitations.py` and
  `app/web/views/_responses.py` own the per-row projection + the
  info-card counter aggregation. Routes stay thin.
- Per-row and Workflow-card reminder send-paths share their
  underlying implementation in `app/services/invitations.py` —
  single source of truth for "send reminder email."
- Filter parsing lives in `app/web/views/_filters.py` so the
  Invitations and Responses pages reuse the same Status / Search
  contract.
- "At risk" thresholds and coverage-state definitions on the
  Responses page are computed in one place in
  `app/web/views/_responses.py`. Future operator configuration of
  the threshold becomes a small change to that one location.
