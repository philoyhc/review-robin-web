# RA Leave Management

> **Moved 2026-10-25 from the private deployment repository** (author), where it was `docs/ra_leave_management_functional_spec_v0.4.md` (at `ad94c1c`). Deployment status (which grants are in place, configuration dates, what IT has delivered) was made generic on the way; it is tracked privately with the deployment. "Strategy v1.0" below is the Cordware deployment strategy, also held privately; what Residential depends on from it is in `residentialapps/guide/todo_master.md`.
>
> **Amended 2026-10-25 (author): one package, two applications.** Residential is one `residentialapps/` package mounted as two applications, RA Operations at `/residentialops` and Support Logs at `/supportlogs`; nothing is mounted at `/residentialapps`. Passages below that say "one application" or mount it at `/residentialapps` predate this and are revised at this spec's next version.

## Functional Specification — Azure Web App

**Status:** Draft v0.4, 22 October 2026 (v0.3 aligned to Cordware strategy v0.9; changes in §36); appeal and cover rulings the same day  
**Target platform:** the Leave module of Residential Apps, one application mounted at `/residentialapps` under Cordware (the Cordware deployment strategy v1.0, held privately)  
**Authentication:** Institutional Microsoft 365 / Microsoft Entra ID, through Azure Easy Auth, interpreted by Cordware

---

# 1. Purpose

RA Leave Management provides a lightweight self-service and administrative system for managing Residential Assistant (RA) leave.

The system should allow:

- RAs to see their leave entitlement, usage, balance, pending applications and leave history;
- RAs to submit leave applications;
- RAs to identify covering RAs for periods of absence;
- designated approvers to review applications sequentially;
- covering RAs to be informed of relevant cover arrangements;
- RAs to request discretionary **extra leave / appeal leave** beyond normal entitlement;
- Residential Masters to approve such exceptional leave where appropriate;
- residential staff to understand upcoming and current team availability;
- administrators to maintain the RA roster, entitlements and leave records;
- the institution to retain a clear audit trail of applications and decisions.

The system replaces the existing Power Apps + Power Automate + SharePoint implementation while preserving useful established rules and simplifying the architecture.

The Leave module is one domain of **Residential Apps**, a single application under Cordware with two pillars: **RA Operations** (Leave and RA Events Proposal/Approval) and **Support Logs** (staff only). A shared core holds people, rosters, RA cycles, residential appointments and teams, used by both pillars; each pillar keeps its own permissions with its own data (strategy v1.0 §4). Leave-specific business data stays within the Leave domain, and Support Logs lives in a separate database (§2.2).

Cordware supplies institutional identity and hosting; it holds no Residential data. Residential Apps follows RRW as its model: it runs fully on localhost with local databases and fake roles, and has its own tests, CI and development practice (strategy v1.0 §3).

---

# 2. Design Principles

## 2.1 Institutional Microsoft 365 identity

All users authenticate using their institutional Microsoft 365 account through Microsoft Entra ID, at Azure Easy Auth in front of Cordware.

There is no separate username/password system, and Residential Apps contains no sign-in code.

Cordware passes the authenticated identity (email, display name, Entra object ID where available) to the application; that establishes who the user is. Residential Apps maps it to its own person record, matching by institutional email and recording the Entra object ID at the person's first sign-in, as RRW does.

Local application records contain the additional information the leave system requires, such as:

- institutional email;
- Entra object ID where available;
- student ID;
- display name;
- RA status;
- residential team;
- approver routing;
- leave entitlement.

## 2.2 Application-owned business data

PostgreSQL is the authoritative operational store. Residential Apps uses two databases on the shared server (strategy v1.0 §4):

- **`residentialops`** holds the shared core (people, institutional identities, rosters, RA cycles, residential appointments, teams), Leave and RA Events with their permissions, and their audit and notification outbox;
- **`supportlogs`** holds Resident Support Log data and its audit, and nothing else.

Within `residentialops`, each module's tables carry its prefix (`core_`, `leave_`, `events_`) rather than living in separate PostgreSQL schemas, so the same models run on the local SQLite databases used for development and tests.

The Leave module must not read Events tables, and cannot reach `supportlogs` at all. Conversely, Events must not obtain leave records merely because both live in `residentialops`.

SharePoint is not the operational database after migration.

Microsoft 365 is used for:

- authentication (Easy Auth, through Cordware);
- email delivery (§17);
- optionally calendar, Teams or other narrowly scoped integrations later (§17.3).

## 2.3 No dependency on the Student Information System

The application should not require an interface to the institutional Student Information System.

The authoritative RA roster is supplied operationally by residential staff each cycle.

Microsoft 365 identity lookup may assist with matching institutional accounts, but it does not determine:

- who is an RA;
- RA appointment dates;
- team membership;
- student ID;
- leave entitlement;
- approval routing.

## 2.4 Deterministic workflow

Leave management is structured and rule-driven.

The primary interface should therefore use:

- forms;
- balances;
- lists;
- status indicators;
- approval queues;
- dashboards.

All consequential actions pass through deterministic application logic.

