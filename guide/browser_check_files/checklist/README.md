# Browser checklist: files and run order

One pass through every open section of
`guide/things_to_check_in_browser.md` that a local run can settle, in an
order where each step sets up the next. The **Ticks** column names the
section and row a step settles; tick it there as you go. **Delete this
folder in the same change that deletes the last section pointing to it.**

**Built and driven through the app with the test client on 2026-10-18**,
against a freshly migrated database. Every upload below gave the result
shown, and so did the steps the client can make: Prepare, Activate and
the warnings detour, Save, Submit and their refusals (the stale tab's
409 included), Close, Release, Revert, the group-clearing asks and their
ticks, the Settings import refusals, the scheduled activation and skip,
the archive and purge rows, and the participant pages as Alice, Olive
and Nobody. The client cannot see layout, scrolling, live JavaScript,
the Instrument card's Band 1 builder, sort memory or downloads; those
are the parts to check by eye. The card's boundary Save was driven
through its service, not the card.

## Before you start

- **The run:** local, `uvicorn` with fake auth, so you are
  `operator@example.edu` ("Local Operator"). Start from a fresh database
  (`review_robin_web.db` deleted, then `alembic upgrade head`).
- **Other people** are a restart of `uvicorn` with these set, then a
  restart back as yourself:

  | Who | Environment |
  |---|---|
  | Bob (operator and admin) | `FAKE_AUTH_EMAIL=bob@example.edu FAKE_AUTH_NAME="Bob Smith"` |
  | Alice (participant only) | `FAKE_AUTH_EMAIL=alice@example.edu FAKE_AUTH_NAME="Alice Chan"` plus the three flags below |
  | Olive (participant only) | `FAKE_AUTH_EMAIL=olive@example.edu FAKE_AUTH_NAME="Olive Grant"` plus the flags |
  | Nobody (no role) | `FAKE_AUTH_EMAIL=nobody@example.edu FAKE_AUTH_NAME="No Body"` plus the flags |

  The flags are `FAKE_AUTH_OPERATOR=false FAKE_AUTH_SYS_ADMIN=false
  FAKE_AUTH_SUPER_ADMIN=false`. Set them from that person's **first**
  sign-in: a role is stored on first sign-in, so an Alice who once
  signed in as an operator stays one.
- **Uploads:** "stage" means choosing files in the New session page's
  upload slots before Create; "Quick Setup" means Session Home's card.
  Tick the replacement box if it shows, then Submit. A settings file
  sets the session's timezone and schedule, so set those on Session
  Home **after** staging one.
- **"Your id"** is the 10-character public ID in the session's address.
- **Skipped (needs Azure):** #2720 "The submitted time does too"; P2's
  signed-out half of "Go back appears after an in-app page"; all of P5.
- **Skipped (not ready):** D28 "Rehydrate still takes it" (author,
  2026-10-13).
- **Skipped (a fresh database cannot hold the case):** S2/E1 "A refused
  rule stored earlier shows the banner", and pair tags rung 3 "A rule
  saved before this change". Neither rule can be stored any more.

## The files

| File | Content |
|---|---|
| `01_reviewers.csv` | Local Operator, Alice Chan (Cohort Day), Bob Smith (Evening) |
| `02_reviewees.csv` | Local Operator, Dev Patel, Erin Walsh (Team A; Subteam X, X, Y); Fay Gomez, Gus Ito (Team B) |
| `03_relationships.csv` | All 15 pairs; `Studio` set on six (North or South), blank on nine |
| `04_observers.csv` | Local Operator, cohort Team CONTAINS "Team" (everyone); Olive Grant, cohort Team IS "Team Z" (no one) |
| `05_settings.csv` | **Team review** ("Team"): grouped by Team, Rating (required) + Comments. **Peer review** ("Peer"): individual, Score (required) + Notes. Observers see summaries while open and Raw after release; reviewees see summaries after release. Shape "By reviewer". Band 1 links all set, no rules. UTC; name and code blank |
| `06_settings_bad_rule.csv` | 05 with a rule set whose `rules_json` is `[{"kind": "NOPE"}]` |
| `07_settings_bad_offset.csv` | 05 with End 2027-06-30 and `session.reminder_offsets` = `-P30D` |
| `08_settings_past_schedule.csv` | 05 with End 2026-09-30 (past) and reminders `-P2D, -PT4H` |
| `09_settings_one_instrument.csv` | 05 with Team review only |
| `10_reviewers_blank_email.csv` | Alice Chan with no email |
| `11_pairs_reviewees.csv` | 02's five reviewees, no tags |
| `12_groups_reviewees.csv` | 02's five reviewees (same tags) |
| `13_groups_relationships.csv` | Every reviewer with Local Operator, Dev (North), Erin, Fay (South); no row for Gus |
| `14_groups_settings.csv` | Team review as in 05; **Studio review** ("Studio"): grouped by the Studio pair tag, on its own page, Comments only (nothing required) |
| `15_groups_relationships_moved.csv` | 13 with Alice → Dev moved to South |
| `16_settings_no_fields.csv` | 05 with Peer review's response fields removed |

