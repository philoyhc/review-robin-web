# Support Logs UI

> **Built so far:** segment 1D item 1 built every Support Logs screen on
> sample data (`residentialapps/guide/segment_1D_support_logs.md`, rungs
> 1–9). Items 2–5 wire them. This file settles the draft UI spec,
> `residentialapps/docs/support_logs_ui_spec_v0.1.md`, which is history
> from here; its open questions are answered in §8 or carried there.

The conventions every Support Logs screen follows. What it shares with
Residential Operations it cites rather than restates:
`residentialapps/spec/residentialops_ui.md` for devices and widths (§1),
button roles and touch targets (§4), sortable tables and column chips
(§6), cards, notices and phone lists (§8), and accessibility (§10). Where
both are silent, RRW's design system applies. The page map, with each
page's grant, is `residentialapps/spec/applications.md` ("Support Logs");
the styles are `residentialapps/web/templates/residential/base.html`,
Support Logs' own under `data-app="supportlogs"`.

## 1. Devices

- **The frontline's pages are mobile-critical**: Home, Log encounter,
  Safety concern, Students, a student, a plan and a safety flag
  are designed at 390 px (functional spec §14, §16).
- **The page map has no device column for Support Logs**, so this
  section gives the classes.
- **Columns** are every Residential app's
  (`residentialapps/spec/residentialops_ui.md` §1, author, 2026-11-08):
  at most three of at least 340 px, three from 1116 px wide, two from
  736 px. Sys admin is desktop-oriented, so it keeps the full width for
  its cards.
- **Overview and the Consultation check are responsive**: their tables
  scroll sideways in `.table-wrap` when their column is narrower than
  they are, on a phone and in Overview's main column below 1116 px.
- **Log's students are the viewer's favorites** (author, 2026-11-06),
  marked with a star on Students, in the order favorited, with a hint to
  mark more there and "Or find a student" for the rest. Home has no Log
  encounter button: Log in the tabs reaches it. Durations are 15, 30 and
  60+ min; the types Check-in, Welfare follow-up, Practical support and
  Other (`residentialapps/guide/1D_refinements.md`).
- **Waiting for you**, on the frontline's Home (author, 2026-11-07,
  `residentialapps/guide/1D_sharing_screens.md` rung 2): every
  agreement the sharing model asks of the staff member (a share
  offered, a team invitation, a handover, a senior's share request),
  each with Agree (Primary) and Decline (Secondary), inert until wired.
  A share, an invitation or a handover names no student until agreed to
  (author, 2026-11-07). A sys admin
  can agree for a staff member only in an emergency, or on a
  handover when they cannot be reached.
- **Teams** (sharing screens rung 5, author, 2026-11-07): a team's
  student shows on Students for each member, under a fourth filter
  choice, **Teams**, with the other members named. A student's page has a
  Team card (members, Leave the team; or Form a team), and a senior's
  view of a student has Form a team over chosen staff; inert until
  wired. A team names its student on Overview (rule 3), with a Team chip.
- **Hand over** (sharing screens rung 6, author, 2026-11-07): a card on
  a student's page, where the viewer has records of their own (all, or
  chosen encounters; To), and on a senior's view of a student (From, To, To being someone other than From:
  all of the owner's records, since a senior sees none of them, author,
  2026-11-07); Sys
  admin's Access lists **Agree on behalf** (§6). All inert until
  wired.
- **Plans and follow-ups are a filter on Students** (author, 2026-11-07):
  My students shows All, Plans, Following or Teams, the last choice kept in the
  browser; each plan's chip opens it, beside its due state. Each row has
  **Log**, a plan row its last contact and any safety-plan instruction,
  and under All and Following the list ends with **Add a student to
  follow up**. There is no
  Plans tab; Home's Due and overdue and Following stay.
- **The routine path is one screen**: student, duration, type, Save,
  about 10–20 seconds (§5.1). The optional details fold on the same page;
  there is no second screen (author, 2026-10-29). Among them, **Share this
  encounter with** offers one colleague this one encounter, which they
  agree to before seeing it (sharing screens rung 4, author, 2026-11-07).

## 2. Chrome

**RA Leave's RA layout, no bottom bar** (author, 2026-10-29): Residential
Operations' slim top bar and page tabs (`residentialops_ui.md` §2), so the
draft's bottom bar and fixed footer are gone. A form's Save sits at the
form's end, and the main action is a full-width Primary on the page
(`.btn-wide`, 52 px).

- **Two areas in the switcher**: *Support Logs*, for anyone with a grant
  beyond administration, and *Sys admin*, for sys admins and the
  super-admin. Nothing neutral sits between them (ruling 3).
