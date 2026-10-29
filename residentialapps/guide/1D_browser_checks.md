# 1D browser checks: Support Logs screens

A step-by-step walk through every Support Logs screen built by segment 1D
item 1 (`residentialapps/guide/segment_1D_support_logs.md`, rungs 1–6), for
the author's review before item 1 is approved. The tests already check what
each page contains. These steps check what only a browser shows: layout at
phone and desktop widths, the scripts' behavior, and whether the screens
read right. Tick a row once it is checked. A row that needs a change becomes
a rung 7+ slice. Delete this file when item 1 closes.

## 0. Start the app (PowerShell)

From the repository root, with the virtualenv set up once as in
`docs/local_setup.md` §G:

```powershell
.\.venv\Scripts\Activate.ps1
git pull
pip install -e ".[dev]"            # only if dependencies changed

# Fake auth for this shell only (overrides .env); the host refuses it
# outside APP_ENV=local, and the sample pages answer only on a local run.
$env:APP_ENV = "local"
$env:ALLOW_FAKE_AUTH = "true"
$env:FAKE_AUTH_EMAIL = "operator@example.edu"
$env:FAKE_AUTH_NAME = "Local Operator"
Remove-Item Env:CORDWARE_APPS -ErrorAction SilentlyContinue   # mount every application

uvicorn cordware.main:app --reload
```

Open <http://127.0.0.1:8000/supportlogs/>.

- The fake-auth account only gets you past sign-in. Who a page is drawn for
  is the **sample viewer**, chosen on the **Sample viewer** card under each
  title (`?as=` in the address bar).
- To check a page at phone width, open DevTools (F12), toggle the device
  toolbar (Ctrl+Shift+M) and pick a 390 px phone. Check 360 px too.
- Check dark mode with the Light/Dark toggle at the top right.

To stop the app, press Ctrl+C. To clear the fake-auth settings, close the
shell or run
`Remove-Item Env:ALLOW_FAKE_AUTH, Env:FAKE_AUTH_EMAIL, Env:FAKE_AUTH_NAME, Env:APP_ENV`.

| Viewer | Holds | Lands on |
|---|---|---|
| Daniel Koh | Frontline | Home (dashboard) |
| Priya Raman | Frontline, safety-flag recipient | Home, with every active flag |
| Sam Lee | Senior identifiable, recipient | Overview |
| Hui Min Goh | Recipient only | Home, flags only |
| Marcus Tan | Consultation check | Consultation check |
| Kenneth Lau | Other Staff view, aggregate | Overview, counts only |
| Siti Rahman | Other Staff view, identifiable | Overview, read-only |
| Nadia Hassan | Consultation check, identifiable view | Home listing both |
| Rachel Yeo | Sys admin | Sys admin › Access |
| Platform super-admin | Super-admin | Sys admin › Access |
| Wei Jie Ong | No grant | the 403 page |

## 1. Chrome and Home

- [ ] **Teal throughout.** The top bar, tabs, primary buttons and focus
  rings are teal. The favicon is a notepad on teal. Dark mode is readable.
- [ ] **No bottom bar** at 390 px. The tabs scroll sideways if they
  overflow, and the bar scrolls away with the page.
- [ ] **Tabs follow the viewer.** Switch through each viewer in the table
  above:
  - Daniel: Home, Log, Students, Plans.
  - Sam: Overview alone, with a red badge **1**.
  - Hui Min: Home alone.
  - Nadia: Home, Overview, Consultation check.
  - Rachel: Access, Configuration, Clusters, Audit log.
- [ ] **The switcher** (top left) lists only *Support Logs* for Daniel,
  only *Sys admin* for Rachel, and *All applications* at the foot.
- [ ] **Wei Jie Ong** sees "You do not have access to this page." with no
  tabs.
- [ ] **Not registered:** open `/supportlogs/not-registered`. The fixed
  message shows, and there is no switcher menu, tabs or unit name.
- [ ] **Daniel's Home** shows, in order:
  - his flags;
  - a full-width **Log encounter**;
  - Due and overdue, each with **Log**;
  - Following;
  - Recent encounters;
  - My last 14 days.
  
  Clara Tan's row reads "Overdue 2 days".
- [ ] **Priya's Home** lists every active flag, with Unacknowledged above
  Acknowledged.
- [ ] **Hui Min's Home** holds only the flags, closed ones included.

## 2. Log encounter (phone first; check at 390 px)

- [ ] **One screen.** As Daniel, open **Log**. Student, duration and type
  fit as choice pills. A selected pill shows a ✓ and bold text, not only a
  color change.
- [ ] **Save stays disabled** until a student, a duration and a type are
  chosen.
- [ ] **Add details** unfolds on the same page:
  - Concern areas allow several choices.
  - Follow-up needed, How and Who started it each have **Clear**.
  - **Who started it?** hides when the type already says who (Student- or
    Staff-initiated conversation).
- [ ] **The note** counts down to 300 characters live, and stops there.
  The guidance text sits beside it.
