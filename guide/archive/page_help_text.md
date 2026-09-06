# Page help text — drafts

**Working drafts of the `<details class="page-guidance">` copy for each
Setup page** (Segment 19E rung 6). Rung 6a shipped the scaffold and
piloted it on Email Template; rung 6b takes the remaining five pages, and
this is where their wording is worked out before it goes into a template.
**RETIRED 2026-09-06.** Both rungs shipped, the wording settled, and this
file did the job it was written for. Read it for the drafting history —
what each page's copy was before the author's revisions, and why each
sentence was chosen — not for what the app says today.

**The shipped copy lives in the six page templates, and nowhere else.**
That is deliberate, and it is this file's own original judgement: a
second place the copy appears to live drifts from the first. Promoting
this file to `spec/` was considered at retirement and rejected for
exactly that reason — it would have made every wording tweak a two-file
edit.

**What outlived it, and where it went.** The parts that were *contract*
rather than drafts — the five rules an edit is held to, the fact each
page's card must carry, the Guide-anchor convention, and the one
sanctioned rule-5 exception — moved to `spec/setup_pages.md` "Shared
body shape" §0, which already owns the scaffold. Nothing below is
canonical; where this file and that spec disagree, the spec wins, and
where the spec and a template disagree, `tests/integration/test_page_guidance.py`
fails.

---

## The rules this copy follows

Five, four from the plan and one from the pilot:

1. **Short.** Two paragraphs. The pilot's copy is the ceiling, not the
   target — an operator opening a disclosure wants the thing they were
   missing, not the page's manual.
2. **Say what the page's own controls do not.** A card labelled "Upload
   Reviewers" already says it uploads reviewers. The guidance earns its
   place by naming the consequence, the constraint, or the thing that
   bites — not by narrating the layout.
3. **Link to the Guide; never restate it.** Each Guide section card
   carries `id="guide-<section key>"`. Links take
   `?return_to={{ request.url.path }}` so the operator lands back here.
   Two copies of the same explanation is the drift this segment exists
   to stop.
4. **Guide vocabulary, verbatim.** "Prepare", "Activate", "Validated",
   "instrument", "assignment" — the Guide's words, so an operator moving
   between the two does not have to translate.
5. **No layout references.** "The card on the right" survives exactly
   until someone moves the card. Name things by their label.

The `<summary>` is fixed in the macro (`What this page is for`) and is
not per-page. A page that genuinely needs different wording is a finding
about the scaffold — raise it rather than working around it.

---

## Shape and placement — decided 2026-09-06

The guidance is a **half-width card**, not an inline disclosure. Closed
it is one line — a chevron and `What this page is for`. Open, the card
grows downwards in place. Width comes from the grid slot each page puts
it in, never from the macro.

| Page | Placement |
|---|---|
| Reviewers / Reviewees / Relationships | `Fields with data` card drops to half width; guidance to its right, same row |
| Observers | Top right, own row above `Cohort match rule` |
| Email Template | Above `Merge tags` in the right column |
| Instruments | `Expand all` / `Collapse all` move into the `Session deadline` card; the vacated card becomes the guidance card |

Placements shipped as a scaffold with placeholder bodies; the copy below
fills them. Two things to judge on the dev slot rather than argue here:
the Observers row leaves an **empty top-left slot**, and an open card may
**stretch its row neighbour** since both grids stretch.

---

## Status

| Page | Guide anchor | Draft | Shipped |
|---|---|---|---|
| Email Template | `#guide-give_access` | below | ✅ copy rung 6a · placement rung 6b |
| Reviewers | `#guide-create_and_set_up` | below | ✅ shipped rung 6b |
| Reviewees | `#guide-create_and_set_up` | below | ✅ shipped rung 6b |
| Relationships | `#guide-create_and_set_up` | below | ✅ shipped rung 6b |
| Observers | `#guide-create_and_set_up` | below | ✅ shipped rung 6b (copy corrected — see below) |
| Instruments | `#guide-create_and_set_up` | below | ✅ shipped rung 6b |

Four of the five remaining pages point at the same Guide section, which
is a signal worth watching: `create_and_set_up` is the Guide's longest
card and it now has to serve as the landing place for four different
questions. If the anchors start feeling imprecise during rung 6b, the fix
is to split that Guide card — a rung 2 correction — not to write longer
guidance to compensate.

**Judged at rung 6b: it holds, narrowly.** Writing the five bodies did
not produce a sentence that wanted a more precise anchor, because each
one links at the *end* of a paragraph that has already said the specific
thing — the link is "there is more about sessions over there", not "the
answer to this is over there". That is the reading under which one broad
card serves four pages. It would stop holding the moment a body needs to
send the operator to a *particular* explanation; the fix then is still
splitting the Guide card, not lengthening the guidance.

