# Segment 15E — Validate page + Next Action revamp

**Status:** Planning — stub created 2026-05-10; scope broadened
2026-05-13 to absorb the Validate-page revisions made necessary
by 15B's per-instrument assignments move. Captures the "super
buttons" idea originally sketched as 15D PR 8 and broadens it
into a Validate-page + Next Action revamp that **streamlines
the operator workflow from setup completion through to just
before email generation**.

> **Working notes scratchpad** at the bottom — capture decisions,
> scope tweaks, and open questions as they come up. Once the shape
> settles, lift the durable parts into a proper "Goal / Scope / PR
> sequence / Out of scope" structure.

## Goal

Streamline the **setup → ready-to-send** stretch of the operator
workflow. Today the operator clicks Validate → (fix issues) →
Generate (per instrument or page-level) → Activate as separate
primitives; the Validate page itself still leans on the
pre-15B "one rule per session, generate the whole table" mental
model that doesn't fit the per-instrument world. 15E
re-examines that stretch as a single surface and lands two
coordinated revamps:

1. **Validate page** — rework the readiness rules + UI in light
   of per-instrument assignments (15B). Each instrument now
   carries its own pinned rule + materialised pair set; the
   page should surface per-instrument readiness (pinned? stale?
   generated? included rows > 0?) alongside the existing
   session-wide checks. Validation actions that auto-fix where
   safe (e.g. "Generate now" for instruments with pinned rules
   but no rows) belong here, scoped to the failing instrument
   rather than the whole session.

2. **Next Action card** on Session Home — collapse the "did
   setup; now nag through Validate → Generate → Activate"
   click-chain to **"one button advances to the next sensible
   state."** The card already names the operator's next move
   per lifecycle state, but each move is a single primitive.
   15E adds **multi-step shortcuts** that chain primitives
   together, while keeping the underlying single-step actions
   individually clickable for operators who want to pause /
   inspect between steps.

End-to-end test: after import + roster work, an operator should
need at most a single click to advance from "setup done" to
"ready to send invitations" — with the Validate page surfacing
any per-instrument blockers along the way (and offering inline
fixes where safe).

The 15D plan parked the super-buttons piece as a follow-on
("PR 8") with one paragraph of intent. 15E gives both the
Validate page work and the multi-step shortcuts a proper home +
per-state surface plan.

## Why a separate segment

- 15D's PR 8 framing assumed the buttons live on the Operations
  Assignments page. **The natural home is the Next Action card on
  Session Home** — that's already the per-state action-prompter
  surface. Putting the chained actions there keeps the single
  "what should I do next?" answer in one place.
- 15D shipped per-step changes (Generate moved to Operations
  Assignments page; Quick Setup loses Generate). 15B then shifted
  Generate from session-wide to per-instrument (rule pinning on
  the Instruments page, status table on the Assignments page).
  Both moves leave the Validate page surfacing checks that no
  longer match the underlying model — the page needs its own
  pass. Layering the multi-step shortcuts on top makes more
  sense after the Validate page settles, so the two revamps live
  in the same segment to share the readiness-rule plumbing they
  both depend on.
- **Operations Assignments page** can also surface the
  Validate-+-Generate / +-Activate buttons for operators who land
  there directly, but the canonical home is Next Action. Decide
  during PR scoping.

## Likely surface

### Validate page revamp (sketchy)

