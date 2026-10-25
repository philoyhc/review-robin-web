# Resident Support Log — Functional Specification

> **Moved 2026-10-25 from the private deployment repository** (author), where it was `docs/resident_support_log_functional_spec_v0.3.md` (at `ad94c1c`). Deployment status (which grants are in place, configuration dates, what IT has delivered) was made generic on the way; it is tracked privately with the deployment. "Strategy v1.0" below is the Cordware deployment strategy, also held privately; what Residential depends on from it is in `residentialapps/guide/todo_master.md`.
>
> **Amended 2026-10-25 (author): one package, two applications.** Residential is one `residentialapps/` package mounted as two applications, RA Operations at `/residentialops` and Support Logs at `/supportlogs`; nothing is mounted at `/residentialapps`. Passages below that say "one application" or mount it at `/residentialapps` predate this and are revised at this spec's next version.

**Version:** 0.3, 22 October 2026 (v0.2 refined around actual user groups, peer viewing, student-centred retrieval, opportunity review and explainable review signals; roster-versus-permission rule settled the same day; changes in §18)  
**Status:** Draft for discussion  
**Purpose:** Minimal residential support encounter logging and lightweight support assignment  
**Platform:** the Support Logs pillar of Residential Apps, mounted under Cordware at `/residentialapps` (the Cordware deployment strategy v1.0, held privately); support-specific student and encounter data and Support Logs authorization live in `supportlogs`, while the shared staff roster and residential appointments live in `residentialops`

---

## 1. Purpose

The Resident Support Log is a lightweight operational system for residential staff to record support-relevant encounters with students.

It is intended to provide enough information to:

- identify which students have been receiving support and from whom;
- retrieve a basic contact history if a situation later becomes more acute;
- identify emerging support hotspots across residential clusters;
- provide a more realistic view of staff support workload;
- support formal assignment of students to staff for regular check-ins;
- allow staff to indicate students they are informally following up even without a formal assignment;
- support selective human review when a student's current support context may matter to a consequential residential decision, without turning support data into a wellness score or automated suitability decision.

The system is **not** intended to replace fuller case notes, counselling records, conduct records, or other substantive institutional records.

### 1.1 Place in the platform

Support Logs is one of Residential Apps' two pillars; the other, RA Operations, holds RA Leave and RA Events (`residentialapps/docs/ra_leave_management_functional_spec_v0.4.md`). The pillars share one application and a core in `residentialops` for people, the canonical staff roster, residential appointments and residential units. Support-specific student identities, encounters, follow-ups, formal support assignments, safety records, review results, Support Logs authorization and support-activity audit remain in `supportlogs`, which RA Operations' credentials cannot reach (strategy v1.0 §4). Nothing in the shared core reveals that a student is known to Support Logs.

Like every Cordware application, it follows RRW as its model: it runs fully on localhost with local databases, a fake directory and fake roles, and has its own tests and CI (strategy v1.0 §3).

---

## 2. Core Design Principles

1. **Minimal logging burden**  
   Routine encounter logging should take approximately 10–20 seconds.

2. **Operational rather than clinical**  
   The system records support activity, not detailed case histories or diagnoses.

3. **Privacy by default**  
   Staff should normally see only their own encounters, follow-ups, and formal assignments.

4. **Senior operational oversight**  
   The Master and authorised senior staff should have aggregate and, where necessary, identifiable views for workload, allocation, hotspot detection, and acute follow-up.

5. **No Student Information System dependency**  
   The system should not require integration with the official SIS.

6. **MS365 for identity lookup**  
   Microsoft 365 / Entra ID is used to search for and identify students by name and institutional email, through a directory search made as the signed-in staff member (§4.1).

7. **Local-first repeat lookup**  
   Students previously encountered, followed up, or assigned to a staff member should be surfaced before wider Microsoft 365 directory results.

8. **Data minimisation**  
   Store only information necessary for residential support coordination.

9. **Designed for the baseline expected practice**  
   The primary design target is the minimum encounter-logging and follow-up practice expected of frontline residential staff. The system must not become harder to use because some users may want richer case-recording features.

10. **Explainable review, never automated suitability judgement**  
    The system may compute transparent review signals that indicate when a human should take a second look or consult the relevant RF/RSLM. It must not compute a wellness score or decide that a student is fit, unfit, suitable or unsuitable for an opportunity.

---

## 3. User Roles

### 3.1 RF / RSLM — Frontline Residential Staff

Residential Fellows (RFs) and Residential Student Life Managers (RSLMs) are one functional user group unless a later policy requires a permission difference. They are frontline staff with residential pastoral responsibilities, typically not acting at the full clinical level.

The application is designed primarily around the minimum practice expected of this group: a quick, consistent way to log support-relevant encounters, most of which will not involve an acute incident.

RFs / RSLMs can:

- log encounters with students;
- view encounters they themselves have logged;
- add a student to their own informal follow-up list;
- optionally indicate an intended follow-up cadence;
- view students formally assigned to them;
- flag a student for formal review or possible assignment;
- use a personal dashboard of their follow-ups, due and overdue check-ins and recent activity (§10.1).

RFs / RSLMs should not ordinarily be able to browse encounter records entered by other staff.

They may, however, grant and revoke **peer-view access** where another RF/RSLM needs to share support responsibility for a particular student (§11.1). The default remains private.

### 3.2 Master / Master's Delegates — Senior Oversight

The Master's primary use is oversight rather than routine encounter entry: dashboarding, workload and resource checking, trend and hotspot analysis, formal assignment tracking, and authorised student-level drill-down.

A Master's delegate need not automatically receive every right held by the Master. Delegate permissions should be assignable narrowly according to task.

The Master / appropriately authorised delegates can:

- view aggregate support activity;
- view staff workload indicators;
- view cluster-level support activity and trends;
- manage formal assignments;
- manage students' cluster membership;
- review students flagged for formal assignment;
- inspect identifiable student contact histories when operationally necessary;
- review overdue or due-soon support assignments;
- run or authorise opportunity-review checks (§10.7), where the role permits.

### 3.2.1 Opportunity-Review Delegate

A person coordinating residential feedback on applicants for an opportunity may be given a narrower review role without receiving unrestricted access to support records.

This role can:

- submit or paste a list of institutional emails for an approved review purpose;
- see which students have **no review signal**, **review suggested**, or **review required / active support condition**;
- see the transparent reason categories for a positive signal;
- see which RF/RSLM(s) should be consulted;
- record that consultation has been requested or completed.

This role does **not** by itself permit reading encounter notes or making automated suitability decisions. The review itself is a sensitive audited action (§10.7, §11.3).

### 3.3 System Administrator

Administrators can:

- manage Support Logs configuration;
- manage Support Logs authorization assignments in `supportlogs`, selecting staff from the canonical roster in `residentialops`;
- manage permitted encounter categories and cadence options;
- manage cluster definitions (the list of clusters), but not which students belong to them: student membership is support data, managed by authorised senior staff and audited (§10.5);
- review administrative audit records (roles, configuration and other administrative actions; not support activity, §11.3);
- support operational maintenance.

Administrative access should not imply unrestricted substantive use of support data beyond what is operationally necessary.

### 3.4 Platform super-admin

The Cordware platform super-admin holds **administrator rights only** in Support Logs: roles, configuration and review of administrative audit events, not encounters, follow-ups, assignments or student histories (author, 2026-10-22). The audit of support activity, which names students and records, is outside those rights (§11.3). This is the one carve-out from the platform rule that a super-admin holds full rights in every application (strategy v1.0 §3). Those administrator rights come straight from the platform role, without a Staff-roster entry or a Support Logs authorization, so the super-admin can always grant the first authorizations in a new deployment (§3.5). A super-admin who also needs substantive access is given a senior-staff role like anyone else, and that access is audited.

### 3.5 Who the roles apply to

The **canonical staff roster and residential appointments are shared Residential data and live in `residentialops`**, because the same staff population may act across Support Logs and RA Operations. This answers **who the staff member is** and **what residential appointment they hold** (for example RF, RSLM or Master).

Support Logs authorization is a separate security concern and lives in **`supportlogs`**. It answers **what this staff member may do with support data**: frontline access, senior identifiable access, opportunity-review access, administration, and any later Support Logs-specific permission. Those authorization records reference the stable staff person ID from `residentialops`; they do not duplicate the roster.

The staff roster should be the first implementation of an **extensible Residential roster framework**, not a one-off staff table designed only for Support Logs. The framework must be able to accommodate later roster types with different attributes and lifecycle rules. The presently anticipated roster types are:

1. **Staff roster** — required before Support Logs;
2. **RA roster** — required later by RA Operations;
3. **Student roster** — to be decided; Residential may instead continue to resolve students directly from Entra / Microsoft 365 without maintaining a complete local roster.

**Appointments are not permissions** (author, 2026-10-22). `residentialops` records who the RFs, RSLMs, Master and other staff are; `supportlogs` decides what each of them may do in Support Logs. A person can read or write Support Logs only when **both** hold:

1. an **active Staff-roster entry** in `residentialops`, plus the qualifying appointment where the authorization type requires one (table below); and
2. an **explicit, active Support Logs authorization** in `supportlogs`, granted by a Support Logs administrator.

Both are checked on every request, and access fails closed if either is missing. An appointment never grants Support Logs access by itself: an RF or RSLM appointment makes the person *eligible* for frontline access, and Support Logs may list eligible staff without access so an administrator can grant it, but the grant is always a deliberate, audited act in `supportlogs`. When the roster entry is retired or the qualifying appointment ends, access stops at once; Support Logs then shows the lapsed authorization to its administrators, who revoke it (audited in `supportlogs`). Support Logs never writes to the roster, and the roster never writes Support Logs authorizations.

| Support Logs authorization | Eligibility in `residentialops` |
|---|---|
| Frontline access (§3.1) | active RF or RSLM appointment |
| Senior identifiable access (§3.2) | active Master appointment; or any active Staff-roster entry, granted at the Master's request (a delegate) |
| Safety-flag recipient (§5.10) | as senior identifiable access |
| Opportunity review (§3.2.1) | active Staff-roster entry |
| Support Logs administration (§3.3) | active Staff-roster entry; the platform super-admin holds it without one (§3.4) |

**The one exception is the platform super-admin**, who holds Support Logs administration directly from Cordware's platform role (`SUPER_ADMIN_EMAILS`), with no Staff-roster entry and no authorization record (§3.4). That is also how a new deployment starts: the super-admin grants the first Support Logs authorizations, and every grant is audited as usual. The exception covers administration only, never support content.

The eligibility rules are configuration, not code, and every type is narrower than the person's residential role: a Master's delegate holds only the authorizations granted to them (§3.2).

Support Logs stores references to staff by stable core person ID when recording activity. RAs never hold a Support Logs authorization merely by virtue of being on the RA roster. Students are data subjects, not users of Support Logs: they never sign in, enter data, manage permissions or receive assignments through the application.

### 3.6 Fake roles for localhost

For local development and testing, Support Logs provides a fake role for each authorization type above (frontline, senior identifiable, safety-flag recipient, opportunity review, administration), keyed off Cordware's fake user and switchable per run in `.env` or the shell, as RRW's are. Each fake role sets up both layers, a seeded Staff-roster entry and appointment in the local `residentialops` and the matching authorization in the local `supportlogs`, so the two-layer check (§3.5) runs locally exactly as deployed. They exist only while Cordware's fake auth is on.

---

## 4. Student Identity and Lookup

### 4.1 Identity Source

