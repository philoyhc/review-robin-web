# Invitations & Responses — functional spec

Two Operations pages that together cover the running-session work
of engaging reviewers and tracking reviewee coverage:

- **Invitations** — reviewer-centric: who has been invited, who has
  responded, who needs nudging. Combines what was previously split
  across the Manage Invitations and Monitoring pages.
- **Responses** — reviewee-centric: per-reviewee coverage,
  surfacing under-served reviewees that the reviewer-centric view
  doesn't make visible.

Both follow a shared list-with-bulk-actions pattern; specifics
differ by audience.

## Page identity

| Page | Template | URL | Operations row position |
|---|---|---|---|
| Invitations | `session_invitations.html` | `/sessions/{id}/invitations` | After Validate, Preview |
| Responses | `session_responses.html` | `/sessions/{id}/responses` | After Invitations |

Operations row after this consolidation:

```
Operations  [Validate][Preview][Invitations][Responses]
```

Pre-flight pair (Validate, Preview), monitoring pair (Invitations,
Responses). The dev-diagnostic Outbox page (`session_outbox.html`)
sits **outside the chrome** — it's reachable from a "View outbox"
button on Manage Invitations, not a tab. Day-to-day operator work
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

## Shared patterns

Both pages share the same overall structure: a primary list, with
filtering, selection, bulk actions, and per-row drill-in.

### List structure

A table-style list of rows, one per primary entity (reviewer for
Invitations, reviewee for Responses). Standard table styling per
Part 1 of the visual style spec. Columns vary per page; common
elements:

- **Identity** (name + key context).
- **Status** (lifecycle within the page's domain — e.g.,
  "responded," "at risk").
- **Quantitative summary** (counts, percentages).
- **Per-row actions** (small buttons or icon-buttons, scoped to
  that row).

### Filtering

Above the list, a filter strip with:

- **Status filter** (dropdown or pill-row): show only rows in a
  particular status. Page-specific values.
- **Search** (text input): filter by name or other identifying
  text.

Filters compose: applying a status filter + search narrows to rows
matching both.

### Bulk selection and actions

- **Checkbox column** as the leftmost table column. A header
  checkbox selects/deselects all currently-visible (filtered) rows.
- **Bulk action bar** appears above the list when at least one row
  is selected. Shows count of selected rows and available bulk
  actions as buttons.
- Bulk actions act on the selection only, not the full filtered
  set unless "select all" is engaged.
- Bulk actions follow the standard inline-confirmation pattern from
  Part 1 — primary button transforms into "Confirm" with adjacent
  Cancel.

### Per-row drill-in

Clicking a row (outside the checkbox and any inline buttons) opens
a detail panel or sub-page showing that entity's full state and
history. Drill-in is for investigating specific cases; the main
mode of operator use is the list itself.

Implementation choice (panel vs. sub-page) is a UI decision left to
implementation; a side panel keeps the operator in context, a
sub-page allows more detail.

### Lifecycle behavior

Both pages render content across all session lifecycle states but
with different action availability:

- **Draft / Validated:** pages render with empty or minimal data
  ("No invitations sent yet — activate the session to begin").
  Bulk and per-row send/remind actions are disabled with
  contextual explanation. Pages remain reachable, consistent with
  P4 (lifecycle disables, never hides).
- **Activated:** full functionality. Sending, reminding, and
  drill-in all work normally.
- **Reserved states (Expired, Archived):** when introduced, pages
  likely render read-only — historical data still inspectable, but
  no new sends or reminders. Treatment to be defined when those
  states ship.

---

## Invitations page

Reviewer-centric. The operator's working surface for engaging
reviewers throughout the session.

### Columns

| Column | Content |
|---|---|
| ☐ | Selection checkbox |
| Reviewer | Name + email |
| Invited | Timestamp of invitation, or "—" if not invited |
| Last activity | Most recent reviewer activity (response submission, link click, login) — operator-meaningful, not raw audit data |
| Response status | Progress summary: "7 / 7 complete," "3 / 5 incomplete," "not started," etc. |
| Actions | Per-row buttons: Send invitation (if uninvited), Send reminder (if invited but incomplete) |

### Status filter values

- All
- Not yet invited
- Invited, not started
- In progress
- Complete
- Stale (invited but no recent activity, threshold operator-configurable or app-default)

### Bulk actions

