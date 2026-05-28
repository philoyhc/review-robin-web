# Codebase assessment — 2026-05-28

**As of:** the close of **Segment 18K** (Completing instrument
visibility on the reviewer surface) plus Segments **18L** (multi-
page reviewer surface) and **18M** (operator instrument ordering
+ page breaks), shipped end-to-end across 2026-05-27 → 2026-05-28.
Built on top of the 18G scheduled-events arc (Parts 0-3,
2026-05-20 → 21), the 18I → 18J new-model instrument takeover
(2026-05-22 → 26), and a tail of doc / sweep / archival passes
through 2026-05-28. Numbers taken on `main` at `7b333cb`. Citizen
project — single author + AI-agent cadence, not yet pilot-deployed.

A **standalone** snapshot, written fresh rather than as a delta
against the 19may assessment. Earlier snapshots (09 / 11 / 16 / 17 /
18 / 19 may) are retained in `guide/archive/` for the audit trail.
Authoritative ship-state lives in `docs/status.md`; the functional
spec audited against is `guide/archive/functional_spec.md`.

---

## 1. What's in the box

A FastAPI + Jinja + SQLAlchemy 2.x server-rendered monolith
implementing the full **operator-setup → reviewer-response** loop
end-to-end. An operator creates a review session, uploads rosters
of reviewers and reviewees, configures one or more instruments
through a three-band per-instrument card (Identity + Rule slots +
Live preview / Response fields), pins assignment rules
(seeded Full Matrix or operator-authored RuleSet via the Rule
Builder), validates, activates, and monitors progress on a
Workflow Card. Reviewers reach a tabular response surface (Azure
Easy Auth or a tokened invite link), save drafts, and submit. The
operator exports per-session CSVs (or one zip bundle), reviews a
per-session audit log, and purges or archives the session.

**New since the 19may snapshot:**

- **18G** (Scheduled events) Parts 0-3 — schema for eight
  scheduled-event anchors + offsets landed inert on `sessions`;
  three lifecycle triggers (scheduled activation, auto-send
  invitations, auto-send reminders) lit up behind a lazy-observer
  dispatch. Parts 4 (auto-archive) + 5 (scheduled / policy purge)
  carved to `deferred_until_pilot_feedback.md`.
- **18I → 18J** (New-model instrument takeover) — the legacy
  individual + group instrument cards retired; every instrument
  flows through the (former "new-model") three-band card. Six
  waves under 18J closed every parity gap, refactored Lock /
  Unlock + readiness gating, retired the RuleSet library / the
  `is_new_model` flag / the `response_type_definitions` table /
  the per-field `response_type_id` FK, and landed a five-cluster
  polish tail. Per-field type + bounds + list options now live on
  `InstrumentResponseField._inline_data_type` / `_inline_min` /
  `_inline_max` / `_inline_step` / `_inline_list_csv`.
- **18K** (Reviewer-surface visibility — Band 3 follow-on) —
  reviewer summary HTML + reviewer-record CSV filter response
  fields by `InstrumentResponseField.visible`; the Band 2 chip
  is the visibility control (no per-row Visible checkbox);
  un-pinning a chip whose field has saved responses requires an
  `acknowledged_drop=true` body flag (server raises
  `ResponseFieldDropAcknowledgementRequired` otherwise; JS
  `confirm()` names the field + count); the reviewer surface
  shows a `banner banner-info` listing dropped fields on the
  next load; `replicate_instrument` copies `visible` as-is; the
  inline-column save path dual-writes the `validation` JSON
  (closes a latent stale-JSON bug).
- **18L** (Multi-page reviewer surface) — URL is
  `/reviewer/sessions/{id}/{page_n}`; pages are operator-defined
  runs of instruments between page breaks; the GET filters to
  the current page only; Save is page-scoped, Submit is session-
  wide.
- **18M** (Operator instrument ordering + page breaks) — drag-
  handle reorder + an inline `+` page-break separator
  (`Instrument.starts_new_page`).
- **Reviewer dashboard rewrite** (2026-05-28) — per-instrument
  sub-rows replaced by per-page sub-rows labelled
  `"Page N: #n {short_label}, #m {short_label}, …"` so the deep
  link lands on the right page URL.
- **Several focused fixes** alongside — Band 2 textarea height
  formula tuned to a 50% typical-response fraction (was 75%)
  with a post-render adjustment that reads the actual rendered
  column width rather than the formula's 224px fallback;
  `replicate_instrument` no longer silently resets cloned
  response-field `visible`.

