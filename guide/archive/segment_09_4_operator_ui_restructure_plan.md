# Segment 9.4 Plan — Operator UI restructure to target page map

**Status:** Plan for a single PR. Sits between Segment 9.2 (shipped)
and Segment 9.3 (monitoring + reminders, not yet shipped). Treats the
operator pages as the segment's surface; backend behavior is
unchanged unless explicitly noted.

## Goal

Refactor the operator-facing HTML so that the live app matches
`spec/target_operator_map.md` for the pages whose target shape is
already decided, and pre-positions stub routes for the pages whose
target shape is decided-but-deferred. After 9.4 the operator's
mental model and URL space match the spec; behavior for deferred
features (inline-editable tables, RuleBased rules engine, real email
templating, multi-instrument index, response-data wipe) is still
absent — but the navigation funnels point at the right targets so
later segments can land them as additive PRs.

## Scope summary

This is a UI restructure. No new domain behavior other than:
- A new `Delete data` action on session detail that wipes responses
  while leaving setup intact (small new audit event).
- A breadcrumb partial used by every operator template.
- A global page chrome (app identity + signed-in user card) that
  replaces the existing topbar.

Everything else maps existing services / routes onto the target page
shapes.

## Cross-page chrome and breadcrumbs

Replaces today's topbar on both the operator and the reviewer
surfaces. Implemented in `app/web/templates/base.html` plus a new
`_partials/breadcrumb.html`.

- **Top left.** Small "Review Robin Web App (version {num})" text
  (not a large heading), linked to `/about`. The version string
  comes from a single source (`app.config.APP_VERSION`, set to
  `"dev"` in 9.4; pipeline-driven version bumping is out of scope).
  Operators navigate to the sessions list via the breadcrumb, not
  the app-identity text.
- **Top left, just below the app identity.** Breadcrumb trail.
  Each page passes a list of `(label, url|None)` tuples; the last
  tuple has `url=None` and renders as a plain non-link label
  marking the current page. Breadcrumb roots:
  - **Operator pages:** `Sessions` → `/operator/sessions`. On
    `/operator/sessions`, the trail is the single non-link label
    `Sessions`.
  - **Reviewer pages:** `Reviewer` → `/reviewer`. On `/reviewer`,
    the trail is the single non-link label `Reviewer`.
- **Top right.** Small card containing "Signed in as {user name}"
  and a **Sign out** button → `/.auth/logout`.
- **Page H1.** Rendered below the breadcrumb in the page body.

Per-page back links and per-page Sign out controls are removed — the
chrome carries both. The reviewer surface inherits the chrome too;
its existing inline navigation stays as-is below the H1.

## Decisions on open design notes (now closed)

The spec previously carried three undecided alternatives. 9.4 closes
them as follows; the spec's "Open design notes" section is removed
in Slice 1.

### Note 1 — `setupinvite` page vs. inline on session detail

**Decision: keep its own page.**

- Pros of own page: clean URL, full canvas for a non-trivial editor
  (subject + body + token preview + "send test" later), can land in
  isolation in the email-templates segment.
- Cons of own page: one extra hop for a piece of setup the operator
  visits ~once per session.
- Pros of inline: zero navigation; setup feels co-located.
- Cons of inline: bloats `/operator/sessions/{id}` (already the
  hub); editor states (preview, validation, save) entangle the hub
  template; harder to gate with the existing edit-lock predicate.

Net: the email-template UI is heavier than the rest of session
setup; better as a sibling page reached from the **Set up invites**
row's Manage button.

### Note 2 — `/assignments/rules` page vs. inline toggleable card

**Decision: inline toggleable card on `/assignments`.**

