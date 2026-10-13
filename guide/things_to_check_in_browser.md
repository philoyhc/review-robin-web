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

## Delete user only for accounts with no activity (#2867)

- [ ] **Delete stays disabled for a user with history.** On Sys Admin →
  Accounts, select an operator who created a session (or a participant
  who has submitted). Delete stays greyed; Revoke is still offered.
- [ ] **Delete works for an account with no activity.** Invite a fresh
  email, select it, and Delete: the row goes.

## Upload banners read Dismiss, and a missing tick says so

- [x] **Quick Setup's banner reads Dismiss.** Refuse a file in a Quick
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
  that tag, and the reviewer surface still groups by team. *The select
  and the save passed (author, checklist step 34, 2026-10-13); the
  reviewer surface is still to check.*

## Session Home's offset boxes show examples

- [ ] **Same hints as Create.** On Session Home, unlock Session details
  on a session with no offsets set. *Send invites* shows `e.g. -P1D,
  -PT2H` and *Send reminders* shows `e.g. -P2D, -PT4H` in grey, as on
  New session.
