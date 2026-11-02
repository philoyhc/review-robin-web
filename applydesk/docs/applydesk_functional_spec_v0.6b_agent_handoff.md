# ApplyDesk — Functional Specification

**Version:** 0.6b (v0.6a plus the author's rulings of 2 November 2026: hard Application deadline, withdrawal window, Entra-only participants, sizing; and the implementation review's comments)  
**Date:** 2 November 2026  
**Status:** Reviewed functional baseline. Suitable for agent planning and explicitly bounded implementation slices; unresolved policy/engineering decisions below must not be invented by an agent. Not a blanket implementation authorization.  
**Application name:** ApplyDesk  
**Mount:** `/applydesk/`  
**Production URL:** `https://cordware.nus.edu.sg/applydesk/`  
**Development home:** Public `philoyhc/review-robin-web` repository  
**Production integration:** Private `philoyhc/cordware` repository, through the existing allowlisted import and release process

**Changes from v0.6a (author, 2 November 2026):**
- **Hard deadline:** the end of the Application stage is a hard deadline. No application can be started, submitted or resubmitted once the Review stage begins, and no late exception extends past it (§6).
- **Withdrawal window:** withdrawal is available only until the exercise's timeline is completed (§6).
- **Entra only:** every participant (applicant, referee, assessor, operator) signs in with Entra. External or magic-link access is out of scope unless a separate access model is approved later (§2.1).
- **Sizing:** sized for three likely scenarios, with the per-application assessor cap lowered from 500 to **50** and a tested design envelope added (§7.8). Panels may also serve as referee nomination pools. Large peer-review exercises belong in Review Robin.
- **From the implementation review:**
  - **The email-sender constraint:** delegated `Mail.Send` only, so there is no unattended sending (§7.4, G5).
  - **Embargoes:** enforced on read, without a scheduler (§8.2, G7).
  - **RRW form-engine reuse:** decided at G1, by a shared package or an explicit fork (§10.2).
  - **File storage:** new infrastructure, with PDPA retention settled before real documents (§5.3, G8).
  - **Corrections:** the registry `icon` (§10), and the handoff note moved to §15.

## 1. Purpose and scope

ApplyDesk is a configurable application, reference/assessment collection, and applicant-communication service hosted within Cordware. It enables an **operator** to establish an application exercise; **applicants** to submit answers and supporting documents, nominate reviewers where configured, and track published progress; and **referees** to provide letters or references and **assessors** to complete structured instruments. Operators extract applications and reviews for **downstream, offline processing and selection**.

ApplyDesk is **not** an end-to-end selection-management or adjudication system. It does not prescribe the external decision-making model, run selection committees, calculate binding decisions, or manage approvals beyond the application/review process. It may nevertheless provide an apparently end-to-end **communication experience** for applicants through timelines, status announcements, outcome imports and controlled release.

The application should serve varied university contexts, including scholarships, fellowships, internships, grants, awards, nominations, project proposals and expressions of interest. The use of the word *application* is broad; the operator may choose exercise-specific public labels.

### 1.1 Design principles

1. **Configurable exercises, deterministic core.** Operators configure forms, deadlines, reviewer modes and communications, but the application uses a bounded set of explicit, testable lifecycle transitions rather than a general workflow designer.
2. **Applicant-initiated submission.** Unlike Review Robin's primarily operator-established reviewer/reviewee rosters, ApplyDesk begins with signed-in applicants creating their own application records.
3. **Review is optional and configurable.** An exercise may collect references/endorsements, assessments, both, or no external reviews.
4. **Explicit information boundaries.** Applicants know which application sections reviewers can see; the server enforces those boundaries in all views, downloads, and APIs.
5. **Offline selection is authoritative.** Downstream processing determines decisions; ApplyDesk publishes only outcomes expressly entered/imported and released by authorized operators.
6. **Communication is distinct from internal state.** Internal events do not automatically become applicant-visible milestones or decisions.
7. **Bounded autonomy and provenance.** Applicant-sent email requires the applicant's explicit action; operator-sent invitations use an independently authorized sending method. Exports, outcome imports, releases and administrative interventions are auditable.

## 2. Roles and access

| Role | Principal responsibilities | Restrictions |
|---|---|---|
| **Operator** | Create/configure exercises; define applicant and contributor forms; open/close intake; oversee submissions and reviews; manage reviewer assignments/exceptions; export; publish updates and outcomes | Does not impersonate an applicant for delegated email; cannot bypass confidentiality policy silently |
| **Applicant** | Create/edit their own draft; upload files; submit, withdraw their own submission until the exercise's timeline is completed, or revise a submitted application only after an operator returns it to draft during the Application stage; nominate reviewers; send invitations from their signed-in mailbox when that route is configured; view allowed status, updates and released outcomes | Cannot view restricted internal notes or confidential reviews; only operator-released, eligible non-confidential sections may become visible after Application stage |
| **Referee** | View only permitted application information; provide a narrative reference/endorsement and/or upload a letter; submit it | Cannot view other applications, hidden applicant sections, or other reviewers' answers by default |
| **Assessor** | View only assigned applications and permitted material; complete one or more assigned structured instruments; submit responses | Cannot see hidden applicant sections or other contributors’ answers by default |
| **Platform super-admin** | Inherits Cordware identity context; any ApplyDesk-specific powers must be explicit and audited | Platform super-admin status should not silently imply unrestricted access to sensitive content |

A signed-in individual may hold more than one role across exercises or even within one exercise. Role and record-level authorization must be evaluated in context. Reviewer eligibility, conflicts of interest, operator delegation, and whether applicants may nominate an operator are open policy settings; default to conservative restrictions.

### 2.1 Identity

- Use the existing Cordware identity service backed by Azure Easy Auth / Microsoft Entra; do not create a separate authentication system.
- Bind accounts to the trusted Entra **tenant ID and object ID**, not an email address alone. Preserve verified email, UPN and display name as identity attributes/snapshots; names and mail addresses can change or differ.
- Reuse the Cordware Graph directory lookup/search mechanism for reviewer nomination. Directory suggestions are not proof of eligibility to review.
- **Every participant signs in with Entra:** applicants, referees, assessors and operators alike. External/non-Entra participants are **out of scope** until and unless a separate access model (e.g. magic links) is approved.
- Application-level authorization is owned by ApplyDesk, not the stateless Cordware host.

## 3. Domain concepts

| Concept | Meaning |
|---|---|
| **Exercise** (working internal term; operator-facing label configurable) | One operator-created call for applications, with configuration, forms, deadlines, reviewer policy and timeline |
| **Application** | One applicant's evolving submission for an exercise, with a stable identifier and version history |
| **Applicant form** | Configured questions and attachment requests, divided into reviewer-visible and reviewer-hidden sections |
| **Nomination** | Ranked candidate proposed by an applicant, separately for referees and assessors; nomination alone confers no access or right to invitation |
| **Contributor assignment** | Operator-selected/authorized referee or assessor linked to an application, with invitation, acceptance/refusal and completion states |
| **Panel** | Operator-maintained exercise roster (maximum five panels, maximum 200 unique members per panel), usable for explicit whole-panel assessor assignment and/or as an applicant nomination pool for assessors or referees; panel membership is not itself an assignment |
| **Panel assignment operation** | Previewed, validated and audited generation of assessor–application assignments and instrument obligations for one, selected or all applications |
| **Assessor instrument** | One exercise-level structured questionnaire/rubric (maximum three distinct definitions per exercise) assigned to selected assessors |
| **Reference / endorsement** | Reviewer-supplied opinion, recommendation or testimonial, generally confidential |
| **Assessment** | Reviewer evaluation of application materials, potentially including scores and structured comments |
| **Exercise stage** | Official operator-controlled **Application** or **Review** stage (and later communication/outcome stages as designed); stage is distinct from any application’s submission state |
| **Timeline milestone** | Scheduled event or operator-published communication shown to applicants under explicit visibility rules |
| **Outcome** | Decision/result imported or entered from downstream processes; not public until released |
| **Export** | Versioned snapshot of applications, reviews, metadata and permitted documents for offline processing |