## 2.5 Mobile-first, desktop-capable

The RA interface should work particularly well on a phone.

Administrative, approval and dashboard views should also work efficiently on desktop screens.

Per surface, following `docs/cordware_mobile_to_desktop.md` §3: applying for leave is **mobile-critical**; checking one's balance is mobile-critical; one's own leave history is responsive general-use; approver actions are **responsive general-use**; team and dashboard views and administration / roster setup are **desktop-oriented**. Every screen stays usable on a phone, and screen size never changes authorization.

There should not be separate mobile and desktop applications. The UI follows RRW's conventions: server-rendered pages, one stylesheet in the base template, small inline scripts for progressive enhancement, and RRW's canonical button roles.

## 2.6 Minimise maintenance surfaces

The replacement should reduce the number of independently maintained platforms.

In particular, the target architecture should **not depend on Power Automate or Teams Approvals**.

Approval workflow, validation, notifications and workflow state should reside in the Azure application.

Microsoft 365 integration should be limited to services that provide clear value, principally identity and email.

## 2.7 Shared platform, isolated domains

The Leave module shares one application with the Resident Support Log and RA Events modules, and one database (`residentialops`) with RA Events. This is an infrastructure rationalization, not permission to share all data.

The design preserves module boundaries at several layers:

- **Support Logs is in its own database** with its own login role; `CONNECT` is revoked from `PUBLIC` on each database, so the `residentialops` role cannot connect to `supportlogs` (strategy v1.0 §4);
- **one least-privilege role for `residentialops`**, never the server admin role, for routine requests;
- **module boundaries in code:** Leave and Events each keep their own repositories and services, neither imports the other's, and a test enforces it, as RRW's import-boundary test does;
- server-side authorization for every consequential action;
- no Support Log content, flags or summaries in shared core tables.

The shared core contains only stable cross-module concepts. A person being known to the Support Log must not reveal to Leave or Events whether that person has support records.

---

# 3. Scope

## 3.1 In scope

The system covers:

- cycle-based RA roster import;
- leave entitlement import;
- manual roster and entitlement maintenance;
- leave applications;
- covering-RA arrangements;
- sequential approvals;
- pending leave;
- approved leave;
- extra-leave / appeal requests;
- leave balances and history;
- administrative corrections;
- team availability views;
- dashboards;
- email notifications;
- audit history;
- reporting and export.

## 3.2 Out of scope

The application is not:

- an RA recruitment system;
- a complete RA HR system;
- a student information system;
- a conduct-management system;
- a student case-management system;
- a repository for sensitive student welfare or disciplinary material.

---

# 4. User Roles

A user may hold more than one role.

## 4.1 RA

An active RA may:

- view their own leave profile;
- view entitlement and current balance;
- view pending applications;
- view approved leave history;
- submit leave applications;
- identify covering RA arrangements;
- submit an extra-leave appeal where normal entitlement is insufficient;
- withdraw applications where permitted;
- view application and appeal status.

## 4.2 First Approver

The RA's **Resident Fellow (RF)**, or, in rare situations, a delegate staff member assigned in approver routing.

May:

- view applications awaiting decision;
- see relevant leave and coverage information;
- approve or reject ordinary leave applications;
- enter remarks;
- see relevant team-level absence information.

First approval advances an ordinary application to the final approver.

## 4.3 Final Approver (the Master's admin delegate) and the Residential Master

The final approver for ordinary leave is the **Residential Master's admin delegate**, acting for the Master. The final approver may:

- review applications that have passed first approval;
- approve or reject ordinary leave;
- see relevant cover arrangements;
- see preceding decisions and remarks;
- record reasons for exceptional decisions.

The Residential Master is the authoritative approver for discretionary extra leave, and **decides extra-leave appeals personally**; the admin delegate does not decide them (author, 2026-10-22).

## 4.4 Covering RA

A covering RA is another active RA identified as providing operational cover during the applicant's absence.

A covering RA:

- is notified of the proposed cover arrangement;
- can see the relevant dates and applicant;
- may confirm or decline the cover arrangement where confirmation is required;
- is notified of the final outcome.

Covering RA status does not grant access to the applicant's broader leave history or entitlement.

## 4.5 Residential Staff / Team Viewer

Authorized residential staff may view operational leave information within their assigned scope, including:

- who is away;
- who is covering whom;
- pending leave;
- upcoming leave;
- overlapping absences;
- team availability.

## 4.6 Administrator

Administrators may:

- import roster and entitlement data;
- manually add, edit and remove roster rows;
- maintain entitlements;
- maintain approver routing;
- correct leave records;
- reassign approvals;
- manage configuration;
- view operational dashboards;
- export data.

Administrative interventions must be audited.

## 4.7 Platform super-admin

The Cordware platform super-admin (`SUPER_ADMIN_EMAILS`) holds full **administrative** rights in Residential Apps, as in RRW, with two limits:

- **Named decisions stay with the named person.** Approving or rejecting leave, deciding an extra-leave appeal and confirming or declining cover are made only by the person routing names for them: the RF or delegate, the Master's admin delegate, the Residential Master, the covering RA. A super-admin, like an administrator, can reassign an outstanding approval (§21.4, audited), but cannot decide it as someone else. So only the Residential Master decides appeals (§4.3).
- **Support Logs is carved out.** In Support Logs the super-admin holds administrator rights only, with no access to support content or the support-activity audit (`residentialapps/docs/resident_support_log_functional_spec_v0.3.md` §3.4; strategy v1.0 §3).

Residential's own administrators are separate and narrower.

## 4.8 Fake roles for localhost

For local development and testing, Residential Apps provides a fake role for each role above (RA, covering RA, first approver, final approver, Residential Master, team viewer, administrator), keyed off Cordware's fake user and switchable per run in `.env` or the shell, as RRW's are. They exist only while Cordware's fake auth is on, which Cordware refuses outside `APP_ENV=local`.

---

# 5. RA Roster and Entitlement Provisioning

## 5.1 Cycle-based CSV import

At the beginning of each RA cycle, residential staff upload a CSV containing the authoritative RA roster and leave entitlement information.

The RA roster portion of the import populates the shared core's RA appointment records, used by both the Leave and Events modules. Leave-specific entitlement columns populate Leave's entitlement records. The import should therefore be treated as a platform cycle-provisioning operation with leave-specific extensions, rather than as a private Leave roster.

The import should be the normal bulk-provisioning mechanism.

Typical fields include:

- student ID;
- institutional email;
- full name;
- team/unit;
- RA appointment start date;
- RA appointment end date;
- normal leave entitlement values;
- first approver or routing key, where applicable.

The exact CSV schema should be documented and versioned.

## 5.2 Import preview

Before committing an import, the application should show:

- number of rows detected;
- new RAs;
- existing RAs being updated;
- rows unchanged;
- duplicate identifiers;
- invalid email addresses;
- missing required data;
- ambiguous matches;
- other validation errors.

No changes should be committed until the administrator confirms the import.

## 5.3 Reconciliation

An upload must not silently delete RAs simply because they are absent from a subsequent CSV.

The system should distinguish between:

- new;
- updated;
- unchanged;
- omitted from current upload;
- explicitly deactivated.

This reduces the risk of destroying historical associations through an incomplete roster file.

## 5.4 Manual maintenance

Administrators must also be able to:

- add an RA manually;
- edit an existing RA row;
- deactivate/remove an RA from the active roster;
- correct student ID, email or team;
- amend entitlement;
- amend approver routing.

Where an RA has historical records, "delete" should normally mean **deactivate**, not physically remove the database row.

## 5.5 Identity matching

Roster rows are matched to people by institutional email. The Entra object ID is recorded at the person's first sign-in, as RRW does; no directory lookup is needed at import. A Microsoft Graph lookup could be added later, but needs an Entra app permission from IT.

The shared RA appointment roster remains authoritative for RA status. An active RA appointment grants the person eligibility to use RA-facing functions in both Leave and Events, subject to module-specific rules.

---

# 6. Leave Entitlements

The system supports configurable leave types.

Normal entitlement values are loaded for each cycle rather than hard-coded into the application.

For each entitlement record, store:

- RA;
- leave type;
- entitlement period/cycle;
- normal entitlement amount;
- adjustments, if any.

Conceptually:

**Available normal leave = entitlement − approved normal leave − qualifying pending normal leave ± administrative adjustments**

Pending normal leave reserves entitlement while the application is active.

---

# 7. Extra Leave / Appeals

## 7.1 Purpose

By established residential practice, a Residential Master may approve leave beyond an RA's normal entitlement.

This is discretionary and is **not itself an entitlement**.

Typical circumstances may include an RA having undertaken additional duties or another circumstance considered sufficient by the Residential Master.

The system should therefore support this practice explicitly instead of treating it as an administrative error, entitlement adjustment or negative balance.

## 7.2 Appeal affordance

Where:

- an RA has insufficient normal leave remaining; or
- the RA otherwise wishes to request exceptional leave,

the application should offer a **Request Extra Leave / Appeal** path.

The system should not simply block the user at the insufficient-entitlement validation step.

Instead it should explain:

- normal entitlement available;
- number of additional days being requested;
- that approval is discretionary.

## 7.3 Appeal data

An extra-leave appeal should contain:

- leave type/category;
- dates;
- number of days;
- normal entitlement available;
- number of days requiring exceptional approval;
- RA's reason for appeal;
- covering RA;
- cover confirmation status;
- Residential Master decision;
- decision remarks;
- timestamps and audit events.

## 7.4 Cover requirement

Extra leave normally requires an agreed covering arrangement.

The RA identifies the covering RA as part of the appeal.

The covering RA is notified and can confirm or decline.

The Residential Master should be able to see the covering RA's response before deciding the appeal.

The system may allow the Residential Master to override an incomplete cover confirmation where necessary, but such an override must be explicit and audited.

## 7.5 Accounting treatment

Approved extra leave must **not increase normal entitlement**.

Nor should the system disguise extra leave as a routine entitlement adjustment.

