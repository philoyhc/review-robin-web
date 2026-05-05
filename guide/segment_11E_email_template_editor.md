# Segment 11E — Operator-editable email template editor

Implementation plan for `unfinished_business.md` #24 — the operator-
facing email template editor at
`/operator/sessions/{id}/setupinvite`. The current page is a stub
("lands in Segment 15"); the underlying `_email_body` /
`_reminder_body` helpers in `app/services/invitations.py` are two
hardcoded plain-text strings. This segment ships the editor + the
merge-field rendering layer so operators can shape their own
invitations and reminders without code changes. **Real SMTP stays
deferred to Segment 15** — this segment only changes the body that
the dev outbox already renders.

## Status

Planning. Sized as **3 PRs** in dependency order (schema → editor
UI → send-side refactor); each independently shippable on top of
`main`.

## Reference

- `guide/unfinished_business.md` #24 — the catalog entry, with the
  decision history (help-contact source, three-options rejected
  alternatives, future-merge-field framing).
- `app/services/invitations.py` — current send path. `_email_body`
  (line 44) and `_reminder_body` (line 386) are the two hardcoded
  helpers; `send_invitation` (line 187), `send_reminder` (line 401),
  and `send_reminders_to_incomplete` (line 467) consume them.
- `app/web/templates/operator/session_setupinvite.html` +
  `setupinvite_stub` route (`routes_operator.py:990`) — the stub
  surface that gets rebuilt.
- `app/db/models/email_outbox.py` — outbox row shape today
  (`to_email` / `subject` / `body`; no CC / BCC).

## Scope

In:

- New columns on `ReviewSession`:
  - `help_contact: Mapped[str | None]` (String(320), nullable) —
    operational help contact for "I have questions about the review
    process." Surfaces in the session create / edit form, on the
    reviewer surface as a small "Questions? Contact X" line, and as
    the `{{help_contact}}` merge field.
  - `email_template_overrides: Mapped[dict | None]` (JSON, nullable)
    — operator overrides keyed by
    `{invitation_subject, invitation_body, invitation_cc,
    invitation_bcc, reminder_subject, reminder_body, reminder_cc,
    reminder_bcc}`. Defaults live in code; `NULL` / missing keys
    fall through to defaults. No separate `email_templates` table;
    1:1 with sessions, no separate lifecycle.