Avoid using a single `status` field for application submission, reviewer completion, internal processing, and publication. These are independent dimensions.

## 4. Operator configuration

An authorized operator can create an exercise and configure:

1. Name, short code/slug, description, purpose, contact and public instructions.
2. Opening and closing dates/time zone; an explicit **Application → Review** stage boundary, optional review deadline, anticipated outcome date and other milestones.
3. Discovery/eligibility: either all signed-in institutional users or an operator-maintained invitation-only list. Directory identity alone is insufficient to infer cohort membership. Invitation-only access must be checked server-side, not merely hidden from listings.
4. Applicant form, including typed fields, help text, validation and required/optional questions.
5. Document requirements: allowed categories, type/size limits and visibility.
6. Review collection: no contributions, **referees** (document/narrative references), **assessors** (structured instruments), or both. Referee assignment requirement and maximum are each 0–5 per application; assessor assignment requirement and maximum are 0–50 **unique assessors per application**. Assessor instruments: up to three distinct definitions per exercise. Separate applicant-nomination caps for each category: 0–10, set by operator (see §7).
7. Panels: up to **five** named panels per exercise, each with up to **200 distinct institutional members**; directory/CSV population; panel-based whole-group assessor assignment, or applicant nomination of assessors or referees from operator-designated pools (see §7.7). Reviewer nomination/dispatch route per exercise: (a) applicant selects reviewers and sends calls directly; (b) applicant proposes reviewers but the operator reviews, can add/replace/edit nominations and sends calls; or (c) the operator selects reviewers and sends calls. Operator intervention and any modification of applicant nominations are audited.
8. Reviewer-visible applicant form subset and reviewer response confidentiality policy, including applicant waiver behavior (see §§5, 7).
9. Applicant submission/withdrawal and operator-only return-to-draft controls, including mass return to draft exclusively during the Application stage. The end of the Application stage is a hard deadline (§6); any late exception happens within it.
10. Applicant-facing timeline and communications, including what is published automatically, if anything.
11. Outcome import/publication settings and applicant-facing result templates.
12. Export schema and operator access (within standard, stable export conventions).

