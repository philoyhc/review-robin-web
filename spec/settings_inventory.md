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

**Surface:** `/operator/settings`. The Email send (SMTP) form-card
carries Cancel + Save (both Secondary); the page also carries a
**Date & time** card (its own Save, Secondary) editing the
`display_timezone` preference key, with a live worked-sample preview
that names the selected zone in full. The
`← Back to {{ return_to_label }}` chrome back-link returns the
operator to wherever they came from (`?return_to=<path>`).

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
| `smtp_encryption` | `String(16)` | `starttls` / `ssl` (validated against `operator_settings.SMTP_ENCRYPTION_MODES`); unset / empty = no encryption. |
| `smtp_transport` | `String(16)` | `smtp` (default; only value supported today). Reserved for the backend swaps Segment 14B plans (Microsoft Graph, ACS). |
| `preferences` | `JSON` | General per-operator preferences container. JSON object keyed by individual operator-level display preferences. First key `display_timezone` — the operator's default display timezone (an IANA zone name), edited on the **Date & time** card on `/operator/settings`. NULL / absent key = "no preference set" → consumer falls through to its in-code default (`UTC` for the timezone key). Future operator-level display settings become new keys, not new migrations. Operator surfaces render dates / times converted into this zone; the canonical render is bare `YYYY-MM-DD HH:MM` (no zone token) via the `format_datetime` Jinja filter — the card carries a worked sample that names the zone. The trailing zone token is behind one internal switch, `date_formatting.SHOW_ZONE_TOKEN` (off by default; flip + restart, no env var or migration). |

**Send-as-me identity model.** The operator who initiates a send in
Invitations sends from their own SMTP credentials. There is
no shared mailbox.

**Canonical spec:** `spec/email_infra_options.md` for the wider
email-infra story; `spec/operator_button_audit.md` Section 15 + 15-supplement
for the form's button taxonomy.

---

## 2. Per-session settings (session metadata)

Stored on the `sessions` table. Owned by the creating operator;
co-owners are surfaced + managed via the `session_operators`
table (per-session permission rows, not settings — see the
Owners card on the Session Details surface).

**Surface:**

- **Create:** `/operator/sessions/new` (Session Details form —
  incl. a Timezone field that sets `display_timezone` and scopes
  the deadline picker — plus optional Quick Setup uploads).
- **Read:** Session Home > Session Details card (`session_detail.html`).
- **Edit:** **inline on Session Home** —
  `/operator/sessions/{id}?editing=1#session-config`, reached via the Edit
  Secondary in the Session Details card. There is no Edit sub-page;
  `/operator/sessions/{id}/edit` survives only as a **308** shim to the
  inline surface, so an old bookmark still lands in the right place.
  The Session Details form carries a **Timezone** field,
  placed before the deadline it scopes; lifecycle-gated like the
  rest of the form. Also hosts the **Owners** card — current
  co-owners + Add-owner typeahead picker over the workspace
  operator allowlist. The editing surface is gated by
  `require_session_operator` (real ownership), so a sys-admin must
  own the session to manage owners — they self-add first via the
  Sessions Diagnostics **"Manage"** (adopt) action. The
  `owners/add` route keeps a relaxed entry
  (`require_sys_admin_or_session_operator`) but is **self-only**
  for a non-owner sys-admin, so the bypass cannot be used to grant
  anyone else access; the remove route requires ownership.

