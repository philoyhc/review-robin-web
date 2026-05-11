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
email-infra story; `spec/operator_button_audit.md` Section 15 + 15-supplement
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
| `assignment_mode` | `String(32)` | `manual` / `rule_based`. **Not directly editable** — set by whichever assignment-generation path the operator runs. Post-15D, the rule-based engine is the only operator-facing path (sets `rule_based`); the legacy Manual CSV upload (sets `manual`) survives as a dev-diagnostic surface only. |
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
| `sort_display_fields` | `JSON` | Operator-defined default sort spec for this instrument's reviewer-surface table (Segment 13B). NULL = "no operator default". **Inert** until 13B's render-path slice consumes it (landed in 13D PR 5). |
| `group_kind` | `String(32)` | Group-scoping flavour for Segment 13C's group-scoped instruments — one shared answer covers a whole group of reviewees instead of per-reviewee. NULL = "regular per-reviewee instrument". **Inert** until 13C wires the render adapter (landed in 13D PR 6). |
| `rule_set_id` | `Integer` (FK → `session_rule_sets.id` ON DELETE SET NULL) | Per-instrument selection of which `session_rule_sets` row applies (Segment 15B). NULL = "no RuleSet currently selected" — the initial state for every existing instrument and the state after a reset-assignments action. **Inert** until 15B Slice 2 wires per-instrument selection (landed in 13D PR 4). |
| Display fields (per-instrument list) | rows in `instrument_display_fields` | Operator picks which reviewee attributes (name, email, tags, etc.) the reviewer sees on the response surface. |
| Response fields (per-instrument list) | rows in `instrument_response_fields` | The actual question schema — labels, types, options. Each row references a `response_type_definitions` row (see §4.5 below) via `response_type_id`. |

**Canonical spec:** `spec/instruments.md`.

---

## 4.5. Per-session Response Type Definitions

Stored on the `response_type_definitions` table — one row per RTD,
scoped to a session. Per-session RTDs are the source of truth for
`instrument_response_fields.response_type_id`; the operator-library
tier (`operator_response_type_definitions`, see §9) auto-copies into
this table on session create.

**Surface:** Instruments page > "Response Types" card (per-session
list with add / edit / delete actions; deletes are blocked when the
RTD is referenced by any response field).

| Field | Type | Notes |
|---|---|---|
| `response_type` | `String(64)` | Operator-chosen name (e.g. `"Likert5"`, `"GPA4"`). Unique per session via `uq_rtd_session_name`. |
| `data_type` | `String(16)` | `int` / `decimal` / `short_text` / `long_text` / `list`. |
| `min` | `Float` | Lower bound for numeric types; NULL for text / list. |
| `max` | `Float` | Upper bound for numeric types; NULL for text / list. |
| `step` | `Float` | Discrete step; NULL when unbounded. |
| `list_csv` | `Text` | Comma-separated option list for `list`-type RTDs; NULL otherwise. |
| `is_seeded` | `Boolean` | `True` for RTDs auto-materialised from the seed catalogue at session create; `False` for operator-authored. |
| `seed_order` | `Integer` | Sort key for seeded rows in their canonical install order. |
| `library_origin_id` | `Integer` (FK → `operator_response_type_definitions.id` ON DELETE SET NULL) | Provenance pointer to the operator-library row this per-session copy was cloned from (Segment 15C). NULL when seeded, authored directly in the session, or when its library origin has since been deleted. **Provenance only** — never read for resolution; the per-session row is the source of truth. **Inert** until 15C wires Save-to-library / Add-from-library (landed in 13D PR 3). |

**Canonical spec:** `spec/instruments.md` (Response Types card);
`app/services/instruments/_rtds.py` (CRUD + seed materialisation).

---

## 5. Per-reviewer / per-reviewee / per-pair data

Stored on `reviewers`, `reviewees`, and `relationships` tables.
Owned by the session. Tags are operator-determined; status is a
mix of operator action (soft-delete via Inactivate, deferred to
Segment 15F) and system state.

**Surface:** Setup Pages — `/operator/sessions/{id}/reviewers`,
`/operator/sessions/{id}/reviewees`, and
`/operator/sessions/{id}/relationships`. Bulk-populated via Quick
Setup or per-entity CSV; managed inline (Manage rows are
read-only today; inline edit deferred to Segment 15F per
`guide/segment_15F_enhanced_setup_pages.md`).

### Reviewer