- [ ] **Follow-ups follow the student.** Pick Clara Tan (on Daniel's plan)
  and the follow-up fields show her current cadence. Pick Bao Nguyen and
  they offer **Add to my follow-ups**.
- [ ] **Save** goes to the confirmation, which names what was saved and,
  for a student not on his follow-ups, offers **Add to my follow-ups**.
- [ ] **Log from Home.** Use a Due row's **Log**: the student arrives
  filled in, with **Change**.

## 3. Safety

- [ ] **Mark a safety concern** is outline red, set apart at the end of
  the Log form. Choose a student and a duration, then tap it: the Safety
  screen keeps both choices.
- [ ] **The Safety screen** has:
  - a red header;
  - the four call links first, each with its number, and all four
    reachable without scrolling at 390 × 844;
  - a "Placeholder numbers" note.
- [ ] **Save and raise safety flag** stays disabled until the student,
  duration, type and escalation step are all set. It then shows the
  confirmation with the step and time.
- [ ] **A flag's page.** As Priya, open F-01 (Elena Park): she can
  **Acknowledge**, and **Close with outcome** asks for an outcome. As
  Daniel, the flag's raiser, open the same flag: he sees its state and no
  actions.
- [ ] **The badge** on Sam's Overview tab counts the unacknowledged flags.
  A screen reader announces "unacknowledged safety flag".

## 4. Students, plans and sharing

- [ ] **Students** (as Daniel) lists his own students first, then those
  shared with him. Hana Rahim's row reads "Shared by Priya Raman".
- [ ] **A student** (Clara Tan) shows:
  - the "Opening this view is recorded" notice;
  - three tiles;
  - **Log encounter with Clara Tan**;
  - Encounters;
  - Safety flags, with closed flags and their outcome;
  - Shared with, with Revoke;
  - Following up, with a Safety-plan marker in violet.
- [ ] **Hana Rahim**, shared by Priya, says so at the top. Her encounters
  are labelled "Shared by Priya Raman".
- [ ] **My plans** with All, Overdue and This week. Formal assignments
  come first, with source and cadence.
- [ ] **A plan** (P-01) shows its facts and history. As Sam, a follow-up
  plan (P-03) offers **Convert to formal assignment**. As Siti, plans are
  read-only.
- [ ] **Share with a colleague** and **Flag for formal assignment** each
  go to their confirmation. The flag form asks for no reason.

## 5. Overview

- [ ] **As Sam:**
  - tiles;
  - Team workload, sortable, with a load note saying it is not a measure
    of performance;
  - Hotspots with a **Rising** chip on Gwyneth Low and no score anywhere;
  - Clusters;
  - Coverage;
  - Flagged for formal assignment, with Assign disabled;
  - Every plan;
  - the **Open the audit** card.
- [ ] **Sorting.** Click a column header's ↕: rows reorder. Reload: the
  sort is kept, and empty values sort last.
- [ ] **A student's history.** Click a hotspot name: the history across
  staff, with "Opening this history is recorded". Its back link returns to
  Overview, and the Overview tab stays marked.
- [ ] **The audit** (Open the audit) says reviewing it is recorded, and
  its When column sorts by date.
- [ ] **As Siti:** names show without history links. There are no flagged
  students and no audit card. Every plan is marked read-only.
- [ ] **As Kenneth:** counts only, with no student's name anywhere on the
  page (search the page with Ctrl+F for "Clara"). The note says
  "Counts only".
- [ ] **At 390 px** the tables scroll sideways inside their cards. The
  page itself never scrolls sideways.

## 6. Consultation check

- [ ] **As Marcus:**
  - the "Running a check is recorded" notice;
  - Purpose and emails fields;
  - **Fill with the sample list**;
  - Your past checks, which shows his run only. Nadia sees only hers.
- [ ] **Check the sample list.**
  - The states run strongest first. Each row shows the named reasons, whom
    to consult, and a disabled Consultation select.
  - The statement that *No consultation indicated* never means well or
    suitable sits at the top.
  - "How a state is reached" lists the rules.
- [ ] **Messy input.** Paste `Clara Tan <clara.tan@u.example.edu>`, a line
  with no address, and a typo'd address:
  - Clara reads *Consultation required*.
  - The line with no address is listed under **Not read**.
  - The typo reads "Not matched to a student".
- [ ] **A missing purpose** returns to the form with the list kept and
  "Add a purpose."
- [ ] **At 390 px** the results table scrolls inside its card.

## 7. Sys admin (desktop first; check at 1280 px, then 390 px)

- [ ] **Access, as Rachel:**
  - Lapsed grants (Jason Teo) above the table, with Revoke;
  - one row per Staff-roster member;
  - appointments as derived pills ("Residential Fellow (RF)");
  - a checkbox per grant, and Other Staff view as a select;
  - her own row marked **You**;
  - the copy saying Sys admin is read-only to her;
  - the super-admin as a note below, not a row.
- [ ] **Access, as the super-admin:** the copy says they grant and revoke
  Sys admin, and there is no **You** row.
- [ ] **Sorting Access** by Other Staff view groups Aggregate and
  Identifiable, with None last.
- [ ] **Configuration:** a grid of list cards, one column at 390 px, each
  with a disabled Edit.
- [ ] **Clusters:** names only, with Rename, Retire and Add disabled.
- [ ] **Audit log:** administrative events only. The lapse row's actor is
  "Support Logs" and its reason names Residential Operations.
- [ ] **No student anywhere** in Sys admin (Ctrl+F for "Clara" or
  "@u.example.edu").

## 8. Rulings to give while looking

Record them in the plan's open questions:

1. **Button and label roles:**
   - Mark a safety concern is outline red;
   - Save and raise safety flag is Primary on a red frame;
   - choice pills are styled radios and checkboxes;
   - status labels are sentence case.
2. **Clusters:** Precincts for now. Should Clusters' Add, Rename and Retire
   stay?
3. **Small counts on aggregate view:** suppress a cluster or colleague with
   one student?
4. **Consultation check:** an active formal assignment suggests rather
   than requires a consultation.
5. **Access:** checkboxes, or the plan's Toggle?