---

## Email Template — `session_setupinvite.html` ✅ shipped

**What the page does not say.** Its three tabs let an operator carefully
compose emails the app does not send: Segment 14B is still `Planning`.
Nothing on the page mentions it, and nothing about reviewer access
depends on it.

```html
<p>
  A session has three emails: an <strong>invitation</strong>, a
  <strong>reminder</strong>, and a <strong>confirmation</strong> sent when
  a reviewer submits. Each tab edits one of them for this session only.
  Leave a field blank and the default shown in grey is used; the merge
  tags on the right are substituted when the mail is built.
</p>
<p>
  <strong>Sending is not switched on yet</strong>, so what you save here is
  stored, not delivered. Nothing about access depends on it — reviewers
  reach their work by signing in, and the roster is what lets them in. See
  <a href="/guide?return_to={{ request.url.path }}#guide-give_access">Give
  reviewers access</a> in the Guide.
</p>
```

> Carries one violation of rule 5 — "the merge tags on the right".
> Deliberate: the merge-tag card has no label an operator could match on
> other than its `Merge tags` heading, and "on the right" is how they
> will look for it. Flagged so rung 6b does not read it as licence.

---

## Reviewers — `session_reviewers.html`

**What the page does not say.** Three things. The email address is not
contact detail, it is the identity the app matches a signed-in person
against — the single most consequential cell on the page. Uploading
replaces the whole roster rather than merging into it, and takes the
session's assignments with it. And tags are not annotation: they are what
assignment rules filter on.

```html
<p>
  Reviewers are the people who fill in the form. The
  <strong>email address is the identity</strong> the app matches each
  person against when they sign in — not an address it writes to — so a
  mismatch means that reviewer never sees their work. The three tag
  columns are what assignment rules filter on, so put the attributes that
  decide who reviews whom there (a tutor, a tutorial group).
</p>
<p>
  Uploading a CSV <strong>replaces the whole roster</strong> rather than
  adding to it, and clears any assignments already generated — you will be
  asked to confirm. To take someone out of a running session without
  losing their rows, mark them <strong>inactive</strong> instead of
  deleting. See
  <a href="/guide?return_to={{ request.url.path }}#guide-create_and_set_up">Create
  and set up a session</a> in the Guide.
</p>
```

---

## Reviewees — `session_reviewees.html`

**What the page does not say.** A reviewee's identifier does not have to
be an email — the column is `email_or_identifier`, and an anonymous ID is
legitimate for an analysis-only session. The cost is invisible here: that
reviewee can never be shown their own results, because identity matching
needs an email. Validate raises it as a warning
(`reviewees.unreachable_for_results`), which is late to find out.

```html
<p>
  Reviewees are the people being reviewed. They may be the same people as
  your reviewers — in a peer review, everyone is both. As with reviewers,
  the <strong>email address is the identity</strong> the app matches a
  signed-in person against, and the tag columns are what assignment rules
  filter on.
</p>
<p>
  A reviewee can carry a plain identifier instead of an email if you are
  only collecting data about them. <strong>They cannot then be shown
  their own results</strong> — that needs a real address to match against
  — and the Validate page will warn you. Use an email for anyone who
  should see what was said about them. See
  <a href="/guide?return_to={{ request.url.path }}#guide-create_and_set_up">Create
  and set up a session</a> in the Guide.
</p>
```

---

## Relationships — `session_relationships.html`

**What the page does not say.** The name invites the wrong model. A
relationship is not an assignment: it does not decide who reviews whom.
It attaches *context* to a pair, which an instrument's rule can then
filter on. An operator who expects to build their review here by listing
pairs will be confused when Prepare generates a different set.

```html
<p>
  A relationship attaches <strong>context to one reviewer–reviewee
  pair</strong> — three tag slots describing something true of that
  pairing, such as a shared group or a supervision link. This page is
  optional; a session works without any relationships at all.
</p>
<p>
  <strong>Relationships do not decide who reviews whom.</strong> That
  comes from each instrument's assignment rule, and the pairs appear when
  you Prepare the session. What relationships give you is something for
  those rules to filter on, so a rule can say "only pairs in the same
  group". Both rosters need people in them before a pair can be added.
  See
  <a href="/guide?return_to={{ request.url.path }}#guide-create_and_set_up">Create
  and set up a session</a> in the Guide.
</p>
```

---

## Observers — `session_observers.html`

**What the page does not say.** Why the page exists at all — it is
hidden until observers are enabled, so an operator seeing it has usually
just switched something on and may not remember what it does. And that an
observer with no cohort rule sees **nothing** — an observer can be added,
saved, and left silently blind, with nothing on this page saying so.