- Pros of inline: rules iteration is a tight loop ("tweak rule →
  preview → tweak again → save"); already symmetric with today's
  FullMatrix preview pattern; **Cancel** button cleanly dismisses.
- Cons of inline: the assignments page grows; two card-modes
  (browse vs. compose) coexist.
- Pros of own page: bookmarkable; uncluttered.
- Cons of own page: more clicks for the iterative loop; second-class
  to the FullMatrix flow which is already inline.

Net: keeping rules adjacent to the resulting pairs is the right UX
shape. The reserved `/assignments/rules` URL goes away.

### Note 3 — One `/instruments` index vs. Instrument 1…6 rows

**Decision: collapse to a single Instruments row → `/instruments`
index page.**

- Pros: scales naturally past one (Segment 13 lands multi-instrument);
  add / delete / reorder live in one place; matches the
  reviewers / reviewees / assignments page pattern.
- Cons: one extra hop for the common single-instrument case; loses
  per-instrument open/closed pill from the session detail.
- Pros of per-row: at-a-glance instrument status from the hub.
- Cons of per-row: arbitrary cap at 6, unbalanced row layout (Add
  vs. Delete affordances), and the row count itself is data the hub
  shouldn't have to know about.

Net: a single index page is the structurally right answer and
matches the rest of the table; the per-instrument detail page
already exists today and stays as the index's row click-through.

## What ships today vs. what 9.4 changes

Implemented and structurally close to the target — needs reshaping
or new buttons:

| Today | 9.4 change |
|---|---|
| `GET /operator/sessions` (table with one big link per row) | Keep today's Name / Code / Status / Deadline / Created columns. Replace the per-row Name link with an **Access** button; add a **Delete** button per row; replace the top "Create session" link with a **Create new session** button below the table. Sign out lives in the top-right user card now, not below the table. |
| `GET /operator/sessions/{id}` (cards stacked freely) | Restructure into four cards: **Session** (details + Edit details), **Session setup** (table with one row each for Reviewers / Reviewees / Instruments / Assignments / Set up invites), **Run Session** (Validate Session Setup, Manage Invitations, Extract Data), **Danger zone** (Delete Data, Delete Session). |
| `GET /operator/sessions/{id}/reviewers` (Manage view) | Promote the existing `/reviewers/import` form to a button on the Manage page (POST to a new combined endpoint). Add a disabled **Edit Reviewers** button (placeholder for the inline-editable mode, not yet implemented). |
| `GET /operator/sessions/{id}/reviewees` | Same shape as reviewers. |
| `GET /operator/sessions/{id}/assignments` | Add an **Assign by Rules** button that toggles a placeholder rules card above the pairs table; add disabled **Edit Assignments** button. Keep the Upload CSV (manual import) and FullMatrix flows as today. |
| `GET /operator/sessions/{id}/invitations` (per-reviewer table) | Add a link to `/outbox` from this page; remove the "View outbox" button from session detail (it's only reachable via Manage Invitations now). |
| `GET /operator/sessions/{id}/instruments/{instrument_id}` | Reachable from a new `/instruments` index page rather than an inline list on session detail. |
| `GET /operator/sessions/{id}/outbox` | No structural change; reached via the invitations page. |

New surface added by 9.4:

- `GET /operator/sessions/{id}/instruments` — index page listing one
  card per instrument. Today every session has exactly one
  Instrument; the page shows a single card. Add-instrument and
  delete-instrument are stubbed (server returns 501 for now;
  Segment 13 lights them up).
- `POST /operator/sessions/{id}/delete-data` — wipes every
  `Response` row for the session, preserves all setup, requires a
  confirm checkbox. Emits `responses.deleted_all` audit event.
- `GET /operator/sessions/{id}/setupinvite` — placeholder page with
  the "email template editor coming in Segment 15" notice and a
  back-breadcrumb. No POST routes yet.
- `GET /operator/sessions/{id}/extract` — placeholder page with the
  "Extract Data coming in Segment 11" notice. No POST routes.
- `GET /about` — short stub page; target of the chrome's
  app-identity link.

## Implementation slices

### Slice 1 — Spec sync + page chrome + breadcrumb plumbing

- Update `spec/target_operator_map.md` (spec sync): drop the Open
  design notes section, fold Decisions 1/2/3 into the existing page
  sections (drop the rules placeholder; collapse Instruments rows
  into a single row pointing at `/instruments`).
- Replace the existing topbar in `base.html` with the new chrome:
  - Top-left "Review Robin Web App (version {num})" link.
  - Top-right user card with "Signed in as {name}" + Sign out.
  - Slot for breadcrumbs below the app identity.
  - Slot for the page H1 in the page body.
- Add `app/web/templates/_partials/breadcrumb.html`. Pass an empty
  crumb list from every existing operator template so the partial
  renders a blank trail until later slices populate it.
- Remove the per-template `← Back` `<a>` links at the top of each
  operator template.

### Slice 2 — Sessions list + session detail restructure

- Sessions list: per-row **Access** + **Delete** buttons (Delete
  uses the existing `/delete` POST + confirm). Move "Create new
  session" to a button below the table. (Sign out is in the chrome
  now, not under the table.)
- Session detail: replace the current ad-hoc body with the four
  cards specified. The Setup table gets its rows from a single
  service helper that returns `[(label, count_or_status, manage_url,
  optional_delete_url)]`; today this is hard-coded to:
  reviewers / reviewees / instruments (collapsed) / assignments /
  setup invites.
- Drop the existing "Run setup validation" / "Validate & activate"
  / "Invitations" links from the legacy layout — they live in the
  new **Run Session** card now.
- **Validate Session Setup** posts back to the session detail and
  surfaces an inline summary card (errors / warnings / info counts
  + readiness verdict) above the Run Session card. The summary
  card carries a **View detailed validation** button linking to
  today's `/operator/sessions/{id}/validate` page (no behaviour
  change to that page itself).
