# Codebase assessment — 2026-05-09

**As of:** end of `routes_operator` refactor (PRs #651 → #660), one
day after Segment 11K closure. Citizen project, single-author cadence;
not yet pilot-deployed.

This document is a snapshot review against the functional spec at
`spec/functional_spec.md`. Numbers were taken on `main` at commit
`c9cec04`. Authoritative ship-state lives in `docs/status.md`; this
file is an audit-style assessment, not a status update.

---

## 1. What's in the box (one-paragraph summary)

A FastAPI + Jinja monolith implementing the operator setup → reviewer
response loop end-to-end at the dev-loop level. An operator can
create a session, upload reviewers and reviewees, configure
multi-instrument response/display fields, generate assignments
(FullMatrix / Manual CSV / Rule-based via 13A's RuleSet engine),
validate readiness, activate, generate per-reviewer invitation tokens,
and watch the Manage Invitations + Responses pages fill in. A
reviewer can land via Microsoft Entra Easy Auth (or
`/reviewer/invite/{token}`), navigate a multi-page tabular review
surface with client-side dirty tracking, save drafts and submit. Every
mutating service writes a canonical-shape `audit_events` row
(51 registered event types, strict-mode validated). Email is staged in
a dev outbox table — no real SMTP / Graph / ACS dispatch yet; that is
deliberately deferred to **Segment 14-1**. Export, retention, and
production hardening are also pending.

## 2. By the numbers (LOC + counts)

### Code

| Area | LOC | Files |
|---|---:|---:|
| `app/services` (business logic) | 9,718 | 18 modules + `rules/` package |
| `app/web` (routes + view-shape adapters) | 9,771 | 11 route files + `views.py` |
|  ├ `routes_operator/` (post-refactor 10 slices + shared) | 4,819 | 12 |
|  ├ `routes_reviewer.py` | 1,122 | 1 |
|  └ `views.py` | 3,483 | 1 |
| `app/db/models` (SQLAlchemy 2.x declarative) | 842 | 14 |
| `app/schemas` (Pydantic shapes) | 493 | 5 |
| `app/auth` | 153 | 2 |
| `app/main.py`, `app/config.py` | 109 | 2 |
| **Total `app/` Python** | **~21,200** | — |
| Alembic migrations | 2,274 | 22 |
| Templates (`*.html`) | 8,029 | 41 |

### Tests

| Area | LOC | Files |
|---|---:|---:|
| Integration | ~25,000 | 51 |
| Unit | ~4,800 | 26 |
| Helpers + conftest | ~50 | 6 |
| **Total tests** | **29,811** | **83** |

Test/code ratio: **1.41 ×** (29,811 LOC tests vs 21,157 LOC app
code). 1,007 tests passing.

### Documentation

| Area | LOC | Files |
|---|---:|---:|
| `spec/` (functional + UI + per-page) | 8,936 | 22 |
| `guide/` (active plans + roadmap) | 6,223 | 13 |
| `guide/archive/` (shipped segment plans) | 21,983 | 27 |
| `docs/` (subsystem deep-dives + status) | 1,507 | 7 |
| `CLAUDE.md` / `AGENTS.md` (byte-identical) | ~280 each | 2 |
| `README.md` | ~250 | 1 |

### Surface area

- **90 HTTP routes** total (83 operator + 7 reviewer + health + about + auth callback)
- **14 database models**, **22 migrations** (Pg 16 / SQLite parity)
- **51 audit event types** registered in `EVENT_SCHEMAS` strict-mode
  registry
- **18 service modules** + 1 `rules/` package (engine + library +
  schemas)
- **41 Jinja templates** + 8 partials

## 3. Compliance against `spec/functional_spec.md`

### §21 Minimum viable functional release (16 items)

| # | Item | State |
|---|---|---|
| 1  | Session creation and configuration | ✅ |
| 2  | Reviewer upload/edit | ⚠️ upload yes; inline edit deferred to Seg 15 |
| 3  | Reviewee upload/edit | ⚠️ upload yes; inline edit deferred to Seg 15 |
| 4  | Single-instrument configuration | ✅ |
| 5  | Manual assignment upload/edit | ⚠️ CSV-replace yes; per-row edit deferred |
| 6  | Full-matrix assignment generation | ✅ (also reachable as a seeded RuleSet) |
| 7  | Basic readiness validation | ✅ (`ValidationRule` registry, find-and-fix Validate page) |
| 8  | Email invitations with individualized links | ⚠️ staged to dev outbox; real send pending Seg 14-1 |
| 9  | Microsoft sign-in or unique-link access | ✅ Easy Auth + `/reviewer/invite/{token}` landing |
| 10 | Reviewer tabular response surface | ✅ multi-instrument; client-side page nav; numeric step-grid validation |
| 11 | Save and submit | ✅ |
| 12 | Operator progress dashboard | ✅ Manage Invitations + Responses pages |
| 13 | Reminder sending | ⚠️ enqueues to outbox; real send pending Seg 14-1 |
| 14 | CSV and Excel export | ❌ Segment 12A scaffolded only |
| 15 | Basic audit log | ✅ canonical envelope, strict-mode gate, 51 event types |
| 16 | Basic retention/deletion workflow | ❌ Segment 12B not started |

**Score: 10/16 fully present, 4 functionally-present-but-dev-only,
2 not yet implemented.**

The four ⚠️ items split two ways:
- **#2/#3/#5** ship the bulk path (CSV upload + delete-all + replace)
  but not the per-row edit affordance the spec also names. Functional
  coverage is operationally adequate for the bulk-data flow; the gap
  shows up when one row needs a typo fix.
- **#8/#13** are end-to-end at the application layer but stop at
  `email_outbox.status="queued"`. The transport plumbing landed in
  Segment 11E (`EmailTransport` / `SmtpEmailTransport` /
  `GraphEmailTransport` stub) and is wired to a `transport_for(...)`
  factory; the call site activation lives in Segment 14-1 Part A.

### §22 Expanded release items

| Item | State |
|---|---|
| Multi-instrument sessions | ✅ schema + reviewer surface; gaps tracked at `unfinished_business.md` #27/#28/#29 |
| Rule-based assignment builder | ✅ Segment 13A + 13A-1 (engine, RuleSet schema, editor) |
| Assignment preview and dry-run counts | ✅ live preview pane in Rule Builder |
| Session cloning | ❌ not planned |
| Richer invitation templates | ✅ Segment 11E editor (Invitation / Reminder / Responses-received) |
| Targeted reminders by completion state | ⚠️ "incomplete" cohort yes; richer slicing not planned |
| Controlled post-activation correction workflows | ✅ revert / invalidate lifecycle hooks; per-instrument open/close |
| Richer audit views | ⚠️ canonical schema in DB; UI surface pending |
| Long-format / wide-format export | ❌ part of Segment 12A |
| Role delegation among multiple operators | ⚠️ `SessionOperator` table supports it; no operator-management UI |
| Advanced retention policies | ❌ Segment 12B |
| Administrative dashboards | ❌ not planned |

### §23 End-to-end acceptance criteria

Items 1-13 of the 16-step end-to-end cycle work today subject to the
dev-outbox caveat on items 8 (send invitations) and 12 (send
reminders). Items 14 (export complete dataset) and 15 (delete or
retain per policy) are blocked on Segments 12A / 12B. Item 16
(review audit records) is satisfied if a reader can read SQL — the
operator-facing audit-history surface isn't built.

## 4. Strengths

1. **Architectural discipline.** Three-layer split (route → service
   → model) is enforced consistently. No SQL in routes, no business
   logic in templates. The `app/web/views.py` "fourth seam" cleanly
   absorbs view-shape adapters that shouldn't grow inside services.
   PRs #651-#659 just split the formerly 4,423-line `routes_operator.py`
   into 10 feature-area sub-modules with a written-down
   "no slice-to-slice imports" invariant (`major_refactor.md` §3.0).

2. **Test coverage.** 1,007 tests passing; test code (29,811 LOC) is
   1.41 × production code (21,157 LOC). CI runs the full suite against
   both SQLite (every PR) and a Postgres 16 service container (every
   PR via `ci-postgres`); the same fixture honours `TEST_DATABASE_URL`
   so dialect parity is exercised, not assumed. Real Alembic migrations
   roundtrip per session.

3. **Audit log discipline.** 51 distinct event types registered under
   the canonical envelope schema (Segment 11K, 2026-05-07). A
   per-event-type allowlist runs as a Pydantic validation gate inside
   `audit.write_event`; strict mode (flipped on for tests) raises on
   any drift, so future emitters can't silently regress the shape.
   The cutover boundary is documented and pre-cutover rows are
   intentionally not rewritten (append-only).

4. **Lifecycle correctness.** Explicit state machine (draft →
   validated → ready → closed) backed by `app/services/session_lifecycle.py`.
   Cross-cutting `invalidate_if_validated()` hook pulled into the
   service layer in Segment 11A; setup-mutating services call it
   uniformly. Edit-locks, response-loss-acknowledge prompts, and
   per-instrument open/close gates are uniformly enforced.

5. **Documentation depth.** 8,936 LOC of specs covering operator UI
   concept, functional spec, architecture, audit-event detail
   schema, every major page, plus a 16-section forward-looking
   functional spec with explicit divergences-from-current called out.
   Active vs archived segment plans cleanly separated. Active plans
   sit in `guide/`; shipped ones move to `guide/archive/`.

6. **Migration hygiene.** 22 ordered migrations; `migrate-on-deploy`
   is a separate CI job (`build → migrate → deploy`) and the deploy
   step is skipped if migration fails. SQLite-friendly (every model
   round-trips on both dialects in CI); no Postgres-specific dialect
   imports inside `app/db/models/` per project convention.

7. **Iteration cadence.** ~13 calendar days from Segment 1 (repo
   skeleton) to current state. Tight PR ladders: Segment 11J in 3
   PRs, Segment 13A in 11 PRs, the routes_operator refactor in 11
   PRs (with all 10 slices landing same-day). Each PR is small
   enough to review in one sitting.

8. **No frontend build step.** Server-rendered Jinja, inline CSS in
   `base.html`, targeted progressive-enhancement JS only (e.g. the
   reviewer-surface page-toggle script, the per-instrument live
   preview). Deployment is `pip install` + gunicorn — no node_modules,
   no asset pipeline, no cache-busting. For a citizen project, this
   is a meaningful complexity reduction.

9. **Identity model is right-sized.** Microsoft Entra ID via Azure
   Easy Auth in deployed environments; `ALLOW_FAKE_AUTH` fallback for
   local dev. `require_session_operator` dependency injects a
   per-session permission check on every operator route and 403s
   non-operators. No app-managed password store except per-operator
   SMTP credentials (encrypted at rest via `cryptography.fernet` keyed
   off `SMTP_ENCRYPTION_KEY`).

10. **Decisions are written down.** When a non-trivial choice is made
    (CSRF: rely on Easy Auth + SameSite=Lax; visibility-when-closed
    exempt from invalidation; Display Fields seed from import data,
    not column-name defaults), it lands in either a docs file
    (`docs/authentication.md`), a code comment with a spec
    cross-reference, or `unfinished_business.md` with a "decided"
    annotation. Decision archaeology is cheap.

## 5. Weaknesses and gaps

1. **Email is not actually sent.** The terminal artifact for
   acceptance-criteria #8 (invitations) and #13 (reminders) is a row
   in `email_outbox` with `status="queued"`. The `EmailTransport`
   protocol + `SmtpEmailTransport` + typed `GraphEmailTransport` stub
   shipped in Segment 11E, but no caller invokes them. **Until Segment
   14-1 Part A lands, this system cannot run a real review cycle**
   without an out-of-band manual mail-merge step. Functional spec §1
   says "reviewers receive individualized invitations" — today they do,
   if and only if someone reads the outbox table out and pastes the
   tokens into Outlook.

2. **No data export.** Segment 12A (export + import) is planned,
   scaffolded on Session Home (`Extract Data` card with disabled
   buttons), but not wired. The system's terminal deliverable per
   functional spec §11 — "produce a clean, complete, auditable
   dataset for downstream users to analyze" — is unreachable without
   this segment.

3. **No retention / deletion workflow.** Segment 12B is planned at
   344 LOC of design but not started. The audit log itself is in
   canonical shape (so future export reads against a stable schema)
   but no purge tooling exists. Functional spec §12.2 enumerates
   retention windows and §12.4 defines the delete-and-archive
   workflow; today the only deletion is hard-delete via
   `POST /sessions/{id}/delete`.

4. **Inline-edit is officially deferred.** Roster + assignment
   surfaces support **CSV replace** and **delete-all + re-upload**
   only. A typo fix for one reviewer's name today requires a fresh
   CSV. Per `unfinished_business.md` #25, inline-row edit is a
   Segment 15 concern bundled with AG Grid (#33).

5. **`views.py` is 3,483 lines.** Single largest file in the codebase
   post-refactor. Holds every view-shape adapter — the boundary
   between business logic (services) and template iteration. The
   recently-shipped `routes_operator` split shows the same medicine
   (split by feature area into `_lobby.py`, `_session_home.py`, etc.)
   would apply naturally; not yet a planned segment.

6. **`_instruments.py` is 1,226 lines.** The largest slice file
   post-refactor. Houses ~25 routes covering instrument CRUD +
   response/display field CRUD + response-type definitions + bulk
   visibility/accepting toggles + lifecycle (open/close/visibility).
   Cohesive but big; another slice-by-sub-feature would not be
   unreasonable.

7. **Production hardening pending.** Segment 14 covers Key Vault
   (today: SMTP encryption key as App Service config setting), VNet
   integration (today: public Postgres with firewall allow-list),
   soft-delete (today: hard-delete on
   `POST /sessions/{id}/delete`), and full Postgres-only
   pytest. Pre-pilot blocker.

8. **AG Grid + autosave deferred.** Reviewer surface uses plain
   HTML `<input>` / `<textarea>` / `<select>` per cell with form-based
   save. Works; doesn't autosave. Larger reviewer cohorts on dense
   matrices may want better in-cell typing UX before pilot scale.
   Tracked at `unfinished_business.md` #33 / Segment 15.

9. **`guide/archive/` weighs 22k LOC.** ~3 × the active guide volume.
   Segment plans are deliberately thorough (each one runs ~500-1500
   LOC of design detail); the cadence of "plan, ship, archive" means
   archive accretes. For a citizen project this is heavy but not
   actively harmful — the archive is read by humans and AI agents
   doing decision archaeology, not parsed by tooling. Could be
   compressed once segment plans stop being load-bearing for
   debugging.

10. **No multi-tenant story.** Single-deployment by design (functional
    spec §3 explicit non-goal). Worth flagging because if anyone
    asks "can we deploy this for two departments?", the answer
    today is "two App Services + two Postgres". Not necessarily a
    weakness — just a constraint.

11. **No reviewer self-service profile.** Reviewers can submit
    responses but cannot view past submissions across sessions or
    edit profile metadata. Spec §5.2 and §8 don't require this in
    the MVP, but pilot feedback may.

12. **CSRF leans on Easy Auth.** `docs/authentication.md` records the
    decision: rely on Microsoft Entra Easy Auth + `SameSite=Lax`
    cookies, no in-app CSRF tokens. This is correct for the deployed
    environment; if the system ever gets behind a different
    auth proxy, the assumption needs revisiting. Worth flagging
    because the documentation is in `docs/`, not in the routes
    themselves.

13. **Reviewer surface cell editing is not type-rich.** Numeric
    fields use `<input type="number">` with min/max/step; long-text
    uses `<textarea>`. A reviewer typing through 50 rows × 6 columns
    is fine but undelighted. Pre-pilot polish target.

## 6. LOC budget estimate to project completion

Past segments suggest a **~2-3 ×** code-to-plan-LOC inflation
(Segment 13A's plan was ~800 LOC and shipped ~2,500 LOC of code).
Tests run ~1.4 × production code per the current ratio. Templates
and migrations scale with feature area.

Estimating from the seven remaining planned segments:

| Segment | Plan LOC | Estimated code | Estimated tests | Migrations |
|---|---:|---:|---:|---:|
| 12A — export / import | 1,242 | ~2,500 | ~1,800 | 1 |
| 12B — audit retention | 344 | ~700 | ~500 | 1 |
| 13B — sort by reviewee | 226 | ~600 | ~500 | 1 |
| 13C — enhanced instruments | 187 | ~1,200 | ~900 | 1 |
| 14 — production hardening | 521 | ~1,500 | ~500 | 0 |
| 14-1 — email infrastructure | 314 | ~1,800 | ~1,200 | 1 |
| 15 — operator polish + docs | 150 (stub) | ~3,000 | ~1,500 | 1 |
| **Total remaining** | | **~11,300** | **~6,900** | **6** |

### Likely shape at completion

| Area | Today | At completion (estimate) |
|---|---:|---:|
| `app/` Python | 21,200 | **~32,500** |
| Tests Python | 29,811 | **~36,700** |
| Templates | 8,029 | **~9,500** |
| Alembic migrations | 22 files / 2,274 LOC | **~28 files / 2,800 LOC** |
| Specs | 8,936 | **~11,500** |
| Guides (active + archive) | 28,206 | **~38,000** |
| Total project (all artifacts) | ~99,500 LOC | **~131,000 LOC** |

**Production Python at completion: ~32-33k LOC, +50% over today.**
The biggest single growth area is Segment 15 (operator polish +
docs + AG Grid + tech-support contact + magic-link auth + sessions-list
delete + inline edit). Past segment-15-shaped work in this codebase
(see Segment 11A as a precedent) tends to inflate beyond its initial
stub once it lands.

These estimates carry roughly ±25% uncertainty. The largest
unknown is Segment 15 — it's a deliberate catch-all, currently a
150-LOC stub that points at six catalog items.

## 7. One-line verdict

A disciplined, well-tested, well-documented FastAPI monolith at
~21k LOC of production code, ~30k LOC of tests, with **10 of 16 MVP
acceptance criteria fully met** and the remaining six tractably
sequenced under five known segment plans. The two blockers between
"runs locally" and "runs a real pilot" are **email send activation
(14-1)** and **data export (12A)**; everything else is polish or
production hardening.