| Field | Type | Notes |
|---|---|---|
| `name` | `String(255)` | |
| `email` | `String(320)` | Identity used for invitation matching. |
| `status` | `String(32)` | `active` / `inactive`. Inactivate UI deferred to Segment 15F (`guide/segment_15F_enhanced_setup_pages.md`). |
| `tag_1`, `tag_2`, `tag_3` | `String(255)` | Free-form labels. Used by rule-based assignment matching and surfaced on the reviewer surface when the corresponding column toggle is enabled. |

### Reviewee

| Field | Type | Notes |
|---|---|---|
| `name` | `String(255)` | |
| `email_or_identifier` | `String(320)` | Identity (may be a non-email identifier in non-email cohorts). |
| `profile_link` | `String(2000)` | Optional URL or photo link. |
| `status` | `String(32)` | `active` / `inactive`. |
| `tag_1`, `tag_2`, `tag_3` | `String(255)` | Same shape as reviewer tags. |

### Relationship (per-pair, post-15D)

Per-pair attributes table — one row per `(session_id, reviewer_id,
reviewee_id)` triple. The home for pair-context tags, lifted out
of `assignments` so per-pair attributes exist independently of
whether the rule engine has materialised an assignment for the
pair (Segment 13E PR 2 + 15D). The legacy
`Assignment.context.pair_context_*` JSON column it replaced was
dropped in 15D PR 6b.

| Field | Type | Notes |
|---|---|---|
| `reviewer_id` | `Integer` (FK → `reviewers.id` ON DELETE CASCADE) | Identity. |
| `reviewee_id` | `Integer` (FK → `reviewees.id` ON DELETE CASCADE) | Identity. Unique with `reviewer_id` per session via `uq_relationships_session_reviewer_reviewee`. |
| `tag_1`, `tag_2`, `tag_3` | `String(255)` | Free-form pair-context labels. Consumed by the rule-based engine via the eager `pair_context_lookup` dict (15D PR 4). Surfaced as the third Ctx-toggle group on the Assignments preview table. |
| `status` | `String(32)` | `active` / `inactive`. Defaults to `active`. |

**Canonical spec:** `spec/setup_pages.md` (Reviewers / Reviewees /
Relationships preview tables, column toggles, per-page column
orders).

---

## 6. Per-user RuleSets (rule-based assignment)

Stored on `operator_rule_sets` + `rule_set_revisions`. Each user can
save **Personal** RuleSets visible only to them; seeded RuleSets are
read-only and shared. (The table was renamed from `rule_sets` →
`operator_rule_sets` in Segment 13D PR 0 to mirror the upcoming
library tier added in 13D PR 2 — see `session_rule_sets` in §9.)

**Surface:** Rule Builder — `/operator/sessions/{id}/assignments/rule-based-editor`.

### `operator_rule_sets`

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
| `combinator` | `String(16)` | `ALL_OF` / `ANY_OF` / `PIPELINE` — see `app/schemas/rules.py::Combinator`. |
| `exclude_self_reviews` | `Boolean` | Default for runs against this revision. The override on the main Assignments page wins when present. |
| `seed` | `Integer` | Global RNG seed for any RANDOM-strategy quota rule whose own selection seed is unset. |
| `rules_json` | `JSON` | The full rule list. Schema validated against `RuleSetSchema` in `app/schemas/rules.py`. |
| `created_at` | `DateTime(timezone=True)` | When this revision was committed. Distinct from the `TimestampMixin` pair on `operator_rule_sets` because `rule_set_revisions` is append-only. |
| `created_by_user_id` | `Integer` (FK → `users.id`, nullable) | Who committed this revision. NULL on seeded revisions inserted by migrations / fixtures. |

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
| `qsu_{session_id}=1` | path `/`, `HttpOnly`, `SameSite=Lax` | Quick Setup card unlock state. Set by `POST /operator/sessions/{id}/quick-setup/lock?action=unlock`; cleared by a Starlette middleware in `app/main.py` whenever the operator navigates anywhere that isn't Session Home or a `/operator/sessions/{id}/quick-setup/...` endpoint (so leaving Home for the lobby, operator settings, or `/about` relocks the card on return). The path is `/` so the cookie is visible on every subsequent request — without that, navigations outside `/operator/sessions/{id}/` couldn't observe and clear the cookie. |

### `localStorage` (per browser, per origin; survives sessions)

