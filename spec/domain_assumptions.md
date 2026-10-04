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
filing state, not a disposal one. The archive *action* can delete,
though: "Purge and archive" (`purge_and_archive` in
`app/services/session_purge.py`) first hard-deletes whichever of the
responses, rosters and audit log the operator ticks, and unarchiving
does not bring them back.

Session setup can be edited only in `draft` or `validated`; an
Activated or Closed session is reverted to draft first. The exceptions
are in `spec/lifecycle.md` §3.1: the Observers roster accepts edits
until the session is archived, and the email-template editor is not
gated at all. Reviewers are not notified of edits (author's ruling,
2026-10-02, F15).

Session is the top-level structure. Operators group sessions with
free-form tags on the lobby (`app/services/session_tags.py`), and can
duplicate a session without its responses, assignments, invitations or
audit history (`app/services/session_clone.py`).

#### Instrument

Associated with one set of response questions (ratings, comments,
etc.) and their instructions.

An instrument has no operator-set status. Accepting responses is
session-wide: the lifecycle sets every instrument's
`accepting_responses` together, so all accept while the session is
Activated and none does once it closes (at its deadline or by the
operator) or reverts to draft. What a reviewer sees
of their answers after close is the instrument's visibility policy.
Instruments are edited under the session's rule above, and reviewers
are not notified of edits. (A per-instrument Draft / Receiving /
Closed status and a notify-on-edit step were struck, author's ruling,
2026-10-02, F15.)

## UI vocabulary — see

- **`spec/visual_style_general.md`** — palette, typography,
  spacing, component shapes (the portable design system).
- **`spec/visual_style_rrw.md`** — Review-Robin instantiation
  (accent assignments, lifecycle colors, chrome, banner family).
- **`spec/ui_elements.md`** — element catalogue mapping
  primitives to CSS classes + the "5a. Banner behaviour
  conventions" sub-section (Cancel button, auto-scroll,
  Cancel-return anchor).
- **`spec/operator_button_audit.md`** — per-page button audit.
