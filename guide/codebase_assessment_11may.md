# Codebase assessment — 2026-05-11

**As of:** end of the locked-block sweep `13E → 12C → 15D → 12A-3`
plus Segment 12B and the Segment 15 doc split, two days after the
[2026-05-09 assessment](codebase_assessment_09may.md). Numbers taken
on `main` at commit `b46081d`. Citizen project, single-author cadence;
not yet pilot-deployed.

This is an audit-style snapshot against `spec/functional_spec.md`.
Authoritative ship-state lives in `docs/status.md`; this document
re-baselines the May 9 assessment after a heavy 48-hour landing
window (224 commits, 12 segments / sub-segments / bundles shipped).

---

## 1. What's in the box (one-paragraph summary)

A FastAPI + Jinja monolith implementing the operator setup →
reviewer response loop end-to-end at the dev-loop level, **now with
full CSV export and a working Settings importer**. Since the May 9
baseline, **CSV export** went from "scaffolded card with disabled
buttons" to five live tiles (Reviewers / Reviewees / Relationships /
Settings / Responses) with active-row-aware grey-out and a sixth
streaming **audit-events** extract that ships live but is parked
behind a forthcoming Sys Admin doorway. **Settings round-tripping**
is byte-stable: `serialize_session_config` ↔ `apply_session_config`,
wired to a graduated Quick Setup slot 4. The **assignments revamp
(15D)** rebuilt the pair-context story from the ground up — a
first-class `relationships` table with its own Setup page replaces
the legacy `Assignment.context` JSON column; the rule engine reads
pair-context via an eager lookup so the predicate path stays
single-pass. Quick Setup on Session Home and Create-New-Session is
fully wired across all four slots (Reviewers → Reviewees →
Relationships → Settings). Email is still staged to a dev outbox;
real send activation remains the Segment 14B boundary.

## 2. By the numbers (LOC + counts)

### Code

| Area | LOC | Files | Δ vs 5-09 |
|---|---:|---:|---:|
| `app/services` (business logic) | 12,996 | 21 modules + `rules/` + `instruments/` + `extracts/` packages | +3,278 |
| `app/web` (routes + view-shape adapters) | 10,575 | 13 route files + `views/` package | +804 |
|  ├ `routes_operator/` (12 slices + shared) | 5,239 | 12 | +420 |
|  ├ `routes_reviewer.py` | 1,135 | 1 | +13 |
|  └ `views/` (10 sub-modules) | 3,854 | 10 | +371 |
| `app/db/models` (SQLAlchemy 2.x declarative) | 1,224 | 19 | +382 (5 new models) |
| `app/schemas` (Pydantic shapes) | 510 | 5 | +17 |
| `app/auth` | 153 | 2 | 0 |
| `app/main.py`, `app/config.py` | ~118 | 2 | +9 |
| **Total `app/` Python** | **25,636** | — | **+4,436 (+21%)** |
| Alembic migrations | 3,143 | 35 | +869 / +13 files |
| Templates (`*.html`) | 8,133 | 42 | +104 / +1 |

### Tests

| Area | LOC | Files | Δ vs 5-09 |
|---|---:|---:|---:|
| Integration | 27,236 | 85 | +2,236 / +34 |
| Unit | 10,806 | 38 | +6,006 / +12 |
| Helpers + conftest | ~1,050 | ~8 | — |
| **Total tests** | **~39,095** | **131** | **+9,284 / +48** |

Test/code ratio: **1.53 ×** (up from 1.41 ×). The unit-test surface
grew dramatically (+125%) — extract serialisers, audit-event detail
shapes, `apply_session_config` two-phase contract, and the `relationships`
service all landed with dense unit coverage.

### Documentation

| Area | LOC | Files | Δ vs 5-09 |
|---|---:|---:|---:|
| `spec/` (functional + UI + per-page) | 9,713 | 22 | +777 |
| `guide/` (active plans + roadmap) | 4,085 | 16 | -2,138 (heavy archiving) |
| `guide/archive/` (shipped + retired plans) | 30,126 | 62 | +8,143 / +35 |
| `docs/` (subsystem deep-dives + status) | 1,532 | 7 | +25 |
| `CLAUDE.md` / `AGENTS.md` (byte-identical) | 222 each | 2 | -116 (trimmed) |
| `README.md` | 212 | 1 | -38 |

