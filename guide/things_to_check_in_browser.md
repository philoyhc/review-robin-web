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

## Accounts toolbar (admin pages Item 1, rungs 1 and 2)

Sys Admin → Accounts, signed in as an admin, with a few accounts of each
kind (invite some; sign in once as a new address for an Unused one).

- [ ] **Two panes above the table.** Left: `Show:` and four chips,
  `Operators (N)`, `Admins (N)`, `No role (N)` and `Unused (N)`, the
  first two solid. Right: `Session role` and `Search` on one row,
  `Search` below. Compare the Reviewers page's toolbar.
- [ ] **A chip filters at once.** Clicking `Unused` reloads with those
  rows added; the counts don't change. Turning every chip off says "No
  accounts match the chips above." and keeps the toolbar.
- [ ] **Role and search wait for Search.** Pick `Owner`, type part of a
  name, press Search: only matching rows; `Clear` appears and drops both,
  keeping the chips. The search box offers emails and names as you type.
- [ ] **An action keeps the view.** With a search on, Admit an Unused
  account: the page comes back with the same search, the account
  selected, and the Operators chip on even if it was off.
- [ ] **Narrow window.** Below about 860px the two panes stack, with the
  chips wrapping rather than overflowing.

## Invite card half width, Overview stub (admin pages Item 3, rung 1)

Sys Admin → Accounts, signed in as a super-admin (the fake operator is one).

- [ ] **Side by side.** Invite by email on the left half, Overview on the
  right, the same height; below about
  800px they stack. Workspace users still spans the page beneath.
- [ ] **The role chip.** Under the email box, one row: a solid chip
  reading `Invite as operator` at its top-left, `Cancel` then `Invite`
  flush right; a click turns it to `Invite as sys-admin` and
  back, staying solid. Cancel (after typing an email) returns it to
  `Invite as operator`.
- [ ] **It still invites an admin.** Invite an address with the chip at
  `Invite as sys-admin`: the new row shows the Admin pill.
- [ ] **Shorter copy.** The card's line ends "they land on the operator
  lobby directly." with no mention of `/me`.

## Accounts typeahead reaches every account (admin pages Item 1 rulings)

Sys Admin → Accounts with more than 200 accounts under the chips that
are on. Locally, invite a few hundred by email, or sign in as many
fake-auth users; `tools/bench_roster_scale.py seed-accounts` makes them
too, but needs a local Postgres (`tools/README.md`). Turn on No role and
Unused if the accounts you made sit there.

- [ ] **Typeahead.** Type the start of an email late in the alphabet
  (`z…`): the suggestions show it within a moment, though the list the
  page opened with stopped well before it. Typing more narrows it. If
  the open dropdown only refreshes on the next keystroke, note it.

## Accounts row expander scaffold (admin pages Item 2, rung 1)

Sys Admin → Accounts, with a few operators and an unused account.

- [ ] **Several rows.** Ticking a second row keeps the first ticked; the
  header box ticks every row and shows a dash when only some are.
- [ ] **The expander.** A tinted bar opens under the last row ticked:
  "N of M selected", then only the controls that fit every selected
  row, grouped as the toolbar was (two operators who own nothing:
  "Operator:" Revoke, "Admin:" Promote, "|" Delete). The count, the
  "Yes, delete these" confirm, the labels and the buttons all sit on
  one line.
- [ ] **Other expanders.** The same confirm on the four roster pages
  (Reviewers, Reviewees, Relationships, Observers) sits level with its
  count too, not lower.

## Accounts row expander live (admin pages Item 2, rung 2)

Sys Admin → Accounts, with a few operators and an unused account.

- [ ] **No toolbar.** Nothing sits above the table but the chips and the
  filter strip; actions are only in the expander.
- [ ] **One click, several rows.** With Unused on, tick two operators who
  own no session, Revoke: both lose the Operator pill and move under
  Unused (or No role, if they have history), and the chips and search
  stay.
- [ ] **Delete's confirm.** Delete stays grey until "Yes, delete these"
  is ticked.
- [ ] **Refused whole.** Tick an unused account and a session owner,
  confirm, Delete: a banner says "Nothing changed: … owns sessions",
  naming the owner, and both rows are still there.

## Accounts Overview cut to two rows of pills (2026-10-14)

- [ ] **Just pills.** Overview shows two rows and nothing else:
  "N Operators · N Admins · N super-admins", then "N No role · N
  Unused", each number and label inside one blue pill, in the case
  written here (not the capitals other pills use). No links, no
  New / Unused-for-30-days / Sessions-with-one-owner lines.
- [ ] **Counts match the chips.** Each kind's number matches its chip
  in the Workspace users toolbar; with one configured super-admin who
  has an account the pill reads "1 super-admin".
- [ ] **Spacing.** The pills sit flush against the ` · ` on either
  side, and the two rows have a small gap between them; Invite and
  Overview stay level, stacking below about 800px.
