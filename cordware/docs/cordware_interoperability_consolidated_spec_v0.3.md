# Cordware — Interoperability and Application Orchestration

**Consolidated architecture and functional protocol specification — v0.3**  
**Date:** 4 November 2026  
**Status:** Proposed consolidated baseline for review and implementation planning; **not** a claim of implemented capabilities or an authorization to modify production  
**Parked (author, 2026-11-04):** no implementation is planned. Revisit when ApplyDesk or RA Lifecycle is further along. Rulings and review notes from that date are §13.  
**Canonical public development repository:** `philoyhc/review-robin-web`  
**Private import/deployment repository:** `philoyhc/cordware`  
**Suggested repository path:** `cordware/spec/interoperability_and_orchestration.md`  
**Companion:** `cordware_interoperability_agent_handoff_v0.3.md` (implementation brief, checks and phased plan)

## 0. Scope, authority and consolidation

This document **replaces as a design reference** the standalone drafts:

- `cordware_interoperability_and_application_orchestration_v0.1.md`;
- `cordware_app_to_app_csv_handoff_spec_v0.2.md`; and
- `cordware_app_to_app_csv_handoff_spec_v0.1.md` (already superseded by v0.2).

It consolidates the architectural principle, capability contract, setup/status/result handoffs, end-to-end ApplyDesk–Review Robin example, security boundaries, data provenance, failure behavior, and generalization to RA Lifecycle. The older drafts are **historical**, not additional mandatory instructions. This document does **not** replace domain-specific specifications for ApplyDesk, Review Robin, Residential Operations, or RA Allocation; those own their actual schemas and business rules.

**Precedence for implementation:** (1) accepted Cordware-wide architectural invariants here; (2) current specialist-owned import/export/authorization contracts for the relevant app; (3) application-specific approved mapping and workflow decisions. A contradiction must be surfaced for a human decision, not silently resolved by copying obsolete draft text. Repository code is evidence of what currently runs, **not automatic authorization to override an adopted specification**. The companion agent handoff identifies the concrete repository documents and gates.

Use **MUST / SHALL** for intended mandatory behavior; **SHOULD** for a strong default; **MAY** for optional extension. Illustrative URLs, schema examples and counts are proposals, not existing APIs.

## 1. Objective

Cordware is a suite of independently functional, separately owned applications capable of cooperating in broader administrative processes. The desired experience is **button-driven initiate → observe → retrieve**, without routine human download/re-upload of CSVs and without making the apps one tightly coupled business system.

A coordinating app can prepare a specialist's input, create a linked unit of work in the specialist, display its authoritative progress, and pull its results on demand. The specialist retains control of its own configuration, decisions, assignments, operations, records and permissions.

**Not required:** a central workflow engine, shared business database, event bus, live bidirectional sync, direct cross-app SQL, or generalized internal-table import APIs.

## 2. Specialist and harness/orchestrator: a continuum

These are **functional tendencies**, not rigid application classes or registry flags.

| Application | Specialist responsibility | Orchestrator/harness responsibility |
|---|---|---|
| **Review Robin** | Review rosters, instruments, assignment rules, invitations, submissions, exports | Its own session workflow |
| **Email Checker** | Directory/address verification, annotated results | None necessary |
| **RA Leave** | Eligibility, leave requests/approval and balance/records | Limited leave-process coordination |
| **ApplyDesk** | Applicant forms/submission, references, native assessments, communications/outcomes | Delegates sophisticated review exercises to RRW, observes progress, retrieves externally collected reviews |
| **RA Lifecycle** | Finalist/offer transitions, native RA allocation, training/appointment coordination | Coordinates recruitment in ApplyDesk and in-service peer reviews in RRW |

A specialist SHALL expose domain-appropriate **request/import** and **result/export** facilities where useful, preferably with manual and API-accessible forms of the same contract. This does **not** entail unrestricted record writes, bypassing approvals or every app implementing every endpoint. A long-running specialist additionally SHOULD expose a narrow status capability. A stateless checker may simply accept inputs and return outputs.

An orchestrator SHALL retain its own authoritative process record and link information, but SHALL NOT recreate the specialist's internal state machine or claim authority over its results before an authorized retrieval.

## 3. Ownership, boundaries and core invariants

1. **Independent app ownership.** RRW, ApplyDesk, Residential Operations and Support Logs retain their respective data, migrations, business logic, audit, RBAC and retention. Proposed ApplyDesk has its own dedicated PostgreSQL database. No cross-app foreign keys, cross-DB write grants, direct SQL joins or business-service/ORM cross-imports.
2. **Stateless host.** Cordware supplies mounting and common identity/transport helpers. It owns no global application session table, orchestration DB, shared people/role store or approval engine. Durable handoff links are stored by the orchestrator; receipts/exports by the specialist.
3. **Recipient rules prevail.** A specialist validates inputs through its actual importers and controls the effect of a handoff. Source labels, CSV columns, manifest claims, a source app's Operator role and the shared domain do not bypass destination permissions.
4. **No implicit work progression.** Creating a RRW session does not generate assignments, Activate/Prepare the session, dispatch invitations, send mail or publish results. Retrieving results does not adjudicate applicants, publish scores, accept offers or activate RA appointments.
5. **Separation of current status and imported data.** A status refresh reads the specialist. A results import is a distinct explicit, auditable transaction. A cached status does not silently become authoritative business data in the orchestrator.
6. **Human-usable fallback.** The same recipient-native CSV contracts MUST remain usable for a manual download/upload where reasonable. An automated adapter SHALL NOT create an incompatible parallel importer.
7. **No blind trust in source assertions.** Browser-supplied manifests and link IDs are claims, not authentication or authorization. Cryptographic or authenticated origin proof is required before *verified source* provenance may be asserted.