Active `guide/` shrank by a third as the 13E / 12C-1 / 15D / 12A-3 /
12B plans plus the legacy `unfinished_business.md`, `major_refactor.md`,
`rules_table.md`, and original umbrella Segment 15 stub all moved to
`guide/archive/`. The active set is now **12 segment plans** (the
upcoming pipeline), down from a mixed working set on May 9.

### Surface area

- **~100 HTTP routes** total (+10 vs May 9: per-entity extract
  endpoints, Relationships Setup CRUD, Settings import, audit-log
  extract).
- **19 database models**, **35 migrations** (Pg 16 / SQLite parity).
  New models since May 9: `Relationship`, `SessionFieldLabel`,
  `SessionRuleSet`, `OperatorResponseTypeDefinition`, and the
  rule-set rename (`OperatorRuleSet` ← `RuleSet`).
- **62 audit event types** registered in `EVENT_SCHEMAS` strict-mode
  registry (+11 since May 9: extract events for each entity,
  relationships imported / deleted, settings imported, audit-log
  extracted).
- **21 service modules** + the `rules/` + `instruments/` +
  `extracts/` sub-packages (new `relationships.py`,
  `session_config_io.py`, `extracts/` package with five serialisers).
- **42 Jinja templates** + partials.
- **224 commits** since the May 9 assessment (12-segment landing
  window: 13A-2, 12A-1, 13E, 12C-1, 15D, Post-15 cleanup, 12A-3,
  12B, plus the original Segment 15 doc split into 15F / 17 / 20
  and the doc-housekeeping sweep that retired `unfinished_business.md`
  and `major_refactor.md`).

## 3. Compliance against `spec/functional_spec.md`

### §21 Minimum viable functional release (16 items)

| # | Item | State | Δ vs 5-09 |
|---|---|---|---|
| 1  | Session creation and configuration | ✅ | — |
| 2  | Reviewer upload/edit | ⚠️ upload yes; inline edit deferred to **15F** | — |
| 3  | Reviewee upload/edit | ⚠️ upload yes; inline edit deferred to **15F** | — |
| 4  | Single-instrument configuration | ✅ | — |
| 5  | Manual assignment upload/edit | ⚠️ manual-CSV path is **dev-only** post-15D; rule-based + relationships is the operator path | shifted (was "per-row edit deferred") |
| 6  | Full-matrix assignment generation | ✅ (reachable as a seeded RuleSet) | — |
| 7  | Basic readiness validation | ✅ | — |
| 8  | Email invitations with individualized links | ⚠️ outbox-only until **14B Part A** | — |
| 9  | Microsoft sign-in or unique-link access | ✅ | — |
| 10 | Reviewer tabular response surface | ✅ multi-instrument, page-aware | — |
| 11 | Save and submit | ✅ | — |
| 12 | Operator progress dashboard | ✅ | — |
| 13 | Reminder sending | ⚠️ outbox-only until **14B Part A** | — |
| 14 | CSV and Excel export | ✅ **CSV shipped** (12A-1 + 12A-3); Excel never an MVP item | **upgraded ❌→✅** |
| 15 | Basic audit log | ✅ (62 event types, canonical envelope, strict-mode gate); CSV export route shipped 12B, surfaced via Segment 16A; richer in-app views are **Segment 16C** | extended (export route shipped) |
| 16 | Basic retention/deletion workflow | ❌ Segment 12B as originally scoped (purge tooling) not started — now owned by **Segment 18C**; the audit-log export piece shipped under the same number | partial |

**Score: 11/16 fully present (was 10), 4 functionally-present-but-dev-only,
1 not yet implemented.** CSV export crossed the line; retention
purge tooling and the four ⚠️ items remain.

