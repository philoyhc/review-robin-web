# AGENTS.md

## Project conventions

- Use Python 3.12+.
- Use FastAPI for the backend.
- Use Pydantic for request/response schemas.
- Use SQLAlchemy 2.x declarative style with `Mapped[]` and `mapped_column`.
  Do not import from `sqlalchemy.dialects.postgresql` in `app/db/models/` —
  Postgres-specific column types are deferred to Segment 14.
- Keep route handlers thin.
- Put business logic in service modules.
- Add or update tests for every behavior change.
- Prefer explicit types and clear names.
- Do not introduce a full frontend framework unless explicitly requested.
- Do not implement Microsoft authentication in app code unless explicitly requested; assume Azure App Service Easy Auth will provide authenticated identity headers in deployed environments.
- Keep changes small and PR-sized.

## Current stage

Segments 1–8, 9 (9.1, 9.2, 9.3, 9.4A, 9.4B, 9.4C, 9.5A), 10A, and 10B-1 complete. See
`docs/status.md` for the authoritative snapshot of what ships today;
this section summarises only what an agent needs before opening files.

The project has:

- FastAPI app on Azure App Service, deploy-on-push to `main` with a
  `build → migrate → deploy` pipeline.
- Azure Postgres Flexible Server with `alembic upgrade head` running
  in CI before every deploy. PR CI runs SQLite pytest plus a
  `postgres-migration` smoke job.
- Microsoft Entra ID via Azure Easy Auth in deployed envs;
  `ALLOW_FAKE_AUTH=true` fallback for local dev. `User` rows are
  created on first sign-in.
- 12-table SQLAlchemy 2.x schema with Alembic migrations.
- Operator MVP: session CRUD, reviewer/reviewee CSV import + Manage
  views, setup validation, FullMatrix + Manual assignment generation,
  per-session Default Instrument (10A made it operator-editable;
  10B-1 added a data-driven reviewer-surface render sourced from
  `InstrumentDisplayField`), audit log on every destructive op.
- Reviewer review surface (Segment 8): dashboard, save / submit /
  clear / cancel.
- Session activation lifecycle (Segment 9.1): draft↔ready transitions
  with audit, edit-lock while ready, per-instrument open/close +
  visibility (originally a sub-page, consolidated into the
  per-instrument card on `/instruments` by 10A; the legacy URL
  303s), lazy deadline-driven instrument close, reviewer write-path
  gated by session status + instrument acceptance + deadline.
- Per-reviewer invitations + dev email outbox (Segment 9.2):
  operator-paced generate / regenerate / send / send-all on a ready
  session; sha256-hashed tokens; `/reviewer/invite/{token}` landing
  route requires Easy Auth + email match (mismatch → 403 page);
  per-session outbox view shows the rendered email + raw token URL.
- Monitoring + reminders (Segment 9.3): per-session monitoring page
  with summary counts and per-reviewer progress; per-row and bulk
  "send reminder to incomplete" actions; reminders reuse the URL
  from the most recent invitation outbox row (no token rotation),
  falling back to a fresh send when an invitation has never been
  sent; single batch `reminders.sent` audit event per bulk send.
- Page chrome + breadcrumbs (Segment 9.4A): global chrome on
  `base.html` (app-identity link to `/about`, breadcrumb partial,
  signed-in user card with Sign out); per-page back-links removed.
  Breadcrumb factories live in `app/web/breadcrumbs.py`. Sessions
  list reshaped: per-row Access/Delete buttons + Create-new-session
  button below the table. New `/about` stub.
- Session detail four-card restructure (Segment 9.4B):
  `app/web/templates/operator/session_detail.html` now renders four
  cards — Session, Session setup (table fed by
  `app/web/views.build_setup_rows`), Run Session, Danger zone.
  Validate Session Setup uses a query-param branch on the existing
  GET (`?validated=1`) to render an inline summary card with the
  Activate form; the legacy activate form on `/validate` is removed
  (page is the read-only deep-dive). New `POST /delete-data` wipes
  every Response row for the session, preserves setup, allowed in
  any status, emits `responses.deleted_all`.
- Manage-page reshape + instruments index + `/setupinvite` stub
  (Segment 9.4C): reviewers / reviewees / assignments Manage pages
  use an always-rendered `<section id="upload-csv">` card for CSV
  upload (the standalone `…/import` GET routes and templates are
  gone; POST validation errors re-render the parent Manage page).
  The assignments page also carries an anchored
  `<section id="rules">` Assign-by-Rules placeholder (Cancel anchor
  drops the fragment). Edit Reviewers / Reviewees / Assignments
  buttons render as disabled anchors (`<a class="btn disabled"
  aria-disabled="true">`). New
  `GET /operator/sessions/{id}/instruments` lists one card per
  instrument with Add / Delete instrument disabled (Segment 13);
  new `GET /operator/sessions/{id}/setupinvite` is a stub pointing
  forward to Segment 15. `build_setup_rows` re-enables the
  Instruments and Set up invites rows; both render as real Manage
  links from session detail.
