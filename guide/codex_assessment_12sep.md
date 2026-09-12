# Codex codebase assessment — 2026-09-12

**Snapshot:** `00e525e3` on 2026-09-12, immediately after Segment 19K closed.
This is a fresh-context assessment of the repository as it stands, not another
amendment to the 11 September assessment. I read the application, schemas,
models, migrations, templates, tests, CI/deploy workflows, live specifications,
status history, roadmap, deferred ledger, known limitations, and the active
Azure-gated plans. Quantitative results use git-tracked files and the area
classification in `guide/assessment.json`.

## Executive assessment

Review Robin Web is a **feature-complete pre-pilot application with a mature
product surface, unusually strong executable documentation, and no credible
case for starting another broad feature segment before the institutional Azure
deployment**. Its principal risk has shifted. The hard problem is no longer
whether the monolith can express the workflow; it can. The hard problem is
proving that the application, identity boundary, operational procedures, and
human workflow hold together on the host and data shape that will actually be
used.

The code is healthy enough to pilot. It is not small: 59,460 production lines,
25,301 template lines, 77 migrations, and 185 routed endpoints. Complexity is
concentrated in a few known seams rather than dispersed as mysterious debt.
The suite is correspondingly large (**3,847 passing tests at the repository's
recorded HEAD result, 16 intentional skips, 0 xfails**), CI exercises SQLite
and Postgres 16, and the Postgres job round-trips the entire Alembic chain.

My recommendation is therefore **stabilize, deploy, observe, and only then
resume the gated roadmap**. There are worthwhile internal cleanups, but none is
more valuable now than turning the institutional deployment from an external
assumption into evidence.

## 1. System and repository shape

The product is a server-rendered FastAPI/Jinja monolith for structured peer
review. Operators assemble a session, import rosters and relationships, define
one or more instruments and assignment rules, generate assignments, validate,
preview, activate, monitor, release results, extract data, and archive or purge.
Reviewers complete assigned forms; reviewees receive policy-controlled results;
observers receive cohort collations. A three-audience by two-phase visibility
model determines what each participant may see and in which of the Raw,
`Anonymized`, or `Summarized` modes.

The repository has four meaningful application seams:

1. `app/web/` owns request parsing, identity dependencies, redirects, and Jinja
   rendering.
2. `app/services/` owns mutations and most domain rules, including assignment
   generation, lifecycle transitions, visibility, extracts, rehydrate, and
   audit emission.
3. `app/db/models/` is a portable SQLAlchemy 2.x model layer with no
   Postgres-dialect imports.
4. `app/web/views/` adapts service/domain state into renderable page shapes.

That organization is visible in the tree rather than merely asserted in the
architecture document: large feature families have already become packages
(`assignments`, `instruments`, `responses`, `scheduled_events`, `extracts`, and
`session_config_io`), while operator and participant routes are split by
surface. The monolith remains the correct deployment unit; there is no service
boundary in the domain that would justify distributed-system cost.

## 2. Quantitative baseline

Physical lines in git-tracked files at `00e525e3`, before this assessment file
was added:

| Area | Files | LOC | Change from the post-19K baseline `ba7b37e7` |
| --- | ---: | ---: | ---: |
| Production Python | 205 | **59,460** | +5 |
| Jinja templates | 64 | **25,301** | +81 |
| Tests | 312 | **105,122** | +1,403 |
| Alembic migrations | 77 | **6,772** | unchanged |
| Tooling | 14 | **13,512** | +1,456 |
| Documentation/spec/guide | 247 | **152,843** | +2,451 |

The test-to-production ratio is **1.77×**. That is high, but it is explicable:
the latest segment added CSS-cascade, contrast, generated-tool, and guide-index
guards without expanding the product model. It is not evidence that production
code is under-factored.

### Largest production modules

| LOC | Module | Assessment |
| ---: | --- | --- |
| 1,264 | `app/web/routes_operator/_instruments.py` | Large route family; stable and below its 1,400 split trigger. |
| 1,106 | `app/services/session_lifecycle.py` | Cohesive state machine; splitting now would scatter invariants. |
| 1,044 | `app/services/instruments/_instrument_crud.py` | Three concerns; column-width helpers remain the clean future carve. |
| 1,038 | `app/web/routes_operator/_operations.py` | Two page families; split Invitations from Responses if it grows. |
| 1,020 | `app/services/responses/_core.py` | Recently crossed 1,000 for the response prefetch; watch, do not react. |
| 1,009 | `app/web/views/_instruments.py` | Dense view-shaping seam matching an unusually dense page. |
| 1,000 | `app/services/csv_imports.py` | Mature import logic; a format-by-format split is available if changed. |
| 984 | `app/web/routes_operator/_quick_setup.py` | Near the watchlist, but its shared orchestration is cohesive. |
| 978 | `app/services/audit.py` | Registry plus validation machinery; size follows the event vocabulary. |
| 964 | `app/services/instruments/_response_fields.py` | Natural feature boundary already exists. |

