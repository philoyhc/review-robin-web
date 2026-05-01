# Segment 9.4A Implementation Plan — Page chrome + breadcrumbs + sessions list reshape

**Status:** First of three PR-sized blocks for Segment 9.4 (operator
UI restructure to the target page map). 9.4A lays the foundational
chrome + breadcrumb plumbing and reshapes the sessions list.

- **9.4A (this doc):** chrome, breadcrumbs, `/about`, sessions list reshape.
- **9.4B (next):** session detail four-card restructure + inline
  validate-summary card + `Delete Data`.
- **9.4C (last):** reviewers / reviewees / assignments Manage page
  reshapes, instruments index, `/setupinvite` + `/extract` stubs,
  closing-segment doc + spec refresh.

See `segment_09_4_operator_ui_restructure_plan.md` for the
segment-level plan and `spec/target_operator_map.md` for the design
target.

---

## 9.4A outcome

One PR that ships:

- A new global page chrome on `base.html` (app-identity link top-left,
  user card top-right, breadcrumb slot below the app identity, page-H1
  slot in the body) replacing today's topbar.
- A new `_partials/breadcrumb.html` partial fed by a `breadcrumbs`
  context value passed from every template render. Trails populated
  for every existing operator and reviewer page.
- A new `/about` stub page so the chrome's app-identity link works
  end-to-end.
- A new `app.config.app_version = "dev"` setting exposed as a Jinja
  global.
- The sessions list reshaped: per-row **Access** + **Delete** buttons,
  **Create new session** button moved below the table.
