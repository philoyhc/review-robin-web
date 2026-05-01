# Review Robin Web Application — Technology-Neutral Functional Specification

> ## ⚠ Pre-implementation forward-looking spec
>
> This document was drafted **before any segment shipped** and
> describes the long-range functional model the system is being
> built toward. It is **not** the source of truth for what
> currently works:
>
> - For what ships today (URL by URL, audit event by audit event),
>   read **`docs/status.md`**.
> - For the operator-page surface contract, read
>   **`spec/operator_map.md`**.
> - For the reviewer-page surface contract, read
>   **`spec/reviewer_map.md`**.
> - For the conceptual data model and layering, read
>   **`spec/architecture.md`**.
>
> Concrete divergences between this spec and what ships today
> include (non-exhaustive): magic-link-without-Microsoft-sign-in
> access (§8.2 — Easy Auth required today; magic-link is
> Segment 16); sortable / filterable reviewer tables and
> save-state indicators (§9.1 — not implemented); async
> invitation sending with progress UI (§7.2 — synchronous outbox
> today); the full invitation-template editor (§6.6 — ships only
> as a stub); export and retention (§§11–12 — entirely
> Segment 11). Treat this document as the destination, not the
> map of where the road goes today.

**Status:** Draft functional specification (pre-implementation)
**Scope:** Platform-independent specification for a web-based successor to Review Robin
**Purpose:** Describe what the system must do regardless of implementation technology
**Starting point:** Existing Review Robin v1.40 functional model, with the review artefact moved from generated Excel workbooks to an online, server-generated tabular review surface

---

## 1. Purpose and framing

Review Robin Web is a system for configuring, distributing, collecting, and exporting structured review data.

The system supports review cycles where:

- an administrator or operator defines a review session;
- reviewers and reviewees are uploaded or entered into the system;
- reviewer-reviewee assignments are generated or supplied;
- reviewers receive individualized invitations;
- reviewers complete dense tabular review forms online;
- responses are stored centrally as structured data;
- the final dataset is exported as CSV or Excel for downstream analysis.

The system replaces the current file-passing model with a server-side review model. Instead of generating one Excel response workbook per reviewer, the system generates one or more individualized online review artefacts for each reviewer. The artefact remains tabular, because the core use case is still high-density structured review.

The system does not perform substantive analysis of the review data. It exists to produce a clean, complete, auditable dataset for downstream users to analyze using their preferred tools.

---

## 2. Functional goals

The system must:

1. Allow authorized administrators or operators to configure a review session.
2. Allow administrators to populate reviewers, reviewees, assignment logic, templates, and invitation settings.
3. Generate individualized online review surfaces based on the session configuration.
4. Invite reviewers by email.
5. Allow reviewers to access their assigned review surface either by signing in with Microsoft or by using a unique individualized access link, subject to the institution's chosen security policy.
6. Provide reviewers with a dense, tabular interface suitable for reviewing many assigned reviewees efficiently.
7. Save reviewer responses centrally.
8. Track completion status at reviewer, instrument, assignment, and response-field level.
9. Allow operators to monitor progress and send reminders.
10. Export the completed response dataset in CSV and/or Excel format.
11. Preserve audit records sufficient to reconstruct key actions and system events.
12. Support appropriate data retention and deletion workflows.

---

## 3. Non-goals

The system is not required to:

- perform ranking, scoring, aggregation, visualization, or decision analysis;
- replace downstream analysis in Excel, Power Query, R, Python, Power BI, or other tools;
- serve as a general-purpose survey platform;
- serve as a full HR, case-management, appointment, scholarship, or awards platform;
- adjudicate or evaluate the fairness of substantive decisions;
- integrate with institutional systems of record in the first functional version;
- support offline reviewing;
- provide mobile-native applications;
- support anonymous public users;
- support multi-institution SaaS deployment.

The system may support future integrations, but its core functional responsibility is review-cycle configuration, online review data collection, monitoring, audit, and export.

---

## 4. User roles

### 4.1 System administrator

