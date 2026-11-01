# 1D browser checks: Support Logs screens

A walk through every Support Logs screen built by segment 1D item 1
(`residentialapps/guide/segment_1D_support_logs.md`, rungs 1–10), for two
uses before the design is locked in:

- **Feedback sessions** with the people who will use it: the frontline
  team first (Part A), then senior staff (Part B). Each is a set of
  everyday tasks, what should happen, and what to ask.
- **The author's checks** (Part C): chrome, widths, Sys admin, and what
  only a browser shows.

The tests already check what each page contains. A row that needs a change
becomes a follow-up rung; a ruling goes in the plan's open questions (§D).
Delete this file when item 1 closes.

## 0. Before you start

- **Start the app** with a block from `residentialapps/guide/fake_ids.md`,
  "Support Logs (1D)". Its table lists the eleven sample viewers and where
  each lands. Every page switches viewer from its **Sample viewer** card,
  at the end of the page; the **Viewing as** chip at the top jumps to it.
- **Everything is sample data.** No real student is named, nothing is
  saved, and a disabled button is one that is wired later. Say so at the
  start of a session, so nobody hunts for a bug in a placeholder.
- **Phone first.** The frontline pages are built for a phone. Show them at
  phone width: in the browser press F12, then the device toolbar, and pick
  a phone around 390 px wide. Check 360 px too.
- **The dates are fixed**: the sample's "today" is Thursday 29 October
  2026, so "Overdue" and "This week" read the same every session.

### Running a feedback session

- **Where:** on your laptop, with each tester on their own phone over the
  same Wi-Fi: start the app with `fake_ids.md`'s "Feedback session" block,
  which serves Support Logs alone and prints the address to give them.
- **Who:** two to four frontline staff (RFs and RSLMs) for Part A, about
  45 minutes; senior staff separately for Part B, about 30 minutes.
- **How:** read out the task, not the screen. Let them drive, and say as
  little as possible: where they hesitate or tap the wrong thing is the
  finding. Ask the questions after the task, not during it.
- **Record** each task's outcome in §E's table as you go: worked, where
  they hesitated, what they expected instead, what is missing.

## Part A. Frontline staff

Act as **Daniel Koh** (RF, frontline) unless a task says otherwise. Priya
Raman (RSLM) is frontline and also receives safety flags.

### A1. The start of a shift: Home

*Task: "You have a few minutes before dinner. What needs your attention?"*

- [ ] Home shows, in order: his safety flags; a full-width **Log
  encounter**; Due and overdue, each with **Log**; Following; Recent
  encounters; My last 14 days.
- [ ] Clara Tan's row reads "Overdue 2 days". *Ruling R1: sentence-case
  status labels.*
- [ ] Tabs read Home, Log, Students, Plans; there is no bottom bar, and the
  top bar scrolls away with the page.

