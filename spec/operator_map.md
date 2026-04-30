# Operator page map

Specification of the operator-facing page surface. Most sections
describe what currently ships; placeholder sections explicitly call
out deferred work. For per-route detail with template paths, form
field schemas, and audit events, see `docs/status.md`'s operator URL
table. For the segment-by-segment implementation history, see
`docs/status.md`'s "Segments shipped" table.

## Cross-page conventions

Every page (operator and reviewer) renders the same chrome before
its body:

- **App identity (top left).** The text "Review Robin Web App
  (version {num})" rendered small (not large heading), as a link to
  `/about`. (Operators reach the sessions list via the breadcrumb,
  not via the app-identity text.)
- **User card (top right).** A small card with "Signed in as
  {user name}" and a **Sign out** button. The Sign out button posts /
  links to `/.auth/logout`.
- **Breadcrumb trail (top left, just below the app identity).**
  Reflects the page's position in the surface hierarchy. Each
  segment except the current page is a link to that ancestor page.
  The current page renders as a plain non-link label. Breadcrumbs
  replace per-page back-link buttons, so individual page specs
  below do not list a separate back link, and individual page specs
  do not list a separate Sign out control either.
  - **Operator root.** The operator's perceived home is the
    sessions list; breadcrumbs start at `Sessions` →
    `/operator/sessions`. On `/operator/sessions` itself, the trail
    is the single non-link label `Sessions`.
  - **Reviewer root.** The reviewer's perceived home is the list of
    sessions they are invited to (the page at `/reviewer`);
    breadcrumbs start at `Reviewer` → `/reviewer`. On `/reviewer`
    itself, the trail is the single non-link label `Reviewer`.
- **Page title.** The page's H1, rendered below the breadcrumb.

### Page layout — two-column option

For pages whose content naturally splits into two parallel groupings
(e.g. session detail's *Session Details + Run Session* alongside
*Session Setup*), the default layout is a two-column CSS grid via
`.page-grid` in `base.html`:

- Two equal-width columns (`grid-template-columns: 1fr 1fr`,
  `gap: 20px`, `align-items: stretch`) so the columns share the
  page's full width and end at the same vertical position.
- The left column (`.col-left`) is a flex column with
  `justify-content: space-between` — its first card pins to the
  top, its last card to the bottom. The right column (`.col-right`)
  has its single card grow (`flex: 1`) to fill the column height.
  Result: top and bottom edges of the two columns are flush.
- Below 800px viewport, the grid collapses to a single column so
  the page reads as a vertical stack on mobile.
- Cards that should sit *outside* the two-column section (full-page
  width — e.g. context-sensitive overlays, danger zones) are
  rendered as siblings after the closing `.page-grid` div. Apply
  `.card-half` (max-width: `calc(50% - 10px)`) when a follow-up
  card should occupy only half the page width.

This is one valid default; pages whose body is a single linear flow
(forms, list/detail tables) keep their existing single-column
layout.

## `/operator/sessions` — Sessions list

- Table of sessions, one row per session. Columns: **Name**,
  **Code**, **Status**, **Deadline**, **Created**, plus two
  per-row buttons:
  - **Access** — replaces the previous Name link; opens the session
    detail.
  - **Delete**
- Below the table:
  - **Create new session** button.

## `/operator/sessions/{id}` — Session detail

- **Session** card: session details, status, **Edit details** button.
- **Session setup** card — table. Each row's **Manage** button links
  to the matching subpage (listed below):
  - **Reviewers** row: number, status, **Manage** →
    `/operator/sessions/{id}/reviewers`.
  - **Reviewees** row: number, status, **Manage** →
    `/operator/sessions/{id}/reviewees`.
  - **Instruments** row: count, status summary, **Manage** →
    `/operator/sessions/{id}/instruments` (single index page; one
    card per instrument, with add / edit / delete).
  - **Assignments** row: number, mode, **Manage** →
    `/operator/sessions/{id}/assignments`.
  - **Set up invites** row: number, status, **Manage** →
    `/operator/sessions/{id}/setupinvite` (email template).
- **Run Session** card:
  - **Validate Session Setup** — pressing this surfaces an inline
    summary card on the session detail (error / warning / info
    counts plus the activate-readiness verdict). The summary card
    includes a **View detailed validation** button →
    `/operator/sessions/{id}/validate` for the full per-issue
    breakdown.
  - **Preview reviewer surface** button →
    `/operator/sessions/{id}/preview` (operator-only read-only
    render of what reviewers will see; bypasses session-status /
    deadline / acceptance gates).
  - **Manage Invitations** button →
    `/operator/sessions/{id}/invitations` (managing the invitations:
    sending, link to outbox, etc.).
  - **Extract Data** button.
- **Danger zone** card:
  - **Delete Data** button — wipes collected response data only;
    setup items (reviewers, reviewees, instruments, assignments,
    invitations) stay.
  - **Delete Session** button — removes everything for the session.

## `/operator/sessions/{id}/reviewers` — Reviewers

- **Reviewers** card: numbers, **Upload CSV** button, **Edit
  Reviewers** button. **Edit Reviewers** turns the table below into an
  inline-editable table on the same page (not yet implemented).
- Table of reviewers.
- **Danger Zone**: **Delete** button.