```html
<p>
  Observers view collated results <strong>without reviewing anyone</strong>
  — a course leader seeing how a cohort went, say. They are optional, and
  this page only appears because observers are switched on for this
  session. Observers have one tag slot rather than three, and never
  appear in assignments.
</p>
<p>
  Each observer's <strong>cohort match rule</strong> decides which
  reviewees they may see, and <strong>an observer with no rule set sees
  nothing</strong>. Their results page stays empty until a rule is saved. What they see of each response — full,
  anonymised, or summarised — is set per instrument, not here. See
  <a href="/guide?return_to={{ request.url.path }}#guide-create_and_set_up">Create
  and set up a session</a> in the Guide.
</p>
```

> **Checked at rung 6b — the draft was inverted, and the paragraph
> above is the corrected text.** `observer_cohort.observer_has_rule`
> returns `False` when `cohort_rule` is `None` or its `rules` list is
> empty, and `materialize_cohort_assignments` returns `EMPTY_COHORT` in
> that case; `_observer_collation.build_observer_collation_context`
> short-circuits to `cohort_empty=True` on the same test. So the default
> is **no access**, not full access — an observer added without a rule
> sees an empty page. As the draft note predicted, the sentence became
> more important once inverted: "sees everything" is a privacy bug an
> operator would report, while "sees nothing" is a silent failure they
> would never think to look for, which is exactly what page guidance is
> for.

---

## Instruments — `instruments_index.html`

**What the page does not say.** That the instrument decides the
assignments. The rule lives on a band of the instrument card, so an
operator looking for "who reviews whom" does not obviously find it here —
and nothing on the page says that pairs materialise later, at Prepare,
rather than as they edit.

```html
<p>
  An instrument is <strong>one form reviewers fill in</strong>. Every
  session starts with one, ready to use, carrying a rating and a comments
  question. Each carries its own response fields (the questions) and
  display fields (the context a reviewer sees while answering).
</p>
<p>
  Add more instruments when a session needs parallel forms over the same
  people — a group based peer review and an individual based one, for
  instance.
</p>
<p>
  Each instrument carries the <strong>assignment rule</strong> that
  decides who reviews whom for that form. Editing the rule does not
  create pairs — they are generated when you <strong>Prepare</strong> the
  session. See
  <a href="/guide?return_to={{ request.url.path }}#guide-create_and_set_up">Create
  and set up a session</a> in the Guide.
</p>
```

**Revised by the author 2026-09-06**, after reading it on the page. Three
changes, each removing something that competed with the paragraph's own
point:

- *"and the Assignments page is where you check what came out"* went. The
  paragraph is about where pairs come from; naming the page you inspect
  them on sends the reader somewhere else mid-sentence.
- **"Add more instruments when…" became its own paragraph**, and on a
  second pass moved to the **middle**. It was originally buried inside
  the definition, where a reader looking for *what an instrument is* had
  to step over *when to add another*. Pulling it out fixed that; putting
  it second fixed the rest. The card now runs *what one is* → *when you
  want another* → *what each one controls*, which is the order the
  questions arrive in. It also puts the Guide link back where a link
  belongs — at the end of the card, not in the middle of it.
- The example changed from *a peer review and a self review* to **a group
  based peer review and an individual based one**. Mine was the weaker
  illustration: a self review is a different *population*, which the
  reader may reasonably think needs a different session. Two peer reviews
  differing only in their assignment rule is the case that actually needs
  a second instrument — and it points straight at the rule the next
  paragraph explains.

---

## Open questions

- ~~**Does `create_and_set_up` hold up as four pages' landing spot?**~~
  Answered at rung 6b — yes, narrowly, on the reasoning recorded under
  `## Status`.
- ~~**The Observers default.**~~ Verified at rung 6b against
  `app/services/observer_cohort.py`; the draft was inverted and the copy
  was corrected before shipping. See the callout above.
- **Does the Instruments page want two disclosures rather than one?**
  It is the largest Setup page and its assignment-rule band is a distinct
  subject from its field editor. The scaffold assumes one per page. If a
  second is wanted, that is a scaffold change, not a copy change.

## Out of scope

- **Operations-row pages** (Assignments, Previews, Validate,
  Invitations, Responses, Extract data) and **Session Home**. Rung 6 is
  scoped to Setup pages. Validate already ships its own per-issue
  `Why this check?` disclosure, which is the pattern this scaffold
  generalised from; whether the Operations pages want page-level
  guidance too is a Segment 20 question.
- **Per-field `.form-help` text**, which stays as it is. Mechanics for
  one field and purpose for a page are different registers and should
  not merge.
