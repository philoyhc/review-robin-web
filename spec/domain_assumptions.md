# Assumptions

A short record of load-bearing **domain** assumptions for Review
Robin Web. **UI vocabulary is not here** — button styles, banners,
typography and layout primitives live in
`spec/visual_style_general.md`, `spec/visual_style_rrw.md` and
`spec/ui_elements.md`, which are authoritative for them. This file
is the small Domain reference plus the cross-reference index
below.

## Domain

### Hierarchy of structures

#### Session

Contains the same universe of Reviewers, Reviewees, Assignments,
Instruments and their associated Response Forms, Email,
deadline. (Typically 1-6 Instruments — a description of usage, not
a cap. Nothing in the code bounds the count.)

Assignments are always produced by the rule engine. `AssignmentMode`
has one live member, `rule_based`; `manual` retired in 16A alongside
the manual-CSV upload path, and Full Matrix is a rule set rather than
a mode of its own — the absorption this line once anticipated.

Status: five values, all live — `draft`, `validated`, `ready`,
`expired`, `archived`. Operators read `ready` as **Activated** and
`expired` as **Closed** (`app/services/lifecycle_display.py`).
Archiving files a session out of the active lobby; it is
**reversible and deletes no data** (`archive_session`), so it is a
filing state, not a disposal one.

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
