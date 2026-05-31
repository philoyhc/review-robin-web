# Participant-model upgrade

**Standing guidance for Review Robin's planned evolution beyond
the MVP** — from the current operator-and-reviewer review
*platform* into a generalized **participant** system where
reviewees and observers are first-class participants too, and
where response visibility is explicit, governed data.

This is the umbrella document for the post-MVP arc. It is **not**
a segment plan and carries no PR ladder: fine-grained
implementation plans (`segment_21_*.md`, `segment_22_*.md`, …)
are written when specific work is scheduled. Nothing is
scheduled yet — this doc records the design direction so it is
not foreclosed and so the eventual segments share a foundation.

## Roadmap numbering

A convention for how the project's work is numbered:

- **Segments 1–20** — the MVP of the *current* review-platform
  model (operator configures, reviewer responds). Tracked in
  `guide/todo_master.md`, which covers this MVP band **only**.
- **Segments 21–30 (and beyond)** — the **participant-model
  upgrade** described here. Deliberately **not** tracked in
  `todo_master.md`; a dedicated todo file is started if and
  when this work begins. Each future segment gets its own
  `segment_2X_*.md` plan when it is scoped.

---

## 1. The shift

Today the model assumes Review Robin is primarily a tool for
**operators** to run reviews and **reviewers** to complete them.
A reviewee is a passive row in `reviewees` — assigned, scored,
never a participant. Responses are visible to the operator and,
trivially, to the reviewer who wrote them. Nothing else.

The participant-model upgrade turns this into a **generalized
participant system**:

- **Reviewers, reviewees, and observers are all participants
  with a surface.** One signed-in person may, across their
  sessions and rows, be a reviewer (gets review *forms* to
  fill), a reviewee (gets *collations of reviews* about them),
  and/or an **observer** — a new audience category who views
  collations without being a reviewer or reviewee (a committee
  chair, a department head, an HR partner).
- **Response visibility is explicit, governed data.** For each
  response, the system can answer: *which audiences may view
  it, and in what form* — identified vs de-identified, per-line
  vs summarized.
- **The session has a schedule.** The operator sets, in
  advance, when the session opens for responses, when it
  closes, and when (and for how long) collected responses
  become viewable by the audiences eligible to see them.

The current generation model — assignment rows produced from
reviewers × reviewees × relationships by a per-instrument rule —
**stays**. This work *enhances* it; it does not replace it.

## 2. What stays, what is new

**Stays — eligibility is already solved.** "Who are the
eligible reviewers / reviewees for this instrument, filtered by
tags and pair-context" is exactly what the per-instrument
`RuleSet` + rule engine already does: reviewer-tag, reviewee-tag,
and `pair_context.tag_N` predicates are all existing rule
grammar (`app/services/rules/`), and each instrument already
pins its own rule (`instruments.rule_set_id`). The upgrade needs
**no new structure for eligibility** — it builds on the rule
engine as-is.

**New — things the current model cannot express:**

1. **A response-visibility policy** — per instrument, which
   audiences may view the responses and in what form.
2. **A session schedule** — open / close / results-availability
   windows.
3. **Observers** — they do not exist at all today.
   (Reviewee identity needs no new structure — see §3.2.)
4. **Magic-link participation** — an in-scope optional auth
   affordance for all three participant audiences (§4).

## 3. New data structures

The core of the design. Five additions; all follow the
established additive-migration playbook (13D / 13E / 13F) —
nullable / defaulted columns and new tables that ship **inert**,
each lit up by its owning slice. Reviewee identity (§3.2)
needs no schema change — only a helper. The friendly-label
retirement (§3.7) is a removal that lands in the same band.

### 3.1 `observers` — the new participant roster

A per-session roster, parallel to `reviewers` and `reviewees`.

```
observers
  id              PK
  session_id      FK -> sessions.id        (indexed, NOT NULL)
  email           String(320)  NOT NULL    (a reachable identity)
  display_name    String        NULL
  status          String(16)   NOT NULL    'active' | 'inactive'
  tag_1           String        NULL       (filter slot for visibility scoping;
                                             see "tags" note below)
  created_at / updated_at
  UNIQUE (session_id, email)
```

Mirrors the `reviewers` shape deliberately so the importer,
the Setup-page table, the friendly-label resolver, and the
sort primitive all extend with no new patterns. Observers
carry **one tag** so they can be categorized — the
per-instrument visibility policy (§3.3) can scope an observer
viewing-grant to a tag, so only observers of a given category
see a given instrument's responses.

