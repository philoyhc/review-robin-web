# Segment 21 — Peer review enhancements

**Status:** Stub. Created 2026-05-16 to hold the
reviewee-facing surface work that `spec/audience_and_identity_model.md`
§3 ("Reviewee — forward-looking, currently not an audience")
records as deliberately out of scope for current work but
explicitly left un-foreclosed.

## Goal

Bring the **reviewee** online as a third live audience — give
the people being reviewed their own surface, instead of
treating them purely as subjects of review who never enter
the system.

Today reviewers and operators are the only audiences with
surfaces. A reviewee is a row in `reviewees`: assigned, scored,
and (in confidential use cases) possibly unaware they are being
reviewed at all. This segment is the pivot for the
non-confidential use cases — peer review where participants see
each other, 360-degree feedback, and results-sharing flows.

## Why a separate segment

- **New audience, not a tweak.** A reviewee surface introduces
  a third audience with its own auth posture, chrome
  conventions, and identity assumptions
  (`spec/audience_and_identity_model.md` §3 + §"Surfaces").
  That is a segment-sized commitment, not a card on an
  existing page.
- **Decision provenance.** The reviewee-as-audience direction
  is recorded in `audience_and_identity_model.md` §3 and the
  spec's "Reviewee surface" forward-looking note — flagged as
  envisioned but explicitly *not in scope* until a segment
  picks it up. This is that segment.
- **Sequencing.** Wants a stable reviewer-surface + response
  model underneath it (responses are what a reviewee surface
  would surface). No hard dep on a specific not-yet-shipped
  segment, but naturally lands after the reviewer-surface
  refinements (17B) settle.

## Likely scope (sketchy)

> Detail settles during PR scoping. The split below is a
> sketch, not a slice ladder.

### Reviewee identity and auth

- Reviewees today have `email_or_identifier`, which may not be
  an email at all (non-email identifiers are valid). A
  reviewee surface needs a reachable identity — decide whether
  the surface is gated by Easy Auth (like operators), by a
  per-reviewee tokened link (like reviewer invitations), or
  both depending on the use case.
- Confidential vs non-confidential is a **per-instrument**
  property, not per-session: one review session can carry both
  confidential instruments (never exposed to the reviewee) and
  non-confidential ones (results shared with the reviewee).
  Likely a per-instrument flag that gates whether *that
  instrument's* responses surface on the reviewee view — the
  reviewee surface for a session shows the non-confidential
  instruments and omits the confidential ones. A session with
  no non-confidential instruments simply has nothing to show a
  reviewee.

### Results-sharing surface

- A read-only reviewee view of the feedback collected about
  them — respecting whatever aggregation / anonymisation the
  session calls for (raw per-reviewer responses vs aggregated
  scores vs operator-curated summary).
- Operator control over *what* and *when*: results are not
  visible until the operator releases them.

### Feedback acknowledgement

- A reviewee marks that they have seen their results;
  operator-visible acknowledgement state.

### Self-assessment / 360-degree

- In a 360 setup the reviewee is also a reviewer of
  themselves — explore whether self-assessment is just an
  existing reviewer assignment (reviewer == reviewee) surfaced
  through the reviewee's own entry point, or a distinct
  instrument flavour.

### Reviewee notifications

- Email surfaces parallel to the reviewer invitation / reminder
  family — "your results are ready", acknowledgement nudges —
  riding the same `email_outbox` + sender plumbing.

## Out of scope

- **Confidential-session use cases.** Sessions that must keep
  reviewees unaware stay exactly as they are; this segment
  adds an opt-in surface, it does not change the default.
- **Operator-facing analytics.** Aggregate reporting for
  operators is its own concern, not the reviewee surface.
- **Reviewee self-service roster edits.** Reviewees do not
  manage their own `reviewees` row — that stays operator-only.

## Working notes / open questions

- _(placeholder)_
- Auth model — Easy Auth vs tokened link vs per-session
  choice. Biggest open design question; needs a decision
  before slice scoping.
- Anonymisation model — does the reviewee see per-reviewer
  responses, aggregated numbers, or an operator-written
  summary? Probably a per-instrument setting (it sits alongside
  the per-instrument confidential / non-confidential flag).
- Naming — "Peer review enhancements" is the working title;
  the segment may end up better named once the auth +
  results-sharing model is decided.
- Relationship to Segment 17B (reviewer surface refinements) —
  shared chrome / component vocabulary; sequence 21 after 17B
  so the reviewee surface inherits a settled reviewer-surface
  visual baseline.

## Related context

- **`spec/audience_and_identity_model.md`** — §3 (Reviewee,
  forward-looking) + the "Reviewee surface" forward-looking
  note under "Surfaces" / "Out of scope". The highest-ranking
  doc on what bringing the reviewee online entails.
- **`spec/reviewer-surface.md`** — the existing
  participant-facing surface; the reviewee surface borrows its
  chrome conventions and tokened-link precedent.
- **`docs/status.md`** — current audience inventory (operator
  + reviewer surfaces live; reviewee + sys-admin tracked
  separately).
