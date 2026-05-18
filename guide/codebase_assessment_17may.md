# Codebase assessment — 2026-05-17

**As of:** end of the **Segment 18 family** landing window — 18A
(Sessions lobby enhancements), 18B (date/time settings), 18C
(operator-triggered purge), 18D (export/import update) — on top
of the Segment 15 family, the Sys-Admin arc (16A/16B/16C), 13B,
and 17A housekeeping. Numbers taken on `main` at `f46abb8`.
Citizen project — single author + AI-agent cadence, not yet
pilot-deployed.

This is an audit-style snapshot, one day after
[`codebase_assessment_16may.md`](codebase_assessment_16may.md).
Authoritative ship-state lives in `docs/status.md`; the
functional spec audited against is
`guide/archive/functional_spec.md` (§ numbers unchanged since
relocation). Earlier snapshots: 09may / 11may / 16may.

---

## 1. What's in the box

A FastAPI + Jinja + SQLAlchemy 2.x server-rendered monolith
implementing the full **operator-setup → reviewer-response**
loop end-to-end. An operator creates a review session, uploads
rosters of reviewers and reviewees, configures one or more
instruments (response-type definitions, display + response
fields), pins assignment rules (seeded Full Matrix or an
operator-authored RuleSet via the Rule Builder), validates,
activates, and monitors progress on a Workflow Card. Reviewers
reach a tabular response surface (Easy Auth or a tokened invite
link), save drafts and submit. The operator exports per-session
CSVs (or one zip bundle), reviews a per-session audit log, and
purges or archives the session.

Since the 16may baseline the **Sessions lobby** was rebuilt
(tagging, archiving, one-click cloning, inline row-expander
actions, search), **operator-triggered purge** shipped, and the
**export/import surface** was refreshed (Settings-CSV parity,
a restructured analysis-facing Responses extract, the Zip-all
bundle).

## 2. Size (LOC)

| Area | Files | LOC |
|---|---|---|
| `app/` Python (production) | 136 | 37,664 |
| `app/` Jinja templates | 54 | 13,164 |
| `alembic/` migrations | — | 3,540 |
| **Production subtotal** | | **~54,400** |
| `tests/` | 186 | 57,657 |
| **Grand total** | | **~112,000** |

Test-to-production ratio **~1.5×**. Largest production file:
`session_config_io/_apply.py` (1,223 LOC); only ~6 files exceed
800 LOC, each a cohesive concern — no re-formed monolith despite
steady growth.

## 3. Functional-spec compliance

**§21 — MVP acceptance criteria: 14 / 16 fully met, 2 partial.**

