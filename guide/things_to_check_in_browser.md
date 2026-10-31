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
  `https://cordware.nus.edu.sg/reviewrobin/`, live since 2026-10-31.
  The dev slot is dormant.
- **What they need.**
  - Rows 1 and 2: NUS IT changing the primary email of a test account
    in the tenant. Ask first, then work in this order: sign in, have IT
    change the email, send row 2's invite, sign in again.
  - Row 3: a second NUS account that has never signed in to Review
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
