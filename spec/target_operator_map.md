# Target operator page map

Work-in-progress specification of the *intended* operator-facing page
surface. This is the design target, not what currently ships — see
`spec/operator_map.md` for today's implementation. Pages are added as
they are specified.

## Cross-page conventions

Every operator page renders the same chrome before its body:

- **App identity (top left).** The text "Review Robin Web App
  (version {num})" rendered small (not large heading), as a link to
  `/operator/sessions`.
- **User card (top right).** A small card with "Signed in as
  {user name}" and a **Sign out** button. The Sign out button posts /
  links to `/.auth/logout`.
- **Breadcrumb trail (top left, just below the app identity).**
  Reflects the page's position in the operator hierarchy (e.g.
  `Sessions › {session name} › Reviewers`). Each segment except the
  current page is a link to that ancestor page. Breadcrumbs replace
  per-page back-link buttons, so individual page specs below do not
  list a separate back link, and individual page specs do not list a
  separate Sign out control either.
- **Page title.** The page's H1, rendered below the breadcrumb.

## `/operator/sessions` — Sessions list

- Table of sessions, one row per session, with two per-row buttons:
  - **Access**
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
  - **Validate Session Setup** button.
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

## `/operator/sessions/{id}/instruments` — Instruments index

- **Instruments** card: count, status summary, **Add Instrument**
  button (deferred until multi-instrument support lands).
- One card per instrument, each with: instrument name, status pill,
  **Manage** → `/operator/sessions/{id}/instruments/{instrument_id}`,
  **Delete** button (the lone first instrument is not deletable).

## `/operator/sessions/{id}/instruments/{instrument_id}` — Instrument

_Placeholder — to be specified. Single-instrument sessions still
address the lone instrument as `.../instruments/1` (etc.); the path
always includes the instrument id._

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
