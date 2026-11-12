# ApplyDesk as the host sees it

> **Built so far:** segment AD1 built "The registry entry", "Health",
> "Running alone" (item 1) and "The URL map" as placeholders on sample
> data (item 2), pending the author's approval in a browser.

ApplyDesk's contract with the Cordware host. The host's side is
`cordware/spec/host.md`; this file states only what ApplyDesk adds. The
rulings behind it are `applydesk/guide/todo_master.md`.

## The registry entry

| | |
|---|---|
| Registry name | `applydesk` |
| Mount path | `/applydesk` |
| Factory | `applydesk.main:create_app` |
| Logger prefix | `applydesk` |
| Landing-page title | `ApplyDesk` |
| Icon | A white application sheet on a rose (`#be123c`) tile, running off the bottom-right, a tick cut in rose (author, 2026-11-02). The source is `applydesk/templates/applydesk/base.html`, copied to `cordware/web/app_icons.py` |

- The registry lists it after Residential's two applications and before
  Utilities, which stays last.
- The factory is a zero-argument callable returning a new `FastAPI`
  application with no schema pages (`/docs`, `/redoc`,
  `/openapi.json`). It reads no setting and opens no database.

## Health

`GET /applydesk/health` returns `{"status": "ok"}`, route name
`applydesk_health`, with no sign-in, setting or database. Excluding it
from Easy Auth is a deployment step.

## Running alone

`CORDWARE_APPS=applydesk` starts with ApplyDesk alone; an unset value
mounts it beside every other application. Its records are stamped
`application: applydesk` in the host's logs.

## The URL map

The table is `applydesk/guide/segment_AD1_skeleton.md`, "The URL map":
operators under `/operator/exercises`, participants under `/me`.

- **Public IDs** (`applydesk/ids.py`): 10 symbols from RRW's alphabet,
  `23456789abcdefghjkmnpqrstuvwxyz`, drawn at random. A path whose ID has
  any other shape, or names nothing, is a 404 before anything is read.
- **The profile page** is named by its own ID, never the application's,
  and shows only the *Shown to reviewers* section. In a blind exercise it
  redacts the applicant's name and identifiers.
- **The chrome** is the shared bar (`docs/header_chrome.md`): the app
  icon, the workspace's top line over the area, a switcher of *Exercises*
  and *My ApplyDesk* then *All applications*, the Light/Dark toggle and the
  account menu. An exercise's operator pages add a row of tabs: Home,
  Setup, Form, Applications, Panels, Review and Reports (author,
  2026-11-12).
- **The gate** (`applydesk/gate.py`): every route but `/health` answers
  anyone on a local run and, deployed, only the platform super-admin,
  with a 404 for everyone else, until the segments that wire them.

## The Form page

Segment AD1B (`applydesk/guide/segment_AD1B_form_builder.md`): the
application form builder on the Form tab, `/operator/exercises/<id>/form`.
Every move works in the browser; nothing is saved until AD2, and a
reload restores the sample form.

- **Layout.** The form's own *Form title* and *Description* at the top,
  which cannot be deleted or moved and collapses like a card, its title
  larger than a card's; then its cards; an Outline beside
  them in the right third, kept in view (one column on a phone, the
  Outline below).
- **Cards.** A question or text card (*field*), a *section* (a title) or a
  *page break*. A field card's type is one of String (min and max length),
  Integer and Decimal (min, max, step), List (comma-separated options,
  *Choose one* or *Choose any*), Photo (an aspect ratio; kept as a JPEG
  600 px on its longer side), Select people (a minimum and maximum, and
  who may be named: *Institution-wide* or a roster on the Panels page)
  and Title and Description (display only).
  Help text and descriptions grow to fit what is typed, with no resize
  handle; so does a long answer's box in Preview. Changing the type keeps the question, help text, *Required* and
  visibility, and empties the new type's fields: a photo's ratio starts
  at 4:5 and a list at *Choose one*.
- **Visibility** is per card: *Shown to reviewers* or *Not shown*; a new
  card is *Not shown*.
- **Collapsed**, a card shows its question and help text (a text card's
  title and description), a summary of its settings, and *Required* or
  *Optional* and its visibility as chips; expanded, its fields and its
  buttons. Cards load collapsed, the form's own card too; a form with
  one card opens it and the form's own card. No card
  shows a number.
- **Buttons** on each card: *Replicate* (a field card), *+ New* (an empty
  String card), *+ Section* and *+ Page break*, each inserted right after
  the card and a new card opened; *Delete*, with no confirmation,
  disabled on the form's last question or text card. A page break has
  *Remove*.
- **Reordering** by dragging a card's handle, or by focusing the handle
  and pressing ↑ or ↓.
- **The Outline** lists sections, cards and page breaks in order, with
  each card's visibility, and the counts of pages, sections, questions
  (a text card is no question) and required ones; a click goes to the
  card. Nothing in it is numbered. It follows every
  change.
- **Preview**, at the foot of the Outline with *Save* (disabled until
  AD2) beside it, shows the form in place of the cards, as an applicant
  sees it, page by page, built from the cards on screen; the button reads
  *Back to edit* meanwhile, and an Outline click also returns. *Open the
  preview in a new tab*, under them, shows the same at
  `/operator/exercises/<id>/form/preview` (a reload of the tab picks up
  later edits; opened on its own, or once the Form page has gone to
  another exercise, it shows the sample form and says so; its *Submit*
  is disabled). Select people previews as a box of pills, after
  Residential's Staff box: each comma-separated name or email found in
  its pool becomes a pill, one not found stays in the box with the
  reason, and the box takes no more at the maximum. Here the pools are
  sample rosters; looking people up in Entra ID through Graph comes with
  the applicant's form (AD4). Otherwise it shows a number field with its bounds, a list as
  radio buttons or tick boxes, a photo's frame at its ratio, and "Reviewers
  see your answer." under a shown question. Nothing typed there is kept.