The system uses the institutional Microsoft 365 / Entra directory as the primary source for student identity lookup.

The search is made **as the signed-in staff member**, with the delegated directory-read permission on the token Easy Auth already holds for them. The permission is delegated `User.ReadBasic.All`, declared on the Easy Auth app registration beside `Mail.Send`, with Easy Auth's token store on; granting and configuring these, and Easy Auth's credential for fetching Graph tokens, are deployment prerequisites. What remains on the application side is validating a real lookup. Until then, staff enter the student's institutional email directly, checked only for format.

Expected available fields:

- Entra object ID;
- display name;
- institutional email.

The institutional email address is sufficient as the main human-facing student identifier. Student ID is not required.

The Entra object ID should be stored internally where available because it provides a more stable technical identifier than email.

### 4.2 Search Behaviour

When a staff member starts typing a substring of a student's name or institutional email, the system should:

1. search the staff member's own locally known students first;
2. rank active formal assignments and informal follow-ups highly;
3. include recently contacted students;
4. if necessary, search the wider Microsoft 365 directory;
5. show display name and institutional email for disambiguation.

The wider directory search is acceptable even if it cannot distinguish students of the residential college from other institutional users.

### 4.3 Local Student Working Set

The system should automatically build a staff-specific working set from:

- prior encounters logged by that staff member;
- active informal follow-ups;
- active formal assignments.

No manually maintained personal student list should be required.

### 4.4 Local Student Record

When a student is selected for the first time, the system should create or reuse a minimal local record containing:

- Entra object ID, where available;
- institutional email;
- current display name;
- limited residential metadata where available or entered separately.

The record lives **only in `supportlogs`** (author, 2026-10-22), never in Residential's shared core: a core person row for every student looked up would reveal to RA Leave and Events who is known to Support Logs. If a student is also an RA or another core person, Support Logs may store that link on its own side; the core never learns of it.

### 4.5 Student-Centred Retrieval

Although encounters are entered individually, authorised users must be able to retrieve the support history of a student across all encounters, follow-ups and formal assignments that they have permission to see.

This is a **student-centred view**, not a case file. A student may have several support-relevant encounters without ever becoming a formal case or receiving a formal assignment.

The view should make it easy to identify the relevant RF/RSLM(s) who have been following the student, subject to the applicable viewing permissions.

### 4.6 Localhost directory

A local run cannot reach Microsoft 365, so the directory search has a local stand-in with seeded fake students, used whenever Cordware's fake auth is on. Tests use the same stand-in.

---

## 5. Encounter Logging

### 5.1 Standard Workflow

The standard encounter flow should be:

1. Open **Log encounter**.
2. Search/select student.
3. Select approximate duration.
4. Select encounter type.
5. Optionally select one or more broad concern areas; if there is a safety concern, mark it, which starts the escalation flow (§5.10).
6. Record whether continuing follow-up is needed when applicable.
7. Optionally enter a very short note.
8. Optionally create or update an informal follow-up.
9. Submit.

For a routine encounter, the expected interaction may be as little as:

> Student → 15 min → Check-in → Submit

### 5.2 Automatically Captured Fields

The system should automatically capture:

- staff identity from Entra sign-in;
- current date/time by default;
- created timestamp;
- modified timestamp.

Date/time may be editable where staff are logging retrospectively.

### 5.3 Required Fields

Required encounter fields:

- student;
- approximate duration;
- encounter type.

### 5.4 Optional Fields

Optional encounter fields:

- broad concern areas;
- safety concern (§5.10);
- whether continuing follow-up is needed;
- whether the encounter was student-initiated or staff-initiated where this is not already captured by encounter type;
- whether the encounter was planned or incidental, if retained after usability testing;
- very short note;
- follow-up action.

### 5.5 Duration Options

Suggested preset values:

- 5 minutes;
- 10 minutes;
- 15 minutes;
- 30 minutes;
- 45 minutes;
- 60 minutes;
- 60+ minutes.

### 5.6 Encounter Types

Initial configurable list:

- Check-in;
- Student-initiated conversation;
- Staff-initiated conversation;
- Welfare follow-up;
- Practical support;
- Other.

The exact list should remain configurable.

### 5.7 Concern Areas

Concern areas are **optional** and broad, and more than one may be chosen (author, 2026-10-22). The seeded default list, configurable afterwards:

| Concern area | Covers, for example |
|---|---|
| Academic / career | academic concerns, career, internships |
| Adjustment | transition, settling in, homesickness |
| Wellbeing | emotional and mental wellbeing, stress |
| Health and accessibility | medical matters, accessibility support, disability accommodations, substance use |
| Family | family circumstances |
| Relationships | friends, partners, roommates, other interpersonal matters |
| Financial / practical | money, logistics, practical arrangements |
| Residential / community | room or housing issues, hall and community life |
| Conduct-related | disciplinary matters |
| Other | anything else |

The list is deliberately compressed from a more clinically geared institutional form (author, 2026-10-22): these categories are for coarse operational analytics, not diagnosis, so the labels stay broad and the right-hand column is guidance for staff, not separate options. A suicidal-ideation or other safety concern is **not** a concern area; it has its own flow (§5.10).

### 5.8 Notes

The note field should be deliberately constrained, for example 250–500 characters.

Suggested UI guidance:

> Brief context only. Detailed case notes belong in the appropriate substantive record system.

The system should actively discourage creation of shadow counselling, conduct, or case files.

### 5.9 Location / Mode

Exact physical location should not be required unless a clear operational need emerges.

If included, use a small coarse list such as:

- In person;
- Phone;
- Online;
- Other.

### 5.10 Safety Concerns and Escalation

Suicidal ideation, and any other risk to a student's safety, warrants escalation beyond the pastoral support the residential team can offer (author, 2026-10-22). Support Logs therefore treats a safety concern as its own flag on an encounter, separate from the concern areas, in two forms.

