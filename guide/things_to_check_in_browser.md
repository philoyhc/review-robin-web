# Things to check in a browser

Browser checks owed on merged changes that the test suite cannot settle:
layout, in-browser behavior and what a page shows. Every PR that owes one
adds a section here. Run them locally (`uvicorn`, fake auth). Tick a row
when it is checked; once every row in a section is ticked, delete the
section (git history keeps it), so this file lists only what is owed. A
section may point to upload files under `guide/browser_check_files/`;
delete them once no remaining section points to them.

A run order for every section below, with upload files, is in
`guide/browser_check_files/checklist/README.md` (2026-10-13). Delete it
with the last section it covers.

## Email dates in the session's zone (#2720)

- [x] **The deadline reads in the session's zone.** On a session whose
  display zone is not UTC (Singapore, say) with a 17:00 deadline, preview
  the invitation email. `$deadline` should read 17:00, not 09:00.
- [ ] **The submitted time does too.** Preview the responses-received
  email for a reviewer who has submitted; `$submitted_at` reads in the
  same zone. *Needs an Azure deployment; not checkable locally (author,
  2026-10-13).*

## Long names survive Duplicate and Replicate

- [ ] **Duplicate keeps a long name.** Rename a session to about 250
  characters, then Duplicate it from the lobby. The copy opens, named
  "Copy of …" cut at the end, with no error page.
- [ ] **Replicate keeps its suffix.** Rename an instrument to about 250
  characters, then Replicate it. The copy's name still ends " (copy)",
  with the source name trimmed to fit.

## A submit queues the confirmation email (G4)

- [x] **On by default.** As a reviewer, submit on an Activated session.
  In Admin → Sessions, open that session's outbox: one
  responses-received row for that reviewer, status `queued`, its body
  naming the submit time.
- [x] **A second submit refreshes it.** Recall and resubmit: still one
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

## Zip all follows the other cards (D28)

- [x] **Card order.** On Extract data, the left column holds Reviewer
  response metadata above Reviewee response metadata. The right column
  holds By instrument above Extract all data. The intro reads "Use
  **Zip all** to download a complete set of response data, plus
  whichever files are selected below, as each card configures them."
- [x] **Same files as the cards.** On By instrument, turn off one
  instrument and Include metadata. On Reviewer response metadata, cycle
  Self-review to Exclude. Download each card's own file, then the intro's
  Zip all. The zip holds `…_responses.csv` and the same files under the
  same names, and each opens identical to its card's download.
- [x] **Chips leave cards out.** Turn off the intro's Reviewee response
  metadata and Data shaper chips. Zip all no longer holds the reviewee
  metadata file or any shape files. No stats or `…_instrument_1.csv`
  files appear in any case.
- [ ] **Rehydrate still takes it.** Give an instrument the short label
  `responses`, then download Extract Setup's Zip all and this Zip all.
  Rehydrate both zips on the lobby: it accepts them.

## A copy keeps its default sort and widths (A28)

- [x] **Duplicate.** On an instrument, set a default sort with a header
  badge and drag a column wider, then Duplicate the session from the
  lobby. The copy's instrument shows the same sort badge and column
  width, and its reviewer surface sorts the same way.
- [ ] **Settings round-trip.** Download Extract Setup's Settings CSV from
  that session and import it through another session's Quick Setup. The
  imported instrument keeps the sort and the width.

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

## An archived session says it has closed (A25)

- [ ] **Closed copy.** Archive a session a reviewer was invited to, then
  open that reviewer's old invitation link (or `/me/sessions/{id}/1`)
  as them. The page reads "{name} — closed" and "This review has
  closed.", with no deadline line and a link back to the dashboard. A
  Prepared session still reads "opens later". *The closed half passed
  (author, 2026-10-13); the Prepared half is checklist step 41.*

## A Settings CSV's errors show in Quick Setup (D31)

- [ ] **The errors are listed.** On a draft session, upload a Settings
  CSV with an instrument row but no `instruments[1].name` through Quick
  Setup's Settings slot. The banner reads "Could not import session
  settings." and lists the error underneath (`instruments[1].name: name is
  required`). With seven bad instruments it lists five and "…and 2 more."

## Assignments' replace banner, and a Settings import's landing (#2809, #2810)

- [x] **The banner reads true and dismisses.** On a session with
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

## Upload banners read Dismiss, and a missing tick says so

- [ ] **Quick Setup's banner reads Dismiss.** Refuse a file in a Quick
  Setup slot: the banner's one button reads Dismiss and clears it.
- [x] **A replace without the tick says so.** On a Setup page with rows,
  open the upload card, then in the inspector remove the Upload button's
  `disabled` and the replace box's `required` (the browser's own checks
  otherwise stop the submit). Choose a clean file, leave the box
  unticked, and Upload: the card shows "Tick the replacement-confirmation box just
  above Upload, then upload again." with Dismiss, not a blank page.
- [ ] **A replace that would discard responses says so on the card.** On
  Reviewers (then Reviewees) for a session reverted to Draft with saved
  responses, open the upload card; the tick names the responses. In the
  inspector delete the hidden `acknowledge_response_loss` input, then
  choose a clean file, tick and Upload: the card shows "This session now
  holds reviewer responses, which replacing this roster would discard…"
  with Dismiss, not a full error page, and no response is gone. On the
  card the banner sits in, choose the file again, tick and Upload: the
  roster is replaced. *Reviewers passed in full and Reviewees up to
  the banner (author, 2026-10-13); the Reviewees retry from the banner's
  card is still to run.*

## The Sample session walkthrough sets Band 1 before Prepare (#3015)

- [ ] **The Guide's steps work as written.** Follow the Guide's Sample
  session card on a fresh session. After the Quick Setup step the
  Workflow card offers no Prepare. The new Instruments step (unlock,
  set the three Instrument assignment rule links to all, all,
  individual, save) brings Prepare back, and Prepare reaches Validated.

## A relationship-tag boundary survives the card (pair-context Link 3)

- [ ] **The boundary is shown and kept.** On an instrument grouped by a
  relationship tag (the checklist's Team review, grouped by
  `PairContextTag1`), unlock the card. Unit of review shows that tag in
  its boundary select, not —. Save without changing it, reload: still
  that tag, and the reviewer surface still groups by team.
