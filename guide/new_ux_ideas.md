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

**Proposed 2026-09-12 by the author.** The **first move of a two-move
consolidation** — entry 2 is the second, folding Previews, Invitations
and Responses into Monitoring on the same structure. Assignments is
deliberately in neither.

Consolidate the four roster Setup pages — **Reviewers**, **Reviewees**,
**Relationships**, **Observers** — into a single **Rosters** page.

### The rationale, as put

They share a largely common structure anyway, so four pages present four
copies of one idea, and an operator learns the same page four times.

### The scope, as set by the author — 2026-09-12

**This is a UX change, not a feature.** The author, governing everything
below:

> As a general point, it's the ux that is being modified; I am not aiming
> to add more action capabilities (and restrictions) over and above
> current, unless they fit easily within the new ux and isn't expensive.

So the test for anything in this entry is **does the operator already
have this?** Re-housing a capability is in scope; inventing one needs to
be cheap and to fall out of the new shape rather than be bolted to it.
That is a stronger constraint than it sounds, because a consolidation
invites tidying, and tidying is how a re-house becomes a rewrite.

**It is worth applying to this entry's own contents.** Nearly all of it
passes — the row-level arity rule is what already ships, *"except
Observers"* is an existing divergence, and Lock / Unlock, `inert`,
dirty-tracking, the unsaved-changes confirm and the block-on-switch are
all shipped mechanisms on the Instruments page. **Nothing in it fails that test**, once the
Instruments page is read with `grep -a`: the unsaved-changes confirm, the
block on switching while dirty and the `beforeunload` nav-away guard all
ship there already. This paragraph twice claimed otherwise; see "How the
error was made".

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

### The structure, refined — 2026-09-12

The author's elaboration, kept as put. It resolves most of what the
sketch above left implicit.

**Select to preview** puts two cards below the roster table:

1. a **search box card**, half width, right;
2. beneath it a **full-width preview table card**, close to the one the
   Setup pages carry today — the same table, its column chips, its row
   pager, and the rest.

**Only one roster's preview is open at a time.** Selecting another
roster's preview closes the previous one. That is the answer to the
"ragged table or union" question the sketch raised for *previews*: the
preview is per-roster, so its columns are that roster's, and no
reconciliation is needed. (The **index** table at the top still has to
answer it — see the open questions.)

**Select to edit** keeps the inline row beneath the roster, as sketched,
and gains a defined scope: **roster-level metadata edits all live
there** — friendly labels, Clear all, Upload / Download CSV, and their
guarding checkboxes. Roster-level, not row-level.

**Row-level work moves to where the rows are.** Selecting one or more
rows *in the preview table* opens a **new action row carrying the
row-level buttons**, in the manner of the sessions lobby's expander.

**So the Operator actions card splits, and this is the part with a
measurement behind it.** `spec/setup_pages.md`'s "Operator actions card"
describes a card doing **two jobs at once** — a *search and filter strip*
(Status, Search by, Search, Clear) **and** an *action row* (Edit,
Inactivate, Activate, Delete, Save / Cancel, and the destructive set).
Under this proposal it keeps the first and sheds the second:

| | today | proposed |
|---|---|---|
| Search, filter, partition | Operator actions card | **the search box card** |
| Row-level actions | Operator actions card | **an action row under the selected rows** |

Each job gets a place, and the row actions sit next to the rows they act
on rather than in a card above the table — which is the same argument
19L.1 made for marking a selected row, applied one level up.

**A requirement, not an open question: the Validate deep links must
survive.** Validate's *Fix on … ↗* links land on a Setup page at a row
anchor, and the Setup coverage matrix links in the same way. The author
has stated this is to be preserved, so it moves out of the open
questions and into the requirements: a consolidated page must still be
addressable at *this roster, this row*.

**What the two consolidations leave in the session nav.** Measured
against the shipped nav at `453546c4` — `session_top_nav.html` carries
**13 destinations**: Session Home, then a **Setup** group (Reviewers,
Reviewees, Relationships, Observers, Instruments, Email Template) and an
**Operations** group (Assignments, Validate, Previews, Invitations,
Responses, Extract data).

The author's target:

> Home · Rosters · Instruments · Email Template · Assignments · Validate
> · Monitoring · Data Extract

**Eight.** The arithmetic holds: four roster pages become one (−3) and
three Operations pages become one (−2), 13 − 5 = 8.

