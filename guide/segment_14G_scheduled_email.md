# Segment 14G — Scheduled email

**Opened:** 2026-11-05, at the author's request, as a **draft** · **Theme:**
the mail an operator schedules goes out at its time with nobody signed in ·
**Related:** `guide/archive/segment_14F_manual_email.md` (built first),
`guide/segment_14C_email_related_ui.md`, `guide/archive/segment_14E_clock.md`,
`guide/no_scheduling_fallback.md`, `guide/email_and_scheduling.md`,
`guide/post_azure_todo_checklist.md` items 7 and 9

Five items, each closing on its own (Item 5, bulk sending, added
2026-11-05 when 14F handed it over). **Item 1 can be built now.** Items 2–4
wait on two things outside this plan: 14F's delegated Graph send (author,
2026-11-05: 14F and 14C are built first), and IT's answer on offline
sending (two requests kept privately with the deployment: offline sending
as the operator, and its fallback, a dedicated mailbox).

## Opportunity

- **The clock queues nothing that mails.** 14E's in-app clock runs
  scheduled activation, the close at End and the release stamps with no
  page view (`spec/lifecycle.md` §8.3). Scheduled invitations and
  reminders stay off behind `RRW_SCHEDULED_SEND`. Even with it on, the
  clock calls `observe_scheduled_events` without `build_invite_url`, so
  `_invites.py` and `_reminders.py` return early. A page view builds that
  URL from its request; a clock has no request. The deployment's origin is
  `CORDWARE_PUBLIC_ORIGIN`, which only `cordware/main.py` reads.
- **A failed scheduled invite or reminder retries forever.** Since B20
  (2026-10-02) a failing pass rolls back, writes
  `session.scheduled_event_failed` and tries again next pass, with no cap
  and no terminal state. Activation has both (`failed_persistent`).
- **Nothing sends with nobody signed in.** 14F sends on a click, with the
  clicking operator's token. A clock has no token unless IT allows one.
- **Some mail has no click at all:** the responses-received confirmation
  on a reviewer's submit, and 14C Item 2's report groups C and D
  (activation done or failed, all submitted, all acknowledged, due
  actions). Those render disabled until this segment ships.

## Decision

**The clock queues on time, and a dispatcher sends what it queued through
whichever offline path IT allows.**

- **Item 1, now:** the app reads the deployment's origin, the clock
  passes `build_invite_url`, and scheduled invites and reminders gain a
  retry cap and a terminal state like activation's. With the setting on,
  rows land in the outbox at their time and stay `queued`; with it off,
  nothing changes. Testable without IT or a transport.
- **Item 2, the offline send path,** one of two, chosen by IT's answer:
  - **(a) As the operator.** Store the scheduling operator's delegated
    refresh token, encrypted (the `SMTP_ENCRYPTION_KEY` pattern), redeem
    it server-side, and send through `/me/sendMail` with 14F's host
    primitive. Mail goes from the operator's own mailbox, as 14F's does.
  - **(b) A dedicated mailbox.** Application `Mail.Send`, restricted to
    one mailbox by an access policy, with a managed identity or a
    certificate, through `/users/{mailbox}/sendMail`.
  - Both send through 14F's dispatch helper: it claims each row
    `queued` → `sending` and stamps `sent` or `failed` (14F Semantics,
    "One send per row"). 14G adds a caller, not a second sender.
- **Item 3, switching on:** `RRW_SCHEDULED_SEND` on, the auto-send fields
  live again, and reminders already past due marked skipped, not sent.
- **Item 4, mail with no click:** confirmations and the report groups C
  and D, through Item 2's path.

Rejected: *a scheduled Cordware workflow calling an internal endpoint*
(`guide/email_and_scheduling.md`, choice 3): 14E's clock already runs in
the app. Rejected: *SMTP for the dedicated mailbox*: institutional tenants
block basic SMTP AUTH under MFA (author, 2026-11-01).

## Semantics

- **No origin configured:** the clock queues no invite or reminder and
  says so once in the log and on System Status. It never builds a
  relative link.
