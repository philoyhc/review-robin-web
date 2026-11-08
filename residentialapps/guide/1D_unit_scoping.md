# Segment 1D: scoping Support Logs by Unit

**Opened 2026-11-08** (author: "write the Unit-scoping plan for Support
Logs"). Residential Operations is designed to scope its rosters and
records by Residential Unit; Support Logs is not. This plan settles how
Support Logs does the same, before its database exists. Read against RRW
`c053b46b1`.

## Opportunity

`residentialapps/docs/residentialapps_roster_structure.md` §4.1 requires
every roster, appointment and unit-specific record to name its
Residential Unit (`residential_unit_id`). This is what lets more than one
Unit use Residential Operations with separate permissions. Support Logs
has no such key:

- **The data model has no Unit key.** In
  `residentialapps/docs/resident_support_log_functional_spec_v0.3.md` §13,
  `SupportAuthorization` holds a staff ID and a permission type. A Student
  has an optional `cluster_id`. No encounter, plan, flag or audit row
  names a Unit. A senior identifiable grant would therefore reach every
  Unit's students.
- **The rule is known but deferred.** The roster structure doc (§5,
  §10) defers it: "reconcile future unit-scoped grants … before exposing
  multiple Units". `residentialapps/guide/todo_master.md` still lists
  multi-Unit authorization as open.
- **The screens assume one Unit.** The sample has one Unit,
  `UNIT_NAME = "Example College"`, shown only in the top line.

There is no database yet, so settling this now costs only prose and
sample data. After wiring it would be a migration of confidential
records.

## Decision

**Every Support Logs grant and every Support Logs record carries the
Unit it belongs to, and every read filters by the viewer's grants in
that Unit.** The model is the same as Residential Operations': the Unit
belongs to the grant and the record, never to the person.

- **Grants.** `SupportAuthorization` gains `residential_unit_id`.
  - A grant in Unit A gives nothing in Unit B.
  - Eligibility (§3.5) requires a Staff-roster entry and qualifying
    appointment in the same Unit.
- **Records.** Each record names its Unit, fixed at creation from the
  author's working Unit (§Semantics): encounters, plans, safety flags,
  flags for formal assignment, teams, shares, handovers, purges, the
  support-activity audit, and cluster membership.
- **Students.** A student's identity row (directory object ID, email,
  name) stays one row per person. Whether a Unit "knows" the student is
  derived from that Unit's records, so a student two Units support
  appears once to each Unit and is never joined across them.
  `cluster_id` moves to a per-Unit membership row.
- **Reads.** Every page, count, download and check filters by the Units
  in which the viewer holds the grant that page needs. Cross-Unit views
  do not exist.

**Rejected: a database per Unit.** It would give the strongest
isolation. But it multiplies migrations and Cordware deployments by the
number of Units, makes a cross-Unit handover impossible, and splits the
platform's single audit trail. A Unit key enforced in queries, and later
by row checks, is enough when every query goes through one service
layer.

**Rejected: putting the Unit on the grant only and deriving a record's
Unit from its author's appointment at read time.** Appointments end and
move. A record must keep the Unit it was made in, or a staff member's
transfer would carry their past records into the new Unit.

## Semantics

- **Working Unit.** A viewer with grants in one Unit works there and sees
  no switcher.
  - A viewer with grants in more than one Unit picks one in the area
    switcher, next to Sys admin. Each page shows one Unit at a time.
  - Log stamps the record with the working Unit.
  - The choice persists per browser and falls back to the first Unit
    held when the stored one is no longer held.
- **A student who moves Units** (proposed, Q1).
  - Records stay in the Unit that made them. The new Unit starts with
    none.
  - History crosses Units only through a handover (§11, sharing model),
    agreed by a senior in each Unit, which re-stamps the handed-over
    records.
- **A staff member who leaves a Unit.** Their grants there end with the
  appointment (eligibility, §3.5). Their records stay in that Unit, under
  the handover rules already in the sharing model.
- **Shares and teams** stay within one Unit. A share to someone with no
  frontline grant in the record's Unit is refused, saying why.
- **Safety flags** reach that Unit's recipients only. A Unit with no
  recipient warns on its Sys admin Access page, as a Unit with no senior
  does today.
- **Consultation check** (proposed, Q4).
  - It answers from the records of the Units the checker holds the grant
    in, and says which Units it covered.
  - An unmatched student and a student unknown to those Units read the
    same: *Not matched* or *No consultation indicated*, never "known
    elsewhere".
- **Workload and counts** (Staff Overview, Students Overview) are
  per-Unit. A staff member appointed in two Units has a separate row in
  each Unit's view.
- **Administration** (proposed, Q3).
  - The platform super-admin stays global and grants Support Logs Sys
    admin per Unit.
  - A Sys admin manages grants in their own Unit only.
  - Senior reads and purged counts in Sys admin's Audit log are
    per-Unit.
- **Audit.** Every audit row names its Unit, so a Unit's review never
  shows another Unit's activity, even its counts.

## Judgment calls — decided

- The Unit is stamped at creation and only a handover changes it. Edits
  never move a record between Units.
