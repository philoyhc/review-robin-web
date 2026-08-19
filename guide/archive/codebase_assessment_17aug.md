# Codebase assessment — 2026-08-17

**As of:** the close of **Segment 18S Item 1** (the three-tier operator role
model — operator ⊂ admin ⊂ super-admin), landing on top of the
**Segment 18R** save/lock harmonization of the Instruments card and the
**Segment 18P** export→import→rehydrate round-trip. This snapshot covers a
long, lower-cadence window (~2.5 months) rather than the two-day sprints the
May–June snapshots described.

Since the 2026-06-03 snapshot:

- **June docs + identity-hardening sweep** (PRs #1827 → #1863, 2026-06-04 →
  ~2026-08) — case-insensitive user-email normalization (`p0-identity`,
  case-variant tolerance now in `get_or_create_user`), a Codex
  "citizen-project compliance" audit + addendum sweeps, README / status /
  deployment-doc sweeps, Azure + CLI setup runbooks, `ruff` upper-bound pin
  (#1857).
- **18P — round-trip harmonize + rehydrate** (PRs #1864 → #1879, 2026-06) —
  config-IO harmonization (clone convergence, settings/tags/Band 1) plus full
  **session rehydration from extract files** (analyzer → Postgres-backed stash
  → sectioned `responses.csv` importer → commit orchestrator).
- **18Q — blob-storage prioritization** (PRs #1880 → #1883) — a decision/plan
  arc; blob storage evaluated and **deferred** (no production code).
- **Quickstart / deployment docs + forward stubs** (PRs #1843, #1851, #1884 →
  #1889) — quickstart guide, NUS deployment doc, a `future-randomizer` stub.
- **18R — save/lock harmonization** (PRs #1890, #1895 → #1921, #1923) — Item 1
  instrument-card identity relabel; Item 2 consolidated `/save` persistence
  (7-PR ladder); Item 3 (open) small card tweaks.
- **18S — three-tier role model** (PRs #1925 → #1928, 2026-08-17) —
  config-derived protected super-admin, management guards, Sys Admin UI +
  chrome, docs. **Item 2** (#1930) added the no-super-tier fallback so an
  un-configured super tier can't lock admin management out.

All shipped 2026-06-03 → 2026-08-18 (106 merge commits, 132 non-merge, over
~76 calendar days — a markedly lower cadence than the prior window's 79
merges in two days). Numbers taken on `main` at `75eea4e`. Development context
unchanged: single author + AI coding agents, pre-deployment, no production
traffic yet.

**Updated 2026-08-17 (same day)** to fold in **18S Item 2** (#1930, the
no-super-tier admin-management fallback — the fix for the footgun this snapshot
flagged as recommended next move #1) plus the 18R doc-archival that started the
recommended `guide/` sweep. Tables, test count, and SHA re-taken to `75eea4e`
(the window extends #1929 → #1930; production +29 LOC, tests +65, no new
production file).

A standalone snapshot; `guide/archive/codebase_assessment_03jun.md` archives
alongside it. Authoritative ship-state lives in `docs/status.md`; functional
specs audited against live in `spec/`.

> **Baseline note.** The 2026-06-03 snapshot shipped without a JSON sidecar and
> predates SHA-pinning, so its baseline was rebuilt by re-running the measure
> script at `0e14a93` (the end-of-day 18O-closure refresh commit). The script
> reports **185 production files / 52,918 LOC** there, slightly above that
> doc's hand-stated **184 / 52,840** — a counter difference (+1 file, +78 LOC).
> All Δ figures below are against the script-rebuilt baseline, so they are
> internally consistent even where they differ from the prior doc's prose.

---

## 1. What's in the box

Review Robin Web is a server-rendered FastAPI + Jinja monolith for running
structured peer/self-review cycles. An **operator** creates a **session**,
imports **reviewer / reviewee / observer** rosters (CSV), authors
**instruments** (a 3-band card: an assignment rule, a display-field preview,
and typed response fields), and lets a rule-based **assignment engine**
(Full-Matrix default, self-review policy, group-scoped fan-out) fan reviewers
across reviewees. The session moves through a lifecycle (draft → validated →
ready → expired → archived) gated by a Validate page. **Reviewers** fill a
multi-page response surface; **reviewees** see a `/results` body (Raw /
Anonymized / Summarized per a visibility policy); **observers** see a
`/collation` cohort surface. Everything mutating writes an **audit event**;
operators extract the whole session as a set of CSVs + a bundle, and — since
18P — can **rehydrate** a complete session back from that extract set. Stack:
Python 3.12, SQLAlchemy 2.x + Alembic on Postgres 16 (SQLite in tests),
Pydantic, Jinja2 with no JS build step, Azure Easy Auth (fake-auth locally).

**New since the 2026-06-03 snapshot:**

- **Session rehydrate — 18P** (PRs #1864 → #1879, 2026-06). New services
  `app/services/session_rehydrate.py` (640 LOC, the orchestrator landing a
  `<name>_REHYD` draft with all-or-nothing rollback + `session.rehydrated`
  audit), `app/services/extracts/responses_import.py` (352, sectioned
  `responses.csv` importer with group fan-out), `app/services/rehydrate_stash.py`
  (97) + `app/db/models/rehydrate_stash.py` (43, the window's one migration),
  and route `app/web/routes_operator/_rehydrate.py` (159, the Validate →
  Rehydrate page off a lobby button). Config-IO harmonization added
  `session_config_io/_apply_session_tag.py` (57). Spec: `docs/rehydrate.md`.
- **Save/lock harmonization — 18R** (PRs #1890, #1895 → #1921, #1923). Item 1
  relabelled the instrument-card top band to "Instrument assignment rule" with
  the three links renamed (Who does / Who is being reviewed / Unit of review).
  Item 2 collapsed the card's three persistence paths into one consolidated
  `POST …/instruments/{id}/save` handler (added to
  `routes_operator/_instruments.py`, +249 LOC), retired the inline ✎/✓ text
  editors in favour of a lock-driven view/edit swap, added the collapse⇒lock
  invariant, and kept the per-concern routes (`/band2-state`, `/column-widths`,
  `/display-fields/order`, `/identity`, `/fields/save`) as test/fixture infra.
  Item 3 (open) added a taller description box + a Link 2 operator-cycle
  reorder. Design decisions in `guide/archive/segment_18R_ux_refine.md`.
- **Three-tier role model — 18S** (PRs #1925 → #1928, 2026-08-17). New
  `app/auth/roles.py` (53, `is_super_admin` / `effective_super_admin_emails`
  config-derived resolver), a `super_admin_emails` config field +
  `fake_auth_super_admin` sandbox toggle, an every-sign-in
  `_reassert_super_admin` self-heal in `deps.py`, actor-super + target-super
  guards in `services/users.py` (`requires_super_admin` / `protected_super_admin`),
  a `User.is_super_admin` property, and Sys Admin tier badges + `(super admin)`
  chrome. No migration. Spec: `spec/audience_and_identity_model.md` §4.
  **Item 2** (#1930, 2026-08-17) added the no-super-tier fallback:
  `_guard_actor_super_admin` early-returns when `effective_super_admin_emails()`
  is empty (any admin manages admins until a super-admin exists), the UI gates
  Promote/Demote on `can_manage_admins`, and `create_app` logs a
  `super_admin.unconfigured` warning on a deployed env with no super tier.

Unchanged this window: the reviewer surface, the assignment engine, the audit
subsystem, the extract-setup CSVs, the participant-model surfaces (observer
collation, reviewee results, visibility policy), and the email infrastructure
(still stubbed — see §3).

---

## 2. Size (LOC)

LOC = physical lines over git-tracked files. Deltas vs the script-rebuilt
`0e14a93` baseline (see the baseline note above).

| Area | Files | LOC | Δ LOC from 03jun |
|---|---|---|---|
| `production` (`app/**/*.py`) | 192 (185 prior) | **55,165** | +2,247 (+4.2%) |
| `app/web/templates/` | 60 (59) | **21,772** | +302 (+1.4%) |
| `tests/` | 251 (240) | **86,808** | +3,319 (+4.0%) |
| `docs` (`docs/` + `spec/` + `guide/` + top-level `*.md`) | 201 (180) | **88,729** | +7,004 (+8.6%) |
| Alembic migrations | 77 (76) | **6,772** | +69 (+1.0%) |

**Test-to-production-Python ratio ~1.57×** (86,808 / 55,165), flat vs ~1.58×
on 03jun. **2,650 tests passing, 17 skipped** (was 2,546 + 17; +104 over the
window). Suite green on the SQLite default; the `ci-postgres` job round-trips
Alembic + runs the full suite on `postgres:16`. `ruff` clean.

**Biggest files** (top 10 production Python):

| LOC | File | Δ |
|---|---|---|
| 1,317 | `app/web/routes_operator/_instruments.py` | **+249** |
| 1,097 | `app/services/instruments/_instrument_crud.py` | unchanged |
| 1,046 | `app/services/session_lifecycle.py` | unchanged |
| 999 | `app/web/views/_instruments.py` | unchanged |
| 982 | `app/web/routes_operator/_quick_setup.py` | unchanged |
| 976 | `app/services/responses/_core.py` | unchanged |
| 970 | `app/services/audit.py` | +5 |
| 966 | `app/services/instruments/_response_fields.py` | unchanged |
| 955 | `app/services/validation.py` | unchanged |
| 942 | `app/services/csv_imports.py` | +98 |

The shape is a **plateau at ~900–1,100 with one file breaking out**:
`routes_operator/_instruments.py` grew +249 (the consolidated `/save`
handler — one route parsing a large form into ~8 typed blocks) and is now the
single biggest file at **1,317**, back over the 1,100 line that 18O had cleared
the whole tree under. It is watchlisted, not queued for a split (§9). The rest
of the top ten is unchanged from 03jun.

**Where the window's growth landed.** Production grew +2,247 LOC but only
**+7 files** (18S Item 2 added +29 LOC of edits, no new file) — almost all
*new* production code is the 18P rehydrate feature
(`session_rehydrate.py` 640 + `responses_import.py` 352 + `_rehydrate.py` 159 +
`rehydrate_stash.py` 97 + its model 43 = ~1,291 LOC across 5 files) plus
18S's `roles.py` (53) and one config-IO helper (57). The remaining ~+800 LOC is
accretion on existing seams — the 18R `/save` handler (+249 on `_instruments.py`),
`csv_imports.py` (+98), and small touches. **18R and 18S added little net
production LOC despite dominating the PR count**: 18R was mostly template + inline
JS churn on `instruments_index.html` (heavy add/remove nets to +301 for the
whole templates area), and 18S added a thin config-derived tier on top of
existing guards. This is the most diagnostic figure in §2: a 104-PR window that
moved production LOC only +4.2% because two of its three big arcs were
*re-shaping*, not *adding*.

**Docs outgrew code** (+7,004 doc LOC vs +2,247 production) — the `guide/`
segment-plan + assessment corpus keeps accumulating (see §5).

**Package shape.** `app/services/` remains the centre of gravity (the
`instruments/`, `responses/`, `scheduled_events/`, `assignments/`,
`session_config_io/`, `extracts/` sub-packages from 18N/18O), joined this
window by the rehydrate trio (`session_rehydrate.py`, `rehydrate_stash.py`,
`extracts/responses_import.py`) and `app/auth/roles.py`. No new top-level area.

---

## 3. Functional-spec compliance

Rows checked against code (route registered / service called / test covering),
not against the spec's self-description. **Bold** = changed this window.

| Functional area | Spec status | Code status |
|---|---|---|
| Operator session CRUD + lifecycle | `spec/lifecycle.md`, `spec/session_home.md`, `spec/workflow_card.md` | ✓ shipped |
| Reviewer / Reviewee / Relationship / Observer rosters | `spec/setup_pages.md`, `spec/csv_contracts.md` | ✓ shipped |
| **Instruments (3-band card; save/lock harmonized)** | `spec/instruments.md` | **✓ shipped (18R, 2026-08-17)** |
| Assignment engine (rule-based, Full Matrix, self-review) | `spec/assignments.md` | ✓ shipped |
| Reviewer surface (multi-page, drafts, submit) | `spec/reviewer-surface.md` | ✓ shipped |
| Operator preview / Validate page | `spec/validate_page.md` | ✓ shipped |
| Audit log + listing UI | `spec/architecture.md` | ✓ shipped |
| Extract setup (5–6 CSVs + bundle) | `spec/csv_contracts.md`, `spec/settings_inventory.md` | ✓ shipped |
| Extract data (per-instrument + metadata + Data shaper + Token keys) | `spec/extract_data.md`, `spec/csv_contracts.md §2.9` | ✓ shipped |
| Per-instrument visibility policy (3 × 2 chip grid) | `spec/visibility_policy.md`, `spec/participant_model.md` | ✓ shipped |
| Reviewee `/results` + observer `/collation` surfaces | `spec/participant_model.md` | ✓ shipped |
| **Session rehydrate (extract → live session)** | `docs/rehydrate.md`, `spec/roundtrip_coverage.md` | **✓ shipped (18P, 2026-06-05)** |
| **Three-tier role model (operator ⊂ admin ⊂ super-admin; + no-super-tier fallback)** | `spec/audience_and_identity_model.md` §4, `docs/security_posture.md` | **✓ shipped (18S Items 1–2, 2026-08-17)** |
| **Blob storage for large extracts** | `guide/segment_18Q_blob.md`, `guide/deferred_infra.md` | **⏸ deferred (18Q decision, 2026-08)** |
| Email infrastructure (transport, queue, templates) | `guide/segment_14B_email_infrastructure.md`, `spec/email_infra_options.md` | ⏸ planned |
| Magic-link landings for reviewees / observers | 14B appendix; design call pending | ⛔ blocked on `invitations`-extensibility shape |

Doc-drift sweeps closed this window: the June README/status/CLAUDE/AGENTS
sweep (#1841 → #1847), the 18R spec + template-comment alignment (#1921), and
the 18S doc slice (#1928, rewriting `audience_and_identity_model.md` §4). Open
drift: the `guide/` corpus holds several plan docs describing shipped work that
could archive (§5).

---

## 4. Strengths

- **Two of three big arcs were re-shapes that shipped without a migration.** 18R
  collapsed three instrument-card persistence paths into one `/save` and 18S
  added a whole role tier — both landed with **zero schema change** (18S's
  super-admin is config-derived; 18R reused existing writers). The suite stayed
  green across the entire 104-PR window; `ruff` clean at the pin.
- **The rehydrate round-trip closed a real correctness gap** (18P): export →
  import → clone had silently dropped hand-set config; the harmonization +
  rehydrate arc made the round-trip complete, with all-or-nothing rollback and a
  Postgres-backed pre-flight stash rather than reaching for blob storage.
- **Security tier added purely in the app + config layer.** The three-tier model
  puts the protected top tier behind `SUPER_ADMIN_EMAILS` (derived, never a DB
  column, unreachable from inside the app) with an actor-super guard on admin
  promote/demote and a target-super protection above the count floor — an
  auditable, migration-free hardening.
- **Test discipline held under a feature-heavy window.** Test-to-production
  stayed at ~1.57× while adding rehydrate, a role tier, and a UI harmonization;
  each behavior change shipped with guard tests (e.g. the 18S management matrix,
  the 18R button-state matrix, the rehydrate round-trip).
- **The per-concern-routes-as-test-infra call** (18R) avoided a ~92-site test
  rewrite for no user-facing gain — a disciplined "retire from the card, keep
  server-side" decision recorded in the plan rather than a reflexive deletion.

---

## 5. Weaknesses

- **`routes_operator/_instruments.py` is back over 1,100 (1,317, +249).** The
  consolidated `/save` handler concentrated the instrument-card write path into
  one route that parses a large form into ~8 typed blocks. It's cohesive (one
  contract) but it is now the single biggest file and the natural place a future
  bug hides. *Cost:* review load + a widening blast radius on the busiest
  operator surface. *Plan:* watchlisted, no queued split (§9).
- **18S admin-management footgun — RESOLVED 2026-08-17 (18S Item 2, #1930).**
  As originally written: with no `SUPER_ADMIN_EMAILS` set (it's optional), *no
  one* could promote/demote admins — the actor-super guard had no valid actor.
  Item 2 added the no-super-tier fallback (`_guard_actor_super_admin`
  early-returns when the effective super set is empty → any admin manages
  admins until a super-admin exists), plus a `super_admin.unconfigured` startup
  warning on deployed envs. No lockout is now reachable; `SUPER_ADMIN_EMAILS`
  stays optional. Kept here as the record of what the same-day amendment closed.
- **Docs outgrew code and the `guide/` corpus is accreting.** +6,587 doc LOC
  this window (vs +2,247 production); several `guide/segment_*.md` plans now
  describe fully-shipped work (18P, 18R, parts of 18S) and could archive like
  18O did. *Cost:* the plan corpus is increasingly a historical record readers
  must date-filter. No queued archive sweep.
- **Large-extract persistence remains deferred (18Q).** Rehydrate's stash is
  Postgres-backed and size-bounded; blob storage was evaluated and pushed to
  deferred infra. For very large sessions the round-trip has an untested ceiling.
- **The instrument card's behavior lives in inline template JS.** The lock state
  machine + Band 1 rule editor + staging harness are hand-written JS inside
  `instruments_index.html` with no build step; tests assert structure
  (`node --check` + string presence), not runtime behavior. The visual/interaction
  result is only verifiable on the dev slot. *Cost:* a class of interaction
  regressions (like the 18R space-key bug) the suite can't catch.

---

## 6. Bugs and regressions

No known open bugs at `75eea4e`. Basis: full suite green (2,650 passed, 17
skipped — flat vs prior, long-standing conditional/environment skips, not
enumerated here); `ruff` clean; no outstanding review comments on the window's
merged PRs; the 18S ladder was verified end-to-end (#1927/#1928 re-checked
against `main`). Skipped-count did not change, so no test was silenced this
window.

Caught and fixed in-window, worth remembering:

- **Space-key collapsed the instrument card while renaming** (18R, #1914 →
  #1915) — the `<summary>` toggle is a browser default action, not propagation;
  `stopPropagation` didn't work, `preventDefault` + manual reinsert did. Space
  toggling of the summary was subsequently removed entirely.
- **A newly-added response field's column width was lost on save** (18R, #1920)
  — a new column skipped by the width-staging path left it unsized and
  `table-layout: fixed` redistributed; fixed by re-adding `width_px` to the
  serialized row.
- **Case-variant user rows** (#1836/#1837) — `get_or_create_user` now resolves
  the oldest row via a case-insensitive email match, closing a duplicate-row
  hazard.

---

## 7. Estimated size upon completion

Today: **55,165 production Python + 21,772 templates + 86,808 tests** (+ 6,772
migrations). Remaining named MVP scope:

- **Segment 14B email infrastructure** — Outbox dispatch + per-backend
  transports (SMTP live; Graph / ACS / generic stubbed) + the W20 invite-trigger
  call sites. **+1,000–1,500 production LOC**, +1.0–1.5k test LOC. Unchanged
  from the 03jun estimate; still unstarted.
- **W21 magic-link landings** — **+400–600 LOC**, still ⛔ blocked on the
  `invitations`-extensibility shape.
- **Segment 20 (operator polish + docs)** — mostly `docs/`, **+100–300
  production LOC** of polish.
- **Blob storage (18Q)** — explicitly deferred; excluded from the v1 line.

Projected feature-complete v1: **~56.5–57.5k production + ~22–22.5k templates +
~88–89k tests.**

**Reconcile vs 03jun.** That snapshot projected ~54–55k production for v1;
we're already past it at 55,165 — because **18P rehydrate (~+1.3k) was
discovered scope not in that projection**, while **14B email (+1–1.5k) still
hasn't shipped.** Net: rehydrate consumed the headroom the prior projection
left for email, so the v1 line moves *up* to ~56.5–57.5k rather than the arc
being "nearly done." The projection excludes anything past v1 (multi-tenancy,
blob storage, VNet/Key Vault deferred infra).

---

## 8. Bottom line

The codebase is a mature, single-author + AI-agent pre-deployment monolith that
spent this window **re-shaping more than adding**: 104 PRs moved production LOC
only +4.2% because two of the three big arcs (18R save/lock, 18S roles) were
consolidations, while the one genuinely additive arc (18P rehydrate) closed the
extract round-trip. It ships green with a held ~1.57× test ratio. The one live
structural thread is `routes_operator/_instruments.py` climbing back to 1,317
LOC on the back of the consolidated `/save`. The nearest real risk *was*
operational — the 18S no-`SUPER_ADMIN_EMAILS` footgun — and it was **closed
same-day by 18S Item 2 (#1930)**; the live thread is now purely the fat
`_instruments.py`.

**Recommended next moves** (≤3):

1. **Start Segment 14B email infrastructure** — the largest remaining MVP scope,
   unblocks the W20 invite triggers, and is the thing standing between the
   current state and a pilot that can actually notify participants. It's now
   first because the footgun that previously held this slot shipped.
2. **Finish the `guide/` archive sweep** — the 18R working docs went to
   `guide/archive/` with #1930; the fully-shipped 18P / 18R / 18S *segment
   plans* are the remaining candidates, so the plan corpus stops out-growing the
   code it describes (docs grew +8.6% this window vs +4.2% production).
3. **Watch `_instruments.py` (1,317)** — no split yet, but set a tripwire at
   ~1,400 (§9) so the consolidated `/save` handler doesn't drift into a junk
   drawer unnoticed.

Prior snapshot's proposals: §9 was already **closed** (the four 18O file splits
shipped). Its §7 email/magic-link remainder items are **carried forward
unchanged** (still unstarted / blocked). Its watchlist item `session_lifecycle.py`
(1,046) held steady; the new watchlist entry is `_instruments.py` (1,317).

**This snapshot's own recommended-move #1 (resolve the footgun) shipped the
same day as 18S Item 2 (#1930)** — recorded in §5 and folded into the numbers
above by the same-day amendment.

---

## 9. Proposed file splits — watchlist

No split is queued. One candidate emerged this window and one holds from the
prior:

- **`app/web/routes_operator/_instruments.py` (1,317 LOC, +249).** The
  consolidated `/save` handler pushed it back over 1,100. Natural seam if it
  keeps growing: carve the `/save` payload-parsing (the ~8 typed blocks:
  band1 / link3 / column-widths / sort / identity / visibility / band2-state /
  display-order) into a `_save.py` sibling under a `routes_operator/` module,
  leaving the thin route in place — mirrors the 18N/18O per-concern carves.
  Currently cohesive enough to leave whole; revisit if it passes ~1,400.
- **`app/services/session_lifecycle.py` (1,046 LOC, unchanged).** Clean
  internally; carried from the 03jun watchlist, still no queued split.

The seven-file 900–1,100 cluster (`_instrument_crud.py`, `views/_instruments.py`,
`_quick_setup.py`, `responses/_core.py`, `audit.py`, `_response_fields.py`,
`validation.py`) is stable and internally coherent — none is a junk drawer, so
none is proposed. Prior split plan archived at
`guide/archive/segment_18O_post_participants_model_file_splits.md`.