| Field | Type | Notes |
|---|---|---|
| `name` | `String(255)` | Display name. |
| `code` | `String(64)` (unique) | Stable short code; appears in `<code>` on lobby + Session Details. |
| `description` | `String(2000)` | Free-text. |
| `status` | `String(32)` | `draft` / `validated` / `ready` / `expired` / `archived`. **Not directly editable** — driven by the lifecycle-transition actions (Validate / Activate / Pause / Close session / Archive). Listed here because it's the ground truth that gates every other operator action. |
| `deadline` | `DateTime(timezone=True)` | Optional. Rendered on operator + reviewer surfaces via the `format_datetime` Jinja filter as bare `YYYY-MM-DD HH:MM` in the session's resolved display timezone; CSV extracts and audit-detail JSON keep ISO 8601. The Create / Edit `datetime-local` input is wall-clock in the form's Timezone field — `parse_local_datetime` converts it to a stored UTC instant, `format_datetime_local` renders it back; changing the zone re-renders the picker, the instant is fixed. Cross-field ordering rule **Start ≤ End** (and **End ≤ Release-from**) enforced by `scheduled_events.validate_schedule_ordering` after parse. |
| `assignment_mode` | `String(32)`, nullable | `rule_based`, or NULL. **Not directly editable** — the rule engine is the only writer, and it is the only path: assignments are never hand-created, uploaded or edited. **NULL means never Generated**, and is the state after deleting every assignment; three validation rules skip on it so a session with no pairs is not also told every reviewer is missing. A clone starts NULL, because it copies no assignment rows. `rule_based` and NULL are what is *written*; nothing has rewritten the rows stored before the manual CSV-upload path retired, so a reader must still tolerate a legacy `manual` or `full_matrix` value. |
| `self_reviews_active` | `Boolean` | Whether self-review pairs (reviewer reviewing themselves) are included when assignments are generated. Defaults to `True`. Edited on the Assignments page; round-trips through the Settings CSV (force-applied on import, see §10). |
| `help_contact` | `String(320)` | Free-text contact info shown to reviewers. |
| `email_template_overrides` | `JSON` | Free-form JSON with the recognised keys named in §3 below. |
| `display_timezone` | `String(64)` | IANA zone name used to render this session's dates / times. Resolution order: session value → creating operator's default → UTC. NULL means "inherit the operator default"; the Create and Edit forms both write a concrete zone, so a new session is never NULL, and the middle resolution step exists for the rows that are. Set on the Create Session form's **Timezone** field and the Edit Session Details form's **Timezone** field — both pre-filled, both also scoping the deadline picker (the deadline is wall-clock in this zone). Every session-scoped operator + reviewer surface renders dates / times in the resolved zone. |
| `scheduled_activate_at` | `DateTime(timezone=True)` | Operator-set Start anchor. When set, the lazy observer fires the scheduled `validated → ready` transition at this moment. Editor sits in the Schedule sub-grid of Create / Edit Session; save-time validator enforces a minimum lead-time of `SCHEDULED_OPERATIONAL_LEAD_HOURS` (default 1), plus the cross-field ordering rule **Start ≤ End** via `scheduled_events.validate_schedule_ordering`. Cleared as a side effect of activation (auto or manual). Persists across `validated → draft` reverts. |
| `invite_offsets` | `JSON` (`list[str] \| None`) | Operator-set list of ISO 8601 durations anchored on `scheduled_activate_at`. Each entry resolves to a fire moment `scheduled_activate_at + offset` for the auto-send-invites trigger. Editor entries are comma-separated; per-entry save-time rules: must parse as ISO 8601 duration, must be negative (fires before Start), `\|offset\| >=` `REVIEWER_NOTICE_MIN_HOURS`, `\|offset\| <=` 10 days, resolved fire moment `>= now + SCHEDULED_OPERATIONAL_LEAD_HOURS`. Inert when `scheduled_activate_at` is unset (§8.2.2 anchor-null). |
| `reminder_offsets` | `JSON` (`list[str] \| None`) | Operator-set list of ISO 8601 durations anchored on `deadline`. Each entry resolves to a fire moment `deadline + offset` for the auto-send-reminders trigger. Same per-entry rules as `invite_offsets` (must be negative; 10-day magnitude cap; lead-time + notice-gap minimums). Inert when `deadline` is unset. |
| `archive_offset` | `String(16)` | Operator-set ISO 8601 duration anchored on `deadline`, resolving to `deadline + archive_offset` for the auto-archive trigger. Editor default `P30D`. **Pre-positioned inert — no consumer wired yet.** |
| `responses_release_at` | `DateTime(timezone=True)` | Operator-set Release-from anchor — the moment reviewees / observers can start viewing collated results. Editor sits in the Schedule sub-grid of Create / Edit Session. Save-time validator `parse_and_validate_responses_release_at` converts a `datetime-local` value to UTC; **no minimum lead-time floor** (the operator can backdate to "immediately viewable"). Cross-field ordering rule **End ≤ Release-from** enforced by `scheduled_events.validate_schedule_ordering` after parse. |
| `responses_release_until` | `DateTime(timezone=True)` | Operator-set absolute close datetime for the responses-release window. Editor in the Schedule sub-grid alongside Release-from — a `datetime-local` input matching the Release-from shape. Save-time validator `parse_and_validate_responses_release_until` in `app/services/scheduled_events/` enforces ordering (must close *after* `responses_release_at` when both are set) and a 365-day magnitude check (must be within 365 days of `responses_release_at`). Accepts an until without an anchor (the resolver treats the window as inert per the §8.2.2 anchor-null rule). An absolute datetime rather than an offset, so the form input and the operator's forthcoming **Stop release** button write to the same column. |
| `relationships_enabled` | `Boolean` | Per-session toggle enabling the Relationships Setup tab and roster. Default `False`. Authored on the **User interface settings** card on the Create Session form and the Edit Session Details form. When `True`, the Relationships tab appears in the Setup chrome and the `/operator/sessions/{id}/relationships` routes resolve; when `False` those routes return 404 (gated by `require_relationships_enabled_session` in `app/web/routes_operator/_shared.py`). |
| `observers_enabled` | `Boolean` | Per-session toggle enabling the Observers Setup tab and roster. Default `False`. Authored on the **User interface settings** card on the Create Session form and the Edit Session Details form. When `True`, the Observers tab appears in the Setup chrome and `GET /operator/sessions/{id}/observers` resolves; when `False` that route returns 404 (gated by `require_observers_enabled_session` in `app/web/routes_operator/_shared.py`). |
| `retention_exception` | `Boolean \| None` | Per-session opt-out of the deployment retention policy. **Pre-positioned inert — no consumer wired yet.** |
| `retention_overrides` | `JSON \| None` | Per-session retention-policy overrides. **Pre-positioned inert — no consumer wired yet.** Recognised keys: `response_days`, `audit_days`, `archived_days`, `delete_after_archive` (ISO 8601 duration anchored on the system-stamped archive timestamp). |
| `created_by_user_id` | `Integer` (FK) | Identity. Not user-editable. |

**Canonical specs:** `spec/session_home.md` (Session Details card),
`spec/sessions_overview.md` (lobby table),
`spec/quick_setup_card_spec.md` (new-session variant).

---

## 2.5. Per-session friendly labels