**Why one tag, not three.** Observer use cases today are
single-axis ("committee" / "hr_partner" / "department_head")
and don't need the multi-axis predicates the reviewer / pair
tag slots support. One tag is the starting shape;
cross-cutting observer-visibility filters are deferred and
**additive if a real case appears** — add `tag_2` / `tag_3`
later, mirror the reviewer pattern. The column name `tag_1`
(rather than `tag`) is kept on purpose so that future
expansion is a pure addition rather than a rename.

### 3.2 Reviewee identity — `email_or_identifier` is enough

`reviewees.email_or_identifier` already covers every case the
participant model needs — **no schema change required**:

- Reviewers always have a valid email (`reviewers.email`).
- If a reviewee is the same human as a reviewer, the same
  identity carries across both rosters; there's no plausible
  case where the same person has an email under one role but
  not the other.
- So `email_or_identifier` *being a valid email* is exactly
  the condition for "this reviewee can authenticate to a
  `/results` surface." A reviewee whose value is a non-email
  identifier has no inbox to authenticate against — the
  confidential / unaware-reviewee use case continues to work
  by construction.

What the participant model adds is a single helper —
`is_email_identified(reviewee)` (an email-format check on
`email_or_identifier`) — used by `require_reviewee_in_session`
(§4) as the surface-gating predicate. No new column on
`reviewees`, no new column on `reviewers`, no rename.

Observers are different: an observer's identity *is* the
visibility grant, so `observers.email` is required and
auth-bearing (§3.1).

**Self-review matching** continues to compare
`reviewer.email` against `reviewee.email_or_identifier`
case-insensitively, unchanged from today.

### 3.3 `instrument_view_policies` — who sees responses, how

The heart of the visibility model. **Visibility is handled at
the instrument level**: each instrument specifies who may see
its responses and in what form. The operator authors the policy
**per instrument**; the resolver applies it **per response** at
view time (no materialization — see §3.6).

```
instrument_view_policies
  id              PK
  instrument_id   FK -> instruments.id    (indexed, NOT NULL)
  audience        String(16)  NOT NULL    'reviewee' | 'peer_reviewer' | 'observer'
  enabled         Boolean     NOT NULL    default FALSE
  granularity     String(16)  NOT NULL    'per_line' | 'summarized'
  identification  String(16)  NOT NULL    'identified' | 'deidentified'
  observer_tag    String        NULL      (observer audience only — restrict the
                                           grant to observers carrying this tag;
                                           NULL = all observers on the session)
  UNIQUE (instrument_id, audience)
```

Up to three rows per instrument — one per configurable
audience:

- **`reviewee`** — may the person being reviewed see the
  feedback collected about them on this instrument?
- **`peer_reviewer`** — may a reviewer see *other* reviewers'
  responses about the same reviewee on this instrument? (Their
  own submission is always theirs; this governs peers.)
- **`observer`** — may session observers see this instrument's
  responses? Optionally **tag-scoped** via `observer_tag`, so
  only a category of observers (e.g. tag = `committee`) sees
  it. This mirrors how eligible reviewers / reviewees are
  tag-filtered for *assignment* — here the same idea governs
  observer *viewing*. (Exact match shape — which tag slot,
  multi-tag — is a slice-scoping detail.)

The **operator** is not a row: the operator always sees
everything, identified and per-line. That is the baseline, not
a policy.

Two orthogonal **form** axes per grant:

- `granularity` — `per_line` (each reviewer's response shown as
  its own row) or `summarized` (aggregated — see §7).
- `identification` — `identified` (the responding reviewer's
  name is shown) or `deidentified` (responses shown without
  attribution).

This subsumes any "confidential instrument" flag: a
*confidential* instrument is simply one whose `reviewee` policy
row is `enabled = FALSE`. Confidentiality is the absence of a
viewing grant.

