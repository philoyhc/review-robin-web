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

## The preview's heading follows the name as typed (19Y Item 6)

- [ ] **The heading keeps up.** Unlock an instrument card and type a new
  name in Band 1: "Preview review instrument"'s heading shows it as you
  type (`#N: name` with several instruments). Cancel: the old name comes
  back (in Firefox too). Give a nameless instrument its first name: the
  same. On a session's only instrument with no name, typing the
  description changes the heading as you type.

## The Guide's screencaps and wording catch up (19Y Item 7)

- [ ] **The Guide shows the new screencaps.** Open `/guide` in light and
  dark: Create session, both roster cards and both Band 2 previews
  (unlocked, then locked) show the new images in the right theme, and
  the Band 2 text reads as in `Guide_6a.docx`; both Band 2 previews
  show the same instrument (`Guide_6b.docx`).
