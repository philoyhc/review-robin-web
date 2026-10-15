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

## Back links name only sessions you can see (P1)

- [ ] **A stranger sees the default.** Signed in as someone with no role
  on a session, open `/about?return_to=/me/sessions/<id>` for that
  session's id. The back link reads "← Back to your reviews" (or "← Back
  to Sessions" if you are an operator), never the session's name.
- [ ] **An owner still sees the name.** As the session's owner, open
  About from inside that session. The back link names the session.

## Participant chrome and copy (M2, M5, M8, M14)

- [ ] **No Settings link for a participant.** Signed in as a reviewer who
  is not an operator, open About. The top bar shows no Settings link,
  and the back link reads "← Back to your reviews" and goes to `/me`.
- [ ] **The Guide shows its version.** As the same reviewer, open the
  Guide. The top bar reads "(version …)" with a number in it.
- [ ] **Sign-in details names you.** From the invite mismatch page, follow
  "Sign-in details". The top bar reads "Signed in as" with your name.
- [ ] **Collation empty states read as a participant's.** As an observer
  with no cohort rule, open the collation page: "You haven't been given
  anyone to observe in this review yet." With a rule on a draft session:
  "There are no results for you to see right now."

## Revisited POST addresses and the empty-cohort download (M10, M13)

- [ ] **Enter on a refused Submit's address lands on the form.** As a
  reviewer, press Submit with a required field empty. With the address
  bar showing `…/submit?page=…`, click into it and press Enter. You land
  back on the page you pressed Submit on, not an error page.
- [ ] **No download for an empty cohort.** As an observer whose cohort
  rule matches nobody, on an instrument released to observers as Raw,
  open the collation page. Row 3 reads "No one in your view takes part
  in this instrument, so there is nothing to download", with no
  Download CSV button.
