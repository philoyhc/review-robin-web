# 1C browser checks: RA Leave screens

A step-by-step walk through every RA Leave screen built by segment 1C item 1
(`residentialapps/guide/segment_1C_ra_leave.md`), for the author's review
before item 1 is approved. The tests already check what each page contains.
These steps check what only a browser shows: layout at phone and desktop
widths, the scripts' behavior, and whether the screens read right.

- Tick a row once it is checked.
- A row that needs a change becomes a follow-up slice.
- Delete this file when item 1 closes.

## 0. Before you start

- **Start the app** with a block from `residentialapps/guide/fake_ids.md`,
  "RA Leave (1C)". Its table lists the RA and staff viewers and what each
  shows. The RA pages and the staff pages switch viewer with chips under
  the title.
- **RA Leave admin has no viewer switch.** It is drawn for a sys admin.
- **Appeal modes** are previewed from Policy's Appeals card (§5). A
  "Previewing appeals" chip by every RA Leave title shows when one is on.
  Choose **By invitation**, the default, to turn it off.
- **Widths:** the RA pages are phone first; check them at 390 px first. Check
  the staff and admin pages at desktop width, then at 390 px.

## 1. Chrome and the landing

- [ ] **Fuchsia throughout.** The top bar, tabs, primary buttons and focus
  rings are fuchsia. The favicon is a house. Dark mode is readable.
- [ ] **No bottom bar** at 390 px. The tabs scroll sideways if they
  overflow, and the bar scrolls away with the page.
- [ ] **The landing** (`/residentialops/`): its viewer chips change the
  cards.
  - Chloe has RA Leave only: RA Events is hidden from RAs for now
    (2026-11-09), on the landing and in the switcher.
  - Hui Min Goh has RA Leave (View records by name) and RA Events.
  - Rachel and Sam add RA Leave admin, Rosters and setup and Sys admin.
- [ ] **The switcher** (top left) lists the viewer's areas, with **All
  applications** at the foot.

## 2. RA side (390 px first)

- [ ] **Chloe's Home**:
  - **My balance** first, Personal leave and Official leave side by side
    (2 days and 1 day available), with no tiles above it;
  - **Apply**;
  - "My applications · 1 in progress";
  - Drafts, with D-0001 "2 days over your Official leave";
  - "Asked to cover · 1" (Ethan Wong, 4 Dec – 6 Dec).
  On a desktop the last three are the side column, beside the balance.
- [ ] **Tabs** read Home, Apply, Cover, History. Appeals are By
  invitation by default (2026-11-09), and Chloe is not invited, so no RA
  page offers her extra leave or links to it, and
  `/residentialops/ra-leave/appeal` is not found; the Extra leave tab
  appears only for an invited RA (Kai Ng) or while Open is previewed.
  Extra leave already on an RA's record would still show on their own
  pages; no sample viewer has such a record, so a test covers it.
- [ ] **No one on leave while covering** (as Chloe): Apply for 4 Dec – 5
  Dec says "You are covering Ethan Wong on 4 Dec – 6 Dec" and Submit stays
  off; 7 Dec – 8 Dec passes.
- [ ] **Apply** names the approvers from the RA's slot and lists blackouts
  ahead. From 960 px its form puts First day and Last day on the left,
  Leave type and Days of leave on the right (stacked in that order below),
  then Covering RA and Remarks across the full width; check the date
  inputs at 960 px. Key in dates: Days of leave counts them and says what
  is wrong (last before first, past, beyond the term, overlapping her own
  leave, a blackout, over the balance), and Submit opens only once they
  pass. With appeals Open previewed, over the balance is a note and Submit
  stays open. Request extra leave
  (as Kai Ng) has the same block, allowing more than the balance. From the draft, **Apply** opens pre-filled with a
  draft notice. Every control is disabled.