| Key | Surface | Purpose |
|---|---|---|
| `rrw-reviewer-tag-visibility` | Setup > Reviewers preview table | Per-column toggle state (Tag1 / Tag2 / Tag3). |
| `rrw-reviewee-tag-visibility` | Setup > Reviewees preview table | Per-column toggle state (Photo / Tag1 / Tag2 / Tag3). |
| `rrw-relationship-tag-visibility` | Setup > Relationships preview table | Per-column toggle state (Tag1 / Tag2 / Tag3). |
| `rrw-assignment-col-visibility` | Operations > Assignments preview table | Per-column toggle state — three groups of three (Reviewer Tag{n} / Reviewee Tag{n} / Relationship Ctx{n}). The legacy assignment-context group retired in 15D. |

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
| `?template={invitation\|reminder\|responses_received}` | Email Template page (`/operator/sessions/{id}/setup-invite`) | Selects which of the three template tabs is active. Defaults to `invitation`. |
| `?rule_set_id=…&new=…&draft_from=…&previous_id=…&saved=…&error=…` | Rule Builder | Round-trip state for the picker / Save flow — which RuleSet the page opened with, whether this is a fresh draft, the draft's source row, the prior selection (so Cancel returns), the just-saved id (drives the success flash), and a slot-scoped error token. |
| `?editing=…&saved=…` plus `?rtd_*=…` and `?rf_save_error=…` flash params | Instruments page | Per-instrument editing target + post-Save success flash, plus a family of flash params for RTD / response-field errors and would-empty / delete-blocked confirmation flows. |

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

## 9. Pre-positioned (inert) schema for upcoming surfaces

Tables / columns that landed in Segment 13D as schema-only
scaffolding ahead of Segments 15A / 15B / 15C. **Inert today** — no
service module reads or writes them and no UI surfaces them yet —
but listed here so a developer auditing "where will this setting
live?" finds the answer without reading the segment plans.

When the wiring lands, the corresponding row should move out of
this section into the appropriate per-feature section above (e.g.
`session_field_labels` into a new sub-section under §2 once 15A
ships its resolver + Settings editor).

### `session_field_labels` (Segment 15A target)

Per-session friendly-label overrides for tag / pair-context
fields. One row per `(session_id, source_type, source_field)`
override.

| Field | Type | Notes |
|---|---|---|
| `session_id` | `Integer` (FK → `sessions.id` ON DELETE CASCADE) | Owning session. |
| `source_type` | `String(32)` | `reviewer` / `reviewee` / `pair_context`. (The legacy `assignment_context` source class retired with `Assignment.context` in 15D PR 6b; not a widening target.) |
| `source_field` | `String(64)` | e.g. `tag_1` / `tag_2` / `tag_3` for the tag sources; `1` / `2` / `3` for `pair_context`. |
| `label` | `String(255)` | The override label. |

Unique on `(session_id, source_type, source_field)`. Wired by
15A Slice 1 (`app/services/field_labels.py` resolver) and Slice
3 (Settings editor surface).

**Canonical spec:** `guide/segment_15A_friendly_labels.md`.

### `session_rule_sets` (Segment 15B + 15C target)

Per-session snapshot copies of RuleSets. Each row carries a
complete snapshot of the rule tree at copy / edit time;
`library_origin_id` links back to the operator-library row it
was cloned from (provenance only).

| Field | Type | Notes |
|---|---|---|
| `session_id` | `Integer` (FK → `sessions.id` ON DELETE CASCADE) | Owning session. |
| `name` | `String(255)` | Snapshot name. Unique per session via `uq_session_rule_set_session_name` (Segment 13A-2). |
| `description` | `Text` | Snapshot description. |
| `combinator` | `String(16)` | `ALL_OF` / `ANY_OF` / `PIPELINE`. |
| `exclude_self_reviews` | `Boolean` | Snapshot flag. |
| `seed` | `Integer` | Global RNG seed. |
| `rules_json` | `JSON` | Serialised rule tree — same shape as `rule_set_revisions.rules_json`. |
| `library_origin_id` | `Integer` (FK → `operator_rule_sets.id` ON DELETE SET NULL) | Provenance pointer; never read for resolution. NULL when the row was authored directly in the session or the library origin has been deleted. |

Wired by 15B Slice 2 (`instruments.rule_set_id` points into this
table) and 15C (auto-copy from operator library on session
create + Save-to-library flow).

**Canonical spec:** `guide/segment_15B_per_instrument_assignments.md`,
`guide/segment_15C_operator_libraries.md`.

### `operator_response_type_definitions` (Segment 15C target)

Operator-library tier for Response Type Definitions — RTDs visible
across all of an operator's sessions. Auto-copied into a
session's `response_type_definitions` rows on session create.