- **Tabs follow the grants**, never the appointment:
  - Log and Students for the frontline;
  - Overview for senior staff and Other Staff view;
  - Consultation check for its grant;
  - Access, Configuration and Audit log in Sys admin.
- **Home is a tab only when it is a page of its own**: the frontline's
  dashboard, a recipient's flags, or a list of what a viewer with more
  than one destination reaches. Otherwise the bare mount redirects to the
  one page the viewer has.
- **There is no Safety flags tab** (author, 2026-10-29). Flags list on Home
  for the frontline and for a recipient without Overview, and on Overview
  for a recipient who has it (senior staff or Other Staff view). That tab carries the count of unacknowledged
  flags as a red badge, with its words for screen readers. A recipient's
  card ends with **Closed**, folded until opened (author, 2026-11-08):
  the flags closed in the last 7 days, latest closed first, each saying
  when it closed, then **Find
  an older one by student or date** (inert until wired).
- **A detail page** (a student, a plan, a flag, a history) has a back link
  and marks the tab of its list (`aria-current="true"`).

## 3. Color

- **Teal is Support Logs' accent** (`#0f766e`, dark `#2dd4bf`), on the
  shared tokens, under the
  one-accent-per-application rule of `residentialops_ui.md` §3.
- **Safety is red and separate**:
  - the Safety concern screen's header is the solid error color (`.safety-head`);
  - a flag's status is the soft error chip (`.chip-safety`);
  - the tab badge is solid.
- **Safety-plan support has its own marker token**,
  `--marker-safety-plan-bg` / `-fg` (violet), never a borrowed
  super-admin one (`.chip-marker`).
- **Teal sits near success green**, so an OK chip always carries its
  words.

## 4. Controls

- **Choice chips are native inputs styled as pills** (`.choice`):
  - single-select sets (duration, type, how, who started it, follow-up
    needed) are radio groups;
  - concern areas are checkboxes;
  - a selected chip shows a check mark and a semibold label as well as the
    tint, so selection never rests on color.
  - An optional set starts unset and has Clear.
- **Status chips are sentence case with their words**: "Overdue 2 days",
  "Due Mon 2 Nov", "Unacknowledged". "This week" means the next seven
  days.
- **Mark a safety concern is Destructive** (outline red). It sits apart,
  at the end of the routine form.
- **Save and raise safety flag is Primary** on the red-framed screen; no
  filled red role is added.
- **Call actions are `tel:` links** with visible numbers, first on the
  Safety concern screen. They are placeholders until the institution
  supplies its crisis protocol (§17 Q7).
- **A staff or student filter is a box of people** (author, 2026-10-30),
  Assignments' token box made live (`residentialapps/web/templates/residential/_people.html`,
  `token_filter`): a typed name or email that matches becomes a pill
  carrying the value, and its remove button brings the typeahead back.
  An empty box means everyone; unmatched text blocks the form, so a typo
  never widens a filter, and a name two people share asks for an email.
  A match is made on a pick, Enter, leaving the box or submit, never
  mid-typing; focus stays in the box, so Enter cannot undo it.
- **A per-row grant** on Access is a native checkbox, as Residential
  Operations' per-row flags are. Other Staff view is a select of its
  scope.
- Every control meets `residentialops_ui.md` §4: 44 px under a finger,
  and `disabled` until wired. A field that does not apply is hidden, not
  disabled: the follow-up fields until they are asked for. "Who started
  it?" is asked of every type (author, 2026-11-06: no type says who).
- **The forms that show their confirmation are live on sample data**:
  Log encounter's Save, Safety concern's Save and raise, Share, Flag for
  formal assignment and the Consultation check's Check. Each submits to its
  confirmation page and stores nothing.
- **When the Consultation check is wired to real records, its Check posts**
  (findings N4, 2026-11-03). On sample data it is a GET, so the purpose
  and the students' emails ride the URL (`/consultation/check?…&emails=`)
  into browser history, the host's access logs and any copied link, and
  that a staff member checked a student is itself sensitive. Wired, the
  emails travel in a POST body and the result renders from that request;
  a redirect after it may carry only a short-lived server-side token,
  never the emails. Your records' Unlock and its two
  downloads, and its template links, are live too, as are Records across staff's
  Unlock, Download CSV, template links and purge filter: the downloads
  are the sample's own records.

- **Your records** (author, 2026-10-30) ends Students on a phone, and
  sits beside Find in the side column on a wider screen while locked
  (author, 2026-11-08): a
  section locked until its holder ticks a confirmation and unlocks it.
  Unlocked, it downloads the holder's own encounters or plans as CSV, for a
  term of Rosters and setup's or all terms and one of their students or
  all (one form, a button for each), and offers a template for each. The upload (follow-ups only, for plans)
  and Purge all, of every record or one student's, are disabled until
  wired. Leaving the page locks it again. A purge hides and keeps.
  Purge all is Destructive, outline red (author, 2026-10-30).
