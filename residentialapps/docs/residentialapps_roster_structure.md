# Residential Apps — Roster, Appointments, and Residential Geography

**Status:** Working functional design; proposed terminology and data relationships for implementation  
**Date:** 26 October 2026  
**Proposed repository location:** `residentialapps/docs/residentialapps_roster_structure.md` in `philoyhc/review-robin-web`  
**Owner:** Residential shared core, administered through Residential Operations (`/residentialops`)

## 1. Purpose and relationship to existing specifications

This document records the intended structure of the Staff and RA rosters, real-world residential appointments, geographical oversight and reporting relationships. The design should work for the current Residential Unit and accommodate more units without redesigning the data model.

Read together with:

- `residentialapps/docs/residentialapps_identity.md` — permanent `person_id`, Entra identity binding, optional enterprise name and student ID, first-sign-in matching.
- `residentialapps/docs/residentialapps_roles.md` — **authoritative** application authorization model; this document does not override it.
- `residentialapps/guide/todo_master.md` — architectural boundaries and the sequence for implementing the shared core.

**Core distinction:** A **Person** is an individual; an **Appointment** records an institutional responsibility for a period; a **Coverage / Reporting Assignment** records where and under whom the person serves; **System Authorization** determines what the person may do in Residential Operations or Support Logs. These must not be collapsed into a single `role` column.

## 2. Terminology recommendation

Use **RF Zone** for the larger area under one RF and retain **Neighborhood** for the floors allocated to an RA.

| Term | Definition | Example |
|---|---|---|
| **Residential Unit** | A hostel under one Master and its residential team; an explicit organizational boundary for records | Unit 1 (illustrative) |
| **Wing** | A named division within a Residential Unit | Cypress, Maple, Teak |
| **Tower** | A physical building/tower within a Wing | Cypress Tower A |
| **RF Zone** | An area assigned to an RF, composed of several RA Neighborhoods, ordinarily a contiguous run of floors in one tower | Cypress A 04–12 |
| **RA Neighborhood** | A contiguous subset of floors, assigned to an RA and belonging to one RF Zone | Cypress A 04–06 |

For administrative screens, use **Zone** and **Neighborhood** once the RF/RA context is apparent; use the longer terms in specifications, imports and potentially ambiguous reports.

Alternatives considered for the larger area: **RF Sector** (unambiguous, but formal), **RF Area** (simple, but generic), **RF District** (potentially too large). Avoid **Cluster** here because that term already has uses in Support Logs and earlier Residential planning. **RF Zone** is the working recommendation, not yet a final naming ruling.

### 2.1 Hierarchy

```text
Residential Unit
└── Wing (e.g., Cypress)
    ├── Tower A
    │   ├── RF Zone: Cypress A 04–12
    │   │   ├── RA Neighborhood: Cypress A 04–06
    │   │   ├── RA Neighborhood: Cypress A 07–09
    │   │   └── RA Neighborhood: Cypress A 10–12
    │   └── Other RF Zones, where applicable
    └── Tower B (if present)
```

Each Wing currently has one or two towers, with multiple floors. An RF ordinarily oversees a geographically contiguous Zone and approximately three or four RAs. Each RA ordinarily oversees one contiguous Neighborhood wholly within the reporting RF's Zone. The number of RAs is an **operational guideline**, not a hard database constraint.

An RSLM covers an entire Wing; the RSLM is **not assigned a Zone or Neighborhood**. RSLMs can also have documented backup responsibilities for other Wings, without changing their primary Wing assignment.

## 3. Person identity: unchanged

Each Person has a permanent application-generated UUIDv4 `person_id` and, after the first matched institutional sign-in, a linked (`entra_tenant_id`, `entra_object_id`). Other person-level attributes follow `residentialapps_identity.md`:

- Entra display name and account-address fields from trusted sign-in;
- optional enterprise-system name, kept in its original form, which may differ significantly in ordering and formatting;
- optional **nine-character Student ID**, stored as a string, including any leading zeroes;
- the imported roster email, retained as an initial matching/contact attribute.

On first sign-in, Residential matches an unlinked provisional roster record **only by an unambiguous exact match** to trusted authenticated email/UPN. If there is no match, display **“You are not registered in Residential Apps. If you believe this is incorrect, please contact your Residential administrator.”** The administrator corrects the provisional roster and the person signs in again. No self-registration, fuzzy name matching, self-claim workflow or special reconciliation queue is required.

**Do not put Residential Unit, current Wing, current Neighborhood or current appointment type on the permanent Person identity record.** A person may change jobs, terms, Wings or Units over time.

## 4. Operational entities and fields

The following is a conceptual model, not a prescribed physical schema. Shared-core tables use the `core_` prefix in the `residentialops` database; identifiers below denote stable internal references, not user-facing keys.

