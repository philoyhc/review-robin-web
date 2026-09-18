# Codex codebase assessment — 2026-09-18

**Snapshot:** `5ee6b6be` on 2026-09-18, after Segment 19Q Item 2. This is
a fresh-context assessment of the repository, not an update to the 12 September
read. I read the application seams, models and migrations, operator and
participant surfaces, tests, workflows, live specifications, current plans,
roadmap, deferred ledger, security posture, and known limitations. Quantitative
results use git-tracked files and the classification in `guide/assessment.json`.

## Executive assessment

Review Robin Web remains a **pilot-ready application awaiting a pilot
environment, not a prototype awaiting features**. Its domain coverage is broad,
its authorization and mutation boundaries are explicit, and its executable
documentation is unusually strong. A fresh full run passes **4,384 tests with
16 skips and no xfails**; lint is clean; CI separately exercises Postgres 16 and
the full migration round-trip.

The largest risk is now the development system around the application. Six
days of work took the suite from 3,847 recorded passes to 4,384 and completed
large roster, workflow, preview, identity, and documentation arcs. That work
found real defects, including an email action whose visible table and recipient
set disagreed. It also produced a very high correction rate: repeated cold reads
found vacuous tests, guards that asserted spellings rather than properties,
prose overclaims, and fixes that moved defects instead of removing them. The
reviews are doing useful work, but the frequency of their findings says the
repository is operating near the limit of how much change its current cadence
can safely absorb.

The recommendation is therefore sharper than it was on 12 September: **finish
the already-open Guide item, stop opening operator-UI refinements, deploy, and
turn the next evidence into operational rather than cosmetic work**. Another
broad improvement segment before institutional deployment would optimize an
already-complete surface while the largest risks—real identity headers,
delivery, restore, monitoring, latency, and accessibility in a browser—remain
unmeasured.

## 1. Repository shape

The server-rendered FastAPI/Jinja monolith is still the correct architecture.
The application has four effective seams:

1. `app/web/` parses requests, resolves identity, enforces route access, and
   renders responses.
2. `app/services/` owns lifecycle, assignment, invitation, response,
   visibility, extract, import, and audit rules.
3. `app/db/models/` and Alembic own the portable SQLAlchemy schema.
4. `app/web/views/` turns domain state into page-specific render shapes.

The system exposes 188 routed endpoints over 77 migrations. It supports the
complete session journey: roster and instrument setup, per-instrument
assignments, validation and preparation, reviewer responses, operator
monitoring, reviewee results, observer collation, extracts, configuration
round-trip, rehydrate, audit, and administrative controls. Email composition
and outbox state exist; external dispatch remains intentionally gated on the
institutional host and sending identity.

This remains one product and one transaction boundary. Nothing in the code
suggests a useful microservice split, and adding a frontend framework would
duplicate state and authorization machinery without solving a measured pilot
problem.

## 2. Quantitative baseline

Physical lines in git-tracked files at the snapshot, before this assessment was
added:

| Area | Files | LOC | Change from 12 September |
| --- | ---: | ---: | ---: |
| Production Python | 204 | **61,655** | +2,195 |
| Jinja templates | 60 | **28,922** | +3,621 |
| Tests | 337 | **121,455** | +16,333 |
| Alembic migrations | 77 | **6,772** | unchanged |
| Tooling | 15 | **14,967** | +1,455 |
| Documentation/spec/guide | 259 | **164,399** | +11,556 |

The test-to-production ratio is **1.97×**, up from 1.77×. That is not itself a
problem: the latest UI work added structural, mutation, and regression guards
faster than runtime code. It is, however, a signal to judge new tests by the
failure they distinguish rather than by count. Recent history contains several
tests that passed because their fixtures produced no relevant rows, mutations
that went red only because Jinja stopped parsing, and source guards that matched
comments. The repository has already responded with anti-vacuity and parse
checks; those practices are more valuable than another broad increase in test
volume.

### Largest production modules

