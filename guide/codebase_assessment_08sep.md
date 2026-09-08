# Codebase assessment — 2026-09-08

**As of** the close of the **participant-disclosure arc** — Segments 19E and 19F
closed and archived, and Segment 19C closed with them, retiring the standing
"holding segment" shape it had run under since 2026-08-20. Unlike the previous
window, this one is mostly product: `/guide` shipped, and who may see a review
narrowed twice.

Since the 2026-09-05 snapshot:

- **Segment 19E — operator onboarding** (PRs #2130 → #2173, closed #2176,
  2026-09-05 → 2026-09-07) — the in-app `/guide`, the lobby first-run card, two
  CSV template sets, `What this page is for` disclosures on six Setup pages, and
  role-aware Guide sections.
- **Theme customizer v1.1 + lobby standardisation** (#2146, #2152 → #2155,
  #2159 → #2165, 2026-09-06) — interleaved with 19E, not part of it: primitive
  readout, unused-primitive marker, stale-document merge fix, and the lobby
  settling on one create affordance.
- **Segment 19F — reviewee participation disclosure** (#2174 → #2186, closed
  #2187, 2026-09-07 → 2026-09-08) — a reviewee's row, chip and `/results` now
  require a currently-resolving visibility grant, and all four session-scoped
  gates answer a bare 404.
- **Segment 19C Items 9 + 10, then its close** (#2188 → #2193, 2026-09-08) — the
  Settings-CSV import refuses a visibility cell the editor refuses; a Sys Admin
  card audits rows written before that guard; the segment closes.
- **Guide content + docs currency** (#2169 → #2172, #2190, #2194) — the author's
  walkthrough with screencaps, then the Instruments section rewritten from a
  supplied draft.

All shipped 2026-09-05 → 2026-09-08 (78 merge commits, 106 non-merge, over 4
calendar days), PRs **#2119 → #2194** (76 numbered; #2119 is the prior snapshot
itself). Numbers taken on `main` at `590993f0`, which the working branch is level
with. A single author directing AI agents, pre-deployment, no pilot yet —
twenty-plus merges in a day is normal here and should not be read against a team
cadence.

A standalone snapshot; `guide/archive/codebase_assessment_05sep.md` is the
prior one it supersedes, retired to the archive in the same change. Authoritative ship-state lives in `docs/status.md`; the functional spec
audited against is `spec/rrw_functional_spec.md` and the per-surface specs under
`spec/`.

---

## 1. What's in the box

Review Robin Web runs 360-style review cycles end to end. An **operator** creates
a **session**, imports **reviewer**, **reviewee** and **relationship** rosters
from CSV, designs one or more **instruments** (the questionnaire, its response
fields and its display fields), and lets the **assignment engine** fan those
instruments across the roster into **assignments**. Activating the session locks
setup and opens the **reviewer surface** at `/me/`, where each reviewer answers
their assigned instruments page by page. Responses flow back through **visibility
policies** that decide who may see what, in what form, and when: reviewees read
their **results**, observers read a cross-cohort **collation**, and the operator
monitors completion, sends reminders, and pulls **extracts** as CSV — which the
**rehydrate** path can read back to rebuild a session. Every mutation writes an
**audit event** against a per-type schema allowlist. It is a server-rendered
FastAPI + Jinja monolith on SQLAlchemy 2.x and Postgres.

**New since the 2026-09-05 snapshot:**

- **Segment 19E — operator onboarding** (#2130 → #2173, closed #2176). `/guide`
  is now the canonical operator documentation, served by `app/web/routes_guide.py`
  (90 LOC) off `app/web/views/_guide.py` (150 LOC), which filters sections by the
  audiences a viewer resolves; `docs/quickstart.md` retired to `docs/archive/`
  with its 11 live references repointed. Two **CSV template sets** — starter and
  demo — are byte-derived from the four serialisers by
  `app/services/setup_templates.py` (337 LOC) and served as zips by
  `app/web/routes_templates.py` (65 LOC) at `/templates/starter.zip` and
  `/templates/demo.zip`; the demo set is proved by a download → Quick Setup →
  `validated` round-trip rather than a fixture, which is the design call worth
  recording — a hand-maintained CSV would be a second source of truth for
  `spec/csv_contracts.md`. A `What this page is for` disclosure lands on six Setup
  pages via `operator/partials/_page_guidance.html`, contract in
  `spec/setup_pages.md` §0. The Guide carries the author's walkthrough with
  **sixteen screencaps** behind the app's first `StaticFiles` mount at `/static`
  (twelve at 19E's close, four added by #2190).
- **Segment 19F — reviewee participation disclosure** (#2174 → #2186, closed
  #2187). `visibility_policies.reviewee_has_current_grant()` is the new predicate;
  a reviewee's `/me` row, role chip, role-navigator chip and `/results` surface all
  hang off it, so roster membership alone no longer discloses that someone is the
  subject of a review. Two window corrections behind it in
  `app/services/session_lifecycle.py`: `while_ongoing` ⇔ `status = "ready"`, and
  `after_release` now requires `expired` **and** the anchor passed — closing two
  paths that had opened a release window on a session nobody had closed. The wide
  change is beyond the theme: all four session-scoped gates in `app/web/deps.py`
  (+134 LOC) answer a **bare 404** with no role-naming detail, so a signed-in
  stranger cannot enumerate session ids from status codes; sys-admins are exempt
  with a 403 on a session that exists and they do not own, existence checked
  first. `roles_held_anywhere` → `disclosable_roles` in
  `app/services/participants.py`, grant-aware.
- **Segment 19C Items 9 + 10** (#2188, #2191 → #2192). Item 9 put the
  `(audience, window)` cell check into the Settings-CSV import's parse phase
  (`session_config_io/_apply_parse._view_policy_cell_errors`, +102 LOC), reading
  `_PER_CELL_VALID_MODES` rather than restating it, so both writers answer to one
  table; an offending bundle now fails before anything is written. Item 10 is its
  retrospective half — `app/web/views/_visibility_audit.py` (186 LOC) reports every
  stored cell whose mode its pair disallows, on a read-only card on Sys Admin →
  Sessions Diagnostics, live findings first.
- **Theme customizer v1.1** (#2152 → #2155). A primitive readout, a marker for
  primitives no semantic token reaches, and a fix for document merges that had
  been dropping tokens added since a saved library was written.

**Unchanged this window:** the assignment engine, the instruments builder, the
reviewer surface's own form and save path, extracts, rehydrate, the audit
subsystem, the migration chain (77 files, 6,772 LOC, byte-identical), and every
`app/db/models/` module. No schema change shipped in this window.

---

## 2. Size (LOC)

LOC = physical lines over git-tracked files. Areas are pinned by
`guide/assessment.json`, committed 2026-09-04, so the denominators match the
prior snapshot exactly.

| Area | Files | LOC | Δ LOC from prior |
| --- | --- | --- | --- |
| `docs` | 231 (225 prior) | **119,775** | +9,785 (+8.9%) |
| `tests` | 269 (255 prior) | **92,425** | +4,501 (+5.1%) |
| `production` | 203 (198 prior) | **57,117** | +1,413 (+2.5%) |
| `templates` | 61 (59 prior) | **23,592** | +1,350 (+6.1%) |
| `tooling` | 9 (8 prior) | **11,481** | +1,203 (+11.7%) |
| `migrations` | 77 | **6,772** | unchanged |

**Test-to-production ratio: 1.62** (92,425 / 57,117), up from **1.58** (87,924 /
55,704). The rise is real but small, and it is not a quality claim on its own —
it reflects that this window's product work was gate-shaped, and a gate is
cheap to write and expensive to prove, so each rung carried more assertions than
lines.

**Suite: 2,936 passed, 16 skipped**, `ruff check .` clean, both CI tracks green
(`test` on SQLite and `postgres` on a `postgres:16` service container, the latter
also round-tripping the Alembic chain). All 16 skips are Wave 5 PR 5.3
legacy-instrument-card retirements plus one fixture-shape skip in
`test_sys_admin_outbox_child.py:113`; none masks a defect, and the one stale skip
the prior snapshot found was resolved there. **No xfail markers exist.**

### Biggest production files

| LOC | File | Δ |
| --- | --- | --- |
| 1,247 | `app/web/routes_operator/_instruments.py` | unchanged |
| 1,087 | `app/services/session_lifecycle.py` | +31 |
| 1,044 | `app/services/instruments/_instrument_crud.py` | +19 |
| 1,000 | `app/services/csv_imports.py` | unchanged |
| 984 | `app/web/routes_operator/_quick_setup.py` | unchanged |
| 981 | `app/web/views/_instruments.py` | unchanged |
| 974 | `app/services/responses/_core.py` | unchanged |
| 967 | `app/services/audit.py` | unchanged |
| 964 | `app/services/instruments/_response_fields.py` | unchanged |
| 954 | `app/services/validation.py` | unchanged |

**A plateau, and a fourth consecutive flat window at the top.** Seven of the ten
are byte-identical to the prior snapshot; the two that moved did so by 31 and 19
lines. `_instruments.py` has been at 1,247 for four snapshots, receding from the
17aug high of 1,317. This is a plateau rather than a long tail: the gap from #1
to #10 is 293 LOC, so no single file dominates, and nothing crossed a tripwire.
The next natural split candidate is unchanged and remains **watchlisted, not
queued** — see §9.

### Where the window's growth landed

**Production grew by 1,413 LOC, and 838 of it (59%) is five new modules**:
`setup_templates.py` (337), `_visibility_audit.py` (186), `_guide.py` (150),
`routes_guide.py` (90), `routes_templates.py` (65). The remaining 575 landed as
small additions on existing seams — `deps.py` +134 (the four gates and the
grant-composing dependency), `_apply_parse.py` +102 (the cell guard),
`participants.py` +95, `visibility_policies.py` +67, `session_lifecycle.py` +31,
and single-digit-to-30-line touches on `_dashboard.py` and `_shared.py`. **No
file gained more than 134 lines.** That is the shape the 18N/18O carves were
meant to produce, and it held under a window with two new user-facing surfaces:
new behaviour arrives as new small modules, and existing modules absorb only the
lines that genuinely belong to them.

**`docs` grew 8.9%, the largest movement of any area, and that is this window's
real signature.** The two biggest single files are the archived segment plans —
`segment_19E_operator_onboarding.md` (1,224) and
`segment_19F_reviewee_participation_disclosure.md` (1,194) — with 913 more lines
of net movement inside `guide/` and 374 in `todo_master.md`. One new spec landed
(`spec/role_landing_and_visibility.md`, 290). **Plans now outweigh the code they
describe by a wide margin**, which is the intended trade of the "plan in, spec
out" rule and is worth naming as a cost as well as a discipline: a 1,200-line
plan is not read end to end, which is one of the three reasons 19C closed (§5).

**`templates` +1,350**, of which `guide.html` is 501 and `base.html` 298; the
rest is the Setup-page guidance partial and the lobby/sys-admin cards.
**`tooling` +1,203 (+11.7%)** is almost entirely regenerated customizer HTML, not
hand-written logic — the generators themselves moved by far less. That percentage
should not be read as tooling complexity growing.

### Package shape

| Package | Modules | In sub-packages |
| --- | --- | --- |
| `app/services` | 96 | 56 |
| `app/web/routes_operator` | 22 | 0 |
| `app/web/views` | 21 (+1) | 0 |
| `app/db/models` | 21 | 0 |
| `app/web/routes_reviewer` | 12 | 5 |
| `app/auth` | 3 | 0 |

`app/web/views/` gained `_visibility_audit.py`, `app/services/` gained
`setup_templates.py`, and `app/web/` gained two routers. The fourth seam
(`app/web/views/`) absorbed the window's one genuinely new view-shape concern
without any route or service growing to hold it, which is the seam working as
specified in `spec/architecture.md`.

---

## 3. Functional-spec compliance

Rows are checked against code, not against the specs' self-description. **Five
rows changed this window.** `tests/unit/test_spec_coverage.py` continues to
assert set equality between the live route table and `SPEC_COVERAGE` ∪
`INFRASTRUCTURE_MODULES` — now **29 mapped modules over 22 distinct spec paths,
plus 3 infrastructure modules (32 first-party routing modules)**, up from 30
modules at the prior snapshot as the two new routers landed and were mapped.

| Functional area | Spec | Code status |
| --- | --- | --- |
| Session lifecycle (5 live states) | `spec/lifecycle.md` | ✓ shipped — `app/services/session_lifecycle.py` |
| Sessions lobby + Session Home | `spec/sessions_overview.md`, `spec/session_home.md` | ✓ shipped |
| Quick Setup card | `spec/quick_setup_card_spec.md` | ✓ shipped — `_quick_setup.py` |
| Setup pages (5) | `spec/setup_pages.md` | ✓ shipped |
| **Setup-page guidance disclosure** | **`spec/setup_pages.md` §0** | **✓ shipped 2026-09-06 (19E rung 6) — `partials/_page_guidance.html` on six pages** |
| Roster CSV + friendly tag labels | `spec/csv_contracts.md` | ✓ shipped 2026-08-20 |
| **CSV template sets (starter + demo)** | **`spec/csv_contracts.md`** | **✓ shipped 2026-09-06 (19E rungs 4–5) — `setup_templates.py`, `/templates/{starter,demo}.zip`, byte-derived from the serialisers** |
| Assignment engine | `spec/assignments.md` | ✓ shipped — `app/services/assignments/` |
| Instruments (Bands 1/2/3) | `spec/instruments.md` | ✓ shipped — `instruments/` (9 modules) |
| Validate page | `spec/validate_page.md` | ✓ shipped — `validation.py` |
| Reviewer surface `/me/` | `spec/reviewer-surface.md` | ✓ shipped — `routes_reviewer/` |
| **Reviewee results (3 modes)** | **`spec/visibility_policy.md`, `spec/participant_model.md`** | **✓ shipped; gate tightened 2026-09-08 (19F) — `require_reviewee_with_current_grant`, bare 404 without a resolving grant** |
| Observer collation + cohorts | `spec/participant_model.md` | ✓ shipped; archive short-circuit added 19F PR 5 |
| **In-app operator Guide** | **`spec/operator_ui_concept.md`, `spec/role_landing_and_visibility.md`** | **✓ shipped 2026-09-07 (19E) — `routes_guide.py`, audience-filtered; a viewer resolving nothing is bounced to `/about`** |
| **Session-id enumeration closed** | **`spec/permissions.md`, `docs/security_posture.md`** | **✓ shipped 2026-09-08 (19F PR 1) — all four session-scoped gates answer a bare 404; sys-admin 403 exemption behind an existence check** |
| **Visibility-cell integrity** | **`spec/visibility_policy.md` §3.1** | **✓ shipped 2026-09-08 (19C Items 9 + 10) — import guard + read-only Sys Admin audit card** |
| Extracts + Extract data tab | `spec/csv_contracts.md`, `spec/extract_data.md` | ✓ shipped |
| Rehydrate | `spec/rehydrate.md` | ✓ shipped — `session_rehydrate.py` |
| Audit events + envelope schema | `spec/architecture.md` | ✓ shipped — `EVENT_SCHEMAS` strict gate |
| Sys-admin + three-tier roles | `spec/permissions.md`, `docs/security_posture.md` | ✓ shipped |
| Light/dark mode | `spec/visual_style_rrw.md` | ✓ shipped 2026-08-21 |
| Two-tier semantic colour tokens | `spec/color_tokens.md` | ✓ shipped 2026-08-23 |
| Theme customizer (developer) | `guide/theme_customizer.md` | ✓ v1.1 shipped 2026-09-06 |
| Email template editor | `spec/email_template_editor.md` | ✓ shipped 2026-09-05 |
| Operator theming (in-app tweaker) | `guide/theme_customizer.md` Stretch | ⏸ planned — `guide/deferred_consolidated.md` Part A |
| Email dispatch / invitations | `guide/segment_14B_email_infrastructure.md` | ⛔ blocked — `email_send.py` has the SMTP backend and writes outbox rows; no live dispatch caller. Gated on institutional Azure provisioning |
| Blob storage | `spec/blob_storage.md`, `guide/segment_18Q_blob.md` | ⏸ planned — awaiting institutional storage account |
| **Technical-support contact (global)** | **none — stub in `guide/todo_master.md`** | **⏸ planned; unhomed 2026-09-08 when 19C closed. Was mis-filed in `docs/status.md` as "19C Item 8" and never built** |
| **Operator button audit §§4–5** | **`spec/operator_button_audit.md`** | **⚠ drift — the spec is behind. Sections 4–5 describe a Session Home layout 18R Item 4 replaced three weeks ago; a staleness banner names all three false claims and the regeneration is filed** |

**Doc-drift work this window.** Three closes ran `spec-writer` over their
doc-impact files. 19E's found three drift items in two files; 19F's found four
(three prose, one that was a code defect and became rung 7); 19C's found five
files, four fixed. **Three of 19C's five were pre-19C drift it had inherited** —
18R Item 4 retired the Edit Session Details page on 2026-08-19,
`spec/session_home.md` recorded it, and three documents that *summarise* that
file did not. The remaining open item is the `operator_button_audit.md` row
above, deliberately deferred rather than absorbed into a close.

---

## 4. Strengths

- **New surfaces arrive as new modules, not as accumulation.** 59% of this
  window's production growth is five files averaging 168 LOC; the largest single
  addition to an existing file is 134 lines, and the top-ten table is a plateau
  with seven files byte-identical. Two user-facing surfaces (`/guide`, the audit
  card) landed without moving any file toward its tripwire.
- **One rule, one table, two enforcement points.** `_PER_CELL_VALID_MODES` is
  read by the Band 3 editor, by the Settings-CSV import guard (Item 9) and by the
  audit card (Item 10) — none restates it. The same pattern holds for the
  `/guide` audience filter, which derives its operator predicate from
  `require_operator` rather than duplicating it. Where the codebase has resisted
  drift, this is consistently why.
- **The fourth seam absorbed the window's one new view concern.** `app/web/views/`
  took `_visibility_audit.py` without any route handler or service growing to
  hold view shape, which is exactly what `spec/architecture.md` specifies it for.
  Two windows ago that seam was a rule; it is now load-bearing.
- **Closes find things that tests structurally cannot.** Each of the three closes
  in this window surfaced defects no test could have caught: prose that contradicts
  a constant, a summary that stopped agreeing with its source, and — in 19F's case
  — a live UI affordance pointing at a route that had started refusing. The
  close-time `spec-writer` pass is now the highest-yield check in the process, and
  it is four windows old.
- **Gate changes shipped without a regression.** Converting every session-scoped
  refusal from 403 to 404 touched 24 assertions across 12 files against a measured
  ceiling of 47, and the suite went from 2,704 to 2,936 passing with no reverts.

---

## 5. Weaknesses

- **The holding-segment shape produced a plan nobody reads, and it took nineteen
  days to notice.** 19C accreted ten items and 1,893 lines. Worse, because
  `close_check`'s window runs from a manifest's first commit to the close, 19C's
  window *swallowed 19A, 19E and 19F whole* — so both of its advisory notes
  pointed at other segments' work, and the check could not distinguish "touched
  during this segment" from "touched by it". **Cost:** a close that had to
  adjudicate two notes belonging to other segments, and a manifest whose C3 check
  was effectively meaningless. **Plan:** the shape is retired — new refinements
  get their own segments (author, 2026-09-08). The `close_check` window semantics
  are unchanged and would behave identically on the next long-lived segment; that
  is filed here, not planned.
- **Summaries stop agreeing with their sources, silently, and nothing compares
  them.** Four separate instances this window: `spec/permissions.md` had the
  enumeration threat model backwards; `spec/visibility_policy.md` §3.1 stated the
  per-cell rule as the opposite of the constant it documents; three files
  summarising `spec/session_home.md` described a page retired three weeks earlier;
  and one wrong cross-file pointer (`"Segment 19C Item 8"`) had three copies. All
  four were found by a human-directed audit, none by a check. **Cost:** each was
  live for between three weeks and four months. **Plan:** none — the sweep cadence
  finds these on an 8-week trigger, which is slower than they appear.
- **`spec/operator_button_audit.md` §§4–5 are knowingly stale.** They describe a
  Session Home layout replaced on 2026-08-19. A banner names the three false
  claims and the regeneration is filed in `todo_master`, but the file remains
  wrong in the meantime, and it is the file `CLAUDE.md` points at for button
  vocabulary. **Cost:** a reader consulting it for layout gets 2026-05 reality.
  **Plan:** filed, one PR, unstarted.
- **The audit card has never run against real data.** `_visibility_audit.py` is
  proven against fixtures only; the pilot has not deployed, so a green card today
  means "no rows here" and there are almost none. **Cost:** the one check written
  specifically to find pre-existing bad data has produced no evidence about
  pre-existing bad data. **Plan:** its first real run is at deploy, before any
  reviewee-facing window opens — recorded in the item, not automated.
- **`app/services` at 96 modules is the largest package and has no stated
  ceiling.** 56 of those sit in sub-packages, which is the 18O carve working, but
  the top-level 40 have accreted without a rule for when a concern earns a
  sub-package. **Cost:** none yet; it is a navigability risk, not a correctness
  one. **Plan:** none. Filed as an observation.

---

## 6. Bugs and regressions

**No known open bugs at `590993f0`**, and here is what that claim rests on: both
CI tracks green on the merged head; `ruff check .` clean; all 16 skips read and
attributed (15 Wave 5 legacy-card retirements, one fixture shape — none masking a
defect); no `xfail` markers anywhere in `tests/`; no unresolved review threads on
any of the window's 76 PRs; and `docs/known_limitations.md` reviewed against the
window's changes with nothing to add.

Two things are **known and deliberately not fixed**:

- **The archived reviewer surface renders no chip strip.** It serves
  `reviewer/pre_open.html`, which has never included the partial (unchanged since
  `f2899b07`), so a multi-role user loses the role navigator on that one page.
  Cosmetic, pre-existing, no disclosure consequence. Recorded in 19F's plan.
- **`spec/operator_button_audit.md` §§4–5** — see §5.

Caught and fixed this window, worth remembering:

- **A test that asserted the defect** (#2186). `test_collation_chips_show_reviewee_when_user_holds_both`
  set up an ungranted reviewee and asserted a *live* chip. It was written before
  19F PR 4 made the target refuse, and no rung revisited it — so the suite was
  pinning the bug in place while every other assertion passed.
- **A grep-shaped tripwire defeated by a comment explaining it** (#2183). 19F's
  Definition of done greps `app/` for a marker phrase; a comment quoting that
  phrase left the tripwire permanently tripped. It recurred in a second form:
  `_shared.py` carried "the W16 / W17 gates will land later", which says the same
  thing and passes the grep.
- **A negative assertion only as strong as its status code** (#2179). A sys-admin
  test asserted `!= 403` against a URL that has never existed, so it passed on a
  404 from the router and would have gone on passing with the bypass deleted.
- **Two release-window paths that opened on a session nobody had closed**
  (#2181) — a backdated anchor on Session Edit, and `revert_session_to_draft`
  never clearing the anchor.
- **`/about` rendering "Signed in as " with an empty name** (#2184) — the
  identical defect 19E rung 7 fixed on `/guide`, in the sibling route nobody
  re-checked.
- **A CSS-class interpolation that would have rendered nothing** (#2192) — the
  reviewer audience is stored as `peer_reviewer` while `base.html` styles
  `.pill-role-reviewer`, so `pill-role-{{ audience }}` produces a class that does
  not exist. Invisible in a markup review; visible only on the page.

---

## 7. Estimated size upon completion

Current: **57,117** production, **23,592** templates, **92,425** tests,
**11,481** tooling.

| Remaining work | Production LOC | Templates | Depends on |
| --- | --- | --- | --- |
| Segment 14B — email dispatch, reminders, invitations | +900–1,400 | +200–400 | institutional Azure provisioning |
| Segment 20 — operator polish + documentation | +200–500 | +300–600 | nothing (unblocked) |
| Blob storage (18Q) seam + first consumers | +400–700 | +50–150 | institutional storage account |
| Operator theming (Stretch) | +150–300 | +100–200 | customizer editor core (shipped) |
| Technical-support contact (global) | +30–60 | +20–50 | nothing (unblocked) |

**Projected feature-complete v1: ~58.8–60.1k production, ~24.3–25.0k templates.**

**Reconcile against 05sep.** That snapshot projected **~57.4–58.6k production,
~22.9–23.6k templates**. This one projects **+1.4k production and +1.4k
templates** higher — and **the movement is almost entirely current totals, not
new scope**: production grew 1,413 LOC and templates 1,350 because 19E and 19F
shipped real surface, which the prior projection had not modelled as arriving in
this window. Production is now **57,117**, already inside the range 05sep
projected for *feature-complete v1* with four work items still outstanding; that
projection was too low, and the honest reading is that it under-weighted how much
surface 19E would add. **One item of scope was discovered** (the technical-support
contact, +30–60) and it was not new work — it was work mis-filed as shipped
under "19C Item 8" and found unbuilt at 19C's close. Nothing was cut. Excludes
anything past v1.

---

## 8. Bottom line

The codebase shipped two segments and closed a third in four days, and the
product change worth naming is that **who may see a review is now decided by a
grant rather than by roster membership** — a reviewee's row, chip and results
page all hang off one predicate, and every session-scoped refusal returns a bare
404 so a signed-in stranger cannot enumerate session ids. Alongside it, `/guide`
gave the operator surface its first in-app documentation. Structurally the
window was cheap: 59% of production growth is five new small modules, the
biggest-file table is a four-window plateau, and no file crossed a tripwire. The
one live thread is that **the specs' summaries keep drifting from their sources
without any check noticing** — four instances this window, found by human-directed
audit, live for between three weeks and four months.

**Recommended next moves:**

1. **Segment 20 (operator polish + documentation)** — still the only unblocked
   feature work, and now more clearly the right next thing than at the prior
   snapshot: 19E built the in-app Guide that Segment 20 would otherwise have
   written, so what remains is genuinely the institutional-host half. It is also
   the first segment that will run start to finish under the new one-segment-per-
   theme rule that replaced 19C's holding shape.
2. **Regenerate `spec/operator_button_audit.md` §§4–5** before the next UI work,
   not after. It is filed, it is one PR, and it is the file `CLAUDE.md` points at
   for button vocabulary — leaving a knowingly-wrong layout section in the
   reference that governs the next button change is the cheapest way to
   manufacture a fifth summary-drift instance.
3. **Decide whether summary drift deserves a mechanism.** Four instances in one
   window, each live for weeks, all found by hand. A check that compares a
   prose claim to a constant is hard; a check that lists which documents
   *summarise* another and flags them when the source changes is not obviously
   hard. Worth one session of thinking before the sweep cadence's next trigger,
   because the sweep finds these on an 8-week clock and they are appearing faster.

**Settling 05sep's proposals.** Move #1 (decide whether a stale skip marker
deserves a mechanism) — **carried, unactioned**; no skip went stale this window
and the question is still open. Move #2 (Segment 20 as the first segment under
the new gates) — **carried**; 19E, 19F and 19C's close all ran under them
instead, and they held, so the evidence Move #2 wanted has partly arrived
without Segment 20. Move #3 (fix the `close_check.py` segment-level blind spot
before Segment 20 closes) — **shipped** (#2121, item-tagged manifest bullets now
date from their own heading), and 19C's close then exposed a *different* blind
spot in the same tool: a window long enough to contain other segments makes C3
meaningless (§5).

---

## 9. Proposed file splits — watchlist

**No split is queued, and the top of the table is flat for a fourth consecutive
window.** The watchlist is carried with updated numbers.

- **`app/web/routes_operator/_instruments.py` (1,247 LOC, unchanged).** Fourth
  flat window, still below the 17aug high of 1,317. The seam if it grows: carve
  the `/save` payload-parsing blocks into a `_save.py` sibling, leaving the thin
  route in place — mirrors the 18N/18O per-concern carves. Revisit only past
  ~1,400.
- **`app/services/session_lifecycle.py` (1,087 LOC, +31).** Grew by the
  `after_release` window precondition and its docstring. Still no natural seam;
  the state machine is cohesive and splitting it would scatter the transition
  table. Watch, do not plan.
- **`app/services/instruments/_instrument_crud.py` (1,044 LOC, +19).** Three
  concerns in one module (lifecycle, group/unit-of-review, column-widths); past
  ~1,200 the column-widths helpers are the cleanest carve.

**Watchlist tripwire: ~1,400 for `_instruments.py`, ~1,200 for the other two.**
None is within 150 LOC of its tripwire.

`tools/close_check.py` — flagged at 770 LOC in the prior snapshot as carrying two
jobs — is now **863 LOC (+93)**, the growth being the item-dating fix (#2121) and
its `--stale` reporting. It is unchanged in *shape*: still the per-segment close
check and the sweep-cadence report sharing `REPO`, `_git` and
`last_touched_ever` and nothing else. The observation stands, is now larger than
when it was made, and is still not a proposal — it is dev tooling with one
caller, and splitting it would buy a reader nothing the module docstring does not
already give them.