### §22 Expanded release items

| Item | State | Δ vs 5-09 |
|---|---|---|
| Multi-instrument sessions | ✅ schema + reviewer surface; per-instrument assignments via 15B | — |
| Rule-based assignment builder | ✅ 13A + 13A-1 + 13A-2 (uniqueness DDL) | + 13A-2 |
| Pair-level context | ✅ **new** — first-class `relationships` table + Setup page; rule engine consumes via eager lookup | **new shipped 15D** |
| Assignment preview and dry-run counts | ✅ | — |
| Session cloning | ⚠️ stub plan — **Segment 18A** | progressed |
| Richer invitation templates | ✅ | — |
| Targeted reminders by completion state | ⚠️ "incomplete" cohort yes; richer slicing not planned | — |
| Controlled post-activation correction workflows | ✅ | — |
| Richer audit views | ⚠️ canonical schema + CSV export shipped; CSV download relocates to **16A** Sys Admin; richer in-app viewer is **Segment 16C** | progressed |
| Long-format / wide-format export | ✅ wide-format CSV shipped per entity; long-format Responses extract via `yield_per(1000)` | **shipped 12A-1** |
| Settings import (round-trip) | ✅ **new** — two-phase `apply_session_config` parses then wipes-and-replaces; byte-stable round-trip on its own output | **new shipped 12A-3** |
| Role delegation among multiple operators | ⚠️ table exists; no UI — owned by **Segment 16B** | — |
| Advanced retention policies | ⚠️ stub plan — **Segment 18C** (per-deployment policy + selective purge) | progressed |
| Administrative dashboards | ⚠️ Sys Admin page planned under **Segment 16A** (stub exists, audit-log download is its first anchor item) | **new plan** |

### §23 End-to-end acceptance criteria

Items 1-13 still work subject to the dev-outbox caveat on 8 + 12.
**Item 14 (export complete dataset) is now reachable** end-to-end via
the five Extract Data tiles + the audit-log route. **Item 15 (delete
or retain per policy)** still depends on retention/purge tooling
not yet scoped to a plan. Item 16 (review audit records) now has a
streaming CSV path — the operator-facing tile relocates to Sys Admin
in Segment 16A.

## 4. Strengths

1. **Locked-block landing.** The four-segment sequence
   `13E → 12C → 15D → 12A-3` shipped in **a single calendar day
   (2026-05-10)** across 14 PRs, with 13A-2 the day prior and
   12B + the doc split on top. That's a heavy fan-out — schema
   prep → service revamp → UI revamp → import/export realignment →
   audit export — and the PR ladder held: each PR small, each
   merge clean, no rollbacks. The "land migrations inert in 13D /
   13E, light them up in 15D / 15C / 15B / 13B / 13C" pattern is
   paying off — the four columns 13E PR 2 carried (`relationships`
   table) and 13E PR 1 carried (`self_reviews_active`) were both
   lit up the same day without migration thrash.

2. **Round-trip discipline on imports/exports.** `serialize_session_config`
   and `apply_session_config` are explicit inverses; the round-trip
   test asserts byte-stability on the export's own output. Two
   round-trip bugs surfaced during 12A-3 and got fixed at the
   right layer — naive datetimes → UTC in `_datetime` formatter,
   capitalized vs lowercase RTD `data_type` accepted on both sides.

3. **Audit-event schema discipline scales.** 62 distinct event
   types now register under the canonical envelope — up 22% from
   May 9 — with no schema drift. Every new emitter in the past
   48 hours (`relationships.imported`, `relationships.deleted_all`,
   `session.relationships_extracted`, `session.settings_imported`,
   `session.audit_log_extracted`, `assignments_extracted` removal)
   registered against `EVENT_SCHEMAS` cleanly. The strict-mode test
   gate caught at least one would-be regression during the sprint.

