# Codex codebase assessment — 2026-09-30

**Snapshot:** `17675383` on 2026-09-30 UTC, after Segment 19T closed. This is
a fresh-context whole-repository assessment, not an amendment to the 21
September read. I read the application seams, schema and migrations, operator
and participant surfaces, tests, workflows, live specifications, active plans,
roadmap, deferred ledger, operational documents, and the history available in
this checkout. Quantitative results use git-tracked files and the classification
in `guide/assessment.json`.

**Operational update, 1 October 2026:** `docs/nus_azure_status_v7.md` supplies
newer deployment evidence than the 30 September snapshot. The assessment below
has been updated where that evidence changes its operational conclusions; its
code and quantitative baseline remains pinned to `17675383`.

## Executive assessment

Review Robin Web remains **technically ready for an institutional pilot, while
institutional readiness remains unproved**. The application is broad, its
layering and authorization boundaries remain coherent, and a fresh run passes
**5,109 tests with 16 skips and no xfails**; lint is clean. Postgres 16 still
has a dedicated CI job that applies the migration head, round-trips to base and
back, and runs the full suite.

The nine days since the previous Codex read added a substantial advanced
instrument builder: row-based display and response-field configuration,
conditional branching, conditionally required fields, numeric ranges, and a
second branch level. The work is unusually well specified and heavily tested.
It also moved the repository farther in exactly the direction the previous
assessment advised against: local capability and polish continued while every
post-Azure evidence item remains open. The available shallow history starts on
24 September and still contains **317 commits touching 131 files, adding
18,522 lines and deleting 2,344**. That is enough to establish the pace without
pretending it covers the full interval.

The next move should still be operational, not another feature segment, but
deployment cannot yet be treated as a project-controlled next action. The NUS
landing zone now has the private Web App, PostgreSQL, Key Vault, telemetry,
Easy Auth, OIDC deployment identity, public IP, DNAT, and Application Gateway
plumbing provisioned. Two external decisions block the remaining path: Microsoft
Support must identify runner VM capacity in Southeast Asia, and NUS must settle
the production hostname. Once those clear, finish the runner, gateway, secrets,
migrations, and deployment; then run the six post-Azure checklist items and let
real browser, identity, latency, delivery, and restore evidence select the next
code change. Do not reopen the builder merely because its new abstractions make
further instrument features possible.

## 1. Repository shape and capability

The server-rendered FastAPI/Jinja monolith remains the right deployment unit.
Its four boundaries are still recognizable:

1. `app/web/` owns HTTP parsing, dependency-based identity and authorization,
   redirects, and rendering.
2. `app/services/` owns lifecycle, assignments, validation, instruments,
   responses, invitations, import/export, visibility, and audit behavior.
3. `app/db/models/` and Alembic own the portable SQLAlchemy schema.
4. `app/web/views/` owns render shapes between business rules and markup.

The application exposes 187 route declarations over 81 migrations. It covers
the complete session path: setup and import, instruments and assignment rules,
generation, validation and preparation, invitations, reviewer response,
operator monitoring, participant results and collation, extracts,
configuration round-trip, rehydrate, audit, retention, and administration.
Nothing suggests a useful microservice or frontend-framework split.

Segment 19T deepened one domain rather than widening the platform. Response
fields can now form validated branches, including required-when behavior,
numeric conditions, and one nested level. The storage is explicit and portable:
a self-reference plus condition and mode columns, backed by service-level shape
validation. Clone, settings CSV, operator preview, reviewer entry, completion,
summary, and results paths carry the shape. This is the correct breadth for a
domain feature: it does not stop at the builder.

## 2. Quantitative baseline

Physical lines in git-tracked files at the snapshot, before this assessment was
added:

| Area | Files | LOC | Change from 21 September |
| --- | ---: | ---: | ---: |
| Production Python | 207 | **66,446** | +2,905 |
| Jinja templates | 62 | **31,561** | +2,400 |
| Tests | 402 | **141,957** | +12,226 |
| Alembic migrations | 81 | **7,027** | +110 |
| Tooling | 18 | **16,800** | +356 |
| Documentation/spec/guide | 276 | **183,995** | +13,832 |

