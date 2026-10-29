# Support Logs UI

> **Built so far:** segment 1D item 1 built every Support Logs screen on
> sample data (`residentialapps/guide/segment_1D_support_logs.md`, rungs
> 1–6). Items 2–5 wire them. This file settles the draft UI spec,
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
  - Access, Configuration, Clusters and Audit log in Sys admin.
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
  confirmation page and stores nothing.

## 5. Lists and tables

- **Phone lists** (`ul.items`) carry the frontline's rows.
- **Tables carry Overview's workload, hotspots and clusters, the
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
- **No score anywhere** (§15):
  - a hotspot's rise is a "Rising" chip on the student's own pattern;
  - a consultation state comes from named reasons;
  - workload's load weighting says it is not a measure of anyone's
    performance.
- **No consultation indicated never means well or suitable.** The result
  says so, and an entry it could not read is listed as not read, never
  given a state.
- **Administration sees no content.** Sys admin shows grants, lists,
  cluster names and administrative events, never a student. The
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
- clusters (open question 2);
- small counts on aggregate view;
- formal assignments in the consultation rules;
- checkboxes for the plan's Toggle.