Operator-renamable display labels for the **nine in-scope tag
slots** across the three Setup pages (reviewer / reviewee tag 1-3
+ pair-context 1-3). The reviewee identity slots (Name / Email /
Profile) are **not renamable** — they are identity, not labels, and
renaming them added no signal — so they appear in neither the
editor nor the allowlist, though their built-in defaults ("Name" /
"Email" / "Profile") still render. Stored as one row per
`(session_id, source_type, source_field)` override on the
`session_field_labels` table.

**Surface:**

- **Edit:** Inline editor card above the data table on
  `/operator/sessions/{id}/reviewers` (3 reviewer-tag slots),
  `/operator/sessions/{id}/reviewees` (3 reviewee-tag slots), and
  `/operator/sessions/{id}/relationships` (3 pair-context
  slots). Save / Cancel pair (both Secondary, both
  disabled-until-dirty). Gated by `is_ready`: inputs render
  disabled when the session is active/closed; the page's
  existing `.card.lock` already messages "revert to draft to
  modify". The same nine slots can also be set via the roster
  CSV header suffix (see **Round-trip** below).
- **Read:** Friendly label flows through every operator
  preview surface (Reviewers / Reviewees / Relationships /
  Assignments column headers + the Assignments
  column-toggle widget), the Instrument editor's read-only
  Friendly Label column, the reviewer-surface preview, and
  the reviewer surface itself.

| Field | Type | Notes |
|---|---|---|
| `session_id` | `Integer` (FK → `sessions.id` ON DELETE CASCADE) | Owning session. |
| `source_type` | `String(32)` | `reviewer` / `reviewee` / `pair_context`. |
| `source_field` | `String(64)` | The nine renamable slots: `tag_1` / `tag_2` / `tag_3` for the reviewer + reviewee tag sources, and `1` / `2` / `3` for `pair_context`. The reviewee identity sources `name` / `email_or_identifier` / `profile_link` are **not renamable**: `resolve` is permissive on read, so a row already stored for one still resolves, but `upsert` / `clear` are strict, so no new one can be created. Allowlist enforced by `app.services.field_labels._VALID_SOURCE_FIELDS` + the parallel `field_label_csv._LABELABLE_COLUMNS` on roster-CSV import. The column is `VARCHAR(64)` with no enum gate, so that allowlist is the only validation layer. |
| `label` | `String(255)` | The override label (stripped on upsert; empty input clears the row). |

Unique on `(session_id, source_type, source_field)`. Resolver
chain: session override → built-in default in
`_DEFAULT_LABELS` → `f"{source_type}:{source_field}"` fallback.
The per-instrument `InstrumentDisplayField.label` override is
**not** in the chain; the column stays in the schema as dead data.

**Round-trip:** **roster CSV headers only.** A tag friendly label
rides on its column as a `ReviewerTag1.<label>` suffix — import
upserts, bare header / absent column clears (mirrors the roster's
wipe-and-replace). Export re-emits the suffix when an override
exists. The Settings CSV carries no `field_labels.*` row, and one in
an older bundle is silently ignored on apply rather than failing the
import. See `spec/csv_contracts.md` §1a; handled by
`app.services.field_label_csv`.

**Logic vs display layer:** friendly labels are a
display-layer concern only. The underlying logic (Band 1
rule-cell operand sentences, CSV-import header validation +
error copy, validation error messages, audit-event payloads)
keeps the canonical machine name. On operator-facing display surfaces
the canonical name renders below the friendly label as `.muted`
subtext when an override is in effect, so operators stay
oriented to the underlying field.

**Canonical spec:** `spec/csv_contracts.md` §1a (the CSV carrier);
design record in `guide/archive/segment_15A_friendly_labels.md`.

---

## 3. Per-session email-template overrides

Stored as JSON inside `sessions.email_template_overrides`. Recognised
keys are pinned in `app.services.email_templates.OVERRIDE_KEYS` plus
the `responses_received_enabled` flag.

**Surface:** `/operator/sessions/{id}/setup-invite` (Email Template
page). The page has three internal nav tabs (Invitation / Reminder /
Responses received) and a two-card body: the composer beside a
merge-tag reference card (rendered previews live on the Previews
hub). Full page contract: `spec/email_template_editor.md`.

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
| `responses_received_enabled` | `True` (when absent) | Gates the post-submit confirmation auto-send. Stored, round-tripped and previewed; **no submit-time consumer reads it yet** (`spec/email_template_editor.md` §7). |

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
| `sort_display_fields` | `JSON` | Operator-defined default sort spec for this instrument's reviewer-surface table. Canonical shape: `[{"display_field_id": int, "dir": "asc|desc"}, ...]`, max 3 entries. NULL or `[]` = "no operator default" (insertion order). Edited via the Sort column on the per-instrument Display Fields card; reviewer-side override + cookie persistence on top, see `spec/sort_by_reviewee.md`. |
| `group_kind` | `String(32)` | Group-scoping flavour — one shared answer covers a whole group of reviewees instead of per-reviewee. NULL = "regular per-reviewee instrument". |
| `rule_set_id` | `Integer` (FK → `session_rule_sets.id` ON DELETE SET NULL) | Per-instrument selection of which `session_rule_sets` row applies. NULL = "no RuleSet currently selected" — the initial state for a new instrument and the state after a reset-assignments action. |
| Display fields (per-instrument list) | rows in `instrument_display_fields` | Operator picks which reviewee attributes (name, email, tags, etc.) the reviewer sees on the response surface. |
| Response fields (per-instrument list) | rows in `instrument_response_fields` | The actual question schema — labels, types, options. **This table is the sole source of truth for response fields.** Data type + bounds live inline on the row (`_inline_data_type` / `_inline_response_type` / `_inline_min` / `_inline_max` / `_inline_step` / `_inline_list_csv`), alongside `visible` (Boolean, default true), `help_text` and `help_text_visible`. There is no FK to a per-session type table. |