4. **Three-layer split + view-adapter seam still holds.** The
   2,469-line `app/services/instruments.py` and 3,483-line
   `app/web/views.py` monoliths split into packages on May 9
   stayed split — neither monolith re-formed under heavy 15D
   pressure. `app/web/views/` grew by 371 LOC across its 10
   sub-modules; no single file ballooned. The new `app/services/extracts/`
   sub-package fits the same pattern (5 per-entity serialisers
   + a small shared streaming helper). `routes_operator/` slices
   absorbed the new `_extracts.py` cleanly.

5. **Tests scaled with code.** Tests/code ratio rose from 1.41 ×
   to **1.53 ×** as code grew 21%. Unit tests **more than doubled**
   (+125%) — the new serialisers, `apply_session_config`, and
   audit-event detail shapes are each unit-tested before the
   integration layer. Integration suite grew +34 files / +2,236 LOC.

6. **Documentation cohesion improved.** Active `guide/` shrank
   from 6,223 to 4,085 LOC by archiving everything shipped and
   retiring three legacy artefacts (`unfinished_business.md` →
   absorbed into segment plans, `major_refactor.md` → done,
   `rules_table.md` → absorbed into `spec/rule_based_assignment.md`).
   The active set is now a focused 12-plan pipeline.
   `spec/` grew 8.7% — every shipped segment that locked a UI
   contract (Quick Setup status awareness, Setup pages preview
   ordering, settings inventory, rule-based assignment §5.4)
   wrote its spec on the way out.

7. **Iteration cadence remains tight.** ~224 commits in 48 hours
   is roughly **one merge every 12 minutes**, sustained over two
   calendar days. PRs continued in the small-and-reviewable shape
   (15D landed as 10 PRs, 12A-3 as 4 + 1 polish, 12B as 2). No
   PRs over ~500 LOC; most under 200.

8. **Decisions still written down at the point of decision.**
   Three new ones since May 9: (a) audit log surface belongs
   behind a Sys Admin doorway, not in Extract Data — recorded
   into `guide/segment_16A_sys_admin_page.md` Anchor item §3 with
   industry-best-practice citations. (b) Settings import is
   wipe-and-replace with two-phase parse, not row-level merge —
   recorded as the `ApplyResult` contract docstring. (c) Manual
   CSV assignment path retires from operator UI post-15D but
   stays live for test fixtures — recorded as a dev-only
   docstring label in 15D PR 7b.

9. **Schema landed inert, woken up cleanly.** 13D's six DB-prep
   migrations (2026-05-09) sat inert until their owning segments
   lit them up. **Two of six are now live** (13E PR 2's
   `relationships` table — 15D; `instruments.rule_set_id` — still
   inert until 15B). The other four (15A's `session_field_labels`,
   15C's `session_rule_sets` + `operator_response_type_definitions`,
   13B's `sort_display_fields`, 13C's `group_kind`) all remain
   inert with no migration churn.

## 5. Weaknesses and gaps

1. **Email is still not actually sent.** Unchanged from May 9.
   Acceptance criteria #8 (invitations) and #13 (reminders) still
   stop at `email_outbox.status="queued"`. Segment 14B Part A
   remains the activation boundary. **This is now the single
   largest gap between "demo-able" and "pilot-able."**

2. **Retention / purge tooling deferred.** Segment 12B was
   re-scoped during the sprint: the audit-log export shipped (one
   route + service + tile), but the retention/purge piece the
   original 12B plan owned moved to **Segment 18C** (stub created
   2026-05-11; per-session selective purge + per-deployment
   retention policy). Functional spec §12.2 / §12.4 are now owned
   but not yet implemented.

3. **Inline-edit still deferred.** Same shape as May 9 — typo fix
   for one reviewer's name requires a fresh CSV. **Segment 15F**
   now owns this explicitly (bundled with the Inactivate/Reactivate
   affordance since both touch the same three Setup pages), with
   a sized stub plan and a clear contract (one-click per-row edit,
   per-row status toggle). Not yet started.

