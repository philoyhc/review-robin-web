# Codebase assessment — 2026-05-16

**As of:** end of the **Segment 15 family** (15A friendly labels →
15B per-instrument assignments → 15C operator libraries → 15E
Operations Workflow Card → 15F enhanced Setup pages), the
**Sys-Admin arc** (16A Sys Admin page → 16B role delegation →
16C MVP in-app audit viewer), **13B** sortable tables, and
**Segment 18B** date / time settings. Five days after the
[2026-05-11 assessment](codebase_assessment_11may.md). Numbers
taken on `main` at commit `4ec05d0`. Citizen project,
single-author + AI-agent cadence; not yet pilot-deployed.

This is an audit-style snapshot. Authoritative ship-state lives
in `docs/status.md`; this document re-baselines the May 11
assessment after a heavy five-day landing window (~146 PRs).
The functional spec it audits against has moved —
`spec/functional_spec.md` was relocated to
`guide/archive/functional_spec.md` on 2026-05-11; section
numbers (§21 / §22 / §23) are unchanged.

> **History note.** The visible git history was linearised at
> some point after the May 11 assessment — the pre-`2026-05-12`
> commits (including the `b46081d` baseline the last assessment
> cited) are no longer ancestors of `main`. The visible tree is
> 306 commits / 146 PR merges spanning 2026-05-12 → 2026-05-16,
> which covers the whole inter-assessment window. Exact
> commit-level archaeology across the May 11 boundary is lossy.

---

## 1. What's in the box (one-paragraph summary)

A FastAPI + Jinja monolith implementing the full operator-setup
→ reviewer-response loop end-to-end at the dev-loop level — and
since May 11 the **operator surface has gone from functional to
polished**. The Segment 15 family rebuilt the operator
experience: **pervasive friendly labels** (operators rename the
12 in-scope display slots per session), **per-instrument
assignments** (each Instrument carries its own pinned rule +
materialised pair set), **operator RTD / RuleSet libraries** (a
symmetric two-tier library / per-session-copy model), the
**Operations Workflow Card** (one persistent card with a
ten-state cascade and an *Activate session* super-button that
collapses generate → validate → activate), and **enhanced Setup
pages** with per-row inline Edit / bulk inactivate-reactivate /
single-row Add — which **closes the long-standing "fix one
reviewer's name needs a fresh CSV" gap**. The **Sys-Admin arc**
shipped a real admin doorway: workspace allowlist, Accounts
Management, Sessions Diagnostics, per-session owner management,
and an in-app per-session **audit-log viewer** with filter
strip. **Sortable tables** (13B) and a full **date / time
display subsystem** (18B — per-operator + per-session
timezones, one canonical render format) round it out. Email is
still staged to a dev outbox; real send activation remains the
**Segment 14B Part A** boundary.

## 2. By the numbers (LOC + counts)

### Code

| Area | LOC | Files | Δ vs 5-11 |
|---|---:|---:|---:|
| `app/services` (business logic) | 18,051 | 25 modules + `rules/` + `instruments/` + `extracts/` packages | +5,055 |
| `app/web` (routes + view-shape adapters) | 15,265 | 4 top-level route files + `routes_operator/` + `views/` | +4,690 |
|  ├ `routes_operator/` (14 slices + `_shared`) | 7,926 | 14 | +2,687 |
|  ├ `routes_reviewer.py` | 1,362 | 1 | +227 |
|  └ `views/` (14 sub-modules) | 5,443 | 14 | +1,589 |
| `app/db/models` (SQLAlchemy 2.x declarative) | 1,316 | 18 files / 20 classes | +92 |
| `app/schemas` (Pydantic shapes) | 505 | 5 | -5 |
| `app/auth` | 153 | 2 | 0 |
| `app/main.py`, `app/config.py` | 154 | 2 | +36 |
| **Total `app/` Python** | **35,515** | — | **+9,879 (+39%)** |
| Alembic migrations | 3,489 | 40 | +346 / +5 files |
| Templates (`*.html`) | 11,876 | 53 | +3,743 / +11 |

### Tests