## Part 1 — BC main, set up

| # | Do | Expect | Ticks |
|---|---|---|---|
| 1 | New session `BC main`, code `bc-main`, Relationships and Observers ticked, Tags `alpha`. Stage 01–05. On Session Home set End a week ahead, 17:00, and Help contact `Pat Lee (pat@example.edu)`; Save. | No banner; two instruments; Prepare offered. Every address shows your id. | 19V: every address |
| 2 | `/me`, then `/me/sessions/<your id>/1`. Then `/operator/sessions/1` and `/me/sessions/1/1`. | Row reads "Not open yet". The page reads "This review is not currently open." with Pat Lee. Both numeric addresses: the 404 page. | M3: status labels (draft), not-open page; 19V: old address |
| 3 | **Prepare session**; reload the review link. | Validated; the same not-open page. | M3: not-open page (prepared) |
| 4 | **Activate session**. | `/me` reads "Open", with today's Start. | M3: status labels (Open) |
| 5 | Lobby: open BC main's row, Save it unchanged; Duplicate it ("Copy of BC main", kept for Part 12). Tick both rows and add the tag `delta` from the bulk panel. Open each Session Home tab. | Each acts on its row and lands on a public-id address. | 19V: lobby |
| 6 | Workflow card **Send invites**. Admin → Sessions: BC main's Outbox and Audit log. | Three invitation rows; both pages are BC main's. Keep the outbox open for Part 5. | 19V: Sys Admin |

## Part 2 — BC main as a reviewer