| Field | Type | Notes |
|---|---|---|
| `owner_user_id` | `Integer` (FK → `users.id` ON DELETE CASCADE) | Owning operator. |
| `response_type` | `String(64)` | Operator-chosen name (e.g. `"Likert5"`). Unique per owner via `uq_operator_rtd_owner_name`. |
| `data_type` | `String(16)` | `int` / `decimal` / `short_text` / `long_text` / `list`. Same value-set as `response_type_definitions.data_type`. |
| `min`, `max`, `step` | `Float` | Numeric bounds; NULL for non-numeric types. |
| `list_csv` | `Text` | Comma-separated option list for `list`-type RTDs. |

Wired by 15C (auto-copy on session create + Add-from-library /
Save-to-library actions on the per-session RTD card).

**Canonical spec:** `guide/segment_15C_operator_libraries.md`.

---

## 10. CSV export / import coverage

Two segment plans co-author the porting / template-capture
workflow:

- **`guide/archive/segment_12A-1_export.md`** — five CSVs off the Extract
  Data card on Session Home (settings, reviewers, reviewees,
  manual assignments, responses). Fully shipped 2026-05-09 across
  PRs #713, #716, #717, #718, #721.
- **`guide/segment_12A-3_export_import_updates.md`** — Settings
  CSV importer (absorbed from 12A-2) + Relationships per-entity
  export + import (parallel to rosters) + manual-assignments CSV
  adjustments around 15D's "always derived" model. Planned, 4
  PRs. (The earlier `guide/segment_12A-2_import.md` is kept as a
  historical-reference document for the Settings importer
  contract — the implementation lands as 12A-3 PR 1.)

> **Inclusion rule** (paraphrased from 12A-1): *if the operator
> were setting up an equivalent new session from scratch, would
> they have to retype this?* Yes → in the export. No
> (machine-derived from operator typing, system-emitted record,
> per-instance state, or per-operator credential) → excluded.

The five CSVs split the work three ways:

1. **Settings CSV** (`{code}_settings.csv`) — 3-column
   `field,value,data_type` shape capturing every per-session
   configuration field the operator typed. Round-trip target for
   12A-2.
2. **Per-entity CSVs** (`{code}_reviewers.csv`,
   `{code}_reviewees.csv`, `{code}_relationships.csv`) —
   round-trip with the existing per-entity importers. The
   relationships CSV ships in 12A-3 PR 1 alongside its
   importer (already shipped in 15D). The legacy
   `{code}_assignments.csv` retired in 12A-3 PR 2 —
   assignments are derived (rule-based engine + roster +
   relationships), not an input to a new session, so the
   download has no place in a porting bundle. The RuleSet
   selection itself travels in the Settings CSV via the
   per-instrument `rule_set_name` field.
3. **Responses CSV** (`{code}_responses.csv`) — wide
   row-per-observation shape for downstream analysis.
   **Independent of the porting workflow** — no import
   counterpart, not part of round-trip.

### Coverage by inventory section

