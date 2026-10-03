# Things to check in a browser

Browser checks owed on merged changes that the test suite cannot settle:
layout, in-browser behavior and what a page shows. Every PR that owes one
adds a section here. Run them locally (`uvicorn`, fake auth). Tick a row
when it is checked; sections with unticked rows sit above the ticked ones.

## Email dates in the session's zone (#2720)

- [ ] **The deadline reads in the session's zone.** On a session whose
  display zone is not UTC (Singapore, say) with a 17:00 deadline, preview
  the invitation email. `$deadline` should read 17:00, not 09:00.
- [ ] **The submitted time does too.** Preview the responses-received
  email for a reviewer who has submitted; `$submitted_at` reads in the
  same zone.

## An inactive reviewer is not a reviewer (#2740)

- [ ] **Their invite link answers 404.** Send a reviewer an invitation,
  copy the link from the outbox, then set that reviewer inactive. Open
  the link: the page is a plain 404, not the "issued to …" mismatch
  page. Set them active again and the same link works.
- [ ] **No reminder for them.** On Manage Invitations the inactive
  reviewer has no row, so no **Send reminder**; the Pending reminders
  count leaves them out.
- [ ] **No observer CSV once archived.** As an observer, note a
  per-instrument CSV link on `/collation`, archive the session, then
  open that link's address directly: 404.

## A stored response sort re-sorts on load (A27, #2743)

- [ ] **Rows follow the badge after a reload.** On the reviewer surface
  of a multi-row instrument, click a response column's header, then
  reload. The rows keep the clicked order and match the badge; blank
  answers stay last. Rows may move once as the page loads.
- [ ] **Descending holds too.** Click the same header again, reload:
  the rows stay in descending order.
- [ ] **A display-column sort is unchanged.** Sort by a display column
  and reload: the rows arrive already sorted, with no visible move.

## Long names survive Duplicate and Replicate

- [ ] **Duplicate keeps a long name.** Rename a session to about 250
  characters, then Duplicate it from the lobby. The copy opens, named
  "Copy of …" cut at the end, with no error page.
- [ ] **Replicate keeps its suffix.** Rename an instrument to about 250
  characters, then Replicate it. The copy's name still ends " (copy)",
  with the source name trimmed to fit.

## A submit queues the confirmation email (G4)

- [ ] **On by default.** As a reviewer, submit on an Activated session.
  In Admin → Sessions, open that session's outbox: one
  responses-received row for that reviewer, status `queued`, its body
  naming the submit time.
- [ ] **A second submit refreshes it.** Recall and resubmit: still one
  queued row for that reviewer, not two.
- [ ] **Off sends nothing.** On the session's Email Template page,
  choose Responses received, untick "Send this confirmation when a reviewer submits" and save.
  Another reviewer's submit adds no row, and the submit itself still
  succeeds.

## Long session names still send (email subjects)

- [ ] **Invite and remind on a long name.** Rename an Activated session
  to about 250 characters, then send one invitation and one reminder
  from Operations. Both succeed, and each outbox row's subject is cut
  short rather than erroring.

## A failing scheduled send no longer breaks Session Home (B20)

- [ ] **Session Home loads.** Nothing in the UI can force a send to
  fail, so this is a smoke check: open Session Home for a session with
  scheduled invites or reminders set and past due. It loads, and Admin →
  Sessions shows the audit log with either the fired events or, if
  something failed, one `session.scheduled_event_failed` row per
  failing trigger, however many times the page is reloaded.

## Replicate copies the set-up (A1)

- [ ] **The copy is set up.** On a draft session, set an instrument's
  Band 1 links and a filter rule, a short label, a column width and a
  default sort, then Replicate it. The copy shows the same Band 1 pills
  and rule (not "Not set up"), the same widths and sort, and the label
  marked "Copy of …".
- [ ] **Edits stay separate.** Change the copy's Band 1 rule and save:
  the source's rule is unchanged.
- [ ] **No new page break.** Replicate an instrument that starts a new
  page: the copy sits on the same reviewer page as its source.
- [ ] **Visibility and label (2026-10-03).** Give an instrument a
  Visibility setting (reviewees see it Anonymized after release, say)
  and the short label "Peer", then Replicate it. The copy's Visibility
  matches the source's, and its card title reads "Copy of Peer".

## Zip all follows the other cards (D28)

