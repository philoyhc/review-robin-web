# Segment 1D: the screens for the sharing model

**Opened 2026-11-07** (author: "revamp the screens according to the
current understanding"). Brings Support Logs' placeholder screens in line
with `residentialapps/guide/1D_sharing_model.md` and confidentiality
rules 2 and 3 (`residentialapps/spec/supportlogs_ui.md` §6). Sample data
only, as every Support Logs screen is: nothing is wired. Read against
RRW `b5ad5abe2`.

## Ladder

One RRW PR per rung, in order, each on the `residential` CI lane with
its spec, browser-check and test changes. New controls land inert
(scaffold-first); rung 1 changes what existing screens show.

### Rung 1 — The wall between senior staff and content

What senior identifiable access, Other Staff view and aggregate view see
becomes metadata only: which students have records with which staff.

- **Overview:**
  - The tiles, Team workload, Hotspots and Coverage all go; they are
    drawn from content.
  - **Who supports whom** takes their place: per staff member, how many
    students they have records with, and their formal plans and
    follow-ups.
  - **Students across staff** lists per student the staff with records
    and the signals (formal plan, active flag, team), named under rule 3.
  - Aggregate view sees the same as counts only.
  - Every plan keeps student, staff and kind; it loses due states and
    cadences.
  - The sample's workload, totals and coverage helpers go with them.
  - The safety flags card is unchanged.
- **A student's history:** the encounters list goes, and so does
  Sharing (Share on their behalf). Staff involved gains **Request a
  share** per staff member, inert. Plans keep staff and kind only.
- **A plan, seen by senior staff:** status, kind, source, cadence and
  assigned by stay (a formal plan's cadence is the senior's own setting).
  Due state, last contact, next expected and contacts go.
- **Records across staff:** the download carries Staff, Student and
  Student email only.

### Rung 1a — The explainer, in the app

The staff explainer (`residentialapps/docs/support_logs_confidentiality.md`)
as a page of its own, **Who can see what**, linked from every Support Logs
account menu that has entries and from every notice on a page that names
students (author, 2026-11-07).

### Rung 2 — Waiting for you

A card on the frontline Home, the inbox for every acknowledgement. Each
item has Accept and Decline, inert:

- a share offered, unnamed until accepted;
- a team invitation;
- a handover;
- a senior's request for a share.

The sample seeds one of each for Daniel Koh.

### Rung 3 — Share past records

On a student's page, Share with a colleague becomes **Share past
records**: choose records (all or some), choose a colleague, Share.
"Shared with" lists each share as pending or accepted, with Withdraw.

### Rung 4 — Share as you log

Log's optional details gain **Share this encounter with**, folded away.

### Rung 5 — Teams

- **Form a team** on a student's page (frontline) and on a student's
  history (senior), inert.
- Students' filter gains **Teams**, and a row shows the team.
- The sample seeds one team.

### Rung 6 — Hand over

- **Hand over** on a student's page (owner) and on a student's history
  (senior): choose records, choose the receiver.
- Sys admin gains **Acknowledge on behalf**: pending handovers and
  emergency share requests whose staff member cannot be reached, with
  no content shown.

## Checks

Each rung keeps `pytest`, `ruff`, `pyright` green and takes one
`diff-reviewer` read; `residentialapps/guide/1D_browser_checks.md` and
`supportlogs_ui.md` follow in the same PR. Done when the author's
browser check passes on each rung.

## Status

- Opened 2026-11-07.
- **Rung 1:** as planned, plus: the support-activity audit stops listing
  when a record was logged (its time is content) and withholds names as
  Overview does; a follow-up seen through the wall shows only who, whom
  and status; the plans download keeps kind, source and status; withheld
  rows sort in an order hashed from the id. One read: the audit, the
  plans download, stale spec sentences, a follow-up's facts, the
  withheld order and dead on-behalf code, all fixed. Left as is: Records
  across staff's purge filter counts encounters per student (senior
  deletion needs it), and the pairs download keeps its term filter.
- **Rung 1a:** as planned.
- **Rung 2:** as planned; the card shows only when something waits. A
  team invitation and a handover, like a share, name no student until
  accepted (the model names only the share's): the author's call to
  confirm, and a team member's choice about their earlier records then
  comes after accepting. Open for wiring: the owner's own row for a
  handover a senior started. One read: copy that overstated acceptance
  against the emergency path, the handover's who-accepts, a handover with
  no records behind it, and thin tests, all fixed.
