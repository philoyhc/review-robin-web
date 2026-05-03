# Segment 11 — Cleaning up unfinished business

(Originally drafted as Segment 10E before the 2026-05-03 segment renumber promoted it. Cross-references in older docs may still point to "10E" by name.)

**Status (2026-05-03):** Tiers 1, 2, and 3 closed. Only the Tier 4 medium-feature work remains. Land Tier 4 before Segment 12 (export / audit retention) starts so the operator surface settles cleanly.

This was a punch list cleaning up Segments 1–10 — small bug fixes, deferred decisions, surfaced polish. Most items shipped or had decisions recorded; a smaller group was deferred to Segment 13 / Segment 15.

---

## Done

Dense list. PRs and catalog entries linked for detail.

### Code shipped

- **#9** — `get_or_create_default_instrument` docstring refresh — done (PR #309)
- **#8** — CSV email-validation drift; shared `_parse_email` helper — done (PR #314)
- **#12** — CSV cross-table identity check — done (PR #315)
- **Reviewer surface heading mismatch** — position-based fallback matching the operator surface — done (PR #319)
- **Reviewer surface UI polish batch** — heading display logic; help text inline; Reviewee column dedup; Photo `View` link; column-width hints by cell type; trailing status-column hide-when-empty; card framing aligned with `spec/visual_style.md`; help-text indentation fix — done (PRs #320 → #324)
- **#10** — `correlation_id` into deadline lazy-close — done (PR #329)
- **#6** — Decouple `invitations.py` from FastAPI `Request` — done (PR #330)

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

All Tier 4 medium features. Suggested order shown.

| # | Item | Notes |
|---|------|-------|
| 1 | **#21 + #22 + #30 — UI clean up (multi-part)** | Three pieces shipping in sequence as one operator-chrome cleanup pass: <ul><li>**#21** — six canonical button restyle. visual_style.md migration on the operator-side `.btn` family, extending the reviewer-surface alignment work shipped in PRs #319 → #324. **Ships first** — #22 and #30 reuse the new button vocabulary.</li><li>**#22** — Home body rebuild + Option F relocation of parked sub-cards from chrome PR #287.</li><li>**#30** — Quick Setup card on Session Home (three slots: Reviewers, Reviewees, Assignments-or-rule). Spec at `spec/quick_setup_card_spec.md`.</li></ul> ~7–10 small PRs total. All three touch operator chrome / Home body, so doing them as one pass avoids touching the same templates multiple times. Catalog entries: `unfinished_business.md` #21 + #22 + #30. |
| 2 | **#24 — Operator-editable email template editor** | Ships **after** the UI clean up bundle. Operator-facing surface at `/operator/sessions/{id}/setupinvite` (currently a stub). New schema column `email_template_overrides` (JSON on `ReviewSession`); body render moves from hardcoded `_email_body` / `_reminder_body` to template + merge fields. Help-contact merge field reads from `ReviewSession.help_contact` per the §24 decision. Tier 3 prerequisite (#6 — decouple `invitations.py` from `Request`) shipped 2026-05-03. Catalog `unfinished_business.md` #24. |
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
