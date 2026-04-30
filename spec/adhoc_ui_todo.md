# Adhoc UI todo

Working notes for ad-hoc UI tweaks the user has called out. Each section is
scoped to a single page or component. Open questions are marked **Q:** —
resolve before implementing.

---

## `/operator/sessions/{id}` — session detail

### Page width

- Constrain page width to **800px** (currently inherits `max-width: 1400px`
  from `base.html`).
- **Q1.** "These pages" — does this apply only to `session_detail.html`
  (the URL the user named), or should the 800px cap also apply to the
  pages reachable from it via Manage / Edit
  (`session_edit`, `session_reviewers`, `session_reviewees`,
  `session_assignments`, `instruments_index`, `session_setupinvite`,
  `session_invitations`, `session_validate`, `session_monitoring`)?

### Session card

- Heading: `Session` → **`Session Details`**.
- New body layout (instead of the current stack of `<p>` rows):
  - **Row 1:** Code · Deadline · Created by
  - **Row 2:** Description
  - **Row 3:** Status · Edit button
- Edit button label: `Edit details` → **`Edit`**.
- "Created by" value pulled from `session.created_by_user.display_name`
  with email fallback (mirroring the chrome's `Signed in as {{ user.display_name or user.email }}` rendering).
- **Q2.** Row 1 layout — three side-by-side columns of equal width?
  Inline `Label: value` per column, like the existing rows? Or
  stacked label-above-value?
- **Q3.** Row 3 layout — Status pill on the left, Edit button on the
  right of the same row (justify-between)? Or both left-aligned with a gap?
- **Q4.** When `is_ready` is true, today's template swaps the Edit
  button for a checkbox + "Revert to draft" form. Where does that
  go in the new 3-row layout — same row as Status (replacing Edit),
  or as a new row below?

### Session setup card

- Heading: `Session setup` → **`Session Setup`**.
- Drop the table `<thead>` (`Item | Status | <actions>` row).
- Restate each row's status in sentence form:
  - Reviewers → `Number of reviewers: {num}`
  - Reviewees → `Number of reviewees: {num}`
  - Assignments → `Number of assignments: {num}`
  - Instruments → `Number of instruments: {num}` · `Status: {status}`
  - Set up invites label → **`Set up email invites`**
- New row order: Reviewers, Reviewees, **Assignments**, **Instruments**,
  Set up email invites.
- **Q5.** Keep the rows as a `<table>` (just without `<thead>`), or
  restyle as a flat list / definition list? A 2-column layout
  (label · Manage button) reads naturally without a table.
- **Q6.** Instruments — when `len(instruments) > 1`, the existing
  status string is `"3 (some open)"`. Under the new format, should
  `Status:` show just `open` / `closed` / `mixed`, with the count
  already stated by `Number of instruments`? Confirm wording.
- **Q7.** "Set up email invites" — change the row label only, or
  also change the page title / heading on
  `session_setupinvite.html`?

### Run Session card

- Four buttons: Validate Session Setup · Preview reviewer surface ·
  Manage Invitations · Extract Data.
- All four equal **width** (and equal height).
- Buttons **double height** vs current `.btn` (currently `padding: 8px 14px`).
- **Color reversed**: dark filled background, light bold font (i.e. flip
  `.btn.secondary`'s white-with-blue-text to filled-blue-with-white-text,
  bold weight).
- Double the horizontal spacing between buttons.
- **Q8.** Approach for the new style — introduce a new CSS class
  (e.g. `.btn-cta` / `.btn-large`) in `base.html`, or override
  inline on this card only? Adding a reusable class is cleaner if
  any future page wants the same look.
- **Q9.** Equal width — fixed pixel width, or stretch each to 25%
  of the row inside the 800px container (using flex `flex: 1`)?
- **Q10.** "Double height" — interpret as doubling vertical padding
  (8px → 16px, yielding a ~52px tall button), or a fixed pixel height?
- **Q11.** "Double the spacing" — current spacing is just default
  whitespace between inline `<a>` tags (~4px). Double that
  (~8px), or something larger (e.g. 16–24px) to feel intentional
  given the bigger buttons?
- **Q12.** Extract Data is rendered with `.btn.secondary.disabled`
  today. Should it match the new heavy style (still visually
  disabled), or stay as a smaller / muted "coming soon" button?

---

## Open questions summary

Q1 width scope · Q2 row 1 layout · Q3 row 3 layout · Q4 revert-to-draft
placement · Q5 table vs list · Q6 instrument status wording ·
Q7 setupinvite page title · Q8 new btn class vs inline · Q9 button
width strategy · Q10 height target · Q11 spacing magnitude ·
Q12 disabled button styling.

**Decisions (round 1):** Q1 only `session_detail`. Q2 inline
`Label: value`, equal-width columns. Q3 status left, Edit right
(space-between). Q4 revert renders as a new row below. Q5 keep
`<table>`. Q6 `Status: Open` / `Closed` / `Mixed`. Q7 update
title/heading; final wording: **`Email Invites`**. Q8 reusable
class (`.btn-cta`). Q9 25% each via flex `flex: 1`. Q10 keep default
padding, split labels into two lines. Q11 `gap: 16px`. Q12 disabled
buttons match the new heavy style.

---

## Round 2 — follow-up tweaks

### Session Details

- Reorder row 1 to `Code · Created by · Deadline`.

### Session Setup

- Drop the `<table>` markup; lay each row out flat (mirroring the
  Session Details meta row).
- Each row leads with the Manage button. Manage buttons reuse the
  Run Session `.btn-cta` style (filled-bold) and are equal width to
  each other and to the Run Session buttons. They do **not** need
  to be double height (single-line label is fine).
- Implementation: 4-column CSS grid (`.setup-grid`,
  `repeat(4, 1fr)`, 16px column gap) so the button column matches
  one Run Session button's `flex: 1` slot exactly.

---

## Round 3 — title + row-1 trim

### Session card title

- Move the **session code** out of row 1 and render it as a subtitle
  directly under the page `<h1>` (the session name). Keeps the page
  identifier visible while freeing space in the meta row.

### Session Details row 1 (revised)

- Now just two items: `Deadline · Created by` (Code now lives in
  the subtitle).
- Re-confirmed order from the user's message: **`Deadline`** first,
  then **`Created by`**.

### Session Setup

- Already shipped in round 2 (4-column grid + `.btn-cta` Manage
  buttons). User repeated the spec; no further changes needed.
