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

## Round 3's follow-ups (#PRNUM)

Round 3 (#3235–#3238) passed in the browser on 2026-10-24 but for the
first row below, which this PR fixes; the second is the PR's own.

- [ ] **A root-path sort cookie is expired, and the lobby is in its own
  order on that load.** With no lobby sort of your own (clear it, or
  check `document.cookie` holds no `rrw-sort-lobby`), run in the lobby's
  console
  `document.cookie = "rrw-sort-lobby=" + encodeURIComponent(JSON.stringify([{key: "name", dir: "desc"}])) + "; Path=/"`
  and reload: the page reloads itself once and lands newest first, not
  Name descending, and `document.cookie` holds no `rrw-sort-lobby`.
- [ ] **An archived session's Cancel is disabled.** On an archived
  session's Email Template page, Cancel is greyed out and not a link, on
  each of the Invitation, Reminder and Responses received tabs.
