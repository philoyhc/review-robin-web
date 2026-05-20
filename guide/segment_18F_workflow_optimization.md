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
invariant "nothing is live until Activate." The opening gate idea
is **retired entirely** (2026-05-19): the decoupling it aimed at —
invitations out first, reviewing starts synchronously — is
delivered instead by **Part 2** below (Activated-as-gate +
invitations from the Prepared state) and **18G's scheduled
activation**, with no separate gate within `ready`.

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

**Decisions (2026-05-19).**
- **No status relabel.** The `validated` state keeps its existing
  displayed label, "Validated" — *not* renamed to "Prepared".
  Because `validated` already entails "assignments generated"
  (today's super-button runs Generate → Validate → `mark_validated`,
  and the codebase nowhere assumes `validated` means "not yet
  generated"), the existing state display is accurate after Prepare
  runs. The button reads "Prepare" while the resulting state pill
  reads "Validated" — a mild vocabulary gap, but not worth a relabel
  or a copy sweep. No change to `SessionStatus` and no change to
  `app/services/lifecycle_display.py`.
- **"Prepare" button body text.** The Workflow-card body copy for
  the Prepare action explains it as something like: *"Prepare the
  session — generate the assignments and validate that the setup
  is ready for prime time."* Final wording settled at PR scoping;
  the intent is that the operator reads "Prepare" as the combined
  generate-plus-validate step, so the "Validated" state label
  needs no defence.

### Part 2 — Pre-activation invitations + reviewer pre-open / closed states

**Goal.** Support the scenario: an operator sends a notification
email to every reviewer *before* the session opens — "the review
opens for responses at «future time»" — and a reviewer who clicks
through lands on a page telling them the review is scheduled and to
come back later. After the review window, a reviewer who returns
sees a "this review is now closed" page.

**The model — Activated-as-gate, no separate opening gate.** The
`draft → ready` **Activate transition is the open event**: a
session is *open for responses* exactly when it is `ready`. There
is **no separate "opening" gate within `ready`** and **no new
`SessionStatus` value** — Activation itself is the gate, and
(in 18G) the activation can be scheduled. This is the call that
retires the old "opening gate" idea; see 18G's Part 3, now
"Scheduled activation".

**Why the current implementation precludes the scenario.** Two
gaps, both addressed here:

1. **Invitations are `ready`-gated.** `invitations.generate` /
   `send-all` / single-send all call `_require_ready`
   (`app/web/routes_operator/_operations.py`), which 409s unless
   the session is `ready`. So no notification email can go out
   before the session is open.
2. **No reviewer pre-open state.** Because a reviewer can't be
   invited before `ready` today, the reviewer surface has no
   "invited, but not open yet" rendering.

The reviewer **closed** state, by contrast, *substantially exists*
already — the surface computes per-instrument `accepting` /
`any_accepting`, and `lifecycle.observe_deadline` lazily closes
instruments at the deadline; the surface renders read-only when
nothing is accepting. Part 2 mostly adds an explicit "this review
is now closed" banner over that existing machinery.

**Scope sketch.**
- **Relax the invitation gate.** Allow `invitations.generate` /
  `send-all` / single-send to run while the session is `validated`
  (Prepared), not only `ready` — the small `_require_ready`
  change. The Workflow-card "Create invites" / "Send invites"
  stepper stages become available from the Prepared state.
- **Reviewer pre-open surface.** When a reviewer follows an
  invitation to a session that is `validated` (Prepared, not yet
  activated), render a "the review is scheduled to open — come
  back later" page instead of the response form. Routed from the
  invitation-token landing and the `/reviewer/sessions/{id}` /
  surface routes.
- **Reviewer closed surface.** A clear "this review is now
  closed" page for the post-window / `expired` period, over the
  existing not-accepting machinery.
- **Edit-after-invite hazard.** Sending invitations while
  `validated` and then editing setup flips `validated → draft`
  (`lifecycle.invalidate_if_validated`) with invitations already
  out. Part 2 adds a confirm / warning guard so the operator
  isn't surprised.

**Schema note.** The *precise* "opens at «future time»" wording
needs a stored open time — that is **18G's `activate_at` column**
(scheduled activation). Part 2 builds the *states* (invites-out-
while-Prepared, the pre-open page, the closed page); until 18G
lands `activate_at`, the pre-open page shows a generic "not open
yet" message rather than a specific time.

### Part 3+ — Holistic workflow work-through (to be catalogued)

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
- Any lifecycle seams the participant-model arc (segments 21+)
  will need — recorded as pre-positioning notes, not built here.

## Revamped Workflow card — proposed layout, states, and buttons (draft for planning)

> **Status:** Draft — captured for planning so the spec rewrite
> at PR time has a target. Final wording, exact pill copy, and
> the warnings-detour mechanics settle at PR scoping.
> `spec/workflow_card.md` is not edited until the implementation
> PR lands.

### Layout

The card goes back to **50% / 50%** column widths
(`grid-template-columns: minmax(0, 1fr) minmax(0, 1fr)`,
restoring the 50/50 split that pre-dated the 15E 60/40 stepper).
The role of each column is unchanged from today's spec — the
left column carries the body copy and the action buttons, the
right column carries the per-state status aside (validation
issues, invitation counts, deadline). The buttons stay where
they live now (left column); the only structural change vs
today is that they form **two rows** instead of one
five-button row, with both rows filling the left column's
width:

```
┌── Workflow (H2) ─────────────────────────────────────────────┐
│ ┌─ .next-action-main (50%) ──┐ ┌─ .next-action-status (50%)┐ │
│ │ <p>State-specific body</p> │ │ State-specific status /  │ │
│ │                            │ │ errors aside.            │ │
│ │ ┌── prep-actions row ───┐  │ │                          │ │
│ │ │ Revert │ Prepare │ Cr-│  │ │                          │ │
│ │ │ to draft│ session│ inv│  │ │                          │ │
│ │ └────────────────────────┘  │ │                          │ │
│ │ ┌── run-actions row ────┐   │ │                          │ │
│ │ │ Send │ Activate│ Send│Cl│ │ │                          │ │
│ │ │ inv- │ session │ rem-│os│ │ │                          │ │
│ │ │ ites │         │ inde│e │ │ │                          │ │
│ │ └─────────────────────────┘ │ │                          │ │
│ └─────────────────────────────┘ └──────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

(Schematic only — exact CSS settles at PR time. Each button
takes `1 / button_count` of the left column's width: row 1's
three buttons are 33.33% of the left column; row 2's four
buttons are 25%.)

- **Left column — body + two action rows.** **Row 1 (prep
  phase):** Revert to draft · Prepare session · Create invites
  — the "before reviewers see anything" actions. **Row 2 (run
  phase):** Send invites · Activate session · Send reminders ·
  Close session — the "reviewers are now in the loop" actions.
  Both rows render in every state; per-state styling drives
  which buttons are Primary / Secondary / inert.
- **Right column — per-state status aside.** Unchanged role
  from the current spec: validation issue list in error
  states, invitation counts / deadline in run states, the
  reconcile-detour confirmation banner when fired, the
  super-button failure banner when fired.
- State-specific failure banners stay above the two-column
  grid (same convention as today).
- Below the ~720 px responsive breakpoint the right column
  drops below the left (same convention as today), so the
  reading order is: body → prep row → run row → status aside.

### Button vocabulary

Both rows live in the **left column** (see Layout above). "Row"
below is the visual row within the left column — not a separate
card column.

| Button | Row | POST | Effect |
| --- | --- | --- | --- |
| Revert to draft | 1 (prep) | existing revert route | `ready → draft` or `validated → draft`, keeping responses. |
| Prepare session | 1 (prep) | new `/workflow/prepare` (Generate + Validate) | replaces the 15E super-button's pre-Activate steps; lands in `validated` on clean validation, stays in `draft` on errors. |
| Create invites | 1 (prep) | `/invitations/generate` | idempotent — creates one row per assigned active reviewer not yet invited. Live from **Validated** (per Part 2's invite-gate relaxation). |
| Send invites | 2 (run) | `/invitations/send-all` | sends every unsent `Invitation`. Live from Validated. |
| Activate session | 2 (run) | `/workflow/activate` (now solo, not a super-button) | `validated → ready`, opens every instrument, emits `session.activated`. |
| Send reminders | 2 (run) | `/invitations/remind-all` | nudges reviewers with outstanding responses. |
| **Close session** | 2 (run) | **same route as Revert to draft** | "exact same backend behaviour as Revert"; the separate label only signals the operator's intent (review window ended vs editing setup). |

### State machine cascade (proposed)

```
if is_setup_empty:                              → State 1
elif is_draft:
    if validation_summary.has_errors:           → State 3
    else:                                       → State 2
elif is_validated:
    if invitations.none:
        if has_unacknowledged_warnings:         → State 4W
        else:                                   → State 4
    elif invitations.generated_not_sent:        → State 5
    else (invitations.sent):                    → State 6
elif is_ready:
    if invitations.none:                        → State 7
    elif invitations.generated_not_sent:        → State 8
    else (invitations.sent):                    → State 9
```

(Ten states, same count as the current spec but rebalanced
around Prepare / Activate as distinct buttons and around the
new pre-activation invite states.)

### Per-state body copy (proposed)

| State | Trigger | Body copy (placeholder wording — refine at PR time) |
| --- | --- | --- |
| **1** | `is_setup_empty` | "Session not fully set up. Make sure that reviewers, reviewees, relationships (optional), and instruments have been set up before continuing." |
| **2** | `is_draft`, no validation errors | "Run **Prepare session** — generates the assignment pairs and validates that the setup is ready for prime time. Nothing goes live until you activate." |
| **3** | `is_draft`, validation errors | "Validation didn't pass. Resolve the errors and re-run Prepare. The issue list is in the right column." |
| **4** | `is_validated`, no invitations | "Setup is prepared and the reviewer surface is previewable. Create invites to draft notifications, send them ahead of the open date if you like, and Activate when ready to open responses." |
| **4W** | `is_validated`, warnings | Same as 4 plus help-line: "{N} warning(s) — review on Validate before activating." |
| **5** | `is_validated`, invites generated, none sent | "Invitations are ready to send. Send them ahead of activation to notify reviewers, or activate now and send afterwards." |
| **6** | `is_validated`, invites sent | "Reviewers have been notified that the review will open. Activate the session when you're ready to open responses." |
| **7** | `is_ready`, no invitations | "Session is open for responses. Create invites and send them so reviewers know they can start." |
| **8** | `is_ready`, invites generated, none sent | "Session is open. Send the prepared invitations so reviewers know they can start." |
| **9** | `is_ready`, invites sent | "Session is open. Send reminders if reviewers fall behind, and Close session when the review window ends." |

### Workflow stepper — proposed button matrix

`Pri` = Primary live, `Sec` = Secondary live, `—` = inert
(rendered in Secondary style, `disabled aria-disabled="true"`).
Revert / Close never promote to Primary — they're recovery /
close-out paths, not the next forward step.

**Row 1 (prep) — Revert · Prepare · Create invites**

| Button | 1 | 2 | 3 | 4 | 4W | 5 | 6 | 7 | 8 | 9 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Revert to draft | — | — | — | Sec | Sec | Sec | Sec | Sec | Sec | Sec |
| Prepare session | — | **Pri** | **Pri** | Sec | Sec | Sec | Sec | — | — | — |
| Create invites | — | — | — | **Pri** | **Pri** | Sec | Sec | **Pri** | Sec | Sec |

**Row 2 (run) — Send invites · Activate · Send reminders · Close session**

| Button | 1 | 2 | 3 | 4 | 4W | 5 | 6 | 7 | 8 | 9 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Send invites | — | — | — | — | — | **Pri** | Sec | — | **Pri** | Sec |
| Activate session | — | — | — | **Pri** | **Pri** (→ warn detour) | **Pri** | **Pri** | — | — | — |
| Send reminders | — | — | — | — | — | — | — | — | — | **Pri** |
| Close session | — | — | — | — | — | — | — | Sec | Sec | **Pri** |

(`Create invites` is idempotent, so it remains Secondary-live
after the first generation in case the roster gains an
uninvited reviewer; the matrix above pins it at Sec / Pri based
on whether *all* currently-eligible reviewers are already
invited. `Send invites` follows the same shape on already-sent
invites. Both detail behaviours stay the same as the current
spec.)

### Open clarifications for PR scoping

- **Body-copy phrasing.** Wording above is placeholder; refine
  against the existing copy register (`spec/workflow_card.md`
  §"Per-state body copy" is the style anchor).
- **Status aside content.** The right column's role is
  unchanged from today (validation issues, invite counts,
  deadline). Decide whether the new pre-activation invite
  states (4 / 5 / 6 with invites generated / sent) introduce
  any new aside content, or just re-use the existing
  "invitations created / sent" counters.
- **Close-session styling.** Render as `.btn.destructive` like
  other destructive operator buttons, or keep Secondary with a
  destructive icon? "Close" is less drastic than "Revert" from
  the operator's mental model (the review just ended), so
  Secondary may be appropriate.
- **State 6 → 9 jump.** Activating from State 6 (invites
  already sent in Validated) lands in State 9 directly — the
  right-column status aside should make that consequence clear
  before the click.
- **Reconcile detour preservation.** The saved-response
  confirmation detour (today on the super-button) attaches to
  the new **Prepare session** button. Same mechanics, same
  banner — moved off Activate.

## Hard dependencies

- **Part 1** is self-contained — no dependency beyond the
  existing Validate / Generate / Activate services and the
  Workflow card.
- **Part 2** is self-contained at the manual level; the *scheduled*
  activation that fills in the "opens at «time»" wording is
  **18G's Scheduled activation** (Part 3 there) — 18F Part 2
  builds the states, 18G adds the schedule.
- The broader work-through coordinates with **Segment 18G**
  (scheduled events): 18G's scheduled activation and auto-send
  assume the Activated-as-gate model 18F settles. 18F should land
  first; 18G consumes its result.

## Out of scope

- Time-based automation of any kind — auto-archive, scheduled
  activation, auto-send invitations, scheduled reminders. All of
  that is **Segment 18G**. 18F Part 2 builds the lifecycle states
  those triggers fire against; it does not build the triggers.
- The participant-model lifecycle redesign (segments 21+) —
  18F only records pre-positioning notes for it.

## Doc impact

When parts ship:

- `spec/workflow_card.md` — the Prepare/Activate split: the
  stepper row, the ten-state cascade, the per-state copy; the
  invite stages becoming available from the Prepared state.
- `spec/lifecycle.md` — assignment generation runs pre-activation
  and the reviewer surface is previewable from that point;
  invitations sendable from `validated`; Activation is the
  "opens for responses" event (Activated-as-gate, no separate
  opening gate).
- `spec/reviewer-surface.md` — the new pre-open ("scheduled to
  open") and closed ("review now closed") reviewer states.
- `spec/operations_pages.md` / `spec/preview_hub.md` — the
  preview becomes reachable once Prepare has run; the Invitations
  surface is usable from the Prepared state.
- `docs/status.md` timeline entry per Part.
- `guide/todo_master.md` updated.

## Working notes

- _(placeholder for decisions during PR scoping)_
- **Lead, don't trail.** 18F lands before 18G — the scheduling
  work hangs off the lifecycle this segment settles.
