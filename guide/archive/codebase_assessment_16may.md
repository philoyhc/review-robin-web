# Codebase assessment — 2026-05-16

**As of:** end of the **Segment 15 family** (15A friendly labels →
15B per-instrument assignments → 15C operator libraries → 15E
Operations Workflow Card → 15F enhanced Setup pages), the
**Sys-Admin arc** (16A Sys Admin page → 16B role delegation →
16C MVP in-app audit viewer), **13B** sortable tables, **Segment
18B** date / time settings, and **Segment 17A** housekeeping
(file splits + test-suite runtime). Five days after the
[2026-05-11 assessment](codebase_assessment_11may.md). Numbers
taken on `main` at commit `a6f8e6e`. Citizen project,
single-author + AI-agent cadence; not yet pilot-deployed.

This is an audit-style snapshot. Authoritative ship-state lives
in `docs/status.md`; this document re-baselines the May 11
assessment after a heavy five-day landing window (~152 PRs).
The functional spec it audits against has moved —
`spec/functional_spec.md` was relocated to
`guide/archive/functional_spec.md` on 2026-05-11; section
numbers (§21 / §22 / §23) are unchanged.

> **History note.** The visible git history was linearised at
> some point after the May 11 assessment — the pre-`2026-05-12`
> commits (including the `b46081d` baseline the last assessment
> cited) are no longer ancestors of `main`. The visible tree
> spans 2026-05-12 → 2026-05-16, which covers the whole
> inter-assessment window. Exact commit-level archaeology across
> the May 11 boundary is lossy.

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
timezones, one canonical render format) round out the feature
work, and **Segment 17A** closed the window with a pure-structure
housekeeping pass — file splits + a parallelised test suite.
Email is still staged to a dev outbox — **deliberately**: the
production transport shape awaits the host institution's IT
decision among the Option B–D backends (§5, weakness 1), so the
rest of the system was built out first.

## 2. By the numbers (LOC + counts)

### Code

| Area | LOC | Files | Δ vs 5-11 |
|---|---:|---:|---:|
| `app/services` (business logic) | 18,123 | 24 modules + `rules/` + `instruments/` + `extracts/` + `session_config_io/` packages | +5,127 |
| `app/web` (routes + view-shape adapters) | 15,412 | 4 top-level route files + `routes_operator/` + `views/` | +4,837 |
|  ├ `routes_operator/` (16 slices + `_shared`) | 8,073 | 18 | +2,834 |
|  ├ `routes_reviewer.py` | 1,362 | 1 | +227 |
|  └ `views/` (14 sub-modules) | 5,443 | 15 | +1,589 |
| `app/db/models` (SQLAlchemy 2.x declarative) | 1,316 | 18 files / 20 classes | +92 |
| `app/schemas` (Pydantic shapes) | 505 | 5 | -5 |
| `app/auth` | 153 | 2 | 0 |
| `app/main.py`, `app/config.py` | 154 | 2 | +36 |
| **Total `app/` Python** | **35,734** | — | **+10,098 (+39%)** |
| Alembic migrations | 3,489 | 40 | +346 / +5 files |
| Templates (`*.html`) | 11,876 | 53 | +3,743 / +11 |

### Tests

| Area | LOC | Files | Δ vs 5-11 |
|---|---:|---:|---:|
| Integration | 42,496 | 130 | +15,260 / +45 |
| Unit | 11,699 | 41 | +893 / +3 |
| Helpers + conftest | ~1,138 | ~9 | +1 (`tests/_sqlite_schema.py`) |
| **Total tests** | **~55,333** | **180** | **+16,238 / +49** |

Test/code ratio: **1.55 ×** (vs 1.53 × on May 11). The
integration suite carried most of the growth (+56%) — the
Segment 15 family and the Sys-Admin arc are both heavily
route-driven, so their coverage lands integration-first. The
full suite is **1,767 tests**; Segment 17A parallelised it with
`pytest-xdist`, so it now runs in **~22 s** on the session
container (down from ~90 s single-process).

### Documentation

