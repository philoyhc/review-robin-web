# New UX ideas — exploration only

**Not for implementation.** Nothing here is scheduled, committed to, or
sized. This file exists so that shape-level ideas about the operator UI
have somewhere to live other than a conversation, and so that the
thinking behind one is available if it is ever picked up.

**Beyond pilot.** Every idea in this file assumes the institutional Azure
deployment has concluded and a pilot has produced evidence. The
2026-09-12 Codex assessment's position is the governing one: *do not open
another broad feature segment before deployment*, and *pick deferred work
only when evidence activates its trigger, not because a document names
it*. An entry here is a description, not a trigger.

**How an entry graduates.** It does not, on its own. If pilot evidence
makes one worth doing, it becomes a segment plan in the normal way
(`guide/segment_plan_template.md`) and this entry becomes that plan's
Opportunity input. Until then, an entry may be edited, argued with, or
deleted without ceremony.

---

## 1. One Rosters page, replacing four

**Proposed 2026-09-12 by the author.**

Consolidate the four roster Setup pages — **Reviewers**, **Reviewees**,
**Relationships**, **Observers** — into a single **Rosters** page.

### The rationale, as put

They share a largely common structure anyway, so four pages present four
copies of one idea, and an operator learns the same page four times.

### The proposed page structure

As described, and kept as described:

1. **A full-width card at the top**, holding a table of **all rosters and
   their columns**. Each row is a roster. The table carries, per roster,
   a facility to **select to edit** and a facility to **select to
   preview**.

2. **Select to edit** opens *a new row* beneath the selected roster,
   holding:
   - edit boxes for that roster's **friendly labels**;
   - **Clear all**;
   - **Upload CSV**;
   - **Download CSV**;
   - **select to preview**;
   - the **guarding checkboxes** those destructive and replacing actions
     need.

3. **Select to preview** shows a **search box** with the **preview table**
   below it.

So the page is one index plus two expandable modes, rather than four
pages each carrying its own full set of cards.

### What the rationale rests on — measured 2026-09-12 at `578ab82f`

The claim that the four share a structure is not an impression. The card
sequence is **identical** across three of them and a superset in the
fourth:

| Page | Template | Route module | Cards |
|---|---:|---:|---|
| Reviewers | 728 | 634 | guidance · tag labels · Operator actions · preview table · Add/Edit · Upload · Danger Zone |
| Reviewees | 742 | 645 | *same seven* |
| Relationships | 710 | 792 | *same seven* |
| Observers | 858 | 707 | *the same seven*, plus **Cohort match rule** |

**3,038 template lines and 2,778 route lines — 5,816 in total** across
the four. The only structural difference found is Observers' extra
cohort-rule card; the only vocabulary difference is the tag-label card's
title (*Reviewer tag labels* / *Reviewee tag labels* / *Pair-context
labels*).

`spec/setup_pages.md` already asserts this in its **"Shared body shape"**
section — every Setup page renders the same cards top-to-bottom — so the
consolidation is partly a proposal to make the code and the UI match a
shape the spec already describes.

Independent support: the 2026-09-12 Codex assessment measured the
**Reviewers/Reviewees setup routes as the most duplicated production pair
in the repository, each roughly half duplicated code**.

### The case against, which is on record and is not weak

The same assessment that supplies the duplication figure also warns
against this abstraction by name:

> a generic roster abstraction would also hide audience-specific
> behavior; consolidate only when a behavior change has to be made twice
> and the two implementations demonstrably remain equivalent.

That is a real objection and it is about *behaviour*, not lines. The four
rosters are not four skins on one entity:

- **Relationships** is a join, not a roster of people. Its rows are
  reviewer–reviewee pairs, and its "columns" are pair context.
- **Observers** carries a cohort match rule that the other three have no
  analogue for, and the observer model is the least settled of the four.
  **Confirmed by the author, 2026-09-12: Observers will have features
  unique to it.** So per-roster divergence is not a hypothetical edge to
  be designed around later — it is a stated property of the target, and
  any consolidation has to carry it as a first-class case from the start.
- **Reviewees** are the only roster whose members may carry a non-email
  identifier, which is why `reviewees.unreachable_for_results` exists as
  a validation rule and has no sibling on the other pages.
- The lifecycle gates and Danger-Zone semantics are per-roster and have
  already been found wrong once each.

So the honest framing is: **the presentation is near-identical and the
semantics are not**. A consolidation that unifies the presentation is a
different, smaller, and safer proposal than one that unifies the
services behind it — and this idea, as described, is the presentation
one. Worth keeping those separable if it is ever taken up.

### Open questions

Not answered here; recorded so they are not rediscovered.

1. **Does the top table show columns per roster, or the union?** Four
   rosters with different column sets in one table is either a ragged
   table or a union with many empty cells. The description says "all
   rosters and their columns" without settling which.
2. **Where do the per-roster exceptions live?** This is now the load-
   bearing question rather than one of six, because the author has
   confirmed Observers will carry unique features — today's cohort match
   rule and more to come. The shape has to answer it *before* the shared
   table is designed, not after, since a design that treats divergence as
   an exception will be wrong in the one place it is most certain to be
   exercised. Candidates, none chosen: a third expandable mode beside
   edit and preview; a per-roster extras slot the shared row renders
   when a roster declares one; or Observers staying its own page and the
   consolidation covering the three that genuinely are alike. That last
   option is not a failure of the idea — three-into-one still removes the
   duplication the rationale is about.
3. **What happens to deep links?** The Validate page's *Fix on … ↗* links
   land on specific Setup pages with a row anchor
   (`spec/validate_page.md` §2.4), and the setup coverage matrix links in
   too. A single page changes every one of those targets.
4. **Does the row pager survive?** Each roster page currently pages
   independently, and `spec/ui_elements.md` §10 settles that a page turn
   reloads. One page hosting four pageable previews needs that answered
   again.
5. **Is the nav still four items?** Consolidating the pages does not
   necessarily consolidate the navigation, and the Setup nav is how
   operators currently know the four rosters exist at all.
6. **What does this do to Quick Setup?** `_quick_setup.py` orchestrates
   across these rosters and is already near the size watchlist.

### What would have to be true before this is worth scheduling

- The pilot has run, and there is evidence that operators find the
  four-page arrangement costly — not merely that it is repetitive in the
  source.
- A behaviour change has actually had to be made four times.
- The deep-link contract has an answer, because Validate's fix links are
  a shipped affordance and breaking them silently would be worse than
  the duplication.

---

*Further ideas go below as `## 2.`, `## 3.`, … each with the same shape:
the idea as put, what it rests on, the case against, open questions.*
