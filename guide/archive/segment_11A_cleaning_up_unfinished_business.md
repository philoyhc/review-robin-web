# Segment 11 — Cleaning up unfinished business

(Originally drafted as Segment 10E before the 2026-05-03 segment renumber promoted it. Cross-references in older docs may still point to "10E" by name.)

**Status (2026-05-04):** Tiers 1, 2, and 3 closed. Tier 4 closed except for one remaining item (`#24` operator-editable email template editor). `#21b` shipped via Segment 11D (PRs A → B → C). Segment 11B (Session Home rebuild) shipped end-to-end and absorbed `#22` + `#30`. `#5` (audit-event detail schema) gates Segment 12 and remains the latest item that must precede it.

This was a punch list cleaning up Segments 1–10 — small bug fixes, deferred decisions, surfaced polish. Most items shipped or had decisions recorded; a smaller group was deferred to Segment 13 / Segment 15.

---

## Done

Dense list. PRs and catalog entries linked for detail.

### Code shipped

- **#9** — `get_or_create_default_instrument` docstring refresh (PR #309)
- **#8** — CSV email-validation drift; shared `_parse_email` helper (PR #314)
- **#12** — CSV cross-table identity check (PR #315)
- **Reviewer surface heading mismatch** — position-based fallback matching the operator surface (PR #319)
- **Reviewer surface UI polish batch** — heading display logic; help text inline; Reviewee column dedup; Photo `View` link; column-width hints by cell type; trailing status-column hide-when-empty; card framing aligned with `spec/visual_style_general.md`; help-text indentation fix (PRs #320 → #324)
- **#10** — `correlation_id` into deadline lazy-close (PR #329)
- **#6** — Decouple `invitations.py` from FastAPI `Request` (PR #330)
- **#21a** — v2 sweep across the session-centric pages: `session_reviewers.html`, `session_reviewees.html`, `session_assignments.html`, `session_invitations.html`, `session_monitoring.html`, `session_outbox.html`, `session_validate.html`, `session_setupinvite.html` (placeholder), `session_previews.html` (placeholder), `session_detail.html` (Session Home), `instruments_index.html`, plus the `session_setup_status_row.html` partial. Tracked in `guide/ui_checklist.md`.
- **#22 + #30** — Session Home rebuild + Quick Setup placeholder card. Placeholder card shipped during the v2 Home sweep; full Home rebuild closed via **Segment 11B** (PRs #380 → #393, plan at `guide/segment_11B_session_home.md`, functional spec at `spec/session_home.md`). The 11B work also introduced the canonical `.card.placeholder` class + `placeholder_card` Jinja macro (now reused on the Assignments page's Rule Based Assignment card) and the `.card.next-action` treatment for Session Home's Next Action card.

### Decisions recorded

- **§2.1** — AG Grid fate → Segment 15 (PR #327, catalog `unfinished_business.md` #33)
- **§2.3** — Queue-based batch invitation sending → Segment 15, bundled with real SMTP (PR #328, catalog #34)
- **§24** — Help-contact merge field source = path 1 (per-session column on `ReviewSession`, primary surface is the response form); separate technical-support contact split out (PR #328, catalog #35 → Segment 15)
- **#7** — CSRF: rely on Easy Auth + `SameSite=Lax` cookies; no CSRF tokens in app code. Write-up in `docs/authentication.md` (PR #328)

### Promotions / restructures

- **§2.6** (sort-column UX) promoted from sketch to full functional spec at `guide/sort_by_reviewee.md`, target Segment 13 (PR #317, catalog #31)
- **Tier 3 / 4 restructure** — #21 + #22 + #30 bundled as multi-part "UI clean up"; #24 moved Tier 3 → Tier 4; §2.4 deferred to Segment 15 (PR #329)

---

## Remaining work

| # | Item | Notes |
|---|------|-------|
| 1 | **#21b — remaining non-session-centric pages** | Pages outside the operator-session chrome. Pending: `sessions_list.html` (Operator's Overview), `session_new.html` (Create Session form), `session_edit.html` (sub-page form, not chrome'd like Setup pages), all three reviewer templates (`reviewer/dashboard.html`, `reviewer/review_surface.html`, `reviewer/invite_mismatch.html`), `about.html`, `me_debug.html`. Implementation plan: `guide/segment_11D_v2_sweep_non_session.md` (3 PRs in dependency order). Mechanical per-template work using the same recipe as #21a, but the non-session chrome conventions in `spec/visual_style_rrw.md` "Non-session and reviewer chrome" apply (light top bar, return-to-origin for About/Settings, reviewer top bar variant). Tracked per-page in `guide/ui_checklist.md`. |
| 2 | **#24 — Operator-editable email template editor** | Operator-facing surface at `/operator/sessions/{id}/setupinvite` (currently a stub). New schema column `email_template_overrides` (JSON on `ReviewSession`); body render moves from hardcoded `_email_body` / `_reminder_body` to template + merge fields. Help-contact merge field reads from `ReviewSession.help_contact` per the §24 decision. Tier 3 prerequisite (#6 — decouple `invitations.py` from `Request`) shipped 2026-05-03. Catalog `unfinished_business.md` #24. |
| 3 | **#5 — Audit-event `detail` schema convention** | Spec write-up in `spec/architecture.md` then incremental emitter migration. Segment 12 (export / audit retention) needs this stable. Catalog `unfinished_business.md` #5. |

---

## Deferred from Segment 11

Implementation moved to other segments. (Decisions made in Segment 11 — see "Done / Decisions recorded" above — also route work to Segment 15; not duplicated here.)

| Item | Target | Catalog |
|------|--------|---------|
| **§2.4** — Operator Inactivate UI (per-row Inactivate button on Reviewers / Reviewees Manage pages) | Segment 15 | `unfinished_business.md` #36 |
| **§2.2** — Vanilla-JS autosave on `/save` | Segment 15 (bundled into AG Grid #33's cell-edit lifecycle) | — |
| **#23** — Sessions-list Delete button (anchor → POST form) | Segment 15 | `unfinished_business.md` #23 |
| **#25** — Inline-editable rows for Reviewers / Reviewees / Assignments Manage pages | Segment 15 | `unfinished_business.md` #25 |
| **#26** — Local Postgres docker-compose for dev | Segment 15 | `unfinished_business.md` #26 |

---

## Conventions

- **Promote-to-`unfinished_business.md`.** Items originally listed in this file as sketches ("This file (was §N)") got promoted to full catalog entries when work started, so the catalog stays the source of truth and Segment 11 retires gracefully. All Tier 4 remaining items already have catalog entries.

---

## Out of scope

- Anything in `docs/status.md` "What's deliberately not yet there" with a named target segment ≥12 (export, RuleBased assignment, production hardening, real SMTP).
- New features not in the original Segments 1–10 audit. Segment 11 was closing books on what shipped through Segment 10D, not opening new scope.