**Canonical spec:** `spec/instruments.md`.

---

## 5. Per-reviewer / per-reviewee / per-pair / per-observer data

Stored on `reviewers`, `reviewees`, `relationships`, and `observers`
tables. Owned by the session. Tags are operator-determined; status
is a mix of operator action (soft-delete via Inactivate) and system
state.

**Surface:** Setup Pages — `/operator/sessions/{id}/reviewers`,
`/operator/sessions/{id}/reviewees`,
`/operator/sessions/{id}/relationships`, and
`/operator/sessions/{id}/observers` (gated by
`session.observers_enabled`). Bulk-populated via Quick Setup or
per-entity CSV; managed inline — per-row Edit / Add /
bulk inactivate-reactivate on all four pages, observers included.

### Reviewer

| Field | Type | Notes |
|---|---|---|
| `name` | `String(255)` | |
| `email` | `String(320)` | Identity used for invitation matching. |
| `status` | `String(32)` | `active` / `inactive`. Flipped via the per-row Edit / bulk inactivate-reactivate UI. |
| `tag_1`, `tag_2`, `tag_3` | `String(255)` | Free-form labels. Used by rule-based assignment matching and surfaced on the reviewer surface when the corresponding column toggle is enabled. |

### Reviewee

| Field | Type | Notes |
|---|---|---|
| `name` | `String(255)` | |
| `email_or_identifier` | `String(320)` | Identity (may be a non-email identifier in non-email cohorts). |
| `profile_link` | `String(2000)` | Optional URL or photo link. |
| `status` | `String(32)` | `active` / `inactive`. |
| `tag_1`, `tag_2`, `tag_3` | `String(255)` | Same shape as reviewer tags. |

### Relationship (per-pair)

Per-pair attributes table — one row per `(session_id, reviewer_id,
reviewee_id)` triple. The home for pair-context tags, held here
rather than on `assignments` so per-pair attributes exist
independently of whether the rule engine has materialized an
assignment for the pair.

| Field | Type | Notes |
|---|---|---|
| `reviewer_id` | `Integer` (FK → `reviewers.id` ON DELETE CASCADE) | Identity. |
| `reviewee_id` | `Integer` (FK → `reviewees.id` ON DELETE CASCADE) | Identity. Unique with `reviewer_id` per session via `uq_relationships_session_reviewer_reviewee`. |
| `tag_1`, `tag_2`, `tag_3` | `String(255)` | Free-form pair-context labels. Consumed by the rule-based engine via the eager `pair_context_lookup` dict. Surfaced as the third Ctx-toggle group on the Assignments preview table. |
| `status` | `String(32)` | `active` / `inactive`. Defaults to `active`. |

### Observer

Per-session observer rows — one per audience member who will view
collated results. Identity is `email` (required, NOT NULL, unique
per session). Unlike reviewers / reviewees, observers are not
enrolled in the reviewer response surface.

| Field | Type | Notes |
|---|---|---|
| `email` | `String(320)` | Required. Unique per session (case-insensitive check at service layer in `app/services/observers.py`). |
| `display_name` | `String(255)` | Optional human-facing label. |
| `status` | `String(32)` | `active` / `inactive`. Managed via per-row Edit / bulk inactivate-reactivate on the Observers Setup page. |
| `tag_1` | `String(255)` | Single free-form label (no `tag_2` / `tag_3`). |

**Canonical spec:** `spec/setup_pages.md` (Reviewers / Reviewees /
Relationships / Observers preview tables, column toggles, per-page
column orders).

---

## 7. Browser-local UI state

State the operator implicitly drives via interaction; not persisted
server-side. Listed here so a developer chasing "where is this
preference stored?" finds the answer quickly.

### Cookies

| Cookie | Scope | Purpose |
|---|---|---|
| `qsu_{session_id}=1` | path `/`, `HttpOnly`, `SameSite=Lax` | Quick Setup card unlock state. Set by `POST /operator/sessions/{id}/quick-setup/lock?action=unlock`; cleared by a Starlette middleware in `app/main.py` whenever the operator navigates anywhere that isn't Session Home or a `/operator/sessions/{id}/quick-setup/...` endpoint (so leaving Home for the lobby, operator settings, or `/about` relocks the card on return). The path is `/` so the cookie is visible on every subsequent request — without that, navigations outside `/operator/sessions/{id}/` couldn't observe and clear the cookie. |
| `rrw-sort-{surface}-{session_id}[-{instrument_id}]` | path `/{operator\|reviewer}/sessions/{id}`, `SameSite=Lax`, 1-year Max-Age, **not** `HttpOnly` | Per-(browser, session, table) sort spec for any opt-in `<table data-rrw-sortable="...">`. Carries JSON `[{"key": "...", "dir": "asc|desc"}, ...]` in cascade order (max 3 entries; malformed JSON / unknown keys silently drop), **percent-encoded** by the browser (`encodeURIComponent`), so the SSR decoders must `unquote()` before `json.loads` (see `spec/sort_by_reviewee.md`). Surfaces: `rs` (reviewer-surface, one cookie per instrument), `reviewers` / `reviewees` / `relationships` / `assignments` / `invitations` / `responses` (operator setup + operations tables, one cookie per page). The three Setup tables also offer an `updated_at` sort key. Written by `_rrwWriteCookie` in `base.html` on every click; read by the JS on `DOMContentLoaded` to seed badges + by the route layer at render time so the initial HTML lands in the persisted order (no JS-reorder flicker). Clearing the sort writes an expired cookie. |

