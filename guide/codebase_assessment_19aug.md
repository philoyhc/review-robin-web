# Codebase assessment — 2026-08-19

**As of:** the close of **Segment 18R** (Items 1–5 all shipped — the
save/lock harmonization plus the config-onto-Session-Home consolidation,
the Archive-card harmonization, and the bulk-toggle retirement + chrome
Responses pill) and **18S Item 3** (sys-admin cross-session writes now
require real ownership), on top of a full **Segment 19 documentation-hygiene**
arc — a whole-`spec/` drift sweep and a whole-`docs/` sweep, both executed
and archived. This is a **two-day, doc-dominated sprint** (48 PRs), the
opposite cadence to the prior snapshot's 2.5-month window.

Since the 2026-08-17 snapshot:

- **18R Item 4 — session config consolidated onto Session Home**
  (PRs #1931 → #1962, ~20 PRs, 2026-08-17 → 08-18) — the standalone
  Edit page retired; session-details config (name / code / deadline /
  timezone / per-session toggles + Owners) now displays and edits
  **inline** on Session Home via a `?editing=1` swap and `POST …/config`.
  Scaffold-first: placeholder → mock → in-place swap → Save persistence →
  Owners add/remove → Danger Zone on Home → delete of the `/edit`
  routes + template (~55 test sites migrated to `/config`).
- **18R Item 5 — Archive-card harmonization** (PRs #1955 → #1968) — an
  Archive session card on the Extract data page, harmonized with the
  lobby "Purge and archive" into one `can_archive` gate + one
  `purge_and_archive` service + a shared `archive-selected` route.
- **18R Item 3 — bulk-toggle retirement + chrome Responses pill**
  (PRs #1963 → #1971) — removed the instruments-page bulk accepting /
  visibility-when-closed toggles (routes + services + two audit event
  types); wired the chrome status-strip Relationships / Observers /
  Responses pills, the Responses pill going data-driven with a
  `<n> drafts / <m> submitted / <reviewees>` breakdown.
- **18S Item 3 — ownership gating** (PR #1935 + a doc sweep) — cross-session
  operator writes (owners/remove, edit config, lobby rename/tag) tightened
  from the relaxed sys-admin gate to `require_session_operator`; only
  `owners/add` (self-add) + `clone` keep the relaxed gate.
- **Segment 19 — documentation hygiene** (PRs #1970 → #1978) — a
  whole-`spec/` drift sweep (18 specs refreshed; `rrw_functional_spec.md`
  + `architecture.md` thoroughly revised to current reality), then a
  whole-`docs/` sweep executed across four buckets: `docs/rehydrate.md` →
  `spec/rehydrate.md`; four docs consolidated/retired; the update-in-place
  batch; and a full README refresh. Both sweep docs archived.

All shipped 2026-08-17 → 2026-08-19 (48 merge commits, 60 non-merge, over
~2 calendar days — a high-cadence burst, the inverse of the prior window).
Numbers taken on `main` at `72cf281`. Development context unchanged:
single author + AI coding agents, pre-deployment, no production traffic.

A standalone snapshot; `guide/codebase_assessment_17aug.md` (+ its JSON
sidecar) retires to `guide/archive/` with this snapshot, per the "latest
only" convention. Authoritative ship-state lives in `docs/status.md`;
functional specs audited against live in `spec/`.

---

## 1. What's in the box

Review Robin Web is a server-rendered FastAPI + Jinja monolith for running
structured peer/self-review cycles. An **operator** creates a **session**,
imports **reviewer / reviewee / observer** rosters (CSV), authors
**instruments** (a 3-band card: an assignment rule, a display-field
preview, and typed response fields), and lets a rule-based **assignment
engine** (Full-Matrix default, self-review policy, group-scoped fan-out)
fan reviewers across reviewees. The session moves through a lifecycle
(draft → validated → ready → expired → archived) gated by a Validate page.
**Reviewers** fill a multi-page response surface; **reviewees** see a
`/results` body (Raw / Anonymized / Summarized per a visibility policy);
**observers** see a `/collation` cohort surface. Everything mutating writes
an **audit event**; operators extract the whole session as CSVs + a bundle
and can **rehydrate** a complete session back from that extract set. Stack:
Python 3.12, SQLAlchemy 2.x + Alembic on Postgres 16 (SQLite in tests),
Pydantic, Jinja2 with no JS build step, Azure Easy Auth (fake-auth locally).

**New since the 2026-08-17 snapshot** (a code-light, doc-heavy window):

- **Session config lives on Session Home now — 18R Item 4** (PRs #1931 →
  #1962). The standalone `/edit` page is gone: `GET …/edit` is a thin
  301-redirect stub and the apply route is `POST …/sessions/{id}/config`
  (`app/web/routes_operator/_session_home.py`). The `#session-config` card
  in `session_detail.html` renders a `?editing=1` display↔edit swap (the
  same pattern the instruments card uses), with Owners add/remove (a
  `last_owner` race guard via `SELECT … FOR UPDATE`) and the Danger Zone
  relocated onto Home; Extract Setup moved to the Extract data page and
  the Schedule-timeline card retired. ~55 test sites migrated off `/edit`.
- **Archive harmonization — 18R Item 5** (PRs #1955 → #1968). One
  `session_lifecycle.can_archive(session)` gate (`not is_ready and not
  is_archived`), one `session_purge.purge_and_archive(...)` service
  (audit-log → responses → rosters → archive), and a shared
  `POST /operator/sessions/archive-selected` route with a `return_to`
  param drive both the lobby "Purge and archive" expander and the new
  Archive session card on the Extract data page.
- **Chrome Responses pill + bulk-toggle retirement — 18R Item 3** (PRs
  #1963 → #1971). `SessionStatusPills` (`app/web/views/_setup.py`) gained
  `responses_drafts` / `responses_submitted` / a `responses_label`
  property: the pill reads `<n> drafts / <m> submitted / <reviewees>`
  (omitting a zero term) and "Awaiting" only when there is no response
  activity — a **data-driven gate, not lifecycle-driven**. The
  instruments-page bulk accepting / visibility-when-closed toggles and
  their routes, `bulk_set_accepting` / `bulk_set_visibility` services, and
  `instruments.bulk_accepting_responses` / `.bulk_visibility_when_closed`
  audit types were removed (visibility-when-closed is governed by the
  per-instrument visibility policy).
- **Sys-admin ownership gating — 18S Item 3** (PR #1935). Cross-session
  operator writes require `require_session_operator` (real ownership);
  `require_sys_admin_or_session_operator` now relaxes only `owners/add`
  (self-add bootstrap) + `clone`. A non-owner sys-admin elevates through
  the audited Diagnostics "Manage"/adopt door.
- **Documentation hygiene — Segment 19** (PRs #1970 → #1978). Beyond the
  content sweep (§3), the structural moves: `docs/rehydrate.md` →
  `spec/rehydrate.md`; four `docs/` files retired (`imports.md`,
  `authentication.md` → folded into `security_posture.md`,
  `codespace_setup.md` → folded into `local_setup.md`, `cli_setup_notes.md`
  → folded into `cli_setup.md`); the three deferral ledgers consolidated
  into `guide/deferred_consolidated.md`; both sweep docs archived. `docs/`
  went 20 → 16 files.

Unchanged this window: the reviewer surface, the assignment engine, the
audit subsystem, the extract pipeline, the participant-model surfaces
(observer collation, reviewee results, visibility policy), session
rehydrate (moved doc, unchanged code), and the email infrastructure
(still stubbed — see §3).

---

## 2. Size (LOC)

LOC = physical lines over git-tracked files. Deltas vs the `17aug`
sidecar (`75eea4e`); area classification unchanged from that snapshot.

| Area | Files | LOC | Δ LOC from 17aug |
|---|---|---|---|
| `production` (`app/**/*.py` + `alembic/env.py`) | 192 (192 prior) | **55,313** | +148 (+0.3%) |
| `app/web/templates/` | 59 (60) | **21,825** | +53 (+0.2%) |
| `tests/` | 250 (251) | **87,263** | +455 (+0.5%) |
| `docs` (`docs/` + `spec/` + `guide/` + top-level `*.md`) | 200 (201) | **91,109** | +2,380 (+2.7%) |
| Alembic migrations | 77 (77) | **6,772** | unchanged |

**Test-to-production-Python ratio ~1.578×** (87,263 / 55,313), flat vs
~1.57× on 17aug. **2,675 tests passing, 17 skipped** (was 2,650 + 17;
+25 over the window). Suite green on the SQLite default; the `ci-postgres`
job round-trips Alembic + runs the full suite on `postgres:16`. `ruff` clean.

**Biggest files** (top 10 production Python):

| LOC | File | Δ |
|---|---|---|
| 1,268 | `app/web/routes_operator/_instruments.py` | **-49** |
| 1,056 | `app/services/session_lifecycle.py` | +10 |
| 1,025 | `app/services/instruments/_instrument_crud.py` | **-72** |
| 984 | `app/web/routes_operator/_quick_setup.py` | +2 |
| 981 | `app/web/views/_instruments.py` | -18 |
| 976 | `app/services/responses/_core.py` | unchanged |
| 967 | `app/services/audit.py` | -3 |
| 966 | `app/services/instruments/_response_fields.py` | unchanged |
| 958 | `app/services/validation.py` | +3 |
| 942 | `app/services/csv_imports.py` | unchanged |

The plateau **eased slightly**: last window's breakout file,
`routes_operator/_instruments.py`, fell **-49 to 1,268** because the
bulk-toggle removal took code out of it, and `_instrument_crud.py` fell
**-72** (the `bulk_set_*` services deleted). No file grew materially; the
biggest single addition was `session_lifecycle.py` +10 (the `can_archive`
helper). The watchlist item from 17aug thus **receded** rather than
climbing to its ~1,400 tripwire (§9).

**Where the window's growth landed.** Production moved only **+148 LOC**
with **zero new production files** (192 → 192) — every code change this
window was an *edit to an existing file*: the `/config` apply path + Owners
routes on `_session_home.py`, `can_archive` + `purge_and_archive`
(lifecycle + `session_purge.py`), the `SessionStatusPills` draft/submitted
aggregates on `views/_setup.py`, and the bulk-toggle *deletions* that
netted several files *down*. This is the single most diagnostic figure in
§2: a 48-PR window that touched production by +0.3% because it was almost
entirely **documentation** and **UI-consolidation** work, not new code.

**Docs still outgrew code, but modestly** (+2,380 doc LOC vs +148
production). The number *understates* the doc churn: the window deleted 4
`docs/` files, moved 1 to `spec/`, consolidated 3 deferral ledgers into 1,
archived 2 sweep docs, and revised 18 spec files — a large *reshaping* of
the doc corpus that nets to only +2,380 LOC because retirement offset the
new sweep docs + revisions. `docs/` itself **shrank 20 → 16 files**.

**Package shape.** `app/services/` remains the centre of gravity
(`instruments/`, `responses/`, `assignments/`, `rules/`,
`scheduled_events/`, `session_config_io/`, `extracts/` — 7 sub-packages,
unchanged this window). No new top-level area, no new sub-package.

---

## 3. Functional-spec compliance

Rows checked against code (route registered / service called / test
covering), not against the spec's self-description. **Bold** = changed
this window.

| Functional area | Spec status | Code status |
|---|---|---|
| **Operator session CRUD + config (inline on Session Home)** | `spec/session_home.md`, `spec/lifecycle.md`, `spec/workflow_card.md` | **✓ shipped (18R Item 4, 2026-08-18 — `/edit` retired → `POST …/config` + `?editing=1`)** |
| Reviewer / Reviewee / Relationship / Observer rosters | `spec/setup_pages.md`, `spec/csv_contracts.md` | ✓ shipped |
| **Instruments (3-band card; bulk toggles removed)** | `spec/instruments.md` | **✓ shipped (18R Item 3 — no bulk accepting/visibility toggle)** |
| Assignment engine (rule-based, Full Matrix, self-review) | `spec/assignments.md` | ✓ shipped |
| **Reviewer surface (multi-page, server-nav)** | `spec/reviewer-surface.md` | **✓ shipped (spec rewritten to server-navigation reality this window)** |
| Operator preview / Validate page | `spec/validate_page.md`, `spec/preview_hub.md` | ✓ shipped |
| Audit log + listing UI | `spec/architecture.md` | ✓ shipped |
| Extract setup + **Extract data (+ Archive card)** | `spec/csv_contracts.md`, `spec/extract_data.md` | **✓ shipped (Archive card added 18R Item 5)** |
| Per-instrument visibility policy (3 × 2 chip grid) | `spec/visibility_policy.md` | ✓ shipped |
| Reviewee `/results` + observer `/collation` surfaces | `spec/participant_model.md` | ✓ shipped |
| Session rehydrate (extract → live session) | `spec/rehydrate.md` (moved from `docs/` this window) | ✓ shipped (18P) |
| **Three-tier role model + sys-admin ownership gating** | `spec/audience_and_identity_model.md`, `docs/security_posture.md` | **✓ shipped (18S Item 3 — cross-session writes require ownership)** |
| **Chrome status-strip Responses pill** | `spec/visual_style_rrw.md` "Responses state values" | **✓ shipped (18R Item 3 — drafts/submitted breakdown, data-driven gate)** |
| Blob storage for large extracts | `guide/deferred_consolidated.md` Part B | ⏸ deferred (18Q) |
| Email infrastructure (transport, queue, templates) | `spec/email_infra_options.md`, `guide/segment_14B_email_infrastructure.md` | ⏸ planned (still stubbed) |
| Magic-link landings for reviewees / observers | 14B appendix | ⛔ blocked on `invitations`-extensibility shape |

**The documentation sweeps closed this window.** The whole-`spec/` drift
sweep refreshed 18 specs and thoroughly revised `rrw_functional_spec.md`
(currency 2026-05-22 → 2026-08-18) + `architecture.md`; the whole-`docs/`
sweep executed all four buckets and both sweep records are archived
(`guide/archive/spec_sweep_18Aug.md`, `.../docs_sweep_19Aug.md`). Remaining
open documentation work is the Tier-1 **spec coverage gap**
(`spec/permissions.md`, `spec/email_template_editor.md`) that Segment 19's
original charter names — not drift, but missing spec homes.

_(Every row above was independently re-checked against the code this
session — route registered / service called / test file named — and **no
drift was found**, including the three rows that changed this window
(instruments bulk-toggle removal, reviewer-surface rewrite to the
server-navigation reality, Responses pill). See §6 for the adversarial
correctness pass.)_

---

## 4. Strengths

- **A 48-PR window moved production LOC +0.3% with zero new files.** The
  window was almost entirely documentation + UI consolidation; the code
  that did change was mostly *deletion* (the bulk toggles) and
  *relocation* (config onto Home reusing existing writers). The suite
  stayed green across all 48 PRs and `ruff` clean — a high-cadence burst
  that added almost no new surface to maintain.
- **The Edit-page retirement removed a whole page without a migration.**
  18R Item 4 folded session-details config into an inline `?editing=1` card
  on Session Home (mirroring the instruments card), migrated ~55 test sites
  from `/edit` to `/config`, and left `GET …/edit` as a 301 stub so
  bookmarks survive — a surface deletion done as reviewable slices
  (scaffold → mock → wire → delete) rather than a big-bang cut.
- **Archive logic converged to one gate + one service.** The lobby and the
  Extract-data card had two archive paths; 18R Item 5 unified them on
  `can_archive` + `purge_and_archive` + a shared `archive-selected` route,
  so the two surfaces can't drift on what "archivable" means or what a
  purge deletes.
- **The documentation corpus was actively pruned, not just grown.** The
  window ran two audits (spec + docs) and *executed* both — retiring 4
  `docs/` files, consolidating 3 deferral ledgers into 1, moving a
  misfiled spec, and refreshing every README — shrinking `docs/` 20 → 16
  files. The 17aug snapshot's recommended "finish the `guide/` archive
  sweep" largely shipped here.
- **Test discipline held under a doc-heavy sprint.** +25 tests, skips flat
  at 17; the code changes that did land (config `/config` path, archive
  harmonization, the Responses-pill aggregates) each shipped with guard
  tests, and the `/edit` → `/config` migration re-pointed ~55 sites rather
  than dropping coverage.

---

## 5. Weaknesses

- **`routes_operator/_instruments.py` is still the largest file (1,268).**
  It receded -49 this window (bulk-toggle removal) but remains the
  single biggest module and the busiest operator write path (the
  consolidated `/save` handler). *Cost:* review load + blast radius on the
  instrument card. *Plan:* watchlisted, no queued split; the tripwire from
  17aug (~1,400) is further away now, so the pressure eased. (§9)
- **The `guide/` corpus keeps accreting despite the sweep.** The window
  pruned `docs/`, consolidated the deferral ledgers, and this snapshot
  retires its predecessor (`codebase_assessment_17aug.md`) to
  `guide/archive/` — but `guide/` still holds fully-shipped segment plans
  (18P / 18R / 18S) that could archive too. *Cost:* the plan corpus is a
  historical record readers must date-filter. *Plan:* partial — the
  deferral + sweep docs + prior assessment archived; the segment plans did
  not.
- **The instrument card's behavior still lives in inline template JS.** The
  lock state machine + Band 1 rule editor + the new `?editing=1` config-card
  swap are hand-written JS inside templates with no build step; tests assert
  structure (`node --check` + string presence), not runtime behavior. *Cost:*
  a class of interaction regressions the suite can't catch (the 17aug
  space-key bug was one); verifiable only on the dev slot.
- **Large-extract persistence remains deferred (18Q).** Rehydrate's stash
  is Postgres-`bytea`-backed and size-bounded; blob storage stays deferred
  infra. For very large sessions the round-trip has an untested ceiling.
- **Email infrastructure is still stubbed** — the largest unstarted MVP
  scope (§7). The transport interface ships (`EmailTransport` +
  `SmtpEmailTransport` + typed-stub `GraphEmailTransport`) but no dispatch
  helper is wired; participants cannot yet be notified.

---

## 6. Bugs and regressions

**No known open bugs at `72cf281`.** This is a checked claim, not a
default. An adversarial pass traced the five surfaces this window changed —
the `/config` + Owners routes, the archive harmonization
(`can_archive` / `purge_and_archive` / `archive-selected`), the
Responses-pill aggregates, the bulk-toggle removal, and the 18S ownership
gating — and found no confirmed defect. Concretely verified:

- **Config path invalidates.** `POST …/config` → `sessions.update_session`
  calls `lifecycle.invalidate_if_validated` first, gated by
  `_require_editable`; a stale `?editing=1` on a `ready`/`archived` session
  degrades to display mode; the `/edit` stub keeps `require_session_operator`
  (no non-owner bounce). Owners-remove locks the owner set `FOR UPDATE`
  before count+delete (race-safe on Postgres).
- **Purge order is FK-safe.** `purge_and_archive` deletes audit-log →
  responses → rosters → archive, and within `purge_rosters` children
  precede parents; the `session.archived` + purge audit events survive the
  audit-log wipe. `can_archive` no-ops on a non-archivable session before
  `archive_session` can raise. `archive-selected` re-resolves each id via
  `sessions.get_for_user` (SessionOperator join) — no per-id ownership
  bypass.
- **Drafts can't go negative.** `responses_submitted` is a strict subset of
  `responses_with_any` (same filters, extra `submitted_at IS NOT NULL`), both
  `count(distinct assignment_id)`, so `drafts = any − submitted ≥ 0` and
  multiple responses per assignment don't double-count.
- **Bulk-toggle removal left no orphans.** No live reference to the deleted
  routes / `bulk_set_*` services / two retired audit types (the strict-mode
  `EVENT_SCHEMAS` gate would fail otherwise; it passes).
- **Ownership gating is airtight.** Only `clone` + `owners/add` keep the
  relaxed sys-admin gate; every other session mutation is on strict
  `require_session_operator`, and `owners/add`'s self-only check
  (`user_can_view_session` = SessionOperator membership) can't be bypassed
  by sys-admin status.

Basis also: full suite green (**2,675 passed, 17 skipped** — skips flat,
long-standing conditional/environment skips, not silenced this window);
`ruff` clean; no outstanding review comments on the window's 48 merged PRs.

**Two non-bugs worth recording** (neither a defect):

- The Responses-pill `responses_submitted` docstring calls itself
  "reviewee-centric," but the numerator counts distinct **include-assignments**
  with a submitted response, not distinct reviewees — the two diverge when a
  reviewee carries multiple include-assignments. The implemented metric is the
  intended one; only the docstring/spec *wording* is loose (a candidate
  one-line clarification, not a code change).
- One frozen Alembic migration docstring
  (`alembic/versions/d8e4f1a2b3c4_…_audit_events_index.py:22`) still names
  `guide/deferred_infra.md`, consolidated into `guide/deferred_consolidated.md`
  this window. It's a non-load-bearing comment in a shipped migration; left as-is.

Caught / handled in-window, worth remembering:

- **The Responses-pill "Awaiting" gate was reworked twice by design**
  (#1969 → #1971): lifecycle-gated → **data-driven** (numbers persist through
  a revert to draft) → the `<n> drafts / <m> submitted` breakdown. Guarded by
  a direct label-composition test plus drafts-only / submitted-persists
  integration tests.
- **The `/edit` → `/config` migration** (18R Item 4 Slice 5b) re-pointed ~55
  test sites and added a `GET …/edit` 301 stub so no bookmark 404s — a
  page deletion done without dropping the coverage that guarded the old path.

---

## 7. Estimated size upon completion

Today: **55,313 production Python + 21,825 templates + 87,263 tests**
(+ 6,772 migrations). Remaining named MVP scope:

- **Segment 14B email infrastructure** — Outbox dispatch + per-backend
  transports (SMTP live; Graph / ACS / generic stubbed) + the W20
  invite-trigger call sites. **+1,000–1,500 production LOC**, +1.0–1.5k
  test LOC. Unchanged; still unstarted.
- **W21 magic-link landings** — **+400–600 LOC**, still ⛔ blocked on the
  `invitations`-extensibility shape.
- **Segment 19 spec coverage-gap closure** — `spec/permissions.md` +
  `spec/email_template_editor.md` + a sweep-cadence template. Mostly
  `spec/` docs, **~0 production LOC**.
- **Segment 20 (operator polish + docs)** — mostly `docs/`, **+100–300
  production LOC** of polish.
- **Blob storage (18Q)** — explicitly deferred; excluded from the v1 line.

Projected feature-complete v1: **~56.5–57.5k production + ~22–22.5k
templates + ~88–89k tests.**

**Reconcile vs 17aug.** That snapshot projected the same ~56.5–57.5k
production v1 line, driven almost entirely by unstarted 14B email. This
window added only +148 production LOC (no feature code — all
consolidation + docs), so **the projection is unchanged**: the v1 gap is
still ~1.2–2.2k production LOC, essentially all 14B email + W21. The
projection excludes anything past v1 (multi-tenancy, blob storage,
VNet/Key Vault deferred infra).

---

## 8. Bottom line

The codebase is a mature, single-author + AI-agent pre-deployment monolith
that spent this window **cleaning house, not building**: 48 PRs in two days
moved production LOC only +0.3% (zero new files) because the work was a
documentation double-sweep (spec + docs, both executed and archived), the
retirement of a whole operator page (Edit → inline config on Home), and
the convergence of two archive paths into one. It ships green (2,675
passed) with a flat ~1.58× test ratio and `ruff` clean. The 17aug live
thread — `_instruments.py` climbing to 1,317 — **reversed**: it fell to
1,268 as the bulk-toggle removal took code out, so there is no file under
active split pressure. The one genuinely open thread is unchanged from
17aug: **14B email is still stubbed**, and it is the last large scope
between here and a pilot that can notify participants.

**Recommended next moves** (≤3):

1. **Start Segment 14B email infrastructure** — unchanged from 17aug as the
   #1 move, and now with even less standing in front of it: this window
   cleared the documentation debt and the operator-UX refinement backlog,
   so email is the last large MVP scope and the one feature a real pilot
   cannot run without.
2. **Archive the shipped segment plans** — this snapshot already retired
   the prior assessment to `guide/archive/`, but the fully-shipped 18P /
   18R / 18S *segment plans* still sit in `guide/` root; moving them
   finishes the "latest only" convention the sweep started.
3. **Close the Segment 19 spec coverage gap** (`spec/permissions.md`,
   `spec/email_template_editor.md`) — the only remaining Segment 19 work;
   cheap, and `permissions.md` is the natural companion to the 18S
   three-tier + ownership-gating model this window tightened.

**Settling 17aug's proposals.** Its recommended move #1 (start 14B email)
**did not ship** — carried forward as #1 again. Move #2 (finish the
`guide/` archive sweep) **partially shipped** — the deferral ledgers +
sweep docs archived, segment plans did not (now move #2). Move #3 (watch
`_instruments.py`) **resolved itself** — the file receded to 1,268, below
its tripwire. 17aug's §9 watchlist (`_instruments.py`, `session_lifecycle.py`)
both held or receded; no split queued.

---

## 9. Proposed file splits — watchlist

No split is queued; the pressure **decreased** this window.

- **`app/web/routes_operator/_instruments.py` (1,268 LOC, -49).** Fell
  below the 17aug high (1,317) as the bulk-toggle routes were deleted. Same
  seam holds if it grows again: carve the `/save` payload-parsing (the ~8
  typed blocks) into a `_save.py` sibling, leaving the thin route in place —
  mirrors the 18N/18O per-concern carves. Revisit only if it passes ~1,400.
- **`app/services/session_lifecycle.py` (1,056 LOC, +10).** Grew slightly
  (the `can_archive` helper). Clean internally; carried from prior
  watchlists, still no queued split.

The 900–1,000 cluster (`_instrument_crud.py` 1,025, `_quick_setup.py` 984,
`views/_instruments.py` 981, `responses/_core.py` 976, `audit.py` 967,
`_response_fields.py` 966, `validation.py` 958, `csv_imports.py` 942) is
stable and internally coherent — none is a junk drawer, so none is
proposed. Prior split plan archived at
`guide/archive/segment_18O_post_participants_model_file_splits.md`.