Fully met (14): session creation/config, reviewer + reviewee
upload/inline-edit, instrument config, manual + full-matrix
assignment, readiness validation, Microsoft / unique-link
access, reviewer tabular surface, save/submit, operator
progress dashboard, CSV export, basic audit log, and — closed
**this week** by Segment 18C (`session_purge.py`) — **basic
retention/deletion (§21 #16)**, the lone item the 16may
assessment flagged unmet.

Partial (2): **#8 email invitations** and **#13 reminder
sending**. Both enqueue `email_outbox` rows at `status="queued"`
and never transmit — a deliberate deferral. `SmtpEmailTransport`
exists in `email_send.py` but no call site invokes
`transport_for`; the pluggable seam is in place, the driver and
dispatch worker are Segment 14B.

**§22 — Expanded release:** substantially met — multi-instrument,
Rule Builder, dry-run counts, post-activation correction
(reconciling regeneration), richer audit views, role delegation,
admin dashboards, session cloning. Targeted reminders by
detailed completion state and scheduled retention remain
(14C / 18F).

**§23 — end-to-end acceptance cycle:** the whole cycle runs
without developer intervention except the two email-send steps,
which degrade to a dev outbox.

**Verdict:** functionally an MVP-complete operator/reviewer
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
  `guide/` segment plans, not as code rot. The
  `sqlalchemy.dialects.postgresql` ban in models is fully
  honoured.
- **Audit discipline scales** — 117 `EVENT_SCHEMAS`
  registrations under one canonical envelope, strict-mode
  validated in tests.
- **Genuine test coverage** — ~1,800 tests, ~79% integration /
  21% unit by LOC, integration-first via `TestClient` so real
  request→service→DB paths are exercised; complex pure logic
  (`session_config_io`, extracts, RTDs) has dedicated unit
  suites. Dual-dialect CI (SQLite + a `postgres:16` job) plus
  `ruff`.
- **Controlled file sizes**, consistent conventions, a coherent
  three-layer architecture that has held across ~18 segments.

## 5. Weaknesses

- **Email send is inert** — the single largest functional gap
  and a hard pilot blocker (gated on the host institution's
  transport choice; Segment 14B).
- **Production hardening (Segment 14A) untouched** — no Key
  Vault, no VNet, no soft-delete; secrets and `database_url`
  flow through plain Pydantic env settings.
- **Auth trust model is thin by design.** Identity depends
  entirely on Azure Easy Auth populating
  `X-MS-CLIENT-PRINCIPAL*` headers, trusted verbatim with no
  in-app signature check — correct *if and only if* the
  platform gate is enforced. There are **no anti-CSRF tokens**
  on the plain `<form method="post">` mutations; CSRF
  protection leans entirely on Easy Auth. `ALLOW_FAKE_AUTH`
  defaults off and is double-gated, but must be verified off in
  every deployed slot.
- **Sparse boundary error handling** — only ~10 service modules
  contain any `except`; `main.py` registers one exception
  handler. Malformed CSV imports and DB integrity errors will
  surface as raw 500s.
- **Migration ordering is exercised only by the Postgres CI
  job** — the SQLite suite uses `create_all`, not migration
  replay. That job should be mandatory on PRs.

## 6. Bugs found

### HIGH — deleting an in-use response type with saved responses fails with an FK violation

`delete_response_type_definition`
(`app/services/instruments/_rtds.py`) does `db.delete(rtd)` and
relies on a DB-level `ON DELETE CASCADE` to remove the dependent
`instrument_response_fields` rows. The cascade chain is broken
one link down:

- `instrument_response_fields.response_type_id` → CASCADE ✓
- `responses.response_field_id` → **no `ondelete`** (defaults
  to `NO ACTION`; `app/db/models/response.py:28`)

So when an operator confirms deletion of a response type whose
fields have any saved `Response` rows, the DB tries to delete
the `instrument_response_fields` rows, the `responses` still
reference them, and the statement aborts. This fails on both
**Postgres** and **SQLite** — `app/db/session.py:20` turns on
`PRAGMA foreign_keys = ON`. The `delete_response_type_definition`
docstring claims "the cascade fires through the FK ON DELETE
CASCADE", but it does not for in-use types. No test covers
RTD-delete-after-responses-exist, so the suite is green.

*Impact:* a pilot operator making a normal late-setup
correction (delete a response type that has collected real
responses) gets a 500 / failed transaction instead of the
documented cascade delete.

*Fix direction:* add `ondelete="CASCADE"` to
`responses.response_field_id` (model + migration), or have
`delete_response_type_definition` delete the dependent
`Response` rows explicitly before `db.delete(rtd)`.

### LOW — "submitted" pill on a no-required-field instrument

`responses._state_from_assignments` can show a draft as
"submitted" on the dashboard for an instrument with zero
required fields (the `all_required_with_submitted` check
inspects an empty set). Display-only; no data corruption.

### LOW — engine pair dedup keys on email

`rules/engine.py` `_pair_sort_key` collapses pairs by
`(reviewer.email, reviewee identifier)` for `ANY_OF` /
`PIPELINE`, while diffing keys by id. CSV import blocks
duplicate reviewer emails, so this is safe today; reviewers
added via a non-CSV path sharing an email could silently merge.

No other high-severity correctness defects were found across
the assignment-generation, lifecycle, purge, clone, CSV-import,
or audit paths.

## 7. Estimated size upon completion

The remaining workplan: **14A** (production hardening), **14B**
(email infrastructure), **14C** (reminders workflow), **13C**
(enhanced/group-scoped instruments), **17B** (reviewer-surface
refinements — partly landed), **18E** (small enhancements),
**18F** (scheduled events), **19/20** (spec/doc sweeps), **21**
(peer-review / reviewee surface).

Rough estimate, extrapolating from recent segment sizes
(18A ≈ 3–4k production LOC; 18C/18D ≈ 0.5–1k each; the
15-family larger):

| | Now | At completion (est.) |
|---|---|---|
| Production (`app/` + templates + migrations) | ~54k | **~70–80k** |
| Tests | ~58k | **~80–95k** |
| **Grand total** | ~112k | **~150–175k** |

The dominant swing factor is **Segment 21** — bringing the
reviewee online as a third live audience is a whole new
surface; if its full scope lands, completion trends to the
upper bound. 19/20 are documentation-weighted and add little
code. So **the codebase is roughly 65–75% of its final size**,
and functionally much further along than that — the remaining
LOC is concentrated in infrastructure (14A/B/C) and one
post-MVP audience (21), not core operator/reviewer features.

## 8. Bottom line

A disciplined, well-layered, genuinely well-tested FastAPI
monolith with unusually clean tech-debt hygiene for a
single-author + AI-agent citizen project. Functionally it is an
MVP-complete operator/reviewer tool — 14/16 MVP criteria fully
met, the loop runs end-to-end. Before a real pilot, three
things gate readiness: **email transport (14B)**, **production
hardening (14A)**, and **explicit verification that the Azure
Easy Auth gate is enforced** — plus a recommended pass on
boundary error handling and CSRF posture. One **HIGH-severity
bug** (RTD-delete FK gap) should be fixed regardless; it is a
small, well-understood change.