- [ ] **Card order.** On Extract data, the left column holds Reviewer
  response metadata above Reviewee response metadata. The right column
  holds By instrument above Extract all data. The intro reads "Use
  **Zip all** to download a complete set of response data, plus
  whichever files are selected below, as each card configures them."
- [ ] **Same files as the cards.** On By instrument, turn off one
  instrument and Include metadata. On Reviewer response metadata, cycle
  Self-review to Exclude. Download each card's own file, then the intro's
  Zip all. The zip holds `…_responses.csv` and the same files under the
  same names, and each opens identical to its card's download.
- [ ] **Chips leave cards out.** Turn off the intro's Reviewee response
  metadata and Data shaper chips. Zip all no longer holds the reviewee
  metadata file or any shape files. No stats or `…_instrument_1.csv`
  files appear in any case.
- [ ] **Rehydrate still takes it.** Give an instrument the short label
  `responses`, then download Extract Setup's Zip all and this Zip all.
  Rehydrate both zips on the lobby: it accepts them.

## A copy keeps its default sort and widths (A28)

- [ ] **Duplicate.** On an instrument, set a default sort with a header
  badge and drag a column wider, then Duplicate the session from the
  lobby. The copy's instrument shows the same sort badge and column
  width, and its reviewer surface sorts the same way.
- [ ] **Settings round-trip.** Download Extract Setup's Settings CSV from
  that session and import it through another session's Quick Setup. The
  imported instrument keeps the sort and the width.

## Relationship changes update self-reviews (B33)

- [ ] **Inactivate a relationship.** In a session whose instrument
  groups by a relationship tag, generate assignments and note the
  instrument's self-review count on Assignments. On Relationships,
  inactivate the row that puts a reviewer's group-mate in their group.
  Back on Assignments, without generating again, the self-review count
  drops by that row. Reactivate it and the count comes back.

## Relationship changes move group answers (B34)

- [ ] **Inactivate a group member.** In a session whose instrument
  groups by a relationship tag, answer a group as a reviewer. On
  Relationships, inactivate one member's row. The reviewer surface
  shows that member outside the group, without the group's answer;
  the rest of the group keeps it. Reactivate the row and the member
  rejoins the group with its answer.
- [ ] **Re-import unchanged.** Download the relationships CSV and import
  it again unchanged. Every answer is still there.

## The lobby Save keeps the schedule (C1)

- [ ] **A rename keeps everything else.** On a draft with a Start, an
  End, invite and reminder offsets, a release window and Relationships
  turned on, open its lobby row, change the Name, Save. Session Home
  still shows every one of those settings.
- [ ] **An End before Start is refused.** In the same row, set the
  Deadline before the session's Start and Save: the page answers with
  "End must be on or after Start." and nothing changes, tags included.

## A repeated name in a Settings CSV is a row error (D1)

- [ ] **No 500 on a repeated shape name.** Export a session's Settings
  CSV with a saved data shape, copy that shape's `data_shapes[0].*`
  rows to `data_shapes[1].*`, and upload it to another session through
  Quick Setup. The page shows the settings slot's "Could not import
  session settings." message, not a 500, and the session is unchanged.

## The preview drops a self-review group Generate drops (B1)

- [ ] **A filtered self-row still excludes the group.** On a grouped
  instrument with **Self reviews** excluded, add a Link 2 rule that
  keeps a reviewer's teammates but not the reviewer's own reviewee row.
  The Band 2 preview no longer offers one of those teammates as its
  sample; with the exclusion off, it does.

## A lowercase response type imports as typed (D2)

- [ ] **`integer` makes a number field.** Export a session's Settings
  CSV. On an Integer field's `instruments[n].response_fields[m].data_type`
  row, change the `value` cell to `integer`. Upload it to another session
  through Quick Setup. On that session's reviewer surface the field has
  a number box. The Instruments page is no test: it read as Integer even
  before the fix.
- [ ] **An unknown type is refused.** Change the value to `Boolean`
  instead and upload again. The page shows "Could not import session
  settings." and the session is unchanged.

## Missing answers name the instrument (A2)

- [ ] **Two instruments on one page.** On a session with two
  instruments on the same page, give the second a short label (say
  "Peer"). As a reviewer, leave a required field blank on the second
  and Submit. The card's entry starts with `#2 Peer:`, not `Page 2:`,
  matching the `#2 Peer` status pill above it.

