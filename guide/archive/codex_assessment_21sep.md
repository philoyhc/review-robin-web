# Codex codebase assessment — 2026-09-21

**Snapshot:** `8dee36e3` on 2026-09-21 UTC, after Segment 19R Item 8. This is
a fresh-context whole-repository assessment, not an amendment to the 18
September read. I read the application seams, schema and migrations, operator
and participant surfaces, tests, workflows, live specifications, active plans,
roadmap, deferred ledger, operational documents, and the changes since the
previous Codex snapshot. Quantitative results use git-tracked files and the
classification in `guide/assessment.json`.

## Executive assessment

Review Robin Web remains **ready for an institutional pilot and overdue for the
evidence only that pilot can provide**. In three days it materially improved
its measured scale behavior and corrected several real workflow defects. At the
current 200 × 200 full-matrix benchmark, the formerly slow operator pages are
near or below the one-second target except Invitations and Responses at roughly
1.4–1.5 seconds. The suite passes **4,636 tests with 16 skips and no xfails**;
lint is clean; CI retains a separate Postgres 16 migration round-trip.

The earlier recommendation to stop broad local refinement was not followed.
The result is not wasted work: a benchmark found row-loading counts, quadratic
staleness evaluation, 2,000-query rollups, and repeated validation loads, and
the fixes are substantive. But the work also reinforces the earlier warning.
Since the 18 September snapshot, 260 commits changed 205 files, adding 20,391
lines and deleting 2,601. Multiple item closes report incorrect blast-radius
counts, vacuous fixtures, incomplete guards, and prose corrections that had to
be repeated across several locations. Review is catching these failures, but it
is catching them after a very high rate of change.

The next move should not be another open-ended local improvement container.
Close Segment 19R at its existing eight completed items, deploy, and let observed
institutional behavior decide what resumes. Keep measured later candidates in
`guide/app_responsiveness.md`; do not turn their existence into a queue.

## 1. Repository shape and capability

The server-rendered FastAPI/Jinja monolith remains the right architecture and
deployment unit. Its four useful seams are intact:

1. `app/web/` handles HTTP, identity dependencies, authorization gates, and
   rendering.
2. `app/services/` owns lifecycle, assignment, validation, response,
   invitation, import/export, visibility, and audit rules.
3. `app/db/models/` plus Alembic own the portable SQLAlchemy schema.
4. `app/web/views/` owns page-shaped read models and presentation decisions.

The application exposes 185 route declarations over 79 migrations. It covers
the full session journey: setup and import, instruments and assignment rules,
generation, validation and preparation, invitations, reviewer response,
operator monitoring, participant results and collation, extracts, configuration
round-trip, rehydrate, audit, retention, and administrative controls. The three
route declarations removed since the prior snapshot belong to the retired
Previews hub; the capability moved to the Invitations reviewer drill-in rather
than disappearing.

No evidence supports a microservice split or a frontend framework. The hottest
recent work improved service queries and cached domain state without changing
the transaction boundary. That is the architecture working as intended.

## 2. Quantitative baseline

Physical lines in git-tracked files at the snapshot, before this assessment was
added:

| Area | Files | LOC | Change from 18 September |
| --- | ---: | ---: | ---: |
| Production Python | 205 | **63,541** | +1,886 |
| Jinja templates | 60 | **29,161** | +239 |
| Tests | 363 | **129,731** | +8,276 |
| Alembic migrations | 79 | **6,917** | +145 |
| Tooling | 18 | **16,444** | +1,477 |
| Documentation/spec/guide | 268 | **170,163** | +5,764 |

The test-to-production ratio is **2.04×**, up from 1.97×. The added tests are
mostly parity oracles, query/ORM budgets, upload-route discovery, cross-roster
identity cases, and migration coverage. Those are appropriate for the rewrites,
but the item records show why count is not confidence: several guards initially
passed without reaching the behavior they claimed to protect. New high-risk
tests should continue to prove fixture reachability and survive a targeted
mutation.

### Largest production modules