## `/operator/sessions/{id}/reviewees` — Reviewees

Analogous to the reviewers page:

- **Reviewees** card: numbers, **Upload CSV** button, **Edit
  Reviewees** button. **Edit Reviewees** turns the table below into an
  inline-editable table on the same page (not yet implemented).
- Table of reviewees.
- **Danger Zone**: **Delete** button.

## `/operator/sessions/{id}/assignments` — Assignments

- **Assignments** card: numbers, **Upload CSV** button, **Assign by
  Rules** button, **Edit Assignments** button.
  - **Assign by Rules** reveals an additional card above the
    assignments table. The card hosts the rules editor and exposes a
    **Cancel** button that dismisses the card without saving. (No
    separate `/assignments/rules` URL; the rules engine itself is
    deferred — the card renders a placeholder until it lands.)
  - **Edit Assignments** turns the table below into an
    inline-editable table on the same page (not yet implemented).
- Table of assignments.
- **Danger Zone**: **Delete** button.

## `/operator/sessions/{id}/instruments` — Instruments

A single consolidated page for everything per-instrument: top-level
count, session-wide settings, and one card per instrument with
in-place editing for description, response fields, and display
fields. Multi-instrument support stays deferred to Segment 13;
single-instrument sessions render exactly one per-instrument card.

- **Instruments header card:** count, **Add instrument** button
  (deferred until Segment 13), **Preview reviewer surface** button
  → `/operator/sessions/{id}/preview`.
- **Instruments Settings card** (session-wide): bulk
  **Open all instruments** / **Close all instruments** toggles for
  every instrument's `accepting_responses`. Three-state pill (`all
  on` / `all off` / `mixed`). Ready-only (visible always; the
  toggles activate when the session is `ready` and pre-deadline).
- **One card per instrument** with:
  - System-handle pill (`Instrument.name`, e.g. `instrument_1`),
    immutable.
  - **Friendly description** form — the operator-visible heading
    that the reviewer surface uses as the section title (falls
    back to the system handle when empty).
  - **Acceptance** form — open / close `accepting_responses`;
    deadline status; `responses_visible_when_closed` toggle on
    the same card.
  - **Display fields** table — read-only columns shown to
    reviewers alongside the always-first reviewee-identity column.
    Operator manages: per-row inline **Edit** (label override +
    visibility), per-row **Delete**. Below the table, an **Add
    display field** form with a single combined source select over
    the seven D6 sources (`reviewee.tag_1/2/3`,
    `reviewee.profile_link`, `pair_context.1/2/3`) minus those
    already on the instrument; the form hides itself when all
    seven are present.
  - **Response fields** table — the reviewer-side answer columns.
    Operator manages: per-row inline **Edit**, per-row **Delete**
    (cascade-confirms when answers exist), per-row up/down
    **Move**, plus a per-field **Help text** + visibility toggle.
    Below the table, an **Add field** form (label, key auto-derived
    from label when blank, type, validation, required, help text).
  - **Field order & visibility** bulk form — operator-chosen
    interleaved order across both display and response fields.
    Per-row numeric `order`, plus `visible` checkbox + `label`
    override on display rows; response rows carry only `order`.
    On save the per-table orders repack to `0..N-1` independently.
  - **Delete instrument** button (deferred until Segment 13).
- Description / display-field / response-field mutations (and the
  bulk save) flip a `validated` session back to `draft`. They
  return HTTP 409 when the session is `ready`. The Acceptance and
  bulk-accepting toggles deliberately do **not** invalidate.

The legacy per-instrument page at
`/operator/sessions/{id}/instruments/{instrument_id}` 303s to the
consolidated index for back-compat.

## `/operator/sessions/{id}/preview` — Preview reviewer surface

Operator-only, read-only render of the reviewer surface. Reachable
from the **Preview reviewer surface** anchor on the instruments
header card and from the same-named anchor on the session detail's
Run Session card.

- **"Preview — not visible to reviewers" banner** at the top.
  Calls out that the page bypasses session-status / deadline /
  acceptance gates and is operator-only.
- Renders **three rows**: real assignments first (by
  `Assignment.id` ascending; up to three), padded with synthetic
  placeholders (`Sample Reviewee 1/2/3`, `sample1@example.edu`,
  per-source sample values for display cells) when fewer real
  assignments exist.
- Every input renders disabled. The Save / Submit / Clear / Cancel
  forms are suppressed (the `<form>` wrapper is replaced with a
  plain `<div>` so no `formaction=` can re-target a write
  endpoint).
- Works in any session status (`draft` / `validated` / `ready`).
- Read-only: does not invalidate, emits no audit events, and
  deliberately skips the lazy deadline-observation side effect.

## `/operator/sessions/{id}/setupinvite` — Set up invites

_Placeholder — to be specified. Own page (rather than inline on the
session detail) because the email-template editor is heavier than
the rest of session setup. Hosts the invitation email template.
Reached from the **Set up invites** row's Manage button on the
session detail._

## `/operator/sessions/{id}/invitations` — Manage invitations

_Placeholder — to be specified. Hosts invitation management:
sending, link to outbox, etc. Reached from the **Manage Invitations**
button on the session detail._

## `/about` — About

_Placeholder — to be specified. Reached from the app-identity text
at the top left of every operator page._
