# Segments 1–10 — Unfinished items audit

**As of:** 2026-05-02
**Source:** `guide/low_intensity_workplan_review_robin_web.md` cross-referenced
with the per-segment plans in `guide/archive/segment_*` and
`guide/segment_10*.md`, the current `docs/status.md`, and
`guide/unfinished_business.md`.

**Purpose.** The workplan declared segments 1–10 as the run-up to the
"first end-to-end milestone" (workplan §23). All ten shipped, but a
handful of work items inside each segment's plan were dropped, deferred,
or silently superseded along the way. This file inventories those
items so they don't get lost.

**Scope.** Items the workplan or a per-segment plan explicitly listed as
in-scope for that segment, that did **not** ship as part of that
segment. Items the workplan explicitly listed as "Keep deliberately
out of scope" — and that are owned by a clearly named later segment
(11+) — are noted only when they're load-bearing for the surface
shipped today (e.g. `/setupinvite` is a stub today; the editor was
previously deferred to Segment 15 and has since been pulled back as
unfinished business — see `unfinished_business.md` #24).

For each item the audit notes whether it is:
- **`[tracked-uf #N]`** — already an entry in
  `guide/unfinished_business.md`. Cross-reference and move on; no
  action needed here.
- **`[tracked-status]`** — listed in `docs/status.md` "What's
  deliberately not yet there" with a named target segment.
- **`[unfiled]`** — not tracked anywhere yet. These are the items most
  worth surfacing.

---

## Headline findings

The audit surfaces **seven `[unfiled]` items** that are neither in
`unfinished_business.md` nor in the `docs/status.md` deferred-items
table. Only two are load-bearing; the rest are minor:

1. **AG Grid replacement of the reviewer table** (Segment 8). Workplan
   §11 explicitly called this out as the second half of the segment;
   plain HTML table shipped instead and the upgrade was never
   re-scoped. Today the surface works without it. Worth a paragraph
   in `docs/status.md` "What's deliberately not yet there" so it
   doesn't quietly become "the way it always was."
2. **Vanilla-JS autosave** (Segment 8 follow-on). Status.md mentions
   it briefly ("Follow-on PR after Segment 8"), but no segment owns
   it.
3. **Queue-based batch invitation sending** (Segment 9 workplan
   §12 work item #7). Never implemented; invitations send synchronously
   into the dev outbox. Will probably be addressed alongside Segment 15
   real-SMTP work, but no plan currently names it.
4. **Operator UI to flip `Reviewer.status` / `Reviewee.status` to
   inactive** (status filter is defensive today). Listed in status.md
   as "Not yet planned" — call it out explicitly so it doesn't
   surprise an operator who expects an Inactivate button.
5. **Inline-editable rows for reviewers / reviewees / assignments**
   (Segment 9.4 deferred scope). Listed in status.md as "Not yet
   planned; would slot before activation." The disabled "Edit"
   buttons render across all three Manage pages today as
   placeholders.
6. **Sort-column UX for response / display fields** (Segment 10C/10D
   deferred scope). The 10D plan flagged "semantics ('default row
   order on reviewer surface') not yet decided" and the sort affordance
   never landed. Low priority; flag so the next instruments-page touch
   doesn't accidentally re-decide it without context.
7. **Local Postgres docker-compose for dev** (Segment 4/5 deferred per
   `segment_05A.md` §3.5). SQLite + CI Postgres covers most needs;
   flagged here as a known deferral, not a silent drop.

The rest of the items in this audit are **already tracked** in
`unfinished_business.md` or `docs/status.md`. Those entries link back
so the punch list can be consumed front-to-back without surprises.

---

## Segment 1 — Repository setup

**Delivered.** Repository skeleton (FastAPI app, `pyproject.toml`,
`AGENTS.md`/`CLAUDE.md` twins, `spec/functional_spec.md`), `/health`
smoke test, GitHub PR rhythm.

**Unfinished items.** None. All work items in workplan §4 + segment
plan §7 shipped.

---

## Segment 2 — Azure hello-world deployment

**Delivered.** Azure App Service provisioned, GitHub Actions OIDC
deploy workflow, `/health` reachable in browser, runtime + deploy
logs accessible.

**Unfinished items.** None. All workplan §5 work items shipped.

---

## Segment 3 — Authentication proof-of-concept

**Delivered.** Easy Auth enabled, `/me` and `/me/debug` introspection
routes, `AuthenticatedUser` parsing of `X-MS-CLIENT-PRINCIPAL` headers,
`ALLOW_FAKE_AUTH=true` local fallback.

**Unfinished items.** None per the workplan §6 / segment plan scope.
The CSRF / SameSite question raised by the move to plain `<form
method="post">` is not a Segment 3 deferral but a downstream concern:

- **CSRF decision write-up** — `[tracked-uf #7]` in
  `unfinished_business.md`. Segment 3 didn't take a stance because
  forms didn't exist yet; the decision falls due now that the
  operator surface is form-heavy.

---

## Segment 4 — Core data model and migrations

**Delivered.** SQLAlchemy 2.x models for the 12 core entities (User,
ReviewSession, SessionOperator, Reviewer, Reviewee, Instrument,
InstrumentDisplayField, InstrumentResponseField, Assignment, Response,
Invitation, AuditEvent — plus ResponseTypeDefinition added in 10D),
Alembic migration infra, model relationship tests.

**Unfinished items.**

- **Local Postgres dev loop / docker-compose** — `[unfiled]`. Workplan
  §7 listed "Connect deployed app to development PostgreSQL" as a
  segment-4 work item; `segment_05A.md` §3.5 explicitly deferred local
  Postgres in favour of "SQLite local + CI Postgres + migration-on-deploy"
  as the parity story. Reasoning is documented in 05A; this entry is
  here so the deferral isn't mistaken for a silent drop.

---

## Segment 5 — Operator session setup MVP

**Delivered.** Postgres Flexible Server provisioned + GRANT bootstrap;
`migrate-on-deploy` GitHub Actions step; operator session list / create
form / detail page; `SessionOperator` ownership model;
`require_session_operator` permission gate; `session.created` audit
event; tests for create / list / detail / access denial.

**Unfinished items.** None. All workplan §8 work items shipped. The
"Keep deliberately out of scope" items (CSV upload, instrument
builder, activation, invitations) all landed in their named target
segments (6 / 10 / 9.1 / 9.2).

---

## Segment 6 — Import and validation MVP

**Delivered.** Reviewer + reviewee CSV import with row-level validation
(missing required columns, duplicate emails, invalid email format), 1
MiB / 5000-row caps, replace-all semantics with cascade-warning
checkbox, setup-validation page, audit events
`reviewers.imported` / `reviewees.imported` / `*.deleted_all`.

**Unfinished items.**

- **Excel upload** — workplan §9 "Keep deliberately out of scope".
  No follow-up planned; CSV is the documented contract.
- **Complex import-mapping UI** — workplan §9 "Keep deliberately out
  of scope". Today's contract is fixed column names; no user-facing
  mapping picker.
- **CSV email-validation drift** — `[tracked-uf #8]`. The reviewer +
  reviewee parsers have slightly different rules; small bug.
- **Reviewer/Reviewee CSV cross-table identity check** —
  `[tracked-uf #12]`. Person-with-same-email-different-name-in-both
  tables imports cleanly today and surfaces as a mismatch downstream.

---

## Segment 7 — Assignment generation MVP

**Delivered.** FullMatrix + Manual modes; preview + replace-all save;
self-review exclusion option (case-insensitive email); manual CSV
validation (unknown reviewer / reviewee references, inactive rows,
duplicates); `assignment_mode` column + `Assignment.created_by_mode`
discriminator; `excluded_counts: {self_review, inactive_reviewer,
inactive_reviewee}` audit detail; assignments hub Manage view; tests.

**Unfinished items.** None against Segment 7 scope. Items the workplan
§10 marked "Keep deliberately out of scope":
- **RuleBased assignment** — owned by Segment 12.
- **Random allocation policies** — Segment 12 contingent.
- **Multi-instrument-aware assignments** — Segment 13 (data layer
  shipped early in 10C; UI gate in 10D).

---

## Segment 8 — Reviewer review-surface MVP

**Delivered.** Reviewer dashboard at `/reviewer` with per-session pill
(`not started` / `in progress` / `submitted`); review surface at
`/reviewer/sessions/{id}` rendering an editable HTML table with
per-instrument loop, assignment rows, response fields, save / submit /
clear / cancel; required-field validation with warn-and-acknowledge
override; tests.

**Unfinished items.**

- **AG Grid replacement of the plain HTML table** — `[unfiled]`. The
  workplan §11 was explicit: "Implement a simple tabular review page
  first with ordinary HTML inputs before introducing AG Grid. … Now
  replace the simple table with AG Grid while keeping the same save
  endpoint." The first half shipped; the second half didn't. Status.md
  doesn't list this as deferred — easy to mistake for "the design"
  rather than "the placeholder." Worth either committing to keep the
  HTML table (and updating workplan + status) or naming a target
  segment.
- **Vanilla-JS autosave on top of `/save`** — `[unfiled]`. Status.md
  mentions it ("Follow-on PR after Segment 8") but no plan owns it.
  Reviewer experience today requires explicit Save clicks.
- **Polished spreadsheet UX, multi-tab multi-instrument review,
  complex autosave conflict handling** — workplan §11 "Keep
  deliberately out of scope". Multi-instrument review is now
  reachable in 10D Slice 5 but the per-instrument tab affordance
  itself isn't there (template loops over instruments and renders
  tables stacked).

---

## Segment 9 — Invitation, monitoring, reminder MVP

The workplan's single Segment 9 split mid-build into 9.1 / 9.2 / 9.3 /
9.4A-C / 9.5A. Audit follows the split.

### Segment 9.1 — Activation lifecycle

**Delivered.** `draft ↔ ready` state machine, edit-lock at `ready`,
per-instrument `accepting_responses` flag, deadline enforcement on
reviewer routes (HTTP 403 when not accepting), revert flow,
`session.activated` / `session.reverted_to_draft` / `instrument.opened`
/ `instrument.closed` audit events, lazy-close on deadline observe.

**Unfinished items.**

- **`expired` / `archived` session states** — workplan §12 hinted at
  these via "Freeze or mark active configuration" but 9.1 deferred
  them. `expired` is a Segment 9.3+ concern (deadline-driven);
  `archived` is Segment 11+ (retention). Both reserved as enum
  values today but unused.
- **`correlation_id` threaded into deadline lazy-close** —
  `[tracked-uf #10]`.

### Segment 9.2 — Invitations + dev outbox

**Delivered.** Invitation model (`pending` → `sent` → `opened`),
bulk-create on ready sessions, dev-mode outbox (writes a row, doesn't
send), token-based reviewer landing route (`/reviewer/invite/{token}`)
with email-match check, `invitation.sent` / `invitation.opened` /
`invitation.regenerated` audit events.

**Unfinished items.**

- **Email template editor (operator-editable)** — `[tracked-uf #24]`.
  Workplan §12 work item #5 ("Add invitation email template"); AI
  prompt called for "merge fields for reviewer name, session name,
  deadline, **help contact**, and review link." Today
  `/operator/sessions/{id}/setupinvite` is a stub page; merge-field
  rendering is hardcoded in `invitations._email_body` /
  `_reminder_body`; no operator-editable template. Pulled back from
  Segment 15 (where it had been auto-bundled with real SMTP) since
  the editor and the dev outbox are independent — the editor shapes
  the body the existing outbox already renders.
- **Real SMTP / Azure email backend** — `[tracked-status]`. Owned by
  Segment 15.
- **Queue-based batch invitation sending** — `[unfiled]`. Workplan
  §12 work item #7 explicitly named "Add queue-based batch sending."
  Never implemented; the outbox-write loop runs synchronously inside
  the request. Will probably get rolled into Segment 15 real-SMTP
  work but no plan currently owns it. Worth a status.md row.
- **`invitations.py` coupling to FastAPI `Request`** —
  `[tracked-uf #6]`. Mostly matters when real SMTP lands and
  invitation send moves out of the request lifecycle.
- **"Help contact" merge field** — `[tracked-uf #24]`. Workplan §12
  listed it but the spec doesn't define where the help contact
  comes from (per-session? per-operator? global env var?). The
  open question is now folded into #24 as the prerequisite
  decision before the editor lands.

### Segment 9.3 — Monitoring + reminders

**Delivered.** Per-session `/monitoring` page with per-reviewer
progress (assignment count, completed, missing required, pill state,
last-reminded-at); `remind` (per-row) and `remind-incomplete` (bulk)
actions; `reminders.sent` audit event with `fell_back_count`.

**Unfinished items.**

- **Sophisticated reminder filters** — workplan §12 "Keep
  deliberately out of scope". Today: "incomplete = not in submitted
  pill state." No segmentation by submitted-with-warn-override vs
  never-opened, etc.
- **Bounce tracking** — workplan §12 "Keep deliberately out of
  scope". Hard to do without real SMTP anyway.

### Segment 9.4 — Operator UI restructure (A / B / C)

**Delivered.** Page chrome (app identity, breadcrumb, signed-in user
card); sessions list with Access / Delete + Create button + Created-by
column; session detail four-card layout; inline `?validated=1`
summary card; `/delete-data` action; reshape of Reviewers / Reviewees
/ Assignments Manage pages; six-button setup-nav header; Instruments
index page (later rebuilt in 10C/10D); `/setupinvite` stub; `/about`
stub.

**Unfinished items.**

- **Inline-editable rows for reviewers / reviewees / assignments** —
  `[tracked-status]` ("Edit individual reviewer / reviewee /
  assignment rows … Not yet planned; would slot before activation").
  The "Edit Reviewers / Reviewees / Assignments" buttons across the
  three Manage pages render as disabled placeholders today. Whatever
  pattern lands here will likely apply to all three.
- **Operator UI to flip `Reviewer.status` / `Reviewee.status` to
  inactive** — `[tracked-status]` ("Not yet planned"). The
  per-row inactive filter is enforced defensively in
  assignment-generation and reviewer-surface paths but operators
  have no UI to set the flag.
- **Real implementation of `/setupinvite`** — covered above under
  9.2.
- **Real `/extract` route** — owned by **Segment 11** (covered in
  status.md).
- **RuleBased rule editor `#rules` card on the assignments page** —
  owned by **Segment 12** (covered in status.md).

### Segment 9.5A — `validated` lifecycle state

**Delivered.** `validated` enum value between `draft` and `ready`;
`?validated=1` flips draft → validated when no errors; activation
requires `is_validated`; setup-mutating routes flip
`validated → draft` via `_invalidate_if_validated` (now
`lifecycle.invalidate_if_validated()` post-#3); per-instrument
open/close/visibility deliberately exempt; `session.validated` /
`session.invalidated` audit events.

**Unfinished items.** None. The arch followups (move policy into
services, decide bulk-visibility exemption) shipped in PR #299
(items `[tracked-uf #3]` + `[tracked-uf #16]`, both ✅).

---

## Segment 10 — Instrument builder MVP

The workplan called Segment 10 a single "Instrument builder MVP"
block. The actual segment expanded into 10A → 10B-1 → 10B-2 → 10B-3
→ 10C → 10D. Audit summarises by sub-segment.

### Segment 10A — Response-field builder + reviewer-surface refactor

**Delivered.** Consolidated `/operator/sessions/{id}/instruments`
page; per-instrument card with response-field table (add / edit /
delete / reorder, per-field help-text + visibility); migration adds
`help_text` + `help_text_visible`; reviewer surface refactors to
loop-by-instrument; empty-instrument validation blocks activation;
`instrument.field_added/updated/deleted/fields_reordered` audit
events.

**Unfinished items.** None against 10A's stated scope.

### Segment 10B-1 / 10B-2 / 10B-3 — Display fields + preview

**Delivered.** Backfill migration seeding `pair_context_1/2/3` display
fields; reviewer surface renders pair-context as separate columns;
per-instrument display-fields card with Add (over seven sources) /
Edit / Delete; shared bulk-save form for display + response fields;
`instrument.display_field_*` audit events;
`/operator/sessions/{id}/preview` route with synthetic-row padding.

**Unfinished items.**

- **Display Fields persistence on the operator UI placeholder rows** —
  the 10C entry in status.md flagged this; the 10D Slice 1 + 2 work
  has now wired the operator UI to the existing routes, so the
  placeholder is gone in current main. Marked complete in
  `[tracked-uf #13]` and `[tracked-uf #14]`.

### Segment 10C — Operator UI cleanup

**Delivered.** `.page-grid` two-column layout; six-button setup-nav;
yellow lock-card pattern across mutating Manage pages; pastel-tinted
per-instrument cards; `.field-builder` half-card layout for Display +
Response Fields; multi-instrument data layer (`Instrument.session_id`,
`Instrument.order`, `create_instrument` / `delete_instrument` services
+ routes + audit events) shipped behind a disabled UI gate.

**Unfinished items.**

- **Multi-instrument operator UI enable** — flagged at the time as
  `[tracked-uf #18]`; ✅ shipped 2026-05-02 in 10D Slice 5.
- **Display Fields persistence on the placeholder rows** —
  `[tracked-uf #13]` / `[tracked-uf #14]`; ✅ shipped 2026-05-01.

### Segment 10D — Instruments page rebuild + multi-instrument enable

**Delivered.** Slices 1–5: state-machine-driven Display + Response
Fields tables (URL-driven `?editing={iid}` Save / Cancel / Edit), Help
textarea + Show checkbox, Response Type Definitions table (10 seeded
RTDs + operator-add/edit/delete with cascade UX), mutual-exclusion
edit lock, multi-instrument enable (Add + Delete with confirm).

**Unfinished items.**

- **Sort-column UX for response / display fields** — `[unfiled]`.
  The 10D plan flagged this with "semantics ('default row order on
  reviewer surface') not yet decided" and didn't make the cut. Low
  priority and not blocking; surface here so a future instruments-page
  touch knows the prior decision lapsed.

The cross-cutting cleanups that 10D spawned (`#19` chrome rollout,
`#20` Operations Pages chrome, `#21` UI consistency, `#22` Home
rebuild, `#15` 10C backfill tests) are separately tracked in
`unfinished_business.md` and `todo_master.md`.

---

## Recommendations

1. **Promote the 7 `[unfiled]` items to either `unfinished_business.md`
   or `docs/status.md` "What's deliberately not yet there"** —
   whichever is the better home. AG Grid (#1), vanilla-JS autosave
   (#2), and queue-based send (#3) probably belong in the status.md
   deferred-items table with named target segments. Operator-side
   inactive-status UI (#4), inline-edit rows (#5), and sort-column
   UX (#6) probably belong in `unfinished_business.md` since they're
   real candidate work.
2. **Decide AG Grid's actual fate.** The workplan called it the
   second half of Segment 8 in plain English. Either fold it back
   into a future segment plan or update the workplan + status.md to
   make "plain HTML table is the design" explicit.
3. **Define the "help contact" merge field's source** before the
   email template editor lands. Per-session field on `ReviewSession`?
   Per-operator on `User`? Global env var? Decision needed before
   the editor work starts. **Update 2026-05-03:** the editor is now
   tracked as `unfinished_business.md` #24 (no longer auto-deferred
   to Segment 15); the help-contact decision is folded into it as
   the prerequisite open question.
