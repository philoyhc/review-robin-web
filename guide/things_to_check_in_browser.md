# Things to check in a browser

Browser checks owed on merged changes that the test suite cannot settle:
layout, in-browser behavior and what a page shows. Every PR that owes one
adds a section here. Run them locally (`uvicorn`, fake auth). Tick a row
when it is checked; once every row in a section is ticked, delete the
section (git history keeps it), so this file lists only what is owed.

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
  choose Responses received, click the chip to "Don't send response
  confirmation" and save.
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
  instrument's self-review count on Assignments (the N in its
  "Include N self reviews" chip since UX refinements Item 7). On Relationships,
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
  instrument with self reviews excluded, add a Link 2 rule that
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

- [ ] **A hidden field stays hidden.** On an instrument, click a
  response field's chip off. As an observer on the collation page,
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

## A Settings CSV's errors show in Quick Setup (D31)

- [ ] **The errors are listed.** On a draft session, upload a Settings
  CSV with an instrument row but no `instruments[1].name` through Quick
  Setup's Settings slot. The banner reads "Could not import session
  settings." and lists the error underneath (`instruments[1].name: name is
  required`). With seven bad instruments it lists five and "…and 2 more."

## Assignments' replace banner, and a Settings import's landing (#2809, #2810)

- [ ] **The banner reads true and dismisses.** On a session with
  assignments, open `/operator/sessions/{id}/assignments?needs_confirm=1`
  (the page a direct POST to `/assignments/generate` without
  `confirm_replace` lands on). The red banner reads "Replace not
  confirmed. The existing assignments were kept." and carries a Cancel
  button at its bottom right; Cancel returns to the page without the
  banner.
- [ ] **A Settings import lands on its slot.** Import a Settings CSV
  through Quick Setup. The page returns to Session Home at the Settings
  slot, with no `?config_imported=ok` in the address bar.

## Delete user only for accounts with no activity (#2867)

- [ ] **Delete stays disabled for a user with history.** On Sys Admin →
  Accounts, select an operator who created a session (or a participant
  who has submitted). Delete stays greyed; Revoke is still offered.
- [ ] **Delete works for an account with no activity.** Invite a fresh
  email, select it, and Delete: the row goes.

## Quick Setup on a validated session (#2873)

- [ ] **The card is live.** Prepare a session so it is Validated, with
  no responses. On Session Home, Quick Setup's slots take a file
  straight away (no Unlock since operator pages Item 1, PR 3).
- [ ] **A submit lands and demotes.** Stage a Reviewers CSV, tick the
  replace confirmation, and Submit:
  the roster changes, the session reads Draft, and the Workflow card
  asks to Prepare again.

## Session Home asks before unsaved details are lost (operator pages Item 1, PR 1)

- [ ] **A dirty card asks.** Unlock Session details, type into the
  description, then click a link off Home (or another card's button):
  the browser asks whether to leave. Stay, and the typing is still there.
- [ ] **Save, Cancel and Lock don't ask.** Edit again and Save: no prompt,
  and the saved card comes back clean. Edit and Cancel, or edit and Lock,
  then leave: no prompt.
- [ ] **A clean card doesn't ask.** Unlock without typing, then leave:
  no prompt.
- [ ] **Back after a Save re-arms it.** Edit and Save, edit again, go
  to another page, then come back with the browser's Back button and
  leave again: it asks (the back/forward-cache case no test covers).

## Owners without a lock; removing another owner asks (operator pages Item 1, PR 2)

- [ ] **The card is live on load.** Open Session Home: the Owners card
  has no Lock / Unlock and isn't greyed; the picker and Add owner work
  straight away.
- [ ] **Removing another owner asks, by name.** Click Remove on another
  owner's row: the browser's confirm reads "Remove *their name* as an
  owner of this session?" (their email if they have no name). Cancel
  posts nothing and leaves no loading bar; OK removes them.
- [ ] **Your own row and the last owner are unchanged.** Your own
  Remove still warns that you'll lose access; on a one-owner session
  the Remove is disabled.
- [ ] **Quick Setup is unaffected.** Add an owner: Quick Setup is as it
  was when the page comes back.

## Quick Setup without a lock (operator pages Item 1, PR 3)

- [ ] **Live on load.** On a Draft session with no responses, Session
  Home's Quick Setup isn't greyed and has no Lock / Unlock; a file can
  be staged at once, and Submit sits alone at the bottom right.
- [ ] **Still locked when unavailable.** On an Activated session (or one
  with responses) the card is greyed, its file inputs and the replace
  checkbox can't be used, and there is nothing to unlock.
- [ ] **Nothing relocks.** Stage nothing, go to the lobby and back, or
  to another session's Home and back: the card is as it was.

## No stuck loading bar after declining a leave prompt (operator pages Item 2)

- [ ] **Instruments.** Unlock a card, type in a field name, click a nav
  tab and choose to stay: no loading bar, no progress cursor.
- [ ] **Observers.** Select an observer, change the cohort rule (AND/OR
  is enough), click a nav tab and choose to stay: no loading bar.
- [ ] **A confirmed leave still works** on both pages: choose to leave
  and the next page loads (without the bar, as on Session Home).

## Lobby cycle chips are always dark (operator pages Item 3, PR 1)

- [ ] **Lobby.** With tagged sessions, the AND/OR and Select all / Clear
  all chips are dark like a selected tag, in both of their labels, in
  light and dark themes; unselected tag chips stay light.
- [ ] **Archived page.** The Select all / Clear all chip is dark too.

## Extract empty-row chips are always dark (operator pages Item 3, PR 2)

- [ ] **Both labels dark.** On Extract data, click "All assignment rows",
  "All reviewers" and "All reviewees": each flips to its "… with data" /
  "… with responses" label and stays dark, in light and dark themes.
  "Include metadata" and the instrument chips still go light when off.
- [ ] **Reload.** With a chip on its "with responses" label, reload: it
  comes back on that label, still dark, and its card's download still
  drops the empty rows.

## The Guide's "Reading the controls" card (UX refinements Item 10)

- [ ] **/guide, light and dark.** The card sits under "What Review
  Robin Web does", Buttons and Checkbox guards on the left, Pills and
  chips on the right; below 800px it stacks to one column.
- [ ] **Every chip sample.** Email and Tag1 switch between solid blue
  and the faint tint; "Include 1 self review" goes solid (2), then faint
  (0); "Include self reviews" flips to "Exclude self reviews" and stays
  solid; "Not set" goes to "All", then "Filter using tags", then back to
  "Not set"; "Observers" doesn't move and shows its reason on hover.
  The copy's "solid blue" and "faint" read true in both themes.
- [ ] **The button samples** don't change the pointer or tint on hover.
- [ ] **The guard.** "Delete all reviewers" is off until the box is
  ticked, and clicking it does nothing.
