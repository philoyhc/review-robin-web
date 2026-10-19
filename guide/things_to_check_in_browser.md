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

## Sessions and answers are named without database IDs (19V, #3126–#3130)

Needs `alembic upgrade head` first (three migrations). A database from
before them works, but its sessions take new addresses.

- [x] **Every address carries the public ID.** The lobby's links,
  Session Home and each of its tabs, `/me`, the review page, Submit and
  Summary all show a 10-character ID of digits and lower-case letters
  where the session's number was.
- [ ] **The lobby still acts on a session.** The row expander's Save and
  Duplicate, and the bulk panel's tag and archive actions, each act on
  the rows chosen. *(2026-10-19: all but the bulk archive checked.)*
- [ ] **A sort is remembered per session.** Sort a Setup table and a
  review page, then reload: each keeps its sort. (A sort remembered
  under the old numeric address is forgotten once, which a fresh
  database cannot show.)
- [ ] **Extract data.** Each card's download works, and a chip turned
  off stays off after a reload.
- [x] **Sys Admin → Sessions.** Outbox, Audit log and Adopt each open the
  session they name.
- [x] **An old address answers 404.** `/operator/sessions/1` and
  `/me/sessions/1/1` show the error page, with no redirect.
- [x] **Back links.** About and Settings, opened from a session page,
  link back to that page.
- [x] **Answers are named by row, not by assignment.** In the review
  page's source the answer boxes are named `response[1][…]`,
  `response[2][…]` and so on, beside a hidden `page_digest`.
- [ ] **Save after a sort.** Sort a column, type answers and Save:
  after a reload each answer is on the row it was typed on.
- [x] **A stale tab is refused.** Open a review page in two tabs. As the
  operator, Revert, Prepare, inactivate one of that reviewer's rows on
  Assignments, and Activate. Type in the stale tab and Save: "This page
  changed after you opened it, so your last changes weren't saved.
  Check the answers below and enter them again.", with what you typed
  listed under it.
- [ ] **A group answer is the group's.** Save one rating on a group row
  and reload: it shows on the row, and the responses CSV holds it on one
  row naming every member, e.g. "Team A (Dev Patel, Erin Walsh, Local
  Operator)".
- [ ] **Sort keys name no ID** (19V Item 4). In the review page's
  source, each table's `data-rrw-sortable` ends with the instrument's
  place in the session (`-1`, `-2`), and the headers' `data-sort-key`
  read `display:reviewee.tag_1`-style sources and `response:` plus the
  field key, never a number. A sort set before this change is forgotten
  once; a new one is kept across a reload.
- [ ] **The observer's CSV names the instrument by its number** (19V
  Item 3; needs `alembic upgrade head` again). On the collation page,
  each Download CSV link ends `/instruments/<n>.csv`, where n is the
  instrument's place in the session (1, 2, …), not its database ID.
  Change n in the address to one the session doesn't have, or to `abc`:
  the error page. *(2026-10-19: the link and `9.csv` checked; `abc` not
  yet.)*

## Quick Setup on a fresh session takes the files as Create does (S4, narrowed)

- [ ] **No question about the untouched default.** Create a session
  with nothing staged; on Session Home's Quick Setup choose reviewers,
  reviewees, relationships and a settings file, tick the replace box,
  Submit. Nothing asks about `Instrument_1`; the file's instruments
  replace it.
- [ ] **A default you changed still asks.** On another fresh session,
  give `Instrument_1` a short label on the Instruments page, then do
  the same: the red banner names it, and the tick applies the file.

## Email dates in the session's zone (#2720)

- [x] **The deadline reads in the session's zone.** On a session whose
  display zone is not UTC (Singapore, say) with a 17:00 deadline, preview
  the invitation email. `$deadline` should read 17:00, not 09:00.
- [ ] **The submitted time does too.** Preview the responses-received
  email for a reviewer who has submitted; `$submitted_at` reads in the
  same zone. *Needs an Azure deployment; not checkable locally (author,
  2026-10-13).*

## A failing scheduled send no longer breaks Session Home (B20)

- [ ] **Session Home loads.** Nothing in the UI can force a send to
  fail, so this is a smoke check: open Session Home for a session with
  scheduled invites or reminders set and past due. It loads, and Admin →
  Sessions shows the audit log with either the fired events or, if
  something failed, one `session.scheduled_event_failed` row per
  failing trigger, however many times the page is reloaded.