- **Records across staff** (`/overview/records`, author, 2026-10-30), for
  senior identifiable access, behind the same lock: download, for any
  staff member or all, by student and term or all, which students each
  has encounters with (staff and student pairs) and their plans' kind,
  source and status, never a record's content; upload records tagged to a staff member (inert until
  wired), which reports how many rows would be added and which fail, by
  row number, with no preview of what they say (author, 2026-11-07); and delete purged records, filtered by staff and by student;
  by student, only that student's records go (Delete permanently inert until wired). Only
  senior identifiable access deletes; Sys admin's Audit log lists purged
  records as counts only (author, 2026-10-30). Its Student filter and
  downloads name every student, withheld or not: the lock is the
  deliberate, recorded step (author, 2026-11-07).
- **Administration and senior staff, each in view of the other** (author,
  2026-10-30). Administration decides who sees content but sees none;
  senior staff see who has records with whom but grant no access:
  - **Who holds access** (`/overview/access`, linked from Overview's card),
    for senior identifiable access: each grant's holders and the access
    changes, read-only.
  - **Senior reads** on Sys admin's Audit log: each senior's reads with
    Senior identifiable in the last 30 days (histories, the
    support-activity audit, downloads across staff), how many were
    downloads and the latest, never which student.
  - **Access warns** when no one holds Senior identifiable (the sample
    always has one; `?preview=no-senior` shows the warning).
  - **Configuration's Access card**: a sys admin may grant itself Senior
    identifiable, off by default and recorded.
  - **The wall** (author, 2026-11-07, rule 3 below): Overview shows
    **Who supports whom** (per staff member, students with records and
    plans) and **Students across staff** (per student, the staff with
    records and the signals), metadata only. A student's history lists
    the staff with records, each with **Request a share** (inert until
    wired); its encounters and Share on their behalf are gone. A plan
    seen by senior staff or Other Staff view shows no due state, last
    contact, next expected or contacts. A formal plan keeps, for senior
    staff, its source, cadence, review, instruction and history from its
    assignment or conversion on; Other Staff view sees any plan's who
    (its staff member and who assigned it), whom, kind and status only,
    on the plan and on Overview's Every plan (author, 2026-11-07). A
    follow-up's Convert form offers no cadence of its own. Records across staff downloads
    encounters as staff and student pairs only.
  - Senior staff never write into others' log records.

## 5. Lists and tables

- **Phone lists** (`ul.items`) carry the frontline's rows.
- **Tables carry Overview's Who supports whom and Students across staff, the
  Consultation check's result, Access and both audits**; their other cards
  are lists. Each table is sortable (`data-sort-auto`), with `data-sort-value` on cells whose text
  is not their value. The exception is a table whose order is its
  meaning: the Consultation check result is strongest first, so it takes
  no sort.
- **Configured lists are rendered from one place**, never hard-coded in a
  template (draft UI spec §3):
  - durations, types, concern areas, modes and cadences;
  - sources, escalation steps and closure outcomes;
  - the note limit;
  - the consultation rules.
- **Configuration** shows each list as a card in a `.card-grid`.

## 6. What the screens say about privacy

**The confidentiality rules** (author, 2026-11-07), which every screen
below applies. **Who can see what** (`/who-can-see-what`) explains them
to staff: the text of `residentialapps/docs/support_logs_confidentiality.md`,
linked from the account menu (wherever it has other entries; not on
the not-registered page or a no-grant viewer's `403` page) and from the
notice on every page that names students.

Copy keeps two words apart (author, 2026-11-07): **agree** for consent
to an action going ahead (a share, a team, a handover, a sys admin's on
someone's behalf), **acknowledge** for having seen information sent on
(a safety flag).

1. **Frontline staff see their own records**, and another staff member's
   only once access is granted.
2. **Access to a student's records is granted deliberately, and the
   receiver agrees to it**: an owner shares past records, or one
   encounter as they log it; two or more staff form a team for a
   student, which a senior may start; or a handover tags records to
   the receiver, agreed to by them and a senior. The model is
   `residentialapps/guide/1D_sharing_model.md` (author, 2026-11-07).
   **Share past records**, on a student's page, offers all or ticked
   records to one colleague; Shared with lists each as Pending or
   Agreed, with Withdraw (Destructive), inert until wired.
3. **Senior identifiable access sees, by default, only which students
   have records with which staff** (author, 2026-11-07): a record's
   metadata, never its content (everything else about a record: when,
   how long, type, concern areas, follow-up and note, and figures drawn
   from them). It
   names a student by default only when they are on a formal plan or
   have a safety flag or a team; any other
   student's name is withheld until a deliberate action reveals it. To
   read content, a senior requests a share from the owner; in an
   emergency a sys admin agrees to it on the owner's behalf. Every
   deliberate view is audited. The screens apply it
   (`residentialapps/guide/1D_sharing_screens.md` rung 1); Request a
   share is inert until wired.
4. **Other staff see a student only with an explicit grant**: Other
   Staff view, aggregate (no names) or identifiable.

- **A read is an action** (§11.3). Every page that names a student says
  that opening it is recorded:
  - a student;
  - a plan;
  - a flag;
  - Overview for identifiable viewers;
  - a history;
  - the support-activity audit;
  - a consultation check.
- **A senior's Overview folds every card that shows names** (author,
  2026-11-08): Who supports whom, Students across staff, Who holds
  access, Flagged for formal assignment and Every plan start closed, each
  heading opening its card, with Show or Hide beside it. The safety flags
  banner and the count tiles stay open; other viewers' Overview is
  unchanged. Folding is presentation only: the names are in the page
  (find-in-page opens a card), and opening one is not a recorded read.
- **Overview names by default only students on a formal plan, with a
  safety flag (open or closed) or with a team** (author, 2026-11-07), in Students across staff, Every plan and Flagged
  for formal assignment. A flag for formal assignment, with its
  suggested cadence, is a message to senior staff, not content. Any other student's name is replaced by
  **Show name** alone (author, 2026-11-07: no "No formal plan" label), which shows the name and its link in place and reads
  **Hide name** once open; a withheld Students across staff row sorts last on the
  Student column. A safety flag names its student, open or closed: the
  flag is the reason to. On sample data the name is in the page (and
  find-in-page can open it); wired, showing it is an audited read that
  fetches the name.
- **Aggregate view names no one.** Other Staff with aggregate view see
  counts only, with no student's name, id or link.
- **A student is known only as a student** (author, 2026-10-30): nothing
  ties one to a housing location, so no screen groups students by place.
  The cluster view (§10.5) is deferred, a cluster being the core's
  Precinct when it comes, and Sys admin keeps no cluster list.
- **No score anywhere** (§15):
  - a consultation state comes from named reasons;
  - Overview counts students and plans, never a load or a rise.
- **The Consultation check's reasons are metadata only** (author,
  2026-11-07): a safety escalation, a plan, or records with Support Logs
  staff, whose staff may have a view; never what records say, how many
  there are or when they were made. Its holder sees which staff have
  records about each student, to know whom to consult.
- **No consultation indicated never means well or suitable.** The result
  says so, and an entry it could not read is listed as not read, never
  given a state.
- **Administration sees no content.** Sys admin shows grants, lists,
  administrative events, purged records' counts, senior reads' counts
  and **Agree on behalf** (a handover or a senior's share request
  waiting on someone who cannot be reached, named by staff only), never
  a student. The
  support-activity audit is senior staff's, on Overview.
- **Notes are short and say so**: a live count to the limit, and the
  minimization guidance beside the field.

## 7. Sample data

As `residentialops_ui.md` §9:
- a **Sample data** chip;
- one sample module;
- local runs, and previewers deployed (`residentialapps/spec/applications.md`, "The preview gate");
- disabled controls, except the live forms of §4.

A **Sample viewer** card on every sample page (not the not-registered
page) switches the viewer (`?as=`). It comes **last on the page**, after
everything the page shows, and a **Viewing as** chip by the title names
the viewer with their line from the card ("Viewing as Daniel Koh, RF:
Frontline") and links down to it (`#sample-viewer`, author 2026-10-31). The viewers are the roles in practice (author, 2026-11-06): the
frontline (an RF, and an RSLM who also receives safety flags), office
staff with the Consultation check, the Master (Senior identifiable,
Other Staff view: aggregate and safety flags), the sys admin and the
super-admin. Other grant combinations, a rostered RF with no grant (the
`403` page) among them, are drawn for `?as=` but not offered on the card.
Every link carries the viewer.

## 8. Open questions

The draft's §9:
1. **Safety button role:** built as Destructive (§4).
2. **Filled red Save:** built as Primary on a red frame (§4).
3. **Choice chips:** built as styled native inputs (§4).
4. **Status labels:** built in sentence case (§4).
5. **Shared screens:** settled 2026-10-23, and since dropped (ruling 3).
6. **Residential customizer:** out of item 1.

Items 1–4 stand for the author to confirm at item 1's approval
(`residentialapps/guide/segment_1D_support_logs.md`, open question 3).
That plan also holds the questions this build raised:
- small counts on aggregate view;
- formal assignments in the consultation rules;
- checkboxes for the plan's Toggle.
