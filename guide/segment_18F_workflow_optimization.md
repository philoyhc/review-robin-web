# Segment 18F — Workflow optimization

> **Stub created 2026-05-19.** Sketch-level scope only — detailed
> PR breakdowns get drafted when this segment is picked up.
>
> This segment number was previously **Scheduled events**; that
> work was renumbered to **Segment 18G**
> (`guide/segment_18G_scheduled_events.md`) so 18F could take the
> workflow work. 18F leads, 18G follows.

## Goal

A deliberate, end-to-end work-through of the **operator workflow**
— the path a session travels from creation through setup,
preparation, activation, the review window, and close-out. The
super-button / Workflow card (Segment 15E) consolidated several
lifecycle actions into one stepper; that consolidation traded away
some intermediate states the operator used to be able to inspect.
18F revisits the whole journey, fixes the concrete regressions,
and — importantly — **pre-positions** the workflow so the later
scheduling work (18G) and the post-MVP participant model
(segments 21+) slot in cleanly rather than each re-litigating the
lifecycle.

This is a workflow / UX / lifecycle segment, not a schema segment.
Where it needs columns, it rides the 13F audit (the same audit
18G depends on).

## Why now / why a segment

- **A concrete regression surfaced.** Because the super-button
  absorbed Validate → Generate → Activate into one action, an
  operator cannot preview the reviewer surface for a specific
  reviewer until *after* activation — and once a session is
  activated, the path to reviewers actually seeing their assigned
  cases is short (only the invitation send stands between).
  There is no longer a safe window: "assignments exist and are
  inspectable, but nothing is live." Part 1 restores that window.
- **The workflow deserves one holistic pass.** Rather than
  patching the super-button regression in isolation, 18F is the
  place to walk the whole operator journey once, catalogue the
  rough edges, and decide the shape of the lifecycle before
  18G layers time-based automation on top of it.
- **Pre-positioning pays compound interest.** 18G (scheduled
  events) and the participant-model arc (segments 21+) both
  assume a lifecycle they can hang triggers and roles off. If 18F
  settles the lifecycle's seams now, those segments consume a
  stable workflow instead of reshaping it.

## Scope (sketch)

The exact part list is drafted at scoping time. Part 1 is
committed; the rest of the segment is the holistic work-through
that will surface further parts.

### Part 1 — Split the super-button: "Prepare" + "Activate"

**The problem.** The Workflow-card super-button runs Validate →
Generate → Activate as one action. Reviewer-surface previews need
the assignment pairs to exist (generation must have run), so today
preview is impossible until activation — at which point the
session is live and reviewers are one invitation-send away from
seeing their cases. The operator never gets a "generated but not
live" window to preview in.

**The decision (2026-05-19): Option A — split the action in two.**

- **"Prepare"** runs **Validate + Generate**. After Prepare the
  session still sits in a pre-activation state (`draft` /
  `validated`): assignment pairs are materialised and the
  reviewer surface is fully previewable, but nothing is live —
  reviewers cannot reach their surfaces and no invitations have
  gone out. Generation has no outbound side effects (it only
  materialises `assignments` + `responses` rows), so running it
  before activation is safe.
- **"Activate"** stays the single, deliberate point of no return
  — the `→ ready` transition, unchanged.

**Why Option A over Option B (an "opening" gate after Activate).**
The opening gate gates *response acceptance*, not *visibility* /
*previewability*, so it would not by itself give the operator a
window where reviewers definitely cannot see their cases. It also
adds a third lifecycle concept. Option A maps the preview window
onto a state that already exists (pre-activation) and keeps the
invariant "nothing is live until Activate." The opening gate is
still worth building — for decoupling invitation timing from the
synchronised start of reviewing — but that is **18G Part 3**, a
scheduling concern, not the fix for this preview problem.

**Sketch of the change.**
- The Workflow-card stepper splits the collapsed forward action
  into a `Prepare` button (Validate + Generate) and the existing
  `Activate session` button. The five-stage stepper row and the
  ten-state cascade in `spec/workflow_card.md` are revised
  accordingly.
- The reviewer-surface preview (Previews / Reviewer Experience
  Preview hub) becomes reachable once Prepare has run — i.e. once
  the instruments have generated pair sets — instead of requiring
  `ready`.
- No schema change expected: `validated` already exists; Generate
  already runs as its own service. This is a Workflow-card +
  routing + preview-gating change.

### Part 2+ — Holistic workflow work-through (to be catalogued)

A walk of the full operator journey, cataloguing rough edges and
deciding fixes. Candidate areas to assess at scoping (not yet
committed parts):

- Whether the Workflow card's state cascade still reads cleanly
  once Prepare/Activate are distinct.
- The Validate ↔ Generate ↔ preview ↔ Activate ordering and the
  affordances between them.
- Re-preparation after a setup edit (the reconcile path —
  `spec/reconciling_regeneration.md` — and how the card surfaces
  it).
- Where invitation create / send sits relative to Activate, and
  how that reads ahead of 18G's auto-send (Part 2 there) and
  opening gate (Part 3 there).
- Any lifecycle seams the participant-model arc (segments 21+)
  will need — recorded as pre-positioning notes, not built here.

## Hard dependencies

- **Part 1** is self-contained — no dependency beyond the
  existing Validate / Generate / Activate services and the
  Workflow card.
- The broader work-through coordinates with **Segment 18G**
  (scheduled events): 18G's opening gate (Part 3) and auto-send
  (Part 2) assume the lifecycle 18F settles. 18F should land
  first; 18G consumes its result.

## Out of scope

- Time-based automation of any kind — auto-archive, auto-send
  invitations, the scheduled "opening" gate, scheduled reminders.
  All of that is **Segment 18G**.
- The participant-model lifecycle redesign (segments 21+) —
  18F only records pre-positioning notes for it.

## Doc impact

When parts ship:

- `spec/workflow_card.md` — the Prepare/Activate split: the
  stepper row, the ten-state cascade, the per-state copy.
- `spec/lifecycle.md` — clarify that assignment generation runs
  pre-activation and the reviewer surface is previewable from
  that point.
- `spec/operations_pages.md` / `spec/preview_hub.md` — the
  preview becomes reachable once Prepare has run.
- `docs/status.md` timeline entry per Part.
- `guide/todo_master.md` updated.

## Working notes

- _(placeholder for decisions during PR scoping)_
- **Lead, don't trail.** 18F lands before 18G — the scheduling
  work hangs off the lifecycle this segment settles.