An exercise can be drafted, validated, published/opened, closed to new submissions, and eventually archived. Validation should flag missing forms, invalid deadline ordering, mismatched reviewer requirements and unsafe visibility configurations. Changes to a published exercise must respect existing submitted applications and form versions. **Edits to published exercise details require applicant-facing change communication, including an announcement email** (sent by the editing operator's delegated identity unless G5 approves another sender); the exact material-change definition, recipients, safe message content, dispatch, failure/retry behavior and treatment of trivial edits must be settled before this behavior is built. Do not silently alter exercise details or interpret every autosave/keystroke as a send instruction.

### 4.1 Contributor categories

**Referees:** provide individualized letters of recommendation, reference or endorsement, optionally with a narrative entered directly. Each application may have at most **five active or fulfilled referee assignments**, with operator-configured required and maximum counts from 0 to 5 (required ≤ maximum). A nominee is not automatically an assigned referee.

**Assessors:** evaluate applications through **structured, Review Robin-style tabular instruments**, from brief ratings to substantial rubrics or narrative questions. The operator may define **up to three distinct assessor instruments per exercise** (shared definitions across applications); assessors may be assigned one or more of those instruments, either individually, through an explicit panel application or from validated CSV rows. Each application may have up to **50 unique active or fulfilled assessors**, with operator-configured required and maximum counts from 0 to 50 (required ≤ maximum). An assessor completing three instruments counts **once**, not three times, toward the people cap. Instrument assignments and responses are separately recorded.

An exercise can have referees, assessors, both, or neither. A person may serve in both capacities when permitted and holds distinct assignments. Do not infer confidentiality from category; see §7.5. The old substantive-versus-lightweight distinction and proposed 50-person rating extension are **retired**: short ratings are assessor instruments. Complex roster generation, inter-rater studies and multi-round review management remain possible reasons to use Review Robin instead.

## 5. Applicant forms and documents

### 5.1 Visibility partitions

Every applicant form is structured into two clearly labelled parts:

- **Shown to reviewers:** questions, answers and attachments that any assigned reviewer authorized to view the application may access.
- **Not shown to reviewers:** information accessible to the applicant and authorized operator(s), excluded from all reviewer views and document download routes.

Applicants see this distinction **while entering information**, before submission. The reviewer-facing preview must reflect exactly what reviewers will actually receive. The interface should not imply that hidden information is invisible to operators.

The initial contract is **section-level visibility** rather than a complex rule editor per question. The visibility label applies to each attachment as well as to text/structured responses. Display filters are insufficient: authorization must be enforced at query, serialization, template, file-download and export levels.

The two-part partition determines **which applicant-provided content reviewers can access**. A separate confidentiality setting determines **which reviewer-provided content applicants can later access**. These controls must not be conflated.

### 5.2 Form capabilities

Design the applicant form editor and assessor instrument editor **by borrowing heavily from Review Robin**: its mature field types, validation, question presentation, instrument layout, tabular response formats and configuration UX are the starting functional reference. Exclude RRW's **generalized assignment-rule engine** from ApplyDesk. Adapt behavior and reusable patterns without directly importing RRW business modules across application boundaries. Exact supported field types, branching and repeaters remain subject to an explicit parity/difference inventory against RRW.

For each application retain the form version or immutable published form schema needed to interpret historical responses. An operator changing questions after submissions exist must not reinterpret old answers silently.

### 5.3 Documents

- Applicants upload documents into private, non-public Azure Blob Storage; the database stores only metadata, object keys, integrity information and access classification.
- Apply limits for file sizes, types, number of files, and total quota; implement secure streaming and avoid user-supplied paths/filenames as storage identifiers.
- Provide malware/unsafe-file scanning strategy before production use, including quarantine and refusal semantics; do not assume existing storage permissions are sufficient.
- Downloads use authenticated, short-lived server-authorized access (or equivalent), with no public blob URLs.
- Attachments belong to a specific application/submission revision and visibility section; replacement and deletion actions are audited.
- Retention, purge and backup implications require explicit policy before production data is accepted. Retention must satisfy the PDPA before any real applicant document arrives.
- **This is new infrastructure.** Nothing on Cordware stores files today. The private Blob container, its access identity, malware scanning (likely Microsoft Defender for Storage, at a cost), quotas and backups all need IT's agreement. Raise them with IT early, in parallel with building, through the private repository's infrastructure process.

## 6. Application lifecycle

**Two distinct state dimensions:**

- **Exercise stage** includes an official **Application** stage followed by a **Review** stage. The operator controls the stage boundary as an auditable transition; subsequent outcome/communication milestones remain separately configurable. A received review does *not* by itself mean the exercise has entered the Review stage. The exercise stage is separate from publication/open/close and from independently configured deadlines; the exact transition trigger and any scheduled transition require an implementation decision before stage mutation is coded.
- **Application submission state** includes `draft`, `submitted`, and `withdrawn`, with recorded historical transitions and submission versions. An authorized operator can move `submitted → draft → submitted` **only while the exercise remains in its Application stage**. Applicants cannot initiate this reopening. Operator **mass return to draft** is supported under the same stage restriction; bulk actions must preview affected records and preserve per-application audit history. After the official Review stage starts, neither individual nor bulk return-to-draft is allowed.
- **The end of the Application stage is a hard deadline.** Once the Review stage begins, no application can be started, submitted or resubmitted, and no late exception extends past it. An earlier closing date, if the operator sets one, falls within the Application stage; an operator-granted exception (e.g. returning one application to draft) is possible only before the stage ends.

**Withdrawal is applicant-controlled and available after submission until the exercise's timeline is completed**, including after the Review stage starts. Once the timeline is completed, withdrawal is no longer offered; the exact trigger (e.g. the operator closing the exercise after its final milestone) is part of G3. Withdrawal is not a way to edit or reopen: record when/why (reason optional), preserve audit and received reviews, and prevent the withdrawn application being treated as actively submitted. An operator should be alerted when a withdrawal occurs after assignments, reviews, exports or outcome publication; any needed downstream correction/notification is separately governed. Reapplication and how a withdrawal affects the separately enforced per-applicant 1–5 application allowance remain to be specified. Withdrawal does not release an admissions "slot": no such slot exists.

**Anticipated applicants (1–200) is a resource-planning estimate, not an admission quota.** Operators configure an expected population between 1 and 200 as workload metadata. It does not reserve places, ration applications, or prevent the 201st or later eligible applicant from applying; draft or withdrawn status does not affect an artificial capacity pool. Report actual distinct applicants, application counts, referee/assessor assignments, instrument obligations, documents and estimated storage separately. If actual demand exceeds the estimate, raise a nonblocking operational warning as appropriate, never refuse a submission on that basis. An operator independently configures **1–5 permitted applications per applicant**, which remains an enforceable functional limit; the exact treatment of withdrawn applications for that allowance is open. Deadlines and invitation-only eligibility remain enforceable. A workload estimate must not be presented as a guarantee of Azure capacity.

On submission, applicants' answers, nominated candidates and waiver are locked against direct editing. **Only an operator** can return a submitted application to draft, individually or in bulk, and only during the Application stage. Each action records actor, reason, time and affected version, with an elevated warning if any referee/assessor work is already in progress or submitted. **Existing reviews remain held and usable upon entry to the Review stage**; returning to draft does not delete them or relax confidentiality. Previously established waiver and disclosure snapshots continue to protect submitted or in-progress reviews; updates apply only to future review requests or an explicitly invalidated/reissued review. An operator must be warned about review/submission version mismatch and decide whether an existing review remains applicable. Reviews may be collected early, but **applicants cannot access any reviewer responses during the Application stage, even responses marked non-confidential and otherwise approved for release**. Normal disclosure requires both the Review stage (or a later applicable stage) and explicit operator release of eligible complete sections. Information already disclosed cannot be made unseen.

Submitted versions and material edits have stable version identifiers and timestamps. Exact downstream effects of withdrawing, definition changes and bulk reopening remain to be finalized.
Applicant portal should expose: available exercises, draft and submitted applications, deadlines, reviewer nomination/invitation status permitted for display, the published timeline, and released outcomes.

## 7. Referee and assessor nomination, invitation and contribution

### 7.1 Exercise policy and distinct counts

For **each category independently**, the operator sets an applicant nomination limit **0–10**. Applicants may submit up to that number of **ranked candidates**; a nomination is merely a proposal, never permission to send an invitation or a commitment to receive a report. The operator separately sets required and maximum **actual contributor** counts: referees **0–5**, assessors **0–50**, required ≤ maximum. A category can be disabled. A zero nomination cap permits operator-only selection. Applicant nomination limits do not raise assignment caps: **ten referee nominees can never authorize ten concurrent/fulfilled referee reports**. Operator-assigned individuals need not have appeared in the applicant's nomination list.

Applicants can rank nominees within each category, reorder their own draft nominations and see that order clearly. Retain the submitted nomination order as immutable provenance; subsequent operator selection, ranking edits, replacement and overrides are separate, attributable audit events. Operator choice is not bound by applicant rank. Prevent duplicate identities within a nomination category; handle an identity proposed across categories as two possible roles, each separately authorized.

Counts for assignment-cap enforcement comprise active assignments plus fulfilled contributions that remain valid. Declined, withdrawn or invalidated assignments remain in history but do not consume a slot; a submitted response counts unless explicitly invalidated by an authorized operator with audit and a defined disposition. Enforce capacity transactionally under concurrent changes. Do not implement these limits as a blanket database CHECK on assignment-row totals: history and replacements exceed active caps. The assessor cap is **unique people per application**, not person × instrument combinations. Define safely how to handle outstanding concurrent instrument work for a contributor who declines or is removed.

### 7.2 Selection and invitation routes

An operator configures the route for each exercise; where needed, allow independent configuration for referees and assessors:

1. **Applicant dispatch:** an applicant may send invitations personally, but only to nominations already **authorized for assignment under the category limit and exercise policy**. Mere nomination never grants unrestricted dispatch. If preauthorization workflow is absent, applicant dispatch must preselect an eligible subset and enforce the limit atomically before any send.
2. **Operator review and dispatch:** applicant nominates; operator selects, may add/modify/replace nominees, and sends invitations.
3. **Operator selection and dispatch:** operator chooses contributors without requiring applicant nominations.

Operator overrides must not overwrite the originally submitted candidate list. In each case, log who chose the contributor, who authorized invitation, who sent, and the current state. Applicant nomination may be required, optional or disabled per category. For large assessor scenarios (§7.8), prefer operator-side bulk assignment/dispatch and paginated tracking; applicant-initiated mailing of large lists is not assumed.

### 7.3 Declines and replacement

An invited referee or assessor can accept or decline. Record decline date, optional reason and replacement-needed state. Route replacement to applicant for an applicant-dispatch exercise, otherwise to the operator, with an auditable operator override. The next ranked, unselected candidate may be suggested but is **not** auto-invited. A replacement uses the same authorization and notification rules, and must not exceed the number of active/fulfilled contributors allowed. Historical invitations remain visible to operators without consuming slots when declined/invalidated. Applicant-visible nomination/assignment identities and progress are governed separately by exercise-specific visibility settings.

### 7.4 Delegated email and sender identity

**Applicant dispatch** calls Microsoft Graph `/me/sendMail` using the signed-in applicant's delegated token, after invitation preview and affirmative send. Only selected/authorized contributors can be targeted. Graph `202 Accepted` means processing accepted, **not** delivered. The applicant must be signed in; neither operator nor scheduled worker can impersonate that applicant.

**Operator dispatch** uses an independently authorized sending path (e.g., signed-in operator delegated `Mail.Send`); a shared mailbox/unattended sender is **not** available by assumption. Record sender, recipient, authorization, message/template version, attempt and result; retries must avoid uncontrolled duplicates. Invitation links point to authenticated, assignment-authorized views; possessing a link is never sufficient permission. `cordware.graph` supports directory lookup but production send-helper functionality still requires implementation.

**What the deployment allows today.** The Cordware app registration holds **delegated Graph permissions only**: `Mail.Send` and `User.ReadBasic.All`, consented tenant-wide. It holds **no application permissions**. Mail can therefore go out only as a person signed in at that moment, never from a shared or unattended mailbox. RRW's Graph mail transport is still a stub. So:

- **Every send happens in a signed-in request.**
  - **Applicant-initiated sends** run in the applicant's request.
  - **Operator-initiated sends** run in the operator's, including invitations, reminders, announcements and outcome notices.
  - **Scheduled sends** can follow RRW's precedent of a lazy observer: due messages go out when an operator next opens the exercise, on that operator's token.
- **Anything truly unattended**, such as a timed release notice when no operator is present or a reminder sweep, needs a decision at G5 between two options:
  - accept operator-present sending;
  - ask IT for an application `Mail.Send` permission scoped to one mailbox.

### 7.5 Confidentiality, waiver and release

The operator chooses an exercise-level disclosure policy independently of referee/assessor category:

- **Confidential:** reviewer/contributor responses never appear in applicant-facing views.
- **Non-confidential-capable:** contributions may contain a confidential section and a non-confidential section, the latter **eligible** for applicant disclosure **only on explicit operator release**. An assessor instrument may label response fields/sections accordingly; a referee document must have an explicit disclosure classification and must never leak through previews or downloads.

When an exercise permits **applicant waiver**, the applicant may freely change it in draft; submitting locks the waiver with the submission version. Reviewers told of a valid waiver need not complete a non-confidential response box. An operator may return the application to draft, with heightened warnings if responses already exist, but any already-received contribution retains the disclosure policy and waiver snapshot on which it was requested/submitted. Retracting a waiver must never reveal an existing confidential contribution. Change for future requests only, or explicitly invalidate and re-request past contributions under a new snapshot, preserving audit. Already released information cannot be made unseen. Operator release must support preview, individual and batch actions, and audit, and must never disclose confidential or waived content. **Release is gated by the exercise stage:** no reviewer response of any kind is applicant-visible during Application, notwithstanding a non-confidential classification or an operator action. When release is permitted, it operates on **complete non-confidential sections**, not individual fields; when no valid waiver applies, reviewers must complete the configured non-confidential section before submission. Contributors cannot see one another's responses by default.

### 7.6 Contributor experience and instruments

Referees sign in, accept/decline, and may upload a letter and/or write a narrative reference as configured; assessors sign in, accept/decline, and complete their explicitly assigned exercise-level instruments. Both may save drafts before submitting; the permitted applicant-form subset is strictly **Shown to reviewers** (§5), never hidden fields. Each assessor instrument has a stable definition and version; assignments map the person to one or more of at most **three distinct definitions per exercise**. Scores, ratings, optional/conditionally required comments and longer structured responses are permitted in principle; precise parity with RRW fields and validation remains to be inventoried. Sharing form/validation concepts with RRW must not create direct imports across application boundaries. **Assessor assignment is manual, via whole-panel operations, or by operator CSV upload**, with validation, preview, error reporting, deduplication and transactional cap enforcement. A future **roster-to-assignment-rows utility** may generate importable CSV rows; it does not require porting RRW's generalized assignment-rule engine.

Support high-volume assessor work with pagination and bulk operator tools; operational safeguards (mail throttling, workload bounds, export streaming, timeouts) must be specified and verified before large exercises are enabled. Review revisions and late reviews remain TBD and audited. Applicant withdrawal follows §6 and is available until the timeline is completed.

### 7.7 Assessor panels and explicit bulk assignment

**Adopted contract.** An exercise may define **0–5 named panels**, each containing **0–200 distinct Entra identities**. The 200-member cap is **per panel**, not a total exercise cap. Panels may overlap, and a person may occur in multiple panels; membership is counted uniquely within each panel. An operator populates and maintains membership via directory selection or validated CSV import, with preview, errors, audit and identity normalization. A panel is a roster, **not** an assignment and not an invitation. Its public-facing name and optional applicant-visible description are exercise-specific.

**Two independent uses of a panel:**

1. **Whole-panel assignment:** an operator explicitly applies every current panel member to **one application, selected applications, or all current eligible applications**. This is a single operator action that generates the underlying assessor–application assignments and the selected instrument obligations (one or more of the exercise's up to three defined instruments). Preview target application count, unique assessors, new versus existing assignments, instrument obligations and duplicates before commit. Requiring all applications in one panel application is a convenient bulk operation, not a rule engine. **Do not automatically assign panels to later submissions** in the initial release; an optional future-submission setting is deferred.
2. **Applicant nomination pool:** the operator designates a panel as available for applicant nominations, **for assessors or for referees** (one category per pool designation). Eligible applicants may browse/search its permitted directory attributes, select and rank people **within that category's independent 0–10 nomination allowance**. These are nominations only, subject to the chosen authorization/dispatch route; applicant selection does not create assignments or grant access. The operator may choose how panel membership is displayed and should minimize disclosed directory information.

These uses **may coexist for the same panel**, but the operator must explicitly choose which operation is being performed. Panel membership does not replace direct individual assessor selection or the validated assessor–application–instrument CSV assignment importer (§7.6). Do not add dynamic roster predicates, balancing, matching, quotas or generalized RRW assignment rules. More sophisticated allocations can be computed externally and imported as CSV, or performed in Review Robin.

**Overlap, limits and lifecycle.** When applying overlapping panels, deduplicate assessor–application pairs on stable Entra tenant/object identity. If an assessor is already assigned, merge only new authorized instrument obligations; never silently duplicate an assignment or overwrite completed responses. Enforce the exercise's operator-configured maximum and the absolute cap of **50 distinct active/fulfilled assessors per application** against the proposed *union* of assignments. If any targeted application exceeds its cap or fails validation, show the exceptions and refuse the unmodified bulk action rather than partially applying it. Keep operations transactional or explicitly segmented with durable reporting if a future large-batch design requires it. Changes or removal from a panel **do not retroactively delete or rewrite assignments, invitations, submitted reviews or audit history**. Changes to instruments after work is assigned need a separate controlled revision policy.

**Scale and notifications.** An assessor assigned to many applications should receive an **exercise-level consolidated invitation** rather than one email per assessor–application pair, where dispatch policy permits, and a paginated/searchable workload queue with progress at both assignment and instrument-obligation levels. One person completing three instruments for the same application counts once toward the 50-person cap but generates up to three instrument responses. Review progress distinguishes **unique contributors**, **assessor–application assignments**, **instrument obligations** and **submitted responses**. Any consolidation and dispatch retries must be auditable and idempotent; sending implementation details remain open.

**Workloads:** §7.8 gives the sizing scenarios and the design envelope. With up to five panels, combined membership can exceed the 50-person per-application cap; applying all panels must validate that cap rather than assume all memberships can be assigned.

### 7.8 Sizing and design envelope (author, 2 November 2026)

ApplyDesk is sized for the three most likely exercises, one application per applicant. It must handle them **comfortably**: list pages, previews and bulk operations stay responsive, and an export completes without timing out.

| Scenario | Applications | Assessor–application assignments | Instrument obligations (up to 3 instruments) | Referee assignments | Distinct contributors | Other |
|---|---|---|---|---|---|---|
| **A.** Panel of 30–40, all assessing 100 applicants | 100 | 3,000–4,000 | up to 12,000 | 0 | 30–40 | each assessor's queue holds 100 applications; 30–40 consolidated invitations |
| **B.** Panel-pool of 100, 40 applicants, 2 referees each | 40 | 0 | 0 | 80 | up to 80 | up to 400 ranked nominations (10 per applicant) drawn from the 100-member pool |
| **C.** General directory, 50 applicants, 10 assessors and 1 referee each | 50 | 500 | up to 1,500 | 50 | up to 550 | directory search for nominations; up to 550 individual invitations |

**Design envelope.** Per exercise: up to **200 applications**, **5,000 assessor–application assignments**, **15,000 instrument obligations**, **250 referee assignments** and **600 distinct contributors**. That is scenario A with 25% headroom, and B and C well inside. Load and browser tests run at the envelope's limits. Above it, the operator sees a **nonblocking warning** that the exercise exceeds what ApplyDesk is tested for. The hard caps elsewhere in this spec (5 referees, 50 assessors and 3 instruments per application, 5 panels of 200) still apply.

**Not ApplyDesk's job.** Large reciprocal review, for example 1,000 participants peer-reviewing in groups of five, belongs in **Review Robin**, whose assignment engine and roster model exist for it. ApplyDesk does not grow toward that scale.

## 8. Operator dashboard and exports

Operators need exercise-level metrics and drill-down: application counts by state, referee and assessor assignments by category and status, incomplete/late reviews, failed invitations, submissions by date, and export history. Filters and CSV-oriented bulk operations should work for realistic cohorts without requiring a browser to download every attachment individually.

### 8.1 Export bundle

Provide a structured, reproducible ZIP containing as applicable:

- Exercise manifest, export timestamp, schema/form version and export filters.
- Applications with stable application IDs, applicant identifiers and submission/revision metadata.
- Applicant responses (with explicit field identifiers and visibility attributes).
- Distinct ranked nominations, selected referee/assessor assignments, instrument mappings, authorization/invitation/completion states and retained history.
- Review responses, with review form versions and explicit missing/not-submitted representation.
- Attachments in predictably organized folders and a document manifest, subject to the operator's authorization.
- Published timeline/outcome metadata as appropriate.

Prefer standard CSV (UTF-8) and machine-readable metadata; offer an Excel-friendly option only if it preserves unambiguous identifiers and semantics. Guard exported cells against spreadsheet formula injection. Create export audit records and establish lifecycle and download expiry for generated bundles.

### 8.2 Downstream outcome handoff

Operator may enter or import a minimal outcome file keyed by stable application ID, e.g. optional operator-defined outcome label, applicant-visible outcome text, next-step instructions and optional effective/publication date. The system validates the file, previews changes, rejects conflicting/unknown IDs and requires explicit operator confirmation. Imported outcomes are **unpublished** until the operator releases them. Outcome embargoes and scheduled publication windows **are required**. Enforce them **on read**: an outcome whose release time has not passed is hidden from every applicant view, download and export, with no background job needed. Only a notification at release time needs a sender (§7.4). Operators can correct or withdraw already released outcomes; preserve the prior published value, timestamps, affected recipients and a complete audit trail. Detailed semantics of correction, recipient notification and publication-window enforcement remain to be designed. Re-import, correction and release/withdrawal must be audited.

No internal selection scores, rankings or committee decision processes are mandated. The outcome interface is a communication handoff, not a selection engine.

## 9. Applicant timeline and communications

ApplyDesk provides both:

1. **Scheduled milestones:** exercise opens/closes, review deadline, expected outcome, and operator-defined future dates. System milestone *types* use a controlled code list.
2. **Actual/published events:** submission receipt, invitations sent, operator announcements, published outcome and next steps.

Internal operational data and applicant communication are separate. For example, a review may be completed, an export generated and a committee meeting held offline without automatically exposing these events to the applicant. Audience and notification rules are **exercise-specific**. Operators configure which milestones and updates are visible to all eligible applicants versus application-specific recipients, subject to authorization. Cohort targeting must rely on explicit operator-managed membership rather than inferred Entra attributes.

### 9.1 Suggested applicant-facing timeline

- Applications open (scheduled)
- Application submitted (system-confirmed)
- Referee/assessor invitations sent (system-confirmed; do not imply delivered)
- Application being processed (operator-published)
- Anticipated outcome date (operator-published, explicitly an estimate)
- Outcome available (operator-released)
- Next steps (operator-published)

Edits to published exercise details must **trigger an announcement email**, in addition to recording the change in the portal; notification details and safeguards remain to be specified. An operator can publish narrative updates without importing any decision data. Timeline publication must avoid accidentally revealing confidential review completion, internal deliberations or another applicant's information.

### 9.2 Notifications beyond the applicant's own invitations

The portal itself is the authoritative record of updates. **Announcement emails on published exercise-detail changes are required** (sender per §7.4 and G5); other email notifications about published announcements/outcomes follow per-exercise settings and require a separately approved sender model; they must not assume the applicant remains signed in. Notifications should contain minimal sensitive information and link back to the authenticated portal.

## 10. Proposed technical placement

The public canonical development repository gains a top-level `applydesk/` package, not a submodule of RRW or Utilities. Proposed host registry entry:

| Property | Proposed value |
|---|---|
| Registry name | `applydesk` |
| Mount | `/applydesk` |
| Factory | `applydesk.main:create_app` |
| Logger prefix | `applydesk` |
| Title | `ApplyDesk` |
| Icon | an `app_icons` entry (every `AppEntry` in `cordware/main.py` requires one) |
| Health | `GET /applydesk/health` |

Naming of internal package subfolders remains open; a possible layout is `applydesk/{main.py,identity.py,models/,services/,web/,templates/,tests/,spec/,docs/,guide/,alembic/}`. Respect the repository's existing spec/guide/docs and segment-based development model, but do not introduce scaffolding solely to fill out an idealized tree.

### 10.1 Database and boundaries

**Settled:** dedicated PostgreSQL database **`applydesk`**, with a dedicated runtime principal (`applydesk_app`), Alembic migration history, application-specific role/permission tables, audit and outbox/send-attempt records. Exact infrastructure names need to be accepted in the Cordware production strategy before implementation. A fourth database shares the existing PostgreSQL Flexible Server but not other applications' data permissions.

- Runtime app principal receives only necessary DML privileges on `applydesk`.
- Migration/DDL permissions are separate, controlled by private release workflow.
- No cross-application ORM imports, foreign keys or direct reads into `reviewrobin`, `residentialops` or `supportlogs`.
- Reuse Cordware's identity, directory and common Graph transport only; do not create a new shared role database.
- Keep each application's health route independent of database/Graph calls for reliable diagnostics.
- Extend the host registry, import boundary tests, public CI, private importer allowlist, `deployment/apps.toml`, migration/release checks and monitoring as separate, explicit steps.
- Run with Cordware alone in local and CI environments, including fake identity/directory fixtures; production fake auth remains prohibited.

### 10.2 Reuse strategy

Review Robin is the primary functional reference for applicant forms and assessor instruments, including field definitions, conditional validation, layouts and tabular output. ApplyDesk deliberately excludes RRW's generalized assignment-rule engine; assessors are assigned individually, through explicit whole-panel generation, or from validated CSV rows, with an optional later roster-to-assignment CSV generator. Review Robin also offers precedents for assignment lifecycle, audit, exports and session configuration. **Do not import RRW's private business modules into ApplyDesk.** First build against a documented ApplyDesk contract. **G1 decides how RRW's form engine is reused**, before any form code is written. RRW's instrument editor is large; its main template alone exceeds 5,000 lines. Copying it creates a fork that drifts, and "extract later" means the copy happens first. G1 therefore chooses between two options, and records the choice:
- extract the field schema, validation and rendering into an in-repo package with its own tests, on which both RRW and ApplyDesk depend;
- accept an explicit, documented fork.

## 11. Security, privacy and operational requirements

- Server-side identity, role, exercise and record authorization on every sensitive route and file fetch.
- Explicit isolation of reviewer-visible vs reviewer-hidden material, including error pages, previews, exports, logs, caches and download links.
- Privacy-preserving audit of create/edit/submit, role changes, ranked nomination/selection/replacement, send attempts, reviewer access/submission, export generation/download, outcome imports and publication.
- CSRF protections appropriate to the actual hosting/authentication design, secure session/cookie handling and no caching of applicant/reviewer-sensitive pages.
- Document upload validation, malware scanning/quarantine strategy, safe MIME handling and file download response headers.
- Rate limits and abuse controls for directory search, repeated invitations, large uploads and exports.
- Avoid leaking sensitive application data, reviewer identities or tokens into URLs, mail content, telemetry, operational logs or public CI fixtures.
- Retention/archive/deletion rules for applications, reviews, exports, documents and audit records, including backup restore implications.
- Accessible desktop operator UI and mobile-friendly applicant/reviewer flows, following Cordware's existing responsive guidance; file uploads and long answers must work on phones.
- Data export and import operations must be idempotent or detect replay and record provenance.

## 12. Indicative first release (MVP)

Deliver a **complete vertical slice**, not maximal configurability:

1. One operator can configure/publish an exercise with both visible/hidden applicant sections, an anticipated population of 1–200 applicants for **planning only** (not a submission cap), sized to the §7.8 design envelope, and an enforced allowance of 1–5 applications per applicant; form/instrument behavior substantially follows RRW minus generalized assignment rules.
2. An applicant signs in with Entra, creates a draft, uploads documents, submits before the Application stage ends (a hard deadline), and may withdraw until the timeline is completed. Individual or bulk operator return-to-draft is possible only during the official Application stage; previously received reviews remain held.
3. The exercise may require referees, assessors, both, or neither; up to three assessor instruments are configured per exercise.
4. Operator selects applicant-send, operator-reviewed-send or operator-selected-send policy; assessor assignments may be entered manually, generated by applying panels to selected/all applications, or uploaded as CSV; panels allow applicant nominations of assessors or referees from a designated pool; referee assignments are capped at 5, assessor identities at 50 per application; applicant nominations are capped at 10 for each category, and reviewers may decline, triggering replacement. Implement both sender paths only after delegated operator-send semantics are validated.
5. Referee/assessor signs in, accepts/declines, sees only authorized application data, and completes confidential or non-confidential-capable responses with applicant waiver handling.
6. Operator sees submission/review status, exports a structured bundle and imports or enters an outcome.
7. Operator publishes milestone updates and outcomes, including embargoed/scheduled release and auditable post-publication correction/withdrawal; applicant sees a coherent timeline. No review responses can be seen during the Application stage; eligible non-confidential sections require explicit operator release thereafter.
8. Access boundaries, import/export integrity, confidential review handling and auditing are exercised by tests and browser checks.

Defer advanced multi-round assessor allocation and inter-rater analytics, sophisticated eligibility rules, applicant teams, multi-round review workflows, automatic ranking/decision engines, external (non-Entra) participant access including magic links, large peer-review exercises (use Review Robin), scheduled sending as an applicant, and generalized workflow scripting.

## 13. Design status and outstanding decisions

### 13.1 Settled through v0.6 (author, 2 November 2026)

1. **Cardinality and workload:** an operator records **1–200 anticipated applicants for provisioning/planning only**, not as an enforceable participant cap; actual applicants may exceed the estimate. Each applicant is separately subject to an enforceable **1–5 applications** allowance. Actual workload also depends on reviewers, instruments and files.
2. **Discovery/eligibility:** all signed-in institutional users or invitation-only. Invitation lists support both manual maintenance and CSV upload; restricted exercises are **hidden entirely** from unauthorized users, including direct URL access. Do not infer cohorts from Entra.
3. **Contributors:** Referees (letters/narrative; max 5 valid active/fulfilled per application) and Assessors (structured RRW-style instruments; max 50 unique people per application), up to 10 ranked applicant nominations in each category. Operator independently sets lower nomination caps, requirements and actual assignment maxima. At most **3 assessor instrument definitions** per exercise; multiple instruments do not multiply unique-person count. Selection and invitations remain separate from nomination, with refusal/replacement, override and full history.
4. **Forms and assignments:** heavily adapt RRW's fields, validation, instruments and tabular UX; **no generalized assignment rules**. Assessor assignments are manual, explicit whole-panel generated, or imported via CSV; optional external roster-to-assignment CSV generator remains exploratory. Panels: **up to five per exercise and 200 members per panel**, populated via directory/CSV, may overlap, may be applied to one/selected/all existing applications as assessors, or exposed as applicant nomination pools for assessors or referees. No automatic assignment to future submissions in MVP. Exact field parity remains pending.
5. **Confidentiality and waivers:** confidential-only versus non-confidential-capable sections; applicant waiver editable before submission, locked at submission. No retroactive access to previously confidential material; operator-only disclosure of **whole non-confidential sections**, not individual questions. Without a valid waiver, configured non-confidential sections are required of contributors.
6. **Stages:** official **Application → Review** boundary. An applicant cannot reopen submitted work; an operator may return individual or multiple submissions to draft **only during Application**, with review-sensitive warnings/audits. Existing reviews are retained and may be used during Review. **No applicant access to reviewer responses in Application stage**, even if non-confidential.
7. **Withdrawal:** an applicant may withdraw a submitted application until the exercise's timeline is completed, without erasing history or already received reviews. Exact count replacement/reapplication policy remains open.
11. **Hard deadline:** the end of the Application stage is a hard deadline. No start, submission or resubmission once the Review stage begins, and no late exception past it.
12. **Identity:** Entra sign-in for every participant; external/magic-link access is out of scope unless separately approved.
13. **Sizing:** the three scenarios and the design envelope of §7.8. The per-application assessor cap is 50. Large peer review stays in Review Robin.
8. **Publication:** applicant-visible review sections require operator release and an eligible stage. Outcome entries are free-text, with **embargoes, scheduled releases, correction and withdrawal of released outcomes** supported; detailed mechanics remain to be specified.
9. **Timeline/notifications:** structured milestone codes, operator-authored application-process updates and exercise-specific audiences/notifications. **Published exercise-detail edits trigger announcement email.**
10. **Naming:** product **ApplyDesk**, mount `/applydesk`, freely named exercises, dedicated `applydesk` database and own migrations/audit.

### 13.2 Still open / to specify

1. **RRW form/instrument parity inventory:** exact field types, branching, repeaters, validation, attachment handling and limits; common model versus separate editing surfaces.
2. **Published-exercise revisions:** scope of edits, immutability/versioning, announcement recipients and templates, batching noisy edits, send failure/retry and changes to currently submitted material.
3. **Withdrawal/reapplication edge cases:** how withdrawals affect the applicant's enforced 1–5 application allowance, reapplication and deadline races. There is **no applicant-capacity slot, slot release or final-slot concurrency policy**.
4. **Review during Application:** when early invitations/reviews are allowed, binding of reviews to submission version, warnings and reuse/invalidations on return-to-draft; optional review-stage entry guard.
5. **Reviewer dispatch:** operator sender mechanism, reminders, refusals and replacement notification. RRW experience is an input; no current assumption that unattended delegated sends work.
6. **Assessor panel/CSV operation details:** CSV columns and identity resolution for membership/assignment, panel membership editing, instrument obligations, preview/bulk error behavior, consolidation of invitations, progress UI at scale and optional roster-to-rows utility. Panel count/size, explicit modes, non-retroactivity and cap enforcement are settled.
7. **Outcome details:** embargo configuration, automatic timed release mechanics, corrections/withdrawals after publication, affected-person alerts and irreversibility of already-read content.
8. **Invitation-only lifecycle:** invitation revocation after draft/submission; exact response to stale direct URLs. Manual and CSV list maintenance and hidden discovery are decided.
9. **Storage/production operations:** Blob permissions, malware scanning, file and export quotas, retention/purge, large export behavior, backup and recovery. Reuse findings from RRW where applicable.
10. **Other policy edges:** what completes the timeline (the withdrawal cut-off), reviewer conflicts, delegation, multi-role conflicts and applicant-visible nominee identities/status.

## 14. Acceptance scenarios (design-level)

- **Planning estimate is nonblocking:** an exercise configured for 200 anticipated applicants accepts a 201st eligible applicant, provided individual allowance, access and deadlines are satisfied. No reservation or quota is consumed by drafts or submissions; the operator is warned nonblockingly when demand exceeds its estimate.
- **Invitation-only:** an uninvited signed-in user cannot discover an invitation-only exercise, open it by direct URL, or start an application; the operator may maintain the allowed list manually or via CSV.
- **Operator-dispatched reviews:** applicant proposals can be amended by operator, and only the operator sends the invitation in that route.
- **Waiver lock:** an applicant may change a waiver in draft, but submission locks it; the reviewer is not required to complete a non-confidential section under an effective waiver. Reopening after a received review requires an explicit warning and cannot make that review newly visible.
- **Operator release:** a non-confidential response remains invisible **throughout the Application stage**, even when received or marked for release. In Review or later, an operator must preview and explicitly release **complete non-confidential sections**; confidential material is never included.
- **Actual versus planned workload:** 200 actual applicants with five applications each can yield 1,000 applications, and actual participation may be higher than the 200-person planning estimate. Track distinct applicants and application counts separately; no estimate-based refusal occurs.
- **Withdrawal:** an applicant can withdraw their own submitted application during either Application or Review, but not once the timeline is completed; the record and review history remain. The effect on the per-person application allowance remains to be defined; no exercise slot exists to reuse.
- **Hard Application deadline:** once the Review stage begins, an applicant cannot start, submit or resubmit an application, even before any separate closing date; an operator cannot return one to draft either.
- **Withdrawal cut-off:** after the exercise's timeline is completed, withdrawal is not offered and a direct request is refused.
- **Entra only:** a referee or assessor without an Entra account cannot be invited or reach any contributor view; no link grants access on its own.
- **Design envelope:** scenarios A, B and C of §7.8 run at full size in load and browser tests, with list pages, previews, bulk panel application and export staying responsive. An exercise projected beyond the envelope shows a nonblocking warning.
- **Stage-sensitive return to draft:** operators can return one or many submitted applications to draft only before the official Review-stage transition, with heightened warnings and version-preserving audit where early reviews exist. The same operation in Review is rejected.
- **Early reviews held:** an assessor completes a review during Application; an operator reopens/resubmits the application before Review. The historical review remains, and no applicant can retrieve its contents during Application. Its applicability is explicitly inspected rather than silently reset.
- **Panel creation:** an operator creates five panels of up to 200 distinct verified members each; attempting a sixth panel or 201st distinct member in a panel is refused. CSV imports support preview and validation. Panels may share members.
- **Whole panel → selected applications:** a 30-member panel applied to 20 applications produces 600 assessor–application assignments (less where duplicates already exist); operator previews additions and instrument obligations before committing.
- **Whole panel → all existing applications:** a 30-member panel applied to 100 applications produces 3,000 assignments; later applications receive none automatically. The same assessor receives a consolidated invitation where supported, not 100 separate messages.
- **Panel as nomination pool:** an operator exposes a 60-member panel for applicant nomination; an applicant may rank only up to the configured assessor nomination limit (never over 10), and nominations create neither access rights nor email sends.
- **Overlapping panels and instruments:** applying panels containing the same identity to the same application creates one assessor–application assignment; additional instrument obligations are merged without deleting existing responses. Removing the assessor from a panel later does not remove their historical/active assignment.
- **Cross-panel overflow:** an operation that would increase an application's distinct active/fulfilled assessors beyond its configured maximum or 50 is blocked before commit with a per-application exception report.
- **Structured assignment import:** operator supplies a CSV of assessor-to-application/instrument assignments; validation and preview precede committed bulk assignments, duplicate identities do not inflate the 50-person count.
- **Published-edit email:** modifying published exercise details records an announcement event and dispatches required notification through an authorized sender; failures remain visible and retryable, not silently reported as delivered.
- **Outcome release:** scheduled/embargoed outcomes remain hidden before release; subsequent operator correction or withdrawal preserves publication history and auditable revisions.
- **Standard count and extensibility:** five active/fulfilled referees prohibit a sixth; ten ranked referee nominations remain legal when the configured nomination limit is ten. Declined/invalidated assignments remain historically recorded without occupying active capacity. Thirty assessors may complete the same instrument; three instruments per exercise and 50 distinct assessors per application are the upper bounds, with one person completing multiple instruments counted once.


- **Referees-only:** applicant submits confidential administrative details and a public project summary, nominates two referees, sends invitations, and either referee may decline and request replacement; neither referee can retrieve the administrative section or the other's reference.
- **Assessors-only:** applicant submits proposal and attachments, nominates/receives assigned assessors, assessors complete a scored or narrative instrument, and operator exports collated results without automatically publishing scores.
- **Combined:** one exercise requests two referees plus one assessor and tracks independent completion against respective deadlines.
- **No-review exercise:** operator accepts applications and files, exports them, and later publishes applicant-specific outcomes without creating reviewer assignments.
- **Email failure:** delegated token expires; invitations remain unsent, applicant sees a truthful recoverable error, and no duplicated send is inferred.
- **Unauthorized access:** a signed-in user with no assignment cannot access another application's details or files even using a copied URL.
- **Offline selection:** operator exports applications, selects externally, imports a validated outcome file, then publishes; applicants do not see draft outcomes or internal processing artifacts.
- **Communication-only continuation:** operator posts a timeline announcement explaining delays even when no outcome data has yet been imported.

### 14.1 Additional reviewer-cap scenarios (retained from v0.4)

- **Ranked surplus:** applicant nominates and ranks ten potential referees; operator selects three, inviting only those three. An attempt to authorize a sixth active/fulfilled referee must fail even if ten were nominated.
- **Separate nomination caps:** an exercise permits four referee nominees and seven assessor nominees; further entries are refused independently, without limiting additional operator-selected contributors under the assignment caps.
- **Decline and substitution:** a selected referee declines, retaining the audit trail while freeing one slot; the next-ranked nominee is suggested but not invited until authorized.
- **Instrument count:** an operator cannot publish four distinct assessor instrument definitions; assessor A completing all three counts as one unique assessor, not three.
- **Assessor upper bound:** a 51st distinct active/fulfilled assessor for an application is rejected, with concurrency protection, while historical declines do not consume active capacity.
- **No premature dispatch:** an applicant with ten ranked nominees may not send all ten referee requests; sends are limited to selected, authorized assignments.


## 15. Coding-agent handoff controls (reviewed 2 November 2026)

**Handoff note:** this section supplies explicit agent gates, invariants and phased slices. Unresolved decisions still require author approval; this document is a functional baseline, not blanket authorization to code all features.

This section is an **implementation control**, not a replacement for the product decisions above. Use §13.1 as the adopted behavior, §13.2 as open decisions, and this section to avoid filling gaps silently. The earlier design history is not a license to resurrect retired models or quotas.

### 15.1 Source-of-truth and repository boundaries

1. Work only in the canonical public `philoyhc/review-robin-web` repository for application source, tests, public-safe spec and guides. Treat private `philoyhc/cordware` as a deployment/import owner; do not change production release code or infrastructure as part of an ApplyDesk feature slice without a separate approved deployment plan.
2. At task start, inspect current `main`, root `AGENTS.md`, `constitution.md`, `rrw_sdd_in_practice.md`, `cordware/spec/host.md`, `cordware/spec/identity.md`, `utilityapps/spec/utilities.md`, and current RRW form/instrument specs and implementation. Do not treat the examples in this file as exact repository APIs. Prefer current contracts over stale examples and report discrepancies.
3. Keep `applydesk` a standalone mount with its own DB, models, audit and authorization. `cordware` stays a stateless identity/hosting shell. Do not import RRW business modules or add a new shared user/roles table to the host. All NUS deployment configuration stays private.
4. For each implementation segment, write a plan identifying behavior, data ownership, migration impact, access boundaries, test/CI lanes, failure/retry behavior and manual browser acceptance. Close the segment by reconciling implemented behavior into `applydesk/spec/`; do not use this working functional draft as proof that a feature is implemented.
5. Keep local fake identities and test fixtures synthetic. No real applicant documents, directory exports, tokens, tenant-specific secrets, or live institutional data in public tests.

### 15.2 Decisions that MUST be resolved before their dependent feature is implemented

| Gate | Required decision or investigation | Safe work before resolution |
|---|---|---|
| **G1 — RRW forms** | Exact field-type/validation/branching parity and authoring UI for applicant forms and up to 3 assessor instruments; document deviations from RRW; shared package versus explicit fork (§10.2) | Form schema prototypes, inventory, isolated field validation tests |
| **G2 — Published changes** | Form-version migration/immutability, material vs trivial edit, announcement audience, batching and failure handling | Unpublished exercise editing; versioned configuration storage |
| **G3 — Stage/reopen/reviews** | When official Review stage starts (it is also the hard submission deadline); what completes the timeline and so closes withdrawal; early-review version binding; whether an old response remains valid after resubmission and who confirms reuse; how in-progress reviews behave | Explicit stage state model, read-only historical submission/review snapshots, isolated lifecycle tests |
| **G4 — Withdrawal/allowance** | Whether withdrawn submissions consume the 1–5 per-applicant allowance, whether reapplication reuses an existing application record, and race-safe counting at submit | Submit/withdraw event history and non-destructive withdrawal UI; do not implement ambiguous new-application eligibility rules |
| **G5 — Email delivery** | Operator-present sending versus an IT-granted application `Mail.Send` (§7.4); operator-authorized sender, reminder sender, Graph token handling, idempotency, retries, audience and rate limits; distinguish Graph acceptance from delivery | Fake/outbox transport and user-confirmed applicant-send prototype |
| **G6 — Panels/import** | Exact CSV formats, bad-row behavior, assignment/instrument obligation merge rules, bulk atomicity and duplicate handling | Panel/member schema, directory validation, preview of deterministic assignments, small-batch tests |
| **G7 — Publication** | Embargo timezone (enforced on read, §8.2) and release-time notification, correction/withdrawal semantics, effects on already-delivered notices or downloads | Draft outcome model and explicit operator preview/manual publish path |
| **G8 — External access/storage** | Invite-list revocation after application exists; IT agreement for the new storage (§5.3); PDPA retention; blob identity permissions, scanning, quotas, retention, backups and high-volume export execution | Local fake-storage interface, access-policy tests, manifests and streaming prototypes |

An agent encountering a gate must either (a) work on the safe bounded portion, (b) record a specific proposed decision for author review, or (c) stop that dependent slice. It must not quietly choose the missing behavior and call the implementation complete.

### 15.3 Non-negotiable invariants to encode as tests

- **No artificial 200-applicant admission ceiling.** The `1–200` value is a *planning estimate*; exceeding it never blocks an eligible applicant. The separate 1–5 per-applicant application allowance is enforced, subject to G4.
- **Submission and stage are orthogonal.** Submitted applicants cannot self-reopen; operators may revert one or many submissions to draft only during Application, with audit and enhanced warning if reviewer work exists. Review responses remain historical and do not automatically become visible or invalid.
- **A reviewer-visible field is not equivalent to a releasable reviewer response.** Never send applicant-hidden answers or files to referee/assessor endpoints, and never expose confidential response material to applicants. Even eligible non-confidential sections require operator release *after* Application stage; waiver snapshots protect existing contributions.
- **Nomination is not assignment.** Ten ranked referee nominations cannot produce ten authorized referee reports. Referee valid active/fulfilled count never exceeds five. Applicant nomination lists remain immutable provenance after submission; operator modifications are separate audit events.
- **Assessor cap is people, not instrument responses.** No more than 50 distinct active/fulfilled assessor identities per application, with a stricter operator-configured maximum where applicable. One person can receive several of at most three exercise instrument definitions without multiplying the distinct-person count.
- **The Application stage's end is a hard deadline.** No application is started, submitted or resubmitted once Review begins; withdrawal closes when the timeline is completed.
- **Entra only.** Every participant route requires an Entra sign-in; no link-only or external access path exists.
- **Panel is not assignment.** At most 5 panels per exercise, each at most 200 distinct members. Applying a panel is a previewed operator action; overlapping members deduplicate on trusted Entra identity; changes to the panel do not rewrite existing assignments. No automatic future-submission assignment in the initial release.
- **Invitations are authorized actions.** Directory nomination, assignment and sending are distinct. Applicant-sent email uses a live signed-in delegated identity after explicit confirmation. Reviewers authenticate and must be independently authorized to the assignment, never by link possession alone.
- **No decision engine.** Offline selection stays external; imports and applicant-facing updates are publication records, not automatic adjudication.

### 15.4 Minimal vertical slices and completion criteria

1. **Host skeleton:** independent `/applydesk` mount, health, identity, fake local sign-in, import boundaries and CI; no production deployment. Verify running with Cordware alone.
2. **Exercise + applicant:** draft/published exercise configuration, restricted discovery, draft/submitted records, reviewer-visible/hidden form read boundaries, versioned submission snapshots, and basic applicant portal. Do not claim the full form-editor feature until G1 is resolved.
3. **Contributor model:** separated nominations, assigned referee/assessor roles, accept/decline, instrument obligations, review response storage and confidentiality protections, with no live sending needed at first.
4. **Assignment workflows:** manual assignment, CSV preview/import, up to five panels, applicant selection pools, whole-panel operations, transactional union/cap checks and paginated assessor queues.
5. **Communication + controlled publication:** delegated applicant send, approved operator sender, safe outbox/retries; exercise-change announcements, timeline, outcome import/export, embargo/release/correction handling after respective gates are resolved.
6. **Production readiness:** Blob access, scanning/quarantine, quotas, retention, migration rehearsal, concurrency and stress tests, export streaming, infrastructure changes in the private repo and operator browser verification. No real uploaded documents before these controls are validated.

Each slice needs server-side authorization tests (including direct URL and download attempts), model/service tests, failure/retry tests, public CI checks, and a short browser walkthrough with clear pass/fail expectations. Finishing a slice does not authorize enabling incomplete modules in production.

### 15.5 Specific risks discovered during this review

- **Fan-out beyond the envelope:** the caps still allow more than §7.8's design envelope (for example 1,000 applications × 50 assessors = 50,000 assignments). Test at the envelope, warn above it, and point large exercises to Review Robin rather than promising untested throughput.
- **Release is irreversible in practice:** a released non-confidential response or outcome may already have been read, emailed or exported. Withdrawal/correction changes *future* portal presentation and audit, not past knowledge.
- **Editing exercise details after publication** may change obligations or applicant expectations. Announcement mails are required for meaningful published changes, but delivery semantics and recipient scope remain a gate; avoid one email per edit-field keystroke.
- **Same assessor across panels** must be deduplicated by trusted account identity, not name or email, and must preserve independent instrument obligations without overwriting submitted work.
- **Early reviews followed by return-to-draft** need a first-class version applicability decision. Retaining records does not mean an old assessment always remains substantively valid.
- **Review Robin code reuse** must be based on a written compatibility inventory, not copying a large subsystem that imports RRW's ORM or assumptions about sessions/rosters.

### 15.6 What to hand back after each agent task

A concise report with: changed files, implemented contract or gate, migration changes, security/privacy impact, automated test results, manually verified browser paths, unresolved decisions, and any difference from this functional specification. Report work as *implemented*, *scaffolded* or *not yet implemented*; do not equate a mocked preview with production behavior.