- Setup-readiness lifecycle (Segment 9.5A): adds a stored
  `validated` value to `SessionStatus` between `draft` and `ready`.
  `GET /operator/sessions/{id}?validated=1` flips draft→validated
  as a side-effect when validation has zero errors (idempotent in
  validated; legacy `/validate` deep-dive stays read-only).
  `activate_session` now requires `is_validated`; revert from ready
  still lands on draft. Setup-mutating routes (reviewer/reviewee
  import + delete-all, assignment generate + manual import +
  delete-all, session edit) flip validated→draft via a route-level
  `_invalidate_if_validated` helper before the mutation, emitting
  dedicated `session.validated` / `session.invalidated` audit
  events. Instrument open/close/visibility and `POST /delete-data`
  deliberately do NOT invalidate.
- Response-field builder + reviewer-surface refactor (Segment 10A):
  `/operator/sessions/{id}/instruments` is now a consolidated page
  with a session-wide Instruments Settings card (bulk Open all /
  Close all) and one card per instrument carrying friendly
  description (`Instrument.description`), acceptance + visibility
  toggles (existing 9.1 behaviours), a response-fields table with
  add / edit / delete / reorder / per-field help text + visibility,
  and a system-handle pill rendering `Instrument.name`. Migration
  adds `help_text` (Text NULL) and `help_text_visible` (Bool
  default true) on `instrument_response_fields`. Field-key format
  is `^[a-z][a-z0-9_]*$` ≤64; auto-derived from label via
  `slugify_field_key` when blank; immutable after save. Empty-
  instrument validation now blocks activation. New audit events:
  `instrument.described`, `instrument.field_added`,
  `instrument.field_updated`, `instrument.field_deleted` (with
  cascaded response count snapshot), `instrument.fields_reordered`,
  `instruments.bulk_accepting_responses`. Description / field
  mutations invalidate `validated → draft`; bulk accepting +
  per-instrument open/close/visibility deliberately do NOT
  invalidate. Locked when `session.status == ready` via a single
  `_can_edit_instrument` helper (returns 409). Reviewer surface
  refactors to loop over instruments (today: N=1) with section
  heading from `Instrument.description` (fallback to system
  handle), per-field help block above each table, and `pair_context_*`
  rendering inside the loop (10B-1 replaces it with display-fields).
  Legacy `GET /operator/sessions/{id}/instruments/{iid}` 303s to
  the consolidated page; the existing 9.1 open / close / visibility
  POSTs keep their URL but redirect to `/instruments`. Body width
  bumped from 900px to 1400px globally with a `.table-scroll`
  utility class.
- Data-driven reviewer-surface render (Segment 10B-1): pair-context
  values move out of the reviewee identity cell and render as their
  own columns sourced from `InstrumentDisplayField` rows. Backfill
  migration (`c2143bd329c7`) seeds three rows per existing instrument
  (`source_type='pair_context'`, `source_field='1'|'2'|'3'`,
  `label=''`, `order=0..2`, `visible=true`) — destructive within
  that filter (operator-typed labels on those slots are not preserved
  across upgrade), `reviewee` rows added later are left intact.
  `ensure_default_instrument` seeds the same three rows on new
  sessions. Reviewee identity (name + email) is the always-first
  column, mandatory and non-toggleable. New helpers
  `display_field_label(field)` and `display_field_value(field,
  assignment)` cover the seven D6 sources (`reviewee.tag_1/2/3`,
  `reviewee.profile_link`, `pair_context.1/2/3`); empty/NULL labels
  fall back to inferred strings. `profile_link` cells render as
  plain `<a>`. No operator UI yet; picker + bulk form land in 10B-2
  and the operator preview route in 10B-3. No new audit events.

Not yet implemented (do not add unless an issue explicitly asks):
display-fields picker (10B-2), operator preview (10B-3), export,
RuleBased assignment, multi-instrument sessions, production hardening
(Key Vault, VNet, soft-delete, real SMTP). These map to Segments
10B-2 / 10B-3 / 11–14 — see `guide/segment_NN_*` and
`docs/status.md` "What's deliberately not yet there."

Update `docs/status.md` at the end of each segment; keep the summary
above in sync.

## Testing expectations

Before considering a change complete, run:

```bash
pytest
```

If dependencies or tooling change, update `README.md`.