## Observers see what reviewers see (A3, A18)

- [ ] **A hidden field stays hidden.** On an instrument, untick a
  response field's Active box. As an observer on the collation page,
  the field has no column, and the instrument's Download CSV has no
  column for it either. The operator's By-instrument extract still has
  it.
- [ ] **An unanswered text field reads a dash.** On the collation page,
  or a reviewee's results page with a summarized policy, a text field
  nobody has answered shows "Total length: —", not "0 characters".

## The reviewer's own row is marked (G7)

- [ ] **A Self review pill.** In a session where a reviewer is also a
  reviewee and self-reviews are active, sign in as that reviewer: their
  own row shows a blue "Self review" pill after the name, and the row
  still saves. On a group instrument, the group row the reviewer
  belongs to shows it under the group name.

## The Data shaper's Zip all works (D13)

- [ ] **Greyed with no shape.** On Extract data with no saved shape,
  the Data shaper card's Zip all is greyed and does nothing.
- [ ] **Live once a shape saves.** Save a shape: Zip all turns live
  without a reload and downloads `{code}_data_shapes.zip`, holding
  that shape's file under the name its own Download gives it. Save a
  second, download again: both files. Delete both: the button greys.
  (Between a Delete click and the server's answer it is greyed too,
  which is too quick to see on localhost; the browser test holds it.)

## An archived session says it has closed (A25)

- [ ] **Closed copy.** Archive a session a reviewer was invited to, then
  open that reviewer's old invitation link (or `/me/sessions/{id}/1`)
  as them. The page reads "{name} — closed" and "This review has
  closed.", with no deadline line and a link back to the dashboard. A
  Prepared session still reads "opens later".

## Setup tabs underline in blue (findings register E5)

- [x] **Light and dark.** On any Setup page (Reviewers, say), the active
  Setup tab's underline is blue rather than grey, in both themes. The
  Operations row's green underline is unchanged.

## Session nav looks the same (E37)

- [x] **Tabs.** On any session page, in light and dark themes, the
  selected Setup or Operations tab still has its white (dark: near-black)
  background, and hovering another tab paints it the same way.

## E5 — Assignments and Validate before the first Prepare (#2717)

- [x] **Assignments loads fast.** Open Assignments on a session with
  about 1,000 × 1,000 rosters, no Prepare yet, and instruments not set
  up. The page should load in well under a second, not several seconds.
- [x] **Validate loads fast.** Open Validate on the same session. It
  should also load in under a second.
- [x] **The second load is no slower.** Reload either page; it should be
  as fast as the first.

## E6 — the sweep's six code defects (#2719)

- [x] **Purge and archive is red.** On Extract data, the **Purge and
  archive** button should be solid red, like the lobby expander's,
  not amber.
- [x] **A saved shape's buttons swap.** On Extract data, in the data
  shaper, a saved shape shows **Edit** and no **Save**. Click **Edit**:
  **Save** shows and **Edit** hides. Click **Cancel**: they swap back.
- [x] **A new shape's buttons still work.** Click **+Shape**. The new
  card shows **Save**, not **Edit**. Name it, pick columns, and Save it.
- [x] **Disabled link buttons match.** On the Reviewers page, switch
  the table into edit mode. The toolbar's **Add new**, a link, should be
  exactly as faint as any other disabled button (0.5, not 0.55).
  *Checked 2026-10-02: Add new looked fainter than Search; fixed in
  #2730 and rechecked the same day.*
- [x] **The Quick Setup banner points the right way.** Upload a second
  reviewers CSV in Quick Setup without ticking the replace box. The
  banner should say the box is "just above Submit", and it is.
- [x] **The Validate Fix link lands.** On a single-instrument session,
  run Prepare, then add a reviewer. On Validate, the
  reviewer-missing warning's **Fix on Assignments** should open
  Assignments at the top, with no dead `#reviewer-row-…` in the URL.

## Per-instrument Open / Close removed (#2722)

- [x] **No Open / Close on an instrument.** On the Instruments page of
  an activated session, no instrument card offers Open or Close.
- [x] **Accepting is session-wide.** Activate a session: every
  instrument accepts. Close session: none does, and the reviewer
  surface goes read-only on every page.

## Closed surface and reading back your own answers (#2723)

