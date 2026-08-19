# Future possibilities

> **Archived 2026-08-19 — superseded by
> [`guide/deferred_consolidated.md`](../deferred_consolidated.md) Part C.**
> This file's content was merged verbatim into the consolidated deferred-work
> ledger. Kept for provenance; the consolidated file is the live reference.

**Aspirational directions that are deliberately *not* on the
roadmap.**

`todo_master.md` is the committed segment sequence —
everything there is intended to ship.
`deferred_until_pilot_feedback.md` holds work that is paused
but still expected, pending real usage data. **This file is
the third bucket: ideas that are plausible and worth recording
so the design doesn't foreclose them, but which the project
has consciously decided *not* to plan for.** An item here may
never be built, and that is the expected outcome unless
something specific changes the call.

Each entry states the idea, why it is off the roadmap, what is
being done instead, and what evidence would move it back onto
the roadmap.

---

## AG Grid (or an equivalent JS data-grid) for the reviewer surface

**The idea.** Replace the reviewer surface's plain HTML
`<table>` of `<input>` / `<textarea>` / `<select>` cells with a
client-side data-grid component (AG Grid was the candidate).
That would bundle, in one library, virtualised row rendering,
column resize / freeze, rich cell editors, and a built-in
cell-edit lifecycle.

**Why it is off the roadmap.** A JS data-grid is judged
**overkill** for this app's actual surfaces:

- *Operator side* — the Setup-page tables took the opposite
  route and shipped per-row inline edit on plain HTML tables
  (Segment 15F). That settled the operator question: no grid
  framework needed.
- *Reviewer side* — a reviewer reviews a **bounded** set of
  reviewees (a handful to a few dozen), so the one genuinely
  grid-only feature, row virtualisation, solves a problem the
  domain does not really have. The features that *do* matter —
  cell-level autosave, sticky headers, return-to-place,
  visible progress — are achievable as targeted progressive
  enhancement without a grid library.
- *Cost* — AG Grid would be the project's **first JS bundle**
  and would force a Community-vs-Enterprise licensing
  decision, against a server-rendered monolith whose `CLAUDE.md`
  explicitly rules out a framework / build pipeline while
  allowing targeted inline progressive-enhancement JS.

**What is being done instead.** The valuable reviewer-surface
ergonomics that `spec/visual_style_rrw.md` pins as first-class
(auto-save, return-to-place, visible progress, sticky headers,
filter-to-incomplete, keyboard navigation) are pursued
incrementally as **vanilla progressive enhancement under
Segment 17B** — debounced `fetch` to the existing `POST /save`
endpoint, CSS `position: sticky`, and small inline scripts.
The reviewer-surface view-shape payload (`_surface_context`'s
list-of-dicts) is already stable and serializable, so it would
*also* feed a JS grid unchanged — keeping this option open at
zero ongoing cost.

**What would move it back onto the roadmap.** Pilot evidence
that reviewers routinely face genuinely large tables (on the
order of 100+ rows per reviewer) where virtualisation, column
freeze, or grid-native keyboard navigation materially change
completion rates — i.e. a real problem the progressive-
enhancement path cannot reach. Absent that, the
progressive-enhancement path is the plan.

*History: this was briefly a roadmap segment — numbered 17,
then 17A, then 22 — before being moved here on 2026-05-16. The
superseded segment plan is recoverable from git history
(`guide/segment_22_ag_grid_replacement.md`).*

---

## Randomizer / grouper

**The idea.** A facility to assign reviewers to reviewees — or to
partition either roster into groups — **at random**, individually
or by group, rather than by an explicit rule. For example: "randomly
pair each student with 3 peers," or "randomly split the cohort into
review groups of 5, everyone reviews their group."

**Why it is off the roadmap.** Random assignment at generate-time
fights the engine's **idempotency** contract. Assignments are not
authored row-by-row; they are *generated* by a deterministic
per-instrument rule pass (Band 1 → the rule engine), and the app
**re-runs that pass repeatedly** — on **Prepare**, and on the
reconcile + regenerate path — precisely because regeneration must be
safe to repeat without disturbing saved responses (responses are
keyed to stable `(reviewer, reviewee, instrument)` pairs). A random
draw *inside* generate is non-deterministic: every re-run would
reshuffle the pairings, orphaning saved responses, and any
**subsequent redraft** (add/remove a person, tweak a field, re-open
setup) would silently re-draw *everyone*. Randomness at the generate
step is fundamentally incompatible with a re-runnable generate.

**What is being done / could be done instead.** Move the randomness
**out of generate-time and into the data, once** — then let the
existing deterministic, tag-based rules do the assignment. The concrete
shape is a **dedicated randomizer / grouper page (or function)** that
takes in **simple requirements** — e.g. "groups of 5," "each reviewer
gets 3 random reviewees," "split the cohort evenly into N groups" — and
**writes its output into persisted inputs**, as **either**:

- **relationships rows** (random pairings, feeding pair-context), or
- **reviewer / reviewee tags** (a randomly-drawn group label, e.g.
  `RevieweeTag2 = "Group C"`).

After that, assignment is an ordinary deterministic function of roster +
rules (Band 1 filters on the group tag, or the relationships feed
pair-context), and **Prepare / regenerate stay idempotent** — re-running
never re-draws, because the draw is now fixed data. **Seed the shuffle**
(persist the seed) for reproducibility and an audit trail.

Because the tag output has to land *somewhere*, the tag mode **requires a
free tag column**: the randomizer targets an **unused** `ReviewerTag*` /
`RevieweeTag*` slot (or the operator explicitly picks which slot it may
overwrite). The relationships mode has the analogous prerequisite that
relationships are enabled for the session.

This is a **pre-processing utility**, **not a rule-engine mode** — which
is exactly why it can be added without touching the idempotent generate
path. And it is *already achievable manually today*: randomize in a
spreadsheet, drop the groups into a spare tag column, upload the CSV, and
use a tag-based rule (the same tag → rule flow the quickstart describes
for tutorial groups).

**What would move it back onto the roadmap.** Pilot evidence that
operators want random grouping / pairing often enough that the manual
spreadsheet route is real friction. The shape to build then is the
**seeded, data-materializing** "shuffle into tags / random pairings"
pre-step above — deliberately never a non-deterministic generate mode.