The test-to-production ratio is **2.14×**, up from 2.04×. The increase is
credible for branching: the feature crosses persistence, save validation,
response editing, completeness, extracts, clones, and several audiences. It is
also another reason not to use test count as the next objective. The suite grew
by more than twelve thousand physical lines in nine days; new tests should now
be justified by the distinct failure they detect, not by the number of new
states the builder can enumerate.

### Largest production modules

| LOC | Module | Assessment |
| ---: | --- | --- |
| 1,300 | `app/services/validation.py` | Stable since the last read; split only if the next validation change exposes a boundary. |
| 1,299 | `app/web/routes_operator/_instruments.py` | Near its existing 1,400-line trigger, but routing is not where most 19T complexity landed. |
| 1,275 | `app/web/views/_instruments.py` | Grew materially with builder and nested-branch render shapes; the next instrument change should test whether branch shaping can become its own adapter. |
| 1,269 | `app/services/responses/_core.py` | Grew with conditional completeness; branch rules are already separated into `_branching.py` and `_branch_rule.py`, so do not split by size alone. |
| 1,254 | `app/services/csv_imports.py` | Stable multi-format boundary; split only alongside a changed format. |
| 1,144 | `app/services/assignments/_generate.py` | Cohesive generation boundary. |
| 1,111 | `app/web/routes_operator/_quick_setup.py` | Large but stable; duplication remains a reading prompt, not a refactor mandate. |
| 1,109 | `app/web/routes_operator/_operations.py` | Still the clearest route-family split if Invitations or Responses changes materially. |
| 1,107 | `app/services/session_lifecycle.py` | Cohesive state machine; keep intact. |
| 1,084 | `app/web/routes_operator/_shared.py` | Continue watching for unrelated concerns accumulating in a shared dependency. |

The important size change is the template, not a Python module.
`operator/instruments_index.html` grew from 5,642 to **7,202 lines** and is now
about 31% larger than `base.html` at 5,499. It combines layout, staged state,
validation, preview rebuilding, row movement, branching, and lock behavior.
That is not a call for a broad rewrite. It is a boundary condition: the next
builder behavior should first extract one complete interaction, including its
markup, script contract, and tests, rather than add another cross-cutting block
to the same file.

### Duplication and churn

`python3 tools/code_metrics.py` reports **6.2% application duplication at
blocks of 10 or more lines** (3,318 of 53,341 code lines), down from 6.3%.
Test duplication is **12.2%**, down from 13.0%. Neither crosses the repository's
action threshold. The setup roster routes remain the leading application
cluster at 34–47%; their visual similarity still does not erase different
mutation and lifecycle rules.

Churn could not be measured. This checkout is shallow, and the tool correctly
refused to calculate a ratio from truncated blame history. No churn ratio or
comparison is claimed here.

## 3. What changed materially

The builder's earlier duplicated controls were simplified before branching was
added. Visibility moved into the Band 2 card, display fields and response fields
became row-based tables, ordering moved to explicit controls, and the response
pills and intermediate apply gesture retired. That sequencing matters: branches
were added to one row model rather than synchronized across pills, rows, and a
preview.

The branch implementation keeps business semantics out of the template.
Response services own condition evaluation, structure checks, nested traversal,
required-item calculations, and closed-branch response cleanup. Instrument
services own mutation rules, including refusing edits that would strand saved
responses. The view layer supplies labels and nested render shape. The template
is still very large, but the architectural split remains intact.

Two migrations added branch persistence incrementally: the parent/condition
shape landed inert before its write path, and branch mode did the same before
`Require` was enabled. That is a sound migration pattern. The main residual
risk is combinatorial rather than relational: active/inactive fields, Show and
Require modes, numeric and nonnumeric operators, saved responses, two levels,
and multiple audience surfaces produce many valid states. The existing two-level
limit is therefore a useful product boundary, not an obvious restriction to
remove.