A system administrator manages the application at the institutional or deployment level.

System administrators can:

- manage operator access;
- view all sessions or sessions within their administrative scope;
- assist with recovery, support, and audit requests;
- configure global settings where applicable;
- manage retention and archival policies where institutionally required.

System administrators do not normally enter review content unless they are also assigned as an operator for a specific session.

### 4.2 Session operator

A session operator creates and runs review sessions.

Session operators can:

- create a session;
- configure session metadata and deadlines;
- upload or enter reviewers;
- upload or enter reviewees;
- define assignment mode and assignment data;
- define one or more review instruments;
- configure response fields and display fields;
- validate session readiness;
- activate the session;
- send invitations and reminders;
- monitor progress;
- close or reopen the session where permitted;
- export the final dataset;
- trigger retention or deletion actions where permitted.

A session may have one or more operators. The system must distinguish session ownership from general system administration.

### 4.3 Reviewer

A reviewer completes assigned reviews.

Reviewers can:

- access their assigned review work through an email invitation link or by signing in and viewing their dashboard;
- see only review work assigned to them;
- complete, save, revise, and submit responses within the allowed session window;
- return later to continue incomplete work;
- see completion status for their own assignments;
- optionally withdraw or unsubmit responses if the session configuration permits.

Reviewers must not see other reviewers' responses unless they have a separate operator or administrator role.

### 4.4 Downstream data user

A downstream data user receives exported data for analysis.

This may be the same person as the session operator, but the role is conceptually distinct. The system's responsibility is to provide complete, well-structured exports, not to perform the analysis.

---

## 5. Core concepts

### 5.1 Session

A session is one review cycle.

A session contains:

- session name;
- session code or identifier;
- description;
- owner/operator information;
- deadline and important dates;
- status;
- reviewer set;
- reviewee set;
- assignment mode;
- assignment data or rules;
- one or more review instruments;
- invitation and reminder settings;
- response data;
- audit log;
- retention settings.

A session progresses through statuses such as:

- Draft;
- Validated;
- Active;
- Closed;
- Exported;
- Archived;
- Deleted or Purged, where policy permits.

The exact labels may vary, but the lifecycle must distinguish configuration, active collection, closed collection, export, and retention/deletion.

### 5.2 Reviewer

A reviewer is a person who provides responses about assigned reviewees.

Reviewer records include:

- reviewer name;
- reviewer email;
- optional reviewer attributes for assignment logic;
- session-specific metadata;
- invitation status;
- access status;
- completion status.

Reviewer identity is primarily matched by email address. Where institutional Microsoft sign-in is used, the system should match the signed-in user's institutional email or user principal name to the reviewer record.

### 5.3 Reviewee

A reviewee is a person or entity being reviewed.

Reviewee records include:

- reviewee name;
- reviewee email or identifier, where applicable;
- optional display attributes;
- optional status fields used for assignment rules;
- optional links, such as profile or supporting-document links.

The system should allow configurable reviewee display fields, because different sessions may need different contextual information shown to reviewers.

### 5.4 Assignment

An assignment is a specific requirement for a reviewer to review a reviewee under a particular instrument.

An assignment minimally consists of:

- session;
- reviewer;
- reviewee;
- instrument;
- inclusion status;
- optional assignment context fields.

The system must support the possibility that the same reviewer reviews the same reviewee under more than one instrument or context.

### 5.5 Instrument

An instrument is a structured question set or review form within a session.

A session may have one or more instruments. Each instrument defines:

- instrument name;
- display order;
- description or instructions;
- reviewee display fields;
- response fields;
- validation requirements;
- optional field-level guidance;
- completion rules.

Single-instrument sessions must be straightforward. Multi-instrument sessions must allow a reviewer to complete separate tabular review surfaces within the same session.

### 5.6 Review artefact

A review artefact is the individualized online surface generated for a reviewer.

It is not a downloaded workbook. It is a server-generated view of the reviewer's assignments and response fields.

A review artefact may consist of:

- one table for a single-instrument session;
- multiple tabs, sections, or tables for a multi-instrument session;
- contextual instructions;
- a completion indicator;
- save/submit controls;
- validation feedback.

The artefact must remain tabular and efficient for reviewers who need to work through many reviewees.

### 5.7 Response

A response is the reviewer's submitted or saved answer to a response field for a specific assignment.

The system should distinguish:

- not started;
- draft or autosaved;
- submitted;
- reopened or revised, if allowed;
- invalid or incomplete, where validation rules fail.

---

## 6. Session setup workflow

### 6.1 Create session

An operator creates a new session and enters basic metadata:

- session name;
- session code;
- description;
- deadline;
- operator contact information;
- review purpose or short instructions;
- retention preference;
- assignment mode.

The session begins in Draft status.

### 6.2 Populate reviewers

The operator must be able to populate reviewers by:

- uploading a CSV or Excel file;
- copying/pasting tabular data;
- manually adding rows;
- editing existing rows;
- deleting rows before activation.

Required reviewer fields:

- reviewer name;
- reviewer email.

Optional reviewer fields:

- status/category fields used for rule-based assignment;
- team, department, group, cohort, or other session-specific attributes;
- metadata used only for operator reference.

The system must validate:

- required fields present;
- email format;
- duplicate reviewer identifiers;
- consistency of imported columns;
- row-level import errors.

### 6.3 Populate reviewees

The operator must be able to populate reviewees by the same mechanisms:

- upload;
- copy/paste;
- manual entry;
- editing;
- deletion before activation.

Required reviewee fields:

- reviewee name;
- reviewee identifier or email, depending on session design.

Optional reviewee fields:

- profile link;
- status/category fields used for rule-based assignment;
- display fields shown to reviewers;
- custom metadata for downstream export.

The system must validate:

- required fields present;
- duplicate reviewee identifiers;
- malformed links where links are provided;
- consistency of imported columns.

### 6.4 Configure instruments

The operator defines one or more instruments.

For each instrument, the operator configures:

- instrument name;
- order;
- instructions;
- reviewee display columns;
- response fields;
- response field types;
- response validation rules;
- whether fields are required;
- optional rating schemes or allowed values;
- optional comments or free-text fields.

Response field types may include:

- text;
- long text;
- integer rating;
- decimal rating;
- single-select choice;
- multi-select choice;
- yes/no;
- date, if needed;
- file/link reference, if needed in future versions.

The system must validate that each instrument has:

- at least one response field;
- unique response field identifiers;
- valid response types;
- valid rating or choice definitions;
- no duplicate exported column names within the same instrument;
- valid references to reviewee or assignment display fields.

### 6.5 Configure assignments

The system must support at least three assignment modes.

#### 6.5.1 Full matrix

Every reviewer reviews every reviewee for the relevant instrument or instruments, subject to self-review policy.

The operator can configure whether self-review is allowed when reviewer and reviewee identities match.

#### 6.5.2 Manual assignments

The operator uploads or enters explicit assignment rows.

Manual assignment rows include:

- reviewer identifier;
- reviewee identifier;
- instrument identifier, if multiple instruments exist;
- include/exclude flag;
- optional context fields.

The system must validate that:

- each reviewer exists;
- each reviewee exists;
- each instrument exists;
- required fields are present;
- duplicate assignments are either prevented or clearly handled;
- excluded rows are not presented to reviewers.

#### 6.5.3 Rule-based assignments

The operator defines rules that generate assignments from reviewer and reviewee attributes.

At minimum, a rule should support:

- rule identifier;
- rule name;
- enabled/disabled flag;
- target instrument;
- reviewer-side criteria;
- reviewee-side criteria;
- include/exclude logic;
- self-review policy;
- allocation policy.

Allocation policies may include:

- allocate all matching pairs;
- randomly or deterministically allocate N reviewees per reviewer;
- other policies added in future versions.

The system must allow the operator to preview rule results before activation, including:

- number of assignment rows generated;
- number of reviewers affected;
- number of reviewees covered;
- warnings for orphan reviewers or orphan reviewees;
- warnings for empty rules or rules producing no assignments;
- duplicate or overlapping assignment warnings.

### 6.6 Configure invitation settings

The operator configures:

- invitation subject;
- invitation body;
- reminder subject/body;
- deadline display;
- help contact name and email;
- optional return or support instructions;
- whether reviewers must sign in with Microsoft;
- whether individualized unique links are allowed;
- whether unique links are single-use, time-limited, or reusable during the session.

The invitation template must support merge fields such as:

- reviewer name;
- session name;
- deadline;
- help contact;
- review link;
- instrument list, where useful.

The system must validate that required merge fields are available and that no unresolved required placeholder remains before invitations are sent.

### 6.7 Validate session readiness

Before activation, the system must provide a readiness check.

The readiness check must validate:

- session metadata;
- deadline;
- reviewer table;
- reviewee table;
- instruments;
- assignments;
- rule outputs, if applicable;
- invitation template;
- access policy;
- export column uniqueness;
- any required retention setting.

Readiness output should distinguish:

- errors that block activation;
- warnings that allow activation but require operator awareness;
- informational notes.

A session cannot be activated while blocking errors remain.

---

## 7. Activation and invitation workflow

### 7.1 Activate session

When a session is activated, the system freezes or versions the active configuration.

Activation should:

- mark the session active;
- generate or finalize assignments;
- generate individualized reviewer access records;
- prepare invitation jobs;
- record an audit event.

After activation, changes to core configuration should be restricted. The system may allow controlled corrections, but it must preserve auditability.

### 7.2 Send invitations

The operator can send invitations to all eligible reviewers or a selected subset.

The system must:

- generate individualized review links;
- send email invitations;
- track invitation status;
- track send failures;
- allow retry of failed sends;
- prevent accidental duplicate sends unless explicitly confirmed.

For large sessions, invitation sending may be asynchronous. The operator should see progress and completion status.

### 7.3 Send reminders

The operator can send reminders based on review progress.

Reminder recipient filters should include:

- not opened;
- opened but not started;
- partially complete;
- not submitted;
- specific reviewer selection;
- specific instrument incompletion.

The system must log reminder sends.

---

## 8. Reviewer access workflow

### 8.1 Access by Microsoft sign-in

Where Microsoft sign-in is required, the reviewer must authenticate using their institutional account.

The system must then:

- match the authenticated identity to reviewer records;
- show only sessions and assignments belonging to that reviewer;
- deny access if the identity does not match an invited reviewer or authorized role.

### 8.2 Access by unique individualized link

Where unique links are allowed, each reviewer receives a link tied to their review access record.

The system must support policy choices such as:

- unique link plus Microsoft sign-in;
- unique link without Microsoft sign-in;
- time-limited link;
- one-time initial link that creates an authenticated session;
- revocable link.

The functional specification does not mandate which policy the institution must choose. It requires the system to implement the chosen policy consistently and audit access events.

### 8.3 Reviewer landing page

After access, the reviewer sees a landing page showing:

- active sessions assigned to them;
- session name and deadline;
- instruments assigned;
- completion status;
- link to begin or continue review;
- help contact.

For a reviewer with only one active assignment set, the system may take them directly to the review surface.

---

## 9. Online review artefact

### 9.1 Tabular review surface

The core reviewer surface must be a dense table.

Rows represent assigned reviewees or assignment-context rows.

Columns include:

- configured display fields;
- configured response fields;
- optional status/completion indicators.

The table must support:

- keyboard-efficient navigation;
- inline editing;
- clear required-field indication;
- validation feedback;
- save state indicators;
- sorting or filtering where appropriate;
- preservation of reviewer-entered data during navigation.

The reviewer should be able to complete a large number of rows more efficiently than in a one-form-per-reviewee interface.

### 9.2 Multi-instrument presentation

If a reviewer has assignments under multiple instruments, the system must present them clearly.

Acceptable patterns include:

- tabs;
- sections;
- accordion panels;
- separate pages linked from an overview.

