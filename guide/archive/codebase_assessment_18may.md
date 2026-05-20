# Codebase assessment — 2026-05-18

**As of:** the close of the **Segment 14A** in-app
production-hardening ladder — structured logging, global error
handling, a database index review, a permission /
destructive-action audit, a basic accessibility pass, a
fail-fast configuration check, the operational documentation
set, and dev-deploy-workflow hardening — landed on top of the
Segment 18 family (lobby / date-time / purge / export-import),
the Segment 15 family, the Sys-Admin arc (16A / 16B / 16C), 13B,
and 17A housekeeping. Numbers taken on `main` at `2442bd1`.
Citizen project — single author + AI-agent cadence, not yet
pilot-deployed.

This is a **standalone** snapshot of the current state, written
fresh rather than as a delta over a prior assessment. Earlier
snapshots (09may / 11may / 16may / 17may) are retained for the
audit trail. Authoritative ship-state lives in `docs/status.md`;
the functional spec audited against is
`guide/archive/functional_spec.md`.

---

## 1. What's in the box

A FastAPI + Jinja + SQLAlchemy 2.x server-rendered monolith
implementing the full **operator-setup → reviewer-response**
loop end-to-end. An operator creates a review session, uploads
rosters of reviewers and reviewees, configures one or more
instruments (response-type definitions, display + response
fields), pins assignment rules (a seeded Full Matrix or an
operator-authored RuleSet via the Rule Builder), validates,
activates, and monitors progress on a Workflow Card. Reviewers
reach a tabular response surface (Azure Easy Auth or a tokened
invite link), save drafts, and submit. The operator exports
per-session CSVs (or one zip bundle), reviews a per-session
audit log, and purges or archives the session.

The application is observable and fails safe at its boundaries:
structured JSON logs on stdout, a global exception handler that
renders friendly error pages (and logs — never leaks —
tracebacks), and a startup check that refuses to boot a
misconfigured deployed environment. An operational documentation
set (deployment, runbook, troubleshooting, backup/restore,
security posture, known limitations) backs a pilot.

## 2. Size (LOC)

| Area | Files | LOC |
|---|---|---|
| `app/` Python (production) | 138 | 38,134 |
| `app/` Jinja templates | 55 | 13,289 |
| `alembic/` migrations | — | 3,597 |
| **Production subtotal** | | **~55,000** |
| `tests/` | 190 | 58,326 |
| **Grand total** | | **~113,000** |

Test-to-production-Python ratio **~1.5×**. Largest production
file: `session_config_io/_apply.py` (1,223 LOC); only ~7 files
exceed 800 LOC, each a cohesive single concern — no re-formed
monolith despite steady growth across ~20 segments.

## 3. Functional-spec compliance

**§21 — MVP acceptance criteria: 14 / 16 fully met, 2 partial.**

Fully met (14): session creation / config, reviewer + reviewee
upload and inline edit, instrument config, full-matrix +
rule-based assignment, readiness validation, Microsoft /
unique-link access, the reviewer tabular surface, save / submit,
the operator progress dashboard, CSV export, the audit log, and
basic retention / deletion (§21 #16, via the Segment 18C
operator-triggered purge).

Partial (2): **#8 email invitations** and **#13 reminder
sending**. Both enqueue `email_outbox` rows at `status="queued"`
and never transmit — a deliberate deferral. `SmtpEmailTransport`
exists and the pluggable transport seam is in place, but no call
site invokes it; the driver and dispatch worker are Segment 14B.

**§22 — Expanded release:** substantially met — multi-instrument
sessions, the Rule Builder, dry-run reconcile counts,
post-activation correction, richer audit views, role delegation,
admin dashboards, session cloning. Targeted reminders by
completion state and scheduled retention remain (14C / 18G).

**§23 — end-to-end acceptance cycle:** the whole cycle runs
without developer intervention except the two email-send steps,
which degrade gracefully to a dev outbox.

**Verdict:** functionally an MVP-complete operator / reviewer
tool. The one true functional shortfall is **email send**.

## 4. Strengths

- **Layering is genuinely respected.** Route handlers parse the
  request and call services; they never `commit` or carry
  business rules. The `app/web/views/` adapter seam is real and
  consistently used. Operator route slices import only
  `_shared` — no slice-to-slice coupling.
- **Tech-debt hygiene is unusually clean** for a single-author
  project: **zero `# TODO` / `# FIXME` / `# XXX` / `# HACK`**
  markers across `app/` and `tests/`. Deferred work lives in
  `guide/` segment plans and `guide/deferred_infra.md`, not as
  code rot. The `sqlalchemy.dialects.postgresql` ban in models
  is fully honoured.
- **Observability and boundary safety are now in place.**
  Stdlib-only JSON logging configured at startup; a global
  exception handler renders standalone friendly error pages for
  `HTTPException` / `RequestValidationError` / any unhandled
  error, logging the full traceback to the structured stream
  and never showing it to a user. A fail-fast `validate_critical_settings`
  check refuses to boot a deployed environment with an empty
  operator allowlist.
- **The security posture is documented and audited.**
  `docs/security_posture.md` records the four-gate authorization
  model, the Easy Auth trust model, the CSRF decision, and the
  deferred-infrastructure list; a §5.6 / §5.7 review walked
  every route's permission dependency and every destructive
  action's confirm + audit gating and found **no gaps**.