Instead, approved leave records should distinguish between:

- leave charged to normal entitlement; and
- discretionary extra leave.

For example:

- Normal leave used: 25 days
- Extra leave approved: 2 days
- Normal entitlement remaining: 0 days

This makes the policy visible and preserves the meaning of the entitlement figure.

---

# 8. RA Home Page

After login, an RA sees a compact dashboard.

## 8.1 Leave balance

For each normal leave type:

- entitlement;
- approved/taken;
- pending;
- remaining.

Extra leave should be shown separately, for example:

- extra leave approved this cycle;
- pending extra-leave appeals.

It should not be presented as part of normal entitlement.

## 8.2 Current applications

Applications that are:

- awaiting cover confirmation;
- pending first approval;
- pending final approval;
- pending Residential Master appeal decision.

Each shows:

- dates;
- leave type;
- number of days;
- covering RA;
- current status.

## 8.3 Actions

Prominent actions:

- **Apply for Leave**
- **Request Extra Leave / Appeal**
- **View Applications / History**

---

# 9. Ordinary Leave Application

## 9.1 Input

The RA provides:

- leave type;
- first date;
- last date;
- covering RA;
- remarks where required.

The application calculates the applicable number of leave days.

Approvers are determined automatically from configured routing.

## 9.2 Covering RA selection

The covering RA should normally be selected from active RAs.

Autocomplete should search the local active RA roster.

The UI should make it difficult to accidentally select:

- the applicant themself;
- an inactive RA;
- an invalid account.

Where policy permits multiple covering RAs, the data model should not preclude that extension, but the initial UI may assume one principal covering RA.

---

# 10. Application Validation

Before normal submission, validate at minimum:

- user is an active RA;
- leave type is valid;
- dates are valid;
- sufficient normal entitlement remains;
- dates do not improperly overlap existing leave;
- required cover information is present;
- approver routing is valid.

If entitlement is insufficient, the user should be offered the **extra-leave appeal** route rather than encountering a terminal error.

Validation must be performed server-side.

---

# 11. Ordinary Leave Workflow

A reasonable workflow is:

**Draft → Pending First Approval → Pending Final Approval → Approved**

Submitting moves a draft straight to Pending First Approval. Rejection or withdrawal is possible at any pending stage.

Cover arrangement status is tracked alongside the leave workflow (§30), not as extra workflow states. Where the setting requires cover confirmation for ordinary leave (§12), the application waits at Pending First Approval until cover is confirmed, and shows "awaiting cover confirmation" from the cover status.

---

# 12. Covering RA Notifications

The replacement system should correct an important limitation of the Power Platform implementation: covering RAs must be notified.

At minimum, the covering RA should receive notification when:

1. they are named as covering RA;
2. the application is materially changed;
3. the leave is finally approved;
4. the leave is rejected, withdrawn or cancelled.

Both facilities are built in for every application: **cover information** (naming the covering RA, who is notified) and **cover confirmation** (the covering RA confirms or declines). Whether ordinary leave requires confirmation is decided by an administrator setting (author, 2026-10-22). It has no built-in default: the setting is chosen as part of cycle setup (§21.1), and ordinary applications cannot be submitted until it has been set. Extra-leave appeals always require confirmation, subject to the explicit, audited override in §7.4.

---

# 13. First Approval

The first approver sees:

- applicant;
- leave type;
- dates;
- number of days;
- available entitlement;
- covering RA;
- cover status;
- RA remarks;
- relevant team-availability context.

The approver selects:

- Approve; or
- Reject,

and may enter remarks.

If approved, the application advances to final approval.

If rejected:

- the application becomes Rejected;
- reserved normal entitlement is released;
- applicant and covering RA are notified.

---

# 14. Final Approval

The final approver (the Master's admin delegate) sees:

- original application;
- entitlement position;
- covering RA and cover status;
- first approver decision and remarks;
- operational team context.

If approved:

- application becomes Approved;
- an authoritative approved leave record is created;
- applicant and covering RA are notified;
- team availability views update.

If rejected:

- reserved entitlement is released;
- applicant and covering RA are notified.

---

# 15. Extra-Leave Appeal Workflow

A typical extra-leave path is:

**Appeal Submitted → Awaiting Cover Confirmation → Pending Master Decision → Approved / Rejected**

The precise sequence may permit cover confirmation and staff review to occur in parallel, but the application must make the outstanding prerequisites visible.

The Residential Master should see:

- ordinary entitlement position;
- amount of leave beyond entitlement;
- applicant's reason;
- covering RA;
- covering RA confirmation;
- relevant previous and upcoming leave;
- team coverage context;
- any staff remarks.

The Residential Master then explicitly:

- approves the extra leave; or
- rejects the appeal.

The decision and reason are retained.

---

# 16. Web-Based Approval Queue

All approval activity takes place in the Azure web application.

Approvers should have an **Awaiting My Decision** view.

It shows:

- ordinary leave requiring first approval;
- ordinary leave requiring final approval;
- extra-leave appeals requiring Residential Master decision;
- age of outstanding requests;
- relevant coverage information.

Approval should normally require only a few clicks.

---

# 17. Email Notifications

Microsoft 365 email is used for notifications without making email itself part of the workflow state machine.

## 17.1 Sent from the actor

Each notification is sent **from the account of the person whose action caused it** (author, 2026-10-22):

- an RA's application, appeal or withdrawal: from the RA;
- a covering RA's confirmation or decline: from the covering RA;
- an approval or rejection: from the approver;
- an administrative correction or reassignment: from the administrator.

Because the actor is signed in at the moment of the action, the send can use the actor's own delegated permission: Microsoft Graph `Mail.Send` (delegated), using the token Easy Auth already holds for the signed-in user. The permission is declared on the Easy Auth app registration, with Easy Auth's token store on and the scope requested at sign-in; granting and configuring these are deployment prerequisites, after which the application-side send is validated. RRW's email uses the same grant (RRW's `guide/post_azure_todo_checklist.md`, item 10). Should delegated sending fail in practice, the fallback is a shared service mailbox (Graph application permission restricted to that mailbox), with the actor named in the message and set as Reply-To.

