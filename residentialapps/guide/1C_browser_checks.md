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
  - Chloe has RA Leave and RA Events "Coming later".
  - Hui Min Goh has RA Events only.
  - Rachel and Sam add RA Leave admin, Rosters and setup and Sys admin.
- [ ] **The switcher** (top left) lists the viewer's areas, with **All
  applications** at the foot.

## 2. RA side (390 px first)

- [ ] **Chloe's Home**:
  - **My balance** first, Personal leave and Official leave side by side
    (2 days and 1 day available), with no tiles above it;
  - **Apply**;
  - "Asked to cover · 1" (Ethan Wong, 4 Dec – 6 Dec);
  - Drafts, with D-0001 "2 days over your Official leave";
  - "My applications · 1 in progress".
- [ ] **Tabs** read Home, Apply, Cover, History. Appeals are By
  invitation by default (2026-11-09), and Chloe is not invited, so no RA
  page offers her extra leave or links to it, and
  `/residentialops/ra-leave/appeal` is not found; the Extra leave tab
  appears only for an invited RA (Kai Ng) or while Open is previewed.
  Records already on file still show on an RA's own pages.
- [ ] **Apply** names the approvers from the RA's slot and lists blackouts
  ahead. From the draft, **Apply** opens pre-filled with a draft notice.
  Every control is disabled.
- [ ] **An application** (L-0101 as Chloe):
  - "‹ My history" back link, with the History tab marked;
  - a timeline with a "Next:" line;
  - "Emails you sent", showing **Not sent** and why, with Resend;
  - cover and Withdraw cards.
- [ ] **Cover**: To answer 1, Covering 1 (Hana Ito 14 Dec – 15 Dec),
  Earlier and declined 1.
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

- [ ] **Daniel's Home**:
  - tiles 3 / 2 / 2 (Awaiting my decision; Of those, waiting on cover;
    Decided);
  - the first three awaiting, with **All N** when there are more;
  - Recent decisions, This week, Later this term.
- [ ] **Awaiting** lists oldest first, with Overdue chips.
  - The "waiting on cover" tile opens it filtered, under the heading
    "Waiting on cover".
  - "Show everything awaiting me" clears the filter.
- [ ] **Deciding** (open an awaiting item):
  - back link and marked tab match where you came from;
  - Approve/Reject when it awaits this viewer;
  - a "Waiting on cover" note when the cover is not confirmed;
  - side cards: entitlement, the RA's other leave, the Precinct on those
    days.
- [ ] **Sam's queue** is L-0105, an appeal: "Cover not confirmed" and the
  "Decide without the cover's confirmation" tick box.
- [ ] **Rachel's queue** is L-0103, Final approval, pending 5 days, with an
  Overdue chip. Decided shows 9.
- [ ] **Precinct leave as Sam**, This week:
  - Away 3 (Maya Seah, Olivia Ng, Pranav Iyer);
  - Pending 7;
  - one clash, Willow A 13-25: Olivia Ng and Pranav Iyer, with "Away too"
    on Pranav.
  
  Change **Period** and press **Show period**: the range and tables
  follow. Sort a table, then reload: the sort is kept.
- [ ] **Precinct leave as Daniel**: This week has nobody away; Rest of term
  shows Hana Ito.
- [ ] **Appeals**: Invitations shows Gwen Ho "Sent: L-0105", Kai Ng Open
  and Nathan Yeo Lapsed, and Appeals with the Master.
- [ ] **Hui Min Goh** sees "You oversee no RA" and no tabs.

## 4. RA Leave admin (desktop first; then 390 px)

Reach it from Rachel's or Sam's landing card.

- [ ] **Dashboard**:
  - tiles: Pending first approval 5, Pending final approval 1, Appeal to
    the Master 1, Cover not yet confirmed 4. Each tile opens Applications
    filtered.
  - Needs attention lists L-0103, L-0104, L-0107, L-0109 and the
    Willow A 13-25 clash;
  - Emails not sent · 3, with Resend.
- [ ] **Policy**:
  - row builders for leave types, holidays and blackouts, with + and X;
  - radio fieldsets;
  - tick boxes and person tokens, all disabled;
  - except the appeal preview chips (§5).
- [ ] **Entitlements**: 30 RAs, each RA's name on its first row only.
  Leon Chia's Personal leave shows +2 with its reason. "None left" chips.
- [ ] **Approval chain**:
  - Maple 03-08's first approver is Marcus Tan, with a Delegate chip and
    "Grace Ho has not signed in yet";
  - Daniel Koh → Priya Raman, 7 Dec – 18 Dec, in the delegates row
    builder.
- [ ] **Applications**:
  - the "Cover not yet confirmed" tile shows "· 4 of 20";
  - **column chips** hide columns, and the choice is kept after a reload;
  - headers sort, with Days sorting as numbers;
  - a hidden column's kept sort is dropped.
- [ ] **An application** (admin): detail, timeline, Emails, the RA's
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