- [ ] **An application** (L-0101 as Chloe):
  - "‹ My history" back link, with the History tab marked;
  - a timeline with a "Next:" line;
  - "Emails you sent", showing **Not sent** and why, with Resend;
  - cover and "Changed your plans?" cards, the latter with **Withdraw to
    draft** (back to the drafts as sent); as Hana, L-0115 (approved, 14 Dec)
    has **Cancel leave** instead, and Chloe's L-0117 (taken) has neither.
  - leave under way: as Sam, the Application page of L-0107 (Olivia Ng) has **Cancel leave
    under way**, naming Olivia and Siti Rahman as told; the admin's L-0107
    says the same.
- [ ] **Cover**: To answer 1, Covering 1 (Hana Ito 14 Dec – 15 Dec),
  Earlier and declined 1; a Summary card (beside the cards on a desktop,
  last on a phone) reads Days covered 0, Days now or upcoming 2,
  Requests to answer 1, Declined 1.
- [ ] **History**: Drafts, then every application newest first.
- [ ] **Each RA viewer's state** reads as the table says. Switch with the
  chips:
  - Hana Ito is asked to name new cover.
  - Faris Iskandar shows his rejection.
  - Kai Ng shows approved leave cancelled, and the Extra leave tab.
  - No viewer is there for an appeal alone (2026-11-09): Gwen Ho, Lucas
    Teo and Maya Seah are not offered.
- [ ] **Text fits at 360 px**: no row or chip overflows its card.

## 3. Staff side

- [ ] **Daniel's Home** (Home and Awaiting are one page, 2026-11-09):
  - no tiles; tabs Home, Records (an RF has no Appeals tab;
    Sam and Rachel do; Priya, an RSLM with no tick, sees no RA Leave);
  - Awaiting my decision lists all three, oldest first, with Overdue
    chips; "Waiting on cover · 2" filters it under the heading "Waiting
    on cover", and "Show everything awaiting me" clears the filter;
  - no Recent decisions card; at the side This week (away
    today) and Later this week (as Sam: Maya Seah and Olivia Ng today,
    Pranav Iyer later);
  - an old `/ra-leave/staff/decide` link lands on Home, an old
    `…/decide/L-0101` on `…/applications/L-0101`, and `…/decided` on
    Records;
  - a Leave calendar under the cards (as Sam: October has Maya, Olivia and
    Pranav; November Chloe Lim (pending) and the Examinations days named
    and hatched); on a phone the whole month still fits at 390 px, each
    entry a first name in a tag;
  - its filter chips: as Daniel, Approved and Pending only; as Sam or
    Rachel, Cypress, Maple and Willow besides. Each turns off and on, and
    the month links keep what is off.
- [ ] **Deciding** (open an awaiting item):
  - back link and marked tab match where you came from;
  - Approve/Reject when it awaits this viewer;
  - a "Waiting on cover" note when the cover is not confirmed;
  - side cards: entitlement, the RA's other leave, the Precinct on those
    days.
- [ ] **Sam's queue** is L-0105, an appeal: "Waiting on cover", Elise Tan
  not yet confirmed, with no override (cover harmonized, 2026-11-10).
- [ ] **Rachel's queue** is L-0103, Final approval, pending 5 days, with an
  Overdue chip.
