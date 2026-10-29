# Residential Operations UI

> **Built so far:** segment 1B item 1 built the chrome, the placeholder
> screens of Rosters and setup and Sys admin, the row builders on the
> Assignments page, the roster tables, the slots and the Terms page, on sample data. Segment 1C item 1 adds RA Leave's
> screens and extends this file from them.

The conventions every Residential Operations screen follows. Where this
file is silent, RRW's design system applies: `spec/ui_elements.md` for
components and `spec/visual_style_general.md` for type, color and spacing.
Support Logs' screens follow their own UI spec,
`residentialapps/docs/support_logs_ui_spec_v0.1.md`, which shares the
tokens and accent rules cited in §3; its chrome is settled at that spec's
next version. The page map, with each page's device
class, is `residentialapps/spec/applications.md` ("Pages"); the styles are
in `residentialapps/web/templates/residential/base.html`.

## 1. Devices and widths

- **Device classes** follow `docs/cordware_mobile_to_desktop.md` §3:
  *mobile-critical*, *responsive* and *desktop-oriented*. The page map
  gives each page its class.
- **Phone first.** A mobile-critical page is designed at 390 px, holds at
  360 px and does not break at 320 px. Base styles are the phone's;
  `min-width` media queries widen them.
- **Up to three columns of cards** from 960 px, stacked in column order
  below it.
- **The page is centered and at most 1232 px wide** (1184 px of content
  inside 24 px padding); the top bar and the tabs keep the same width.
  RRW's 1400 px left-aligned page is its own (author, 2026-10-27).
- **Desktop-oriented pages stay usable on a phone**: nothing breaks, and a
  wide table scrolls sideways in its box (`.table-wrap`, at least 640 px
  wide). They are not designed for one.
- Routes and permissions are the same at every width
  (`docs/cordware_mobile_to_desktop.md` §7.5, §9).

## 2. Chrome

One chrome, phone first (author, 2026-10-26, from the RA Leave mockups).
Residential Operations is served to a browser, never as an installed app,
so its chrome is one slim top bar at every width and no bottom bar, which
would compete with a phone browser's own toolbar. The bar scrolls away
with the page.

- **On the left, the switcher**: the Unit's name above the current area's
  name. Its menu lists the areas the viewer reaches (Home, RA Leave, RA
  Events; RA Leave admin, Rosters and setup and Sys admin for sys admins),
  RA Leave at the viewer's own side, RA's or staff's, then one link,
  **All applications**, to the host's landing page, which lists what
  Cordware mounts (author, 2026-10-26). An application cannot see the
  host's mounts without importing `cordware.main`, which it may not, nor
  read another application's permissions; the landing page knows both. A
  page with no areas (not registered) shows the switcher static.
- **On the right, the Light/Dark toggle and the account**: the toggle at
  every width, sharing RRW's `rrw-theme` choice so one choice holds across
  the host; initials, with the viewer's name beside them from 960 px, and their role
  once identity is wired (1B item 3).
- **Under the bar, the area's page tabs**, with short labels, scrolling
  sideways on a phone. Rosters and setup's are Home, Assignments, Staff
  roster and RA roster (§7); RA Leave's split by audience (`residentialapps/spec/applications.md`):
  an RA's under `/ra-leave/`, staff's under `/ra-leave/staff/`, and sys
  admins' under `/ra-leave/admin/` (Dashboard, Policy, Entitlements,
  Approval chain, Applications, Appeals), each set its own. A detail page
  adds a back link instead of a breadcrumb, and marks the tab of the list
  it belongs to (`aria-current="true"`; author, 2026-10-29).
- **The favicon** is the accent behind a white glyph, as inline SVG: a
  house for Residential Operations, a lined notepad for Support Logs
  (author, 2026-10-27, from the design canvas). The shared chrome picks it
  by application; one icon serves both themes.

## 3. Color

- **Fuchsia is Residential Operations' accent** (`#a21caf`, dark
  `#e879f9`), for primary actions, selection, focus, links and the current
  navigation item. The accent follows the application, not the viewer, and
  never takes a status hue; the figures and the shared tokens are
  `residentialapps/docs/support_logs_ui_spec_v0.1.md` §6.
- **Dark** takes RRW's dark neutrals and the accent's dark-surface tone.
- **Status is a chip with words**, never color alone: info, warning, OK,
  muted, each on the shared status tokens.

