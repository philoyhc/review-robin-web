# Mock rosters for browser tests

These are mock files for Example College. They are for trying the import screens by hand once segment 1B wires them, and for setting fake sign-ins locally (item 3):

- the Organization CSV, item 4;
- the appointment-type and roster CSVs, item 5.

Every person and address is fictional; no file here is imported into production. The units are the author's hostel breakdown (2026-10-27): 3 Wings, 9 Precincts and 30 Neighborhoods across Cypress, Maple and Willow. The Notes are each Neighborhood's room unit numbers, kept as text.

The layouts follow the ruling in `residentialapps/guide/todo_master.md` (organization by units, 2026-10-27):

- **The rosters hold people and their appointments only.** The Staff and RA files add the optional columns that `residentialapps/docs/residentialapps_identity.md` §5.1 allows: the enterprise-system name, and the student ID for RAs.
- **The Organization file holds the units, one row per Neighborhood, top level first.** A person column is headed by the level its cell sits on and the appointment it takes (`Precinct.RF`), and names people by roster email.

## The Unit

| Who | How many | Where |
|---|---|---|
| Master | 1 (Sam Lee) | the whole Unit |
| Residential Admin | 1 (Rachel Yeo) | the whole Unit |
| RSLM | 3 | one per Wing: Priya Raman (Cypress), Marcus Tan (Maple), Nadia Hassan (Willow) |
| RF | 9 | one per Precinct |
| RA | 30 | one per Neighborhood |

## Files and what each should do

| File | Import it… | Expect |
|---|---|---|
| `staff_appointment_types.csv` | First, on the Staff roster | 5 types; Other Staff has no abbreviation |
| `student_appointment_types.csv` | First, on the RA roster | 1 type, Residential Assistant (RA) |
| `staff_roster.csv` | After its types | 14 staff: the Master, the Admin, 3 RSLMs, 9 RFs |
| `staff_roster_errors.csv` | After `staff_roster.csv` | Refused in preview: a duplicate email (Daniel Koh); an unknown appointment (Warden); a student appointment on the Staff roster (Ravi Kumar, Residential Assistant); a row with no email; an end date before the start |
| `ra_roster.csv` | After its types | 30 RAs |
| `ra_roster_errors.csv` | After `ra_roster.csv` | Refused in preview: a duplicate email (Chloe Lim); a staff appointment on the RA roster (Owen Pang, Residential Fellow); a student ID that is not nine characters; a row with no email; an end date before the start |
| `organization_units.csv` | Any time | The 30 Neighborhoods under their Precincts and Wings, with Notes and every person cell empty |
| `organization.csv` | After both rosters | The same units with every cell filled: an RSLM per Wing, an RF per Precinct, an RA per Neighborhood. Each RA reports to their Precinct's RF |
| `organization_errors.csv` | After both rosters | Refused in preview, row by row: Cypress A 04-05-06 twice; Cypress A 06-07 overlapping it; two different RFs for Cypress A 13-20; a floor list with a floor missing (`Maple 03-05`); an RA (Lucas Teo) in an RF cell; an email on no roster (zara.khoo@example.edu); a row with no Wing. One warning: Willow B 04-12 has no RF, so its RA reports to the Willow RSLM |

One case sits outside the files, for the browser:

- **Sys admin.** Granted by hand by the super-admin: Sam Lee and Rachel Yeo.

## Fake sign-ins

`sign_ins.csv` lists, for each scenario, the `FAKE_AUTH_EMAIL`, `FAKE_AUTH_NAME` and `FAKE_AUTH_SUPER_ADMIN` to set in `.env`, and what should happen. Set `ALLOW_FAKE_AUTH=true` and `APP_ENV=local` as well.

**Set `FAKE_AUTH_SUPER_ADMIN=false` for every scenario but the super-admin's.** It defaults to `true` (`cordware/settings.py`), which makes the fake user a platform super-admin with every sys admin right. With it left on, an RF or an unregistered person would not be refused.

Leave `SUPER_ADMIN_EMAILS` empty, or set it to Sam Lee's address only. Restart the server between scenarios, since fake auth is read at startup.

The not-registered cases follow `residentialapps/docs/residentialapps_identity.md` §6:

- A roster email that differs from the sign-in address does not match.
- A sys admin fixes this by correcting the roster email.
- The person's next sign-in then links them.

Until items 3–5 land, the screens show the built-in sample data whatever is imported or signed in; these files are ready for when they do.
