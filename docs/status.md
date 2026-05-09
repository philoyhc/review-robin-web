# Implementation status

**As of:** end of major-refactor §12 (2026-05-09) — `routes_operator.py`, `app/services/instruments.py`, and `app/web/views.py` package splits + cross-cutting hygiene + integration-test split

This document is a periodic snapshot of what Review Robin Web actually
does today, vs. what is planned but not yet implemented. It is updated
at the end of each segment. Per-segment plans live in
`guide/segment_NN_*` and `guide/segment_NNA.md`.

For the full long-term plan see
`guide/archive/low_intensity_workplan_review_robin_web.md`.

---

## Project timeline

| Date | Milestone |
|---|---|
| 2026-04-25 → 2026-04-28 | Project bootstrapped: GitHub repository created (04-25), Azure subscription + App Service provisioned (04-26), Postgres Flexible Server provisioned and Segments 1–4 shipped (skeleton, deploy, auth, data model — 04-27), Segments 5–7 shipped (operator session MVP, imports + validation, assignment generation — 04-28). |
| 2026-04-29 | Segments 8 → 9.5A shipped: reviewer surface MVP + roster status-filter retrofit (8); session activation lifecycle + per-instrument acceptance gates (9.1); per-reviewer invitations + dev outbox + token landing route (9.2); monitoring page + reminder send (9.3); page chrome + breadcrumbs + sessions list reshape + `/about` (9.4A); session detail four-card restructure + inline validate-summary + Delete Data (9.4B); Manage-page reshapes + instruments index + `/setupinvite` stub (9.4C); `validated` lifecycle state + setup-mutation invalidation hooks (9.5A). |
| 2026-04-30 | Segments 10A → 10B shipped: response-field builder + reviewer-surface loop-by-instrument refactor (10A); data-driven reviewer-surface render + display-field backfill (10B-1); operator display-field builder + shared field-order bulk form (10B-2); operator preview route completes Segment 10B (10B-3). |
| 2026-05-01 → 2026-05-03 | Segments 10C → 11A shipped. **10C (05-01):** operator UI clean-up — page-grid layouts, six-button setup nav, yellow lock-card pattern, per-instrument card refactor with live preview + Save/Edit lock toggle, multi-instrument schema/services landed UI-disabled. **10D (05-02):** Instruments-page rebuild — state-machine-driven Display + Response Fields tables, Response Type Definitions card with cascade-delete UX, mutual-exclusion edit lock, multi-instrument enable. **11A (05-03):** Tier 1–3 cleanup punch list — shared `_parse_email`, CSV cross-table identity check, `correlation_id` into deadline lazy-close, decoupled `invitations.py` from `Request`, CSRF decision, reviewer-surface polish batch, v2 chrome rebuild + per-page sweep across the session-centric pages. |
| 2026-05-04 | Segment 11B shipped (Session Home rebuild: lifecycle display-label mapping, Next Action card with constant title + `accent-blue` border + `min-height: 200px` + bottom button row, canonical `.card.placeholder` + `placeholder_card` macro for Quick Setup / Extract Data / Rule Based Assignment, Quick Setup disabled in `ready`, Danger Zone Delete-Session visible-but-disabled, `.pill-lifecycle-closed` retired) |
| 2026-05-04 | Segment 11D shipped (v2 sweep across the eight remaining non-session-centric templates; reviewer top bar variant via `{% block top_bar %}` + `reviewer/_top_bar.html`; About / `me/debug` return-to-origin via `app/web/return_to.py`; `session_edit` gains the two-row session chrome with no tab active; reviewer surface picks up status-icon classes, the four-variant `.banner` family, and the H1 + deadline page header) |
| 2026-05-04 | Segment 11D follow-ups (PRs #410 → #413): sessions list lobby reverted from `.card.session-card` rows back to a v2 `<table>` inside a single `.card`, with the column set settled at Session Name (link) / Session Code / Deadline (pill) / Created by / Created / Last Modified plus an unlabelled trailing column carrying an unwired select-row checkbox; redundant Access button + per-row Delete anchor retired; redundant `/about` link dropped from the top-left chrome identity (the right-side user-menu About link with `?return_to=` is now the sole About affordance); the Next Action card on Session Home now surfaces inline validation feedback (error / warning / info pill row + headline) when `?validated=1` fails on a draft session, instead of leaving the operator without feedback |
| 2026-05-04 | Segment 11L shipped (PR #429) — `Instrument.short_label String(32) | NULL` column + Setup-side editor; reviewer-surface Page #N buttons and per-instrument H2 headings consume it (with bare `Page #N` fallback when unset). Independent prereq for Segment 11D follow-on PR γ |
| 2026-05-05 | Segment 11D follow-on — Reviewer surface multi-instrument rewrite shipped (PRs **#428 α → #430 β → #431 γ → #432 δ → #433 ε**) per `guide/archive/segment_11D_v2_sweep_non_session.md` "Follow-on". α: URL routing `/reviewer/sessions/{id}/{instrument_position}`, dashboard rewiring, per-position Save URL, hidden `current_position` field driving Submit redirect. β: top-row `.bottom-grid` (description card + always-on `.rs-status-panel` with per-page `PageStatus` pills: `not_started` / `in_progress` / `complete` / `submitted`). γ: unified `.rs-action-row` (Save / Discard / Page #N: `short_label` / divider / Submit, mirrored top + bottom), per-instrument `instrument_heading()` helper, `Instrument.short_label`-driven page button labels, server narrows render to one instrument + per-position Save filter, retired Previous/Next + `.rs-action-row-left`. δ: client-side page navigation (every group in DOM, CSS hides non-active, JS toggles `.rs-active` + `pushState`), per-group dirty tracking, Save enabled-state recompute, Discard restores from `data-rs-saved-value`, popstate honoured. ε: page-aware missing-required banner enumerating `(position, reviewee_name, field_label)`, operator-preview chrome adaptation (action row collapses to Page #N buttons; status panel without per-page pills) |
| 2026-05-05 | Reviewer surface polish stream (PRs **#434 → #448**): missing-required moved from a panel banner to its own full-width 2-column `.rs-missing-card` below the bottom-grid (#434, #435); Submit became a hard gate on missing required (#436 — retired the acknowledge-and-submit-anyway path); per-instrument intro became a half-width card grid + tinted help cards + auto-seed assignments on instrument add (#436, #437, #438); missing-required Cancel returns to the originating instrument page rather than dangling on `/submit` (#439); numeric-field journey: text-input + `inputmode` (#440) → server-side numeric validation + drop save/submit flash + form-action sync to keep page in place (#441) → placeholder + width experiments (#442 → #444) → final shape: HTML5 `type="number"` with `min`/`max` + `step="any"` + hidden spinners + `title` hint (#445) + `setCustomValidity` step-grid popup with `1e-6` tolerance (#446); per-instrument constraint summary line above each table (`**Rating** (1-5, steps of 1), **Comments** (0-2000 char)`) with List rows omitted (#447, #448) |
| 2026-05-05 | Segment 11E shipped (PRs **#461 PR 1 → #462 PR 2-A → #463 PR 4 → #464 PR 5 → #465 PR 2**, plus **#468** polish; **#532 PR 6** added 2026-05-07 to land the responses-received template editor third tab). Operator-editable email template editor on `/operator/sessions/{id}/setupinvite` with per-template (Invitation / Reminder / Responses received) Save / Cancel / per-field Reset to default; new `email_templates.render_invitation` / `render_reminder` / `render_responses_received` over `string.Template.safe_substitute` against per-template merge-field sets (invitation / reminder share the canonical five — `$reviewer_name` / `$session_name` / `$deadline` / `$help_contact` / `$invite_url`; responses-received drops `$invite_url` and adds `$submitted_at`). Per-session `help_contact` column surfaces the operational contact on the reviewer surface as `Questions? Contact <X>`. Per-session `responses_received_enabled` toggle (default `True`) on `email_template_overrides` JSON gates whether the responses-received confirmation auto-sends; the editor's third tab surfaces it as a checkbox. Operator-level Settings page at `/operator/settings` (per-operator SMTP credentials, password encrypted at rest via `cryptography.fernet` keyed off `SMTP_ENCRYPTION_KEY`); reachable via the chrome user-menu Settings link with `?return_to=` plumbing matching the About-page convention. Transport scaffolding: `EmailTransport` Protocol + `EmailMessage` / `SendResult` dataclasses + concrete `SmtpEmailTransport` (`smtplib`, STARTTLS / implicit-SSL) + typed-stub `GraphEmailTransport` placeholder + `transport_for(settings)` factory. **Nothing in the app sends real mail yet** — outbox rows still write `status="queued"`; **Segment 14-1 Part A** is the first call site for the transport interface. Spec at `spec/email_infra_options.md` for the broader transport landscape (Options A / B / C / D — SMTP, Microsoft Graph application permission, Azure Communication Services, third-party transactional). Plan: `guide/archive/segment_11E_email_template_editor.md`. Closes catalog `unfinished_business.md` #24 (editor side). |
| 2026-05-06 | Segment 11H shipped (PRs **#480 → #481 → #482 → #483 → #484 → #485 → #486 → #487**). Replaces the `placeholder_card(...)` stubs on Session Home with their inert-but-fully-rendered real shapes. New partials `_quick_setup_card.html` + `_extract_data_card.html` (in `app/web/templates/operator/partials/`). New `views.QuickSetupSlot` / `QuickSetupContext` / `build_quick_setup_context` + `views.ExtractDataRow` / `ExtractDataContext` / `build_extract_data_context` dataclasses + builders. Quick Setup card renders four slots (Reviewers / Reviewees / Assignments / Session settings — the last renamed in #484 from "Configuration import"); each slot has file input + Submit + count indicator + dormant banner container, all disabled (`is_wired=False`, `wire_url=None`) until Segment 11J flips them live. Extract Data card renders a per-entity row scaffold (settings / reviewers / reviewees / assignments / responses / bundle) inert until Segment 12A PR 6 wires the download paths. Polish stream landed alongside: 2-column top grid + divider on Quick Setup (#482); lock toggle + Exclude self-review checkbox + drop Segment 13 caption (#483); rename Configuration import → Session settings (#484); session-detail card-order pass — Next Action / Extract Data / Session Details / Quick Setup / Danger Zone (#485); Danger Zone moves to bottom of left column (#486); Quick Setup card on `/operator/sessions/new` via `build_new_session_quick_setup_context` (#487). Plan: `guide/archive/segment_11H_placeholder_card_scaffolds.md`. Unblocks Segment 11J (Quick Setup wiring) and Segment 12A PR 6 (Extract Data wiring). |
| 2026-05-06 | Segment 11G shipped (PRs **#505 → #506 → #507 → #508**, plus polish **#509 → #511**). Validate page (`/operator/sessions/{id}/validate`) rebuilt as a find-and-fix surface. **PR A** introduced the structured layout (since simplified): readiness summary card + setup-coverage matrix + lifecycle-aware copy + existing issue list. **PR B** refactored `validate_session_setup` into a `ValidationRule` registry; each issue carries a `rule_key`, `fix_url`, `fix_anchor`, `fix_page_label`, and `why`. Two new rules: `email_template.no_help_contact` (info) and `instruments.no_display_fields` (warning). Setup-page tables grow `id="reviewer-row-{id}"` / `id="reviewee-row-{id}"` anchors so per-issue deep-links scroll to the offending row. `ReadinessReport.has_non_blocking_findings` tightened to ignore info severity (info is advisory only, never triggers acknowledgment). **PR C** added the severity filter chip strip (`?severity=` query param), per-source group count summary on the issue list (`Reviewers (1 error)`), and per-issue native-disclosure "Why this check?" element. **PR D** moved the warnings-acknowledgment ceremony out of the cramped Next Action card on Session Home and onto a confirmation banner on `/validate?activate=1`: the `acknowledge_warnings` checkbox is removed; when warnings exist, Activate 303-redirects to the detour banner with the warnings inline + Cancel + Acknowledge-and-activate; lifecycle guards on `?activate=1` redirect ineligible states to the clean URL. Polish stream (#509 → #511): readiness summary card removed (severity counts already in the chip strip); setup-coverage moved off `<table>` markup onto a 4-column flex grid with the descriptive subtitle inline next to the H2; cells display label + status inline with a small gap. New helpers: `views.build_validate_context`, `views.validate_lifecycle_copy`, `views.SetupCoverageRow` / `SeverityChip` / `IssueSourceGroup` dataclasses, `app/services/validation.py::ValidationRule` + `REGISTERED_RULES`. New tests: `tests/integration/test_session_validate_page.py`. Plan: `guide/archive/segment_11G_validate_page.md`. |
| 2026-05-06 | Segment 11F **Part 1** shipped (PRs **#517 / #520 PR A → #521 / #522 PR B → #523 PR C**, plus follow-ups #524 / merged-back layout split). Pre-flight Reviewer Experience Preview hub at `/operator/sessions/{id}/previews`. **PR A** stood up the page chrome + reviewer picker — typeahead `<input list>` + `<datalist>` with Apply / `← Previous` / `Next →` / Random + `?reviewer_email=` URL state; new `views.PreviewPickerContext` / `PreviewPickerOption` dataclasses + `build_preview_picker_context` adapter; new `POST /previews/random` route picking via server-side `secrets.choice` so no reviewer-email list leaks into client JS. Default behavior is no reviewer selected — explicit pick is the only path to an artifact render (avoids the "looks done" failure mode that defaulting-to-first introduces). **PR B** added the tabbed email previews region: a single full-width card with a `.btn-pair` tab strip (Invitation / Reminder / Responses-received) and only the active tab's body rendered at a time. Only the Invitation tab is wired to a real render adapter in Part 1 (Reminder + Responses-received render disabled with a "(coming soon)" suffix until 11F Part 2). New `views.EMAIL_PREVIEW_TABS` registry + `EmailPreviewTab` / `EmailBody` dataclasses + `build_email_preview_body` dispatch + `email_preview_from_display(user)` helper; the invitation render calls `email_templates.render_invitation` with a `PREVIEW_INVITE_URL_PLACEHOLDER` so real one-time-use tokens aren't burned on previews. Source-of-truth footer deep-links to Email Template (Setup) `?template=invitation` + Reviewers (Setup). **PR C** filled the placeholder below the `<hr>` separator with the real reviewer-surface card: an `<iframe srcdoc="…" sandbox="allow-scripts">` of the picker-selected reviewer's would-be reviewer surface, rendered with `preview_mode=True`. Sandbox uses `allow-scripts` only (no `allow-same-origin`) so the reviewer-surface inline page-toggle JS keeps working for multi-instrument Page #N navigation while opaque origin blocks parent-cookie / localStorage access; `allow-forms` stays off (the reviewer surface in `preview_mode` already suppresses Save / Submit / Discard write-path forms). `routes_reviewer.build_preview_context` grows an optional `target_reviewer` parameter so synthetic-row pad surfaces *that reviewer's* reviewees rather than the unfiltered first-three-by-id fallback. New `views.build_surface_preview_context` + `SurfacePreviewContext` / `SurfacePreviewMissing` dataclasses with scoped missing-data handling (no instruments configured / reviewer has no assignments → Setup-page link inline; the email region above the `<hr>` keeps rendering). Standalone `/sessions/{id}/preview` retired as a 308 permanent redirect to `/sessions/{id}/previews#reviewer-surface`; Session Home's "See previews" secondary button + the reviewer-surface preview-mode `PageButton.href` migrate to the hub anchor. Tests reshape: new `tests/integration/_preview_iframe.py` helper extracts + unescapes the iframe srcdoc so the existing reviewer-surface chrome / panel / inputs / page-button tests in `test_segment_11d_*.py` migrate cleanly off the retired route; `test_preview_route.py` shrinks to redirect + 403 + D9 deadline-observation contract. Layout follow-up split the picker into two side-by-side half-width cards (`Previewing as` left + `About this reviewer` right) inside a `.bottom-grid`. **PR D shipped 2026-05-07** — single dispatch branch in `views.build_email_preview_body` calling `email_templates.render_reminder(session, reviewer, PREVIEW_INVITE_URL_PLACEHOLDER)` plus the `EMAIL_PREVIEW_TABS["reminder"].is_shipped=True` flip; same shape as the responses-received tab activation in 11E PR 6. **PR E shipped via Segment 11E PR 6 (#532, 2026-05-07)** — the responses-received tab activation rode along with the editor third tab on the same `render_responses_received` helper. **Segment 11F is now fully shipped (5/5 PRs); plan archived** at `guide/archive/segment_11F_previews_page.md`. Send-test affordances per artifact (originally deferred to "either a small 11F follow-on or to Segment 11C PR F") now live in **Segment 14-1 Part A** as part of the wider email send-activation work. |
| 2026-05-09 | Major-refactor **§12** ladder shipped (20 PRs **#663 → #683**). Plan: `guide/major_refactor.md` §12. **§12.A** (PRs #663 → #667) split `app/services/instruments.py` (2,469 LOC, ~50 public functions, five concerns) into a package — `_state.py` (cross-slice plumbing including `_instrument_label`, lifted to break a display-fields ↔ legacy import cycle), `_rtds.py` (Response Type Definitions), `_display_fields.py`, `_response_fields.py` (incl. `bulk_save_fields` ~230 LOC), `_instrument_crud.py` (lifecycle + bulk toggles). `__init__.py` re-export wall keeps `from app.services import instruments; instruments.add_response_field(...)` byte-identical for all 5 importers (`csv_imports.py`, `sessions.py`, `assignments.py`, `routes_reviewer.py`, `routes_operator/_shared.py`). Model classes (`InstrumentResponseField`, `ResponseTypeDefinition`) re-exported through their natural slices. **§12.B** (PRs #668 → #678) split `app/web/views.py` (3,483 LOC, 79 builders / dataclasses) into a package along page / entity lines — `_setup.py`, `_instruments.py`, `_validate.py`, `_quick_setup.py`, `_extract_data.py`, `_invitations.py`, `_responses.py`, `_filters.py`, `_previews.py`, `_rule_builder.py` (largest, ~1,200 LOC). Same re-export-wall pattern; six callers in `app/web/` (every operator route slice + `routes_reviewer.py`) unchanged. **§12.C** (PRs #680 → #682) cross-cutting hygiene: **C1** promoted `csv_imports._decode_csv` → public `decode_csv(content, source, *, max_bytes=MAX_BYTES)` and rewrote `assignments.parse_manual_csv` to call it (drops the duplicated `MANUAL_CSV_MAX_BYTES` constant); **C2** lifted 14 inline `from app.services.rules import library/engine` and `from pydantic import TypeAdapter` callsites to module scope across `routes_operator/_quick_setup.py`, `routes_operator/_rule_builder.py`, `views/_quick_setup.py`, `views/_rule_builder.py` (no circular-import risk — purely stylistic relics); **C3** new `app/services/_queries.py::session_scoped(target, session_id)` returning a partially-applied `select` (helper + busiest-callers migration in `assignments.py`). **§12.D** (PR #683) split `tests/integration/test_display_field_routes.py` (2,167 LOC, 53 tests) into 6 per-surface files (`test_display_field_routes.py` 7 CRUD tests, `test_display_field_lazy_seeding.py` 4 tests, `test_display_field_locked_rows.py` 3 tests, `test_display_field_state_machine.py` 8 tests, `test_response_field_bulk_save.py` 17 tests + inline `reviewer_user` fixture, `test_response_type_card.py` 14 tests) backed by a new `tests/integration/_display_field_helpers.py` shared-helper module (mirroring the `_preview_iframe.py` convention). Pure relocation — no fixture or test changes. Each ladder used `git mv` for the finale slice to preserve blame. Plan archived in-place at `guide/major_refactor.md` §12. |
| 2026-05-07 | Segment 11K shipped (PRs **#544 → #545 → #546 → #547 → #548 → #549 → #550 → #551**, the 8-PR plan in order). Pins the canonical envelope schema for `AuditEvent.detail` and migrates every emitter in the codebase to it. **PR 1 (#544)** introduced the spec section `spec/architecture.md` "Audit-event detail schema" (four payload envelopes: `changes` / `snapshot` / `counts` / `set_changes`; identity slots: top-level `session_id` / `session_code`; orthogonal slots: `reason` / `refs` / `context`), the typed envelope helpers `audit.changes(...)` / `audit.snapshot(...)` / `audit.counts(...)` / `audit.set_changes(...)`, the new `write_event` kwargs `session=` / `payload=` / `reason=` / `refs=` / `context=`, and migrated the session-lifecycle family as proof. **PRs 2-5 (#545 → #548)** swept the four service-module emitter families: instruments (~18 emitters in `app/services/instruments.py`), invitations (6), responses (4), assignments (2). PR 5 introduced the `excluded_<reason>` flatten-into-`counts` pattern that lets 13A's RuleBased exclusions plug in without schema churn; PR 5 also pinned `mode` / `filename` to the new `context` slot for descriptive scalars. **PR 6 (#549)** lifted `email_template.updated` / `.reset` from `routes_operator.py` into `app/services/email_templates.py::record_template_change` / `.record_template_reset` as a no-op relocation so PR 7 could sweep them with the rest of the settings family. **PR 7 (#550)** swept the settings family: CSV imports (4), operator settings (2), email templates (2). Replaced the legacy `detail={}` on `operator_email_settings.cleared` with the canonical `detail=None`. **PR 8 (#551, this segment's closing PR)** lands the Pydantic write-validation gate: new `app/services/audit.py::EVENT_SCHEMAS` per-event-type registry pins the allowed envelopes/slots; `validate_detail` runs in `write_event` after composition; `settings.audit_strict_mode` (added to `app/config.py`) gates strict (raise `AuditDetailValidationError`) vs lenient (warn-and-write); `tests/conftest.py` flips strict on so CI catches drift. New `tests/unit/test_audit_detail_schema.py` covers the gate. **Cutover boundary** is 2026-05-07 — rows written before that date use legacy per-emitter shapes, rows written after follow the canonical envelope schema. The audit log is append-only; legacy rows are not rewritten. Closes catalog `unfinished_business.md` #5. Plan archived: `guide/archive/segment_11K_audit_event_detail_schema.md`. Unblocks **Segment 12B** (audit retention + export reads against the pinned shape). |
| 2026-05-07 | Segment 11J shipped (PRs **#526 → #527 → #528**). Quick Setup card on Session Home wires Reviewers / Reviewees / Assignments slots from inert (Segment 11H scaffold state) to live POST forms over the existing per-entity import pipelines, and unifies the card's status awareness behind a single Lock / Unlock toggle. **#526** revised the segment plan: scope refocused on the three "existing capability" slots, status awareness collapsed onto one body-greying signal that applies in every editable-conceivable state (including `ready`), slot 4 (Session settings) explicitly carved out for Segment 12A PR 6. **#527 (PR A)** flips the Reviewers and Reviewees slots live via three new routes — `POST /sessions/{id}/quick-setup/reviewers` and `.../reviewees` delegate to a thin `_handle_quick_setup_import` wrapper that reuses the same `parse / save / invalidate-if-validated` pipeline the per-entity Setup pages use; `POST /sessions/{id}/quick-setup/lock` flips a per-session `HttpOnly` cookie (`qsu_{session_id}`, scoped to `/operator/sessions/{id}`) that the context-builder reads to decide `is_locked`. New `views.cascade_message_for_replace` centralises the "this will replace N existing X (and clears M assignments)" copy as a banner-warning rendered inline above the slot's submit form. `.card.disabled` retired in favour of a single `.quick-setup-body.locked` greying signal; the Lock / Unlock toggle now renders in every editable-conceivable state including `ready`, where unlocking is purely visual — `_require_editable` stays the hard gate, with rejection surfacing as a scoped `banner-error` carrying "Pause first" copy. **#528 (PR B)** flips the Assignments slot live via `POST /sessions/{id}/quick-setup/assignments`, which auto-detects mode from the form payload: when `file` is attached and non-empty it runs the existing `parse_manual_csv` → `manual_rows_to_pairs` → `replace_assignments(mode=manual)` pipeline; otherwise it generates `full_matrix` from the stored rule via `generate_full_matrix` → `replace_assignments(mode=full_matrix)`. `exclude_self_review` honoured on both branches. Cascade banner reuses PR A's shape; per spec assignments are leaf data so the cascade copy stops at "This will replace N existing assignments." with no further consequence to surface. Slot 4 (Session settings / configuration-import) stays inert pending Segment 12A PR 6 (the seam 11H pinned still holds — that PR flips `is_wired=False → True` and supplies a `wire_url`). Failure paths share a uniform shape: parse / lifecycle / confirm-required failures 303 → Home with `?quick_setup_error={kind}&quick_setup_reason={parse|lifecycle|needs_confirm}` so the GET render places a `.banner.banner-error` inside the offending slot only. New tests: `tests/integration/test_quick_setup_card.py`. Updated scaffold expectations in `test_quick_setup_scaffold.py` and `test_session_detail_restructure.py` for the unified pattern. Plan: `guide/archive/segment_11J_quick_setup_card.md`. Spec follow-ons (lifecycle table line in `spec/quick_setup_card_spec.md`; "Lock / Unlock button does not render" line in `spec/session_home.md`) landed alongside. Closes catalog `unfinished_business.md` #30 (modulo slot 4 which carries forward into 12A). |
| 2026-05-07 | Segment 11C **Part 2** shipped (**PR #541**, PR F: outbox audit-log scaffolding). Migration `c4f6a8b0d2e5` adds the seven nullable audit-log columns to `email_outbox` per `spec/email_infra_options.md` "Future-target additions" — `error_message` (truncated transport error), `from_address` (the address actually sent from), `backend` (which `EmailTransport` implementation handled the send), `backend_message_id` (Graph / ACS operation id, third-party message id, SMTP server queue id), `delivered_at` (when delivery confirmed), `payload_hash` ((to, subject, body) hash for dedup), `correlation_id` (deterministic identifier for "this send to this recipient at this intent" — drives idempotent retry; **indexed**). `app/db/models/email_outbox.py` gains matching `Mapped[X | None]` declarations and the canonical value-set constants `EMAIL_OUTBOX_STATUSES = (queued, sending, sent, failed)` / `EMAIL_OUTBOX_KINDS = (invitation, reminder, responses_received)` so any future widening is a deliberate edit; the class docstring is updated to reflect the broader audit-log role and to point at `spec/email_infra_options.md` for the field semantics. **Pure additive** — all columns nullable, no defaults beyond column defaults, no backfill, no service-layer reads or writes. Today's enqueue paths continue to write only `status="queued"` / `"sent"`, `kind="invitation"` / `"reminder"`, and the existing baseline columns. The new columns sit inert until **Segment 14-1 Part A** lights up the dispatch helper against this stable schema. New tests at `tests/integration/test_email_outbox_schema.py`: round-trips every new column on both SQLite and the `ci-postgres` Postgres dialect, exercises an indexed `correlation_id` lookup, and pins the canonical value-set constants. Plan archived: `guide/archive/segment_11C_operations_consolidation.md`. **Segment 11C is now fully shipped.** |
| 2026-05-06 | Segment 11C **Part 1** shipped (PRs **#490 → #491 → #492 → #493**). Operations row consolidated: Manage Invitations (`/operator/sessions/{id}/invitations`) absorbs the retired Monitoring page's reviewer-centric surface and now renders a seven-column reviewer-centric table — Reviewer / Email Status / Email Sent / Review Progress / Required Fields / Last reminder / Action — with all five data cells styled as pills (`pill-count` for filled / good states, `pill-empty` for absent / not-yet states). New reviewee-centric Responses page at `/operator/sessions/{id}/responses` classifies each reviewee per `monitoring.AT_RISK_THRESHOLDS` (Complete / Adequate / At risk / No responses). Bulk reminder dispatch funnels through a single `POST /invitations/remind-incomplete` endpoint shared by both pages. Reviewer drill-in at `.../invitations/{inv_id}/detail`; reviewee drill-in at `.../responses/{reviewee_id}/detail` (both scaffolds — per-assignment / per-response detail deferred). Outbox schema slice: `email_outbox.cc_emails` / `bcc_emails` (Text, comma-separated) populated at queue time from the `email_template_overrides` JSON's `{kind}_cc` / `{kind}_bcc` keys (Migration `b3d5e7f9a1c4`). Chrome retired the Monitoring tab; `GET /sessions/{id}/monitoring` 303-redirects to `/invitations` to preserve bookmarks. Outbox is **not** a chrome tab — it stays a dev-diagnostic surface reachable via the "View outbox" button on Manage Invitations. New helpers: `monitoring.per_reviewee_coverage`, `monitoring.AT_RISK_THRESHOLDS`, `views.build_invitations_rows`, `views.build_responses_rows`. New audit events: none in Part 1 (the two Send-related events ride along with the wiring in Segment 14-1). Plan: `guide/archive/segment_11C_operations_consolidation.md`. Functional spec: `spec/operations_renew.md`. **Part 2 shipped 2026-05-07 in PR #541** — `email_outbox` audit-log column scaffolding (the seven `error_message` / `from_address` / `backend` / `backend_message_id` / `delivered_at` / `payload_hash` / `correlation_id` nullable columns per `spec/email_infra_options.md` "Future-target additions", plus `EMAIL_OUTBOX_STATUSES` / `EMAIL_OUTBOX_KINDS` value-set widening at the service layer) so all four transport options have a stable schema to write to at send time. **All wiring** — per-row Send + bulk Send + Send-test-to-me + `email_send_dispatch.py` + chrome pill + audit events + responses-received submit-time enqueue — lives in **Segment 14-1 Part A** (`guide/segment_14-1_email_infra.md`). |

---

## Segments shipped

| Segment | What it added | Completed |
|---|---|---|
| 1 | Repository skeleton, `/health`, local dev install | 2026-04-27 |
| 2 | Azure App Service deployment via OIDC | 2026-04-27 |
| 3 | Microsoft Entra ID sign-in via Easy Auth | 2026-04-27 |
| 4 | 12-table schema + Alembic migration infra | 2026-04-27 |
| 5 | Postgres provisioning + migrate-on-deploy + operator session CRUD-lite | 2026-04-28 |
| 6 | Reviewer / reviewee CSV imports + setup validation | 2026-04-28 |
| 7 | FullMatrix + Manual assignment generation + roster Manage views | 2026-04-28 |
| 8 | Reviewer dashboard + review surface (save / submit / clear / cancel); active-only roster filter retrofit | 2026-04-29 |
| 9.1 | Session activation lifecycle (draft↔ready), edit-lock, per-instrument open/close, response-window gates | 2026-04-29 |
| 9.2 | Invitation generation + dev email outbox + `/reviewer/invite/{token}` landing route | 2026-04-29 |
| 9.3 | Per-session monitoring page + per-row and bulk reminder send | 2026-04-29 |
| 9.4A | Global page chrome (app identity + user card + breadcrumb), `/about` stub, sessions list per-row Access/Delete + Create-new-session button | 2026-04-29 |
| 9.4B | Session detail four-card layout (Session / Session setup / Run Session / Danger zone), inline validate-summary card via `?validated=1`, `POST /delete-data` with `responses.deleted_all` audit event | 2026-04-29 |
| 9.4C | Reviewers / reviewees / assignments Manage pages with anchored Upload-CSV cards and disabled Edit buttons; Assign by Rules placeholder card; `/operator/sessions/{id}/instruments` index page; `/operator/sessions/{id}/setupinvite` stub; setup-table Manage buttons for Instruments and Set up invites enabled | 2026-04-29 |
| 9.5A | `validated` stored state in `SessionStatus` (between `draft` and `ready`); `GET ?validated=1` flips draft→validated when no errors; activation now requires `is_validated`; setup-mutating routes (reviewer/reviewee/assignment import + delete-all + assignment generate + session edit) flip validated→draft via dedicated `session.validated` / `session.invalidated` audit events; instrument open/close/visibility and `/delete-data` deliberately do not invalidate | 2026-04-29 |
| 10A | Consolidated `/operator/sessions/{id}/instruments` page: per-instrument card with friendly description, acceptance + visibility toggles, response-fields table (add / edit / delete / reorder, per-field help text + visibility), session-wide Instruments Settings card with bulk Open all / Close all toggles. Migration adds `help_text` (Text, NULL) and `help_text_visible` (Bool, default true) on `instrument_response_fields`. Reviewer surface refactors to loop-by-instrument with section heading from `Instrument.description` (fallback to system handle) and a per-field help block above each table. Empty-instrument validation now blocks activation. Description / field mutations invalidate `validated → draft` via `lifecycle.invalidate_if_validated()` called from inside each mutating service (post-PR for items #3 + #16, 2026-05-02); bulk accepting + per-instrument open/close/visibility deliberately do not invalidate. Body width bumped from 900px to 1400px globally with a `.table-scroll` overflow utility. | 2026-04-30 |
| 10B-1 | Backfill migration (`c2143bd329c7`) seeds three `InstrumentDisplayField` rows (`source_type='pair_context'`, `source_field='1'|'2'|'3'`, `label=''`, `order=0..2`, `visible=true`) on every existing instrument; destructive within that filter (operator-typed labels on those slots are not preserved across upgrade); operator-added `reviewee` rows left intact. `ensure_default_instrument` seeds the same three rows on new sessions. Reviewer surface renders pair-context values as separate columns sourced from the display-field rows (no longer inline in the identity cell); reviewee identity (name + email) is the always-first column, mandatory and non-toggleable. New service helpers `display_field_label(field)` and `display_field_value(field, assignment)` cover the seven D6 sources (`reviewee.tag_1/2/3`, `reviewee.profile_link`, `pair_context.1/2/3`); empty/NULL labels fall back to inferred strings. `profile_link` cells render as plain `<a>`. No operator UI yet (picker + bulk form land in 10B-2; preview route in 10B-3). No new audit events. | 2026-04-30 |
| 10B-2 | Per-instrument display-fields card on `/operator/sessions/{id}/instruments`: Add (combined source picker over the seven D6 sources minus those already on the instrument; colon-delimited values like `reviewee:tag_1`), inline Edit (label override + visibility), Delete (no cascade-confirm — display fields carry no per-row dependent data). New shared "Field order & visibility" bulk form covering both display + response fields, interleaved in operator-chosen order, with per-table independent repack to `0..N-1` on save. Four new audit events: `instrument.display_field_added`, `instrument.display_field_updated`, `instrument.display_field_deleted`, `instrument.display_fields_saved` (D11 diff shape; `added` / `removed` always empty since adds + deletes are row-level only). Reuses 10A `instrument.fields_reordered` when bulk save reorders response fields. Display-field mutations invalidate `validated → draft` and 409 when `status=ready` (mirrors 10A). Rank-based change detection on bulk save means submitting current state is a no-op. | 2026-04-30 |
| 10B-3 | New `GET /operator/sessions/{id}/preview` route renders the reviewer surface in operator-only preview mode — pads with up to three synthetic rows (`Sample Reviewee 1/2/3`, `sample1@example.edu`, …) when fewer real assignments exist; bypasses session-status / deadline / acceptance gates; all inputs render disabled (via the existing `accepting=False` template branch); save / submit / clear / cancel forms suppressed via a single `preview_mode` template flag; "Preview — not visible to reviewers" banner at the top. Two operator-side entry-point anchors at ship time (instruments page header + session detail's Run Session card); the instruments-page anchor was disabled in 10C. No new audit events (read-only — also skips the `lifecycle.observe_deadline` lazy-close side-effect). Completes Segment 10B. | 2026-04-30 |
| 10D | Instruments-page rebuild taking the per-instrument card from frame to fully-functional. Slice 1 wired the Display Fields table + URL-driven `?editing={iid}` Save / Cancel / Edit state machine on every per-instrument card (with two locked Name + Email rows, inline Friendly Label edit, ▲/▼ reorder, and operator-defined visibility on the rest). Slice 2 reused the same state machine for the Response Fields table (inline label + Required edit, ➕ row-level Add via JS-deferred `<template>` clones bound to the bulk-save form, ✗ row-level Delete via queued hidden inputs, ▲/▼ client-side reorder). Slice 3 wired Response Fields Help (per-row textarea + Show checkbox) into the same bulk-save round-trip. Slice 4a introduced the `response_type_definitions` table (10 seeded rows per session: `Long_text` / `Short_text` / `Yes_no` / `Grade` / `Likert5` / `100int` / `0-to-2int` / `1-to-5int` / `1-to-5half` / `1-to-5dec`), migrated `instrument_response_fields.response_type` (text) into `response_type_id` (FK with `ON DELETE CASCADE` + SQLite `PRAGMA foreign_keys = ON`), and rendered the new Response Type Definitions card read-only with the Response Fields Type cell as a `<select disabled>` over RTD names. Slice 4b shipped operator-add / -edit / -delete on operator-defined RTD rows with the cascade-on-delete confirmation banner; Min / Max / Step / List stay editable post-create with `update_response_type_definition` re-deriving every dependent RF's `validation` block on save. Slice 4c wired Response Fields ↔ RTD on add (Type `<select>` is enabled on JS-deferred new rows so operators can pick from the RTD catalog; saved rows stay locked per spec). Slice 4d closed the cross-cutting consistency gaps: per-instrument and RTD card editing state machines are mutually exclusive; bulk-save refuses to commit an instrument with zero Response Fields; cascade-delete that would empty an instrument is hard-blocked with a banner naming the affected instrument(s). Banner-convention follow-ups added a Cancel button + auto-scroll-on-display + Cancel-returns-to-source-row to the new error / cascade banners and pinned the convention into `spec/assumptions.md`. Slice 5 enabled multi-instrument support: `Add new instrument` + `Delete this instrument` are wired through their existing POST routes, with native `confirm()` on Delete; both buttons share an `is_ready` / mutual-exclusion / single-instrument disable gate matching the per-instrument Edit button. The action row at the bottom of every per-instrument card is a `.bottom-grid` of two half-width cards: an invisible left card hosts Save / Cancel / Edit and Add new instrument together on a right-flushed row (state-machine pair sits immediately to the left of Add); a red-bordered, white-interior Danger Zone right card hosts Delete this instrument (also right-flushed) with cascade warning copy. Post-Slice-5 polish PRs (#262 → #268) landed the half-card layout, white inner Danger Zone background, tightened cascade copy, restyled `Add a Response Type` as a proper half-width card with a single inline Name + Data Type + Add row, and right-flushed the per-instrument Delete button. | 2026-05-02 |
| 10C | Operator UI clean-up consolidating the post-10B surface: every session-scoped operator page renders a 6-button **setup nav** header card (Session / Reviewers / Reviewees / Assignments / Instruments / Email Invites); session detail adopts a `.page-grid` two-column layout (Session Details / Session Setup / Run Session) with Danger Zone in `.bottom-grid`; the inline session-detail revert form is replaced by a reusable yellow lock card pattern (with `return_to` allowlist `{reviewers, reviewees, assignments, instruments}`) shared across the four mutating setup pages; sessions list adds a `Created by` column; reviewers / reviewees / assignments pages standardise on info-card + status-pill rows + `#upload-csv` anchored card + Danger Zone, with upload + Danger Zone hidden while locked. Instruments page restructured: All Instrument Status full-width card carries three pill rows + bulk Open/Close + bulk Show/Don't-show + a disabled Preview button; per-instrument card uses pastel-tint cycling, a top `.bottom-grid` (description + per-instrument status), a `.field-builder` `.bottom-grid` of Display + Response Fields half-cards, and a live client-rendered Preview Instrument table; bottom button row (Back / Save / Edit / Add an instrument / Delete) with a JS-only Save/Edit `field-builder.locked` toggle. Response Fields gains inline label edit (per-row hidden form via HTML5 `form=` attribute), Required auto-submit, row-level Add (`/fields/add-row`) + Delete; Type stays read-only by design. Display Fields renders a hardcoded 6-row CSV-named placeholder; persistence is deferred. Multi-instrument data layer fully shipped (`Instrument.session_id`, `order`, FK cascades, `create_instrument` / `delete_instrument` services + routes + `instrument.created` / `instrument.deleted` audit events) with the operator UI behind a disabled Add button; Delete is reachable when more than one instrument exists. Bulk visibility toggles emit `instruments.bulk_visibility_when_closed`. Cross-cutting primitives in `base.html`: `.page-grid`, `.bottom-grid`, `.card-tl/r/bl/l/tr/br`, `.setup-nav`, `.setup-grid`, `.btn-row` / `.btn-pair`, `.fill-col`, `.col-shrink`, `.session-meta-row`, `.session-status-row`, `.field-builder` (+ `.locked`), `.display-edit`. `.btn[hidden]` honours the standard hidden attribute. | 2026-05-01 |
| 11A | Tier 1–3 cleanup punch list across Segments 1–10. Code shipped: shared `_parse_email` helper for CSV (#314), CSV cross-table identity check (#315), reviewer-surface polish batch (heading display logic, help text inline, photo View link, column-width hints, status-column hide-when-empty; PRs #319 → #324), `correlation_id` threaded into deadline lazy-close (#329), `invitations.py` decoupled from FastAPI `Request` (#330), `get_or_create_default_instrument` docstring refresh (#309). Decisions recorded: AG Grid → Segment 15; queue-based batch invitations → Segment 15; help-contact merge field source = per-session column on `ReviewSession`; CSRF → rely on Easy Auth + `SameSite=Lax` cookies (`docs/authentication.md`). UI: v2 chrome rebuild rolled out across the session-centric pages (`session_reviewers.html`, `session_reviewees.html`, `session_assignments.html`, `session_invitations.html`, `session_monitoring.html`, `session_outbox.html`, `session_validate.html`, `session_setupinvite.html`, `session_previews.html`, `session_detail.html`, `instruments_index.html`, plus the `session_setup_status_row.html` partial). Two follow-on Tier 4 items remain open (#21b non-session-centric v2 sweep; #24 operator-editable email template editor). Plan: `guide/archive/segment_11A_cleaning_up_unfinished_business.md`. | 2026-05-03 |
| 11E | Operator-editable email template editor + per-operator SMTP scaffolding. PRs #461 (PR 1 — schema + service-layer renderer), #462 (PR 2-A — placeholder cards), #463 (PR 4 — operator Settings page + encrypted credential storage), #464 (PR 5 — `EmailTransport` Protocol + `SmtpEmailTransport` + typed-stub `GraphEmailTransport`), #465 (PR 2 — editor UI), #468 polish (button consistency + Settings `?return_to=` plumbing), **#532 (PR 6 — responses-received template editor third tab)**. New columns `sessions.help_contact` (String 320, nullable) + `sessions.email_template_overrides` (JSON, nullable; recognises invitation / reminder / responses_received subject / body / cc / bcc keys plus the `responses_received_enabled` bool toggle) + seven `users.smtp_*` columns. New `app/services/email_templates.py` (`render_invitation` / `render_reminder` / `render_responses_received` over per-template merge-field sets — invitation / reminder share the canonical five tags, responses-received drops `$invite_url` and adds `$submitted_at` resolved via the reviewer's responses), `app/services/operator_settings.py` (`EmailSettings` dataclass, `get_email_settings` / `save_email_settings` / `clear_email_settings`), `app/services/_secrets.py` (`cryptography.fernet`-backed encrypt / decrypt keyed off `SMTP_ENCRYPTION_KEY`), `app/services/email_send.py` (transport abstraction + SMTP backend). Editor at `/operator/sessions/{id}/setupinvite` with per-template selection, per-field "Reset to default", `email_template.updated` / `email_template.reset` audit events; the responses-received tab carries an extra "Send this confirmation when a reviewer submits." checkbox backed by the `responses_received_enabled` flag. Settings at `/operator/settings` reachable from the chrome user-menu, with `?return_to=` honoured per `app/web/return_to.py`. Reviewer surface picks up a per-session `Questions? Contact <X>` line. **Nothing sends real mail yet** — outbox rows still write `status="queued"`; **Segment 14-1 Part A** is the first call site for the transport interface. Spec at `spec/email_infra_options.md` for the broader transport landscape (Options A / B / C / D — SMTP, Microsoft Graph application permission, Azure Communication Services, third-party transactional). Plan: `guide/archive/segment_11E_email_template_editor.md`. Closes `unfinished_business.md` #24 (editor side). | 2026-05-07 |
| 11F | Previews page — pre-flight Reviewer Experience Preview hub at `/operator/sessions/{id}/previews`. PRs **#517 / #520 (PR A — page chrome + reviewer picker)**, **#521 / #522 (PR B — tabbed email previews region + invitation card)**, **#523 (PR C — reviewer-surface iframe card + retire `/preview` singular)**, **#524 (layout split into `Previewing as` + `About this reviewer` half-cards)**, **#532 (PR E — responses-received tab activation, shipped via 11E PR 6 since both depend on the same `render_responses_received` helper)**, and **PR D 2026-05-07 (reminder tab activation — single dispatch branch in `views.build_email_preview_body` calling `email_templates.render_reminder` with `PREVIEW_INVITE_URL_PLACEHOLDER`; `EMAIL_PREVIEW_TABS["reminder"].is_shipped=True`)**. Reviewer picker is a typeahead `<input list>` + `<datalist>` with Apply / `← Previous` / `Next →` / Random; `?reviewer_email=` URL state survives a full-cohort re-upload. New `views.PreviewPickerContext` / `PreviewPickerOption` / `EmailPreviewTab` / `EmailBody` / `SurfacePreviewContext` / `SurfacePreviewMissing` dataclasses + `build_preview_picker_context` / `build_email_preview_body` / `email_preview_from_display(user)` / `build_surface_preview_context` adapters. Reviewer-surface iframe uses `sandbox="allow-scripts"` only (no `allow-same-origin`) so the inline page-toggle JS keeps working while opaque origin blocks parent-cookie / localStorage access; `routes_reviewer.build_preview_context` grows an optional `target_reviewer` parameter. Standalone `/sessions/{id}/preview` retired as a 308 permanent redirect. Tests reshape via `tests/integration/_preview_iframe.py` helper that extracts + unescapes the iframe srcdoc. Send-test affordances per artifact moved to **Segment 14-1 Part A**. Plan: `guide/archive/segment_11F_previews_page.md`. | 2026-05-07 |
| 11G | Validate page rebuilt as a find-and-fix surface. PRs **#505 → #508** (the four-PR segment plan) plus polish **#509 → #511**. Replaces the thin issue-list body with a setup-coverage card (4-col grid of label + status cells) + severity filter chip strip + per-issue "Fix on {Setup page} ↗" deep-links + per-issue "Why this check?" native-disclosure + activate-warns detour banner. New `ValidationRule` registry in `app/services/validation.py` carries each rule's `key` / `severity` / `why` / `fix_url` / `fix_page_label`; `validate_session_setup` iterates the registry. Two new rules: `email_template.no_help_contact` (info) and `instruments.no_display_fields` (warning). `ValidationIssue` schema gains `rule_key` / `fix_url` / `fix_anchor` / `fix_page_label` / `why` fields stamped by the orchestrator. Setup-page tables gain `id="reviewer-row-{id}"` / `id="reviewee-row-{id}"` anchors so per-issue deep-links scroll to the offending row. `ReadinessReport.has_non_blocking_findings` tightened to only consider warnings (info is advisory only). `acknowledge_warnings` checkbox removed from the Next Action card on Session Home; Activate 303s to `/validate?activate=1` when warnings exist, banner inlines the warnings + Cancel + Acknowledge-and-activate. New helpers: `views.build_validate_context`, `views.validate_lifecycle_copy`, `views.SetupCoverageRow` / `SeverityChip` / `IssueSourceGroup` dataclasses. New tests: `tests/integration/test_session_validate_page.py`. Plan: `guide/archive/segment_11G_validate_page.md`. | 2026-05-06 |
| 11K | Audit-event `detail` schema convention. 8 PRs (**#544 → #545 → #546 → #547 → #548 → #549 → #550 → #551**). Pins the canonical envelope schema for `AuditEvent.detail` and migrates every emitter in the codebase to it. Spec at `spec/architecture.md` "Audit-event detail schema": four payload envelopes (`changes` / `snapshot` / `counts` / `set_changes`), top-level identity slots (`session_id` / `session_code`), orthogonal slots (`reason` / `refs` / `context`). Typed envelope constructors `audit.changes(...)` / `.snapshot(...)` / `.counts(...)` / `.set_changes(...)` in `app/services/audit.py`. Migrated emitters (file-by-file): session lifecycle (PR 1), instruments / display fields / response types / bulk events (PR 2, ~18 emitters), invitations (PR 3), responses (PR 4), assignments (PR 5), settings family covering CSV imports + operator settings + email templates (PRs 6-7). PR 6 lifted `email_template.updated` / `.reset` from `routes_operator.py` into `email_templates.py::record_template_change` / `.record_template_reset` so the route stays thin and the settings sweep covered them. PR 8 lands the Pydantic write-validation gate: per-event-type `EVENT_SCHEMAS` registry, `validate_detail` hook in `write_event`, `settings.audit_strict_mode` flag (False in production, flipped True in `tests/conftest.py`); strict mode raises `AuditDetailValidationError`, lenient mode logs and writes through. New `tests/unit/test_audit_helpers.py` and `tests/unit/test_audit_detail_schema.py` cover the helper composition + the gate. Cutover boundary 2026-05-07 — older rows keep their legacy shapes (the audit log is append-only). Closes catalog `unfinished_business.md` #5. Unblocks **Segment 12B** (audit retention + export reads against the canonical shape). Plan: `guide/archive/segment_11K_audit_event_detail_schema.md`. | 2026-05-07 |
| 11J | Quick Setup card wiring on Session Home. PRs **#526 → #527 → #528**. Reviewers / Reviewees / Assignments slots flip from inert (Segment 11H scaffold state) to live POST forms over the existing per-entity import pipelines. New routes `POST /sessions/{id}/quick-setup/reviewers` / `.../reviewees` / `.../assignments` delegate to thin wrappers (`_handle_quick_setup_import` / `quick_setup_assignments_submit`) that reuse the existing parse / save / `invalidate_if_validated` pipelines; `POST /sessions/{id}/quick-setup/lock` flips a per-session `HttpOnly` cookie (`qsu_{session_id}`, scoped to `/operator/sessions/{id}`) that the context-builder reads to decide `is_locked`. Status awareness collapses on one body-greying signal — `.quick-setup-body.locked` — applied in every editable-conceivable state including `ready`; `.card.disabled` retired. Lock / Unlock toggle renders consistently across `draft` / `validated` / `ready`; on `ready` unlocking is purely visual and `_require_editable` stays the hard gate (rejection surfaces as a scoped `banner-error` with "Pause first" copy). Assignments route auto-detects mode from the form payload (file attached ⇒ manual-CSV pipeline; else FullMatrix rule generation). Cascade-aware confirmation copy lives in new `views.cascade_message_for_replace` helper and renders as a banner-warning inline above the submit form. Slot 4 (Session settings / configuration-import) stays inert per the seam 11H pinned — graduates with Segment 12A PR 6. New tests: `tests/integration/test_quick_setup_card.py`. Spec follow-ons in `spec/quick_setup_card_spec.md` and `spec/session_home.md` align with the unified status-awareness model. Plan: `guide/archive/segment_11J_quick_setup_card.md`. Closes catalog `unfinished_business.md` #30 (modulo slot 4). | 2026-05-07 |
| 11H | Placeholder card scaffolds (Quick Setup + Extract Data on Session Home). PRs **#480 → #481 → #482 → #483 → #484 → #485 → #486 → #487**. Replaces the post-11B `placeholder_card(...)` stubs with full inert scaffolds: Quick Setup card with four slots (Reviewers / Reviewees / Assignments / Session settings) + Extract Data card with the per-entity row set, all controls disabled until the wiring segments. New partials `_quick_setup_card.html` + `_extract_data_card.html`; new dataclasses `QuickSetupSlot` / `QuickSetupContext` / `ExtractDataRow` / `ExtractDataContext` + builder helpers in `app/web/views.py`. The Quick Setup card on `/operator/sessions/new` consumes the same scaffold via `build_new_session_quick_setup_context`. Polish stream pinned the visual + DOM contract (2-column top grid, lock toggle, Exclude self-review checkbox, card reordering on Session Home). Plan: `guide/archive/segment_11H_placeholder_card_scaffolds.md`. Unblocks Segment 11J (Quick Setup wiring) and Segment 12A PR 6 (Extract Data wiring). | 2026-05-06 |
| 11C Part 2 | Outbox audit-log scaffolding (schema-only). **PR #541** (PR F). Migration `c4f6a8b0d2e5` adds the seven nullable audit-log columns to `email_outbox` per `spec/email_infra_options.md` "Future-target additions" — `error_message`, `from_address`, `backend`, `backend_message_id`, `delivered_at`, `payload_hash`, `correlation_id` (the last is **indexed** because the Segment 14-1 dispatch helper looks rows up by it on idempotent retry). `app/db/models/email_outbox.py` gains matching `Mapped[X | None]` declarations and the canonical value-set constants `EMAIL_OUTBOX_STATUSES = (queued, sending, sent, failed)` / `EMAIL_OUTBOX_KINDS = (invitation, reminder, responses_received)` so any future widening at the service layer is a deliberate edit; the class docstring is updated to reflect the broader audit-log role and to point at `spec/email_infra_options.md` for the field semantics. **Pure additive** — all columns nullable, no defaults beyond column defaults, no backfill, no service-layer reads or writes. Today's enqueue paths continue to write only `status="queued"` / `"sent"` and `kind="invitation"` / `"reminder"` plus the existing baseline columns; the new columns sit inert until **Segment 14-1 Part A** lights up the dispatch helper against this stable schema. New tests at `tests/integration/test_email_outbox_schema.py`: round-trips every new column (including the timezone-aware `delivered_at`) on both SQLite and the `ci-postgres` Postgres dialect, exercises an indexed `correlation_id` lookup, and pins the canonical value-set constants. Plan: `guide/archive/segment_11C_operations_consolidation.md` "Part 2". | 2026-05-07 |
| 11C Part 1 | Operations consolidation — Manage Invitations rewrite + new Responses page + Monitoring retired. PRs **#490** (chrome: restore Outbox tab — later removed in #493), **#491** (Manage Invitations rewrite with the seven-column reviewer-centric table + `email_outbox.cc_emails` / `bcc_emails` migration `b3d5e7f9a1c4` + reviewer drill-in scaffold), **#492** (new Responses page + reviewee drill-in scaffold + retire `session_monitoring.html` + `/monitoring` 303 redirect to `/invitations`), **#493** (drop Outbox from chrome — now reachable only via the "View outbox" button on Manage Invitations — and pillify the five data cells on Manage Invitations). Manage Invitations columns: Reviewer / Email Status / Email Sent / Review Progress / Required Fields / Last reminder / Action; data cells render inside `<span class="pill ...">` (`pill-count` for filled / good states, `pill-empty` for absent / not-yet states). Responses page (`/operator/sessions/{id}/responses`) classifies reviewees per `monitoring.AT_RISK_THRESHOLDS` (`adequate_fraction=0.5`) into Complete / Adequate / At risk / No responses. Bulk reminder dispatch funnels through `POST /operator/sessions/{id}/invitations/remind-incomplete` (single-source — both pages call it). Drill-ins at `.../invitations/{inv_id}/detail` and `.../responses/{reviewee_id}/detail` ship as scaffolds; per-assignment / per-response detail deferred. Operations row is now **four tabs**: Validate / Previews / Invitations / Responses (Outbox is a dev-diagnostic surface, not a chrome tab). New helpers: `monitoring.per_reviewee_coverage`, `monitoring.AT_RISK_THRESHOLDS`, `views.build_invitations_rows`, `views.build_responses_rows`, `email_templates.cc_bcc_for`. New breadcrumbs: `breadcrumbs.operator_session_invitations_reviewer`, `.operator_session_responses_reviewee`. Test reorg: `tests/integration/test_monitoring.py` → `test_reminders.py`; new `test_segment_11c_pr3_responses.py`. Plan: `guide/archive/segment_11C_operations_consolidation.md`. Functional spec: `spec/operations_renew.md`. Part 2 (the schema scaffolding for the 14-1 dispatch helper) shipped as PR #541 on 2026-05-07 — see the row above. |
| 2026-05-07 | Email subsystem plan reshuffle. **Segment 11E retired to archive** after PR 6 (#532) shipped the responses-received template editor (third tab + per-session "Send when reviewer submits?" checkbox + `render_responses_received` helper + `responses_received_enabled` getter/setter + `views.merge_tags_for_template` + `EMAIL_PREVIEW_TABS` registry flip lighting up the previously deferred Preview hub artifact card). **Segment 11C Part 2 truncated** to ship only the `email_outbox` audit-log column scaffolding (`error_message` + the spec's "Future-target additions" — `from_address` / `backend` / `backend_message_id` / `delivered_at` / `payload_hash` / `correlation_id`; status / kind value-set widening at the service layer) — no wiring, no UI; the columns sit inert until **new Segment 14-1** lights up the actual send paths. **Segment 14-1 created** as the home for *all* email *wiring* — absorbs the formerly-11C-Part-2 send-activation work (per-row Send + bulk Send + Send-test-to-me + `email_send_dispatch.py` + chrome pill + `email.sent` / `email.send_failed` audit events + responses-received submit-time enqueue with `responses_received_email.queued`) plus the broader transport landscape from `spec/email_infra_options.md` (correlation_id strategy, bulk-send queue + worker, per-deployment from-identity defaults, generalised Outbox diagnostic surface, Options B / C / D backend implementations). Stub at `guide/segment_14-1_email_infra.md`; functional spec stays at `spec/email_infra_options.md`. **Segment 11F Part 2 collapses to PR D only** — PR E (Responses-received tab) shipped via 11E PR 6 since the registry mutation + dispatch branch rode along with the editor third tab on the same `render_responses_received` helper. Plan-revision PRs: **#531** (narrow 11E to editor-only + reframe send wiring as a 11C Part 2 PR H seam) → **#532** (11E PR 6 ship) → **THIS PR** (retire 11E + truncate 11C Part 2 + create 14-1). | 2026-05-06 |
| 11D follow-on | Reviewer surface multi-instrument rewrite plus the numeric-field validation polish stream. PRs #428 (α — URL routing + dashboard rewiring), #430 (β — top-row layout + per-page status pills), #431 (γ — unified action row + multi-instrument heading), #432 (δ — client-side page navigation + dirty preservation), #433 (ε — page-aware missing-required banner + preview adaptation), then polish #434–#448. Highlights: per-page `PageStatus` (`not_started` / `in_progress` / `complete` / `submitted`); URL `/reviewer/sessions/{id}/{instrument_position}` with `current_position` hidden field driving Save / Submit; client-side group toggle + `pushState` keeps reviewer-typed dirty edits across pages; per-position Save filter; missing-required moved from a panel banner to its own full-width 2-column `.rs-missing-card`; Submit became a hard gate on missing required (acknowledge-and-submit-anyway retired); save / submit flash banners removed; numeric-field validation landed as `<input type="number">` with `min`/`max` + `step="any"` + hidden spinners + `title` constraint hint + JS `setCustomValidity` for step-grid violations (with `1e-6` tolerance) + server-side `validate_value` backstop in `responses.py`; per-instrument constraint summary line above each table reads e.g. `**Rating** (1-5, steps of 1), **Comments** (0-2000 char)` (List rows omitted). New helpers: `views.placeholder_for_field`, `views.constraint_summary_for_field`, `views.page_button_label`, `views.instrument_heading`. Plan: `guide/archive/segment_11D_v2_sweep_non_session.md` "Follow-on". | 2026-05-05 |
| 11L | `Instrument.short_label String(32) | NULL` column + Setup-side editor (`/operator/sessions/{id}/instruments`). Reviewer-surface Page #N buttons and per-instrument H2 headings consume it via `views.page_button_label(instrument, position)` and `views.instrument_heading(instrument, position, total_count)`. Bare `Page #N` fallback when unset. Independent prereq for Segment 11D follow-on PR γ. PR #429. Plan: `guide/archive/segment_11L_instrument_short_label.md`. | 2026-05-04 |
| 11B | Session Home rebuild end-to-end across PRs #380 → #393. New `app/services/lifecycle_display.py` + `lifecycle_label` Jinja filter so `ready` renders as **"Activated"** wherever an operator reads it (status pill, sessions list, prose). `session_detail.html` body rebuilt around three left-column cards (Next Action / Quick Setup / Extract Data) and two right-column cards (Session Details / Danger Zone). The **Next Action card** is the page's center of gravity: constant H2 ("Next Action"), `accent-blue` border matching the Primary button, fixed `min-height: 200px`, three vertically-stacked children (`.next-action-body` flex-grows; optional `.next-action-confirm` for the Pause checkbox; `.next-action-buttons` pinned at the bottom). All actions render as buttons in the bottom row — Primary (Validate Setup / Activate Session / Pause Session) plus Secondary supporting actions (See validation details / See previews / Revert to draft / Manage invitations / Monitor responses), with state-conditional trims and sentence-case copy. POST forms (Activate / Revert to draft / Pause) declare a hidden form id in the body and the bottom-row button declares `form="next-action-{name}-form"` so the form definition stays near its checkbox. `POST /operator/sessions/{id}/revert` extended to dispatch by current status: `validated → draft` calls `lifecycle.invalidate_session(reason="operator_revert")`; `ready → draft` calls `lifecycle.revert_session_to_draft`. Quick Setup and Extract Data on Home plus Rule Based Assignment on the Assignments page now share a canonical `.card.placeholder` class + `placeholder_card` Jinja macro (uniform muted treatment regardless of state); Quick Setup greys in `ready`; Extract Data greys in `draft` / `validated`. Danger Zone Delete Session is **visible-but-disabled** in `ready` rather than hidden (server-side gate in `_require_editable` is the source of truth). Stale `.pill-lifecycle-closed` v2 CSS retired. Spec at `spec/session_home.md`; plan at `guide/archive/segment_11B_session_home.md`. | 2026-05-04 |

Migration round-trips on both SQLite (every test session) and Postgres
(every PR via the `ci-postgres` job, which also runs the full pytest
suite against a `postgres:16` service container).

---

## Capabilities today

### Infrastructure & dev loop

- **Azure App Service** (Linux, Python 3.12, gunicorn + uvicorn).
- **Azure Postgres Flexible Server** (Burstable B1ms, Pg 16, Southeast
  Asia). Public access with firewall allow-list ("Allow Azure
  services" + dev IP). VNet integration deferred to Segment 14.
- **Deploy on push to `main`** — three jobs: `build` → `migrate` →
  `deploy`. The `migrate` job runs `alembic upgrade head` against
  Azure Postgres before the App Service swap; deploy is skipped if
  migration fails.
- **CI on every PR**: SQLite pytest plus a `ci-postgres` job that
  applies and round-trips migrations and runs the full pytest suite
  against a `postgres:16` service container. The `engine` fixture in
  `tests/conftest.py` honours `TEST_DATABASE_URL` / `DATABASE_URL` so
  the same suite covers both dialects without duplication.
- **Test infrastructure**: in-memory SQLite engine running real
  Alembic migrations once per session; per-test savepoint-based
  isolation so service-layer commits don't leak across tests;
  `make_client` factory for multi-user integration tests.
- **Documentation**: `docs/{authentication,database,imports}.md`,
  `docs/deployment_dev.md` (incl. one-time Postgres GRANT bootstrap),
  segment plans in `guide/`.

### Authentication & permissions

- **Microsoft Entra ID via Azure Easy Auth** in deployed environments.
- **Local fake-auth fallback** (`ALLOW_FAKE_AUTH=true`) for offline
  development.
- **`AuthenticatedUser`** dataclass parses `X-MS-CLIENT-PRINCIPAL` and
  the simpler `X-MS-CLIENT-PRINCIPAL-{NAME,ID,IDP}` headers.
- **`get_or_create_user`** dependency creates a `User` row on first
  sign-in. We don't pre-provision.
- **`require_session_operator`** dependency gates every operator route
  on a `SessionOperator(user, session)` row — non-operators get **403**
  and never see another operator's session.
- **Diagnostic pages**: `/me` (JSON), `/me/debug` (HTML with the raw
  claims list and a sign-out link).

### UI / branding

- Inline-SVG favicon (bird emoji 🐦) defined in
  `app/web/templates/base.html`. Edit the emoji or the SVG markup
  in the `<link rel="icon">` data URI to change it; for a real
  graphic asset, mount `StaticFiles` and point `href` at
  `/static/favicon.png`.
- **Manage-page reshape (Segment 9.4C)**: the reviewers, reviewees,
  and assignments Manage pages now render an always-present
  `<section id="upload-csv">` card with the existing import form;
  the Upload CSV button is `<a href="#upload-csv">` (no JS, no
  `<details>`, stateful via the URL fragment). Validation errors on
  POST re-render the Manage page itself — there is no longer a
  standalone `…/import` GET. The assignments page also carries an
  anchored `<section id="rules">` "Assign by Rules" placeholder
  (Rule editor — Segment 13) with a Cancel anchor that drops the
  fragment. **Edit Reviewers / Reviewees / Assignments** buttons
  render as disabled anchors (`<a class="btn disabled"
  aria-disabled="true">`) per the 9.4B disabled-affordance
  convention. New `/operator/sessions/{id}/instruments` index
  introduced (Segment 10C reshaped this page substantially — see
  the Segments-shipped 10C entry and the operator URL table for
  the current contract). New `/operator/sessions/{id}/setupinvite`
  is the operator-editable email template editor (Segment 11E
  shipped the editor + the SMTP transport scaffolding; the page
  was a stub through Segment 11D follow-on). Session-detail
  Setup table Manage buttons for Instruments and Set up invites
  are now real links.
- **Page chrome (Segment 9.4A)** in `app/web/templates/base.html`:
  top-left "Review Robin Web App (version {num})" link to `/about`,
  breadcrumb trail rendered just below, top-right user card with
  "Signed in as ..." + Sign out. Per-page back-links across pages
  are removed — the breadcrumb replaces them. (Segment 10C
  reintroduced one in-page Back affordance: the per-instrument
  card's bottom button row carries a Back button that
  smooth-scrolls to the top of the Instruments page. This is a
  same-page navigation aid, not a cross-page back-link.)
  Operator-page crumbs root at `Sessions → /operator/sessions`;
  reviewer-page crumbs root at `Reviewer → /reviewer`. Crumb
  factories live in `app/web/breadcrumbs.py`; the partial is
  `app/web/templates/_partials/breadcrumb.html`. Version string
  comes from `app.config.app_version` (`"dev"` for now;
  pipeline-driven version bumping is a Segment 14 concern).
- **Setup nav + lock card (Segment 10C)**: every session-scoped
  operator page (Session detail, Reviewers, Reviewees,
  Assignments, Instruments, Set up invites) renders a 6-button
  `.setup-nav` header card and — when the session is `ready` — a
  reusable yellow lock card immediately below it. The lock card
  posts to `/operator/sessions/{id}/revert` with a hidden
  `return_to` field; the route allowlists
  `{reviewers, reviewees, assignments, instruments}` so the
  operator lands back on the same page. The session-detail lock
  card omits `return_to`. While locked, each page hides its own
  mutation affordances (upload cards, Danger Zone, per-instrument
  Save button); `<input>` / `<select>` elements inside
  `.field-builder` are disabled. See `spec/operator_ui_concept.md` for
  the per-page contract and `spec/assumptions.md` for the markup.
- Card-based layout, monospace tabular code spans, severity pills
  (`error` / `warning` / `info`) for validation issues. All inline
  `<style>` in `base.html`. CSS framework / extraction is a Segment
  14 concern.
- **Session Home rebuild (Segment 11B)**: `session_detail.html`
  renders a two-column body. Left column: a **Next Action card**
  (constant H2 "Next Action", `accent-blue` border; height grows to
  fit content; per-state Primary + Secondary buttons at the bottom
  for most states; the Activated state lays out as two body sections
  separated by an `<hr>` with their own inline buttons — Manage
  invitations + Monitor responses, then Pause Session); Quick Setup;
  Extract Data. Right column:
  Session Details + Danger Zone. The two left-column placeholder
  cards plus the Rule Based Assignment card on `/assignments`
  share the canonical `.card.placeholder` class + `placeholder_card`
  Jinja macro
  (`app/web/templates/operator/partials/_placeholder_card.html`),
  so all three render with identical typography and contrast.
  See `spec/session_home.md`.
- **Lifecycle display label mapping (Segment 11B)**: a single
  helper in `app/services/lifecycle_display.py` translates
  `ReviewSession.status` enum values into operator-facing strings.
  Today's only divergence is `ready` → "Activated"; other states
  pass through capitalised. Registered as the `lifecycle_label`
  Jinja filter on the operator templates instance and used by every
  surface that renders a lifecycle state in user copy (status pill,
  sessions list table, Session Home prose, lock-card prose on
  Invitations / Monitoring). URL slugs, query params, API
  responses, log messages, audit-event detail, and CSS class names
  continue to use enum values.

### Operator-facing app

| URL | What it does |
|---|---|
| `GET /` | service metadata |
| `GET /health` | unauthenticated `{"status": "ok"}` |
| `GET /about` | unauthenticated stub page; chrome's app-identity link target |
| `GET /me`, `/me/debug` | identity introspection |
| `GET /operator/sessions` | list of sessions where user is operator |
| `GET /operator/sessions/new` | create form |
| `POST /operator/sessions` | create + insert `SessionOperator` + audit + 303 |
| `GET /operator/sessions/{id}` | Session Home (post-11B shape, with 11H scaffolds) — two-column body: left column stacks **Next Action card** (constant H2, blue border, fixed min-height, state-conditional Primary + Secondary buttons at the bottom; surfaces Validate Setup / Activate Session / Pause Session per lifecycle state), then **Quick Setup** (4-slot scaffold via `_quick_setup_card.html`) and **Extract Data** (per-entity row scaffold via `_extract_data_card.html`); right column stacks Session Details (with Edit link) and Danger Zone (Delete Data + Delete Session, both visible-but-disabled in `ready`). Quick Setup / Extract Data render every slot / row / button visible-but-disabled until 11J / 12A wire them up. `?validated=1` re-runs setup validation and (when no blocking errors) marks the session `validated`; the Next Action card switches its primary button to **Activate Session**. When warnings exist, that button 303s to `/validate?activate=1` for a confirmation banner with the warnings inline (Segment 11G PR D); when warnings don't exist, the button POSTs directly. Spec at `spec/session_home.md`. |
| `GET /operator/sessions/{id}/edit` | edit form |
| `POST /operator/sessions/{id}/edit` | apply changes + audit |
| `POST /operator/sessions/{id}/delete` | delete session and all dependents (confirm; locked while `ready`) |
| `POST /operator/sessions/{id}/delete-data` | wipe every reviewer Response for the session; preserves setup; allowed in any status; emits `responses.deleted_all` audit event |
| `GET /operator/sessions/{id}/validate` | read-only setup validation deep-dive (Activate moved to the inline summary card on session detail) |
| `GET /operator/sessions/{id}/reviewers` | roster Manage view with anchored `#upload-csv` import card and disabled Edit Reviewers button |
| `POST /operator/sessions/{id}/reviewers/import` | parse + replace + audit; on validation errors re-renders the Manage page |
| `POST /operator/sessions/{id}/reviewers/delete-all` | delete every reviewer + cascade |
| `GET /operator/sessions/{id}/reviewees` | roster Manage view with anchored `#upload-csv` import card and disabled Edit Reviewees button |
| `POST /operator/sessions/{id}/reviewees/import` | parse + replace + audit; on validation errors re-renders the Manage page |
| `POST /operator/sessions/{id}/reviewees/delete-all` | delete every reviewee + cascade |
| `GET /operator/sessions/{id}/assignments` | hub (counts, mode pill, current pairs) with anchored `#upload-csv` manual-import card, anchored `#rules` Assign-by-Rules placeholder, and disabled Edit Assignments button |
| `POST /operator/sessions/{id}/assignments/full-matrix` | preview / save |
| `POST /operator/sessions/{id}/assignments/manual/import` | preview / save |
| `POST /operator/sessions/{id}/assignments/delete-all` | delete every assignment, clear mode |
| `POST /operator/sessions/{id}/activate` | flip session draft→ready (warn-and-acknowledge for non-blocking findings) |
| `POST /operator/sessions/{id}/revert` | dispatched by current status (Segment 11B): `ready → draft` calls `lifecycle.revert_session_to_draft` (confirm checkbox required; closes all instruments); `validated → draft` calls `lifecycle.invalidate_session(reason="operator_revert")` (no confirm checkbox). Wired to the Pause Session and Revert to draft buttons in the Next Action card on Session Home. |
| `GET /operator/sessions/{id}/instruments` | consolidated instruments page (post-10C shape) — setup nav header, yellow lock card when ready, full-width **All Instrument Status** card (deadline + accepting + visibility pill rows; bulk Open/Close + bulk Show/Don't-show; disabled Preview button), then one pastel-tinted card per instrument with a top `.bottom-grid` (description + per-instrument status), a `.field-builder` `.bottom-grid` of Display + Response Fields half-cards, a live client-rendered Preview Instrument #N table, and a Back / Save / Edit / Add an instrument / Delete button row. Multi-instrument schema + services ship; the `Add an instrument` button is the single UI gate (disabled with tooltip). Display Fields render a hardcoded 6-row CSV-named placeholder; the schema-level display-field routes still exist server-side but the template doesn't post to them. See `spec/instruments.md` for the per-section contract. |
| `GET /operator/sessions/{id}/setupinvite` | operator-editable email template editor (Segment 11E). Two-card `.bottom-grid`: composer left, merge tags + Save / Cancel right. `?template=invitation|reminder` selects the active template; per-field "Reset to default" forms remove individual override keys. POSTs to `POST .../setupinvite` (save) and `.../setupinvite/reset` (per-field reset). |
| `GET /operator/settings` | per-operator Settings page (Segment 11E). SMTP credentials (host / port / username / app-password / display name / encryption mode) stored on `users.smtp_*`; password encrypted at rest via `cryptography.fernet` keyed off the `SMTP_ENCRYPTION_KEY` env var. Honours `?return_to=<path>` per `app.web.return_to`. Reachable via the chrome user-menu Settings link. POSTs to `POST /operator/settings` (save) and `.../settings/clear` (wipe). |
| `GET /operator/sessions/{id}/instruments/{instrument_id}` | legacy redirect — 303 to `/instruments` (back-compat for bookmarks; 10A) |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/edit` | edit friendly description (`Instrument.description`); audit `instrument.described`; invalidates `validated → draft` |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/fields` | add a response field; auto-derives `field_key` from label when blank; audit `instrument.field_added` |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/fields/{field_id}/edit` | edit a response field (label / required / validation / help text + visibility); audit `instrument.field_updated`; banner-warns when optional → required leaves existing reviewer rows incomplete |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/fields/{field_id}/delete` | delete a response field; cascade-confirm flow when responses exist; audit `instrument.field_deleted` |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/fields/{field_id}/move` | up / down reorder; repacks `0..N-1`; audit `instrument.fields_reordered` |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/display-fields` | add a display field (one of the seven D6 sources, posted as `source_pair=reviewee:tag_1`); audit `instrument.display_field_added`; invalidates `validated → draft`; `DisplaySourceError` (unknown source / duplicate) redirects with `?display_source_error=<pair>` |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/display-fields/{df_id}/edit` | edit label override + visibility; `(source_type, source_field)` are immutable; audit `instrument.display_field_updated` (diff-shaped) |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/display-fields/{df_id}/delete` | delete a display field; no cascade-confirm; audit `instrument.display_field_deleted` (with snapshot) |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/fields/save` | shared bulk form covering display + response fields — repacks `order` to `0..N-1` per table independently; persists display rows' `visible` + `label`; audit `instrument.fields_reordered` (when response order changes) and / or `instrument.display_fields_saved` (D11 diff shape) |
| `GET /operator/sessions/{id}/preview` | retired in Segment 11F PR C; permanent (308) redirect to `/sessions/{id}/previews#reviewer-surface` (the surface card on the consolidated Previews hub). Bookmarks + external links keep working through the redirect |
| `GET /operator/sessions/{id}/previews` | Operations-row Previews hub — pre-flight Reviewer Experience Preview. Picker (typeahead / Prev / Next / Random / `?reviewer_email=`) drives a tabbed email region (Invitation live; Reminder + Responses-received tabs disabled until 11F Part 2) plus a sandboxed iframe of the picker-selected reviewer's would-be reviewer surface (`sandbox="allow-scripts"` only — opaque origin blocks cookie / localStorage access while preserving the inline page-toggle JS) |
| `POST /operator/sessions/{id}/previews/random` | server-side `secrets.choice` over the session's reviewer list; 303 redirects to `?reviewer_email=…` so no reviewer-email list leaks into client JS |
| `POST /operator/sessions/{id}/instruments/accepting/all-on` | bulk-open every instrument under the session; audit `instruments.bulk_accepting_responses` (ready-only, pre-deadline; deliberately does NOT invalidate `validated`) |
| `POST /operator/sessions/{id}/instruments/accepting/all-off` | bulk-close every instrument |
| `POST /operator/sessions/{id}/instruments/visibility/all-on` | bulk-flip `responses_visible_when_closed=True` on every instrument; audit `instruments.bulk_visibility_when_closed` (always available; deliberately does NOT invalidate `validated`) |
| `POST /operator/sessions/{id}/instruments/visibility/all-off` | bulk-flip `responses_visible_when_closed=False` on every instrument |
| `POST /operator/sessions/{id}/instruments/add` | create a new instrument under the session (optional `after={instrument_id}` for placement); audit `instrument.created`; invalidates `validated → draft`. UI button currently disabled — multi-instrument operator UI is intentionally deferred |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/delete` | delete an instrument and its dependents (cascades response fields, display fields, and assignments via FK delete-orphan); audit `instrument.deleted`; invalidates `validated → draft`. UI button only renders when more than one instrument exists; 400 when deleting the last instrument |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/open` | start accepting responses (requires session ready, pre-deadline) |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/close` | stop accepting responses (manual) |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/visibility` | toggle `responses_visible_when_closed` |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/fields/add-row` | append a new response field with a default key/label/type after `after={field_id}` (or at the end when omitted); audit `instrument.field_added`; invalidates `validated → draft`. Powers the Response Fields ➕ button on the per-instrument card |
| `GET /operator/sessions/{id}/invitations` | consolidated reviewer-centric Manage Invitations page (Segment 11C Part 1). Seven-column pill-styled table — Reviewer / Email Status / Email Sent / Review Progress / Required Fields / Last reminder / Action — absorbs the retired Monitoring page's per-reviewer progress + reminder affordances |
| `GET /operator/sessions/{id}/invitations/{iid}/detail` | reviewer drill-in scaffold from a Manage Invitations row (Segment 11C Part 1) |
| `POST /operator/sessions/{id}/invitations/generate` | bulk-create invitations for assigned active reviewers (idempotent; ready-only) |
| `POST /operator/sessions/{id}/invitations/send-all` | write outbox row per pending invitation (ready-only) |
| `POST /operator/sessions/{id}/invitations/{iid}/send` | send a single invitation (rotates token; ready-only) |
| `POST /operator/sessions/{id}/invitations/{iid}/regenerate` | rotate token + reset to pending (ready-only) |
| `POST /operator/sessions/{id}/invitations/{iid}/remind` | send a single reminder reusing the prior invitation URL (ready-only) |
| `POST /operator/sessions/{id}/invitations/remind-incomplete` | bulk reminders to every incomplete reviewer (ready-only). Single-source endpoint for both Manage Invitations and Responses bulk-remind buttons (Segment 11C Part 1) |
| `GET /operator/sessions/{id}/responses` | reviewee-centric coverage view (Segment 11C Part 1). Each row classifies a reviewee per `monitoring.AT_RISK_THRESHOLDS` (Complete / Adequate / At risk / No responses) |
| `GET /operator/sessions/{id}/responses/{reviewee_id}/detail` | reviewee drill-in scaffold from the Responses table (Segment 11C Part 1) |
| `GET /operator/sessions/{id}/outbox` | dev-mode email outbox view for the session. **Not a chrome tab** — reachable via the "View outbox" button on Manage Invitations |
| `GET /operator/sessions/{id}/monitoring` | 303-redirects to `/invitations`. The Monitoring page itself was retired in Segment 11C Part 1; the redirect preserves old bookmarks |

### Reviewer-facing app

| URL | What it does |
|---|---|
| `GET /reviewer` | dashboard: sessions where user has an active `Reviewer` row; per-session pill (`not started` / `in progress` / `submitted`) |
| `GET /reviewer/invite/{token}` | invitation token landing — Easy Auth required, email-match check, stamps `opened_at`, 303 to surface |
| `GET /reviewer/sessions/{id}` | review surface: editable table of assigned reviewees and Default Instrument fields; ?saved=ok / ?submitted=ok flash banners |
| `POST /reviewer/sessions/{id}/save` | upsert response cells (empty value deletes the row); 303 → surface with `?saved=ok` |
| `POST /reviewer/sessions/{id}/submit` | persist + validate required; 400 + warn-and-override on missing without acknowledge; else stamps `submitted_at` and 303 → surface with `?submitted=ok` |
| `POST /reviewer/sessions/{id}/clear` | delete every response for this reviewer in this session (confirm checkbox required); 303 → surface |

The Cancel link on the surface is just `<a>` back to `GET /reviewer/sessions/{id}` — no server-side state change.

### Sessions

- Create with name, code (unique per operator), description, deadline.
- Session creation **also synchronously creates the Default
  Instrument** with two seed response fields (`rating` integer 1–5
  required; `comments` long text optional) and three seed display
  fields (`pair_context_1/2/3`, `visible=true`, `label=''`). Operator
  edits both kinds via the consolidated `/instruments` page (10A:
  response-field builder + friendly description; 10B-1: data-driven
  reviewer-surface render; 10B-2: display-field picker + shared
  field-order bulk form, replaced by the 10C per-instrument card
  shape — Display Fields renders a hardcoded 6-row CSV-named
  placeholder with persistence deferred, while the 10B-2
  schema-level routes remain in place; Response Fields inline edit
  + Required auto-submit + row-level Add/Delete are wired). The
  seven supported display-field sources at the schema layer are
  `reviewee.tag_1/2/3`, `reviewee.profile_link`, and
  `pair_context.1/2/3`; `assignment_context_*` is deliberately
  excluded. See `spec/architecture.md` "Conceptual hierarchy."
- View detail with live counts of reviewers, reviewees, assignments,
  and the current `assignment_mode`.
- **Edit** name / code / description / deadline; changes recorded as
  `session.updated` with a `changes: {field: [old, new]}` map.
- **Delete** session — removes operators, reviewers, reviewees,
  instruments, assignments, invitations, and the session's audit
  events; a final `session.deleted` event with `session_id=None`
  survives in the global audit log. Requires explicit confirm
  checkbox.

### Reviewers & reviewees

- **CSV upload** with required `ReviewerName/ReviewerEmail` (or
  `RevieweeName/RevieweeEmail`); optional `Tag1/2/3` for future
  RuleBased; optional `PhotoLink` on reviewees.
- **One-shot replace** with explicit confirm checkbox when the session
  already has rows. CSV files cap at 1 MiB / 5000 rows. Unknown
  columns are silently ignored. UTF-8 with BOM tolerated.
- **Browseable Manage views** showing the saved rows in a table,
  with an anchored `Upload CSV` card on the same page (no separate
  `…/import` GET) and a disabled `Edit Reviewers` / `Edit Reviewees`
  button reserved for the future inline-edit pattern.
- **Setup validation** page lists structural issues (no reviewers, no
  reviewees, duplicate emails) plus info-level placeholders for not-
  yet-implemented surfaces.
- **Cascade safety**: re-uploading a roster on a session with
  assignments deletes those assignments via ORM cascade. Operator
  sees a warning before they confirm. Audit event records the
  cascaded count.
- **Delete all** reviewers / reviewees from the roster Manage page
  with explicit confirm checkbox. Cascades to assignments. Audit
  events `reviewers.deleted_all` / `reviewees.deleted_all` record
  both the deleted count and the cascaded assignment count.

### Assignments

- **Hub page** at `/operator/sessions/{id}/assignments` with current
  count, mode pill, browseable Pairs table, and per-mode generation
  forms.
- **FullMatrix mode**: deterministic every-with-every; default
  excludes self-review (case-insensitive email/identifier match);
  preview shows total + coverage + the first 200 pairs; replace-all
  on confirm. Inactive reviewers and reviewees (rows whose `status`
  is anything other than `"active"`) are silently excluded; the
  audit `excluded_counts` records `inactive_reviewer` /
  `inactive_reviewee` keys when any are skipped.
- **Manual CSV mode**: required `ReviewerEmail`/`RevieweeEmail` (must
  exist in roster, and roster row must be active); optional
  `IncludeAssignment`, `PairContext1/2/3`, and
  `AssignmentContext1/2/3`. Re-upload pattern for preview-then-save
  (no draft table). Blocking errors for unknown / inactive roster
  references and duplicates. See `docs/imports.md` for the
  pair-vs-assignment-context distinction.
- **`assignment_mode`** column on `sessions` records the strategy
  used; `Assignment.created_by_mode` records the same per row.
- **Delete all** assignments from the hub with explicit confirm.
  Reviewers and reviewees stay; `session.assignment_mode` clears
  back to `null`. Audit event `assignments.deleted_all`.

### Reviewer review surface

- **Identity matching**: an authenticated user is matched to
  `Reviewer` rows by case-insensitive email equality (`casefold()`
  both sides). Only `Reviewer` rows with `status == "active"` count.
- **Dashboard** at `/reviewer` lists the user's reviewer-sessions
  with per-session pill (`not started` / `in progress` /
  `submitted`) computed from the reviewer's `Response` rows.
- **Surface** at `/reviewer/sessions/{id}` renders an editable HTML
  table per instrument (today: N=1, the Default Instrument) with a
  section heading from `Instrument.description` (fallback to the
  system handle) and a per-field help block above the table for
  fields whose `help_text_visible` is true. Each table row is one
  non-excluded assignment (`include = true`); columns are reviewee
  identity (name + email_or_identifier, always-first, mandatory)
  followed by the instrument's visible `InstrumentDisplayField`
  rows (10B-1 — sourced from `pair_context_1/2/3` today; the
  10B-2 add-display-field route over `reviewee.tag_1/2/3` /
  `reviewee.profile_link` exists server-side but the 10C per-
  instrument card placeholder doesn't reach it yet), then the
  response-field inputs in stored order, then a row-level
  submitted-status indicator. Empty
  / NULL display-field labels fall back to inferred strings from
  the D6 helper. `profile_link` cells render as plain `<a href>`.
  `assignment_context_*` is deliberately excluded from the surface
  per the pair-vs-assignment-context distinction.
- **Save draft**: form post upserts `Response` rows. Empty value
  deletes the row, so the row's absence == empty answer. Never
  touches `submitted_at`.
- **Submit**: persists pending writes, then validates required
  fields. Missing-required-without-acknowledge re-renders the page
  at HTTP 400 with a warning card and an `acknowledge_missing`
  checkbox. Missing-required-with-acknowledge stamps `submitted_at`
  and writes audit. Editing a previously-submitted required field
  to empty deletes the row including its `submitted_at`, flipping
  the dashboard pill back to `in progress` next render.
- **Clear all**: confirm-checkbox-required action that deletes
  every `Response` row for this reviewer in this session. No
  partial undo; reviewers re-enter values from scratch afterward.
- **Cancel**: plain `<a>` link back to the surface; no DB write,
  no audit. Discards in-progress edits by re-fetching saved values.
- **Autosave is deferred** to a follow-on PR (vanilla JS layered
  over the same `/save` endpoint).
- **Lifecycle gating (Segment 9.1)**: reviewer save / submit / clear
  return **HTTP 403** unless the session is `ready`, the assigned
  instrument is `accepting_responses`, and `now() < session.deadline`.
  When the gate is closed, the surface renders read-only; saved values
  are hidden unless the operator turns on
  `responses_visible_when_closed` on the per-instrument sub-page.
  Deadline closure is observed lazily on every reviewer GET/POST and
  on the per-instrument operator page; the first observer flips
  `accepting_responses=false`, stamps `deadline_closed_at`, and emits
  one `instrument.closed reason=deadline` audit event.

### Audit log

Every destructive operation writes an `audit_events` row with
`event_type`, `summary`, JSON `detail`, and a per-request
`correlation_id`. As of 2026-05-07 (Segment 11K PR 1) new
`detail` writes follow the canonical envelope schema documented
in [`spec/architecture.md`](../spec/architecture.md) "Audit-event
detail schema"; the per-event-type sample shapes below are the
**legacy** shapes from before the cutover and remain accurate
for `audit_events` rows written before that date. PRs 2-7 of
Segment 11K migrate the emitters listed below to the canonical
envelopes; the legacy shapes will fall away one family at a
time as those PRs ship.

| event_type | When |
|---|---|
| `session.created` | new session |
| `session.updated` | edit form save (incl. `changes: {field: [old, new]}`) |
| `session.deleted` | session deletion (`session_id=None` in the row, original id in `detail`) |
| `reviewers.imported` | reviewer CSV save (incl. `cascaded_assignment_count`) |
| `reviewees.imported` | reviewee CSV save (incl. `cascaded_assignment_count`) |
| `reviewers.deleted_all` | delete-all from roster Manage view |
| `reviewees.deleted_all` | delete-all from roster Manage view |
| `assignments.generated` | FullMatrix or Manual save (incl. `mode`, `excluded_counts`) |
| `assignments.deleted_all` | delete-all from assignments hub |
| `responses.saved` | reviewer saves a draft (incl. `count`, `reviewer_id`) |
| `responses.submitted` | reviewer submits (incl. `count`, `missing_required_count`, `acknowledged_missing`) |
| `responses.cleared` | reviewer clears all their responses in a session |
| `responses.deleted_all` | operator-driven Delete Data on session detail (`detail.deleted_count`); allowed in any session status, including `ready` |
| `session.activated` | operator flips session draft→ready (`detail.override_warnings`) |
| `session.reverted_to_draft` | operator flips session ready→draft (`detail.closed_instrument_ids`, `response_count_at_revert`) |
| `session.invalidated` | operator flips session validated→draft (`detail.reason ∈ {"operator_revert", …}`); also auto-emitted by setup-mutating service code when the session was previously `validated` |
| `session.validated` | session marked validated on `?validated=1` when no blocking errors |
| `instrument.opened` | operator manually re-opens a closed instrument |
| `instrument.closed` | manual or lazy-deadline close (`detail.reason ∈ {manual, deadline}`) |
| `instrument.described` | operator edits the friendly description (`detail.description: [old, new]`) |
| `instrument.field_added` | operator adds a response field (`detail.field_key`, `label`, `response_type`, `required`, `validation`, `help_text`, `help_text_visible`) |
| `instrument.field_updated` | operator edits a response field (`detail.changes: {key: [old, new]}` for each changed key only) |
| `instrument.field_deleted` | operator deletes a response field (`detail.snapshot`, `cascaded_response_count`) |
| `instrument.fields_reordered` | up/down move OR bulk fields-save when response order changes (`detail.old_order`, `detail.new_order` as `field_key` lists; scoped to response fields) |
| `instrument.display_field_added` | operator adds a display field (`detail.source_type`, `source_field`, `label`, `order`, `visible`) |
| `instrument.display_field_updated` | operator edits a display field (`detail.changes: {key: [old, new]}` for each changed key only — `(source_type, source_field)` are immutable) |
| `instrument.display_field_deleted` | operator deletes a display field (`detail.snapshot`); no cascade since display fields have no per-row dependents |
| `instrument.display_fields_saved` | bulk fields-save when display rows' label / visibility / order changed (`detail.added` / `removed` always `[]` in 10B-2; `detail.updated` carries `[{source_type, source_field, changes: {key: [old, new]}}, …]`) |
| `instruments.bulk_accepting_responses` | bulk Open all / Close all (`detail.target`, `detail.changed_instrument_ids`); not duplicated as per-instrument open / close events |
| `instruments.bulk_visibility_when_closed` | bulk Show all / Don't show any (`detail.target`, `detail.changed_instrument_ids`); not duplicated as per-instrument visibility events |
| `instrument.created` | operator creates a new instrument via `/instruments/add` (`detail.instrument_id`, `detail.session_id`, `detail.order`, `detail.after_instrument_id`); UI button currently disabled, route active for when multi-instrument UI lifts |
| `instrument.deleted` | operator deletes an instrument via `/instruments/{id}/delete` (`detail.instrument_id`, `detail.session_id`, `detail.name`, `detail.order`); cascade to response fields / display fields / assignments / responses runs via FK delete-orphan |
| `invitations.generated` | bulk-create invitations on a ready session (`detail.count`, `detail.invitation_ids`, `detail.reviewer_ids`) |
| `invitation.sent` | outbox row written + invitation flipped to `sent` |
| `invitation.opened` | first valid token follow with matching email |
| `invitation.regenerated` | per-row token rotation + reset to `pending` |
| `reminders.sent` | batch reminder send (`detail.count`, `detail.invitation_ids`, `detail.reviewer_ids`, `detail.fell_back_count`) |

`excluded_counts` is a generic map (`{"self_review": N,
"inactive_reviewer": M, ...}`) so RuleBased exclusions in Segment 13 can
plug in additional reasons without a schema change. Today's keys are
`self_review`, `inactive_reviewer`, `inactive_reviewee`.

---

## What's deliberately not yet there

| Capability | Lands in |
|---|---|
| Edit individual reviewer / reviewee / assignment rows (today: bulk operations only via CSV replace or delete-all) | **Segment 15** (officially deferred 2026-05-03; tracked at `guide/unfinished_business.md` #25 — needs a design pass before code) |
| Operator UI to flip `Reviewer.status` / `Reviewee.status` to inactive (filter is defensive today) | **Segment 15** (officially deferred 2026-05-03 from Segment 11 Tier 3 §2.4; tracked at `guide/unfinished_business.md` #36) |
| Vanilla-JS autosave on top of the reviewer `/save` endpoint | **Segment 15** (officially deferred 2026-05-03; bundles into AG Grid #33's cell-edit lifecycle) |
| **Real SMTP email backend** (production sending, not the dev outbox) | **Segment 15** |
| Activating SMTP / Graph / ACS / third-party transactional sends out of the dev outbox; institutional Microsoft 365 tenants typically block basic SMTP AUTH, so the realistic production path is one of Options B–D in `spec/email_infra_options.md` | **Segment 14-1 Parts A → H** (Part A consumes the 11E `EmailTransport` interface against the audit-log columns Segment 11C Part 2 scaffolds, with subsequent Parts F → H landing each non-SMTP backend driven by deployment / IT demand) |
| **Export / audit retention** | **Segment 12** |
| **RuleBased assignment** | **Segment 13** |
| Multi-instrument sessions: FullMatrix per-instrument target picker, Manual CSV `Instrument` column, reviewer dashboard per-instrument grouping | Schema + reviewer-surface multi-instrument support shipped 2026-05-02 in Segment 10D Slice 5; the three remaining items are tracked at `guide/unfinished_business.md` #27 / #28 / #29 (Segment 13 plan archived as `guide/archive/segment_13_multi_instrument_sessions_superseded.md`) |
| **Production hardening** (Key Vault, VNet, soft-delete, full Postgres pytest matrix) | **Segment 14** |
| Local Postgres docker-compose for dev (SQLite + the `ci-postgres` job + migration-on-deploy is the parity story today) | **Segment 15** (officially deferred 2026-05-03; tracked at `guide/unfinished_business.md` #26 — likely settles "won't fix" via the developer setup guide work) |
| Sessions-list per-row Delete button posts directly (today: anchor link to `#danger-zone` on the session's Home page, where the operator confirms + clicks the real Delete) | **Segment 15** (officially deferred 2026-05-03; tracked at `guide/unfinished_business.md` #23 — small fix, bundles with whatever `/operator/sessions` UI work this segment touches) |
| Sort by reviewee on the reviewer surface — operator picks up to 3 default sort columns from the Display Fields table; reviewer can override at view time via clickable column headers (today: rows render in implicit insertion order) | **Segment 13** (promoted 2026-05-03 from Segment 11 §2.6 sketch; full design spec at `spec/sort_by_reviewee.md`; tracked at `guide/unfinished_business.md` #31) |
| Further refinement of the reviewer surface — catch-all for polish beyond the Segment 11 Tier 1 batch (PRs #319 → #324). Known sub-item: multi-instrument preview (`build_preview_context` extension explicitly deferred from Tier 1). Pilot-feedback-driven polish lands here too. | **Segment 15** (filed 2026-05-03; tracked at `guide/unfinished_business.md` #32) |
| AG Grid replacement of the reviewer-surface table (today: plain HTML `<input>` / `<textarea>` / `<select>` per cell, form-based save). Second half of workplan §11 that never landed; decided as still-on-roadmap 2026-05-03. | **Segment 15** (decided 2026-05-03 from Segment 11 Tier 2 §2.1; tracked at `guide/unfinished_business.md` #33) |
| Queue-based batch invitation sending (today: synchronous in-request loop over eligible reviewers; fine with the dev outbox, doesn't survive real SMTP latency + provider rate limits). Picks up workplan §12 work item #7. | **Segment 15** (decided 2026-05-03 from Segment 11 Tier 2 §2.3, bundled with real SMTP; tracked at `guide/unfinished_business.md` #34; depends on #6 shipping first) |
| Technical-support contact (global env var, surfaces on app chrome footer + error pages + invalid-link landing). Distinct from the operational help contact on `ReviewSession` (which lives in #24). | **Segment 15** (filed 2026-05-03 from Segment 11 Tier 2 §24 reframe; tracked at `guide/unfinished_business.md` #35) |

---

## Architectural notes worth preserving

### FullMatrix is a (future) RuleBased preset

FullMatrix and Manual currently have parallel implementations, but the
storage model treats them uniformly: every assignment is a row in
`assignments` with `created_by_mode` as a string discriminator and
`Assignment.context` as JSON. Segment 13 RuleBased is expected to
introduce a generic generation framework; FullMatrix becomes the
simplest preset of that framework. The audit-detail shape
(`excluded_counts: {...}`) is already generic; Manual rows ship with
`excluded_counts: {}`. The only friction is one specific service
function name (`generate_full_matrix`) and one preview template.

### Replace-all everywhere

All destructive ops (CSV imports + assignment generation) follow the
same shape: explicit confirm checkbox when rows already exist; audit
event records old count, new count, and any cascaded downstream
deletions. No append/merge for now — defer until activation
constraints make it necessary.

### Multi-instrument support

The data layer and the operator + reviewer surfaces are
multi-instrument-aware. Every session seeds one Instrument at
creation time via `ensure_default_instrument` (system handle
`Default`, operator-editable `description`, two seed response
fields, three seed `pair_context_1/2/3` display fields). The
schema columns (`Instrument.session_id`, `Instrument.order`,
`Assignment.instrument_id`) and the FK delete-orphan cascades are
in place; `create_instrument(after_instrument_id=…)` and
`delete_instrument(...)` exist as service helpers and emit the
`instrument.created` / `instrument.deleted` audit events; the
reviewer surface and the operator's `/instruments` page loop over
instruments; and the `Add an instrument` / `Delete this instrument`
operator buttons are wired (10D Slice 5, 2026-05-02) with mutual-
exclusion + single-instrument-floor gates. See
`spec/architecture.md` "Conceptual hierarchy."

The original Segment 13 plan (multi-instrument sessions) is
archived at
`guide/archive/segment_13_multi_instrument_sessions_superseded.md`
since most of its scope shipped early in Segments 10A → 10D. Three
items did not ship and live in `guide/unfinished_business.md` as
#27 (FullMatrix per-instrument target picker), #28 (Manual CSV
`Instrument` column), and #29 (reviewer dashboard per-instrument
grouping).

### Pair-level vs assignment-level context

Manual CSV imports carry two distinct kinds of per-pair context
(`pair_context_*` and `assignment_context_*`), both stored on
`Assignment.context`. Pair-level is reviewer-facing informational
metadata; assignment-level is logic-engaging metadata that
RuleBased (Segment 13) will read. See `docs/imports.md` and
`spec/architecture.md` "Pair-level vs assignment-level context."