- **Send invitations** — to selected reviewers who haven't been
  invited. Reviewers already invited are silently skipped (the
  action's confirmation makes this clear: "Send invitations to 12
  selected reviewers (3 already invited will be skipped)").
- **Send reminders** — to selected reviewers who have been invited
  but are not yet complete. Same skip behavior for reviewers
  already complete or not yet invited.

The two actions are deliberately separate even though both produce
emails. Combining them ("Reach out to selected") would obscure the
distinction the operator usually cares about (first contact vs.
follow-up).

### Per-row drill-in

Shows the reviewer's full engagement history:

- Invitation sent (timestamp).
- Reminders sent (each timestamp).
- Logins / link clicks (if tracked).
- Response submissions (per-instrument timestamps).
- Currently assigned reviewees with per-reviewee response status.

Drill-in is read-only; actions on the reviewer (resending, manual
reminders) happen via the row's Actions column or via bulk
selection, not from inside the drill-in.

---

## Responses page

Reviewee-centric. Surfaces coverage from the reviewee's perspective
and identifies under-served reviewees that the Invitations page
doesn't make visible.

### Columns

| Column | Content |
|---|---|
| ☐ | Selection checkbox |
| Reviewee | Name + key context |
| Reviewers assigned | Count of reviewers expected to review this reviewee |
| Responses received | Count of reviewers who have completed their review of this reviewee |
| Coverage | Visual indicator (e.g., 4/5, with bar or percentage) |
| Status | "Complete" / "Adequate" / "At risk" / "No responses" — operator-meaningful summary |
| Actions | Per-row button: Remind assigned reviewers (sends reminders to the subset of this reviewee's assigned reviewers who haven't yet responded for this reviewee) |

### Status definitions

Operator-meaningful summaries derived from the coverage:

- **Complete** — all assigned reviewers have responded.
- **Adequate** — coverage above some threshold (e.g., ≥ 60% of
  assigned reviewers responded). Threshold is app-default; future
  enhancement could let operator configure.
- **At risk** — coverage below threshold and session deadline
  approaching, or zero responses well into session run.
- **No responses** — zero reviewers have responded for this
  reviewee.

These are guidance, not enforcement. The operator decides what to
do; the status helps them prioritize.

### Status filter values

- All
- At risk
- No responses
- Adequate
- Complete

### Bulk actions

- **Remind assigned reviewers for selected reviewees** — sends
  reminders to the union of "reviewers assigned to any selected
  reviewee, who haven't yet responded for that reviewee." This
  crosses into the Invitations page's reminder mechanism but is
  triggered from the reviewee view because it's a reviewee-centric
  intervention.

  Confirmation makes the scope clear: "Send reminders to 8
  reviewers covering 3 selected reviewees."

The action shares the underlying reminder send-path with the
Invitations page; only the selection logic differs.

### Per-row drill-in

Shows the reviewee's coverage detail:

- List of reviewers assigned to this reviewee.
- Per-reviewer response status for this reviewee specifically.
- Timestamps for completed responses.
- A "Remind non-responders" action that triggers reminders to the
  subset that hasn't responded for this reviewee.

Drill-in is read-only for response content (the operator doesn't
read responses here — that's the Extract Data flow); it shows
status and lets the operator trigger reminders.

---

## Cross-page interactions

The two pages share data and occasionally overlap in operator intent:

- **Reminder send-path is shared.** Whether the operator triggers a
  reminder from the Invitations page (reviewer-centric), the
  Responses page (reviewee-centric), or per-row drill-in, the same
  underlying email send happens. Implementation should not duplicate
  the send logic.
- **Pre-fill across pages.** When the Responses page surfaces an
  at-risk reviewee and the operator wants more context, a "View
  reviewers for this reviewee" link can navigate to the Invitations
  page pre-filtered to the relevant reviewers. Optional; useful
  for investigation flows.
- **Reminder content and configuration live on the Email Template
  Setup page**, not on these Operations pages. These pages trigger
  sends; the content (subject, body, reminder schedule defaults)
  is configured at setup time.

---

## What these pages do not do

- **Read response content.** The operator does not read individual
  reviewer responses from these pages. Response content is for
  Extract Data; the Operations pages show *whether* responses
  exist, not *what* they say.
- **Edit assignments or rosters.** Cannot move reviewers around,
  reassign reviewees, or change instruments. That's Setup work; if
  the operator needs to do it mid-session, they Pause Session and
  go to the Setup pages.
- **Modify email content.** Reminder and invitation emails are
  edited on the Email Template Setup page. These pages send
  whatever the templates produce.
- **Live updates.** Pages render snapshot data. A refresh
  affordance updates the snapshot; auto-refresh is out of scope.
- **Cross-session views.** Both pages are scoped to a single
  session per P1 of the UI concept doc.

---

## Migration from the current pages

The current implementation has two Operations pages:

- `session_invitations.html` (`/sessions/{id}/invitations`) —
  Manage Invitations.
- `session_monitoring.html` (`/sessions/{id}/monitoring`) —
  Monitoring with reminders.

After this consolidation:

- The new Invitations page (`session_invitations.html`,
  `/sessions/{id}/invitations`) **reuses the URL slug** and
  template name of the current Manage Invitations page, but its
  content is the consolidated reviewer-centric list with sending +
  monitoring + reminders combined.
- The new Responses page (`session_responses.html`,
  `/sessions/{id}/responses`) is a new template and URL.
- The current `session_monitoring.html` is retired. The
  `/sessions/{id}/monitoring` URL can either redirect to
  `/sessions/{id}/invitations` (preserving inbound links) or 404
  with explanation. The redirect is friendlier for any existing
  bookmarks.

The reuse of the Invitations slug is intentional: it's the closest
fit semantically, and bookmarks/links to that URL still land on a
useful page.

---

## Doc impact

`spec/operator_ui_concept.md`:

- Operations Pages list updates to reflect the new structure:
  Validate, Preview, Invitations, Responses. (The Outbox page
  retains its `/sessions/{id}/outbox` URL but exits the chrome
  taxonomy — reachable from a button on Manage Invitations.)
- Description of Invitations updates to note its broader scope
  (sending + monitoring + reminders).
- Responses is a new entry.
- New page-level contract entries for Responses and the
  consolidated Invitations.
- Retired contract for the old Monitoring page.

## Implementation pointers

- The list-with-bulk-actions pattern is shared between the two
  pages. Implement once as a reusable component (or set of
  conventions); both pages instantiate it with their own columns,
  filters, and actions.
- Per-row and bulk reminder send-paths must share their underlying
  implementation — single source of truth for "send reminder
  email."
- Filtering and selection state is page-local and not persisted
  across navigations. Operators returning to the page see the
  default unfiltered list.
- Drill-in implementation choice (side panel vs. sub-page) is open;
  pick whichever fits the codebase's existing patterns. If
  introducing a new pattern, side panel is gentler — keeps the
  operator in list context.
- "At risk" thresholds and status definitions on the Responses
  page should be implemented as constants or config in one place,
  not scattered across rendering code. Future operator
  configuration of these thresholds becomes a small change to that
  one location.