Default on instrument create: all three audiences `enabled =
FALSE` (today's behaviour — operator-only). The operator opts
each audience in deliberately.

**Reviewee-reachability warning (validation pass, not the Band 3
editor).** The Band 3 visibility editor stays roster-unaware —
it lets the operator author *which audience and what form*
without forcing them to also reason about roster realities.
The cross-cutting check that *N reviewees on this session
can't authenticate* belongs on the **Validate page** as a
soft warning, not on the per-instrument card:

> If any instrument on the session has `reviewee` visibility
> enabled **and** any reviewee on the session is not
> email-identified (`is_email_identified(reviewee)` is false —
> §3.2), surface:
>
> *"`<N>` of `<total>` reviewees have no email identification
> and will not be able to view results. Affected
> instruments: …"*

It's a warning, not an error — the confidential-subject case
is by design, and the operator may deliberately enable a
policy that only the email-identified subset of reviewees can
use. One pass over the session's reviewees at validate-time;
no materialization. **Observers need a separate treatment**
— observer reachability is a different problem (every observer
must have an email by §3.1, so the failure mode is roster
import / cleanup, not a policy-vs-roster mismatch) and is
spec'd when the observer surface lands.

### 3.4 Session schedule columns

Four timestamps on `sessions`, all nullable (NULL = "no
scheduled transition; operator drives it manually," i.e. today's
behaviour):

```
sessions
  + opens_at           DateTime(tz)  NULL   reviewer responding starts
  + responses_close_at DateTime(tz)  NULL   reviewer responding stops
  + results_open_at    DateTime(tz)  NULL   collations become viewable
  + results_close_at   DateTime(tz)  NULL   collations stop being viewable
```

Notes and open points:

- `responses_close_at` and the existing `deadline` overlap.
  Decide whether `responses_close_at` *is* `deadline` reused, or
  a distinct hard gate with `deadline` staying advisory.
  Leaning: reuse `deadline` as the hard close — fewer columns,
  and the lazy-close deadline machinery already exists.
- `opens_at` overlaps **Segment 18G**'s scheduled activation
  (a timed `validated → ready` flip — Activation is the open
  event; there is no separate "opening gate"). The upgrade
  should *consume* 18G's scheduler, not build a second one
  (see §8).
- The viewing window (`results_open_at` / `results_close_at`)
  is genuinely new — nothing today gates *viewing* by time.

If per-instrument viewing windows turn out to be needed (one
instrument's results released earlier than another's), these
move to a per-instrument table — flagged as an open question
(§9), not built up front.

### 3.5 Audit events

New emitters, registered in `audit.EVENT_SCHEMAS` per the 11K
canonical-envelope convention:

- `instrument.view_policy_set` — operator changes a visibility
  grant (changes envelope).
- `session.schedule_set` — operator sets / clears a schedule
  window.
- `observer.added` / `observer.removed` / `observer.bulk_*` —
  mirror the `reviewer.*` family.
- `results.released` — the first moment a collation becomes
  viewable for a session (snapshot envelope).
- `results.acknowledged` — a reviewee marks their results seen
  (§6).
- `session.feature_toggled` — operator flips
  `relationships_enabled` or `observers_enabled` (§3.8; changes
  envelope; carries which flag and its old / new value).

### 3.6 What does *not* get a new structure

- **Assignment rows.** Visibility is *derived* at view time
  from `instrument_view_policies` joined through the row's
  `instrument_id` — not stamped onto `assignments`. This keeps
  the row model lean and avoids materialization staleness when
  the operator edits a policy. The extension point if per-row
  variance is ever required (one reviewee opts out of an
  otherwise-shared instrument) is a small
  `assignment_view_overrides` table; deliberately deferred
  until a real case demands it.
- **A `participants` identity table.** The unified
  participant surface (§5) is a *query* over the existing
  identity spine — `users.email` matched against
  `reviewers.email` / `reviewees.email_or_identifier` /
  `observers.email` — not a new table. A reviewee whose
  `email_or_identifier` is a non-email identifier simply
  never matches a `users.email` row, which is exactly the
  desired "no surface" outcome. Operators and reviewers
  already get a `users` row on first Easy Auth sign-in;
  reviewees and observers join that spine through their email
  columns.

### 3.7 Friendly-label retirement for fixed columns

Beta feedback: the friendly-label affordance on the Reviewer /
Reviewee **Name**, **Email**, **Identifier**, and **Profile**
columns is redundant — those columns mean what they say, and
operators renaming them adds no signal. The
actively-used friendly labels are the **tag columns** (`tag_1`
/ `tag_2` / `tag_3`), which name domain categories the
operator brings (e.g. "Department", "Cohort").

The cleanup, scoped to land alongside the §3.2 split rather
than as a standalone refactor:

- Narrow the friendly-label feature to the tag columns only.
- Stop rendering the rename affordance for fixed columns on
  the Setup-Reviewers / Setup-Reviewees pages.
- Persisted custom labels for those columns are dropped on
  the migration — they were redundant; no data loss in any
  meaningful sense.

**Before retiring**: verify no CSV-import column-mapping
flow recognises operator import headers via the friendly
label of Name / Email / Identifier / Profile. If headers
match on canonical names only, retirement is purely UI
cleanup. If they match on friendly labels, the import side
has to switch to canonical matching first.

### 3.8 Per-session feature toggles — Relationships, Observers

Two boolean columns on `sessions`, both default `FALSE`:

```
sessions
  + relationships_enabled  Boolean  NOT NULL  default FALSE
  + observers_enabled      Boolean  NOT NULL  default FALSE
```

These drive what appears in the operator Setup nav. The core
tabs — Reviewers, Reviewees, Instruments, Assignments,
Settings — stay always-on; they're the minimum to run a
session end to end. Relationships and Observers are
**conditional**, gated by these two columns. The togglable
set is deliberately closed (see §11).

**Authoring.** A small card with two checkboxes appears on:

- the **New Session** creation form, and
- the **Session Settings / Edit Details** page.

Default-unchecked. Checking either flag exposes the
corresponding Setup tab and the corresponding Quick Setup
slot (see below).

**Lock-on-data.** Once at least one row exists in the
relevant roster (any row in `relationships` for the session →
Relationships flag locked; any row in `observers` → Observers
flag locked), the checkbox is disabled with a tooltip:
*"Has configured data — delete all rows to disable."* This
prevents accidental hiding of data the operator already
invested in. To re-disable, the operator must explicitly
empty the roster first.

**Route guards.** When a flag is `FALSE`, GET / POST routes
under `/operator/sessions/{id}/setup/relationships` (or
`/setup/observers`) return **404**. A deep link to a disabled
tab is genuinely not there — cleaner than a redirect.

**Quick Setup integration.** The Quick Setup card on Session
Home surfaces an Observer slot when `observers_enabled =
TRUE` — same paste-roster shape as the Reviewer slot,
matching the lock-on-nav behavior documented in
`spec/quick_setup_card_spec.md`. Relationships does *not*
get a Quick Setup slot — relationships authoring is heavier
than the paste-roster shape supports; it stays
tab-only.

**Extract Setup integration.** Observer-related extract
shapes (at minimum, observer roster CSV) become selectable on
the Extract Setup card when `observers_enabled = TRUE`. The
reviewer / reviewee shapes are always present, unchanged.

**Migration backfill.** Sessions with existing relationship
rows get `relationships_enabled = TRUE` on migration so the
tab doesn't disappear on existing operators. Observers have
no backfill — the column ships inert; no rows exist yet
anywhere.

## 4. Auth posture & magic links

Per `spec/audience_and_identity_model.md` the standing posture
is **institutional SSO (Easy Auth) by default**. The
participant-model upgrade holds that as the default and adds
**magic links as an in-scope, optional affordance** for all
three participant audiences:

- **Magic links are in scope** — an operator may issue a
  magic-link invitation to a reviewer, a reviewee, or an
  observer as an alternative entry path, chosen per session (or
  per participant). They suit external participants without an
  institutional identity — an outside panellist, a job
  candidate in a 360, a partner-institution observer.
- A magic link still **authenticates** (it proves possession of
  the email account); it does **not** bypass identity. The
  "tokenized link replaces auth" pattern remains rejected. The
  existing `invitations` tokened-landing machinery (built for
  reviewers) is the foundation — the upgrade extends it to
  reviewees and observers and surfaces it as a first-class,
  operator-selectable affordance rather than an undocumented
  fallback.
- Reviewee and observer surfaces otherwise gate on Easy Auth
  identity matched to `reviewees.email_or_identifier`
  (when the value parses as an email — see §3.2) /
  `observers.email` case-insensitively — the mechanism
  `require_reviewer_in_session` already uses. New dependencies
  `require_reviewee_in_session` / `require_observer_in_session`
  in `app/web/deps.py`.

## 5. Surfaces

- **Reviewee results surface** at `/me/sessions/{id}/results`
  — read-only. For each instrument whose `reviewee` policy is
  enabled, renders the collation of feedback about the
  signed-in reviewee, in the policy's form (per-line/summarized
  × identified/de-identified). Nothing shows for confidential
  instruments or before `results_open_at`.
