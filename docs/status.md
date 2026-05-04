# Implementation status

**As of:** end of Segment 10D (2026-05-02)

This document is a periodic snapshot of what Review Robin Web actually
does today, vs. what is planned but not yet implemented. It is updated
at the end of each segment. Per-segment plans live in
`guide/segment_NN_*` and `guide/segment_NNA.md`.

For the full long-term plan see
`guide/low_intensity_workplan_review_robin_web.md`.

---

## Project timeline

| Date | Milestone |
|---|---|
| 2026-04-25 | GitHub repository created |
| 2026-04-26 | Azure subscription + App Service provisioned |
| 2026-04-27 | Postgres Flexible Server provisioned; Segments 1–4 shipped (skeleton, deploy, auth, data model) |
| 2026-04-28 | Segments 5–7 shipped (operator session MVP, imports + validation, assignment generation) |
| 2026-04-29 | Segment 8 shipped (reviewer surface MVP + roster status-filter retrofit) |
| 2026-04-29 | Segment 9.1 shipped (session activation lifecycle + per-instrument acceptance gates) |
| 2026-04-29 | Segment 9.2 shipped (per-reviewer invitations + dev outbox + token landing route) |
| 2026-04-29 | Segment 9.3 shipped (monitoring page + reminder send) |
| 2026-04-29 | Segment 9.4A shipped (page chrome + breadcrumbs + sessions list reshape + `/about`) |
| 2026-04-29 | Segment 9.4B shipped (session detail four-card restructure + inline validate-summary + Delete Data) |
| 2026-04-29 | Segment 9.4C shipped (Manage-page reshapes + instruments index + `/setupinvite` stub) |
| 2026-04-29 | Segment 9.5A shipped (`validated` lifecycle state + setup-mutation invalidation hooks) |
| 2026-04-30 | Segment 10A shipped (response-field builder + reviewer-surface loop-by-instrument refactor) |
| 2026-04-30 | Segment 10B-1 shipped (data-driven reviewer-surface render + display-field backfill) |
| 2026-04-30 | Segment 10B-2 shipped (operator display-field builder + shared field-order bulk form) |
| 2026-04-30 | Segment 10B-3 shipped (operator preview route — completes Segment 10B) |
| 2026-05-01 | Segment 10C shipped (operator UI clean-up: page-grid layouts, six-button setup nav, yellow lock-card pattern, per-instrument card refactor with live preview + Save/Edit lock toggle, multi-instrument schema/services landed UI-disabled) |
| 2026-05-02 | Segment 10D shipped (Instruments-page rebuild: state-machine-driven Display + Response Fields tables, Response Type Definitions card with cascade-delete UX, mutual-exclusion edit lock, multi-instrument enable) |

---

## Segments shipped

