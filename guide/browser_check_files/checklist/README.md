# Browser checklist: files and run order

One pass through every open section of
`guide/things_to_check_in_browser.md`, in an order where each step sets
up the next. The **Ticks** column names the section and row a step
settles; tick it there as you go. **Delete this folder in the same
change that deletes the last section pointing to it.**

**Built and driven through the app with the test client on 2026-10-13.**
Every upload below gave the result shown. That run also covered:
Prepare and Activate on the BC main session, the operator's Self review
pills, and the collation page loading. The client cannot see layout,
scrolling, live JavaScript or downloads; those are the parts to check by
eye. It also posted Prepare directly, which hid that the first 05 left
both instruments' Band 1 links at "Not set", so Session Home offered no
Prepare. The settings files now mark all three links set; a re-run
through Quick Setup showed both instruments set up and Prepare offered.

## Before you start

- **The run:** local, `uvicorn` with fake auth, so you are
  `operator@example.edu` ("Local Operator"). A fresh database
  (`review_robin_web.db` deleted, then `alembic upgrade head`) keeps the
  sessions below from clashing with old ones.
- **You are on every roster.** Local Operator is a reviewer, a reviewee
  (Team A) and an observer in these files. So `/me` shows the reviewer
  and observer pages without switching identity.
- **Uploads:** "Quick Setup" means Session Home's Quick Setup card.
  Choose each file in its slot, tick the replacement box if it shows,
  then Submit.
- **Skipped (needs Azure):** #2720 "The submitted time does too".
- **Skipped (not ready for testing):** D28 "Rehydrate still takes it".
  Rehydrate is off by default and not yet ready (author, 2026-10-13).
- **Needs a second identity:** G4 "Off sends nothing" needs a second
  reviewer to submit. Restart `uvicorn` with
  `FAKE_AUTH_EMAIL=bob@example.edu FAKE_AUTH_NAME="Bob Smith"` for that
  one step, then switch back. Skip it if you'd rather.

## The files

| File | Content |
|---|---|
| `01_reviewers.csv` | Local Operator, Alice Chan, Bob Smith |
| `02_reviewees.csv` | Local Operator, Dev Patel, Erin Walsh (Team A); Fay Gomez, Gus Ito (Team B) |
| `03_relationships.csv` | All 15 pairs, `PairContextTag1` = the reviewee's team |
| `04_observers.csv` | Local Operator, Olive Grant |
| `05_settings.csv` | Two instruments on one page. **Team review** ("Team"): grouped by `PairContextTag1`, Rating (required) + Comments. **Peer review** ("Peer"): individual, Score (required) + Notes + Extra. Observers see summaries while the session runs; reviewees see summaries after release. One saved shape, "By reviewer". Both instruments' Band 1 links are set (so they count as set up) but carry no rules: every pair is assigned, self reviews included. Name and code left blank, so an import keeps the session's own. |
| `06_settings_repeated_shape.csv` | 05 with the shape's rows copied to `data_shapes[1]` |
| `07_settings_lowercase_integer.csv` | 05 with Peer's Score `data_type` = `integer` |
| `08_settings_boolean_type.csv` | 05 with Peer's Score `data_type` = `Boolean` |
| `09_settings_missing_name.csv` | 05 with `instruments[1].name` blank |
| `10_settings_seven_nameless.csv` | Seven instruments, none named |
| `11_reviewers_blank_email.csv` | Alice Chan with no email |
| `12_long_name.txt` | A 250-character name to paste |

## Part 1 — BC main, set up (Draft)