- [x] **Prev / Next survive the close.** Close a two-page session. The
  reviewer surface shows the read-only form with Prev / Next and no
  Save / Cancel / Submit.
- [x] **Raw shows them.** Set "Who can see what you wrote" → You →
  Responses released to Raw and open a release window. The reviewer
  sees their own values on the surface and on the summary page.
- [x] **Off hides them.** Set that cell off. The surface says the
  values are hidden; the summary says the responses are not shown and
  has no CSV link.
- [x] **Archive hides everything.** Archive the session; the summary
  shows nothing.

## Blocked Submit and stale sort keys (#2724)

- [x] **A blocked Submit stays on its page.** On a two-page session,
  leave a required field empty, go to page 2 and press Submit. The
  missing-fields card shows over page 2, and its Cancel stays on page 2.
- [x] **A deleted sort field doesn't block the save.** On an instrument
  sorted by a display field, delete that field, then save the card. It
  saves, and the remaining sort keys renumber 1, 2…

## Observer tag retired (A19)

- [x] **Migrate first.** Run `alembic upgrade head`; the app then
  starts and the Instruments page loads.
- [x] **An old settings CSV still imports.** Import a settings CSV
  exported before this change (it has `…observer_tag` rows) through
  Quick Setup. It applies without an error, and a fresh export has no
  `observer_tag` rows.
- [x] **Observers still see their cohort.** On the observer collation
  page, an observer with a cohort rule sees their counts; one with no
  rule sees the "no rule" message.

## Reviewer visibility is Raw or off (A18)

- [x] **Migrate first.** Run `alembic upgrade head`.
- [x] **The You cell cycles two ways.** On an instrument card, unlock
  "Who can see what you wrote" and click You → Responses released. It
  cycles — / Raw responses only; Anonymized summaries no longer appears.
- [x] **A stored summary reads as off.** An instrument whose You cell
  was Anonymized summaries before migrating now shows —, and the
  reviewer's own card shows — in that cell too.

## Inactive people keep their pairs, excluded (B2, B4)

- [x] **Deactivating excludes, not deletes.** On a prepared session
  with a saved response, set that reviewer's reviewee inactive and run
  Prepare. On Assignments the pair is still there, shown inactive; the
  Prepare card warns of no response loss.
- [x] **Reactivating brings the answer back.** Set the reviewee active
  and Prepare again. The pair is included, and the reviewer sees their
  saved answer on the surface.
- [x] **Validate names a reviewer left with nothing.** Make every
  reviewee of one active reviewer inactive. Validate warns that the
  reviewer "has no active assignments"; an inactive reviewer is never
  named.
- [x] **A group member who comes back sees current answers.** On a
  group-scoped instrument, answer a group, deactivate one member and
  Prepare, change the group's answer, then reactivate the member and
  Prepare. The reviewer sees the changed answer, not the old one.

## Settings replace names its loss (C3)

- [x] **The tick says what a settings file does.** On Session Home's
  Quick Setup card, the replacement tick ends "A settings file rebuilds
  every instrument and deletes its assignments."
- [x] **A settings upload still needs the tick.** Unlock the card,
  choose a settings CSV and leave the tick off: Submit stays disabled.
  Tick it and submit: the settings apply.

## Data shaper Delete needs a tick (E36)

- [x] **Delete waits for the tick.** On Extract data, every shape card
  has a "Yes, delete this shape" tick on its own line beneath the
  buttons, flushed right. **Delete** stays disabled until that card's
  tick is on, and ticking one card opens no other card's **Delete**.
- [x] **The tick resets.** Tick a card, then click **Cancel**, **Edit**
  on another shape, or **+Shape**: the tick clears and **Delete** is
  disabled again. Ticked, **Delete** removes the shape, and it stays
  gone after a reload.
- [x] **A deleted card stays gone (#2742).** Tick and **Delete** a
  shape: no other card opens or highlights in its place, and **+Shape**
  or **Edit** on another card behaves as before.

## Reviewee results only after release (A13)

- [x] **Nothing before release.** On an Activated session with a
  reviewee policy set on After release, sign in as that reviewee:
  `/me` shows no reviewee row, and `/me/sessions/{id}/results` is a
  404.
- [x] **Values after release.** Close the session and let the release
  window open: the results page lists every reviewer with an included
  assignment, with submitted values filled and the rest empty.
