# Codebase assessment — 2026-05-19

**As of:** the close of **Segment 13C** (Enhanced instruments —
group-scoped instruments + the Replicate-instrument button),
landed on top of the Segment 14A production-hardening ladder, the
Segment 18 family (lobby / date-time / purge / export-import),
the Segment 15 family, the Sys-Admin arc (16A / 16B / 16C), 13B,
and 17A housekeeping. Numbers taken on `main` at `8b6112d`.
Citizen project — single author + AI-agent cadence, not yet
pilot-deployed.

A **standalone** snapshot, written fresh rather than as a delta.
Earlier snapshots (09may / 11may / 16may / 17may / 18may) are
retained for the audit trail. Authoritative ship-state lives in
`docs/status.md`; the functional spec audited against is
`guide/archive/functional_spec.md`.

---

## 1. What's in the box

A FastAPI + Jinja + SQLAlchemy 2.x server-rendered monolith
implementing the full **operator-setup → reviewer-response** loop
end-to-end. An operator creates a review session, uploads rosters
of reviewers and reviewees, configures one or more instruments
(response-type definitions, display + response fields), pins
assignment rules (a seeded Full Matrix or an operator-authored
RuleSet via the Rule Builder), validates, activates, and monitors
progress on a Workflow Card. Reviewers reach a tabular response
surface (Azure Easy Auth or a tokened invite link), save drafts,
and submit. The operator exports per-session CSVs (or one zip
bundle), reviews a per-session audit log, and purges or archives
the session.

**New since the 18may snapshot — Segment 13C.** A second
instrument flavour, the **group-scoped instrument**: one reviewer
answer covers a whole boundary-defined group of reviewees. Group
boundary tags partition a reviewer's universe; a reviewer answer
fans out to identical Response rows on every group member and
collapses back to one row on read; the reviewer surface renders
one row per group; reviewer-state, monitoring, and the Extract
Data CSV count a group response once. A persisted per-instrument
reviewer-group pair count (migration `c3a9f1d7b2e8`), a
grouping-tag-change defunct safeguard, and the **Replicate**
instrument button round it out. Follow-ons: the Assignments-page
refinement cards, the app-wide confirm-checkbox-gates-button
standard, and the normal / group instrument-card harmonization.

The application is observable and fails safe at its boundaries:
structured JSON logs on stdout, a global exception handler that
renders friendly error pages (logging — never leaking —
tracebacks), and a startup check that refuses to boot a
misconfigured deployed environment. An operational documentation
set (deployment, runbook, troubleshooting, backup/restore,
security posture, known limitations) backs a pilot.

## 2. Size (LOC)

| Area | Files | LOC |
|---|---:|---:|
| `app/` Python (production) | 138 | 40,073 |
| `app/` Jinja templates | 55 | 13,835 |
| `alembic/` migrations | 44 | 3,625 |
| **Production subtotal** | | **~57,500** |
| `tests/` | 191 | 60,352 |
| **Grand total** | | **~118,000** |

Test-to-production-Python ratio **~1.5×**. Largest production
file: `session_config_io/_apply.py` (1,223 LOC). **File-size
creep is the one watch item here:** 13C inflated several services
— **13 files now exceed 800 LOC** (the 18may snapshot had ~7),
and four sit above 1,150 (`_apply.py` 1,223, `responses.py`
1,216, `assignments.py` 1,189, `routes_operator/_instruments.py`
1,179). Each is still a cohesive single concern, but the
trajectory suggests another 17A-style housekeeping split is worth
scheduling before they harden.

## 3. Functional-spec compliance

**§21 — MVP acceptance criteria.** Substantively unchanged from
the 18may read; 13C is a §22 feature and does not move §21.
**14 / 16 fully met, 2 inert.** Fully met: session creation /
config, reviewer + reviewee upload and inline edit, instrument
config (now single, multi, and group), full-matrix + rule-based
assignment, readiness validation, Microsoft / unique-link access,
the reviewer tabular surface, save / submit, the operator
progress dashboard, CSV export, the audit log, and basic
retention / deletion (§21 #16, via the 18C operator-triggered
purge). Two notes: #5 "manual assignment upload/edit" was
**deliberately superseded** in 15D (assignments are always
derived — full-matrix or rule-based — not hand-authored), and
#14's Excel half was never built (CSV only — judged sufficient).