| # | Do | Expect | Ticks |
|---|---|---|---|
| 1 | New session `BC main`, code `bc-main`. Quick Setup: 01, 02, 03, 04 and 05 together. | No banner. Relationships and Observers tabs appear. Instruments has Team review and Peer review, each with its three Band 1 links set (none reads "Not set"). Session Home offers **Prepare**. | — |
| 2 | Instruments → Peer review: unlock, click the **Extra** field's chip off, Save. | Extra greys out. | — (A3 setup) |
| 3 | On Peer review, set a default sort with a header badge and drag a column wider, then Save. | Badge and width stay after a reload. | — (A28 setup) |
| 4 | Extract → Extract Setup: download the Settings CSV and keep it as `bc-main-settings.csv`. | — | — (A28 setup) |
| 5 | Session Home → **Prepare**, then Manage Invitations → send all. | Validated. The outbox holds three invitation rows: Prepare only creates the invitations, and sending writes the rows with their links. | — |
| 6 | Assignments: note Team review's "Include N self reviews" (3). On Relationships, inactivate the row Local Operator → Dev Patel. Back on Assignments, without generating: 2. Reactivate the row: 3 again. | As stated | B33 |
| 7 | Open `/operator/sessions/{id}/assignments?needs_confirm=1`. | Red banner: "Replace not confirmed. The existing assignments were kept.", with Cancel at its bottom right. Cancel returns to the page without the banner. | #2809, #2810: banner |
| 8 | Admin → Sessions → BC main's outbox: copy Alice Chan's invitation link. Reviewers: set Alice inactive. Open the link. | A plain 404. Manage Invitations has no Alice row, and Pending reminders leaves her out. | #2740: 404, no reminder |
| 9 | Set Alice active again; open the same link. | The "issued to alice@example.edu" page, since you are signed in as the operator. Not a 404. | #2740: 404 (the second half) |
| 10 | **Prepare** again (step 6 put the session back to Draft), then **Activate**. | Activated. | — |

## Part 2 — BC main as a reviewer (Activated)

Open `/me` → BC main.

| # | Do | Expect | Ticks |
|---|---|---|---|
| 11 | Look at both instruments. | A blue "Self review" pill after Local Operator on Peer. On Team review, one under the Team A group. Save works on those rows. | G7 |
| 12 | On Peer, give Scores of 3, 1, 5 and 2 to four rows and leave one blank. Save. Click Score's header, then reload. Click it again, then reload. Then sort by Name and reload. | Rows match the badge after each reload, blank last. Descending holds. The Name sort arrives already sorted, with no visible move. | A27 (all three) |
| 13 | Leave that Peer Score blank and Submit. | The missing-answers card's entry starts `#2 Peer:`, matching the `#2 Peer` pill. | A2 |
| 14 | Fill every Score and every Team Rating, leave Notes empty, and Submit. In Admin → Sessions → outbox: | One responses-received row for you, `queued`, its body naming the submit time. | G4: on by default |
| 15 | Recall, then Submit again; check the outbox. | Still one row for you. | G4: second submit |
| 16 | *(Optional, second identity.)* Email Template → Responses received: set the chip to "Don't send response confirmation" and Save. As Bob, submit. | The submit succeeds, and no new outbox row appears. | G4: off |
| 17 | `/me/sessions/{id}/collation`. Note the address of Peer's Download CSV link for step 25. | Peer has no Extra column, and its Download CSV has none. Notes reads "Total length: —". The operator's By instrument extract still has Extra. | A3 (both rows) |
| 18 | Extract data, rows 1–3 of D28 as written. | As the checklist says | D28: card order, same files, chips |
| 19 | Extract data → Data shaper: delete "By reviewer", then run the D13 rows as written. | As the checklist says | D13 (both rows) |

## Part 3 — BC main back in Draft (it has responses now)

| # | Do | Expect | Ticks |
|---|---|---|---|
| 20 | Session Home → Revert to draft. | Draft; responses kept. | — |
| 21 | Relationships: inactivate Local Operator → Dev Patel. Preview the reviewer surface as `operator@example.edu`. | Dev shows outside Team A without its Rating; Erin and you keep it. Reactivate the row, and Dev rejoins Team A with its Rating. | B34: inactivate |
| 22 | Relationships upload: 03 again, tick, Upload. Preview again. | Every Rating and Score is still there. | B34: re-import |
| 23 | Reviewees first: run the response-loss row's banner part with `02_reviewees.csv` (acknowledgment input removed). Stop before its final upload, which would discard the responses the Reviewers run still needs. | The banner, as the checklist says, and no response gone. | Upload banners: acknowledgment (Reviewees) |
| 24 | Reviewers: run both upload-banner rows with `01_reviewers.csv`, as written. First the tick is missing, then the acknowledgment is removed. | As the checklist says. The final upload replaces the roster and discards the responses. | Upload banners: tick, acknowledgment (Reviewers) |

## Part 4 — BC main, closed out