## 4. Capability model — minimum interoperability contract

| Capability | Semantics | Long-lived linked task | Stateless task |
|---|---|---|---|
| **Initiate / import** | Receive a versioned domain-native request; validate before commit | Required when externally creatable | Request processing suffices |
| **Receipt / stable reference** | Durable target ref, operation ID, source linkage and canonical UI URL | Required | Optional |
| **Status** | Read-only domain-defined state, numerator/denominator counts, source timestamp | Required if tracked over time | Not needed |
| **Results/export** | Versioned, scoped output with source identity and provenance | Required where results are consumed externally | Immediate return may suffice |
| **Open specialist UI** | Navigate to the ordinary destination work page | Required where human work continues | Optional |
| **Manual parity** | Download/upload using same data schema and parser | Strong default | Strong default |

Capabilities are independently versioned and discoverable/documented. No universal schema is imposed on all apps: **the destination defines valid setup files; the exporting specialist defines results, and the consuming app defines its own interpretation**.

## 5. Data and exchange conventions

### 5.1 Formats

- **CSV:** primary payload for structured tabular business data; UTF-8, header names and semantics from the relevant specialist. Preserve the destination's precise CSV quirks and limits rather than inventing generic parsing behavior.
- **JSON:** manifests, control parameters, status, receipts, validation/errors and mapping metadata.
- **ZIP bundle:** preferred transport for several related CSVs plus `manifest.json`. Equivalent bounded multipart form transport MAY be supported if semantics remain identical. A complete immutable byte snapshot is processed per request.
- **No generic `persons.csv` or `reviews.csv` standard.** Source adapters emit recipient-native CSVs. The same CSVs MAY be downloadable for manual use.

### 5.2 Versioned setup package

Illustrative envelope, subject to final schema approval:

```json
{
  "protocol": "cordware.csv-handoff",
  "protocol_version": 1,
  "operation": "reviewrobin.create_draft_session",
  "source_app": "applydesk",
  "source_kind": "exercise",
  "source_ref": "opaque-exercise-ref",
  "target_app": "reviewrobin",
  "transfer_id": "3d2d1842-69bf-47f9-950f-e55aa7385bc7",
  "created_at": "2026-11-04T00:00:00Z",
  "format": "reviewrobin.quick-setup-v1",
  "session_suggestion": {"name": "RA Recruitment — Interviews", "code": "RA-INT-27"},
  "files": [
    {"kind": "reviewers", "name": "reviewers.csv", "sha256": "<SHA-256 of exact CSV bytes>", "row_count": 25},
    {"kind": "reviewees", "name": "reviewees.csv", "sha256": "<SHA-256 of exact CSV bytes>", "row_count": 100},
    {"kind": "settings", "name": "settings.csv", "sha256": "<SHA-256 of exact CSV bytes>", "row_count": 140}
  ]
}
```

The manifest is **metadata, not evidence of permission**. Verify actual contents, exact byte hashes, supported protocol and recipient-format versions, unique member names/kinds, sizes, rows and required files. Reject unknown required kinds, duplicate members, traversal paths, symlinks/executable payloads where inappropriate, decompression bombs and invalid encodings. Reject unexpected schema semantics rather than ignoring critical mapped data. Include a source reference but never sensitive participant rows, credentials or bearer tokens in URLs or manifests.

Versions must separately address **envelope protocol**, **operation**, **recipient-native CSV format**, and **result projection**. Use explicit version compatibility checks, not assumptions from filename.

### 5.3 Durable linkage and operation receipts

An orchestrator link stores at minimum:

- orchestrator app/record ID and **purpose** (e.g., RA interview round);
- destination app, stable destination record ID and server-issued canonical relative URL;
- create transfer ID and receipt, initiating actor and timestamps;
- source and destination schema versions; **versioned crosswalk** of source application IDs to destination reviewees, instruments and fields;
- last successful status check (if stored) and its freshness; last imported result snapshot ID, scope, digest and timestamp;
- linkage state (pending/created/recoverable/revoked/invalid) without pretending to own RRW's own lifecycle.

Recipient stores its own source provenance and durable creation receipt. Neither database references the other with a foreign key. **One intent = one transfer ID**. Replaying the same ID/actor/source/operation/digest MUST return the same result, not create another session. Same ID with changed bytes, actor or declared source MUST be rejected. Concurrent retries must be serialized or guarded by uniqueness constraints. A source-side failure to save the link is recoverable by authorized recipient receipt lookup.

