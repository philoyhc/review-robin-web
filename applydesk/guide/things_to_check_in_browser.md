# Things to check in a browser: Apply Desk

Browser checks owed on merged Apply Desk changes that the test suite cannot
settle: layout, in-browser behavior and what a page shows. Every PR that
owes one adds a section here, as Review Robin's register does
(`guide/things_to_check_in_browser.md`). Tick a row when it is checked;
once every row in a section is ticked, delete the section, so this file
lists only what is owed.

Run them locally at `http://127.0.0.1:8000/applydesk/` (`uvicorn`, fake
auth). Most need the samples loaded first:
`alembic -c applydesk/alembic.ini upgrade head`, then
`python -m applydesk.seed`.

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

