# Things to check in a browser

Browser checks owed on merged changes that the test suite cannot settle:
layout, in-browser behavior and what a page shows. Every PR that owes one
adds a section here. Run them locally (`uvicorn`, fake auth). Tick a row
when it is checked; once every row in a section is ticked, delete the
section (git history keeps it), so this file lists only what is owed. A
section may point to upload files under `guide/browser_check_files/`;
delete them once no remaining section points to them.

**Some rows need more than a local run:** an Azure deployment (#2720,
P5) or the Rehydrate round trip (D28).

## Email dates in the session's zone (#2720)

- [ ] **The submitted time does too.** Preview the responses-received
  email for a reviewer who has submitted; `$submitted_at` reads in the
  session's zone. *Needs an Azure deployment; not checkable locally (author,
  2026-10-13).*

## Zip all follows the other cards (D28)

- [ ] **Rehydrate still takes it.** Give an instrument the short label
  `responses`, then download Extract Setup's Zip all and this Zip all.
  Rehydrate both zips on the lobby: it accepts them.

## Sign-in keeps its row when the email changes (P5)

These need real Easy Auth claims, so they are checks for an Azure
deployment, not a local run.

- **What they prove.** A real sign-in carries the account's directory
  principal id. The first sign-in records it on the user's row, and
  later sign-ins find the row by that id before the email
  (`app/services/users.py`). So an address change keeps the row. Fake
  auth never records one, which is why a local run can't show it.
- **Where.** The institutional deployment,
  `https://<institutional host>/reviewrobin/`, live since 2026-10-31.
  The dev slot is dormant.
- **What they need.**
  - Rows 1 and 2: the institution's IT changing the primary email of a test account
    in the tenant. Ask first, then work in this order: sign in, have IT
    change the email, send row 2's invite, sign in again.
  - Row 3: a second institutional account that has never signed in to Review
    Robin.
- **Where to look.** The event names below are in the sys-admin audit
  log.

- [ ] **A changed email keeps the account.** Sign in as an operator, have
  the tenant change that account's primary email, and sign in again:
  the same sessions, flags and SMTP settings are there, and the
  sys-admin audit log shows `workspace.user_email_changed`.
- [ ] **An invite for the new address folds in.** Before that sign-in,
  invite the new address as an operator on Accounts Management: after
  it, there is one account, an operator, and the log shows
  `workspace.user_absorbed`.
- [ ] **An invited user's first sign-in binds them.** Invite a new
  address, then sign in as it: the log shows
  `workspace.user_principal_recorded`.

## Where display fields sit (20M)

Run order and files: `guide/browser_check_files/20m/`. Instrument 1 is
individual, Instrument 2 grouped by Group AND Team.

**Profile beside the name (Instrument 1)**

- [ ] **Band 3 pins it.** Profile's row sits right after Email with no
  ▲ ▼; the other rows still reorder around it.
- [ ] **No column, on the preview or the review page.** Kenji Russo's
  name is followed by **View**, which opens his link; Aisha Bello's by a
  muted ••• whose hover reads `Room 4B`; Diego Marsh's by nothing.
  Neither page has a Profile column.

**Individual layouts (Instrument 1)**

- [ ] **The chip.** Right of Band 3's *Display fields* header, it
  reads *Across* and cycles *Stacked* → *Joined* → *Across*, and it
  fits there without widening the column. The *Display fields* heading
  looks as it did before.
- [ ] **Stacked.** Tutor, Group and Team leave the preview's columns
  and sit under the sample email, one muted `Label:` per line. Save,
  reload: still *Stacked*. On the review page, Hana Ito shows Tutor and
  Group lines and no Team line.
- [ ] **Joined.** The values sit on one line under the email,
  comma-separated: Hana Ito reads `Zoe Tan, TW01`, with no empty
  slot.
- [ ] **Across is as before.** Back on *Across*, the three columns
  return on both pages.
- [ ] **A sort on a hidden field goes quiet.** On *Across*, set Tutor
  descending with its badge and Save: the review page lists Zoe Tan's
  reviewees first. Switch to *Stacked* and Save: the rows no longer
  follow Tutor, and a Name sort still orders them.
- [ ] **A width on a hidden column.** On *Across*, drag the Tutor
  column wider in the preview and Save, then switch to *Stacked* and
  Save. The review page's table still lays out sensibly, with no gap
  where Tutor was and no squeezed columns.

**Group layouts (Instrument 2)**

- [ ] **The chip.** It reads *Joined* and cycles *Joined* ↔ *Stacked*
  only; there is no *Across*.
- [ ] **Joined.** Each group row shows the member names first, then one
  line of tags below them, not bold: for example `Zoe Tan, TW01, Team 1`
  under Kenji Russo and Wen Novak.
- [ ] **Stacked.** Names first, then one muted `Label: value` line per
  tag, styled like an individual row's. Hana Ito's group has no Team
  line.

**Group order on the review page (Instrument 2)**

- [ ] **Rows follow the shown tags.** With Tutor, Group, Team in that
  order: Ahmed Shah's two TW45 groups (Team 1, then Team 2), then Zoe
  Tan's: Hana Ito's group (no Team) first, then Team 1, then Team 2.
- [ ] **Reordering moves them.** Move Group above Tutor in Band 3 and
  Save: the TW01 groups now come before the TW45 groups.
- [ ] **Descending reverses it.** Set the Group header descending:
  the order reverses, and Hana Ito's group is now last of the TW01
  rows.