| Area | LOC | Files | Δ vs 5-11 |
|---|---:|---:|---:|
| `spec/` (UI + per-page + reference) | 10,746 | 27 | +1,033 / +5 |
| `guide/` (active plans + roadmap) | 6,335 | 21 | +2,250 / +5 |
| `guide/archive/` (shipped + retired plans) | 37,453 | 76 | +7,327 / +14 |
| `docs/` (subsystem deep-dives + status) | 1,661 | 7 | +129 |
| `CLAUDE.md` / `AGENTS.md` (byte-identical) | 224 each | 2 | ~0 |
| `README.md` | 225 | 1 | +13 |

New specs since May 11: `workflow_card.md`, `instruments.md`,
`sort_by_reviewee.md`, `group_scoped_instruments.md`,
`timezone_display.md`. Active `guide/` grew despite heavy
archiving — upcoming-segment stubs (17B, 18C, 18D, 21) and the
2026-05-16 codebase assessment were added faster than shipped
plans (17A, 18B) left for `archive/`.

### Surface area

- **~143 HTTP routes** (+~43 vs May 11) — the Sys-Admin pages,
  workflow-card POST endpoints, per-row roster CRUD, library
  save / add actions, the timezone routes.
- **18 model files / 20 mapped classes**, **40 migrations**
  (Pg 16 / SQLite parity). Net +1 model class since May 11
  (`SessionOperator` role-delegation table lit up); the inert
  13D / 13F prep columns kept migration churn near zero.
- **103 audit event types** registered in the `EVENT_SCHEMAS`
  strict-mode registry (+41 since May 11) — every 15-family
  and 16-family emitter registered cleanly.
- **24 service modules** + the `rules/` (2,463 LOC),
  `instruments/` (3,402 LOC), `extracts/` (583 LOC) and
  `session_config_io/` (1,805 LOC) sub-packages — the last
  promoted from a flat module by Segment 17A.
- **53 templates** + partials (21 operator partials).
- **~152 PRs** merged across the May 12 → 16 window — the
  Segment 15 family, the 16A/B/C arc, 13B, 18B, the
  timezone-display follow-on, the segment-21 stub, and the six
  Segment 17A housekeeping PRs.

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
| 5  | Manual assignment upload/edit | ✅ delivered via the rule engine + Relationships table; the literal manual-CSV upload path was **fully retired** by design (16A PR 5, 2026-05-11) | **corrected** — May 11 mis-stated this as a lingering dev-only path |
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

