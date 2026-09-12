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

### A constraint the author has set — 2026-09-12

**If this is ever built, any edit or delete mechanism must make it very
clear — *visually* — which roster is being affected.** Set in response to
the objection above, and sharpened by the author on 2026-09-12: **the
point is not copy that names the selected roster. It is a visual state
that marks the selected row out.**

That distinction is the whole of this section, so it is worth stating
once, flatly. **Copy is read if it is read.** Visual state is not read at
all — it is seen, before the operator has decided to attend to anything,
and it is still doing its work for someone moving fast enough not to
finish the sentence. The operator this constraint protects is precisely
the one going too fast to read, so a safeguard that only works on the
careful reader answers a different problem.

Copy and visual state are therefore **complementary and not substitutes**,
and they act at different moments: the confirm sentence catches you *at*
the irreversible click, the visual marking tells you *the whole time*
which roster you are inside. An earlier draft of this section conflated
them and argued the case almost entirely on copy. That was a mistake and
is corrected below.

It is worth being precise about which half of that objection this
answers. Codex's warning has two halves: a shared *implementation* can
hide that reviewees are not reviewers, and a shared *page* can hide it
from the operator. This constraint governs the second. The first is still
open, and is why the presentation/services split above matters.

**Nothing in the app does this today** — checked at `496cc183`, not
assumed, and confirmed by the author: *the lobby does not, beyond the
check box.* The expander tints its own injected panel
(`background: var(--surface-muted)` on the panel's `<td>`) and applies
**no class whatever to the source row**; the only `classList.add`
anywhere in that script targets an options element.

So the lobby's entire row-level selection signal is **the checkbox's own
checked state** — a ~13px mark at the left edge of a full-width row, with
no fill, border, weight or rule distinguishing the row from its
neighbours. That is enough for the lobby, where the action panel names a
count and the operator is choosing among like things. It is the wrong
strength for a page where the four choices are *unlike* things, one of
the actions is Clear all, and the row can sit above a tall panel or
scroll off entirely.

A selected-row visual state is therefore **new work, not reuse of an
existing primitive** — and the honest reading is that the lobby is a
precedent for the *fan-out*, and an example of the gap for the *marking*.

The author's view is that the lobby's own marking wants improving too,
**separately** — recorded as entry 2 below rather than folded in here,
because it stands on its own and this entry should not acquire a
dependency it does not need.

**The reason it is load-bearing rather than a nicety.** Today, "which
roster am I acting on" is answered by ambient context nobody had to
design: the URL, the Setup nav highlight, the page heading, the
breadcrumb. Four pages means the page *is* the answer, continuously and
for free. Consolidate to one page and that signal disappears — the only
remaining cue is which row the operator expanded, and a row can scroll
out of view above a long preview table.

**Where that bites hardest is the destructive actions**, and the proposed
structure puts two of them inside the expandable row: **Clear all**, and
**Upload CSV** where it replaces. Those are the actions where getting the
roster wrong is unrecoverable or expensive.

~~The guarding checkboxes gate *intent* and not *target*, so a guard must
be made to name its roster — a stronger requirement than the four pages
have today.~~ **Wrong, and corrected 2026-09-12 by reading the
templates rather than imagining them.** The guards already name their
roster, on every one of the four pages:

| | today's confirm | today's button |
|---|---|---|
| Reviewers | *Yes, delete the existing **N reviewers*** | **Delete all reviewers** |
| Reviewees | *… **N reviewees*** | **Delete all reviewees** |
| Relationships | *… **N relationships*** | **Delete all relationships** |
| Observers | *… **N observers*** | **Delete all observers** |

The count sits in a pill inside the sentence, and the template comment
says so in as many words — *"The sentence names what goes"* (Segment 19I
Item 3, modelled on the Instruments page). The Upload card's replace
carries its own *"replaces the whole roster"* wording.

So the requirement is **not stronger than today — it is exactly today's,
and the job is to carry it across rather than invent it.** The error was
reasoning from an invented checkbox (*"I understand this removes every
row"*) instead of opening the file, which is the failure this repository
keeps recording against itself.

**And the author's objection to the framing holds.** The four pages are
already similar enough to mislead a careless operator, so consolidation
is not a step change in that risk — the ambient signal I called "free"
is weaker than I claimed, because what actually distinguishes the pages
at the dangerous moment is the *roster-naming copy*, and that copy is
per-control rather than per-page. It travels with the control. Which is
why it survives consolidation intact.

What consolidation genuinely removes is narrower than I first wrote: the
**nav highlight, breadcrumb, URL and page heading**. Those orient an
operator *before* they act; the confirm copy protects them *as* they act,
and only the first group is lost. That is a real but much smaller claim.

### A candidate mechanism — the lobby's row expander

**Proposed by the author, 2026-09-12:** take a leaf from the session
lobby. *Select to edit* fans the selected row out — a panel below it
carrying the edit / delete / upload-to-replace affordances — in a visual
state where the relevant roster row is clearly marked out.

**What the lobby actually does**, read at `496cc183` rather than recalled:

- A `<template id="single-session-expander">` is cloned and injected as a
  full-width `<tr class="session-expander">` **below the selected row**,
  `colspan` across the table.
- The injected `<td>` takes `background: var(--surface-muted)` — a
  distinct fill is the whole of its visual separation.
- It carries a `session-expander-title`, and a bulk variant reading
  *"N sessions selected"*.

Two things about it matter here, and both cut against copying it
literally.

**1. The lobby never names the row it is acting on.** Its single-select
title reads *"**1** session selected"*, and the template comment gives
the reason: *"the session name already shows in the Name box below, so
the single-select header just reads '1 session selected'."* Identity
arrives as a side effect of an **editable field** that happens to hold
it.

A roster has no such field. *Reviewers* is not a name you edit in the
panel; it is the row's fixed identity. Copy the lobby exactly and you get
a panel headed *"1 roster selected"* with nothing anywhere saying
**which** — the one page where that is least affordable, since the panel
holds Clear all and replacing Upload. **So the author's addition — mark
the roster row out clearly — is not a garnish on the lobby pattern; it is
the part the lobby did not need and this page does.**

**2. The lobby's expander is a placeholder.** Its own comment: *"the
action buttons are disabled; only the selection-management buttons are
wired."* So the precedent is a **shape that has been agreed, not an
interaction that has been proven in use**. Worth knowing before it is
cited as a solved problem — and a reason the Rosters version would want
its own look at whether a `--surface-muted` fill alone reads as "this
panel belongs to *that* row" once the panel is tall.

**What the mechanism has going for it**, stated plainly: it keeps target
and action adjacent — the affordances are literally attached to the row
they act on, which is a stronger spatial claim than a heading elsewhere
on the page — and it reuses a pattern the operator will already have met
in the lobby, which is the same argument the consolidation itself rests
on.

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
- The selected-roster constraint above has a design that holds **while
  the panel is open and the source row may be scrolled away**, and the
  existing roster-naming confirm copy is carried across unchanged. A gate
  rather than a preference — though a narrower one than first written:
  the confirm copy already names its roster today and travels with the
  control, so what needs designing is the *orientation* signal the nav,
  breadcrumb and heading currently supply, not the *confirmation* signal,
  which survives on its own.

---

## 2. The lobby's selected row is marked only by its checkbox

**Raised by the author, 2026-09-12**, while discussing entry 1, and
**explicitly separable from it**: this stands whether or not the Rosters
consolidation ever happens, and entry 1 should not wait on it.

> **✅ Graduated 2026-09-12 to `guide/segment_19L_ux_refinements.md`
> Item 1**, on the author's instruction. The plan is authoritative for
> the work; this entry stays as the record of how the observation arose
> and why it was judged separable. Entry 1 remains an idea, not an item.

### The observation

On the sessions lobby, selecting a row injects an action panel beneath it
— and the only thing distinguishing the *selected row itself* from its
neighbours is that its checkbox is ticked. Verified at `496cc183`: the
panel's `<td>` takes `background: var(--surface-muted)`, and no class is
applied to the source `<tr>` at any point.

### Why it is worth improving

A ticked checkbox is a small mark at one edge of a full-width row. It is
adequate while the panel sits directly beneath it and the operator has
just clicked. It degrades in exactly the conditions the lobby invites:

- **bulk selection**, where several rows are selected and the panel
  states only a count, so *which* rows are in that count is carried
  entirely by scattered checkbox states;
- **a tall panel**, which pushes the source row toward or past the top of
  the viewport;
- **returning to the page**, where selection may be restored without the
  click that created it.

The panel's actions include **Purge and archive** and **Delete** — the
Delete button ships disabled today, and the expander is a placeholder,
but the intended action set is destructive, and target-clarity matters
most where the action is irreversible.

### What this is not

Not a proposal for a mechanism, and not an argument that the lobby is
currently unsafe — its destructive buttons are not wired. It records that
**the row-marking is the weakest link in a pattern the app is likely to
reuse**, which is the reason to fix it before it is copied rather than
after.

### Relationship to entry 1

If both are ever done, this one is the **cheaper and lower-risk** of the
two and could land first: it improves a shipped page in place, needs no
route or service change, and would give entry 1 the primitive it
otherwise has to invent. That is an argument for sequence, not for
bundling — entry 1 remains gated on pilot evidence, and this one is not.

---

*Further ideas go below as `## 3.`, `## 4.`, … each with the same shape:
the idea as put, what it rests on, the case against, open questions.
Entries are independent unless one says otherwise.*