| # | Do | Expect | Ticks |
|---|---|---|---|
| 7 | `/me/sessions/<your id>/summary`. | Back on `/me`: "Your summary is available once every review is submitted." | M11: summary notice |
| 8 | On the review page, view source. | Boxes named `response[1][rating]`, `response[2][rating]`, `response[6][score]` … `response[10][notes]` (a group row takes its first member's number), and a hidden `page_digest`. | 19V: named by row |
| 9 | Press Submit with Scores empty, then Enter on `…/submit?page=1` in the address bar. | The missing-answers card; Enter lands back on page 1. | M10: Enter |
| 10 | Click Score's header to sort; type Scores 3, 1, 5, 2, 4 and Ratings Team A 4, Team B 3; Save; reload. | Each answer on its row; the sort kept. The responses CSV holds the Rating once, on "Team A (Dev Patel, Erin Walsh, Local Operator)". | 19V: save after a sort, group answer, sort memory |
| 11 | Run "A change after Submit needs a new Submit" rows 1–3 as written (Team A's Comments). | As the checklist says. | R1, R7 (rows 1–3) |
| 12 | Download the responses CSV; Save unchanged; download again; change Dev's Score; download again. | Version and SavedAt move only on the change. | R6 |
| 13 | Sort the Reviewers page by Name; reload. On Extract data turn off the intro's Data shaper chip; reload; download Reviewers. | Both kept; the file downloads. | 19V: sort memory, Extract data |
| 14 | About, then Settings, from a BC main page. | Each links back to it. | 19V: back links |

## Part 3 — BC groups, set up and answered

| # | Do | Expect | Ticks |
|---|---|---|---|
| 15 | New session `BC groups`, code `bc-groups`, Relationships ticked, Tags `beta`. Stage 01, 12, 13, 14. **Prepare session**, **Activate session**. | Activated. | — |
| 16 | `/me/sessions/<id>/2` (Studio). | Before any answer: `#2 Studio: not started`; `/me` "not started". | R7: no answer |
| 17 | Page 1: Rating Team A 4, Team B 3. Page 2: a comment on each of the three groups (Dev + you; Erin + Fay; Gus alone). Save each. | Saved. | — |

## Part 4 — BC late (a deadline that passes)

| # | Do | Expect | Ticks |
|---|---|---|---|
| 18 | New session `BC late`, code `bc-late`. Stage 01–05. On Session Home set Timezone `Asia/Singapore`, **then** End an hour from now (Singapore time), and Help contact `Pat Lee (pat@example.edu)`; Save. | End reads in GMT+8. | L8: an edit after the change |
| 19 | **Prepare session**. Invitations → a reviewer's row → preview; then its Reminder tab. | Each greets the reviewer by name, gives the deadline "(GMT+8 Asia/Singapore)", says MS365, and ends "Questions? Contact Pat Lee (pat@example.edu)." | L5: default invitation and reminder |
| 20 | Clear the help contact and the End; Save; preview both again. | No "Questions?" line, no "by …" line. | L5: default (cleared) |
| 21 | Email Template: Reminder body `Ask $help_contact`; Invitation body `Hello $reviewer_name.`; Save each; preview both. | "Ask the person running this review"; the invitation ends "Open this link: …". | L5: override fallbacks |
| 22 | Set End 30 minutes ahead; Save. On Assignments select Bob's ten rows and Inactivate. **Activate session**: the warnings page lists Bob's two "no active assignments"; **Acknowledge and activate**. | Activated. | — (M6 setup) |
| 23 | Fill every Score and Rating, Submit, open the summary. In a second tab open page 1 and type a Note with a line break; don't Save. | "Recall my submission" shows. | M1 (setup) |

Leave both tabs; do Part 5 while the deadline approaches.

## Part 5 — Other people

| # | Who | Do | Expect | Ticks |
|---|---|---|---|---|
| 24 | You | Copy Alice's and Bob's links from BC main's outbox. BC main's Invitations: **Regenerate** Alice's row, then **Send** it. Copy her new link from the outbox. | Her row reads `sent` again. | — (M12 setup) |
| 25 | You | BC main's Email Template → Responses received: chip to "Don't send response confirmation", Save. | — | — (G4 setup) |
| 26 | Bob | `/me`: BC late reads "Nothing assigned to you". BC main: fill everything and Submit. BC groups page 2: comment on all three groups; Save. | The submit succeeds. | M6: nothing assigned; G4: off (outbox below) |
| 27 | Bob | In the console on any page: `fetch('/operator/sessions/<BC main id>/clone', {method: 'POST', body: new URLSearchParams({mode: 'all'})})`. Then Admin → Sessions → BC main → **Adopt**. | Adopt lands on BC main's Session Home. | P2: duplicate trace (setup); 19V: Adopt |
| 28 | Alice | About, Guide, `/auth/me/debug`; a review page. | "Review Robin" with "Your reviews", no version; the participant About and Guide copy; every tab title ends "— Review Robin Web". | M8: top bar; L2; L3; L4 |
| 29 | Alice | Bob's link; her first link; her new link; `/operator/sessions`. | `b•••@example.edu`, no Sign-in details button, Pat Lee; "replaced by a newer one"; her BC main review; `/me` says the page is for the people who run reviews. | M9; M12: old link; M11: operator URL; L2 |
| 30 | Alice | BC groups page 2: comment on all three groups; Save. Open `/me/sessions/zzzzzzzzzz/results` in a new tab. Then on `/me` run `document.body.insertAdjacentHTML('afterbegin', '<a href="/me/sessions/zzzzzzzzzz/results">test</a>')` and click, then Ctrl-click, the link. | "Go to your reviews" only; then "Go back" too, in both tabs, returning to `/me`. | P2: error page, Go back |
| 31 | Nobody | `/me`. | "You're signed in as nobody@example.edu but there's nothing here…" | P2: empty dashboard |
| 32 | You | BC main's outbox; BC main's Audit log. | No responses-received row for Bob. A `session.duplicated` row naming Bob and his copy's code. | G4: off; P2: duplicate trace |

## Part 6 — BC late, after the deadline

| # | Do | Expect | Ticks |
|---|---|---|---|
| 33 | In the typing tab press Save; again with Submit. | Read-only, "This review closed at its deadline, … (GMT+8 Asia/Singapore), so your last changes weren't saved." with the Note's two lines; Submit says "so your answers weren't submitted". | P3: past the deadline |
| 34 | Reload the summary tab; then `/me`. | No "Recall my submission". BC late reads "Available". Hover the Timezone chips. | M1; M6: Available (reviewer); L6: timezone hover |

## Part 7 — BC main, through Close and Release

| # | Do | Expect | Ticks |
|---|---|---|---|
| 35 | In the console: `fetch('/operator/sessions/<id>/invitations/regenerate-all', {method: 'POST'})`; reload Invitations. | As the checklist says. | O2 |
| 36 | Review page: type a Note; in another window **Revert to draft**; Save. Then `/me`. | "This review is not currently open." in the card and the page. BC main's Start reads "—". | P3: reverted; M6: Start after a revert |
| 37 | **Prepare**, **Activate**. Type a two-line Note; **Close session**; Save. | The amber "This review has closed, so your last changes weren't saved.", the Note under it. | P3: closed mid-edit |
| 38 | **Release responses**. `/me`; the collation page; Peer's Download CSV. | "Available" (observer); the file is `bc-main_Peer.csv`. | M6: Available (observer); L6: observer CSV |
| 39 | As Olive: the collation page. | Row 3: "No one in your view takes part in this instrument, so there is nothing to download", no Download CSV. | M13 |
| 40 | **Revert to draft**; run the two "Session Home Save after Close early" rows. | As the checklist says. | L6 (Session Home) |
| 41 | Lobby: rename BC main (the oldest); `/me`. | Row order unchanged. | L6: row order |

## Part 8 — BC groups, the asks

Revert BC groups to draft first. Studio's groups are per reviewer:
row 43 changes yours, 44 Bob's, 45–46 Alice's. Keep this order: row 47's
Prepare clears the groups the earlier rows need answered.

| # | Do | Expect | Ticks |
|---|---|---|---|
| 42 | Reviewees: rename Erin; set Gus's Team to `Team C`; then Erin's Team to `Team B`, Save; tick, Save. | No asks, then the ask; ticked, Team B unanswered and Team A kept. | Reviewee tag edit (all rows); Group: tag edit |
| 43 | Relationships: your → Dev to `South`, Save; tick, Save. Add you → Gus `North`, Save; tick, Save. | Each asks, then goes through. | Relationships: edit and add |
| 44 | Relationships: select Bob → Fay, Inactivate; tick, Inactivate. Then Activate the same way. | Rows stay selected; the line and the tick; then through. | Relationships: Inactivate, Activate |
| 45 | Select Alice → Erin; tick Delete; tick the ask; Delete. | As above. | Relationships: Delete |
| 46 | Upload `15_groups_relationships_moved.csv`; tick; choose it again, Upload. Then Delete all; tick; Delete all. Then upload `13`. | Both ask, then go through. The last asks nothing. | Relationships: Delete all and Upload, nothing to clear |
| 47 | Reviewees: add Hana Ota (`hana@example.edu`, Team A, Subteam Y); **Prepare session**; **Regenerate & prepare**. | "Preparing will delete N saved responses", "on groups it adds members to". Team A unanswered; Team C (Gus) kept. | Group: Prepare asks |
| 48 | **Activate**; rate Team A 5 and Team B 2; **Revert**. Reviewees: select Fay, Delete, ticking the response-loss box. Preview the reviewer surface as `operator@example.edu`. | Erin, alone in Team B now, keeps its Rating. | Group: deleting a reviewee |
| 49 | Team review card: add a Subteam boundary cell; Save. Reload; Save unedited. Preview again. | No ask either time; Team A, X (Dev, you) and Team A, Y (Hana) both show 5. | Group: split; Card: split or unchanged |
| 50 | Remove the Subteam cell; Save. Reload. Remove it again, tick `Yes, clear them`, Save. | The red count banner, edits kept, nothing saved; then through, Team A unanswered; the audit row counts `defuncted_group_responses`. | Group: merge; Card: refused, ticked |

## Part 9 — BC import (Settings files, Instruments)

New session `BC import`, code `bc-import`, Relationships and Observers
ticked, Tags `gamma`; stage 01–05.

| # | Do | Expect | Ticks |
|---|---|---|---|
| 51 | Quick Setup, Session settings: `06`. Open Instruments, Assignments, Validate. | Refused, naming `rules_json`; all three open. | S2/E1: bad Settings file |
| 52 | `07`; then `08`. | Refused on `session.reminder_offsets`, Home loads; then applies with End 2026-09-30. | L1 (both) |
| 53 | `09`; tick both boxes, choose it again, Submit. Then `05`. | "deletes 1 instrument", listing Peer; then applies, Peer gone; 05 applies without asking. | S4 |
| 54 | Reviewers slot: `10_reviewers_blank_email.csv`. Unlock, Cancel, reload. Then `?quick_setup_error=settings&quick_setup_reason=parse&quick_setup_detail=hello` on Home. | Re-rendered at the banner ("ReviewerEmail is blank (1 row)"), Home address throughout; then no banner. | O7: refused upload, no text from a link |
| 55 | New session `BC refused`, code `bc-refused`, staging only `10`. Quick Setup it again. | "The reviewers file was refused…" without lines; then the lines. | O7: new session |
| 56 | **Prepare**. Assignments: turn Team review's Self review off. Edit any roster row; **Prepare**. Add reviewer Dev Patel (`dev@example.edu`); **Prepare**. Duplicate the session; Replicate Team review; export Settings. | As the checklist says. | E3 (all rows) |
| 57 | **Prepare**; rename Peer's Notes field, Save. **Prepare**; Save the card unedited. | As the checklist says. | S1 |
| 58 | Peer review card: the pair-tag rows "Offered once" to "Group skips beside IS FILLED"; for IS FILLED / IS EMPTY, Generate on Assignments. | IS FILLED: 6 Peer pairs (you → Dev, Fay; Alice → Erin, Gus; Bob → Dev, Fay); IS EMPTY: the other 9. | Pair tags: offered, cycle, IS FILLED, Group skips |
| 59 | Peer review Link 2: Team IS THE SAME AS reviewer Cohort; Save; reload. | Saved; the rule shows. | S2/E1: cross-side rule |
| 60 | Drag a Peer preview column wider: run O9 as written. With JavaScript off, run O7's sort-banner row. | As the checklist says. | O9; O7: sort banner |

## Part 10 — BC pairs and BC broken

| # | Do | Expect | Ticks |
|---|---|---|---|
| 61 | New session `BC pairs`, code `bc-pairs`, Relationships ticked; stage 01, 11, 03. Instrument card: Who is being reviewed → Filter; type `North`; Save; reload. | Opens on "Pair: Studio" with IS and a value box; the rule kept. | Pair tags: untagged reviewees |
| 62 | New session `BC broken`, code `bc-broken`; stage 01, 02, 16. In the console: `const f = document.createElement('form'); f.method = 'post'; f.action = location.pathname + '/workflow/prepare'; document.body.append(f); f.submit()`. Then the two forged addresses. | "Prepare session failed at the Validate setup." over "Validation reported errors. The Validate page lists them."; no "Call us" anywhere. | O7: workflow failure, forged link |

## Part 11 — BC sched (scheduled events)

Restart with `SCHEDULED_OPERATIONAL_LEAD_HOURS=0 REVIEWER_NOTICE_MIN_HOURS=0`.

| # | Do | Expect | Ticks |
|---|---|---|---|
| 63 | New session `BC sched`, code `bc-sched`; stage 01–05. Session Home: Start 5 minutes ahead, End a week ahead, Send invites `-PT2M`, reminders `-P2D`; Save. **Prepare**; open the review link. On BC broken (draft) set a Start 5 minutes ahead too. | "Scheduled to open". | M3: scheduled |
| 64 | After both Starts pass, open the lobby, not Session Home. Then Session Home, reloaded a few times. | BC sched reads Activated; its audit log has `session.activated` (`trigger=scheduled`) and the invitations sent. BC broken logs `session.scheduled_activation_skipped` and its Start is cleared. Home loads each time. | L4 (both); B20 |

Restart as yourself without the two settings.

## Part 12 — Lobby, archive, codes, zones

| # | Do | Expect | Ticks |
|---|---|---|---|
| 65 | Lobby: the O1 rows with the `alpha` / `beta` / `gamma` chips. | As the checklist says. | O1 (lobby half) |
| 66 | Copy of BC main: **Prepare**, **Activate**; console `fetch('/operator/sessions/<id>/workflow/archive', {method: 'POST'})`; Archived → Unarchive. Its review page and Instruments. | Not open; "0 accepting". | L5: archive closes accepting |
| 67 | Lobby: Copy of BC main → Purge and archive, Rosters ticked. BC main: **Prepare**, **Activate**, **Close session**, **Archive**. | Both on Archived. | — |
| 68 | `/me/sessions/<BC main id>/summary`, `…/summary.csv`, `…/collation`. | The error page each time. | M4: archived |
| 69 | Archived: the O1 rows with the `delta` chip. Then Unarchive the copy; its Observers. | As the checklist says; no observer rows. | O1 (Archived half); L7 |
| 70 | New session, code `Café-日本`; stage 01. Extract data: Reviewers CSV, setup Zip all. | `Café-日本_reviewers.csv`, `Café-日本_setup.zip`. | R2 |
| 71 | The L8 rows: New Session's four boxes, then Session Home's. | As the checklist says. | L8 (rows 1–2) |