| LOC | Module | Assessment |
| ---: | --- | --- |
| 1,279 | `app/web/routes_operator/_instruments.py` | Stable large route family; still below its 1,400 split trigger. |
| 1,107 | `app/services/session_lifecycle.py` | Cohesive state machine; keep intact unless a real boundary changes. |
| 1,102 | `app/web/routes_operator/_operations.py` | Now the clearest route split candidate if Invitations or Responses changes again. |
| 1,082 | `app/services/csv_imports.py` | Mature but multi-format; split by format only alongside changed behavior. |
| 1,066 | `app/services/instruments/_band1.py` | Dense feature module with an existing package boundary. |
| 1,061 | `app/web/routes_operator/_shared.py` | Watch closely: a shared module over 1,000 lines can become a dependency sink. |
| 1,049 | `app/web/views/_instruments.py` | Dense view adapter matching the page's density. |
| 1,029 | `app/services/audit.py` | Registry size follows the event vocabulary; no arbitrary split. |
| 1,020 | `app/services/responses/_core.py` | Stable response core; below its existing trigger. |
| 993 | `app/services/validation.py` | Registry-driven and cohesive. |

No file warrants a standalone refactor. `_shared.py` is the new item to watch:
shared route helpers are useful, but once unrelated feature behavior moves
there merely to satisfy the no-slice-import rule, the package has replaced
explicit dependencies with a miscellaneous hub. The trigger should be a new
unrelated concern, not line count alone.

### Duplication and churn

`python3 tools/code_metrics.py` reports **6.5% application duplication at
blocks of 10 or more lines** (3,195 of 49,493 code lines), unchanged from the
established baseline. The four roster route modules are the leading cluster,
at 34–47% duplicated. Their pages now share a visual idiom but retain different
mutation and lifecycle rules; a generic roster controller would be premature.
Extract a helper only when the same behavior must be corrected twice.

Test duplication is **13.6%**, down from the previous 15.0% measure despite the
suite's growth. The deterministic churn measure could not be reproduced:
`tools/code_metrics.py` reported no merge commits on `origin/main` in this
checkout. Accordingly, this assessment makes **no churn claim and no baseline
ratio claim** rather than substituting the sample-dependent mode.

## 3. Functional and architectural assessment

I found no capability represented as shipped but missing in the application.
The recent work made three especially valuable corrections:

- identity matching now has one explicit normalization rule and documents the
  Python/Postgres/SQLite non-ASCII boundary;
- invitation creation moved into Prepare, removing an operator step that
  created an unusable token but sent nothing;
- all send paths now use an assigned-and-active eligibility predicate, closing
  a defect where “Send all” could email a person absent from the table above it.

Those are material improvements, not polish. They also demonstrate why the
service seam matters: the strongest recent fixes replaced repeated route-local
predicates with one service helper.

The documented three-layer rule remains an aspiration with practical
exceptions. Dependencies necessarily query for authorization, view adapters
build efficient read models, and handlers perform scoped lookups. A purity
sweep would create risk without product value. Continue the local rule: when a
query-backed rule is changed, move it behind a service/read-model API if that
prevents a second spelling or makes authorization semantics explicit.

Audit handling is a particular strength. Mutation services emit typed event
envelopes validated against `EVENT_SCHEMAS` in tests, while production does not
lose the underlying mutation solely because diagnostic validation fails. The
schema has grown large but remains centralized and inspectable.

## 4. UI and maintainability

The dominant maintenance cost is Jinja and inline client behavior, not Python:

| LOC | Template | Risk |
| ---: | --- | --- |
| 5,616 | `operator/instruments_index.html` | Multiple editors and client-side state machines in one page. |
| 5,276 | `base.html` | Global CSS, shared primitives, and progressive-enhancement scripts. |
| 2,664 | `operator/session_extract_data.html` | Dense configuration and download surface. |
| 1,665 | `operator/session_observers.html` | Roster, cohort editor, and expander behavior. |
| 1,420 | `operator/session_reviewers.html` | Roster and unlock/row-expander behavior. |

The latest roster-expander work made the visible interaction more coherent, but
it increased the two largest templates and showed how fragile source-string
guards can be. Do not schedule template carving by size alone. When one of
these pages next needs substantive behavior, extract one complete component at
a time—markup, context contract, script entry point, and tests together—rather
than moving fragments merely to lower the headline number.

The static accessibility posture is credible: semantic color roles and 73
foreground/background pairs are machine-checked in both themes. It is still
only static evidence. Keyboard navigation, focus order, screen-reader output,
non-text contrast, JavaScript execution, and browser history remain unmeasured.
The new expanders and dirty-state/sort interactions make a deployed browser
walk more urgent, not less.

## 5. Test and delivery confidence