## 17.2 Outbox and retry

Every notification is written to an outbox row in `residentialops` first, with its fully rendered message, including the absolute link back to the relevant page, built from the request at the moment of the action (Cordware has no configured base URL). Sending then reads the outbox. A failed send leaves the row visible as failed; the actor, or an administrator, can resend it from the application. There is no background worker: retries are triggered by people, as in RRW's outbox.

## 17.3 Teams

Approvals stay in the web application (§16, §18). Teams notifications, such as a chat message or activity-feed item linking to the application, are possible later, but need a Teams app or bot and Graph permissions approved by IT, so they are not in the initial release.

Examples of notifications:

Examples:

- application submitted;
- covering RA named;
- cover confirmation requested;
- cover confirmation received/declined;
- first approval completed;
- final approval required;
- appeal requires Residential Master decision;
- application approved;
- application rejected;
- application withdrawn;
- leave cancelled or amended.

Notification emails contain a link back to the relevant application page, which still requires sign-in.

The database remains authoritative even if email delivery fails.

---

# 18. No Power Automate / Teams Approval Dependency

The target system should not require Power Automate or Teams Approvals.

Specifically:

- application submission occurs in the web app;
- approval routing is computed by the web app;
- approval decisions are entered in the web app;
- state transitions are executed by the web app;
- audit events are stored by the web app;
- notifications are generated by the web app;
- email is delivered from the actor's account through Microsoft 365 (§17).

This deliberately reduces the number of independently configured components that must be maintained.

A future Teams notification or bot integration could be added if genuinely useful, but must not become necessary for the core workflow.

---

# 19. Leave History

RAs may view their own leave and application history.

Each record should show:

- normal or extra leave;
- leave type;
- dates;
- number of days;
- covering RA;
- status;
- submission date;
- decision dates;
- appropriate decision remarks.

---

# 20. Rejected and Withdrawn Applications

Rejected and withdrawn applications remain structurally stored.

They do not count against entitlement.

This replaces the older approach in which parts of the audit history might exist mainly in email.

---

# 21. Administrative Portal

## 21.1 Cycle setup

Administrators can:

- create a new RA cycle;
- choose whether ordinary leave requires cover confirmation (§12);
- upload roster/entitlement CSV;
- preview and validate changes;
- commit the import;
- inspect import history.

## 21.2 RA management

Administrators can:

- search RAs;
- manually add an RA;
- edit an RA;
- deactivate an RA;
- amend team assignment;
- amend approval routing.

## 21.3 Entitlement management

Administrators can:

- inspect imported entitlements;
- adjust individual entitlement where policy requires;
- record reason for adjustment.

Entitlement adjustment must remain conceptually distinct from extra-leave approval.

## 21.4 Leave administration

Administrators can:

- search applications;
- filter by RA, team, status, dates and leave type;
- inspect workflow history;
- correct erroneous records;
- cancel approved leave;
- reassign outstanding approvals;
- record externally authorised leave;
- perform explicit administrative overrides.

All changes are audited.

---

# 22. Team Leave Dashboard

Authorized residential staff should be able to see, for a selected period:

- RAs currently away;
- upcoming approved leave;
- covering RA arrangements;
- pending applications;
- pending appeals;
- overlapping absences;
- potential coverage conflicts;
- numbers available/away by team.

A calendar or timeline view may complement a list view.

---

# 23. Covering RA Dashboard / View

An RA should have a lightweight view of occasions where they are:

- proposed as covering RA;
- awaiting their confirmation;
- confirmed as covering RA;
- currently providing cover;
- scheduled to provide future cover.

This prevents cover commitments from being buried solely in email.

---

# 24. Approver Dashboard

Approvers should see:

- requests awaiting their decision;
- age of outstanding requests;
- requests awaiting cover confirmation;
- forthcoming absences;
- relevant team coverage;
- recent decisions.

Actionable work should appear first.

---

# 25. Administrative Dashboard

Administrators should be able to see:

- pending requests by stage;
- appeals awaiting Residential Master decision;
- outstanding cover confirmations;
- unusually old applications;
- upcoming leave;
- team coverage conflicts;
- entitlement anomalies;
- extra leave approved by cycle;
- incomplete routing/configuration;
- recent administrative corrections.

---

# 26. Audit Trail

For consequential events record:

- timestamp;
- actor;
- event type;
- affected record;
- previous state where relevant;
- resulting state;
- reason/remarks where relevant.

Examples:

- roster imported;
- roster row manually changed;
- entitlement changed;
- application submitted;
- covering RA selected;
- cover confirmed/declined;
- approval decision;
- appeal submitted;
- extra leave approved/rejected;
- withdrawal;
- cancellation;
- administrative override.

Email messages are communications artifacts, not the authoritative audit record.

The audit trail follows RRW's audit model: Residential's own audit table in `residentialops`, one canonical detail envelope, and a registered allowlist of event types that the tests enforce. Support Logs' audit lives in `supportlogs`.

---

# 27. Permissions and Data Visibility

Entra authentication establishes identity.

Application authorization determines access.

## RA

Own leave information plus cover commitments assigned to them.

## Covering RA

Only the information required to understand and manage the relevant cover arrangement.

## Approver

Applications and operational context within assigned scope.

## Residential staff

Team-level operational information within assigned scope.

## Administrator

Administrative information according to assigned scope.

All authorization is enforced server-side.

## 27.1 Database-level isolation

Application authorization is not the only control. The databases also use least-privilege roles (strategy v1.0 §4):

- `residentialops` and `supportlogs` each have their own login role, with `CONNECT` and `TEMPORARY` revoked from `PUBLIC` and `CONNECT` granted only to that role;
- Leave runs with the `residentialops` role, which cannot connect to `supportlogs`;
- the web application never runs routine requests as the PostgreSQL server admin.

This limits the blast radius of an application bug: a flaw in Leave code cannot query Resident Support Log content, because Leave's credentials cannot reach that database. Leave and Events share the `residentialops` role, and are kept apart in code (§2.7).

---

# 28. Technical Shape

The Leave module is part of Residential Apps, built in `residentialapps/` of `philoyhc/review-robin-web` (strategy v1.0 §2, §5). The implementation is:

- **one Cordware App Service**, shared with RRW; Residential Apps mounted at `/residentialapps`;
- **one Python package, `residentialapps.app`**, a modular monolith with `core`, `leave`, `events` and `supportlogs` modules;
- **FastAPI, server-rendered Jinja templates and SQLAlchemy 2.x**, following RRW's three-layer split (thin routes, services, models) and its UI conventions (§2.5); no frontend framework;
- **two PostgreSQL databases**, `residentialops` and `supportlogs`, each with its own login role and Alembic history; local SQLite files by default for development;
- **identity from Cordware** (Easy Auth); no sign-in code in the application;
- **email from the actor's account** through Microsoft 365, via an outbox (§17);
- **Residential's own audit and outbox** in `residentialops`;
- **no Power Automate dependency**;
- **no Teams Approvals dependency**.

The application should remain a conventional web application unless future requirements justify additional frontend complexity.

---

# 29. Conceptual Data Model

The Leave module consumes shared platform entities and owns leave-specific entities.

## Shared `core` entities

### Person / InstitutionalIdentity

Local representation of an institutional person and their Entra identity.

### RACycle

Defines an operational RA appointment cycle.

### RAAppointment

States that a person is an RA for a particular cycle and team/unit. This is shared by Leave and Events. Leave applications should reference the RA appointment, not simply the person, because leave belongs to a specific appointment/cycle.

### Team / ResidentialUnit

Residential team/unit structure.

### ResidentialAppointment

