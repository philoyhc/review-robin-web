# Browser checklist, round 2: files and run order

One pass through every row of `guide/things_to_check_in_browser.md` still
owed after the 2026-10-19 run, except the ones set aside below. Steps are
in an order where each sets up the next. **Ticks** names the section and
row a step settles; tick it there as you go. **Delete this folder in the
same change that deletes the last section pointing to it.**

**Built and driven on 2026-10-19 against a freshly migrated database**:

- **Test client:** the uploads, Save and Submit, the workflow buttons,
  the scheduled activation and skip, archive and purge, the downloads'
  status and file names.
- **Chromium against a live `uvicorn`:**
  - Part 3's card split and merge, the Relationships and Reviewers asks;
  - Part 5's Filter cell and both planted rules.

Every result below is what those gave. Nothing here sees layout,
scrolling, sort memory or a file once it is saved; those are the parts
to check by eye.

## Set aside

- **Needs Azure:**
  - #2720 "The submitted time does too";
  - P2's signed-out half of "Go back appears after an in-app page";
  - all three P5 rows.
- **Rehydrate:** D28 "Rehydrate still takes it".

## Before you start

- **The run:** local, `uvicorn` with fake auth, so you are
  `operator@example.edu` ("Local Operator") throughout. Start from a
  fresh database: delete `review_robin_web.db`, then `alembic upgrade
  head`.
- **Two restarts:** Part 6 needs the second line, then the first again.
  Each line clears what the other set.

  ```powershell
  # You
  Remove-Item Env:FAKE_AUTH_*, Env:SCHEDULED_OPERATIONAL_LEAD_HOURS, Env:REVIEWER_NOTICE_MIN_HOURS -ErrorAction SilentlyContinue; uvicorn app.main:app --reload

  # You, for Part 6 (scheduled events)
  Remove-Item Env:FAKE_AUTH_*, Env:SCHEDULED_OPERATIONAL_LEAD_HOURS, Env:REVIEWER_NOTICE_MIN_HOURS -ErrorAction SilentlyContinue; $env:SCHEDULED_OPERATIONAL_LEAD_HOURS="0"; $env:REVIEWER_NOTICE_MIN_HOURS="0"; uvicorn app.main:app --reload
  ```
- **Uploads:**
  - "stage" means choosing files in the New session page's upload slots
    before Create;
  - "Quick Setup" means Session Home's card: tick the replace box if it
    shows, then Submit.
  - A settings file sets the session's timezone and schedule, so set
    those on Session Home **after** staging one.
- **"Its id"** is the 10-character public ID in the session's address.
- **Preview** means
  `/operator/sessions/<its id>/preview-surface/1?reviewer_email=operator@example.edu`
  (`/2` for page 2). It shows your answers on a draft session too.
- **An unedited card's Save is greyed out.** Where a step says "Save
  unedited", type a letter into a response field's name, delete it,
  then Save.

## The files

| File | Content |
|---|---|
| `01_reviewers.csv` | Local Operator, Alice Chan (Cohort Day), Bob Smith (Evening) |
| `02_reviewees.csv` | Local Operator, Dev Patel, Erin Walsh (Team A; Subteam X, X, Y); Fay Gomez, Gus Ito (Team B) |
| `03_relationships.csv` | All 15 pairs; `Studio` set on six (North or South), blank on nine |
| `04_observers.csv` | Local Operator, cohort Team CONTAINS "Team" (everyone); Olive Grant, cohort Team IS "Team Z" (no one) |
| `05_settings.csv` | **Team review** ("Team"): grouped by Team, Rating (required) + Comments. **Peer review** ("Peer"): individual, Score (required) + Notes. UTC; name and code blank |
| `06_settings_bad_rule.csv` | 05 with a rule set whose `rules_json` is `[{"kind": "NOPE"}]` |
| `07_settings_bad_offset.csv` | 05 with End 2027-06-30 and `session.reminder_offsets` = `-P30D` |
| `08_settings_past_schedule.csv` | 05 with End 2026-09-30 (past) and reminders `-P2D, -PT4H` |
| `09_settings_one_instrument.csv` | 05 with Team review only |
| `10_reviewers_blank_email.csv` | Alice Chan with no email |
| `11_reviewees_untagged.csv` | 02's five reviewees, no tags |
| `12_groups_relationships.csv` | Every reviewer with Local Operator, Dev (North), Erin, Fay (South); no row for Gus |
| `13_groups_settings.csv` | Team review as in 05; **Studio review** ("Studio"): grouped by the Studio pair tag, on its own page, Comments only |
| `14_groups_relationships_moved.csv` | 12 with your row for Dev moved to South |
| `15_settings_no_fields.csv` | 05 with Peer review's response fields removed |
| `plant_old_rule.py` | Stores a Band 1 rule the card no longer saves (Part 5); its docstring says how to run it |

