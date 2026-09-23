# Review Robin Web — Constitution

Six rules the practice holds itself to. Each is the decision line of one
core decision in `rrw_sdd_in_practice.md` §6, with its rationale and its
trade-off and nothing else — the evidence, the history and the numbers
live there. This document is derived from that one: change the practice
document first, then this.

A rule here binds every change to the repository, by whoever or whatever
makes it. A rule that stops being followed should be struck from this
list, not left standing as a wish.

---

## I. Plan on the way in, spec on the way out

Inside a segment the plan (`guide/segment_*.md`) carries the intent and
leads the code; the spec (`spec/`) is settled when the segment closes, to
match what shipped; `docs/status.md` records that it did. A spec edited
slice by slice describes a moving target; a spec written at the close is
right until the next segment opens it.

*Trade-off.* A window of spec drift inside every open segment, by
design — and an exit held by convention, not mechanism. A missing plan is
self-revealing (there is nothing to build from); a missing spec edit is
silent. Drift not noticed at the close survives it.

## II. A convention becomes a failing test only where the repository states something to derive it from

Where a rule can be read from something the repository itself states,
enforce it with a test that reads that thing, so the check cannot go
stale when it changes. The source can be a constant in the code (an enum,
a label map, a schema allowlist), the route table, or the file tree and
the documents' own structure. Where nothing states it, the rule stays
prose, read by a person or a reader (III). Vigilance fails at exactly the
things vigilance is structurally bad at; a derived test does not.

*Trade-off.* A gate sees only what the repository names. The route table
names every routing surface, so a surface with no spec at all is caught
(`tests/unit/test_spec_coverage.py`, 2026-09-05); nothing names what a
spec must *contain*, so one that exists and says too little still passes.
The exit of I is **checkable, not mechanised** — `tools/close_check.py`
is run by a person at the close, and it asks whether the committed edit
happened, never whether it was right.

## III. Maker and checker are separate

Whatever writes a change does not check it. A separate, read-only reader
opens the governing spec and reads the diff cold — reporting what the diff
does that the spec does not describe, what the commit message claims that
the diff does not support, and scope beyond the stated purpose. Reporting
nothing is a valid result; inventing findings to look thorough is worse
than no reader. The reader is not capped at a smaller model than the
author.

*Trade-off.* A reader works only when run, and costs the author a
reading each time. Making the pass routine is the open item; making it
cheap enough to *stay* routine is the constraint on how.

*(Annotated 2026-09-14, after `rrw_sdd_in_practice.md` §6.4.* "Only when
run" was measured and the answer was **never**: `diff-reviewer` had not
read a diff since the arc that created it, and `spec-writer` — chartered
at a close — had become the per-rung reader by default. The two now have
separate cadences, stated in `CLAUDE.md` "Where work runs". The open item
is answered by *naming* a cadence, not by demonstrating it holds; the next
audit re-measures it.*)

*(Annotated 2026-09-18.* The cadence named above was measured rather
than assumed, and **halved**. A merge-history audit found the cold read
catching real defects on code rungs while overclaiming only prose on
plan and close rungs — and costing roughly **2× a slice's elapsed
time**, which is the "cheap enough to stay routine" constraint above
failing in the direction the trade-off warned about. So the read is now
**per item** rather than per slice, with prose-only slices exempt and
one-off code slices unchanged; the rules are in `CLAUDE.md` "Where work
runs". The maker ≠ checker principle is untouched — what changed is the
unit a reading covers, from a rung's diff to an item's cumulative one.
Each item close now records how many reads it took and what they found,
so the next audit re-measures against this cadence instead of naming a
third. The measurement, and its first re-take under the new cadence,
are in `rrw_sdd_in_practice.md` §6.4 (2026-09-19); `tools/pace_audit.py`
reproduces both.*)

## IV. The human is the verifier of last resort, and nothing runs unattended

Anything the suite and the reader cannot see — layout, rendering,
in-browser behaviour, real authentication — is verified by a person on
the deployed dev slot, and a change that touches such things says so in
its description rather than claiming verification. No autonomous loop,
no scheduled agent, no agent that merges: the definition of done is not
machine-checkable for the defects that actually occur here, and a loop
without one has no exit.

*Trade-off.* Throughput is bounded by one person's attention, and the
largest measured class of real defects is the one only that person
catches. Scaffold-first (a placeholder surface agreed before wiring) is
the partial answer; it looks once, not twice.

## V. The reasoning travels with the change

A commit message or PR body carries what was found, what was measured,
and why the obvious alternative was not taken — not only what changed. A
plan records what was intended and what was done when they differ. A
dated document is annotated with a dated correction, never silently
rewritten. Policy that judgement already follows is written down (as in
`CONTRIBUTING.md`) rather than enforced with ceremony.

*Trade-off.* Reasoning written in two places is written twice, and
twice-written reasoning drifts — the same failure II exists to catch, one
layer up. Keep it in one place and point to it.

## VI. Retire a convention rather than mechanise it badly

A rule that cannot be checked without a growing allowlist, or that would
fire on identifiers as readily as on prose, is not made into a test — it
is dropped, or left as guidance, and the decision is recorded. A check
that gets argued with, raised, then disabled leaves the practice worse
than the paragraph did.

*Trade-off.* Some real conventions stay unenforced. The list of them
should be short, written down, and revisited when the repository comes
to state something that would make one derivable (II). It is
`docs/unenforced_conventions.md` — written 2026-09-08, having been
promised by this paragraph and absent until then.

---

**Not articles.** Two of §6's decisions are operating practices rather
than constraints and are deliberately not elevated here: two altitudes of
spec (§6.2 — a functional contract above per-page contracts) and periodic
sweeps and snapshots rather than continuous synchronisation (§6.5). Both
serve I and II; neither binds a single change.