### `localStorage` (per browser, per origin; survives sessions)

| Key | Surface | Purpose |
|---|---|---|
| `rrw-reviewer-tag-visibility` | Setup > Reviewers preview table | Per-column toggle state (Tag1 / Tag2 / Tag3). |
| `rrw-reviewee-tag-visibility` | Setup > Reviewees preview table | Per-column toggle state (Photo / Tag1 / Tag2 / Tag3). |
| `rrw-relationship-tag-visibility` | Setup > Relationships preview table | Per-column toggle state (Tag1 / Tag2 / Tag3). |
| `rrw-assignment-col-visibility` | Operations > Assignments preview table | Per-column toggle state — three groups of three (Reviewer Tag{n} / Reviewee Tag{n} / Relationship Ctx{n}). Three chip rows, one key: the key rides on the table, not the row. |
| `rrw-invitation-tag-visibility` | Operations > Invitations table | Per-column toggle state (reviewer Tag1 / Tag2 / Tag3). |
| `rrw-response-tag-visibility` | Operations > Responses table | Per-column toggle state (reviewee Tag1 / Tag2 / Tag3). |
| `rrw-theme` | Chrome light/dark toggle (every page) | Display mode. Values `"light"` / `"dark"` (absent = light). Applied as `data-theme` on `<html>` — Light removes the attribute (bare `:root`), Dark stamps `data-theme="dark"` (the `:root[data-theme="dark"]` palette + `color-scheme: dark`). A synchronous no-FOUC `<script>` at the top of `base.html`'s `<head>` reads the key and sets the attribute before first paint; the shared `_partials/theme_toggle.html` pill (in the operator chrome + reviewer top bar) writes it. **Two-state, no OS-follow** (no `prefers-color-scheme`). Browser-local only — never synced to the server. `error.html` (standalone) carries its own copy of the same read-script + palette. |

**The six column-visibility keys share one implementation and no
naming scheme.** One primitive in `base.html` reads its key from the
table's `data-rrw-col-toggles` attribute, so the six keys are data,
not code — and **none of them may be renamed**, because a rename
silently resets every operator's saved columns on that page. That is
why Assignments says `col-visibility` where the rest say
`tag-visibility`; the inconsistency is cheaper than the reset. All
six are pinned by `tests/unit/test_column_visibility_primitive.py`;
the pattern itself is specified in `spec/setup_pages.md`.

### `sessionStorage` (per browser tab; cleared on tab close)

| Key | Surface | Purpose |
|---|---|---|
| `instrumentsScrollY:{path}` | Instruments page | Restore scroll position after a Save/Edit cycle reload. |

### URL state

| Param | Surface | Purpose |
|---|---|---|
| `?return_to=<path>` | Chrome-detour pages (Operator Settings, About) | Round-trip target for the `← Back to {{ return_to_label }}` back-link. |
| `?validated=1` | Session Home | Triggers a fresh validation run on this render. |
| `?activate=1` | Validate detail page | Surfaces the activate-warns acknowledgment banner. |
| `?quick_setup_error=…&quick_setup_reason=…` | Session Home | Slot-scoped error feedback after a failed Quick Setup submit. |
| `?rule_based_error=…` | Assignments page | Slot-scoped error feedback after a failed rule-based generate. |
| `?edit_id=<id>` | Reviewers / Reviewees / Relationships Setup pages | Server-rendered inline-Edit state — that row's cells render as inputs / pickers. |
| `?add=1` | Reviewers / Reviewees / Relationships Setup pages | Server-rendered Add-new-row state — a blank input row prepends the table. |
| `?selected=<id>` (repeatable) | Reviewers / Reviewees / Relationships Setup pages | Row selection carried through the post-Edit / post-bulk-action redirect so the acted-on rows stay checked. |
| `?status=…` / `?q=…` | Reviewers / Reviewees / Relationships / Observers Setup pages | Operator-actions status filter (`all` / `active` / `inactive`) + search term, one shape on all four pages. Preserved through Edit / bulk actions via hidden `filter_status` / `filter_q` form fields. One search box per page, no side-picker — see `spec/setup_pages.md` "Search matching and suggestions". |
| `?template={invitation\|reminder\|responses_received}` | Email Template page (`/operator/sessions/{id}/setup-invite`) | Selects which of the three template tabs is active. Defaults to `invitation`. |
| `?editing=…&saved=…` plus `?rf_save_error=…` flash params | Instruments page | Per-instrument editing target + post-Save success flash, plus flash params for response-field errors and would-empty / delete-blocked confirmation flows. |

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
| `FAKE_AUTH_OPERATOR` | `True` | Sandbox-only: the fake identity is seeded as operator. Honoured only when `ALLOW_FAKE_AUTH` is also `True`; inert in deployed envs. |
| `FAKE_AUTH_SYS_ADMIN` | `True` | Sandbox-only: the fake identity is seeded as sys-admin (admin tier). Same gating. |
| `FAKE_AUTH_SUPER_ADMIN` | `True` | Sandbox-only: the fake identity is treated as **super-admin** — its email is folded into the effective super-admin set by `app/auth/roles.py`. Honoured only when `ALLOW_FAKE_AUTH` is also `True`, so the localhost operator holds super-admin for testing with zero env coordination; inert in deployed envs. |
| `OPERATOR_EMAILS` | empty | Comma-separated operator allowlist (first-sign-in bootstrap of `users.is_operator`). |
| `SYS_ADMIN_EMAILS` | empty | Comma-separated admin allowlist (first-sign-in bootstrap of `users.is_sys_admin`). In a deployed env, at least one of `OPERATOR_EMAILS` / `SYS_ADMIN_EMAILS` must be non-empty or the app refuses to boot. |
| `SUPER_ADMIN_EMAILS` | empty | Comma-separated **super-admin** allowlist — the protected top tier. **Derived, not stored**: `is_super_admin` is computed from this list (case-insensitive), never a DB column, so it can't drift or be flipped in-app. Set **only** via App Settings. Optional (not part of the boot fail-fast); a super-admin self-heals to full admin rights on every sign-in and can't be demoted/removed in-app. |
| `DATABASE_URL` | `sqlite:///./review_robin_web.db` | SQLAlchemy connection string. Postgres in deployed environments; SQLite locally / in tests. |
| `SMTP_ENCRYPTION_KEY` | `None` | Symmetric Fernet key (Base64-urlsafe-encoded 32 bytes) used to encrypt operator SMTP passwords at rest. Generate with `cryptography.fernet.Fernet.generate_key()`. Fail-loud at encrypt / decrypt time, not at startup, so local dev / tests that don't touch Operator Settings don't need it set. |
| `AUDIT_STRICT_MODE` | `False` | When `True`, `audit.write_event` raises on a detail-shape violation. Production stays `False` (logs + writes through). Test runner flips to `True` so drift surfaces in CI. |