No split should be scheduled solely because a file crosses 1,000 lines. The
top five are stable, their seams are understood, and churn is not accumulating
at the top. Use the existing triggers: about 1,400 lines for the Instruments
route and about 1,200 for the other watchlisted modules.

### Duplication and churn

`python3 tools/code_metrics.py` reports **6.5% application duplication at
blocks of 10 or more lines** (3,113 of 48,203 code lines), exactly the recorded
baseline. Test duplication is 15.0%, which is unsurprising in integration
fixtures and HTML assertions. The most duplicated production pair is the
Reviewers/Reviewees setup routes, each at roughly half duplicated code. That is
a real maintainability signal, but a generic roster abstraction would also
hide audience-specific behavior; consolidate only when a behavior change has
to be made twice and the two implementations demonstrably remain equivalent.

Churn is **1.0× against a 1.0× age baseline**: all 2,847 deleted Python lines
were under 14 days old, but all 62,416 eligible lines were also under 14 days
old in the available 99-merge history. In other words, the repository snapshot
is too young for raw deletion age to distinguish rework from ordinary change;
the ratio correctly says there is no measurable excess churn.

## 3. Functional completeness

I found no functional-spec area that is represented as shipped in
`docs/status.md` but absent from the code. The principal contracts map as
follows:

| Capability | Implementation read | Assessment |
| --- | --- | --- |
| Five-state lifecycle and per-instrument open/close | `session_lifecycle.py`, `scheduled_events/` | Shipped, audited, and heavily tested. |
| Session lobby, Home, Setup, Workflow, Validate, Previews | operator route package + operator templates | Shipped; page contracts have dedicated specs. |
| Multi-instrument assignment generation | `assignments/`, `rules/`, `relationships.py` | Shipped, including group scope and self-review policy. |
| Reviewer response workflow | reviewer surface routes, `responses/` | Shipped with save, submit, recall, progress, and paging. |
| Reviewee results and observer collation | reviewer route package + visibility services | Shipped in all documented visibility modes. |
| Invitations and monitoring | `invitations.py`, `email_templates.py`, `monitoring.py` | UI/outbox shipped; external delivery intentionally not activated. |
| Extract, configuration round-trip, and rehydrate | `extracts/`, `session_config_io/`, `session_rehydrate.py` | Shipped with explicit coverage and known exclusions. |
| Audit and administration | `audit.py`, sys-admin routes/templates | Shipped with strict test-mode envelope validation. |
| Role and session authorization | `deps.py`, `roles.py`, permission tests | Shipped, including non-enumerating 404 behavior. |
| Guide and theme system | `guide.html`, guide assets, `base.html`, theme tools | Shipped; references and generated artifacts are guarded. |

The honest gap is **delivery infrastructure**, not an unfinished operator UI.
The email outbox and transport interface exist, but the Graph/ACS/SMTP-backed
dispatch path is deliberately gated on an institutional sending identity.
Blob storage is also planned rather than present; current bytea/streaming paths
are explicit fallbacks, not accidental placeholders.

## 4. Architecture and code quality

### What is working well

- **Business invariants live close to mutation.** Lifecycle invalidation,
  assignment reconciliation, audit emission, and visibility resolution are
  service concerns rather than template decisions.
- **The data model is portable.** Models use SQLAlchemy 2.x declarations and
  the migration guidance explicitly records SQLite/Postgres traps. There is one
  Alembic head, and the CI design tests upgrade, downgrade-to-base, and upgrade
  again on Postgres 16.
- **The view-adapter seam is valuable.** Complex render state for assignments,
  instruments, workflow, results, collation, validation, and pagination is
  named and testable outside Jinja.
- **Audit events are treated as a schema.** A per-event registry validates the
  envelope in strict test mode while production remains fail-open for
  observability. This is a good trade: a malformed diagnostic record should be
  caught before deploy but should not suppress the mutation in production.