| LOC | Module | Assessment |
| ---: | --- | --- |
| 1,300 | `app/services/validation.py` | Now the largest module after the report-context rewrite; registry-driven, but the next validation behavior change should test whether loading/report construction can separate cleanly. |
| 1,279 | `app/web/routes_operator/_instruments.py` | Stable and still below its existing 1,400-line split trigger. |
| 1,246 | `app/services/csv_imports.py` | Grew with count and upload-label corrections; split only along a changed format boundary. |
| 1,119 | `app/services/assignments/_generate.py` | Generation remains cohesive; cache stamping increased its responsibility but belongs on this write boundary. |
| 1,109 | `app/web/routes_operator/_operations.py` | Invitations and Responses still make this the clearest route-family split candidate if either surface changes materially. |
| 1,109 | `app/services/responses/_core.py` | Group-aware counting and response semantics remain tightly coupled; no size-only split. |
| 1,107 | `app/services/session_lifecycle.py` | Cohesive state machine; keep intact. |
| 1,066 | `app/services/instruments/_band1.py` | Dense feature module inside an existing package boundary. |
| 1,061 | `app/web/routes_operator/_shared.py` | Still the module to watch for unrelated concerns becoming a dependency sink. |
| 1,049 | `app/web/views/_instruments.py` | Dense view adapter matching a dense page. |

There is no compelling standalone file split. `validation.py` crossed the prior
list because it now builds one shared report context rather than having every
rule reload its inputs. Splitting that immediately would risk hiding the reuse
the optimization made explicit.

### Duplication and churn

`python3 tools/code_metrics.py` reports **6.3% application duplication at
blocks of 10 or more lines** (3,234 of 50,977 code lines), down from 6.5%.
Test duplication is **13.0%**, down from 13.6%. Both changes are below the
repository's action thresholds. The setup roster routes remain the leading
application cluster at 34–47%; their shared visual shape still does not erase
their different lifecycle and mutation rules.

Churn could not be measured: this checkout is shallow and the tool correctly
refused to manufacture a 1.0× result from truncated blame history. This
assessment therefore makes no churn or baseline-ratio claim.

## 3. What changed materially

The strongest change is that performance work began from a reproducible
Postgres benchmark rather than file size or intuition. Segment 19R replaced
row-fetching counts with SQL counts, cached the expensive reconcile verdict at
the assignment-generation boundary, rolled reviewer/reviewee progress up in
SQL, and stopped validation rules from rebuilding the same report inputs. At
the original 1,000 × 1,000 fixture, caching reduced Session Home from 11.9
seconds to 0.67, Assignments from 13.1 to 0.67, and Validate from 14.0 to 0.99.
At the reset 200 × 200 full-matrix fixture, Invitations and Responses fell to
roughly 1.36 and 1.52 seconds with flat query counts.

The cache design is appropriately conservative: mutations stamp or invalidate
it, reads may recompute inside a request, and the durable warm state comes from
the write boundary rather than a GET committing. Four scalar columns are less
elegant than an opaque blob but portable, inspectable, and migration-tested.
The remaining SQLite `count + max(id)` invalidation limitation is documented;
it is a development-dialect edge, not hidden certainty.

Correctness work was equally important. Quick Setup now preserves imported
friendly field labels on every roster-saving upload path, instrument numbering
is session-local, invitation creation occurs in Prepare, send eligibility is
shared, and the dead Previews hub no longer offers a parallel workflow. The
upload regression produced a useful general guard that discovers file-upload
routes from the router rather than relying on a hand-maintained endpoint list.

## 4. Maintainability and UI

The largest templates remain `operator/instruments_index.html` (5,642 lines)
and `base.html` (5,320), followed by `operator/session_extract_data.html`
(2,664). Their sizes barely moved. The recent risk was not new template mass but
behavior distributed between templates, base-level scripts, route context, and
source guards. Component extraction should remain change-driven: move one whole
interaction, including its context contract and tests, when that interaction
next changes.

The UI is more internally consistent: Previews was retired, the Guide and
workflow card now teach Prepare and Invitations as the same path, session-local
instrument numbering reaches operator surfaces, and wide tables consistently
use the shared scroll wrapper. The screenshot corpus was refreshed and checked
for paired light/dark provenance.

Static accessibility evidence remains strong: semantic tokens and both themes
are machine-checked. It is still static evidence. Keyboard flow, focus behavior,
screen-reader output, responsive behavior, real browser history, and
progressive-enhancement failures need a deployed browser. No structural test
can close that gap.

## 5. Test and delivery confidence

The suite is broad and green, Node is present so inline-script parsing ran, and
Postgres-specific behavior has dedicated query-budget and migration tests.
Parity oracles now hold the SQL rollups against the previous Python answers,
and route-discovery guards reduce the chance that a newly added upload path
silently escapes coverage.