Each instrument must preserve its own response fields, validation rules, and completion status.

### 9.3 Saving

The system must support saving work before final submission.

Saving may be automatic, manual, or both. The functional requirement is that reviewers can leave and return without losing entered responses.

The system must make save state visible, such as:

- saved;
- saving;
- unsaved changes;
- save failed;
- offline or connection issue.

### 9.4 Submission

The system must allow reviewers to mark their work complete.

Submission should:

- validate required fields;
- identify incomplete rows or fields;
- confirm successful submission;
- update completion status;
- record audit events.

The system may allow post-submission edits before the deadline if configured by the operator. If edits after submission are allowed, the system must preserve revision timestamps or audit events.

### 9.5 Session closed behavior

When a session is closed or the deadline has passed, the system must enforce the configured policy:

- read-only access;
- no access;
- late submission allowed with warning;
- operator-controlled reopening.

Late submissions, reopening, or edits after deadline must be auditable.

---

## 10. Operator monitoring workflow

The operator must be able to monitor session progress while the session is active.

Monitoring views should show:

- total invited reviewers;
- invitation send status;
- reviewers who have not opened the link;
- reviewers who have opened but not started;
- reviewers in progress;
- reviewers submitted;
- completion by instrument;
- response completeness by required field;
- recent activity;
- send failures or access issues.

The operator should be able to filter by:

- reviewer;
- instrument;
- status;
- group/status field;
- completion state.

The system must avoid exposing reviewer response content in monitoring views unless the operator has explicit permission to view responses before export.

---

## 11. Data export

### 11.1 Export purpose

The system's final output is a complete structured dataset for downstream analysis.

The system must support export to:

- CSV;
- Excel workbook.

### 11.2 Export formats

The system should support at least two export shapes.

#### Long format

One row per response cell or response value.

Typical columns:

- session identifier;
- instrument identifier;
- reviewer identifier;
- reviewer name;
- reviewer email;
- reviewee identifier;
- reviewee name;
- assignment context fields;
- response field identifier;
- response field label;
- response value;
- response timestamp;
- submission status.

This format is best for Power Query, pandas, R, or database-style analysis.

#### Wide format

One row per reviewer-reviewee-instrument assignment.

Typical columns:

- session identifier;
- instrument;
- reviewer fields;
- reviewee fields;
- assignment context fields;
- one column per response field;
- completion/submission metadata.

This format is best for direct inspection in Excel.

### 11.3 Export completeness

Exports must include enough metadata to reconstruct:

- who reviewed whom;
- under which instrument;
- under which assignment context;
- which fields were asked;
- what responses were given;
- whether the assignment was submitted or still incomplete;
- timestamps relevant to submission or last save.

### 11.4 Export validation

Before generating the final export, the system should provide an export readiness check showing:

- number of reviewers invited;
- number submitted;
- number incomplete;
- missing required responses;
- any assignment rows with no responses;
- any export-column conflicts;
- any data-shape warnings.

The operator may still export incomplete data if permitted, but the export should clearly include completion status.

---

## 12. Retention and deletion

Each session must have a retention policy.

Supported policies should include:

- delete response data after export;
- delete response data N days after session close;
- retain until manually deleted;
- archive session metadata while deleting response content.

The system must distinguish between:

- deleting response data;
- deleting exported files generated by the system;
- deleting session configuration;
- deleting audit records.

Deletion actions must:

- require appropriate permission;
- warn the operator clearly;
- be auditable;
- be irreversible unless backups are separately restored under institutional procedure.

The system should default toward minimal retention unless institutional policy requires otherwise.

---

## 13. Audit and logging

The system must maintain an audit log for important events.

Audit events should include:

- session created;
- session configuration changed;
- reviewer import/upload;
- reviewee import/upload;
- assignments generated or imported;
- instrument created/edited/deleted;
- readiness validation run;
- session activated;
- invitations sent;
- reminder sent;
- reviewer accessed session;
- reviewer saved responses;
- reviewer submitted;
- operator reopened or closed session;
- export generated;
- data deleted or retention action taken;
- administrative permission changes.