**Score: 13/16 fully present, 2 outbox-only (#8, #13), 1 not
implemented (#16).** Two items crossed the line via 15F inline
roster edit (#2, #3). #5 is re-scored ✅: the May 11 assessment
mis-stated the manual-CSV path as a lingering dev-only escape
hatch, but 16A PR 5 retired it outright — the rule engine +
Relationships table fully cover precise operator control of who
reviews whom. The only genuine feature gaps left are the email
pair (#8 / #13, outbox-only until 14B Part A) and retention
(#16, not built).

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
Sys-Admin arc. Open: cloning (18A), targeted reminders (14C),
advanced retention (18C). The expanded-release surface is now
mostly shipped.

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
   pressure — and was actively maintained.** `routes_operator/`
   grew +2,834 LOC and `views/` +1,589, and both stayed split;
   no monolith re-formed. When three files did drift past
   ~1.3k LOC, **Segment 17A re-split them cleanly** —
   `_setup_rosters.py` into three per-page slices,
   `session_config_io.py` into a package, the Response Type
   routes out of `_instruments.py` — all pure-structure PRs with
   the suite passing unchanged. The operator package is now 16
   feature slices; no `app/` production file is over ~1,200 LOC
   without a deliberate reason.

6. **Tests scaled with code, and the suite stays fast.** Ratio
   held at **1.55 ×** while production code grew 39%. The
   integration suite (+15k LOC) carried the route-heavy 15/16
   work. Segment 17A parallelised the run with `pytest-xdist`
   and swapped the SQLite path's migration replay for
   `create_all` — 1,767 tests now run in **~22 s** (was ~90 s),
   with real headroom for the route-heavy 14B / 21 coverage to
   come.

7. **Date / time done as one coherent subsystem.** 18B
   standardised every render site on one format via
   `date_formatting.py`, added per-operator + per-session
   timezones with a clean resolution order, and — in the
   follow-on this week — got its principles written up as a
   standalone `spec/timezone_display.md`. A textbook
   cross-cutting refactor.

8. **Cadence held, and the codebase acts on its own audits.**
   ~152 PRs over five days, still small-and-reviewable — the
   largest segment (15E) landed as ~12 PRs rather than one big
   drop. When this very assessment flagged three oversized
   files and a creeping suite runtime, Segment 17A shipped the
   fixes the same day as five tightly-scoped PRs.

9. **Spec discipline intact.** `spec/` is now 27 files; every
   shipped segment that locked a contract wrote it down
   (`workflow_card.md`, `instruments.md`, `timezone_display.md`
   are all new since May 11).

## 5. Weaknesses and gaps

1. **Email send is deliberately deferred — not neglected.**
   #8 (invitations) and #13 (reminders) still stop at
   `email_outbox.status="queued"`. It is the largest
   *functional* gap, and it remains the last pilot
   prerequisite — but the deferral is a sound sequencing
   decision, not a slip. The **backend shape is gated on an
   external dependency**: institutional Microsoft 365 tenants
   typically block basic SMTP AUTH, so the production
   transport must be one of Options B–D in
   `spec/email_infra_options.md` (Graph / ACS / third-party),
   and *which* one is the host institution's IT decision to
   make. Building the rest of the system first — while that
   decision is pending — is the right call. The groundwork is
   already laid so the wait costs nothing: the pluggable
   `EmailTransport` interface (11E) and the `email_outbox`
   audit-log schema (11C Part 2) are in place, so Segment 14B
   Part A is a backend driver slotting into a ready seam
   rather than a from-scratch build. The risk to watch is
   simply that the IT decision stays open long enough to
   become the critical path to a pilot date.

2. **Retention / purge still not built.** §21 #16 / §23 #15.
   Segment 18C owns it as a stub; no implementation, no
   scheduled cadence.

3. **Production hardening (14A) untouched.** Key Vault, VNet,
   soft-delete, full-Postgres pytest — 521-LOC plan, not
   started. It gates pilot-readiness alongside email.

4. **Reviewer surface still plain HTML, no autosave.** The
   reviewer table is `<input>` / `<textarea>` / `<select>` with
   per-page form-based save. The large-table ergonomics
   (cell-level autosave, sticky headers, visible progress) are
   owned by **Segment 17B** as vanilla progressive enhancement
   — the AG Grid framing was taken off the roadmap (see
   `guide/future_possibilities.md`). One structural note for
   17B: `app/web/routes_reviewer.py` (1,362 LOC) is still a
   single file rather than a package — unlike the operator
   side — so converting it to a `routes_reviewer/` package is
   the natural first step of 17B before the surface grows.

5. **The reviewee is still not an audience.** A whole
   third-audience surface (results-sharing, feedback
   acknowledgement, non-confidential peer review) is only just
   stubbed as **Segment 21** — sizeable greenfield work, no
   implementation.

6. **`guide/archive/` keeps ballooning** — **37,453 LOC / 76
   files** (+24% since May 11). The "compression would matter
   at scale" note is now three assessments old. Not yet a real
   problem; still drifting the wrong way.

7. **Structural caveats unchanged.** No multi-tenant story
   (single-deployment by design); CSRF leans on Easy Auth
   (documented in `docs/authentication.md`); no reviewer
   self-service profile (not an MVP requirement).

Two weaknesses from the morning's draft of this assessment —
oversized files and a slow test suite — are **not listed above
because Segment 17A resolved them the same day** (see strengths
5 and 6).

## 6. LOC budget estimate to project completion

The May 11 model forecast the 15-family at ~5,400 code /
~8,100 tests; actuals across the whole window were +10,098 code
/ +16,238 tests — but that window also absorbed the unforecast
16-family, 13B, the entire 18B subsystem, and the 17A
housekeeping pass. Per-segment the model held to within its
stated ±20%; the tests/code ratio for new work stayed near
**1.0–1.5 ×** depending on how route-driven the segment was.

Twelve segments remain (per `guide/todo_master.md`; Segment 17A
shipped 2026-05-16 and is no longer listed):

| Segment | Est. code | Est. tests | Migrations |
|---|---:|---:|---:|
| 13C — enhanced instruments | ~1,000 | ~1,500 | 0 (inert col) |
| 13F (PRs 3-5) — DB prep | ~400 | ~400 | 2-3 |
| 14A — production hardening | ~1,500 | ~600 | 0-1 |
| 14B — email infra (Parts A → E) | ~1,800 | ~2,000 | 0 |
| 14B — email infra (Parts F → H, optional backends) | ~1,800 | ~1,500 | 0 |
| 14C — reminders workflow | ~1,200 | ~1,400 | 0-1 |
| 17B — reviewer surface refinements + ergonomics | ~900 | ~900 | 0 |
| 18A — session cloning + tagging + archiving | ~1,300 | ~1,500 | 0-1 |
| 18C — retention / deletion workflow | ~900 | ~1,000 | 0-1 |
| 18D — export / import update | ~700 | ~900 | 0 |
| 19 — spec documentation | n/a (docs) | n/a | 0 |
| 20 — operator polish + docs | ~500 | ~400 | 0 |
| 21 — peer review enhancements (reviewee surface) | ~2,500 | ~2,500 | 1-2 |
| **Total remaining** | **~14,500** | **~14,600** | **~3-9** |

Segment 17A is absent from the table because it shipped — and
it was LOC-neutral anyway: file splits move code rather than add
it, so its net production-code delta was roughly zero (a new
~70-LOC `tests/_sqlite_schema.py` helper plus small `conftest` /
`pyproject` edits).

### Likely shape at completion

| Area | Today | At completion (estimate) | Δ |
|---|---:|---:|---:|
| `app/` Python | 35,734 | **~50,500** | +41% |
| Tests Python | 55,333 | **~70,000** | +27% |
| Templates | 11,876 | **~14,500** | +22% |
| Alembic migrations | 40 files / 3,489 LOC | **~46 / ~3,900** | +15% |
| Specs | 10,746 | **~13,500** | +26% |
| Guides (active + archive) | 43,788 | **~45,500** | +4% |
| **Total project (all artifacts)** | **~163k LOC** | **~200k LOC** | **+23%** |

**Production Python at completion: ~50–51k LOC, ~+41% over
today.** The two biggest remaining chunks are **Segment 21**
(the reviewee surface — a new audience, ~2,500 code / ~2,500
tests) and **Segment 14B** (email infra). The 14B figure above
assumes every backend ships, which it likely will not — the
host institution's IT decision picks the production transport,
so in practice one or two of the Option B–D drivers land, not
all three; treat ~1,800–2,800 code as the realistic 14B range.
Estimates carry roughly **±20%**; the largest unknown is
Segment 21, which is genuine greenfield (new auth posture, new
chrome) rather than the operator-polish breadth that dominated
the May 11–16 window and estimates more reliably.

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
- **Segment 17A housekeeping** closed the window — five
  pure-structure PRs split the three oversized files
  (`_setup_rosters.py`, `session_config_io.py`,
  `_instruments.py`) and parallelised the test suite (~90 s →
  ~22 s).
- **MVP score: 10 → 13 of 16.** Audit event types 62 → 103;
  routes ~100 → ~143; production Python +39%.
- **Roadmap reshaped.** Segment 21 (peer review / reviewee
  surface) stubbed; the recycled 17A slot was used for the
  housekeeping segment and has now shipped; the AG Grid
  replacement was taken off the roadmap as overkill (now an
  aspirational item in `guide/future_possibilities.md`), its
  reviewer-surface ergonomics folded into 17B.

## 8. One-line verdict

A disciplined, well-tested, well-documented FastAPI monolith at
**~35.7k LOC of production code (+39% in five days)**, **~55k
LOC of tests (1.55 × ratio, ~22 s suite)**, with the **operator
surface now genuinely polished**, **13 of 16 MVP acceptance
criteria fully met**, and no production file left oversized
after the 17A housekeeping pass. The last functional gap before
a real pilot — **email send activation (Segment 14B Part A)** —
is deliberately deferred, not stalled: its backend shape awaits
the host institution's IT decision among the Option B–D
transports, the pluggable seam for it is already built, and the
rest of the system was sequenced ahead of it on purpose.
Production hardening (14A) and retention tooling (18C) are the
next two pilot gates.
