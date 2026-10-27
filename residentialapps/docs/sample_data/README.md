# Mock rosters for browser tests

These are mock files for Example College, the Unit drawn on segment 1B's
placeholder screens (`residentialapps/residentialops/sample_data.py`). They are for
trying the import screens by hand once segment 1B wires them (the
appointment-types and structure CSVs, item 4; Staff and RA roster CSVs,
item 5), and for setting fake
sign-ins locally (item 3). Every person and address is fictional; no file
here is imported into production.

The column layouts follow the formats ruled in
`residentialapps/guide/todo_master.md` (the organization setup CSVs) and
the CSV cards on the roster pages. A roster row appoints a person to a **post**; Other Staff hold none. The Staff and RA files add the optional
columns that `residentialapps/docs/residentialapps_identity.md` §5.1
allows: the enterprise-system name, and the student ID for RAs. If item 4
or 5 rules a different layout, change these files with it.

## The Unit

One Wing (RSLM-01), three Precincts (RF-01–RF-03, with RF-04 beside RF-02) and ten Neighborhoods
(RA-01–RA-10) across two towers.

- Cypress A holds floors 04–16. Floor 16 is in no Neighborhood: it is the
  floor gap the Organization page warns about.
- Cypress B holds floors 01–16.
- RA-10 has no RA.

## Files and what each should do

| File | Import it… | Expect |
|---|---|---|
| `appointment_types.csv` | First, on an empty Unit | 6 types and the level labels Wing, Precinct, Neighborhood; Other Staff has no abbreviation, so no posts |
| `appointment_types_errors.csv` | Any time | Refused in preview: duplicate abbreviation RF; unknown type Faculty; a sixth level (`Level6.Floor`, past the five); a row with no title; two labels for one level (`Level3.Neighborhood`, `Level3.House`) |
| `structure.csv` | After `appointment_types.csv` | 1 Wing, 3 Precincts and 10 Neighborhoods, 17 posts; Precinct RF-02 holds two posts, RF-02 and RF-04; one warning: Cypress A 16 is in no Neighborhood |
| `structure_reimport_retire.csv` | After `structure.csv` | Preview: RA-10's node and post to be retired (end-dated, not deleted); RA-04 and its Precinct changed (gain Cypress A 16) and RA-09 changed (gains Cypress B 15-16); the floor-gap warning clears |
| `structure_reimport_blocked.csv` | After the RA roster | Blocked: post RA-01 is left out but has a current appointment (Chloe Lim). RA-02 is also changed, gaining RA-01's floors |
| `structure_errors.csv` | After `appointment_types.csv` | Refused in preview: duplicate post RA-01; overlap on Cypress A 07–09 (RA-02 against RA-01's second row and RA-03); a non-contiguous floor list (`13-15`); unknown building Cypress Q; a row with no Dorms; RA-07, which fits no Precinct; RSLM-02 on a Precinct (Cypress B 13-14), where RSLM is not a type; an unknown level (`Level6.Room`). RA-05, RA-06 and RA-11 are refused for their own fields, not also as unparented |
| `staff_roster.csv` | After `structure.csv` | 8 staff, each on a post: the Master and Admin-01 at the Unit, RSLM-01, three RFs on RF-01–RF-03, one Other Staff with no post, and Grace Ho on RF-04, a dated second RF post beside RF-02 (2026-10-01 to 2026-12-31), so RA-04–RA-06 report to both |
| `staff_roster_errors.csv` | After `staff_roster.csv` | Flagged in preview: duplicate roster email (Daniel Koh); unknown post RF-09; unknown appointment Warden; an RSLM on a Precinct rather than a Wing; a row with no email; an end date before the start |
| `ra_roster.csv` | After `structure.csv` | 9 RAs on posts RA-01–RA-09, with reporting derived from the tree: every RF on the Precinct (RA-01–RA-03 to Daniel Koh, RA-04–RA-06 to Mei Ling Tan and Grace Ho, RA-07–RA-09 to Arjun Nair); RA-10 stays vacant |
| `ra_roster_errors.csv` | After `ra_roster.csv` | Flagged in preview: duplicate roster email (Chloe Lim); unknown post RA-11; an RF post (RF-02) on the RA roster; a student ID that is not nine characters; a second RA on a filled post (RA-04); an end date before the start |

One case sits outside the files, for the browser:

- **Sys admin.** Granted by hand by the super-admin: Sam Lee and Rachel Yeo.

## Fake sign-ins

`sign_ins.csv` lists, for each scenario, the `FAKE_AUTH_EMAIL`,
`FAKE_AUTH_NAME` and `FAKE_AUTH_SUPER_ADMIN` to set in `.env` (with
`ALLOW_FAKE_AUTH=true` and `APP_ENV=local`) and what should happen.
**Set `FAKE_AUTH_SUPER_ADMIN=false` for every scenario but the
super-admin's:** it defaults to `true` (`cordware/settings.py`), which makes
the fake user a platform super-admin with every sys admin right, so an RF
or an unregistered person would not be refused. Leave
`SUPER_ADMIN_EMAILS` empty, or set it to Sam Lee's address only. Restart the server between
scenarios, since fake auth is read at startup. The not-registered cases
follow `residentialapps/docs/residentialapps_identity.md` §6:

- A roster email that differs from the sign-in address does not match.
- A sys admin fixes this by correcting the roster email.
- The person's next sign-in then links them.

Until items 3–5 land, the screens show the built-in sample data whatever
is imported or signed in; these files are ready for when they do.