## Zip all follows the other cards (D28)

- [x] **Card order.** On Extract data, the left column holds Reviewer
  response metadata above Reviewee response metadata. The right column
  holds By instrument above Extract all data. The intro reads "Use
  **Zip all** to download a complete set of response data, plus
  whichever files are selected below, as each card configures them."
- [x] **Same files as the cards.** On By instrument, turn off one
  instrument and Include metadata. On Reviewer response metadata, cycle
  Self-review to Exclude. Download each card's own file, then the intro's
  Zip all. The zip holds `…_responses.csv` and the same files under the
  same names, and each opens identical to its card's download.
- [x] **Chips leave cards out.** Turn off the intro's Reviewee response
  metadata and Data shaper chips. Zip all no longer holds the reviewee
  metadata file or any shape files. No stats or `…_instrument_1.csv`
  files appear in any case.
- [ ] **Rehydrate still takes it.** Give an instrument the short label
  `responses`, then download Extract Setup's Zip all and this Zip all.
  Rehydrate both zips on the lobby: it accepts them.

## The /me fallback: error page link and empty dashboard (P2)

- [x] **The error page always has a way out.** Open a bookmark-style URL
  for a session you're not on, e.g. `/me/sessions/999999/results`, in a
  new tab. The page shows "Go to your reviews" and no "Go back"; the
  link lands on `/me`.
- [ ] **"Go back" appears after an in-app page.** Click through to the
  same URL from another page of the app in the same tab. "Go back" shows
  beside "Go to your reviews" and returns to that page. Both links sit
  centered under the message. Ctrl-click (open in new tab) the same link
  instead: the new tab shows "Go back" too, and it works. On a
  deployment, open the URL signed out in a fresh tab: after the sign-in
  redirect, no "Go back" shows. *(Local half checked 2026-10-19; the
  signed-out half needs a deployment.)*
- [x] **The empty dashboard.** Signed in as someone with no role, `/me`
  reads "You're signed in as <your address> but there's nothing here
  for you right now.", then who to contact, and links to About.

## `/me` status, the not-open page, archived sessions (M3, M4, M6, M7)