- There is no cross-Unit "all Units" view for anyone except the
  super-admin's Sys admin pages, which list Units and grants and no
  support content.
- The working Unit lives in the switcher, not in the URL. Paths stay
  Unit-free, as Residential Operations' do.

## Blast radius (measured)

Taken 2026-11-08 at `c053b46b1`.

| What | Count | Command |
|---|---|---|
| Entities in the functional spec's data model (§13) | 11 | `awk '/^## 13/,/^## 14/' residentialapps/docs/resident_support_log_functional_spec_v0.3.md \| grep -c "^### "` |
| Sample data classes that would gain a Unit | 37 | `grep -c "^class \|^@dataclass" residentialapps/supportlogs/sample_support.py` |
| Support Logs routes to scope | 33 | `grep -cE "^@router\.(get\|post)" residentialapps/supportlogs/routes_*.py` (summed) |
| Route modules resolving a viewer's grants | 14 | `grep -rlE "sample\.(holds\|viewer)\(" residentialapps/supportlogs \| wc -l` |
| Unit mentions in the roles doc | 0 | `grep -rn -i "unit" residentialapps/docs/residentialapps_roles.md \| wc -l` |
| Support Logs tests | 185 | `grep -c "def test_" residentialapps/tests/test_supportlogs*.py` (summed) |

## PR ladder

1. **This plan** (prose only).
2. **Rulings into the specs** (prose only, after Q1–Q4 are answered):
   - functional spec §3.5 and §13 (the Unit on `SupportAuthorization`
     and on every record entity; per-Unit cluster membership);
   - the roles doc (per-Unit Support Logs Sys admin);
   - the roster structure doc §5 and §10 (close the multi-Unit item);
   - `residentialapps/spec/supportlogs_ui.md` (the working Unit, and the
     per-Unit rules above);
   - `residentialapps/guide/todo_master.md` (strike the open item).

   Must not touch code.
3. **Sample screens, scaffold-first.**
   - Add a second sample Unit, "Example Hall", with its own staff,
     students and records.
   - Add a viewer holding grants in both Units.
   - Add the working-Unit switcher.
   - Scope every page, count, download and check by Unit.
   - Add tests that no page shows another Unit's student, record or
     count to a single-Unit viewer.

   Must not change any rule the sharing model fixed.
4. ~~Wiring~~: belongs to the Support Logs wiring segment (Out of scope).

## Definition of done

- `residentialapps/docs/resident_support_log_functional_spec_v0.3.md` §13
  lists `residential_unit_id` on `SupportAuthorization` and on every record
  entity.
- `residentialapps/spec/supportlogs_ui.md` states the working-Unit rule and
  the per-Unit scoping of reads, shares, flags, checks and audit.
- `residentialapps/guide/todo_master.md` no longer lists multi-Unit
  authorization as open.
- The sample's second Unit is never visible to a single-Unit viewer.
  Tests assert this on every Support Logs GET route.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 1D` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `residentialapps/guide/todo_master.md` entries deleted; plan moved to `residentialapps/guide/archive/` with segment 1D

## Open questions

All four are the author's to rule. Each has a proposed answer in
§Semantics.

1. **A student who moves Units.** Do records stay where they were made,
   crossing only by handover? Or does the student's history follow them?
2. **Staff in two Units.** Should there be one working Unit at a time with
   a switcher, as proposed? Or a merged view that labels each row's Unit?
3. **Administration.** Should Support Logs Sys admin be per Unit under a
   global super-admin, as proposed? Or global?
4. **Consultation check across Units.** Should it answer only from the
   checker's Units, as proposed? Or from every Unit, for a checker
   granted platform-wide?

## Out of scope

- **The database, migrations and row-level enforcement.** These belong
  to the Support Logs wiring segment, which follows 1B's databases
  (`residentialapps/guide/todo_master.md` ruling 13). That segment
  inherits this plan's model and adds a constraint test.
- **Residential Operations' Administrator grant across Units.** This
  also belongs to the multi-Unit item, but it is ResidentialOps' own.
  It is noted in the roster doc §10, not ruled here.
- **Students' place within a Unit** (clusters, wings). This is already
  deferred, in segment 1D's Out of scope.

## Doc impact

- `residentialapps/docs/resident_support_log_functional_spec_v0.3.md` — §3.5 eligibility in the grant's Unit; §13 `residential_unit_id` on `SupportAuthorization` and every record entity, per-Unit cluster membership (rung 2).
- `residentialapps/docs/residentialapps_roles.md` — Support Logs Sys admin per Unit under the global super-admin (rung 2).
- `residentialapps/docs/residentialapps_roster_structure.md` — §5 and §10: the multi-Unit authorization item closed for Support Logs (rung 2).
- `residentialapps/spec/supportlogs_ui.md` — the working Unit and the switcher; per-Unit reads, shares, teams, flags, checks, workload and audit (rungs 2–3).
- `residentialapps/spec/applications.md` — the switcher's place in the area menu (rung 3).
- `residentialapps/guide/todo_master.md` — strike "multi-Unit authorization" for Support Logs (rung 2).
- `residentialapps/guide/segment_1D_support_logs.md` — Status line for this plan (each rung).