### 4.1 ResidentialUnit

| Field | Treatment |
|---|---|
| `residential_unit_id` | Required stable key |
| `code`, `name` | Human-readable identifier and name |
| `active` | Retain retired units for historical records |

A Master is connected to a Unit through a dated **Appointment**, not through a permanent `master_name` text field. Every **roster/appointment record and unit-specific operational record** must identify its Residential Unit. Global Person identity and genuinely platform-wide entities are exceptions: the Unit belongs to an individual's **appointment**, not to the person.

### 4.2 Wing and Tower

| Entity | Essential fields |
|---|---|
| **Wing** | `wing_id`, `residential_unit_id`, `code`, `name`, active status |
| **Tower** | `tower_id`, `wing_id`, `code`, `name`, active status, available-floor configuration if maintained |

Cypress, Maple and Teak are initial Wings **within the current Unit**, not globally unique identifiers. Names and codes are scoped to the parent organization. A Wing may have one or two towers under the current operating model; do not bake that count into a permanent data constraint unless specifically required.

### 4.3 RF Zone

| Field | Treatment |
|---|---|
| `zone_id` | Stable identifier |
| `residential_unit_id` | Required, consistent with Wing |
| `wing_id`, `tower_id` | Identify location |
| `floor_start`, `floor_end` | Inclusive contiguous floor range |
| `label` | Derived or editable display label, e.g., `Cypress A 04–12` |
| `active_from`, `active_to` | Optional validity of configuration |

A Zone is a **geographical/organizational area**, not a person. RF appointments are assigned to it by dated assignment records, so an RF's successor can inherit the same Zone without rewriting its historical identity.

**Initial design assumption:** A Zone's normal geographical footprint is one contiguous floor range within one tower. If operations require one RF to cover portions of multiple towers, represent that as multiple associated coverage segments or an explicit exception rather than storing an ambiguous single range. Confirm this requirement before fixing the database schema.

### 4.4 RA Neighborhood

| Field | Treatment |
|---|---|
| `neighborhood_id` | Stable identifier |
| `residential_unit_id` | Required |
| `zone_id` | Required parent RF Zone |
| `tower_id` | Normally inherited from Zone; available for validation |
| `floor_start`, `floor_end` | Inclusive contiguous subset of the Zone |
| `label` | Derived or editable, e.g., `Cypress A 04–06` |
| `active_from`, `active_to` | Optional configuration validity |

A Neighborhood belongs to **one RF Zone at a time**. Geographic configuration and its assignment to a particular RA are separate. Neighboring RA Neighborhoods ordinarily partition their RF Zone; highlight gaps and overlaps for administrator review rather than silently adjusting them.

### 4.5 ResidentialAppointment

An Appointment is an actual residential designation held by a specific Person within a Residential Unit and term.

| Field | Treatment |
|---|---|
| `appointment_id` | Stable appointment identifier |
| `person_id` | Required Person reference |
| `residential_unit_id` | Required |
| `appointment_type` | Controlled vocabulary: `RA`, `RF`, `RSLM`, `MASTER`, `RESIDENTIAL_ADMINISTRATOR`, `MASTERS_ADMIN_DELEGATE`, and future types |
| `start_date`, `end_date` | Appointment term; end may be absent only where genuinely open-ended |
| `status` | Administrative lifecycle (e.g., planned, active, ended, cancelled) |
| `source_import_id` | Optional CSV/import provenance |

`appointment_type` is the person's **real-world appointment**, not an application-level permission. One Person may have multiple appointments across terms, types or Units. A new appointment or term does **not** create a new `person_id`.

Prefer deriving current/ended state consistently from dates and explicit cancellation status, rather than keeping contradictory free-standing flags. Preserve appointment history and record corrections in the audit trail.

### 4.6 CoverageAssignment

Links an Appointment to its physical or organizational coverage for a given period.

| Appointment | Typical assignment |
|---|---|
| **RA** | One Neighborhood; Wing and Zone derived through its parent |
| **RF** | One RF Zone; Wing derived from the Zone |
| **RSLM** | Whole Wing; no Zone or Neighborhood |
| **Master** | Whole Residential Unit |
| **Residential Administrator** | Whole Unit, unless duties are explicitly scoped otherwise |
| **Master's Administrative Delegate** | Whole Unit, with approval rights governed by actual routing |

Assignments need `assignment_id`, `appointment_id`, target type/ID, applicable dates and audit information. Avoid storing the same mutable location details independently on Person, Appointment and CoverageAssignment; the **roster UI can join and display** all relevant values as columns.

RSLM backup coverage for another Wing is a **separate dated assignment** marked `BACKUP`, linked to the same RSLM appointment; it does not create a fictitious RF Zone or imply broader Support Logs permissions.