- New editor page at `/operator/sessions/{id}/setupinvite` —
  replaces the stub. Two-half-width-card layout (see "Editor
  surface" below).
- Refactor `_email_body` / `_reminder_body` to render
  `string.Template` substitutions over an override-or-default
  template string. Reviewer row context (`reviewer_name`) injected
  at send time from the `Invitation.reviewer` row.
- Two new audit events: `email_template.updated` and
  `email_template.reset` (per-field), both with a `changes` diff
  shape mirroring `session.updated`.
- The `/setupinvite` setup-nav button label stays "Email Invites"
  (no change). Once the editor ships, `docs/status.md`'s row for
  `/setupinvite` flips from "stub" to its real description.

Out (deferred):

- **Real SMTP** — Segment 15. The dev outbox stays the only sink
  in this segment. Operators see the rendered body in the outbox
  view as today.
- **CC / BCC at send time** — the editor stores them in the
  override JSON but the existing
  `email_outbox` table has only `to_email`. Send-path consumption
  of CC / BCC waits on a follow-on schema change (likely folded into
  Segment 15's SMTP work). Storing them now means the editor stays
  shape-stable across the SMTP cutover.
- **Per-reviewer body customization** (e.g. different copy per
  cohort). Out — overrides are per-session.
- **Operator-defined merge fields** beyond the canonical five
  (`reviewer_name`, `session_name`, `deadline`, `help_contact`,
  `invite_url`). Out — the merge-field set is fixed.
- **Rich text / HTML email bodies.** Bodies stay plain text in this
  segment; `string.Template` over Text columns. Rich text is a
  Segment 15 polish concern.

## Editor surface

Two-card layout in a `.bottom-grid` (matching the session-detail
two-column pattern). Both cards are half-width and stack on the
narrow-viewport breakpoint.

### Left card — `.card.email-composer`

The email-shape preview. Reads top-to-bottom like an email
client's compose pane. Carries the editable fields for the active
template (invitation OR reminder — see "Template selector" below).

Fields, top to bottom:

| Field | Treatment | Notes |
|---|---|---|
| **From** | Read-only display | `Review Robin <noreply@…>`. Static placeholder copy until Segment 15 wires sender identity. |
| **To** | Read-only display | "Sent individually to each reviewer." Per-reviewer email is fetched from the `Reviewer` row at send time; not editable at the template level. |
| **CC** | Editable text input | Comma-separated email addresses. Persists to `{invitation,reminder}_cc`. (Ignored at send time until outbox schema picks them up — Segment 15.) |
| **BCC** | Editable text input | Same shape as CC. |
| **Subject** | Editable text input | Persists to `{invitation,reminder}_subject`. |
| **Body** | Editable textarea | Plain-text, `min-height: 12em`. Persists to `{invitation,reminder}_body`. |

Each field carries a small "Reset to default" link rendered next
to its label, only when the field has an override. Click clears
the per-field override (POSTs to a per-field reset endpoint or
toggles the JSON key to `null`); the field re-renders with the
default value plus the link disappears.

### Right card — `.card.merge-tags`

Two stacked sections:

**Section 1 — usable tags.** A static list, one row per merge
tag, each row carrying:
- The tag literal (e.g. `{{reviewer_name}}`) in `<code>`.
- A short description.
- A "Copy" button that copies the tag literal to clipboard via
  the standard clipboard API.

The five tags:

| Tag | Resolves to |
|---|---|
| `{{reviewer_name}}` | `Invitation.reviewer.name` at send time. |
| `{{session_name}}` | `ReviewSession.name`. |
| `{{deadline}}` | `ReviewSession.deadline.strftime("%Y-%m-%d")` (or "no deadline set" when `None`). |
| `{{help_contact}}` | `ReviewSession.help_contact` (or "(help contact not set)" when `None`). |
| `{{invite_url}}` | The reviewer-specific invitation URL the existing send path computes. |

**Section 2 — actions.** A button row, flush right, with:
- **Save** (Primary) — submits the form. Persists overrides to
  `email_template_overrides`; emits `email_template.updated` audit
  event with a `changes` diff naming each field that moved.
- **Cancel** (Secondary) — anchor back to Session Home, no save.
- **Preview as Rae Reviewer** (Secondary, optional) — opens a
  modal / new-tab page rendering the merged body using the seeded
  fixture reviewer (`Rae Reviewer`, `rae@example.edu`). Defer the
  modal mechanics to PR 2 review.

### Template selector

The page edits both invitation and reminder templates. Two
patterns to choose from in PR 2 review (call out in the PR
description; pick one):

1. **Toggle / sub-tabs** at the top of the page (Invitation /
   Reminder) — single composer card visible at a time, URL
   carries `?template=invitation` (default) or `?template=reminder`.
2. **Stacked composer cards** — both templates render at once, top
   to bottom; one form per template.

PR 2 ships pattern 1 unless the operator-UI direction at the time
nudges otherwise. Pattern 2 trades vertical scroll for a flat
mental model.

## Proposed PR sequence

### PR 1 — Schema + service-layer template rendering

**Goal.** The data shape is in place. `_email_body` and
`_reminder_body` already read overrides + render merge fields, but
the editor UI hasn't shipped yet, so operators are still on
defaults. Send-side and outbox behaviour are byte-identical to
today for a session with no overrides.

- Alembic migration:
  - Adds `help_contact` (String(320), nullable) on `review_sessions`.
  - Adds `email_template_overrides` (JSON, nullable) on
    `review_sessions`.
- New `app/services/email_templates.py`:
  - `DEFAULT_INVITATION_SUBJECT` / `_BODY` / `DEFAULT_REMINDER_*`
    constants — exact copies of today's hardcoded strings,
    parameterised on the merge-field placeholders.
  - `render_invitation(session, reviewer, invite_url) -> tuple[str, str]`
    and `render_reminder(...)` — the new entry points.
  - `_resolve(session, key, default)` reads
    `session.email_template_overrides[key]` with `NULL`-key fall
    through.
  - `_substitute(template_str, **merge)` runs `string.Template`
    safely (`safe_substitute` so a missing key doesn't 500).
- `_email_body` / `_reminder_body` retire; their callers
  (`send_invitation`, `send_reminder`,
  `send_reminders_to_incomplete`) call the new renderers.
- Session create / edit forms (`session_new.html`, `session_edit.html`)
  pick up an optional `help_contact` field.
- Reviewer surface picks up a small footer / header line —
  `Questions? Contact <span>{{ help_contact }}</span>` — when the
  field is set. Hidden when `NULL`.
- Tests: round-trip on overrides (NULL fall-through, partial
  override, full override); `_substitute` safe-handles unknown
  keys; reviewer-surface footer renders only when set.

### PR 2 — Editor UI

**Goal.** The /setupinvite page is the editor.

- Replace `setupinvite_stub` with a full handler. Reads the
  session's overrides + current template selection; renders the
  editor.
- New template `app/web/templates/operator/session_setupinvite.html`
  (full rewrite). Uses the `.bottom-grid` two-card layout per
  "Editor surface" above.
- Right-card "Copy" button is JS-only (`navigator.clipboard.writeText`)
  with a toast / inline confirmation; degrades gracefully when JS
  is off (button is `type="button"` and a no-op). Per CLAUDE.md
  the inline JS is fine — no framework.
- Save handler (`POST /operator/sessions/{id}/setupinvite`):
  - Reads form fields per template (subject / cc / bcc / body for
    the active template).
  - Diffs against current overrides + defaults; only persists keys
    that diverge from default.
  - Emits `email_template.updated` audit with a `changes` diff
    `[(field, old, new), …]`.
  - 303 → `?saved=ok` flash inside a status banner card on the
    same page.
- Per-field "Reset to default" handler
  (`POST /operator/sessions/{id}/setupinvite/reset?field={k}`):
  - Removes the per-field override key.
  - Emits `email_template.reset` audit.
- Tests: GET renders defaults when no override; GET reflects
  saved override; Save persists + audits; reset clears one
  field without touching others; help-contact column surfaces
  in the merge-tag list when set; per-field "Reset to default"
  link only renders for fields with overrides.

### PR 3 — Send-side wiring + cleanup

**Goal.** The send path consumes the rendered template and the
outbox holds the merged body. Defaults / overrides indistinguishable
to a downstream reader of the outbox.

- `send_invitation` / `send_reminder` /
  `send_reminders_to_incomplete` thread the new renderer's output
  into the outbox row (`subject`, `body`).
- `EmailOutbox` row gains no new columns in this PR — CC / BCC
  storage on the override JSON sits unused at send time. PR
  description names this gap explicitly so a future Segment 15
  reader doesn't think we forgot.
- "Preview as Rae Reviewer" modal lands here (optional; defer to
  PR 2 review per the editor-surface notes above).
- Tests: invitation send-path uses override when set; falls through
  to default when null; outbox row carries the merged body
  byte-exact; existing send-path tests still pass.

## Implementation pointers

- **Default templates.** The two existing strings are short enough
  that the cost of parameterising them is one-line each. Today:
  ```
  subject: f"Invitation to review: {session.name}"
  body: f"You've been invited to review for: {session.name}.\n…"
  ```
  Become:
  ```
  DEFAULT_INVITATION_SUBJECT = "Invitation to review: $session_name"
  DEFAULT_INVITATION_BODY = (
      "You've been invited to review for: $session_name.\n"
      "Open this link (sign in with your work email): $invite_url\n"
  )
  ```
- **Merge-field rendering.** `string.Template` is preferred over
  Jinja `from_string` because:
  - The merge-field set is closed (five tags).
  - Operator-supplied templates shouldn't have access to template-
    engine machinery (loops / conditionals / filters); plain
    placeholder substitution matches the user's mental model.
  - `safe_substitute` keeps a typo'd `{{wrong_tag}}` from 500ing.
- **Storage shape.** `email_template_overrides` is JSON on
  Postgres / TEXT-as-JSON on SQLite. Use `sqlalchemy.JSON` (already
  used by `instrument_response_fields.validation`); both backends
  honour it.
- **Audit diff format.** Reuse the `session.updated` shape
  (`changes: list[[field, old, new]]`) for `email_template.updated`
  so the audit reader / future export tooling has one diff
  vocabulary.
- **Re-using the outbox view.** No template changes in
  `session_outbox.html` — the merged body lands in the existing
  `body` column and renders as today.
- **Help-contact wiring.** Three sites consume `help_contact`:
  1. Session create / edit form input.
  2. Reviewer surface footer / header inline.
  3. The `{{help_contact}}` merge field.
  Pick the surface label copy at PR 1 review; default to
  `"Questions about this review? Contact <X>"` on the reviewer
  surface.

## Out of scope (cross-references)

- **Real SMTP / Azure email backend.** Segment 15
  (`guide/segment_15_operator_polish_and_documentation.md`).
- **Outbox CC / BCC columns.** Folds into Segment 15's SMTP work.
- **Per-reviewer / per-cohort body customization.** Not in this
  segment; a future enhancement if pilots ask for it.
- **Rich-text / HTML email.** Segment 15 polish concern.
- **Segment 11C — Operations consolidation.** Disjoint surface;
  ships in parallel if capacity allows.

## Test impact

- Two new test files: `tests/integration/test_email_template_editor.py`
  (route + audit + override persistence) and
  `tests/unit/test_email_templates.py` (renderer fall-through and
  `safe_substitute` behaviour).
- Existing `tests/integration/test_invitations.py` and
  `tests/unit/test_email_outbox.py` need a small update — assertions
  that match `_email_body`'s exact output continue to pass since
  PR 1 keeps default outputs byte-identical, but worth grepping
  for any literal-string match on subjects / bodies that relies on
  the old helper signature.
- `tests/integration/test_session_detail_restructure.py`'s
  "edit-lock visibility" tests pick up the new `help_contact` field
  on the session edit form — verify the lock-card visibility logic
  still applies cleanly to the new field.

## Doc impact

- `docs/status.md` gains a timeline entry per PR; the "Capabilities
  today" line for `/setupinvite` flips from "stub" to its real
  description after PR 2.
- `guide/todo_master.md` — Segment 11E moves from **Upcoming** to
  the **Segment 11** Done section once PR 3 ships. Cross-references
  `unfinished_business.md` #24 (closed by this segment).
- `guide/unfinished_business.md` #24 — strikethrough closure once
  PR 3 ships, naming the merge PRs.
- `spec/architecture.md` "Data import / export" can pick up a one-
  liner about the merge-tag rendering layer; verify on PR 1 review.
- No new spec doc — this guide doubles as the spec until / unless
  the editor proves stable enough to promote.
