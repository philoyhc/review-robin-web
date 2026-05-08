# Settings inventory

**A single-stop reference for every setting Review Robin Web persists
on a user's behalf.** Each section names where the setting lives
(table + column / cookie / localStorage key), the UI surface that
edits it, and the canonical spec doc that describes its semantics
in detail. When a setting moves or grows, this file is the index
that should be updated alongside the per-page spec.

> **Scope.** Operator- and per-session settings the operator sets
> through the UI, plus the small handful of browser-local UI-state
> primitives (cookies / localStorage / URL params) that the operator
> implicitly drives. Deployer-set environment configuration appears
> at the end for context — it bounds what the operator can do, but
> the operator does not edit it through the app.

> **Scope exclusions.** Reviewer-side response state (the
> `responses` table — answers, autosave drafts, submission
> timestamps) is reviewer-determined, not operator-determined, and
> is documented in `spec/reviewer-surface.md`. The audit log
> (`audit_events`) is system-emitted and is documented in
> `spec/architecture.md` "Audit-event detail schema".

---

## 1. Operator-level settings (per signed-in user)

Stored on the `users` table. One row per authenticated principal
(matched by `external_principal_id` and `email` from Azure Easy
Auth). The same row backs every session that operator owns or
co-operates.

**Surface:** `/operator/settings`. Form-card with Cancel + Save
(both Secondary). The `← Back to {{ return_to_label }}` chrome
back-link returns the operator to wherever they came from
(`?return_to=<path>`).

| Field | Type | Notes |
|---|---|---|
| `email` | `String(320)` | Identity. Set by Easy Auth on first sign-in; not user-editable from the Operator Settings form. |
| `display_name` | `String(255)` | Identity. Same as `email` — Easy Auth-supplied, not user-editable. |
| `external_principal_id` | `String(255)` | Identity. Same as above. |
| `smtp_host` | `String(255)` | SMTP server hostname. |
| `smtp_port` | `Integer` | SMTP server port. |
| `smtp_username` | `String(320)` | SMTP login. |
| `smtp_password_encrypted` | `LargeBinary` | Fernet ciphertext keyed off the deployer's `SMTP_ENCRYPTION_KEY` env var. **Plaintext is never persisted.** |
| `smtp_from_display_name` | `String(255)` | Friendly name used in the `From:` header. |
| `smtp_encryption` | `String(16)` | `none` / `starttls` / `tls`. |
| `smtp_transport` | `String(16)` | `smtp` (default; only value supported today). Reserved for the Segment 14-1 backend swaps (Microsoft Graph, ACS). |

**Send-as-me identity model.** The operator who initiates a send in
Manage Invitations sends from their own SMTP credentials. There is
no shared mailbox.

**Canonical spec:** `spec/email_infra_options.md` for the wider
email-infra story; `guide/all_buttons.md` Section 15 + 15-supplement
for the form's button taxonomy.

---

## 2. Per-session settings (session metadata)

Stored on the `sessions` table. Owned by the creating operator;
surfaced to co-operators via `session_operators` (out of scope for
"settings" — that table records permissions, not settings).

**Surface:**

- **Create:** `/operator/sessions/new` (Session Details form +
  optional Quick Setup uploads).
- **Read:** Session Home > Session Details card (`session_detail.html`).
- **Edit:** `/operator/sessions/{id}/edit` (Edit Session sub-page,
  reached via the Edit Secondary in the Session Details card).