- **Observer surface** at `/me/sessions/{id}/collation` —
  read-only collation view across the instruments whose
  `observer` policy is enabled *and* whose `observer_tag` (if
  set) matches the signed-in observer's tags.
- **Unified participant landing** at `/me/` — one entry point.
  A single table lists every session the signed-in identity
  touches, across roles. Each row carries one or more **role
  pills** (Reviewer / Reviewee / Observer) tagging how the
  identity is involved in that session; the pills are
  click-targets that route to the per-role surface (reviewer
  paging at `/me/sessions/{id}/{page_n}`, reviewee results at
  `/me/sessions/{id}/results`, observer collation at
  `/me/sessions/{id}/collation`). The lobby query is the union
  `Reviewer ∪ Reviewee ∪ Observer` filtered to the signed-in
  identity (matched case-insensitively against
  `reviewers.email` / `reviewees.email_or_identifier` /
  `observers.email`) — a new helper in
  `app/services/participants.py`, since today's dashboard
  query (`app/web/routes_reviewer/_dashboard.py`) is
  reviewer-only. A 360-degree self-assessment falls out
  naturally — it is just an assignment row whose reviewer and
  reviewee are the same person (the existing
  `self_reviews_active` path), seen on the landing as a row
  carrying both Reviewer and Reviewee pills. No special
  "self-assessment" structure.

