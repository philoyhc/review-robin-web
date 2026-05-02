# Master todo sequence

Prioritized order for working through the
`guide/unfinished_business.md` catalog. **Two files, two
purposes:**

- **`guide/unfinished_business.md`** — the catalog. Every open
  item, with Why / Where / Plan. Read it for the detail.
- **This file** — the sequence. Which item next, and why that
  order. Read it for the roadmap.

When you ship an item, tick it off in **both** files.

The sequence is shaped by three forces: (a) close test gaps that
Segment 10D opened up before the upcoming arch refactors trip
over them, (b) some items must land in a specific order because
they touch the same code (item 12 follows item 13, item 16
bundles with item 9; item 11's previous "wait for P0" gate has
already cleared, item 4's previous "wait for #17" gate is also
gone after the 2026-05-02 re-audit), and (c) defensive CI
hardening (lint, Postgres pytest) should land before the big
refactors themselves.

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

## P1 — Close test gaps + ship CI hardening (immediate next)

The Slice-5 PR (#265) added route-level coverage for
`create_instrument` / `delete_instrument`; the rest of the 10C
surface still has no integration test floor. With the planned
arch refactors below (item 3 in particular) about to ripple
through the same code, the test gaps need to close first.

| Order | Item | Why this position |
|---|---|---|
| 4 | ~~**#15 — Backfill 10C integration tests**~~ | ✅ shipped 2026-05-02 — `bulk_set_visibility` + `instruments.bulk_visibility_when_closed` audit covered in `tests/integration/test_bulk_visibility.py` (4 cases). The other three originally-listed surfaces had been silently covered during Segment 10D (re-audit 2026-05-02). |
| 5 | **#1 — Wire `ruff check` into CI** | 5-minute change, but two-PR sequence: clean up the ~10 pre-existing ruff findings in unrelated files first (mostly unused imports + unused locals), then add a `ruff check .` step to `ci.yml`. Without this, lint never executes anywhere. Catches regressions in the arch churn that's about to start. |
| 6 | **#19 — Roll session-status partial onto Reviewers / Reviewees / Assignments / Instruments** | Pure chrome cleanup. The shared `operator/partials/session_status_card.html` partial (#252) lives on Session detail + Email Invites; the four other session-scoped pages still hand-roll their top cards and drift in subtle ways. Land per-page (4 small PRs); Instruments is the most careful — it keeps its own status sub-rows. Settles the visual contract before Segment 11 planning. |
| 7 | **#2 — Run pytest against Postgres in CI** | The `ci-postgres-migration` job today only round-trips Alembic; it never imports `app/` and never runs a test. SQLite-only test runs hide JSON coercion / dialect divergence until the dev-slot deploy. Higher-cost than #1 but high-value before Segment 11 introduces export. |

---

## P2 — Architectural debt before Segment 11

Segment 11 (export / audit retention) will read
`Assignment.context` and write a stable `audit_events.detail`
schema, so settle the arch story first.

| Order | Item | Why this position |
|---|---|---|
| 8 | **#4 — Extract a single reviewer-session-state helper** | Two functions in `responses.py:435` + `monitoring.py:67` compute overlapping projections. The previously-cited `Assignment.include` filter divergence (item #17) is **already resolved** — both paths now route through the shared `_reviewer_assignments()` filter at `responses.py:54`, so consolidation can proceed directly. |
| 9 | **#3 — Move `_invalidate_if_validated` into the service layer** | 22 caller sites across `routes_operator.py` (re-grepped 2026-05-02; helper at `:789`). Naturally bundles with **#16** (decide bulk_visibility invalidation policy) since both touch the invalidation surface. |
| 10 | **#16 — Decide bulk_visibility_when_closed invalidation policy** | Bundle with #9. The policy question is whether `bulk_set_visibility` should flip `validated → draft` (the previously-cited "compare to bulk_set_accepting" framing was misleading — that route requires session=ready and never sees a validated session). |
| 11 | **#11 — Extract instruments-index template context to `views.py`** | Now safe (P0 prerequisites #13–14 shipped 2026-05-01). Re-grepped 2026-05-02: handler at `routes_operator.py:960–1100`, ~48 lines (10D shrunk from ~100). |
| 12 | **#5 — Define audit-event `detail` schema convention** | Document in `spec/architecture.md`. Migrate emitters incrementally — one PR per emitter family. Segment 11 will export these, so the convention needs to settle first. |

**#17 (filter divergence) — resolved on re-audit 2026-05-02; removed from sequence.**

---

## P3 — Small cleanups + pre-Segment-15

Items that aren't blocking the next feature segment but should
land before they age into harder problems.

| Order | Item | Why this position |
|---|---|---|
| 13 | **#8 — Fix CSV email-validation drift** | Sets up #14 (cross-table identity check) cleanly — same code path. |
| 14 | **#12 — Reviewer/Reviewee CSV cross-table identity check** | Builds on #8's shared `_parse_email` helper. Tightens the rule that email is the unique person-identifier across reviewer + reviewee tables in the same session. |
| 15 | **#10 — Thread `correlation_id` into deadline lazy-close** | Cheap. Bundle with whichever route refactor next touches `observe_deadline`. |
| 16 | **#9 — Refresh `get_or_create_default_instrument` docstring** | Tiny. (Pointer corrected to `app/services/assignments.py:402`.) |
| 17 | **#6 — Decouple `invitations.py` from `Request`** | Only matters when Segment 15 (real SMTP) lands and sends from a background worker. Worth fixing now while the surface is small. |
| 18 | **#7 — CSRF decision write-up** | One paragraph in `docs/authentication.md`. Decide between Easy Auth + SameSite cookies vs. CSRF tokens. If "tokens", that becomes its own segment. |

---

## Notes on the order

- **Why #15 (test backfill) is the next concrete PR.** The
  Slice-5 PR (#265) just established a fresh test pattern for
  the Instruments routes; #15 is a direct continuation of that
  momentum, no design decisions, and defends against #3 / #11
  rippling through the same code.
- **Why CI items (#1, #2) precede arch items.** Without lint and
  Postgres-flavoured pytest, the arch refactors below ship
  silently-broken code on every PR until the dev-slot deploy.
  Land the safety net before the churn.
- **Why item #19 (chrome) sits inside P1.** It's pure chrome but
  it touches every session-scoped operator page, so it
  competes for the same review attention as the arch items
  below. Better to land it as a bounded follow-up to Segment
  10D's chrome work than to delay until after the P2 arch
  surgery.
- **Why item 17 dropped out.** Re-audit 2026-05-02: the cited
  `Assignment.include` filter divergence between
  `responses.session_pill_for_reviewer` and
  `monitoring._reviewer_completion` is gone. Both now route
  through the shared `_reviewer_assignments()` filter at
  `responses.py:54`. Item #4 (consolidation) can proceed without
  the prerequisite investigation.
- **Why item 11 waits for P0.** The instruments-index handler
  builds context that items 13–14 reshaped substantially.
  Extracting the helper any earlier was throwaway work; now it's
  the right time. (Re-audit 2026-05-02: handler is now at
  `routes_operator.py:960–1100`, ~48 lines — Segment 10D shrank
  it from ~100.)

---

## What's not on this list

Anything in `docs/status.md` "What's deliberately not yet there"
— those are owned by their assigned future segments. The
"Display Fields persistence" entry there *was* one of those
deferred items, but the round-3 audit promoted the user-facing
correctness slice to item 13. Persistence proper is now part of
the shipped Segment 10D surface.