## 4. Buttons

RRW's roles (`spec/ui_elements.md` §6), under Residential's class names:

| Role | Class | Use |
|---|---|---|
| Primary | `.btn .btn-primary` | the page's or card's main action, accent filled |
| Secondary | `.btn .btn-secondary` | other actions, outlined |
| Destructive | `.btn .btn-danger` | remove, revoke, delete, outline red |
| Glyph | `.btn-glyph` with a role above | one-character row actions (+, X) |

A page action is at least 36 px tall; a back link, and the link that
opens an item in a phone list, at least 44 px (author, 2026-10-29). A
control a placeholder cannot yet
perform is `disabled`, not hidden.

## 5. Row builders

A list the viewer edits row by row — the levels on Assignments — takes
RRW's Band 3 response-field rows as its model (author, 2026-10-27):

- **Each row ends in + and X**: a Secondary + adds a row below, a
  Destructive X removes the row. There is no fixed number of rows.
- **Each list has a limit**, and its + says so once the list is full:
  up to 5 levels (`residentialapps/guide/todo_master.md`, organization
  by units).
- **Measures, after RRW's rows** (measured in Chromium, 2026-10-27):
  16 px text in boxes padded 4 px 8 px, glyph buttons 32 px wide at
  weight 500, 4 px cells and a rule under each row (`.rows`). Boxes, selects and
  buttons are all 30 px tall (author, 2026-10-27; RRW's selects are
  32 px).
- On a phone the list's table scrolls in its box rather than squeezing
  its fields.

## 6. Roster tables and the slots

The Staff and RA rosters take RRW's roster pages and Sessions Lobby as their
model (author, 2026-10-27):

- **A filter card above the table**: one filter box over name and email,
  after the lobby's, beside the page's filter selects, then Clear and
  the page's add action (Primary).
- **A tick box leads each row**, with a select-all in the header. Ticked
  rows take accent rails at both ends.
- **Ticking opens an expander** under the last row ticked, closing the
  rails: the count selected, then the row actions. Edit takes one row, and
  more than one ticked fades it (author, 2026-10-27; RRW's rule,
  `spec/setup_pages.md`); End appointment end-dates and keeps the history; Delete, for a row made in
  error, waits on its confirm tick box. Unticking every row closes it.
- **The setup cards sit below the table, on one row** (`.bottom-row`,
  author, 2026-10-27): its CSV card takes two thirds from 960 px, beside
  the levels (a third) on Assignments and alone on a roster (author,
  2026-10-28); below 960 px the cards stack at full width. A CSV card carries the sample, then Upload and
  preview and Export.
- **A value has one home.** Where it is set, it is plain text and edited
  there; where another page repeats it, it is a pill (`.pill-derived`),
  read-only (author, 2026-10-27): a person's slots, on their detail page,
  come from the Assignments page's cells. Sign-in stays a status chip (§3). The Staff roster shows no access: sys admin is listed on the Sys admin page, and other applications' grants stay in those applications (author, 2026-10-28).
- **A roster row carries its appointment and its abbreviation**, in
  their own columns; a roster's appointments are the pairs its rows hold,
  with no types table and no limit (author, 2026-10-28).
- **Assignments' slots table** takes the same tick boxes and expander,
  with Retire in place of End appointment. One row per slot, under its
  higher levels, whose names show on a group's first row only; a new top
  level opens under a heavier rule. Notes are small subtle text; the Staff
  and RA cells are typeahead boxes (organization by units, 2026-10-27).

## 7. Setup order

Rosters and setup runs in order, after RRW's Setup tabs (author,
2026-10-27): **Home**, **Assignments** (Organization until 2026-10-28),
**Staff roster**, **RA roster**.

- **Home** (`/rosters/`) summarizes four numbered steps (author,
  2026-10-28), each with its state, counts and a link: 1 Setup (the
  levels, the slots and the terms; its link opens Terms until done, then
  Assignments), 2 the Staff roster, 3 the RA roster (people and their
  appointments), 4 the assignments for a term, and a Checks card listing the warnings across the steps. Until setup is done it opens on how to do it, after RRW's
  first-run lobby card (`spec/sessions_overview.md`).
