# Operator page map

A snapshot of every HTML page an operator can land on, derived from
`app/web/routes_operator.py` and `app/web/templates/operator/`. All pages
extend `app/web/templates/base.html`, which renders a topbar with a
"Review Robin Web" home link (→ `/operator/sessions`), the signed-in
user's name/email, and a sign-out link to `/.auth/logout`.

Routes that only accept `POST` (form submissions, lifecycle actions,
deletions) are not pages — they redirect on success and are listed under
each page that posts to them.

## Site structure (operator-facing pages only)

```
/operator/sessions                                   Sessions list
└── /operator/sessions/new                           New session form
└── /operator/sessions/{id}                          Session detail (hub)
    ├── /operator/sessions/{id}/edit                 Edit session form
    ├── /operator/sessions/{id}/validate             Setup validation + activate
    ├── /operator/sessions/{id}/reviewers            Reviewers list (Manage)
    │   └── /operator/sessions/{id}/reviewers/import Reviewer CSV import
    ├── /operator/sessions/{id}/reviewees            Reviewees list (Manage)
    │   └── /operator/sessions/{id}/reviewees/import Reviewee CSV import
    ├── /operator/sessions/{id}/assignments          Assignments hub
    │   ├── (preview) FullMatrix dry-run             rendered after POST
    │   └── (preview) Manual CSV dry-run             rendered after POST
    ├── /operator/sessions/{id}/instruments/{iid}    Instrument detail
    ├── /operator/sessions/{id}/invitations          Invitations index
    └── /operator/sessions/{id}/outbox               Dev email outbox
```

---

## `GET /operator/sessions` — Sessions list
Template: `operator/sessions_list.html`

- H1: "Your sessions".
- "Create session" button → `/operator/sessions/new`.
- If sessions exist: table with columns **Name** (linked to session
  detail), **Code**, **Status**, **Deadline** (ISO or "—"),
  **Created** (`YYYY-MM-DD`).
- If no sessions: empty-state card with a prompt to use **Create
  session**.

## `GET /operator/sessions/new` — New session form
Template: `operator/session_new.html`

- H1: "New session".
- Form `POST /operator/sessions` with fields:
  - `name` (text, required, max 255)
  - `code` (text, required, max 64)
  - `description` (textarea, optional, max 2000)
  - `deadline` (`datetime-local`, optional; parsed as ISO-8601 server-side)
- Buttons: **Create session** (submit), **Cancel** → sessions list.

## `GET /operator/sessions/{id}` — Session detail (hub)
Template: `operator/session_detail.html`

The session's home page; flow gates differ by `is_draft` / `is_ready`.

- Back link → `/operator/sessions`.
- H1: session name.
- **Details** card:
  - Status pill ("ready" pill-info, otherwise the raw status as
    pill-warning), code, deadline, description.
  - If ready: muted note that setup is locked, revert to draft to edit.
  - If not ready: **Edit details** button → `/operator/sessions/{id}/edit`.
- **Setup** card — list of:
  - Reviewers count + **Manage** (`/reviewers`) + **Import / Replace
    CSV** (`/reviewers/import`).
  - Reviewees count + **Manage** (`/reviewees`) + **Import / Replace
    CSV** (`/reviewees/import`).
  - Instruments — links per-instrument to
    `/instruments/{iid}` with an "open" / "closed" pill.
  - Assignments count, mode pill (when set), **Manage / Generate** link
    → `/assignments`.
  - Action buttons: **Run setup validation**, **Validate & activate**
    (only when draft, anchors to `#activate`), **Invitations**.
- **Revert to draft** card (only when `is_ready`):
  - Confirm checkbox + amber **Revert to draft** button →
    `POST /operator/sessions/{id}/revert`.
- **Existing-responses warning** banner (when `has_responses` and
  `is_draft`): explains that further edits may discard responses.
- **Danger zone** card:
  - When ready: locked message, must revert first.
  - When draft: confirm checkbox + red **Delete session** →
    `POST /operator/sessions/{id}/delete`.

