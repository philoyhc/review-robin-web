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
  - **PR 5 (#464)** — `EmailTransport` Protocol + `EmailMessage` / `SendResult` dataclasses + concrete `SmtpEmailTransport` (`smtplib`, STARTTLS / implicit-SSL) + typed-stub `GraphEmailTransport` placeholder + `transport_for(settings)` factory. Nothing in the app calls this yet; first call site is Segment 11C PR F.
  - **PR 2 (#465)** — actual editor UI on `/setupinvite`. Two-card `.bottom-grid` layout: composer left, merge tags + Save / Cancel right. Per-template (Invitation / Reminder) selection via `?template=` query. Per-field "Reset to default" forms; `email_template.updated` / `email_template.reset` audit events.
  - **#468** polish — Email Template + Settings button consistency: Invitation / Reminder tabs out of card / normal-sized / flushed left, Save / Cancel at bottom-right of their card, no flash banners (Save disables until dirty), Settings page picks up `?return_to=` plumbing matching the About-page convention.
  - Spec at `spec/email_infra_options.md` for the broader transport landscape (Options A–D: SMTP, Microsoft Graph application permission, Azure Communication Services, third-party transactional). The Graph stub will become Option B once the institution's IT conversation lands.
  - Plan: `guide/segment_11E_email_template_editor.md`. Catalog `unfinished_business.md` #24 (closed by this segment).

---

## Upcoming

Items still open, in shipping order. Each is a sub-segment of Segment 11; sequence and rationale on each line.

1. **Segment 11C — Operations consolidation (Invitations + Responses).** New page-set absorbing the standalone Monitoring page into a consolidated reviewer-centric Invitations page, adding a reviewee-centric Responses page, and restoring Outbox as a chrome tab. Sized as ~3–5 PRs (A: `/monitoring` redirect + chrome update; B: list-with-bulk-actions pattern; C: Invitations rewrite; D: Responses page; E: retire `session_monitoring.html`) plus PR F — wires Segment 11E's `EmailTransport` interface into per-row + bulk Send + test-send affordances on the rebuilt Manage Invitations page. **Plan: `guide/segment_11C_operations_consolidation.md`.** Functional spec: `spec/operations_renew.md`.
2. **Segment 11F — Previews page.** The chrome's Operations-row Previews tab (`/operator/sessions/{id}/previews`) ships today as a placeholder. Build out the per-instrument preview surface per `spec/preview_hub.md`, with the per-instrument cards listing display-field labels + sample reviewer table + a "Send test" affordance. Plan TBD.
3. **Segment 11G — Validate page.** The chrome's Operations-row Validate tab (`/operator/sessions/{id}/validate`) shipped on v2 during 11A but as a read-only deep-dive page. Polish per the latest operator-UI direction: clearer error / warning / info pillification, lifecycle-aware framing, deeper integration with the Next Action card on Home (e.g. clicking Activate on a Validated session should still surface the warnings here rather than from inside the card). Plan TBD.
4. **Segment 11H — Extract Data.** The Extract Data card on Session Home ships today as a placeholder via the canonical `placeholder_card` macro (Segment 11B). 11H builds out the real extraction surface — picks which formats to support (CSV / JSON / etc.), wires the response dump endpoint, and ships the format selector + counts summary inside the card. Likely overlaps with the original Segment 12 (export / audit retention MVP); see "Deferred" section. Plan TBD.
5. **Segment 11J — Quick Setup.** The Quick Setup card on Session Home ships today as a placeholder via the canonical `placeholder_card` macro (Segment 11B). 11J builds out the real card per `spec/quick_setup_card_spec.md` — bulk-populate reviewers, reviewees, and assignments from files or rules in one place. Catalog `unfinished_business.md` #30. Plan TBD. (Letter 11I is skipped to avoid I/1 ambiguity, a common convention.)
6. **Segment 11K — #5 Audit-event `detail` schema convention.** Spec write-up in `spec/architecture.md` then incremental emitter migration. Segment 12 (export / audit retention) reads `audit_events` and needs the `detail` JSON shape pinned first; this is the latest item that gates Segment 12. Catalog `unfinished_business.md` #5. Plan TBD.

### Notes on the order

- **Item 1 (11C)** rebuilds Manage Invitations + ships the email send-activation work that consumes 11E's transport interface. PR F is the load-bearing piece for getting real emails out the door.
- **Items 2, 3** polish or build out specific Operations-row tabs (Previews, Validate). They share patterns with 11C (list-with-bulk-actions, the chrome Operations row) and benefit from 11C landing first.
- **Items 4, 5** build out the two Session Home placeholder cards (Extract Data and Quick Setup). They have no special prerequisite but reuse the v2 vocabulary (`.card.placeholder` retires for each specific card once its real implementation lands).
- **Item 6** gates Segment 12 (export / audit retention). Should be the last sub-segment before Segment 12 starts. If Extract Data (item 4) is folded into Segment 12 instead of a separate 11H, the sequencing becomes 11K → Segment 12.

### Open question on Segment 12 scope

With Extract Data carved off as **11H** and the audit-event `detail` schema as **11K**, Segment 12 (`guide/segment_12_export_audit_retention_mvp_plan.md`) narrows to "audit retention" only — or **11H** subsumes it entirely. Reconcile when 11H's plan drafts.

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