Ask: *Is this what you would want to see first? Is anything here you
would never look at? Is anything missing (a reminder, a count, a
colleague's name)?*

### A2. Log a quick check-in

*Task: "You just had a 10-minute check-in with Clara Tan in the corridor.
Log it."*

- [ ] **Log** is one screen: student, duration and type as choice pills.
  A chosen pill shows a ✓ and bold text, not only a color. *Ruling R1:
  pills as styled radios and checkboxes.*
- [ ] **Save** stays disabled until a student, a duration and a type are
  chosen, then goes to a confirmation naming what was saved, with **Log
  another**, **Open Clara Tan** and **Home**.
- [ ] From Home, a Due row's **Log** arrives with Clara already chosen,
  with **Change**.

Ask: *How long did that take? Would you do this on your phone, straight
after the conversation? Are the durations and types the ones you would
use? Is any word unclear?*

### A3. Log with details

*Task: "This time it was 30 minutes about adjustment and sleep. Note it,
and say you will follow up weekly."*

- [ ] **Add details** unfolds on the same page: Concern areas (several
  allowed), Follow-up needed, How, Who started it, the note.
- [ ] Follow-up needed, How and Who started it each have **Clear**. **Who
  started it?** hides when the type already says who (Student- or
  Staff-initiated conversation).
- [ ] For Clara, who is on his plans, the follow-up fields show her
  current cadence.
- [ ] The note counts down to 300 characters and stops there, with the
  guidance "Brief context only…" beside it.

Ask: *Are the concern areas the right list? Is 300 characters enough, or
too much? Does the guidance make it clear what not to write? Would you
ever fill in How and Who started it?*

### A4. Someone new

*Task: "Bao Nguyen came to you for the first time. Log it, and keep in
touch with him."*

- [ ] Bao Nguyen offers **Add to my follow-ups** on the form, and again
  on the confirmation.
- [ ] "Or find a student" (disabled) says other students come from the
  directory once wired.

Ask: *How would you expect to find a student who is not on your list:
name, email, room? Is "follow-ups" the word you would use?*

### A5. A safety concern

*Task: "During a conversation with Elena Park you became worried about
her safety. Record it."*

- [ ] **Mark a safety concern** is outline red, set apart at the end of
  the Log form. Choose Elena and a duration first, then tap it: the
  Safety screen keeps both. *Ruling R1: its outline red.*
- [ ] The Safety screen has a red header and the four call links first,
  each with its number, all reachable without scrolling on a phone, and a
  "Placeholder numbers" note.
- [ ] **Save and raise safety flag** stays disabled until the student,
  duration, type and escalation step are set, then confirms with the step
  and the time. *Ruling R1: Primary on a red frame.*

Ask: *In the moment, is this the order you would want: call first,
record after? Are the escalation steps the real ones? Is anything here
you would hesitate to record?*

### A6. Receiving a safety flag (as Priya Raman)

*Task: "You are on the flag list. A colleague has raised a flag. Find it
and deal with it."*

- [ ] Priya's Home lists every active flag, Unacknowledged above
  Acknowledged.
- [ ] F-01 (Elena Park) offers **Acknowledge**, and **Close with outcome**
  asks for an outcome. As Daniel, its raiser, the same flag shows its
  state and no actions.

Ask: *Would you notice a new flag quickly enough? What would you do
next, outside the app? Are the closure outcomes right?*

### A7. Find a student and see your record

*Task: "Look up everything you have on Clara Tan."*

- [ ] **Students** lists his own students first, then those shared with
  him; Hana Rahim's row reads "Shared by Priya Raman".
- [ ] Clara's page shows the "Opening this view is recorded" notice,
  three tiles, **Log encounter with Clara Tan**, Encounters, Safety flags
  (closed ones with their outcome), Shared with (with Revoke), and
  Following up with a Safety-plan marker in violet.

Ask: *Is the "recorded" notice reassuring or off-putting? Is this the
information you would want before seeing her again?*

### A8. Your plans and follow-ups

*Task: "Which students are you meant to check in on this week? Change
Aiden Chen to fortnightly."*

- [ ] **My plans** has All, Overdue and This week. Assigned (formal
  plans, with source and cadence) comes before Following.
- [ ] Aiden Chen's follow-up (P-03) offers a cadence with **Save cadence**
  and **Stop following up**.
- [ ] Clara's formal plan (P-01) shows its facts and history and says
  "Assigned by Sam Lee; senior staff change or close it."

Ask: *Is the difference between an assigned plan and your own follow-up
clear? Are the cadences right? What should happen when a follow-up is
overdue?*

### A9. Sharing with a colleague

*Task: "Arjun Nair is covering for you next week. Let him see your
records for Clara Tan. Then see what Priya has shared with you."*

- [ ] Clara's page already lists Mei Ling Tan under Shared with, with
  Revoke. **Share with a colleague** offers the other colleagues (not Mei
  Ling, who has it already), then a confirmation.
- [ ] Hana Rahim, shared by Priya, says so at the top; her encounters
  are labelled "Shared by Priya Raman". *Ruling R5: what a share shows.*

Ask: *Would you share like this, one student at a time? Should a share
end by itself after a date? Is it clear what the colleague can and
cannot see?*

### A10. Asking for a formal plan

*Task: "You think Aiden Chen needs a formal support plan. Ask for one."*

- [ ] **Flag for formal assignment** on Aiden's page asks only for an
  optional suggested cadence, with no reason, and confirms that senior
  staff will review it.

Ask: *Is it right that the form asks for no reason? How would you tell
senior staff why?*

### A11. Your records

*Task: "Download your encounters for this term."*

- [ ] At the end of Students and of My plans, Your records is locked;
  Unlock is refused until the confirmation is ticked.
- [ ] Unlocked: the term list opens on the current term, All terms last;
  a Student box takes one of his own students as a pill; **Download CSV**
  saves a file named for the term (and the student, when one is picked),
  one row per own encounter, and no Hana Rahim, who is shared.
- [ ] **Download the template** saves the columns only. Upload and Purge
  all are disabled; Purge says nothing is deleted. *Ruling R2: Purge all's
  outline red.*
- [ ] **Lock again**, or leaving the page, locks it.

Ask: *Would you use this, and when: end of term, handing over? Is
"purge" understood as hide-and-keep?*

### A12. Anything else

Ask, after the tasks: *What would stop you using this every day? What do
you record today, anywhere, that has no place here? Which word or label
would you change?*

## Part B. Senior staff

Act as **Sam Lee** (Master: senior identifiable, safety-flag recipient)
unless a task says otherwise.

### B1. The weekly picture: Overview

*Task: "How is the team's support load, and who should we be worried
about?"*

- [ ] Overview alone in the tabs, with a red badge **1** for the
  unacknowledged flag (a screen reader hears "unacknowledged safety
  flag").
- [ ] Tiles; Team workload (sortable), with a note that load is not a
  measure of performance; Hotspots, with a **Rising** chip on Gwyneth Low
  and no score anywhere; Coverage (overdue, due this week, review due);
  Flagged for formal assignment, with Assign disabled; Every plan.

Ask: *Does Hotspots match who you would have named? Is the load weighting
fair? What is missing for a weekly meeting?*

### B2. One student across staff

*Task: "Look at everything the team has on Hana Rahim."*

- [ ] A hotspot's name opens the history across staff, with "Opening this
  history is recorded"; the back link returns to Overview, which stays
  marked.
- [ ] **Sharing** lists Priya Raman → Daniel Koh and offers Whose records
  / With / **Share on their behalf**, disabled.

Ask: *When would you open this, and would you tell the staff member? Is
sharing on someone's behalf something you would do?*

### B3. Turning a follow-up into a formal plan

*Task: "Daniel's follow-up with Aiden Chen needs to become a formal
plan."*

- [ ] P-03 offers **Convert to formal assignment**, with source, cadence,
  review date, instruction and Safety-plan support.

Ask: *Are the sources and cadences right? Who should be told when a plan
is assigned?*

### B4. Safety flags as recipient

- [ ] F-01 (Elena Park) offers **Acknowledge** and **Close with outcome**
  to Sam, as to Priya.

### B5. Oversight

- [ ] **Open the audit**: "Reviewing this log is recorded", When sorts by
  date, and reads of no one student (the audit itself, a download) show
  no student.
- [ ] **Who holds access**: a card below Hotspots names who holds Senior
  identifiable and identifiable view; **See every grant** lists every
  grant's holders and the access changes, with no button anywhere.

Ask: *Is it right that you can see who holds access but not change it?*

### B6. Records across staff

*Task: "Download Daniel's encounters for this term."*

- [ ] **Open records** is locked until the confirmation is ticked.
- [ ] Download: Encounters or Plans; a staff member's and a student's
  name or email each become a pill (empty for everyone); a term or All
  terms; each row names its staff member.
- [ ] A typo in a box (say "Daniel Kho") blocks Download CSV with a
  message rather than downloading for everyone; × on a pill brings the box
  back.
- [ ] The two templates lead with a Staff column; Upload is disabled.
- [ ] Purged records filter by staff and by student (no term) with
  **Show**; **Delete permanently** is outline red and disabled. With a
  student chosen, each purge shows that student's records of its total.

### B7. The consultation check (as Marcus Tan)

*Task: "Before nominating students for an exchange, check whether anyone
should be consulted first."*

- [ ] The "Running a check is recorded" notice, Purpose and emails,
  **Fill with the sample list**, and Your past checks (his run only; Nadia
  sees only hers).
- [ ] The result runs strongest first, each row with its named reasons,
  whom to consult and a disabled Consultation select; *No consultation
  indicated* is stated never to mean well or suitable. *Ruling R4: formal
  assignments.*
- [ ] Messy input (`Clara Tan <clara.tan@u.example.edu>`, a line with no
  address, a typo'd address): Clara reads *Consultation required*, the
  line is under **Not read**, the typo reads "Not matched to a student".
- [ ] A missing purpose returns to the form with the list kept and "Add a
  purpose."

Ask: *Would you trust "No consultation indicated"? Are the reasons ones
you would act on?*

### B8. Other staff's views

- [ ] **As Siti Rahman** (identifiable view): names without history
  links, no flagged students, no audit card, every plan read-only.
- [ ] **As Kenneth Lau** (aggregate view): counts only, no student's name
  anywhere (Ctrl+F for "Clara"), and the note says "Counts only". *Ruling
  R3: small counts.*

## Part C. The author's checks

### C1. Chrome

- [ ] **Teal throughout**: top bar, tabs, primary buttons, focus rings;
  the favicon is a log sheet on teal; dark mode is readable.
- [ ] **Tabs follow the viewer**: Hui Min Home alone; Nadia Home,
  Overview, Consultation check; Rachel Access, Configuration, Audit log.
- [ ] **The switcher** (top left) lists only *Support Logs* for Daniel,
  only *Sys admin* for Rachel, and *All applications* at the foot.
- [ ] **Wei Jie Ong** sees "You do not have access to this page." with no
  tabs. `/supportlogs/not-registered` shows the fixed message with no
  switcher, tabs or unit name.
- [ ] **Hui Min's Home** holds only the flags, closed ones included.

### C2. Tables and widths

- [ ] **Sorting**: a header's ↕ reorders rows; after a reload the sort is
  kept, and empty values sort last.
- [ ] **At 390 px** every table scrolls sideways inside its card; no page
  scrolls sideways. At 360 px no row or chip overflows.

### C3. Sys admin (desktop first; 1280 px, then 390 px)

- [ ] **Access, as Rachel** (*ruling R6: checkboxes or Toggle*): Lapsed
  grants (Jason Teo) above the table, with Revoke; one row per
  Staff-roster member; appointments as derived pills ("Residential Fellow
  (RF)"); a checkbox per grant and Other Staff view as a select; her row
  marked **You**; Sys admin read-only to her; the super-admin a note below.
- [ ] **As the super-admin**: the copy says they grant and revoke Sys
  admin, and there is no **You** row.
- [ ] **Sorting Access** by Other Staff view groups Aggregate and
  Identifiable, None last.
- [ ] **No senior warning**: Access with `&preview=no-senior` added shows
  an amber warning at the top; without it, none.
- [ ] **Configuration**: list cards, one column at 390 px, each with a
  disabled Edit; the Access card's self-grant setting unticked (*ruling
  R7: its default*).
- [ ] **Audit log**: administrative events only (the lapse row's actor is
  "Support Logs", its reason names Residential Operations); **Senior
  reads** shows Sam Lee, 3 reads, 1 download and his latest; Purged
  records shows Grace Ho's 6 encounters as a count, with no Delete.
- [ ] **No student anywhere** in Sys admin (Ctrl+F for "Clara" or
  "@u.example.edu").

## D. Rulings to give while looking

Each is marked *Ruling Rn* at the row that shows it. Record each answer in
the plan's open questions (`residentialapps/guide/segment_1D_support_logs.md`):

- **R1. Button and label roles** (open question 3; A1–A5):
  - Mark a safety concern is outline red;
  - Save and raise safety flag is Primary on a red frame;
  - choice pills are styled radios and checkboxes;
  - status labels are sentence case.
- **R2. Purge all** (A11): outline red, though a purge hides and keeps?
- **R3. Small counts on aggregate view** (B8, as Kenneth): suppress a
  colleague with one student?
- **R4. Consultation check** (B7): an active formal assignment suggests
  rather than requires a consultation.
- **R5. Peer-view scope** (A9; spec §17 Q10): a share shows the grantor's
  records for that student, encounters and plans, read-only.
- **R6. Access** (C3): checkboxes, or the plan's Toggle?
- **R7. The self-grant setting's default** (C3, Configuration's Access
  card): built off; the ruling of 2026-10-30 asked for the option but
  not its default.

The frontline sessions can also answer four of the functional spec's
§17 questions (`residentialapps/docs/resident_support_log_functional_spec_v0.3.md`):
Q2, which encounter types (A2); Q5, whether staff see only their own
encounters when a colleague is also formally assigned (A7); Q6, when a
formal assignment is due soon or overdue (A8); Q15, whether "planned vs
incidental" earns a field (A3). Record their answers beside the rulings.

Not for the browser: the crisis protocol's real contents (the
institution's).

## E. Feedback record

One row per task per session. Copy the table for each session.

| Task | Who (role) | Worked? | Hesitated at / expected instead | Missing or wrong | Change to make |
|---|---|---|---|---|---|
| A1 | | | | | |
