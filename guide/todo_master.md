# Master todo sequence

**Open work only.** What is queued, what is filed but small, and the
order constraints between them. Nothing here is history: when a
segment closes it deletes its own entries from this file (its queue
line, any stub it shipped or absorbed, any sequencing note that named
it — the `segment-plan` skill, "Closing a segment"), and the record of
what shipped is the archived plan (`guide/archive/README.md`), its PRs
and the git log. The `## Done` section this file carried until
2026-10-05 is verbatim in `guide/archive/todo_master_done.md`.

When a segment plan exists, that plan is the day-to-day source of truth
for its own slices; this file points at it without duplicating its PR
ladder.

Two sibling registers hold the open work that is not queued here:

- `guide/post_azure_todo_checklist.md` — work **blocked on the
  institutional Azure deployment** itself, not merely unscheduled.
- `guide/deferred_consolidated.md` — work scoped but not scheduled,
  ordered by disposition.

---

## Upcoming

### After segment 21

- **Segment 21D's live check** under real Easy Auth, on the institutional
  host (the dev slot stays dormant, author 2026-10-24). Review Robin's
  first release went out on 2026-10-31, and three of the four
  requirements are recorded passing there with the deployment: the
  invite link on the public origin, `/.auth/*` sign-in end to end, and
  both health probes. Not recorded: `/reviewrobin` redirecting to
  `/reviewrobin/`. One visit settles it; then delete this entry.

### Queued segments

20 is **gated on the institutional Azure deployment concluding**
(decision 2026-09-05); 14G is gated on IT. 14B was retired 2026-11-02
for 14E, 14F and 14G. The
host is provisioned and serving Review Robin since 2026-10-31; whether
the deployment has *concluded* (verified, the personal web app retired)
is the author's call.

**Order (author, 2026-11-04): 14E and 22C (both closed 2026-11-04),
then 14F with 14C Item 2.** 14F's send path is written under 22C's type
gate.

1. **14F — Email by hand, as the operator** (not gated: the tenant
   already grants delegated `Mail.Send`). Sends on the operator's click
   through `/me/sendMail`; disables the auto-send fields and adds
   due-action prompts while no mail goes on a clock.
   **Plan:** `guide/segment_14F_manual_email.md`.

   **With it, 14C Item 2 — Email-related UI** (Item 1, the SMTP cards
   retired, is done): a half-width Email settings card of toggles,
   scaffolded beside 14F's scaffold and wired as 14F's send path reads
   them. **Plan:** `guide/segment_14C_email_related_ui.md`.

2. **14G — Scheduled email** (gated on IT: offline sending as the
   operator, else a dedicated mailbox). Sends due invitations, reminders
   and confirmations from 14E's clock, and switches 14F's auto-send
   fields back on. Planned when IT answers; see
   `guide/no_scheduling_fallback.md`. A shared mailbox under an app-wide
   permission is a credential every mounted app could reach: plan one
   per app, or rule a shared one accepted (`guide/interoperability.md` §2).
   **Switching `RRW_SCHEDULED_SEND` on** (14E rung 0) would fire every
   reminder already past due on every open session in one pass, after
   operators may have reminded by hand: 14G marks those skipped, not
   sent, when it turns the setting on.

3. **22G — Diagnostics** (parked, author, 2026-11-04). Item 1: a small
   set of status reports about the session on Azure, the in-app clock's
   state first; where they sit waits on how many there are.
   **Plan:** `guide/segment_22G_diagnostics.md`.

### Stubs

Small items with no plan doc; each fits one PR and its reasoning fits
the PR body unless it says otherwise.

- **Cordware host logging, events 4 and 5** *(filed 2026-10-22, at
  segment 21's close)*. v0.8 §3 "Host logging" names two events the host
  still does not log:
  - event 4, requests no mounted application handled;
  - event 5, errors outside any mounted application, and failing
    `/health` checks.

  21A deferred event 5 to 21D, whose plan never took it up
  (`guide/archive/segment_21_domain_retrofit.md` § Status).
  `cordware/spec/host.md` "Logging" says they are not yet built. Overdue: the
  institutional deployment has been live since 2026-10-31, and the logs
  are the host's only operational record.

- **`regenerate_token` leaves `last_reminder_at` standing** *(filed
  2026-09-18; the author answered **yes, clear it**, placement open)*.
  `regenerate_token` (`app/services/invitations.py`) clears
  `token_hash`, `status`, `sent_at` and `opened_at`, but not
  `last_reminder_at` or the outbox rows, so a reissued invitation still
  reports a reminder sent against the dead token. Clearing it moves the
  Invitations **Reminder** column and the reminder scheduler. Reasoning
  at `guide/archive/segment_19P_expander_revamp.md` Item 6 OQ4.

- **The three Operations pages gate their left toolbar pane on having
  rows** *(filed 2026-09-17)*, where the four roster pages let the
  partials guard themselves. The filter in the right pane stays
  reachable on a search that matches nothing, so nothing is lost
  today; it is a divergence of pattern between the two families.

- **`close_check`'s manifest check is one-directional** *(filed
  2026-09-13)*. C3 asks whether every path a plan **declared** was
  edited in the window, never whether every path **edited** was
  declared — 19N.1 edited three specs with no `Doc impact` bullet and
  passed. The advisory `touched; not in manifest` notes compute most
  of it; the open question is promoting them to a check without
  drowning in the long-window noise 19C and 19J recorded. Likely one
  slice in `tools/close_check/`.

- **Should a rehydrate audit observer, relationship and assignment
  counts?** *(filed 2026-09-13)*. `session.rehydrated` carries four
  count keys (`reviewers`, `reviewees`, `responses`,
  `responses_dropped`) and `spec/rehydrate.md` §7 names those four. A
  design question the author ruled future work: deciding it needs a
  reason someone would read the other three.

- **Theme customizer — a full pass over every element** *(author
  intent, 2026-09-06)*. 19C Item 8 found three defects only by looking
  (an inherited 2px border, a stale pick-list facet, an edit box with
  no visible edge). The intent is to work through every element the
  same way rather than as defects surface. Unscoped on purpose; each
  finding is likely its own slice. Open a plan doc when the pass starts.

- **Does *Invitations* still name the page?** *(filed 2026-09-18)*.
  Since 19P.6 it is reviewer-keyed and its rows render with no
  invitation at all, so the tab name describes the artefact rather than
  the job. Naming only. **Author's call**, and cheap to leave alone.

### Sequencing notes

- **The email pipeline:** the `email_outbox` schema landed inert in 11C
  Part 2 (migration `c4f6a8b0d2e5`); 14F is its first sender, and 14G
  adds mail on 14E's clock. 14E and 14F are independent of each other.
- **20** is independent of the email pipeline but gated on the
  deployment, so it does not interleave with other work.
