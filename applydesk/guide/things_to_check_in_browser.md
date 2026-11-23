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

## Run order (2026-11-23)

The sections below, grouped by the setup each needs, so each setup is
made once. Tick rows in their own sections as they pass; this section goes
when they are all ticked.

1. **Seeded, as the super-admin** (`.env` as `docs/local_setup.md`; then
   `alembic -c applydesk/alembic.ini upgrade head` and
   `python -m applydesk.seed`). Most rows:
   - *Admin's layout*; *Owners on record*; *Details saved, and one way of
     writing dates* (RA-2027, the Graduate Travel Grant).
   - *The Lobby wired, and the Archive*: Delete last, on a scratch
     exercise made with *New exercise*.
   - *Process: Candidates, the form's moves, published stages and outcome
     values*, on RA-2027 and the samples it names.
   - *Home's timeline*, *Hovers, tables and empty states*: a pass of
     every operator page at 1300px and 390px, light and dark, in one go.
   - *Owners and operators*, **Your role**, **The panel** and **Archived is
     read-only**: these need no second person.
2. **A second person.** Restart with `FAKE_AUTH_EMAIL=jane.tan@example.edu`
   and `FAKE_AUTH_NAME=Jane Tan` and load the Lobby once (Jane has now
   signed in); restart as Local Operator. On Accounts Management, add
   `jane.tan@example.edu` as an operator, then on RA-2027's Home, *Add
   operator* Jane. Then:
   - *Owners and operators*: **The card**, **Make Owner, then Step down**,
     **Leave**, **Transfer**. Do Transfer on a scratch exercise, since it
     makes Jane the only Owner.
   - *Admins and adopting*: **Promote and Demote**, **Revoke skips an
     Admin** (on Jane).
3. **Not the super-admin.** With Local Operator promoted to Admin in
   sitting 2, restart with `FAKE_AUTH_SUPER_ADMIN=false`: **An Admin's
   view**.
4. **A fresh database, unseeded.** Stop the server, move `applydesk.db`
   aside, run `alembic -c applydesk/alembic.ini upgrade head` only:
   **Unseeded**.
5. **Seeded for someone else.** On that database, run
   `python -m applydesk.seed --owner pat@example.edu`: **Manage adopts,
   asking first**. Afterwards, restore the moved `applydesk.db` (or
   re-seed) for everyday use.

## Process: Candidates, the form's moves, published stages and outcome values (AD2C: #4158, #4161)

- [ ] **The form's move on Home.** A draft exercise's *Open form* is
  disabled and says why. On `r6tm4kq9wz` (form open), *Close form* closes
  it and Home says so. Publish a draft exercise's first stage on Process,
  save, and its Home's *Open form* is enabled.
- [ ] **Candidates.** On a stage holding Candidates, the search finds
  someone and *Add* lists them; *Remove* takes them off (two in a row
  both go); a CSV adds its good rows and lists the rest. None of it marks
  Process unsaved. The Outline names the item *Candidates*.
- [ ] **Candidates moved and replicated.** *Take Candidates off this
  stage*, then *+ Candidates* on another draft stage: the list is as it
  stands. *Replicate* a stage holding Candidates: the copy has none.
- [ ] **Published stages.** Extend a published stage's *Ends* and save: it
  saves. *Revert to draft* asks for a reason; after saving, its name and
  start are editable.
- [ ] **Outcome values.** Values show one row each with *Remove* and
  *+ Value*. Rename one a rule names: the rule line and any later rule
  reading it follow, with no warning. Swap two labels (each typed into the
  other's row): the decisions swap with them. Save and reload: values and
  rules are as left.


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

