# Segment 11E — Operator-editable email template editor + SMTP scaffolding

**Shipped 2026-05-05 → 2026-05-07.** Archived for historical
reference; consult `docs/status.md` for the authoritative summary
of what's in production and `unfinished_business.md` #24 for the
catalog entry.

Implementation plan for `unfinished_business.md` #24 — the
operator-facing email template editor at
`/operator/sessions/{id}/setupinvite`. Pre-segment, that page was a
stub ("lands in Segment 15"); the underlying `_email_body` /
`_reminder_body` helpers in `app/services/invitations.py` were two
hardcoded plain-text strings. This segment shipped the editor + the
merge-field rendering layer so operators can shape their own
invitations, reminders, and post-submit responses-received
confirmations without code changes, **plus the SMTP transport
scaffolding** — a per-operator Settings page, encrypted credential
storage, and a transport-agnostic send interface — that **Segment
14-1 Part A** will wire up on the Manage Invitations page. **Real
SMTP sends do not happen in 11E**: outbox rows still write
`status="queued"` and the dev outbox is the only sink the operator
sees on this surface.

## Status

**Done. Six PRs landed against the planned five (PR 3 collapsed
into PR 1 — the renderer wiring landed there) plus one polish PR
plus the Follow-on PR 6:**

- **PR 1 (#461)** — schema + service-layer renderer.
  `sessions.help_contact` (String 320, nullable) and
  `sessions.email_template_overrides` (JSON, nullable) columns;
  new `app/services/email_templates.py` rendering
  `string.Template.safe_substitute` over the canonical five-tag
  merge-field set (`$reviewer_name` / `$session_name` /
  `$deadline` / `$help_contact` / `$invite_url`); the legacy
  `_email_body` / `_reminder_body` helpers retire in favour of
  `render_invitation` / `render_reminder`. Help-contact also
  surfaces on the reviewer surface as a small "Questions? Contact
  X" line.
- **PR 2-A (#462)** — placeholder cards on `/setupinvite` framing
  the editor surface ahead of the actual editor.
- **PR 4 (#463)** — operator Settings page at `/operator/settings`.
  Per-operator SMTP credentials (seven new columns on `users`);
  password encrypted at rest via `cryptography.fernet` keyed off
  the `SMTP_ENCRYPTION_KEY` env var; new
  `app/services/operator_settings.py` + `app/services/_secrets.py`;
  user-menu Settings link in the chrome.
- **PR 5 (#464)** — `EmailTransport` Protocol + `EmailMessage` /
  `SendResult` dataclasses + concrete `SmtpEmailTransport`
  (`smtplib`, STARTTLS / implicit-SSL) + typed-stub
  `GraphEmailTransport` placeholder + `transport_for(settings)`
  factory. Nothing in the app calls this yet; **Segment 14-1
  Part A** is the first call site.
- **PR 2 (#465)** — actual editor UI on `/setupinvite`. Two-card
  `.bottom-grid` layout: composer left, merge tags + Save / Cancel
  right. Per-template selection via `?template=` query.
  Per-field "Reset to default" forms; `email_template.updated` /
  `email_template.reset` audit events.
- **#468 polish** — Email Template + Settings button consistency:
  Invitation / Reminder tabs out of card / normal-sized / flushed
  left, Save / Cancel at bottom-right of their card, no flash
  banners (Save disables until dirty), Settings page picks up
  `?return_to=` plumbing matching the About-page convention.
- **PR 6 (#532, 2026-05-07)** — responses-received template
  editor third tab. Adds the responses-received subject / body /
  cc / bcc keys to `email_template_overrides` plus a per-session
  `responses_received_enabled` bool flag (default `True`) the
  editor surfaces as a "Send this confirmation when a reviewer
  submits." checkbox. New
  `email_templates.render_responses_received(session, reviewer)`
  helper (drops `$invite_url`, adds `$submitted_at` resolved via
  `_latest_submitted_at` against the reviewer's responses) +
  `responses_received_enabled(session)` reader +
  `set_responses_received_enabled(session, enabled)` writer.
  Editor's right-card merge-tag list goes per-template via new
  `views.merge_tags_for_template(template)` helper.
  `views.EMAIL_PREVIEW_TABS` flips `is_shipped=True` on the
  responses-received entry — lights up the previously deferred
  Preview hub artifact card without needing a new registry seam.
  The submit-time send wiring (originally planned as PR 7) was
  absorbed into **Segment 14-1 Part A** so all email *sending*
  lives in one segment regardless of which transport backend
  lights up.

The plan below preserves the original PR-sequence text as a
historical record of how the segment was scoped before any of it
shipped. The "Follow-on — Responses-received email" section near
the bottom captures PR 6's revised scope (the cross-segment
reshuffle around 11C Part 2 / 14-1 happened mid-flight; #531
narrowed 11E to editor-only + reframed the send wiring as a 14-1
seam, then #532 shipped that scope).

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
- **Operator-level Settings page** at `/operator/settings`:
  per-operator SMTP credential storage. The page sits behind the
  user-menu dropdown (alongside About / Sign out) so it's reachable
  from any surface. Card layout TBD at PR 4 review; minimum
  contents per "SMTP credentials storage" below.
- **Transport-agnostic send interface** in `app/services/email_send.py`.
  Defines `EmailTransport` Protocol; ships an SMTP backend
  (`SmtpEmailTransport` over `smtplib`); leaves a typed-stub
  `GraphEmailTransport` placeholder so a future Graph addition is
  a one-enum-value-plus-implementation change. The interface is
  in place but **not yet invoked from any send path** in 11E.
- **Two new audit events on top of the editor's two:**
  `operator_email_settings.updated` / `operator_email_settings.cleared`.

Out (deferred):

- **Activating actual sends** — the transport sits in code but no
  route triggers it. **Segment 11C** wires per-row + bulk activate-
  send and test-send affordances on the Manage Invitations page;
  that's where outbox rows transition from `queued` to `sent` /
  `failed`.
- **Microsoft Graph backend.** The Protocol and a typed stub land
  in 11E; the `httpx`-against-`/me/sendMail` implementation, Entra
  app `Mail.Send` scope grant, and token-cache module all wait on
  a future segment. The shape is designed to accept the Graph
  backend without touching call sites.
- **Outbox CC / BCC + error columns** — folded into 11C alongside
  the send-activation work, since that's where they're observable.
  The editor stores CC / BCC in the override JSON in 11E so the
  operator-facing surface stays shape-stable across the cutover.
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

## Operator Settings page

Per-operator page at `/operator/settings`, reached from the user-
menu dropdown. **Per-operator** because the send-as-me model means
the operator who clicks Send needs their own credentials in the
transport's `from_addr` / auth pair; no concept of a session-level
or app-level shared mailbox in this segment.

### Contents (PR 4)

A single `.card.settings-card` (full-width, no two-column layout)
carrying:

| Field | Treatment | Notes |
|---|---|---|
| **Transport** | Read-only display | "SMTP (Outlook / Office 365)" — only legal value today. Documented as the slot a future Graph backend would swap into. |
| **SMTP host** | Editable text input | Default placeholder `smtp.office365.com`. |
| **SMTP port** | Editable number input | Default placeholder `587`. |
| **Encryption** | Radio (STARTTLS / SSL) | Default `STARTTLS`. |
| **From email** | Editable text input | The operator's Outlook address. Used as both SMTP `username` and the message `From`. |
| **App password** | Editable password input | Empty by default; entering a value triggers a re-encrypt + persist. The page never re-renders the existing plaintext (it isn't stored). A "Password is set" / "Password is not set" indicator sits next to the field. |
| **From display name** | Editable text input | Optional. Falls back to the From email when blank. |

Action row at the bottom of the card: **Save** (Primary), **Clear
all settings** (Destructive), **Cancel** (Secondary back to the
last page). Saved confirmation is a `?saved=ok` flash inside the
existing banner family.

When the page loads with no credentials configured, an intro card
sits above the form pointing at Microsoft's docs for generating
SMTP-AUTH-compatible app passwords. Empty-state UX matters more
here than usual — "configure SMTP" is one of the few in-app gates
on actually sending mail.

## Transport interface

`app/services/email_send.py` defines the contract every backend
implements:

```python
@dataclass(frozen=True)
class EmailMessage:
    from_addr: str
    from_display_name: str | None
    to: str
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    subject: str = ""
    body: str = ""

@dataclass(frozen=True)
class SendResult:
    ok: bool
    error_message: str | None = None
    transport_response: str | None = None  # truncated, for audit

class EmailTransport(Protocol):
    def send(self, msg: EmailMessage) -> SendResult: ...
```

Backends:

- **`SmtpEmailTransport`** — concrete, ships in PR 5. Wraps
  `smtplib.SMTP` (STARTTLS) / `smtplib.SMTP_SSL`. Catches every
  `smtplib` exception → `SendResult(ok=False, error_message=…)`.
- **`GraphEmailTransport`** — typed stub in PR 5. Documents the
  expected swap (`POST /me/sendMail` via `httpx`, OAuth2 token
  cached per-operator). `raise NotImplementedError(...)` until a
  future segment.

`transport_for(settings: EmailSettings) -> EmailTransport`
dispatches on `settings.transport`. Today only `"smtp"` is
reachable; the factory shape leaves room for `"graph"` without
touching call sites.

Critically: **nothing in 11E imports `transport_for` from a
route**. The interface and SMTP backend ship in PR 5 ready for
import. Segment 11C's Manage Invitations send handler is the first
caller.

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

### PR 4 — Operator Settings page + credential storage

**Goal.** A signed-in operator can land on `/operator/settings` and
persist their SMTP credentials. The credentials are encrypted at rest
and decryptable on read. **No send path consumes them yet** — the
read happens only in unit tests in 11E and in 11C's send-activation
work.

- New columns on `users` (operator-scoped, since "Send as me"):
  - `smtp_host: Mapped[str | None]` (String(255)).
  - `smtp_port: Mapped[int | None]` (Integer).
  - `smtp_username: Mapped[str | None]` (String(320)).
  - `smtp_password_encrypted: Mapped[bytes | None]` (LargeBinary)
    — Fernet-encrypted; the plaintext is never persisted.
  - `smtp_from_display_name: Mapped[str | None]` (String(255)).
  - `smtp_encryption: Mapped[str | None]` (String(16) — one of
    `"starttls"` / `"ssl"`).
  - `smtp_transport: Mapped[str]` (String(16), default `"smtp"`)
    — keyed for the future Graph swap. Today the only legal value
    is `"smtp"`; the column is constrained at the service layer
    rather than via a CHECK constraint to keep the migration small.
- New `app/services/operator_settings.py`:
  - `get_email_settings(user) -> EmailSettings | None` — returns
    a frozen dataclass with the decrypted password if all fields
    are populated; `None` otherwise. Callers (PR 5's transport
    factory + 11C's send-activation) treat `None` as "operator
    hasn't configured a transport yet."
  - `save_email_settings(user, *, …, plaintext_password)` — encrypts
    the password and upserts the row. Emits
    `operator_email_settings.updated` audit with the diff (excluding
    the password field; "password changed: yes/no" is the only
    detail logged).
  - `clear_email_settings(user)` — wipes every field. Emits
    `operator_email_settings.cleared`.
- New module `app/services/_secrets.py` (or fold into
  `operator_settings.py`):
  - `encrypt_password(plaintext) -> bytes` and
    `decrypt_password(ciphertext) -> str` using
    `cryptography.fernet.Fernet`.
  - Reads the Fernet key from a new env var
    `SMTP_ENCRYPTION_KEY` (Base64-encoded 32-byte key). **Fail-loud
    on startup** if the env var is missing or malformed; refuse to
    boot rather than risk writing unencrypted ciphertext or losing
    decryption later. Add to `app/config.py`'s settings model.
  - The `cryptography` package becomes a new runtime dependency
    in `pyproject.toml`.
- New route + template:
  - `GET /operator/settings` — renders the form. Pre-fills every
    field except the password (which renders as an empty input
    plus a "Password is set" / "Password is not set" indicator
    next to it; entering a new value re-encrypts; leaving it
    empty preserves the existing value).
  - `POST /operator/settings` — saves. 303 → same page with
    `?saved=ok` flash.
  - `POST /operator/settings/clear` — wipes the row. 303 → same
    page.
  - Page reachable from the user-menu dropdown (alongside the
    existing About / Sign out items). Update
    `app/web/templates/_partials/user_menu.html` (or wherever the
    dropdown lives) accordingly.
- No "Send test" button on the Settings page itself — that's
  on Manage Invitations per 11C. The Settings page indicates only
  whether the credential set is *complete* (every required field
  populated), not whether it actually works.
- **Empty-state copy** when no credentials are configured: a
  short intro card pointing at Microsoft's app-password / SMTP
  AUTH docs ("To send via Outlook / Office 365, generate an app
  password at https://…"). Better than a blank form for first-
  time operators.
- Tests: round-trip encryption (encrypt then decrypt → original);
  save form persists every field except the password when blank;
  password upsert encrypts and decrypts correctly; clear wipes all
  fields; audit events emit with the correct diff shape; missing
  `SMTP_ENCRYPTION_KEY` causes a startup failure (or a fail-loud
  exception when the encryption helper is first invoked, depending
  on whether the env-var check is wired into `Settings` at import
  time).

### PR 5 — Transport interface + SMTP backend

**Goal.** Send logic exists in code, fully testable, but no route
in the app actually invokes it. The handoff to Segment 11C is a
single import.

- New `app/services/email_send.py`:
  - `class EmailMessage` — frozen dataclass with `from_addr`,
    `from_display_name`, `to`, `cc`, `bcc`, `subject`, `body`.
  - `class SendResult` — frozen dataclass with `ok`,
    `error_message`, `transport_response` (raw provider message,
    truncated).
  - `class EmailTransport(Protocol)` — `def send(self, msg:
    EmailMessage) -> SendResult: ...`.
  - `class SmtpEmailTransport(EmailTransport)` — concrete class
    constructed from an `EmailSettings` dataclass. Uses
    `smtplib.SMTP` with STARTTLS by default, `smtplib.SMTP_SSL`
    when `encryption="ssl"`. Catches every `smtplib`-side
    exception, normalises to `SendResult(ok=False, error_message=…)`;
    never raises.
  - `class GraphEmailTransport(EmailTransport)` — typed stub
    (`raise NotImplementedError(...)` in `send`). Documented
    in-line as "Segment 11+ — wire to httpx /me/sendMail."
  - `transport_for(settings: EmailSettings) -> EmailTransport` —
    factory that dispatches on `settings.transport`. Today only
    `"smtp"` is reachable.
- Tests cover the SMTP backend with a `unittest.mock`-patched
  `smtplib.SMTP` (no real network): success, auth failure,
  connection timeout, bad recipient. `GraphEmailTransport.send`
  raises `NotImplementedError`.
- **No call sites change in 11E.** `send_invitation` /
  `send_reminder` continue writing `status="queued"` outbox
  rows. `transport_for` is imported by 11C's Manage Invitations
  send handler, which transitions queued rows to sent / failed.

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

- **Activating actual sends** — Segment 11C wires Manage Invitations
  per-row + bulk Send + test-send affordances on top of the
  transport interface this segment ships. 11E's outbox rows stay
  `status="queued"` until 11C lands.
- **Microsoft Graph backend.** Protocol + typed stub here; full
  implementation (httpx against `/me/sendMail`, Entra `Mail.Send`
  scope grant, token cache) defer to a future segment.
- **Outbox CC / BCC + error columns.** Folded into Segment 11C
  alongside the send activation work, since that's where they're
  observable.
- **Per-reviewer / per-cohort body customization.** Not in this
  segment; a future enhancement if pilots ask for it.
- **Rich-text / HTML email.** Segment 15 polish concern.

## Test impact

- New test files:
  - `tests/integration/test_email_template_editor.py` — editor
    route + audit + override persistence (PR 2).
  - `tests/unit/test_email_templates.py` — renderer fall-through
    and `safe_substitute` behaviour (PR 1).
  - `tests/integration/test_operator_settings.py` — Settings page
    GET / Save / Clear, audit events, encryption round-trip
    (PR 4).
  - `tests/unit/test_email_send.py` — `SmtpEmailTransport` over
    a mocked `smtplib.SMTP` (success + auth failure + connection
    timeout + bad recipient); `GraphEmailTransport.send` raises
    `NotImplementedError` (PR 5).
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
  description after PR 2; a new "Capabilities today" line covers
  `/operator/settings` after PR 4.
- `guide/todo_master.md` — Segment 11E moves from **Upcoming** to
  the **Segment 11** Done section once PR 5 ships. Cross-references
  `unfinished_business.md` #24 (closed by this segment) and the
  forward dependency from Segment 11C.
- `guide/unfinished_business.md` #24 — strikethrough closure once
  PR 5 ships, naming the merge PRs.
- `guide/archive/segment_11C_operations_consolidation.md` — picks
  up the Manage Invitations send-activation scope. Update
  separately. (Send-activation scope subsequently moved to
  Segment 14-1 Part A; 11C Part 2 shipped only the schema slice
  on 2026-05-07.)
- `spec/architecture.md` "Data import / export" can pick up a one-
  liner about the merge-tag rendering layer; verify on PR 1 review.
- No new spec doc — this guide doubles as the spec until / unless
  the editor proves stable enough to promote.

---

## Follow-on — Responses-received email (editor-only)

PRs 1-5 shipped invitation + reminder. The third reviewer-facing
email — the **responses-received** confirmation sent to the
reviewer when they submit their review — slots in on top of the
same primitives without re-architecting anything: the
`email_template_overrides` JSON column gets new keys (subject /
body / cc / bcc + an enabled flag), the editor grows a third
selector tab, the renderer gets one more function, and the
Preview hub registry picks up the artifact card.

The Preview hub (`spec/preview_hub.md`) lists this artifact in
its registry; Segment 11F deferred its preview card explicitly
on the grounds that no render path existed yet. This follow-on
ships the render path, which lights up that card too.

**The submit-time send wiring is *not* in this segment.** Per
the Segment 11C Part 2 consolidation, all email *sending* —
buttons, dispatch helpers, audit events, transport readiness —
lives on the Operations side. 11E owns "what does this email
say, and should it auto-send?"; 11C Part 2 owns "queue, send,
report status." The two surfaces meet at the
`email_template_overrides.responses_received_enabled` flag this
PR introduces and the `render_responses_received` helper this
PR ships, both of which 11C Part 2's PR H consumes.

### Status

**Shipped 2026-05-07 as PR 6 (#532).** This Follow-on landed
exactly as scoped: editor-only — schema additions + render
helper + editor third tab + send-on-submit checkbox + Preview
hub registry flip. Anything further on the responses-received
email (auto-send wiring, audit event, the Operations-side
buttons) moved to **Segment 14-1 Part A** during the cross-
segment reshuffle (#533) — see `guide/segment_14-1_email_infra.md`.

### Why a third email type, not a fold-into-an-existing-one

- **Different audience moment.** Invitation goes out on
  Activate; reminder goes out on a deadline threshold;
  responses-received fires the instant the reviewer submits. A
  unified template across the three would have to special-case
  every merge field on every send path.
- **Different merge-tag set.** `$invite_url` is moot
  post-submission (the link is already used). A
  `$submitted_at` tag is novel here. Sharing a template across
  audience moments forces awkward conditional copy in the body
  ("if you've already submitted, ignore this").
- **Different default body.** The confirmation is short and
  closes the loop ("Thanks. Your responses are recorded."); the
  invitation onboards. Distinct defaults read better than a
  shared one.

### Scope

In:

- **Schema additions** to `email_template_overrides` JSON.
  Five new optional keys, mirroring the invitation / reminder
  shape plus a new on/off toggle:
  - `responses_received_subject`
  - `responses_received_body`
  - `responses_received_cc`
  - `responses_received_bcc`
  - `responses_received_enabled` *(bool, default `True` when
    absent — the per-session "Send this email when a reviewer
    submits?" toggle the editor exposes as a checkbox; consumed
    by Segment 11C Part 2 PR H's submit-time enqueue)*

  No Alembic migration — the column is already a free-form JSON;
  new keys land at write time. Defaults live in code alongside
  `DEFAULT_INVITATION_*` / `DEFAULT_REMINDER_*` constants in
  `app/services/email_templates.py`.
- **Render helper** `render_responses_received(session,
  reviewer)` in `app/services/email_templates.py`. Same shape
  as `render_invitation` / `render_reminder`: `string.Template`
  substitution over the override-or-default body. Returns the
  same `RenderedEmail` dataclass the other two return.
- **Editor third tab.** The template selector at the top of
  `/operator/sessions/{id}/setupinvite` grows a third option —
  "Responses received" — alongside Invitation and Reminder.
  `?template=responses_received` selects it via the same
  query-param convention PR 2 shipped. The composer + merge-
  tags cards re-render with this template's fields.
- **Send-on-submit checkbox.** The Responses-received tab
  carries a single extra control above (or alongside) the
  subject / body fields: a checkbox labelled e.g.
  *"Send this confirmation when a reviewer submits."*,
  defaulting to checked, backed by the
  `responses_received_enabled` JSON key. Per-field "Reset to
  default" mirrors the existing pattern (resets to `True`).
  This is the only operator-facing send-policy control on the
  page; everything else about *how* it sends (transport, queue,
  retry) lives on Operations per Segment 11C Part 2.
- **Per-template merge-tag list.** The right-card merge-tag
  list is now per-template:
  - **Invitation / Reminder:** unchanged (the canonical five —
    `$reviewer_name`, `$session_name`, `$deadline`,
    `$help_contact`, `$invite_url`).
  - **Responses received:** four tags — `$reviewer_name`,
    `$session_name`, `$deadline`, `$help_contact`. **Drops**
    `$invite_url` (moot post-submit). Adds an optional
    `$submitted_at` (formatted `"%Y-%m-%d %H:%M %Z"`) that
    resolves to the `Assignment.submitted_at` of the most
    recently submitted assignment for that reviewer in that
    session.
  - The view-shape adapter the editor consumes (PR 2's
    `views.merge_tags_for_template(template)`) gains the new
    case; everything else flows through unchanged.
- **Default body / subject** in code:
  - Subject: `"Responses received: $session_name"`.
  - Body:
    ```
    Hi $reviewer_name,

    Thanks. Your responses for $session_name are recorded
    as of $submitted_at.

    Questions? Contact $help_contact.
    ```
- **Preview hub registry append** (lands here, not in 11F):
  one new `PreviewArtifactSpec` entry for the responses-received
  card. Render adapter calls `render_responses_received` with
  the picker-selected reviewer. Card source-of-truth footer
  points at `setupinvite?template=responses_received` and the
  Reviewers Setup page. Ships as part of this PR since the
  render helper lands here too.

Out (handed to Segment 11C Part 2 PR H):

- **Submit-time send wiring.** The reviewer-submit handler
  enqueueing an `email_outbox` row with
  `kind="responses_received"` lives on the Operations / send
  side, alongside the per-row Send / bulk-Send / dispatch
  helpers PR F + PR G already own. PR H reads
  `email_template_overrides.responses_received_enabled` (the
  flag this PR introduces) to decide whether to enqueue, and
  calls `render_responses_received` (the helper this PR
  introduces) to populate the row.
- **The `responses_received_email.queued` audit event.** Same
  rationale as above — emitted from the enqueue site in 11C
  Part 2 PR H.
- **Re-submit semantics, idempotency, "once per reviewer per
  session" toggles.** All on the send-side; PR H's concern.
- **Operator BCC of every responses-received email.** Some
  operators will want a copy. The CC / BCC fields in the
  override JSON cover this once Segment 15's outbox CC / BCC
  schema work lands; until then the CC / BCC columns store
  the operator's intent but the send path ignores them, same
  as the invitation / reminder fields.
- **Aggregated digest** (one summary email per operator at end
  of day) — separate scope, separate audience.

### Proposed PR sequence

#### PR 6 — Schema + render helper + editor tab + Preview hub card

**Goal.** The third email type is fully editable in the
operator UI and previewable in the Preview hub; an operator
can flip the auto-send toggle on or off; nothing yet fires on
submit (that's PR H in 11C Part 2).

- Add the five new keys to the override JSON's documented
  shape (in this guide and the `email_template_overrides`
  docstring). No Alembic migration.
- New `DEFAULT_RESPONSES_RECEIVED_SUBJECT` /
  `DEFAULT_RESPONSES_RECEIVED_BODY` constants and a
  `responses_received_enabled_default = True` constant in
  `app/services/email_templates.py`.
- New `render_responses_received(session, reviewer) ->
  RenderedEmail`. Same Template-substitution path as the
  other two. `$submitted_at` resolves via the helper
  `_latest_submitted_at(session, reviewer)` querying the
  reviewer's assignments in this session and taking the
  newest `submitted_at`; falls back to "(not yet submitted)"
  if no submitted assignment exists (only the Preview hub
  hits that branch — when 11C PR H lights up the live send
  path, `submitted_at` is always set on enqueue).
- New helper
  `email_templates.responses_received_enabled(session) -> bool`
  that reads the flag from `email_template_overrides` with
  the documented `True` default. PR H in 11C Part 2 imports
  and consumes this.
- Editor: extend the template selector partial to render the
  third option; extend `views.merge_tags_for_template` to
  return the four-tag set; per-field "Reset to default"
  links re-use the existing pattern. Add the
  send-on-submit checkbox above the subject / body fields,
  posting under the same Save form.
- Preview hub: append the registry entry; the
  responses-received card renders inline below the reviewer-
  surface card on `/operator/sessions/{id}/previews`.
- Tests:
  - `render_responses_received` substitutes all four tags;
    `$submitted_at` resolves correctly when the reviewer has
    submitted assignments and falls back to the "not yet
    submitted" placeholder otherwise.
  - Editor tab navigation: `?template=responses_received`
    selects the tab; merge-tag list shows four tags (no
    `$invite_url`).
  - Save / Reset round-trip on the new fields persists to
    `email_template_overrides`, including the
    send-on-submit checkbox (default `True`, flips to
    `False` when unchecked, "Reset to default" returns it to
    `True`).
  - `responses_received_enabled(session)` returns `True` on
    a session with no overrides, honours an explicit
    `False`, and honours an explicit `True`.
  - Preview hub renders the card with the right body for
    the picker-selected reviewer.

### Implementation pointers

- **Submitted-at formatting.** Use the same
  `format_datetime_for_display` helper the invitation /
  reminder `$deadline` formatting uses. Keep the merge-tag
  rendering consistent across all three email types.
- **Help-contact fallback.** The `$help_contact` tag's "(help
  contact not set)" placeholder is jarring in a closing
  confirmation; if `session.help_contact is None`, drop the
  whole "Questions? Contact …" sentence from the default body
  rather than printing the placeholder. Operator-supplied
  bodies that reference `$help_contact` still get the
  placeholder — that's their decision to make.
- **Checkbox copy.** Phrase the editor toggle so an operator
  reading it cold understands the behaviour change without
  scrolling — "Send this confirmation when a reviewer
  submits." (default checked) is clearer than
  "Auto-send enabled." Keep the on-state copy short; the
  details about *how* it sends (transport, queue, retries) are
  Operations-side concerns the operator already knows about
  from Manage Invitations.
- **Don't pre-emit anything from the send path.** The
  enqueue logic, audit event, and any "you have N
  responses-received queued" surfacing all belong in 11C
  Part 2 PR H. Resist the temptation to wire even a stub
  here — keeping 11E strictly authoring-side keeps the
  retire-after-PR-6 line crisp.

### Test impact

- One new unit test file —
  `tests/unit/test_render_responses_received.py` (covers the
  render helper + the `responses_received_enabled` reader).
- Existing `tests/integration/test_session_setupinvite.py`
  picks up cases for the third tab (selector, save / reset
  round-trip, send-on-submit checkbox round-trip).
- Existing `tests/integration/test_session_previews.py` (from
  11F) picks up the new artifact card.
- No churn on the existing invitation / reminder test suites.
- No `tests/integration/test_responses_received_send.py` here
  — that file lands in 11C Part 2 PR H alongside the enqueue
  logic.

### Doc impact

- `guide/todo_master.md` — when PR 6 ships, move 11E from its
  un-archived "follow-on PR pending" note to a clean Done
  entry, citing PR 6's number; mention the 11C PR H seam in
  the entry.
- `docs/status.md` — timeline entry + summary-table row.
- `guide/archive/segment_11C_operations_consolidation.md` — the
  formerly-PR-H send-activation scope moved to **Segment 14-1
  Part A**; the helper + the `responses_received_enabled` flag
  remain hard prerequisites and should be cross-referenced in
  14-1 PRs that depend on them.
- After PR 6 ships, **archive this guide**: `git mv
  guide/segment_11E_email_template_editor.md
  guide/archive/`. Then update the cross-references in
  `todo_master.md`, `docs/status.md`, and `segment_11C` /
  `segment_11F` if any still point at the un-archived path.