- Per-page `← Back` `<a>` links removed from every operator and
  reviewer template (the chrome's breadcrumbs replace them).

Behavior unchanged otherwise: session detail still uses today's
ad-hoc layout, the Manage pages still use today's standalone import
GETs, nothing changes on the reviewer write path.

---

## Decisions locked for 9.4A

1. **`/about` lands in 9.4A** (not Slice 4 of the segment plan). The
   chrome's app-identity text is a link to `/about`; shipping the
   chrome without `/about` would 404 the link until 9.4C. Stub: H1
   "About", one short paragraph, displays the version string. Public
   route (no Easy Auth) so it works on the sign-in page too.
2. **Breadcrumb trails populated everywhere in 9.4A.** Every existing
   operator and reviewer template passes a real crumb list, not an
   empty one. The segment plan's "empty everywhere, fill later"
   approach is rejected — the partial-call is one line per template
   either way, and populated trails make 9.4A reviewable as a
   finished change.
3. **Reviewer surface inherits chrome + breadcrumbs.** `dashboard.html`
   → `Reviewer`. `review_surface.html` → `Reviewer / {session name}`.
   `invite_mismatch.html` → `Reviewer / Access denied`.
4. **Sessions-list per-row Delete** links to
   `/operator/sessions/{id}#danger-zone` (anchored at the session
   detail's existing Danger-zone form). Reuses today's
   confirm-checkbox flow; no new POST endpoint, no new confirm modal.
   Rendered for every row regardless of status — `ready` sessions
   land on the existing "deletion locked while ready" message at the
   anchor, matching today's UX.
5. **`spec/target_operator_map.md` is already synced.** Open design
   notes section is gone, Decisions 1/2/3 are folded in,
   `/about` is documented as a placeholder. 9.4A only edits this spec
   if a verify-pass surfaces stale wording.
6. **`spec/operator_map.md` (as-is map) deferred to 9.4C.** The
   sessions list reshapes here, but session detail and Manage pages
   keep changing through 9.4B/C; regenerating the as-is map three
   times is wasteful. Single regen at the end of 9.4C.
7. **`docs/status.md`: per-sub-PR row** — matches 9.1A/9.2A/9.3A
   precedent (each sub-PR landed its own row).

---

## Implementation slices

### Slice 1 — Config + chrome + breadcrumb partial

- `app/config.py`: add `app_version: str = "dev"` to `Settings`.
- New `app/web/breadcrumbs.py` with factory functions returning a list
  of `(label, url | None)` tuples. The last tuple always has
  `url=None` (current page, non-link). Helpers:
  - `operator_root()` — `[("Sessions", None)]`
  - `operator_session(session)` —
    `[("Sessions", "/operator/sessions"), (session.name, None)]`
  - `operator_session_child(session, label)` —
    `[("Sessions", "/operator/sessions"),
       (session.name, f"/operator/sessions/{session.id}"),
       (label, None)]`
  - `reviewer_root()` — `[("Reviewer", None)]`
  - `reviewer_session(session)` —
    `[("Reviewer", "/reviewer"), (session.name, None)]`
  - `reviewer_invite_mismatch()` —
    `[("Reviewer", "/reviewer"), ("Access denied", None)]`
- New `app/web/templates/_partials/breadcrumb.html`. Iterates
  `breadcrumbs` (default `[]`); renders linked tuples as `<a>`,
  unlinked tuples as plain `<span>`, joined by `/`. Empty list
  renders nothing.
- Rewrite `app/web/templates/base.html`:
  - Top-left: small `<a href="/about">Review Robin Web App (version
    {{ app_version }})</a>` text (not a heading).
  - Below the app identity: `{% include "_partials/breadcrumb.html" %}`.
  - Top-right: small card with `Signed in as {{ user.display_name or
    user.email }}` and a **Sign out** button → `/.auth/logout`.
    Hidden when `user` is unset.
  - Body still hosts `{% block content %}` — page H1 stays in the body.
- Expose `app_version` as a Jinja global at router init time:
  `_templates.env.globals["app_version"] = settings.app_version` in
  `routes_operator.py`, `routes_reviewer.py`, and the new about
  router. One line per router, no per-route plumbing.

### Slice 2 — Plumb breadcrumbs through every existing template

- Every `_templates.TemplateResponse(...)` call in
  `app/web/routes_operator.py` and `app/web/routes_reviewer.py` adds
  `"breadcrumbs": breadcrumbs.<factory>(...)` to its context dict.
- Remove per-template back-links from these operator templates:
  `session_detail.html`, `session_edit.html`, `session_validate.html`,
  `session_reviewers.html`, `session_reviewees.html`,
  `session_import_reviewers.html`, `session_import_reviewees.html`,
  `session_assignments.html`,
  `assignments_preview_full_matrix.html`,
  `assignments_preview_manual.html`, `instrument_detail.html`,
  `session_invitations.html`, `session_outbox.html`,
  `session_monitoring.html`.
- Remove the `← Your reviews` link from `reviewer/review_surface.html`.
- The `Cancel` `<a>` links inside forms (e.g. on
  `session_new.html`, `session_edit.html`) stay — those are form
  controls, not chrome.

### Slice 3 — Sessions list reshape

- `operator/sessions_list.html`:
  - Drop the link wrapping the Name cell — Name is plain text now.
  - Add two action columns at the right: **Access** (anchor to
    `/operator/sessions/{id}`, `btn secondary`) and **Delete**
    (anchor to `/operator/sessions/{id}#danger-zone`, destructive
    styling). No new endpoints.
  - Move the existing top "Create session" link to a
    **Create new session** button rendered *below* the table.
  - Empty-state card keeps the muted prompt; the **Create new
    session** button renders below the card too.
  - Keep `<h1>Your sessions</h1>` for screen-reader clarity (the
    chrome doesn't render the H1).
- `operator/session_detail.html`: add `id="danger-zone"` to the
  existing Danger-zone card so the per-row Delete anchor targets it.
  No other change here in 9.4A — the four-card restructure is 9.4B.

### Slice 4 — `/about` stub

- New `app/web/routes_about.py` with `GET /about` returning
  `about.html`. Public (no Easy Auth dependency) so the chrome link
  works on every page. Wire into `app/main.py`.
- New `app/web/templates/about.html`: H1 "About"; one short paragraph
  describing Review Robin Web; renders `version {{ app_version }}`.
  Empty `breadcrumbs` list (no canonical hierarchy — `/about` is
  reachable from anywhere via the chrome).

### Slice 5 — Tests (~10) in `tests/integration/test_chrome_breadcrumbs.py`

1. **Operator chrome.** `GET /operator/sessions` body contains the
   app-identity link with `version dev`, the signed-in user's name,
   and a Sign-out anchor pointing at `/.auth/logout`.
2. **Reviewer chrome.** `GET /reviewer` body contains the same three
   elements (shared via `base.html`).
3. **Breadcrumb on operator root.** `/operator/sessions` renders the
   single non-link label `Sessions` and no `<a>` to itself.
4. **Breadcrumb on session detail.** `/operator/sessions/{id}` renders
   `Sessions` as an `<a href="/operator/sessions">` and the session
   name as a non-link label.
5. **Breadcrumb on a nested operator page.**
   `/operator/sessions/{id}/reviewers` renders the three-tuple trail:
   `Sessions` link, session-name link, `Reviewers` non-link.
6. **Breadcrumb on reviewer root.** `/reviewer` renders the single
   non-link label `Reviewer`.
7. **Sessions list buttons.** Each row renders an **Access** button
   linking to `/operator/sessions/{id}` and a **Delete** button
   linking to `/operator/sessions/{id}#danger-zone`.
8. **Create-new-session button.** Renders below the table, links to
   `/operator/sessions/new`. (Old top-of-page "Create session" link
   no longer present.)
9. **`/about` reachable.** `GET /about` returns 200, body contains
   `version dev`, request succeeds without an Easy Auth header.
10. **Back-links removed.** `/operator/sessions/{id}/reviewers` no
    longer contains the `← {session name}` anchor (regression-guard
    for the "chrome replaces back-links" contract).

---

## Out of scope (explicitly deferred)

- **Session detail restructure** — four-card layout, setup-table
  service helper, inline validate-summary card with Activate flow
  on it. → 9.4B.
- **Delete Data** — `POST /operator/sessions/{id}/delete-data`,
  `responses.deleted_all` audit event. → 9.4B.
- **Reviewers / reviewees / assignments Manage reshapes** — fold
  `…/import` GETs into anchored Upload-CSV cards, disabled Edit
  buttons, Assign-by-Rules toggleable card. → 9.4C.
- **Instruments index page** —
  `GET /operator/sessions/{id}/instruments`. → 9.4C.
- **`/setupinvite` and `/extract` stubs.** → 9.4C.
- **`spec/operator_map.md` regen.** → 9.4C (after Manage reshapes
  land).
- **Pipeline-driven version string** — `APP_VERSION = "dev"` is the
  floor; deploy-SHA wiring is a Segment 14 concern.

---

## Docs to update at PR time

- `docs/status.md`:
  - Timeline row: `2026-04-NN | Segment 9.4A shipped (page chrome +
    breadcrumbs + sessions list reshape)`.
  - Segments-shipped row: `9.4A | Global page chrome (app identity +
    user card + breadcrumb), /about stub, sessions list per-row
    Access/Delete + Create-new-session button | <date>`.
  - UI / branding section: replace the topbar bullet (now stale)
    with a short paragraph on the new chrome + breadcrumb partial.
  - Operator URL table: add `GET /about`.
- `AGENTS.md`: bump "Current stage" to mention 9.4A.
- `spec/target_operator_map.md`: only if a verify-pass surfaces stale
  wording. The cross-page chrome and breadcrumb sections already
  match.
- `spec/operator_map.md`: do **not** touch in 9.4A; deferred to 9.4C.

---

## Risk notes

- **Wide diff, shallow changes.** Slice 2 touches every operator
  and reviewer route handler plus every template. Land Slice 1
  (factories + partial + base.html) atomically before the
  per-call additions, so reviewers can mentally model the contract
  before the wide change.
- **Existing tests assert on rendered HTML.** `test_list_shows_users_session`
  in `tests/integration/test_operator_sessions.py` checks for session
  name + code in the body — still passes (column values stay). Any
  test that asserts on the old `← All sessions` back-link or the
  topbar `<a href="/operator/sessions">Review Robin Web</a>` text
  needs updating; grep for `Review Robin Web` and `&larr;` in
  `tests/` before merging.
- **`/about` must be unauthenticated.** Mounting through the operator
  router would gate it behind Easy Auth and break the chrome link on
  the sign-in page. Use a public router (parallel to `/health`).
- **`me_debug.html` and other diagnostic pages.** Not in the operator
  router but extend `base.html`, so they pick up the new chrome
  automatically — verify they still render and pass an empty
  `breadcrumbs` list (or a sensible one) when their route handler
  calls `TemplateResponse`.
- **Session detail anchor target.** Adding `id="danger-zone"` to the
  existing card is the only change to `session_detail.html` in 9.4A.
  Avoid touching anything else there — 9.4B will rewrite the whole
  template and a noisy 9.4A diff makes 9.4B's review harder.
