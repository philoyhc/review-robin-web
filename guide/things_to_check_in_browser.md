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

**Apply Desk's checks are here too**, under "Apply Desk" at the end, at
`http://127.0.0.1:8000/applydesk/` on the same local run; its plans and
`applydesk/guide/todo_master.md` point here rather than keeping their own
(consolidated 2026-11-22). Most need the samples loaded first:
`alembic -c applydesk/alembic.ini upgrade head`, then
`python -m applydesk.seed`.

**Residential's walkthroughs stay in their own files**, since they are also
scripts for feedback sessions, each deleted when its item closes:
`residentialapps/guide/1B_browser_checks.md`,
`residentialapps/guide/1C_browser_checks.md` and
`residentialapps/guide/1D_browser_checks.md`.

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

---

# Apply Desk

## Admins and adopting an exercise (AD2M: #4131, #4132)

- [ ] **Promote and Demote.** On Admin → Accounts Management, tick
  someone who has signed in and click *Promote to Admin*: the row's
  *Admin* reads *Admin* and they move under the *Admins* chip. Tick them
  again and click *Demote from Admin*: it asks first, then they read *no*
  and stay an operator.
- [ ] **Revoke skips an Admin.** Tick an Admin and click *Revoke*: the
  status line counts them as skipped.
- [ ] **An Admin's view.** With `FAKE_AUTH_SUPER_ADMIN=false` and Local
  Operator promoted: the account menu reads *admin*, the Admin pages
  open, and the bulk bar has no *Promote* or *Demote*.
- [ ] **Manage adopts, asking first.** On a fresh database seeded with
  `python -m applydesk.seed --owner pat@example.edu`, the Lobby lists no
  sample. On Admin → Exercises Diagnostics, *Manage* on one asks first;
  after it the exercise's Home opens, the Lobby lists it, and *Owners*
  reads `pat@example.edu, Local Operator`.
- [ ] **Unseeded.** With no seed run, *Manage* says the exercise is not in
  the database yet and names the command.

## Owners on record, and the super-admin's own row (#4128, #4129)

- [ ] **Owners column and Created by.** After the seed, Exercises
  Diagnostics' *Owners* and the Lobby's *Created by* read Local Operator
  for every sample, the Lobby's with its tooltip.
- [ ] **Your own row.** On Accounts Management, Local Operator's *(self)*
  row reads Operator *yes*, with its tooltip, and the workspace Unit when
  `CORDWARE_INSTITUTION_NAME` is set.

## Home's timeline and the copy sweep (AD1S: #4101, #4102)

Moved from `applydesk/guide/todo_master.md` (deferred 2026-11-21).

- [ ] **The timeline.** Exercise Home's timeline in both layouts, at
  1300px and 390px, and the applicant's `/me` exercise page.
- [ ] **The copy sweep.** Read the pages #4102 touched; restore any cut
  line still needed (`applydesk/guide/removed_help_lines.md`).

## Hovers, tables and empty states (AD1R: #4096, #4097, #4098)

Moved from `applydesk/guide/todo_master.md` (deferred 2026-11-21).
Tweaks it finds land as their own PRs.

- [ ] **Hovers and tables** on every operator page.
- [ ] **The blank draft's empty states** (*Graduate Travel Grant 2027*).
- [ ] **Widths and themes.** Extract, Dossiers, Panels, Form, Home and the
  gate page at 1300px and 390px, light and dark.