- **Retry:** a scheduled invite or reminder failing at queue or send
  retries on later passes up to the activation cap, then reads
  `failed_persistent` with its reason, shown where activation's is.
  The dedupe stamp already committed with an outbox row stops a requeue
  (B31).
- **Which operator sends, under (a):** the operator who last set the
  session's offsets. If their token is gone, revoked or past the tenant's
  sign-in frequency, the row stays `queued` and goes out on their next
  sign-in, with a due-action prompt meanwhile (14F's). Never another
  operator's token.
- **How far ahead, under (a):** a schedule beyond the token's lifetime is
  accepted, with a warning on the form naming the date it may slip past.
- **Switching on:** a reminder or invite whose time passed while the
  setting was off is marked skipped with a reason, never sent late.
- **The backlog** of rows queued before Item 2: 14F's rule, unchanged.

## Judgment calls — decided

- 14G reuses 14F's dispatcher and host primitive (2026-11-05).
- Item 1 ships behind the setting, off by default (2026-11-05).

## Blast radius (measured)

Taken 2026-11-05 at `c0cd4dcc`.

| What | Count | Command |
|---|---|---|
| Files in `app/` passing `build_invite_url` | 6 | `git grep -l "build_invite_url" -- app \| wc -l` |
| Files reading the origin | 1 (+ its test) | `git grep -l "public_origin" -- app cordware '*.py'` |
| Files in `app/` gating on the setting | 7 | `git grep -l "scheduled_send_enabled()" -- app \| wc -l` |
| Test files naming the setting | 4 | `git grep -l "scheduled_send\|RRW_SCHEDULED_SEND" -- tests \| wc -l` |
| Specs and docs naming scheduled send | 9 | `git grep -l "RRW_SCHEDULED_SEND\|scheduled send\|Scheduled sending" -- spec docs \| wc -l` |

## Item 1 — the clock queues on time

### PR ladder

1. **The origin, the builder and the retry (one PR).** The settings read
   `CORDWARE_PUBLIC_ORIGIN` where `app` can; the clock passes
   `build_invite_url`; scheduled invites and reminders gain the cap and
   `failed_persistent`. Tests: the clock queues a due invite and reminder
   with an absolute link; no origin queues none; a repeated failure ends
   `failed_persistent`. Its own read.
2. **Close.**

### Definition of done

- With the setting on in a test, the clock queues a due invitation and a
  reminder whose links start with the configured origin.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 14G.1` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

### Doc impact

- `spec/lifecycle.md` — §8.3: the clock passes the invite builder; the retry and terminal state for invites and reminders.
- `docs/deployment.md` — `CORDWARE_PUBLIC_ORIGIN` read by the application too.
- `guide/post_azure_todo_checklist.md` — item 7: the builder and the retry done; the send left to Item 2.

## Item 2 — the offline send path (gated)

**Gated on** 14F's transport and IT's answer. Planned in full when both
are in; the ladder below is the shape.

### PR ladder

1. **Path (a) or (b)**, as IT allows: the credential, its storage and the
   send through 14F's helper, with a test transport.
2. **The clock dispatches** what Item 1 queued, through that path.
3. **The token-lifetime warning** on the schedule form, under (a) only.
4. **Close.**

### Definition of done

- A scheduled invitation and a scheduled reminder each go out at their
  set time on the deployed app with no operator page open; the audit and
  outbox times show it, and the links open on the deployed host (a
  check on Azure, the author's; checklist item 7's "Done when").
- `## Doc impact` section present and current
- `python3 tools/close_check.py 14G.2` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

### Doc impact

- `spec/email_infra_options.md` — the offline path in use, beside 14F's delegated one.
- `cordware/spec/identity.md` — "Graph": the stored token or the app-only credential.
- `docs/security_posture.md` — what is stored, how it is encrypted, and who it can send as.

## Item 3 — switching on (gated)

### PR ladder

1. **The setting on:** the auto-send fields live, the past-due rows
   skipped, the Workflow caption's dispatch line back.
2. **Close:** the Guide's "Running a session by hand" says what is now
   automatic; `guide/no_scheduling_fallback.md` retires.

### Definition of done

- `RRW_SCHEDULED_SEND` is on in the deployment, and
  `tests/integration/test_scheduled_send_off.py` still covers the off state.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 14G.3` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

### Doc impact

- `spec/workflow_card.md` — the auto-send caption with the setting on.
- `spec/settings_inventory.md` — the setting, on where a send path exists.
- `docs/deployment.md` — the setting in its table: when to turn it on.

## Item 4 — mail with no click (gated)

### PR ladder

1. **Confirmations** on a reviewer's submit, through Item 2's path, under
   14F's backlog rule.
2. **Report groups C and D** (`guide/segment_14C_email_related_ui.md`
   Item 2), their toggles live.
3. **Close.**

### Definition of done

- A submit's confirmation and an activation report each arrive with
  nobody signed in (a check on Azure, the author's).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 14G.4` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

### Doc impact

- `spec/email_template_editor.md` — the confirmation sent on submit.
- `guide/post_azure_todo_checklist.md` — item 9 settled for clock-sent rows.

## Item 5 — bulk sending, paced (from 14F, 2026-11-05)

### Opportunity

14F builds Send all, Remind incomplete, Send queued confirmations and the
Workflow card's Send invites, but leaves them disabled behind
`RRW_BULK_SEND`. 1,500 reviewers is 1,500 messages, one per personal link.
In one request that runs far past the gateway's 120 s, and it meets the
sending mailbox's own limits (Exchange Online documents a per-minute
message rate and a daily recipient cap; to be measured on the tenant).
Until this item ships, operators share 14F's session link instead.