A single ApplyDesk exercise MAY link to several RRW sessions for distinct rounds; the first vertical slice can expose one at a time, but the data model MUST NOT assume `exercise_id` uniquely identifies a single RRW session. Never merge results from multiple sessions or treat the newest as primary without an explicit policy.

## 6. Reference workflow: ApplyDesk → Review Robin → ApplyDesk

### 6.1 Operator-facing sequence

1. **Prepare in ApplyDesk.** Operator configures the application exercise, chooses eligible submitted applications, assessor/reviewer population and eligible RRW-compatible instrument(s)/template, and selects the purpose and data scope.
2. **Click `Create in Review Robin`.** Open a new tab during the user gesture, initially on a safe RRW-controlled holding/error page. Build and transfer a complete RRW-native setup bundle.
3. **Review Robin receives and creates.** RRW authenticates the human as its own Operator, validates all files and creates the draft session, ownership and setup **atomically**, returning an authorized receipt and actual Session Home URL. The tab navigates straight to the standard populated **Session Home**, not a new import wizard. ApplyDesk retains the link.
4. **Review Robin takes over.** Operator edits/validates configuration, generates assignments, handles invitations, reviews and submissions using RRW's ordinary workflow. The setup transfer does **not** trigger any of those actions.
5. **Observe within ApplyDesk.** The `Linked Review Robin` panel fetches RRW's current authorized status on page load or manual `Refresh status` and shows state/counts/freshness, without importing response bodies.
6. **Click `Import Review Robin results`.** While remaining in ApplyDesk, operator triggers a fresh authorized RRW response/completion export and imports it into a restricted ApplyDesk external-review store. Show receipt with counts and snapshot time.
7. **Repeat as needed.** A later click retrieves corrections/new submissions without duplicating data. ApplyDesk's publication, outcomes and own assessment records remain separate.

For an existing linked session, the default action becomes **Open in Review Robin**; **Create another** is separate and deliberate. Returning to ApplyDesk must not reset RRW's live configuration from the original setup snapshot.

### 6.2 What ApplyDesk sends to RRW

The receiver understands the following **existing RRW Quick Setup** files, subject to configuration and compatibility:

| File | ApplyDesk source/mapping | Important caveat |
|---|---|---|
| `reviewers.csv` | Authorized assessor/reviewer list or explicitly selected panel(s); `ReviewerName`, `ReviewerEmail`, optional tags/status | RRW's directory checks and account identity behavior apply; panel membership alone is not permission to review |
| `reviewees.csv` | Selected applications (normally submitted/eligible) with `RevieweeName`, `RevieweeEmail` or supported unique opaque reviewee identifier | **One ApplyDesk application ID must map to one reviewee key** even if a person submitted several applications |
| `relationships.csv` | Explicit reviewer–reviewee pair *context* where expressible | **Relationships are not RRW assignments**; they do not substitute for per-instrument rule generation |
| `observers.csv` | Explicit approved observer list | Do not infer observers from ApplyDesk Operators |
| `settings.csv` | RRW-compatible session settings, instruments, fields and rules | Exact `field,value,data_type` format; instrument/rule semantics require parity checking |
| `manifest.json` plus crosswalk | Exercise/application/instrument/field identity, source scope and version | Not another arbitrary RRW importer; mapping may remain in verified receipt/metadata |

RRW already accepts the five CSV categories within one Quick Setup save pipeline; it has no normal **Assignments** CSV importer. The standard RRW `Prepare` action constructs assignments from the rosters, relationships and **per-instrument rules**. Sending explicit ApplyDesk assessor-to-application obligations therefore requires a compatible RRW rule/relationship representation and tests; do not promise perfect preservation without one.

ApplyDesk's own forms/assessor instruments are *not automatically equivalent* to RRW's. Its field types, branching, bounds, display visibility, versions and rules must be compared with the actual RRW Settings contract. Unsupported mapping SHALL refuse the complete-instrument handoff or be explicitly accepted as **roster-only**; never silently drop required questions, restrictions or visibility controls. Applicant-hidden form sections, attachments, referee letters and earlier confidential assessments SHALL NOT automatically be transmitted.

An ApplyDesk participant may submit multiple applications. An email address alone cannot distinguish those review targets; preserve immutable ApplyDesk **application IDs** through a versioned crosswalk, using RRW's supported opaque reviewee identifiers only where the intended reviewer display/visibility model permits them.

### 6.3 Review Robin's create/import obligations

The new receiver SHALL:

1. Reuse existing RRW CSV parsers and Quick Setup services; check file-level, roster cross-file, relationship reference, symmetric-review, Settings and identity validation using RRW's own rules.
2. Ensure **draft session creation + RRW owner assignment + all included setup saves + receipt** commit in a single RRW database transaction. On failure, leave no orphan draft or partial setup. Current ordinary New Session behavior must not be assumed atomic on all invalid uploads; verify/refactor the new handoff path without incidental changes to existing pages.
3. Bind ownership to the actual signed-in **RRW-authorized** user; an ApplyDesk Operator without RRW authorization cannot create this session. **No Prepare, Activate, invitation or email send** occurs.
4. Enforce a durable idempotency receipt keyed by transfer intent, with source/ref/digest/actor binding and recovery when the browser loses confirmation.
5. Return a stable RRW session ref and a **destination-generated relative Session Home URL**. The new tab navigates there on success; otherwise show a safe actionable error and retry/recover path.
6. Apply RRW's normal delegated Graph directory-resolution behavior where available. Entra account binding is RRW's responsibility; source-supplied emails are not magically verified identities.

**Existing RRW operational constraints to preserve:** reviewer/reviewee importers use case-sensitive required headers, 1 MiB and 5,000 data-row limits per roster file, cross-roster identity checks and atomic Quick Setup saves. Settings is not subject to precisely the same import caps; the new handoff **must add an overall bounded package limit** to prevent abuse. Existing RRW Settings applies substantial configuration, including instruments, and may have destructive behavior when imported into an existing session. **Initial handoffs create new drafts only**, not automatic merge/replace of live sessions. Symmetric-review setup has its own valid file combinations.

### 6.4 Status displayed in ApplyDesk

A **read-only RRW status endpoint** SHALL expose a documented, appropriately authorized projection containing:

- stable RRW session ref, name/code, lifecycle state and safe Session Home URL;
- reviewer count, reviewee count, instrument count, when meaningful;
- generated **assignment obligation count**, invited reviewer count, submitted/completed counts and **precise denominators**; distinguish people, assignments, response-field answers, and fully completed obligations;
- activity watermark, RRW-as-of timestamp and status-schema version; no confidential answers or reviewer narratives;
- optional indication of result snapshot newer than the last imported ApplyDesk snapshot, with a clearly defined comparison.

ApplyDesk requests this using the signed-in operator's **independent RRW rights**. An ApplyDesk-only operator receives a permission-unavailable state, not an impersonated elevated status. On a failed check show **unavailable/stale and last checked**, never silently display old counts as current or interpret unavailable as zero. Refresh may occur on page load and button click; foreground polling is optional. No background synchronization is required.

**Keep two separate concepts visible:** *live RRW status last checked at T* and *RRW result snapshot last imported at U*. Status refresh never writes ApplyDesk-native assessment state.

### 6.5 Return results: RRW export → ApplyDesk import

On **`Import Review Robin results`** in ApplyDesk:

1. Resolve an existing verified link and versioned crosswalk. Operator must have permission both to **export this RRW session/scope** and to **import into this ApplyDesk exercise**.
2. Request a **fresh, scoped export** from RRW; no RRW tab or manual download is required. RRW checks link, actor and scope, generates a versioned, consistent response/completion snapshot, and audits export.
3. Transfer ZIP/CSV bytes and manifest securely to ApplyDesk. ApplyDesk validates source linkage and attestation level, schema, digest, completeness, crosswalk, permitted data types and per-app identity keys.
4. ApplyDesk atomically imports into a **restricted external-RRW-results** store; do not create fictional ApplyDesk assessor submissions, overwrite native reviewer records or publish applicant outcomes. Record snapshot/transfer receipt, counts and provenance.
5. Provide `Already up to date` on the same snapshot; use a newer **complete** snapshot to reconcile updated, cleared/withdrawn or removed-from-current source responses. Older snapshots must not overwrite newer current views.

**Important existing RRW export limitation:** its general analysis-facing `responses.csv` is a 21-column long-form CSV with a field-key preamble, positional `InstrumentName=instrument_N`, no durable ApplyDesk application key, and special group-scoped representation. Its per-field `Version` is not a globally stable answer ID and can reset after a clear. This output **cannot by itself be treated as a lossless incremental result feed**. A narrow handoff export or companion key/crosswalk metadata is required, built from RRW's authoritative serializers/read services.

Recommended **logical** contents (exact filenames/columns need to be approved):

| Logical item | Required contents |
|---|---|
| `manifest.json` | RRW session, source exercise/link, operation/export ID, protocol/result schema version, timestamp, scope, snapshot completeness flag, digest, member hashes and counts |
| Response rows | Reviewer/assignment reference, stable reviewee key, stable instrument ID and field key/version, answer value/type, source timestamps, submission state and current/withdrawn semantics |
| Completion rows | Status of assigned obligations (not started/in progress/submitted/inactive as RRW actually defines), without answer text |
| Mapping | Immutable/versioned RRW reviewee/instrument/field → ApplyDesk application/instrument/field crosswalk, plus validation of post-handoff edits |

These may be one normalized CSV, several CSVs or ordinary `responses.csv` **plus explicit key files**. Preserve RRW's own group-scoped reviews; import them into an application-specific result only when group→application semantics are explicitly defined. Do not infer membership from a composed group label.

**Snapshot/reconciliation rules:**