| Segment | What it added | Completed |
|---|---|---|
| 1 | Repository skeleton, `/health`, local dev install | 2026-04-27 |
| 2 | Azure App Service deployment via OIDC | 2026-04-27 |
| 3 | Microsoft Entra ID sign-in via Easy Auth | 2026-04-27 |
| 4 | 12-table schema + Alembic migration infra | 2026-04-27 |
| 5 | Postgres provisioning + migrate-on-deploy + operator session CRUD-lite | 2026-04-28 |
| 6 | Reviewer / reviewee CSV imports + setup validation | 2026-04-28 |
| 7 | FullMatrix + Manual assignment generation + roster Manage views | 2026-04-28 |
| 8 | Reviewer dashboard + review surface (save / submit / clear / cancel); active-only roster filter retrofit | 2026-04-29 |
| 9.1 | Session activation lifecycle (draft↔ready), edit-lock, per-instrument open/close, response-window gates | 2026-04-29 |
| 9.2 | Invitation generation + dev email outbox + `/reviewer/invite/{token}` landing route | 2026-04-29 |
| 9.3 | Per-session monitoring page + per-row and bulk reminder send | 2026-04-29 |
| 9.4A | Global page chrome (app identity + user card + breadcrumb), `/about` stub, sessions list per-row Access/Delete + Create-new-session button | 2026-04-29 |
| 9.4B | Session detail four-card layout (Session / Session setup / Run Session / Danger zone), inline validate-summary card via `?validated=1`, `POST /delete-data` with `responses.deleted_all` audit event | 2026-04-29 |
| 9.4C | Reviewers / reviewees / assignments Manage pages with anchored Upload-CSV cards and disabled Edit buttons; Assign by Rules placeholder card; `/operator/sessions/{id}/instruments` index page; `/operator/sessions/{id}/setupinvite` stub; setup-table Manage buttons for Instruments and Set up invites enabled | 2026-04-29 |
| 9.5A | `validated` stored state in `SessionStatus` (between `draft` and `ready`); `GET ?validated=1` flips draft→validated when no errors; activation now requires `is_validated`; setup-mutating routes (reviewer/reviewee/assignment import + delete-all + assignment generate + session edit) flip validated→draft via dedicated `session.validated` / `session.invalidated` audit events; instrument open/close/visibility and `/delete-data` deliberately do not invalidate | 2026-04-29 |
| 10A | Consolidated `/operator/sessions/{id}/instruments` page: per-instrument card with friendly description, acceptance + visibility toggles, response-fields table (add / edit / delete / reorder, per-field help text + visibility), session-wide Instruments Settings card with bulk Open all / Close all toggles. Migration adds `help_text` (Text, NULL) and `help_text_visible` (Bool, default true) on `instrument_response_fields`. Reviewer surface refactors to loop-by-instrument with section heading from `Instrument.description` (fallback to system handle) and a per-field help block above each table. Empty-instrument validation now blocks activation. Description / field mutations invalidate `validated → draft` via `lifecycle.invalidate_if_validated()` called from inside each mutating service (post-PR for items #3 + #16, 2026-05-02); bulk accepting + per-instrument open/close/visibility deliberately do not invalidate. Body width bumped from 900px to 1400px globally with a `.table-scroll` overflow utility. | 2026-04-30 |
| 10B-1 | Backfill migration (`c2143bd329c7`) seeds three `InstrumentDisplayField` rows (`source_type='pair_context'`, `source_field='1'|'2'|'3'`, `label=''`, `order=0..2`, `visible=true`) on every existing instrument; destructive within that filter (operator-typed labels on those slots are not preserved across upgrade); operator-added `reviewee` rows left intact. `ensure_default_instrument` seeds the same three rows on new sessions. Reviewer surface renders pair-context values as separate columns sourced from the display-field rows (no longer inline in the identity cell); reviewee identity (name + email) is the always-first column, mandatory and non-toggleable. New service helpers `display_field_label(field)` and `display_field_value(field, assignment)` cover the seven D6 sources (`reviewee.tag_1/2/3`, `reviewee.profile_link`, `pair_context.1/2/3`); empty/NULL labels fall back to inferred strings. `profile_link` cells render as plain `<a>`. No operator UI yet (picker + bulk form land in 10B-2; preview route in 10B-3). No new audit events. | 2026-04-30 |
| 10B-2 | Per-instrument display-fields card on `/operator/sessions/{id}/instruments`: Add (combined source picker over the seven D6 sources minus those already on the instrument; colon-delimited values like `reviewee:tag_1`), inline Edit (label override + visibility), Delete (no cascade-confirm — display fields carry no per-row dependent data). New shared "Field order & visibility" bulk form covering both display + response fields, interleaved in operator-chosen order, with per-table independent repack to `0..N-1` on save. Four new audit events: `instrument.display_field_added`, `instrument.display_field_updated`, `instrument.display_field_deleted`, `instrument.display_fields_saved` (D11 diff shape; `added` / `removed` always empty since adds + deletes are row-level only). Reuses 10A `instrument.fields_reordered` when bulk save reorders response fields. Display-field mutations invalidate `validated → draft` and 409 when `status=ready` (mirrors 10A). Rank-based change detection on bulk save means submitting current state is a no-op. | 2026-04-30 |
| 10B-3 | New `GET /operator/sessions/{id}/preview` route renders the reviewer surface in operator-only preview mode — pads with up to three synthetic rows (`Sample Reviewee 1/2/3`, `sample1@example.edu`, …) when fewer real assignments exist; bypasses session-status / deadline / acceptance gates; all inputs render disabled (via the existing `accepting=False` template branch); save / submit / clear / cancel forms suppressed via a single `preview_mode` template flag; "Preview — not visible to reviewers" banner at the top. Two operator-side entry-point anchors at ship time (instruments page header + session detail's Run Session card); the instruments-page anchor was disabled in 10C. No new audit events (read-only — also skips the `lifecycle.observe_deadline` lazy-close side-effect). Completes Segment 10B. | 2026-04-30 |
| 10D | Instruments-page rebuild taking the per-instrument card from frame to fully-functional. Slice 1 wired the Display Fields table + URL-driven `?editing={iid}` Save / Cancel / Edit state machine on every per-instrument card (with two locked Name + Email rows, inline Friendly Label edit, ▲/▼ reorder, and operator-defined visibility on the rest). Slice 2 reused the same state machine for the Response Fields table (inline label + Required edit, ➕ row-level Add via JS-deferred `<template>` clones bound to the bulk-save form, ✗ row-level Delete via queued hidden inputs, ▲/▼ client-side reorder). Slice 3 wired Response Fields Help (per-row textarea + Show checkbox) into the same bulk-save round-trip. Slice 4a introduced the `response_type_definitions` table (10 seeded rows per session: `Long_text` / `Short_text` / `Yes_no` / `Grade` / `Likert5` / `100int` / `0-to-2int` / `1-to-5int` / `1-to-5half` / `1-to-5dec`), migrated `instrument_response_fields.response_type` (text) into `response_type_id` (FK with `ON DELETE CASCADE` + SQLite `PRAGMA foreign_keys = ON`), and rendered the new Response Type Definitions card read-only with the Response Fields Type cell as a `<select disabled>` over RTD names. Slice 4b shipped operator-add / -edit / -delete on operator-defined RTD rows with the cascade-on-delete confirmation banner; Min / Max / Step / List stay editable post-create with `update_response_type_definition` re-deriving every dependent RF's `validation` block on save. Slice 4c wired Response Fields ↔ RTD on add (Type `<select>` is enabled on JS-deferred new rows so operators can pick from the RTD catalog; saved rows stay locked per spec). Slice 4d closed the cross-cutting consistency gaps: per-instrument and RTD card editing state machines are mutually exclusive; bulk-save refuses to commit an instrument with zero Response Fields; cascade-delete that would empty an instrument is hard-blocked with a banner naming the affected instrument(s). Banner-convention follow-ups added a Cancel button + auto-scroll-on-display + Cancel-returns-to-source-row to the new error / cascade banners and pinned the convention into `spec/assumptions.md`. Slice 5 enabled multi-instrument support: `Add new instrument` + `Delete this instrument` are wired through their existing POST routes, with native `confirm()` on Delete; both buttons share an `is_ready` / mutual-exclusion / single-instrument disable gate matching the per-instrument Edit button. The action row at the bottom of every per-instrument card is a `.bottom-grid` of two half-width cards: an invisible left card hosts Save / Cancel / Edit and Add new instrument together on a right-flushed row (state-machine pair sits immediately to the left of Add); a red-bordered, white-interior Danger Zone right card hosts Delete this instrument (also right-flushed) with cascade warning copy. Post-Slice-5 polish PRs (#262 → #268) landed the half-card layout, white inner Danger Zone background, tightened cascade copy, restyled `Add a Response Type` as a proper half-width card with a single inline Name + Data Type + Add row, and right-flushed the per-instrument Delete button. | 2026-05-02 |
| 10C | Operator UI clean-up consolidating the post-10B surface: every session-scoped operator page renders a 6-button **setup nav** header card (Session / Reviewers / Reviewees / Assignments / Instruments / Email Invites); session detail adopts a `.page-grid` two-column layout (Session Details / Session Setup / Run Session) with Danger Zone in `.bottom-grid`; the inline session-detail revert form is replaced by a reusable yellow lock card pattern (with `return_to` allowlist `{reviewers, reviewees, assignments, instruments}`) shared across the four mutating setup pages; sessions list adds a `Created by` column; reviewers / reviewees / assignments pages standardise on info-card + status-pill rows + `#upload-csv` anchored card + Danger Zone, with upload + Danger Zone hidden while locked. Instruments page restructured: All Instrument Status full-width card carries three pill rows + bulk Open/Close + bulk Show/Don't-show + a disabled Preview button; per-instrument card uses pastel-tint cycling, a top `.bottom-grid` (description + per-instrument status), a `.field-builder` `.bottom-grid` of Display + Response Fields half-cards, and a live client-rendered Preview Instrument table; bottom button row (Back / Save / Edit / Add an instrument / Delete) with a JS-only Save/Edit `field-builder.locked` toggle. Response Fields gains inline label edit (per-row hidden form via HTML5 `form=` attribute), Required auto-submit, row-level Add (`/fields/add-row`) + Delete; Type stays read-only by design. Display Fields renders a hardcoded 6-row CSV-named placeholder; persistence is deferred. Multi-instrument data layer fully shipped (`Instrument.session_id`, `order`, FK cascades, `create_instrument` / `delete_instrument` services + routes + `instrument.created` / `instrument.deleted` audit events) with the operator UI behind a disabled Add button; Delete is reachable when more than one instrument exists. Bulk visibility toggles emit `instruments.bulk_visibility_when_closed`. Cross-cutting primitives in `base.html`: `.page-grid`, `.bottom-grid`, `.card-tl/r/bl/l/tr/br`, `.setup-nav`, `.setup-grid`, `.btn-row` / `.btn-pair`, `.fill-col`, `.col-shrink`, `.session-meta-row`, `.session-status-row`, `.field-builder` (+ `.locked`), `.display-edit`. `.btn[hidden]` honours the standard hidden attribute. | 2026-05-01 |

Migration round-trips on both SQLite (every test session) and Postgres
(every PR via the `ci-postgres` job, which also runs the full pytest
suite against a `postgres:16` service container).

---

## Capabilities today

### Infrastructure & dev loop

- **Azure App Service** (Linux, Python 3.12, gunicorn + uvicorn).
- **Azure Postgres Flexible Server** (Burstable B1ms, Pg 16, Southeast
  Asia). Public access with firewall allow-list ("Allow Azure
  services" + dev IP). VNet integration deferred to Segment 14.
- **Deploy on push to `main`** — three jobs: `build` → `migrate` →
  `deploy`. The `migrate` job runs `alembic upgrade head` against
  Azure Postgres before the App Service swap; deploy is skipped if
  migration fails.
- **CI on every PR**: SQLite pytest plus a `ci-postgres` job that
  applies and round-trips migrations and runs the full pytest suite
  against a `postgres:16` service container. The `engine` fixture in
  `tests/conftest.py` honours `TEST_DATABASE_URL` / `DATABASE_URL` so
  the same suite covers both dialects without duplication.
- **Test infrastructure**: in-memory SQLite engine running real
  Alembic migrations once per session; per-test savepoint-based
  isolation so service-layer commits don't leak across tests;
  `make_client` factory for multi-user integration tests.
- **Documentation**: `docs/{authentication,database,imports}.md`,
  `docs/deployment_dev.md` (incl. one-time Postgres GRANT bootstrap),
  segment plans in `guide/`.

### Authentication & permissions

- **Microsoft Entra ID via Azure Easy Auth** in deployed environments.
- **Local fake-auth fallback** (`ALLOW_FAKE_AUTH=true`) for offline
  development.
- **`AuthenticatedUser`** dataclass parses `X-MS-CLIENT-PRINCIPAL` and
  the simpler `X-MS-CLIENT-PRINCIPAL-{NAME,ID,IDP}` headers.
- **`get_or_create_user`** dependency creates a `User` row on first
  sign-in. We don't pre-provision.
- **`require_session_operator`** dependency gates every operator route
  on a `SessionOperator(user, session)` row — non-operators get **403**
  and never see another operator's session.
- **Diagnostic pages**: `/me` (JSON), `/me/debug` (HTML with the raw
  claims list and a sign-out link).

### UI / branding

- Inline-SVG favicon (bird emoji 🐦) defined in
  `app/web/templates/base.html`. Edit the emoji or the SVG markup
  in the `<link rel="icon">` data URI to change it; for a real
  graphic asset, mount `StaticFiles` and point `href` at
  `/static/favicon.png`.
- **Manage-page reshape (Segment 9.4C)**: the reviewers, reviewees,
  and assignments Manage pages now render an always-present
  `<section id="upload-csv">` card with the existing import form;
  the Upload CSV button is `<a href="#upload-csv">` (no JS, no
  `<details>`, stateful via the URL fragment). Validation errors on
  POST re-render the Manage page itself — there is no longer a
  standalone `…/import` GET. The assignments page also carries an
  anchored `<section id="rules">` "Assign by Rules" placeholder
  (Rule editor — Segment 13) with a Cancel anchor that drops the
  fragment. **Edit Reviewers / Reviewees / Assignments** buttons
  render as disabled anchors (`<a class="btn disabled"
  aria-disabled="true">`) per the 9.4B disabled-affordance
  convention. New `/operator/sessions/{id}/instruments` index
  introduced (Segment 10C reshaped this page substantially — see
  the Segments-shipped 10C entry and the operator URL table for
  the current contract). New `/operator/sessions/{id}/setupinvite`
  is a stub (Email template editor tracked as
  `guide/unfinished_business.md` #24, no longer auto-deferred to
  Segment 15). Session-detail
  Setup table Manage buttons for Instruments and Set up invites
  are now real links.
- **Page chrome (Segment 9.4A)** in `app/web/templates/base.html`:
  top-left "Review Robin Web App (version {num})" link to `/about`,
  breadcrumb trail rendered just below, top-right user card with
  "Signed in as ..." + Sign out. Per-page back-links across pages
  are removed — the breadcrumb replaces them. (Segment 10C
  reintroduced one in-page Back affordance: the per-instrument
  card's bottom button row carries a Back button that
  smooth-scrolls to the top of the Instruments page. This is a
  same-page navigation aid, not a cross-page back-link.)
  Operator-page crumbs root at `Sessions → /operator/sessions`;
  reviewer-page crumbs root at `Reviewer → /reviewer`. Crumb
  factories live in `app/web/breadcrumbs.py`; the partial is
  `app/web/templates/_partials/breadcrumb.html`. Version string
  comes from `app.config.app_version` (`"dev"` for now;
  pipeline-driven version bumping is a Segment 14 concern).
- **Setup nav + lock card (Segment 10C)**: every session-scoped
  operator page (Session detail, Reviewers, Reviewees,
  Assignments, Instruments, Set up invites) renders a 6-button
  `.setup-nav` header card and — when the session is `ready` — a
  reusable yellow lock card immediately below it. The lock card
  posts to `/operator/sessions/{id}/revert` with a hidden
  `return_to` field; the route allowlists
  `{reviewers, reviewees, assignments, instruments}` so the
  operator lands back on the same page. The session-detail lock
  card omits `return_to`. While locked, each page hides its own
  mutation affordances (upload cards, Danger Zone, per-instrument
  Save button); `<input>` / `<select>` elements inside
  `.field-builder` are disabled. See `spec/operator_ui_concept.md` for
  the per-page contract and `spec/assumptions.md` for the markup.
- Card-based layout, monospace tabular code spans, severity pills
  (`error` / `warning` / `info`) for validation issues. All inline
  `<style>` in `base.html`. CSS framework / extraction is a Segment
  14 concern.

### Operator-facing app

| URL | What it does |
|---|---|
| `GET /` | service metadata |
| `GET /health` | unauthenticated `{"status": "ok"}` |
| `GET /about` | unauthenticated stub page; chrome's app-identity link target |
| `GET /me`, `/me/debug` | identity introspection |
| `GET /operator/sessions` | list of sessions where user is operator |
| `GET /operator/sessions/new` | create form |
| `POST /operator/sessions` | create + insert `SessionOperator` + audit + 303 |
| `GET /operator/sessions/{id}` | session detail in four cards (Session / Session setup / Run Session / Danger zone). `?validated=1` re-runs setup validation and renders an inline summary card with the Activate form when there are no blocking errors. |
| `GET /operator/sessions/{id}/edit` | edit form |
| `POST /operator/sessions/{id}/edit` | apply changes + audit |
| `POST /operator/sessions/{id}/delete` | delete session and all dependents (confirm; locked while `ready`) |
| `POST /operator/sessions/{id}/delete-data` | wipe every reviewer Response for the session; preserves setup; allowed in any status; emits `responses.deleted_all` audit event |
| `GET /operator/sessions/{id}/validate` | read-only setup validation deep-dive (Activate moved to the inline summary card on session detail) |
| `GET /operator/sessions/{id}/reviewers` | roster Manage view with anchored `#upload-csv` import card and disabled Edit Reviewers button |
| `POST /operator/sessions/{id}/reviewers/import` | parse + replace + audit; on validation errors re-renders the Manage page |
| `POST /operator/sessions/{id}/reviewers/delete-all` | delete every reviewer + cascade |
| `GET /operator/sessions/{id}/reviewees` | roster Manage view with anchored `#upload-csv` import card and disabled Edit Reviewees button |
| `POST /operator/sessions/{id}/reviewees/import` | parse + replace + audit; on validation errors re-renders the Manage page |
| `POST /operator/sessions/{id}/reviewees/delete-all` | delete every reviewee + cascade |
| `GET /operator/sessions/{id}/assignments` | hub (counts, mode pill, current pairs) with anchored `#upload-csv` manual-import card, anchored `#rules` Assign-by-Rules placeholder, and disabled Edit Assignments button |
| `POST /operator/sessions/{id}/assignments/full-matrix` | preview / save |
| `POST /operator/sessions/{id}/assignments/manual/import` | preview / save |
| `POST /operator/sessions/{id}/assignments/delete-all` | delete every assignment, clear mode |
| `POST /operator/sessions/{id}/activate` | flip session draft→ready (warn-and-acknowledge for non-blocking findings) |
| `POST /operator/sessions/{id}/revert` | flip session ready→draft (confirm checkbox; closes all instruments) |
| `GET /operator/sessions/{id}/instruments` | consolidated instruments page (post-10C shape) — setup nav header, yellow lock card when ready, full-width **All Instrument Status** card (deadline + accepting + visibility pill rows; bulk Open/Close + bulk Show/Don't-show; disabled Preview button), then one pastel-tinted card per instrument with a top `.bottom-grid` (description + per-instrument status), a `.field-builder` `.bottom-grid` of Display + Response Fields half-cards, a live client-rendered Preview Instrument #N table, and a Back / Save / Edit / Add an instrument / Delete button row. Multi-instrument schema + services ship; the `Add an instrument` button is the single UI gate (disabled with tooltip). Display Fields render a hardcoded 6-row CSV-named placeholder; the schema-level display-field routes still exist server-side but the template doesn't post to them. See `guide/instruments.md` for the per-section contract. |
| `GET /operator/sessions/{id}/setupinvite` | stub page — email-template editor is now tracked as `guide/unfinished_business.md` #24 (was previously auto-deferred to Segment 15) |
| `GET /operator/sessions/{id}/instruments/{instrument_id}` | legacy redirect — 303 to `/instruments` (back-compat for bookmarks; 10A) |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/edit` | edit friendly description (`Instrument.description`); audit `instrument.described`; invalidates `validated → draft` |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/fields` | add a response field; auto-derives `field_key` from label when blank; audit `instrument.field_added` |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/fields/{field_id}/edit` | edit a response field (label / required / validation / help text + visibility); audit `instrument.field_updated`; banner-warns when optional → required leaves existing reviewer rows incomplete |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/fields/{field_id}/delete` | delete a response field; cascade-confirm flow when responses exist; audit `instrument.field_deleted` |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/fields/{field_id}/move` | up / down reorder; repacks `0..N-1`; audit `instrument.fields_reordered` |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/display-fields` | add a display field (one of the seven D6 sources, posted as `source_pair=reviewee:tag_1`); audit `instrument.display_field_added`; invalidates `validated → draft`; `DisplaySourceError` (unknown source / duplicate) redirects with `?display_source_error=<pair>` |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/display-fields/{df_id}/edit` | edit label override + visibility; `(source_type, source_field)` are immutable; audit `instrument.display_field_updated` (diff-shaped) |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/display-fields/{df_id}/delete` | delete a display field; no cascade-confirm; audit `instrument.display_field_deleted` (with snapshot) |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/fields/save` | shared bulk form covering display + response fields — repacks `order` to `0..N-1` per table independently; persists display rows' `visible` + `label`; audit `instrument.fields_reordered` (when response order changes) and / or `instrument.display_fields_saved` (D11 diff shape) |
| `GET /operator/sessions/{id}/preview` | operator-only preview of the reviewer surface; works in any session status; bypasses deadline / acceptance gates; renders synthetic rows when fewer than three real assignments exist; all inputs disabled; save / submit / clear forms suppressed via the `preview_mode` template flag |
| `POST /operator/sessions/{id}/instruments/accepting/all-on` | bulk-open every instrument under the session; audit `instruments.bulk_accepting_responses` (ready-only, pre-deadline; deliberately does NOT invalidate `validated`) |
| `POST /operator/sessions/{id}/instruments/accepting/all-off` | bulk-close every instrument |
| `POST /operator/sessions/{id}/instruments/visibility/all-on` | bulk-flip `responses_visible_when_closed=True` on every instrument; audit `instruments.bulk_visibility_when_closed` (always available; deliberately does NOT invalidate `validated`) |
| `POST /operator/sessions/{id}/instruments/visibility/all-off` | bulk-flip `responses_visible_when_closed=False` on every instrument |
| `POST /operator/sessions/{id}/instruments/add` | create a new instrument under the session (optional `after={instrument_id}` for placement); audit `instrument.created`; invalidates `validated → draft`. UI button currently disabled — multi-instrument operator UI is intentionally deferred |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/delete` | delete an instrument and its dependents (cascades response fields, display fields, and assignments via FK delete-orphan); audit `instrument.deleted`; invalidates `validated → draft`. UI button only renders when more than one instrument exists; 400 when deleting the last instrument |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/open` | start accepting responses (requires session ready, pre-deadline) |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/close` | stop accepting responses (manual) |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/visibility` | toggle `responses_visible_when_closed` |
| `POST /operator/sessions/{id}/instruments/{instrument_id}/fields/add-row` | append a new response field with a default key/label/type after `after={field_id}` (or at the end when omitted); audit `instrument.field_added`; invalidates `validated → draft`. Powers the Response Fields ➕ button on the per-instrument card |
| `GET /operator/sessions/{id}/invitations` | per-reviewer invitation table (status / sent / opened) |
| `POST /operator/sessions/{id}/invitations/generate` | bulk-create invitations for assigned active reviewers (idempotent; ready-only) |
| `POST /operator/sessions/{id}/invitations/send-all` | write outbox row per pending invitation (ready-only) |
| `POST /operator/sessions/{id}/invitations/{iid}/send` | send a single invitation (rotates token; ready-only) |
| `POST /operator/sessions/{id}/invitations/{iid}/regenerate` | rotate token + reset to pending (ready-only) |
| `GET /operator/sessions/{id}/outbox` | dev-mode email outbox view for the session |
| `GET /operator/sessions/{id}/monitoring` | per-reviewer progress + reminder actions (ready-only for actions) |
| `POST /operator/sessions/{id}/invitations/{iid}/remind` | send a single reminder reusing the prior invitation URL (ready-only) |
| `POST /operator/sessions/{id}/monitoring/remind-incomplete` | bulk reminders to every incomplete reviewer (ready-only) |

### Reviewer-facing app

| URL | What it does |
|---|---|
| `GET /reviewer` | dashboard: sessions where user has an active `Reviewer` row; per-session pill (`not started` / `in progress` / `submitted`) |
| `GET /reviewer/invite/{token}` | invitation token landing — Easy Auth required, email-match check, stamps `opened_at`, 303 to surface |
| `GET /reviewer/sessions/{id}` | review surface: editable table of assigned reviewees and Default Instrument fields; ?saved=ok / ?submitted=ok flash banners |
| `POST /reviewer/sessions/{id}/save` | upsert response cells (empty value deletes the row); 303 → surface with `?saved=ok` |
| `POST /reviewer/sessions/{id}/submit` | persist + validate required; 400 + warn-and-override on missing without acknowledge; else stamps `submitted_at` and 303 → surface with `?submitted=ok` |
| `POST /reviewer/sessions/{id}/clear` | delete every response for this reviewer in this session (confirm checkbox required); 303 → surface |

The Cancel link on the surface is just `<a>` back to `GET /reviewer/sessions/{id}` — no server-side state change.

### Sessions

- Create with name, code (unique per operator), description, deadline.
- Session creation **also synchronously creates the Default
  Instrument** with two seed response fields (`rating` integer 1–5
  required; `comments` long text optional) and three seed display
  fields (`pair_context_1/2/3`, `visible=true`, `label=''`). Operator
  edits both kinds via the consolidated `/instruments` page (10A:
  response-field builder + friendly description; 10B-1: data-driven
  reviewer-surface render; 10B-2: display-field picker + shared
  field-order bulk form, replaced by the 10C per-instrument card
  shape — Display Fields renders a hardcoded 6-row CSV-named
  placeholder with persistence deferred, while the 10B-2
  schema-level routes remain in place; Response Fields inline edit
  + Required auto-submit + row-level Add/Delete are wired). The
  seven supported display-field sources at the schema layer are
  `reviewee.tag_1/2/3`, `reviewee.profile_link`, and
  `pair_context.1/2/3`; `assignment_context_*` is deliberately
  excluded. See `spec/architecture.md` "Conceptual hierarchy."
- View detail with live counts of reviewers, reviewees, assignments,
  and the current `assignment_mode`.
- **Edit** name / code / description / deadline; changes recorded as
  `session.updated` with a `changes: {field: [old, new]}` map.
- **Delete** session — removes operators, reviewers, reviewees,
  instruments, assignments, invitations, and the session's audit
  events; a final `session.deleted` event with `session_id=None`
  survives in the global audit log. Requires explicit confirm
  checkbox.

### Reviewers & reviewees

- **CSV upload** with required `ReviewerName/ReviewerEmail` (or
  `RevieweeName/RevieweeEmail`); optional `Tag1/2/3` for future
  RuleBased; optional `PhotoLink` on reviewees.
- **One-shot replace** with explicit confirm checkbox when the session
  already has rows. CSV files cap at 1 MiB / 5000 rows. Unknown
  columns are silently ignored. UTF-8 with BOM tolerated.
- **Browseable Manage views** showing the saved rows in a table,
  with an anchored `Upload CSV` card on the same page (no separate
  `…/import` GET) and a disabled `Edit Reviewers` / `Edit Reviewees`
  button reserved for the future inline-edit pattern.
- **Setup validation** page lists structural issues (no reviewers, no
  reviewees, duplicate emails) plus info-level placeholders for not-
  yet-implemented surfaces.
- **Cascade safety**: re-uploading a roster on a session with
  assignments deletes those assignments via ORM cascade. Operator
  sees a warning before they confirm. Audit event records the
  cascaded count.
- **Delete all** reviewers / reviewees from the roster Manage page
  with explicit confirm checkbox. Cascades to assignments. Audit
  events `reviewers.deleted_all` / `reviewees.deleted_all` record
  both the deleted count and the cascaded assignment count.

### Assignments

- **Hub page** at `/operator/sessions/{id}/assignments` with current
  count, mode pill, browseable Pairs table, and per-mode generation
  forms.
- **FullMatrix mode**: deterministic every-with-every; default
  excludes self-review (case-insensitive email/identifier match);
  preview shows total + coverage + the first 200 pairs; replace-all
  on confirm. Inactive reviewers and reviewees (rows whose `status`
  is anything other than `"active"`) are silently excluded; the
  audit `excluded_counts` records `inactive_reviewer` /
  `inactive_reviewee` keys when any are skipped.
- **Manual CSV mode**: required `ReviewerEmail`/`RevieweeEmail` (must
  exist in roster, and roster row must be active); optional
  `IncludeAssignment`, `PairContext1/2/3`, and
  `AssignmentContext1/2/3`. Re-upload pattern for preview-then-save
  (no draft table). Blocking errors for unknown / inactive roster
  references and duplicates. See `docs/imports.md` for the
  pair-vs-assignment-context distinction.
- **`assignment_mode`** column on `sessions` records the strategy
  used; `Assignment.created_by_mode` records the same per row.
- **Delete all** assignments from the hub with explicit confirm.
  Reviewers and reviewees stay; `session.assignment_mode` clears
  back to `null`. Audit event `assignments.deleted_all`.

### Reviewer review surface

- **Identity matching**: an authenticated user is matched to
  `Reviewer` rows by case-insensitive email equality (`casefold()`
  both sides). Only `Reviewer` rows with `status == "active"` count.
- **Dashboard** at `/reviewer` lists the user's reviewer-sessions
  with per-session pill (`not started` / `in progress` /
  `submitted`) computed from the reviewer's `Response` rows.
- **Surface** at `/reviewer/sessions/{id}` renders an editable HTML
  table per instrument (today: N=1, the Default Instrument) with a
  section heading from `Instrument.description` (fallback to the
  system handle) and a per-field help block above the table for
  fields whose `help_text_visible` is true. Each table row is one
  non-excluded assignment (`include = true`); columns are reviewee
  identity (name + email_or_identifier, always-first, mandatory)
  followed by the instrument's visible `InstrumentDisplayField`
  rows (10B-1 — sourced from `pair_context_1/2/3` today; the
  10B-2 add-display-field route over `reviewee.tag_1/2/3` /
  `reviewee.profile_link` exists server-side but the 10C per-
  instrument card placeholder doesn't reach it yet), then the
  response-field inputs in stored order, then a row-level
  submitted-status indicator. Empty
  / NULL display-field labels fall back to inferred strings from
  the D6 helper. `profile_link` cells render as plain `<a href>`.
  `assignment_context_*` is deliberately excluded from the surface
  per the pair-vs-assignment-context distinction.
- **Save draft**: form post upserts `Response` rows. Empty value
  deletes the row, so the row's absence == empty answer. Never
  touches `submitted_at`.
- **Submit**: persists pending writes, then validates required
  fields. Missing-required-without-acknowledge re-renders the page
  at HTTP 400 with a warning card and an `acknowledge_missing`
  checkbox. Missing-required-with-acknowledge stamps `submitted_at`
  and writes audit. Editing a previously-submitted required field
  to empty deletes the row including its `submitted_at`, flipping
  the dashboard pill back to `in progress` next render.
- **Clear all**: confirm-checkbox-required action that deletes
  every `Response` row for this reviewer in this session. No
  partial undo; reviewers re-enter values from scratch afterward.
- **Cancel**: plain `<a>` link back to the surface; no DB write,
  no audit. Discards in-progress edits by re-fetching saved values.
- **Autosave is deferred** to a follow-on PR (vanilla JS layered
  over the same `/save` endpoint).
- **Lifecycle gating (Segment 9.1)**: reviewer save / submit / clear
  return **HTTP 403** unless the session is `ready`, the assigned
  instrument is `accepting_responses`, and `now() < session.deadline`.
  When the gate is closed, the surface renders read-only; saved values
  are hidden unless the operator turns on
  `responses_visible_when_closed` on the per-instrument sub-page.
  Deadline closure is observed lazily on every reviewer GET/POST and
  on the per-instrument operator page; the first observer flips
  `accepting_responses=false`, stamps `deadline_closed_at`, and emits
  one `instrument.closed reason=deadline` audit event.

### Audit log

Every destructive operation writes an `audit_events` row with
`event_type`, `summary`, JSON `detail`, and a per-request `correlation_id`:

| event_type | When |
|---|---|
| `session.created` | new session |
| `session.updated` | edit form save (incl. `changes: {field: [old, new]}`) |
| `session.deleted` | session deletion (`session_id=None` in the row, original id in `detail`) |
| `reviewers.imported` | reviewer CSV save (incl. `cascaded_assignment_count`) |
| `reviewees.imported` | reviewee CSV save (incl. `cascaded_assignment_count`) |
| `reviewers.deleted_all` | delete-all from roster Manage view |
| `reviewees.deleted_all` | delete-all from roster Manage view |
| `assignments.generated` | FullMatrix or Manual save (incl. `mode`, `excluded_counts`) |
| `assignments.deleted_all` | delete-all from assignments hub |
| `responses.saved` | reviewer saves a draft (incl. `count`, `reviewer_id`) |
| `responses.submitted` | reviewer submits (incl. `count`, `missing_required_count`, `acknowledged_missing`) |
| `responses.cleared` | reviewer clears all their responses in a session |
| `responses.deleted_all` | operator-driven Delete Data on session detail (`detail.deleted_count`); allowed in any session status, including `ready` |
| `session.activated` | operator flips session draft→ready (`detail.override_warnings`) |
| `session.reverted_to_draft` | operator flips session ready→draft (`detail.closed_instrument_ids`, `response_count_at_revert`) |
| `instrument.opened` | operator manually re-opens a closed instrument |
| `instrument.closed` | manual or lazy-deadline close (`detail.reason ∈ {manual, deadline}`) |
| `instrument.described` | operator edits the friendly description (`detail.description: [old, new]`) |
| `instrument.field_added` | operator adds a response field (`detail.field_key`, `label`, `response_type`, `required`, `validation`, `help_text`, `help_text_visible`) |
| `instrument.field_updated` | operator edits a response field (`detail.changes: {key: [old, new]}` for each changed key only) |
| `instrument.field_deleted` | operator deletes a response field (`detail.snapshot`, `cascaded_response_count`) |
| `instrument.fields_reordered` | up/down move OR bulk fields-save when response order changes (`detail.old_order`, `detail.new_order` as `field_key` lists; scoped to response fields) |
| `instrument.display_field_added` | operator adds a display field (`detail.source_type`, `source_field`, `label`, `order`, `visible`) |
| `instrument.display_field_updated` | operator edits a display field (`detail.changes: {key: [old, new]}` for each changed key only — `(source_type, source_field)` are immutable) |
| `instrument.display_field_deleted` | operator deletes a display field (`detail.snapshot`); no cascade since display fields have no per-row dependents |
| `instrument.display_fields_saved` | bulk fields-save when display rows' label / visibility / order changed (`detail.added` / `removed` always `[]` in 10B-2; `detail.updated` carries `[{source_type, source_field, changes: {key: [old, new]}}, …]`) |
| `instruments.bulk_accepting_responses` | bulk Open all / Close all (`detail.target`, `detail.changed_instrument_ids`); not duplicated as per-instrument open / close events |
| `instruments.bulk_visibility_when_closed` | bulk Show all / Don't show any (`detail.target`, `detail.changed_instrument_ids`); not duplicated as per-instrument visibility events |
| `instrument.created` | operator creates a new instrument via `/instruments/add` (`detail.instrument_id`, `detail.session_id`, `detail.order`, `detail.after_instrument_id`); UI button currently disabled, route active for when multi-instrument UI lifts |
| `instrument.deleted` | operator deletes an instrument via `/instruments/{id}/delete` (`detail.instrument_id`, `detail.session_id`, `detail.name`, `detail.order`); cascade to response fields / display fields / assignments / responses runs via FK delete-orphan |
| `invitations.generated` | bulk-create invitations on a ready session (`detail.count`, `detail.invitation_ids`, `detail.reviewer_ids`) |
| `invitation.sent` | outbox row written + invitation flipped to `sent` |
| `invitation.opened` | first valid token follow with matching email |
| `invitation.regenerated` | per-row token rotation + reset to `pending` |
| `reminders.sent` | batch reminder send (`detail.count`, `detail.invitation_ids`, `detail.reviewer_ids`, `detail.fell_back_count`) |

`excluded_counts` is a generic map (`{"self_review": N,
"inactive_reviewer": M, ...}`) so RuleBased exclusions in Segment 13 can
plug in additional reasons without a schema change. Today's keys are
`self_review`, `inactive_reviewer`, `inactive_reviewee`.

---

## What's deliberately not yet there

| Capability | Lands in |
|---|---|
| Edit individual reviewer / reviewee / assignment rows (today: bulk operations only via CSV replace or delete-all) | **Segment 15** (officially deferred 2026-05-03; tracked at `guide/unfinished_business.md` #25 — needs a design pass before code) |
| Operator UI to flip `Reviewer.status` / `Reviewee.status` to inactive (filter is defensive today) | **Segment 15** (officially deferred 2026-05-03 from Segment 11 Tier 3 §2.4; tracked at `guide/unfinished_business.md` #36) |
| Display Fields persistence on the Instruments page placeholder rows (Friendly Label edit, Visible toggle, Order column don't POST yet; the 10B-2 schema-level routes still exist server-side). Wiring up requires extending `_VALID_DISPLAY_SOURCES` / `_DEFAULT_DISPLAY_LABELS` with reviewee name + email, extending `display_field_value` and the reviewer-surface render path, and pointing the placeholder cells at the existing endpoints. | Next round of UI work (a future 10x slice or folded into Segment 12) |
| Vanilla-JS autosave on top of the reviewer `/save` endpoint | Follow-on PR after Segment 8 |
| **Real SMTP email backend** (production sending, not the dev outbox) | **Segment 15** |
| Operator-editable email template editor + merge fields (`{{reviewer_name}}` / `{{deadline}}` / `{{help_contact}}` etc.); the `/setupinvite` stub today | Tracked as `guide/unfinished_business.md` #24 (independent of real SMTP — the editor shapes the body the dev outbox already renders) |
| **Export / audit retention** | **Segment 12** |
| **RuleBased assignment** | **Segment 13** |
| Multi-instrument sessions: FullMatrix per-instrument target picker, Manual CSV `Instrument` column, reviewer dashboard per-instrument grouping | Schema + reviewer-surface multi-instrument support shipped 2026-05-02 in Segment 10D Slice 5; the three remaining items are tracked at `guide/unfinished_business.md` #27 / #28 / #29 (Segment 13 plan archived as `guide/archive/segment_13_multi_instrument_sessions_superseded.md`) |
| **Production hardening** (Key Vault, VNet, soft-delete, full Postgres pytest matrix) | **Segment 14** |
| Local Postgres docker-compose for dev (SQLite + the `ci-postgres` job + migration-on-deploy is the parity story today) | **Segment 15** (officially deferred 2026-05-03; tracked at `guide/unfinished_business.md` #26 — likely settles "won't fix" via the developer setup guide work) |
| Sessions-list per-row Delete button posts directly (today: anchor link to `#danger-zone` on the session's Home page, where the operator confirms + clicks the real Delete) | **Segment 15** (officially deferred 2026-05-03; tracked at `guide/unfinished_business.md` #23 — small fix, bundles with whatever `/operator/sessions` UI work this segment touches) |
| Sort by reviewee on the reviewer surface — operator picks up to 3 default sort columns from the Display Fields table; reviewer can override at view time via clickable column headers (today: rows render in implicit insertion order) | **Segment 13** (promoted 2026-05-03 from Segment 11 §2.6 sketch; full design spec at `guide/sort_by_reviewee.md`; tracked at `guide/unfinished_business.md` #31) |
| Further refinement of the reviewer surface — catch-all for polish beyond the Segment 11 Tier 1 batch (PRs #319 → #324). Known sub-item: multi-instrument preview (`build_preview_context` extension explicitly deferred from Tier 1). Pilot-feedback-driven polish lands here too. | **Segment 15** (filed 2026-05-03; tracked at `guide/unfinished_business.md` #32) |
| AG Grid replacement of the reviewer-surface table (today: plain HTML `<input>` / `<textarea>` / `<select>` per cell, form-based save). Second half of workplan §11 that never landed; decided as still-on-roadmap 2026-05-03. | **Segment 15** (decided 2026-05-03 from Segment 11 Tier 2 §2.1; tracked at `guide/unfinished_business.md` #33) |
| Queue-based batch invitation sending (today: synchronous in-request loop over eligible reviewers; fine with the dev outbox, doesn't survive real SMTP latency + provider rate limits). Picks up workplan §12 work item #7. | **Segment 15** (decided 2026-05-03 from Segment 11 Tier 2 §2.3, bundled with real SMTP; tracked at `guide/unfinished_business.md` #34; depends on #6 shipping first) |
| Technical-support contact (global env var, surfaces on app chrome footer + error pages + invalid-link landing). Distinct from the operational help contact on `ReviewSession` (which lives in #24). | **Segment 15** (filed 2026-05-03 from Segment 11 Tier 2 §24 reframe; tracked at `guide/unfinished_business.md` #35) |

---

## Architectural notes worth preserving

### FullMatrix is a (future) RuleBased preset

FullMatrix and Manual currently have parallel implementations, but the
storage model treats them uniformly: every assignment is a row in
`assignments` with `created_by_mode` as a string discriminator and
`Assignment.context` as JSON. Segment 13 RuleBased is expected to
introduce a generic generation framework; FullMatrix becomes the
simplest preset of that framework. The audit-detail shape
(`excluded_counts: {...}`) is already generic; Manual rows ship with
`excluded_counts: {}`. The only friction is one specific service
function name (`generate_full_matrix`) and one preview template.

### Replace-all everywhere

All destructive ops (CSV imports + assignment generation) follow the
same shape: explicit confirm checkbox when rows already exist; audit
event records old count, new count, and any cascaded downstream
deletions. No append/merge for now — defer until activation
constraints make it necessary.

### Multi-instrument support

The data layer and the operator + reviewer surfaces are
multi-instrument-aware. Every session seeds one Instrument at
creation time via `ensure_default_instrument` (system handle
`Default`, operator-editable `description`, two seed response
fields, three seed `pair_context_1/2/3` display fields). The
schema columns (`Instrument.session_id`, `Instrument.order`,
`Assignment.instrument_id`) and the FK delete-orphan cascades are
in place; `create_instrument(after_instrument_id=…)` and
`delete_instrument(...)` exist as service helpers and emit the
`instrument.created` / `instrument.deleted` audit events; the
reviewer surface and the operator's `/instruments` page loop over
instruments; and the `Add an instrument` / `Delete this instrument`
operator buttons are wired (10D Slice 5, 2026-05-02) with mutual-
exclusion + single-instrument-floor gates. See
`spec/architecture.md` "Conceptual hierarchy."

The original Segment 13 plan (multi-instrument sessions) is
archived at
`guide/archive/segment_13_multi_instrument_sessions_superseded.md`
since most of its scope shipped early in Segments 10A → 10D. Three
items did not ship and live in `guide/unfinished_business.md` as
#27 (FullMatrix per-instrument target picker), #28 (Manual CSV
`Instrument` column), and #29 (reviewer dashboard per-instrument
grouping).

### Pair-level vs assignment-level context

Manual CSV imports carry two distinct kinds of per-pair context
(`pair_context_*` and `assignment_context_*`), both stored on
`Assignment.context`. Pair-level is reviewer-facing informational
metadata; assignment-level is logic-engaging metadata that
RuleBased (Segment 13) will read. See `docs/imports.md` and
`spec/architecture.md` "Pair-level vs assignment-level context."