| Area | LOC | Files | Δ vs 5-11 |
|---|---:|---:|---:|
| Integration | 42,501 | 130 | +15,265 / +45 |
| Unit | 11,699 | 41 | +893 / +3 |
| Helpers + conftest | ~1,050 | ~8 | — |
| **Total tests** | **~55,250** | **~179** | **+16,155 / +48** |

Test/code ratio: **1.56 ×** (up from 1.53 ×). The integration
suite carried most of the growth (+56%) — the Segment 15 family
and the Sys-Admin arc are both heavily route-driven, so their
coverage lands integration-first. The full suite is **1,766
tests, ~90 s** on the session container.

### Documentation

| Area | LOC | Files | Δ vs 5-11 |
|---|---:|---:|---:|
| `spec/` (UI + per-page + reference) | 10,738 | 27 | +1,025 / +5 |
| `guide/` (active plans + roadmap) | 5,771 | 20 | +1,686 / +4 |
| `guide/archive/` (shipped + retired plans) | 37,269 | 75 | +7,143 / +13 |
| `docs/` (subsystem deep-dives + status) | 1,660 | 7 | +128 |
| `CLAUDE.md` / `AGENTS.md` (byte-identical) | ~221 each | 2 | ~0 |
| `README.md` | ~212 | 1 | 0 |

New specs since May 11: `workflow_card.md`, `instruments.md`,
`sort_by_reviewee.md`, `group_scoped_instruments.md`,
`timezone_display.md`. Active `guide/` grew despite heavy
archiving — five upcoming-segment stubs were added or revised
(17B, 18B → done, 18C, 18D, 21, 22) faster than shipped plans
left.

### Surface area

- **~136 HTTP routes** (+~36 vs May 11) — the Sys-Admin pages,
  workflow-card POST endpoints, per-row roster CRUD, library
  save / add actions, the timezone routes.
- **18 model files / 20 mapped classes**, **40 migrations**
  (Pg 16 / SQLite parity). Net +1 model class since May 11
  (`SessionOperator` role-delegation table lit up); the inert
  13D / 13F prep columns kept migration churn near zero.
- **103 audit event types** registered in the `EVENT_SCHEMAS`
  strict-mode registry (+41 since May 11) — every 15-family
  and 16-family emitter registered cleanly.
- **25 service modules** + the `rules/` (2,463 LOC),
  `instruments/` (3,402 LOC), and `extracts/` (583 LOC)
  sub-packages.
- **53 templates** + partials (21 operator partials).
- **~146 PRs** merged across the May 12 → 16 window — the
  Segment 15 family, the 16A/B/C arc, 13B, 18B, plus the
  timezone-display follow-on and the segment-21 stub.

## 3. Compliance against the functional spec

(`guide/archive/functional_spec.md` — moved out of `spec/` on
2026-05-11; §-numbers unchanged.)

### §21 Minimum viable functional release (16 items)

| # | Item | State | Δ vs 5-11 |
|---|---|---|---|
| 1  | Session creation and configuration | ✅ | — |
| 2  | Reviewer upload/edit | ✅ **inline edit shipped (15F)** | **upgraded ⚠️→✅** |
| 3  | Reviewee upload/edit | ✅ **inline edit shipped (15F)** | **upgraded ⚠️→✅** |
| 4  | Single-instrument configuration | ✅ | — |
| 5  | Manual assignment upload/edit | ⚠️ manual-CSV path is **dev-only**; rule-based + relationships is the operator path | — |
| 6  | Full-matrix assignment generation | ✅ (seeded RuleSet) | — |
| 7  | Basic readiness validation | ✅ (15B + 15E broadened the rule set) | — |
| 8  | Email invitations with individualized links | ⚠️ outbox-only until **14B Part A** | — |
| 9  | Microsoft sign-in or unique-link access | ✅ | — |
| 10 | Reviewer tabular response surface | ✅ multi-instrument, page-aware | — |
| 11 | Save and submit | ✅ | — |
| 12 | Operator progress dashboard | ✅ (15E Workflow Card consolidated it) | — |
| 13 | Reminder sending | ⚠️ outbox-only until **14B / 14C** | — |
| 14 | CSV and Excel export | ✅ CSV shipped; Excel never an MVP item | — |
| 15 | Basic audit log | ✅ 103 event types + **in-app viewer shipped (16C MVP)** + filtered CSV | extended (viewer shipped) |
| 16 | Basic retention/deletion workflow | ❌ owned by **Segment 18C** (stub); not started | — |

