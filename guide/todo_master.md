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

### Queued segments

20 is **gated on the institutional Azure deployment concluding**
(decision 2026-09-05); 14G is gated on IT. 14B was retired 2026-11-02
for 14E, 14F and 14G. The
host is provisioned and serving Review Robin since 2026-10-31; whether
the deployment has *concluded* (verified, the personal web app retired)
is the author's call.

**Order (author, 2026-11-06):** host logging (the stub below), then 14C Item 2, then 22J; 14G when IT answers.

1. **14C Item 2 — Email-related UI** (Items 1 and 3 done): the Email
   settings card of toggles, built and read by 14F's send path. Before
   its close, the card gains the candidate report-email toggles: live
   where the send needs no scheduled email, inactive where it does
   (author, 2026-11-06). **Plan:** `guide/segment_14C_email_related_ui.md`.

2. **14G — Scheduled email** (gated on IT: offline sending as the
   operator, else a dedicated mailbox). Sends due invitations, reminders
   and confirmations from 14E's clock, turning the offset fields from
   prompts (14F rung 5) back into sends. **Plan:**
   `guide/segment_14G_scheduled_email.md` (a draft, 2026-11-05); Item 1 can be built now,
   Items 2–4 wait on IT. See also
   `guide/no_scheduling_fallback.md`. A shared mailbox under an app-wide
   permission is a credential every mounted app could reach: plan one
   per app, or rule a shared one accepted (`guide/interoperability.md` §2).
   **Switching `RRW_SCHEDULED_SEND` on** (14E rung 0) would fire every
   reminder already past due on every open session in one pass, after
   operators may have reminded by hand: 14G marks those skipped, not
   sent, when it turns the setting on.

3. **22J — The Setup routes' shared handler** (opened 2026-11-06, the
   assessments' carried move). One body for what the four Setup roster
   route modules repeat (bulk actions, delete all, dismiss, field labels,
   self fields), and Observers' and Relationships' imports onto
   `roster_import._handle_import`; no behavior change. Independent of 14C
   and 14G. **Plan:** `guide/segment_22J_setup_routes_shared_handler.md`.

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

### Sequencing notes

- **The email pipeline:** 14F (closed) sends by hand; 14G adds mail on
  14E's clock, and 14C's Email settings card is read by both.
- **20** is independent of the email pipeline but gated on the
  deployment, so it does not interleave with other work.