- Default import **submitted responses only**. Draft/saved unsubmitted answers are excluded unless separately authorized; missing values remain missing, not zero.
- Scope and completeness must be explicit. **Absence of a row in a complete authorized snapshot** may mean it is no longer current; reconcile with an audited tombstone/supersession policy. **Absence in a partial/restricted snapshot MUST NOT delete existing data**.
- Idempotency key includes source session, export scope and snapshot digest, plus transfer receipt. Same operation ID with changed content is a conflict. Protect against out-of-order concurrent imports.
- Retain enough prior snapshots/receipts to explain corrections; keep one clearly identified current imported view. Mark provenance `Collected in Review Robin`, not `Assessed in ApplyDesk`.
- RRW remains authority for original responses; ApplyDesk remains authority for any decision, release, embargo and its own native form/review records. **Result import never equals publication.**

### 6.6 Confidentiality and permission boundary

The operator must be individually authorized in each application and for each specific exercise/session and data category. Ownership of an ApplyDesk exercise grants **no** RRW session ownership, and owning a RRW session does not grant ApplyDesk applicant-data access.

- Restrict outbound participant data to the chosen purpose. Hidden ApplyDesk questions, attachments, private referee material and other privileged sections do not cross by default.
- RRW result access may include confidential scores/narratives. Results enter a restricted ApplyDesk external-review area. Any later applicant disclosure still respects ApplyDesk confidentiality/waivers, its stage policy, explicit release and embargoes.
- The link must be verified to refer to **this** RRW session created for **this** source exercise and purpose. Never allow a free-text RRW session ID to import arbitrary results into another exercise.
- Export only approved data categories; exclude raw tokens, cookies, Graph credentials, unrelated RRW session data, personnel notes, unrestricted logs.
- Source and receiver have independent retention/audit requirements. Live-result retention and treatment of corrections after publication require policy decisions before rollout.

## 7. Transport, trust and API contract

### 7.1 Recommended v1: same-origin browser-mediated transfer

The operator's authenticated browser may be the **ephemeral byte carrier** because Cordware apps share the same HTTPS origin and Easy Auth. It does **not** create a cross-app service principal or grant source-side rights in the destination.

- Outbound: user clicks in ApplyDesk; new RRW tab opens synchronously to a safe holding page; browser fetches an ApplyDesk-generated RRW-native bundle and posts it to RRW's authenticated create endpoint; successful tab moves to RRW Session Home.
- Status: while ApplyDesk page is open, browser fetches narrowly scoped RRW JSON, then displays it; no business-state replication.
- Inbound: user clicks in ApplyDesk; browser fetches fresh RRW export in memory and posts to ApplyDesk's protected import endpoint; stays on ApplyDesk page.

Use same-origin HTTPS, cookie-auth appropriate CSRF defenses, Origin/Fetch-Metadata checks, response `Cache-Control: no-store`, bounded package sizes and rate limits. Do not put sensitive data in URLs, HTML hidden elements, client storage, analytics, application logs or browser download folders by default. Do not forward Entra/Graph tokens or DB credentials between app backends. Support normal app-independent fake-auth/test fixtures locally.

**Trust limitation:** a user-controlled browser can change the CSV bytes/manifest. A receiver that simply checks an unsigned manifest and validates its own CSV cannot claim that the package *came from* the purported specialist. For verified app-to-app provenance, implement **one** tested mechanism before assigning the corresponding trust label: (a) short-lived sender-signed digest/receipt bound to actor, source/target refs, scope, digest, expiry, plus key management; or (b) authenticated receiver-to-sender verification of a server-generated receipt/digest. The same problem applies in the reverse direction. A manual upload may be allowed as `operator supplied`, but must be distinctly labeled and cannot create a verified link by assertion alone.

**Atomicity boundary:** one app's DB transaction cannot include the other. Receiver commit + source link save is a recoverable two-step workflow, not a distributed transaction. Durable transfer IDs and independently retrievable receipts make an interrupted browser flow recoverable.

### 7.2 Illustrative app-owned endpoints (not implemented)

| Application | Example method/path | Contract |
|---|---|---|
| ApplyDesk | `GET /applydesk/api/v1/exercises/{id}/handoffs/reviewrobin/setup` | Authorize source scope, create immutable RRW setup snapshot, record source receipt |
| Review Robin | `GET /reviewrobin/operator/handoffs/new` | Authenticated new-tab holding/failure view |
| Review Robin | `POST /reviewrobin/api/v1/handoffs/sessions` | Validate and atomically create new draft + setup, return receipt and Session Home URL |
| Review Robin | `GET /reviewrobin/api/v1/handoffs/{transfer_id}` | Authorized receipt retrieval/recovery, not open enumeration |
| Review Robin | `GET /reviewrobin/api/v1/sessions/{id}/handoff-status` | Session-owner-scoped status projection; JSON |
| Review Robin | `POST /reviewrobin/api/v1/sessions/{id}/handoff-export` | Audited fresh response/completion snapshot scoped to linked workflow |
| ApplyDesk | `POST /applydesk/api/v1/exercises/{id}/handoffs/reviewrobin/results` | Authenticated, independently authorized reconciliation into restricted external-results store |
| ApplyDesk | `GET /applydesk/api/v1/exercises/{id}/handoffs` | Authorized linked sessions, receipt and import metadata for ApplyDesk UI |