**Score: 12/16 fully present (+2 — inline roster edit closed
#2 and #3), 3 functionally-present-but-dev-only/outbox (#5,
#8, #13), 1 not implemented (#16).** The remaining four are the
same four flagged on May 11; only the email pair (#8 / #13) and
the retention item (#16) are genuine feature gaps — #5 is a
deliberate UI retirement.

### §22 Expanded release items

| Item | State | Δ vs 5-11 |
|---|---|---|
| Multi-instrument sessions | ✅ schema + reviewer surface + per-instrument assignments (15B) | — |
| Rule-based assignment builder | ✅ | — |
| Pair-level context | ✅ first-class `relationships` table + Setup page | — |
| Assignment preview and dry-run counts | ✅ (per-instrument status blocks, 15B) | — |
| Session cloning | ⚠️ stub plan — **Segment 18A** | — |
| Richer invitation templates | ✅ | — |
| Targeted reminders by completion state | ⚠️ "incomplete" cohort yes; richer slicing owned by **14C** | — |
| Controlled post-activation correction workflows | ✅ | — |
| Richer audit views | ✅ **in-app viewer + filter strip shipped (16C MVP)** | **upgraded ⚠️→✅** |
| Long-format / wide-format export | ✅ | — |
| Settings import (round-trip) | ✅ | — |
| Role delegation among multiple operators | ✅ **shipped (16B)** — per-session owner management | **upgraded ⚠️→✅** |
| Advanced retention policies | ⚠️ stub plan — **Segment 18C** | — |
| Administrative dashboards | ✅ **shipped (16A)** — Sys Admin page: workspace allowlist, Accounts Management, Sessions Diagnostics | **upgraded ⚠️→✅** |

Three §22 items crossed the line since May 11 — all from the
Sys-Admin arc. Five remain open: cloning (18A), targeted
reminders (14C), advanced retention (18C). The expanded-release
surface is now mostly shipped.

### §23 End-to-end acceptance criteria

Items 1–13 work subject to the dev-outbox caveat on #8 / #12.
Item 14 (export complete dataset) is reachable via the Extract
Data tiles + audit-log route — and the per-session CSV
timestamps now localise to the session zone (18B follow-on).
Item 15 (delete or retain per policy) still depends on the
retention/purge tooling not yet built (18C). Item 16 (review
audit records) now has a **full in-app path** — the 16C MVP
viewer with filter strip and pretty-printed detail expander —
not just the CSV export.

## 4. Strengths

1. **The Segment 15 family landed clean.** 15A → 15B → 15C →
   15E → 15F shipped across roughly four calendar days as ~50
   PRs, and the operator surface moved from "functional" to
   "polished" without a single rollback. 15F in particular
   closes the most-cited UX gap from every prior assessment —
   inline per-row roster edit — so an operator no longer
   round-trips a CSV to fix one name.

2. **The Sys-Admin doorway exists now.** For three assessments
   running, segment after segment deferred items "to the Sys
   Admin page." 16A built the page (workspace allowlist,
   Accounts Management, Sessions Diagnostics), 16B added
   per-session role delegation, 16C MVP added the in-app audit
   viewer. The parked tiles now have a home.

3. **The Workflow Card is a genuine UX-architecture win.**
   15E's single persistent card — ten-state cascade, uniform
   seven-stage stepper, the *Activate session* super-button
   that runs generate → validate → activate with per-step
   rollback — replaces a scatter of page-body buttons with one
   coherent operator mental model. The design evolved across
   ~12 PRs and the final contract is captured authoritatively
   in `spec/workflow_card.md`.

4. **Audit-event discipline scaled again.** 62 → **103**
   registered event types under the canonical envelope, strict
   mode still catching drift. Roughly 40 new emitters across
   the 15- and 16-families all registered against
   `EVENT_SCHEMAS` cleanly.

5. **The three-layer + view-adapter seam held under heavy
   pressure.** `routes_operator/` grew +2,687 LOC and `views/`
   +1,589 — and both stayed split (14 sub-modules each); no
   monolith re-formed. New feature areas (`_sys_admin`,
   workflow card) slotted into the existing package shapes.

6. **Tests scaled with code.** Ratio held at **1.56 ×** while
   production code grew 39%. The integration suite (+15k LOC)
   carried the route-heavy 15/16 work; 1,766 tests run in
   ~90 s.

7. **Date / time done as one coherent subsystem.** 18B
   standardised every render site on one format via
   `date_formatting.py`, added per-operator + per-session
   timezones with a clean resolution order, and — in the
   follow-on this week — got its principles written up as a
   standalone `spec/timezone_display.md`. A textbook
   cross-cutting refactor.

8. **Cadence held.** ~146 PRs over five days, still
   small-and-reviewable — the largest segment (15E) landed as
   ~12 PRs rather than one big drop.

9. **Spec discipline intact.** `spec/` is now 27 files; every
   shipped segment that locked a contract wrote it down
   (`workflow_card.md`, `instruments.md`, `timezone_display.md`
   are all new since May 11).

## 5. Weaknesses and gaps

1. **Email is *still* not actually sent.** Unchanged across
   three assessments. #8 (invitations) and #13 (reminders)
   stop at `email_outbox.status="queued"`. This is now the
   single largest — and increasingly conspicuous — gap:
   everything *around* the send path is polished, hardened,
   and tested, and the path itself is inert. **Segment 14B
   Part A is the one thing standing between "demo" and
   "pilot."**

2. **Retention / purge still not built.** §21 #16 / §23 #15.
   Segment 18C owns it as a stub; no implementation, no
   scheduled cadence.

3. **Large files are creeping.** `_setup_rosters.py` is now
   **1,759 LOC** (15F's per-row CRUD bloated it),
   `session_config_io.py` 1,733, `_instruments.py` 1,398.
   Three files over 1.3k, none on a split plan. The
   `_instruments.py` warning from May 11 went unaddressed and
   `_setup_rosters.py` overtook it.

4. **Manual-assignment path lingers in dev-only limbo.**
   Unchanged from May 11 — schema supports it, test helpers
   exercise it, operators can't reach it. Either delete it or
   repromote it as a documented Sys-Admin escape hatch.

5. **`guide/archive/` keeps ballooning** — **37,269 LOC / 75
   files** (+24% since May 11). The "compression would matter
   at scale" note is now three assessments old. Not yet a real
   problem; still drifting the wrong way.

6. **Production hardening (14A) untouched.** Key Vault, VNet,
   soft-delete, full-Postgres pytest — 521-LOC plan, not
   started. It gates pilot-readiness alongside email.

7. **Reviewer surface still plain HTML.** AG Grid + cell
   autosave (renumbered 17A → **22** this week) is still
   deferred; the reviewer table is `<input>` / `<textarea>` /
   `<select>` with form-based save.

8. **The reviewee is still not an audience.** A whole
   third-audience surface (results-sharing, feedback
   acknowledgement, non-confidential peer review) is only just
   stubbed as **Segment 21** — sizeable greenfield work, no
   implementation.

9. **Test-suite runtime is creeping.** 1,766 tests / ~90 s is
   fine today but has no headroom plan (no parallelisation,
   no split fast/slow tiers). Worth watching as 14B / 21 add
   route-heavy coverage.

10. **Structural caveats unchanged.** No multi-tenant story
    (single-deployment by design); CSRF leans on Easy Auth
    (documented in `docs/authentication.md`); no reviewer
    self-service profile (not an MVP requirement).

## 6. LOC budget estimate to project completion

The May 11 model forecast the 15-family at ~5,400 code /
~8,100 tests; actuals across the whole window were +9,879 code
/ +16,155 tests — but that window also absorbed the unforecast
16-family, 13B, and the entire 18B subsystem. Per-segment the
model held to within its stated ±20%; the tests/code ratio for
new work stayed near **1.0–1.5 ×** depending on how
route-driven the segment was.

Thirteen segments remain (per `guide/todo_master.md`):

| Segment | Est. code | Est. tests | Migrations |
|---|---:|---:|---:|
| 13C — enhanced instruments | ~1,000 | ~1,500 | 0 (inert col) |
| 13F (PRs 3-5) — DB prep | ~400 | ~400 | 2-3 |
| 14A — production hardening | ~1,500 | ~600 | 0-1 |
| 14B — email infra (Parts A → E) | ~1,800 | ~2,000 | 0 |
| 14B — email infra (Parts F → H, optional backends) | ~1,800 | ~1,500 | 0 |
| 14C — reminders workflow | ~1,200 | ~1,400 | 0-1 |
| 17B — reviewer surface refinements | ~400 | ~400 | 0 |
| 18A — session cloning + tagging + archiving | ~1,300 | ~1,500 | 0-1 |
| 18C — retention / deletion workflow | ~900 | ~1,000 | 0-1 |
| 18D — export / import update | ~700 | ~900 | 0 |
| 19 — spec documentation | n/a (docs) | n/a | 0 |
| 20 — operator polish + docs | ~500 | ~400 | 0 |
| 21 — peer review enhancements (reviewee surface) | ~2,500 | ~2,500 | 1-2 |
| 22 — AG Grid replacement | ~1,800 | ~600 | 0 |
| **Total remaining** | **~16,300** | **~15,100** | **~5-9** |

### Likely shape at completion

| Area | Today | At completion (estimate) | Δ |
|---|---:|---:|---:|
| `app/` Python | 35,515 | **~51,000** | +44% |
| Tests Python | 55,250 | **~70,000** | +27% |
| Templates | 11,876 | **~14,500** | +22% |
| Alembic migrations | 40 files / 3,489 LOC | **~46 / ~3,900** | +15% |
| Specs | 10,738 | **~13,500** | +26% |
| Guides (active + archive) | 43,040 | **~45,000** | +5% |
| **Total project (all artifacts)** | **~162k LOC** | **~200k LOC** | **+23%** |

**Production Python at completion: ~50–52k LOC, ~+44% over
today.** The two biggest remaining chunks are now **Segment 21**
(the reviewee surface — a new audience, ~2,500 code / ~2,500
tests) and **Segment 14B** (email infra with all backend
options — ~3,600 code if every backend ships). Estimates carry
roughly **±20%**; the largest unknown is Segment 21, which is
genuine greenfield (new auth posture, new chrome) rather than
the operator-polish breadth that dominated the May 11–16 window
and estimates more reliably.

## 7. Five-day delta summary

What changed between the May 11 baseline and this assessment:

- **The operator surface got polished.** The Segment 15 family
  (15A friendly labels, 15B per-instrument assignments, 15C
  operator libraries, 15E Workflow Card, 15F enhanced Setup
  pages) all shipped.
- **Inline roster edit closed §21 #2 + #3** — the most-cited UX
  gap from every prior assessment.
- **The Sys-Admin arc shipped** — 16A page, 16B role
  delegation, 16C MVP audit viewer — upgrading three §22 items.
- **Date / time became a real subsystem** — 18B, plus the
  `spec/timezone_display.md` follow-on.
- **Sortable tables** (13B) landed across the operator and
  reviewer surfaces.
- **MVP score: 10 → 12 of 16.** Audit event types 62 → 103;
  routes ~100 → ~136; production Python +39%.
- **AG Grid renumbered 17A → 22; Segment 21 (peer review /
  reviewee surface) stubbed.**

## 8. One-line verdict

A disciplined, well-tested, well-documented FastAPI monolith at
**~35.5k LOC of production code (+39% in five days)**, **~55k
LOC of tests (1.56 × ratio)**, with the **operator surface now
genuinely polished** and **12 of 16 MVP acceptance criteria
fully met (+2)**. The one blocker between "runs locally,
fully featured" and "runs a real pilot" is unchanged and now
starkly isolated: **email send activation (Segment 14B Part A)**
— with production hardening (14A) and retention tooling (18C)
the next two pilot gates behind it.
