# Browser checklist, round 2: files and run order

What `guide/things_to_check_in_browser.md` still owes after the
2026-10-19 run that a local run can settle: the 19X Item 3 check, and
the steps that run set aside (its old steps 33, 38 and 39). Steps are in an
order where each sets up the next. **Ticks** names the section a step
settles; tick it there as you go. **Delete this folder in the same
change that deletes the last section pointing to it.**

The full run order is in git history, at this file's version from
before 2026-10-19's cleanup.

## Set aside

- **Needs Azure:** #2720 "The submitted time does too"; P2's signed-out
  row; all three P5 rows.
- **Rehydrate:** D28 "Rehydrate still takes it".

## Before you start

- **The run:** local, `uvicorn` with fake auth, so you are
  `operator@example.edu` ("Local Operator") throughout. A fresh database
  is simplest: delete `review_robin_web.db`, then `alembic upgrade head`.
- **Two restarts:** Part 3 needs the second line, then the first again.
  Each line clears what the other set.

  ```powershell
  # You
  Remove-Item Env:FAKE_AUTH_*, Env:SCHEDULED_OPERATIONAL_LEAD_HOURS, Env:REVIEWER_NOTICE_MIN_HOURS -ErrorAction SilentlyContinue; uvicorn app.main:app --reload

  # You, for Part 3 (scheduled events)
  Remove-Item Env:FAKE_AUTH_*, Env:SCHEDULED_OPERATIONAL_LEAD_HOURS, Env:REVIEWER_NOTICE_MIN_HOURS -ErrorAction SilentlyContinue; $env:SCHEDULED_OPERATIONAL_LEAD_HOURS="0"; $env:REVIEWER_NOTICE_MIN_HOURS="0"; uvicorn app.main:app --reload
  ```
- **Uploads:** "stage" means choosing files in the New session page's
  upload slots before Create; "Quick Setup" means Session Home's card:
  tick the replace box if it shows, then Submit. A settings file sets
  the session's timezone and schedule, so set those on Session Home
  **after** staging one.

## The files

| File | Content |
|---|---|
| `01_reviewers.csv` | Local Operator, Alice Chan (Cohort Day), Bob Smith (Evening) |
| `02_reviewees.csv` | Local Operator, Dev Patel, Erin Walsh (Team A; Subteam X, X, Y); Fay Gomez, Gus Ito (Team B) |
| `03_relationships.csv` | All 15 pairs; `Studio` set on six (North or South), blank on nine |
| `04_observers.csv` | Local Operator, cohort Team CONTAINS "Team" (everyone); Olive Grant, cohort Team IS "Team Z" (no one) |
| `05_settings.csv` | **Team review** ("Team"): grouped by Team, Rating (required) + Comments. **Peer review** ("Peer"): individual, Score (required) + Notes. UTC; name and code blank |
| `12_groups_relationships.csv` | Every reviewer with Local Operator, Dev (North), Erin, Fay (South); no row for Gus |
| `13_groups_settings.csv` | Team review as in 05; **Studio review** ("Studio"): grouped by the Studio pair tag, on its own page, Comments only |

## Part 1 — the 19X Item 3 check

| # | Do | Expect | Ticks |
|---|---|---|---|
| 1 | New session `R groups`, code `r-groups`, Relationships ticked. Stage 01, 02, 12, 13. **Prepare**, **Activate**. Open `/me/sessions/<its id>/2` (its id is the 10-character public ID in the session's address). Comments: `North note` on the row naming Dev Patel and Local Operator, `South note` on the row naming Erin Walsh and Fay Gomez; Save. Session Home: **Revert to draft**. | Saved. These are the answers a Delete all clears. | — |
| 2 | Relationships: **Unlock**; scroll to the Danger Zone. Read the tick; tick it and press **Delete all relationships**. | The tick reads "Yes, delete the existing 12 relationships and the 4 reviewer responses on the groups they form". Delete all goes through with no banner; the relationships and both notes are gone. | 19X Item 3 |
| 3 | New session `R main`, code `r-main`, Relationships and Observers ticked. Stage 01–05. | Created; Part 2 uses it. | — |

## Part 2 — instrument cards (old step 33)

| # | Do | Expect | Ticks |
|---|---|---|---|
| 4 | R main, Instruments, Peer review: run O9 as written. With JavaScript off, run O7's sort-banner row. | As the rows say. | O9; O7: sort banner |

## Part 3 — R sched (scheduled events; old steps 38–39)

Restart with the Part 3 line.

| # | Do | Expect | Ticks |
|---|---|---|---|
| 5 | New session `R sched`, code `r-sched`. Stage 01–05. On Session Home set Start 5 minutes ahead, End a week ahead, Send invites `-PT2M`, reminders `-P2D`, and Help contact `Pat Lee (pat@example.edu)`; Save. **Prepare**; open the review link. New session `R draft`, code `r-draft`, nothing staged; set a Start 5 minutes ahead. | R sched's link: "This review is not currently open.", "Scheduled to open: …" and Pat Lee. | Not open page: scheduled |
| 6 | After both Starts pass, open the lobby (not Session Home). Then R sched's Session Home, reloaded a few times. Then both audit logs. | R sched reads Activated; its log has `session.activated` with `trigger=scheduled`. R draft's has `session.scheduled_activation_skipped`, and its Start is cleared. Home loads every time, and no `session.scheduled_event_failed` row appears. | L4; B20 |

Restart with the "You" line.