| Field | Type | Notes |
|---|---|---|
| `name` | `String(255)` | Display name. |
| `code` | `String(64)` (unique) | Stable short code; appears in `<code>` on lobby + Session Details. |
| `description` | `String(2000)` | Free-text. |
| `status` | `String(32)` | `draft` / `validated` / `ready` / `closed`. **Not directly editable** — driven by the lifecycle-transition actions (Validate / Activate / Pause / Close). Listed here because it's the ground truth that gates every other operator action. |
| `deadline` | `DateTime(timezone=True)` | Optional; rendered ISO 8601 with date+time. |
| `assignment_mode` | `String(32)` | `manual` / `rule_based`. **Not directly editable** — set by whichever assignment-generation path the operator runs (Manual CSV upload sets `manual`; the rule-based engine sets `rule_based`). Surfaced as a passive count on Quick Setup slot 3. |
| `help_contact` | `String(320)` | Free-text contact info shown to reviewers. |
| `email_template_overrides` | `JSON` | Free-form JSON with the recognised keys named in §3 below. |
| `created_by_user_id` | `Integer` (FK) | Identity. Not user-editable. |

**Canonical specs:** `spec/session_home.md` (Session Details card),
`spec/sessions_overview.md` (lobby table),
`spec/quick_setup_card_spec.md` (new-session variant).

---

## 3. Per-session email-template overrides

Stored as JSON inside `sessions.email_template_overrides`. Recognised
keys are pinned in `app.services.email_templates.OVERRIDE_KEYS` plus
the `responses_received_enabled` flag.

**Surface:** `/operator/sessions/{id}/setup-invite` (Email Template
page). The page has three internal nav tabs (Invitation / Reminder /
Responses received) and a side-by-side composer + preview region.

**String overrides** (per template kind, with the empty string
meaning "use the default"):

| Template kind | Subject | Body | Cc | Bcc |
|---|---|---|---|---|
| Invitation | `invitation_subject` | `invitation_body` | `invitation_cc` | `invitation_bcc` |
| Reminder | `reminder_subject` | `reminder_body` | `reminder_cc` | `reminder_bcc` |
| Responses received | `responses_received_subject` | `responses_received_body` | `responses_received_cc` | `responses_received_bcc` |

**Boolean toggle:**

| Key | Default | Notes |
|---|---|---|
| `responses_received_enabled` | `True` (when absent) | Gates the post-submit confirmation auto-send introduced in Segment 11C Part 2 PR H. |

**Canonical spec:** `spec/operator_ui_concept.md` "Email Template"
section; `app/services/email_templates.py` for the resolver
semantics.

---

## 4. Per-instrument settings (per session)

Stored on the `instruments` table — one row per instrument, scoped
to a session.

**Surface:** `/operator/sessions/{id}/instruments`. Each instrument
renders as its own card with an Edit / Save / Cancel action row plus
a per-instrument Danger sub-card.

| Field | Type | Notes |
|---|---|---|
| `name` | `String(255)` | Long-form label (e.g. "Mid-semester peer evaluation"). |
| `short_label` | `String(32)` | Short label used in the reviewer-surface chrome and in dashboards. |
| `description` | `String(2000)` | Operator-visible explanation. |
| `order` | `Integer` | Position within the session. |
| `accepting_responses` | `Boolean` | Per-instrument open/close. |
| `responses_visible_when_closed` | `Boolean` | Whether reviewers can see their own past responses after the instrument closes. |
| `deadline_closed_at` | `DateTime` | Auto-closed timestamp; populated when the deadline passes. |
| Display fields (per-instrument list) | rows in `instrument_display_fields` | Operator picks which reviewee attributes (name, email, tags, etc.) the reviewer sees on the response surface. |
| Response fields (per-instrument list) | rows in `instrument_response_fields` | The actual question schema — labels, types, options. |

**Canonical spec:** `spec/instruments.md`.

---

## 5. Per-reviewer / per-reviewee data

Stored on `reviewers` and `reviewees` tables. Owned by the session.
Tags are operator-determined; status is a mix of operator action
(soft-delete via Inactivate, deferred to Segment 15) and system
state.