**A new safety concern** covers a first disclosure, or a fresh one from a student already being supported. Marking an encounter with it:

1. shows the institution's crisis protocol in the form (whom to contact, in what order, and emergency numbers), so the staff member acts on it at once;
2. requires the staff member to record the escalation step taken (for example: counselling contacted, duty senior staff contacted, emergency services called) and when;
3. raises a **safety flag** on the student, visible immediately on the dashboard of every staff member holding the *safety-flag recipient* authorization (§3.5). The flag stays **active**, and prominent, until it is closed with a recorded outcome (for example: referred to counselling, assessed by counselling, no further action). Acknowledging it (a senior staff member taking it on) does not close it: unacknowledged flags sit above acknowledged ones, and both count as active until closure.

The application records and surfaces the escalation; it is not the alerting channel of record. The escalation happens through the protocol's own contacts (a call, a handover), which the form prompts. An email or Teams alert to senior staff can follow once the email mechanism is settled (§17); until then, v1 has no automated alerts, so the protocol step is what carries the urgency.

**Managed safety support** covers a student whom counselling has assessed as low risk and fit to stay, and who asks the residential team for regular check-ins, reminders about their coping plan, and similar support. This is recorded as a **formal assignment** (§7) with source *Counselling*, a cadence, a *safety-plan support* marker and a short operational instruction (for example: "weekly check-in; remind of coping plan"). Check-ins under it are logged as ordinary encounters, usually with concern area *Wellbeing*, and do not raise new flags. If the student discloses a new or worsening concern, the staff member marks a new safety concern and the escalation above runs again.

Data minimisation still applies: the flag and the marker record that escalation or support is happening, and the steps taken, never method, plan or clinical detail.

Who sees what:

- the staff member who raised a flag, and staff holding the *safety-flag recipient* authorization, see it and its outcome;
- the staff member assigned to managed safety support, and senior staff, see the marker and instruction;
- every view is an audited read (§11.3).

This is a human-raised flag, not automated risk scoring (§15).


### 5.11 Structured Signals for Later Human Review

The encounter form must capture enough structured information to support later human-review workflows without turning the form into clinical assessment.

Primary review-relevant signals are:

- encounter type;
- optional concern area(s);
- whether continuing follow-up is needed;
- active informal follow-up;
- active formal assignment and its cadence;
- safety escalation or managed safety-plan support;
- which staff are involved;
- recency and pattern of encounters.

Duration, total encounter count and change in encounter frequency are useful **secondary** signals. They must not be treated as sufficient on their own.

The system should not ask RFs/RSLMs to assign a numeric severity, wellness or risk rating. If a structured field does not materially help frontline follow-up or later review logic, it should not be required.

A practical consequence is that several low-intensity practical-support contacts need not have the same review significance as repeated welfare follow-ups, an active follow-up relationship, or a formal high-cadence check-in plan.

---

## 6. Informal Follow-Up

### 6.1 Purpose

A staff member should be able to indicate:

> This is someone I am deliberately keeping in touch with.

This represents an informal staff follow-up and does not imply formal institutional assignment.

### 6.2 Creation

A staff member may create an informal follow-up:

- directly from an encounter;
- from the student profile;
- through a quick post-submit action.

### 6.3 Fields

Suggested fields:

- student;
- staff member;
- start date;
- optional intended cadence;
- optional short operational note;
- active / closed status;
- created and modified timestamps.

### 6.4 Suggested Cadence Options

- No fixed cadence;
- Fortnightly;
- Weekly;
- Custom.

### 6.5 Visibility

The staff member should see their own follow-ups.

The Master / authorised senior staff should be able to view informal follow-ups for workload and operational oversight.

---

## 7. Formal Assignment

### 7.1 Purpose

Formal assignment is for students whom the institution has deliberately assigned to a staff member for ongoing support or regular check-ins.

Examples include students referred by counselling or other authorised institutional sources.

### 7.2 Formal Assignment Fields

Suggested fields:

- student;
- assigned staff member;
- assigned by;
- assignment source;
- start date;
- expected contact frequency;
- optional review date;
- optional end date;
- status;
- short operational instruction;
- created and modified timestamps.

### 7.3 Assignment Sources

Initial configurable examples:

- Counselling (a reserved source with a fixed identifier: it can be relabelled but not removed, because safety-plan support depends on it, §5.10);
- Dean's Office;
- Master / residential leadership;
- Residential staff referral;
- Other.

### 7.4 Assignment Cadence

Possible values:

- Monthly;
- Fortnightly;
- Weekly;
- Twice weekly;
- 3+ times weekly;
- Custom.

### 7.5 Data Minimisation

The assignment should store only the operational information required for residential follow-up.

For example:

> Counselling referral — weekly check-in — review in four weeks.

The system should not require the substantive reason, clinical assessment, or counselling notes. The one exception is the *safety-plan support* marker (§5.10), which records only that the assignment supports a counselling-assessed safety plan.

### 7.6 Assignment Status

Suggested statuses:

- Active;
- Paused;
- Closed.

### 7.7 Assignment Monitoring

For active assignments, the system should calculate:

- last logged contact;
- next expected contact;
- due-soon status;
- overdue status;
- number of contacts within the relevant review period.

---

## 8. Conversion from Informal Follow-Up to Formal Assignment

An informal follow-up should be convertible into a formal assignment without creating a disconnected duplicate record.

The system should preserve the history, for example:

- staff began informal follow-up;
- senior staff converted the relationship into a formal assignment;
- expected cadence was set.

This supports continuity and retrospective understanding.

---

## 9. Student View

A staff member viewing a student should see only information they are authorised to access. Opening the view is itself an audited action (§11.3).

Where permission allows, the student view should bring together all relevant encounters, informal follow-ups and formal assignments for that student. This aggregation is for retrieval and coordination; it does not create a formal "case file."