### Decision (draft)

- **Paced and resumable.** The dispatcher already claims each row once
  and stamps it, so a bulk send is a loop over queued rows that can stop
  and resume without sending anything twice. It paces under the measured
  mailbox rate and backs off on a `429`.
- **Two ways to drive it:**
  - **(a) page-driven batches:** the browser posts the queue in chunks
    with a progress line. This needs no IT, but the tab must stay open.
  - **(b) the clock drains the queue** with Item 2's offline send path,
    with nobody's tab open. This needs Item 2.

  The draft favors (b) once Item 2 lands, and (a) only if bulk is wanted
  sooner.
- **Send queued confirmations** sends under 14F's backlog rule (author,
  2026-11-05): confirmations queued before go-live are not resent, nor
  any for a recalled or deleted submission.

### PR ladder

1. **Measure:** per-send time and the mailbox rate on Azure, through the
   per-row Send.
2. **The paced loop** behind `RRW_BULK_SEND`, by (a) or (b).
3. **Switch on:** the four buttons live; `docs/deployment.md` says when.
4. **Close.**

### Definition of done

- A Send all of 1,500 test rows completes, paced, with every row
  stamped `sent` or `failed` and none sent twice (a test, plus a check
  on Azure, the author's).
- `## Doc impact` section present and current
- `python3 tools/close_check.py 14G.5` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

### Doc impact

- `spec/operations_pages.md` — the bulk buttons live, with their progress line.
- `docs/deployment.md` — `RRW_BULK_SEND`: when to turn it on.

## Open questions

- **Item 5's driver:** (a) page-driven batches, or (b) the clock.
  Author, once Item 2's path is known.

- **Path (a) or (b).** IT, then the author.
- **Which operator's token sends under (a)** when several own a session:
  proposed the one who last set the offsets. Author, at Item 2.
- **When to switch the setting on:** with Item 3 only, or as soon as
  Item 2's dispatch lands (`guide/no_scheduling_fallback.md`, first open
  question). Author.
- **The retry cap:** proposed activation's. Author, at Item 1.

## Out of scope

- Sending on a click: 14F.
- The Email settings card itself: 14C Item 2.
- Reviewee and observer notifications and magic links (W20 / W21,
  `guide/magic_links.md`).
- A separate background worker or queue service: Item 5 paces sending
  inside the app.