Chrome stays light and audience-local per the identity spec;
components stay universal.

### 5.1 URL shape

The participant-model headcount goes from three URL-bearing
roles (sys admin / operator / reviewer) to five (add reviewee +
observer). The decision **don't introduce `/reviewee/` or
`/observer/` URL prefixes — fold every participant role into a
meta-lobby at `/me/`** shipped 2026-05-30 via the URL remodel
slice (`guide/archive/url_remodel.md`): PR A moved the existing
`/me` JSON debug endpoint to `/auth/me`; PR B flipped the four
``routes_reviewer/`` router prefixes from `/reviewer` to `/me`
and bulk-renamed every callsite (~340 occurrences across code,
templates, tests, and spec).

The shipped layout:

- ``/me/`` — reviewer landing today; **becomes the unified
  participant lobby** (§5) when the reviewee + observer
  features ship — same URL, broadened query, role-pill column
  added to the existing table.
- ``/me/sessions/{id}/{page_n}`` — the reviewer per-page
  response surface. Unchanged.
- ``/me/sessions/{id}/summary`` — the **reviewer's**
  post-submission read-only summary, gated on full submission
  (`app/web/routes_reviewer/_summary.py`). Stays
  reviewer-only; the reviewee and observer collations get
  distinct paths (next two bullets) rather than role-branching
  this handler.
- ``/me/sessions/{id}/results`` — **new.** Reviewee
  collation surface (§5). Gated on
  `require_reviewee_in_session` and on the session's
  `results_open_at` window.
- ``/me/sessions/{id}/collation`` — **new.** Observer
  collation surface (§5). Gated on
  `require_observer_in_session` and on the session's
  `results_open_at` window.
- ``/operator/`` + ``/operator/sys-admin/`` — administrative
  surfaces, unchanged.

See ``guide/archive/url_remodel.md`` for the historical
reasoning behind the URL-shape decisions, the "why drop
``/reviewee/`` / ``/observer/``" notes, and the per-session
role-tab design.

## 6. Acknowledgement & notifications

- A reviewee may mark results **acknowledged** (seen);
  operator-visible. Either a small `result_acknowledgements`
  table `(session_id, reviewee_id, acknowledged_at)` or — if it
  stays this thin — a single nullable
  `reviewees.results_acknowledged_at` column. Lean toward the
  column.
