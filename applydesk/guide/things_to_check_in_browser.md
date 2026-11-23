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


## Admin's layout (AD1U Item 1)

- [ ] **Admin lines up with the operator pages.** Go from an exercise's
  Home to Admin (*Accounts Management*): the bar, the title and the cards
  keep the 40 px left margin and run as wide as Home's, not a centred
  column. The same on *Exercises Diagnostics* and *System Status*.

## Owners and operators, and *Your role* (AD2O: #4144, #4145, #4146)

- [ ] **The card.** On an exercise's Home, the card reads *Owners and
  operators*, Owners first. As its only Owner, your row offers no *Step
  down* and says why; another operator's row offers *Make Owner*,
  *Transfer ownership* and *Remove*, the last two asking first.
- [ ] **Make Owner, then Step down.** Make a colleague an Owner: both rows
  say Owner. *Step down* on your row: you are an operator, they the Owner,
  and your row now offers only *Leave*.
- [ ] **Leave.** As an operator, *Leave* asks, then lands on the Lobby
  without that exercise.
- [ ] **Transfer.** *Transfer ownership* asks, then you are an operator and
  they the only Owner.
- [ ] **Your role.** The Lobby and the Archive show *Your role* (Owner or
  Operator) where *Created by* was; the Lobby sorts by it.
- [ ] **The panel.** Tick an exercise you only operate: *Purge and archive*
  and *Delete* are disabled and the note names it; untick it and they
  return.
- [ ] **Archived is read-only.** On an archived exercise's Home, the card's
  moves are refused with *Archived: restore it to change who runs it.*

## The Lobby wired, and the Archive (AD2B: #4139, #4140)

- [ ] **Sorting.** Click a header: the rows sort by it, its arrow shows the
  way; click again to flip it. Reload: the order stays.
- [ ] **Tags and the filter.** Click two tag chips: only exercises carrying
  both show; click *OR*: either. Type in the filter and press Enter: name,
  code or tag matches. *Clear* empties each.
- [ ] **The panel, one exercise.** Tick a row, change its name, code and
  tags, *Save*: it says *Saved.* A code another live exercise holds is
  refused. *Duplicate settings only* opens "Copy of …"'s Home.
- [ ] **The panel, several.** Tick two, type tags, *All tags to all*, then
  *Remove from all*. Press Enter in that Tags box: it does not post Save.
- [ ] **Archive and Restore.** *Purge and archive* moves an exercise to
  *Go to Archive*; *Restore* brings it back, unless another exercise has
  taken its code meanwhile.
- [ ] **Delete.** Without *Yes, delete* ticked it says so; ticked, it asks,
  then the exercise is gone from the Lobby, Admin's Diagnostics and `/me`.

## Details saved, and one way of writing dates (AD2B: #4137, #4138)

Re-seed first: AD2B adds a migration, and the seed now records each
sample's settings.

- [ ] **Details saves.** On RA-2027's Home, *Unlock* Details, change the
  description and the timezone, *Lock*: it says *Saved.* Reload: the
  change is still there.
- [ ] **A stale Lock is refused.** Open the same Home in two tabs. Save a
  change in one, then *Lock* a change in the other: it is refused, says
  to reload, and saves nothing.
- [ ] **A taken code is refused.** On the Graduate Travel Grant's Home,
  set the code to `ra-2027`: Lock is refused on the code field.
- [ ] **Dates read one way.** Home's timeline, Process's stage cards and
  a gate's *send* line write a range with its year once
  ("1–30 Sep 2026", "9 Nov – 4 Dec 2026"). On Process, change a stage's
  dates: its card's summary follows in the same words.

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