## 4. Maintainability and UI

The instrument surface is more coherent for an operator. Configuration now
lives on the rows it changes, visibility is previewed where it is edited, and
the Guide has matched light/dark captures. The work also standardized several
small layout and focus details across Settings, uploads, preview columns, and
reviewer-facing tables.

The cost is concentrated. The instrument template and its integration test are
both dominant files: `test_instrument_builder_routes.py` contains 7,722 code
lines and leads test duplication by absolute duplicated lines. Their sizes are
not defects by themselves, but together they make a future builder change
expensive to understand. Extraction should be change-driven and vertical: one
interaction, its context data, and its behavioral tests. Splitting only the
JavaScript or only the tests would distribute the same contract without making
it smaller.

The live design record has a small currency defect. Its opening status still
says Item 6's second-level branch is merely “logged as 19T Item 14,” while 19T
is closed and the same record later describes two-level behavior. The live
Guide index similarly says Item 14 is logged rather than shipped. This does not
misdescribe application behavior in a spec, but it shows that even a close with
extensive documentation can leave the design record one state behind.

Static accessibility evidence remains strong: semantic tokens, contrast, focus
styles, and inline-script parsing are machine checked. It is still static
evidence. The new branch editor's keyboard flow, focus order, narrow layout,
locked/unlocked transitions, and reviewer interaction all remain owed in a real
browser under post-Azure checklist item 6.

## 5. Test and delivery confidence

The full SQLite suite is green, Node-backed inline scripts ran, and lint is
clean. The Postgres workflow still upgrades to head, downgrades to base,
upgrades again, and runs pytest against Postgres 16. Branching has focused tests
for persistence, validation, clone and CSV transport, response visibility,
conditional required counts, nested behavior, and operator rendering.

Confidence is high for the modeled states and lower for interaction. The
repository's own close correctly leaves browser verification open rather than
claiming template tests prove it. That distinction is especially important
here: much of the feature is client-side staging before one server save, and a
parseable script plus correct posted payload does not prove that keyboard and
pointer sequences produce that payload.

The cold-read record remains useful but expensive. Recent commit subjects show
multiple reads finding stale copy, missing tests, overbroad layout claims, and
cases where a pair collapsed. Those corrections are evidence that the cadence
works, and evidence that the change rate continues to generate correctable
premises. Keep the per-item cadence for code, but do not manufacture more items
to exercise it.

## 6. Security and operations

Authorization remains appropriate for a pilot: Easy Auth is the deployed
identity boundary; session-scoped operator, reviewee, and observer gates are
explicit; refusals avoid enumeration; and mutating services write schema-checked
audit events. Branching does not create a new authorization seam or accept
executable conditions—the operator chooses from bounded tokens interpreted by
services.

Operational uncertainty remains the dominant risk, but the infrastructure state
is materially stronger than the 30 September read established. The Web App,
PostgreSQL Flexible Server, and Key Vault are private; App Service Route All is
enabled; Log Analytics and Application Insights are provisioned; Easy Auth v2
is enabled with tenant consent; the GitHub OIDC identity exists; and the
Application Gateway can reach the App Service private endpoint. A default-probe
HTTP 404 demonstrates network reachability, not application health.

The remaining uncertainty is now more precisely divided:

- **Two external blockers:** repeated `SkuNotAvailable` failures prevent the
  private self-hosted runner VM, pending Microsoft Support advice; and NUS has
  not yet decided the production domain/hostname needed for DNS, TLS, gateway
  routing, and the final Easy Auth redirect URI.
- **Project work after those blockers clear:** register and verify the private
  runner, validate its firewall path and private Key Vault access, create the
  least-privilege database role, store production secrets, switch the NUS
  deployment workflow to the runner, run migrations, and complete HTTPS gateway
  routing with App Service host-header handling and an application health probe.
- **Evidence still owed after deployment:** real Easy Auth claims and role
  landing, external email delivery, backup and restore rehearsal, useful
  telemetry, transfer compression and page latency, and keyboard, screen-reader,
  responsive, and progressive-enhancement behavior in a deployed browser.

