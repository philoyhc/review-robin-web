# Master todo sequence

The roadmap: what's shipped, what's coming up, and why that
order. The earlier `guide/archive/unfinished_business.md` catalog
retired 2026-05-10 once all of its open items were either
shipped or absorbed into named segments below — its content
lives at `guide/archive/unfinished_business.md` as a
historical reference for the Why / Where / Plan detail on
items closed pre-12B. Open items going forward are tracked
directly in this file's **Upcoming** section.

When a sub-segment plan exists (e.g.
`guide/archive/segment_11B_session_home.md`), that plan is
the day-to-day source of truth for its own slices; this file
references it without duplicating its PR ladder.

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

- **Segment 11D — #21b v2 sweep, non-session-centric pages** — done 2026-05-04. PRs **#407 (A) → #408 (B) → #409 (C)** plus follow-up refinements **#410 → #413**. PR A swept `sessions_list`, `session_new`, `about`, and `me_debug` onto `body.ui-v2` and landed the return-to-origin helper for detour destinations (`app/web/return_to.py`); PR B added the two-row session chrome to `session_edit` (with `current_page = ""` so no tab activates per "Sub-pages of Home") and made an initial run at the sessions-list lobby as a flex column of `.card.session-card` rows; PR C introduced the lighter reviewer top-bar variant via a new `{% block top_bar %}` in `base.html` plus `reviewer/_top_bar.html`, and swept the three reviewer templates onto `body.ui-v2 reviewer` with D5 status icons (`.status-icon-{complete,incomplete}`), D6 banners (`.banner.banner-{info,success,warning}`), and D7 page header. Post-11D follow-ups (#410–#413) reverted the lobby back to a v2 `<table>` inside a single `.card` and settled the column set at Session Name (link) / Session Code / Deadline (pill) / Created by / Created / Last Modified plus an unlabelled trailing column carrying an unwired select-row checkbox; retired the redundant Access button and the per-row Delete anchor; dropped the redundant `/about` link from the top-left chrome identity; and surfaced inline validation feedback in the Next Action card on Session Home when `?validated=1` fails on a draft session. Plan: `guide/archive/segment_11D_v2_sweep_non_session.md`. Catalog `guide/archive/unfinished_business.md` #21.

