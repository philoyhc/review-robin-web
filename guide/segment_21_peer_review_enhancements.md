# Segment 21 — Generalized audiences & response visibility

**Status:** Planned, not scheduled. Built out 2026-05-18 from
the 2026-05-16 stub after the audience model was spelled out in
more detail. Still forward-looking — "if we ever get there."

Supersedes the earlier "Peer review enhancements" stub framing.
The work is broader than a reviewee surface: it generalizes
Review Robin from an operator-and-reviewer review *platform*
into a system where **reviewees and observers are first-class
participants too**, and where **who may see a response — and in
what form — is explicit, configurable data** rather than an
implicit "only the operator and the reviewer who wrote it."

---

## 1. The shift

Today the model assumes Review Robin is primarily a tool for
**operators** to run reviews and **reviewers** to complete them.
A reviewee is a passive row in `reviewees` — assigned, scored,
never a participant. Responses are visible to the operator and,
trivially, to the reviewer who wrote them. Nothing else.

Segment 21 turns this into a **generalized participant system**:

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
**stays**. Segment 21 *enhances* it; it does not replace it.

## 2. What stays, what is new

**Stays — eligibility is already solved.** "Who are the
eligible reviewers / reviewees for this instrument, filtered by
tags and pair-context" is exactly what the per-instrument
`RuleSet` + rule engine already does: reviewer-tag, reviewee-tag,
and `pair_context.tag_N` predicates are all existing rule
grammar (`app/services/rules/`), and each instrument already
pins its own rule (`instruments.rule_set_id`). Segment 21 needs
**no new structure for eligibility** — it builds on the rule
engine as-is.

**New — three things the current model cannot express:**

1. **A response-visibility policy** — per instrument, which
   audiences may view the responses and in what form.
2. **A session schedule** — open / close / results-availability
   windows.
3. **Observers, and reviewee identity** — observers do not
   exist at all today; reviewees exist but have no reachable
   identity for a surface.

The rest of this document is about those three.

---

## 3. New data structures

This is the core of the segment. Five additions; all follow the
established additive-migration playbook (13D / 13E / 13F) —
nullable / defaulted columns and new tables that ship **inert**,
each lit up by its owning slice.

### 3.1 `observers` — the new participant roster

A per-session roster, parallel to `reviewers` and `reviewees`.

```
observers
  id              PK
  session_id      FK -> sessions.id        (indexed, NOT NULL)
  email           String(320)  NOT NULL    (a reachable identity)
  display_name    String        NULL
  status          String(16)   NOT NULL    'active' | 'inactive'
  tag1/tag2/tag3  String        NULL       (filter slots, mirrors reviewers)
  created_at / updated_at
  UNIQUE (session_id, email)
```

Mirrors the `reviewers` shape deliberately so the importer,
the Setup-page table, the friendly-label resolver, and the
sort primitive all extend with no new patterns. Observer tags
let a future refinement scope *which* observers see *which*
instruments; the MVP can treat observers session-wide.

### 3.2 Reviewee identity — a reachable email

`reviewees.email_or_identifier` is explicitly allowed to be a
non-email identifier today, so it cannot be the auth key for a
reviewee surface. Add:

```
reviewees
  + contact_email   String(320)  NULL    (reachable identity; NULL = no surface)
```

A reviewee with no `contact_email` simply has no surface — the
confidential / unaware-reviewee use case stays the untouched
default. `email_or_identifier` keeps its current role
(display + self-review matching); `contact_email` is the new,
separate, auth-bearing field. Observers get `email` directly
(§3.1) because an observer with no identity has no reason to
exist.

### 3.3 `instrument_view_policies` — who sees responses, how

The heart of the visibility model. The operator authors
visibility **per instrument**; the resolver applies it
**per response** at view time (no materialization — see §3.6).

