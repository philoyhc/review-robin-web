# Residential Apps: roles

**Ruled 2026-10-25** (author). Who can do what in Residential Operations (`/residentialops`) and Support Logs (`/supportlogs`), read across from RRW's three system roles. The functional specs in this folder carry each pillar's role detail; where they differ from this file, this file holds until their next versions.

**Terms (author, 2026-10-26).** In Residential, **sys admin** is the system role (granted in the application, below); **admin** is the real-life appointment, the Master's admin delegate. The two are never interchangeable: an admin appointment opens no setup page, and a sys admin need hold no appointment.

RRW's three nested system roles (`spec/permissions.md` §1), read across to Residential:

| RRW | `/residentialops` | `/supportlogs` |
|---|---|---|
| **Super-admin** (`SUPER_ADMIN_EMAILS`, protected) | Every residentialops sys admin right, plus granting and revoking sys admin. Decisions routing assigns to a named person (approvals, appeals, cover) stay with that person; the super-admin may only reassign them. | Administration only (`residentialapps/docs/resident_support_log_functional_spec_v0.3.md` §3.4): grants and revokes Support Logs sys admin; no support content, no support-activity audit; needs no roster entry. |
| **Admin** | **Sys admin**, stored in `residentialops`: rosters (Staff, RA), appointments, units, imports, routing, and later leave corrections and reassignment; reads all operational data and its audit; exports. | **Support Logs sys admin**, stored in `supportlogs`: grants the other authorizations; configuration, categories, the cluster list, the administrative audit. No content, and no adopt-style path into it. |
| **Operator** | No such tier. Workflow roles follow the roster, appointments and routing: RA (RA roster), first approver (by the Leave policy, typically the slot's RF, or a delegate; none if the policy needs none), final approver (by the Leave policy, typically the Master's admin delegate), the Master (appeals), covering RA. Every linked Staff-roster member also has the read-only operational leave view (who is away, who covers whom); there is no Team Viewer grant (author, 2026-10-28). | The authorization types, each an explicit grant over Staff-roster eligibility (every Staff-roster member is eligible, author, 2026-10-28): frontline, senior identifiable, safety-flag recipient, opportunity review (spec §3.5, superseded in part on eligibility). |

1. **Sys admin is granted and revoked by the super-admin only**, in each application; sys admins manage every role below their own.
2. **No `*_EMAILS` bootstrap.** The super-admin grants the first sys admins, so a Residential deployment needs `SUPER_ADMIN_EMAILS`; locally Cordware's fake super-admin covers it.
3. **In `residentialops`, appointments and routing drive the workflow roles**; sys admin is the only explicit grant (author, 2026-10-28: Team Viewer retired, a staff account being a staff account). Support Logs keeps "appointments are not permissions".
4. **Sys admin reads all operational data in `residentialops`**, as RRW's sys-admin reads every session. In `supportlogs` the roles are not nested: administration grants no content.
5. **The two sys admins are separate grants**: a residentialops sys admin makes staff *eligible* (the Staff-roster entry), only a Support Logs sys admin *authorizes* them.
6. **Carried over from RRW:** no self-action, a last-sys-admin floor per application, the super-admin protected, every grant audited.
7. **Rosters and setup open to sys admin only** (author, 2026-10-26), which the super-admin normally grants to the Master and the admin. An appointment alone opens nothing in setup.
8. **Other Staff view in Support Logs** (author, 2026-10-26): any active Staff-roster entry may be granted view access, its scope chosen per grant: *aggregate* (the dashboard's counts, no student named) or *identifiable* (dashboard drill-down and plans, read-only). It is a fifth authorization type beside spec §3.5's four; every identifiable view is audited as the spec's are.
9. **Each application keeps its own access** (author, 2026-10-28). Support Logs reads the Staff roster to know who is eligible, and every Staff-roster member is; its grants are made and shown in Support Logs only. Residential Operations shows no other application's access: the Staff roster has no Access column, and sys admins are listed on its Sys admin page.

Which pages each role reaches: `residentialapps/spec/applications.md` "Pages".