Audit records should include:

- timestamp;
- actor;
- actor role;
- session;
- event type;
- severity or category;
- affected object;
- summary;
- structured details;
- correlation identifier for batch operations.

Audit logs should be searchable or filterable by session, actor, event type, and date range.

---

## 14. Permissions and access control

The system must enforce role-based access control.

Minimum rules:

- Reviewers can see only their own assigned review artefacts.
- Reviewers cannot see other reviewers' responses.
- Operators can manage sessions they own or have been granted access to.
- Operators can export response data for their sessions.
- System administrators can manage users, roles, and sessions within their scope.
- Access by unique link must be scoped to the specific invited reviewer and must not grant broader operator privileges.

The system must support revoking reviewer access, operator access, or individual invitation links.

---

## 15. Validation requirements

The system must validate data at several stages.

### 15.1 Import validation

For uploaded reviewers, reviewees, assignments, and instruments:

- required columns;
- required values;
- duplicate identifiers;
- valid email format;
- valid links where applicable;
- unknown references;
- invalid response field types;
- invalid choice/rating definitions.

### 15.2 Session readiness validation

Before activation:

- all blocking setup issues must be resolved;
- warnings must be visible;
- generated assignment counts must be previewable;
- invitation templates must be checked;
- access policy must be defined.

### 15.3 Reviewer response validation

During review:

- field type validation;
- required fields;
- allowed values;
- numeric range validation;
- field-specific constraints;
- submission completeness.

### 15.4 Export validation

Before export:

- data shape consistency;
- completion summary;
- missing required responses;
- duplicate or conflicting export headers;
- session status and retention warnings.

---

## 16. Configuration versioning and mid-cycle changes

The system must handle changes carefully.

Before activation, operators may freely edit configuration subject to validation.

After activation, the system should restrict or version changes to:

- reviewer list;
- reviewee list;
- assignments;
- instruments;
- response fields;
- validation rules;
- invitation settings.

Allowed post-activation changes may include:

- typo fixes in instructions;
- deadline updates;
- reminder template edits;
- adding reviewers before they begin;
- reopening a closed session;
- correcting access issues.

Potentially disruptive changes, such as deleting response fields or changing rating scales after responses exist, must either be blocked or handled through explicit versioning.

The system must audit all post-activation changes.

---

## 17. Error handling and recovery

The system must support recovery from common operational problems.

Examples:

- uploaded file has invalid rows;
- reviewer email is wrong;
- reviewer did not receive invitation;
- reviewer changed institutional email;
- reviewer link expired;
- invitation send failed;
- reviewer submitted accidentally;
- operator needs to reopen a reviewer assignment;
- export was generated before all responses arrived;
- session needs to be cloned or rerun.

The system should provide clear operator-facing messages and avoid requiring database-level intervention for ordinary recovery actions.

---

## 18. Cloning and reuse

The system should support copying an existing session as the starting point for a new session.

The operator should be able to clone:

- instrument definitions;
- invitation templates;
- reviewer or reviewee structures;
- assignment rules;
- retention settings.

The cloned session must not copy prior responses unless explicitly exported/imported through a separate workflow.

---

## 19. Data integrity principles

The system must preserve the following integrity guarantees:

1. Every response is traceable to one reviewer, one reviewee, one instrument, and one session.
2. Every exported response must be reconstructable from stored system data at the time of export.
3. Assignment generation must be deterministic or auditable enough to explain how rows were created.
4. Reviewer access must not expose assignments belonging to another reviewer.
5. Completion status must be derived from stored responses and configured requirements, not manually asserted without trace.
6. Deletion and export events must be auditable.

---

## 20. Functional parity with Review Robin concepts

The web application preserves the conceptual strengths of Review Robin while changing the delivery mechanism.

