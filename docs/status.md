# Implementation status

**As of:** end of Segment 7 (2026-04-28)

This document is a periodic snapshot of what Review Robin Web actually
does today, vs. what is planned but not yet implemented. It is updated
at the end of each segment. Per-segment plans live in
`guide/segment_NN_*` and `guide/segment_NNA.md`.

For the full long-term plan see
`guide/low_intensity_workplan_review_robin_web.md`.

---

## Segments shipped

| Segment | What it added | Status |
|---|---|---|
| 1 | Repository skeleton, `/health`, local dev install | ✅ |
| 2 | Azure App Service deployment via OIDC | ✅ |
| 3 | Microsoft Entra ID sign-in via Easy Auth | ✅ |
| 4 | 12-table schema + Alembic migration infra | ✅ |
| 5 | Postgres provisioning + migrate-on-deploy + operator session CRUD-lite | ✅ |
| 6 | Reviewer / reviewee CSV imports + setup validation | ✅ |
| 7 | FullMatrix + Manual assignment generation + roster Manage views | ✅ |

86 → 89 tests across unit + integration. Migration round-trips on both
SQLite (every test session) and Postgres (every PR via the
`ci-postgres-migration` smoke job).

---

## Capabilities today

### Infrastructure & dev loop

- **Azure App Service** (Linux, Python 3.12, gunicorn + uvicorn).
- **Azure Postgres Flexible Server** (Burstable B1ms, Pg 16, Southeast
  Asia). Public access with firewall allow-list ("Allow Azure
  services" + dev IP). VNet integration deferred to Segment 13.
- **Deploy on push to `main`** — three jobs: `build` → `migrate` →
  `deploy`. The `migrate` job runs `alembic upgrade head` against
  Azure Postgres before the App Service swap; deploy is skipped if
  migration fails.
- **CI on every PR**: SQLite pytest plus a `postgres-migration` smoke
  job that applies and round-trips migrations against a `postgres:16`
  service container.
- **Test infrastructure**: in-memory SQLite engine running real
  Alembic migrations once per session; per-test savepoint-based
  isolation so service-layer commits don't leak across tests;
  `make_client` factory for multi-user integration tests.
- **Documentation**: `docs/{authentication,database,imports}.md`,
  `deployment_dev.md` (incl. one-time Postgres GRANT bootstrap),
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

### Operator-facing app

| URL | What it does |
|---|---|
| `GET /` | service metadata |
| `GET /health` | unauthenticated `{"status": "ok"}` |
| `GET /me`, `/me/debug` | identity introspection |
| `GET /operator/sessions` | list of sessions where user is operator |
| `GET /operator/sessions/new` | create form |
| `POST /operator/sessions` | create + insert `SessionOperator` + audit + 303 |
| `GET /operator/sessions/{id}` | session detail (counts, mode pill, links) |
| `GET /operator/sessions/{id}/validate` | setup validation page |
| `GET /operator/sessions/{id}/reviewers` | roster Manage view |
| `GET /operator/sessions/{id}/reviewers/import` | upload form |
| `POST /operator/sessions/{id}/reviewers/import` | parse + replace + audit |
| `GET /operator/sessions/{id}/reviewees` | roster Manage view |
| `GET /operator/sessions/{id}/reviewees/import` | upload form |
| `POST /operator/sessions/{id}/reviewees/import` | parse + replace + audit |
| `GET /operator/sessions/{id}/assignments` | hub (counts, mode pill, current pairs) |
| `POST /operator/sessions/{id}/assignments/full-matrix` | preview / save |
| `POST /operator/sessions/{id}/assignments/manual/import` | preview / save |

### Sessions

- Create with name, code (unique per operator), description, deadline.
- View detail with live counts of reviewers, reviewees, assignments,
  and the current `assignment_mode`.
- **Cannot edit or delete** a session yet.

### Reviewers & reviewees

- **CSV upload** with required `ReviewerName/ReviewerEmail` (or
  `RevieweeName/RevieweeEmail`); optional `Tag1/2/3` for future
  RuleBased; optional `PhotoLink` on reviewees.
- **One-shot replace** with explicit confirm checkbox when the session
  already has rows. CSV files cap at 1 MiB / 5000 rows. Unknown
  columns are silently ignored. UTF-8 with BOM tolerated.
- **Browseable Manage views** showing the saved rows in a table, with
  Replace CSV link.
- **Setup validation** page lists structural issues (no reviewers, no
  reviewees, duplicate emails) plus info-level placeholders for not-
  yet-implemented surfaces.
- **Cascade safety**: re-uploading a roster on a session with
  assignments deletes those assignments via ORM cascade. Operator
  sees a warning before they confirm. Audit event records the
  cascaded count.

### Assignments

- **Hub page** at `/operator/sessions/{id}/assignments` with current
  count, mode pill, browseable Pairs table, and per-mode generation
  forms.
- **FullMatrix mode**: deterministic every-with-every; default
  excludes self-review (case-insensitive email/identifier match);
  preview shows total + coverage + the first 200 pairs; replace-all
  on confirm.
- **Manual CSV mode**: required `ReviewerEmail`/`RevieweeEmail` (must
  exist in roster); optional `IncludeAssignment` and
  `AssignmentContext1/2/3`. Re-upload pattern for preview-then-save
  (no draft table). Blocking errors for unknown roster references and
  duplicates.
- **Default Instrument** auto-created per session (placeholder until
  Segment 8 ships real instruments).
- **`assignment_mode`** column on `sessions` records the strategy
  used; `Assignment.created_by_mode` records the same per row.

### Audit log

Every destructive operation writes an `audit_events` row with
`event_type`, `summary`, JSON `detail`, and a per-request `correlation_id`:

| event_type | When |
|---|---|
| `session.created` | new session |
| `reviewers.imported` | reviewer CSV save (incl. `cascaded_assignment_count`) |
| `reviewees.imported` | reviewee CSV save (incl. `cascaded_assignment_count`) |
| `assignments.generated` | FullMatrix or Manual save (incl. `mode`, `excluded_counts`) |

`excluded_counts` is a generic map (`{"self_review": N, ...}`) so
RuleBased exclusions in Segment 11 can plug in additional reasons
without a schema change.

---

## What's deliberately not yet there

| Capability | Lands in |
|---|---|
| Edit / delete sessions, reviewers, reviewees, individual assignments | Not yet planned; would slot before activation |
| **Instruments** (custom review forms beyond placeholder "Default") | **Segment 8** |
| **Reviewer surface** — the actual review experience for reviewers | **Segment 8** |
| **Activation** (operator publishes the session, locks edits, opens to reviewers) | **Segment 9** |
| **Invitations & reminders** (email reviewers their links) | **Segment 9** |
| **Responses** (reviewer-submitted data) | **Segment 8 / 9** |
| **Export / audit retention** | **Segment 10** |
| **RuleBased assignment** | **Segment 11** |
| **Multi-instrument sessions** | **Segment 12** |
| **Production hardening** (Key Vault, VNet, soft-delete, full Postgres pytest matrix) | **Segment 13** |

---

## Architectural notes worth preserving

### FullMatrix is a (future) RuleBased preset

FullMatrix and Manual currently have parallel implementations, but the
storage model treats them uniformly: every assignment is a row in
`assignments` with `created_by_mode` as a string discriminator and
`Assignment.context` as JSON. Segment 11 RuleBased is expected to
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

### Single-instrument constraint

`Assignment.instrument_id` is `NOT NULL`. Until Segment 8 ships
real instruments, every session gets one auto-created `Default`
Instrument; every assignment points at it. This is not a bug; it's
the intended placeholder.
