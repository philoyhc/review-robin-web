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

## 14E: the clock, and auto-send off (#3577, #3578, #3579)

A local run, with the clock every 30 seconds (production keeps 120),
scheduled sending off (the shipped default), and Start's one-hour lead
time lifted so a Start a few minutes ahead saves. From the repository
root, your usual `.env` (fake auth as `operator@example.edu`) in place:

```powershell
# Windows PowerShell. The first line lets this window run the venv's
# activation script; it lasts until the window closes.
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
Remove-Item Env:RRW_SCHEDULED_SEND -ErrorAction SilentlyContinue
$env:SCHEDULER_INTERVAL_SECONDS = "30"
$env:SCHEDULED_OPERATIONAL_LEAD_HOURS = "0"
alembic upgrade head
uvicorn cordware.main:app --reload
```

```bash
# macOS / Linux
source .venv/bin/activate
unset RRW_SCHEDULED_SEND
alembic upgrade head
SCHEDULER_INTERVAL_SECONDS=30 SCHEDULED_OPERATIONAL_LEAD_HOURS=0 uvicorn cordware.main:app --reload
```

The log shows `scheduled clock started` with `interval_seconds: 30`; the
app is at `http://127.0.0.1:8000/reviewrobin/`.

**Reading the audit log.** A session's log is
`/reviewrobin/operator/sys-admin/sessions/<id>/audit-log`, `<id>` being
the code after `/sessions/` in Session Home's address; "Show detail"
opens an event. One the clock wrote carries `fired_by: clock`. The log
page does not run the scheduled steps, but Session Home, the Operations
pages and the lobby do, so **between setting a time and checking, keep
only the audit log open**.

**Times are set together, beforehand:** Start, End and the release
window are editable only before the session opens.

- [ ] **Auto-send is off.** On New session, Send invites and Send
  reminders are greyed out with "Scheduled sending isn't available on
  this deployment; send from Invitations when it's time"; the Guide's
  paragraph on them says the same.
- [ ] **Set up.** Create a session; on Quick Setup upload
  `docs/sample_data/basic_cohort/mock_reviewers.csv` and
  `mock_reviewees.csv`. Run Validate and Prepare session until the
  Workflow card offers Activate (Validated). In Session Home's edit mode
  the two offset fields are greyed out with the same line, and the
  Workflow card never says "System will dispatch automatically".
- [ ] **Schedule.** Note the time *T*. In Session Home's edit mode set
  Start *T*+3 min, End *T*+6 min, Release responses from *T*+9 min and
  Release responses until *T*+12 min; save. Copy the session's code
  from the address, open its audit log, and close every other Review
  Robin tab.
- [ ] **Activation on time.** At *T*+4, reload the audit log:
  `session.activated`, detail `fired_by: clock`.
- [ ] **The deadline closes on time.** (Optional, before *T*+6: open
  `/reviewrobin/me` and submit your own reviews, as
  `operator@example.edu` is a reviewer.) At *T*+7, reload: one
  `instrument.closed` per instrument and one `session.deadline_reached`,
  "Deadline reached: *n* of *N* reviewers submitted", each `fired_by:
  clock`.
- [ ] **The window waits for the session to end.** Open Session Home and
  press **Close session** before *T*+9, then close it again, leaving the
  audit log. At *T*+13, reload: one `session.release_window_opened` and
  one `session.release_window_ended`. Reload twice more: neither repeats.
- [ ] **Off is off, and a page view still does it.** Stop the app
  (Ctrl+C) and start it with the interval at `0`, keeping the lead time
  at `0`: in PowerShell `$env:SCHEDULER_INTERVAL_SECONDS = "0"` then
  `uvicorn cordware.main:app --reload`; in bash
  `SCHEDULER_INTERVAL_SECONDS=0 SCHEDULED_OPERATIONAL_LEAD_HOURS=0 uvicorn
  cordware.main:app --reload`. No `scheduled clock started` in the log.
  Note a **new** time *T2*, take a second session to Validated with Start
  *T2*+2 and End *T2*+4, keep its Session Home open, and reload it after
  *T2*+2 and again after *T2*+4: it opens, then closes, and its
  `session.activated` and `session.deadline_reached` carry no
  `fired_by`.

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