**Surface:** Setup Pages — `/operator/sessions/{id}/reviewers` and
`/operator/sessions/{id}/reviewees`. Bulk-populated via Quick Setup
or per-entity CSV; managed inline (Manage rows are read-only today;
inline edit deferred to Segment 15 per `unfinished_business.md` #25).

### Reviewer

| Field | Type | Notes |
|---|---|---|
| `name` | `String(255)` | |
| `email` | `String(320)` | Identity used for invitation matching. |
| `status` | `String(32)` | `active` / `inactive`. Inactivate UI deferred to Segment 15 (`unfinished_business.md` #36). |
| `tag_1`, `tag_2`, `tag_3` | `String(255)` | Free-form labels. Used by rule-based assignment matching and surfaced on the reviewer surface when the corresponding column toggle is enabled. |

### Reviewee

| Field | Type | Notes |
|---|---|---|
| `name` | `String(255)` | |
| `email_or_identifier` | `String(320)` | Identity (may be a non-email identifier in non-email cohorts). |
| `profile_link` | `String(2000)` | Optional URL or photo link. |
| `status` | `String(32)` | `active` / `inactive`. |
| `tag_1`, `tag_2`, `tag_3` | `String(255)` | Same shape as reviewer tags. |

**Canonical spec:** `spec/setup_pages.md` (Reviewers / Reviewees
preview tables, column toggles, per-page column orders).

---

## 6. Per-user RuleSets (rule-based assignment)

Stored on `rule_sets` + `rule_set_revisions`. Each user can save
**Personal** RuleSets visible only to them; seeded RuleSets are
read-only and shared.

**Surface:** Rule Builder — `/operator/sessions/{id}/assignments/rule-based-editor`.

### `rule_sets`

| Field | Type | Notes |
|---|---|---|
| `name` | `String(255)` | Editable on Personal rows; carried by the Name input next to the selector. |
| `description` | `Text` | Editable on Personal rows. |
| `scope` | `String(16)` | `seed` (read-only) / `personal` (caller-owned). |
| `owner_user_id` | `Integer` | NULL on seeds; FK to `users` on Personal. |
| `is_seed` | `Boolean` | Mirror of `scope == "seed"`. |
| `current_revision_id` | `Integer` | Pointer into `rule_set_revisions`. |
| `deleted_at` | `DateTime` | Soft-delete timestamp; past audit refs still resolve. |

### `rule_set_revisions` (per Save / Copy / Delete)

| Field | Type | Notes |
|---|---|---|
| `revision_no` | `Integer` | Monotonic per RuleSet. |
| `combinator` | `String(16)` | `AND` / `OR`. |
| `exclude_self_reviews` | `Boolean` | Default for runs against this revision. The override on the main Assignments page wins when present. |
| `seed` | `Integer` | Random seed for stochastic rule kinds (e.g. random-pair quotas). |
| `rules_json` | `JSON` | The full rule list. Schema validated against `RuleSetSchema` in `app/schemas/rules.py`. |

**Canonical spec:** `spec/rule_based_assignment.md` (§7.2 covers
the Rule Builder page; §7.1 covers the Rule Based card on the
Assignments page).

---

## 7. Browser-local UI state

State the operator implicitly drives via interaction; not persisted
server-side. Listed here so a developer chasing "where is this
preference stored?" finds the answer quickly.

### Cookies

| Cookie | Scope | Purpose |
|---|---|---|
| `qsu_{session_id}=1` | `/operator/sessions/{id}`, `HttpOnly` | Quick Setup card unlock state. Set by `POST /operator/sessions/{id}/quick-setup/lock?action=unlock`; cleared by a Starlette middleware whenever the operator navigates away from Session Home (or by the lock action). |

### `localStorage` (per browser, per origin; survives sessions)

| Key | Surface | Purpose |
|---|---|---|
| `rrw-reviewer-tag-visibility` | Setup > Reviewers preview table | Per-column toggle state (Tag1 / Tag2 / Tag3). |
| `rrw-reviewee-tag-visibility` | Setup > Reviewees preview table | Per-column toggle state (Photo / Tag1 / Tag2 / Tag3). |
| `rrw-assignment-col-visibility` | Setup > Assignments preview table | Per-column toggle state (Pair{n} / Assign{n} pair-/assignment-context columns). |

### `sessionStorage` (per browser tab; cleared on tab close)

| Key | Surface | Purpose |
|---|---|---|
| `instrumentsScrollY:{path}` | Instruments page | Restore scroll position after a Save/Edit cycle reload. |

### URL state

| Param | Surface | Purpose |
|---|---|---|
| `?return_to=<path>` | Chrome-detour pages (Operator Settings, About) and Rule Builder | Round-trip target for the `← Back to {{ return_to_label }}` back-link. |
| `?validated=1` | Session Home | Triggers a fresh validation run on this render. |
| `?activate=1` | Validate detail page | Surfaces the activate-warns acknowledgment banner. |
| `?quick_setup_error=…&quick_setup_reason=…` | Session Home | Slot-scoped error feedback after a failed Quick Setup submit. |
| `?rule_based_error=…` | Assignments page | Slot-scoped error feedback after a failed rule-based generate. |

**Canonical specs:** `spec/setup_pages.md` (visibility-toggle
pattern), `spec/quick_setup_card_spec.md` (cookie + lock semantics),
`spec/operator_ui_concept.md` (chrome-detour return-to-origin).

---

## 8. Deployer-set environment configuration

Listed for context — these are not operator-determined. Set in
`.env` locally and via Azure App Service "Application settings" in
deployed environments. Source: `app/config.py`.

| Var | Default | Purpose |
|---|---|---|
| `APP_ENV` | `local` | `local` / `dev` / `prod` — informational. |
| `APP_NAME` | `Review Robin Web` | Display name. |
| `APP_VERSION` | `dev` | Surfaced in the chrome footer. |
| `DEBUG` | `True` | FastAPI debug mode. |
| `ALLOW_FAKE_AUTH` | `False` | When `True`, bypasses Azure Easy Auth and injects a fake operator. **Must remain `False` in deployed environments.** |
| `FAKE_AUTH_PRINCIPAL_ID` | `local-dev` | Fake-auth identity slot. |
| `FAKE_AUTH_EMAIL` | `operator@example.edu` | Fake-auth identity slot. |
| `FAKE_AUTH_NAME` | `Local Operator` | Fake-auth identity slot. |
| `DATABASE_URL` | `sqlite:///./review_robin_web.db` | SQLAlchemy connection string. Postgres in deployed environments; SQLite locally / in tests. |
| `SMTP_ENCRYPTION_KEY` | `None` | Symmetric Fernet key (Base64-urlsafe-encoded 32 bytes) used to encrypt operator SMTP passwords at rest. Generate with `cryptography.fernet.Fernet.generate_key()`. Fail-loud at encrypt / decrypt time, not at startup, so local dev / tests that don't touch Operator Settings don't need it set. |
| `AUDIT_STRICT_MODE` | `False` | When `True`, `audit.write_event` raises on a detail-shape violation. Production stays `False` (logs + writes through). Test runner flips to `True` so drift surfaces in CI. |

**Canonical spec:** `docs/local_setup.md` (env-var setup),
`docs/deployment_dev.md` (deployment-side configuration),
`docs/authentication.md` (Easy Auth + `ALLOW_FAKE_AUTH`).

---

## See also

- `app/config.py` — env-config source of truth.
- `app/db/models/` — SQLAlchemy declarations for every persisted
  setting named here.
- `app/services/operator_settings.py` — Operator Settings save /
  load flow.
- `app/services/email_templates.py` — `OVERRIDE_KEYS` +
  `RESPONSES_RECEIVED_ENABLED_KEY`.
- `guide/unfinished_business.md` — catalog of deferred settings
  surfaces (e.g. inline-editable Manage rows #25, Inactivate UI
  #36).