- **Assignments** (`/rosters/assignments`) shows one term at a time,
  chosen in a term card above the slots table (`?term=AY2026-2027.1`),
  opening on the term today falls in, else the next. The card also holds
  Copy from (an earlier term's assignments, to edit) and Set up terms.
  Below it, full width above the slots table, the **Every slot** card
  sets who is in every slot for the term, by Unit-level appointment, by
  name, or both; they oversee every RA, and copying a term's assignments
  copies its choices (author, 2026-10-29). It opens with the Staff
  cells; a past term, or one before the slots stand, has none. Its
  choices are set on the card, not carried by the Assignments CSV. A
  past term is read-only, under a notice and with no Copy from; a term
  before the slots stand lists none; a term without assignments says so
  and offers the copy. A partial-overlap warning, one notice per
  assignee, names the gap in days. Below the table, the Assignments CSV
  card (its upload mode chosen by radio buttons, none chosen at first:
  New slots, Refresh a term, Add a term, each with what it does; Upload
  and preview unavailable until one is chosen; and Export over a From–To
  run of terms, the term shown by default, author, 2026-10-28) beside the
  levels.
- **Terms** (`/rosters/assignments/terms`) is a detour, after RRW's
  `/guide`: a "← Back to" link returns to the roster page named in
  `?return_to=`, else to Assignments. It lists each year's terms (up to 5,
  each a name and dates, never overlapping) with their length in days and
  their status, under an Add year Primary; each row but a past term's has
  an Edit button, since a past term is read-only. Its CSV card sits below.
- **A blank cell in an upload** means what its mode makes it (author,
  2026-10-28):
  - a **roster** upload appends, so a blank optional column (enterprise
    name, student ID) leaves the value on file as it is;
  - an **Assignments** upload with **New slots** or **Refresh a term** is
    the term's whole content, so a blank Staff, RA or Notes cell is empty
    and replaces what was there; with **Add a term** there is nothing on
    file, and a blank is simply empty;
  - every **Terms** column is required, so a blank is refused;
  - a refused row raises no warning besides its refusal, in every upload.
- **The slots** open once terms exist; **both rosters** once the slots
  exist; the slots' Staff and RA cells once both rosters have people.
- **A step not yet open is shown, not hidden**: its content renders
  inactive (`.gated`, `inert`) under a note naming what to finish, with a
  link there.

## 8. Cards and notices

- **Cards**: 8 px corners, a subtle border, 16 px padding; a card's `h2`
  is 18 px with its explanation beneath in subtle text.
- **A notice** above the cards carries a page-level warning, such as an
  overlap; warnings that never block a save say so.
- **Stat tiles** (`.tiles`, RA Leave admin's dashboard, 2026-10-28): a
  count over its label, each tile a link to the rows it counts.
- **Numbers in a table** sit right-aligned (`td.num`).
- **Phone lists** (`ul.items`, RA Leave's RA pages, 2026-10-28): on a
  mobile-critical page, rows are list items rather than table rows, each
  a head line (`.item-head`: what, then its date or chip) over a subtle
  line of details.

## 9. Placeholders and sample data

Until a screen is wired:

- it shows a **Sample data** chip by its title, and its sample data lives
  in one module, deleted in one place by the item that wires it;
- its controls are present and `disabled`, except a roster's tick boxes,
  which open the expander so its shape can be checked (§6), and
  Assignments' term selector and its Show term button, which are
  navigation, and its upload-mode radios, so the Upload button's
  unavailable state can be seen (§7);
- it answers only on a local run (`APP_ENV=local`), 404 elsewhere;
- a page drawn for one person (RA Leave's RA and staff pages, the
  landing) says so in a **Viewing as** chip beside the Sample data chip;
  the staff pages and the landing switch that person on the page
  (`?as=`; the staff pages' tabs carry it);
- Rosters and setup previews each setup state with `?stage=start`,
  `?stage=slots` or the default, `done` (§7), switched from the title row.

## 10. Accessibility

RRW's floor applies: text at 4.5:1 and control boundaries at 3:1 in both
themes. Beyond it:

- **Every control has an accessible name.** A control repeated per row
  names its row: "Cypress A 04-05-06: Staff", "Remove Level 3".
- **A column of buttons has a header**, visually hidden when the buttons
  speak for themselves.
- **Color is never the only signal** (§3).

Links follow `residentialapps/spec/applications.md` ("URLs"): `url()` inside
the application, `host_url()` for the host's.
