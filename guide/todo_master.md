# Master todo sequence

Prioritized order for working through the
`guide/unfinished_business.md` catalog. **Two files, two
purposes:**

- **`guide/unfinished_business.md`** — the catalog. Every open
  item, with Why / Where / Plan. Read it for the detail.
- **This file** — the sequence. Which item next, and why that
  order. Read it for the roadmap.

When you ship an item, tick it off in **both** files.

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

## P1 — Close test gaps + ship CI hardening (immediate next)

The Slice-5 PR (#265) added route-level coverage for
`create_instrument` / `delete_instrument`; the rest of the 10C
surface still has no integration test floor. With the planned
arch refactors below (item 3 in particular) about to ripple
through the same code, the test gaps need to close first.

| Order | Item | Why this position |
|---|---|---|
| 4 | ~~**#15 — Backfill 10C integration tests**~~ | ✅ shipped 2026-05-02 — `bulk_set_visibility` + `instruments.bulk_visibility_when_closed` audit covered in `tests/integration/test_bulk_visibility.py` (4 cases). The other three originally-listed surfaces had been silently covered during Segment 10D (re-audit 2026-05-02). |
| 5 | ~~**#1 — Wire `ruff check` into CI**~~ | ✅ shipped 2026-05-02 — `ci.yml` now runs `ruff check .` between dependency install and pytest. Pre-existing 10 findings (8 unused imports + 2 unused locals) cleaned up in the same PR. |
| 6 | ~~**#19 — Roll session-status partial onto Reviewers / Reviewees / Assignments / Instruments**~~ | ✅ shipped 2026-05-02 — chrome system rebuilt and rolled out to all 6 main session-scoped pages (Home + 5 setup). Original literal scope satisfied; actual scope grew into a full chrome redesign (PRs #272 / #279 / #280–#290). Three follow-ons spawned: #20 (remaining pages), #21 (UI consistency updates), and #22 (Home body rebuild + Option F). |
| 7 | ~~**#20 — Complete chrome rollout to remaining session-scoped pages**~~ | ✅ Operations Pages shipped 2026-05-02 (Invitations / Monitoring / Outbox now carry the chrome with their own tab active). The two Home sub-pages (Edit Session / Validate detail) are **deferred** — their status / function / location is being rethought as part of #22 (Home body rebuild). Adopting the chrome on those two now would risk locking in placement decisions the rethink might overturn. |
| 8 | ~~**#2 — Run pytest against Postgres in CI**~~ | ✅ shipped 2026-05-02 — `ci-postgres-migration.yml` renamed to `ci-postgres.yml`; the `engine` fixture in `tests/conftest.py` now honours `TEST_DATABASE_URL` / `DATABASE_URL` (defaults to in-memory SQLite); CI runs the full 405-test suite against a `postgres:16` service container after the Alembic round-trip. The `committed_engine` fixture in `tests/integration/conftest.py` was deliberately left on SQLite (its purpose is commit-vs-rollback semantics, not dialect coverage). No dialect-only test failures surfaced on first run. |

---

## P2 — Architectural debt before Segment 12

Segment 12 (export / audit retention) will read
`Assignment.context` and write a stable `audit_events.detail`
schema, so settle the arch story first.

| Order | Item | Why this position |
|---|---|---|
| 9 | ~~**#4 — Extract a single reviewer-session-state helper**~~ | ✅ shipped 2026-05-02 — new `ReviewerSessionState` dataclass + `reviewer_session_state()` helper in `responses.py` walks `assignments → fields → responses` once; `session_pill_for_reviewer` is now a thin projection, and `monitoring._reviewer_completion` deleted (it had been inlining its own assignment query, contrary to the catalog's claim that it routed through the shared filter). `monitoring.per_reviewer_progress` halved its per-row work — one helper call instead of two. 5 new unit tests added; full 410-test suite passes on both SQLite and Postgres. |
| 10 | ~~**#3 — Move `_invalidate_if_validated` into the service layer**~~ | ✅ shipped 2026-05-02 — new public `lifecycle.invalidate_if_validated()` helper (idempotent, no-op on non-validated). Every mutating service in `csv_imports.py`, `assignments.py`, `sessions.py`, `instruments.py` calls it at the top with a service-local `reason` constant; routes no longer thread the rule. The 23 explicit `_invalidate_if_validated` calls in `routes_operator.py` and the route helper itself are gone. 11 new service-layer invariant tests pin the rule (one per mutating service category); full 423-test suite passes on both dialects. |
| 11 | ~~**#16 — Decide bulk_visibility_when_closed invalidation policy**~~ | ✅ shipped 2026-05-02 alongside #3. **Decision: visibility-when-closed is exempt** — it's a display flag, not part of the validation snapshot. Pinned in code at `instruments.bulk_set_visibility` and `lifecycle.set_responses_visible_when_closed` (each carries a `# #16` comment) and in two regression tests (one each for the bulk and per-instrument toggle). The previously-existing `test_bulk_visibility_does_not_invalidate_validated_session` had its docstring updated since the policy is now decided rather than provisional. |
| 12 | ~~**#11 — Extract instruments-index template context to `views.py`**~~ | ✅ shipped 2026-05-02 — new `build_instruments_context()` in `app/web/views.py` owns the 5 idempotent display-field / RTD backfills, the editing-state machine, the bulk Accepting / Visibility three-state derivation, and the URL-driven `rtd_delete_blocked` / `rtd_would_empty` packaging. Handler shrank from 140 lines → 46 lines (query-param declarations + 1 view call + render). The catalog's "preview route reuse" framing turned out to be stale (preview uses `routes_reviewer.build_preview_context`); motivation reduced to "thin the route" per the CLAUDE.md services/routes/views split. No behaviour change; full 423-test suite passes on both dialects. |
| 13 | **#5 — Define audit-event `detail` schema convention** | Document in `spec/architecture.md`. Migrate emitters incrementally — one PR per emitter family. Segment 12 will export these, so the convention needs to settle first. |
| 14 | **#21 — UI consistency updates aligning with the new chrome** | Umbrella for follow-on UI cleanups that align the surface with the chrome's visual language. First sub-task: restyle the six canonical button modifiers (Primary / Primary Outline / Alert / Alert Outline / Danger / Danger Outline) — they now read as jarringly contrastive against the chrome's understated tints. Move them to softer fills / lighter borders / lighten-on-hover. Update `spec/assumptions.md` once settled. Sequenced before #22 because the Home rebuild will use these buttons, so getting the visual right first saves rework. |
| 15 | **#22 — Home body rebuild + Option F relocation** | After #20 / #21, the chrome system is fully deployed and the visual vocabulary is settled, but Home's body still uses the old four-card layout (not the launch-point framing in `spec/operator_ui_concept.md`), and page-specific status content (`fields_with_data`, self-review breakdown, etc.) is parked in sub-cards instead of relocated next to its relevant action per Option F. 4–6 small PRs total. Worth landing before Segment 12 so the operator surface is settled when export ships. |

**#17 (filter divergence) — resolved on re-audit 2026-05-02; removed from sequence.**

---

## P3 — Small cleanups + pre-Segment-15

Items that aren't blocking the next feature segment but should
land before they age into harder problems.

| Order | Item | Why this position |
|---|---|---|
| 16 | **#23 — Sessions-list Delete button doesn't actually delete** | UX bug: the per-row `Delete` button on `/operator/sessions` is a navigation link to the session's Home `#danger-zone`, not a real one-click delete. Operators click it, see nothing happen, conclude the wiring is broken. Fix: convert to a real POST form with `onsubmit` confirm, mirroring the per-instrument Delete pattern. Small surface, high visibility. |
| 17 | **#8 — Fix CSV email-validation drift** | Sets up #18 (cross-table identity check) cleanly — same code path. |
| 18 | **#12 — Reviewer/Reviewee CSV cross-table identity check** | Builds on #8's shared `_parse_email` helper. Tightens the rule that email is the unique person-identifier across reviewer + reviewee tables in the same session. |
| 19 | **#10 — Thread `correlation_id` into deadline lazy-close** | Cheap. Bundle with whichever route refactor next touches `observe_deadline`. |
| 20 | **#9 — Refresh `get_or_create_default_instrument` docstring** | Tiny. (Pointer corrected to `app/services/assignments.py:402`.) |
| 21 | **#6 — Decouple `invitations.py` from `Request`** | Only matters when Segment 15 (real SMTP) lands and sends from a background worker. Worth fixing now while the surface is small. Bundles naturally with #24. |
| 22 | **#24 — Operator-editable email template editor** | Pulled back from Segment 15 (where it had been auto-bundled with real SMTP). The editor is independent of SMTP — it shapes the body the dev outbox already renders. Workplan §12 work item #5 specified merge fields for reviewer name / session name / deadline / help contact / review link; today's hardcoded bodies carry only session name + invite URL. Operators landing on `/setupinvite` from the setup-nav today get a stub. Has one open question (help-contact source: per-session field, per-operator field, or global env var) to settle before coding. |
| 23 | **#7 — CSRF decision write-up** | One paragraph in `docs/authentication.md`. Decide between Easy Auth + SameSite cookies vs. CSRF tokens. If "tokens", that becomes its own segment. |

---

## Notes on the order

- **Why #20 (chrome rollout completion) is the next concrete
  PR.** Direct continuation of #19 — the chrome system is built
  and live on 6 of the 11 session-scoped pages. Adopting it on
  the remaining 5 (Operations Pages + Home sub-pages) is
  mechanical and small. Per **P2** in `spec/operator_ui_concept.md`,
  *"both phases always reachable"* requires the chrome on
  Operations Pages, so #20 is a P2-correctness fix as much as a
  cleanup.
- **Why CI items (#2) and chrome cleanups (#20) precede arch
  items.** Without Postgres-flavoured pytest, the arch
  refactors below would have shipped silently-broken code on
  every PR until the dev-slot deploy. #2 closed 2026-05-02; the
  arch slate (#4 / #3+#16 / #11 / #5) is now safe to touch.
- **Why #19's actual scope dwarfed its catalog framing.** The
  original "roll a partial onto 4 pages" turned into a full
  chrome redesign (PRs #272 / #279 / #280–#290). The catalog
  entry now reflects the larger work; the follow-on items
  (#20, #21, #22) capture what's left.
- **Why #21 (UI consistency) precedes #22 (Home rebuild).**
  The Home body rebuild will use the canonical buttons that
  #21 restyles. Settling the visual vocabulary first saves
  rework on the buttons that Home's lifecycle-transition
  primary, sub-page links, etc. will use.
- **Why #21 / #22 sit in P2.** Feature-shaped rather than
  test/CI hardening, but pre-Segment-11 work — settling the
  operator surface (visually and structurally) before export
  ships.
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