Two consequences worth naming because the list makes them rather than
states them. It is a **flat list**, so the Setup / Operations grouping
disappears — arguably the point, since eight items may not need
grouping, but it is a change to the page chrome and not only to the page
count. And the last item is written **Data Extract** where the app says
**Extract data**; recorded as a possible rename rather than silently
adopting either spelling.

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

### A first constraint — mark the roster being worked on, visually

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

**Nothing in the app did this when this entry was written** — checked at
`496cc183`, not assumed, and confirmed by the author: *the lobby does
not, beyond the check box.* The expander tinted its own injected panel
and applied **no class whatever to the source row**, so the lobby's
entire row-level selection signal was the checkbox's own checked state —
a ~13px mark at one end of a full-width row.

**That is no longer true, and the change came from this paragraph.**
Segment 19L Items 1 and 2 marked the selected row, and the lobby now
carries a *bracket*: `--selected-bg` as a 6px inset rail at **each** end
of the selected row, carried through the injected panel, whose cell also
fills with `--selection-panel-bg`. Re-checked at `38110b0f`, not recalled.

*Three paragraphs here argued the old state in the present tense for
some hours after it stopped being the state, beneath a later paragraph
that already named the bracket — the correction reached the sentence it
was written in and no further. Corrected 2026-09-12 on the author's
question, which is the check that caught it.*

So a selected-row visual state is **no longer new work**, and the
argument moves rather than collapses. What has to be decided is
**whether the lobby's bracket transfers**: it was designed for one wide
row in a tall table of *like* things, where the panel names a count and
the operator is choosing among sessions. A Rosters index is four *unlike*
things, one of the actions is Clear all, and the row can sit above a tall
panel or scroll off. Those are the conditions the bracket was not
designed against, and its own open questions — a scattered selection, a
lone row whose panel has scrolled away — are live for exactly that
reason.

The author's view was that the lobby's own marking wanted improving too,
**separately** — and it since has been, as Items 1 and 2 of
`guide/segment_19L_ux_refinements.md`, which is why it is not an entry in
this file. It stood on its own, and this entry never acquired the
dependency.

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

### A second constraint — strict gating on one roster at a time

**Set by the author, 2026-09-12.** The index and everything below it are
gated together: *"there should be a strict gating between the roster
index and the table such that you can only work on one roster at a time.
For instance, if Reviewers is selected, then, only the Reviewers row in
the index may be edited, only the Reviewers preview table can be shown,
and only Reviewers rows can be searched for, partitioned, or edited. To
jump to work on Reviewees, for instance, you need to select Reviewees in
the index."*

**This makes the page a mode, not a dashboard**, and that is the whole
of it. The index is a *selector* that happens to summarise, not a
summary you can act on in parallel. At any instant every control on the
page — the editable index row, the preview, the search box, the
partition controls, the row-level action row — belongs to one named
roster, and the others are not merely unselected but **unavailable**.

**It generalises the rule the refinement already set.** *"Only one
roster's preview is open at a time"* becomes the special case of a rule
that now covers editing, search, partition and row actions too. Nothing
above is contradicted; it is widened.

**It is a stronger answer to the Codex objection than marking alone.**
That objection is that a generic roster abstraction hides
audience-specific behaviour — that a reviewee is not a reviewer and a
shared surface can make them look interchangeable. Visual marking says
*which* roster you are in. Gating removes the moment when the question
could arise: there is never a state in which the page is showing, or
accepting input for, two rosters at once. **Marking answers the question;
gating means it is never ambiguous enough to need asking.**

#### What it settles, and what it opens

**It weakens the pressure on open question 1**, though it does not close
it. If only one roster is ever workable, the index no longer has to be a
working surface, so it does not obviously have to carry *"all rosters and
their columns"* as the original sketch put it — enough to **choose**
between them (name, count, status, when last changed) might be the whole
job, and the column-faithful view is the preview's. *That is an
observation, not a decision: the sketch is the author's and says
columns.* Worth settling deliberately, because the ragged-versus-union
problem mostly evaporates if the index is a chooser.

**It collapses two selections into one, and that needs confirming.** The
sketch has *select to edit* and *select to preview* as two independent
affordances. Under strict gating there is one **active roster**, and
edit and preview read as two things you can then do to it — not two
separate selections that could disagree about which roster is live. If
they really are two selections, the gating has to say what happens when
one names Reviewers and the other Reviewees.

**The active roster has to live in the URL.** Two requirements converge
on this:

- The Validate deep links — already a requirement above — must land on
  *this roster, this row*, which under gating means the link must set the
  active roster, not merely scroll.
