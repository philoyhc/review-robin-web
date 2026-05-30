# Codebase assessment — 2026-05-30

**As of:** the close of **Segment 18N** (housekeeping splits +
settings round-trip catch-up) plus the full **Extract data**
slice — Phase 1 (Session Home card split + new Operations tab
+ Data shaper; PRs #1565 → #1627) and Phase 2 (the *Self-review
handling* chip; PRs #1642 → #1647) — and the
**Self-review consolidation** mini-slice (PRs #1633 → #1637)
that put `Assignment.is_self_review` in as the canonical
classification column. All shipped 2026-05-28 → 2026-05-30
(102 PRs merged in 2 days). Numbers taken on `main` at
`5a23b4d`. Citizen project — single author + AI-agent cadence,
not yet pilot-deployed.

A **standalone** snapshot. Prior snapshot
`guide/codebase_assessment_28may.md` archives alongside this
write-up. Authoritative ship-state lives in `docs/status.md`;
the functional spec audited against is
`guide/archive/functional_spec.md`.

---

## 1. What's in the box

A FastAPI + Jinja + SQLAlchemy 2.x server-rendered monolith
implementing the full **operator-setup → reviewer-response →
extract** loop end-to-end. An operator creates a review
session, uploads rosters of reviewers and reviewees, configures
one or more instruments through a three-band per-instrument
card (Identity + Rule slots + Live preview / Response fields),
pins assignment rules (seeded Full Matrix or operator-authored
RuleSet via the Rule Builder), validates, activates, and
monitors progress on a Workflow Card. Reviewers reach a tabular
response surface (Azure Easy Auth or a tokened invite link),
save drafts, and submit. The operator now exports along three
distinct shapes — porting-portable CSVs via the Session Home
**Extract setup** card, response-data shapes via the new
**Extract data** Operations tab, or custom column compositions
via the **Data shaper** sub-surface on that tab. Audit logging,
purges, and archival round out the lifecycle.

**New since the 28may snapshot:**

- **Segment 18N — Housekeeping** (PRs #1556 → #1560,
  2026-05-28). File splits + reviewer-surface defensive-
  asymmetry fix + settings round-trip catch-up. The
  ``instruments/_instrument_crud.py`` 1,928-LOC file split
  into ``_band2.py`` + ``_pagination.py`` + a 1,052-LOC core;
  ``routes_operator/_instruments.py`` 1,497 → 1,027;
  ``responses.py`` 1,444 → a package (``_core.py`` 976 +
  ``_group_reconciliation.py``). PR 5 closed a **high-severity
  settings-round-trip silent drop** the audit flagged: 8 ×
  18G ``ReviewSession`` columns + 6 response-field inline
  fields + ``Instrument.column_widths`` /
  ``starts_new_page`` / ``band2_state`` had all been silently
  lost on Zip-all → import for ~2 weeks after 18J Wave 2 PR
  iii-b4. Plan archived to
  ``guide/archive/segment_18N_housekeeping.md``.

- **Extract data slice — Phase 1** (PRs #1565 → #1627,
  2026-05-29 → 2026-05-30). Two-pronged surface split. The
  Session Home **Extract data** card became **Extract setup**
  (porting-shaped CSVs only — Reviewers / Reviewees /
  Relationships / Session settings + a four-CSV
  ``{code}_setup.zip``); a new **Extract data** tab joined the
  Operations strip at ``/operator/sessions/{id}/extract-data``
  for fine-grained response-data shaping. 2-column grid of
  half-width lens cards (By instrument + Reviewer response
  metadata + Reviewee response metadata) with a full-width
  **Data shaper** below. Saved ``data_shapes`` persist as a
  per-session library with CRUD routes, file generation,
  Settings CSV round-trip (via portable refs — instrument by
  ``short_label``, response field by ``field_key``), and
  Zip-all integration.

- **Self-review consolidation** (PRs #1633 → #1637,
  2026-05-30 — one-day five-PR slice). Added
  ``Assignment.is_self_review`` as the single source of truth
  for self-review classification, with a self-contained
  per-session backfill via the canonical whole-group rule.
  Every Assignment write path (regenerate, manual add,
  instrument clone / replicate) and every edit trigger
  (reviewer email, reviewee identifier or boundary tag,
  relationship pair-context tag, instrument ``group_kind``)
  calls ``recompute_self_review_classification`` after its
  flush; ``replace_assignments`` runs a continuous-gate
  ``verify_self_review_classification`` invariant after its
  own recompute (strict in tests, log + auto-correct in
  production). **Fixed a latent bug**: the wide-format
  By-instrument extract had hardcoded ``SelfReview = FALSE``
  on group-scoped rows since group-scoped instruments shipped,
  silently mislabelling self-review groups; retired with a
  dedicated regression test. Plan archived to
  ``guide/archive/self_review_consolidate.md``.

- **Extract data slice — Phase 2: Self-review handling chip**
  (PRs #1642 → #1647, 2026-05-30). Three-state cycle
  (``Include self`` / ``Exclude self`` / ``Both``) shipped
  end-to-end on the two metadata cards + the Data shaper
  scope row. Drives the column-name suffix
  (``_self`` / ``_noself`` / ``_both``), filename suffix, and
  ``context.self_review_handling`` audit slot. Per-shape state
  persists on the new ``data_shapes.self_review_handling``
  column + round-trips through Settings CSV. A
  post-implementation audit found no bugs / no spec drift; PR
  #1647 closed three test-coverage gaps the audit flagged.
  Plan archived to ``guide/archive/extract_data.md``.

The 28may snapshot's "new-model takeover" + "scheduled events"
+ "operator-preview parity" foundations are unchanged. The
reviewer surface, instrument builder, assignment engine, and
audit log are all where they were on 28may.

## 2. Size (LOC)

| Area | Files | LOC | Δ from 28may |
|---|---:|---:|---:|
| `app/` Python (production) | 137 | 46,082 | +4,626 (+11%) |
| `app/` Jinja templates | 53 | 19,459 | +2,591 (+15%) |
| `alembic/` migrations (chain + env) | 70 | 5,872 | +372 (+3 files) |
| **Production subtotal** | | **~71,400** | **+~7,600 (+12%)** |
| `tests/` | 193 | 71,996 | +7,525 (+12%) |
| **Grand total** | | **~143,400** | **+~15,100 (+12%)** |

Test-to-production-Python ratio steady at **~1.56×** (was
~1.5×). **2,185 tests** passing (was 2,010 on 28may; +175
tests in two days). Suite **green**, `ruff` **clean**.

**File-size creep largely tamed.** 28may flagged 15 files past
800 LOC and 6 past 1,150; the current count is **16 past 800**
and **5 past 1,150**. The 28may "biggest two" —
``_instrument_crud.py`` (1,928) and
``routes_operator/_instruments.py`` (1,497) — both shrank
substantially via Segment 18N's structural splits (1,097 +
1,027 respectively). The largest production file is now
``services/assignments.py`` at **1,426 LOC**. Five files now
sit above 1,200 LOC: ``assignments.py`` (1,426),
``session_config_io/_apply.py`` (1,355),
``routes_reviewer/_surface.py`` (1,269),
``scheduled_events.py`` (1,231), and
``instruments/_instrument_crud.py`` (1,097). Watch-item, not
urgent.

## 3. Functional-spec compliance

**§21 — MVP acceptance criteria.** Unchanged from the 28may
read. **14 / 16 fully met, 2 inert.** Inert are still **#8
email invitations** and **#13 reminder sending** — rows queue
to ``email_outbox`` at ``status="queued"`` and never transmit;
``SmtpEmailTransport`` exists; **Segment 14B** still owns the
send activation. Every other item — multi-instrument, manual
+ rule-based assignment, validation, reviewer surface, save +
submit, audit log, retention — runs end-to-end as today.

**§22 — Expanded functional release.** All MVP+ items shipped:
multi-instrument unified card (18I–18J), rule-based builder
(13A), operator-defined multi-page reviewer surfaces (18L),
instrument ordering + page breaks (18M), per-field visibility
+ dropped-field banner (18K), scheduled session activation +
auto-send invitations + auto-send reminders (18G Parts 1-3).
Two completion-state reminder refinements (targeted reminders
by completion state; reminders analytics card) sit in
``guide/deferred_until_pilot_feedback.md``.

**§22 — Extract / analysis surface (new on 30may).** The
spec's "basic CSV / Excel export" line is now satisfied by a
richer-than-spec extract surface: porting-portable CSVs from
the Session Home **Extract setup** card; response-data shapes
from the new **Extract data** tab (per-instrument long-format
CSVs, Reviewer / Reviewee response metadata aggregates, plus
the Data shaper for custom shapes); chip-driven self-review
handling on every aggregate surface. Worth a small spec
catch-up — the canonical pages are now `spec/extract_data.md`
+ `spec/settings_inventory.md` §9.5.

**§23 — Acceptance criteria (16-step end-to-end cycle).**
Unchanged. All 16 steps run without developer intervention
except the email-send half (which still degrades cleanly to
the dev outbox).

## 4. Strengths

- **Settings CSV round-trip is now provably comprehensive.**
  A 30may audit (`guide/codebase_assessment_30may.md` source
  data) confirmed every per-session setting in
  ``spec/settings_inventory.md`` §2 / §2.5 / §3 / §4 / §9 /
  §9.5 round-trips with no asymmetries between serialize /
  apply, no model drift, and explicit test coverage for each
  category. The 18N PR 5 catch-up plus the
  ``data_shapes.self_review_handling`` PR closed the last
  gaps the prior assessment hinted at.
- **Self-review classification is unified.** Three places in
  code formerly computed self-review (pair-level helper,
  whole-group-aware helper, hardcoded ``FALSE`` in the
  by-instrument extract). The consolidation slice put
  ``Assignment.is_self_review`` in as the column-of-truth,
  with the canonical helper writing it at every trigger and a
  continuous-gate invariant catching drift. The latent
  by-instrument extract bug retired with its own regression
  test. Spec'd in ``spec/assignments.md`` § *Group-scoped
  instruments — the whole-group rule*.
- **Structural file-size creep mitigated.** Segment 18N's
  splits dropped the two largest files by 800+ LOC each
  without changing semantics; the package-shape pattern
  (``services/instruments/`` + ``services/responses/`` +
  ``services/extracts/`` + ``services/session_config_io/``)
  is the established way of carving when files cross
  ~1,500 LOC. The remaining big files (1,200-1,400) are
  cohesive single concerns.
- **Extract surface is richer than spec demanded.** The
  Data shaper's saved-shape library + Settings CSV
  round-trip means an operator can compose a custom CSV
  shape on one session and clone it to the next via the
  porting workflow — a use case the original spec didn't
  anticipate.
- **Audit-event detail envelope holds firm.** Every new
  ``_extracted`` audit event uses the canonical
  ``_IDENTITY | {counts, refs, context}`` shape; the
  ``context.self_review_handling`` slot threaded through the
  three target events (Reviewer / Reviewee metadata +
  ``data_shape_extracted``) cleanly.

## 5. Weaknesses

- **Email send is still inert.** Unchanged from the 28may
  read; the single largest functional gap and a hard pilot
  blocker. Gated on the host institution's transport choice;
  Segment 14B owns the activation.
- **Azure infrastructure is still deferred.** Unchanged. The
  in-app hardening shipped (14A); the platform side has not
  — no Key Vault, no VNet / private endpoints, no staging
  slot, no production environment, no Application Insights
  resource. Documented in ``guide/deferred_infra.md``.
- **Auth trust model is still thin by design.** Unchanged.
  Identity depends entirely on Azure Easy Auth populating
  ``X-MS-CLIENT-PRINCIPAL*`` headers, trusted verbatim —
  correct only if the platform gate is enforced. The startup
  check still does **not** hard-fail on
  ``ALLOW_FAKE_AUTH=true`` in a deployed environment.
- **Migration ordering exercised only by the Postgres CI
  job.** Unchanged. The SQLite suite builds the schema with
  ``create_all``; only the ``ci-postgres`` job round-trips
  the Alembic chain. That job should be a required status
  check on PRs.
- ~~**Per-individual rows × `Exclude self` on the Data
  shaper pinned at conservative interpretation.**~~ **Closed
  2026-05-30 by the chip-controlled-drop slice** (PRs #1654 →
  #1659). New per-shape `include_empty_rows` column +
  scope-row chip (`All rows` ↔ `Rows with data`) lets the
  operator opt into dropping rows whose accumulator is
  empty; the Q4 case (self-review-only row × `exclude_self`)
  closes by implication. Same general policy now drives the
  empty-row drop on all four Extract data cards (cycling-
  pill chips with explicit labels per state). Preview-table
  labels unified across saved + edit modes as a polish at
  the tail end (#1659). See
  `guide/archive/self_review_consolidate.md` addendum for
  the decision matrix + the dropped row-count-pill
  rationale.

## 6. Bugs and regressions

**Open:** none on in-scope surfaces. Two thorough audits this
week — the Extract data audit (2026-05-30, post-PR-#1646) and
the Settings round-trip audit (2026-05-30) — both came back
clean. The PR #1647 follow-up closed the three test-coverage
gaps the Extract data audit flagged.

**Closed since 28may:**

- **`by_instrument_extract.py:436` `SelfReview = FALSE`
  hardcode** (group-scoped rows). Latent since group-scoped
  instruments shipped. Fixed in PR #1635 (self-review
  consolidation PR 3) with dedicated regression test
  ``test_by_instrument_group_scoped_self_review.py``.
- **Silent settings round-trip drop.** 18N PR 5 closed the
  high-severity defect where the serializer wasn't updated
  after 18J Wave 2 PR iii-b4 retired the RTD table and moved
  type / bounds inline — every response field had been
  silently losing ``data_type``, ``min``, ``max``, ``step``,
  ``list_options``, and the ``visible`` flag on Zip-all →
  import for ~2 weeks. Eight 18G ``ReviewSession`` columns
  silently dropped on the same window. Six new round-trip
  regression tests pin the fix.
- **Reviewer-surface page-validity asymmetry.** 18N PR 1
  unified the page-validity check between GET / POST save /
  preview routes behind a ``validate_page_n`` helper; the
  pre-fix asymmetry was unreachable in practice but
  defensive-inconsistent.

The ``verify_self_review_classification`` continuous-gate
invariant in ``replace_assignments`` provides a permanent
drift detector for the new ``Assignment.is_self_review``
column — strict in tests, log + auto-correct in production.

## 7. Estimated size upon completion

The 28may projection put the MVP-complete codebase at ~70k
production LOC. Today's count is **~71,400** — already past
that estimate, driven by:

- Extract data slice: +~6,000 LOC across new services
  (``entity_metadata_extract.py``, ``data_shape_extract.py``,
  ``zip_bundle.py`` extensions, ``data_shapes.py``), the
  ``_extract_data.py`` route module, and the
  ``session_extract_data.html`` template.
- Self-review consolidation: +~1,500 LOC including the
  canonical helper + recompute hooks + invariant + the new
  test files.
- Segment 18N's splits added ~550 LOC of module-docstring
  scaffolding while reducing the largest files.

Remaining work to MVP-complete:

- **14B email infrastructure** (Parts A → E sequential + F →
  H optional backend swaps). Estimated +1,500-2,500 LOC for
  the sequential parts.
- **Segment 19 — Spec documentation.** Doc-only; doesn't
  move production LOC.
- **Segment 20 — Operator polish + documentation.** Mix of
  small UI polish PRs + `docs/` prose; estimated +500-1,000
  production LOC.

Realistic MVP-complete projection: **~73,000-75,000
production LOC**.

## 8. Bottom line

The Extract data feature shipped to a richer-than-spec state,
and the Self-review classification has a clean canonical
source of truth with a permanent drift gate. The 18N
housekeeping wave reversed the file-size creep watch-item.
The two thorough audits this week (Extract data + Settings
round-trip) both came back clean, with the only follow-up
actions being the test-coverage closure (done in PR #1647)
and the open Q4 on per-individual rows × `exclude_self` —
closed 2026-05-30 by the chip-controlled-drop slice
(PRs #1654 → #1657 + spec/archive close-out).

MVP-functional is two segments away: **14B** (email send,
the single hard blocker) and **20** (operator-facing docs +
polish). Azure infrastructure (Key Vault, VNet, staging,
production environment, Application Insights) is the
operational close-out beyond MVP, documented in
``guide/deferred_infra.md``.

Citizen-project cadence remains: single author + AI-agent;
102 PRs merged 2026-05-28 → 2026-05-30 with no rollbacks and
two clean post-implementation audits. The pattern that's
working — plan-doc-first → small-slice PRs → archive on
close-out → periodic assessment + spec sync — appears to
scale.