For their own supported student, the view may show:

- student name and institutional email;
- formal assignment status, if assigned to that staff member;
- informal follow-up status;
- expected cadence;
- last contact;
- next due date;
- recent encounters logged by that staff member;
- action to log a new encounter.

---

## 10. Dashboard and Operational Analytics

### 10.1 Personal RF / RSLM Dashboard

Each RF/RSLM should have a personal dashboard focused on **self-management**, not supervisory comparison.

It should help the staff member answer:

- whom am I currently following up;
- which formal or self-set check-ins are due soon or overdue;
- which students with an expected cadence have not been seen recently;
- what support activity have I logged recently;
- which encounters or follow-ups currently require my attention.

The dashboard should include, at minimum:

- active formal assignments, including Counselling-originated check-in plans;
- active informal follow-ups;
- optional self-set expected frequency / cadence;
- next expected check-in, due-soon and overdue state;
- recent encounters;
- students with no recent contact despite an expected cadence;
- encounter count and total support minutes over a recent period;
- a simple breakdown of recent activity by encounter type and, where useful, concern area;
- active safety-related items that the staff member is authorised to see.

The scheduling and follow-up portion should work well on a phone; richer analytical views may make better use of desktop width.

This dashboard is distinct from the Master's dashboard:

> **Personal dashboard:** what do I need to attend to, and what has my own recent support activity looked like?

> **Master dashboard:** how is support distributed across the team, where are the hotspots, and where may reallocation or intervention be needed?

### 10.2 Team Workload and Oversight

The Master / senior team should be able to view workload indicators such as:

- number of active formal assignments;
- number of informal follow-ups;
- number of distinct students contacted;
- encounter count over rolling periods;
- total support minutes;
- expected formal-assignment contact burden.

Simple counts of assigned students should not be treated as sufficient because different cases may have very different expected intensity.

### 10.3 Assignment Load Weighting

A simple weighting model may be used for planning, for example:

- Monthly = 1
- Fortnightly = 2
- Weekly = 4
- Twice weekly = 8
- 3+ times weekly = 12

This is an operational indicator only, not a scientific measure of case complexity or staff performance.

### 10.4 Student Hotspot Detection

Useful indicators may include:

- contact frequency;
- total support minutes;
- number of different staff involved;
- formal assignment status;
- escalation / review flags, including active safety flags, open or acknowledged (§5.10);
- acceleration in contact frequency compared with a preceding period.

A sharp increase in contacts may be more informative than a high but stable baseline.

### 10.5 Cluster View

The list of clusters can be shared with RA Operations as Residential's core residential units. **Which cluster a student belongs to** is Support Logs data, held in `supportlogs` and entered or imported there by authorised senior staff, not administrators, for the reason in §4.4; each change is audited.

Where cluster information is available, the system should support views such as:

- number of students receiving support;
- support contacts per cluster;
- total support time;
- number of students with rising activity;
- trend over time.

### 10.6 Coverage / Due Follow-Up

The system should highlight:

- overdue formal check-ins;
- due-soon formal check-ins;
- assignments approaching review date.

The system may later support reduced-contact or no-contact alerts if a specific operational need is defined.

### 10.7 Opportunity / Applicant Review

Sometimes another institutional unit asks Residential for feedback on a list of students applying for an opportunity where current wellbeing or support needs may matter, for example an overseas field trip.

An authorised reviewer may submit a batch of institutional emails. The system matches them against Support Logs and returns one of three review states:

- **No review signal**
- **Review suggested**
- **Review required / active support condition**

The purpose is solely to identify students for whom the relevant RF/RSLM should be consulted before Residential gives feedback. The system does not decide whether a student should participate.

A positive result should show **why** the student was surfaced, using named, interpretable reasons rather than a composite score. Possible reasons include:

- active formal check-in assignment;
- active safety-plan support;
- active informal follow-up;
- unresolved safety escalation;
- repeated recent welfare/support encounters;
- marked increase in recent support activity compared with the student's own prior pattern;
- several different staff recently involved;
- explicit recent indication that further follow-up is needed.

A raw encounter count or total duration is insufficient by itself. The logic should consider the pattern and type of activity.

**No review signal** means only that nothing currently recorded in this system triggered a second look. It must never be presented as evidence that the student is well or suitable for the opportunity.

For a positive signal, the reviewer should be shown which RF/RSLM(s) have the relevant current or recent involvement so that human consultation can follow.

The review should be current-state and recent-activity oriented. Historical pastoral data should not become a permanent suitability marker merely because it exists.

### 10.8 Review-Signal Rules

Review signals are rule-based, transparent and configurable. They are not machine-learned and do not create a stored wellness score.

The implementation may distinguish:

- **Review required / active support condition:** strong current state such as an unresolved safety escalation or specified active formal support condition;
- **Review suggested:** softer but meaningful patterns such as active informal follow-up, repeated welfare contacts, several staff recently involved, or a significant increase in recent support activity;
- **No review signal:** no configured trigger is currently met.

The exact thresholds remain a policy/configuration decision and should be tested against real workflow before production use.

The review signal should normally be computed on demand. For a consequential opportunity-review run, the audit record should preserve the result and the reason categories that were presented at that time, so the review is retrospectively explainable.

---

## 11. Access Control

### 11.1 RF / RSLM

RFs / RSLMs should normally be able to access only:

- encounters they created;
- their own informal follow-ups;
- students formally assigned to them;
- records made visible through an explicit peer-view grant;
- minimal student directory information needed for lookup.

**Peer-view grants** are private-by-default exceptions. A staff member may grant or revoke another RF/RSLM access where shared support responsibility makes this necessary.

The preferred scope is student-level access to the granting staff member's relevant records for that student, rather than broad access to all of the grantor's records. The grant, revocation and subsequent identifiable reads are audited.