Actual route names, auth dependencies, request media types and ownership policies shall be reconciled with current FastAPI implementation. **Endpoints do not replace the existing manual upload/download routes.** Avoid a Cordware-host endpoint with unrestricted authority over every app.

### 7.3 Operation responses and failures

A successful **create** receipt contains operation/transfer ID, `created` or `already_created`, destination app/ref/relative URL, imported categories/counts, schema versions, and nonblocking warnings. A **status** response declares its actual count definitions, authoritative as-of timestamp, and session status. An **export** receipt declares scope, completeness, snapshot digest/version/time and authorized content types. An **import** receipt declares source export ID, local import time, accepted/new/changed/no-longer-current counts and a no-op outcome when identical.

Use stable error categories such as `not_authorized`, `unsupported_version`, `invalid_package`, `mapping_error`, `invalid_setup`, `not_editable`, `duplicate_conflict`, `session_code_conflict`, `source_unavailable`, `stale_snapshot`, `export_scope_denied`, `source_unverified`, `rate_limited` and `unexpected_failure`. Conventional status guidance: `401/403` auth, `404` scoped record existence where confidentiality requires, `409` conflict, `413` size, `415` format, `422` validation, `429` rate, `5xx` unexpected. Errors must be actionable **without including full row payloads or confidential answers in browser URLs or server logs**.

| Event | Required outcome |
|---|---|
| Destination refuses operator role / source refuses data access | No unauthorized transfer or leaked record details |
| Any setup file fails validation | No RRW session or partial setup created |
| Same transfer replayed / two tabs race | One RRW session; same authorized receipt or explicit conflicting-digest refusal |
| Creation commits, acknowledgement is lost | Recover original session through transfer receipt |
| Status unavailable or permission revoked | Show unavailable/stale; last successful import unchanged |
| New results fail mapping / trust / schema | No mutation of previous valid imported projection |
| Older result snapshot arrives late | Never roll the current mirror back silently |
| RRW data changes after last import | Status may update; imported data remains labeled by last import snapshot |
| New tab blocked/closed | Recovery/re-open, no second unintended creation |
| Existing RRW session has responses | No automatic destructive setup re-import or Settings replacement |

## 8. Example user interface

**ApplyDesk exercise — Linked Review Robin**

Before handoff: `Create in Review Robin`, description of included population/instruments, any blocking mapping errors. After creation: RRW session code and purpose, `Open in Review Robin`, `Refresh status`, `Import Review Robin results`, last successful status time and last import snapshot time. Multiple sessions display independently. Failure messages distinguish unavailable, unauthorized, incompatible and stale. Display explicitly whether setup was **complete** or **roster-only**.

**RRW new tab:** temporary RRW-controlled loading/failure surface → standard populated **Session Home** on success. All subsequent validation, `Prepare`, assignment generation, invitations, editing and reviews remain native RRW actions.

**ApplyDesk results area:** imported data is visibly sourced from RRW, separately classified from native assessor contributions; re-import receipts show new/updated/no-longer-current counts and any excluded/unmapped items. No applicant-visible publication is implied.

## 9. Other Cordware workflows

| Orchestrator → specialist | Initiate | Observe | Retrieve |
|---|---|---|---|
| **RA Lifecycle → ApplyDesk** | Draft recruitment exercise/panels/invitation list (when ApplyDesk has matching importer) | Recruitment application/review stage and permitted counts | Validated finalist/selection outcomes imported into Lifecycle cohort; **selection is not appointment** |
| **RA Lifecycle → RRW** | New peer-review session from authorized RA/staff roster and review template | Review completion and workload | Usually limited completion metadata; confidential raw peer feedback only under separate explicit policy |
| **ApplyDesk → RRW** | New complex review session with compatible rosters/instruments | Actual RRW lifecycle and submission counts | Source-attributed restricted responses and completion snapshot |
| **RA Lifecycle native allocation** | No app-to-app transport required | Native solver/run state | Confirmed primary neighborhood assignments into Residential core, not unreviewed suggestions |

RA Allocation should ultimately be absorbed from `res-apps` into the Residential Operations codebase. Its selection+placement kernel, preflight, hard/soft constraints, manual pin/redo and regression fixtures have their **own functional/migration specifications**. Do not treat it as a separately hosted specialist merely to satisfy this protocol. The Residential core owns appointments and neighborhood assignments; Lifecycle controls allocation proposals and their explicit confirmation.

## 10. Deliberate non-goals and unresolved decisions

### 10.1 Non-goals

- Imposing two rigid kinds of Cordware app, or requiring every app to implement every capability.
- Rebuilding specialist engines inside ApplyDesk/RA Lifecycle; a central database or generalized integration/workflow service.
- Automatic bidirectional data synchronization, scheduled background exports, webhooks, event bus or distributed transactions for v1.
- Direct cross-app DB queries/writes, universal person table or shared app authorization role.
- Arbitrary update/replace of existing RRW sessions, import of RRW assignments/responses through its normal Quick Setup, or bypassing RRW's Prepare/Validate steps.
- Claiming ApplyDesk forms/instruments are already RRW compatible, or that the current RRW analyst CSV is a safe durable import feed.
- Implicitly releasing results, initiating email, making recruitment decisions or activating appointments.

