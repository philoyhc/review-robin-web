# Cordware Interoperability — Agent Handoff and Implementation Plan

**Version:** 0.3  
**Date:** 4 November 2026  
**Status:** Planning and reconciliation instructions; no blanket authorization to implement or deploy  
**Primary specification:** `cordware_interoperability_consolidated_spec_v0.3.md`  
**Target repository path for primary specification:** `cordware/spec/interoperability_and_orchestration.md`  
**Recommended path for this handoff:** `cordware/guide/interoperability_agent_handoff.md`

## 1. Mission and definition of success

Adopt the consolidated Cordware interoperability specification as the architectural baseline and prepare implementable, small, independently testable increments for **ApplyDesk ↔ Review Robin** linked workflows.

A completed **product workflow** eventually provides:

1. In ApplyDesk, `Create in Review Robin` opens a new RRW tab on a new **populated draft Session Home**.
2. RRW owns its usual `Validate` → `Prepare`/generate assignments → invitations → reviews workflow.
3. ApplyDesk displays RRW's session status and freshness without copying answer text.
4. In ApplyDesk, `Import Review Robin results` asks RRW to generate a **fresh scoped export** and imports a snapshot into ApplyDesk's **restricted external-review results** store.
5. Repeats/retries are safe; data/authorization boundaries remain intact; normal manual CSV workflows continue to work.

This file is an **execution brief**, not a replacement for the main spec. Do not build every feature from one prompt; plan/approve slices with their tests and database changes.

## 2. Read in this order

**New authoritative files** (the two fresh documents accompanying this handoff):

1. `cordware_interoperability_consolidated_spec_v0.3.md` — architecture, common capabilities, precise functional behavior and unresolved gates.
2. This handoff — repository pointers, phased execution, acceptance and reporting.

**Current canonical repository, `philoyhc/review-robin-web`:**

- Root: `AGENTS.md`, `constitution.md`, `rrw_sdd_in_practice.md` **if present**; current architecture/CI rules and package import-boundary tests.
- `cordware/spec/host.md`; `cordware/spec/identity.md`; `cordware/main.py` and relevant mounted-host tests.
- `spec/csv_contracts.md` — primary source for RRW setup and response CSV format.
- `spec/quick_setup_card_spec.md`; `app/web/routes_operator/_quick_setup.py` — actual five-slot create/import behavior and lifecycle gates.
- `app/services/sessions.py`; `app/services/csv_imports/`; `app/services/relationships.py`; `app/services/session_config_io/`; relevant DB transaction/receipt/audit utilities.
- `spec/permissions.md`; RRW route dependencies for operator/session-owner gates.
- `spec/assignments.md`, `spec/instruments.md`, `spec/extract_data.md`, `app/services/extracts/responses_extract.py` — actual RRW assignments and response-export semantics.
- `applydesk/docs/applydesk_functional_spec_v0.6b_agent_handoff.md` and any newer `applydesk/spec/` and implementation. Check whether ApplyDesk has advanced beyond the cited November 2 spec.
- `residentialapps/spec/architecture.md` only for subsequent RA Lifecycle adoption, not needed for first RRW integration slices.

**Private deployment:** Consult private `philoyhc/cordware` import rules, migrations, `deployment/apps.toml`, Azure/Graph readiness and operational plans **only for separately authorized deployment work**. Do not move institutional configuration, credentials or real personnel data into public code/tests.

The old standalone interoperability/handoff v0.1/v0.2 drafts are **superseded design history**. Do not attach them as parallel instructions.

## 3. Required first deliverable: repository reconciliation, not application code

Before changing runtime code, produce a short written findings report that answers:

1. Which RRW services can already be invoked for **new-session create plus five-slot Quick Setup**, and at which boundary the new-session creation might commit before an upload refusal? Provide exact function names and line references.
2. Which current RRW import contract applies to Reviewers, Reviewees, Relationships, Observers and Settings? Distinguish mandatory/optional members, case-sensitive headers, symmetric-review behavior, Graph directory checks and caps.
3. Which session-owner authorization gates can a narrow API call reuse for create/status/export? Is there already a safe API-oriented error/transaction wrapper?
4. What status fields/denominators are meaningful and derivable without expensive joins or disclosing response content?
5. Which immutable RRW identifiers can anchor **reviewee + assignment + instrument + field + submitted response** at return time? Explain why ordinary `responses.csv` and positional instrument names are insufficient.
6. What instruments, rules and source identities can ApplyDesk actually map today, versus what remains only in its specification? Preserve the distinction between one applicant and multiple applications from that person.
7. What **source attestation** mechanism fits existing infrastructure and security needs? Do not confuse browser authentication with verified provenance.
8. What changes to schema, migration ownership, audit, CSRF, no-store policy, package limits and import-boundary tests are required?

Document assumptions and uncertainties. Do not invent decisions D1–D8 in the main spec.

## 4. Implementation slices (separate PRs or coherent PR ladders)

### Slice A — Shared, import-safe protocol primitives

**Goal:** Small versioned envelope/manifest and receipts, with bounded ZIP/CSV payload validation, source/target/scope references, digest checks, safe errors, and fake/synthetic fixtures.

**Must not:** add a global Cordware business database, global application permissions, a second RRW CSV parser, or depend on ApplyDesk existing.

**Tests:** malformed member name, traversal, duplicate kind, digest mismatch, unsupported version, decompression/size cap, changed replay ID; independent mounted application tests.

**Gate:** choose proof/verification strategy before labeling transfers as *source-verified*. Envelope parsing alone does not meet this gate.

### Slice B — RRW create-draft receiver and durable receipt

**Goal:** New narrowly scoped RRW endpoint/service that calls the existing create + Quick Setup parsing/saving paths, atomically commits **session, ownership, all included setup categories, receipt**. Returns actual Session Home URL.

**Must not:** automatically call Prepare, generate assignments, send mail, publish results, or allow arbitrary replacement of an existing session. Preserve RRW manual New Session and Quick Setup semantics.

**Tests:** all five CSV types, partial valid package, symmetric mode, invalid final Settings row rollback, role denial, ownership, concurrent duplicate IDs, lost acknowledgment receipt recovery, no writes on refusal, no assignments/invitations.

### Slice C — RRW read-only linked status

**Goal:** A documented JSON projection of session lifecycle, distinct reviewers/reviewees, generated obligations, invitations/submissions and completion using RRW's actual definitions; live as-of timestamp and source identity.

**Tests:** permission/owner denial, 404 confidentiality, changing status after RRW workflow events, zero/undefined denominator, slow/unavailable response, never exporting answer text to status UI.

**Gate:** define the counting semantics and names before returning any headline `% complete`.

### Slice D — RRW handoff result export

**Goal:** Audited, explicit fresh-export operation, with recipient/source link scope and stable crosswalk keys, complete/partial semantics, submitted-only default, completion metadata and source proof; reuse actual RRW response serializers.

**Tests:** no submissions, submitted review, correction/clear, disabled/withdrawn assignment, instrument reordering, multiple applications/opaque reviewees, group-scoped instruments, version changes, unauthorized export. Ensure general analyst CSV remains unchanged.

**Gate:** approve stable return schema and correction semantics (main spec D2), plus confidentiality scope (D7).

### Slice E — ApplyDesk adapter, link store and UI

**Goal:** During ApplyDesk development, implement authorized source-to-RRW mapping, `Create in Review Robin` tab launch, link/transfer receipt storage, authorized RRW status panel and manual `Refresh status`.

**Tests:** source access denied; RRW role denied; imported setup populated; popup blocker/recovery; duplicate click; source mutation after click; multiple RRW sessions linked to one ApplyDesk exercise; last-checked vs last-imported distinction; unsupported instrument mapping.

**Gate:** ApplyDesk instrument/rule mapping (D1), eligibility scope (D5), and source proof (D3). If unavailable, a clearly labeled **roster-only** handoff MAY be implemented without claiming instrument parity.

### Slice F — ApplyDesk restricted results import/reconciliation

**Goal:** Button-triggered RRW export and authenticated ApplyDesk import; apply current external-view changes in a single transaction, keep receipts/history, refuse stale/malformed/mis-mapped data, show result counts; no implicit publication.

