# Group-level inclusion and exclusion by members' tags

**Opened:** 2026-10-18 · **Status:** deferred idea, unplanned (author,
2026-10-18) · **Lift trigger and ledger entry:**
`guide/deferred_consolidated.md`, Part A, "Assignment rules" ·
**Related:** `spec/instruments.md` (Band 1), `spec/assignments.md`,
`guide/pair_context_tags_further_clarify.md`

A record of an idea and the shape it would likely take, not a plan:
there is no PR ladder, and nothing here is ruled. If it is lifted, it
becomes a plan in the shape of `guide/segment_plan_template.md`.

## The idea

On a **Group** instrument (Link 3, unit of review Group), the operator
forms groups as usual, then includes or rules out **whole groups** by
what their members carry:

- a group is **included** if at least one member has a given tag or tag
  value;
- a group is **ruled out** if at least one member has it.

The tag can be any of:

- a **reviewee** roster tag of a member;
- a **reviewer** roster tag of a member, where groups contain people who
  are also reviewers, as in peer review;
- a **relationship (pair) tag** on the pair between the reviewer and a
  member, for example a conflict of interest with any one member ruling
  out the whole group.

## Why the card cannot say it today

- Links 1 and 2 judge one reviewer, one reviewee or one pair, **before**
  groups form. A Link 2 rule on a member's tag drops that member from
  the group, not the group.
- A Link 2 relationship-tag `IS` keeps pairs one by one, so it is
  refused beside Group. `IS NOT` on a Group instrument drops only that
  member's row. That was deliberate (`guide/archive/assignment_rule_clarify.md`
  Item 2): a pair joins two individuals, not a reviewer and a group.

## The two jobs (author, 2026-10-18)

The card is being asked to do two different things:

1. **Normal formation:** Links 1–3 decide who reviews whom and how the
   groups form.
2. **A special inclusion or exclusion**, applied on top of that
   formation.

Running both through the same Link rules is what blurs them.

## Likely shape

A separate **Exceptions** block on the Band 1 card, applied after the
Links:

- each rule has an **action** (Include / Exclude), a **tag** (roster or
  relationship) with `IS` *v* or `IS FILLED`, and a **scope**: *this
  pair*, or, on a Group instrument, *the whole group* (any member
  matches);
- the result is **formation + includes − excludes**, and an exclude wins;
- the order is formation, then groups, then exceptions, so no Link-level
  Group guard is needed.

## Open questions, if lifted

1. **Does Include add or narrow?** "Impose a pair" reads as *add*: a pair
   or group the Links did not form. Today's Link 2 pair-tag `IS`
   *narrows*.
2. **"Only these pairs" needs an empty formation.** Either a "No one"
   state on the Links, or "all Links Not set plus an Include means
   nothing but the includes".
3. **Do relationship tags leave the Links altogether?** Then
   `guide/pair_context_tags_further_clarify.md` Item 1, which keeps them
   in Link 2, would be superseded or reworked. Whichever builds first
   should say so.
4. **Self-review.** How a whole-group include meets the instrument's
   self-review toggle and the exclude-self-reviews chip.
5. **Generate and staleness.** The exceptions must run inside Prepare /
   Generate and the reconcile stamp, and so must the group-clear rules
   that run when a group's membership changes.
