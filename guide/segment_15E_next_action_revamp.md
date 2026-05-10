# Segment 15E — Next Action revamp + multi-step shortcuts

**Status:** Planning — stub created 2026-05-10. Captures the
"super buttons" idea originally sketched as 15D PR 8 and broadens
it into a Next Action card revamp on Session Home.

> **Working notes scratchpad** at the bottom — capture decisions,
> scope tweaks, and open questions as they come up. Once the shape
> settles, lift the durable parts into a proper "Goal / Scope / PR
> sequence / Out of scope" structure.

## Goal

Reduce the operator click-count from "did setup work; now nag the
session through Validate → Generate → Activate one step at a
time" to **"one button advances to the next sensible state."**
The Next Action card on Session Home is the natural home: it
already names the operator's next move per lifecycle state, but
each move is a single primitive. 15E adds **multi-step shortcuts**
that chain primitives together, while keeping the underlying
single-step actions individually clickable for operators who want
to pause / inspect between steps.

The 15D plan parked this work as a follow-on ("PR 8 — super
buttons") with one paragraph of intent. 15E gives it a proper
home + per-state surface plan.

## Why a separate segment

- 15D's PR 8 framing assumed the buttons live on the Operations
  Assignments page. **The natural home is the Next Action card on
  Session Home** — that's already the per-state action-prompter
  surface. Putting the chained actions there keeps the single
  "what should I do next?" answer in one place.
- 15D shipped per-step changes (Generate moved to Operations
  Assignments page; Quick Setup loses Generate). Layering a
  multi-step UI on top makes more sense as its own segment, after
  the per-step routes settle.
- **Operations Assignments page** can also surface the
  Validate-+-Generate / +-Activate buttons for operators who land
  there directly, but the canonical home is Next Action. Decide
  during PR scoping.

## Likely surface

### Next Action card states + super buttons (sketchy)

| Lifecycle state | Single-step Primary today | Proposed super button |
|---|---|---|
| `draft` (setup-empty) | (no action — fill rosters first) | n/a |
| `draft` (populated, not validated) | Validate Setup | **Validate + Generate** (then re-render in `validated`) |
| `validated` (no warnings) | Activate Session | **Validate + Generate + Activate** (chain from any earlier state too) |
| `validated` (with warnings) | Activate (via `/validate?activate=1` detour) | **Acknowledge warnings + Activate** (single-click acknowledge + post) |
| `ready` | Manage invitations / Monitor / Pause | (no chain — operator's already past the progression) |

Single-step Secondary buttons stay (See validation details, See
previews, Revert to draft, etc.) so operators retain the granular
flow.

### Operations Assignments page (optional)

A subset of super buttons surfaces here too — at minimum the
"Generate + Activate" chain (skip Validate when the operator just
wants to push the engine forward). Decide during scoping; may
defer to a follow-on if the Next Action surface feels complete on
its own.

## Mechanics (sketchy)

- **Chain semantics.** Each super button posts to a new route
  (e.g. `POST /operator/sessions/{id}/next-action/validate-and-generate`)
  that runs the steps in order, stopping at the first failure.
  No new schema; no new audit events — each underlying step
  emits its own event. The route returns a single
  success / failure banner.
- **Failure-handling.** If Validate fails, the chain stops and
  the operator lands on Session Home with the validation summary
  already populated (same path the existing single-step flow
  hits). If Generate fails, the chain stops and the operator
  sees an inline error banner naming the failed step. **Deferred
  decision:** whether the partial-success state needs explicit
  audit framing (e.g. "Validate passed; Generate aborted with X
  errors").
- **Button styling.** Super buttons render as Primary on Next
  Action; underlying single-step actions move to Secondary or
  hide depending on layout. Lock down during PR scoping.
- **No re-Generate on idempotent paths.** "Validate + Generate"
  re-runs Generate even when the assignments table is already
  populated and matches. Acceptable: Generate is fast and
  idempotent; no need to special-case.

## Out of scope

- **Acknowledge-warnings widget.** The current `/validate?activate=1`
  detour is its own UI for warning acknowledgement; integrating it
  into the super button is a UX question for PR scoping, not a
  hard ask of 15E.
- **State machine refactor.** Lifecycle is `draft / validated /
  ready / paused / closed`; the super buttons compose the existing
  transitions rather than introducing a new state.
- **Email-notification chain.** "Activate + send invitations"
  could be a future super button, but emails are a separate
  segment (12B-equivalent) — out of scope here.
- **Multi-session bulk operations.** Lobby-page bulk actions
  (e.g. "Activate every session in this cohort") are a different
  shape and not in scope.

## Working notes / open questions

- _(placeholder)_
- Which surfaces ship buttons in PR 1 — Next Action only, or also
  Operations Assignments page?
- Single chain route per shortcut (e.g.
  `/next-action/validate-and-generate`) vs. one polymorphic route
  with a `chain={validate,generate,activate}` form param?
- Failure inline-banner copy: short ("Generate failed — see
  validation details") vs. linkified ("Generate failed: 3 errors;
  See validation details ↗")?
- Does the Operations Assignments page need its own per-state
  super button row, or is "Generate + Activate" enough?
- What about a "Pause + revert + Edit setup" shortcut for
  operators who realise mid-cycle the rosters are wrong? Probably
  out of scope (reverting is destructive enough that the operator
  should stay deliberate), but worth a one-line note.
- Animated progress UX: do we want a spinner / multi-step status
  indicator while the chain runs, or just block + reload? Plain
  block-+-reload is the simpler call.

## Related context

- **Segment 15D — Assignments revamp**
  (`guide/archive/segment_15D_assignments_revamp.md`). Original "super
  buttons" framing in PR 8; carved out into 15E for proper
  surface scoping.
- **Session Home spec** (`spec/session_home.md`) — the canonical
  Next Action card behaviour. 15E extends rather than replaces.
- **Next Action card template**
  (`app/web/templates/operator/session_detail.html:17-170`).
  State-conditional body + button row; the super buttons slot
  into the existing button-row structure with state-specific
  routing.
- **Lifecycle service**
  (`app/services/session_lifecycle.py`). The transitions super
  buttons compose (`is_draft` / `is_validated` / `is_ready`) live
  here; 15E doesn't touch the state machine, just chains
  existing primitives.
- **Operations Assignments page**
  (15D PR 6a). Generate button + bulk Include toggle live here;
  decide during scoping whether super buttons also surface
  here.