Who holds which residential appointment (RF, RSLM, Master, the Master's admin delegate), for which period and team. RA appointments are this same record with appointment type RA: `RAAppointment` above is that RA-typed row, not a second store, so the roster import creates one appointment per RA and there is one source of truth for RA status. Appointments are not permissions (strategy v1.0 §4): Leave's own permissions and approver routing live with Leave in `residentialops` and may be derived from appointments, while Support Logs' permissions live in `supportlogs`.

### AuditEvent / OutboxMessage

Residential's audit events and notification outbox, in `residentialops`. Support Logs keeps its own audit in `supportlogs`. File storage is not needed by Leave and is not part of the platform for now.

## Leave-owned entities

### LeaveAuthorization

Leave's own permissions, in `residentialops` beside the Leave tables: one row per grant of a Leave role that routing does not already give, chiefly **team viewer** (§4.5) and **Leave administrator** (§4.6), each naming its grantee (the `Person`, by stable core person ID), with its scope (all teams or named teams), granted_by / granted_at and revoked_by / revoked_at, and audited. A grant may require an appointment as eligibility (for example a staff appointment for team viewer), but the appointment alone grants nothing. RA-facing rights come from an active RA appointment (§5.5), and decision rights (first and final approval, appeal decisions) from `ApproverRouting`; neither needs a `LeaveAuthorization`.

### ApproverRouting

Who decides what, per team and cycle: the first approver (the RF, or a delegate), the final approver (the Master's admin delegate) and the **appeal decider** (the Residential Master, §4.3). Each is a named person, set and changed by an administrator and audited; routing is usually seeded from appointments, but the routing row, not the appointment, is what authorizes the decision. A covering RA's right to confirm or decline comes from being named on the application (§4.4).

### LeaveType

Configured normal leave category.

### LeaveEntitlement

RA appointment + leave type + cycle + entitlement.

### EntitlementAdjustment

Audited adjustment to normal entitlement.

### LeaveApplication

Ordinary application or appeal request.

### CoverArrangement

Applicant, covering RA, relevant dates and confirmation state.

### ApprovalDecision

One record per leave approval decision. This remains a Leave-domain object rather than being forced into a generic cross-platform approval table.

### LeaveRecord

Authoritative approved leave.

Should identify whether leave is:

- `NORMAL_ENTITLEMENT`; or
- `EXTRA_LEAVE`.

### ImportBatch / LeaveImportDetail

Tracks the leave-specific effects and validation of a shared RA-cycle CSV provisioning operation.

---

# 30. Application Status Model

Ordinary application states may include:

- `DRAFT`
- `PENDING_FIRST_APPROVAL`
- `PENDING_FINAL_APPROVAL`
- `APPROVED`
- `REJECTED`
- `WITHDRAWN`
- `CANCELLED`

Extra-leave appeals may include:

- `APPEAL_DRAFT`
- `AWAITING_COVER_CONFIRMATION`
- `PENDING_MASTER_DECISION`
- `EXTRA_LEAVE_APPROVED`
- `APPEAL_REJECTED`
- `WITHDRAWN`

`WITHDRAWN` is one terminal state shared by both kinds of request.

Cover status should be modelled separately rather than multiplying leave workflow states unnecessarily.

For example:

- `PROPOSED`
- `CONFIRMED`
- `DECLINED`
- `CANCELLED`

---

# 31. Migration from Existing System

Migration should include where practicable:

- active RA profiles;
- current entitlements;
- approved leave history;
- pending applications;
- approver assignments;
- useful historical applications.

Existing SharePoint identifiers may be retained as migration-reference fields.

Migration should distinguish:

1. authoritative structured data available from SharePoint; and
2. historic information existing only in emails or old workflow artifacts.

A reconciliation report should compare per RA:

- normal entitlement;
- approved normal leave;
- pending normal leave;
- remaining balance.

Extra-leave history should be migrated where it can be reliably identified, but uncertain historical records should not be artificially reconstructed.

---

# 32. Cutover

At cutover:

1. freeze creation/editing in the old Power App;
2. perform final migration;
3. reconcile balances and pending applications;
4. enable the Azure application;
5. redirect users to the new application;
6. retain old SharePoint data read-only as appropriate;
7. retire Power Automate leave workflows once outstanding legacy applications have been resolved or migrated.

Post-cutover transactions have one authoritative source: the Azure application's database.

---

# 33. Minimum Viable Release

## RA

- Entra login;
- balance dashboard;
- application submission;
- covering RA selection;
- application/history view;
- extra-leave appeal.

## Covering RA

- notification;
- cover confirmation where required;
- cover-commitment view.

## Approval

- sequential ordinary approval;
- Residential Master extra-leave decision;
- web approval queues;
- remarks and decisions.

## Staff

- team leave and coverage dashboard.

## Admin

- CSV cycle import;
- preview/validation;
- manual add/edit/deactivate;
- entitlement management;
- application search;
- corrections;
- reporting/export.

## Platform

- mounted under Cordware at `/residentialapps`;
- a full localhost run with local databases and fake roles, plus tests and CI (§4.8);
- PostgreSQL (`residentialops`: Support Logs, built first, starts the core with the Staff roster, residential appointments and residential units; Leave adds RA cycles, appointments and rosters to it);
- application authorization;
- audit trail;
- email notifications;
- responsive UI;
- no Power Automate/Teams dependency.

---

# 34. Acceptance Scenarios

## A. Cycle import

Administrator uploads valid CSV → preview identifies additions/changes → administrator commits → RA roster and entitlements become active.

## B. Manual roster correction

Administrator edits an imported RA row → correction is immediately effective → audit trail records old/new values.

## C. Normal application

RA logs in → sees correct balance → selects dates and covering RA → submits → first approver approves → final approver approves → applicant and covering RA are notified → balance and team dashboard update.

## D. Cover notification

RA names another RA as covering RA → covering RA receives notification and sees the commitment in the application.

## E. First-stage rejection

RA submits → entitlement is reserved → first approver rejects → reservation released → applicant and covering RA notified.

## F. Final-stage rejection

RA submits → first approver approves → final approver rejects → reservation released → decisions retained.

## G. Insufficient entitlement

RA requests more leave than remains → system explains shortfall and offers extra-leave appeal instead of merely blocking submission.

## H. Extra-leave appeal

RA submits appeal → names covering RA → covering RA confirms → Residential Master sees reason, entitlement shortfall and cover → approves → leave is recorded as extra leave rather than increasing entitlement.

## I. Appeal rejected

Residential Master rejects appeal → normal entitlement remains unchanged → no extra-leave record is created → decision remains auditable.

## J. Pending entitlement

RA submits normal leave → pending days reserve entitlement against subsequent applications.

## K. Overlap

RA attempts invalid overlapping leave → application is blocked.

## L. Cover declined

Covering RA declines proposed cover → applicant and relevant staff are notified → application cannot silently proceed as though cover existed.

## M. Administrative correction

Administrator corrects a leave record → balances recalculate → old value, new value, actor and reason remain auditable.

## N. Authorization

RA attempts direct access to another RA's leave record → server denies access.

## O. Notification failure

Email notification fails → underlying application and workflow state remain intact → the failed outbox row is visible → the actor or an administrator resends it.

## P. Support Log isolation

Leave's database credentials are used to connect to `supportlogs` → the connection is refused.

## Q. Localhost

A fresh checkout runs Cordware + Residential Apps on localhost with local databases and fake auth → each fake role can walk scenarios C–I.

---

# 35. Architectural Boundary Decisions

1. **PostgreSQL is the operational source of truth.**
2. **Leave is one module of Residential Apps, mounted under Cordware; Cordware supplies identity.**
3. **Leave, Events and the shared core live in `residentialops`; Support Logs lives in `supportlogs`, which Leave's credentials cannot reach.**
4. **The shared core contains stable cross-module concepts only; Support Log content and indicators never belong there.**
5. **RA membership is provisioned once per cycle as shared core RA appointment data; Leave and Events consume the same roster.**
6. **Leave entitlements are Leave-domain data, even when loaded from the same CSV.**
7. **Administrators can manually add, edit and deactivate RA appointment records and correct leave entitlements.**
8. **Entra provides identity, not RA membership or entitlement.**
9. **There is no SIS dependency.**
10. **Covering RA is a first-class application relationship and receives notifications.**
11. **Extra leave is a discretionary approval, not additional entitlement.**
12. **Extra leave is recorded separately from normal entitlement usage.**
13. **The Residential Master owns the discretionary extra-leave decision.**
14. **Approval workflow lives entirely in the Azure application.**
15. **Leave approval tables remain Leave-domain tables; similarity with Events approvals does not justify a generic approval schema at this stage.**
16. **Power Automate and Teams Approvals are not required components.**
17. **Microsoft 365 email is a notification channel, not a workflow engine.**
18. **The RA interface is mobile-first and form-based.**
19. **Administrative exceptions are explicit and audited.**
20. **Routine Leave execution paths cannot connect to the Support Log database.**
21. **First approval is by the RA's RF, or a delegate staff member; final approval of ordinary leave is by the Residential Master's admin delegate.**
22. **Notifications are sent from the actor's account, through an outbox; the mechanism awaits IT (§17).**
23. **Residential Apps follows RRW as its model: localhost with local databases and fake roles, tests, CI and development practice.**

---

# 36. Changes from v0.3

v0.3 predates the Cordware strategy. v0.4 (22 October 2026) aligns it with strategy v0.9 and the author's rulings of the same day:

- **Platform:** a module of Residential Apps under Cordware, not a stand-alone platform with its own App Service and sign-in (§1, §2.1, §28).
- **Databases:** `residentialops` (core, Leave, Events) and `supportlogs`, replacing one database with four schemas; module table prefixes instead of schemas, so local SQLite works (§2.2, §2.7, §27.1).
- **Database roles:** one role per database with `PUBLIC` access revoked; Leave and Events separated in code rather than by per-module roles (§2.7, §27.1).
- **UI:** RRW's conventions, not HTMX and Bootstrap (§2.5, §28).
- **Identity matching:** by email, with the Entra object ID recorded at first sign-in; no Graph lookup at import (§5.5).
- **Approvers:** first approver is the RF (or a delegate staff member); final approver of ordinary leave is the Master's admin delegate; the Residential Master decides extra-leave appeals personally (§4.2, §4.3).
- **Cover:** cover information and cover confirmation are both built in; an administrator setting decides whether ordinary leave requires confirmation (§12).
- **Email:** from the actor's account, through an outbox with people-triggered retry; Teams deferred (§17).
- **Audit:** Residential's own, on RRW's model; file storage dropped (§26, §29).
- **Localhost and fake roles,** the platform super-admin, and scenarios P and Q added (§4.7, §4.8, §33, §34).
- **Workflow tidied:** no separate Submitted state; cover status drives "awaiting cover confirmation"; one shared `WITHDRAWN` (§11, §30).
- **Classified by device (author, 2026-10-23):** each surface carries its mobile-to-desktop UX class (§2.5).

## Open questions

1. **Email mechanism:** delegated `Mail.Send` (§17.1), Easy Auth's token store and login scopes, and Easy Auth's credential for fetching Graph tokens are deployment prerequisites; what remains on the application side is validating the send. The shared-mailbox fallback applies only if that fails.