- **Four pages give an operator two browser tabs for free**; one gated
  page does not, unless the selection is addressable. Comparing Reviewers
  against Relationships side by side is possible today and would quietly
  stop being possible. *This is a real cost of the consolidation that the
  rationale does not mention, and the URL is what pays it back.*

**Unsaved work at the moment of switching is the sharp boundary.** If
the Reviewers edit row is open and dirty and the operator selects
Reviewees, the page must discard, block, or prompt. Four separate pages
cannot lose work this way — a navigation either warns or does not apply
— so a gated single page **introduces a failure mode the current design
does not have**. Whichever way it is answered should be answered on
purpose.

**And what is active on arrival?** Nothing selected, so the first action
is always a choice; or a default roster, which risks acting on the wrong
one. The first is safer and costs a click; the second is faster and is
how the wrong-roster mistake starts.

#### The interaction, refined — 2026-09-12

The author, settling three of the questions above and adding a second,
inner gate:

> Active roster in URL is fine. Nav away from uncommitted edits should be
> treated as cancellations, with warning (analogies from Instrument
> cards). […] you select which roster to work on. Doing that makes the
> corresponding search card and table show below. However, to access the
> friendly label edit, you should click on an "Edit" button. When
> metadata row is being edited, you can't also do other roster actions
> (e.g., attempt to do a search or select a table row); navigating away
> to another session page counts as a discard (with warning).

**So there are two nested gates, not one.** The outer gate is the active
roster; the inner one is edit mode. Selecting a roster is cheap and
opens the search card and the preview table. Editing roster metadata is
a **mode you enter deliberately**, by a button, and while you are in it
the rest of that roster's surface is unavailable too.

**This answers open question 5 better than either option it offered.**
That question asked whether *select to edit* and *select to preview* are
one selection or two. The answer is **neither**: there is one selection —
the active roster — and edit is a mode you can then enter. Selection and
editing are different kinds of act, which is why treating them as two
selections felt awkward.

**And it answers open question 3**: a switch that abandons uncommitted
edits is a cancellation, warned about rather than silently applied.

#### What the Instrument-card analogy does and does not supply

Checked at `04323d44` rather than recalled, because the analogy carries
most of the design and **not the part that sounds hardest**.

**The gating half already ships, and is a close match.** The Instruments
page holds per-instrument edit state as **`?editing=<id>` in the URL** —
so only one instrument is editable at a time, which is the same
one-at-a-time rule one level down — and blocks everything else with
**`inert`** on `data-lock-region` containers (22 uses in
`instruments_index.html`), plus an opacity fade as the visual cue. Its
own comment: *"`inert` blocks every interaction below (clicks, focus,
native HTML5 drag); the opacity fade gives the visual cue that the band
is view-only until Edit is engaged."* That is precisely *"you can't also
do a search or select a table row"*, already built.

It also means **the two URL decisions are one decision**. The active
roster is in the URL (settled above), and if edit mode follows the
Instruments pattern it is in the URL too — which is what makes
"navigating away discards" true rather than aspirational: there is no
client-side edit state to lose, because the server renders the mode.

**The whole analogy ships. There is no gap.** This paragraph has now
been wrong twice, in opposite directions, and both versions are described
here rather than quietly replaced.

*First version:* "the warning half does not exist anywhere in the app."
*Second version, after the author sent a screenshot of the Instruments
page's unsaved-changes confirm:* corrected to say the in-page confirm
ships and **only leaving the page** is unguarded. *That was still wrong.*
The author sent a second screenshot — the browser's own **"Leave site?
Changes you made may not be saved."** — which is a `beforeunload` dialog.

What actually ships, read at `04323d44`:

| piece | where |
|---|---|
| **Lock / Save / Cancel** on the card | `instrument_action_row` |
| **dirty tracking** — Save starts `disabled`, enables when dirty | the Save button's state is the signal |
| **confirm on Lock while dirty** | `newModelTryLock(card)` |
| **collapse ⇒ lock** runs the same confirm | one function, two callers |
| **switching while dirty is blocked** | `newModelUnlockClick` — *"a dirty one blocks (the operator must Save or Cancel it first); a clean one is locked silently"* |
| **nav-away guard** | `instruments_index.html:3737`, Segment 18R Item 2 PR 2 — `beforeunload`, firing only on `[data-instrument-dirty="true"]` |
| **deliberate navigation excluded** | `window._newModelIntentionalNav`, set by Save's submit and Cancel's reload |

