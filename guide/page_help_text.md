# Page help text — drafts

**Working drafts of the `<details class="page-guidance">` copy for each
Setup page** (Segment 19E rung 6). Rung 6a shipped the scaffold and
piloted it on Email Template; rung 6b takes the remaining five pages, and
this is where their wording is worked out before it goes into a template.

**This file is a drafting surface, not a contract.** The shipped text
lives in the page templates; the scaffold's contract lives in
`spec/setup_pages.md` "Shared body shape" and each page's own spec. Once
rung 6b lands, this file's job is done — it retires to `guide/archive/`
with the segment plan rather than becoming a second place where the copy
appears to live.

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

## Status

| Page | Guide anchor | Draft | Shipped |
|---|---|---|---|
| Email Template | `#guide-give_access` | below | ✅ rung 6a |
| Reviewers | `#guide-create_and_set_up` | below | rung 6b |
| Reviewees | `#guide-create_and_set_up` | below | rung 6b |
| Relationships | `#guide-create_and_set_up` | below | rung 6b |
| Observers | `#guide-create_and_set_up` | below | rung 6b |
| Instruments | `#guide-create_and_set_up` | below | rung 6b |

Four of the five remaining pages point at the same Guide section, which
is a signal worth watching: `create_and_set_up` is the Guide's longest
card and it now has to serve as the landing place for four different
questions. If the anchors start feeling imprecise during rung 6b, the fix
is to split that Guide card — a rung 2 correction — not to write longer
guidance to compensate.

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
observer with no cohort rule sees everything, which is the wrong default
to discover after activation.

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
  reviewees they may see; an observer with no rule set sees every
  reviewee in the session. What they see of each response — full,
  anonymised, or summarised — is set per instrument, not here. See
  <a href="/guide?return_to={{ request.url.path }}#guide-create_and_set_up">Create
  and set up a session</a> in the Guide.
</p>
```

> **Check before shipping.** "An observer with no rule set sees every
> reviewee" is my reading of the cohort-rule default and is **not yet
> verified against `app/services/`**. Confirm it at rung 6b; if the
> default is the opposite, the sentence inverts and becomes more
> important, not less.

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
  question. Add more when a session needs parallel forms over the same
  people — a peer review and a self review, say. Each carries its own
  response fields (the questions) and display fields (the context a
  reviewer sees while answering).
</p>
<p>
  Each instrument also carries the <strong>assignment rule</strong> that
  decides who reviews whom for that form. Editing the rule does not
  create pairs — they are generated when you <strong>Prepare</strong> the
  session, and the Assignments page is where you check what came out. See
  <a href="/guide?return_to={{ request.url.path }}#guide-create_and_set_up">Create
  and set up a session</a> in the Guide.
</p>
```

---

## Open questions

- **Does `create_and_set_up` hold up as four pages' landing spot?**
  See `## Status`. Decided by: whoever writes rung 6b, on the evidence of
  writing it.
- **The Observers default.** Flagged inline above; verify before
  shipping that card.
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