- **Audit discipline scales** — 117 `EVENT_SCHEMAS`
  registrations under one canonical envelope, strict-mode
  validated in tests.
- **Genuine test coverage** — ~1,870 tests, integration-first
  via `TestClient` so real request → service → DB paths are
  exercised; complex pure logic (`session_config_io`, extracts,
  RTDs, the rule engine) has dedicated unit suites. Dual-dialect
  CI (SQLite + a `postgres:16` job) plus `ruff`.
- **Controlled file sizes**, consistent conventions, and a
  three-layer architecture that has held across ~20 segments.

## 5. Weaknesses

- **Email send is inert** — the single largest functional gap
  and a hard pilot blocker. Gated on the host institution's
  transport choice; Segment 14B.
- **Azure infrastructure is deferred, not done.** The *in-app*
  hardening shipped (Segment 14A), but the *platform* side has
  not: no Key Vault (secrets and `database_url` flow through
  plain Pydantic env settings), no VNet / private endpoints, no
  staging slot, no production environment, and no Application
  Insights resource (logs are structured and ingestion-ready
  but nothing ingests them yet). All are documented as
  prerequisites in `guide/deferred_infra.md` and the deployment
  guide — they need the Azure portal, not code.
- **The auth trust model is thin by design.** Identity depends
  entirely on Azure Easy Auth populating `X-MS-CLIENT-PRINCIPAL*`
  headers, trusted verbatim with no in-app signature check —
  correct *if and only if* the platform gate is enforced. This
  is now deliberately documented rather than implicit, and
  CSRF protection (no anti-CSRF tokens; reliance on Easy Auth +
  `SameSite=Lax`) is a recorded decision. Residual risk: a
  deployment must verify Easy Auth is enabled and
  `ALLOW_FAKE_AUTH` is off — the startup check guards the
  empty-allowlist footgun but, by deliberate scoping, does
  **not** hard-fail on `ALLOW_FAKE_AUTH=true` in a deployed
  environment. Adding that assertion is a reasonable future
  tightening.
- **Migration ordering is exercised only by the Postgres CI
  job** — the SQLite suite builds the schema with `create_all`,
  not a migration replay. That job should be a required status
  check on PRs.
- **Minor.** `requirements.txt` is hand-synced against
  `pyproject.toml`'s runtime dependencies; the `--text-muted`
  colour token fails WCAG AA contrast and is still used on
  operator chrome (flagged in the Segment 14A accessibility
  pass, left for a later sweep).

## 6. Bugs and regressions

The 17may bug hunt's three defects — one HIGH (deleting an
in-use response type aborted on an FK violation) and two LOW
(a misrolled "submitted" pill; engine pair-dedup keyed on
email) — were all fixed on 2026-05-18, each with a regression
test.

One regression shipped during the Segment 14A ladder and was
caught the same day: PR #1146 attached a GitHub `environment: dev`
to the deploy job, which changed the OIDC subject claim GitHub
presents to Azure (`…:ref:refs/heads/main` →
`…:environment:dev`) so `azure/login` failed with `AADSTS700213`;
PR #1147 reverted the one line and the deploy recovered. A
review of the 14A additions — `logging_config.py`,
`web/error_handlers.py`, `validate_critical_settings`, and the
`ix_audit_events_session_created` migration — surfaced no new
correctness defects: the changes are additive, narrowly scoped,
and test-covered.

## 7. Estimated size upon completion

The remaining workplan: **14B** (email infrastructure), **14C**
(reminders workflow), **13C** (enhanced / group-scoped
instruments), **17B** (reviewer-surface refinements — partly
landed), **18E** (small enhancements), **18G** (scheduled
events), **19 / 20** (spec / doc sweeps), and **21**
(peer-review / reviewee surface). Segment 14A is now closed.

Rough estimate, extrapolating from recent segment sizes:

| | Now | At completion (est.) |
|---|---|---|
| Production (`app/` + templates + migrations) | ~55k | **~70–80k** |
| Tests | ~58k | **~80–95k** |
| **Grand total** | ~113k | **~150–175k** |

The dominant swing factor is **Segment 21** — bringing the
reviewee online as a third live audience is a whole new surface;
if its full scope lands, completion trends to the upper bound.
19 / 20 are documentation-weighted and add little code. So the
codebase is roughly **65–75% of its final size**, and
functionally further along than that — the remaining LOC is
concentrated in infrastructure (14B / 14C) and one post-MVP
audience (21), not core operator / reviewer features.

## 8. Bottom line

A disciplined, well-layered, genuinely well-tested FastAPI
monolith with unusually clean tech-debt hygiene for a
single-author + AI-agent citizen project. Functionally it is an
MVP-complete operator / reviewer tool — 14 / 16 MVP criteria
fully met, the loop runs end-to-end.

With the Segment 14A ladder landed, the pilot-readiness picture
has narrowed. Observability, boundary error handling, the
permission audit, and a documented security posture — all
previously flagged gaps — are now addressed. Two things still
gate a real pilot: **email transport (14B)**, the lone
functional blocker, and **standing the deployment up on real
Azure infrastructure** — Key Vault, a verified-enforced Easy
Auth gate, and the rest of the deferred platform list — for
which the runbooks and the deferred-infrastructure inventory
now exist. No open correctness defects: the 17may hunt's three
bugs are fixed, and the one deploy regression from the 14A
window was reverted the same day.