The page today (Segment 11G) registers a `ValidationRule`
registry, runs every rule against the session, and renders one
issue list with severity-chip filters + per-issue
fix-here deep-links. Pre-15B that was enough because the
"Assignments" check was a single yes-or-no ("did the operator
generate?"). Post-15B the picture is per-instrument and finer-
grained.

Surface adjustments:

- **Per-instrument readiness pills.** A new section above (or
  inside) the setup-coverage matrix lists every instrument with
  its current readiness signal — `rule pinned` (yes/no),
  `eligible pairs > 0`, `generated rows` (count), `included
  rows > 0`, `stale` (eligible vs. generated diverge). Drives
  the at-a-glance "which instrument blocks Activate?" question
  without making the operator hop to the Assignments page first.
- **New validation rules** (registered in `validation.py`):
  - `instruments.no_rule_pinned` — error if any instrument has
    `rule_set_id IS NULL` while the session has reviewers /
    reviewees (otherwise that instrument can't produce
    assignments). Fix link: the Instruments page card.
  - `instruments.stale_generated` — warning if any pinned
    instrument's eligible count diverges from its generated
    count (operator hasn't regenerated since a roster / rule
    change). Fix link: page-level Generate on Assignments
    page.
  - `instruments.zero_included` — warning (or info?) if any
    instrument has `generated_count > 0` but `included_count
    == 0` (every row deactivated, including via the Self-review
    bulk toggle).
  - Re-frame the existing session-wide assignment check —
    `assignments.no_pairs` → tighter "no included pairs across
    any instrument" (since per-instrument visibility is in the
    new rules above).
- **Inline auto-fix actions.** Where safe, the per-issue fix
  button runs the fix in-line rather than deep-linking off-
  page. Specifically: `instruments.stale_generated` gets a
  "Generate this instrument" button that hits the per-instrument
  Generate route (added in 15B, or to be added in this segment
  if not yet present); on success the page reloads with the
  rule's status updated.
- **Severity chip strip stays.** The filter / count pattern
  carries over unchanged; new rules slot into the existing
  severity ladder.

Out of scope for the Validate page work: re-render as something
other than a flat issue list (the existing surface works; we're
extending it). The setup-coverage matrix at the top stays as-is
modulo the new per-instrument readiness pills.

### Next Action card states + super buttons (sketchy)

| Lifecycle state | Single-step Primary today | Proposed super button |
|---|---|---|
| `draft` (setup-empty) | (no action — fill rosters first) | n/a |
| `draft` (populated, not validated) | Validate Setup | **Validate + Generate** (then re-render in `validated`) |
| `validated` (no warnings) | Activate Session | **Validate + Generate + Activate** (chain from any earlier state too) |
| `validated` (with warnings) | Activate (via `/validate?activate=1` detour) | **Acknowledge warnings + Activate** (single-click acknowledge + post) |
| `ready`, no invitations sent | Manage invitations (Primary) + Monitor responses (Secondary) | **Generate and send** (Primary) — one-click flow that generates invitations and dispatches the pending batch, replacing the current two-hop detour through Manage invitations |
| `ready`, invitations sent | Manage invitations (Primary) + Monitor responses (Secondary) | Manage invitations (Secondary) + Monitor responses (Secondary) — both demoted, no Primary; the "do something now" affordance has already fired |

Single-step Secondary buttons stay (See validation details, See
previews, Revert to draft, etc.) so operators retain the granular
flow.

The two-row treatment for `ready` absorbs the **Activated-state
split** originally listed in Segment 15's polish stub: today the
Activated branch always renders Manage invitations + Monitor
responses regardless of whether any invitation emails have
actually gone out, and the post-15E behaviour splits on
invitation-send progress. The horizontal-rule content (Pause
Session) stays unchanged across both sub-states. Cross-ref:
`spec/operator_button_audit.md` "Drift / inconsistencies" §3.

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

- **Segment 15B — per-instrument assignments**
  (`guide/archive/segment_15B_per_instrument_assignments.md`). The
  Validate-page revamp half of 15E lights up the per-instrument
  readiness signals 15B shipped (`Instrument.rule_set_id`,
  per-instrument Generate, per-instrument Self review include).
- **Segment 15D — Assignments revamp**
  (`guide/archive/segment_15D_assignments_revamp.md`). Original
  "super buttons" framing in PR 8; carved out into 15E for
  proper surface scoping.
- **Segment 11G — Validate page rebuild**
  (`guide/archive/segment_11G_validate_page.md`). Shipped the
  `ValidationRule` registry + per-issue fix-here deep-links 15E
  extends.
- **Validation service**
  (`app/services/validation.py`). `REGISTERED_RULES` is the slot
  for the new per-instrument rules.
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
  (15D PR 6a + 15B refinements). Per-instrument status table +
  page-level Generate live here; the Validate page's auto-fix
  buttons share the per-instrument Generate route this surface
  exposes.