The suite is broad and freshly green. Unit tests exercise services, parsers,
view adapters, generated artifacts, CSS rules, contrast, and document
conventions. Integration tests cover route authorization and rendered HTML.
Node is present, so the inline-script parse test runs rather than silently
skipping. The separate CI workflows provide the Postgres dialect and Alembic
downgrade/upgrade evidence unavailable from the default SQLite run.

Two limits should stay explicit:

1. Structural assertions over HTML, CSS, and JavaScript are not browser tests.
   Recent fixes to sorting, expander reinjection, unsaved-change confirmation,
   and dynamic toolbars still require the dev slot.
2. The correction record shows that green is not sufficient evidence for a
   newly written guard. For high-risk assertions, keep the current discipline:
   prove the fixture reaches the state, ensure the target parses, mutate the
   property rather than a preferred spelling, and have the item-level cold read
   examine the cumulative result.

The move from per-slice to per-item cold reads is sensible. The previous rate
was generating review prose and correction commits faster than it was improving
the product, while the cumulative read is the one that found a defect spanning
rungs. Preserve an additional read only when later work reopens code after that
item-level review.

## 6. Security and operations

Application authorization is strong for this stage: Easy Auth is the deployed
identity boundary; operator, owner, admin, super-admin, reviewer, reviewee, and
observer gates are explicit; session refusals resist id enumeration; and the
super-admin anchor cannot be removed in-app. The identity-fold consolidation
also records its deliberate ASCII limitation instead of pretending Python and
both databases agree on Unicode casing.

Operational risk remains materially higher than application-code risk:

- there is one dev slot and no production/staging promotion gate;
- Postgres uses public access rather than private networking;
- secrets are App Settings/GitHub secrets rather than Key Vault references;
- Application Insights is not provisioned;
- restore is whole-database and has not been rehearsed;
- retention is operator-driven;
- external email delivery is not active;
- `requirements.txt` and `pyproject.toml` remain manually synchronized.

These are documented limitations, but only deployment work can reduce them.
No amount of template refinement substitutes for a restore drill, real Easy
Auth claims, representative data, logs, or an institutional sending identity.

## 7. Documentation and process

The specification system is a genuine asset: it catches stale paths, indexes
plans and archives, validates close manifests, and preserves why decisions were
made. The recent history also exposes its cost. Documentation/spec/guide prose
is now **164,399 lines**, 2.7 times production Python, and six days added more
than 11,000 lines. `docs/status.md` contains valuable evidence but increasingly
acts as a per-rung incident log rather than a status summary.

That ratio is not a mandate for deletion. It is a warning against further
accretion. Follow the repository's own compact-at-close rule more aggressively:
one durable conclusion, the evidence that changes the decision, and a pointer
to the owning spec. Keep the cold-read findings that teach a reusable lesson;
do not preserve every correction sequence in every index and status surface.
The top-of-file status date also needs to move with current work rather than
remaining at 12 September while rows through 18 September accumulate below it.

## 8. Recommended next moves

### 1. Close 19Q with the Guide currency item—and stop there

Item 3 is already planned, bounded, and necessary because the shipped workflow
and screenshots changed. Complete it as a prose/asset close, archive 19Q, and do
not use its close findings to open another operator-refinement holding segment.
Route genuine defects directly; park preferences until pilot evidence exists.

### 2. Make institutional deployment the active workstream

Execute the NUS runbook and post-Azure checklist against representative data.
The minimum evidence is real identity headers and role landing; owner and
participant gates; the end-to-end operator/reviewer/result journey; browser
behavior for the new expanders and sorting; backup/restore; logs; transfer size;
and latency/query behavior at intended roster scale.

### 3. Activate email only after the backend and sender are known

Resume Segment 14B from its existing transport seam once the institution has
selected and provisioned a supported sender. Implement one real backend, not
all documented options. Preserve idempotency and eligibility at the service
boundary before adding background or scheduled dispatch.

### 4. Let observed failures choose structural work

The likely candidates are a browser smoke layer if client regressions recur,
component extraction if one of the three large templates changes again, or a
shared roster query/helper if another divergence appears. None should be
scheduled merely because this assessment measured it.

## Bottom line

Review Robin Web is healthy, feature-complete for a pilot, and unusually well
specified. It does not need rescue, decomposition, or another broad UI pass.
Its current weakness is a mismatch between where effort is going and where
risk remains: rapid, review-heavy refinement of local surfaces while the real
deployment is still an assumption. Close the open documentation item, deploy,
observe, recover, and support the application in its intended environment.
Only then let evidence earn the next feature or refactor.
