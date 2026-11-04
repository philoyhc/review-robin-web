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

## 14E: the clock, and auto-send off (#3577, #3578 and rung 2)

A local run. In `.env`: `SCHEDULER_INTERVAL_SECONDS=30` (a short interval
for testing; production keeps the default 120), and `RRW_SCHEDULED_SEND`
**unset** (off, the shipped default). Restart `uvicorn`: its log shows
`scheduled clock started` with `interval_seconds: 30`.

**To tell the clock from a page view:** open the session's audit log
(`/reviewrobin/operator/sys-admin/sessions/<id>/audit-log`) and "Show
detail" on the event: one the clock wrote carries `fired_by: clock`. Any
operator page you open runs the page-view trigger too, so between
setting a time and checking, **close every Review Robin tab** and wait.

- [ ] **Auto-send is off.** On New session and in Session Home's edit
  mode, Send invites and Send reminders are greyed out with "Scheduled
  sending isn't available on this deployment; send from Invitations when
  it's time." Session Home's display shows any stored offsets without a
  send time; the Workflow card never says "System will dispatch
  automatically"; the Guide's paragraph on the offsets says scheduled
  sending is off.
- [ ] **Activation on time, with no page view.** Take a session to
  Validated, set Start about 2 minutes ahead, save, close the tabs. Two
  minutes past Start, open the lobby: the session is open, and its
  `session.activated` event carries `fired_by: clock`.
- [ ] **The deadline closes on time.** On that open session, submit one
  reviewer's responses, then set End about 2 minutes ahead and close the
  tabs. After End, the audit log shows `instrument.closed` for each
  instrument and one **`session.deadline_reached`**, "Deadline reached: 1
  of N reviewers submitted", both `fired_by: clock`; the reviewer can no
  longer save.
- [ ] **The release window is stamped, once the session has ended.** The
  window opens only on an ended session. End the session from the
  Workflow card, then set Release responses from about 2 minutes ahead
  and Release responses until about 4 minutes ahead; close the tabs.
  After both, the audit log shows one `session.release_window_opened`
  and one `session.release_window_ended`. Reload a few times: neither
  repeats. On a session still open, a passing Release from stamps
  nothing.
- [ ] **A page view first still works, and records it once.** Set End 2
  minutes ahead and keep Session Home open; reload it just after End:
  the instruments close at once, and the `session.deadline_reached`
  event has no `fired_by`. The clock's next pass adds nothing.
- [ ] **Off is off.** `SCHEDULER_INTERVAL_SECONDS=0`, restart: no
  `scheduled clock started` in the log, and a Start that passes fires
  only when an operator page is opened, as before.

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