## Part 1 — Quick Setup on fresh sessions

| # | Do | Expect | Ticks |
|---|---|---|---|
| 1 | New session `R fresh`, code `r-fresh`, Relationships ticked, nothing staged. Quick Setup with 01, 02, 12, 13 and the replace box ticked. | No banner; Team review and Studio review replace `Instrument_1`. | S4 fresh: no question |
| 2 | New session `R touched`, code `r-touched`, Relationships ticked. Instruments: give `Instrument_1` the short label `Mine`; Save. Quick Setup the same four files. Then tick `Yes, delete it` and Submit with nothing chosen again. | "Nothing was imported. This settings file deletes 1 instrument it does not name, with its fields: Mine". Every slot reads "Holding … from your last Submit", and the replace box stays ticked. After the tick, it applies: Team review and Studio review. | S4 fresh: a default you changed |

## Part 2 — R main: a reviewer's page and its downloads

| # | Do | Expect | Ticks |
|---|---|---|---|
| 3 | New session `R main`, code `r-main`, Relationships and Observers ticked, Tags `alpha`. Stage 01–05. On Session Home set End a week ahead at 17:00 and Help contact `Pat Lee (pat@example.edu)`; Save. Open `/me/sessions/<its id>/1`. | "This review is not currently open.", the deadline, "Questions? Contact Pat Lee (pat@example.edu)". | Not open page (draft, help contact) |
| 4 | **Prepare session**; reload the review link. | The same page. | Not open page (prepared) |
| 5 | **Activate session**. View the review page's source. | The two tables' `data-rrw-sortable` end `-1` and `-2`. The `data-sort-key`s read `display:reviewee.tag_1`, `display:pair_context.1`, `response:rating`, `response:score` and so on, with no number. | 19V: sort keys |
| 6 | Click Score's header. Type Scores Dev 3, Gus 1, you 5, Fay 2, Erin 4; Ratings Team A 4, Team B 3. Save; reload. | Each answer on its row; still sorted by Score. | 19V: save after a sort; sort per session (review page) |
| 7 | Reviewers page: sort by Name, twice (descending); reload. | Still sorted. | 19V: sort per session (Setup) |
| 8 | Extract data: download each card's file (both metadata cards, By instrument, Extract all data's Zip all). Turn off the intro's Data shaper chip; reload. Open `r-main_responses.csv` from the Zip all. | Every download works; the chip stays off. The Rating 4 is on one row, naming "Team A (Dev Patel, Erin Walsh, Local Operator)". Note Dev's Score row: `Version` 1. | 19V: Extract data; group answer |
| 9 | Save the review page unchanged; Zip all again. Change Dev's Score to 5, Save; Zip all again. | Unchanged Save: `Version` and `SavedAt` as before. After the change: `Version` 2 and a new `SavedAt`. | R6 |
| 10 | Team A's Comments `Good team`; Save; **Submit**. Change it to `Better team`; Save. Look at the page pill, `/me` and Invitations. Submit. Empty it; Save; Submit. Type `x`, Save, empty it, Save; Submit. Save unedited. | After each change: `#1 Team: complete`, "Saved but not submitted", and your Invitations row `in progress`. After each Submit, and after the unedited Save, all three read submitted. | R1, R7 (rows 1–3) |
| 11 | **Close session**. `/me`. | R main reads "Closed". | `/me` status: Closed |
| 12 | **Release responses**. Open the collation page. Change a Download CSV link's `2.csv` to `abc.csv`. | The links end `/instruments/1.csv` and `/instruments/2.csv`; `abc.csv` shows the error page. | 19V: observer CSV (`abc`) |