The application is observable and fails safe at its boundaries:
structured JSON logs on stdout, a global exception handler that
renders friendly error pages (logging — never leaking —
tracebacks), and a startup check that refuses to boot a
misconfigured deployed environment. The operational documentation
set (deployment, runbook, troubleshooting, backup/restore,
security posture, known limitations) backs a pilot.

## 2. Size (LOC)

| Area | Files | LOC |
|---|---:|---:|
| `app/` Python (production) | 133 | 41,456 |
| `app/` Jinja templates | 52 | 16,868 |
| `alembic/` migrations (chain + env) | 67 | 5,500 |
| **Production subtotal** | | **~63,800** |
| `tests/` | 188 | 64,471 |
| **Grand total** | | **~128,300** |

Test-to-production-Python ratio is steady at **~1.5×**.
**2,010 tests** collected (was 1,910 on 19may); suite **green**,
`ruff` **clean**. Largest production file is now
`app/services/instruments/_instrument_crud.py` at **1,928 LOC** —
the new-model takeover consolidated previously-split Band 1 / 2 /
3 logic, the new `set_band2_state` + `_sync_response_fields_to_db`
+ replicate + page-break write helpers all sit there.

**File-size creep is the watch item again.** The 19may snapshot
flagged 13 files past 800 LOC and 4 past 1,150; the current count
is **15 past 800** and **6 past 1,150**. The two largest
production files are now `_instrument_crud.py` (1,928) and
`routes_operator/_instruments.py` (1,497). The 17A-style
housekeeping split flagged on 19may has not been scheduled yet.

## 3. Functional-spec compliance