### 10.2 Decisions that MUST be resolved before dependent implementation

| Gate | Decision / investigation |
|---|---|
| **D1 — Form/instrument compatibility** | Exact supported ApplyDesk→RRW question/response/branching/visibility/rule mapping and whether complex assessor-to-application pairings can be represented without semantic loss |
| **D2 — Stable return keys** | Exact RRW response/obligation/instrument/field IDs and crosswalk format; correction/withdrawal/group-scoped handling; complete vs partial snapshot rules |
| **D3 — Source proof** | Signed receipts versus authenticated verification; keys, expiration, replay prevention, whether manual packages may be merely operator-supplied |
| **D4 — Status vocabulary** | Which RRW live counts/denominators and lifecycle states safely represent progress; no invented single percent |
| **D5 — Source eligibility and permissions** | Which submitted/withdrawn/returned-to-draft applications are eligible; who may request each transfer, including different RRW owners and ApplyDesk operators |
| **D6 — Session and link lifecycle** | Multiple RRW rounds, changed ownership, deletion/archive, re-link, failed transfer recovery and concurrency between importing operators |
| **D7 — Review confidentiality/retention** | Approved return scopes, restrictions, how imported material relates to ApplyDesk waiver/release/embargo, corrections after publication, retention/purge |
| **D8 — Operational envelope** | ZIP/member/row/time limits, synchronous versus bounded async export execution, large-session performance, retention of short-lived transfer artifacts |

These are **explicit design gates**. Coding agents may implement independent primitives while blocked gates remain open, but shall not invent policies or assert full end-to-end readiness.

## 11. Acceptance scenarios (system-wide)

1. ApplyDesk creates a new RRW draft with selected reviewers, reviewees, permitted relationships, compatible instruments and settings; a new tab opens on populated **Session Home**, with **zero generated assignments/invitations**.
2. Import of invalid Settings, roster or relationship data leaves no RRW session; a repeating click/timeout/concurrent retry yields only one session and a recoverable receipt.
3. RRW's existing manual Quick Setup import behavior and contracts remain unchanged; no new duplicate CSV parser or invented Assignments importer appears.
4. Two ApplyDesk applications submitted by one person retain distinct reviewee/crosswalk keys and import separately; identity aliases never substitute for application IDs.
5. A source instrument with unsupported branching or confidentiality setting blocks full setup rather than silently changing its meaning; explicit roster-only mode is labeled.
6. The RRW operator works normally: edits settings, validates, prepares assignments and collects responses; ApplyDesk does not modify the live RRW session via status polling.
7. ApplyDesk displays current **RRW-defined** status and its timestamp without importing response content. Unauthorized RRW status is not exposed to ApplyDesk-only operators.
8. One click in ApplyDesk triggers a fresh RRW response/completion export and imports into restricted external results without RRW-tab navigation or manual files.
9. Identical repeat snapshot is a no-op; newer corrected/cleared/withdrawn response is reconciled from a **complete** snapshot; incomplete exports do not delete previously imported current rows.
10. Changed RRW instrument order/identity or group-scoped configuration cannot accidentally remap an answer; unsupported changes block safe import with an explanation.
11. A stale result snapshot cannot overwrite a newer committed one; a failed export/import leaves the last valid import intact and visibly dated.
12. Verify source attestation (when claimed), actor and target-side rights, link scope and archive integrity; refuse swapped content, mismatched origin, oversize and unauthorized imports.
13. Imported confidential RRW results remain operator-restricted and unpublished; an RRW import does not imply ApplyDesk applicant release, recruitment selection or RA appointment.
14. Manual export/import parity uses the same specialist schemas and validation, with distinctly labeled **operator-provided** provenance if no verified source receipt.
15. Each app runs/test independently and mounts under Cordware; cross-package business imports and cross-database writes remain prohibited.

## 12. Current repo references and implementation status

These paths in **`philoyhc/review-robin-web`** are the relevant domain specifications; agent handoff lists required code/service inspection:

- [`cordware/spec/host.md`](https://github.com/philoyhc/review-robin-web/blob/main/cordware/spec/host.md) and [`cordware/spec/identity.md`](https://github.com/philoyhc/review-robin-web/blob/main/cordware/spec/identity.md) — mounting, Easy Auth identity, Graph and boundary conventions.
- [`spec/csv_contracts.md`](https://github.com/philoyhc/review-robin-web/blob/main/spec/csv_contracts.md) — **authoritative RRW import/export formats**.
- [`spec/quick_setup_card_spec.md`](https://github.com/philoyhc/review-robin-web/blob/main/spec/quick_setup_card_spec.md) — RRW's existing five-category, atomic **save** pipeline; new create+save atomicity requires explicit attention.
- [`spec/assignments.md`](https://github.com/philoyhc/review-robin-web/blob/main/spec/assignments.md), [`spec/instruments.md`](https://github.com/philoyhc/review-robin-web/blob/main/spec/instruments.md) — rules, assignments and instrument semantics.
- [`spec/permissions.md`](https://github.com/philoyhc/review-robin-web/blob/main/spec/permissions.md) — RRW Operator and session-owner authorization.
- [`spec/extract_data.md`](https://github.com/philoyhc/review-robin-web/blob/main/spec/extract_data.md) — response analysis/download surfaces.
- [`applydesk/docs/applydesk_functional_spec_v0.6b_agent_handoff.md`](https://github.com/philoyhc/review-robin-web/blob/main/applydesk/docs/applydesk_functional_spec_v0.6b_agent_handoff.md) — specified ApplyDesk, **not** proof of implementation.

**State as checked 3–4 November 2026:** RRW's CSV setup and response export machinery exists; the linked-handoff endpoints/status projection/response import are **proposals**. ApplyDesk is an advanced functional specification, not a completed hosted app. Before coding, re-read current `main` and reconcile any changes. Private Cordware deployment/runtime specifics remain owned by the private repo and must not be pasted into public specs.

## 13. Review notes and rulings (2026-11-04)

Taken against RRW `main` at `97908801`. The rulings are the author's;
the rest is a review, and changes nothing above until the spec is
revised.

### 13.1 Rulings

- **Parked.** No implementation now; revisit when ApplyDesk or RA
  Lifecycle is further along. Either may turn out to be the first
  consumer: RA Lifecycle → RRW peer review needs no instrument mapping
  if it uses RRW's own templates.
- **v1 sends rosters only.** The first handoff carries the roster files
  (Reviewers, Reviewees, Observers, and Relationships as pair context)
  and no `settings.csv`; instruments, fields and rules are built in RRW.
  This defers D1's instrument mapping entirely, and §6.2's
  "roster-only" mode becomes the v1 contract rather than a fallback.
  Whether Relationships counts as a roster here is this review's
  reading, to confirm at revisit.
- **One operator in both apps (D5, in part).** Two apps interoperate
  only for a person who is an operator in both. Someone authorized in
  one app sees no interoperability control there, and the other app
  refuses them (`not_authorized`); there is no cross-app delegation.

### 13.2 Claims checked against RRW

Confirmed: roster files are capped at 1 MiB and 5,000 rows
(`app/services/csv_imports/_parse.py`); RRW has no Assignments importer;
`responses.csv` is 21 columns with a field-key preamble and positional
`instrument_{n}` names; New session commits the session before its
staged files are checked, so a refused file leaves an empty draft, by
design today (`spec/quick_setup_card_spec.md`, "Failure mode").

### 13.3 What the spec does not yet say

1. **One person, two applications.** RRW refuses a duplicate
   `RevieweeEmail` within a file as a blocking error. The handoff must
   send the ApplyDesk application ID as the reviewee identifier, not the
   applicant's email. Validate then warns
   `reviewees.unreachable_for_results` for every row, which the handoff
   should explain or suppress.
2. **D2 is half answered.** An instrument's `session_seq` is assigned
   once and never renumbered, and `field_key` is unique per instrument,
   so `session_seq` + `field_key` is a stable field key, unlike
   `instrument_{n}`. The response and obligation identity remain open,
   since a field's `Version` resets after a clear.
3. **The directory check bounds a create.** A handoff create resolves
   every roster address through Graph within RRW's 120 s budget. The
   upload countdown's kept answers (RRW segments 20H and 20I,
   `spec/setup_pages.md`) fit the §6.1 holding tab: count down there,
   then create. D8 should name it.
4. **RRW has no API surface.** There are no `/api/` routes today, so
   §7.2's endpoints are a new layer: an error envelope, a CSRF posture
   beyond SameSite=Lax (Origin / Fetch-Metadata), and registration with
   RRW's URL-crawl and spec-coverage tests.

### 13.4 Recommendations for the revisit

1. Start with the handoff's §3 reconciliation report; build nothing for
   a consumer that does not exist yet.
2. Atomic create + setup has value on its own: it removes the empty
   draft today's New session leaves. It changes an existing page, which
   the handoff's Slice B rules out, so it needs a ruling.
3. For D3, a signer supplied by the host: every Cordware app runs in one
   process behind one Easy Auth, so a small Cordware helper that signs
   and verifies digests with a key from an app setting fits §3's
   "stateless host supplies transport helpers", with no cross-app import
   and no server-to-server call.
4. Keep this document in `cordware/docs/` as a proposal until D2 and D3
   are ruled; the work then opens a segment plan whose Doc impact names
   `cordware/spec/interoperability_and_orchestration.md`, and the spec,
   trimmed of what §3, §6.6, §10 and the handoff repeat, lands at its
   close.

Still open from the review: D7, whether results imported into ApplyDesk
follow a different retention policy from RRW's own.

---

**Consolidated decision:** Cordware standardizes a modest, versioned **initiate → observe → retrieve** interoperability contract. Specialist apps own their domain; orchestrators coordinate it. CSVs carry structured bulk payloads; JSON carries control and status; links and receipts provide recoverable one-click cooperation without tight coupling.