**Tests:** same snapshot no-op, newer snapshot corrected/cleared, partial export cannot erase, stale concurrent export refusal, group mapping block, source/target authorization, swapped bytes, unrelated RRW session, confidential answer not displayed to applicants, operator import retention/provenance.

**Gate:** approve all D2/D3/D6/D7 decisions and source-app schema/migration details first.

### Slice G — Generalization (later)

Add RA Lifecycle → ApplyDesk and RA Lifecycle → RRW adapters only once Residential core, cohort/term identity and destination importer are ready. Native RA allocation remains within Residential Operations; no synthetic network integration for an internal module.

## 5. Cross-cutting invariants to assert in tests

- **Authority:** no cross-app ORM/business imports, direct DB queries, role inheritance or host-owned business state.
- **Create atomicity:** a failing final CSV does not leave even an empty RRW draft; successful create has owner, setup and receipt.
- **Replay safety:** same transfer intention creates at most one RRW session despite races/timeouts; replay with different bytes/actor/source is rejected.
- **Status is not a result import:** no response bodies or decisions copied on `Refresh status`.
- **Result import is not publication:** imported data is restricted, explicitly external and does not change native assessor history or applicant outcomes.
- **Stable identity:** use ApplyDesk application ID, RRW durable keys and verified crosswalk; not names, emails alone or instrument ordinals.
- **Complete versus partial:** missing current rows only reconcile away after a complete, authorized snapshot; imported current view cannot move backwards because an old export arrived late.
- **Source trust:** signed/verified receipt or clearly identified `operator supplied` provenance; no trust promotion from an unsigned manifest.
- **Minimal disclosure:** no hidden applicant sections in setup, no raw tokens, confidential responses or bulk CSVs in URLs, telemetry or logs.
- **Manual parity:** existing RRW Quick Setup and export routes retain their contracted behavior.
- **App independence:** each app starts/tests without the other deployed; integration fixtures use local synthetic identities, never production data.

## 6. Required design decisions — do not silently settle

Use the **D1–D8 gates** in the main spec as the definitive list. Prioritize:

1. **D1** — exact ApplyDesk → RRW instrument, rule and applicant/reviewee mappings.
2. **D2** — stable RRW response/export schema, changed instruments, group reviews, corrections/clears.
3. **D3** — cryptographically or server-verified source attestation across browser-carried ZIPs.
4. **D4** — RRW status counts and definitions.
5. **D5–D7** — eligible data, two-app permissions, session ownership changes, confidentiality and retention.
6. **D8** — operational size/time/runtime envelope and short-lived package handling.

Where a decision remains open, implement only independent foundations or submit a narrow proposal with options/trade-offs and tests. Do **not** claim ApplyDesk↔RRW end-to-end completeness.

## 7. PR report-back template

At the conclusion of each slice, report:

- Behavioral change and explicitly **unchanged** app workflows.
- Source files, endpoints, DB migrations and configuration touched; source/public versus private responsibilities.
- Exact app-owned CSV/status schema and version, where relevant.
- Authorization, CSRF, source proof, privacy and idempotency decisions.
- CI/test evidence and browser acceptance results, including negative cases and mounted-host paths.
- Remaining gates, newly discovered incompatibilities and next smallest reviewable slice.

Do not modify private Cordware deployment or live institutional resources as an incidental part of public application development.

## 8. Distinction from RA Lifecycle and RA Allocation work

The following are **not** consolidated into the general interoperability protocol and are not a prerequisite for RRW receiver work:

- RA Lifecycle's cohorts, final selection/acceptance, training, appointments and governance.
- The `res-apps` allocation solver's joint selection/matching, hard/soft constraints, manual pins/REDO, fairness scoring and migration to Residential Operations' term-specific assignments.

Those retain their domain specs. They reuse this interoperability contract only when exchanging data with another mounted Cordware app.

---

**Agent instruction:** first reconcile this handoff against current `main`; produce a phased PR plan with explicit blockers. Do not interpret this document as permission to skip unresolved data-mapping, authorization or confidentiality decisions.