**§21 — MVP acceptance criteria.** Unchanged from the 19may
read. **14 / 16 fully met, 2 inert.** Inert are still **#8 email
invitations** and **#13 reminder sending**: rows go to
`email_outbox` at `status="queued"` and never transmit;
`SmtpEmailTransport` exists, the pluggable transport seam is
ready, but no call site invokes it. Driver + dispatch worker are
**Segment 14B**. (18G Parts 2 and 3 added the scheduled fire-
event side, but they enqueue Outbox rows the same way — they
don't activate transport.)

**§22 — Expanded release.** Substantially further along since
19may:

- Multi-instrument with the unified new-model card, including
  group-scoped instruments (13C), and now **operator-defined
  multi-page reviewer surfaces** (18L) with **operator-controlled
  instrument ordering + page breaks** (18M).
- Scheduled session activation, auto-send invitations, and
  auto-send reminders (18G Parts 1-3) — the timing automation
  the original spec called out, now live behind a lazy-observer
  dispatch.
- Reviewer-side **visibility tail closed** (18K) — every
  reviewer-facing surface (form / summary HTML / reviewer-record
  CSV) honours per-field `InstrumentResponseField.visible`;
  operator-side guard rails (confirm-on-drop, dropped-field
  banner) match the lock-decision policy.

Remaining §22 items: targeted reminders by completion state
(18G Part 3c, deferred), reminders analytics card (18G Part 3d,
deferred), scheduled / policy-driven retention (18G Part 5,
deferred), and the reviewee / observer surface (post-MVP
participant arc, segments 21+).

**§23 — end-to-end acceptance cycle.** The whole cycle runs
without developer intervention except the two email-send steps,
which still degrade gracefully to a dev outbox. 18L's multi-page
shape did not change §23's contract.

**Verdict:** functionally an MVP-complete operator / reviewer
tool. The one true functional shortfall is still **email send**.

## 4. Strengths

- **Layering is still genuinely respected.** Route handlers parse
  the request, call services, and never `commit` or carry business
  rules. The `app/web/views/` adapter seam stays real. Operator
  route slices import only `_shared`. The reviewer-route slice
  boundary held through the 18L multi-page refactor — the
  dashboard's import of `_pages_for_session` from `_surface` is
  the one cross-slice reach, deferred to avoid cycle risk.
- **Tech-debt hygiene stays unusually clean** — **zero `# TODO`
  / `# FIXME` / `# XXX` / `# HACK`** markers across `app/` and
  `tests/`. Deferred work lives in `guide/` plans, not as code
  rot. The `sqlalchemy.dialects.postgresql` ban in models holds.
- **18J → 18K landed cleanly.** A genuinely intricate retirement
  (the RTD table + the `is_new_model` flag + the `response_type_id`
  FK + the parallel legacy + group cards, all consolidated into
  one three-band card) shipped across six 18J waves without a
  net regression — the perf, ordering, and observer-fan-out
  invariants survived. 18K then closed the per-field visibility
  tail with proper guard rails (confirm-on-drop, dropped-field
  banner, `validation` JSON dual-write).
- **Observability and boundary safety stay in place** — stdlib
  JSON logging, a global exception handler, a fail-fast
  `validate_critical_settings` startup check. `audit.write_event`
  now has **121** registered `EVENT_SCHEMAS` entries under the
  canonical envelope (was ~115 on 19may); strict-mode tests gate
  any drift.
- **Genuine test coverage grew with the surface.** **2,010
  tests** (1,910 on 19may; +100 net across 18G / 18I / 18J /
  18K / 18L / 18M and the dashboard rewrite). Integration-first
  via `TestClient`, with focused unit suites for the complex
  pure logic. Dual-dialect CI (SQLite + `postgres:16`) plus
  `ruff`. Suite is **green**, ruff **clean**.
- **The doc set kept pace.** `spec/` was swept on 2026-05-28
  to clear `{position}` → `{page_n}` URL drift and the retired
  RTD card section; `guide/visibility_audit.md`,
  `guide/instrument_builder_project.md`, and four 18-series
  segment plans archived under the standard provenance-note
  convention; `docs/status.md` carries a per-segment timeline
  log; the As-of header repoints to 18K.

## 5. Weaknesses

- **Email send is still inert** — the single largest functional
  gap and a hard pilot blocker. Gated on the host institution's
  transport choice; **Segment 14B**. (18G Parts 2 and 3 added
  scheduled fire-events on the queueing side; the send side
  still no-ops.)
- **Azure infrastructure is still deferred, not done.** The
  *in-app* hardening shipped (14A); the *platform* side has
  not — no Key Vault, no VNet / private endpoints, no staging
  slot, no production environment, no Application Insights
  resource. Documented in `guide/deferred_infra.md` and the
  deployment guide.
- **The auth trust model is still thin by design.** Identity
  depends entirely on Azure Easy Auth populating
  `X-MS-CLIENT-PRINCIPAL*` headers, trusted verbatim — correct
  only if the platform gate is enforced. The startup check still
  does **not** hard-fail on `ALLOW_FAKE_AUTH=true` in a deployed
  environment (a reasonable future tightening, unchanged from
  19may).
- **File-size creep got worse.** Was 13 files past 800 LOC on
  19may; now **15**. Was 4 past 1,150; now **6**. The biggest
  file (`_instrument_crud.py` at 1,928 LOC) is a cohesive single
  concern but is approaching "split it into a package of slices"
  territory — the new-model takeover consolidated several
  previously-split flows. A 17A-style housekeeping split is
  overdue.
- **Defensive code asymmetry in the reviewer surface (very
  minor).** The GET handler at `routes_reviewer/_surface.py:784`
  clamps `page_count = len(pages) or 1` (so an empty session
  renders as a clamped single page); the POST save handler at
  line 993 short-circuits with a hard `len(pages)` check. The
  asymmetry is currently moot because `_require_session_accepting`
  at line 987 short-circuits with 403 when there are no
  assignments (which an empty session always implies), but the
  defensive shape is inconsistent and would mask a real bug if
  the upstream guard ever changed. Tighten when next in the area.
- **Migration ordering is exercised only by the Postgres CI
  job** — the SQLite suite still builds the schema with
  `create_all`. That job should be a required status check on
  PRs. Unchanged from 19may.

## 6. Bugs and regressions

A fresh bug hunt focused on the surfaces shipped since the 19may
assessment — **18G** (scheduled events), **18I → 18J** (new-model
takeover), **18K** (visibility), **18L** (multi-page reviewer
surface), **18M** (page breaks + reorder), and the **2026-05-28
reviewer-dashboard per-page rewrite**.

The 19may hunt's findings (the HIGH config-CSV round-trip defect
and the MEDIUM / new MEDIUM defunct-safeguard defects) all shipped
fixes under Segment 18H on 2026-05-19 and remain closed.

This pass found **zero open correctness defects** on the in-scope
surfaces. The bug hunt agent flagged a single HIGH (page-validity
asymmetry between the GET and POST save handlers,
`routes_reviewer/_surface.py:784` vs `:993`) but verification
showed the asymmetry is unreachable in the current code —
`_require_session_accepting` at `:987` 403s first whenever there
are no assignments (which an empty session always implies). It is
captured as a minor defensive-asymmetry weakness in §5 rather
than a defect.

Other items the hunt verified as correct:

