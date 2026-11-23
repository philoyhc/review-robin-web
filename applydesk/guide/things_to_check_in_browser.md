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
   - Run headless on 2026-11-23 (`041d436d6`): Admin's layout, Owners on
     record and Details saved passed whole and are gone; the rows ticked
     below passed too. Left for a person: *The panel, several* (Enter in
     its Tags box, then *All tags to all* and *Remove from all*).
   - *Process: Candidates, the form's moves, published stages and outcome
     values*, on RA-2027 and the samples it names.
   - *Home's timeline*, *Hovers, tables and empty states*: a pass of
     every operator page at 1300px and 390px, light and dark, in one go.
   - *Owners and operators*, **Your role**, **The panel** and **Archived is
     read-only**: these need no second person.
2. **A second person.** As Local Operator, on Accounts Management, add
   `jane.tan@example.edu` (Jane Tan, from the fake directory) as an
   operator. Then sign in as her once: restart with
   `FAKE_AUTH_EMAIL=jane.tan@example.edu`, `FAKE_AUTH_NAME=Jane Tan` and
   `FAKE_AUTH_PRINCIPAL_ID=11111111-1111-4111-8111-111111111111` (her
   fake-directory ID; people are matched by tenant and that ID, not by
   address), and load the Lobby. Restart as Local Operator, with
   `FAKE_AUTH_PRINCIPAL_ID` back to `local-dev`, and on RA-2027's Home
   *Add operator* Jane. Then:
   - *Owners and operators*: **The card**, **Make Owner, then Step down**,
     **Leave**, **Transfer**. Do Transfer on a scratch exercise, since it
     makes Jane the only Owner.
   - *Admins and adopting*: *Promote to Admin* on Jane (the first half of
     **Promote and Demote**), then **Revoke skips an Admin**. Leave her an
     Admin for sitting 3.
3. **An Admin, not the super-admin.** Local Operator cannot promote its own
   row, so the Admin is Jane: restart as Jane (her three values from
   sitting 2) with `FAKE_AUTH_SUPER_ADMIN=false`: **An Admin's view**, read
   as Jane rather than Local Operator. Then restart as Local Operator
   (`local-dev`, `FAKE_AUTH_SUPER_ADMIN=true`) and *Demote from Admin* on
   Jane, the second half of **Promote and Demote**.
4. **A fresh database, unseeded.** Stop the server (super-admin still on:
   a fresh database keeps no Admin role, and Exercises Diagnostics needs
   one), move `applydesk.db` aside,
   run `alembic -c applydesk/alembic.ini upgrade head` only, and start the
   server: **Unseeded**.
5. **Seeded for someone else.** On that database, run
   `python -m applydesk.seed --owner pat@example.edu`: **Manage adopts,
   asking first**. Afterwards, restore the moved `applydesk.db` (or
   re-seed) for everyday use.

## Process: Candidates, the form's moves, published stages and outcome values (AD2C: #4158, #4161)

- [x] **The form's move on Home.** A draft exercise's *Open form* is
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
- [x] **Your role.** The Lobby and the Archive show *Your role* (Owner or
  Operator) where *Created by* was; the Lobby sorts by it.
- [ ] **The panel.** Tick an exercise you only operate: *Purge and archive*
  and *Delete* are disabled and the note names it; untick it and they
  return.
- [ ] **Archived is read-only.** On an archived exercise's Home, the card's
  moves are refused with *Archived: restore it to change who runs it.*

## The Lobby wired, and the Archive (AD2B: #4139, #4140)

- [x] **Sorting.** Click a header: the rows sort by it, its arrow shows the
  way; click again to flip it. Reload: the order stays.
- [x] **Tags and the filter.** Click two tag chips: only exercises carrying
  both show; click *OR*: either. Type in the filter and press Enter: name,
  code or tag matches. *Clear* empties each.
- [x] **The panel, one exercise.** Tick a row, change its name, code and
  tags, *Save*: it says *Saved.* A code another live exercise holds is
  refused. *Duplicate settings only* opens "Copy of …"'s Home.
- [ ] **The panel, several.** Tick two, type tags, *All tags to all*, then
  *Remove from all*. Press Enter in that Tags box: it does not post Save.
- [x] **Archive and Restore.** *Purge and archive* moves an exercise to
  *Go to Archive*; *Restore* brings it back, unless another exercise has
  taken its code meanwhile.
- [x] **Delete.** Without *Yes, delete* ticked it says so; ticked, it asks,
  then the exercise is gone from the Lobby, Admin's Diagnostics and `/me`.

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