- **Large features are split by behavior, not by arbitrary line count.** The
  packages for instruments, responses, extracts, and session configuration
  show that the repository can refactor incrementally without changing its
  runtime topology.

### Architectural debt to acknowledge

The documented layering is stricter than the implementation. A scan found SQL
in participant route helpers, reviewer surface context builders, several
operator routes, dependencies, and view adapters. Some is defensible:
authorization dependencies must load records, and view adapters need efficient
read models. Some route-local lookups are simply thin handler conveniences.
Nevertheless, the statement “route handlers: no SQL” is not literally true.

This should **not** trigger a repository-wide purity refactor. Such a sweep
would move code without changing behavior and create review risk across 185
endpoints. Instead, adopt a local rule: when a route-local query is changed for
product reasons, move the query to an existing service/read-model helper if the
move makes the contract clearer or prevents duplication. Update the
architecture prose if dependencies and view adapters are intended exceptions;
do not preserve a rule the codebase does not actually follow.

## 5. Testing and delivery confidence

The testing posture is one of the repository's strongest features:

- Unit tests cover domain decisions, parsers, view adapters, CSS/token
  contracts, generated artifacts, and documentation conventions.
- Integration tests exercise routes against schemas built from ORM metadata.
- SQLite is the fast default, while Postgres 16 CI catches dialect and migration
  behavior.
- The migration job performs the expensive operation many projects omit: a
  complete downgrade-to-base followed by upgrade-to-head.
- There are no xfails. The 16 skips are intentional historical retirement
  markers rather than a queue of failing behavior.
- Recent guard work is mutation-conscious. The repository repeatedly checks
  that a test fails when the forbidden state is reintroduced, which is much
  stronger than counting assertions.

The main confidence gap is also clearly documented: there is **no browser
runtime layer in CI**. Static tests can validate markup, event-registration
shape, CSS tokens, and much of the cascade, but they cannot prove keyboard
flows, screen-reader output, focus order, JavaScript execution, browser history,
or real Easy Auth behavior. The deferred Playwright smoke layer is therefore a
valid candidate after deployment evidence identifies the handful of flows
worth stabilizing. Installing a browser harness before that would risk testing
screenshots rather than user-critical behavior.

One environment limitation affected this assessment: the supplied container
has Python 3.14 and lacks the declared `httpx` development dependency. The
network proxy prevented `pip install -e .[dev]`, so I could not independently
re-run the full suite. I did run import-free document tests, compilation, lint,
and Alembic-head checks; the **3,847 passing** figure above is the repository's
recorded result at this exact HEAD, not a claim of a fresh local full-suite run.

## 6. UI and maintainability

The server-rendered approach remains appropriate. It gives the application a
small operational footprint and makes authorization and lifecycle transitions
easy to reason about. Targeted progressive enhancement is preferable to
introducing a frontend framework at this maturity stage.

The cost is concentration:

- `operator/instruments_index.html` is **5,599 lines**.
- `base.html` is **4,727 lines** and owns the global inline stylesheet plus
  shared scripts.
- `operator/session_extract_data.html` is **2,664 lines**.

These are the repository's largest maintainability risks, larger in practical
review cost than any Python module. They already have a sensible disposition in
the deferred ledger: carve the three templates only when the page is being
changed, and first measure what the inline stylesheet costs on the real wire.
That is the right call. Splitting markup or CSS now would generate a broad diff
with no pilot benefit and could weaken the “one canonical implementation”
guards that currently prevent drift.

The color system is in substantially better condition after 19K. A generated
contrast inventory checks 73 foreground/background relationships in both
themes, with three hover-only exceptions explicitly accepted and tied to
passing resting states. This is credible static evidence, but it is not a full
accessibility audit. Keyboard navigation, focus order, screen-reader output,
and non-text contrast remain unmeasured and should be checked on the deployed
participant journey before a pilot opens.

## 7. Security and operations

The application-level posture is appropriate for a pre-pilot internal system:
Easy Auth supplies identity, fake auth is local-only, workspace roles and
session ownership are explicit, participant reachability is roster-based, and
session-scoped refusals avoid enumeration. Destructive actions and mutations
have audit coverage.

The larger risks are infrastructure facts recorded in
`docs/known_limitations.md`: one dev environment, public database access,
secrets in App Settings/GitHub secrets rather than Key Vault, no Application
Insights resource, no automatic retention, and no rehearsed restore drill.
None is hidden. That transparency matters, but documentation is not mitigation.
Before real review data is accepted, the institutional deployment needs a
visibility-grid audit on representative data, an auth/role smoke pass, an
actual backup/restore rehearsal, and a decision on monitoring and retention.

