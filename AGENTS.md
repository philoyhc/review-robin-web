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

Segments 1–8 and 9 (9.1, 9.2, 9.3, 9.4A, 9.4B, 9.4C) complete. See `docs/status.md`
for the authoritative snapshot of what ships today; this section
summarises only what an agent needs before opening files.

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
  per-session Default Instrument placeholder, audit log on every
  destructive op.
- Reviewer review surface (Segment 8): dashboard, save / submit /
  clear / cancel.
- Session activation lifecycle (Segment 9.1): draft↔ready transitions
  with audit, edit-lock while ready, per-instrument open/close +
  visibility sub-page, lazy deadline-driven instrument close,
  reviewer write-path gated by session status + instrument acceptance
  + deadline.
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

Not yet implemented (do not add unless an issue explicitly asks):
operator-editable instruments, export, RuleBased assignment,
multi-instrument sessions, production hardening (Key Vault, VNet,
soft-delete, real SMTP). These map to Segments 10–14 — see
`guide/segment_NN_*` and `docs/status.md` "What's deliberately not
yet there."

Update `docs/status.md` at the end of each segment; keep the summary
above in sync.

## Testing expectations

Before considering a change complete, run:

```bash
pytest
```

If dependencies or tooling change, update `README.md`.
