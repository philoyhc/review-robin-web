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

- **Segment 11E — Operator-editable email template editor + SMTP scaffolding** — done 2026-05-05. Five PRs landed against the plan (PR 3 collapsed into PR 1 — the renderer wiring landed there) plus one polish PR:
  - **PR 1 (#461)** — schema + service-layer renderer. `sessions.help_contact` (String 320, nullable) and `sessions.email_template_overrides` (JSON, nullable) columns; new `app/services/email_templates.py` rendering `string.Template.safe_substitute` over the canonical five-tag merge field set (`$reviewer_name` / `$session_name` / `$deadline` / `$help_contact` / `$invite_url`); `_email_body` / `_reminder_body` retire in favour of the new `render_invitation` / `render_reminder`. Help-contact also surfaces on the reviewer surface as a small "Questions? Contact X" line.
  - **PR 2-A (#462)** — placeholder cards on `/setupinvite`, framing the editor surface ahead of the actual editor.
  - **PR 4 (#463)** — operator Settings page at `/operator/settings`. Per-operator SMTP credentials (seven new columns on `users`); password encrypted at rest via `cryptography.fernet` keyed off the `SMTP_ENCRYPTION_KEY` env var; new `app/services/operator_settings.py` + `app/services/_secrets.py`; user-menu Settings link in the chrome.
  - **PR 5 (#464)** — `EmailTransport` Protocol + `EmailMessage` / `SendResult` dataclasses + concrete `SmtpEmailTransport` (`smtplib`, STARTTLS / implicit-SSL) + typed-stub `GraphEmailTransport` placeholder + `transport_for(settings)` factory. Nothing in the app calls this yet; first call site is Segment 11C Part 2.
  - **PR 2 (#465)** — actual editor UI on `/setupinvite`. Two-card `.bottom-grid` layout: composer left, merge tags + Save / Cancel right. Per-template (Invitation / Reminder) selection via `?template=` query. Per-field "Reset to default" forms; `email_template.updated` / `email_template.reset` audit events.
  - **#468** polish — Email Template + Settings button consistency: Invitation / Reminder tabs out of card / normal-sized / flushed left, Save / Cancel at bottom-right of their card, no flash banners (Save disables until dirty), Settings page picks up `?return_to=` plumbing matching the About-page convention.
  - Spec at `spec/email_infra_options.md` for the broader transport landscape (Options A–D: SMTP, Microsoft Graph application permission, Azure Communication Services, third-party transactional). The Graph stub will become Option B once the institution's IT conversation lands.
  - Plan: `guide/segment_11E_email_template_editor.md` (un-archived 2026-05-05 to host a "Responses-received email" follow-on section — 2 PRs adding `render_responses_received` + editor third tab + submit-time send trigger; PRs not yet shipped). Catalog `unfinished_business.md` #24 (closed by this segment).

- **Segment 11C Part 1 — Operations consolidation** — done 2026-05-06. PRs **#490 → #491 → #492 → #493**.
  - **#490** — chrome restored Outbox as a tab (later removed in #493).
  - **#491** — Manage Invitations (`/operator/sessions/{id}/invitations`) rewrite. Seven-column reviewer-centric table — Reviewer / Email Status / Email Sent / Review Progress / Required Fields / Last reminder / Action — absorbs the retired Monitoring page's reviewer-centric surface (per-reviewer progress, per-row reminders). New helper `views.build_invitations_rows` joins `monitoring.per_reviewer_progress` with a single batched outbox query for "latest invitation outbox row per reviewer". Reviewer drill-in scaffold at `.../invitations/{inv_id}/detail`. Outbox schema slice: Migration `b3d5e7f9a1c4` adds `email_outbox.cc_emails` / `bcc_emails` (Text); `send_invitation` / `send_reminder` populate them at queue time from the `email_template_overrides` JSON (new `email_templates.cc_bcc_for(session, kind)` helper). Columns sit unused at send time until Part 2.
  - **#492** — new Responses page (`/operator/sessions/{id}/responses`). Reviewee-centric coverage view; classifies each reviewee per a new `monitoring.AT_RISK_THRESHOLDS` constant (`adequate_fraction=0.5`) into Complete / Adequate / At risk / No responses. New helpers `monitoring.per_reviewee_coverage`, `views.build_responses_rows`. Reviewee drill-in scaffold at `.../responses/{reviewee_id}/detail`. Bulk reminder dispatch funnels through the same `POST /operator/sessions/{id}/invitations/remind-incomplete` endpoint Manage Invitations uses. Monitoring template + dedicated bulk-remind endpoint deleted; `GET /sessions/{id}/monitoring` 303-redirects to `/invitations` to preserve old bookmarks.
  - **#493** — drops Outbox from chrome (Operations row is now four tabs: Validate / Previews / Invitations / Responses). The Outbox page itself stays accessible via the "View outbox" button on Manage Invitations — it's a dev-diagnostic surface, not part of day-to-day Operations. Same PR styles the five Manage Invitations data cells as pills (`pill-count` for filled / good states, `pill-empty` for absent / not-yet states) so the table reads as a sparkline of state at a glance.
  - **Polish stream (#494 → #500).** Docs sync (#494); Responses table column rename + pill styling on `Reviewers completed` + `Last response` (#495); status-dropdown + name/email search filter strip on both pages closing the `spec/operations_renew.md` "Filtering" gap (#496) plus visual refinements — half-width filter card, side-by-side inputs, bottom-right Apply (#497); summary card + filter card paired side-by-side in `.bottom-grid` with new generic `.card-action-row` v2 primitive on Responses (#498) then Manage Invitations (#499); bulk **Regenerate all** secondary button + `invitations.regenerate_all_tokens` service helper + batch `invitations.regenerated` audit event (#500).
  - Test reorg: `tests/integration/test_monitoring.py` → `test_reminders.py`; new `test_segment_11c_pr3_responses.py`.
  - Plan: `guide/segment_11C_operations_consolidation.md`. Functional spec: `spec/operations_renew.md`.

- **Segment 11H — Placeholder card scaffolds (Quick Setup + Extract Data)** — done. Both Session Home placeholder cards have shipped their inert-but-fully-rendered real shapes via the `_quick_setup_card.html` and `_extract_data_card.html` partials (included from `session_detail.html`), backed by the `QuickSetupSlot` / `QuickSetupContext` and `ExtractDataRow` / `ExtractDataContext` dataclasses + builder helpers in `app/web/views.py`. Every slot / row / button is laid out and accessible; every interactive control renders disabled (`is_wired=False`, `wire_url=None`) until the wiring segments. The Quick Setup card on `/operator/sessions/new` is also wired to the same scaffold via `build_new_session_quick_setup_context`. Plan: `guide/segment_11H_placeholder_card_scaffolds.md`. Unblocks Segment 11J (Quick Setup wiring) and Segment 12A PR 6 (Configuration import slot graduation).

- **Segment 11G — Validate page** — done 2026-05-06. PRs **#505 → #506 → #507 → #508** (the four-PR sequence in the plan) plus polish PRs **#509 → #511**. Builds the Validate page out from a thin read-only issue list into a find-and-fix surface:
  - **#505 (PR A)** — page layout (later simplified): three-card structure with severity counts + lifecycle-aware copy + setup-coverage matrix + existing issue list. New `views.build_validate_context` adapter + `views.validate_lifecycle_copy` pure function.
  - **#506 (PR B)** — `validate_session_setup` refactored into a `ValidationRule` registry. Each issue carries a `rule_key`, `fix_url`, `fix_anchor`, `fix_page_label`, and `why`. Two new rules added: `email_template.no_help_contact` (info) and `instruments.no_display_fields` (warning). Setup-page tables grow `id="reviewer-row-{id}"` / `id="reviewee-row-{id}"` anchors so per-issue deep-links can scroll to the offending row. `ReadinessReport.has_non_blocking_findings` tightened to ignore info severity (info is advisory only, never triggers acknowledgment).
  - **#507 (PR C)** — severity filter chip strip (`?severity=` query param), per-source group count summary on the issue list (`Reviewers (1 error)`), per-issue native-disclosure "Why this check?" element with the rule's `why` paragraph.
  - **#508 (PR D)** — activate-warns detour from Home. The Next Action card's `acknowledge_warnings` checkbox is removed; when warnings exist, the Activate button 303s to `/validate?activate=1` and surfaces a `.banner.banner-warning` with the warnings inline + Cancel + Acknowledge-and-activate. `?activate=1` on a draft / ready / closed session redirects to the clean URL.

- **Segment 11F Part 1 — Previews page (chrome + picker + invitation email + reviewer surface)** — done 2026-05-06. The Operations-row Previews tab (`/operator/sessions/{id}/previews`) graduates from a placeholder to the pre-flight Reviewer Experience Preview hub. Three of the five planned PRs landed:
  - **PR A (#517 / #520)** — page chrome + reviewer picker. New `_preview_picker.html` partial with typeahead (`<input list>` + `<datalist>`), Apply / Previous / Next / Random controls, "Reviewer N of M" count, and assigned-reviewees peek strip. `?reviewer_email=` URL state is canonical (email, not id, so bookmarks survive a full-cohort re-upload). New `views.build_preview_picker_context` adapter + `POST /sessions/{id}/previews/random` route (server-side `secrets.choice`, no reviewer-email list leaks into client JS). Default behavior is no reviewer selected — the body collapses to a "pick a reviewer" empty state rather than defaulting to the first reviewer alphabetically.
  - **PR B (#521 / #522)** — tabbed email previews region + invitation card. Single full-width card with a `.btn-pair` tab strip (Invitation / Reminder / Responses-received); only the active tab's body renders at a time, and only the Invitation tab is wired to a real render adapter (Reminder + Responses-received render disabled with "(coming soon)" until PRs D / E activate them). New `views.EMAIL_PREVIEW_TABS` registry + `EmailPreviewTab` / `EmailBody` dataclasses + `build_email_preview_body` dispatch + `email_preview_from_display(user)` helper; the invitation render calls `email_templates.render_invitation` with a `PREVIEW_INVITE_URL_PLACEHOLDER` so real one-time-use tokens aren't burned on previews. Source-of-truth footer deep-links to Email Template (Setup) `?template=invitation` + Reviewers (Setup). `<hr>` separator below the email card with a placeholder where PR C's surface card would land.
  - **PR C (#523)** — reviewer-surface card + retire `/preview` (singular). New `_surface_preview_card.html` partial renders the picker-selected reviewer's would-be reviewer surface inside an `<iframe srcdoc="…" sandbox="allow-scripts">`. Sandbox uses `allow-scripts` only (no `allow-same-origin`) so the reviewer-surface inline page-toggle JS keeps working for multi-instrument Page #N navigation while opaque origin blocks parent-cookie / localStorage access; `allow-forms` stays off. `routes_reviewer.build_preview_context` grows an optional `target_reviewer` parameter so synthetic-row pad surfaces *that reviewer's* reviewees rather than the unfiltered first-three-by-id fallback. New `views.build_surface_preview_context` + `SurfacePreviewContext` / `SurfacePreviewMissing` dataclasses with scoped missing-data handling (no instruments configured / reviewer has no assignments → Setup-page link inline; email region above the `<hr>` keeps rendering). Standalone `/sessions/{id}/preview` retired as a 308 permanent redirect to `/sessions/{id}/previews#reviewer-surface`; Session Home's "See previews" secondary button + the reviewer-surface preview-mode `PageButton.href` migrate to the hub anchor. Tests reshape: new `tests/integration/_preview_iframe.py` helper extracts + unescapes the iframe srcdoc so the existing reviewer-surface chrome / panel / inputs / page-button tests in `test_segment_11d_*.py` migrate cleanly off the retired route; `test_preview_route.py` shrinks to redirect + 403 + D9 deadline-observation contract.
  - Plan: `guide/segment_11F_previews_page.md`. **Part 2 (PRs D + E) still upcoming** — wires the Reminder and Responses-received tabs (the latter gated on Segment 11E's `render_responses_received` follow-on, PR 6).
  - **#509 → #511 polish** — readiness summary card removed (severity counts already live in the chip strip); setup-coverage matrix moved off `<table>` markup onto a flex-row-per-cell + 4-column grid layout (3-col → 4-col after #511) with the descriptive subtitle inline next to the H2.
  - Plan: `guide/segment_11G_validate_page.md`. New: `tests/integration/test_session_validate_page.py` covering the four-PR surface end-to-end.

---

## Upcoming

Items still open, in shipping order. Each is a sub-segment of Segment 11; sequence and rationale on each line. Every entry below now has a detailed plan in `guide/`; "Plan TBD" is gone.

1. **Segment 11C Part 2 — Email send activation.** Wires Segment 11E's `EmailTransport` interface into the Manage Invitations page Part 1 just rebuilt. Two PRs:
   - **PR F** — outbox schema move (`error_message` Text + status enum widening to `{queued, sending, sent, failed}`); new `app/services/email_send_dispatch.py` (read row → build `EmailMessage` → call `transport.send` → persist result, with truncated `transport_response` for audit); per-row Send + Send-test-to-me affordances + transport-ready chrome pill on Manage Invitations; new `email.sent` / `email.send_failed` audit events.
   - **PR G** — bulk Send-all-queued (selection-driven; iterates rows synchronously inside the request).
   Hard prerequisites already met: Part 1 PR C ships the consolidated page; Segment 11E PRs 4 + 5 ship the operator Settings page + transport interface. **Plan: `guide/segment_11C_operations_consolidation.md` "Part 2".**
2. **Segment 11F Part 2 — Previews page (Reminder + Responses-received tabs).** Part 1 (PRs A / B / C) shipped — page chrome + reviewer picker + tabbed email region with the Invitation tab live + reviewer-surface iframe card + retired `/preview` (singular). Part 2 lights up the two remaining email tabs by attaching their render adapters to the existing `views.EMAIL_PREVIEW_TABS` registry; the tab strip's "shipped vs. coming" branch flips automatically. Two PRs:
   - **PR D — Reminder tab.** Wire the Reminder entry to a render adapter calling `email_templates.render_reminder(session, reviewer)`; same `EmailBody` shape as the invitation card. Independent — does not depend on PR E.
   - **PR E — Responses-received tab.** Wire the Responses-received entry to `email_templates.render_responses_received(session, reviewer)` — the helper Segment 11E's PR 6 follow-on introduces. Cross-segment seam with 11E PR 6 (whichever ships first carries the registry mutation; the other strikes its scope item). Pre-submit preview surfaces a placeholder note since `$submitted_at` falls back to the "(not yet submitted)" placeholder when the picker-selected reviewer hasn't submitted. Hard prerequisite: 11E PR 6 must ship `render_responses_received` first (or with this PR).
   **Plan: `guide/segment_11F_previews_page.md`** ("PR D" / "PR E" subsections).
3. **Segment 11J — Quick Setup wiring.** Unblocked: Segment 11H's scaffold has shipped, so each PR here is a thin diff that flips one slot from `is_wired=False` to `True` and supplies a `wire_url` against the existing per-entity import pipeline; no markup created in this segment. Three live slots (Reviewers / Reviewees / Assignments) plus a fourth Configuration-import placeholder that graduates when Segment 12A PR 6 lands. Sized as 3 PRs (PR C may collapse to a no-op). Catalog `unfinished_business.md` #30. **Plan: `guide/segment_11J_quick_setup_card.md`.** (Letter 11I is skipped to avoid I/1 ambiguity, a common convention.)
4. **Segment 11K — #5 Audit-event `detail` schema convention.** Spec write-up in `spec/architecture.md` (canonical envelopes — `changes` / `snapshot` / `counts` / `set_changes` — plus orthogonal identity / `reason` / `refs` slots) + typed audit helpers in `app/services/audit.py` + incremental emitter migration (one PR per family) + optional Pydantic write-validation gate. Sized as ~8 PRs. The last sub-segment before Segment 12; pinning the `detail` shape now means Segment 12's audit-export consumer reads a stable schema. Catalog `unfinished_business.md` #5. **Plan: `guide/segment_11K_audit_event_detail_schema.md`.**

### Notes on the order

- **Item 1 (11C Part 2)** ships the email send-activation work that consumes 11E's transport interface. The load-bearing piece for getting real emails out the door.
- **Item 2 (11F Part 2)** lights up the two remaining email tabs (Reminder / Responses-received) on the previews hub Part 1 just shipped; thin diffs against the existing `EMAIL_PREVIEW_TABS` registry. PR E coordinates with Segment 11E PR 6's `render_responses_received` follow-on.
- **Item 3 (11J)** is unblocked now that 11H's scaffold has shipped — each PR is a thin diff that flips one Quick Setup slot live; no markup creation.
- **Item 4 (11K)** gates Segment 12 (audit retention). Last sub-segment before Segment 12 starts.

### Segment 12 scope — resolved

Earlier this segment carried an "open question" footer on whether Extract Data should be a standalone 11H or fold into Segment 12. **Resolved:** Extract Data has folded into **Segment 12A** (`guide/segment_12A.md`), which is now broader than the original "session metadata export / import" framing — it ships the configuration round-trip (PRs 1-2) **and** the Extract Data card with five separate per-entity CSVs + a "Download all" zip bundle (PRs 3-6). The original Segment 12 (`guide/segment_12_export_audit_retention_mvp_plan.md`) narrows to "audit retention" only and gates on 11K landing first.

Likewise, the broader email-transport work (Microsoft Graph application permission, ACS, third-party transactional) carries forward as a Segment 11M / 15 concern; `spec/email_infra_options.md` is the menu of options the IT conversation drives, with 11E having shipped the abstraction layer those backends slot into.

---

## Deferred to later segments

Items intentionally pushed to where they bundle with related work. Not in the active sequence.

### Segment 12 (export / audit retention MVP)

- **AG Grid evaluation extension** — folds in if the export surface needs interactive grid editing (otherwise stays in Segment 15 with #33).

### Segment 13 (rule-based assignment builder + sort UX)

- **§2.6 / `guide/sort_by_reviewee.md`** — sort-column UX on Manage pages. Functional spec ready; ships with the rule-builder work.
- **Rule Based Assignment** card on `/assignments` is currently a placeholder (uses `placeholder_card` macro); real implementation lands in 13.

### Segment 15 (operator polish + production hardening + real SMTP)

- **#23** — Sessions-list per-row Delete button (anchor → POST form).
- **#25** — Inline-editable rows for Reviewers / Reviewees / Assignments Manage pages.
- **#26** — Local Postgres docker-compose for dev.
- **#33** — AG Grid integration on Manage pages (was §2.1).
- **#34** — Queue-based batch invitation sending (was §2.3; bundled with real SMTP).
- **#35** — Technical-support contact (split out from §24 / #24).
- **#36** — Operator Inactivate UI on Reviewers / Reviewees Manage pages (was §2.4).
- **§2.2** — Vanilla-JS autosave on `/save` (folded into AG Grid #33's cell-edit lifecycle).

### Future / undated

Anything in `docs/status.md` "What's deliberately not yet there" with a named target segment ≥12 (export, RuleBased assignment, production hardening, real SMTP). Owned by their target segments, not this list.

---

## Notes on the order

- **Why CI items (#1 / #2) preceded the arch slate.** Without Postgres-flavoured pytest and `ruff check` in CI, the arch refactors (#3 / #4 / #11 / #16) would have shipped silently-broken code on every PR until the dev-slot deploy.
- **Why Segment 11B closed before 11C.** Home is the operator's anchor page; settling its layout, vocabulary (`.card.placeholder`, `.card.next-action`, `lifecycle_label`), and disabled-state pattern first means 11C can compose on top of stable primitives.
- **Why #5 (audit-event detail schema) gates Segment 12.** Segment 12's first deliverable is exporting `audit_events`; the export is much less work if the JSON shape is pinned first.
- **Why #21b / 11C / #24 can ship in parallel.** Disjoint surfaces — #21b touches non-session chrome, 11C touches Operations pages, #24 touches the invitation pipeline.
