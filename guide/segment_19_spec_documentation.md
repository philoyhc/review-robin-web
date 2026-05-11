# Segment 19 — Spec documentation

> **Stub created 2026-05-11** as part of the Stage 4 guide/
> reorg.

**Stub. Sketch-level scope only.** Detailed PR breakdowns
get drafted when this segment is picked up.

## Goal

A **spec-hygiene segment** dedicated to keeping `spec/` —
the canonical "what is this thing supposed to look like /
behave like?" layer — internally consistent, fully covering
the codebase, and free of drift against the implementation.

Distinct from **Segment 20** (operator polish + documentation),
which produces operator- + developer-facing **prose docs**
(`docs/`, README, Start Here page, runbooks). 19 is about
the `spec/` folder itself — the design-intent contracts that
the templates, services, and tests are supposed to match.

## Why a dedicated spec segment

`spec/` already absorbs spec content per-segment (every
shipped segment that locks a UI contract writes its spec on
the way out). What's missing is a **periodic cross-cutting
sweep** that:

- Confirms each spec file still describes the code accurately.
- Identifies new surfaces shipped without a spec home.
- Compresses redundancies across sibling specs.
- Promotes informative filenames over generic ones.
- Updates the `spec/README.md` taxonomy.

The 2026-05-09 → 2026-05-11 sprint did one such sweep
(`guide/spec_sweep_11may.md` — 25 files / 10,224 LOC of
spec touched across F1-F8 drift fixes, C1-C5 consolidation,
S1-S5 style touch-ups, plus the three new Tier-1 specs:
`lifecycle.md`, `csv_contracts.md`, `validate_page.md`).
That sweep is the prototype for what 19 codifies as a
recurring concern.

## Scope (sketch)

### Part 1 — Initial spec coverage gap closure

**Goal.** The set of Tier-1 specs identified in
`guide/spec_sweep_11may.md` "Done vs Remaining" that
remain unwritten as of 2026-05-11:

- **#4 Email Template editor** → `spec/email_template_editor.md`.
- **#5 Permissions / authorization** → `spec/permissions.md`.

Plus the Tier-2 partial-coverage candidates flagged in the
same doc (Relationships Setup deep-dive, Operations
Assignments dedicated section, Operator Settings spec).

Per the sweep doc's tier framing, these are the items the
2026-05-11 sweep didn't get to but identified as worth a
dedicated spec. Part 1 of 19 picks them up.

### Part 2 — Periodic drift audit cadence

**Goal.** Establish a **cadenced** spec sweep — every N
weeks (or every K segments shipped, whichever comes first)
— that surfaces drift before it accretes.

Likely shape:

- A new `guide/spec_sweep_template.md` checklist that drives
  each sweep (the 2026-05-11 sweep doc is a one-off; the
  template is reusable).
- A `guide/spec_audit_YYYY-MM-DD.md` naming convention for
  each sweep's working notes (matches the
  `codebase_assessment_*.md` cadence on the codebase side).
- Sweep entry points: which spec files to grep for which
  tells, how to identify orphan surfaces, how to identify
  generic filenames.
- Output: a per-sweep PR (or PR sequence) carrying the
  drift fixes + consolidation + style touch-ups.

### Part 3 — Spec-coverage gate (post-MVP)

**Goal.** Tooling support — a test or lint pass that catches
new operator routes / templates / models without a spec
home.

Likely shape (deferred — confirm need before scoping):

- A test that maps every operator route in
  `app/web/routes_operator/` to a `spec/` file (via a small
  manual registry or convention-based lookup).
- A CI gate that fails when a new route lands without a
  spec mapping.
- Lighter touch: a `pytest` warning that surfaces missing
  spec coverage without failing the build.

May not be worth the maintenance burden — revisit when
operator-route fan-out makes the manual review of
spec coverage unsustainable.

### Part 4 — Spec rendering / cross-reference UX (post-MVP)

**Goal.** Beyond the markdown files themselves, give
contributors a navigable surface for the spec corpus.

Likely shape (deferred):

- Static-site generation from `spec/` (e.g. via mkdocs)
  with auto-rendered cross-references between specs.
- Per-spec "this references" / "this is referenced by"
  back-links.
- A "what changed in spec since version X" diff view.

Plausibly out of scope forever for a citizen project — the
flat-file markdown is fine in practice. Recorded here as a
maybe-future direction.

## Hard dependencies

- **None.** Part 1 can start any time. Parts 2 / 3 / 4 are
  process / tooling work that fits into the cadence
  whenever it's picked up.

## Out of scope

- **`docs/` content** — operator runbook, deployment guide,
  troubleshooting, etc. That's Segment 20.
- **README / CLAUDE.md / AGENTS.md** — those are the
  outermost framing; their content is maintained per-segment
  (Stage-1 of every reorg PR touches them as needed) rather
  than under a dedicated segment.
- **Code documentation** (docstrings, inline comments).
  Maintained per-PR; not a 19 concern.

## Doc impact

When parts ship:

- `docs/status.md` timeline entry per Part.
- `guide/todo_master.md` updated.
- `spec/README.md` taxonomy refreshed as new specs land in
  Part 1.
- `guide/README.md` mentions the cadence convention (Part 2).
- Existing `guide/spec_sweep_11may.md` retires to
  `guide/archive/` once its remaining items land via Part 1.

## Working notes

- _(placeholder for decisions during PR scoping)_
- **Sweep cadence.** Every N weeks vs every K segments?
  Lean "every codebase_assessment cadence" since the two
  rhyme — pair each codebase_assessment with a spec sweep.
- **Tier-1 vs Tier-2 / 3 priorities.** Already established
  in `guide/spec_sweep_11may.md` — adopt as the default
  tiering for future sweeps.
- **Where to register new specs.** New `spec/<name>.md`
  files land via the segment that first locks the contract;
  Segment 19 picks up the cross-cutting hygiene work, not
  the per-segment authoring.
- **Naming conventions.** Sweep §C5 retired "assumptions" /
  generic filenames; future spec adds should pre-emptively
  pick informative names rather than waiting for a sweep
  to rename them.
