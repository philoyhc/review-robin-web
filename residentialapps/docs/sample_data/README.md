# Mock rosters for browser tests

These are mock files for Example College. They are for trying the import screens by hand once segment 1B wires them, and for setting fake sign-ins locally (item 3):

- the Terms and Assignments CSVs, item 4;
- the roster CSVs, item 5.

In the error files, a refused row raises no warning, and a blank optional column (an enterprise name, a student ID) leaves the value on file as it is; a row repeating a known person's appointment and dates matches the row on file rather than adding one. These are the files' reading, for item 5 to confirm.

Every person and address is fictional; no file here is imported into production. The units are the author's hostel breakdown (2026-10-27): 3 Wings, 9 Precincts and 30 Neighborhoods across Cypress, Maple and Willow. The Notes are each Neighborhood's room unit numbers, kept as text.

The layouts follow the rulings in `residentialapps/guide/todo_master.md` (organization by units, 2026-10-27; rosters, terms and assignments, 2026-10-28):

- **The rosters hold people and their appointments only**, each row naming its appointment and its abbreviation (`Appointment`, `Abbrev`); there are no appointment types files. A roster upload appends: rows are added, and a known email given a different name, enterprise name or student ID warns before it proceeds. The Staff and RA files add the optional columns that `residentialapps/docs/residentialapps_identity.md` §5.1 allows: the enterprise-system name, and the student ID for RAs.
- **The Terms file sets out each year's terms**: `Year,Term,Name,Start,End`, up to five a year, never overlapping.
- **An Assignments file holds the area slots, one row per Neighborhood per term.** It opens with the slot's `Term`, as the Terms page names it (`AY2026-2027 Term 1`). Its grouping columns come top level first, headed `Level1.Wing`, `Level2.Precinct` and `Level3.Neighborhood`, up to `Level5`. Each header sets that level's name, and the last level is the slot. Notes come after them. After those come the slot's **Staff** and **RA** cells. They name people by roster email, several separated by `;`.

## The Unit

| Who | How many | Where |
|---|---|---|
| Master | 1 (Sam Lee) | the whole Unit |
| Residential Admin | 1 (Rachel Yeo) | the whole Unit |
| RSLM | 3 | one per Wing: Priya Raman (Cypress), Marcus Tan (Maple), Nadia Hassan (Willow), in the Staff cell of every slot in their Wing |
| RF | 9 | one per Precinct, in the Staff cell of every slot in their Precinct |
| RA | 30 | one per Neighborhood, in its slot's RA cell |

## Files and what each should do

| File | Import it… | Expect |
|---|---|---|
| `staff_roster.csv` | First | 14 staff: the Master, the Admin, 3 RSLMs, 9 RFs |
| `staff_roster_errors.csv` | After `staff_roster.csv` | Refused in preview: a duplicate email (Daniel Koh); a student appointment on the Staff roster (Ravi Kumar, Residential Assistant); a row with no email; an end date before the start. One warning: Mei Ling Tan's name and enterprise name change (Meiling Tan, TAN MEILING) |
| `ra_roster.csv` | First | 30 RAs |
| `ra_roster_errors.csv` | After `ra_roster.csv` | Refused in preview: a duplicate email (Chloe Lim); a staff appointment on the RA roster (Owen Pang, Residential Fellow); a student ID that is not nine characters; a row with no email; an end date before the start. One warning: Ethan Wong's student ID changes (A0234127C) |
| `terms.csv` | First, on Terms | Two years, AY2025-2026 and AY2026-2027, of three terms each, none overlapping. Read against 2026-10-28, the placeholders' today: three past (read-only), AY2026-2027 Term 1 current, two upcoming |
| `assignments_slots.csv` | After the terms, with New slots | The 30 slots under their Precincts and Wings, from AY2026-2027 Term 1, with Notes and no Staff or RA columns |
| `assignments.csv` | After both rosters, with New slots (or Refresh a term once the slots exist) | The same slots for AY2026-2027 Term 1, each Staff cell naming its RF and RSLM and each RA cell its RA. Each RA reports to the slot's Staff. One warning: Umairah Salleh's appointment starts 2026-08-17, 14 days into the term; her assignment stands |
| `assignments_term2.csv` | After `assignments.csv`, with Add a term | AY2026-2027 Term 2: the same slots and Staff, with Bella Koh and Cheng Hao Lin swapping Maple 03-04 and Maple 05-06, a normal cycle's RA change. With Refresh a term it is refused: Refresh takes the current term, or a future term that already has assignments (author, 2026-10-28), and Term 2 has none; with New slots it warns that Term 2 and later would be wiped |
| `assignments_errors.csv` | After both rosters, with New slots | Refused in preview, row by row: Cypress A 04-05-06 twice; Cypress A 06-07 overlapping it; a floor list with a floor missing (`Maple 03-05`); an RA (Lucas Teo) in a Staff cell; an RF (Benjamin Chua) in an RA cell; an email on no roster (zara.khoo@example.edu); a row with no Wing; a past term (AY2025-2026 Term 3); a term not set up (AY2027-2028 Term 1). One warning: Willow B 04-05-06 has no Staff |
| `quick_setup.csv` | First, on an empty Unit, in place of all the above | Every table at once: the 3 levels, the 30 slots, 14 staff and 30 RAs, the 4 staff appointments and 1 student appointment they hold, with their abbreviations, and every cell. One row per person per slot, a person's details on their first row only and their email alone after it, and a slot's levels and Notes on its first row only and its name (the Neighborhood) alone after it; the Master and the Admin, in no slot, leave the level columns empty. Its format is held for further rulings (2026-10-28) |

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
