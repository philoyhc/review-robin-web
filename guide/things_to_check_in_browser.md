# Things to check in a browser

Browser checks owed on merged changes that the test suite cannot settle:
layout, in-browser behavior and what a page shows. Every PR that owes one
adds a section here. Run them locally (`uvicorn`, fake auth). Tick a row
when it is checked; once every row in a section is ticked, delete the
section (git history keeps it), so this file lists only what is owed. A
section may point to upload files under `guide/browser_check_files/`;
delete them once no remaining section points to them.

**One run order covers every open section:**
`guide/browser_check_files/round_2/README.md`, with its upload files.
It names the rows it sets aside and why.

## Email dates in the session's zone (#2720)

- [ ] **The submitted time does too.** Preview the responses-received
  email for a reviewer who has submitted; `$submitted_at` reads in the
  session's zone. *Needs an Azure deployment; not checkable locally (author,
  2026-10-13).*

## A failing scheduled send no longer breaks Session Home (B20)

- [ ] **Session Home loads.** Nothing in the UI can force a send to
  fail, so this is a smoke check: open Session Home for a session with
  scheduled invites or reminders set and past due. It loads, and Admin →
  Sessions shows the audit log with either the fired events or, if
  something failed, one `session.scheduled_event_failed` row per
  failing trigger, however many times the page is reloaded.

## Zip all follows the other cards (D28)

- [ ] **Rehydrate still takes it.** Give an instrument the short label
  `responses`, then download Extract Setup's Zip all and this Zip all.
  Rehydrate both zips on the lobby: it accepts them.

## The /me fallback after sign-in (P2)

- [ ] **No "Go back" after the sign-in redirect.** On a deployment, open
  `/me/sessions/999999/results` signed out in a fresh tab: after the
  sign-in redirect, the error page shows "Go to your reviews" and no
  "Go back". *Needs a deployment; the local half was checked 2026-10-19.*

## The not-open page for a scheduled start (M3)

- [ ] **Scheduled to open.** A prepared session with a scheduled start
  and a help contact: its review link reads "This review is not
  currently open.", then "Scheduled to open: …" and the help contact.
  *(Draft and prepared without a schedule checked 2026-10-19.)*

## The sort banner keeps its line (O7)

- [ ] **With JavaScript off**, Save an instrument card with a sort spec
  the fallback refuses (e.g. a forged `sort_dir=sideways`): the banner
  reads "Could not save the sort order: A sort direction is not one of
  asc or desc."

## Column widths survive the page's own snapshot (O9)

- [ ] **Widths round-trip.** Unlock an instrument card, drag a preview
  column wider, Save, reload, then unlock and Save again without
  touching the columns: the widths are still the dragged ones.

## Operations pages and the lobby fire scheduled events (L4)

- [ ] **Without visiting Session Home.** Give a `validated` session a
  Start a minute or two ahead and wait for it to pass. Open the lobby
  (or Validate, Assignments, Invitations or Responses): the session
  reads Activated, and the audit log shows `session.activated` with
  `trigger=scheduled`. Repeat with a `draft` session: it logs
  `session.scheduled_activation_skipped` and clears Start.

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

## Relationships' Delete all names the group answers (19X Item 3)

- [ ] **One tick, no banner.** On Relationships, with group answers
  saved on an instrument grouped by a relationship tag, open the Danger
  Zone: the tick reads "Yes, delete the existing … relationships and the
  N reviewer responses on the groups they form". Tick it and press
  Delete all: everything goes, with no banner. On a session with no
  such answers, the tick names only the relationships.