- [ ] **Records as Sam** (desktop; `/ra-leave/staff/precinct` lands
  here; Bella Koh's row marked "1st: Marcus Tan"), This week:
  - Leave applications: Period, From, To and Name in a row; typing
    "elise" leaves Elise Tan's rows and the count, Enter not reloading;
    Filters closed,
    opening on Status, Cover, Precinct and Columns rows, its summary
    naming what is off; hide Submitted: it goes at once and stays hidden
    after a reload; the table ID, RA, Precinct, Type (PL, OL), Dates, Days,
    Cover, Submitted, Stage, Remarks (Bella Koh's "1st: Marcus Tan" and
    "Pending 5 days"; Olivia Ng's "Cover away"); Maya Seah and
    Olivia Ng On leave, Pranav Iyer Approved (from tomorrow); turn a chip off and change the period: it
    stays off; Whole term adds Taken, Rejected and Withdrawn rows;
  - Summary, this week: Estab., Full, −1, −2, −3 per Precinct (Willow A
    13-25: 4, 3, 2, 2, 0), with Leave taken, Leave approved and Leave
    approval pending chips, and Weekdays and Weekends; turning Leave
    approval pending off makes Cypress A 04-12 seven days Full, and
    Weekends off counts 5 days; Clashes at its right, one, Willow A
    13-25: Olivia Ng and Pranav Iyer.

  Choose a **Period**: the page reloads at the top with the range and
  tables following; no Show period button. Each chip, Select all and
  Clear all (Status and Precinct each have their own) also lands at the
  top, the other group unchanged. Sort a table, then reload: the sort is kept.
- [ ] **Records as Daniel**: no Precinct chips or column; This week
  has nobody away; Rest of term shows Hana Ito.
- [ ] **Appeals**: Invitations shows Gwen Ho "Sent: L-0105", Kai Ng Open
  and Nathan Yeo Lapsed, and Open appeals.
- [ ] **Priya Raman** sees "no tick in Permissions" and no tabs; **Hui Min Goh**
  sees the Cypress Precincts and Maple 03-08, read-only.

## 4. RA Leave admin (desktop first; then 390 px)

Reach it from Rachel's or Sam's landing card.

- [ ] **Dashboard**:
  - tiles: Pending first approval 5, Pending final approval 1, Appeal to
    the Master 1, Cover not yet confirmed 4. Each tile opens Leave records
    over the whole term with only its rows' chips on.
  - Set-up: Term and cycle, Rosters, Policy at a glance, Approval
    chain, Who reaches the staff pages, Coming up, three across at
    1440 px, two at 1000 px, one on a phone, each ending in its link;
  - Needs attention: Records lists L-0103, L-0104, L-0107, L-0109, the
    three emails not sent and the Willow A 13-25 clash; Entitlements;
    Roster mismatches (no one in every slot for Term 2).
- [ ] **Policy**:
  - row builders for leave types, holidays and blackouts, with + and X;
  - radio fieldsets;
  - tick boxes and person tokens, all disabled;
  - except the appeal preview chips (§5).
- [ ] **Entitlements**: 30 RAs, each RA's name and Neighborhood pill
  on its first row only; sorting by Neighborhood groups the RAs by slot.
  Leon Chia's Personal leave shows +2 with its reason. "None left" chips.
- [ ] **Approval chain**:
  - Maple 03-08's first approver is Marcus Tan, with a Delegate chip and
    "Grace Ho has not signed in yet";
  - Daniel Koh → Priya Raman, 7 Dec – 18 Dec, in the delegates row
    builder.
- [ ] **Leave records** (admin; `/ra-leave/admin/applications` lands here):
  - the staff Records card: Period, then From and To, one above the
    other; Status, Cover and Precinct chips, each row ending in Select all
    and Clear all; the "Cover not yet confirmed" tile shows 4 rows;
  - choosing a period, or keying in both From and To, reloads at the top;
  - headers sort, with Days sorting as numbers;
  - Export CSV and Record external leave under the table.
- [ ] **An application** (admin, `/ra-leave/admin/records/{id}`): detail, timeline, Emails, the RA's
  balance, and Administer buttons by stage.
- [ ] **At 390 px** wide tables scroll inside their cards, and the page
  never scrolls sideways.

## 5. Appeal modes

On Policy's Appeals card, choose each preview chip in turn. Each one
redirects back to the card and puts a "Previewing appeals: …" chip by every
RA Leave title.

- [ ] **By invitation** (the default) clears the preview, and the chip
  goes:
  - Only Kai Ng has the Extra leave tab, with "send it by 10 Nov".
  - `/residentialops/ra-leave/appeal` as Chloe returns Not Found.
  - Staff Appeals offers "Open an appeal" to Sam and Rachel only.
  - Approval chain gains an "Opens appeals" column.
- [ ] **Open:** every RA has the Extra leave tab and **Request extra
  leave** on Home.
- [ ] **Off:** no RA has the Extra leave tab or link, the appeal page not found, and Apply says
  only "Leave in a blackout cannot be submitted." The staff Appeals tab
  stays while L-0105 is still open.

## 6. After looking

The 1C plan has no open UI questions: leave types and the day count were
ruled 2026-10-28 and 2026-10-29. Note anything that reads wrong by page and
viewer; each becomes a follow-up slice before item 1 is approved.