Inert (2): **#8 email invitations** and **#13 reminder sending**.
Both enqueue `email_outbox` rows at `status="queued"` and never
transmit — a deliberate deferral. `SmtpEmailTransport` exists and
the pluggable transport seam is in place, but no call site
invokes it; the driver and dispatch worker are Segment 14B.

**§22 — Expanded release:** substantially met and now further
along — multi-instrument **and group-scoped** instruments, the
Rule Builder, dry-run reconcile counts, post-activation
correction, richer audit views, role delegation, admin
dashboards, session cloning. Targeted reminders by completion
state and scheduled retention remain (18G).

**§23 — end-to-end acceptance cycle:** the whole cycle runs
without developer intervention except the two email-send steps,
which degrade gracefully to a dev outbox.

**Verdict:** functionally an MVP-complete operator / reviewer
tool. The one true functional shortfall is **email send**.

## 4. Strengths

- **Layering is genuinely respected.** Route handlers parse the
  request and call services; they never `commit` or carry
  business rules. The `app/web/views/` adapter seam is real and
  consistently used. Operator route slices import only `_shared`.
- **Tech-debt hygiene stays unusually clean** — **zero `# TODO` /
  `# FIXME` / `# XXX` / `# HACK`** markers across `app/` and
  `tests/`. Deferred work lives in `guide/` plans, not as code
  rot. The `sqlalchemy.dialects.postgresql` ban in models holds.
- **13C landed cleanly.** A genuinely intricate feature (write
  fan-out, collapse-on-read, partition-aware rendering, a
  persisted cache) shipped with the perf-conscious touches in
  place — `group_keys` is hoisted out of per-reviewer /
  per-instrument loops, no N+1 reintroduced — and the suite
  stayed green.
- **Observability and boundary safety are in place** — stdlib
  JSON logging, a global exception handler, a fail-fast
  `validate_critical_settings` startup check.
- **The security posture is documented and audited** —
  `docs/security_posture.md` records the four-gate authorization
  model, the Easy Auth trust model, and the CSRF decision; the
  14A review found no permission or destructive-action gaps.
- **Audit discipline scales** — ~115 `EVENT_SCHEMAS`
  registrations under one canonical envelope, strict-mode
  validated in tests; every 13C emitter is registered.
- **Genuine test coverage** — **1,910 tests** (1 skipped),
  integration-first via `TestClient`, with dedicated unit suites
  for the complex pure logic. Dual-dialect CI (SQLite + a
  `postgres:16` job) plus `ruff`. Suite is **green**, ruff
  **clean**.

## 5. Weaknesses

- **Email send is inert** — the single largest functional gap
  and a hard pilot blocker. Gated on the host institution's
  transport choice; Segment 14B.
- **Azure infrastructure is deferred, not done.** The *in-app*
  hardening shipped (14A), but the *platform* side has not: no
  Key Vault, no VNet / private endpoints, no staging slot, no
  production environment, no Application Insights resource. All
  documented in `guide/deferred_infra.md` and the deployment
  guide — they need the Azure portal, not code.
- **The auth trust model is thin by design.** Identity depends
  entirely on Azure Easy Auth populating `X-MS-CLIENT-PRINCIPAL*`
  headers, trusted verbatim — correct only if the platform gate
  is enforced. Documented, not implicit; the startup check does
  **not** hard-fail on `ALLOW_FAKE_AUTH=true` in a deployed
  environment (a reasonable future tightening).
- **One open correctness defect** — see §6: the config CSV
  round-trip is broken for group-scoped instruments. New with
  13C; should be fixed before the Settings-CSV round-trip or
  session-clone path is relied on for group-instrument sessions.
- **File-size creep** (see §2) — 13C pushed 13 files past 800
  LOC; schedule a housekeeping split.
- **Migration ordering is exercised only by the Postgres CI
  job** — the SQLite suite builds the schema with `create_all`.
  That job should be a required status check on PRs.
- **Minor.** `requirements.txt` is hand-synced against
  `pyproject.toml`; the `--text-muted` colour token fails WCAG AA
  contrast and is still used on operator chrome.

