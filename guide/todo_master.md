# Master todo sequence

Roadmap for working through the `guide/unfinished_business.md`
catalog. **Two files, two purposes:**

- **`guide/unfinished_business.md`** — the catalog. Every open
  item, with Why / Where / Plan. Read it for the detail.
- **This file** — the sequence. What's shipped, what's coming
  up, and why that order. Read it for the roadmap.

When you ship an item, tick it off in **both** files. When a
sub-segment plan exists (e.g. `guide/segment_11B_session_home.md`),
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

### P2 — Architectural debt + Segment 11

- **#4 — Single reviewer-session-state helper** — done 2026-05-02. New `ReviewerSessionState` dataclass + `reviewer_session_state()` helper in `responses.py`; `session_pill_for_reviewer` is a thin projection; `monitoring._reviewer_completion` deleted.
- **#3 — Move `_invalidate_if_validated` into the service layer** — done 2026-05-02. New public `lifecycle.invalidate_if_validated()` helper. Every mutating service calls it at the top with a service-local `reason`; route helpers gone. 11 new service-layer invariant tests.
- **#16 — `bulk_visibility_when_closed` invalidation policy** — done 2026-05-02 alongside #3. **Decision: visibility-when-closed is exempt** (it's a display flag, not part of the validation snapshot). Pinned in code at `instruments.bulk_set_visibility` and `lifecycle.set_responses_visible_when_closed` and in two regression tests.
- **#11 — Extract instruments-index template context to `views.py`** — done 2026-05-02. New `build_instruments_context()` in `app/web/views.py` owns the 5 idempotent backfills, the editing-state machine, the bulk three-state derivation, and the URL-driven cascade packaging. Handler shrank from 140 lines → 46.
- **#21a — v2 sweep, session-centric pages** — done 2026-05-03 across Segment 11A. Session-centric pages migrated onto `body.ui-v2` and ticked off in `guide/ui_checklist.md`.
- **Segment 11B — Session Home rebuild** — done 2026-05-04. PRs **#380 → #393**, plus a placeholder-card unification pass (#385 → #388) and Next Action card refinements (#390 → #393). Spec at `spec/session_home.md`. Highlights:
  - Lifecycle display label mapping (`ready` → "Activated") via `lifecycle_display.py` + `lifecycle_label` Jinja filter (#22, #30 absorbed here).
  - Next Action card with constant H2, `accent-blue` border, fixed `min-height: 200px`, body grows + button row pinned at the bottom (Primary + Secondary, no inline links).
  - State-conditional contents: Validate Setup / Activate Session / Pause Session as primary, sentence-case secondaries (See validation details / See previews / Revert to draft).
  - Confirm checkbox in `ready` sits in `.next-action-confirm` just above the buttons.
  - Quick Setup grey'd in ready; Extract Data grey'd in draft / validated; both render via the canonical `.card.placeholder` class + `placeholder_card` Jinja macro (also adopted by the Assignments page's Rule Based Assignment card).
  - Danger Zone Delete-Session is visible-but-disabled in ready (server still rejects via `_require_editable`).
  - `.pill-lifecycle-closed` retired; doc pass via PR F aligns specs and guides with what shipped.

### P3 — Tier 3 polish (closed during Segment 11A)

- **#9 — Refresh `get_or_create_default_instrument` docstring** — done 2026-05-03 (PR #309).
- **#8 — Fix CSV email-validation drift** — done 2026-05-03 (PR #314); shared `_parse_email` helper.
- **#12 — Reviewer/Reviewee CSV cross-table identity check** — done 2026-05-03 (PR #315); built on #8.
- **#10 — Thread `correlation_id` into deadline lazy-close** — done 2026-05-03 (PR #329).
- **#6 — Decouple `invitations.py` from `Request`** — done 2026-05-03 (PR #330).
- **#7 — CSRF decision write-up** — done 2026-05-03 (PR #328). Decision: rely on Easy Auth + `SameSite=Lax` cookies; no CSRF tokens in app code. Recorded in `docs/authentication.md`.

### Resolved on re-audit (no work needed)

- **#17 — Filter divergence between `responses.session_pill_for_reviewer` and `monitoring._reviewer_completion`** — re-audit 2026-05-02: gone. Both already routed through the shared `_reviewer_assignments()` filter at `responses.py:54`.

---

## Upcoming

Items still open, in shipping order.

1. **#21b — v2 sweep, non-session-centric pages.** Mechanical port using the same recipe as #21a, but the non-session chrome conventions in `spec/visual_style_rrw.md` apply (light top bar, return-to-origin for About / Settings, reviewer top bar variant). Pending templates: `sessions_list.html`, `session_new.html`, `session_edit.html`, `reviewer/dashboard.html`, `reviewer/review_surface.html`, `reviewer/invite_mismatch.html`, `about.html`, `me_debug.html`. Tracked per-page in `guide/ui_checklist.md`.
2. **Segment 11C — Operations consolidation (Invitations + Responses).** New page-set absorbing the standalone Monitoring page into a consolidated reviewer-centric Invitations page, adding a reviewee-centric Responses page, and restoring Outbox as a chrome tab. Sized as ~3–5 PRs (A: `/monitoring` redirect + chrome update; B: list-with-bulk-actions pattern; C: Invitations rewrite; D: Responses page; E: retire `session_monitoring.html`). Plan: `guide/segment_11C.md`. Functional spec: `spec/operations_renew.md`.
3. **#24 — Operator-editable email template editor.** Operator-facing surface at `/operator/sessions/{id}/setupinvite` (currently a stub). New schema column `email_template_overrides` (JSON on `ReviewSession`); body render moves from hardcoded `_email_body` / `_reminder_body` to template + merge fields. Help-contact merge field reads from `ReviewSession.help_contact` per the §24 decision. Catalog `unfinished_business.md` #24.
4. **#5 — Audit-event `detail` schema convention.** Spec write-up in `spec/architecture.md` then incremental emitter migration. Segment 12 (export / audit retention) reads `audit_events` and needs the `detail` JSON shape pinned first; this is the latest item that gates Segment 12. Catalog `unfinished_business.md` #5.

#21b / 11C / #24 are disjoint surfaces and can ship in parallel — pick whichever is most pressing. #5 is the gate to Segment 12 and should be the last P2-tier item before Segment 12 starts.

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