The correction record is the important qualifier. Across the eight 19R items,
reviews found fixtures with no relevant rows, source recognizers that missed
valid Python annotation shapes, query guards whose exemption was too broad,
blast-radius commands that counted the wrong twin helper, and causal prose
inferred from a cache key's deliberately wider inputs. None remains open, but
the pattern is consistent: the repository's risk is not absence of checks; it
is writing checks and claims faster than their premises are verified.

Keep the current item-level cold-read cadence. For the next code slice, require
three pieces of evidence before calling a guard complete: the fixture reaches
the case, a mutation of the protected property fails, and the recognizer is
tested outside the current production examples. More tests without those
properties would increase maintenance faster than confidence.

## 6. Security and operations

Authorization remains strong for a pilot: deployed identity is delegated to
Easy Auth, session-scoped denials resist enumeration, role gates are explicit,
participant reachability follows roster identity and status, and audit events
have validated envelopes. Recent identity work also aligns cross-roster
case-folding and records the ASCII/Unicode boundary instead of implying perfect
cross-dialect equivalence.

Operational risk is still the dominant risk:

- real Easy Auth claims and institutional role landing remain unproved;
- external email delivery is not active;
- backup/restore has not been rehearsed;
- Application Insights is not provisioned;
- Postgres networking and secrets remain below a mature production posture;
- stylesheet compression, real transfer size, browser behavior, and intended
  roster latency await the Azure slot.

These are not code-review findings. They require the environment. The
post-Azure checklist already names the evidence, so another local abstraction
or visual refinement should not displace it.

## 7. Documentation and process

The documentation system remains unusually capable: live-path and section
references, guide indexes, close manifests, generated artifacts, contrast, and
constant-derived conventions are executable. The latest work also added useful
practice tooling and corrected the instruction-timestamp campaign record.

Its cost remains high. Documentation/spec/guide is now 170,163 lines. Segment
19R's plan alone is over 1,500 lines for eight completed items and one moved
item, despite the stated preference for short plans and compact closes. The
content records valuable failures, but much of it is an incident narrative
rather than a plan a future maintainer can scan. When 19R closes, preserve the
measured outcomes and reusable lessons, then archive it; do not add another
item merely because the file is already open.

The campaign-stamp finding is representative: 37 commits wrote an
`Instruction-Received` line, only 16 parsed as trailers, and only 14 entered the
split. The repository correctly retired the standing instruction rather than
building another gate around a measurement campaign. Apply the same restraint
to assessment findings: a measurement is not automatically a backlog item.

## 8. Recommended next moves

### 1. Close Segment 19R now

All eight built items are closed and Item 9 moved to the deferred ledger
unbuilt. Correct the stale opening paragraph that still says Item 5 is open,
compact the durable conclusions, archive the plan, and stop using it as an
open-ended intake channel. Route a genuine defect directly; require a separate,
bounded plan for anything larger.

### 2. Deploy and execute the institutional evidence checklist

Run the NUS deployment path with representative data. Verify real identity
headers and every role landing; the operator-to-reviewer-to-results journey;
email decisions; browser and accessibility behavior; query/latency figures;
logging; transfer compression; and restore. Record observed failures, not
anticipated polish.

### 3. Preserve, but do not pre-schedule, the measured later candidates

`guide/app_responsiveness.md` is the right home for bulk assignment insertion,
remaining page furniture, and other measured candidates. Promote one only when
pilot scale or an operator report crosses its stated trigger. Invitations and
Responses at roughly 1.5 seconds are not a reason to optimize blindly before
network and browser measurements exist.

### 4. Let the next failure choose the structural seam

If validation changes again, consider separating report-input loading from rule
evaluation. If Invitations or Responses changes materially, consider splitting
`_operations.py`. If a large template interaction changes, extract that whole
component. None is currently valuable as a size-only cleanup.

## Bottom line

Review Robin Web is healthy, broad, and technically ready for pilot use. The
last three days replaced serious scale costs with measured, tested mechanisms
and fixed real workflow defects. They also showed a development process running
at a pace where measurements, guards, and prose repeatedly need correction.
The right response is not more machinery and not another refinement segment.
Close the open container, deploy the product, rehearse recovery, observe real
users and real identity, and let that evidence earn the next change.