- **Segment 11L — Instrument friendly short label** — done 2026-05-04 (PR #429). New `Instrument.short_label String(32) | NULL` column + Setup-side editor on `/operator/sessions/{id}/instruments`. Two reviewer-side helpers (`views.page_button_label(instrument, position)` and `views.instrument_heading(instrument, position, total_count)`) ship inside Segment 11D follow-on PR γ. Plan: `guide/archive/segment_11L_instrument_short_label.md`.

- **Segment 11D follow-on — Reviewer surface, multi-instrument rewrite** — done 2026-05-05. The five planned PRs **#428 (α) → #430 (β) → #431 (γ) → #432 (δ) → #433 (ε)** landed in dependency order, then a polish stream **#434 → #448** swept the missing-required UX, the per-instrument intro grid + tinted help cards, the auto-seed-assignments-on-instrument-add behaviour, the missing-required Cancel-back-to-source-page link, the numeric-field journey (`type="number"` with `min`/`max` + `step="any"` + hidden spinners + `title` constraint hint + JS `setCustomValidity` step-grid popup with `1e-6` tolerance + server-side `validate_value` backstop in `responses.py`), and the per-instrument constraint summary line above each table (List rows omitted). Save / Submit flash banners retired in #441; missing-required moved to its own full-width 2-column `.rs-missing-card` and Submit became a hard gate (acknowledge-and-submit-anyway retired) in #436. New helpers: `views.placeholder_for_field`, `views.constraint_summary_for_field`. Plan: `guide/archive/segment_11D_v2_sweep_non_session.md` "Follow-on". Catalog `guide/archive/unfinished_business.md` #32 partial (general "further refinement" remains a Segment 15 catch-all).

- **Segment 11E — Operator-editable email template editor + SMTP scaffolding** — done 2026-05-07. Six PRs landed against the plan (PR 3 collapsed into PR 1 — the renderer wiring landed there; PR 7 absorbed into Segment 14B) plus one polish PR:
  - **PR 1 (#461)** — schema + service-layer renderer. `sessions.help_contact` (String 320, nullable) and `sessions.email_template_overrides` (JSON, nullable) columns; new `app/services/email_templates.py` rendering `string.Template.safe_substitute` over the canonical five-tag merge field set (`$reviewer_name` / `$session_name` / `$deadline` / `$help_contact` / `$invite_url`); `_email_body` / `_reminder_body` retire in favour of the new `render_invitation` / `render_reminder`. Help-contact also surfaces on the reviewer surface as a small "Questions? Contact X" line.
  - **PR 2-A (#462)** — placeholder cards on `/setupinvite`, framing the editor surface ahead of the actual editor.
  - **PR 4 (#463)** — operator Settings page at `/operator/settings`. Per-operator SMTP credentials (seven new columns on `users`); password encrypted at rest via `cryptography.fernet` keyed off the `SMTP_ENCRYPTION_KEY` env var; new `app/services/operator_settings.py` + `app/services/_secrets.py`; user-menu Settings link in the chrome.
  - **PR 5 (#464)** — `EmailTransport` Protocol + `EmailMessage` / `SendResult` dataclasses + concrete `SmtpEmailTransport` (`smtplib`, STARTTLS / implicit-SSL) + typed-stub `GraphEmailTransport` placeholder + `transport_for(settings)` factory. Nothing in the app calls this yet; first call site is **Segment 14B Part A**.
  - **PR 2 (#465)** — actual editor UI on `/setupinvite`. Two-card `.bottom-grid` layout: composer left, merge tags + Save / Cancel right. Per-template selection via `?template=` query. Per-field "Reset to default" forms; `email_template.updated` / `email_template.reset` audit events.
  - **#468** polish — Email Template + Settings button consistency: tabs out of card / normal-sized / flushed left, Save / Cancel at bottom-right of their card, no flash banners (Save disables until dirty), Settings page picks up `?return_to=` plumbing matching the About-page convention.
  - **PR 6 (#532)** — responses-received template editor (third tab). Adds the responses-received subject / body / cc / bcc keys to `email_template_overrides` plus a per-session `responses_received_enabled` bool flag (default `True`) the editor surfaces as a "Send this confirmation when a reviewer submits." checkbox. New `email_templates.render_responses_received(session, reviewer)` helper (drops `$invite_url`, adds `$submitted_at` resolved via `_latest_submitted_at` against the reviewer's responses) + `responses_received_enabled(session)` reader + `set_responses_received_enabled(session, enabled)` writer. Editor's right-card merge-tag list goes per-template via new `views.merge_tags_for_template(template)` helper. `views.EMAIL_PREVIEW_TABS` flips `is_shipped=True` on the responses_received entry — lights up the previously deferred Preview hub artifact card without needing a new registry seam.
  - Spec at `spec/email_infra_options.md` for the broader transport landscape (Options A–D: SMTP, Microsoft Graph application permission, Azure Communication Services, third-party transactional). The Graph stub will become Option B once the institution's IT conversation lands; the wiring lives in **Segment 14B**.
  - Plan: `guide/archive/segment_11E_email_template_editor.md`. Catalog `guide/archive/unfinished_business.md` #24 (closed by this segment). The submit-time send wiring (formerly planned as 11E PR 7) absorbed into **Segment 14B Part A** so all email *sending* lives on one segment regardless of which transport backend lights up.

- **Segment 11K — Audit-event `detail` schema convention** — done 2026-05-07. PRs **#544 (PR 1) → #545 (PR 2) → #546 (PR 3) → #547 (PR 4) → #548 (PR 5) → #549 (PR 6) → #550 (PR 7) → this PR (PR 8)**. Pins the canonical envelope schema for `AuditEvent.detail` and migrates every emitter in the codebase to it.
  - **PR 1 (#544)** — spec section in `spec/architecture.md` ("Audit-event detail schema") + typed envelope helpers (`audit.changes` / `.snapshot` / `.counts` / `.set_changes`) + new `write_event` kwargs (`session=` / `payload=` / `reason=` / `refs=` / `context=`) + session-lifecycle family migrated as proof.
  - **PRs 2–5 (#545 → #548)** — service-module sweeps: instruments (~18 emitters), invitations (6), responses (4), assignments (2). PR 5 introduced the `excluded_<reason>` flatten-into-counts pattern that lets 13A's RuleBased exclusions plug in without schema churn.
  - **PR 6 (#549)** — relocated `email_template.updated` / `.reset` from `routes_operator.py` into `app/services/email_templates.py::record_template_change` / `.record_template_reset` so PR 7 could sweep them with the rest of the settings family. Pure relocation; no shape change.
  - **PR 7 (#550)** — settings sweep: CSV imports (4), operator settings (2), email templates (2). Replaces the legacy `detail={}` on `operator_email_settings.cleared` with the canonical `detail=None`. Every emitter in the codebase now uses canonical shape.
  - **PR 8 (this PR)** — Pydantic write-validation gate. New `app/services/audit.py::EVENT_SCHEMAS` registry pins the allowed envelopes/slots per event_type; `validate_detail` runs in `write_event` after composition. `settings.audit_strict_mode` gates strict (raise) vs lenient (warn-and-write). `tests/conftest.py` flips strict on so CI catches drift. New `tests/unit/test_audit_detail_schema.py` covers the gate.
  - Closes catalog `guide/archive/unfinished_business.md` #5. Plan: `guide/archive/segment_11K_audit_event_detail_schema.md`. Spec: `spec/architecture.md` "Audit-event detail schema".

- **Segment 11C Part 2 — Outbox audit-log scaffolding** — done 2026-05-07. **PR #541** (PR F). Migration `c4f6a8b0d2e5` adds the seven nullable audit-log columns to `email_outbox` (`error_message`, `from_address`, `backend`, `backend_message_id`, `delivered_at`, `payload_hash`, `correlation_id`) + an index on `correlation_id` (the dispatch helper's idempotent-retry lookup key). `app/db/models/email_outbox.py` gains matching `Mapped[X | None]` declarations and the canonical value-set constants `EMAIL_OUTBOX_STATUSES = (queued, sending, sent, failed)` / `EMAIL_OUTBOX_KINDS = (invitation, reminder, responses_received)` so any future widening is a deliberate edit. Pure additive — all columns nullable, no defaults, no backfill, no service-layer reads or writes; today's enqueue paths continue to write only the existing columns. New tests at `tests/integration/test_email_outbox_schema.py`. The columns sit inert until **Segment 14B Part A** lights up the dispatch helper against this stable schema. Plan: `guide/archive/segment_11C_operations_consolidation.md` "Part 2".

- **Segment 11C Part 1 — Operations consolidation** — done 2026-05-06. PRs **#490 → #491 → #492 → #493**.
  - **#490** — chrome restored Outbox as a tab (later removed in #493).
  - **#491** — Manage Invitations (`/operator/sessions/{id}/invitations`) rewrite. Seven-column reviewer-centric table — Reviewer / Email Status / Email Sent / Review Progress / Required Fields / Last reminder / Action — absorbs the retired Monitoring page's reviewer-centric surface (per-reviewer progress, per-row reminders). New helper `views.build_invitations_rows` joins `monitoring.per_reviewer_progress` with a single batched outbox query for "latest invitation outbox row per reviewer". Reviewer drill-in scaffold at `.../invitations/{inv_id}/detail`. Outbox schema slice: Migration `b3d5e7f9a1c4` adds `email_outbox.cc_emails` / `bcc_emails` (Text); `send_invitation` / `send_reminder` populate them at queue time from the `email_template_overrides` JSON (new `email_templates.cc_bcc_for(session, kind)` helper). Columns sit unused at send time until Part 2.
  - **#492** — new Responses page (`/operator/sessions/{id}/responses`). Reviewee-centric coverage view; classifies each reviewee per a new `monitoring.AT_RISK_THRESHOLDS` constant (`adequate_fraction=0.5`) into Complete / Adequate / At risk / No responses. New helpers `monitoring.per_reviewee_coverage`, `views.build_responses_rows`. Reviewee drill-in scaffold at `.../responses/{reviewee_id}/detail`. Bulk reminder dispatch funnels through the same `POST /operator/sessions/{id}/invitations/remind-incomplete` endpoint Manage Invitations uses. Monitoring template + dedicated bulk-remind endpoint deleted; `GET /sessions/{id}/monitoring` 303-redirects to `/invitations` to preserve old bookmarks.
  - **#493** — drops Outbox from chrome (Operations row is now four tabs: Validate / Previews / Invitations / Responses). The Outbox page itself stays accessible via the "View outbox" button on Manage Invitations — it's a dev-diagnostic surface, not part of day-to-day Operations. Same PR styles the five Manage Invitations data cells as pills (`pill-count` for filled / good states, `pill-empty` for absent / not-yet states) so the table reads as a sparkline of state at a glance.
  - **Polish stream (#494 → #500).** Docs sync (#494); Responses table column rename + pill styling on `Reviewers completed` + `Last response` (#495); status-dropdown + name/email search filter strip on both pages closing the `spec/operations_pages.md` "Filtering" gap (#496) plus visual refinements — half-width filter card, side-by-side inputs, bottom-right Apply (#497); summary card + filter card paired side-by-side in `.bottom-grid` with new generic `.card-action-row` v2 primitive on Responses (#498) then Manage Invitations (#499); bulk **Regenerate all** secondary button + `invitations.regenerate_all_tokens` service helper + batch `invitations.regenerated` audit event (#500).
  - Test reorg: `tests/integration/test_monitoring.py` → `test_reminders.py`; new `test_segment_11c_pr3_responses.py`.
  - Plan: `guide/archive/segment_11C_operations_consolidation.md`. Functional spec: `spec/operations_pages.md`.

- **Segment 11H — Placeholder card scaffolds (Quick Setup + Extract Data)** — done. Both Session Home placeholder cards have shipped their inert-but-fully-rendered real shapes via the `_quick_setup_card.html` and `_extract_data_card.html` partials (included from `session_detail.html`), backed by the `QuickSetupSlot` / `QuickSetupContext` and `ExtractDataRow` / `ExtractDataContext` dataclasses + builder helpers in `app/web/views.py`. Every slot / row / button is laid out and accessible; every interactive control renders disabled (`is_wired=False`, `wire_url=None`) until the wiring segments. The Quick Setup card on `/operator/sessions/new` is also wired to the same scaffold via `build_new_session_quick_setup_context`. Plan: `guide/archive/segment_11H_placeholder_card_scaffolds.md`. Unblocks Segment 11J (Quick Setup wiring) and Segment 12A PR 6 (Configuration import slot graduation).

- **Segment 11J — Quick Setup wiring** — done 2026-05-07. PRs **#526 → #527 → #528**.
  - **#526** — plan revision. `guide/archive/segment_11J_quick_setup_card.md` rewritten to refocus on wiring the three "existing capability" slots (Reviewers / Reviewees / Assignments) and to unify the card's status-awareness model behind a single Lock / Unlock toggle that applies in every editable-conceivable lifecycle state, including `ready`. Slot 4 (Session settings, the configuration-import slot) explicitly carved out as a separate sub-plan and deferred to Segment 12A PR 6.
  - **#527 (PR A)** — Reviewers + Reviewees slots go live, plus the Lock / Unlock toggle wiring. New routes `POST /sessions/{id}/quick-setup/reviewers` / `.../reviewees` delegate to a thin `_handle_quick_setup_import` wrapper that reuses the same `parse / save / invalidate-if-validated` pipeline the per-entity Setup pages use. New `POST /sessions/{id}/quick-setup/lock` flips a per-session `HttpOnly` cookie (`qsu_{session_id}`, scoped to `/operator/sessions/{id}`) that the context-builder reads to decide `is_locked`. `views.cascade_message_for_replace` centralises the "this will replace N existing X (and clears M assignments)" copy. Status awareness collapses on a single signal — `is_locked` — and the body wrapper carries `.locked` greying by default in every editable-conceivable state; `.card.disabled` is retired in favour of body-greying, and `show_lock_toggle=True` on `ready` (visual unlock only — `_require_editable` stays the hard gate, with rejection surfacing as a scoped `banner-error` carrying the "Pause first" copy).
  - **#528 (PR B)** — Assignments slot goes live. New route `POST /sessions/{id}/quick-setup/assignments` auto-detects mode from the form payload: when `file` is attached and non-empty it runs the existing `parse_manual_csv` → `manual_rows_to_pairs` → `replace_assignments(mode=manual)` pipeline; otherwise it generates `full_matrix` from the stored rule via `generate_full_matrix` → `replace_assignments(mode=full_matrix)`. `exclude_self_review` honoured on both branches. Cascade banner reuses PR A's shape (banner-warning above the submit form, required confirm checkbox, Cancel + Confirm replacement); per spec assignments are leaf data so the cascade copy stops at "This will replace N existing assignments." with no further consequence to surface.
  - Slot 4 (Session settings / configuration-import) stays inert — graduates with Segment 12A PR 6, which flips `is_wired=False → True` and supplies `wire_url` against the seam 11H pinned. No markup or scaffold changes needed there.
  - New tests: `tests/integration/test_quick_setup_card.py` covers per-slot golden path, cookie-scoped lock toggle (round-trip + per-session isolation), cascade copy + helper unit-side, replace-confirmation flow, scoped parse-error / lifecycle-rejection / needs-confirm banners. Updated scaffold expectations in `tests/integration/test_quick_setup_scaffold.py` and `tests/integration/test_session_detail_restructure.py` for the unified pattern (toggle visible on `ready`, `.card.disabled` retired, all three live slots posting to their wire URLs).
  - Plan: `guide/archive/segment_11J_quick_setup_card.md`. Catalog `guide/archive/unfinished_business.md` #30 (closed by this segment, modulo slot 4 which carries forward into 12A).

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
preserves blame. Plan + slice-by-slice ranges: `guide/archive/major_refactor.md`.

- **`app/web/routes_operator.py`** (4,423 LOC, 79 routes) → `app/web/routes_operator/` with 10 feature-area sub-modules + `_shared.py`. PRs **#651 → #659** (1 package-conversion + 10 slice PRs). 2026-05-08.
- **`app/services/instruments.py`** (2,469 LOC, ~50 public functions, 5 concerns) → `app/services/instruments/` with `_state.py` / `_rtds.py` / `_display_fields.py` / `_response_fields.py` / `_instrument_crud.py`. PRs **#663 → #667** (§12.A). 2026-05-09.
- **`app/web/views.py`** (3,483 LOC, 79 builders / dataclasses) → `app/web/views/` with 10 page / entity sub-modules. PRs **#668 → #678** (§12.B). 2026-05-09.
- **Cross-cutting hygiene** (§12.C): public `csv_imports.decode_csv`, 14 inline imports lifted to module scope, new `app/services/_queries.py::session_scoped`. PRs **#680 → #682**. 2026-05-09.
- **`tests/integration/test_display_field_routes.py`** (2,167 LOC, 53 tests) split into 6 per-surface files + `_display_field_helpers.py` shared module. PR **#683** (§12.D). 2026-05-09.

### Segment 13D — DB prep for the library / per-session-copy split — done 2026-05-09 (PRs #696 → #702)

Pre-positions every additive, nullable, no-backfill schema change downstream feature segments need (15A, 15C, 15B; 13B / 13C ride-alongs). Mirrors how 11C Part 2 pre-positioned the seven `email_outbox` audit-log columns. **Every migration shipped inert** — no service or web code reads or writes the new shape until its owning feature segment lights it up. Plan: `guide/archive/segment_13D_db_prep.md`.

- **PR 0** (#696) — rename `rule_sets` → `operator_rule_sets` (Tier 1 table-name harmonisation; SQL only, Python class identifier `RuleSet` unchanged).
- **PR 1** (#697) — new `session_field_labels` table (15A friendly-label resolver).
- **PR 2** (#698) — new `session_rule_sets` snapshot table (15C per-session RuleSet copies).
- **PR 3** (#699) — new `operator_response_type_definitions` library table + `response_type_definitions.library_origin_id` provenance pointer (15C).
- **PR 4** (#700) — `instruments.rule_set_id` nullable FK → `session_rule_sets`, ON DELETE SET NULL (15B per-instrument selection).
- **PR 5** (#701) — `instruments.sort_display_fields` JSON column (13B sort spec).
- **PR 6** (#702) — `instruments.group_kind String(32)` column (13C group-scoped instruments).

### Segment 12A-1 — Session export (settings + per-entity CSVs + responses) — done 2026-05-09 (PRs #713, #716, #717, #718, #721)

Splits the umbrella "Segment 12A — Session settings import + export" into the export half (this segment) and the import half (12A-2 → 12A-3, both shipped 2026-05-10 — see the 12A-3 entry below). Ships **five CSV downloads** off the Extract Data card on Session Home — four serving the session-porting use case (Settings + Reviewers / Reviewees + Manual Assignments) plus the seeded-RuleSet audit-log fallback for pre-15B rule-based sessions, and a fifth (Responses) serving the independent **downstream-analysis** use case (Excel pivots, pandas groupby, BI tools). Plan: `guide/archive/segment_12A-1_export.md`.

- **PR 1** (#713) — Settings export + shared `extracts/` plumbing. New `app/services/session_config_io.py` with `serialize_session_config`; new `app/services/extracts/__init__.py` with `stream_csv` + `filename({code}_{kind}.csv)` helper; new `GET /operator/sessions/{id}/export/settings.csv` route in a new `_extracts.py` slice; `session.settings_extracted` audit event registered in `EVENT_SCHEMAS`. Settings row on the Extract Data card flips live. Tests: 14 unit + 6 integration.
- **PR 1a** (#716) — Capture seeded-RuleSet selection from the audit log. Pre-15B fallback in `_audit_log_rule_set_name` that fills `instruments[N].rule_set_name` cells from the latest `assignments.generated` audit row when the referenced `operator_rule_sets` row is a seed (`is_seed=True`). Memoised once per export so multi-instrument sessions hit the audit table once. Personal-library RuleSets intentionally out of scope (empty cell; destination operator picks on re-Generate). Post-15B precedence: populated `Instrument.rule_set_id` wins over the audit-log fallback. Tests: 6 new unit cases.
- **PR 2** (#717) — Reviewers + reviewees extracts. New `serialize_reviewers` + `serialize_reviewees` modules; routes `/export/reviewers.csv` and `/export/reviewees.csv`; `session.reviewers_extracted` + `session.reviewees_extracted` audit events. Column shapes match `parse_reviewer_csv` and `parse_reviewee_csv` (incl. `PhotoLink` not `ProfileLink`) so files round-trip with the upload flows on the Manage pages and Quick Setup. Both card rows flip live. Tests: 8 unit + 6 integration.
- **PR 3** (#718) — Manual assignments extract. New `serialize_assignments` raising `ManualOnlyError` on `assignment_mode != "manual"`; route `/export/assignments.csv` catches and returns 404; `session.assignments_extracted` audit event. Column shape `ReviewerEmail,RevieweeEmail,IncludeAssignment,Instrument` matches `parse_manual_csv`. Card row flips live on manual sessions; rule-based / full-matrix / unset sessions get a mode-specific tooltip. Multi-instrument N×M fanout; the importer collapses repeated pairs back into one Assignment per instrument on re-upload. Tests: 9 unit + 8 integration.
- **PR 4** (#721) — Responses extract (downstream-analysis use case). New `serialize_responses` that yields a 19-column wide CSV per `Response` row — denormalised reviewer + reviewee identity / tags, instrument context, field context, response-type name, value, and lifecycle (saved / submitted / version) so the file is readable in isolation. Streams through a `yield_per(1000)` cursor; route counts up front via `responses.session_response_count` so the audit event carries the row count without materialising the generator. `session.responses_extracted` audit event. Card row flips live with `{code}_responses.csv` filename. Empty-cell vs no-row semantics: null `Response.value` → empty `Value` cell with row preserved; missing-`Response` → no row. Tests: 9 unit + 5 integration.
- **PR 4a** — Add `SelfReview` column to the responses extract. Inserts a derived `TRUE` / `FALSE` cell between `Value` and `SavedAt` (HEADER goes 19 → 20 cols), computed via the canonical `is_self_review(reviewer, reviewee)` helper in `app/services/assignments.py` — case-insensitive `reviewer.email` vs `reviewee.email_or_identifier`, `FALSE` for non-email reviewee identifiers. Uppercase `TRUE` / `FALSE` (Excel idiom) — deliberate divergence from the lowercase booleans the assignments / settings CSVs use, since the responses CSV is analyst-tool-facing rather than round-trip-import-facing. Renames `_is_self_review` → `is_self_review` to expose the helper across module boundaries (3 internal call sites updated in lockstep). Tests: 4 new unit cases (TRUE / FALSE / case-insensitive / non-email identifier) + 1 integration assertion bump. No route, audit, or card changes.

Out of scope (deferred): zip bundle (mixed porting + analysis use case earns its own UX pass) and the Manual Assignments tile (retired in 12A-3 PR 2 — assignments are derived post-15D). The import side originally planned as 12A-2 was absorbed into 12A-3 and shipped 2026-05-10; plan archived at `guide/archive/segment_12A-2_import.md` as historical reference.

### Implementation sequence — `13E → 12C → 15D → 12A-3` (locked block, fully shipped 2026-05-10)

The four entries below are the operator-facing block locked
2026-05-10: self-review revamp + assignments revamp + matching
export / import updates as one coherent direction.

> **`13E → 12C → 15D → 12A-3`** is **fully shipped** as of
> 2026-05-10. 13E (schema prep), 12C-1 (self-review revamp),
> 15D (assignments revamp + Relationships page + chrome
> restructure), and 12A-3 (export / import updates for the
> post-15D shape) all merged. The locked block is closed.

12A-2 was absorbed into 12A-3; 12C-2 + 12C-3 were absorbed
into 15D. The Post-Segment 15 cleanup PRs (#760 → #769) walked
the freshly-shipped pages with the operator and applied
single-concern polish on top.

### Segment 13E — DB prep for the 12C / 15D block — done 2026-05-10 (PRs #743, #744)

Two inert schema migrations following the 13D playbook (additive, nullable / DEFAULT-shaped, no-backfill). Pre-positions the schema for 12C-1 (bulk Include toggle) and 15D (Relationships + per-pair attributes). Plan: `guide/archive/segment_13E_db_prep.md`.

- **PR 1** (#743) — `sessions.self_reviews_active` Boolean column, default `FALSE`. Lands inert; 12C-1 PR 1 is the first reader / writer.
- **PR 2** (#744) — new `relationships` table with `(session_id, reviewer_id, reviewee_id)` unique constraint, three `tag_N` slots, and `status` enum (`active` / `inactive`). Lands inert; 15D PR 1 is the first writer.

### Segment 12C-1 — Self-review revamp — done 2026-05-10 (PRs #745, #746, #747)

Three PRs wiring self-review behaviour against the 13E PR 1 column. The originally-planned 12C-2 + 12C-3 sub-segments were deferred under the holistic-sequence revision and absorbed into 15D. Plan: `guide/archive/segment_12C_self-review_revamp.md`.

- **PR 1** (#745) — `replace_assignments` consults `sessions.self_reviews_active` for self-review pairs when no explicit `includes` mapping is supplied. New `set_self_reviews_active` writer + `self_review_include_breakdown` reader.
- **PR 2** (#746) — Rule Builder card surfaces the `exclude_self_reviews` checkbox so it's editable per RuleSet rather than only at generate time.
- **PR 3** (#747) — full-matrix dead-code cleanup. Retires the standalone Full Matrix card / route — the seeded `Full Matrix` RuleSet covers the same case from inside the Rule Based Assignment card.

### Segment 15D — Assignments revamp — done 2026-05-10 (PRs #749 → #758)

The locked-sequence centrepiece. **Pair Context becomes Setup-primary** (new Relationships table + Setup page); **Assignments table becomes always-derived** (manual authoring retired); chrome restructure (Assignments moves from Setup to Operations); Quick Setup gets a Relationships slot; Rule Builder consumes `pair_context.tag_N`. Sized as 8 PRs (with PR 6 split into 6a / 6b and PR 7 split into 7a / 7b / 7c under post-12C codebase-check revisions; PR 8 carved out into Segment 15E). Plan: `guide/archive/segment_15D_assignments_revamp.md`.

- **PR 1** (#749) — `relationships` service + per-entity importer. New `app/services/relationships.py` with `parse_relationship_csv`, `save_relationships`, `delete_all_relationships`, `existing_count`, `list_for_session`, `pair_context_lookup`. Mirrors the reviewer / reviewee importer shape.
- **PR 2** (#750) — Relationships Setup page (`/operator/sessions/{id}/relationships`) + chrome integration. Slots into the Setup tab row between Reviewees and Instruments. Per-tag column-toggle UI mirrors the reviewer / reviewee preview-table shape.
- **PR 3** (#751) — `pair_context.tag_N` rule grammar + UI surface. New field-source class in `app/services/rules/fields.py`; Rule Builder picker exposes the three tags; predicates evaluate against the bound `pair_context_lookup`.
- **PR 4** (#752) — engine consumes `pair_context` via eager lookup. ContextVar-scoped `_pair_context_lookup` dict pre-built once per `engine.evaluate` call so the predicate evaluator dodges N×M re-queries.
- **PR 5** (#753) — Alembic data migration backfilling existing `Assignment.context.pair_context_*` JSON values into `relationships` rows. Lazy-seeding hook moves to `save_relationships`.
- **PR 6a** (#754) — Operations Assignments page + chrome restructure. Manual upload card retired; new bulk Include toggle for self-reviews; chrome row label moves from Setup to Operations.
- **PR 6b** (#755) — drop `Assignment.context` JSON column. Round-trip-friendly downgrade re-creates the column nullable. Pair-context readers rewritten to consult `relationships` directly.
- **PR 7a** (#756) — retire the legacy Quick Setup Assignments slot. Slot 3 (Rule-or-CSV) drops; the card collapses to one column awaiting PR 7c.
- **PR 7b** (#757) — dev-only docstring labels on the manual-CSV path. The route still exists (test fixtures need it) but is no longer reachable from the operator UI.
- **PR 7c** (#758) — re-introduce a Quick Setup Relationships slot at position 3. File-upload only; the chain is now Reviewers → Reviewees → Relationships → Settings.

### Post-Segment 15 clean up — done 2026-05-10 (PRs #760 → #769)

Small UI / behaviour polish on top of the freshly-shipped 15D. Each PR was a single-concern change driven by walking the new pages with the operator. Bundled here rather than carved into a new sub-segment because none of them needed planning beyond the one-sentence brief that triggered them.

- **#760** — Relationships page mirrors Reviewers / Reviewees: explanatory paragraph card replaced by a stats card (`Number of pairwise relationships: N` + `Fields with data:` pills); new `relationships.fields_with_data` helper.
- **#761** — Relationships info card collapses to a single line so count + pills sit side by side.
- **#762** — Setup status row drops the **Assignments:** slot. With 15D's "Assignments are derived" model, count + mode surface on the Operations Assignments page itself.
- **#763** — Assignments page layout polish: chrome moves Assignments between Validate and Previews (Validate · Assignments · Previews · Invitations · Responses); helping-info card retired; Rule Based card retitled **Assignment Rule** and lifted out of the wrapper card into a half-width slot in `.bottom-grid`; Self-reviews card sits half-width on the right; "Current pairs" → "Assignment pairs"; the third Ctx-toggle group label flips from "Pair" to "Relationship".
- **#764** — Assignment Rule subtitle: lowercase "relationship" to match the surrounding casing of "reviewer" / "reviewee".
- **#765** — Quick Setup card on Session Home + Create New Session now uses the two-column shape the CSS has always carried: Reviewers + Reviewees on the left, Relationships + Session settings on the right. Description copy gains "session settings" so the body matches the four slots.
- **#766** — Seeded RuleSets default `excludeSelfReviews` to **false** (was `true`). New migration `d92f4a710e88` flips `rule_set_revisions.exclude_self_reviews` for revisions belonging to seeds; Personal forks untouched. Operators reach self-review activation through the bulk Include toggle on the Operations Assignments page rather than forking a seed.
- **#767** — Rule Builder "+ New blank RuleSet" defaults to `exclude_self_reviews=false` to match the seed flip.
- **#768** — bookkeeping: archive shipped 13E / 12C-1 / 15D plans into `guide/archive/`; Done entries land in this file.
- **#769** — Reviewers / Reviewees / Relationships / Assignments preview tables: trailing `status` (or `Include`) cell renders as a `pill-info` (active / yes) or `pill-empty` (inactive / no) span so the column reads as a sparkline of state.

### Segment 12A-3 — Export / import updates for 15D — done 2026-05-10 (PRs #779, #780, #782, #783)

Last leg of the locked sequence `13E → 12C → 15D → 12A-3`. Brings the export / import surface into alignment with the post-15D session model: ships the Relationships per-entity export, retires the Assignments-CSV tile (assignments are derived post-15D, output not input), ships the Settings CSV importer (absorbed from 12A-2), and graduates Quick Setup slot 4 (Settings) to live. After this lands, an operator can round-trip a session end-to-end via the four porting CSVs (Reviewers · Reviewees · Relationships · Session settings) on a fresh session. Plan: `guide/archive/segment_12A-3_export_import_updates.md`.

- **#779** — PR 1 (Relationships export + Extract Data tile): `serialize_relationships()` extract service, `/export/relationships.csv` route, `session.relationships_extracted` audit event, new "Relationships" tile in the Extract Data card. The matching importer side (`parse_relationship_csv`, Manage page upload form, audit event) was already shipped by 15D PR 1.
- **#780** — PR 2 (Assignments-CSV retirement sweep): drops the Extract Data tile, `/export/assignments.csv` route, `assignments_extract.py` service, `session.assignments_extracted` registration, and the assignment-mode-aware count display end-to-end. Reorders the row list to lock in the target left/right column layout (Reviewers · Settings · Reviewees · Responses · Relationships · Zip-all). **Keeps** the seeded-RuleSet audit-log fallback in `session_config_io.py` — load-bearing for Settings CSV's `rule_set_name` capture pre-15B.
- **#782** — PR 3 (Settings importer + route): `apply_session_config(db, session, rows) -> ApplyResult` in `session_config_io.py` — the inverse of `serialize_session_config`. Two-phase parse + apply (validate every row first, then wipe-and-replace in a single transaction). `POST /operator/sessions/{id}/import-config` route with the lifecycle gate (`status in {"draft", "validated"}`). `session.settings_imported` audit event. Round-trip is byte-stable on the export's own output. Pre-15B `Instrument.rule_set_id` stays NULL; cross-row validation catches typo references.
- **#783** — PR 4 (Quick Setup Settings slot graduation): flips slot 4's `is_wired=True` and points it at PR 3's route. Submit-all chain on Session Home runs reviewers → reviewees → relationships → settings; the Create New Session POST handler dispatches the same per-slot pipeline when the operator stages uploads on the new-session form. `_run_quick_setup_settings` helper extracted so per-slot route, submit-all, and create-session share one pipeline.

#779 also folded in two round-trip stability fixes: `_datetime` formatter normalises naive readbacks to UTC (SQLite drops tzinfo, Postgres preserves it); the importer's RTD `data_type` validation accepts both the documented lowercase tokens and the model's capitalized values that today's export emits.

Bonus: **#781** — Grey out the Reviewers / Reviewees / Relationships / Responses Download buttons in the Extract Data card when the corresponding count is 0 (rendered between PR 2 and PR 3 as a small follow-on polish).

### Segment 16C — Richer audit views (MVP) — done 2026-05-11 (PRs #860, #861, #863)

Moves the audit log from "CSV download only" to a sys-admin-gated in-app viewer with filter strip + per-row pretty-printer. Reachable from the Sessions Diagnostics row's Audit log link (now points at the child page rather than the CSV directly). Plan archived: `guide/archive/segment_16C_richer_audit_views.md`. All three post-MVP PRs (4 + 5 + 6 — entity drill-in, cross-session search, Session Home Recent activity card) carved out to `guide/deferred_until_pilot_feedback.md`.

- **#860** — PR 1 per-session audit log child page. New `audit.list_events_for_session` reader + `views.build_audit_log_rows` view adapter (8-column projection mirroring the CSV exporter, keyset pagination on `id DESC`, default page size 50). Route `GET /operator/sys-admin/sessions/{id}/audit-log` in `_sys_admin.py`, gated `require_sys_admin`. Template `sys_admin_session_audit_log.html` with the Admin top-nav + back-link chrome conventions + Download CSV button. Sessions Diagnostics row's Audit log link migrates from `/operator/sessions/{id}/export/audit_log.csv` (direct CSV download) to the new child page. CSV route gate tightens from `require_sys_admin_or_session_operator` to `require_sys_admin` since the operator-facing entry point retired with 12B PR 2 → 16A PR 4; existing relaxed-gate test in `test_outbox_sys_admin_relax.py` reshaped accordingly.
- **#861** — PR 2 filter strip + filtered CSV download. New `AuditFilters` dataclass + shared `_apply_filters` helper composing event-type / severity / actor-email / date-range predicates onto both the viewer and the CSV serializer. URL-param state: `?event_type=` (multi), `?severity=` (multi), `?actor=`, `?from=`, `?to=`. `views.parse_audit_log_filters` + `build_audit_log_filter_form` + `filters_querystring` (stable encoding for pagination + CSV link carry-over). Filter-aware Download CSV button rewrites to embed the active filter query string. `session.audit_log_extracted` audit event grows a `context` slot recording the active filter set on filtered extracts (scalar-only values per the canonical envelope; multi-value slots flatten to comma-joined strings). Layout follow-on commit constrains the table layout (`table-layout: fixed`, per-column widths, `overflow-wrap: anywhere`) so the JSON detail column wraps rather than horizontally bloating; new `{% block extra_head %}` slot in `base.html` so per-page `<style>` rules don't have to ride inside the body.
- **#863** — PR 3 per-row `<details>` expander + per-shape detail pretty-printer. New `views.format_audit_detail` view adapter mapping each canonical envelope into structured sections: `changes` → before/after rows, `snapshot` / `counts` / `refs` / `context` → sorted-keys `<dl>`, `set_changes` → added/removed/updated pill lists, `reason` → free text, unknown keys (legacy pre-11K detail) → "Other" fallback. Raw JSON sits in a nested `<details>` for inspection.

30 new integration tests in `test_sys_admin_audit_log.py` plus 4 reshaped in `test_extracts_audit_log_route.py`.

---

### Segment 16B PR 2 — Per-session owner management — done 2026-05-11 (PRs #853, #854, #855)

Per-session owner management ships on the Session Edit page (`/operator/sessions/{id}/edit`), with the operator allowlist + sys-admin chrome from Segment 16A already in place. The original 16B plan had PR 1 (service) and PR 2 (UI) as separate slices; they landed as a single PR (#853) since the service surface is small and the UI is a thin wrapper. PR 3 (per-session role granularity beyond binary owner) was retired from the roadmap 2026-05-11 — binary owner-or-not is the deliberate final shape. Plan archived: `guide/archive/segment_16B_role_delegation.md`.

- **#853** — Owners section on the Session Edit page. New `app/services/session_owners.py` with `list_owners` / `workspace_operator_candidates` / `add_owner` / `remove_owner` + `OwnerOperationError` (codes: `last_owner`, `not_in_workspace`, `already_owner`, `not_owner`). New audit events `session.owner_added` / `session.owner_removed` registered in `EVENT_SCHEMAS` (snapshot + refs envelope, `refs.target_user_id` for the target). New routes `POST /sessions/{id}/owners/add` (form takes `target_email`, case-insensitive email lookup) and `POST /sessions/{id}/owners/{user_id}/remove`. `GET /edit` + `POST /edit` + the two owner routes share `require_sys_admin_or_session_operator` — a relaxed gate that lets a sys-admin reach the edit page of a session they don't own (they self-add as owner via the Add-owner form, then act on the session via the normal `require_session_operator` path). Sessions Diagnostics row's "Operators" placeholder retires; "Details" link to `/edit` replaces it. **Scope deltas from the plan:** surface placement moved from Session Home to the Edit page (closer to other session-identity edits); the picker submits `target_email` rather than `target_user_id` so the form is robust to typos / unlisted entries.
- **#854** — Race fix on last-owner remove. Codex review flagged a TOCTOU between count + delete (two concurrent removes could both read `count == 2`, both pass the guard, each delete one row → zero owners). Replaced with `SELECT ... FOR UPDATE` over the session's `session_operators` rows, then count + locate + delete from the locked snapshot. Postgres enforces row-level locking; SQLite ignores `FOR UPDATE` silently (fine for the in-process test suite).
- **#855** — Chrome polish: `(sys admin)` suffix on the top-right "Signed in as ..." label for users with `is_sys_admin` so they can tell at a glance that they're running with elevated workspace privileges; applied to both `base.html` (operator chrome) and `reviewer/_top_bar.html`. `request_access.html` skipped (its `AuthenticatedUser` shape has no `is_sys_admin`, and a user awaiting workspace admission can't be a sys-admin anyway).

---

### Segment 16A — Sys Admin page + workspace user/role management — done 2026-05-10 → 2026-05-11 (PRs #834 → #852)

All six planned PRs shipped (PRs #834 / #841 / #844 / #845 / #851 / #852), plus a handful of follow-on reshape + polish PRs (#835 / #836 / #837 / #838 / #839 / #840 / #842 / #843 / #846 / #847 / #848 / #849 / #850). The "Option C strict-allowlist" access model locks in: `users.is_operator` + `users.is_sys_admin` Boolean columns (13F PR 2 + PR 4) gate the operator surface; `OPERATOR_EMAILS` + `SYS_ADMIN_EMAILS` env vars seed both at user-create time. The Sys Admin chrome lives at workspace level under `/operator/sys-admin/*` and surfaces Sessions Diagnostics + Accounts Management tabs. Plan archived: `guide/archive/segment_16A_sys_admin_page.md`.

- **#834 — PR 1a (Operator-allowlist gate)** Foundation: `operator_emails` / `sys_admin_emails` / `operator_contact_email` in `app/config.py`; `get_or_create_user` reads both at user-create time and sets `users.is_operator` / `users.is_sys_admin` accordingly; `require_operator` dependency redirects denied users to `/request-access` via `OperatorAllowlistDenied`; new `request_access.html` renders the contact + mailto + sign-out chrome.
- **#835 — PR 1b (apply the gate)** Applies `require_operator` to the operator router so every `/operator/*` route except `/request-access` is gated.
- **#836 — PR 1c (fake-auth defaults)** Defaults `FAKE_AUTH_OPERATOR` + `FAKE_AUTH_SYS_ADMIN` to `True` for the local dev loop so the sandbox doesn't blackhole every test request behind the gate.
- **#837 / #838 / #839 / #840 — env / docs polish** `.env.example` seeds `OPERATOR_EMAILS` + `SYS_ADMIN_EMAILS`; pydantic list-parse fix for the comma-separated env-var form; `docs/deployment_dev.md` records the first-deploy allowlist bootstrap gotcha + the pre-existing-row backfill story.
- **#841 — PR 2 (Sys-admin gate + chrome scaffold)** `require_sys_admin` dependency + workspace-level `/operator/sys-admin` route + "Admin" link in the chrome user-card (visible only when `is_sys_admin`, self-suppresses on `/sys-admin` paths, carries `?return_to=`).
- **#842 — PR 2b (reshape to workspace-level)** Original PR 2 attempted a per-session sys-admin chrome variant; reverted to workspace-level only so the Admin doorway lands on a workspace dashboard rather than threading into per-session chrome.
- **#843 — plan: chrome + session-table picker** Plan-only PR; documents the Sessions Diagnostics + Accounts Management tab structure.
- **#844 — PR 3 (Sessions Diagnostics tab + Outbox per-row links)** Workspace Sessions Diagnostics page at `/operator/sys-admin/sessions` lists every session in the workspace. Per-row links to Outbox + audit log. `sys_admin_top_nav.html` partial. Root `/operator/sys-admin` 303-redirects to `/sessions`. **Scope delta from plan:** per-session Outbox route was retired entirely (not relaxed). Old bookmark URLs 404.
- **#845 — PR 4 (Sessions Diagnostics columns + audit log + relax)** Audit log per-row link wired to the existing `/export/audit_log.csv` route. New `require_sys_admin_or_session_operator` dependency (`app/web/deps.py`) gates the audit-log CSV route so a sys-admin who isn't a session operator can still pull the log. Sessions Diagnostics column set landed.
- **#846 → #847 — Outbox UX iteration** PR #846 first surfaced the Outbox inline on the Admin Sessions Diagnostics page with an inline Status pill; PR #847 then split it onto a child page under Sessions Diagnostics (`/operator/sys-admin/sessions/{id}/outbox`) for a cleaner two-level hierarchy.
- **#848 — Status pill lifecycle color** Sessions Diagnostics Status pill picks up the same lifecycle-tinted variants the per-session chrome status row uses.
- **#849 / #850 — Sessions lobby Status column** New Status column on the operator Sessions lobby table; spec sync in `spec/sessions_overview.md`.
- **#851 — PR 5 (Retire manual-assignment upload)** `parse_manual_csv` / `manual_rows_to_pairs` / `ManualAssignmentRow` / `AssignmentMode.manual` enum variant all removed. `AssignmentMode` enum kept with `rule_based` as the only value. Cleanest possible deletion sweep — the dev-diagnostic-only manual upload path bowed out once 15D's rule-based engine became the only operator-facing assignment path.
- **#852 — PR 6 (Accounts Management tab + workspace user toggles)** New `app/services/users.py` (259 LOC) ships `list_workspace_users`, `admit`, `revoke`, `promote`, `demote` (+ bonus `invite`). Per-row POST routes on `/operator/sys-admin/users` with per-toggle `confirm` checkbox guard on promote/demote (400 if missing) and a last-admin 409 guard. Four canonical audit events (`workspace.operator_admitted`, `workspace.operator_revoked`, `sys_admin.role_promoted`, `sys_admin.role_demoted`) registered in `EVENT_SCHEMAS`. Workspace user list with per-row toggles ships the workspace-level admit/revoke/promote/demote affordances that 16B PR 2's per-session Owners picker assumes.

**Scope deltas worth flagging:**

- Outbox per-session route retired entirely (PR 3) rather than relaxed; old bookmark URLs 404. Documented in-flight reshape.
- `sys_admin.outbox_viewed` audit event not emitted — plan called it optional ("lean skip").
- PR 6 adds an "Invite by email" form + `users.invite` service — bonus over the strict plan, sensible companion to admit/revoke.
- **Undocumented:** the actor-owner check in `session_owners.add_owner` / `remove_owner` (16B PR 2) lives at the route layer (`require_sys_admin_or_session_operator`), not in the service. Defensible (the relaxed gate intentionally lets sys-admins act without owning the session), but worth recording — file under "16B PR 2 scope deltas" if pilot feedback wants service-level enforcement instead.

---

### Segment 12B — Audit-events export — done 2026-05-10 (PRs #788, #789)

Smallest possible slice — adds a per-session `audit_events` CSV download. The original Segment 12 framing (response-data export + retention) was already covered by 12A-1 / 12A-3, so 12B reduced to a single PR for the audit log. Plan archived: `guide/archive/segment_12B_audit_retention.md`.

- **#788** — PR 1 (Audit-events extract + Extract Data tile): new `app/services/extracts/audit_events_extract.py` with `serialize_audit_events()` (8-column wide CSV: `EventType,Severity,Summary,ActorEmail,CorrelationId,CreatedAt,DetailJson`, JSON-encoded detail envelope via `json.dumps(..., sort_keys=True)`, LEFT JOIN against `users` for ActorEmail, streamed via `yield_per(1000)`); `session.audit_log_extracted` registered in `EVENT_SCHEMAS`; `GET /operator/sessions/{id}/export/audit_log.csv` route in `_extracts.py`; new "Audit log" tile in `_extract_data.py` between Relationships and the inert Zip-all bundle. Naive-datetime readbacks normalised to UTC so the cell shape is dialect-stable.
- **#789** — Move audit log out of Extract Data → flag for Sys Admin. Per industry best practice (GitHub, Stripe, Slack, Notion, Atlassian) audit data sits behind an admin / diagnostics doorway rather than alongside everyday data exports. The route + service + audit event + tests stay live; the Extract Data tile retires so the surface relocates cleanly to the Sys Admin page when Segment 16A ships. Segment 16A stub upgraded audit log download from "Future" to a planned **Anchor item §3** alongside Outbox and Manual assignment upload.

---

## Upcoming

Each item below has a detailed plan in its own doc; entries
here are 1-3 lines for at-a-glance sequencing. Catalog-item
refs (e.g. "Catalog #33") point at the historical
`guide/archive/unfinished_business.md` numbering for items
that originated there before the catalog retired.

### Implementation sequence

The locked block `13E → 12C → 15D → 12A-3` shipped 2026-05-10
(see Done above for the four entries) and 12B (audit-events
export) followed the same day. **Segments 16A** (Sys Admin
page + workspace user/role management) and **16B PR 1 + PR 2**
(per-session owner management) shipped 2026-05-10 → 2026-05-11,
absorbing the audit-log download route 12B left UI-less,
retiring the dev-only manual assignment upload, and standing
up the operator-allowlist gate + workspace Accounts
Management surface. **Segment 16C** (richer in-app audit views) MVP shipped 2026-05-11 the same day; the post-MVP polish (entity drill-in + cross-session search) carved out to `guide/deferred_until_pilot_feedback.md`. The remaining schedule items —
13B, 13C, 13F, 14A, 14B, 14C, 15A, 15B, 15C, 15E, 15F, 17, 18A, 18B, 18C, 19, 20 — ship per
their own plan; no ordering constraints beyond shared schema
conflicts (none detected).

#### Numbered queue

1. **13B — Reviewer surface sort.**
   Sort-by-reviewee column on the reviewer surface — operator
   default + reviewer live override. Sized as 3 PRs (schema +
   read path → operator UI tri-state Sort column → reviewer-
   side live override). Independent of 13A and 13C; ships in
   any order.
   **Plan:** `guide/segment_13B_sort_tables.md`.
   **Functional spec:** `spec/sort_by_reviewee.md`.

2. **13C — Enhanced instruments.**
   Group-scoped instruments (per-instrument flavour where one
   answer covers a group of reviewees) + a "Duplicate
   instrument" action-row button. Sized as 5 PRs. Action row
   ends up with: Edit / Save / Cancel (state-aware) + Add new
   instrument + Add group-scoped instrument (new) + Duplicate
   instrument (new). No `Response` schema change. **Note**
   (post-15D): the original plan stamped per-instrument flavour
   metadata onto the now-dropped `Assignment.context` JSON
   column; that stash will need to relocate (likely onto the
   `relationships` row or onto a new per-instrument column on
   `assignments`) — flag for the 13C plan revision.
   Independent of 13A and 13B.
   **Plan:** `guide/segment_13C_enhanced_instrument.md`.
   **Functional spec:** `spec/group_scoped_instruments.md`.

3. **14A — Production hardening.**
   Observability, security, support runbooks, real-pilot prep.
   Catalog #26 (local Postgres docker-compose for dev).
   **Plan:** `guide/segment_14A_production_hardening.md`.

4. **14B — Email infrastructure (send activation + backends).**
   *(Renamed from 14-1 on 2026-05-11 as part of the 14 → 14A /
   14B / 14C split.)* All email *wiring* lives here. The schema
   columns Part A writes to landed with **Segment 11C Part 2**
   (PR #541, 2026-05-07) and are ready for the dispatch helper.
   - **Parts A → E** (sequential): SMTP send activation →
     `correlation_id` strategy → bulk-send queue + worker →
     per-deployment from-identity defaults → generalised
     Outbox diagnostic surface.
   - **Parts F → H** (independent backend swaps): Option B
     (Microsoft Graph), Option C (Azure Communication Services),
     Option D (third-party transactional). Ship as deployment
     demand dictates.

   Catalog #34 (queue-based batch invitation sending — Part C).
   **Plan:** `guide/segment_14B_email_infrastructure.md`.
   **Functional spec:** `spec/email_infra_options.md`.

5. **14C — Reminders workflow.**
   Scheduled, policy-driven reminder dispatch sitting on top
   of 14B's transport. Per-session cadence settings + a
   background scheduler + post-MVP cohort slicing + reminder
   analytics. Stub-state plan; hard-deps on 14B Parts A / B
   (and reuses 14B Part C's worker scaffold if available).
   **Plan:** `guide/segment_14C_reminders_workflow.md`.

6. **15A — Pervasive friendly labels.**
   Operator-renamable `ReviewerTag1-3` / `RevieweeTag1-3` /
   `PairContext1-3` flowing through every header / picker /
   tooltip via a session-level resolver, not just per-instrument
   Display Field rows. New `session_field_labels` table +
   `app/services/field_labels.py` resolver + Settings-page
   editor. ~3-4 PRs. Lands cleanly any time after the major
   refactor; recommended **before 15B** so 15B's per-instrument
   UI consumes the resolver instead of re-introducing hardcoded
   literals. (The originally-planned `AssignmentContext1-3`
   slot retired with `Assignment.context` in 15D PR 6b.)
   **Plan:** `guide/segment_15A_friendly_labels.md`.

7. **15C — Operator RTD / RuleSet libraries.**
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

8. **15B — Per-instrument assignments.**
    Each `Instrument` carries its own assignment set (e.g. the
    Manager survey collects different reviewer → reviewee
    pairings than the Peer survey within one session). Schema
    already supports this — `Assignment` carries `instrument_id`
    with a `(session_id, reviewer_id, reviewee_id, instrument_id)`
    unique constraint — but `replace_assignments` fans out
    uniformly today. Post-15D the per-instrument hook is
    `instruments.rule_set_id` (the FK landed inert in 13D PR 4)
    pointing at a `session_rule_sets` row that 15C populates.
    Slices: per-instrument service scope, persist per-instrument
    rule-set selection, per-instrument Assignments page UI,
    Quick Setup selector, per-instrument validation. ~5-7 PRs.
    Recommended after 15C. (Manual-CSV `Instrument` column
    catalog item #28 is moot post-15D; manual-row authoring
    retired.)
    **Plan:** `guide/segment_15B_per_instrument_assignments.md`.

#### Stubs

- **13F — More DB prep (14C / 16A / 16B / 18B / 18C
  ride-along)** *(in flight — **PRs 1 + 2 shipped 2026-05-11**;
  PRs 3-5 deferred until consumer segments)*. Mirrors the
  13D / 13E inert-migrations pattern for the **next** batch
  of schema needs identified during the Segment 16 PR-ladder
  sizing pass. Reordered 2026-05-11 so the 16-series work
  leads: **PR 1 (shipped)** — `users.is_sys_admin` Boolean
  + model-only `session_operators.role` value-set lock and
  Python-default fix; **PR 2 (shipped)** — `users.is_operator`
  Boolean for Option C strict-allowlist access (16A PR 1
  reads it). PRs 3-5 (`session_tags`,
  `sessions.reminder_settings`,
  `sessions.retention_exception` + `retention_overrides`)
  ride with their consumer segments (18B / 14C / 18C) when
  those segments are picked up. **The 16-series schema
  scaffolding is now complete — Segment 16A is unblocked.**
  **Plan:** `guide/segment_13F_more_db_prep.md`.

- **15E — Next Action revamp + multi-step shortcuts**
  *(carved out of 15D PR 8, 2026-05-10)*. Promotes the
  Next Action card on Session Home to drive Validate →
  Generate → Activate as one-click "super button"
  chains, with single-step actions retained for granular
  flows. Stub-state plan; ready for sizing now that the
  locked block is closed.
  **Plan:** `guide/segment_15E_next_action_revamp.md`.

- **15F — Enhanced Setup pages** *(carved out of the
  original Segment 15, 2026-05-10)*. Per-row inline edit +
  Inactivate / Reactivate affordances on the Reviewers /
  Reviewees / Relationships Manage pages. Today's only
  per-row edit path is CSV bulk-replace; 15F adds the
  single-row affordance so operators don't have to round-
  trip a CSV to fix one name or toggle one status.
  **Plan:** `guide/segment_15F_enhanced_setup_pages.md`.

- **17 — AG Grid replacement of the reviewer-surface table**
  *(carved out of the original Segment 15, 2026-05-10)*.
  Replaces the plain HTML `<input>` / `<textarea>` /
  `<select>` reviewer-surface table with an AG Grid
  instance backed by the existing render adapter +
  `POST /save` endpoint. Unlocks cell-level autosave +
  large-table ergonomics.
  **Plan:** `guide/segment_17_ag_grid_replacement.md`.

- **18A — Session cloning** *(stub created 2026-05-11)*.
  One-click clone of an existing session's setup
  (reviewers / reviewees / relationships / instruments /
  RTDs / RuleSets / email-template overrides / settings)
  into a new session, without carrying responses, audit
  history, or runtime state. Closes the §22 acceptance
  criterion "Session cloning". Lands more cleanly after
  15C (library auto-copy precedent) and 15B (per-instrument
  RuleSet pointers).
  **Plan:** `guide/segment_18A_session_cloning.md`.

- **18B — Session tagging and archiving** *(stub created
  2026-05-11)*. Free-form per-session tags surfaced as
  filterable chips on the Sessions lobby + the
  `closed → archived` lifecycle transition that lights up
  the reserved `archived` state from `spec/lifecycle.md`.
  Independent of 18A / 18C.
  **Plan:** `guide/segment_18B_session_tagging_archiving.md`.

- **18C — Retention / deletion workflow** *(stub created
  2026-05-11)*. Per-session selective purge (responses /
  audit log / rosters) + per-deployment retention policy
  enforced by a scheduled job. Closes the §21 #16
  acceptance criterion "Basic retention/deletion workflow"
  + the §22 row "Advanced retention policies". Reuses
  14B Part C's worker scaffold if available; sys-admin
  surface gated by 16A.
  **Plan:** `guide/segment_18C_retention_deletion.md`.

- **19 — Spec documentation** *(stub created 2026-05-11)*.
  Periodic spec-hygiene sweeps on `spec/` — initial
  coverage-gap closure for Tier-1 specs flagged in
  `guide/spec_sweep_11may.md` (Email Template editor,
  Permissions), plus a recurring cadence template.
  Distinct from Segment 20 which produces operator- +
  developer-facing prose in `docs/`.
  **Plan:** `guide/segment_19_spec_documentation.md`.

- **20 — Operator polish + documentation** *(renumbered
  from the original Segment 15, 2026-05-10)*. The
  documentation pass + technical-support contact item
  the original Segment 15 stub bundled. Runs after
  Segment 14A (production hardening) so the system is
  operationally credible before the documentation is
  written for it. Workplan §18 items 1–10 (Start Here
  page through Known limitations page).
  **Plan:** `guide/segment_20_operator_polish_and_documentation.md`.

#### Historical-reference entries

These plan docs are archived alongside the segment they were
folded into; they stay reachable as references for the contracts
they pinned:

- **12A-2 — Session settings import** — absorbed into 12A-3 under
  the 2026-05-10 holistic-sequence revision; the import service +
  route + Quick Setup slot 4 graduation all landed in 12A-3 PRs.
  Plan: `guide/archive/segment_12A-2_import.md`.
- **12C-2 / 12C-3** — absorbed into 15D under the same revision.
  No standalone plan file; original scope (Quick Setup slot 3
  retire-and-restore, chrome restructure, Operations Assignments
  page move) shipped as part of 15D PRs 6a / 7a / 7c.

### Sequencing notes

- **13E → 12C → 15D → 12A-3** was the locked
  operator-facing block (locked 2026-05-10, fully
  shipped 2026-05-10): self-review revamp + assignments
  revamp + matching export / import updates as one
  coherent direction. **All four segments shipped**
  (see Done above). 13E shipped the schema prep inert;
  12C-1 wired generation against the new column; 15D
  added Relationships + restructured Quick Setup +
  chrome + dropped `Assignment.context`; 12A-3 brought
  Extract Data + Quick Setup into alignment with the
  post-15D model (Relationships export, Assignments-CSV
  retirement, Settings importer, Quick Setup slot 4
  graduation). 12A-2 was absorbed into 12A-3; 12C-2 +
  12C-3 were absorbed into 15D.
- **11C Part 2 → 14B Part A** is the email pipeline: 11C Part 2
  landed the schema (Migration `c4f6a8b0d2e5`, 2026-05-07); 14B
  Part A is the first writer.
- **11K → 12B** is the audit pipeline: 11K pinned the `detail`
  shape (shipped 2026-05-07); 12B's export reads against it.
- **12A is fully shipped** as of 2026-05-10 (12A-1 export +
  12A-3 export-refresh + Settings importer + Quick Setup
  slot 4 graduation; 12A-2 was absorbed into 12A-3). The
  remaining schedule items — **13B, 13C, 13F, 14A, 14B, 14C, 15A,
  15B, 15C, 15E, 15F, 17, 18A, 18B, 18C, 19, 20** — are independent of the email +
  audit pipelines and can interleave at any time. The three
  13-family segments are also independent of each other;
  13C PR 3 (rule-engine fanout for group-scoped instruments)
  lands more naturally after 13A's RuleSet machinery exists,
  but 13C PRs 1 / 2 / 4 / 5 don't depend on 13A.
- **Within 14B**, Parts B-E are sequential enhancements on top
  of Part A; Parts F-H are independent backend swaps. **14C
  reminders workflow** layers on top of 14B Parts A / B / C and
  ships on its own pace.