4. **Manual assignments retired from operator UI but path lingers.**
   Post-15D the operator can no longer hand-author manual rows;
   pair-context is set via the Relationships table and the manual-CSV
   route stays alive only for test fixtures (15D PR 7b dev-only
   docstring label). Acceptance criteria §21 #5 sits in a strange
   intermediate state — the schema supports manual mode, the test
   helpers still exercise it, but operators can't reach it through
   the UI. Worth either deleting the path entirely or repromoting
   it as a documented escape hatch (Segment 16A Sys Admin candidate?).

5. **`_instruments.py` is now ~1,330 LOC.** The largest slice file
   post-refactor crossed the 1,200 line mark on May 9 and is
   creeping further. Still cohesive (~25 routes covering
   instrument CRUD + response/display field CRUD + RTDs + bulk
   visibility + lifecycle), but another slice-by-sub-feature isn't
   unreasonable. Not on any current plan.

6. **Sys Admin page is a long-known gap with no owner cadence.**
   Segment 16A (carved from the original Segment 16 on 2026-05-11)
   exists as a ~330-LOC stub with concrete anchor items
   (audit-log download, Outbox diagnostic surface, dev-only manual
   assignment escape hatch, security-model proposal with four
   authorization options sketched, Option C env-allowlist
   recommended for MVP). Several segment plans now defer items
   "to Sys Admin" — at some point the doorway has to exist.
   **Recommended near-term pick** given how many tiles park
   behind it.

7. **Production hardening unchanged.** Segment 14A still owns Key
   Vault, VNet, soft-delete, full Postgres pytest. 521-LOC plan,
   not started.

8. **`guide/archive/` ballooned to 30k LOC** (+37% in two days)
   — eight segment plans + four retired catalogue docs all moved
   in. Still readable, still not parsed by tooling. The 22k-LOC
   complaint from May 9 just got 37% worse. Compression would
   matter if anyone ever needs to grep across it for decision
   archaeology at scale.

9. **AG Grid + autosave deferred (now Segment 17).** Unchanged
   shape; lifted out of the original Segment 15 into its own
   130-LOC stub plan. Reviewer surface still uses plain HTML
   inputs with form-based save.

10. **No multi-tenant story.** Unchanged. Single-deployment by
    design.

11. **No reviewer self-service profile.** Unchanged. Spec doesn't
    require it for MVP.

12. **CSRF leans on Easy Auth.** Unchanged. Documented in
    `docs/authentication.md`.

13. **Reviewer surface cell editing is not type-rich.** Unchanged.
    Pre-pilot polish target tracked under Segment 17.

## 6. LOC budget estimate to project completion

Past-segment data has tightened the estimating model. Comparing
the May 9 forecast for 12A (estimated +2,500 code / +1,800 tests)
against actuals (12A-1 + 12A-3 + 12B shipped ~1,650 code + ~3,000
tests across `extracts/`, `session_config_io.py`,
`audit_events_extract.py`): code came in **34% under** the forecast,
tests came in **67% over**. The tests/code ratio for newly-shipped
work is closer to **1.8 ×**, not 1.4 × — consistent with the
overall ratio drifting up from 1.41 to 1.53.

Recalibrating with that ratio and the 12 remaining plans:

