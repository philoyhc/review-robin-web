# Assumptions

A short record of load-bearing **domain** assumptions for Review
Robin Web. The original UI-vocabulary content (button styles,
banners, typography, layout primitives) was officially superseded
2026-05-03 by `spec/visual_style_general.md` +
`spec/visual_style_rrw.md` + `spec/ui_elements.md`; the
superseded sections moved to `guide/archive/assumptions_ui_legacy.md`
on 2026-05-11 once the sweep at `guide/archive/spec_sweep_11may.md` C1
landed.

Today this file is the small Domain reference + a cross-reference
index pointing into the canonical visual-style docs.

## Domain

### Hierarchy of structures

#### Session

Contains the same universe of Reviewers, Reviewees, Assignments,
1-6 Instruments and their associated Response Forms, Email,
deadline.

At any one time, operating under one assignment mode (FullMatrix,
Manual, RuleBased; note that FullMatrix should be absorbed as a
particular rule set).

Status: Draft, Ready (when populated sufficiently, within
deadline), Expired (when deadline has passed), Archived (data
collected has been downloaded and deleted).

Session can be edited when instruments are closed/paused; if there
are ongoing reviews, reviewers need to be notified.

Note: While Session is the top level structure, there should be a
way to put arbitrarily assign them to Groups. Sessions can be
duplicated (without the response data).

#### Instrument

Associated with one set of response questions (ratings, comments,
etc.) and their instructions.

Status: Draft, Receiving responses, Closed/Paused.

Closed/Paused defaults to keeping existing responses invisible to
reviewers, but visibility can be turned on.

Instrument can be edited when closed/paused; if there are ongoing
reviews, reviewers need to be notified.

Instrument automatically closes upon session deadline.

## UI vocabulary — see

- **`spec/visual_style_general.md`** — palette, typography,
  spacing, component shapes (the portable design system).
- **`spec/visual_style_rrw.md`** — Review-Robin instantiation
  (accent assignments, lifecycle colors, chrome, banner family).
- **`spec/ui_elements.md`** — element catalogue mapping
  primitives to CSS classes + the "Inline error / warning
  banner behaviour" sub-section (Cancel button, auto-scroll,
  Cancel-return anchor).
- **`spec/operator_button_audit.md`** — per-page button audit.
