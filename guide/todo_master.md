# Master todo sequence

Prioritized order for working through the
`guide/unfinished_business.md` catalog. **Two files, two
purposes:**

- **`guide/unfinished_business.md`** — the catalog. Every open
  item, with Why / Where / Plan. Read it for the detail.
- **This file** — the sequence. Which item next, and why that
  order. Read it for the roadmap.

When you ship an item, tick it off in **both** files. When a
sub-segment plan exists (e.g. `guide/segment_11B_session_home.md`),
that plan is the day-to-day source of truth for its own slices;
this file references it without duplicating its PR ladder.

The sequence is shaped by three forces: (a) finish the chrome
work that #19 spawned (#20 + #21 + #22) before the operator
surface ships into Segment 12, (b) some items must land in a
specific order because they touch the same code (#16 bundles
with #10; #12 follows #8; #22 follows #21 because Home rebuild
uses the buttons #21 restyles), and (c) defensive CI hardening
(Postgres pytest) should land before the big arch refactors
themselves.

---

## P0 — Stop the bleeding (Instruments UI ↔ data drift) — ✅ closed

The round-3 audit (2026-05-01) found that the operator's per-
instrument **Display Fields** card and the underlying schema had
drifted apart in ways that silently lost user input and silently
hid imported reviewee data. The full slice ladder now ships.

| Order | Item | Outcome |
|---|---|---|
| 1 | ~~**#13 — Fix Display Fields placeholder**~~ | ✅ shipped 2026-05-01 (option 2: wired to existing routes). |
| 2 | ~~**#14 — Drop `pair_context_*` default seed; seed from import data**~~ | ✅ shipped 2026-05-01 (lazy-seed + Alembic data migration). |
| 3 | ~~**#18 — Decide "Add an instrument" button vs route**~~ | ✅ shipped 2026-05-02 as Slice 5 of Segment 10D — Add + Delete enabled with mutual-exclusion / `is_ready` / single-instrument gates and a native `confirm()` on Delete. |

Segment 10D (#220 → #268) closed P0 end-to-end: the per-instrument
card and Response Type Definitions card are now built around a
single editing state machine, mutual-exclusion edit lock, save-
time RF / RTD guards, banner auto-scroll convention, and live
multi-instrument support. Reviewers see the right columns,
operators don't get gaslit, and the Instruments-page surface
matches the backing routes end-to-end.

---

## P1 — Close test gaps + ship CI hardening — ✅ closed

The Slice-5 PR (#265) added route-level coverage for
`create_instrument` / `delete_instrument`; the rest of the 10C
surface still has no integration test floor. With the planned
arch refactors below (item 3 in particular) about to ripple
through the same code, the test gaps need to close first.

| Order | Item | Why this position |
|---|---|---|
| 4 | ~~**#15 — Backfill 10C integration tests**~~ | ✅ shipped 2026-05-02 — `bulk_set_visibility` + `instruments.bulk_visibility_when_closed` audit covered in `tests/integration/test_bulk_visibility.py` (4 cases). The other three originally-listed surfaces had been silently covered during Segment 10D (re-audit 2026-05-02). |
| 5 | ~~**#1 — Wire `ruff check` into CI**~~ | ✅ shipped 2026-05-02 — `ci.yml` now runs `ruff check .` between dependency install and pytest. |
| 6 | ~~**#19 — Roll session-status partial onto Reviewers / Reviewees / Assignments / Instruments**~~ | ✅ shipped 2026-05-02 — chrome system rebuilt and rolled out to all 6 main session-scoped pages. Original literal scope satisfied; actual scope grew into a full chrome redesign (PRs #272 / #279 / #280–#290). Three follow-ons spawned: #20 (remaining pages), #21 (UI consistency updates), and #22 (Home body rebuild). |
| 7 | ~~**#20 — Complete chrome rollout to remaining session-scoped pages**~~ | ✅ Operations Pages shipped 2026-05-02 (Invitations / Monitoring / Outbox now carry the chrome with their own tab active). The two Home sub-pages (Edit Session / Validate detail) were folded into Segment 11B's rethink. |
| 8 | ~~**#2 — Run pytest against Postgres in CI**~~ | ✅ shipped 2026-05-02 — `ci-postgres.yml` runs the full suite against a `postgres:16` service container after the Alembic round-trip. |

---

## P2 — Settle the operator surface before Segment 12

Segment 12 (export / audit retention) will read
`Assignment.context` and write a stable `audit_events.detail`
schema, so the operator UI and the audit-event convention should
both settle first. The architectural-debt slate (items 9–12) has
shipped; the remaining work is the Segment 11 sub-segments and
the audit-schema convention.

| Order | Item | Why this position |
|---|---|---|
| 9 | ~~**#4 — Extract a single reviewer-session-state helper**~~ | ✅ shipped 2026-05-02. |
| 10 | ~~**#3 — Move `_invalidate_if_validated` into the service layer**~~ | ✅ shipped 2026-05-02. |
| 11 | ~~**#16 — Decide bulk_visibility_when_closed invalidation policy**~~ | ✅ shipped 2026-05-02 (decision: visibility-when-closed is exempt). |
| 12 | ~~**#11 — Extract instruments-index template context to `views.py`**~~ | ✅ shipped 2026-05-02. |
| 13 | ~~**Segment 11B — Session Home rebuild (PRs A–E + placeholder unification)**~~ | ✅ shipped 2026-05-04. PR A (lifecycle display label), PR B (contextual primary action card), PR C (Extract Data card), PR D (Quick Setup disabled + Danger Zone visible-disabled), PR E (`.pill-lifecycle-closed` cleanup) all merged. Placeholder treatment unified across Quick Setup + Extract Data + Rule Based Assignment via the canonical `.card.placeholder` class and `placeholder_card` macro. Plan: `guide/segment_11B_session_home.md`. |
| 14 | **Segment 11B — PR F (doc updates)** | Last slice of 11B. Update `spec/operator_ui_concept.md` to retire the Run Session four-button pattern and reflect the two-column Home; tidy `spec/session_home.md`'s now-completed `.pill-lifecycle-closed` mentions; tick `session_detail.html` in `guide/ui_checklist.md`. Lands after dev-slot verification of the visual changes from PRs B / C / D. |
| 15 | **#21b — Remaining non-session-centric pages on v2** | Per Segment 11A's Tier 4. The session-centric sweep (#21a) shipped during the chrome rebuild. Remaining: `sessions_list.html`, `session_new.html`, `session_edit.html`, `reviewer/dashboard.html`, `reviewer/review_surface.html`, `reviewer/invite_mismatch.html`, `about.html`, `me_debug.html`. Mechanical port using the same recipe as #21a, but the non-session chrome conventions in `spec/visual_style_rrw.md` apply (light top bar, return-to-origin for About/Settings, reviewer top bar variant). Tracked per-page in `guide/ui_checklist.md`. |
| 16 | **Segment 11C — Operations consolidation (Invitations + Responses)** | New page-set that absorbs the standalone Monitoring page into a consolidated reviewer-centric Invitations page, adds a reviewee-centric Responses page, and restores Outbox as a chrome tab. Sized as ~3–5 PRs (A: `/monitoring` redirect + chrome update; B: list-with-bulk-actions pattern; C: Invitations rewrite; D: Responses page; E: retire `session_monitoring.html`). Plan: `guide/segment_11C.md`. Functional spec: `spec/operations_renew.md`. Lands after 11B is fully shipped (verified on dev slot). |
| 17 | **#24 — Operator-editable email template editor** | Per Segment 11A's Tier 4. Operator-facing surface at `/operator/sessions/{id}/setupinvite` (currently a stub). New schema column `email_template_overrides` (JSON on `ReviewSession`); body render moves from hardcoded `_email_body` / `_reminder_body` to template + merge fields. Help-contact merge field reads from `ReviewSession.help_contact` per the §24 decision. Tier 3 prerequisite (#6 — decouple `invitations.py` from `Request`) shipped 2026-05-03. Catalog `unfinished_business.md` #24. |
| 18 | **#5 — Define audit-event `detail` schema convention** | Spec write-up in `spec/architecture.md` then incremental emitter migration. Segment 12 (export / audit retention) needs this stable, so this is the latest item that must precede Segment 12 starting. |

**#17 (filter divergence) — resolved on re-audit 2026-05-02; removed from sequence.**

---

## P3 — Closed-out items + deferrals to Segment 15

The Tier 3 polish bundle largely shipped during Segment 11A; the
items that didn't ship were intentionally pushed to Segment 15
where they bundle with real SMTP / multi-row inline-edit work.

### Shipped during Segment 11A

| Item | Outcome |
|---|---|
| ~~**#9 — Refresh `get_or_create_default_instrument` docstring**~~ | ✅ shipped 2026-05-03 (PR #309). |
| ~~**#8 — Fix CSV email-validation drift**~~ | ✅ shipped 2026-05-03 (PR #314), shared `_parse_email` helper. |
| ~~**#12 — Reviewer/Reviewee CSV cross-table identity check**~~ | ✅ shipped 2026-05-03 (PR #315), built on #8. |
| ~~**#10 — Thread `correlation_id` into deadline lazy-close**~~ | ✅ shipped 2026-05-03 (PR #329). |
| ~~**#6 — Decouple `invitations.py` from `Request`**~~ | ✅ shipped 2026-05-03 (PR #330). |
| ~~**#7 — CSRF decision write-up**~~ | ✅ closed 2026-05-03 (PR #328). Decision: rely on Easy Auth + `SameSite=Lax` cookies; no CSRF tokens in app code. Recorded in `docs/authentication.md`. |

### Deferred to Segment 15 (per Segment 11A's "Deferred" table)

| Item | Why Segment 15 |
|---|---|
| **§2.4 — Operator Inactivate UI** (per-row Inactivate button on Reviewers / Reviewees Manage pages) | Bundles with the Manage-page refresh in Segment 15. |
| **§2.2 — Vanilla-JS autosave on `/save`** | Bundles into AG Grid #33's cell-edit lifecycle. |
| **#23 — Sessions-list Delete button (anchor → POST form)** | Picked up with the Segment 15 sessions-list polish bundle. |
| **#25 — Inline-editable rows for Manage pages** | Bundles with #33 (AG Grid). |
| **#26 — Local Postgres docker-compose for dev** | Tooling polish, not blocking any feature work. |

---

## Notes on the order

- **What changed from the previous revision.** Segment 11A
  closed out most of the Tier 3 polish items (#6 / #7 / #8 / #9
  / #10 / #12). Segment 11B shipped the Home rebuild end-to-end
  except for the doc-updates slice (PR F). The placeholder-card
  vocabulary added during 11B (canonical `.card.placeholder`
  class + `placeholder_card` macro) is now used by Quick Setup,
  Extract Data, and Rule Based Assignment; future placeholder
  cards should reuse it without further design work. The next
  concrete unit of work is Segment 11B PR F, then the parallel
  remaining-Tier-4 items (#21b, 11C, #24) in any order.
- **Why item 14 (11B PR F) is the immediate next PR.** Closes
  out the Home rebuild and lets us stop touching
  `session_detail.html` for now. Cheap and isolated.
- **Why 11C, #21b, and #24 can ship in parallel.** Disjoint
  surfaces — 11C touches Operations pages, #21b touches the
  non-session chrome, #24 touches `/setupinvite` + the
  invitation-send pipeline. Pick whichever is most pressing
  next.
- **Why #5 (audit-event detail schema) must precede Segment 12.**
  Segment 12's first deliverable is exporting `audit_events`;
  the export is much less work if the `detail` JSON shape is
  pinned first. Land #5 as the last P2 item before Segment 12
  starts.
- **Why CI items (#1 / #2) preceded the arch slate.** Without
  Postgres-flavoured pytest and `ruff check` in CI, the arch
  refactors (#3 / #4 / #11 / #16) would have shipped silently-
  broken code on every PR until the dev-slot deploy.

---

## What's not on this list

Anything in `docs/status.md` "What's deliberately not yet there"
— those are owned by their assigned future segments. The
"Display Fields persistence" entry there *was* one of those
deferred items, but the round-3 audit promoted the user-facing
correctness slice to item 13. Persistence proper is now part of
the shipped Segment 10D surface.