| Current Review Robin concept | Web application functional equivalent |
|---|---|
| Control workbook | Operator web interface |
| Session sheet | Session configuration page |
| Reviewers table | Reviewer roster import/edit surface |
| Reviewees table | Reviewee roster import/edit surface |
| Assignments table | Assignment import/editor and generated assignment preview |
| RuleBased mode | Rule builder and assignment generator |
| ReviewConfig | Instrument/template configuration |
| Instructions sheet | Instrument/session instructions rendered online |
| Generated response workbook | Individualized online tabular review artefact |
| Email with attachment | Email invitation with individualized link |
| Distribution queue | Invitation/reminder/job status tracking |
| Build activity log | Operator activity/status view |
| Full forensic log | Session audit log |
| Generated file validation | Session/readiness and artefact-configuration validation |
| Returned workbook collation | Direct central response storage and export |
| Export to downstream analysis | CSV/Excel export |

---

## 21. Minimum viable functional release

A minimum viable release should include:

1. Session creation and configuration.
2. Reviewer upload/edit.
3. Reviewee upload/edit.
4. Single-instrument configuration.
5. Manual assignment upload/edit.
6. Full-matrix assignment generation.
7. Basic readiness validation.
8. Email invitations with individualized links.
9. Microsoft sign-in or unique-link access, according to chosen policy.
10. Reviewer tabular response surface.
11. Save and submit.
12. Operator progress dashboard.
13. Reminder sending.
14. CSV and Excel export.
15. Basic audit log.
16. Basic retention/deletion workflow.

Rule-based assignments and multi-instrument sessions may be included in the first release if they are functionally required, but they can also be staged after the core review loop works.

---

## 22. Expanded functional release

A fuller release may add:

- multi-instrument sessions;
- rule-based assignment builder;
- assignment preview and dry-run counts;
- session cloning;
- richer invitation templates;
- targeted reminders by detailed completion state;
- controlled post-activation correction workflows;
- richer audit views;
- long-format and wide-format export options;
- role delegation among multiple operators;
- advanced retention policies;
- administrative dashboards.

---

## 23. Acceptance criteria

The system is functionally acceptable when an operator can complete this end-to-end cycle without developer intervention:

1. Create a session.
2. Upload reviewers.
3. Upload reviewees.
4. Configure at least one instrument.
5. Configure assignments.
6. Validate the session.
7. Activate the session.
8. Send invitations.
9. Have reviewers access their individualized online review surfaces.
10. Have reviewers save and submit tabular responses.
11. Monitor completion.
12. Send reminders to incomplete reviewers.
13. Close the session.
14. Export a complete dataset.
15. Delete or retain data according to the configured retention policy.
16. Review audit records showing the major actions in the cycle.

---

## 24. Open policy decisions

The following are functional-policy decisions that must be settled before implementation, but are not technology choices:

1. Must reviewers always sign in with Microsoft, or may unique links alone grant access?
2. Are unique links reusable, time-limited, revocable, or single-use?
3. Can reviewers edit after submission before the deadline?
4. Can operators view live response content before session close, or only completion status?
5. Are late submissions allowed?
6. Who may reopen a submitted review?
7. What is the default retention policy?
8. Must audit logs outlive response data?
9. Are multi-instrument sessions required in the first release?
10. Are rule-based assignments required in the first release?
11. Should exports include incomplete assignments by default?
12. Should the system support anonymous or pseudonymous exports?
13. What accessibility standard must the tabular review surface meet?
14. What level of operator delegation is needed?
15. What data classifications are permitted for use in the system?

---

## 25. Summary

Review Robin Web must preserve the core insight of the Excel/VBA system: many institutional review tasks require dense, structured, reviewer-specific, tabular data collection.

The web version changes the artefact and workflow:

- from generated Excel response files to server-generated online review forms;
- from emailed attachments to emailed links;
- from returned files to direct database-backed responses;
- from post-hoc collation to direct export;
- from file-level tracking to live session monitoring.

The system remains deliberately bounded. It configures review sessions, collects structured review responses, tracks progress, preserves auditability, and exports clean data. It does not replace downstream analysis or substantive institutional judgment.