```
instrument_view_policies
  id              PK
  instrument_id   FK -> instruments.id    (indexed, NOT NULL)
  audience        String(16)  NOT NULL    'reviewee' | 'peer_reviewer' | 'observer'
  enabled         Boolean     NOT NULL    default FALSE
  granularity     String(16)  NOT NULL    'per_line' | 'summarized'
  identification  String(16)  NOT NULL    'identified' | 'deidentified'
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
  responses?

The **operator** is not a row: the operator always sees
everything, identified and per-line. That is the baseline, not
a policy.

Two orthogonal **form** axes per grant:

- `granularity` — `per_line` (each reviewer's response shown as
  its own row) or `summarized` (aggregated — see §7).
- `identification` — `identified` (the responding reviewer's
  name is shown) or `deidentified` (responses shown without
  attribution).

This subsumes the "confidential instrument" idea from the
earlier stub: a *confidential* instrument is simply one whose
`reviewee` policy row is `enabled = FALSE`. No separate
confidential flag is needed — confidentiality is the absence of
a viewing grant.

Default on instrument create: all three audiences `enabled =
FALSE` (today's behaviour — operator-only). The operator opts
each audience in deliberately.

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
  Decide whether `responses_close_at` *is* `deadline` renamed /
  reused, or a distinct hard gate with `deadline` staying
  advisory. Leaning: reuse `deadline` as the hard close and not
  add `responses_close_at` — fewer columns, and the lazy-close
  deadline machinery already exists.
- `opens_at` overlaps **Segment 18F**'s "session opening gate."
  21 should *consume* 18F's scheduler, not build a second one
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
  viewable for a session (snapshot envelope; useful for "when
  did reviewees gain access").
- `results.acknowledged` — a reviewee marks their results seen
  (§6).

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
  `reviewers.email` / `reviewees.contact_email` /
  `observers.email` — not a new table. Operators and reviewers
  already get a `users` row on first Easy Auth sign-in;
  reviewees and observers join that spine through their email
  columns.

---

## 4. Auth posture for the new surfaces

Per `spec/audience_and_identity_model.md` the standing posture
is **institutional SSO (Easy Auth) by default, magic-link as a
fallback**, and "tokenized link replaces auth" is explicitly
*not* the model. Segment 21 holds that line:

- Reviewee and observer surfaces gate on Easy Auth identity,
  matched to `reviewees.contact_email` / `observers.email`
  case-insensitively — the same mechanism `require_reviewer_in_session`
  already uses. New dependencies `require_reviewee_in_session`
  / `require_observer_in_session` in `app/web/deps.py`.
- Magic-link invitations (the existing `invitations` +
  tokened-landing machinery) extend to reviewees / observers as
  the fallback for external participants without institutional
  SSO.
- **Open risk** — external reviewees (a job candidate in a
  360, an outside subject) may have no institutional identity
  at all. This is the single biggest auth question and must be
  decided before slice scoping. See §9.

## 5. Surfaces

- **Reviewee results surface** — read-only. For each
  instrument whose `reviewee` policy is enabled, renders the
  collation of feedback about the signed-in reviewee, in the
  policy's form (per-line/summarized × identified/de-identified).
  Nothing shows for confidential instruments or before
  `results_open_at`.
- **Observer surface** — read-only collation view across the
  instruments whose `observer` policy is enabled. Scope of
  *which* reviewees an observer sees is an open question (§9) —
  MVP: all session reviewees.
- **Unified participant landing** — one entry point. For the
  signed-in identity it resolves every role across every
  session: review forms to complete (reviewer), results to
  read (reviewee), collations to observe (observer). A
  360-degree self-assessment falls out naturally — it is just
  an assignment row whose reviewer and reviewee are the same
  person (the existing `self_reviews_active` path), seen on the
  landing as both a form to fill and, later, an input to one's
  own collation. No special "self-assessment" structure.

Chrome stays light and audience-local per the identity spec;
components stay universal.

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
  Segment 14B** (email send) actually being live.

## 7. Cross-cutting: summarization & de-identification

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
- **Coordinates with Segment 18F** (scheduled events). 18F
  owns the scheduler that fires timed lifecycle transitions
  (auto-archive, auto-send, the opening gate). Segment 21's
  `opens_at` / `results_open_at` / `results_close_at` should be
  *driven by 18F's scheduler*, not a second timer. If 21 lands
  before 18F, it ships the columns inert with a manual operator
  toggle; 18F (or 21's own slice) then wires the automation.
- **Naturally follows 17B** (reviewer-surface refinements) so
  the new participant surfaces inherit a settled visual
  baseline.
- No hard dependency on 13C / 18E.

## 9. Open questions — decide before slice scoping

1. **External-participant auth.** Reviewees / observers without
   institutional SSO — magic-link only, or out of scope for the
   first cut? Biggest single design question.
2. **`responses_close_at` vs `deadline`.** Reuse `deadline` as
   the hard close (recommended) or add a distinct column.
3. **Per-instrument vs per-session viewing window.** §3.4 puts
   the window on the session; confirm no instrument needs its
   own release schedule, or move to a per-instrument table.
4. **Observer scope.** Do observers see all reviewees in a
   session, or a tag-filtered subset? MVP says all; tag-scoping
   is the refinement.
5. **Free-text summarization.** Concatenated list vs
   operator-curated written summary for `summarized` text
   fields.
6. **Per-row visibility override.** Is per-instrument policy
   enough, or is an `assignment_view_overrides` table needed
   for the case where one reviewee's row diverges?
7. **Naming.** "Peer review enhancements" no longer fits;
   "Generalized audiences & response visibility" is the working
   title — confirm.

## 10. Sketch PR ladder

Not a committed slice plan — sized once the §9 questions
resolve. Rough shape:

1. **Schema prep** — all of §3 as inert additive migrations
   (`observers`, `instrument_view_policies`,
   `reviewees.contact_email`, the session schedule columns,
   `EVENT_SCHEMAS` registrations).
2. **Observer roster** — importer + Setup page, mirroring the
   reviewer roster.
3. **Reviewee identity** — `contact_email` editor on the
   Reviewees Setup page; `require_reviewee_in_session`.
4. **Visibility-policy authoring** — the per-instrument
   view-policy editor card on the Instruments page.
5. **Session schedule authoring** — open / close / results
   windows on Session Edit; manual gate first, 18F-driven
   automation second.
6. **Collation service** — `collation.py` + view adapters;
   summarization + de-identification.
7. **Reviewee results surface.**
8. **Observer surface.**
9. **Unified participant landing.**
10. **Acknowledgement + notifications** (gated on 14B).

## 11. Out of scope

- **Confidential sessions stay the default.** Every new
  audience grant is opt-in (`enabled = FALSE` by default); a
  session that exposes nothing behaves exactly as today.
- **Operator-facing aggregate analytics** — cross-session
  reporting is its own concern, not a participant surface.
- **Reviewee / observer self-service roster edits** — they do
  not manage their own rows; that stays operator-only.
- **Multi-tenancy / cross-workspace identity** — unchanged.

## 12. Related context

- **`spec/audience_and_identity_model.md`** — §3 (reviewee,
  forward-looking) and §4 (audiences). The authoritative doc on
  what adding an audience entails; update it *first* when this
  segment is picked up — observers and the reviewee surface
  become live audiences §3 / §4 must then describe.
- **`guide/segment_18F_scheduled_events.md`** — owns the
  scheduler the §3.4 windows must ride on.
- **`guide/segment_14B_email_infrastructure.md`** — the
  notification half depends on it.
- **`spec/rule_based_assignment.md`** — the eligibility engine
  Segment 21 builds on unchanged.
- **`docs/status.md`** — current audience inventory.