**Canonical spec:** `docs/local_setup.md` (env-var setup),
`docs/deployment_dev.md` (deployment-side configuration),
`docs/security_posture.md` (Easy Auth + `ALLOW_FAKE_AUTH`).

---

## 8.5. Internal display switches (source constants)

Listed for context — these are neither operator- nor
deployer-determined. They are module-level constants in `app/`,
flipped by editing the source and restarting; no env var, no
database migration, no UI. Reserved for display-shape decisions
that a deployment might want to reverse without a feature-flag
framework.

| Constant | Default | Purpose |
|---|---|---|
| `date_formatting.SHOW_ZONE_TOKEN` | `False` | When `True`, the `format_datetime` helper appends the resolved zone's `%Z` token (`UTC` / `+08` / `EDT`) to every date-time render, and both timezone-card live previews follow via the operator Jinja env's `show_zone_token` global. Off by default — IANA reports a numeric offset for many zones and a letter code for others, so the mixed token reads unevenly; the zone is instead named on the `/operator/settings` and Session Edit cards. |

---

## 9. `session_rule_sets` — backing store for Band 1's inline rule editor

``session_rule_sets`` is the only RuleSet tier: `instruments.rule_set_id`
points into it, Band 1's inline editor on the per-instrument card is the
sole authoring surface, and rows are auto-managed by `set_band1_*`
service calls.

Per-session rule rows. Each row carries a complete snapshot of
the rule tree.

| Field | Type | Notes |
|---|---|---|
| `session_id` | `Integer` (FK → `sessions.id` ON DELETE CASCADE) | Owning session. |
| `name` | `String(255)` | Snapshot name. Unique per session via `uq_session_rule_set_session_name`. |
| `description` | `Text` | Snapshot description. |
| `combinator` | `String(16)` | `ALL_OF` / `ANY_OF` / `PIPELINE` — see `app/schemas/rules.py::Combinator`. |
| `exclude_self_reviews` | `Boolean` | Vestigial — the engine layer hardcodes `excludeSelfReviews=False` regardless (project-wide policy; see `spec/assignments.md` "Self-review policy"). Every row is `False`: `_create_band1_rule_set` writes `False` on every save. |
| `seed` | `Integer` | Global RNG seed for any RANDOM-strategy quota rule whose own selection seed is unset. |
| `rules_json` | `JSON` | Serialised rule tree. Schema validated against `RuleSetSchema` in `app/schemas/rules.py`. Empty list = Full Matrix. |

**Canonical spec:** `spec/assignments.md` (engine + Assignments
page); `spec/instruments.md` § Band 1 (per-instrument authoring
surface). Backing model: `app/db/models/session_rule_set.py`.

---

## 9.5. `data_shapes` — operator-saved Data shaper shapes

Per-session library of custom column compositions the operator
composes via the Data shaper card and downloads as CSVs.
``UNIQUE (session_id, name)`` keeps shape names unique inside
a session. Round-trips through the Settings CSV via portable
references (instrument by ``short_label``, response field by
``field_key``) — see §10 below.