## `GET /operator/sessions/{id}/edit` — Edit session
Template: `operator/session_edit.html`

- Back link → session detail.
- H1: "Edit session".
- Same fields as the new-session form, pre-filled from the session.
- Submit `POST /operator/sessions/{id}/edit`. Server requires draft and
  may require `acknowledge_response_loss=true` if responses exist
  (currently no checkbox in the form — POST will 400 in that case).
- Buttons: **Save changes**, **Cancel** → session detail.

## `GET /operator/sessions/{id}/validate` — Setup validation
Template: `operator/session_validate.html`
Partial: `operator/partials/validation_results.html`

- Back link → session detail.
- H1: "Setup validation".
- Read-only summary pills: **N errors**, **N warnings**, **N info**.
- Issues card (from partial), grouped by `source` (e.g. session,
  reviewers, reviewees, assignments). Each row shows a severity pill,
  optional **Row N** + field code, and the message.
- **Activate session** card (anchor `#activate`):
  - If already ready: muted note pointing to revert flow.
  - If not draft and not ready: muted "activation not available".
  - If draft and `can_activate`: form `POST .../activate`.
    - Shows an "I have reviewed the warnings/info and want to activate
      anyway" confirm checkbox when there are non-blocking findings.
    - **Activate session** submit + muted note that activation opens
      every instrument.
  - If draft but errors block: muted "Cannot activate while N errors
    remain".

## `GET /operator/sessions/{id}/reviewers` — Reviewers list (Manage)
Template: `operator/session_reviewers.html`

- Back link → session detail.
- H1: "Reviewers".
- Header card: count + **Import / Replace CSV** link.
- Table (only if reviewers exist) with columns **Name**, **Email**,
  **Status**, and **Tags** (only when any reviewer has tag_1/2/3).
  Tag column shows up to three numbered tags.
- Empty state: muted "No reviewers yet."
- **Danger zone** card (when reviewers exist):
  - Confirm checkbox + red **Delete all reviewers** →
    `POST /operator/sessions/{id}/reviewers/delete-all`. Server also
    requires `acknowledge_response_loss=true` when responses exist
    (no checkbox surfaced; will 400 in that case).

## `GET /operator/sessions/{id}/reviewers/import` — Reviewer CSV import
Template: `operator/session_import_reviewers.html`

- Back link → session detail.
- H1: "Import reviewers".
- Format note: required `ReviewerName`, `ReviewerEmail`; optional
  `ReviewerTag1/2/3`; UTF-8, max 5000 rows.
- Validation results partial (issues from the most recent upload, if any).
- Form `POST .../reviewers/import` (multipart):
  - File input (`.csv`).
  - When `existing_count > 0`: amber replace-warning card listing how
    many reviewers (and assignments) will be wiped, plus a required
    `confirm_replace=true` checkbox.
  - Buttons: **Upload**, **Cancel** → session detail.
- On invalid/blocked uploads the same template re-renders inline with
  issues at HTTP 400; on success it redirects to session detail.

## `GET /operator/sessions/{id}/reviewees` — Reviewees list (Manage)
Template: `operator/session_reviewees.html`

- Back link → session detail.
- H1: "Reviewees".
- Header card: count + **Import / Replace CSV** link.
- Table (only if reviewees exist) with columns **Name**, **Email /
  Identifier**, **Status**, plus **Photo** (only when any reviewee has
  a `profile_link`, rendered as a "link" anchor) and **Tags** (only
  when any tag is set).
- Empty state: muted "No reviewees yet."
- **Danger zone** card (when reviewees exist): confirm checkbox + red
  **Delete all reviewees** → `POST .../reviewees/delete-all`. Same
  acknowledge-response-loss server gate as reviewers.

## `GET /operator/sessions/{id}/reviewees/import` — Reviewee CSV import
Template: `operator/session_import_reviewees.html`