- `_pages_for_session` empty-session handling (the
  `if pages else set()` guard at `:788` covers the otherwise
  unreachable empty case).
- `dropped_fields` deduplication via JOIN + a deduping `set()`
  on the reviewer surface — multiple Response rows on the same
  hidden field collapse to one banner entry.
- `replicate_instrument` leaves `starts_new_page` unset on the
  clone — the column default is `False`, and a replicated
  instrument logically inherits the source's pagination context
  (which is "this row is just another instrument on the same
  page"); deliberate.
- The `acknowledged_drop` confirm guard fires only on a true
  `visible: True → False` transition with `count > 0` — a brand-
  new row created with `selected: False` has `prior_visible=True`
  (default column value) but `drop_response_count=0` (no
  responses exist yet), so the guard does not falsely fire on
  the new-row case.
- The `validation` JSON dual-write at `_sync_response_fields_to_db`
  is the only inline-column writer in the operator-edit path, so
  the original 18K stale-JSON bug cannot re-introduce itself
  through a side door.
- The dashboard's per-page rollup correctly collapses uniform
  "no assignments" to "no assignments" and surfaces "in progress"
  on mixed submitted + not-started pages.

The suite is **green** (2,010 passed, 18 skipped) and `ruff` is
clean. No regressions found in the non-recent surface.

## 7. Estimated size upon completion

18K, 18L, and 18M closed since 19may; 18G Parts 1-3 shipped, Parts
4-5 carved to deferred; 18I and 18J consolidated the instrument
takeover. The remaining MVP workplan:

- **14B** (Email infrastructure — Parts A → E sequential + F → H
  independent backend swaps) is now the **only substantive
  remaining MVP block**.
- **19** (Spec documentation — recurring sweep cadence) and
  **20** (Operator polish + documentation) are documentation-
  weighted with little net code.

The post-MVP **participant-model arc (segments 21+)** is tracked
in `guide/participant_model_upgrade.md` and is out of MVP scope.

| | Now | At MVP completion (est.) |
|---|---:|---:|
| Production (`app/` + templates + migrations) | ~63.8k | **~70–75k** |
| Tests | ~64.5k | **~75–82k** |
| **Grand total** | ~128.3k | **~150–160k** |

The MVP figure on 19may was ~145–160k; the actual trajectory ran
slightly above the low end (18I → 18J added more code than the
notional 18-family budget allowed), but the convergence still
holds — 14B is the dominant remaining block, 19 / 20 add little
code, and 18G Parts 4-5 are deferred. The codebase is therefore
roughly **80–85% of its final MVP size**, and functionally
further along than that — the remaining work is concentrated in
email send, not core operator / reviewer features. The
**participant-model arc**, if pursued, would push the total well
past the MVP figure (a further ~+15–25k).

## 8. Bottom line

A disciplined, well-layered, genuinely well-tested FastAPI
monolith with unusually clean tech-debt hygiene for a single-
author + AI-agent citizen project. Functionally it is an MVP-
complete operator / reviewer tool — 14 / 16 §21 criteria fully
met, the loop runs end-to-end — and the 18J → 18K → 18L → 18M
sequence consolidated the instrument card, closed the Band 3
visibility tail, and gave the reviewer surface its operator-
defined multi-page shape, all without disturbing the
architecture.

The same two things stand between here and a pilot: **email
transport (14B)** — the lone functional blocker — and **standing
the deployment up on real Azure infrastructure** (Key Vault,
VNet, staging slot, production environment, Application Insights).
The bug-hunt findings are all closed; there are **no open
correctness defects** on the in-scope surfaces. The watch items
are **file-size creep** (the biggest service is now nearly 2k
LOC; a 17A-style housekeeping split is overdue) and the **minor
defensive asymmetry between the reviewer-surface GET and POST
save handlers** documented in §5.

---

## 9. Follow-up — Segment 18N (2026-05-28 PM)

Closes both §5 watch items from the morning's assessment **and**
surfaces a latent silent-drop defect the assessment hadn't
spotted. Five PRs (#1556 → #1560) shipped the same afternoon.

### What 18N closed from §5

- **The defensive asymmetry** (§5 weakness 4). Reviewer-surface
  GET (`routes_reviewer/_surface.py:784`) clamped `len(pages) or
  1` while POST save (`:993`) hard-failed with `len(pages)`. The
  asymmetry was unreachable in practice but inconsistent. PR 1
  (#1556) lifted a `validate_page_n` helper into
  `routes_reviewer/_shared.py` and called it from all three
  page-bound routes (GET surface / POST save / operator
  preview), with 23 new test cases pinning the alignment.
- **File-size creep** (§5 weakness 3). PRs 2-4 carved the three
  biggest production files into per-concern slices:

  | File | 28may AM | 28may PM | Δ |
  |---|---:|---:|---|
  | `services/instruments/_instrument_crud.py` | 1,928 | 1,052 | −876 |
  | `routes_operator/_instruments.py` | 1,497 | 1,027 | −470 |
  | `services/responses.py` | 1,444 | 976 (`_core.py`) | −468 |

  Every carve was pure structural (mechanical move + `__init__.py`
  re-export wall), and each PR landed with the full suite green.
  Six new sibling slices appeared:
  `instruments/_band2.py` + `_pagination.py` (PR 2);
  `routes_operator/_instruments_band2.py` +
  `_instruments_pagination.py` (PR 3); the new `responses/`
  package with `_core.py` + `_group_reconciliation.py` (PR 4).

### The latent defect 18N PR 5 found

While auditing the export / import surface for **Track C**
(the original scope — round-trip the eight 18G `ReviewSession`
scheduled-event columns the existing `session_config_io/`
pre-dated), a thorough sweep against every operator-input
column surfaced a much bigger story. After 18J Wave 2 PR
iii-b4 retired the `response_type_definitions` table and moved
type + bounds inline onto `InstrumentResponseField._inline_*`,
the serializer wasn't updated to match. **Every Zip-all →
import round-trip had been silently dropping each response
field's `_inline_data_type` / `_inline_min` / `_inline_max` /
`_inline_step` / `_inline_list_csv` / `visible`** for ~2 weeks.
An operator-imported session got back response fields collapsed
to the default Rating Integer 1-5 shape; the bug surfaces only
on the second leg of the round-trip, which is why it slipped
the morning's bug hunt (the surfaces the hunt covered all read
the live DB state, not the re-imported state).

PR 5 closes all 17 round-trip gaps in one go: 8 18G fields + 6
response-field inline fields + `Instrument.column_widths` +
`Instrument.starts_new_page` + `Instrument.band2_state`. Apply
recomputes `validation` JSON from the imported inline state via
the same `validation_block_from_inline` seam Band 3's save path
uses, so the reviewer surface (which reads `validation`) lines
up post-round-trip. Six new round-trip regression tests pin
each closed gap.

This is a **HIGH-severity correctness defect the morning bug
hunt missed**, downgraded to "closed" by EOD. Severity rating
is "would silently corrupt operator data on import"; user
impact at this stage is "no real users yet, so nothing was
lost in practice". The relevant lesson for the next bug hunt:
**round-trip tests need their own audit pass** — read-side bugs
in export-shape code only manifest after a re-import, which
the live surface-walk hunts don't exercise.

### Updated numbers (`main` at `70ee32b`)

| Metric | 28may AM | 28may PM |
|---|---:|---:|
| Production LOC (`app/`) | 41,456 | 42,006 |
| Test LOC (`tests/`) | 64,471 | 65,022 |
| Test count | 2,010 | **2,021** (PR 1 added 23 new page-validity tests; PR 5 added 6 new round-trip tests; structural splits were pure moves) |
| Files > 800 LOC | 15 | 15 |
| Files > 1,150 LOC | **6** | **4** (down) |
| Files > 1,500 LOC | 1 (1,928) | **0** |
| Biggest production file | `_instrument_crud.py` (1,928) | `routes_reviewer/_surface.py` (1,269) |

The biggest file is now the cohesive reviewer-surface route
stack — that's a deliberate "cohesive, one route's full GET +
POST" carve-out the morning assessment already noted as
"don't split" (its natural split lifts `_surface_context` into
`app/web/views/`, a bigger move than 18N scoped). Production +
test LOC growth (+1,100 net) is mostly the new slice module
docstrings + per-slice import boilerplate the PR 2-4 splits
introduced; offset by the carved code being net-smaller than
the inline source (CRUD seam mostly cleaner post-split).

### Updated bottom line

The same two pilot blockers stand (14B email transport + Azure
infrastructure). One latent correctness defect surfaced and was
closed the same day. Both §5 weakness 3 (file-size creep) and
weakness 4 (defensive asymmetry) are now closed. **The
codebase is healthier than the morning numbers suggested**:
zero files > 1,500 LOC, the package layouts are cleaner, and
the export / import round-trip — the operator's main
session-sharing primitive — actually preserves every operator
input now. The watch list reduces to the pilot-deployment
blockers + the remaining 19 / 20 doc segments.