Whether an authorised senior staff member may create a peer-view grant on behalf of staff remains a policy decision.

### 11.2 Senior Staff and Opportunity Reviewers

Authorised senior staff may access:

- aggregate data across all staff;
- formal assignments;
- informal follow-up indicators;
- identifiable student contact history where required for operational reasons.

An opportunity-review delegate (§3.2.1) receives only the narrower review surface: batch matching, review state, reason categories and relevant RF/RSLM identities. That role does not itself grant access to encounter notes or complete student histories.

### 11.3 Auditability

In Support Logs, **reads are actions** (author, 2026-10-22). The audit trail, kept in `supportlogs`, records:

- every view of identifiable student data: a student view, an encounter or follow-up list, a senior-level student history, a dashboard drilled down to named students, and every export;
- encounter creation and edits;
- creation / closure of informal follow-up;
- formal assignment creation, changes, and closure;
- changes in expected frequency;
- every safety-escalation transition (§5.10): raised, with the escalation step; acknowledged; closed, with the outcome; each recording who acted and when;
- setting or clearing the *safety-plan support* marker on an assignment;
- peer-view grants and revocations;
- opportunity-review runs, including purpose, students checked, review state, reason categories presented, and staff identified for consultation;
- significant administrative actions.

Aggregate views that show no individual student are not audited as reads.

Audit ownership follows **object ownership**:

- changes to the canonical staff roster and residential appointments are `residentialops` events and are audited there;
- grants, revocations or changes to Support Logs authorization are `supportlogs` events and are audited in `supportlogs`;
- peer-view grants and every other student-specific access grant are `supportlogs` events and are audited in `supportlogs`;
- if a `residentialops` roster/appointment change causes a distinct Support Logs authorization change, each database audits its own event, with the Support Logs event recording the source/reason where useful. This is a causal pair, not a duplicated audit record.

Within `supportlogs`, the audit trail then splits by what it reveals. **Administrative events** (Support Logs authorization, configuration and other administrative changes) can be reviewed by administrators and the platform super-admin. **Support-activity events** (reads and changes of student data) reveal who was seen and when, so they can be reviewed only by senior staff holding identifiable cross-staff access, and that review is itself an audited read. Audit records follow RRW's audit model (one canonical detail envelope and a registered list of event types, checked by the tests), extended with read events. Each read records who looked, what was shown and when, never the content itself.

---

## 12. Security and Privacy

The system uses institution-approved Azure and Microsoft identity infrastructure.

Minimum principles:

- authentication through institutional Microsoft Entra ID, at Easy Auth in front of Cordware; the application contains no sign-in code;
- role-based application authorisation, with canonical staff identity and residential appointments sourced from `residentialops` but Support Logs-specific authorization stored and audited in `supportlogs`, including a narrow opportunity-review permission distinct from full support-record access;
- a separate database, `supportlogs`, with its own login role, `CONNECT` and `TEMPORARY` revoked from `PUBLIC`, and `CONNECT` granted only to that role; RA Operations' role cannot connect to it (strategy v1.0 §4);
- only the Support Logs module opens a `supportlogs` session, enforced by a test;
- encrypted transport;
- encrypted storage using Azure-managed capabilities;
- no credentials stored directly in application code;
- minimal personal data;
- no support content in operational logs;
- clear separation from substantive counselling and conduct records;
- appropriate logging and audit retention.

Entra (managed identity) authentication to PostgreSQL is a possible later hardening step; the initial design uses a password-based login role per database, as strategy v0.9 does.

---

## 13. Data Model — Initial Shape

### Student