### 4.7 ReportingAssignment

RA-to-RF reporting is an explicit dated relationship:

- `reporting_assignment_id`
- `ra_appointment_id`
- `rf_appointment_id`
- `start_date`, `end_date` where they differ from appointment terms
- optional administrative notes and audit references

Refer to the **RF appointment**, not only `person_id`, so succession, a change of Zone, and the historical chain of supervision remain meaningful. At a given moment an RA ordinarily has one reporting RF, and that RA's Neighborhood must fall inside the RF's active Zone. Reporting assignments must have overlapping valid dates and belong to the same Residential Unit.

## 5. Roles and authorization: keep separate

The Staff and RA roster screens show **real-world Appointment** only; they show no system access (author, 2026-10-28: each application shows its own grants, and Residential Operations' one grant, sys admin, is listed on its Sys admin page). Do not store one manually editable `system_role` column as a substitute for authorization.

- In **Residential Operations (`/residentialops`)**, the explicit Administrator grant (made/revoked only by the platform super-admin; Team Viewer retired 2026-10-28) remains governed by `residentialapps_roles.md`. RA, first approver, final approver, Master appeal decider and covering RA rights are determined by active appointments and named workflow/routing relationships where applicable.
- In **Support Logs (`/supportlogs`)**, an active Staff-roster entry is **eligibility only** (every Staff-roster member is eligible, author, 2026-10-28). Frontline, senior identifiable, safety-flag recipient and opportunity-review permissions remain separate explicit grants in the `supportlogs` database. A Residential Administrator or RSLM appointment does not automatically grant Support Logs access.
- **Platform super-admin** is a protected deployment role. The two application Administrator grants are distinct and retain the document's no-self-action, audit and last-Administrator protections.

The roster shows no per-application access chips (author, 2026-10-28). Authorization settings belong to their respective administration screens, not a general-purpose CSV column.

**Multiple-Unit consideration:** Unit-scoped rosters and app data are required now. The exact future scope of Administrator / Support Logs permission grants across multiple Residential Units must be reconciled with `residentialapps_roles.md` before multi-unit rollout; do not silently change its presently authoritative rules.

## 6. CSV imports and routine administrative presentation

Continue the simple agreed identity-onboarding design: provisional rosters can be imported before any individual signs in, with an empty Entra ID. The first exact-match sign-in links their existing `person_id`.

### 6.1 Conceptual Staff roster columns

| Column | Notes |
|---|---|
| Residential Unit | **Required**; resolve by approved Unit code |
| Roster email | Required for initial first-sign-in matching |
| Enterprise-system name | Optional; retain exactly as provided |
| Student ID | Optional; exactly nine characters if present |
| Appointment | RF, RSLM, Residential Administrator, Master's Admin Delegate, Master, etc. |
| Term start / end | Dates for the actual appointment |
| Wing | Required for RF / RSLM; not applicable to unit-wide appointments |
| RF Zone | Required for ordinary RF assignment; not applicable to RSLM |
| RSLM backup Wings | Optional; usually maintained through separate assignments |
| Effective system roles | **Read-only derived display**, not an imported authority |

### 6.2 Conceptual RA roster columns

| Column | Notes |
|---|---|
| Residential Unit | **Required** |
| Roster email | Required for initial first-sign-in matching |
| Enterprise-system name | Optional |
| Student ID | Optional nine-character string |
| Appointment | RA |
| Term start / end | Dates, potentially aligned to an RA cycle |
| Wing | May be derived from Neighborhood |
| Neighborhood | Required for an assigned RA; includes Tower and floor range |
| Reporting RF | Resolve to the appropriate RF **appointment**, using a stable roster reference rather than just a displayed name |
| Leave entitlement / RA cycle | Leave-owned provisioning extension where applicable, not identity fields |

Avoid treating Wing, Zone, Neighborhood and Reporting RF as uncontrolled text fields internally. A CSV may use human-readable labels, but the preview step should resolve them to the core's IDs and flag ambiguous or unknown references. Use one import-preview/confirmation operation; no elaborate identity-reconciliation workflow is needed.

### 6.3 Administrator views

The simplest usable interface is a Staff roster and an RA roster, filterable by **Residential Unit → Wing → RF Zone → Neighborhood** as applicable. Display:

- Person's default name (Entra display name once linked, otherwise enterprise name);
- appointment and term;
- Unit, geographical assignment and reporting RF;
- `Entra linked` / `Not yet linked`;
- effective system roles/authorizations as **read-only indicators**;
- actions to edit roster email, appointment, coverage, reporting and term (subject to authorization and audit).

A mismatch at sign-in requires the person to **contact the administrator**; the administrator fixes the provisional email so the person can retry. Do not add a self-claim screen, account-search wizard or pending linkage queue.

## 7. Validation and lifecycle rules

1. **Unit consistency:** Wing, Tower, Zone, Neighborhood, appointments and reporting relationships must belong to the same Residential Unit where they represent a single assignment.
2. **Range validity:** Floors are interpreted as configured numeric levels, and `floor_start <= floor_end`; the range must belong to the selected Tower.
3. **Containment:** An RA Neighborhood must be fully inside its parent RF Zone, and a reporting RA's assignment must be contained in that RF's active Zone during the relevant dates.
4. **No implicit role grants:** Importing an Appointment or CoverageAssignment does not create an app Administrator or Support Logs authorization.
5. **Date consistency:** Assignment dates must lie within/overlap the associated Appointment term appropriately; reporting periods overlap RA and RF terms.
6. **Duplicates / overlap:** Warn about overlapping active Zone or Neighborhood allocations and multiple concurrent RF assignments to the same Zone; provide deliberate override handling where real operations require exceptions.
7. **History:** Do not delete appointments, geographic assignments or Person references when someone moves, graduates or a term ends. End or supersede the relevant dated record.
8. **Identity:** Never change `person_id` because a term, email or geographical assignment changes. First-sign-in binding and conflict rules remain those in `residentialapps_identity.md`.
9. **Operational guidance:** Three or four RAs per RF, and one RSLM per Wing, are defaults to highlight in validation/reports, not irrevocable database constraints.
10. **Audit:** Record administrative edits to appointments, units, geographical assignments, reporting relationships and explicit application-grant actions under their owning applications.

## 8. Illustrative roster view

| Name | Appointment | Unit | Wing | RF Zone | RA Neighborhood | Reports to | Term |
|---|---|---|---|---|---|---|---|
| Jane Tan | RF | Unit 1 | Cypress | Cypress A 04–12 | — | — | 2026–27 |
| Benjamin Wong | RA | Unit 1 | Cypress | Cypress A 04–12 | Cypress A 04–06 | Jane Tan (RF appointment) | 2026–27 |
| Clara Lim | RA | Unit 1 | Cypress | Cypress A 04–12 | Cypress A 07–09 | Jane Tan (RF appointment) | 2026–27 |
| Farah Lee | RA | Unit 1 | Cypress | Cypress A 04–12 | Cypress A 10–12 | Jane Tan (RF appointment) | 2026–27 |
| David Ng | RSLM | Unit 1 | Cypress | — | — | — | 2026–27 |
| Elaine Lee | Master's Admin Delegate | Unit 1 | — | — | — | Master (workflow routing as assigned) | 2026–27 |

*All names, unit labels, assignments and dates above are illustrative.*

## 9. Acceptance scenarios

1. An RA imports with `person_id` generated, Unit/Neighborhood/term/Reporting RF assigned and no Entra ID; their first exact-match institutional sign-in populates the identity link without changing the RA appointment.
2. An RF with a new term retains the same `person_id` but receives a distinct Appointment and dated RF Zone assignment.
3. Multiple RAs assigned to `Cypress A 04–06`, `07–09`, and `10–12` share one RF Zone (`Cypress A 04–12`) and refer to the same reporting RF appointment.
4. An RSLM has Wing-level responsibility without a Zone or Neighborhood, and can temporarily back up another Wing by a separate assignment.
5. A Person serving in a second Residential Unit retains their `person_id`, while both appointments and their access context remain Unit-specific.
6. A changed enterprise/Entra name, roster email, or optional Student ID does not change the `person_id` or the appointment's historical identity.
7. A roster CSV containing a Wing or Neighborhood ambiguous across Units cannot accidentally attach someone to the wrong Unit.
8. A Support Logs user remains unauthorized unless explicitly granted the required Support Logs role, even after their Staff appointment is successfully imported and Entra-linked.
9. A first-login email mismatch displays the agreed not-registered message; an administrator fixes the roster address and the next matching login links the account.

## 10. Decisions still worth confirming before implementation

- **Terminology:** adopt **RF Zone** as the official name for the collection of RA Neighborhoods, or choose an alternative.
- **Geographic exception:** can an RF Zone ever span more than one Tower? This affects whether the Zone needs multiple floor-range segments.
- **Neighborhood continuity:** must RA Neighborhoods fully partition an RF Zone, or are deliberate gaps/overlaps permitted? Current proposal is to warn rather than silently prohibit exceptions.
- **Reporting exceptions:** can an RA temporarily report to another RF, and should a backup arrangement have its own dates?
- **Multi-Unit authorization:** reconcile future unit-scoped grants with existing global Administrator rules before exposing multiple Units.

These are limited policy/data-model questions. They do **not** reopen the agreed minimal Entra-first-sign-in or CSV roster-onboarding design.