## Part 3 — R groups: what clears a group's answer

Your groups here:

- **Team review:** Team A is you, Dev and Erin; Team B is Fay and Gus.
- **Studio review:** North is you and Dev; South is Erin and Fay; Gus
  has no relationship, so he is alone.

| # | Do | Expect | Ticks |
|---|---|---|---|
| 13 | New session `R groups`, code `r-groups`, Relationships ticked, Tags `beta`. Stage 01, 02, 12, 13. **Prepare**, **Activate**. Page 1: Rating Team A 4, Team B 3. Page 2: `North note` (Dev, you), `South note` (Erin, Fay), `Gus note`. Save each page. **Revert to draft**. | Saved. | — |
| 14 | Instruments → Team review: unlock. Under Unit of review press **+**, choose Subteam in the new cell; Save. Preview page 1. Unlock again and Save unedited. | Neither Save asks. Team A, X (Dev, you) and Team A, Y (Erin) both show 4. | Group: split; Card: split or unchanged |
| 15 | Unlock; press the Subteam cell's **X**; Save. Reload. | Red banner: "Couldn't save this instrument: This change clears 3 saved responses on groups whose members it changes.", over an unticked `Yes, clear them`. The card stays unlocked with the cell gone. After the reload, Subteam is back: nothing was saved. | Card: refused with the count |
| 16 | Remove the cell again, tick `Yes, clear them`, Save. Preview page 1. Admin → Sessions → R groups → Audit log. | The banner goes. Team A has no Rating; Team B keeps 3. The last `instrument.group_boundary_updated` row has `defuncted_group_responses` 3. | Card: ticked; Group: merge |
| 17 | Relationships: unlock, choose `14`, tick the replace box, Upload. | Red banner: "This change clears 3 saved responses…", with `Yes, clear them` and Dismiss **inside** it. The replace tick stays above it, still ticked. The file box is empty, and the card reads "Holding 14_groups_relationships_moved.csv". | Group-clear tick: upload; 19W rung 3: group clear |
| 18 | **Dismiss**. Then upload `14` the same way, tick `Yes, clear them`, and press Upload with no file chosen. Preview page 2. | Dismiss: back to the card, no banner, no held file. Then the upload goes through. North (just you) keeps `North note`; South, which Dev joined, is blank; Gus keeps his. | 19W rung 3: Dismiss; group clear |
| 19 | Danger Zone: tick `Yes, delete the existing 12 relationships`, press Delete all. Dismiss. | Red banner with its own `Yes, clear them`; the delete tick stays above it. Dismiss: no banner, nothing deleted. | Group-clear tick: Delete all |
| 20 | Reviewers: unlock and choose `01`. In the console, run `document.getElementById('upload-csv-form').submit()`. Then tick the replace box and press Upload. | "Tick the replacement-confirmation box just above Upload, then upload again." The card reads "Holding 01_reviewers.csv", and the file box is empty. The tick and Upload replace the roster. | 19W rung 3: missing replace tick |

## Part 4 — R import: Settings files and Quick Setup's asks