That last row matters: `spec/reviewer-surface.md` lists *"a `beforeunload`
listener that prompts only when dirty, skipping intentional-discard
controls"* under **what lands later**. On the operator side it landed in
18R. **The design that spec defers is already proven on another surface.**

So the author's ask — Save and Cancel on the friendly-label edit, a
warning on locking without saving, a warning on navigating away — is
**entirely a re-house**. The scoping principle is satisfied with nothing
left over, and the earlier suggestion here of `inert`-ing the other index
rows was inventing a worse substitute for a mechanism that was already
built and already refined.

#### How the error was made, since checking was done and was not enough

The grep that produced the first version was:

```
grep -rn "beforeunload" app/ spec/ docs/ | grep -v Binary
```

The only match in `app/` is in `instruments_index.html`, which **`grep`
classifies as binary** — one literal NUL byte at line 2048, inside a
JavaScript `.join()` separator. For such a file grep prints *"Binary file
… matches"* instead of the line, and **the `| grep -v Binary` filter,
added to tidy the output, deleted exactly that.** The command then
reported nothing, and "nothing" was written up as a finding.

*The failure is not an unchecked assumption. It is a check whose
output-tidying step removed the only evidence that could have falsified
it* — which is worse, because it returns a confident negative rather than
a silence.

**The rule this repo now has to carry:** `instruments_index.html` is its
largest template and greps against it return nothing unless `-a` is
passed. **A negative grep result is not evidence of absence here without
`-a`.** The single NUL could also just be written `'\u0000'`, which is
identical to the engine and would make the file text again — small enough
to be worth doing for the greps it would stop swallowing.

**A vocabulary collision to settle before this is built.** The author's
word is *"Edit"*, and the roster pages do ship an **Edit** button today
(`session_reviewers.html`, `session_reviewees.html`) — but it is
**row-level**, sits in the Operator actions card this proposal splits
apart, and is disabled until rows are selected. A roster-level *Edit* on
the same page would mean two buttons of that name at two scopes.
Meanwhile the closest analogue — the Instruments card, which is also
card-level metadata — **deliberately went the other way**: its Wave 4
comment records *"Edit / Cancel retired in favour of a Lock / Unlock
toggle"*, modelled on Quick Setup's footer. Recorded as a question
rather than decided: the author said Edit, and the app's most recent
decision at this exact scope said Lock / Unlock.

#### The controls, specified — 2026-09-12

The author, answering open questions 4 and 6 and setting out the control
set. *"Individual row" here means a row in the preview table, confirmed
by the author.*

**Q4 — nothing is active on load.** The first act is always a deliberate
choice of roster.

**Q6 — Lock / Unlock, not Edit.** Which also resolves the collision that
made it a question: the row-level **Edit** keeps its name, and the
roster-level control takes the vocabulary the Instruments card already
uses at this exact scope.

**The index row carries two controls**, and they stage the work:

| control | state | what it does |
|---|---|---|
| selection checkbox | one roster at a time | shows that roster's search card and preview table below; activates its Unlock |
| **Unlock** | inactive until the checkbox is ticked | reveals the roster-level action row |

**The roster-level action row**, revealed by Unlock and hidden again by
Lock: edit the friendly labels (**except Observers**), delete all data in
the roster, upload a replacement CSV, download the current one. The
guarding checkboxes the first constraint describes still apply to the two
destructive ones.

**In the preview table, arity differs by action**, and the split has a
reason worth stating so it does not later look arbitrary:

- **Edit column values — one row at a time.** Editing is data entry
  against *this* row's values; two rows have different ones.
- **Flip status active / inactive, or delete — several rows together.**
  These are uniform operations; applying one to twenty is the same act
  twenty times.

**That rule is not new — it is exactly what ships today**, checked at
`04323d44` in `session_reviewers.html` rather than recalled:

```js
setBtn(editBtn, n !== 1);        // Edit needs exactly one row
setBtn(inactivateBtn, n === 0);  // status flips need at least one
setBtn(reactivateBtn, n === 0);
```

So the consolidation **preserves the operator's existing muscle memory
here rather than asking for relearning**, and the rule already has tests
and a spec entry. Worth knowing: it is one of the few parts of this idea
that costs nothing to carry across.

