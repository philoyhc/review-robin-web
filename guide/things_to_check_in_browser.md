# Things to check in a browser

Browser checks owed on merged changes that the test suite cannot settle:
layout, in-browser behavior and what a page shows. Every PR that owes one
adds a section here. Run them locally (`uvicorn`, fake auth). Tick a row
when it is checked; once every row in a section is ticked, delete the
section (git history keeps it), so this file lists only what is owed. A
section may point to upload files under `guide/browser_check_files/`;
delete them once no remaining section points to them.

**Some rows need more than a local run:** an Azure deployment (#2720,
P2's signed-out row, P5) or the Rehydrate round trip (D28).

## Email dates in the session's zone (#2720)

- [ ] **The submitted time does too.** Preview the responses-received
  email for a reviewer who has submitted; `$submitted_at` reads in the
  session's zone. *Needs an Azure deployment; not checkable locally (author,
  2026-10-13).*

## Zip all follows the other cards (D28)

- [ ] **Rehydrate still takes it.** Give an instrument the short label
  `responses`, then download Extract Setup's Zip all and this Zip all.
  Rehydrate both zips on the lobby: it accepts them.

## The /me fallback after sign-in (P2)

- [ ] **No "Go back" after the sign-in redirect.** On a deployment, open
  `/me/sessions/999999/results` signed out in a fresh tab: after the
  sign-in redirect, the error page shows "Go to your reviews" and no
  "Go back". *Needs a deployment; the local half was checked 2026-10-19.*

## Sign-in keeps its row when the email changes (P5)

These need real Easy Auth claims, so they are checks for an Azure
deployment, not a local run.

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

## An instrument's intro picks its layout (19Y Item 1)

- [ ] **The Guide's screencap.** Reshoot
  `app/web/static/guide/instrument-card-preview.png` and `-dark` with the
  new default and the chip, and update their alt text in
  `app/web/templates/guide.html` to say the help texts sit as rows in
  the heading card on the left and the visibility table on the right
  (Item 2: rows, not help cards).