| Segment | Plan LOC | Est. code | Est. tests | Migrations |
|---|---:|---:|---:|---:|
| 13B — sort by reviewee | 226 | ~500 | ~900 | 0 (col landed inert in 13D) |
| 13C — enhanced instruments | 187 | ~1,000 | ~1,800 | 0 (col landed inert in 13D) |
| 14 — production hardening | 521 | ~1,500 | ~600 | 0-1 |
| 14B — email infra (Parts A → E) | 314 | ~1,800 | ~2,000 | 0 (cols landed in 11C Part 2) |
| 14B — email infra (Parts F → H, optional backends) | — | ~1,800 (if all three) | ~1,500 | 0 |
| 15A — friendly labels | 207 | ~700 | ~1,000 | 0 (table landed in 13D) |
| 15B — per-instrument assignments | 391 | ~1,400 | ~2,000 | 0 (FK landed in 13D) |
| 15C — operator libraries | 289 | ~1,500 | ~2,200 | 0 (tables landed in 13D) |
| 15E — Next Action revamp | 160 | ~600 | ~900 | 0 |
| 15F — Enhanced Setup pages | 159 | ~1,200 | ~2,000 | 0 |
| 16A — Sys Admin page + admin role | ~330 | ~800 | ~900 | 0-1 |
| 16B — Role delegation | ~120 | ~600 | ~700 | 0 |
| 16C — Richer audit views | ~160 | ~900 | ~1,000 | 0 |
| 17 — AG Grid replacement | 130 | ~1,800 | ~600 | 0 |
| 18A — Session cloning | ~150 | ~700 | ~900 | 0 |
| 18B — Session tagging + archiving | ~150 | ~600 | ~800 | 0-1 |
| 18C — Retention / deletion workflow | ~190 | ~900 | ~1,000 | 0-1 |
| 19 — Spec documentation | ~170 | n/a (docs) | n/a | 0 |
| 20 — Operator polish + docs | 94 | ~500 (code) + heavy docs | ~400 | 0 |
| **Total remaining** | **3,015** | **~15,300** | **~17,100** | **0-2** |

### Likely shape at completion

| Area | Today | At completion (estimate) | Δ |
|---|---:|---:|---:|
| `app/` Python | 25,636 | **~41,000** | +60% |
| Tests Python | 39,095 | **~56,000** | +43% |
| Templates | 8,133 | **~10,500** | +29% |
| Alembic migrations | 35 files / 3,143 LOC | **~37 / ~3,300** | flat |
| Specs | 9,713 | **~12,500** | +29% |
| Guides (active + archive) | 34,211 | **~40,000** | +17% |
| **Total project (all artifacts)** | **~120k LOC** | **~165k LOC** | **+37%** |

**Production Python at completion: ~40-42k LOC, +60% over today.**
The biggest single growth area now is the **Segment 15 family**
(15A + 15B + 15C + 15E + 15F = ~5,400 code, ~8,100 tests on the
revised estimates) — operator polish work that runs broad rather
than deep. Segment 14B (with all three backend options) is the
second-largest at ~3,600 code if every backend ships.

These estimates carry roughly **±20% uncertainty** (down from
±25% on May 9 — the 12A actuals tightened the model). The largest
unknown remains how much polish the Segment 15 family absorbs once
real pilot feedback lands. 17 (AG Grid) is also wobbly since it
introduces the first JS bundle and the LOC count there depends on
how thin the integration shim ends up.

## 7. Two-day delta summary

What changed between the May 9 baseline and this assessment:

- **CSV export crossed the MVP line.** §21 #14 went from ❌ to ✅.
- **Settings round-trip became a thing.** Inverse of the export
  shipped as `apply_session_config`; Quick Setup slot 4 lit up.
- **Pair-level context became first-class.** New `relationships`
  table + Setup page + Quick Setup slot replaced the dropped
  `Assignment.context` JSON column.
- **Audit-events export shipped.** 62 event types covered; export
  route lives, surfaced via Segment 16A Sys Admin when that lands.
- **Segment 15 split.** The umbrella stub broke into 15F (per-row
  affordances) / 17 (AG Grid) / 20 (operator polish + docs); the
  150-LOC stub became three focused plans summing to ~380 LOC.
- **Operator-facing surface broadened.** ~10 new routes, ~+800 LOC
  in `app/web/`. Per-entity download tiles, Relationships Setup
  page, Settings import route.
- **5 new models, 13 new migrations.** All ride on the 13D / 13E
  inert-prep pattern; no migration thrash.

## 8. One-line verdict

A disciplined, well-tested, well-documented FastAPI monolith at
**~25.6k LOC of production code (+21% in two days)**, **~39k LOC of
tests (1.53 × ratio)**, with **11 of 16 MVP acceptance criteria
fully met (+1)** and the remaining five tractably sequenced under
**12 active segment plans**. The single blocker between "runs
locally with full export" and "runs a real pilot" is now
**email send activation (Segment 14B Part A)**; everything else
is polish, hardening, or operator-affordance breadth.
