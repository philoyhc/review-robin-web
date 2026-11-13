# ApplyDesk — the applicant photo field (design)

**Saved:** 2026-11-12, by the author's ruling: "Save the spec for Apply
Desk's use later." A design, not a contract, and not scheduled. Ruling 3
in `applydesk/guide/todo_master.md` keeps uploads out of the MVP; this
field is the one upload that needs no Blob storage, so when, and whether,
it enters is the author's call (an open decision there).

**Source:** Utilities' photo proof of concept, segment U4
(`utilityapps/guide/segment_U4_photo_poc.md`, `utilityapps/spec/utilities.md`
"Photo proof of concept"): the cropper, the server's pipeline and the
storage were built and checked there. ApplyDesk keeps its own copy of
both, as it does RRW's ID alphabet: no package imports another.

## Mock-ups

`photo_field/mockup.html` is the static mock-up (open it as a file; add
`?chosen` for the second state). Rendered at 1280 px and at 390 px:

| | |
|---|---|
| Desktop, no photo yet | `photo_field/desktop_empty.png` |
| Desktop, a photo chosen | `photo_field/desktop_chosen.png` |
| Phone, a photo chosen | `photo_field/phone_chosen.png` |

## Layout

- **Width.** ApplyDesk's page is at most 1232 px with 16 px gutters, so a
  form section is up to 1200 px wide (`applydesk/templates/applydesk/base.html`,
  `.page`). The photo field is capped at **760 px**, so the drop box does
  not stretch across the section.
- **Desktop, two columns.** Left, **the frame**, 240 × 300 px (4:5): it is
  also the preview, so there is no second one. The **zoom bar** stands
  upright on its right (up is zoom in); the **rotate bar** lies below it,
  −180° to 180°, snapping to −90°, 0° and 90° when dragged, marked under
  the bar. Right, the **upload area**, filling the rest.
- **Upload area, before a photo.** A dashed drop box: an image icon,
  *Choose a photo, or drop it here*, *JPEG, PNG or WebP · 5 MB at most*.
  Under it, one line of guidance (face the camera, plain background,
  nobody else) and what is kept (480 × 600 px, nothing else from the
  file).
- **Upload area, after.** A box with the file's name, size and pixel
  size; three short how-tos (drag to move; the bars; pinch and twist on a
  phone); *Choose another photo* (Secondary). Below it, a slim drop strip
  for a different photo, and the line on what is kept.
- **Phone (under 600 px).** One column: the frame full width with its
  bars, then the upload area.
- **Field chrome** as the form's other fields: a bold label (*Photo*), a
  muted help line ("A recent head-and-shoulders photo. Frame it in the
  window: that is exactly what assessors will see.").

## Behavior

As U4's tool, which is where to read the code:

- **Choosing** checks type and the 5 MB limit in the browser first; the
  photo appears in the frame covering it, upright from its EXIF
  orientation.
- **Framing**: drag (one finger, a pointer, the arrow keys); zoom 1 to 4;
  rotate any angle; on a touch screen two fingers pinch and twist about
  their midpoint. The photo always covers the frame.
- **Saving** goes with the form: *Save draft* and *Submit* send the
  original file and the frame (center, width, turn) with the other
  answers. There is no Save button of the field's own.
- **The server** decodes (JPEG, PNG, WebP, a phone's MPO; 40 Mpx at
  most, checked before decoding), orients, checks every corner of the
  frame lies over the photo, cuts out and turns what the frame shows,
  converts any color profile to sRGB, and keeps a **480 × 600 JPEG with
  no metadata** (`utilityapps/photo_poc/service.py`, `Frame` and
  `process`). The original is never kept.
- **Reading back** is through an authorized route, `private, no-store`,
  never a public URL.

## Open questions

- **Into the MVP?** Ruling 3 says no uploads; this needs no Blob (author).
- **Blind exercises.** Ruling 6 redacts name and identifiers on the
  application file; a face is an identifier. Hide the photo there, or keep
  the field under *Not shown to reviewers* in a blind exercise (author,
  at AD4/AD5).
- **Required or optional**, per exercise (AD4's form builder).
- **Retention.** Real applicants' photos need a retention rule under PDPA
  before any is kept (U4's plan, Semantics).
- **Where it is stored**: a column on the application in ApplyDesk's own
  database (AD2), as U4's `photo_poc_photos` table holds its bytes.
- **Removing** a chosen photo before submit, if the field is optional.
