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

**Order (author, 2026-11-06):** 14G when IT answers. 23C is open
(author, 2026-11-11) and runs beside it.

1. **14G — Scheduled email** (gated on IT: offline sending as the
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

2. **23C — Interoperability: status as Review Robin reports it** (author,
   2026-11-11). The handoff status carries Review Robin's own readings
   (status row, schedule, validation, instruments, progress, per person)
   for the diagnostic Utilities tool. **Plan:**
   `guide/segment_23C_diagnostic_status.md`.

### Stubs

Small items with no plan doc; each fits one PR and its reasoning fits
the PR body unless it says otherwise. None open.

### Sequencing notes

- **The email pipeline:** 14F (closed) sends by hand; 14G adds mail on
  14E's clock and makes 14C's waiting report rows live.
- **20** is independent of the email pipeline but gated on the
  deployment, so it does not interleave with other work.
