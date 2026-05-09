# Master todo sequence

Roadmap for working through the `guide/unfinished_business.md`
catalog. **Two files, two purposes:**

- **`guide/unfinished_business.md`** — the catalog. Every open
  item, with Why / Where / Plan. Read it for the detail.
- **This file** — the sequence. What's shipped, what's coming
  up, and why that order. Read it for the roadmap.

When you ship an item, tick it off in **both** files. When a
sub-segment plan exists (e.g. `guide/archive/segment_11B_session_home.md`),
that plan is the day-to-day source of truth for its own slices;
this file references it without duplicating its PR ladder.

---

## Done

Closed items, dense list. Each line names the catalog item (or a
named scope) and the date / PR refs that closed it.

### P0 — Stop the bleeding (Instruments UI ↔ data drift)

- **#13 — Fix Display Fields placeholder** — done 2026-05-01 (option 2: wired to existing routes).
- **#14 — Drop `pair_context_*` default seed; seed from import data** — done 2026-05-01 (lazy-seed + Alembic data migration).
- **#18 — "Add an instrument" button vs route** — done 2026-05-02 as Slice 5 of Segment 10D (Add + Delete with mutual-exclusion / `is_ready` / single-instrument gates and a native `confirm()` on Delete).
- **Segment 10D — Instruments rebuild end-to-end** — closed P0 (#220 → #268). Per-instrument card and Response Type Definitions card built around a single editing state machine, mutual-exclusion edit lock, save-time RF / RTD guards, banner auto-scroll convention, multi-instrument support.

### P1 — Test gaps + CI hardening

- **#15 — Backfill 10C integration tests** — done 2026-05-02. `bulk_set_visibility` + the `instruments.bulk_visibility_when_closed` audit covered in `tests/integration/test_bulk_visibility.py`. The other three originally-listed surfaces had been silently covered during Segment 10D.
- **#1 — Wire `ruff check` into CI** — done 2026-05-02. `ci.yml` now runs `ruff check .` between dependency install and pytest.
- **#19 — Roll session-status partial onto Reviewers / Reviewees / Assignments / Instruments** — done 2026-05-02. Original literal scope satisfied; actual work grew into a full chrome redesign (PRs #272 / #279 / #280–#290) on all 6 main session-scoped pages. Spawned the follow-on bundle #20 / #21 / #22 / #30 → all closed via 11A + 11B.
- **#20 — Complete chrome rollout to remaining session-scoped pages** — Operations Pages shipped 2026-05-02 (Invitations / Monitoring / Outbox carry the chrome with their own tab active). The two Home sub-pages (Edit Session / Validate detail) folded into Segment 11B's rethink.
- **#2 — Run pytest against Postgres in CI** — done 2026-05-02. `ci-postgres.yml` runs the full suite against a `postgres:16` service container after the Alembic round-trip; the `engine` fixture in `tests/conftest.py` honours `TEST_DATABASE_URL` / `DATABASE_URL`.

### P2 — Architectural debt

- **#4 — Single reviewer-session-state helper** — done 2026-05-02. New `ReviewerSessionState` dataclass + `reviewer_session_state()` helper in `responses.py`; `session_pill_for_reviewer` is a thin projection; `monitoring._reviewer_completion` deleted.
- **#3 — Move `_invalidate_if_validated` into the service layer** — done 2026-05-02. New public `lifecycle.invalidate_if_validated()` helper. Every mutating service calls it at the top with a service-local `reason`; route helpers gone. 11 new service-layer invariant tests.
- **#16 — `bulk_visibility_when_closed` invalidation policy** — done 2026-05-02 alongside #3. **Decision: visibility-when-closed is exempt** (it's a display flag, not part of the validation snapshot). Pinned in code at `instruments.bulk_set_visibility` and `lifecycle.set_responses_visible_when_closed` and in two regression tests.
- **#11 — Extract instruments-index template context to `views.py`** — done 2026-05-02. New `build_instruments_context()` in `app/web/views.py` owns the 5 idempotent backfills, the editing-state machine, the bulk three-state derivation, and the URL-driven cascade packaging. Handler shrank from 140 lines → 46.

### Resolved on re-audit (no work needed)

- **#17 — Filter divergence between `responses.session_pill_for_reviewer` and `monitoring._reviewer_completion`** — re-audit 2026-05-02: gone. Both already routed through the shared `_reviewer_assignments()` filter at `responses.py:54`.

### Segment 11

Segment 11's sub-segments and their catalog items, in completion order. Each entry names the plan it ships against; per-PR detail lives there.

- **Segment 11A — Tier 1–3 cleanup punch list** — done 2026-05-03 across PRs **#309, #314, #315, #319 → #324, #328, #329, #330**. v2 chrome rebuild rolled out across the session-centric pages (**#21a**, ticked off in `guide/ui_checklist.md`). Tier 3 polish items closed under this segment:
  - **#9 — Refresh `get_or_create_default_instrument` docstring** (PR #309).
  - **#8 — Fix CSV email-validation drift** (PR #314); shared `_parse_email` helper.
  - **#12 — Reviewer/Reviewee CSV cross-table identity check** (PR #315); built on #8.
  - **#10 — Thread `correlation_id` into deadline lazy-close** (PR #329).
  - **#6 — Decouple `invitations.py` from `Request`** (PR #330).
  - **#7 — CSRF decision write-up** (PR #328). Decision: rely on Easy Auth + `SameSite=Lax` cookies; no CSRF tokens in app code. Recorded in `docs/authentication.md`.

  Plan: `guide/archive/segment_11A_cleaning_up_unfinished_business.md`.

- **Segment 11B — Session Home rebuild** — done 2026-05-04. PRs **#380 → #393**, plus a placeholder-card unification pass (#385 → #388) and Next Action card refinements (#390 → #393). Spec at `spec/session_home.md`. Highlights:
  - Lifecycle display label mapping (`ready` → "Activated") via `lifecycle_display.py` + `lifecycle_label` Jinja filter (#22, #30 absorbed here).
  - Next Action card with constant H2, `accent-blue` border, fixed `min-height: 200px`, body grows + button row pinned at the bottom (Primary + Secondary, no inline links).
  - State-conditional contents: Validate Setup / Activate Session / Pause Session as primary, sentence-case secondaries (See validation details / See previews / Revert to draft).
  - Confirm checkbox in `ready` sits in `.next-action-confirm` just above the buttons.
  - Quick Setup grey'd in ready; Extract Data grey'd in draft / validated; both render via the canonical `.card.placeholder` class + `placeholder_card` Jinja macro (also adopted by the Assignments page's Rule Based Assignment card).
  - Danger Zone Delete-Session is visible-but-disabled in ready (server still rejects via `_require_editable`).
  - `.pill-lifecycle-closed` retired; doc pass via PR F aligns specs and guides with what shipped.

- **Segment 11D — #21b v2 sweep, non-session-centric pages** — done 2026-05-04. PRs **#407 (A) → #408 (B) → #409 (C)** plus follow-up refinements **#410 → #413**. PR A swept `sessions_list`, `session_new`, `about`, and `me_debug` onto `body.ui-v2` and landed the return-to-origin helper for detour destinations (`app/web/return_to.py`); PR B added the two-row session chrome to `session_edit` (with `current_page = ""` so no tab activates per "Sub-pages of Home") and made an initial run at the sessions-list lobby as a flex column of `.card.session-card` rows; PR C introduced the lighter reviewer top-bar variant via a new `{% block top_bar %}` in `base.html` plus `reviewer/_top_bar.html`, and swept the three reviewer templates onto `body.ui-v2 reviewer` with D5 status icons (`.status-icon-{complete,incomplete}`), D6 banners (`.banner.banner-{info,success,warning}`), and D7 page header. Post-11D follow-ups (#410–#413) reverted the lobby back to a v2 `<table>` inside a single `.card` and settled the column set at Session Name (link) / Session Code / Deadline (pill) / Created by / Created / Last Modified plus an unlabelled trailing column carrying an unwired select-row checkbox; retired the redundant Access button and the per-row Delete anchor; dropped the redundant `/about` link from the top-left chrome identity; and surfaced inline validation feedback in the Next Action card on Session Home when `?validated=1` fails on a draft session. Plan: `guide/archive/segment_11D_v2_sweep_non_session.md`. Catalog `unfinished_business.md` #21.

- **Segment 11L — Instrument friendly short label** — done 2026-05-04 (PR #429). New `Instrument.short_label String(32) | NULL` column + Setup-side editor on `/operator/sessions/{id}/instruments`. Two reviewer-side helpers (`views.page_button_label(instrument, position)` and `views.instrument_heading(instrument, position, total_count)`) ship inside Segment 11D follow-on PR γ. Plan: `guide/archive/segment_11L_instrument_short_label.md`.

- **Segment 11D follow-on — Reviewer surface, multi-instrument rewrite** — done 2026-05-05. The five planned PRs **#428 (α) → #430 (β) → #431 (γ) → #432 (δ) → #433 (ε)** landed in dependency order, then a polish stream **#434 → #448** swept the missing-required UX, the per-instrument intro grid + tinted help cards, the auto-seed-assignments-on-instrument-add behaviour, the missing-required Cancel-back-to-source-page link, the numeric-field journey (`type="number"` with `min`/`max` + `step="any"` + hidden spinners + `title` constraint hint + JS `setCustomValidity` step-grid popup with `1e-6` tolerance + server-side `validate_value` backstop in `responses.py`), and the per-instrument constraint summary line above each table (List rows omitted). Save / Submit flash banners retired in #441; missing-required moved to its own full-width 2-column `.rs-missing-card` and Submit became a hard gate (acknowledge-and-submit-anyway retired) in #436. New helpers: `views.placeholder_for_field`, `views.constraint_summary_for_field`. Plan: `guide/archive/segment_11D_v2_sweep_non_session.md` "Follow-on". Catalog `unfinished_business.md` #32 partial (general "further refinement" remains a Segment 15 catch-all).

- **Segment 11E — Operator-editable email template editor + SMTP scaffolding** — done 2026-05-07. Six PRs landed against the plan (PR 3 collapsed into PR 1 — the renderer wiring landed there; PR 7 absorbed into Segment 14-1) plus one polish PR:
  - **PR 1 (#461)** — schema + service-layer renderer. `sessions.help_contact` (String 320, nullable) and `sessions.email_template_overrides` (JSON, nullable) columns; new `app/services/email_templates.py` rendering `string.Template.safe_substitute` over the canonical five-tag merge field set (`$reviewer_name` / `$session_name` / `$deadline` / `$help_contact` / `$invite_url`); `_email_body` / `_reminder_body` retire in favour of the new `render_invitation` / `render_reminder`. Help-contact also surfaces on the reviewer surface as a small "Questions? Contact X" line.
  - **PR 2-A (#462)** — placeholder cards on `/setupinvite`, framing the editor surface ahead of the actual editor.
  - **PR 4 (#463)** — operator Settings page at `/operator/settings`. Per-operator SMTP credentials (seven new columns on `users`); password encrypted at rest via `cryptography.fernet` keyed off the `SMTP_ENCRYPTION_KEY` env var; new `app/services/operator_settings.py` + `app/services/_secrets.py`; user-menu Settings link in the chrome.
  - **PR 5 (#464)** — `EmailTransport` Protocol + `EmailMessage` / `SendResult` dataclasses + concrete `SmtpEmailTransport` (`smtplib`, STARTTLS / implicit-SSL) + typed-stub `GraphEmailTransport` placeholder + `transport_for(settings)` factory. Nothing in the app calls this yet; first call site is **Segment 14-1 Part A**.
  - **PR 2 (#465)** — actual editor UI on `/setupinvite`. Two-card `.bottom-grid` layout: composer left, merge tags + Save / Cancel right. Per-template selection via `?template=` query. Per-field "Reset to default" forms; `email_template.updated` / `email_template.reset` audit events.
  - **#468** polish — Email Template + Settings button consistency: tabs out of card / normal-sized / flushed left, Save / Cancel at bottom-right of their card, no flash banners (Save disables until dirty), Settings page picks up `?return_to=` plumbing matching the About-page convention.
  - **PR 6 (#532)** — responses-received template editor (third tab). Adds the responses-received subject / body / cc / bcc keys to `email_template_overrides` plus a per-session `responses_received_enabled` bool flag (default `True`) the editor surfaces as a "Send this confirmation when a reviewer submits." checkbox. New `email_templates.render_responses_received(session, reviewer)` helper (drops `$invite_url`, adds `$submitted_at` resolved via `_latest_submitted_at` against the reviewer's responses) + `responses_received_enabled(session)` reader + `set_responses_received_enabled(session, enabled)` writer. Editor's right-card merge-tag list goes per-template via new `views.merge_tags_for_template(template)` helper. `views.EMAIL_PREVIEW_TABS` flips `is_shipped=True` on the responses_received entry — lights up the previously deferred Preview hub artifact card without needing a new registry seam.
  - Spec at `spec/email_infra_options.md` for the broader transport landscape (Options A–D: SMTP, Microsoft Graph application permission, Azure Communication Services, third-party transactional). The Graph stub will become Option B once the institution's IT conversation lands; the wiring lives in **Segment 14-1**.
  - Plan: `guide/archive/segment_11E_email_template_editor.md`. Catalog `unfinished_business.md` #24 (closed by this segment). The submit-time send wiring (formerly planned as 11E PR 7) absorbed into **Segment 14-1 Part A** so all email *sending* lives on one segment regardless of which transport backend lights up.

- **Segment 11K — Audit-event `detail` schema convention** — done 2026-05-07. PRs **#544 (PR 1) → #545 (PR 2) → #546 (PR 3) → #547 (PR 4) → #548 (PR 5) → #549 (PR 6) → #550 (PR 7) → this PR (PR 8)**. Pins the canonical envelope schema for `AuditEvent.detail` and migrates every emitter in the codebase to it.
  - **PR 1 (#544)** — spec section in `spec/architecture.md` ("Audit-event detail schema") + typed envelope helpers (`audit.changes` / `.snapshot` / `.counts` / `.set_changes`) + new `write_event` kwargs (`session=` / `payload=` / `reason=` / `refs=` / `context=`) + session-lifecycle family migrated as proof.
  - **PRs 2–5 (#545 → #548)** — service-module sweeps: instruments (~18 emitters), invitations (6), responses (4), assignments (2). PR 5 introduced the `excluded_<reason>` flatten-into-counts pattern that lets 13A's RuleBased exclusions plug in without schema churn.
  - **PR 6 (#549)** — relocated `email_template.updated` / `.reset` from `routes_operator.py` into `app/services/email_templates.py::record_template_change` / `.record_template_reset` so PR 7 could sweep them with the rest of the settings family. Pure relocation; no shape change.
  - **PR 7 (#550)** — settings sweep: CSV imports (4), operator settings (2), email templates (2). Replaces the legacy `detail={}` on `operator_email_settings.cleared` with the canonical `detail=None`. Every emitter in the codebase now uses canonical shape.
  - **PR 8 (this PR)** — Pydantic write-validation gate. New `app/services/audit.py::EVENT_SCHEMAS` registry pins the allowed envelopes/slots per event_type; `validate_detail` runs in `write_event` after composition. `settings.audit_strict_mode` gates strict (raise) vs lenient (warn-and-write). `tests/conftest.py` flips strict on so CI catches drift. New `tests/unit/test_audit_detail_schema.py` covers the gate.
  - Closes catalog `unfinished_business.md` #5. Plan: `guide/archive/segment_11K_audit_event_detail_schema.md`. Spec: `spec/architecture.md` "Audit-event detail schema".

- **Segment 11C Part 2 — Outbox audit-log scaffolding** — done 2026-05-07. **PR #541** (PR F). Migration `c4f6a8b0d2e5` adds the seven nullable audit-log columns to `email_outbox` (`error_message`, `from_address`, `backend`, `backend_message_id`, `delivered_at`, `payload_hash`, `correlation_id`) + an index on `correlation_id` (the dispatch helper's idempotent-retry lookup key). `app/db/models/email_outbox.py` gains matching `Mapped[X | None]` declarations and the canonical value-set constants `EMAIL_OUTBOX_STATUSES = (queued, sending, sent, failed)` / `EMAIL_OUTBOX_KINDS = (invitation, reminder, responses_received)` so any future widening is a deliberate edit. Pure additive — all columns nullable, no defaults, no backfill, no service-layer reads or writes; today's enqueue paths continue to write only the existing columns. New tests at `tests/integration/test_email_outbox_schema.py`. The columns sit inert until **Segment 14-1 Part A** lights up the dispatch helper against this stable schema. Plan: `guide/archive/segment_11C_operations_consolidation.md` "Part 2".

- **Segment 11C Part 1 — Operations consolidation** — done 2026-05-06. PRs **#490 → #491 → #492 → #493**.
  - **#490** — chrome restored Outbox as a tab (later removed in #493).
  - **#491** — Manage Invitations (`/operator/sessions/{id}/invitations`) rewrite. Seven-column reviewer-centric table — Reviewer / Email Status / Email Sent / Review Progress / Required Fields / Last reminder / Action — absorbs the retired Monitoring page's reviewer-centric surface (per-reviewer progress, per-row reminders). New helper `views.build_invitations_rows` joins `monitoring.per_reviewer_progress` with a single batched outbox query for "latest invitation outbox row per reviewer". Reviewer drill-in scaffold at `.../invitations/{inv_id}/detail`. Outbox schema slice: Migration `b3d5e7f9a1c4` adds `email_outbox.cc_emails` / `bcc_emails` (Text); `send_invitation` / `send_reminder` populate them at queue time from the `email_template_overrides` JSON (new `email_templates.cc_bcc_for(session, kind)` helper). Columns sit unused at send time until Part 2.
  - **#492** — new Responses page (`/operator/sessions/{id}/responses`). Reviewee-centric coverage view; classifies each reviewee per a new `monitoring.AT_RISK_THRESHOLDS` constant (`adequate_fraction=0.5`) into Complete / Adequate / At risk / No responses. New helpers `monitoring.per_reviewee_coverage`, `views.build_responses_rows`. Reviewee drill-in scaffold at `.../responses/{reviewee_id}/detail`. Bulk reminder dispatch funnels through the same `POST /operator/sessions/{id}/invitations/remind-incomplete` endpoint Manage Invitations uses. Monitoring template + dedicated bulk-remind endpoint deleted; `GET /sessions/{id}/monitoring` 303-redirects to `/invitations` to preserve old bookmarks.
  - **#493** — drops Outbox from chrome (Operations row is now four tabs: Validate / Previews / Invitations / Responses). The Outbox page itself stays accessible via the "View outbox" button on Manage Invitations — it's a dev-diagnostic surface, not part of day-to-day Operations. Same PR styles the five Manage Invitations data cells as pills (`pill-count` for filled / good states, `pill-empty` for absent / not-yet states) so the table reads as a sparkline of state at a glance.
  - **Polish stream (#494 → #500).** Docs sync (#494); Responses table column rename + pill styling on `Reviewers completed` + `Last response` (#495); status-dropdown + name/email search filter strip on both pages closing the `spec/operations_renew.md` "Filtering" gap (#496) plus visual refinements — half-width filter card, side-by-side inputs, bottom-right Apply (#497); summary card + filter card paired side-by-side in `.bottom-grid` with new generic `.card-action-row` v2 primitive on Responses (#498) then Manage Invitations (#499); bulk **Regenerate all** secondary button + `invitations.regenerate_all_tokens` service helper + batch `invitations.regenerated` audit event (#500).
  - Test reorg: `tests/integration/test_monitoring.py` → `test_reminders.py`; new `test_segment_11c_pr3_responses.py`.
  - Plan: `guide/archive/segment_11C_operations_consolidation.md`. Functional spec: `spec/operations_renew.md`.

- **Segment 11H — Placeholder card scaffolds (Quick Setup + Extract Data)** — done. Both Session Home placeholder cards have shipped their inert-but-fully-rendered real shapes via the `_quick_setup_card.html` and `_extract_data_card.html` partials (included from `session_detail.html`), backed by the `QuickSetupSlot` / `QuickSetupContext` and `ExtractDataRow` / `ExtractDataContext` dataclasses + builder helpers in `app/web/views.py`. Every slot / row / button is laid out and accessible; every interactive control renders disabled (`is_wired=False`, `wire_url=None`) until the wiring segments. The Quick Setup card on `/operator/sessions/new` is also wired to the same scaffold via `build_new_session_quick_setup_context`. Plan: `guide/archive/segment_11H_placeholder_card_scaffolds.md`. Unblocks Segment 11J (Quick Setup wiring) and Segment 12A PR 6 (Configuration import slot graduation).

- **Segment 11J — Quick Setup wiring** — done 2026-05-07. PRs **#526 → #527 → #528**.
  - **#526** — plan revision. `guide/archive/segment_11J_quick_setup_card.md` rewritten to refocus on wiring the three "existing capability" slots (Reviewers / Reviewees / Assignments) and to unify the card's status-awareness model behind a single Lock / Unlock toggle that applies in every editable-conceivable lifecycle state, including `ready`. Slot 4 (Session settings, the configuration-import slot) explicitly carved out as a separate sub-plan and deferred to Segment 12A PR 6.
  - **#527 (PR A)** — Reviewers + Reviewees slots go live, plus the Lock / Unlock toggle wiring. New routes `POST /sessions/{id}/quick-setup/reviewers` / `.../reviewees` delegate to a thin `_handle_quick_setup_import` wrapper that reuses the same `parse / save / invalidate-if-validated` pipeline the per-entity Setup pages use. New `POST /sessions/{id}/quick-setup/lock` flips a per-session `HttpOnly` cookie (`qsu_{session_id}`, scoped to `/operator/sessions/{id}`) that the context-builder reads to decide `is_locked`. `views.cascade_message_for_replace` centralises the "this will replace N existing X (and clears M assignments)" copy. Status awareness collapses on a single signal — `is_locked` — and the body wrapper carries `.locked` greying by default in every editable-conceivable state; `.card.disabled` is retired in favour of body-greying, and `show_lock_toggle=True` on `ready` (visual unlock only — `_require_editable` stays the hard gate, with rejection surfacing as a scoped `banner-error` carrying the "Pause first" copy).
  - **#528 (PR B)** — Assignments slot goes live. New route `POST /sessions/{id}/quick-setup/assignments` auto-detects mode from the form payload: when `file` is attached and non-empty it runs the existing `parse_manual_csv` → `manual_rows_to_pairs` → `replace_assignments(mode=manual)` pipeline; otherwise it generates `full_matrix` from the stored rule via `generate_full_matrix` → `replace_assignments(mode=full_matrix)`. `exclude_self_review` honoured on both branches. Cascade banner reuses PR A's shape (banner-warning above the submit form, required confirm checkbox, Cancel + Confirm replacement); per spec assignments are leaf data so the cascade copy stops at "This will replace N existing assignments." with no further consequence to surface.
  - Slot 4 (Session settings / configuration-import) stays inert — graduates with Segment 12A PR 6, which flips `is_wired=False → True` and supplies `wire_url` against the seam 11H pinned. No markup or scaffold changes needed there.
  - New tests: `tests/integration/test_quick_setup_card.py` covers per-slot golden path, cookie-scoped lock toggle (round-trip + per-session isolation), cascade copy + helper unit-side, replace-confirmation flow, scoped parse-error / lifecycle-rejection / needs-confirm banners. Updated scaffold expectations in `tests/integration/test_quick_setup_scaffold.py` and `tests/integration/test_session_detail_restructure.py` for the unified pattern (toggle visible on `ready`, `.card.disabled` retired, all three live slots posting to their wire URLs).
  - Plan: `guide/archive/segment_11J_quick_setup_card.md`. Catalog `unfinished_business.md` #30 (closed by this segment, modulo slot 4 which carries forward into 12A).

- **Segment 11G — Validate page** — done 2026-05-06. PRs **#505 → #506 → #507 → #508** (the four-PR sequence in the plan) plus polish PRs **#509 → #511**. Builds the Validate page out from a thin read-only issue list into a find-and-fix surface:
  - **#505 (PR A)** — page layout (later simplified): three-card structure with severity counts + lifecycle-aware copy + setup-coverage matrix + existing issue list. New `views.build_validate_context` adapter + `views.validate_lifecycle_copy` pure function.
  - **#506 (PR B)** — `validate_session_setup` refactored into a `ValidationRule` registry. Each issue carries a `rule_key`, `fix_url`, `fix_anchor`, `fix_page_label`, and `why`. Two new rules added: `email_template.no_help_contact` (info) and `instruments.no_display_fields` (warning). Setup-page tables grow `id="reviewer-row-{id}"` / `id="reviewee-row-{id}"` anchors so per-issue deep-links can scroll to the offending row. `ReadinessReport.has_non_blocking_findings` tightened to ignore info severity (info is advisory only, never triggers acknowledgment).
  - **#507 (PR C)** — severity filter chip strip (`?severity=` query param), per-source group count summary on the issue list (`Reviewers (1 error)`), per-issue native-disclosure "Why this check?" element with the rule's `why` paragraph.
  - **#508 (PR D)** — activate-warns detour from Home. The Next Action card's `acknowledge_warnings` checkbox is removed; when warnings exist, the Activate button 303s to `/validate?activate=1` and surfaces a `.banner.banner-warning` with the warnings inline + Cancel + Acknowledge-and-activate. `?activate=1` on a draft / ready / closed session redirects to the clean URL.

- **Segment 11F — Previews page** — done 2026-05-07. The Operations-row Previews tab (`/operator/sessions/{id}/previews`) graduates from a placeholder to the pre-flight Reviewer Experience Preview hub. All five planned PRs landed:
  - **PR A (#517 / #520)** — page chrome + reviewer picker. New `_preview_picker.html` partial with typeahead (`<input list>` + `<datalist>`), Apply / Previous / Next / Random controls, "Reviewer N of M" count, and assigned-reviewees peek strip. `?reviewer_email=` URL state is canonical (email, not id, so bookmarks survive a full-cohort re-upload). New `views.build_preview_picker_context` adapter + `POST /sessions/{id}/previews/random` route (server-side `secrets.choice`, no reviewer-email list leaks into client JS). Default behavior is no reviewer selected — the body collapses to a "pick a reviewer" empty state rather than defaulting to the first reviewer alphabetically.
  - **PR B (#521 / #522)** — tabbed email previews region + invitation card. Single full-width card with a `.btn-pair` tab strip (Invitation / Reminder / Responses-received); only the active tab's body renders at a time, and only the Invitation tab is wired to a real render adapter (Reminder + Responses-received render disabled with "(coming soon)" until PRs D / E activate them). New `views.EMAIL_PREVIEW_TABS` registry + `EmailPreviewTab` / `EmailBody` dataclasses + `build_email_preview_body` dispatch + `email_preview_from_display(user)` helper; the invitation render calls `email_templates.render_invitation` with a `PREVIEW_INVITE_URL_PLACEHOLDER` so real one-time-use tokens aren't burned on previews. Source-of-truth footer deep-links to Email Template (Setup) `?template=invitation` + Reviewers (Setup). `<hr>` separator below the email card with a placeholder where PR C's surface card would land.
  - **PR C (#523)** — reviewer-surface card + retire `/preview` (singular). New `_surface_preview_card.html` partial renders the picker-selected reviewer's would-be reviewer surface inside an `<iframe srcdoc="…" sandbox="allow-scripts">`. Sandbox uses `allow-scripts` only (no `allow-same-origin`) so the reviewer-surface inline page-toggle JS keeps working for multi-instrument Page #N navigation while opaque origin blocks parent-cookie / localStorage access; `allow-forms` stays off. `routes_reviewer.build_preview_context` grows an optional `target_reviewer` parameter so synthetic-row pad surfaces *that reviewer's* reviewees rather than the unfiltered first-three-by-id fallback. New `views.build_surface_preview_context` + `SurfacePreviewContext` / `SurfacePreviewMissing` dataclasses with scoped missing-data handling (no instruments configured / reviewer has no assignments → Setup-page link inline; email region above the `<hr>` keeps rendering). Standalone `/sessions/{id}/preview` retired as a 308 permanent redirect to `/sessions/{id}/previews#reviewer-surface`; Session Home's "See previews" secondary button + the reviewer-surface preview-mode `PageButton.href` migrate to the hub anchor. Tests reshape: new `tests/integration/_preview_iframe.py` helper extracts + unescapes the iframe srcdoc so the existing reviewer-surface chrome / panel / inputs / page-button tests in `test_segment_11d_*.py` migrate cleanly off the retired route; `test_preview_route.py` shrinks to redirect + 403 + D9 deadline-observation contract.
  - **PR D** — reminder tab activation. Single dispatch branch in `views.build_email_preview_body` calling `email_templates.render_reminder(session, reviewer, PREVIEW_INVITE_URL_PLACEHOLDER)` plus the `EMAIL_PREVIEW_TABS["reminder"].is_shipped=True` flip. Same shape as the responses-received tab activation that shipped via 11E PR 6 (#532).
  - **PR E** shipped via Segment 11E PR 6 (#532) — the responses-received tab activation rode along with the editor third tab, since both depend on the same `render_responses_received` helper + the EMAIL_PREVIEW_TABS registry mutation.
  - Plan: `guide/archive/segment_11F_previews_page.md`.
  - **#509 → #511 polish** — readiness summary card removed (severity counts already live in the chip strip); setup-coverage matrix moved off `<table>` markup onto a flex-row-per-cell + 4-column grid layout (3-col → 4-col after #511) with the descriptive subtitle inline next to the H2.
  - Plan: `guide/archive/segment_11G_validate_page.md`. New: `tests/integration/test_session_validate_page.py` covering the four-PR surface end-to-end.

### Segment 13

- **Segment 13A — Rule-based assignment builder** — done 2026-05-07. PRs **#563 / #565 / #566 / #569 / #570 / #576 / #577 / #578 / #579 / #580 / #581** plus follow-on polish **#564 / #571 / #572 / #573 / #574 / #575**. Replaces the placeholder Rule Based card on `/operator/sessions/{id}/assignments` with a real RuleSet-driven rule menu — schema (`rule_sets` + `rule_set_revisions`), pure-Python engine (predicates / combinators / quotas / deterministic ordering), five seeded RuleSets in install order, an editor child page at `/assignments/rule-based/edit/{rule_set_id}` with Save / Save As / in-place revisioning + soft-delete, and a server-side live preview pane reusing the engine. New audit emitters (`rule_set.created` / `.updated` / `.deleted`) registered in `audit.EVENT_SCHEMAS` per 11K PR 8. The retired-card cleanup (PR 8) removed the standalone Full Matrix card from the assignments page; the seeded `Full Matrix` RuleSet covers the same case from inside the new card. Plan archived: `guide/archive/segment_13A_rulebased_assignment_builder.md`.

- **Segment 13A-1 — Rule Based editor revamp** — done 2026-05-07. PRs **#587 (PR 1) → #588 (PR 2) → #589 (PR 3) → #601 (PR 4a) → #602 (PR 4b)** plus an iterated layout-spec stream **#590 → #591 → #592 → #593 → #594 → #595 → #596 → #597 → #598 → #599 → #600**. Supersedes 13A's two-column editor (Library panel + Personal editable view + seed view + preview) with a single-card **Rule Builder** at `/operator/sessions/{id}/assignments/rule-based-editor` paired with an **Available Rulesets** sibling card. Highlights:
  - Single self-sufficient page — no redirect back to assignments on Save / Copy / Cancel / Delete; the dropdown switches in-place.
  - Three render branches share one form: seeded read-only (sentence-shaped rule lines), saved Personal (PR 5b/5c indented inline-composite editable form lifted unchanged), unsaved draft (Copy from seed/Personal **and** "+ New blank RuleSet"). Action row is selection-aware per locked decision #3.
  - **Friendly Description** textarea on editable branches (default `"User created ruleset"` on fresh drafts) replaces 13A's read-only description caption; persists via the same `/save` route. Caption stays for seeded read-only views.
  - **"Available rulesets"** sibling card at half page width lists every visible RuleSet with its description and a seed/personal pill; the active row highlights.
  - Locked banner copy + "Combine these rules with:" helper inline (no "Combinator" heading); `+ MATCH/FILTER/QUOTA/COMPOSITE rule` button labels (no "Add"); no "Exclude self-review" affordance on the card (lives on the main Assignments page).
  - 13A's standalone editor surface (`/edit/{rule_set_id}` + companion POSTs `/copy`, `/save`, `/save-as`, `/rename`, `/delete`, `/preview`) and template / partials retired in PR 4b; the reused PR 5b/5c rules-JSON serializer (`_rule_based_editor_js.html`) and shared view-shape helpers (`RuleLine`, `EditableRule`, `_flatten_rule_lines`, `_flatten_editable_rules`, picker option lists) stayed.
  - Plan archived: `guide/archive/segment_13A_1_rule_based_editor_revamp.md`. As-built layout: `spec/rule_based_assignment.md` §7.2 (Rule Builder page). New tests: `tests/integration/test_rule_builder_page.py`, `test_rule_builder_copy_save_delete.py`, `test_rule_builder_new_blank.py`. Net diff after 4b: **-3487 lines** of legacy editor surface.

- **Segment 13A-2 — `session_rule_sets` name uniqueness within session** — done 2026-05-09. PR **#711**. Adds the `uq_session_rule_set_session_name` constraint on `session_rule_sets(session_id, name)`, mirroring the parallel `uq_rtd_session_name` already on `response_type_definitions`. Pure DDL — the table was empty on every deployment running the migration (lands inert from 13D PR 2). Underpins 12A-1's name-based `instruments[N].rule_set_name` reference + 15B's per-instrument selection + 15C's Save-to-library / Add-from-library flows. Service-layer collision check (mirror of `_resolve_save_as_name` for `operator_rule_sets`) deferred to 15C Slice 4 where the editor reroutes to write into `session_rule_sets`; this DB constraint is the safety net behind that future adaptation. Follow-on details appended to `guide/archive/segment_13A_1_rule_based_editor_revamp.md`.

### Major refactor — done 2026-05-08 → 2026-05-09 (PRs #651 → #683)

Three large monoliths split into per-concern packages with re-export
walls (callers stay byte-identical), plus a hygiene bundle and a
test-file split. Pattern across all three ladders: package
conversion + `_legacy.py` shrinks slice-by-slice, `git mv` finale
preserves blame. Plan + slice-by-slice ranges: `guide/major_refactor.md`.

- **`app/web/routes_operator.py`** (4,423 LOC, 79 routes) → `app/web/routes_operator/` with 10 feature-area sub-modules + `_shared.py`. PRs **#651 → #659** (1 package-conversion + 10 slice PRs). 2026-05-08.
- **`app/services/instruments.py`** (2,469 LOC, ~50 public functions, 5 concerns) → `app/services/instruments/` with `_state.py` / `_rtds.py` / `_display_fields.py` / `_response_fields.py` / `_instrument_crud.py`. PRs **#663 → #667** (§12.A). 2026-05-09.
- **`app/web/views.py`** (3,483 LOC, 79 builders / dataclasses) → `app/web/views/` with 10 page / entity sub-modules. PRs **#668 → #678** (§12.B). 2026-05-09.
- **Cross-cutting hygiene** (§12.C): public `csv_imports.decode_csv`, 14 inline imports lifted to module scope, new `app/services/_queries.py::session_scoped`. PRs **#680 → #682**. 2026-05-09.
- **`tests/integration/test_display_field_routes.py`** (2,167 LOC, 53 tests) split into 6 per-surface files + `_display_field_helpers.py` shared module. PR **#683** (§12.D). 2026-05-09.

### Segment 13D — DB prep for the library / per-session-copy split — done 2026-05-09 (PRs #696 → #702)

Pre-positions every additive, nullable, no-backfill schema change downstream feature segments need (15A, 15C, 15B; 13B / 13C ride-alongs). Mirrors how 11C Part 2 pre-positioned the seven `email_outbox` audit-log columns. **Every migration shipped inert** — no service or web code reads or writes the new shape until its owning feature segment lights it up. Plan: `guide/segment_13D_db_prep.md`.

- **PR 0** (#696) — rename `rule_sets` → `operator_rule_sets` (Tier 1 table-name harmonisation; SQL only, Python class identifier `RuleSet` unchanged).
- **PR 1** (#697) — new `session_field_labels` table (15A friendly-label resolver).
- **PR 2** (#698) — new `session_rule_sets` snapshot table (15C per-session RuleSet copies).
- **PR 3** (#699) — new `operator_response_type_definitions` library table + `response_type_definitions.library_origin_id` provenance pointer (15C).
- **PR 4** (#700) — `instruments.rule_set_id` nullable FK → `session_rule_sets`, ON DELETE SET NULL (15B per-instrument selection).
- **PR 5** (#701) — `instruments.sort_display_fields` JSON column (13B sort spec).
- **PR 6** (#702) — `instruments.group_kind String(32)` column (13C group-scoped instruments).

### Segment 12A-1 — Session export (settings + per-entity CSVs + responses) — done 2026-05-09 (PRs #713, #716, #717, #718, #721)

Splits the umbrella "Segment 12A — Session settings import + export" into the export half (this segment) and the import half (12A-2, see Upcoming below). Ships **five CSV downloads** off the Extract Data card on Session Home — four serving the session-porting use case (Settings + Reviewers / Reviewees + Manual Assignments) plus the seeded-RuleSet audit-log fallback for pre-15B rule-based sessions, and a fifth (Responses) serving the independent **downstream-analysis** use case (Excel pivots, pandas groupby, BI tools). Plan: `guide/segment_12A-1_export.md`.

- **PR 1** (#713) — Settings export + shared `extracts/` plumbing. New `app/services/session_config_io.py` with `serialize_session_config`; new `app/services/extracts/__init__.py` with `stream_csv` + `filename({code}_{kind}.csv)` helper; new `GET /operator/sessions/{id}/export/settings.csv` route in a new `_extracts.py` slice; `session.settings_extracted` audit event registered in `EVENT_SCHEMAS`. Settings row on the Extract Data card flips live. Tests: 14 unit + 6 integration.
- **PR 1a** (#716) — Capture seeded-RuleSet selection from the audit log. Pre-15B fallback in `_audit_log_rule_set_name` that fills `instruments[N].rule_set_name` cells from the latest `assignments.generated` audit row when the referenced `operator_rule_sets` row is a seed (`is_seed=True`). Memoised once per export so multi-instrument sessions hit the audit table once. Personal-library RuleSets intentionally out of scope (empty cell; destination operator picks on re-Generate). Post-15B precedence: populated `Instrument.rule_set_id` wins over the audit-log fallback. Tests: 6 new unit cases.
- **PR 2** (#717) — Reviewers + reviewees extracts. New `serialize_reviewers` + `serialize_reviewees` modules; routes `/export/reviewers.csv` and `/export/reviewees.csv`; `session.reviewers_extracted` + `session.reviewees_extracted` audit events. Column shapes match `parse_reviewer_csv` and `parse_reviewee_csv` (incl. `PhotoLink` not `ProfileLink`) so files round-trip with the upload flows on the Manage pages and Quick Setup. Both card rows flip live. Tests: 8 unit + 6 integration.
- **PR 3** (#718) — Manual assignments extract. New `serialize_assignments` raising `ManualOnlyError` on `assignment_mode != "manual"`; route `/export/assignments.csv` catches and returns 404; `session.assignments_extracted` audit event. Column shape `ReviewerEmail,RevieweeEmail,IncludeAssignment,Instrument` matches `parse_manual_csv`. Card row flips live on manual sessions; rule-based / full-matrix / unset sessions get a mode-specific tooltip. Multi-instrument N×M fanout; the importer collapses repeated pairs back into one Assignment per instrument on re-upload. Tests: 9 unit + 8 integration.
- **PR 4** (#721) — Responses extract (downstream-analysis use case). New `serialize_responses` that yields a 19-column wide CSV per `Response` row — denormalised reviewer + reviewee identity / tags, instrument context, field context, response-type name, value, and lifecycle (saved / submitted / version) so the file is readable in isolation. Streams through a `yield_per(1000)` cursor; route counts up front via `responses.session_response_count` so the audit event carries the row count without materialising the generator. `session.responses_extracted` audit event. Card row flips live with `{code}_responses.csv` filename. Empty-cell vs no-row semantics: null `Response.value` → empty `Value` cell with row preserved; missing-`Response` → no row. Tests: 9 unit + 5 integration.

Out of scope (deferred): zip bundle (mixed porting + analysis use case earns its own UX pass) and the import side (12A-2 — `guide/segment_12A-2_import.md`).

---

## Upcoming

Each item below has a detailed plan in its own doc; entries here
are 1-3 lines for at-a-glance sequencing + the catalog items
pinned to each segment. The catalog itself lives in
`unfinished_business.md`.

1. **12A-2 — Session settings import.**
   The import counterpart to 12A-1 (export, shipped 2026-05-09).
   Consumes the 3-column Settings CSV the export half emits and
   rehydrates a fresh-named session into the same shape. Two
   PRs: importer service + route, then Quick Setup slot 4
   graduation in both contexts (Create New Session + Session
   Home). New emitter `session.config_imported` inherits the
   canonical detail shape pinned by 11K.
   **Plan:** `guide/segment_12A-2_import.md`.

2. **12B — Audit retention.**
   `audit_events` export + retention / purge tooling. Reads
   against the canonical detail shape pinned by 11K (shipped
   2026-05-07). Folded out of the original Segment 12 plan when
   Extract Data moved into 12A.
   **Plan:** `guide/segment_12B_audit_retention.md`.

3. **13B — Reviewer surface sort.**
   Sort-by-reviewee column on the reviewer surface — operator
   default + reviewer live override. Sized as 3 PRs (schema +
   read path → operator UI tri-state Sort column → reviewer-
   side live override). Independent of 13A and 13C; ships in
   any order.
   **Plan:** `guide/segment_13B_sort_by_reviewee.md`.
   **Functional spec:** `spec/sort_by_reviewee.md`.

4. **13C — Enhanced instruments.**
   Group-scoped instruments (per-instrument flavour where one
   answer covers a group of reviewees) + a "Duplicate
   instrument" action-row button. Sized as 5 PRs. Action row
   ends up with: Edit / Save / Cancel (state-aware) + Add new
   instrument + Add group-scoped instrument (new) + Duplicate
   instrument (new). No `Response` schema change — duplicate-
   and-stamp on `Assignment.context`. Independent of 13A and
   13B.
   **Plan:** `guide/segment_13C_enhanced_instrument.md`.
   **Functional spec:** `spec/enhanced_instruments.md`.

5. **14 — Production hardening.**
   Observability, security, support runbooks, real-pilot prep.
   Catalog #26 (local Postgres docker-compose for dev).
   **Plan:** `guide/segment_14_production_hardening_plan.md`.

6. **14-1 — Email infrastructure (send activation + backends).**
   All email *wiring* lives here. The schema columns Part A
   writes to landed with **Segment 11C Part 2** (PR #541,
   2026-05-07) and are ready for the dispatch helper.
   - **Parts A → E** (sequential): SMTP send activation →
     `correlation_id` strategy → bulk-send queue + worker →
     per-deployment from-identity defaults → generalised
     Outbox diagnostic surface.
   - **Parts F → H** (independent backend swaps): Option B
     (Microsoft Graph), Option C (Azure Communication Services),
     Option D (third-party transactional). Ship as deployment
     demand dictates.

   Catalog #34 (queue-based batch invitation sending — Part C).
   **Plan:** `guide/segment_14-1_email_infra.md`.
   **Functional spec:** `spec/email_infra_options.md`.

7. **15 — Operator polish + documentation.**
   Inline-edit Manage rows, Inactivate UI, sessions-list per-
   row Delete, AG Grid integration, tech-support contact, the
   "make the system understandable to a new operator" pass
   before broader pilot. Runs after 14.
   Catalog #23, #25, #33, #35, #36, §2.2.
   **Plan:** `guide/segment_15_operator_polish_and_documentation.md`.

8. **15A — Pervasive friendly labels.**
   Operator-renamable `ReviewerTag1-3` / `RevieweeTag1-3` /
   `PairContext1-3` (and optional `AssignmentContext1-3`) flowing
   through every header / picker / tooltip via a session-level
   resolver, not just per-instrument Display Field rows. New
   `session_field_labels` table + `app/services/field_labels.py`
   resolver + Settings-page editor. ~3-4 PRs. Lands cleanly any
   time after the major refactor; recommended **before 15B** so
   15B's per-instrument UI consumes the resolver instead of
   re-introducing hardcoded literals.
   **Plan:** `guide/segment_15A_friendly_labels.md`.

9. **15C — Operator RTD / RuleSet libraries.**
   Symmetric two-tier model for both RTDs and RuleSets:
   operator master library (cross-session, reusable) +
   per-session copy (portable, independently editable). Explicit
   "Save to library" / "Add from library" actions; auto-copy
   whole library on session create; workspace seeds bypass the
   library. ~5-7 PRs (service + UX only — every table comes
   from 13D PR 2 / PR 3). Sequenced **before 15B** so
   `session_rule_sets` rows exist for 15B's
   `instruments.rule_set_id` to point at.
   **Plan:** `guide/segment_15C_operator_libraries.md`.

10. **15B — Per-instrument assignments.**
   Each `Instrument` carries its own assignment set (e.g. the
   Manager survey collects different reviewer → reviewee pairings
   than the Peer survey within one session). Schema already
   supports this — `Assignment` carries `instrument_id` with a
   `(session_id, reviewer_id, reviewee_id, instrument_id)` unique
   constraint — but `replace_assignments` fans out uniformly today.
   Slices: per-instrument service scope, persist per-instrument
   `instruments.rule_set_id` selection, manual CSV `Instrument`
   column, per-instrument Assignments page UI, Quick Setup
   selector, per-instrument validation. ~5-7 PRs. Recommended
   after 15C.
   **Plan:** `guide/segment_15B_per_instrument_assignments.md`.

### Sequencing notes

- **11C Part 2 → 14-1 Part A** is the email pipeline: 11C Part 2
  landed the schema (Migration `c4f6a8b0d2e5`, 2026-05-07); 14-1
  Part A is the first writer.
- **11K → 12B** is the audit pipeline: 11K pinned the `detail`
  shape (shipped 2026-05-07); 12B's export reads against it.
- **12A, 13A, 13B, 13C** are independent of the email + audit
  pipelines and can interleave at any time. The three 13-family
  segments are also independent of each other; 13C PR 3
  (rule-engine fanout for group-scoped instruments) lands more
  naturally after 13A's RuleSet machinery exists, but 13C
  PRs 1 / 2 / 4 / 5 don't depend on 13A.
- **Within 14-1**, Parts B-E are sequential enhancements on top
  of Part A; Parts F-H are independent backend swaps.
