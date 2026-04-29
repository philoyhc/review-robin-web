# Target operator page map

Work-in-progress specification of the *intended* operator-facing page
surface. This is the design target, not what currently ships — see
`spec/operator_map.md` for today's implementation. Pages are added as
they are specified.

## `/operator/sessions` — Sessions list

- Table of sessions, one row per session, with two per-row buttons:
  - **Access**
  - **Delete**
- Below the table:
  - **Create new session** button
  - **Sign out** button

## `/operator/sessions/{id}` — Session detail

- **Session** card: session details, status, **Edit details** button.
- **Session setup** card — table:
  - **Reviewers** row: number, status, **Manage** button.
  - **Reviewees** row: number, status, **Manage** button.
  - **Instrument 1** row: status, **Manage** button. Always present.
  - **Instrument 2…6** rows: status, **Manage** button, **Delete**
    button. Each row only exists if the operator has added that
    instrument; capped at 6 instruments total. (Add-instrument
    affordance: TBD.)
  - **Assignments** row: number, mode, **Manage** button.
  - **Invitations** row: number, status, **Manage** button.
- **Run Session** card:
  - **Validate Session Setup** button
  - **Manage Invitations** button
  - **Extract Data** button
- **Danger zone** card:
  - **Delete Data** button — wipes collected response data only;
    setup items (reviewers, reviewees, instruments, assignments,
    invitations) stay.
  - **Delete Session** button — removes everything for the session.
- Back link/button → `/operator/sessions`.