| § | Section | In CSV? | Where / why |
|---|---------|---------|-------------|
| §1 | Operator-level (`users` + SMTP) | ❌ | Per-operator credentials + identity, not per-session. Each operator configures their own. |
| §2 | Per-session metadata | Partial | `name`, `code`, `description`, `deadline`, `help_contact` → Settings CSV. `status` and `assignment_mode` are machine-derived (excluded); `created_by_user_id` is identity (excluded). On import, `name` / `code` / `description` / `deadline` / `help_contact` are **fallback values** — applied only when nothing more authoritative is present. |
| §3 | Email-template overrides | ✅ All | All 12 string keys + `responses_received_enabled` → Settings CSV. None / `""` / key-absent collapse to empty cell on export; importer treats empty as "use the default". |
| §4 | Per-instrument | Partial | All operator-typed columns → Settings CSV, including the inert `sort_display_fields` / `group_kind` / `rule_set_id` (resolved to `rule_set_name`). `deadline_closed_at` is machine-derived (excluded). Pre-15B, `rule_set_id` is universally NULL — 12A-1 PR 1a falls back to the latest `assignments.generated` audit row's `refs.rule_set_id` for **seeded** RuleSets only. |
| §4.5 | Per-session RTDs | Partial | Operator-defined (`is_seeded=False`) rows → Settings CSV. Seeded RTDs are excluded — they auto-regenerate from `SEED_RESPONSE_TYPE_DEFINITIONS` on session create. `library_origin_id` is provenance-only (excluded). |
| §5 | Reviewers / Reviewees / Relationships | ✅ All | Each in its own per-entity CSV; round-trips with the existing importers (`reviewers.imported` / `reviewees.imported` / `relationships.imported` audit-event paths). Relationships shipped in 12A-3 PR 1 (importer was already shipped in 15D PR 1). |
| §6 | Operator-library RuleSets (`operator_rule_sets`) | ❌ | Workspace-scoped (per-operator across sessions), not per-session. Portability is deferred to its own segment; travels as JSON, not CSV. |
| §7 | Browser-local UI state | ❌ | Cosmetic per-browser preferences; carry over via the operator's own browser, not via export. |
| §8 | Deployer env config | ❌ | Deployer-set; not operator-determined. |
| §9 | `session_field_labels` (inert, 15A target) | ✅ All | All listed columns → Settings CSV. Serialises empty rows today; pinning the key shape now means future-equipped sessions round-trip without an export-shape change once 15A lights up. |
| §9 | `session_rule_sets` (inert, 15B / 15C target) | Partial | Non-seeded rows → Settings CSV. Seeded copies are excluded — they auto-materialise from `app/services/rules/seeds.py` via `materialise_seed_rule_sets` on session create. `library_origin_id` is provenance-only (excluded). |
| §9 | `operator_response_type_definitions` (inert, 15C target) | ❌ | Workspace-scoped, parallel to §6. |
| n/a | Responses (reviewer-typed) | ✅ (analytics only) | `{code}_responses.csv` — wide row-per-observation shape for downstream analysis. **No import counterpart**, no round-trip. |
| n/a | Audit events (`audit_events`) | ✅ (analytics only) | `{code}_audit_log.csv` (Segment 12B PR 1) — 8-column wide CSV (`EventType` / `Severity` / `Summary` / `ActorEmail` / `CorrelationId` / `CreatedAt` / `DetailJson`) with the canonical Segment 11K detail envelope JSON-encoded in the trailing column. **No import counterpart**, no round-trip — audit events are system-emitted. The route ships live but **without an Extract Data tile** — operator-facing surface relocates to the Sys Admin page when Segment 16 ships, per industry best practice for audit-data downloads. |
| n/a | Audit events (`audit_events`) | ❌ | System-emitted; out of inventory scope per the top-of-doc exclusion. |

### Deferred follow-ons

- **Zip bundle** — single `/export.zip` covering all CSVs in
  one click. Deferred follow-on of the 12A-1 export track;
  orthogonal to the import side, which always reads a single
  Settings CSV per upload.
- **Operator-library RTD / RuleSet portability** — workspace-
  scoped (per-operator across sessions). Anchored on Operator
  Settings + Rule Builder; lives on a separate import / export
  surface and travels as JSON. Excluded from the per-session
  Settings CSV by design.

**Canonical specs:** `guide/archive/segment_12A-1_export.md` (export
CSV shapes + inclusion rule),
`guide/segment_12A-3_export_import_updates.md` (Settings
importer + Relationships export + import + post-15D
assignments-CSV adjustments). The earlier
`guide/segment_12A-2_import.md` is kept as historical reference
for the Settings importer contract.

---

## See also

- `app/config.py` — env-config source of truth.
- `app/db/models/` — SQLAlchemy declarations for every persisted
  setting named here. The §9 inert tables live in
  `session_field_label.py`, `session_rule_set.py`, and
  `operator_response_type_definition.py`; their docstrings link
  back to the segment plans that will wire them.
- `app/services/operator_settings.py` — Operator Settings save /
  load flow.
- `app/services/email_templates.py` — `OVERRIDE_KEYS` +
  `RESPONSES_RECEIVED_ENABLED_KEY`.
- `app/services/instruments/_rtds.py` — per-session RTD CRUD +
  `SEEDED_RESPONSE_TYPE_DEFINITIONS` seed catalogue.
- `app/main.py` — Quick Setup unlock-cookie navigation
  middleware (mirrors the `qsu_` prefix in
  `app/web/routes_operator/_shared.py`).
- `guide/archive/segment_13D_db_prep.md` — rationale for every §9
  inert table / column.
- `guide/archive/segment_12A-1_export.md` / `guide/segment_12A-3_export_import_updates.md`
  — CSV export / import contract referenced by §10.
  (`guide/segment_12A-2_import.md` is the superseded importer
  plan, kept as historical reference.)
- `guide/archive/unfinished_business.md` — catalog of deferred settings
  surfaces (e.g. inline-editable Manage rows #25, Inactivate UI
  #36).
