# Residential Apps: roles

**Ruled 2026-10-25** (author). Who can do what in RA Operations (`/residentialops`) and Support Logs (`/supportlogs`), read across from RRW's three system roles. The functional specs in this folder carry each pillar's role detail; where they differ from this file, this file holds until their next versions.

RRW's three nested system roles (`spec/permissions.md` §1), read across to Residential:

| RRW | `/residentialops` | `/supportlogs` |
|---|---|---|
| **Super-admin** (`SUPER_ADMIN_EMAILS`, protected) | Every residentialops Administrator right, plus granting and revoking Administrator. Decisions routing assigns to a named person (approvals, appeals, cover) stay with that person; the super-admin may only reassign them. | Administration only (`residentialapps/docs/resident_support_log_functional_spec_v0.3.md` §3.4): grants and revokes Support Logs Administrator; no support content, no support-activity audit; needs no roster entry. |
| **Admin** | **Administrator**, stored in `residentialops`: rosters (Staff, RA), appointments, units, imports, routing, and later leave corrections and reassignment; reads all operational data and its audit (holds Team Viewer implicitly); exports. | **Support Logs Administrator**, stored in `supportlogs`: grants the other authorizations; configuration, categories, the cluster list, the administrative audit. No content, and no adopt-style path into it. |
| **Operator** | No such tier. Workflow roles follow the roster, appointments and routing: RA (RA roster), first approver (RF or delegate), final approver (the Master's admin delegate), the Master (appeals), covering RA. Team Viewer is an explicit grant. | The authorization types, each an explicit grant over Staff-roster eligibility: frontline, senior identifiable, safety-flag recipient, opportunity review (spec §3.5). |

1. **Administrator is granted and revoked by the super-admin only**, in each application; Administrators manage every role below their own.
2. **No `*_EMAILS` bootstrap.** The super-admin grants the first Administrators, so a Residential deployment needs `SUPER_ADMIN_EMAILS`; locally Cordware's fake super-admin covers it.
3. **In `residentialops`, appointments and routing drive the workflow roles**; only Administrator and Team Viewer are explicit grants. Support Logs keeps "appointments are not permissions".
4. **Administrator implies Team Viewer in `residentialops`**, as RRW's sys-admin reads every session. In `supportlogs` the roles are not nested: administration grants no content.
5. **The two Administrators are separate grants**: a residentialops Administrator makes staff *eligible* (roster and appointment), only a Support Logs Administrator *authorizes* them.
6. **Carried over from RRW:** no self-action, a last-Administrator floor per application, the super-admin protected, every grant audited.
