# Reviewer page map

> **Note (2026-05-03):** Sections referencing the operator chrome
> (which reviewer pages share) and the standalone
> `/operator/sessions/{id}/preview` surface overlap with
> `spec/visual_style_rrw.md` and `spec/preview_hub.md` respectively.
> Those two files are now authoritative for the areas they cover.
> Reviewer-facing chrome specifically is documented in
> `spec/visual_style_rrw.md` "Reviewer-facing pages". Where this
> file disagrees with either, the newer spec wins. A reconciliation
> pass is pending.

Specification of the reviewer-facing page surface — the pages a
signed-in reviewer sees when they follow an invitation link or
visit `/reviewer` directly. Sibling to `spec/operator_map.md`
(operator-facing surface). For per-route detail with template
paths, form fields, and audit events, see `docs/status.md`'s
"Reviewer-facing app" URL table.

The reviewer surface is intentionally minimal — three pages
total, built to prioritise legibility on the table view since
that's where reviewers spend ~all of their time.

## Cross-page conventions

Reviewer pages render the same chrome as operator pages
(documented in `spec/operator_map.md` "Cross-page conventions"):

- **App identity (top left)** linking to `/about`.
- **User card (top right)** with "Signed in as {user name}" and
  a Sign out button posting to `/.auth/logout`.
- **Breadcrumb trail** rooted at `Reviewer` → `/reviewer`. On
  `/reviewer` itself the trail is the single non-link label
  `Reviewer`. On `/reviewer/sessions/{id}` it reads
  `Reviewer → {session.name}`.
- **Page title** as the page H1, below the breadcrumb.

There is no setup-nav on reviewer pages — the surface is too
small to warrant one. Navigation is just breadcrumb + per-page
links.

### Identity matching

A signed-in user is matched to `Reviewer` rows by case-insensitive
email equality (`casefold()` both sides). Only `Reviewer` rows
with `status == "active"` are visible. Both rules are enforced in
`app/services/responses.py::reviewer_sessions_for_user` and the
per-session lookup that drives the surface.

## `/reviewer` — Dashboard

Lists every session the signed-in user is an active reviewer on,
with a per-session progress pill.

- **Table** with one row per session. Columns:
  - **Session** — `<a>` to `/reviewer/sessions/{id}`.
  - **Deadline** — ISO timestamp, or `—` if unset.
  - **Status** — pill (`not started` / `in progress` /
    `submitted`) computed from the reviewer's `Response` rows;
    plus a muted `(completed_rows / total_assignments)` count.
- **Empty state** — when the user has no active reviewer rows in
  any session, render a single muted card stating "You don't have
  any review sessions assigned to your account ({user.email})."

The pill state machine, computed by
`app/services/responses.py::session_pill_for_reviewer`:

- **submitted** — every required field on every assignment has
  a `Response.submitted_at` timestamp.
- **in progress** — at least one `Response` row exists but
  `submitted` doesn't apply.
- **not started** — no `Response` rows exist.

The "Edit / Re-submit" affordance lives on the surface itself
(below) — submitting once doesn't lock the form.

## `/reviewer/sessions/{id}` — Review surface

The reviewer's primary working page. One **tabular response
artifact** per instrument the reviewer is assigned on, stacked.

Page sections, in DOM order:

1. **H1** — session name.
2. **Optional description** + ISO deadline as muted text.
3. **Flash banners** (mutually compatible, all may render):
   - `?saved=ok` — green "Your draft has been saved."
   - `?submitted=ok` — blue "Your responses have been submitted.
     You can keep editing and re-submit if needed."
   - **Required-fields-missing card** — yellow card listing
     `(reviewee_name, field_label)` pairs from the most recent
     submit attempt; renders only when the prior POST refused
     for missing-required-without-acknowledge.
4. **No-longer-accepting banner** — yellow card shown when the
   session/instrument gates have closed. Two variants:
   - "Your previously saved values remain visible below in
     read-only form." (operator left visibility on)
   - "Your previously saved values are hidden by the operator's
     visibility setting." (operator turned visibility off)
5. **Cancel card** — single Primary Outline anchor "Cancel —
   discard unsaved edits" → re-fetches `GET /reviewer/sessions/{id}`
   without the form re-submit. Hidden when the session is no
   longer accepting and in preview mode.
6. **Per-instrument table** (one per instrument the reviewer is
   assigned on, in DOM order):
   - **H2 section heading** from `Instrument.description`
     (fallback to system handle).
   - **Help block** (`<dl class="help-block">`) above the table
     listing each response field's `help_text` whose
     `help_text_visible=true`.
   - **Table** wrapped in `.table-scroll`. Columns:
     - **Reviewee** (always-first, mandatory): name in bold,
       email/identifier in `<code>` beneath.
     - **Display fields** (in the operator-configured order),
       each rendered per the field's source. `profile_link`
       cells render as plain `<a href>` to the URL value.
     - **Response fields** (in stored `order`), each rendered
       per `response_type`:
       - `long_text` → `<textarea rows="2">`.
       - `integer` → `<input type="number">` with optional
         `min`/`max` from `validation`.
       - `yes_no` → `<select>` with empty / `yes` / `no`.
       - `short_text` (and any unknown type) → `<input type="text">`.
       Required fields get a trailing `*` in the column header.
       When the assignment isn't accepting, every input renders
       `disabled`.
     - **Status indicator** column (1% width): green ✓ when the
       row is complete, yellow ⚠ when missing-required after a
       submit acknowledge, plus a muted "submitted YYYY-MM-DD HH:MM"
       stamp when `submitted_at` is set.
