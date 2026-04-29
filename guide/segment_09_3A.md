# Segment 9.3A Implementation Plan — Monitoring + reminders

**Status:** Implementation plan for Segment 9.3 (single PR). Segment 9 is split
into three PR-sized blocks: **9.1**, **9.2**, **9.3**. This file is the A-plan
for 9.3 and closes out Segment 9.

## 9.3 outcome

Deliver one PR that gives operators a session-level monitoring page (summary
+ per-reviewer progress) and a "send reminder to incomplete reviewers"
workflow that reuses the invitation tokens issued in 9.2.

---

## Decisions locked for 9.3

### Monitoring page
1. New page `GET /operator/sessions/{id}/monitoring` with two regions:
   - **Summary header counts**: `assigned reviewers`, `invited`, `opened`,
     `submitted`, `incomplete`.
   - **Per-reviewer table**: name + email, invitation status pill
     (`pending`/`sent`/`opened`), `# assignments`, `# completed`,
     `# missing required`, `last_reminder_at`, per-row "Send reminder"
     button.
   - Per-reviewee progress is **deferred** (matches seg9stuff decision).
2. Linked from `session_detail.html` alongside the existing Invitations and
   Outbox links.

### "Incomplete" definition
3. A reviewer is **incomplete** iff at least one of their `include=true`
   assignment rows has any of:
   - a required field with no `Response` row (or empty value), **or**
   - a `Response` row whose `submitted_at IS NULL`.

   "Submitted" (the inverse) means: every required field on every assigned
   row has a non-empty `Response` AND every relevant `Response` row carries
   `submitted_at`. Already computed by `responses_service.session_pill_for_reviewer`
   — reuse it.
4. Reminder targeting includes everyone classified as incomplete: never
   opened, opened-but-not-submitted, and submitted-with-warn-override that
   still has missing required fields.

### Reminder send
5. Reminders **reuse** the URL from the most recent outbox row on the same
   `Invitation` (the raw token URL is stored verbatim in `email_outbox.body`
   from 9.2). The token is **not** rotated.
6. If no outbox row exists for the invitation yet (operator never sent the
   original invitation), the reminder action **falls back to a fresh send** —
   it rotates the token, writes a brand-new invitation outbox row, and the
   row is logged with `kind='invitation'` (not `reminder`). This collapses
   "no prior delivery" into the standard send path, so the operator's intent
   ("get this reviewer their link") always results in a deliverable
   message.
7. Reminder actions are operator-paced: per-row `Send reminder` button **and**
   bulk `Send reminders to incomplete reviewers` button at the top of the
   monitoring page.
8. **No throttle.** Operator decides cadence. The page surfaces
   `Invitation.last_reminder_at` so the operator can see what they've sent.

### Email body
9. Plain text, two-line:
   ```
   Reminder — your review for {session_name} isn't complete yet.
   Open this link (sign in with your work email): {invite_url}
   ```
   Subject: `Reminder: review for {session_name}`. The `{invite_url}` is
   pulled from the existing outbox row and kept verbatim.

### Outbox + audit
10. Reminder rows go into the existing `email_outbox` table with
    `kind='reminder'`, same `queued → sent` synchronous flip, visible in the
    existing per-session outbox view (no separate page).
11. New audit event: `reminders.sent` (batch). `detail = {count,
    invitation_ids, reviewer_ids}`. No per-row event in 9.3.

### Lifecycle gating
12. All reminder actions require `session.status == "ready"` (HTTP **409**
    otherwise) — consistent with 9.1/9.2 invitation gates so reminder
    emails never point at a draft session.

---

## Implementation slices

### Slice 1 — Service additions (`app/services/invitations.py`)
- `most_recent_invitation_url(db, invitation_id) -> str | None` — extracts
  the `/reviewer/invite/{token}` URL from the most recent
  `kind='invitation'` outbox body for that invitation, returns None if
  none.
- `send_reminder(db, invitation, review_session, reviewer, user, request,
  correlation_id)` — fetches the existing URL; if absent, internally calls
  `send_invitation` (fresh token, kind='invitation' row); else writes a
  `kind='reminder'` outbox row with the existing URL, stamps
  `Invitation.last_reminder_at`. Returns the outbox id and a flag noting
  whether it fell back to a fresh send.
- `send_reminders_to_incomplete(db, review_session, user, request,
  correlation_id) -> ReminderBatchResult` — iterates reviewers classified
  incomplete, calls `send_reminder` per row, emits a single
  `reminders.sent` audit event with the batch detail.

### Slice 2 — Monitoring queries (`app/services/monitoring.py` — new module)
- `class ReviewerProgress`: dataclass with `reviewer`, `invitation`,
  `assignment_count`, `completed_count`, `missing_required_count`,
  `is_incomplete`, `last_reminder_at`, `pill_state` (reuses
  `session_pill_for_reviewer`).
- `summary_counts(db, session) -> dict` and
  `per_reviewer_progress(db, session) -> list[ReviewerProgress]`.

### Slice 3 — Routes (in `app/web/routes_operator.py`)
- `GET /operator/sessions/{id}/monitoring`.
- `POST /operator/sessions/{id}/invitations/{iid}/remind` — single-row
  reminder.
- `POST /operator/sessions/{id}/monitoring/remind-incomplete` — bulk
  reminder.
- All require `_require_ready` (re-using the helper from 9.2).

### Slice 4 — Templates
- `operator/session_monitoring.html` — summary + per-reviewer table.
- Link from `session_detail.html`.

### Slice 5 — Tests (~10) in `tests/integration/test_monitoring.py`
1. Monitoring page renders summary counts (assigned/invited/opened/submitted/incomplete).
2. Monitoring page lists each invited reviewer with their status pill +
   completion counts.
3. Per-reviewer reminder POST sends a `kind='reminder'` outbox row whose
   body contains the same URL as the prior invitation outbox body
   (token NOT rotated).
4. Per-reviewer reminder for an invitation with no prior outbox row falls
   back to a fresh send: writes `kind='invitation'` outbox, rotates token.
5. Bulk `remind-incomplete` targets only incomplete reviewers (skips fully
   submitted ones).
6. Bulk reminder writes one `reminders.sent` batch audit event with
   `detail.count` matching the number of reminders sent.
7. Bulk + per-row reminders both stamp `Invitation.last_reminder_at`.
8. Reminder actions return **409** while session is `draft`.
9. Submitted-with-missing-required-override is classified as incomplete
   (still receives a reminder).
10. Bulk reminder in a session with zero incomplete reviewers writes no
    outbox rows and no audit event.

---

## Out of scope (explicitly deferred)
- Per-reviewee monitoring view.
- Charts / advanced analytics.
- Reminder throttle / scheduling.
- Reminder text customisation per session.
- Real SMTP backend (Segment 15).

## Docs to update at PR time
- `docs/status.md`: mark 9.3 shipped, add monitoring + reminder endpoints,
  add `kind='reminder'` outbox row, add `reminders.sent` audit event.
- `ARCHITECTURE.md`: short paragraph noting reminders reuse URLs from the
  outbox (no token rotation) and the fallback-to-fresh-send semantics.
- `AGENTS.md`: bump "Current stage" to "Segments 1–8 and 9 complete."