- id
- entra_object_id
- institutional_email
- display_name
- optional cluster_id (a core residential unit's ID; the membership itself is held here)
- active
- created_at
- updated_at

### Shared Roster Core / Staff Roster

Not a Support Logs table.

`residentialops` owns an extensible Residential roster framework. Its first required roster is the **Staff roster**, containing the stable identities of people eligible to act as Residential staff users. Residential appointments in `residentialops` establish roster eligibility and institutional role (for example RF/RSLM/Master). They do not themselves own Support Logs permissions.

The framework should support later roster types without forcing them into one undifferentiated schema:

- **Staff roster** — implemented first and required by Support Logs;
- **RA roster** — added later for RA Operations;
- **Student roster** — optional/TBC; students may instead continue to be resolved directly from Entra / Microsoft 365.

Support Logs refers to a staff member by the stable `residentialops` core person ID. It does not copy the staff roster into `supportlogs`. Core staff identities are retired rather than deleted so historical support references continue to resolve.

### SupportAuthorization

Owned by `supportlogs`; references a staff person from `residentialops`.

- id
- staff_id (stable `residentialops` core person ID)
- permission / role type
- active
- granted_by
- granted_at
- revoked_by
- revoked_at
- optional source / reason (for example: granted because of an active RF appointment, or at the Master's request)

The types are those in §3.5's table: frontline access, senior identifiable access, safety-flag recipient, opportunity review and Support Logs administration. These are Support Logs security objects, not residential appointments. Effective access requires an active authorization here **and** an active Staff-roster entry, with the qualifying appointment, in `residentialops` (§3.5).

This boundary is asymmetric by design: **staff identity and eligibility are shared operational data; student support membership and activity are not.**

### Encounter

- id
- student_id
- staff_id (core person ID)
- encounter_datetime
- duration_minutes
- encounter_type
- optional mode
- optional initiated_by: student / staff / other where not implicit in encounter_type
- optional planned_or_incidental, if retained after usability testing
- follow_up_needed
- optional short_note
- created_at
- updated_at

### EncounterConcern

- encounter_id
- concern_type (one row per chosen concern area; none is required)

### SafetyEscalation

One per new safety concern (§5.10).

- id
- encounter_id
- student_id
- raised_by (core person ID)
- escalation_step (configurable list) and escalated_at
- status: `open` / `acknowledged` / `closed`; `open` and `acknowledged` are both **active** (§5.10), and closing requires an outcome
- acknowledged_by, acknowledged_at (core person ID; senior staff)
- outcome (short, from a configurable list) and closed_at
- created_at, updated_at

### SupportRelationship

Represents either informal follow-up or formal assignment.

- id
- student_id
- staff_id
- relationship_type: `informal_follow_up` / `formal_assignment`
- start_date
- optional end_date
- optional review_date
- optional expected_frequency (for formal assignments and for self-set informal follow-up cadence)
- optional source
- optional operational_instruction
- safety_plan_support (formal assignments only; §5.10). When set, `source` must be the reserved Counselling source (§7.3), identified by its fixed identifier rather than its display label, and `expected_frequency` and `operational_instruction` are required, so the assignment has a cadence to monitor (§7.7) and guidance for the assigned staff member
- status
- created_by
- created_at
- updated_at

### PeerViewGrant

- id
- student_id
- grantor_staff_id (core person ID)
- viewer_staff_id (core person ID)
- scope
- granted_at
- revoked_at
- created_by

### OpportunityReviewRun

A sensitive, audited review of a defined applicant list; it is not a student case record.

- id
- initiated_by (core person ID)
- purpose / opportunity reference
- created_at

### OpportunityReviewResult

Snapshot of the explainable signal shown during a review run.

- review_run_id
- student_id or submitted institutional email where no local student exists
- review_state: `none` / `suggested` / `required`
- reason_codes shown at review time
- relevant_staff_ids shown for consultation

There is no persistent global wellness or risk score on the Student.

### AuditEvent

In `supportlogs`, on RRW's audit model (§11.3), including read events.

- id
- actor_id (core person ID)
- event_type (registered)
- entity_type
- entity_id
- event_datetime
- detail (the canonical envelope)

All support-specific entities above live in `supportlogs`; the `Staff / Eligible Staff Roster` is the explicit exception and lives in `residentialops`. `Student` and student cluster membership never appear in `residentialops`.


## 13.1 Deployment Prerequisite — Shared Residential Admin Core

Support Logs depends on the shared Residential staff roster and residential appointments in `residentialops`. Before Support Logs can be used in production, Residential Apps must therefore provide a minimal administrative surface for that shared core.

The prerequisite is deliberately small. For Support Logs it needs only to support:

- adding and maintaining eligible Residential staff;
- associating staff with their institutional / Entra identity;
- marking staff active or retired rather than deleting them;
- maintaining residential appointments such as RF, RSLM and Master; Support Logs-specific permissions are then managed separately in `supportlogs`;
- maintaining the canonical residential-unit / cluster list where that list is shared across Residential Apps.

The underlying roster design should nevertheless be **extensible from the outset**. Staff is the first roster type, but the same core should later support an **RA roster**, and should leave open the possibility of a **student roster** if Residential later decides that direct Entra lookup is insufficient. Extensibility does not mean forcing all roster types into identical fields: shared identity/lifecycle concepts should be factored once, while roster-specific attributes remain specific to each roster.

This is not a requirement to build RA Leave, RA Events, the RA roster, or a student roster before Support Logs. The intended dependency is:

> **Residential shared core + generic roster framework + Staff roster/appointment admin → Support Logs authorization + Support Logs → RA roster / broader RA Operations → possible Student roster if later required**

Support Logs should not introduce a temporary parallel staff roster merely to avoid this dependency.

---

## 14. Likely Technology Stack

### Application

- one responsive web application, with no separate mobile front end and no native mobile app initially;
- every screen remains usable on a phone, and each surface is optimized for the device its workflow is used on, per `docs/cordware_mobile_to_desktop.md`:

| Surface | UX class |
|---|---|
| Log encounter (§5) | Mobile-critical |
| My follow-ups and assignments (§6, §7) | Mobile-critical |
| Student view (§9) | Responsive general-use |
| Personal RF / RSLM dashboard (§10.1) | Responsive general-use |
| Master overview and dashboard (§10.2–10.6) | Desktop-oriented |
| Opportunity / applicant review (§10.7) | Desktop-oriented |
| Audit review (§11.3) | Desktop-oriented |
| Authorization and configuration administration (§3.3) | Desktop-oriented |

Screen size never changes authorization: a narrower layout shows the same data under the same server-side checks.

### Hosting

- the shared Cordware App Service; Support Logs is a pillar of Residential Apps at `/residentialapps`.

### Application stack

- FastAPI, server-rendered Jinja templates and SQLAlchemy 2.x, following RRW's three-layer split and UI conventions; no frontend framework.

### Authentication

- institutional Microsoft Entra ID through Easy Auth, interpreted by Cordware.

### Student Lookup

- Microsoft Graph directory search, delegated, as the signed-in staff member (§4.1); a local stand-in on localhost and in tests (§4.6).

### Database

- PostgreSQL, the `supportlogs` database on the shared server, with its own Alembic history; a local SQLite file by default for development, in-memory SQLite in tests, and Postgres round trips in CI.

### Authorisation

Application-level role and record access controls should enforce:

- staff visibility of their own logs and support relationships;
- senior authorised cross-staff oversight;
- administrator permissions.

Database-level row security may be added if useful but should not replace application-layer authorisation.

### Analytics

For v1:

- built-in application queries and lightweight charts, rendered server-side or as inline SVG under RRW's UI conventions, with no charting library.

Power BI is optional later if richer reporting becomes necessary.

---

## 15. Out of Scope for v1

The following are explicitly out of scope unless later approved:

- full case management;
- counselling notes;
- conduct investigation records;
- diagnosis or clinical categorisation;
- integration with the official Student Information System;
- automated decision-making on student risk;
- numeric or composite wellness/risk scoring;
- automated suitability, eligibility or participation decisions for opportunities;
- using historical support data as a permanent suitability marker;
- staff performance scoring;
- complex workflow engines;
- native mobile applications;
- comprehensive student roster management;
- email or Teams reminders (reminders are in-app only in v1, §17).

---

## 16. Key UX Target

The system should be designed around the assumption that staff will use it only if logging remains extremely lightweight.

The personal follow-up / check-in dashboard should be responsive and practical on a phone, while the Master's comparative dashboard may remain desktop-oriented.

For a routine repeat encounter, the target interaction is:

> Search familiar student → select duration → select encounter type → submit

Everything else should be optional or automatically derived wherever possible.

---

## 17. Open Design Questions

Answered on 2026-10-24:

- **Directory read granted?** It is a deployment prerequisite (delegated `User.ReadBasic.All`, §4.1), with Easy Auth's Graph credential; the application side needs a live check.

Answered on 2026-10-22:

- **Senior access audited?** Yes: in Support Logs every read of identifiable data is an audited action (§11.3).
- **Reminders in v1?** In-app only. Due-soon and overdue states are computed when a page loads (§7.7, §10.6); nothing is sent by email or Teams, and there is no scheduler.
- **Where cluster membership lives:** in `supportlogs`; the cluster list itself may be shared (§10.5).
- **Concern areas:** a compressed, broad list, optional and multi-select (§5.7).
- **Suicidal ideation and other safety concerns:** a separate flag with escalation, plus managed safety support as a formal assignment (§5.10).

Still open:

1. How is students' cluster membership supplied: entered manually, imported periodically, or inferred from another institutional source?
2. What exact encounter-type list is useful without creating unnecessary bureaucracy?
3. How long should encounter and assignment records be retained? This is strategy v1.0 §8's open item on `supportlogs` retention, backup and export.
4. Which senior roles should have identifiable cross-staff access?
5. Should staff be able to see only their own encounter details even when another staff member is also formally assigned to the same student?
6. What threshold, if any, should mark a formal assignment due-soon or overdue?
7. The crisis protocol shown in the form (§5.10): its contacts, order and wording, from the institution's existing protocol.
8. Who should hold the *safety-flag recipient* authorization (§3.5), and is there a duty rota?
9. Once the email mechanism is settled, should an open safety flag also email those senior staff?
10. What exact scope should a peer-view grant have: all of the grantor's records for one student, selected records, or another bounded unit?
11. May senior staff create/revoke peer-view grants on behalf of frontline staff, or only the record owner?
12. Which delegates may run opportunity reviews, and what institutional purposes qualify?
13. What exact rule thresholds separate no signal, review suggested and review required?
14. How far back should recent-activity rules look, and how should older activity decay?
15. Should "planned vs incidental" remain a structured encounter field after usability testing, or is it redundant with encounter type and follow-up?
16. How long should opportunity-review snapshots and their reason codes be retained?

---

## 18. Changes from v0.2

v0.3 (22 October 2026) refines the functional model around the actual users and a new sensitive review use case:

- **Primary user clarified:** RFs and RSLMs are one frontline functional role, and the application is designed around the minimum encounter-logging practice expected of them (§2, §3.1).
- **Private by default, with peer viewing:** frontline staff do not see one another's records unless an explicit, revocable, audited peer-view grant applies (§3.1, §11.1, §13).
- **Master/delegate role clarified:** the Master's main work is dashboarding, workload/resource checking, trends, assignments and authorised drill-down; delegates may receive narrower rights (§3.2).
- **Personal RF/RSLM dashboard added:** frontline staff get a self-management dashboard for active follow-ups, formal and self-set check-in schedules, due/overdue contacts, recent activity and their own support workload (§3.1, §10.1).
- **Student is a data subject, not a user:** authorised users can nevertheless assemble a student-centred view of the records they may see, without creating a formal case file (§3.5, §4.5, §9).
- **Opportunity / applicant review added:** an authorised reviewer can check a list of student applicants and identify which ones warrant consultation with the relevant RF/RSLM before Residential gives feedback (§3.2.1, §10.7).
- **No wellness score and no automated suitability decision:** the system produces only explainable review states and reason categories; the substantive decision remains human (§2, §10.7–10.8, §15).
- **Encounter signal requirements refined:** encounter type, concern areas, follow-up need, support relationships, safety status, staff involvement and recency/pattern are primary signals; raw counts and duration are secondary (§5.4, §5.11).
- **Review signals are rule-based and transparent:** normally computed on demand; consequential review runs preserve the result and reasons shown at the time (§10.8, §13).
- **Audit expanded:** peer-view grants and opportunity-review runs are auditable sensitive actions (§11.3).
- **Audit ownership clarified:** each database audits the security objects it owns; `residentialops` audits roster/appointment changes, while `supportlogs` audits Support Logs authorization and student-specific grants (§11.3).
- **Data model extended:** encounter signal fields, `PeerViewGrant`, `OpportunityReviewRun` and `OpportunityReviewResult`; no persistent student wellness/risk score (§13).
- **Appointments are not permissions** (author, same day): Support Logs access needs an active Staff-roster entry, with the qualifying appointment, in `residentialops` **and** an explicit Support Logs authorization in `supportlogs`, checked on every request; appointments make staff eligible, administrators grant; lapsed eligibility stops access at once (§3.5, §13). Safety-flag recipients become an authorization type (§5.10), and fake roles seed both layers (§3.6).
- **Classified by device (author, 2026-10-23):** each surface carries its mobile-to-desktop UX class, replacing "mobile-friendly first" (§14); the people supported are called students throughout.
- **Shared staff boundary clarified:** the canonical Staff roster and residential appointments live in `residentialops`; Support Logs-specific authorization lives in `supportlogs` and references staff by stable core person ID (§1.1, §3.5, §11.3, §12, §13).