- The Activate flow moves onto the inline summary card (it needs
  the readiness verdict anyway): when there are no blocking errors
  the card renders the **Activate session** form (with the
  existing `acknowledge_warnings` checkbox path). **Revert to
  draft** stays as a contextual button on the Session card per the
  existing edit-lock UX.

### Slice 3 — Reviewers / reviewees / assignments page reshape

- Fold each `…/import` GET into the parent Manage page: the
  **Upload CSV** button on the Manage page opens a file-input form
  on the same page (anchored card) and POSTs to the existing
  `…/import` endpoint. The standalone `…/import` GET routes are
  removed once the inline form ships.
- Add a disabled **Edit Reviewers / Reviewees / Assignments** button
  with a tooltip "inline editing — coming soon". No new endpoint.
- Assignments page: add an **Assign by Rules** button that toggles a
  placeholder card containing only a "Rule editor — Segment 12"
  notice and a **Cancel** button. Card has no POST yet.

### Slice 4 — Instruments index + placeholder pages

- New `GET /operator/sessions/{id}/instruments`: lists one card per
  instrument with name, current `accepting_responses` pill, link to
  the existing per-instrument detail page. Single-instrument
  sessions render exactly one card. **Add instrument** and
  **Delete instrument** buttons are present but disabled with a
  "Multi-instrument — Segment 13" tooltip.
- New `GET /operator/sessions/{id}/setupinvite`: stub page with the
  "Email template editor — Segment 15" notice.
- New `GET /operator/sessions/{id}/extract`: stub page with the
  "Extract Data — Segment 11" notice.
- New `GET /about`: stub page (single short paragraph + version
  string). Targets the chrome's app-identity link.

### Slice 5 — Delete Data + Danger zone wiring

- New `POST /operator/sessions/{id}/delete-data`: deletes every
  `Response` row for the session in one transaction; preserves
  reviewers / reviewees / assignments / instruments / invitations
  intact. Confirm checkbox required. Allowed in any session status.
  Emits a single `responses.deleted_all` audit event with
  `detail = {"deleted_count": N}`.
- Wire **Delete Data** + **Delete Session** buttons under the new
  **Danger zone** card on session detail.

### Slice 6 — Tests + docs