| Field | Type | Notes |
|---|---|---|
| `session_id` | `Integer` (FK → `sessions.id` ON DELETE CASCADE) | Owning session. |
| `name` | `String(255)` | Operator-typed name; unique per session via `uq_data_shape_session_name`. |
| `axis` | `String(16)` | ``reviewer`` / ``reviewee`` — drives the row-key contract (see `guide/archive/extract_data.md` § *Row-key semantics*). |
| `instrument_id` | `Integer` (FK → `instruments.id` ON DELETE CASCADE; nullable) | Scope-filter chip: NULL = aggregates span every session instrument. |
| `response_field_id` | `Integer` (FK → `instrument_response_fields.id` ON DELETE CASCADE; nullable) | Scope-filter chip: NULL = aggregates span every field on the chosen instrument. |
| `column_chip_slots` | `Text` (JSON list) | Operator's column-chip selection in click order. Drives the preview-row + CSV header order. |
| `self_review_handling` | `String(16)` | Self-review handling chip state: ``include_self`` (default) / ``exclude_self`` / ``both``. Drives the column-name suffix (`_self` / `_noself` / `_both`), filename suffix, audit ``context.self_review_handling`` slot, and the in-pool ``Assignment.is_self_review.is_(False)`` filter on the non-default states. |
| `include_empty_rows` | `Boolean` | Empty-row drop chip state: ``True`` (default, "All rows" — every relevant row ships, including empty ones) / ``False`` ("Rows with data" — drops body rows whose ``_Acc.is_empty()`` on per-individual / per-tag-combo shapes; single-summary always emits its one row). |
| `created_by_user_id` | `Integer` (FK → `users.id` ON DELETE SET NULL; nullable) | Audit-trail anchor for the operator who saved the shape. |

**Canonical spec:** `guide/archive/extract_data.md` (the
shipped feature surface). Backing model:
`app/db/models/data_shape.py`. File-gen lives in
`app/services/extracts/data_shape_extract.py`; service-layer
CRUD + validation lives in `app/services/data_shapes.py`.

---

## 10. CSV export / import coverage

> **Inclusion rule:** *if the operator were setting up an
> equivalent new session from scratch, would they have to retype
> this?* Yes → in the export. No (machine-derived from operator
> typing, system-emitted record, per-instance state, or per-operator
> credential) → excluded.

The CSVs split the work three ways:

1. **Settings CSV** (`{code}_settings.csv`) — 3-column
   `field,value,data_type` shape capturing every per-session
   configuration field the operator typed.
2. **Per-entity CSVs** (`{code}_reviewers.csv`,
   `{code}_reviewees.csv`, `{code}_relationships.csv`,
   `{code}_observers.csv`) — round-trip with the per-entity
   importers. **There is no `{code}_assignments.csv`:** assignments
   are derived (rule-based engine + roster + relationships), not an
   input to a new session, so the download has no place in a
   porting bundle. The RuleSet selection itself travels in the
   Settings CSV via the per-instrument `rule_set_name` field.
3. **Responses CSV** (`{code}_responses.csv`) — wide
   row-per-observation shape for downstream analysis.
   **Independent of the porting workflow** — no import
   counterpart, not part of round-trip.

### Coverage by inventory section