- Back link → session detail.
- H1: "Import reviewees".
- Format note: required `RevieweeName`, `RevieweeEmail`; optional
  `PhotoLink`, `RevieweeTag1/2/3`; UTF-8, max 5000 rows.
- Same validation partial + replace-warning + upload flow as the
  reviewer import.

## `GET /operator/sessions/{id}/assignments` — Assignments hub
Template: `operator/session_assignments.html`

- Back link → session detail.
- H1: "Assignments".
- **Current state** card: total assignment count + mode pill,
  reviewer/reviewee counts.
- **Current pairs** card (when pairs exist): table with **Reviewer**,
  **Reviewee**, **Include** (yes/no) and a **Context** column when any
  pair has `pair_context_*` or `assignment_context_*`. Up to
  `assignments.PAIR_PREVIEW_LIMIT` rows; muted "Showing first N of M".
- If reviewer or reviewee count is zero: amber warning with shortcut
  buttons to import reviewers / reviewees.
- Otherwise two generator cards:
  - **FullMatrix** — `exclude_self_review` checkbox (default checked),
    submit posts `dry_run=true` to
    `POST .../assignments/full-matrix`, which returns the FullMatrix
    preview page.
  - **Manual CSV** — file input, dry-run posts to
    `POST .../assignments/manual/import`, returning the manual preview
    page. Format note: required `ReviewerEmail`, `RevieweeEmail`;
    optional `IncludeAssignment`, `AssignmentContext1/2/3`.
- **Danger zone** card (when assignments exist): confirm checkbox + red
  **Delete all assignments** → `POST .../assignments/delete-all`.

## (preview) FullMatrix dry-run
Template: `operator/assignments_preview_full_matrix.html`
Reached by `POST .../assignments/full-matrix` with `dry_run=true` (or
when an unconfirmed replace was attempted).

- Back link → assignments hub.
- H1: "Preview: FullMatrix".
- Red "Replace not confirmed" banner when `missing_confirm`.
- **Will generate** card: total, reviewers covered (`x / y`), reviewees
  covered, self-reviews excluded count (when applicable), and muted
  lists of any uncovered reviewers / reviewees.
- **Pairs** card (when sample available): table of `Reviewer` /
  `Reviewee`, with truncation note.
- Confirm form `POST .../assignments/full-matrix` (no `dry_run`) with:
  - Hidden `exclude_self_review` carrying the prior choice.
  - Amber replace card + required `confirm_replace=true` checkbox when
    `needs_confirm_replace`.
  - **Confirm and generate** button, **Cancel** → assignments hub.

## (preview) Manual CSV dry-run
Template: `operator/assignments_preview_manual.html`
Reached by `POST .../assignments/manual/import` with `dry_run=true` or
when a real save needs confirmation / has blocking issues.

- Back link → assignments hub.
- H1: "Preview: Manual CSV (filename)".
- Red "Replace not confirmed" banner when `missing_confirm`.
- Red "Blocking errors" banner when `is_blocked`.
- **Issues** card with severity pills, row numbers, fields, messages.
- When not blocked:
  - **Will save** card: total, plus excluded `include=false` count.
  - **Pairs** card (when sample available): table with **Reviewer**,
    **Reviewee**, **Include**, **Context** (P1–P3 pair context, A1–A3
    assignment context).
  - **Save** card with file input (must re-upload), optional amber
    replace-confirm, **Save** + **Cancel** buttons.

## `GET /operator/sessions/{id}/instruments/{iid}` — Instrument detail
Template: `operator/instrument_detail.html`

- Back link → session detail.
- H1: instrument name.
- **Acceptance** card:
  - Status pill (`accepting responses` info / `not accepting` warning).
  - Session deadline display (with note that it auto-closes the
    instrument), or "not set".
  - When `deadline_closed_at` is set: muted "Closed by deadline at …".
  - Single action button:
    - When accepting: **Stop accepting responses** →
      `POST .../instruments/{iid}/close`.
    - When not accepting and session is ready: **Resume accepting
      responses** → `POST .../instruments/{iid}/open`.
    - When not accepting and session is not ready: muted "Activate the
      session before re-opening this instrument."