**"Except Observers" is also a shipped fact, not a new exception.**
`spec/setup_pages.md` lists the friendly-label editor as Reviewers and
Relationships (a 3-cell row) and Reviewees (a 2-row stacked grid);
`session_observers.html` has no label editor at all. **This is open
question 2's first named, concrete instance** — the per-roster divergence
that question is about is no longer hypothetical, and the consolidated
design has to carry at least this one on day one. A shared row that
renders three label editors and one blank is the shape to avoid.

**One small divergence from the Instruments analogy, worth a deliberate
call.** The author's rule is that the action row *does not show* when
locked; the Instruments page keeps its gated region in the DOM and
neutralises it with `inert` plus an opacity fade. Hiding avoids the
"why is this greyed out" question; `inert` keeps the page height stable,
which is the reflow concern 19L.2 took seriously one level down. Hiding
is probably right here — an absent row has nothing to explain — but the
page will grow on unlock, and the Unlock button should not move under
the pointer that just clicked it.

#### The index columns, and where the exceptions live — 2026-09-12

**Q1 — the index shows name, count, status and last updated. Nothing
else.** So the index is a chooser, as the gating constraint implied, and
this **supersedes the sketch's *"all rosters and their columns"***. The
column-faithful view is the preview's job. The ragged-versus-union
problem does not need solving; it needed dissolving, and gating dissolved
it.

*Three of those four are free; the fourth is not.* Checked at
`04323d44`: **none of `Reviewer`, `Reviewee`, `Observer` or
`Relationship` carries a `created_at` or `updated_at`, and there is no
timestamp mixin.** So *last updated* is not derivable from the rosters —
it needs either a migration across four tables or a query against
`audit_events`, which is a log rather than an index. Under the scoping
principle above that is the one index column that is not a re-house, and
it should be priced before it is drawn.

*And "status" wants defining at the roster level.* Status is a **member**
attribute — a reviewer is active or inactive; a roster is not. So the
column is presumably a summary, at which point it may be the same column
as **count** (*"12 active of 15"*) rather than a second one.

**Q7 — checkbox, and the question it was conditional on has a firm
answer.** *"Unless there's a way to unselect a radio"*: **not natively.**
Clicking a selected radio does not clear it, and a radio group has no
native none-affordance. Clearing one takes JavaScript, and click-a-
selected-radio-to-clear is an interaction nobody expects. Since Q4 makes
*nothing selected* both the initial state and one the operator returns to
by un-ticking, the checkbox is the control that can express it. It also
avoids introducing a control type this app has never used — **there is
not one `type="radio"` in any template today.**

**Q2 — the exceptions live in the action rows, because the action rows
are already per-roster surfaces.** Observers diverges twice, and each
divergence lands in the row that owns that scope:

| scope | Observers differs by |
|---|---|
| roster-level row (behind Unlock) | **fewer actions** — no friendly labels to edit, so that control is simply absent |
| row-level action row | **one more action** — the **Cohort match rule**, edited for one or more selected observers |

That is a better answer than the three this entry had been carrying
(a third mode, a per-roster extras slot, or Observers staying separate):
**no new mechanism is needed at all.** A per-roster action row renders
the actions that roster has. Fewer for one, more for another, and the
shape is the same.

**Moving rule construction into the row-level action row is the part that
earns it.** The rule is per-observer (`Observer.cohort_rule`), so it
belongs beside the observers it applies to, which is the same argument
made for row actions generally and for marking a selected row one level
down.

*It does bend the arity rule just set — edit one row at a time — and the
bend is consistent with that rule's reason rather than an exception to
it.* Column-value editing is one row at a time because two rows hold
different values. Applying **one** cohort rule to several selected
observers is a uniform operation, like flipping status: the same act,
several times. So the rule reads: **per-row values, one row; uniform
operations, many rows** — and the cohort rule is the second kind.

### A candidate mechanism — the lobby's row expander

**Proposed by the author, 2026-09-12:** take a leaf from the session
lobby. *Select to edit* fans the selected row out — a panel below it
carrying the edit / delete / upload-to-replace affordances — in a visual
state where the relevant roster row is clearly marked out.

**What the lobby actually does** — read at `496cc183` rather than
recalled, and re-checked at `38110b0f` after 19L.2 changed part of it:

- A `<template id="single-session-expander">` is cloned and injected as a
  full-width `<tr class="session-expander session-expander-bracketed
  session-expander-single">` **below the selected row**, `colspan` across
  the table. (The middle class is 19L.2's opt-in. **19L.3 gave the
  archived page the same class and the same row marking**, so both pages
  now bracket a selection identically.)