- Reviewee / observer email surfaces ("your results are
  ready", acknowledgement nudges) ride the existing
  `email_outbox` + transport plumbing. **Hard-depends on
  Segment 14B** (email send) being live.

## 7. Summarization & de-identification

`granularity = summarized` needs aggregation logic, by response
field type:

- numeric (Integer / Decimal RTDs) — mean / distribution /
  count;
- list (single-choice RTDs) — tallies per option;
- free-text (String RTDs) — the hard one. Options: a plain
  concatenated list, or an operator-curated written summary.
  Likely operator-curated for text — flagged in §9.

`identification = deidentified` is a render-layer concern: the
collation builder omits reviewer attribution. Both axes belong
in `app/web/views/` adapters (the established view-shape seam)
plus an `app/services/collation.py` service — services compute,
views shape, templates render markup, exactly as today.

## 8. Sequencing & dependencies

- **Hard-depends on Segment 14B** for the notification half
  (§6) — without email send, results-ready notices have no
  channel.
- **Coordinates with Segment 18G** (scheduled events). 18G
  owns the scheduler that fires timed lifecycle transitions
  (auto-archive, auto-send, scheduled activation). The §3.4 windows
  must be *driven by 18G's scheduler*, not a second timer. If
  participant-model work lands before 18G, it ships the columns
  inert with a manual operator toggle; 18G (or a later slice)
  then wires the automation.
- **Naturally follows 17B** (reviewer-surface refinements) so
  the new participant surfaces inherit a settled visual
  baseline.

## 9. Open questions

Decide before any segment in this band is scoped:

1. **External-participant auth.** Magic links (§4) are the
   intended answer for participants with no institutional SSO —
   confirm that covers every external case, or scope which do
   not get a surface at all.
2. **`responses_close_at` vs `deadline`.** Reuse `deadline` as
   the hard close (recommended) or add a distinct column.
3. **Per-instrument vs per-session viewing window.** §3.4 puts
   the window on the session; confirm no instrument needs its
   own release schedule, or move to a per-instrument table.
4. **Per-row visibility override.** Is per-instrument policy
   enough, or is an `assignment_view_overrides` table needed?
5. **Free-text summarization.** Concatenated list vs
   operator-curated written summary for `summarized` text
   fields.

## 10. Candidate segment breakdown

Not a committed plan — a sketch of how the band might divide
into `segment_2X_*.md` plans once scoped. Each line is
plausibly one segment (some may split or merge):

- Schema prep — the §3 additions as inert additive migrations.
- Per-session feature toggles (§3.8) — `relationships_enabled`
  / `observers_enabled` columns, settings card on New Session
  + Session Details, lock-on-data, route guards, migration
  backfill. Ships before Observer roster so Observers slots
  into the toggle from day one.
- Observer roster — importer + Setup page (+ Quick Setup +
  Extract Setup integration per §3.8).
- Reviewee identity helper — `is_email_identified(reviewee)`
  + `require_reviewee_in_session`. No schema change (§3.2).
- Friendly-label retirement for fixed roster columns (§3.7).
- Magic-link affordance — extend the tokened-landing path to
  reviewees / observers; operator-selectable per session.
- Per-instrument visibility-policy authoring.
- Session schedule authoring + 18G integration.
- Collation service — summarization + de-identification.
- Reviewee results surface at ``/me/sessions/{id}/results``.
- Observer surface at ``/me/sessions/{id}/collation``.
- Unified participant landing — broaden the existing ``/me/``
  dashboard query to the cross-role union and add the
  role-pill column to the table; ships paired with (or after)
  the surfaces above so the pills route to live pages.
- Acknowledgement + notifications (gated on 14B).

## 11. Out of scope

- **Confidential sessions stay the default.** Every audience
  grant is opt-in (`enabled = FALSE` by default); a session
  that exposes nothing behaves exactly as today.
- **Operator-facing aggregate analytics** — cross-session
  reporting is its own concern, not a participant surface.
- **Reviewee / observer self-service roster edits** — they do
  not manage their own rows; that stays operator-only.
- **Multi-tenancy / cross-workspace identity** — unchanged.
- **The Setup-nav togglable set is closed.** Only
  Relationships and Observers are per-session optional via
  §3.8. Reviewers, Reviewees, Instruments, Assignments, and
  Settings are the minimum to run a session end to end —
  they stay always-on. Resist future "should this be optional
  too?" temptations unless a feature genuinely belongs in the
  same advanced / not-essential bucket; the goal of §3.8 is a
  closed list, not a feature-flag framework.
- **Excel / `.xlsx` import-export.** Considered and set aside.
  CSV stays the interchange format throughout; when several
  files must travel together they go in a zip container (the
  existing `{code}_bundle.zip` pattern from Segment 18D). A
  multi-worksheet workbook would carry more structure but is
  not worth the new dependency and the loss of CSV's
  diff-friendly, zero-dependency round-trip.

## 12. Related context

- **`spec/audience_and_identity_model.md`** — §3 (reviewee,
  forward-looking) and §4 (audiences). The authoritative doc on
  what adding an audience entails; update it *first* when this
  work is picked up — observers and the reviewee surface become
  live audiences §3 / §4 must then describe, and magic links
  move from "fallback" to an in-scope affordance.
- **`guide/archive/segment_18G_scheduled_events.md`** — owns the
  scheduler the §3.4 windows must ride on.
- **`guide/segment_14B_email_infrastructure.md`** — the
  notification half depends on it.
- **`spec/rule_based_assignment.md`** — the eligibility engine
  this work builds on unchanged.
- **`guide/todo_master.md`** — the roadmap; it tracks the MVP
  (segments 1–20) only. The participant-model upgrade is
  deliberately not in it — a dedicated todo file is started
  when this work begins.
