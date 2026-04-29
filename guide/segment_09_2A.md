# Segment 9.2A Implementation Plan — Invitations, dev outbox, reviewer-access tokens

**Status:** Implementation plan for Segment 9.2 (single PR). Segment 9 is split
into three PR-sized blocks: **9.1**, **9.2**, **9.3**. This file is the A-plan
for 9.2 only.

## 9.2 outcome

Deliver one PR that gives operators a way to issue per-reviewer invitation
tokens, "send" them via a developer-visible outbox table (no real SMTP),
and let reviewers follow the token URL into the existing review surface
(Easy Auth sign-in still required).

---

## Decisions locked for 9.2

### Generation trigger
1. **Explicit operator action.** No auto-generation on activation. A
   "Generate invitations" button on a new `/operator/sessions/{id}/invitations`
   sub-page creates Invitation rows for every reviewer with at least one
   `include=true` assignment who does not yet have one. Idempotent: clicking
   it twice does not duplicate rows or re-send.
2. All invitation actions (generate / send / regenerate / resend) require
   `session.status == "ready"` and return **HTTP 409** otherwise — so emailed
   links never point at a draft session.

### Lifecycle states
3. `Invitation.status` values used in 9.2: `pending`, `sent`, `opened`.
   `revoked` / `expired` are deferred. Transitions:
   - `pending` — row created by generate; no outbox row yet.
   - `sent` — outbox row written; `Invitation.sent_at` stamped.
   - `opened` — reviewer first followed the token URL; `Invitation.opened_at`
     stamped (one-shot — repeat visits do not re-stamp or change state).

