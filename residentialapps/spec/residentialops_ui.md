# Residential Operations UI

> **Built so far:** segment 1B item 1 built the chrome, the placeholder
> screens of Rosters and setup and Sys admin, and the row builders on the
> Organization page, on sample data. Segment 1C item 1 adds RA Leave's
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
  Events; Rosters and setup and Sys admin for sys admins), then one link,
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
  sideways on a phone. Rosters and setup's are Organization, Staff roster
  and RA roster; RA Leave's, when built, are an RA's Home, Apply, Extra leave,
  My cover, History, and an approver's Awaiting my decision, Team leave,
  Decided; staff with Leave admin add its pages. A detail page adds a
  back link instead of a breadcrumb.
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

A page action is at least 36 px tall. A control a placeholder cannot yet
perform is `disabled`, not hidden.

## 5. Row builders

A list the viewer edits row by row — the Level labels and Appointments
on the Organization page — takes RRW's Band 3 response-field rows as its
model (author, 2026-10-27):

- **Each row ends in + and X**: a Secondary + adds a row below, a
  Destructive X removes the row. There is no fixed number of rows.
- **Each list has a limit**, and its + says so once the list is full:
  up to 5 levels and up to 10 appointments
  (`residentialapps/guide/todo_master.md`, organization levels, amended).
- **Measures, as RRW's rows render** (measured in Chromium, 2026-10-27): 16 px text in 30 px boxes padded
  4 px 8 px (selects 32 px), 32 px glyph buttons at weight 500, 4 px
  cells and a rule under each row (`.rows`).
- On a phone the list's table scrolls in its box rather than squeezing
  its fields.

## 6. Cards and notices

- **Cards**: 8 px corners, a subtle border, 16 px padding; a card's `h2`
  is 18 px with its explanation beneath in subtle text.
- **A notice** above the cards carries a page-level warning, such as a
  floor gap; warnings that never block a save say so.

## 7. Placeholders and sample data

Until a screen is wired:

- it shows a **Sample data** chip by its title, and its sample data lives
  in one module, deleted in one place by the item that wires it;
- its controls are present and `disabled`;
- it answers only on a local run (`APP_ENV=local`), 404 elsewhere.

## 8. Accessibility

RRW's floor applies: text at 4.5:1 and control boundaries at 3:1 in both
themes. Beyond it:

- **Every control has an accessible name.** A control repeated per row
  names its row: "Appointment 2: type", "Remove Level 3".
- **A column of buttons has a header**, visually hidden when the buttons
  speak for themselves.
- **Color is never the only signal** (§3).

Links follow `residentialapps/spec/applications.md` ("URLs"): `url()` inside
the application, `host_url()` for the host's.
