# 1B browser checks: Rosters and setup, Sys admin, the landing

A step-by-step walk through the Residential Operations screens built by
segment 1B item 1 (`residentialapps/guide/segment_1B_rosters_and_organization.md`):
the landing, Rosters and setup, a person's page and Sys admin. It is for the
author's review on sample data. The tests already check what each page
contains. These steps check what only a browser shows: layout, the scripts'
behavior (tick boxes and the expander, sorting, column chips, the upload
modes, gated steps) and whether the screens read right.

- Tick a row once it is checked.
- A row that needs a change becomes a follow-up slice.
- Delete this file when the screens are approved.

## 0. Before you start

- **Start the app** with a block from `residentialapps/guide/fake_ids.md`,
  "Rosters and setup, Sys admin (1B)". Each block opens the right page.
- **Rosters, setup and Sys admin have no viewer switch.** They are drawn for
  a sys admin. The landing switches viewer with its chips.
- **Sys admin is checked twice**, as a sys admin and as the super-admin:
  it is the one page the fake account changes.
- **Setup states** are previewed from the title row of every Rosters page:
  **Preview: Not started · Slots saved · Set up**.
- **Widths:** these pages are desktop-oriented. Check at 1280 px, then once
  at 390 px (§7).

## 1. The landing (`/residentialops/`)

- [ ] **Fuchsia throughout**, with a house favicon. Dark mode is readable.
- [ ] **The chips change the cards:**
  - Chloe Lim has RA Leave and RA Events "Coming later".
  - Daniel Koh's and Priya Raman's RA Leave cards open the staff side.
  - Hui Min Goh has RA Events only.
  - Rachel Yeo and Sam Lee add RA Leave admin, Rosters and setup and Sys
    admin.
- [ ] **The switcher** (top left) lists Home and the viewer's areas, with
  **All applications** at the foot.
- [ ] **Not registered** (`/residentialops/not-registered`): the fixed
  message, a static switcher, and no tabs.

## 2. Rosters home (`/rosters/`)

- [ ] **Set up:**
  - four steps with their chips;
  - step 4 reads "Filled" with "30 of 30 slots";
  - the Checks card names Umairah Salleh's short appointment and "1 staff
    and 1 RA have not signed in yet".
- [ ] **Not started:**
  - an "Example College is not set up yet" card;
  - only step 1 open, the others "Not open yet";
  - the Primary button on the first open step;
  - step 1's link goes to Terms and comes back here.
- [ ] **Slots saved:** steps open in order, and the Primary button moves to
  the next one.

## 3. Assignments (`/rosters/assignments`)

- [ ] **The term selector** is live: pick another term and press **Show
  term**.
  - A past term shows its notice.
  - **Copy from** and **Set up terms** are present.
- [ ] **Every slot card:**
  - "· 2 staff";
  - Master and Admin ticked;
  - "In every slot: Sam Lee, Rachel Yeo" as name tokens.
- [ ] **The slots table:**
  - Tick a row: the expander opens under it, reading "1 of 30 selected",
    with Edit, Retire and Delete.
  - Tick a second row: Edit fades, and the count follows.
  - Select-all ticks every row.
  - Delete asks to confirm.
- [ ] **Sorting:** sort by a header while rows are ticked.
  - The expander stays under the last-ticked row.
  - Sort cycles ↕ → ↑ → ↓ → page order.
  - Reload: the sort is kept.
- [ ] **The Notes column chip** hides the column. The choice is kept after a
  reload, and a hidden column's kept sort is dropped.
- [ ] **Upload modes:**
  - **Upload and preview** stays faded, with the tip "Choose what the
    upload does first", until a mode is ticked: New slots, Refresh a term
    or Add a term.
  - The button itself stays disabled until wiring.
- [ ] **Gated steps:** under **Not started**, the Assignments content is
  inert under "Not open yet".
- [ ] **The Levels row builder** shows + and X, both disabled.

## 4. Terms (`/rosters/assignments/terms`)

- [ ] "· 6 in 2 years".
  - AY2026-2027 Term 1 is Current: 2026-08-03 to 2027-01-10.
  - 3 terms are Past and 2 Upcoming, each with a status chip.
  - Edit appears only on terms that are not past.
- [ ] **"← Back to …"** returns to the tab you came from (Assignments or
  Home).

## 5. Staff roster and RA roster

- [ ] **Staff roster:** "15 people, 14 linked"; Grace Ho has not signed in
  yet.
- [ ] **Oversight:**
  - Sam Lee → Example College;
  - Priya Raman → Cypress;
  - Daniel Koh → Cypress A 04-12;
  - Hui Min Goh → None, which sorts last.
- [ ] **RA roster:** "30 RAs, 29 linked"; Nur Aisyah is not linked. An empty
  Neighborhood sorts last.
- [ ] **On both tables:**
  - tick boxes open the expander (End appointment);
  - column chips hide every column but Name, kept after a reload;
  - headers sort;
  - the filter bar is disabled.
- [ ] **A person's page:** click a name.
  - Chloe Lim shows Entra display name "Chloe Lim Wei Ling" and UPN
    `e0234567@u.example.edu`.
  - It also has Appointments, slot pills, Correct the roster email, and
    two history rows.
  - Reach a person's page from the roster link, not a saved address: its
    id changes each time the app starts.

## 6. Sys admin (`/sys-admin/`)

- [ ] **As Rachel Yeo** (a sys admin):
  - Sys admins lists Sam Lee and Rachel Yeo, each granted 2026-08-01;
  - Revoke is disabled;
  - "You see this read-only.";
  - the Grant select offers Priya Raman, Marcus Tan and Daniel Koh.
- [ ] **As the super-admin:** the read-only sentence is gone.
- [ ] **The audit log:**
  - 7 rows, newest first: "2026-10-26 09:42 Assignment changed … Staff: +
    Grace Ho";
  - kind chips;
  - a sortable table;
  - disabled filters and Export CSV.

## 7. At 390 px

- [ ] **Every page holds up:**
  - wide tables scroll inside their cards;
  - the page never scrolls sideways;
  - tick boxes, sort buttons and column chips keep their desktop size.

## 8. After looking

Note anything that reads wrong by page and setup state. Each one becomes a
follow-up slice. The import files in `residentialapps/docs/sample_data/`
cannot be uploaded until 1B's wiring, so uploads are not part of this walk.
