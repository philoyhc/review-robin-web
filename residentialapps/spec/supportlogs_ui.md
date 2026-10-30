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
the styles are `residentialapps/web/templates/residential/base.html`
under `data-app="supportlogs"`.

## 1. Devices

- **The frontline's pages are mobile-critical**: Home, Log encounter,
  Safety concern, Students, a student, My plans, a plan and a safety flag
  are designed at 390 px (functional spec §14, §16).
- **The page map has no device column for Support Logs**, so this
  section gives the classes.
- **Overview and the Consultation check are responsive**: their tables
  scroll sideways in `.table-wrap` on a phone. **Sys admin is
  desktop-oriented**.
- **The routine path is one screen**: student, duration, type, Save,
  about 10–20 seconds (§5.1). The optional details fold on the same page;
  there is no second screen (author, 2026-10-29).

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
  - Log, Students and Plans for the frontline;
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
  flags as a red badge, with its words for screen readers.
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
  disabled: Log encounter's "Who started it?" when the type already says,
  and the follow-up fields until they are asked for.
- **The forms that show their confirmation are live on sample data**:
  Log encounter's Save, Safety concern's Save and raise, Share, Flag for
  formal assignment and the Consultation check's Check. Each submits to its
  confirmation page and stores nothing. Your records' Unlock and Download
  CSV, and its template link, are live too, as are Records across staff's
  Unlock, Download CSV, template links and purge filter: the downloads
  are the sample's own records.

- **Your records** (author, 2026-10-30) ends Students and My plans: a
  section locked until its holder ticks a confirmation and unlocks it.
  Unlocked, it downloads the holder's own encounters or plans as CSV, for a
  term of Rosters and setup's or all terms and one of their students or
  all, and offers the template. The upload (follow-ups only, for plans)
  and Purge all, of every record or one student's, are disabled until
  wired. Leaving the page locks it again. A purge hides and keeps.
  Purge all is Destructive, outline red (author, 2026-10-30).
- **Records across staff** (`/overview/records`, author, 2026-10-30), for
  senior identifiable access, behind the same lock: download any staff
  member's records, or all staff's, by student and term or all, each row
  naming its staff member; upload records tagged to a staff member (inert until
  wired); and delete purged records, filtered by staff and by student;
  by student, only that student's records go (Delete permanently inert until wired). Only
  senior identifiable access deletes; Sys admin's Audit log lists purged
  records as counts only (author, 2026-10-30).
- **Administration and senior staff, each in view of the other** (author,
  2026-10-30). Administration decides who sees content but sees none;
  senior staff see content but grant no access:
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
  - **Sharing on a student's history**: senior staff share a staff
    member's records for the student with a colleague on that staff
    member's behalf (§17 Q11, inert until wired); the grant shows both
    names, and the staff member sees "shared by … on your behalf".
  - Senior staff read others' log records and never write into one.

## 5. Lists and tables

- **Phone lists** (`ul.items`) carry the frontline's rows.
- **Tables carry Overview's workload and hotspots, the
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

- **A read is an action** (§11.3). Every page that names a student says
  that opening it is recorded:
  - a student;
  - a plan;
  - a flag;
  - Overview for identifiable viewers;
  - a history;
  - the support-activity audit;
  - a consultation check.
- **Aggregate view names no one.** Other Staff with aggregate view see
  counts only, with no student's name, id or link.
- **A student is known only as a student** (author, 2026-10-30): nothing
  ties one to a housing location, so no screen groups students by place.
  The cluster view (§10.5) is deferred, a cluster being the core's
  Precinct when it comes, and Sys admin keeps no cluster list.
- **No score anywhere** (§15):
  - a hotspot's rise is a "Rising" chip on the student's own pattern;
  - a consultation state comes from named reasons;
  - workload's load weighting says it is not a measure of anyone's
    performance.
- **No consultation indicated never means well or suitable.** The result
  says so, and an entry it could not read is listed as not read, never
  given a state.
- **Administration sees no content.** Sys admin shows grants, lists,
  administrative events, purged records' counts and senior reads' counts,
  never a student. The
  support-activity audit is senior staff's, on Overview.
- **Notes are short and say so**: a live count to the limit, and the
  minimization guidance beside the field.

## 7. Sample data

As `residentialops_ui.md` §9:
- a **Sample data** chip;
- one sample module;
- local runs only;
- disabled controls, except the live forms of §4.

A **Sample viewer** card on every sample page (not the not-registered
page) switches the viewer (`?as=`), and a **Viewing as** chip by the
title names them. The viewers are one per authorization type, a viewer
reaching two pages, the
super-admin and a rostered RF with no grant (the `403` page). Every link
carries the viewer.

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