- The injected `<td>` took `background: var(--surface-muted)` — a
  distinct fill was the whole of its visual separation. **Since 19L.2 the
  lobby's panel instead carries `--selection-panel-bg` plus a rail at
  each end**, the same pair the selected row carries, so the panel and
  the row it acts on read as one bracketed object. The bare
  `.session-expander` rule still sets `--surface-muted`, which is now the
  fallback for any page that does **not** opt in — **as of 19L.3 that is
  no page**: the archived sessions page took the class and the marking
  too.
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
interaction that has been proven in use** — still true at `38110b0f`:
the template comment stands and the Delete buttons still ship disabled.
Worth knowing before it is cited as a solved problem.

The question this paragraph used to end on — whether a `--surface-muted`
fill alone reads as *"this panel belongs to **that** row"* once the panel
is tall — **the lobby has since answered for itself, in the negative**.
That is what 19L.2's rails are for. A Rosters version inherits the
answer rather than having to re-ask it.

**What the mechanism has going for it**, stated plainly: it keeps target
and action adjacent — the affordances are literally attached to the row
they act on, which is a stronger spatial claim than a heading elsewhere
on the page — and it reuses a pattern the operator will already have met
in the lobby, which is the same argument the consolidation itself rests
on.

### Open questions

Not answered here; recorded so they are not rediscovered.

1. ~~**Does the top *index* table show columns per roster, or the
   union?**~~ **Answered 2026-09-12: neither — name, count, status and
   last updated only.** The index is a chooser; the column-faithful view
   is the preview's. Two riders, both in "The index columns, and where
   the exceptions live": no roster model carries a timestamp, so *last
   updated* is the one column that is not a re-house; and *status* is a
   member attribute, so at roster level it may be the same column as
   *count*.
2. ~~**Where do the per-roster exceptions live?**~~ **Answered
   2026-09-12: in the action rows, which are already per-roster
   surfaces.** Observers renders one fewer roster-level action (no
   friendly labels) and one more row-level action (the Cohort match
   rule, moved beside the observers it applies to). **No new mechanism
   is needed** — which is a better answer than the three candidates this
   question had been carrying.
3. ~~**What happens to unsaved work when the active roster changes?**~~
   **Answered 2026-09-12: a cancellation, with warning.** The warning is
   the part that does not exist yet — there is no `beforeunload` guard
   anywhere in the app — but a design for one is already deferred in
   `spec/reviewer-surface.md`, so two surfaces would want it and it
   should be built once. See "What the Instrument-card analogy does and
   does not supply".
4. ~~**Is anything active when the page first loads?**~~ **Answered
   2026-09-12: nothing.** The first act is always a deliberate choice of
   roster. The click it costs is the point — it is the click that stops
   the wrong-roster mistake.
5. ~~**Are *select to edit* and *select to preview* one selection or
   two?**~~ **Answered 2026-09-12: neither.** There is one selection, the
   active roster, which opens the search card and the preview; edit is a
   **mode** entered afterwards by a button, which gates the rest of that
   roster's surface while it is open. The question offered two options
   and the answer was a third — selection and editing are different kinds
   of act, which is why framing both as selections felt awkward.
6. ~~**Is the roster-level control called Edit, or Lock / Unlock?**~~
   **Answered 2026-09-12: Lock / Unlock**, matching the Instruments card
   at the same scope. The row-level **Edit** keeps its name, so the
   collision that made this a question does not arise.
7. ~~**Does the index use checkboxes or radios?**~~ **Answered
   2026-09-12: checkbox.** The condition it was put under — *"unless
   there's a way to unselect a radio"* — resolves firmly: **not
   natively**, and clearing one takes JavaScript plus an interaction
   nobody expects. The checkbox is the control that can express the
   *nothing selected* state question 4 made the default, and the app has
   never used a `type="radio"` anywhere.

**Nothing left open here.** Abandoning an unlocked roster edit was
recorded as an open tension twice — first against the scoping principle,
then narrowed to "only leaving the page is unguarded". **Both were
wrong**: Save / Cancel, dirty tracking, the confirm on Lock, the block on
switching while dirty, *and* a `beforeunload` nav-away guard all ship on
the Instruments page, including the intentional-navigation exclusion that
`spec/reviewer-surface.md` still lists as future work. See "What the
Instrument-card analogy does and does not supply" — which now also
records why two greps missed it.

**Also worth applying to the scoping principle above**: this entry's ask
is a re-house with **no** new mechanism, which is a stronger position
than the entry claimed for itself at any point today.
