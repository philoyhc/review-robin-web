# Target operator page map

Work-in-progress specification of the *intended* operator-facing page
surface. This is the design target, not what currently ships — see
`spec/operator_map.md` for today's implementation. Pages are added as
they are specified.

## Cross-page conventions

- **Breadcrumb navigation.** Every page renders a breadcrumb trail at
  the top reflecting its position in the operator hierarchy (e.g.
  `Sessions › {session name} › Reviewers`). Each segment except the
  current page is a link to that ancestor page. Breadcrumbs replace
  per-page back-link buttons, so individual page specs below do not
  list a separate back link.

## `/operator/sessions` — Sessions list

- Table of sessions, one row per session, with two per-row buttons:
  - **Access**
  - **Delete**
- Below the table:
  - **Create new session** button
  - **Sign out** button

## `/operator/sessions/{id}` — Session detail

- **Session** card: session details, status, **Edit details** button.
- **Session setup** card — table. Each row's **Manage** button links
  to the matching subpage (listed below):
  - **Reviewers** row: number, status, **Manage** →
    `/operator/sessions/{id}/reviewers`.
  - **Reviewees** row: number, status, **Manage** →
    `/operator/sessions/{id}/reviewees`.
  - **Instrument 1** row: status, **Manage** →
    `/operator/sessions/{id}/instruments/{instrument_id}`. Always
    present.
  - **Instrument 2…6** rows: status, **Manage** →
    `/operator/sessions/{id}/instruments/{instrument_id}`, **Delete**
    button. Each row only exists if the operator has added that
    instrument; capped at 6 instruments total. (Add-instrument
    affordance: TBD.)
  - **Assignments** row: number, mode, **Manage** →
    `/operator/sessions/{id}/assignments`.
  - **Invitations** row: number, status, **Manage** →
    `/operator/sessions/{id}/invitations`.
- **Run Session** card:
  - **Validate Session Setup** button
  - **Manage Invitations** button
  - **Extract Data** button
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

Analogous to the reviewers / reviewees pages:

- **Assignments** card: numbers, **Upload CSV** button, **Edit
  Assignments** button. **Edit Assignments** turns the table below
  into an inline-editable table on the same page (not yet
  implemented).
- Table of assignments.
- **Danger Zone**: **Delete** button.

## `/operator/sessions/{id}/invitations` — Invitations

_Placeholder — to be specified._

## `/operator/sessions/{id}/instruments/{instrument_id}` — Instrument

_Placeholder — to be specified. Single-instrument sessions still
address the lone instrument as `.../instruments/1` (etc.); the path
always includes the instrument id._