- ~10 tests, SQLite via the existing harness:
  1. Sessions list renders **Access** + **Delete** per row.
  2. "Create new session" button posts to `/operator/sessions`.
  3. Session detail renders the four-card layout with the new Setup
     table (label, value, manage URL).
  4. Session setup table collapses instruments into a single row
     linking to `/instruments`.
  5. Instruments index renders one card per instrument with the
     correct `accepting_responses` pill.
  6. Add / delete-instrument controls render as disabled.
  7. Reviewers / reviewees / assignments Manage pages render the
     **Upload CSV** card-toggle form and a disabled **Edit** button.
  8. Assignments page renders an **Assign by Rules** toggleable card
     with a Cancel button; toggling does not call any endpoint.
  9. `POST /delete-data` wipes responses and leaves setup rows
     intact; confirm checkbox required.
  10. Breadcrumb partial renders the expected trail on each page,
      with the operator root (`Sessions`) and the reviewer root
      (`Reviewer`) each rendering as a non-link label on their own
      root page.
  11. Chrome renders the app-identity link, the signed-in user
      name, and a Sign out button on every operator and reviewer
      page.
  12. Validate Session Setup on session detail renders an inline
      summary card with counts + a View detailed validation button
      that targets `/operator/sessions/{id}/validate`.
  11. Chrome renders the app-identity link, the signed-in user
      name, and a Sign out button on every operator page.
- `docs/status.md`: add Segment 9.4 row; refresh the operator URL
  table (drop `…/reviewers/import` and `…/reviewees/import` GETs;
  add `…/instruments`, `…/setupinvite`, `…/extract`,
  `…/delete-data`).
- `spec/operator_map.md`: regenerate (or note as stale) at the end of
  the segment so the "as-is" map matches the new layout.

## Out of scope (explicitly deferred)

- **Inline-editable tables** for reviewers / reviewees / assignments
  — buttons render but are disabled. Lands later when the
  inline-edit pattern is designed once and reused across all three.
- **`/assignments/rules` rule engine** — placeholder card only;
  Segment 12 (RuleBased) lights it up.
- **`/setupinvite` email template editor** — placeholder page only;
  real templating + `Send test` lands with the real-SMTP work
  (Segment 15).
- **`/extract` data export** — placeholder page only; Segment 11.
- **Add / delete instruments** — the index page renders the cards,
  but the buttons are disabled until Segment 13 (multi-instrument).
- **Session-status changes** — activation, revert, edit-lock all
  keep today's semantics; only the UI placement moves.
- **Sign-out behavior** — reuses the existing `/.auth/logout` link;
  no auth changes (the chrome's Sign out button targets the same URL).
- **Version string source** — `app.config.APP_VERSION = "dev"` for
  9.4. Pipeline-driven version bumping (e.g. reading the deployed
  build SHA) is out of scope.

## Pre-positioned placeholders summary

| Surface | Status after 9.4 | Lands in |
|---|---|---|
| Edit Reviewers / Reviewees / Assignments inline tables | button rendered, disabled | follow-on UX PR |
| `/assignments` Assign by Rules toggleable card | card toggles, no POST | Segment 12 |
| `/setupinvite` page | stub page, no POST | Segment 15 |
| `/extract` page | stub page, no POST | Segment 11 |
| `/instruments` index page | renders today's single instrument; Add / Delete disabled | Segment 13 |
| Per-instrument detail (`/instruments/{iid}`) | unchanged from 9.1 | (already shipped) |

## Risk notes

- **Breadcrumbs touch every operator template.** Land them in
  Slice 1 with empty crumb lists everywhere; later slices fill in
  the trails per page. Avoids a single sprawling diff.
- **Session detail is the riskiest template.** Behavior on it
  (activate, revert, edit-lock banners, response-loss banners)
  must keep working through the restructure. Snapshot the existing
  template's user flows in tests before refactoring.
- **`/reviewers/import` GET removal.** Any external bookmark / link
  to that URL becomes a 404. Today it's only linked from the
  reviewers Manage page, so safe to drop; flag in `docs/status.md`.
- **Spec/code drift is real if 9.4 doesn't land cleanly.** If the
  segment is split, keep Slice 1 (spec sync + breadcrumbs) atomic so
  later slices reference a single source of truth.