The post-Azure checklist now has six open items, including browser verification
for the Owners/typeahead work and the whole 19T instrument surface. This is a
better description of readiness than another local test count.

## 7. Documentation and process

The documentation system remains unusually executable. It checks live paths,
section references, guide/archive indexes, generated tools, contrast, lifecycle
labels, button vocabulary, close manifests, and cited pytest nodes. The 19T
close leaves a compact roadmap summary and archives the 17-item plan.

The documentation corpus is now **183,995 lines**, up 13,832 since the prior
Codex snapshot and 2.77× production Python. Some of that is durable specification
for genuinely complex behavior; some is the cost of narrating each correction.
The active `advanced_instruments.md` is 756 lines even though every item it
contains is built. Its rationale remains useful, but its stale status wording
shows the danger of retaining a completed design record as though it were a
live tracker. Keep it as a design record only if its status is compacted to the
settled result; do not keep extending it as the next work queue.

The roadmap also retains stale stubs whose proposed destinations have passed:
for example, the `regenerate_token` reminder item still says it could ship in
19Q, which is closed. This is not urgent product work. It is a prompt to prune
or re-home the stubs in the next corpus sweep rather than treating every listed
observation as scheduled work.

## 8. Recommended next moves

### 1. Hold feature work while the two deployment blockers clear

Do not substitute local product work for progress that currently depends on
Microsoft Support and the NUS hostname decision. Keep the deployable artifact
ready and avoid hard-coding a guessed public hostname or making further runner
VM attempts until NUS receives an approved/capacity-backed SKU path.

### 2. Complete the private deployment path, then test 19T

When the blockers clear, create and register the private runner, verify its
forced outbound and private-service access, establish the least-privilege
database identity and secrets, switch the deployment workflow, run migrations,
and complete the Application Gateway HTTPS route and health probe.

Exercise the instrument builder and reviewer surface in the dev slot: row
movement, lock state, branching modes, nested branches, range boundaries,
conditional required behavior, saved-response locks, narrow layout, and focus
flow. Record failures against the checklist instead of reopening the archived
segment.

### 3. Execute the remaining institutional evidence checklist

Verify real identity and visibility, navigation behavior, stylesheet transfer
cost, Owners and tag typeahead, restore, logging, and the participant journey.
These observations now have higher expected value than another locally inferred
feature or abstraction.

### 4. Freeze advanced-instrument scope until use supplies a case

Two-level branching is already a considerable rules language. Do not add deeper
nesting, compound predicates, or another field mode without a real instrument
that cannot be represented and a clear migration/export contract. Complexity
here multiplies across authoring, entry, completeness, summaries, results,
clone, and configuration round-trip.

### 5. Make the next builder change pay for one vertical extraction

If pilot evidence requires another instrument change, extract the complete
interaction it touches from `instruments_index.html`, with its view contract and
tests. Candidate seams are branch-row authoring or preview reconstruction. Do
not schedule a size-only rewrite, and do not split markup, script, and tests
independently.

### 6. Compact the completed design record and stale roadmap stubs

Correct the Item 14 status in the advanced-instruments record and Guide index,
then let the next corpus sweep dispose of destinations that name already-closed
segments. This is a small documentation close, not a new implementation
segment.

## Bottom line

Review Robin Web is a capable, well-tested pilot application. Segment 19T added
a coherent advanced instrument model and carried it across every relevant
surface without breaking the repository's architectural seams. It also expanded
the largest UI file, the tests, and the documentation substantially while the
same institutional unknowns remained untouched. The 1 October handoff now shows
that most of the private Azure foundation exists; what remains is a specific
external capacity problem, a specific institutional naming decision, the
project-side work they unblock, and then operational proof. The application does
not need another locally imagined capability to become ready. It needs those
blockers cleared, deployment completed, observed use, browser evidence, and an
operational rehearsal. Let those results decide what changes next.