- [ ] **Status labels.** On `/me`, rows read "Not open yet" (draft or
  prepared), "Open" (Activated, before the deadline), "Closed" or
  "Available" after it. Archived sessions are not listed (see "Archived
  sessions are off limits" below). There are no "View responses" or
  "Until" columns. *(2026-10-19: Not open yet, Open, Available and the
  columns checked; Closed and archived not yet.)*
- [x] **Available.** As an observer on a closed session with a release
  window open and Band 3 granting observers, the row reads "Available".
  As a reviewer past the deadline who saved an answer, likewise.
- [x] **Nothing assigned.** A reviewer whose assignments are all
  excluded reads "Nothing assigned to you", not "0/0".
- [x] **Start after a revert.** Revert an Activated session to draft:
  its row's Start goes back to "—".
- [ ] **Not open page.** Open a draft and a prepared session's review
  link: each reads "This review is not currently open." A prepared
  session with a scheduled start shows "Scheduled to open"; set a help
  contact and it shows on both.
- [ ] **Archived is off limits.** On an archived session, the summary,
  its CSV and an observer's collation page each show the error page.

## Band 1 rules and the Settings import refuse what the engine rejects (S2, E1)

- [ ] **A refused rule stored earlier shows the banner.** Only a rule
  stored before this change can still pair two pair-context tags (none
  should exist outside a test). If one does, its card loads with the rule
  as stored, and Save shows a banner beginning "This assignment rule
  can't be used" and stores nothing.
- [ ] **A cross-side rule still saves.** Change the operand to a
  reviewer tag and Save: it saves, and a reload shows the rule.
- [ ] **A bad Settings file is refused by name.** Export the session's
  Settings CSV, change one `session_rule_sets[1].rules_json` cell to
  `[{"kind": "NOPE"}]`, and import it. The import is refused, the error
  names `rules_json`, and Instruments, Assignments and Validate all still
  open.

## The Settings import refuses an offset the details card refuses (L1)

- [ ] **A bad reminder offset is refused.** Export a session's
  settings, set `session.reminder_offsets` to `-P99999999999D` (or
  `-P30D`, past the 10-day cap), and import it: the import is refused
  with the error on `session.reminder_offsets`, nothing changes, and
  Session Home still loads.
- [ ] **An old schedule still imports.** Import the settings of a
  session whose End has passed, reminders included: it applies, since
  only the lead-time floor is waived.

## Lobby and Archived Select all follows the filter (O1)

- [ ] **Select all ticks only what is shown.** On the lobby, filter to
  a few sessions (a tag chip or the filter box), then tick Select all:
  only the rows shown are ticked, and the bulk panel counts them alone.
  Clear the filter: the other rows are unticked and the header reads
  partial. Same on Archived.
- [ ] **Hiding a ticked row unticks it.** Tick a session, then filter it
  out: it is no longer selected, and the panel drops it.

## An instrument's response-field Save un-validates the session (S1)

- [ ] **A changed field demotes.** Validate a session, then on
  Instruments rename a response field (or delete one) and Save: the
  session is back in draft, and the audit log has an
  `instrument.response_fields_saved` row naming the field.
- [ ] **An unchanged Save does not.** Validate again and Save the card
  without editing anything: the session stays validated and no new row
  is logged.

## Downloads keep a session code's own characters (R2)

- [ ] **A code past ASCII downloads.** Create a session with the code
  `Café-日本`, then on Extract data download its Reviewers CSV and the
  setup card's Zip all: both download (no error page), and the saved
  files are named `Café-日本_reviewers.csv` and `Café-日本_setup.zip`.

## A group that gains a member is cleared; one that only shrinks keeps its answer

- [ ] **A merge clears, a split keeps.** On a session back in draft with
  answers saved on a `Group using tags` instrument, remove a boundary
  tag so two answered groups merge, and Save (ticking `Yes, clear them`
  when asked, below): the merged group shows no answer, and the audit log's `instrument.group_boundary_updated` row
  counts `defuncted_group_responses`. Add a boundary tag that splits a
  group: both halves still show its answer.
- [x] **A tag edit clears only the group joined.** Edit one reviewee's
  team tag to another answered team: that team shows unanswered, and
  the team they left keeps its answer.
- [x] **Prepare asks before clearing a joined group.** Add a reviewee
  to an answered team and click `Prepare session`: the card's banner
  reads "Preparing will delete N saved responses" with a line that
  they are "on groups it adds members to". `Regenerate & prepare` then
  shows that team unanswered; a team nobody joined keeps its answer.
- [x] **Deleting a reviewee keeps their group's answer.** Delete one
  member of an answered team on Reviewees: the members who remain still
  show the team's answer.

## The Instrument card asks before its Save clears group answers

- [ ] **A merge is refused with the count.** On a draft session with
  answers on a `Group using tags` instrument, remove a boundary tag so
  two answered groups merge, and Save: the card stays unlocked with your
  edits, and its red banner reads "This change clears N saved responses
  on groups whose members it changes." above an unticked
  `Yes, clear them`. Reload: nothing was saved.
- [ ] **Ticked, the same Save goes through.** Repeat, tick
  `Yes, clear them` and Save again: the banner goes, and the merged
  group shows no answer.
- [ ] **A split or an unchanged Save never asks.** Add a boundary tag
  that splits a group, or Save the card unedited: no banner, and every
  answer stays.

## Error banners show only fixed copy (O7)

- [ ] **Workflow failures still say why.** Prepare a session whose setup
  has a validation error: the Workflow card reads "Prepare session failed
  at the Validate setup." over "Validation reported errors. The Validate
  page lists them." (the count is gone from this line).
- [ ] **A forged link adds nothing.** Open Session Home with
  `?super_status=failed&super_button=activate&super_step=activate&super_error=Call+us`,
  then with `?owners_error=Call+us`: the first shows only the headline,
  the second no Owners banner, and "Call us" appears nowhere.
- [ ] **The sort banner keeps its line.** With JavaScript off, Save an
  instrument card with a sort spec the fallback refuses (e.g. a forged
  `sort_dir=sideways`): the banner reads "Could not save the sort
  order: A sort direction is not one of asc or desc."

## Column widths survive the page's own snapshot (O9)

- [ ] **Widths round-trip.** Unlock an instrument card, drag a preview
  column wider, Save, reload, then unlock and Save again without
  touching the columns: the widths are still the dragged ones.

## Purge rosters takes observers too (L7)

- [ ] **Observers are gone.** On a session with observers, Purge and
  archive with `Rosters` ticked, then Unarchive: the Observers page has
  no rows.

## A timezone change keeps the instants (L8)

- [ ] **Create converts every box.** On New Session fill Start, End and
  both Release responses boxes, then change Timezone: every box shows
  the same moment in the new zone. Create, and Session Home shows those
  moments.
- [ ] **Session Home converts too.** Unlock the details card on a
  session with all four dates set, change Timezone and Save without
  touching the dates: the instants are unchanged (the lobby and the
  audit log's UTC view agree).
- [x] **An edit after the change reads in the new zone.** Change
  Timezone, then type a new End and Save: End is that wall-clock time
  in the new zone.

## The Self review toggle survives Prepare (E3)

- [ ] **Off stays off.** On an instrument whose rule produces
  self-review pairs, turn its Self review toggle off on the Assignments
  page, then edit a roster row (any field) and run Prepare: the
  instrument's self-review rows are still excluded and the chip still
  reads off. Another instrument's toggle is unaffected.
- [ ] **New rows follow the instrument.** With the toggle off, add a
  reviewer who reviews themselves and Prepare: the new self-review row
  arrives excluded.
- [ ] **Carried along.** Duplicate the session, and Replicate the
  instrument: both copies keep the toggle off. Export the Settings CSV
  and find `instruments[n].self_reviews_active` = `false`.

## A change after Submit needs a new Submit (R1, R7)

- [ ] **A changed answer un-submits it.** As a reviewer, fill a rating
  and a comment and Submit. Change the comment and Save: the page pill
  reads `complete`, the session pill "Saved but not submitted", and
  the operator's Invitations row `in progress`. Submit again: all three
  read submitted.
- [ ] **A blanked answer un-submits the rest.** After Submit, empty the
  comment and Save: the same three readings as above. So does changing
  the comment, saving, and then emptying it in a second Save.
- [ ] **Re-saving unchanged keeps it.** After Submit, press Save
  without editing: everything still reads submitted.
- [x] **No answer is not started.** On an instrument with nothing
  required, leave a row blank: its pill reads `not started`, as the
  dashboard does.

## Archive, Duplicate's trail, scheduled events off Home, response versions (L5, P2, L4, R6)

- [ ] **Operations pages and the lobby fire scheduled events (L4).**
  Give a `validated` session a Start a minute or two ahead and wait
  for it to pass. Without visiting Session Home, open the lobby (or
  Validate, Assignments, Invitations or Responses): the session reads
  Activated, and the audit log shows `session.activated` with
  `trigger=scheduled`. Repeat with a `draft` session: it logs
  `session.scheduled_activation_skipped` and clears Start.
- [x] **Duplicate leaves a trace on the original (P2).** As a non-owner
  sys-admin, Duplicate someone else's session from the lobby: the
  original's audit log lists `session.duplicated` naming you and the
  new code.
- [ ] **Archive closes accepting (L5).** Archive an Activated session
  (only a direct POST to `/workflow/archive` reaches this), then
  Unarchive: the reviewer surface stays read-only and the Instruments
  page shows nothing accepting.
- [ ] **Versions count changes (R6).** In `responses.csv`, `Version`
  goes up and `SavedAt` moves only after a reviewer saves a changed
  answer; a re-save of the same value leaves both.

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

## The Settings import names what it deletes; refused uploads re-render (S4, O7)

- [ ] **Deletes are named first (S4).** On a draft session with two
  instruments, upload a Settings CSV naming only one through Quick
  Setup Submit with the replace box ticked: the 422 banner reads
  "Nothing was imported. This settings file deletes 1 instrument…",
  lists its label, and offers "Yes, delete it." Choose the file
  again, tick both boxes and Submit: it applies and that instrument is
  gone. A file naming every instrument applies without asking.
- [ ] **A refused upload stays on Home (O7).** Upload a bad roster or
  Settings file on an existing session: the page re-renders with the
  banner and the file's lines, scrolled to the banner, and the address
  bar reads the session's Home path. Unlock, Cancel and a reload stay
  on Home.
- [ ] **No text from a link.** Open Home with
  `?quick_setup_error=settings&quick_setup_reason=parse&quick_setup_detail=hello`:
  no banner.
- [ ] **New session (O7).** Stage a bad file on New session: you land
  on the new session's Home with the fixed "…was refused…" sentence and
  no lines; upload it again in Quick Setup and the lines appear.

## A relationship tag judges the pair, in Link 2 only (pair tags Item 1, rung 2)

Use a session with tagged relationships (Setup → Relationships) and an
instrument card unlocked.

- [ ] **Offered once.** "Pair: …" options appear in Who is being
  reviewed's field list only: not in Who does the review, not in the
  reviewer-tag list beside IS THE SAME AS, not in Unit of review.
- [ ] **Its own cycle.** Pick a "Pair: …" field in Who is being
  reviewed: the operator opens on IS and cycles IS → IS NOT → IS FILLED
  → IS EMPTY, the caption reads "Pairwise tag" throughout, and the value
  box goes inactive on IS FILLED / IS EMPTY. Pick a reviewee tag again:
  the full cycle, from IS THE SAME AS, is back and the caption reads
  "Reviewee's tag".
- [ ] **IS FILLED assigns by any value.** Save "Pair: … IS FILLED", then
  Generate on Assignments: only the pairs carrying a value in that tag
  are assigned. "IS EMPTY" assigns every other pair.
- [ ] **Group skips beside IS FILLED.** With "Pair: … IS FILLED" (or
  IS) in Who is being reviewed, the Unit of review pill cycles
  Individual → Not set, skipping Group; IS NOT or IS EMPTY leave Group
  in the cycle.
- [ ] **Untagged reviewees (rung 2 read fix).** With tagged reviewers,
  untagged reviewees and tagged relationships, turn Who is being reviewed
  to Filter: the cell opens on "Pair: …" with IS and a value box, no
  reviewer-tag picker. Type a value and Save: the rule is kept.
- [ ] **A rule saved before this change (rung 3).** A local session
  saved since 2026-10-17 with "Pair: …" in Who does the review, or with
  "Pair: …" under IS FILLED / IS EMPTY / IS THE SAME AS in Who is being
  reviewed, now holds a retired field: Assignments and Validate answer
  500. Open its Instruments card: the rule shows as "Reviewer's pair
  tag: …" / "Reviewee's pair tag: …"; Save is refused until it is
  removed, after which both pages load.

## Dismiss clears a Quick Setup banner on Home (2026-10-19 run)

- [ ] **A refusal.** On Session Home, Quick Setup a file that is
  refused (a Settings file with a bad `rules_json`, or a reviewers file
  with a blank email): Dismiss hides the banner, the page scrolls to
  the slot, and the address stays Home's.
- [ ] **The deletion ask.** A Settings file naming one of two
  instruments: Dismiss hides the banner and its `Yes, delete it` tick.
  Submitting the file again asks again rather than deleting.

## A group-clear tick sits inside its red banner (2026-10-19 run)

- [ ] **Upload.** On Relationships, a replace that clears group answers
  (ticking the replace box): the red banner holds the line and
  `Yes, clear them` under it; the replace tick stays above.
- [ ] **Delete all.** The Danger Zone's ask: the same, with the
  `Yes, delete the existing …` tick staying above the banner.

## A Setup upload's ask keeps the file (19W rung 3)

- [ ] **Missing replace tick.** On Reviewers with a roster, choose a
  file and press Upload without ticking replace (the browser stops
  you, so untick after choosing on a stale tab, or use a direct POST).
  The card names the file as held and the file box is empty; tick and
  Upload, and the roster is replaced.
- [ ] **Group clear.** A Relationships replace that clears group
  answers: the ask holds the file and the replace tick comes back
  ticked. Tick `Yes, clear them` and press Upload with no file chosen;
  it goes through.
- [ ] **Dismiss.** On either ask, Dismiss returns to the card with no
  banner and no held file named.

## Quick Setup's ask keeps the files (19W rung 4)

- [ ] **The deletion ask.** A Settings file naming one of two
  instruments: the Settings slot names the file as held, the replace
  box is ticked and Submit is live. Tick `Yes, delete it` and
  Submit, and the file applies with nothing chosen again.
- [ ] **A missing replace tick.** With rosters in place, choose two
  files and Submit without the replace tick: both slots name their
  files; tick replace and Submit, and both apply.
- [ ] **Dismiss.** On either ask, Dismiss reloads Home with no banner
  and no held file named.
