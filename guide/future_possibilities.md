# Future possibilities

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