- **Visibility when closed** card: form posting to
  `.../instruments/{iid}/visibility` with a `visible_when_closed`
  checkbox (controls whether reviewers can see their saved responses
  while the instrument is closed) and a **Save visibility** button.

## `GET /operator/sessions/{id}/invitations` — Invitations index
Template: `operator/session_invitations.html`

- Back link → session detail.
- H1: "Invitations".
- Amber "Session must be ready" banner when not ready.
- Header card with summary numbers:
  - Eligible reviewers (active + ≥1 assignment), without invitation,
    pending send.
  - Buttons:
    - **Generate invitations** (`POST .../invitations/generate`),
      disabled when not ready or `uninvited_count == 0`.
    - **Send all pending** (`POST .../invitations/send-all`), disabled
      when not ready or `pending_count == 0`.
    - **View outbox** → `/operator/sessions/{id}/outbox`.
  - Muted note: each send rotates the token and writes a fresh outbox
    row; reviewers must sign in with their work email.
- Per-invitation table (when `rows` exist) with columns **Reviewer**
  (name + email), **Status** (`pending` / `sent` / `opened` pill),
  **Sent** timestamp, **Opened** timestamp, and per-row buttons:
  - **Send** → `POST .../invitations/{iid}/send`.
  - **Regenerate** → `POST .../invitations/{iid}/regenerate`.
  - Both disabled when session is not ready.
- Empty state: muted "No invitations yet."

## `GET /operator/sessions/{id}/outbox` — Dev email outbox
Template: `operator/session_outbox.html`

- Back link → invitations.
- H1: "Outbox".
- Muted note explaining the dev-mode outbox (no real SMTP; rows flip
  `queued → sent` synchronously when an operator clicks Send).
- Per outbox row, a card with:
  - Kind, recipient `to_email`, status pill (`sent` info, otherwise
    warning), and the `sent_at` timestamp when present.
  - Subject line.
  - Preformatted email body (includes the raw invitation URL).
- Empty state: muted "No outbox rows yet for this session."

---

## POST-only routes (no own page)

These never render a unique page; they only redirect (303) on success
or 4xx with an error detail. They are listed here so the map of
operator HTTP surface is complete.

- `POST /operator/sessions` — create from new-session form, redirects
  to session detail.
- `POST /operator/sessions/{id}/edit` — save edits, redirect to detail.
- `POST /operator/sessions/{id}/delete` — delete session, redirect to
  sessions list.
- `POST /operator/sessions/{id}/activate` — draft → ready.
- `POST /operator/sessions/{id}/revert` — ready → draft.
- `POST /operator/sessions/{id}/reviewers/delete-all`
  / `.../reviewees/delete-all` / `.../assignments/delete-all`.
- `POST /operator/sessions/{id}/instruments/{iid}/open` /
  `/close` / `/visibility`.
- `POST /operator/sessions/{id}/invitations/generate` /
  `/send-all` / `/{iid}/send` / `/{iid}/regenerate`.

## Cross-page conventions

- Every nested page has a single back-link to its parent (session
  detail or the matching index).
- Edit-lock: while a session is `ready`, the operator is funnelled
  through a "Revert to draft" step on session detail before any
  setup-mutating page accepts changes — server enforces this with a
  409.
- Replace + response-loss gating: pages that overwrite rosters,
  assignments, or session details surface an amber "you are about to
  replace N rows" card with a required confirm checkbox; when the
  session has reviewer responses, the server additionally requires an
  `acknowledge_response_loss=true` form field.
- Severity pills: `pill-error` (red), `pill-warning` (amber),
  `pill-info` (blue) are the shared vocabulary used by the validation
  results partial, status badges, and outbox/instrument acceptance
  states.
