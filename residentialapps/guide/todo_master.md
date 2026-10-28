# Residential Apps — open work

**Opened 2026-10-25** (author). Residential's own to-do: what is ruled, what it depends on from the Cordware deployment strategy (v1.0, held privately with the deployment), and what is still to decide or revise. RRW's `guide/todo_master.md` covers RRW and the Cordware host only. Residential's functional specs and working designs are in `residentialapps/docs/`, and its contracts in `residentialapps/spec/` (ruled 2026-10-26, segment 1A); shared UX guidance is RRW's `docs/cordware_mobile_to_desktop.md`.

## Stubs

- **`tools/close_check.py` learns Residential's plans** *(filed 2026-10-26, at 1A's close)*: it finds a plan only in RRW's `guide/` and `guide/archive/`, so 1A's close was checked by hand. Searching `residentialapps/guide/` and its `archive/` too lets 1B close with the tool. One `tools/` PR with tests, before 1B closes.

## Rulings (author, 2026-10-25)

1. **One package, two applications.** One `residentialapps/` package (`core/`, `leave/`, `events/`, `supportlogs/`, `web/`), mounted as two applications: **Residential Operations at `/residentialops`** and **Support Logs at `/supportlogs`**, each with its own factory, landing-page entry, health path (`/residentialops/health`, `/supportlogs/health`), database and permissions. **Nothing is mounted at `/residentialapps`**, which names only the package. The two may share code; neither imports the other's routes.
2. **The shared core's admin** (Staff and RA rosters, appointments, units) lives under `/residentialops`, beside the core's own database. Support Logs only reads it.
3. **No neutral Residential screens.** Cordware's landing page lists both applications; the neutral sign-in landing and switcher in `residentialapps/docs/support_logs_ui_spec_v0.1.md` are dropped.
4. **Database URLs per mount.** `/residentialops` needs `RES_OPS_DATABASE_URL` only. `/supportlogs` needs both: it reads `residentialops` through the shared core as `residentialops_app`, and it is the only code that opens a `supportlogs` session.
5. **Each application runs with Cordware alone.** `CORDWARE_APPS=supportlogs` and `CORDWARE_APPS=residentialops` each start and work, locally and in CI.
6. **Registry entries** `residentialops` and `supportlogs`; logger prefixes `residentialapps.residentialops` (`residentialapps.ops` until the package rename of 2026-10-27, author) and `residentialapps.supportlogs`, neither nested in the other; lifespan state keys prefixed per application.
7. **Import boundaries** in RRW's existing `cordware/tests/test_import_boundary.py`, extended: neither application imports the other's routes; Leave and Events stay apart; only Support Logs opens `supportlogs`.
8. **Fake roles** use one `RES_` prefix, over a role list reconciled across both functional specs (below), written in the first segment plan.
9. **Alembic:** one `alembic.ini`, two histories (`residentialapps/alembic/residentialops/`, `residentialapps/alembic/supportlogs/`). The core's first migration lands in the scaffold segment.
10. **Stale text:** the deployment strategy and RRW's `guide/todo_master.md` are corrected now; the functional specs carry a banner and are revised at their next version.
11. **Segment shape** (sequence revised the same day): first, Residential Operations' rosters: the scaffold (package, both mounts, CI with both databases) and the core's admin under `/residentialops` for the Staff and RA rosters, appointments and units; then Support Logs; then RA Leave, which adds cycles and leave on the finished core; then RA Events. The RA Events spec is written before RA Leave is built. Step 1 is planned as segments 1A, the package and mounts (closed 2026-10-26, `residentialapps/guide/archive/segment_1A_package_and_mounts.md`), and 1B, the admin screens and their wiring (`residentialapps/guide/segment_1B_rosters_and_organization.md`).
13. **Sequence revised** (author, 2026-10-27), superseding ruling 11's order: **Residential Operations: RA Leave**, then **Support Logs**, then **Residential Operations: RA Events**. RA Leave goes first because it is the best understood of the three, so it is where Residential's UX conventions are firmed up. Segment 1B pauses after item 1 (the core's screens, built); RA Leave's placeholder screens come next (segment 1C, `residentialapps/guide/segment_1C_ra_leave.md`), then the core's wiring (1B items 2–5: databases, identity, organization, rosters) with RA Leave on top of it. The RA Events spec is still written before RA Events is built.
12. **Rename** (author, 2026-10-26): the application at `/residentialops` is **Residential Operations**, formerly RA Operations. The name was replaced wherever it appeared, these rulings included; mount, package, database and route names are unchanged.

## Roles

Ruled 2026-10-25: `residentialapps/docs/residentialapps_roles.md`.

## What Residential takes from the deployment strategy

- **Built here from scratch**, in this public repository, imported into production as allowlisted runtime code (its `spec/`, `docs/`, `guide/` and tests are not imported).
- **Every RRW baseline item applies:** runs with Cordware alone, on localhost with fake roles; its own tests and CI; mount-aware URLs with a leak test and a GET crawl; RRW's practice (plan in, spec out; maker ≠ checker).
- **Import boundary:** `residentialapps` never imports `app` (RRW), and `app` and `cordware` never import `residentialapps`.
- **Databases:** `residentialops` (core, Leave, Events, their permissions and audit, the email outbox; module table prefixes `core_`, `leave_`, `events_`) and `supportlogs` (students, encounters, follow-ups, assignments, safety records, review results, authorizations, peer-view grants, their audit). Runtime roles `residentialops_app` and `supportlogs_app` hold DML only; migrations run as the owner; `PUBLIC` holds no `CONNECT` or `TEMPORARY`. Cross-database references use stable IDs, never deleted, checked by a test. Locally `./residentialops.db` and `./supportlogs.db`; CI round-trips both histories on Postgres with two Residential-only databases.
- **Identity** comes from Cordware (email, display name, Entra object ID). Residential maps it to its own people by email and records the object ID at first sign-in. Appointments are not permissions. Support Logs needs an active Staff-roster entry **and** an active Support Logs authorization, both checked on every request; RAs never see Support Logs. The platform super-admin administers Residential, but in Support Logs holds administration only (no support content or support-activity audit), and named decisions stay with the named person.
- **Presentation:** each application its own name, entry point, navigation and accent (Support Logs teal `#0f766e`, Residential Operations fuchsia `#a21caf`, RRW blue), on RRW's design system; server-rendered, no frontend framework; each surface classed by device (`docs/cordware_mobile_to_desktop.md`).
- **Email:** RA Leave sends as the actor with delegated `Mail.Send` through an outbox in `residentialops`; Support Logs v1 sends no email. Directory lookup uses delegated `User.ReadBasic.All`. Both grants are deployment prerequisites.
- **Audit:** business actions only, each pillar's in its own database, on RRW's envelope-and-registered-types model. In Support Logs reads of identifiable data are audited, and support content never reaches operational logs.
- **Order** (ruling 13, superseding ruling 11): RA Leave's placeholder screens → the core's wiring (1B items 2–5) and RA Leave on it → Support Logs → RA Events.

## Decide before Support Logs goes live

- `supportlogs` retention, backup and export, and who may run them (`residentialapps/docs/resident_support_log_functional_spec_v0.3.md` §17 Q3, Q16).
- The policy questions in the same §17: Q4, Q8 and Q11, which bear on the authorization types.
- Core admin and Support Logs authorization admin both working.

## Reconcile in the first segment plan

- **Identity and roster structure** (2026-10-26): `residentialapps/docs/residentialapps_identity.md` §12 lists what it changes in this file, the RA Leave spec and the roles doc; `residentialapps/docs/residentialapps_roster_structure.md` §10 lists the decisions still to confirm.
- **Roster structure, ruled 2026-10-26** (author, on `residentialapps/docs/residentialapps_roster_structure.md` §10):
  1. The area an RF oversees is a **Precinct** (tentative; the doc's working name was "RF Zone"). RA **Neighborhood** stays.
  2. **Both exceptions from the start:** a Precinct may span more than one Tower (so it is a set of floor-range segments, not one range), and an RA may report to another RF for a dated period (a backup reporting assignment beside the primary one; from 2026-10-27 a backup is a dated second post, below).
  3. **Neighborhoods warn, not block:** gaps and overlaps against their Precinct are flagged for administrator review; real-world exceptions still save.
  4. **Cordware's identity gains the tenant ID and UPN** (`tid` and the UPN claim), so Residential binds on (tenant, object ID) as the identity spec says; a small Cordware change in the scaffold segment, tested in `cordware/tests`.
  - Still open: multi-Unit authorization (§10's last item), before more than one Residential Unit is exposed.
- **Organization levels, ruled 2026-10-26** (author; supersedes the roster doc's fixed Wing / Tower / RF Zone / Neighborhood, and turns rulings 1 and 2 above into configuration). After RRW's renamable roster tags (`spec/csv_contracts.md` §1a):
  1. **Three fixed level slots per Unit** (`level_1`, `level_2`, `level_3`), each with the Unit's own friendly label; Unit 1's are Wing, Precinct, Neighborhood. Code and data use the slots, never the labels, so renaming a level is a label edit. A fourth slot, if ever needed, is a migration.
  2. **One tree of organization nodes** (unit, level, parent one level up, code, name, dated), not a table per term.
  3. **Floors only on the bottom level**: a node carries one or more floor-range segments (building + floors), which is how a node spans towers; Tower is part of a segment, not a level. Higher levels cover the union of their children; gaps and overlaps warn (ruling 3 above).
  4. **Appointment type → level is configured per Unit**; Unit 1's are RSLM → level 1, RF → level 2, RA → level 3, with Master and the administrators covering the whole Unit.
  - **Amended 2026-10-27** (author, on 1B item 1's screens): a Unit has **up to five levels** below the whole Unit (slots `level_1`–`level_5`, superseding point 1's three) and **up to ten appointments**; floors sit on the lowest level. Appointments are **rows of title, abbreviation, type (Staff or Student) and level** (the whole Unit or a level), each row ending in **+** (add a row below) and **X** (remove it), after RRW's response-field rows; levels take the same rows. Every Unit starts with Master, Residential Fellow (RF), Residential Admin (the *admin* appointment, renamed on screen), Residential Assistant (RA, Student) and Other Staff; RSLM is one Unit's own, added as a row. *Type* now means Staff or Student; what point 4 calls the appointment type is the appointment's *title*. **Post codes** are the appointment type's abbreviation, a hyphen and a two-digit number (`RSLM-01`, `RF-01`, `RA-01`); the floor list a node covers is its *Dorms*. **Posts, ruled the same day:** a node is identified by its Dorms and holds one or more **posts**, each one person's appointment slot coded as the appointment type's abbreviation, a hyphen and the next free two-digit number (`Admin-01`, `RF-11`), or a numbering a setup CSV gives; the Master's single post is unnumbered. The rosters appoint people to posts, so the Unit's posts read `Master, Admin-01, Admin-02` and a Precinct may hold two RFs. An RA reports to **every** RF on its Precinct. **A backup is a second, dated post** on the same node (`RF-04` beside `RF-02` to 31 Dec), not a reporting line (author, option A); the setup CSVs below carry posts.
  5. **Reporting is derived**: an RA reports to the RF holding the parent node (to every RF on it, from 2026-10-27). Only the dated backup and temporary arrangements are stored explicitly.
  6. **CSVs carry the labels** as RRW's do (`Level1.Wing`; in the `Level` values from 2026-10-27, setup CSVs below); headcount norms (3 RFs + 1 RSLM per Wing, 3–4 RAs per RF) are per-Unit warnings, never constraints.
- **Organization setup CSVs, ruled 2026-10-27** — *superseded the same day by organization by units, below.* (Author; supersedes the 2026-10-26 structure CSV of one row per bottom-level node). A Unit's whole setup, rosters aside, uploads as two files, appointment types first:

  | File | Columns | One row per |
  |---|---|---|
  | Appointment types | `Title`, `Abbrev`, `Type` (`Staff` or `Student`), `Level` | appointment type (up to 10) |
  | Structure | `Level`, `Dorms`, `Post` | post |

  ```
  Level,Dorms,Post
  Unit,Cypress A; Cypress B,Master
  Unit,Cypress A; Cypress B,Admin-01
  Level1.Wing,Cypress A; Cypress B,RSLM-01
  Level2.Precinct,Cypress A 13-14-15; Cypress B 01-02-03-04-05-06,RF-02
  Level2.Precinct,Cypress A 13-14-15; Cypress B 01-02-03-04-05-06,RF-04
  ```

  1. **`Level` is `Unit` or a slot and its label**, `Level1.Wing` to `Level5.<label>`, as RRW's friendly labels are (`spec/csv_contracts.md` §1a): the appointment-types file sets the labels, the structure file must agree, and the export writes them back. An appointment type with no abbreviation (Other Staff) has no posts.
  2. **A node is its Level and Dorms**: rows with the same pair are one node's posts. Its parent is the one node a level up whose Dorms contain its own, so every level's Dorms are written out; a node that fits no parent, or more than one, is refused in the preview.
  3. **Dorms are a building and its floors joined by hyphens**, a building alone covering all its floors, several separated by `;` (`Cypress A 10-11-12; Cypress B 01-02`). Every floor is listed, so no gap hides in a range.
  4. **A post's abbreviation names an appointment type at that row's level**, and its number is the CSV's own or the next free one. A duplicate post is refused.
  5. **The structure file is the Unit's complete structure**, matched to what exists by post. The preview lists new, changed and to-retire nodes and posts, and floor gaps and overlaps (warnings); on confirm a missing node is end-dated, never deleted, and a post with a current appointment blocks the import until the appointment is ended or moved.
- **Setup order and inter-table rules, ruled 2026-10-27** — *superseded the same day by organization by units, below.* (Author; screens in `residentialapps/spec/residentialops_ui.md` §7). Setup runs in four steps, each open once the one before it is done: appointment types and levels, the organization tree, the Staff roster, the RA roster. A value has one home; elsewhere it is a read-only pill (§6). Across the tables:
  1. **An appointment type with posts** may be retitled freely; a new abbreviation or level is previewed with the posts it recodes, then confirmed; removing it is blocked while it has posts.
  2. **A level with nodes** cannot be removed.
  3. **A post or node someone holds** cannot be retired; the refusal names the holder and links to their roster.
  4. **A node with children** cannot be retired until they are.
  5. **Delete** is only for a row never appointed; anything with history is retired.
  6. **A post holds one person at a time**: overlapping appointments to it are refused, and a backup is a second post.
  7. **One person may hold several posts**, one Staff roster row each.
  8. **A post's roster follows its type**: Staff types on the Staff roster, Student types on the RA roster.
  9. **A Staff roster row names a Post**, or an Appointment only for a type with no posts (Other Staff); a row whose two disagree is refused.
  10. **Moving someone to another post** ends the old appointment and starts the new one on the same date, so the history keeps both.
  11. **A roster CSV is the complete roster**: a person it leaves out is end-dated, never deleted.
  12. **An RA whose Precinct has no RF in post** reports to the RSLM, and Home's Checks flags it.

- **Organization by units, ruled 2026-10-27** — *partly superseded 2026-10-28 by rosters, terms and assignments, below: appointment types, the Organization CSV and its cells.* (Author; supersedes the posts in the amendment above, the setup CSVs and the inter-table rules). Mock data: `residentialapps/docs/sample_data/` (the author's 30-Neighborhood breakdown).
  1. **The rosters hold people and appointments only.** Staff roster columns are Name, Email, Appointment, From – to, Sign-in and Access; the RA roster's the same less Access. Each roster page carries its own appointment types (Staff appointment types, Student appointment types: a title and an abbreviation, no level). There are no posts or post codes.
  2. **Organization is a list of area slots**, one row per smallest unit (a Neighborhood, one RA's charge), grouped under its Precinct and Wing for Example College. A Neighborhood is named by its floors (`Cypress A 04-05-06`), its Precinct and Wing by free text (`Cypress A 04-12`, `Cypress`). Buildings are not decomposed exhaustively: floor gaps are not checked, overlaps warn. **Notes** (a Neighborhood's room unit numbers) are kept and shown as text.
  3. **Each slot has two person cells, Staff and RA**, typeaheading current people from the Staff roster and the RA roster. Nothing about people carries a level: the operator puts the slot's RF and RSLM in its Staff cell and its RA in the RA cell. A cell takes several people, comma separated, and a person may sit in many slots.
  4. **Dates come from the roster**: a cell is undated, and a person leaves every cell when their appointment ends; a backup is a second name in a cell. The audit log keeps cell history.
  5. **Reporting follows the slot**: a slot's RAs report to its Staff. Who among them approves leave, by appointment (RF but not RSLM, say), is set on RA Leave's admin page (segment 1C). A slot with no Staff, or no RA, is flagged in Home's Checks.
  6. **Setup order**: Organization's slots; the Staff roster (its types, then people); the RA roster; then the person cells. Retiring a slot is blocked while its cells name anyone; a roster CSV is the complete roster, its omissions end-dated.
  7. **The comprehensive CSV** is one row per slot: the grouping columns top level first, headed `Level1.<label>` to at most `Level5.<label>` (`Level1.Wing,Level2.Precinct,Level3.Neighborhood`, RRW's `Slot.Label` grammar, which sets the level names; the last is the slot), then Notes, Staff and RA, people named by roster email and several separated by `;`. Loaded without Staff and RA, it sets up the slots alone.
- **CSV precedence and Quick setup, ruled 2026-10-27** — *partly superseded 2026-10-28 below: roster uploads append, and Assignments uploads take a mode; Quick setup is held for further rulings.* (Author; with organization by units above). Mock data: `residentialapps/docs/sample_data/`.
  1. **The usual order** is appointment types, then rosters, then Organization, but an upload fills in what it names and the preview lists it:
     - **A roster CSV creates the appointment types it names** that its roster lacks, title only (the abbreviation is added after). A typo shows as a new type in the preview; past ten types the import is refused; a title the other roster has warns. Imports only add types: one is removed on the types card or CSV, refused while anyone holds it.
     - **The Organization CSV's `LevelN.<label>` headers set or overwrite the levels**, renames shown in the preview; a change in depth is allowed only if every slot fits.
     - **Its Staff and RA columns are optional.** Without them the import changes the slots and leaves every cell alone; with them it replaces every cell. An email there not on its roster (Staff column, Staff roster; RA column, RA roster) is added to that roster with no appointment, shown so and flagged in Checks until one is set; an email on the other roster is refused, a person sitting on one roster at a time.
  2. **When one upload contradicts another:**
     - a roster CSV that ends someone in cells takes them out of every cell, the preview saying which ("leaves 3 slots"), and Checks flags the slots left without Staff or an RA;
     - an Organization CSV that leaves out a slot clears its cells and retires it in the same import;
     - a re-imported slot is matched by its name, the last level (`Cypress A 04-05-06`), which is unique; a move to another Precinct or Wing is a change, and a rename is made on screen.
  3. **The Quick setup CSV loads every table at once.** It is the Organization CSV with one row per person per slot: its level columns and Notes, then `Roster` (`Staff` or `RA`), `Name`, `Email`, `Appointment`, `Abbrev`, `From`, `To`, `Enterprise name` and `Student ID`. A slot repeats for each person in it and a person for each slot they sit in. **A person's details are given once**, on their first row; a later row needs only their email, which identifies them (a name alone may not), and any detail it does repeat must agree. **A slot likewise is given once**: a later row of it needs only its last level, the slot's name (`Cypress A 04-05-06`), which is unique, and any higher level or Notes it repeats must agree. Repeating whole rows stays valid; a person in no slot (the Master, the Admin) leaves the level columns empty, and a slot with nobody the person columns. One preview sets the levels, the slots, both rosters with their types and abbreviations, and the cells. Its format is the mock's (`quick_setup.csv`). The whole contract is to be written as `residentialapps/spec/organization_and_rosters.md` when items 4 and 5 implement it.
- **Rosters, terms and assignments, ruled 2026-10-28** (author; supersedes the two rulings above where they differ). Quick setup is held: its format, and how it meets terms and modes, wait on further rulings.
  1. **No appointment types tables.** A roster row carries its own `Appointment` and `Abbrev`; a roster's types are the pairs its rows hold, with no limit.
  2. **Roster uploads append**: rows are added, never removed by omission; ending or deleting an appointment is done on the page. A file giving a known email a different name, enterprise name or student ID warns, listing the changes, before it proceeds. A roster marks appointment to a role type; someone may hold an appointment with no assignment (yet). Appointments keep `From` and `To`.
  3. **Organization is renamed Assignments** (`/rosters/assignments`): who sits in which slot, for a term, as RRW's Assignments table but made by hand or upload rather than by rules. Levels stays its label editor; the slots stand from the term they are created for.
  4. **Terms** (`/rosters/assignments/terms`, a "Set up terms" button with a back link after RRW's `/guide?return_to=`): per year (`AY2026-2027`), up to five terms, each a name and start and end dates (Term 1, Sem 1 + Winter break; Term 2, Sem 2; Term 3, Summer break), across years; terms never overlap. Its CSV is `Year,Term,Name,Start,End`.
  5. **Assignments carry a Term, not dates.** The page shows one term, chosen by a selector, opening on the term today falls in (else the next). A wholly past term is read-only. "Copy from Term N" fills a term from an earlier one to edit.
  6. **Guard**: an assignee holds an appointment on the right roster. One covering the whole term qualifies; one wholly outside it does not; one covering part of it qualifies with a warning naming the gap in days ("starts 9 days into Term 1").
  7. **Assignments uploads take a mode, chosen on the upload card** and checked in the preview; every Term in the file must be defined, a wholly past one is refused, and each term in the file is checked on its own:
     - **New slots**: the file defines the slots from its first term on (earlier terms keep theirs); that term and every later one are wiped, with a warning naming them;
     - **Refresh a term**: the slots must match those on file exactly; the current term's assignments, or a future term's that already has some, are replaced, with a warning;
     - **Add a term**: the slots must match exactly; the term has no assignments yet.
  8. **Home's steps**: Setup (the levels, the slots and the terms), Staff roster, RA roster, Assignments for a term (refined the same day from five steps, Terms and Slots apart). Assignments uploads choose their mode by radio buttons.
  9. **A blank cell means what the upload's mode makes it** (ruled the same day):
     - **Roster upload** (it appends): a blank optional column (enterprise name, student ID) leaves the value on file as it is;
     - **Assignments, New slots or Refresh a term** (the file is the term's whole content): a blank Staff, RA or Notes cell is empty and replaces what was there;
     - **Assignments, Add a term** (nothing on file): a blank is empty;
     - **Terms**: every column is required; a blank is refused;
     - in every upload, a refused row raises no warning besides its refusal.
  10. **No Access column; Team Viewer retired** (ruled the same day): the Staff roster shows no access. Other applications' grants stay in them: Support Logs reads the Staff roster for eligibility (every Staff-roster member is eligible) and makes and shows its grants itself. In Residential Operations a staff account is a staff account: appointments and routing decide what each does, every linked Staff-roster member has the read-only operational leave view, and sys admin, granted by the super-admin on the Sys admin page, is the only grant (`residentialapps/docs/residentialapps_roles.md`).
- **Role names** (terms ruled 2026-10-26: *sys admin* the system role, *admin* the appointment, `residentialapps/docs/residentialapps_roles.md`): administrator is "Administrator", "System Administrator", "Leave administrator" and "Residential admin" across the specs; who administers the shared core is not named.
- **Appointments:** RF, RSLM, Master, RA, and the Master's admin delegate; a Support Logs delegate is granted at the Master's request.
- **Unit vocabulary:** unit, team, house and cluster (`cluster_id` is a core unit).
- **RA Events** has no functional spec yet.

## Revise at each spec's next version

- `residentialapps/docs/ra_leave_management_functional_spec_v0.4.md`: §2.5 classes approver actions mobile-critical, not responsive (page map, `residentialapps/spec/applications.md`, author 2026-10-26); the header and introduction ("a single application", `/residentialapps`), the implementation and Platform sections (`/residentialapps`), the open-items list, scenario Q ("Cordware + Residential Apps"); the strategy version its header cites (v0.9).
- `residentialapps/docs/resident_support_log_functional_spec_v0.3.md`: header and §1.1 (`/residentialapps`, "share one application"), §14 hosting, the v0.9 reference in §12. §3.5 gains the Other Staff view authorization (roles doc rule 8), and "Administrator" becomes *sys admin* (roles doc, "Terms").
- `residentialapps/docs/support_logs_ui_spec_v0.1.md`: whether Support Logs keeps its bottom bar (its §2 and §5) or takes Residential Operations' slim top bar (`residentialapps/spec/residentialops_ui.md` §2); §1 item 6 ("stays one Residential application"), and the neutral shared Residential screens in the colour sections (ruling 3).
