# Email and scheduled jobs: where they stand, and what is recommended

**Opened:** 2026-11-01, at the author's request after a survey of both
repositories. A recommendation, not yet a plan: the three choices at the
end are the author's, and a segment plan follows them. **Related:**
`guide/segment_14B_email_infrastructure.md` (the email-wiring plan, not
started), `guide/post_azure_todo_checklist.md` items 7–10,
`spec/email_infra_options.md`, `spec/lifecycle.md` §8.3.

## Where things stand

**No email is delivered, and nothing runs on a clock.**

- **Sending is recorded, not done.** `send_invitation` and `send_reminder`
  (`app/services/invitations.py`) write an `email_outbox` row and mark it
  and the invitation `sent` at once; no transport is called. The
  responses-received confirmation (`queue_responses_received`) stays
  `queued` for good. The page says so ("no email is delivered until email
  sending is switched on"); the rows do not, since they read `sent`
  (`guide/post_azure_todo_checklist.md` item 8).
- **Transports exist, unused.** `app/services/email_send.py` has an SMTP
  transport over per-operator settings (`User.smtp_*`, the password
  encrypted with `SMTP_ENCRYPTION_KEY`) and a Graph transport that is a
  stub. "Nothing in the app calls this yet."
- **Scheduled events run on page views.** Activation, scheduled
  invitations and reminders (`app/services/scheduled_events/`) and the
  deadline close fire when an operator opens Session Home, an Operations
  page or the lobby, by design ("no new processes / cron / queue infra",
  `spec/lifecycle.md` §8.3). A 09:00 reminder goes out whenever someone
  next looks. Auto-archive has a column and no code.
- **On Azure,** delegated `Mail.Send` and `User.ReadBasic.All` have
  tenant-wide consent, sign-in asks for `offline_access`, and a delegated
  `POST /me/sendMail` from a user's token answered `202` and was delivered
  (Cordware's Azure progress record, 2026-10-31). **No application
  permission** is granted, so a shared-mailbox send needs choice 2's ask
  (read 2026-11-01). The Web App runs with Always On, on **one instance
  with one `uvicorn` process** (read 2026-11-01). No Cordware workflow
  runs on a schedule.

## The disagreement to settle

The repositories disagree about **who sends**.

- **Cordware's design rationale (§4.9): delegated `Mail.Send`, "sent as
  the actor".** No shared mailbox and no application-wide send right; but
  mail goes only while that person is signed in, and the rationale itself
  says "Scheduled sends need another answer."
- **`spec/email_infra_options.md`: delegated is out of scope,** because
  scheduled reminders cannot wait for an operator session. Its target is
  an application permission sending from a shared mailbox
  (`/users/{mailbox}/sendMail`) through a queue and a worker.

Both are right about their half. A click has a signed-in sender; a clock
does not.

## Recommendations

1. **Make the outbox honest first.** A row stays `queued` until a
   transport has sent it, and a failure is `failed` with its reason
   (`guide/post_azure_todo_checklist.md` item 8). It needs no decision
   below and every option builds on it.
2. **Two send paths.**
   - **What a person sends** (Send invites, Send reminder, Send all) goes
     **delegated, as that operator**, through `/me/sendMail` on the token
     Easy Auth holds. Nothing to ask IT for: the consent exists.
   - **What the clock sends** (scheduled invitations and reminders, the
     responses-received confirmation) goes **from a shared mailbox under
     an application `Mail.Send` permission**, which IT scopes to that one
     mailbox with an Exchange application access policy, so the app can
     send as nobody else.
   - **If IT will not grant it,** clock mail stays `queued` and goes out,
     delegated, the next time one of the session's operators is signed in.
     Worse, but honest.
3. **A real clock, inside the app.** The Web App is Always On, so a small
   background loop can run the existing scheduled-event pass every few
   minutes, with a lock so only one worker runs it. Today there is one
   instance and one process, so the lock guards a future scale-out rather
   than today's host. No new Azure resource,
   and it reuses the code and audit rows that fire today on page views.
   It needs a base URL for links, from `CORDWARE_PUBLIC_ORIGIN`, and a
   retry with a terminal state (`guide/post_azure_todo_checklist.md`
   item 7). *Rejected for now:* a scheduled Cordware workflow on the
   in-VNet runner calling an internal endpoint. It keeps the timer outside
   the app but adds a route, a credential and a workflow to keep in step.
4. **Renew the delegated token.** Delegated sends need a live token.
   Built 2026-11-01: every page renews it through `/.auth/refresh` once 45
   minutes have passed, and the directory pickers renew and retry on
   `unauthorized` (`cordware/spec/identity.md`, "Graph"). A delegated send
   reuses `window.cordwareRenewGraph()` the same way.

## Narrowed (author, 2026-11-01)

**The choice is between Graph as the operator and Graph as a dedicated
mailbox.** SMTP drops out: institutional tenants typically block basic
SMTP AUTH and app passwords under MFA, so even a dedicated mailbox would
be reached through Graph. The per-operator SMTP cards on Settings retire
(`guide/segment_14C_email_related_ui.md` Item 1), their storage kept for
a deployment outside Microsoft 365, so choice 1's option (c) below means
a dedicated mailbox over Graph. Per-operator email choices, such as
keeping a copy in Sent Items, get their own card (14C Item 2).

## The author's choices

1. **Who sends:** (a) split, as recommended; (b) delegated only, clock
   mail waiting for the next operator sign-in; (c) a shared mailbox for
   everything.
2. **Ask IT now** for the application `Mail.Send` permission, a shared
   mailbox and its access policy? It is the longest lead time.
3. **The clock:** (a) a loop inside the app, as recommended; (b) a
   scheduled Cordware workflow.

## Order, once chosen

The honest outbox (1); the delegated path for clicks (2, first half) with
token renewal (4); the clock (3), still firing what it fires today; the
shared-mailbox path for clock mail (2, second half) when IT delivers. Each
is its own PR or rung under segment 14B, which this note feeds.