## 6. Bugs and regressions

A fresh bug hunt focused on the new 13C surface. The 17may hunt's
three defects were all fixed on 2026-05-18 with regression tests;
this pass found **one new HIGH defect and two suspected lower
ones**, all in 13C code.

1. **HIGH — config CSV round-trip broken for group-scoped
   instruments.** `session_config_io/_serialize.py:323` exports
   the raw `group_kind` column value — which the runtime codec
   writes as boundary codes (`r1`/`r2`/`r3`/`p1`/`p2`/`p3`) or
   the no-boundary sentinel. But `session_config_io/_apply.py`
   `_parse_group_kind` (line 764) accepts only `tag_1`/`tag_2`/
   `tag_3` (`_VALID_GROUP_KINDS`, line 199). Importing any
   exported config containing a group-scoped instrument raises
   `_ParseError`; a hand-authored `tag_1` would be stored
   verbatim and then silently skipped by `decode_group_kind`,
   producing a group instrument with an empty boundary. No test
   covers this path. Fix: serialize / parse through
   `encode_group_kind` / `decode_group_kind`.
2. **MEDIUM — suspected — defunct safeguard mis-targets on a
   re-pointed relationship.** `defunct_group_responses_for_
   relationship_tag_change` reads `relationship.reviewer_id` /
   `reviewee_id` *after* the edit's `setattr` has applied. If an
   operator re-points a relationship to a different pair *and*
   changes a grouping tag in one edit, the old pair's
   group-scoped responses are left mis-attributed. Needs closer
   confirmation.
3. **LOW — suspected — defunct safeguard can over-defunct.**
   `defunct_group_responses_for_tag_change` deletes group
   responses for all assignments on affected instruments, even
   where the tag change does not actually move the reviewee to a
   different group. Harmless per the "lossless" claim *unless*
   the reviewer is the sole group member. Worth checking against
   that claim.

No regressions found in the non-13C surface; the suite is green
(1,910 passed) and ruff is clean.

## 7. Estimated size upon completion

13C is now shipped; 17B closed. The remaining MVP workplan:
**14B** (email infrastructure), **18E** (small enhancements,
ongoing), **18F** (workflow optimization — Prepare/Activate split
+ Activated-as-gate), **18G** (scheduled events — auto-archive,
auto-send, scheduled activation, reminders), **19 / 20** (spec /
doc sweeps), and **13F PRs 4-5** (small DB prep). The post-MVP
**participant-model arc (segments 21+)** is tracked separately
and is out of the MVP scope.

| | Now | At MVP completion (est.) |
|---|---:|---:|
| Production (`app/` + templates + migrations) | ~57.5k | **~67–73k** |
| Tests | ~60k | **~75–85k** |
| **Grand total** | ~118k | **~145–160k** |

14B is the dominant remaining block (email transport + the
dispatch worker + backend swaps); 18F / 18G are moderate; 18E /
19 / 20 are documentation-weighted and add little code. The
codebase is therefore roughly **75–80% of its final MVP size**,
and functionally further along than that — the remaining LOC is
concentrated in email/scheduling infrastructure, not core
operator / reviewer features. The **participant-model arc**, if
pursued, is a whole new audience surface and would push the
total well past the MVP figure (a further ~+15–25k).

## 8. Bottom line

A disciplined, well-layered, genuinely well-tested FastAPI
monolith with unusually clean tech-debt hygiene for a
single-author + AI-agent citizen project. Functionally it is an
MVP-complete operator / reviewer tool — 14 / 16 §21 criteria
fully met, the loop runs end-to-end — and 13C added a genuinely
intricate second instrument flavour without disturbing the
architecture.

Three things stand between here and a pilot: **email transport
(14B)**, the lone functional blocker; **standing the deployment
up on real Azure infrastructure**; and the **one HIGH bug** found
this pass — the group-instrument config round-trip — which is
small and well-localised but should be fixed before the
Settings-CSV / clone path is trusted for group-instrument
sessions. The two suspected defunct-safeguard issues warrant
confirmation. Beyond that, the watch item is file-size creep:
13C inflated several services, and a housekeeping split in the
spirit of 17A is worth scheduling.