| # | Do | Expect | Ticks |
|---|---|---|---|
| 21 | New session `R import`, code `r-import`, Relationships and Observers ticked, Tags `gamma`. Stage 01–05. Quick Setup's Session settings slot: `06`. **Dismiss**. Open Instruments, Assignments, Validate. | Refused, naming `rules_json` and `'NOPE'`; the address stays Home's. Dismiss hides the banner and the page scrolls to the slot. All three pages open. | S2/E1: bad Settings file; Dismiss on Home: a refusal |
| 22 | Quick Setup `07`; then `08`. | `07` is refused on `session.reminder_offsets` ("exceeds the 10-day maximum"), and Home loads. `08` applies, with End 2026-09-30. | L1 (both) |
| 23 | Quick Setup `09`. **Dismiss**. | "Nothing was imported. This settings file deletes 1 instrument…", listing Peer, with `Yes, delete it`. The Settings slot reads "Holding 09_settings_one_instrument.csv", and the replace box stays ticked. Dismiss reloads Home with no banner and no held file. | Dismiss on Home: the deletion ask; 19W rung 4: Dismiss |
| 24 | Quick Setup `09` again; tick `Yes, delete it`; Submit with nothing chosen. Then Quick Setup `05`. | It asks again; then it applies and Peer is gone. `05` applies without asking, and Peer is back. | S4: deletes are named; 19W rung 4: the deletion ask |
| 25 | Choose `01` in Reviewers, `02` in Reviewees and `03` in Relationships; untick replace; Submit. Tick replace; Submit. | "Tick the replacement-confirmation box just above Submit…", and each slot reads "Holding …". Then all three apply. (A roster replace drops the relationships, so `03` goes with them for step 31.) | 19W rung 4: a missing replace tick |
| 26 | Reviewers slot: `10`. Unlock, Cancel, reload. Then open Home with `?quick_setup_error=settings&quick_setup_reason=parse&quick_setup_detail=hello`. | The page scrolls to the banner, "ReviewerEmail is blank (1 row)", with the address Home's throughout. The query string shows no banner. | S4/O7: refused upload stays on Home; no text from a link |
| 27 | New session `R refused`, code `r-refused`, staging only `10`. Then Quick Setup `10` there. | "The reviewers file was refused, so none of the files uploaded with the new session were saved…", without lines. Quick Setup shows the lines. | S4/O7: new session |
| 28 | Back in **R import**: **Prepare**. Assignments: turn Team review's Self review off. Rename Bob on Reviewers; **Prepare**. Add reviewer Dev Patel (`dev@example.edu`); **Prepare**. | Team review's self-review rows stay excluded and its chip reads off; Peer's are unaffected. Dev's new self-review rows arrive excluded. | E3: off stays off; new rows |
| 29 | Instruments: Replicate Team review. Lobby: Duplicate R import. Export R import's Settings CSV. | Both copies have Self review off. The CSV has `instruments[1].self_reviews_active` = `false`. | E3: carried along |
| 30 | **Prepare**. Peer review: rename Notes; Save. Audit log. **Prepare**; Save Peer unedited. | Renamed: back in draft, with an `instrument.response_fields_saved` row naming the field. Unedited: still validated, no new row. | S1 (both) |
| 31 | Peer review card: run "Offered once", "Its own cycle" and "Group skips beside IS FILLED". Save "Pair: Studio IS FILLED" and Generate on Assignments; then "IS EMPTY" and Generate. | As the rows say. IS FILLED: 6 Peer pairs (you → Dev, Fay; Alice → Erin, Gus; Bob → Dev, Fay). IS EMPTY: 14, the other 9 plus Dev's 5 (step 28 added him with no relationship rows, so his pairs carry no tag). | Pair tags: offered, cycle, IS FILLED, Group skips |
| 32 | Peer review's Who is being reviewed: Team IS THE SAME AS reviewer Cohort; Save; reload. | Saved, and the rule shows. | S2/E1: a cross-side rule |
| 33 | Peer review: run O9 as written. With JavaScript off, run O7's sort-banner row. | As the rows say. | O9; O7: sort banner |

## Part 5 — R pairs and R broken

