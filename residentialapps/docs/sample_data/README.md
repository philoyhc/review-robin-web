# Mock rosters for browser tests

These are mock files for Example College, the Unit drawn on segment 1B's
placeholder screens (`residentialapps/ops/sample_data.py`). They are for
trying the import screens by hand once segment 1B wires them (structure
CSV, item 4; Staff and RA roster CSVs, item 5), and for setting fake
sign-ins locally (item 3). Every person and address is fictional; no file
here is imported into production.

The column layouts follow the formats ruled in
`residentialapps/guide/todo_master.md` (the organization-structure CSV) and
the CSV cards on the roster pages. The Staff and RA files add the optional
columns that `residentialapps/docs/residentialapps_identity.md` §5.1
allows: the enterprise-system name, and the student ID for RAs. If item 4
or 5 rules a different layout, change these files with it.

## The Unit

One Wing (Cypress), three Precincts (RF1–RF3) and ten Neighborhoods
(RA1–RA10) across two towers.

- Cypress A holds floors 04–16. Floor 16 is in no Neighborhood: it is the
  floor gap the Organization page warns about.
- Cypress B holds floors 01–16.
- RA10 has no RA.

## Files and what each should do

| File | Import it… | Expect |
|---|---|---|
| `structure.csv` | First, on an empty Unit | 10 Neighborhoods, 3 Precincts, 1 Wing created; one warning: Cypress A 16 is in no Neighborhood |
| `structure_reimport_retire.csv` | After `structure.csv` | Preview: RA10 to be retired (end-dated, not deleted); RA4 changed (gains Cypress A 16) and RA9 changed (gains Cypress B 15-16); the floor-gap warning clears |
| `structure_reimport_blocked.csv` | After the RA roster | Blocked: RA1 is left out but has a current appointment (Chloe Lim). RA2 is also changed, gaining RA1's floors |
| `structure_errors.csv` | Any time | Refused in preview: duplicate code RA1; overlap on Cypress A 09 (RA1/RA3 rows); a non-contiguous floor list (`13-15`); unknown building Cypress Q; a row with no floors; a row with no Precinct |
| `staff_roster.csv` | After `structure.csv` | 8 staff: Master and admin at the Unit, the RSLM at Cypress, three RFs at RF1–RF3, one Other Staff with no node, and Grace Ho as a dated second RF at RF2 (2026-10-01 to 2026-12-31) |
| `staff_roster_errors.csv` | After `staff_roster.csv` | Flagged in preview: duplicate roster email (Daniel Koh); unknown node RF9; unknown appointment Warden; an RSLM on a Precinct rather than a Wing; a row with no email; an end date before the start |
| `ra_roster.csv` | After `structure.csv` | 9 RAs on RA1–RA9, with reporting derived from the tree (RA1–RA3 to Daniel Koh, RA4–RA6 to Mei Ling Tan, RA7–RA9 to Arjun Nair); RA10 stays vacant |
| `ra_roster_errors.csv` | After `ra_roster.csv` | Flagged in preview: duplicate roster email (Chloe Lim); unknown Neighborhood RA11; a Precinct code (RF2) where a Neighborhood belongs; a student ID that is not nine characters; a second RA on an occupied Neighborhood (RA4); an end date before the start |

Two cases that sit outside the files, for the browser:

- **Dated backup reporting.** Set by hand on the RA roster: RA5 (Jia Hui
  Ong) reports to Grace Ho until 2026-12-31. The roster shows the backup
  beside the derived RF, Mei Ling Tan.
- **Sys admin.** Granted by hand by the super-admin: Sam Lee and Rachel Yeo.

## Fake sign-ins

`sign_ins.csv` lists, for each scenario, the `FAKE_AUTH_EMAIL` and
`FAKE_AUTH_NAME` to set in `.env` (with `ALLOW_FAKE_AUTH=true` and
`APP_ENV=local`) and what should happen. Restart the server between
scenarios, since fake auth is read at startup. The not-registered cases
follow `residentialapps/docs/residentialapps_identity.md` §6:

- A roster email that differs from the sign-in address does not match.
- A sys admin fixes this by correcting the roster email.
- The person's next sign-in then links them.

Until items 3–5 land, the screens show the built-in sample data whatever
is imported or signed in; these files are ready for when they do.