7. **Action row** (when accepting and not preview mode):
   - **Save draft** (Primary Outline) — posts to `…/save`.
   - **Submit** (Primary) — posts to `…/submit` via
     `formaction=`.
   - When the prior submit raised missing-required, a checkbox
     "I acknowledge required fields are missing — submit anyway."
     appears below.
8. **Clear-all card** (red border, when accepting and not preview):
   - Confirm checkbox: "Yes, delete every response I have saved
     for this session. This also clears my submitted state."
   - **Clear all** button — currently uses an inline-style red
     fill, will migrate to `.btn.danger-solid` (see
     `spec/assumptions.md`'s danger-zone migration note).

### Save / Submit / Clear semantics

- **Save**: upserts `Response` rows in `(assignment, response_field)`
  shape. Empty value deletes the row; absence == empty answer.
  Never touches `submitted_at`. 303 → surface with `?saved=ok`.
- **Submit**: persists pending writes, then validates required
  fields. Missing-required-without-acknowledge re-renders this
  page at HTTP 400 with the `missing` card and an
  `acknowledge_missing` checkbox. Missing-required-with-acknowledge
  stamps `submitted_at` and writes audit. Editing a previously-
  submitted required field to empty deletes the row (including
  its `submitted_at`), flipping the dashboard pill back to
  `in progress` next render.
- **Clear**: confirm-checkbox-required action that deletes
  every `Response` row for this reviewer in this session. No
  partial undo.
- **Cancel**: plain `<a>` link back to the surface; no DB
  write, no audit. Discards in-progress edits by re-fetching
  saved values.

### Lifecycle gating

Reviewer save / submit / clear return **HTTP 403** unless the
session is `ready`, the assignment's instrument is
`accepting_responses`, and `now() < session.deadline`. When the
gate is closed, the surface still renders but every input is
`disabled` and the action row + Clear-all card are suppressed.
Saved values are hidden unless the operator turned on
`responses_visible_when_closed` for that instrument. Deadline
closure is observed lazily on every reviewer GET / POST and on
the operator's instruments page; the first observer flips
`accepting_responses=false`, stamps `Instrument.deadline_closed_at`,
and emits one `instrument.closed reason=deadline` audit event.

### Preview mode

When the operator hits `/operator/sessions/{id}/preview`, the
same `review_surface.html` template renders with `preview_mode=True`:

- Top banner reads "**Preview** — not visible to reviewers. This
  page is operator-only and bypasses session-status / deadline /
  acceptance gates."
- The `<form>` wrapper is replaced by a plain `<div>` so no
  `formaction=` can re-target a write endpoint.
- Save / Submit / Clear / Cancel are suppressed.
- Up to three real assignments render first (by `Assignment.id`
  ascending); fewer than three are padded with synthetic
  placeholders (`Sample Reviewee 1/2/3`,
  `sample1@example.edu`, per-source sample values).
- Read-only: emits no audit events and skips the deadline-
  observation lazy-close side-effect.

See `spec/operator_map.md` "/operator/sessions/{id}/preview" for
the operator-side spec of the entry point.

## `/reviewer/invite/{token}` — Invitation landing

Token redemption + identity check. Lookup is by SHA-256 hash;
the raw token is never persisted, only mailed.

Behavior:

1. Easy Auth must be signed in (otherwise the platform
   redirects to sign-in and back).
2. Look up the invitation by `sha256(token)`.
3. **Email match check** — case-insensitive comparison of the
   signed-in email against `Invitation.reviewer_email`. On
   mismatch, render `invite_mismatch.html` (HTTP 403, see below).
4. On match, stamp `Invitation.opened_at` once (idempotent on
   subsequent visits), emit `invitation.opened` audit event,
   and 303 → `/reviewer/sessions/{id}`.

### Invitation-mismatch page

A single red-bordered card that explains the email mismatch
and offers two Primary Outline links: "Sign-in details"
(`/me/debug`) and "Your reviewer dashboard" (`/reviewer`). The
operator's preferred remedy is to sign out and sign back in
with the invited account.

This is the only reviewer-side page that returns a non-200 status
under normal flow.

## What's deliberately not yet here

| Capability | Lands in |
|---|---|
| Per-row autosave (vanilla JS over the `/save` endpoint) | Follow-on PR after Segment 8 |
| Per-reviewee progress on the operator monitoring page | Not yet planned |
| Magic-link invitations (no Easy Auth required) | **Segment 16** |
| Real SMTP (production sending, not the dev outbox) | **Segment 15** |

See `docs/status.md` "What's deliberately not yet there" for the
full project-wide list.