| # | Do | Expect | Ticks |
|---|---|---|---|
| 34 | New session `R pairs`, code `r-pairs`, Relationships ticked. Stage 01, 11, 03. Instrument card: unlock; turn Who is being reviewed to Filter; type `North`; Save; reload. | It opens on "Pair: Studio" with IS and a value box, and no reviewer-tag picker. The rule is kept. | Pair tags: untagged reviewees |
| 35 | From the repository root: `python guide/browser_check_files/round_2/plant_old_rule.py r-pairs same-side`. Open Assignments and Validate. Reload the card; unlock; Save unedited. | Assignments and Validate answer 500. The card shows "Pair: Studio IS THE SAME AS" a second pair tag. Save is refused, storing nothing: "A relationship tag can't be compared with IS THE SAME AS or IS DIFFERENT FROM…". The row expects "This assignment rule can't be used"; the pair-tag check now catches this rule first. | S2/E1: a refused rule stored earlier |
| 36 | `… plant_old_rule.py r-pairs retired`. Assignments and Validate. The card: Save unedited. Turn Who does the review back to All; Save. Assignments and Validate. | Both answer 500. Who does the review reads "Reviewer's pair tag: Studio". Save is refused: "A rule reads a person's relationship tag, which the card no longer offers…". Once the rule is removed, it saves and both pages load. | Pair tags: a rule saved before (rung 3) |
| 37 | New session `R broken`, code `r-broken`. Stage 01, 02, 15. In the console: `const f = document.createElement('form'); f.method = 'post'; f.action = location.pathname + '/workflow/prepare'; document.body.append(f); f.submit()`. Then run O7's two forged addresses. | "Prepare session failed at the Validate setup." over "Validation reported errors. The Validate page lists them.". The forged addresses show only the headline, then no Owners banner. "Call us" appears nowhere. | O7: workflow failure; forged link |

## Part 6 — R sched (scheduled events)

Restart with the Part 6 line.

| # | Do | Expect | Ticks |
|---|---|---|---|
| 38 | New session `R sched`, code `r-sched`. Stage 01–05. On Session Home set Start 5 minutes ahead, End a week ahead, Send invites `-PT2M`, reminders `-P2D`, and Help contact `Pat Lee (pat@example.edu)`; Save. Open the review link. **Prepare**; reload it. On R broken (still draft) set a Start 5 minutes ahead. | Draft: not open, with Pat Lee. Prepared: "Scheduled to open: …" and Pat Lee. | Not open page (scheduled, help contact) |
| 39 | After both Starts pass, open the lobby (not Session Home). Then R sched's Session Home, reloaded a few times. Then both audit logs. | R sched reads Activated. R sched's log has `session.activated` with `trigger=scheduled`. R broken's has `session.scheduled_activation_skipped`, and its Start is cleared. Home loads every time, and no `session.scheduled_event_failed` row appears. | L4 (both); B20 |

Restart with the "You" line.

## Part 7 — Lobby, archive, codes, zones

| # | Do | Expect | Ticks |
|---|---|---|---|
| 40 | Lobby: run the O1 rows with the `alpha`, `beta` and `gamma` chips. | As the rows say. | O1 (lobby) |
| 41 | Duplicate R main ("Copy of R main"). On the copy: **Prepare**, **Activate**. In the console on its Session Home: `fetch(location.pathname + '/workflow/archive', {method: 'POST'})`. Archived → Unarchive it. Its review link and Instruments. | The review link is not open; Instruments reads "0 accepting". | L5: archive closes accepting |
| 42 | Lobby: the copy's Purge and archive, Rosters ticked. Archived → Unarchive. Its Observers. | No rows. | L7 |
| 43 | Lobby: tick R main, R fresh and R touched; the bulk panel's Archive. | All three move to Archived. | 19V: the lobby (bulk archive) |
| 44 | `/me`. Then `/me/sessions/<R main's id>/summary`, `…/summary.csv` and `…/collation`. | R main is not listed. Each address shows the error page. | `/me` status: archived not listed; archived is off limits |
| 45 | Archived: run the O1 rows, filtering with the box (`fresh`). | As the rows say. | O1 (Archived) |
| 46 | New session `Code test`, code `Café-日本`; stage 01. Extract data: the Reviewers CSV and the setup card's Zip all. | The files save as `Café-日本_reviewers.csv` and `Café-日本_setup.zip`. | R2 |
| 47 | Run the two open L8 rows: New Session's four boxes, then Session Home's details card on that session. | As the rows say. | L8 (rows 1–2) |