One operational footgun remains small but real: runtime dependencies are
duplicated between `pyproject.toml` and `requirements.txt` and synchronized by
hand. Do not build a dependency-management project around it now, but every
dependency PR must continue to change and review both files together.

## 8. Known gaps versus defects

I found **no known open product defect** that should block deployment. The
following are deliberate gaps and should stay labeled as such:

1. External email dispatch is not active; operators must distribute the app
   link and chase incomplete reviewers manually.
2. Scheduled/policy-driven purge is absent; retention is operator-driven.
3. Restore is whole-database rather than per-session.
4. Blob storage is unimplemented because no institutional storage account has
   been provisioned.
5. Full browser accessibility and JavaScript interaction testing are absent.
6. Several advanced refinements—targeted reminder cohorts, audit search,
   assignment-engine fast paths, and operator theming—are deferred pending
   pilot evidence.

The distinction is important. Treating these as bugs would invite speculative
work; treating an observed pilot failure as “already deferred” would be equally
wrong. Each deferred item has a lift trigger, which is the right governance
mechanism.

## 9. Recommended next moves

### 1. Make deployment verification the next active workstream

Do not open another free-standing feature segment while the institutional host
is unresolved. Complete the NUS cutover runbook, then execute the post-Azure
checklist against real infrastructure and representative data. In order:

- verify identity headers, role landing, session-owner gates, and participant
  reachability;
- run the visibility grid with real policy combinations before opening a
  reviewee-facing window;
- exercise the operator workflow end to end, including the navigation busy
  indicator and downloads;
- rehearse restore rather than merely reading the runbook;
- capture latency/query/log evidence at the intended roster size;
- decide the inline-stylesheet question from actual transfer/compression data.

This is the highest-value work because every subsequent plan—email delivery,
institutional documentation, monitoring, and possibly blob storage—depends on
facts only the deployed environment can provide.

### 2. Ship the global technical-support contact only if an address is known

This is the one small unblocked product slice with clear operational value. Add
the deployment-wide contact setting and surface it on error/invalid-link/footer
paths, with an unset value rendering nothing. Do not invent a placeholder
address. If ownership is not settled, leave the mechanism unbuilt rather than
shipping a dead help link.

### 3. After cutover, activate email through the institutional backend

Resume Segment 14B only after the sending identity and approved backend are
known. Preserve the existing sequence: dispatch/idempotency foundation before
batch queueing, then backend-specific integration. Avoid implementing every
backend option; choose the institutionally supported one and retain the
transport seam for replacement.

### 4. Use pilot evidence to select—not accumulate—the deferred queue

The deferred ledger is comprehensive enough to become a temptation. Pick work
only when evidence activates its trigger. Likely examples are targeted reminder
cohorts if manual chasing is costly, a browser smoke layer if client-side
regressions recur, or assignment-engine fast paths if measured rosters exceed
current latency budgets. Do not schedule template carving, abstract roster
routes, or audit search merely because this assessment names them.

## 10. Completion outlook

The remaining named production work is modest relative to the shipped system:

| Work | Production estimate | Template estimate | Gate |
| --- | ---: | ---: | --- |
| Segment 14B email activation | +900–1,400 | +200–400 | Institutional host and sending identity |
| Segment 20 institutional documentation/polish | +200–500 | +300–600 | Successful institutional deployment |
| Blob seam plus first consumer | +400–700 | +50–150 | Provisioned storage and a chosen use |
| Global technical-support contact | +30–60 | +20–50 | Named owner/address |
| **Named-work floor** | **60,990–62,120 total production** | **25,871–26,501 total templates** | |

This is a floor, not a forecast. Recent history shows that assessment findings
often create work that no roadmap row predicted, while tooling-heavy segments
can create major quality gains with almost no production growth. The more
meaningful completion criterion is operational evidence: a deployed pilot can
be created, run, observed, recovered, and supported by someone other than its
author.

## Bottom line

The repository does not need rescue, a rewrite, a frontend framework, or a
microservice decomposition. It needs **deployment reality**. Its functional
surface is broad, its test and specification discipline are stronger than most
projects of this size, and its known structural risks have named seams and
triggers. The correct next phase is to stop expanding the model, prove the
institutional host and human workflow, and let measured pilot friction decide
which deferred capability earns the next slice.