| # | Do | Expect | Ticks |
|---|---|---|---|
| 25 | **Prepare**, **Activate**, then close and **Archive** the session. Open `/me/sessions/{id}/1` and the CSV address from step 17. | The page reads "BC main — closed" and "This review has closed.", with no deadline line and a dashboard link. The CSV address answers 404. | A25: closed copy; #2740: observer CSV |

## Part 5 — BC import (Settings CSV checks)

New session `BC import`, code `bc-import`, then Quick Setup 01, 02, 03,
04 and 05.

| # | Upload in the Session settings slot | Expect | Ticks |
|---|---|---|---|
| 26 | `06_settings_repeated_shape.csv` | "Could not import session settings." over `data_shapes[1].name: duplicate data_shapes name 'By reviewer' (also at data_shapes[0])`. Nothing changed. | D1 |
| 27 | `07_settings_lowercase_integer.csv` | Imports. In the reviewer Preview, Peer's Score is a number box. | D2: `integer` |
| 28 | `08_settings_boolean_type.csv` | "Could not import session settings." naming `'Boolean'`. Nothing changed. | D2: unknown type |
| 29 | `09_settings_missing_name.csv` | "Could not import session settings." over `instruments[1].name: name is required`. | D31: listed |
| 30 | `10_settings_seven_nameless.csv` | Five `instruments[n].name` lines, then "…and 2 more." | D31: five and more |
| 31 | `05_settings.csv` | Lands on Session Home at the Settings slot, with no `?config_imported=ok` in the address bar. | #2809, #2810: landing |
| 32 | Reviewers slot: `11_reviewers_blank_email.csv` | The banner's one button reads Dismiss, and it clears the banner. | Upload banners: Dismiss |
| 33 | `bc-main-settings.csv` (step 4) | Peer review keeps step 3's sort badge and column width. | A28: round-trip |
| 34 | Instruments → Team review: run B1 as written. Exclude self reviews, then add a Link 2 rule that keeps reviewees whose email is not `operator@example.edu`. | As the checklist says | B1 |

## Part 6 — BC long (long names)

| # | Do | Expect | Ticks |
|---|---|---|---|
| 35 | New session named with `12_long_name.txt`'s text, code `bc-long`. Quick Setup 01–05. Rename Peer review to the same text, then Replicate it. | The copy's name ends " (copy)", with the source name trimmed. | Long names: Replicate |
| 36 | Lobby → Duplicate this session. | The copy opens, named "Copy of …" and cut at the end, with no error page. | Long names: Duplicate |
| 37 | Prepare and Activate. Then from Operations, send one invitation and one reminder, and look at the outbox. | Both succeed. Each subject is cut short. | Long session names still send |

## Part 7 — BC sched (schedule and lobby Save)

| # | Do | Expect | Ticks |
|---|---|---|---|
| 38 | New session `BC sched`, code `bc-sched`, Relationships box ticked. Quick Setup 01–05. On Session Home set a Start (tomorrow), an End (a week later), invite and reminder offsets, and a release window. Save. | Saved | — |
| 39 | Lobby: open BC sched's row, change the Name, Save. | Session Home still shows every step-38 setting. | C1: rename |
| 40 | Same row: set the Deadline before the Start and Save. | "End must be on or after Start." Nothing changes, tags included. | C1: End before Start |
| 41 | **Prepare**, then open `/me/sessions/{id}/1`. | "opens later" | A25 (the Prepared half) |
| 42 | Set the Start a minute or two ahead and save. Wait until it passes, then reload Session Home a few times. | Session Home loads each time. Admin → Sessions → audit log shows the fired events, or one `session.scheduled_event_failed` row per failing trigger. | B20 |

## Part 8 — Accounts

| # | Do | Expect | Ticks |
|---|---|---|---|
| 43 | Sys Admin → Accounts: select `operator@example.edu`. | Delete stays greyed; Revoke is offered. | #2867: history |
| 44 | Invite `nobody@example.edu`, select it, and Delete. | The row goes. | #2867: no activity |

## Part 9 — The Guide's sample session

| # | Do | Expect | Ticks |
|---|---|---|---|
| 45 | Guide → Sample session: download the sample data, then follow the card's steps on a new session `BC demo`, code `bc-demo`. | After Quick Setup the Workflow card shows no Prepare; after the Instruments step it does; Prepare reaches Validated. | Sample session walkthrough |