### Tokens
4. Token = `secrets.token_urlsafe(32)`. Stored as `sha256` of the raw token
   in `Invitation.token_hash` (already in schema). Raw token is shown to the
   operator at the moment the outbox row is written (and persisted in the
   outbox row's body so the operator can re-copy the link). No expiry beyond
   the existing session/instrument deadline gates from 9.1.
5. Token URL: `/reviewer/invite/{token}`. The route requires Easy Auth
   sign-in (existing dependency), looks up the invitation by token hash, and:
   - If not found → **404**.
   - If signed-in user's email casefold-equals the invitation's
     `Reviewer.email` casefold → stamp `opened_at` (only on first hit; status
     `pending` or `sent` → `opened`), then **303** to
     `/reviewer/sessions/{id}`.
   - If signed-in user's email differs → **403** with a dedicated
     "This invitation belongs to someone else" page.

### Re-activation idempotency
6. After a `revert → edit → activate` cycle, the operator clicks "Generate
   invitations" again. For reviewers who already have an Invitation row, the
   row is **reused untouched** (token + state preserved). New reviewers get
   fresh invitations. This is the cheapest path and avoids invalidating
   already-distributed tokens. Operator can use "Regenerate" per-row to
   force-rotate a token.

### Outbox table
7. New table `email_outbox`:
   ```
   id              integer pk
   session_id      fk → sessions
   reviewer_id     fk → reviewers (nullable for future broadcast kinds)
   invitation_id   fk → invitations (nullable; future kinds)
   kind            string(32)  -- 'invitation' (9.2); 'reminder' reserved
   to_email        string(320)
   subject         string(255)
   body            text         -- includes the raw token URL for invitations
   status          string(32)   -- 'queued' | 'sent'  (sync-flips to 'sent' in 9.2)
   created_at      timestamptz default now
   sent_at         timestamptz nullable
   ```
   In dev mode, "send" is synchronous: write the row with `status='queued'`
   then immediately flip to `status='sent'` and stamp `sent_at`. Real SMTP
   is deferred (Segment 15). The outbox view is per-session at
   `/operator/sessions/{id}/outbox`.

### Operator invitation surface
8. New page `GET /operator/sessions/{id}/invitations` shows a table:
   - reviewer name + email
   - invitation status pill (`pending` / `sent` / `opened`)
   - `sent_at`, `opened_at`
   - per-row actions: `Regenerate` (rotate the token, reset to `pending`,
     no outbox write), `Send` (write a new outbox row, flip to `sent`)
   - bulk action at the top: `Generate invitations` (idempotent; only does
     anything when there are reviewers without invitations) and
     `Send to all pending` (writes outbox rows for every `pending` row).
9. New page `GET /operator/sessions/{id}/outbox` shows the per-session
   outbox table with timestamps and the rendered email body (including the
   raw token URL) for inspection / copy.

### Email body
10. Plain text. Two-line template:
    ```
    You've been invited to review for: {session_name}.
    Open this link (sign in with your work email): {invite_url}
    ```
    `invite_url` is built via `request.url_for("reviewer_invite", token=...)`
    so it's absolute under the deployed host. We do not embed any
    HTML/styling for 9.2.

### Audit events (new)
11. `invitations.generated` — `detail = {count, reviewer_ids}`.
12. `invitation.sent` — `detail = {invitation_id, reviewer_id, outbox_id}`.
13. `invitation.opened` — `detail = {invitation_id, reviewer_id}`.
14. `invitation.regenerated` — `detail = {invitation_id, reviewer_id}`.

---

## Implementation slices

### Slice 1 — Schema + migration
- New Alembic migration adding the `email_outbox` table.
- No change to `invitations` (columns already exist).

### Slice 2 — Domain service
- New module `app/services/invitations.py` with:
  - `generate_invitations(db, session, user, *, correlation_id)` — idempotent
    bulk-create.
  - `regenerate_token(db, invitation, user, *, correlation_id)` — rotate
    `token_hash`, reset status to `pending`, return raw token.
  - `send_invitation(db, invitation, user, *, request, correlation_id)` —
    write outbox row + flip invitation to `sent` + stamp `sent_at`.
  - `record_open(db, invitation)` — first-hit stamps `opened_at` and flips
    to `opened`.
  - Helper `hash_token(raw)` (sha256 hex).
  - Token URL builder (uses `request.url_for`).

### Slice 3 — Routes
- `GET /operator/sessions/{id}/invitations` — list + actions form.
- `POST /operator/sessions/{id}/invitations/generate` — bulk-create.
- `POST /operator/sessions/{id}/invitations/{invitation_id}/regenerate`.
- `POST /operator/sessions/{id}/invitations/{invitation_id}/send`.
- `POST /operator/sessions/{id}/invitations/send-all` — convenience for all
  `pending`.
- `GET /operator/sessions/{id}/outbox` — outbox table view.
- `GET /reviewer/invite/{token}` — token landing.
- All operator invitation routes gated on `status == ready` (9.1 helper).

### Slice 4 — Templates
- `operator/session_invitations.html`
- `operator/session_outbox.html`
- `reviewer/invite_mismatch.html` (403 page for email mismatch)
- Link the new invitations page from `session_detail.html`.

### Slice 5 — Audit
- Wire the four new audit events from the service layer.

### Slice 6 — Tests (~12)
1. Generate creates one row per assigned active reviewer; idempotent on
   second click.
2. Generate is 409 while session is `draft`.
3. Regenerate rotates `token_hash` and resets status → `pending`.
4. Send writes an outbox row, flips invitation to `sent`, stamps
   `sent_at`, audit event.
5. Send-all writes one outbox row per `pending` row.
6. Token URL with correct signed-in email stamps `opened_at` and 303s to
   the reviewer surface.
7. Token URL repeat-visit does not re-stamp `opened_at`.
8. Token URL with mismatched signed-in email returns 403 + mismatch page.
9. Token URL with unknown token returns 404.
10. After revert + reactivate, generate is a no-op for reviewers who
    already have invitations and creates new ones for newly-added
    reviewers.
11. Outbox view renders the rendered token URL for an `invitation`
    outbox row.
12. Audit events `invitations.generated`, `invitation.sent`,
    `invitation.opened`, `invitation.regenerated` written with correct
    detail.

---

## Out of scope (explicitly deferred)
- Reminder generation/sending (9.3).
- Monitoring dashboard (9.3).
- Real SMTP backend / production email hardening (Segment 15).
- Magic-link / anonymous-token sign-in (Segment 16).
- Revoke / expire invitation actions.
- Bulk CSV-style export of token URLs.

## Docs to update at PR time
- `docs/status.md`: list Segment 9.2 row, new endpoints, new audit events,
  new `email_outbox` table, the token URL flow.
- `ARCHITECTURE.md`: short paragraph on invitation tokens (sha256-hashed
  storage, raw token shown in dev outbox, Easy Auth still required).
- `AGENTS.md`: bump "Current stage" to "Segments 1–8, 9.1, 9.2 complete."