| § | Section | In CSV? | Where / why |
|---|---------|---------|-------------|
| §1 | Operator-level (`users` + SMTP) | ❌ | Per-operator credentials + identity, not per-session. Each operator configures their own. |
| §2 | Per-session metadata | ✅ All | `name`, `code`, `description`, `deadline`, `help_contact`, `display_timezone`, `self_reviews_active`, `relationships_enabled`, `observers_enabled`, plus the eight scheduled-event columns (`scheduled_activate_at`, `responses_release_at`, `responses_release_until`, `invite_offsets`, `reminder_offsets`, `archive_offset`, `retention_exception`, `retention_overrides`) → Settings CSV. `status` and `assignment_mode` are machine-derived (excluded); `created_by_user_id` is identity (excluded). `relationships_enabled` / `observers_enabled` (the participant-model feature toggles) are force-applied on import — config, not operator-typed identity. On import, `name` / `code` / `description` / `deadline` / `help_contact` are **fallback values** (applied only when the destination field is blank); every other slot — `display_timezone`, `self_reviews_active`, both feature toggles, and the eight scheduled-event columns — is **force-applied** because each is session config, not operator-typed identity, and the fallback rule would never fire (a created session always has them set). |
| §3 | Email-template overrides | ✅ All | All 12 string keys + `responses_received_enabled` → Settings CSV. None / `""` / key-absent collapse to empty cell on export; importer treats empty as "use the default". |
| §4 | Per-instrument | ✅ All | All operator-typed columns → Settings CSV. **Instrument-level:** `name` / `short_label` / `description` / `order` / `accepting_responses` / `responses_visible_when_closed` / `sort_display_fields` / `group_kind` / `rule_set_id` (resolved to `rule_set_name`) / `column_widths` (Band 2 drag-gripper widths) / `starts_new_page` (18M page-break flag) / `band2_state` (Band 2 chip selections + sample-reviewee pick + sample-group-member-ids). **Per response field:** `field_key` / `label` / `response_type` / `required` / `help_text` / `help_text_visible` / inline `data_type` / `min` / `max` / `step` / `list_csv` / `visible`. **Per display field:** `source_type` / `source_field` / `visible`. **Per-instrument visibility policy:** the `instruments[n].view_policies[<audience>].*` rows (the 3 × 2 chip grid — Reviewers / Reviewees / Observers × Session-ongoing / Responses-released, each Raw / Anonymized / Summarized; see `spec/visibility_policy.md`). The columns take only the values legal for their `(audience, window)` **cell**, not merely any word from the vocabulary: the import validates each cell against `_PER_CELL_VALID_MODES` and rejects the apply with a named error on an illegal one — a `reviewee` `while_ongoing` grant being the case that matters, since it is the one with a disclosure behind it (`spec/visibility_policy.md` §3.1). **Band 1 link rule:** `band1_touched_links` (the operator's hand-touched link set). `deadline_closed_at` is machine-derived (excluded). `rule_set_id` is the sole source of truth for a pinned instrument — there is no fallback to an audit row. |
| §5 | Reviewers / Reviewees / Relationships / Observers | ✅ All | Reviewers / Reviewees / Relationships / Observers each in their own per-entity CSV; round-trips with the existing importers (`reviewers.imported` / `reviewees.imported` / `relationships.imported` / `observers.imported` audit-event paths). The `{code}_observers.csv` download is exposed on the Extract Setup card (conditionally, when `observers_enabled`) via `GET /operator/sessions/{id}/export/observers.csv`; the Zip-all bundle includes it when the toggle is on. |
| §7 | Browser-local UI state | ❌ | Cosmetic per-browser preferences; carry over via the operator's own browser, not via export. |
| §8 | Deployer env config | ❌ | Deployer-set; not operator-determined. |
| §2.5 | `session_field_labels` (per-session friendly labels) | ✅ Roster headers | Round-trip via the **roster CSV headers** as the sole carrier: the tag friendly label rides on its column as a `ReviewerTag1.<label>` suffix. **Not** in the Settings CSV (a stale `field_labels.*` row in an old bundle is silently ignored on apply). Allowlist: the nine tag slots, via `field_label_csv._LABELABLE_COLUMNS`. |
| §9 | `session_rule_sets` | Partial | All rows → Settings CSV. The export emits no `library_name` cell, and **an unrecognized `session_rule_sets[n].<attr>` row on input is rejected, not skipped**: the parse phase raises and the whole apply fails before anything is written. The strictness is deliberate and it is not the unknown-key silent ignore that covers top-level paths — a rule set is the one structure where a misspelled attribute would otherwise be dropped in silence and change which pairs generate. The cost is that a bundle exported while `library_name` existed cannot be imported without that column removed first. |
| §9.5 | `data_shapes` | ✅ All | Each saved Data shape ships 7 `data_shapes[N].*` rows in the Settings CSV — `name`, `axis`, `instrument_short_label` (portable ref), `response_field_key` (portable ref), `column_chip_slots` (JSON list), `self_review_handling` (Self-review handling chip state), and `include_empty_rows` (Empty-row drop chip state). Shapes round-trip cleanly across sessions whose instruments + response fields match by `short_label` / `field_key`; unresolved refs at import drop the shape's FK columns to NULL (CASCADE-on-instrument-delete handles the same case post-import). **A bundle missing either chip row still imports:** absent `self_review_handling` applies `include_self`, absent `include_empty_rows` applies `True` — the chip defaults. An unrecognized `self_review_handling` string falls back to `include_self` rather than failing the apply. |
| n/a | Responses (reviewer-typed) | ✅ (analytics only) | `{code}_responses.csv` — wide row-per-observation shape for downstream analysis. **No import counterpart**, no round-trip. |
| n/a | Audit events (`audit_events`) | ✅ (analytics only) | `{code}_audit_log.csv` — 7-column wide CSV (`EventType` / `Severity` / `Summary` / `ActorEmail` / `CorrelationId` / `CreatedAt` / `DetailJson`) with the canonical detail envelope JSON-encoded in the trailing column. **No import counterpart**, no round-trip — audit events are system-emitted. The route carries **no Extract Data tile**: the operator-facing surface is the Sys Admin page's per-session Diagnostics row, which is where audit-data downloads belong. **The ✅ is about the extract, not about this inventory**: audit events are system-emitted, so they are outside the operator-settings scope this document covers (see the top-of-doc exclusion) and there is nothing here to round-trip. The row is listed so a reader looking for the audit CSV finds it. |

### Bundles

Two zip bundles: the **setup bundle** (`{code}_setup.zip`,
all setup CSVs including Observers when enabled) via the Extract
Setup card's Zip-all tile, and the **responses bundle**
(`{code}_responses.zip`) via the Extract data Operations tab. The
import side always reads **a single Settings CSV per upload** — no
bundle importer.

**Canonical spec:** `spec/csv_contracts.md` (column shapes, parsing
rules, and the round-trip stability contract).

---

## See also

- `app/config.py` — env-config source of truth.
- `app/db/models/` — SQLAlchemy declarations for every persisted
  setting named here. The §2.5 / §9 backing tables live in
  `session_field_label.py` and `session_rule_set.py`.
- `app/services/operator_settings.py` — Operator Settings save /
  load flow.
- `app/services/email_templates.py` — `OVERRIDE_KEYS` +
  `RESPONSES_RECEIVED_ENABLED_KEY`.
- `app/main.py` — Quick Setup unlock-cookie navigation
  middleware (mirrors the `qsu_` prefix in
  `app/web/routes_operator/_shared.py`).
- `spec/csv_contracts.md` — the CSV export / import contract
  referenced by §10.
- `spec/setup_pages.md` — the inline-editable Setup rows + Add +
  Inactivate / Reactivate UI for Reviewers / Reviewees /
  Relationships / Observers.
