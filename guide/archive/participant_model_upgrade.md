# Participant-model upgrade

**Standing guidance for Review Robin's planned evolution beyond
the MVP** — from the current operator-and-reviewer review
*platform* into a generalized **participant** system where
reviewees and observers are first-class participants too, and
where response visibility is explicit, governed data.

This is the umbrella document for the post-MVP arc. It is **not**
a segment plan and carries no PR ladder: fine-grained
implementation plans (`segment_21_*.md`, `segment_22_*.md`, …)
are written when specific work is scheduled. The phase-by-phase
S / P / W identifier glossary lives in **Appendix A** at the
foot of this doc; outstanding items live in
`guide/participant_model_remainder.md`. The participant-model
work is otherwise pulled into `guide/todo_master.md` under Done
as each slice ships.

## Status snapshot

Prep work has been landing ahead of any named segment. As of
2026-06-01:

- **Design** locked across §§3.1, 3.2, 3.3, 3.5, 3.7, 3.8, 3.9,
  4, 5 (PRs #1671 → #1677).
- **Phase 1 schema + audit allowlist** shipped (PR #1678) —
  every ✓ row in Appendix A's Phase 1 table.
- **Phase 1 dead-code helpers + dependency stubs** shipped
  (PR #1679) — W1 / W2 / W3 / W4 callable, no consumers yet.
- **§3.7 friendly-label retirement** + **§3.9 partial** (Quick
  Setup + Extract for Reviewer PhotoLink) shipped (PR #1680).
- **§5 unified `/me/` lobby** shipped — cross-role union
  query + role pills folded into the Session cell + role-aware
  reachability-gated links + role-navigator chip strip on
  every role-specific surface (PRs #1684, #1709, #1712, #1714,
  #1715).
- **§3.8 per-session feature toggles wired end-to-end** —
  Session Settings + New Session card with the two checkboxes,
  Setup-nav gating, 404 route guards, lock-on-data, and the
  Quick Setup new-session side (PRs #1685, #1686, #1705);
  follow-on polish across PRs #1687 → #1703.
- **§3.1 Observer roster CSV importer + Setup page CRUD**
  shipped (W10 / PR #1706) — the observer roster is a
  first-class Setup page; Quick Setup slot (W12 / #1754) and
  Extract Setup row + bundle inclusion (W13 / #1755) closed
  the round-trip end-to-end.
- **§5 reviewee + observer placeholder surfaces** shipped
  (PR #1713) — `/me/sessions/{id}/results` +
  `/me/sessions/{id}/collation` render the reviewer-surface
  chrome with the standard description card; real bodies
  land with W16 / W17.
- **§3.4 release-window authoring (W14)** shipped (PR #1716)
  + reshape to absolute close datetime (S12 / Alembic
  `f4a92b3c6d18`) — `responses_release_at` +
  `responses_release_until` ride end-to-end through the
  Edit / Create form and Settings-CSV; the Release-now /
  Stop-release Operations buttons + their audit events are
  the only piece of the release-window story still pending.
- **§3.3 Band 3 visibility-policy editor** shipped (W15
  persistence + S14 per-window mode pairs) — Alembic
  `a7e3b1d92c64` (expand, four pair columns) + PR #1730
  (service / view / route / template flip onto the new
  columns + per-window-axis 3 × 2 chip grid) + Alembic
  `b8f4c2a91d35` (contract; legacy `enabled` /
  `granularity` / `identification` / `visible_when`
  quadruple dropped). Operator card-level Save now persists
  the visibility table (PR #1733 retired the standalone
  `/view-policy` POST; hidden inputs ride
  `form="dfsave-<id>"` and the chip click fires the dirty
  tracker per PR #1734).
- **§3.3 reviewer-surface transparency card** shipped
  (PR #1732) — read-only "Who can see what you wrote (other
  than admin)" card lands in the per-instrument intro grid
  on the reviewer surface, mirroring the operator's policy
  for two non-admin audiences (You / Reviewees). PR #1733
  adds the matching preview alongside the description card
  in the operator's Band 2 intro grid; PR #1734 renames the
  ``summarized`` mode's display label to "Anonymized
  summaries" everywhere it surfaces.
- **§5 reviewee `/results` body — all three visibility modes**
  shipped (W16 / PRs #1737 → #1749) — raw + anonymized +
  summarized aggregates (median / min / max for numerical,
  per-choice frequency + percentage for List, total + average
  character length for String).
- **§6 Acknowledge gesture** shipped (W19 / PR #1750) —
  bottom Acknowledge card on `/me/sessions/{id}/results` with
  checkbox-gated button, post-ack pill, idempotent POST,
  `reviewee.results_acknowledged` audit event.
- **§3.3 reviewee-reachability soft warning** on the Validate
  page shipped (W8 / PR #1758) — `reviewees.unreachable_for_results`
  rule (severity = warning, non-blocking) flags active
  reviewees whose `email_or_identifier` isn't a deliverable
  email, since the `/results` surface needs email auth.
- **§3.9 reviewer `profile_link` affordance** shipped (W11 /
  PR #1680 + #1756). The column on the model, CSV round-trip,
  Setup-page form / preview, and friendly label all mirror
  the reviewee treatment. Where else to surface the link
  (e.g. as a display-fields source for the reviewee `/results`
  identity column, or on the operator's reviewer-detail
  surface) is left as a future design call — the affordance
  is the deliverable; placement is decided when a specific
  surface needs it.
- **§7 observer `/collation` body** still pending (W17, with
  the supporting service module W5 bundled).

Outstanding items track in `guide/participant_model_remainder.md`.
Appendix A at the foot of this doc carries the full S / P / W
identifier glossary with per-item status + PR pointers.

## Roadmap numbering

A convention for how the project's work is numbered:

- **Segments 1–20** — the MVP of the *current* review-platform
  model (operator configures, reviewer responds). Tracked in
  `guide/todo_master.md`.
- **Participants Model Prep** — the inert schema, dead-code
  helpers, and small standalone retirements / parity gaps that
  ship ahead of any named segment. Tracked in `todo_master.md`'s
  Done section.
- **Segments 21–30 (and beyond)** — the **participant-model
  upgrade** surface slices (Phases 2 / 3 of the prep audit).
  Not yet scheduled; a dedicated todo file is started if and
  when that work begins. Each future segment gets its own
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

The core of the design. Six additions; all follow the
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
  id                              PK
  instrument_id                   FK -> instruments.id    (indexed, NOT NULL)
  audience                        String(16)  NOT NULL    'reviewee' | 'peer_reviewer' | 'observer'
  while_ongoing_granularity       String(16)    NULL      'row' | 'aggregated' | NULL
  while_ongoing_identification    String(16)    NULL      'identified' | 'deidentified' | NULL
  after_release_granularity       String(16)    NULL      'row' | 'aggregated' | NULL
  after_release_identification    String(16)    NULL      'identified' | 'deidentified' | NULL
  observer_tag                    String        NULL      (observer audience only — restrict the
                                                           grant to observers carrying this tag;
                                                           NULL = all observers on the session)
  UNIQUE (instrument_id, audience)
```

Each per-window `(granularity, identification)` pair encodes the
audience's mode in that window. **Both members NULL ≡ "off in
this window"**; the audience can't view this instrument during
that window. A row with both windows off is the explicit "this
audience cannot view this instrument in any form" state; a
missing row reads identically. `(aggregated, identified)` is
reserved-incoherent and rejected by the service.

The original `enabled` / `granularity` / `identification` /
`visible_when` quadruple shipped with Phase 1 and retired with
S14's contract step (Alembic `b8f4c2a91d35`) once the per-window
pairs carried the operator's intent end-to-end. See
`spec/visibility_policy.md` for the full functional contract.

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

**Audience scope — what rows each row's grant covers.** The
audience tells *who* can see; the audience's identity also
implies *which* responses they can see. The resolver enforces
the scope rule alongside the policy lookup:

| Audience | Scope of "responses they may see" |
|---|---|
| `peer_reviewer` (reviewer viewing own work) | The reviewer's **own** submitted responses on this instrument — never any other reviewer's. Useful for letting reviewers re-read their own work post-submit / across pages. The schema name `peer_reviewer` is historical; today the grant covers self-view only. |
| `reviewee` | Responses **about this reviewee** — or about a group this reviewee is a member of, for group-scoped instruments. Never about another reviewee or another group. The Reviewee surface filters at view time: a reviewee only sees rows whose `Assignment.reviewee_id` (or group containment) matches their identity. |
| `observer` | All responses about all reviewees, on instruments this observer is granted (subject to `observer_tag`). No self-scope. Observers are the only audience whose grant is cross-cohort. |

These rules are not stored on `instrument_view_policies` —
they are properties of the audience itself, applied by the
resolver. The schema's job is to record which audiences are
enabled, in what form, and during which window; *scope* is
intrinsic.

**Scope of the visibility policy — strictly per-pair flow.**
The visibility policy governs **the information flow from
reviewers to the reviewees they are reviewing** (and the
mirrors of that flow back to the reviewer themselves and out
to the relevant observers). It is deliberately **not** a
mechanism for surfacing cross-cohort summaries — e.g.
"every reviewer sees the cohort-wide average of every
instrument, anonymised". Those use cases can come up and are
worth supporting later, but they belong to a separate
mechanism — an **Operator- or Observer-published report**
that someone with cohort-wide standing explicitly makes
available to one or more audiences. Keeping the two
mechanisms separate avoids loading the per-instrument
audience policy with cohort-aggregate semantics it isn't
shaped for (e.g. a reviewer who reviewed only Alice would
otherwise need to see "summarised across all reviewees" they
have no pairwise connection to). The pairwise flow is small,
local, and the resolver can be implemented cleanly against
each (reviewer, reviewee) edge; cohort-aggregate publication
is a separate slice if and when it lands.

As a corollary, the **Reviewer scope is strictly self-only**
in the policy table: a reviewer's grant covers only the
responses they themselves keyed in. A future operator-level
"Self only / All peers" toggle (a `peer_scope` column) is
sketched as **S13** in Appendix A — parked, not actively in
design, because the same use case
might be served by an Operator- or Observer-published report
instead.

**Reviewer post-release modes.** During the session
(`while_ongoing`) the reviewer is locked at Raw (the baseline
self-view guarantee — they keep visibility of what they wrote
while the review is in flight). After release
(`after_release`) the operator picks one of three modes for
the Reviewer row: ``—`` (off; default — today's behaviour),
``Raw`` (keep showing the reviewer their own submissions
read-only — no recall / resubmit), or ``Anonymized summaries``
(an aggregate across the reviewees the reviewer reviewed on
this instrument; useful when the reviewer reviewed multiple
people and the operator wants to give the reviewer a sense of
the shape of their own contribution without exposing
individual rows back). ``Anonymized`` (row + deidentified) is
deliberately **not** offered for Reviewer — anonymising one's
own work against oneself is incoherent.

Three orthogonal axes per grant — two **form** axes (what the
audience sees) plus one **window** axis (when):

- `granularity` — `row` (each reviewer's response shown as its
  own line) or `aggregated` (summarised — see §7). `NULL` ≡
  "off in this window".
- `identification` — `identified` (the responding reviewer's
  name is shown) or `deidentified` (responses shown without
  attribution). `NULL` ≡ "off in this window".

The two form axes are not all four combinations open — only
three modes are coherent for a participant audience:

| Operator-facing mode | granularity | identification |
|---|---|---|
| Raw | `row` | `identified` |
| Anonymized | `row` | `deidentified` |
| Summarized | `aggregated` | `deidentified` |
| (off this window) | `NULL` | `NULL` |

`aggregated` + `identified` is incoherent ("average Alice"
isn't a thing); the service rejects it. The Band 3 editor
presents three named modes; the encoder maps each onto the
two columns.

**Visibility windows.** Each policy row carries two per-window
pair slots (`while_ongoing_*` + `after_release_*`); the
operator picks a mode per window cell. Setting both windows to
the same mode is the operator-facing "Throughout" shape.
`always` is reserved for the operator (who isn't an audience
row — see paragraph above) and has no schema slot today.

| Window | Drawn from |
|---|---|
| `while_ongoing` | `[sessions.activated_at, sessions.deadline)` — session lifecycle, the same window the reviewer surface stays reachable in. |
| `after_release` | `[sessions.responses_release_at, sessions.responses_release_until)` — the Release-responses window authored on Session Edit Details / Create New Session. Originally W14 (PR #1716) wired `release_until_offset` here; S12 retires the offset in favour of an absolute `responses_release_until` datetime that the form input and the Stop button share. |

**Operator buttons for the After-release window.** The
`after_release` window is bracketed by two datetime columns on
`sessions`: `responses_release_at` (start) and
`responses_release_until` (end; `NULL` ⇒ open-ended). Either
can be driven from the Edit / Create form **or** from two
session-level Operations buttons that overwrite the schedule:

- **Release responses now** — stamps `responses_release_at =
  now()` and clears any prior `responses_release_until` so the
  window re-opens open-ended. Emits `session.responses_released`
  audit (snapshot).
- **Stop release** — stamps `responses_release_until = now()`.
  Emits `session.responses_release_stopped` audit (snapshot).

Both the scheduled-close form input and the Stop button write
to the same `responses_release_until` column; the difference
between "schedule a future close" and "stop now" is just the
audit event the writer emits, not which column is touched.

View-time predicate, used by the resolver for the
`after_release` window:

> *Release window is open* ⇔ `responses_release_at IS NOT NULL`
> AND `now() ≥ responses_release_at` AND
> (`responses_release_until IS NULL` OR `now() <
> responses_release_until`).

**Archive forces zero visibility.** When `sessions.status =
'archived'`, the resolver treats every per-window pair as
`(NULL, NULL)` for every non-operator audience. No schema
change — pure view-time gate, mirrors how archive retires a
session out of reviewer reach today.

This subsumes any "confidential instrument" flag: a
*confidential* instrument is simply one whose `reviewee` policy
row has both windows off. Confidentiality is the absence of a
viewing grant.

Default on instrument create: no policy rows. The resolver
treats a missing row as "off in both windows" for that
audience — instrument invisible to it — which matches
today's operator-only behaviour. The operator opts each
audience in deliberately on the Band 3 editor (and the
matching reviewer-surface transparency card / Band 2 preview
re-render to reflect the change on next page load).

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

**Release-window close (S12) — datetime column replaces
offset.** The original 18G shape for the release window was
anchor + ISO 8601 offset duration (`responses_release_at` +
`release_until_offset`, both wired by W14 / PR #1716). S12
retires the offset in favour of an absolute close datetime,
so the scheduled-close form input and the operator's Stop
button can write to the same column:

```
sessions
   responses_release_at           DateTime(tz)  NULL  (W14, kept)
 + responses_release_until        DateTime(tz)  NULL  (S12 — when the release
                                                       window closes; NULL =
                                                       open-ended)
 - release_until_offset           String(16)    NULL  (W14 — retired; the
                                                       offset semantics fold
                                                       into responses_release_until
                                                       via the migration)
```

Migration writes `responses_release_until = responses_release_at
+ parse_iso_duration(release_until_offset)` on any row where
both source columns are set, then drops `release_until_offset`.

**Offset-only rows (`release_until_offset IS NOT NULL` AND
`responses_release_at IS NULL`)** — these exist today because
the W14 validator
(`parse_and_validate_release_until_offset`) deliberately accepts
the offset without an anchor; the §8.2.2 anchor-null rule
treats it as inert until the anchor is later set. Under the
new absolute-datetime model the staged offset has no
translation (there is no anchor to compute the close
datetime against), so the migration **drops these offsets
silently** and leaves `responses_release_until` NULL.
Operators who had staged an offset alone must re-enter a close
datetime on the form after the migration. We accept this as a
deliberate data-clear rather than carry a vestigial column
through the cutover — exploratory offsets without an anchor
are rare in practice and don't generalise to the new shape.

Paired with the existing `responses_release_at`, this gives
the resolver one predicate that covers scheduled and
operator-driven close uniformly — see the **Visibility
windows** subsection of §3.3 for the expression. The Stop
button writes `responses_release_until = now()`; Release-now
writes `responses_release_at = now()` and clears
`responses_release_until`. Both emit dedicated audit events
(`session.responses_released` /
`session.responses_release_stopped`).

The 365-day magnitude cap that W14 enforced on the offset
moves to a soft "until must be within 365 days of
`responses_release_at`" check on the datetime path — guards
operator typos (e.g. a 2030 datetime on a 2026 session)
without losing the bound.

### 3.5 Audit events

New emitters, registered in `audit.EVENT_SCHEMAS` per the 11K
canonical-envelope convention:

- `instrument.view_policy_set` — operator changes a visibility
  grant (changes envelope). Covers any axis: the four per-window
  pair columns (`while_ongoing_granularity` /
  `while_ongoing_identification` / `after_release_granularity` /
  `after_release_identification`) and `observer_tag`.
- `session.schedule_set` — operator sets / clears a schedule
  window.
- `session.responses_released` (S12) — operator pressed
  Release-responses-now (snapshot envelope; carries
  `responses_release_at`; also notes if a prior
  `responses_release_until` was cleared by the press).
- `session.responses_release_stopped` (S12) — operator pressed
  Stop-release (snapshot envelope; carries
  `responses_release_until`, which the button has just
  stamped to `now()`).
- `observer.created` / `observer.updated` /
  `observer.bulk_inactivated` / `observer.bulk_reactivated` /
  `observers.imported` / `observers.deleted_all` — mirror the
  `reviewer.*` family. Shipped by W10 (PR #1706) alongside the
  CRUD service.
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

### 3.9 Reviewer `profile_link` parity

Today, `reviewees` carry a `profile_link` (a free-form URL,
rendered as a clickable link wherever the reviewee surfaces);
`reviewers` do not. §3.7 already implicitly assumed parity
when it spoke of retiring the friendly-label affordance for
the "Reviewer / Reviewee … Profile columns" — close the gap
by mirroring the column onto the reviewer side.

```
reviewers
  + profile_link  String(2000)  NULL    (matches reviewees.profile_link)
```

**Pre-position vs slice work.** The column itself
pre-positions cleanly as an inert nullable addition. The
surrounding surface mirror is non-trivial — `profile_link`
already touches roughly twelve files for reviewees:

- `app/services/reviewers.py` (create + update normalisation,
  audit-event payloads),
- `app/schemas/imports.py` (`ReviewerImportRow`),
- `app/services/csv_imports.py` (header parse +
  `_reviewer_to_kwargs`),
- `app/services/extracts/reviewers_extract.py` (export
  header + serialisation),
- `app/web/templates/operator/session_reviewers.html`
  (visibility toggle, table cell, edit-form inputs),
- `app/web/routes_operator/_setup_reviewers.py` (form
  handlers, edit-mode prep, slot tuple),
- `app/services/session_config_io/_apply.py` (Quick Setup
  reviewer frozenset),
- `app/services/field_labels.py` (default label entry —
  `("reviewer", "profile_link"): "Profile"`),
- `app/services/instruments/_display_fields.py` (label map,
  CSV name map, `ALLOWED_SOURCES`, seeding logic),
- `app/web/views/_setup.py` (CSV-header → field mapping),
- plus the reviewer-surface display path
  (`app/web/views/_reviewer_summary.py` and
  `routes_reviewer/_surface.py`) — the `is_profile_link`
  cell-styling check is field-name-keyed, so it should
  pick up the reviewer column without code changes; verify
  in the slice,
- and the corresponding test files.

The implementation is "small in concept, large in surface
area" — one coordinated PR rather than many small ones. The
column add can sit inert in the prep migration; the surface
mirror is its own slice and lights up immediately on land
(there's no useful intermediate state — half-wired CSV import
or template breaks the page).

No new audit-event type required — the existing
`reviewer.created` snapshot and `reviewer.updated` changes
envelopes pick up the new field automatically.

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
2. ~~`responses_close_at` vs `deadline`.~~ **Settled** —
   `deadline` is reused as the hard close. No separate
   `responses_close_at` column ships; S4 in the prep audit
   reads as "already exists" against `sessions.deadline`.
3. **Per-instrument vs per-session viewing window.** §3.4 puts
   the window on the session; confirm no instrument needs its
   own release schedule, or move to a per-instrument table.
4. **Per-row visibility override.** Is per-instrument policy
   enough, or is an `assignment_view_overrides` table needed?
5. **Free-text summarization.** Concatenated list vs
   operator-curated written summary for `summarized` text
   fields. (The reviewer-facing display label is now
   "Anonymized summaries" per PR #1734 — the underlying
   computation still has to be picked.)

## 10. Candidate segment breakdown

Not a committed plan — a sketch of how the band might divide
into `segment_2X_*.md` plans once scoped. Each line is
plausibly one segment (some may split or merge); the ones
that ended up shipping as named PRs rather than as a segment
are marked.

- ✓ Schema prep — the §3 additions as inert additive
  migrations (Phase 1 / #1678).
- ✓ Per-session feature toggles (§3.8) — `relationships_enabled`
  / `observers_enabled` columns + Settings + New Session card
  + lock-on-data + route guards (PRs #1685, #1686, #1705).
- ✓ Observer roster — importer + Setup page (W10 / PR #1706).
  Quick Setup observer slot + Extract Setup observer shapes
  still pending (L2).
- ✓ Reviewee identity helper —
  `is_email_identified(reviewee)` + `require_reviewee_in_session`
  / `require_observer_in_session` (W1 / W2 / W3 / PR #1679).
- ⚠ Reviewer `profile_link` parity (§3.9) — column add shipped
  (S11 / #1678); Quick Setup + Extract surface mirror shipped
  via #1680; the rest of the ~12-file mirror (services / Setup
  page / display fields / etc.) is still W11's remainder.
- ✓ Friendly-label retirement for fixed roster columns
  (§3.7 / W9 / PR #1680).
- ✘ Magic-link affordance — blocked on the `invitations`
  extensibility design call (W21).
- ✓ Per-instrument visibility-policy authoring (W15 + S12 +
  S14) — Alembic `f4a92b3c6d18` (S12 window axis +
  responses_release_until), `a7e3b1d92c64` (S14 expand),
  `b8f4c2a91d35` (S14 contract); plus PRs #1656 (placeholder),
  #1730 (read-path swap), #1732 (reviewer transparency card),
  #1733 (card-Save consolidation + Band 2 preview), #1734
  (chip-click dirty + "Anonymized summaries" rename).
- ✓ Session schedule authoring + 18G integration — W14 (PR
  #1716) for `responses_release_at` + `responses_release_until`;
  Release-now / Stop-release Operations buttons pending.
- ✘ Collation service — summarization + de-identification.
- ✘ Reviewee results surface at ``/me/sessions/{id}/results``
  (W16) — placeholder chrome shipped (P5 / PR #1713); body
  pending.
- ✘ Observer surface at ``/me/sessions/{id}/collation``
  (W17) — placeholder chrome shipped (P6 / PR #1713); body
  pending.
- ✓ Unified participant landing — `/me/` cross-role union +
  role pills + role-aware links + role-navigator chip strip
  (W18 / PRs #1684, #1709, #1712, #1714, #1715). Helper
  consolidation in `participants.sessions_for_user` is a
  cleanup follow-up (L1).
- ✘ Acknowledgement + notifications (W19 / W20; gated on
  Segment 14B).

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
- **`guide/todo_master.md`** — the roadmap. Tracks both the MVP
  (segments 1–20) and every shipped participant-model slice
  under Done; outstanding items live in
  `guide/participant_model_remainder.md`.
- **`guide/participant_model_remainder.md`** — focused filter on
  this doc listing only the items still to ship. Refresh
  whenever a row moves out by adding the matching Done entry
  in `todo_master.md`.

---

## Appendix A — Implementation-phase identifier glossary

The participant-model design above is also the source for the
**S<N> / P<N> / W<N>** identifiers cited inline. The categorisation
classifies each change by implementation phase:

1. **Schema (S)** — additive migrations + `EVENT_SCHEMAS` rows.
2. **UI placeholders (P)** — empty surfaces establishing layout
   and navigation without functionality.
3. **Wiring & logic (W)** — services, route guards, helpers,
   business rules; lights up placeholders.

This glossary supersedes the standalone `participant_model_prep.md`
audit doc (retired 2026-06-01). The full ship trail is in
`guide/todo_master.md`'s Done section; the currently-outstanding
subset is in `guide/participant_model_remainder.md`.

### Phase 1 — Schema

| # | Change | Status |
|---|---|---|
| S1 | New `observers` table | ✓ shipped (#1678) |
| S2 | New `instrument_view_policies` table | ✓ shipped (#1678) |
| S3–S6 | Schedule columns (`scheduled_activate_at` / `deadline` / `responses_release_at` / `responses_release_until`) | ✓ pre-positioned by Segment 18G; S12 reshaped the release-window close to a datetime |
| S7 | `sessions.relationships_enabled` | ✓ shipped (#1678) |
| S8 | `sessions.observers_enabled` | ✓ shipped (#1678) |
| S9 | `reviewees.results_acknowledged_at` | ✓ shipped (#1678); lit up by W19 (#1750) |
| S10 | New event types in `EVENT_SCHEMAS` (`observer.*`, `instrument.view_policy_set`, `session.feature_toggled`, `session.responses_released` / `_release_stopped`, `reviewee.results_acknowledged`, `session.observers_extracted`) | ✓ shipped (#1678 + add-ons through #1758) |
| S11 | `reviewers.profile_link` column | ✓ shipped (#1678); surface mirror W11 |
| S12 | Visibility-window axis + release-until datetime — `instrument_view_policies.visible_when` (later retired by S14) + `sessions.responses_release_until` replacing `release_until_offset` | ✓ shipped — Alembic `f4a92b3c6d18` |
| S13 | *(parked)* `instrument_view_policies.peer_scope` | ✘ parked — see §3.3 "Scope of the visibility policy" |
| S14 | Per-window mode pairs on `instrument_view_policies` (`while_ongoing_*` / `after_release_*`); legacy `enabled` / `granularity` / `identification` / `visible_when` quadruple retired | ✓ shipped — Alembic `a7e3b1d92c64` (expand), #1730 (read-path swap), `b8f4c2a91d35` (contract) |

### Phase 2 — UI placeholders

| # | Placeholder | Status |
|---|---|---|
| P1 | Empty Observers Setup page | ✓ shipped (#1686 + polish #1687–#1692); lit up by W10 (#1706) |
| P2 | Band 3 visibility-policy card | ✓ shipped (#1656); lit up by W15 |
| P3 | Session-schedule authoring card | ✓ shipped (#1656); lit up by W14 (#1716) |
| P4 | Two-checkbox card on Session Settings + New Session | ✓ shipped (#1685 + #1705); wired by W6 |
| P5 | Empty `/me/sessions/{id}/results` page | ✓ shipped (#1713); body wired by W16 |
| P6 | Empty `/me/sessions/{id}/collation` page | ✓ shipped (#1713); body wiring pending (W17) |
| P7 | Role-pill column on `/me/` lobby | ✓ shipped (#1684, polish through #1715) |

### Phase 3 — Wiring & logic

| # | Item | Status |
|---|---|---|
| W1 | `is_email_identified(reviewee)` helper | ✓ shipped (#1679) |
| W2 | `require_reviewee_in_session` dep | ✓ shipped (#1679) |
| W3 | `require_observer_in_session` dep | ✓ shipped (#1679) |
| W4 | Cross-role query helper shape | ✓ retired with L1 (#1757) — W18 built the union inline in `_dashboard.py` |
| W5 | `app/services/collation.py` service | ✘ bundled into W17 — no useful pre-positioning |
| W6 | Per-session toggle wiring | ✓ shipped (#1685 + #1686) |
| W7 | Visibility-policy resolver | ✓ shipped alongside W15 |
| W8 | Reviewee-reachability warning on Validate | ✓ shipped (#1758) |
| W9 | Friendly-label retirement on reviewee identity slots | ✓ shipped (#1680) |
| W10 | Observer CSV importer + Setup page wiring | ✓ shipped (#1706) |
| W11 | Reviewer `profile_link` surface mirror | ✓ shipped (#1680 + #1756). The affordance is in place — column on the model, CSV round-trip, Setup-page form / preview, friendly label. Where else to surface it (display-fields seeding for the reviewee `/results` identity column, operator's reviewer-detail cell styling) is a future design call left open. |
| W12 | Quick Setup Observer slot | ✓ shipped (#1754) |
| W13 | Extract Setup observer shapes | ✓ shipped (#1755) |
| W14 | Session schedule authoring | ✓ shipped (#1716, S12 reshape after) |
| W15 | Band 3 visibility-policy editor | ✓ shipped (#1728 + #1730 + #1732–#1734) |
| W16 | Reviewee results surface body | ✓ shipped (#1737 → #1749) — raw / anonymized / summarized |
| W17 | Observer collation surface body | ✘ outstanding — see `_remainder.md` |
| W18 | Unified `/me/` lobby cross-role query | ✓ shipped (#1709, polish through #1715) |
| W19 | `Acknowledge` flow | ✓ shipped (#1750) |
| W20 | Reviewee / observer email notifications | ✘ blocked on Segment 14B |
| W21 | Magic-link landing for reviewees / observers | ✘ blocked on `invitations`-extensibility design call |
