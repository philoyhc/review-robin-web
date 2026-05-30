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
3. **Observers, and reviewee identity** — observers do not
   exist at all today; reviewees exist but have no reachable
   identity for a surface.
4. **Magic-link participation** — an in-scope optional auth
   affordance for all three participant audiences (§4).

## 3. New data structures

The core of the design. Five additions; all follow the
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
sort primitive all extend with no new patterns. Observers carry
**at least one tag** so they can be categorized — the
per-instrument visibility policy (§3.3) can scope an observer
viewing-grant to a tag, so only observers of a given category
see a given instrument's responses. Three tag slots mirror
`reviewers`; one is the minimum that has to be meaningful.

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
  identity matched to `reviewees.contact_email` /
  `observers.email` case-insensitively — the mechanism
  `require_reviewer_in_session` already uses. New dependencies
  `require_reviewee_in_session` / `require_observer_in_session`
  in `app/web/deps.py`.

## 5. Surfaces

- **Reviewee results surface** — read-only. For each
  instrument whose `reviewee` policy is enabled, renders the
  collation of feedback about the signed-in reviewee, in the
  policy's form (per-line/summarized × identified/de-identified).
  Nothing shows for confidential instruments or before
  `results_open_at`.
- **Observer surface** — read-only collation view across the
  instruments whose `observer` policy is enabled *and* whose
  `observer_tag` (if set) matches the signed-in observer's
  tags.
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

- ``/me/`` — reviewer landing today (the participant meta-
  lobby spec lands when the reviewee + observer features
  ship; for now it's the dashboard).
- ``/me/sessions/{id}/{page}`` — the per-session participant
  surface (role-tabbed once reviewee + observer features
  ship; reviewer-mode-only today).
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
- Observer roster — importer + Setup page.
- Reviewee identity — `contact_email` + `require_reviewee_in_session`.
- Magic-link affordance — extend the tokened-landing path to
  reviewees / observers; operator-selectable per session.
- Per-instrument visibility-policy authoring.
- Session schedule authoring + 18G integration.
- Collation service — summarization + de-identification.
- Reviewee results surface.
- Observer surface.
- Unified participant landing.
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
