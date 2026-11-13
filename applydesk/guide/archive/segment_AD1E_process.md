# Segment AD1E — ApplyDesk: the Process page, a stack of stage cards

**Opened:** 2026-11-13 · **Theme:** Process built as Form is: the exercise's timeline as a stack of stage cards, each holding the form, or gates, and perhaps an outcome, with their dates, rules and emails; every move working in the browser, nothing saved; the builder first, Preview after · **Related:** `applydesk/guide/todo_master.md` (rulings 13–15), `applydesk/guide/archive/segment_AD1B_form_builder.md` (the Form page this repeats), `applydesk/guide/segment_AD1D_chrome.md` (the placeholder this replaces), `applydesk/spec/applications.md` ("The Form page")

## Opportunity

Process is a placeholder (AD1D): a read-only table per stage of what `applydesk/stages.py` holds. Ruling 15 says how it should work: "Process is a stack of stage cards, as Form is of question cards: a new exercise starts with one stage card offering the form and an outcome; stages are added, moved and deleted, but the last one cannot be deleted." Every rule Applications applies (ruling 13) is set here, and nothing on screen sets one yet.

## Decision

**Process sets up the whole flow; the other Setup pages flesh out its nodes** (author, 2026-11-13): the operator lines up stage cards until the exercise's process is complete, then goes to Form, Gates and Emails for the detail of each node. So a stage card holds what places a node in the flow (its name, dates and milestones, what it holds, its rules) and links out for the rest (the form's questions, a gate's panel, an email's text).

**The Form page's pattern, with stages for questions** (author, 2026-11-13: "model on Form"):

1. **Layout.** Stage cards in timeline order, the Outline beside them in the right third, kept in view; below the cards on a phone. *Save* at the Outline's foot, disabled until AD2.
2. **A stage card**: its name (placeholder *Stage N*) and From–To dates at the top; then what it holds, each an **item** inside the card, in this order:
   - **Form** (one stage at most): when it opens and closes, a link to the Form tab, and its emails (the receipt, reminders).
   - **Gates** (one or more): name, how it runs (*A Review Robin session* or *Results entered here*), its result's measure, and its **entry rule**; its panel is on Gates, linked.
   - **Outcome** (at most one): name, its values, due date, its **rule** (with the combined result's weights, when it reads one), what its release does (to whom; which email from Emails — *since ruling 16, only to whom: Emails lists the templates that makes owed*).
3. **Collapsed**, a card shows its name, dates and a summary (`Form · opens 1 Sep, closes 15 Oct` / `2 gates · Outcome: Shortlist for interview`); cards load collapsed, a lone card open.
4. **Buttons** along each card's foot, flush right, as Form's: *Replicate*, *+ Stage*, *Delete* (disabled, with a reason in its title, on the last stage). Inside the card: *+ Gate*, *+ Outcome*, *Form* — each disabled with its reason where ruling 15 forbids it (a gate beside the form, a second outcome, a second form).
5. **Reordering** by a card's handle, dragged or with ↑ ↓, as Form's.
6. **The Outline**: each stage by name and dates, its items beneath, the counts (stages, gates, outcomes), and any problem (a rule reading a later outcome, a gate a rule names that was deleted).
7. ~~**Preview** shows the Workflow card as it would be, built from the cards on screen.~~ Held until the builder is complete (author, 2026-11-13: "hold off the Workflow card first; we complete the builder first").
8. ~~**Announcements** stay a card at the foot.~~ Removed: not part of the flow; their equivalent is part of the exercise's own setup (author, 2026-11-13). **Milestones fold into the stages**: a stage's dates and an outcome's due date carry a *Shown to applicants* switch. (The outcome's became its per-audience *Update timeline* at iteration 1; the stage's stays.)

**Rejected:**
- **A table of stages** (the placeholder): no room for rules, and nothing to reorder by hand.
- **Panels on Process**: a gate's roster stays on Gates (ruling 14); Process links to it.
- **A free-form rule language**: the rule editor offers ruling 13's conditions only, joined by AND.

## Semantics

- **Ruling 15's shape is enforced as it is edited**, mirroring `stages.problems`: one form at most, anywhere; never the form and a gate; one outcome at most per stage. An empty stage is allowed while it is set up and shown as such.
- **Numbering** of gates and outcomes follows the timeline and changes when a card moves; the Outline and Applications' headers follow.
- **A rule names columns by key**, not number: moving a stage keeps its rules' meaning, and a rule left reading a later outcome, or a deleted gate, is named on its item and in the Outline.
- **An outcome's scope** is the gates since the previous outcome (ruling 13); its weights list only those, and moving a card can change them, which the item says.
- **A blank exercise** shows one stage card, *Stage 1*, holding the form, open.
- **Nothing is saved.** A reload restores the sample, as Form's.

## Judgment calls — decided

- **The page renders on the server, moves happen in one inline script**, as Form's; the cards are drawn from `stages.plan_of` so Process, Applications and the Workflow card agree on load.
- **A collapsed form reads *Form*, not its dates** (2026-11-13): the form opens and closes on its stage's dates, already in the head beside it; Decision 3's example would say them twice.
- ~~**Emails are chosen, not written, here**: an outcome or the form picks a template by name from Emails (ruling 14); a missing one is offered as *Not set up*.~~ Superseded by ruling 16 (2026-11-13): an item ticks whom it emails; Emails lists every template owed.

## Blast radius (measured)

Taken 2026-11-13 at `fb6e75f07`.

| What | Count | Command |
|---|---|---|
| The Process partial replaced | 1 file, 51 lines | `wc -l applydesk/templates/applydesk/operator/_process.html` |
| The Form page it models | 474 lines | `wc -l applydesk/templates/applydesk/operator/_form.html applydesk/templates/applydesk/operator/_form_cards.html` |
| The stages model it edits | 433 lines | `wc -l applydesk/stages.py` |
| Page tests naming Process | 11 lines | `grep -c "process" applydesk/tests/test_pages.py` |

## Status

Closed 2026-11-13. The spec is `applydesk/spec/applications.md` "The Process page".

- **The ladder held** (#3852 plan, #3854–#3857 rungs 2–5), plus two iterations at the author's browser check (#3858, #3859). Announcements left at rung 3 (their equivalent is the exercise's own setup); milestones live on the stage cards; Preview stays held.
- **Iteration 1** (#3858): an outcome's release is set per audience, *Applicants* and *Panel evaluators*, each *Update timeline* and *Send email*, replacing *Shown to applicants*, *Email to applicants* and *Tell reviewers*; the Outline's entries open and go to their card.
- **Iteration 2, ruling 16** (#3859): Process ticks whom an item emails and picks no template; Emails lists every template that makes owed, named for its stage, *Written* or *Owed*; an owed email holds back an outcome still to release. This supersedes the judgment call that items pick a template.
- **Decisions confirmed at build:** a rule names columns by key, so moving a stage keeps its meaning; a rule left reading a removed, out-of-scope or later column keeps it and is flagged on the item and in the Outline, never silently rebound; open editors redraw on every structural change; a replica's rules and weights read its own gates; a new gate takes what is left of 100.
- **Reads: three.** One cumulative `diff-reviewer` read on rungs 2–5 (base `e7e0231b8`, main before rung 2) found eight defects in the rule editor, all fixed in rung 5 (*Then*/*Otherwise* redrawn away on click, flagged rules rebound, focus lost, replica keys, the server's problems wiped, silent weights, rule-text edge cases). Codex then found two more there (open editors not following values or structure), fixed. Each iteration took its own read: #3858's found a new outcome claiming another's email; #3859's found a released outcome reading *Not ready*. Both fixed before merge.

## PR ladder

1. **Plan** (this file), its README and roadmap rows.
2. **The scaffold.** Stage cards from the sample, each with its items, collapsed summaries, the Outline, Announcements, *Save*; every control drawn, inert. Tests: the cards follow the sample in order; a blank exercise shows one open *Stage 1* holding the form. Must not touch Applications or the Workflow card.
3. **Cards that move.** Expand and collapse, name and dates, *+ Stage*, *Replicate*, *Delete* (not the last), reordering, *Form* on or off within ruling 15; the Outline follows. A Chromium test for each.
4. **Gates and the outcome.** *+ Gate*, *+ Outcome*, their fields, removing one; numbering follows the timeline. Chromium tests.
5. **Rules.** Each gate's entry rule and the outcome's, from ruling 13's conditions, joined by AND; an outcome's weights over its scope; a rule's line as Applications' header shows it (`rule_text`); a rule reading a later outcome or a deleted gate named. Chromium tests. Last build rung: `diff-reviewer` reads the cumulative diff.
6. ~~**Preview**~~: held until the builder is complete (author); a later rung or segment.
7. **Iteration rungs**, as the author's browser checks ask.
8. **Close.**

## Definition of done

- Process shows the model exercise's four stages as cards, in order, with their items and rules (test).
- In Chromium: a stage added, replicated, moved and deleted (not the last); the form moved between stages and refused beside a gate; a gate and an outcome added and removed; a rule edited and its line updated; a broken rule named (tests).
- The author has used the page locally and approved it.
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD1E` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- **Preview**: held until the builder is complete (author, 2026-11-13); what it shows is decided then.
- **Milestones**: inside the stage cards (author, 2026-11-13: "stage milestones belong inside the stage cards"), as Decision 8 has it.
- **What a gate before the form evaluates** (AD1D's open question): its rows before applications exist.
- **`close_check.py` reads only RRW's `guide/`**: this close is checked by hand.

## Out of scope

- **Saving** (AD2) and **sending** anything: releases, emails and gates sent to Review Robin stay inert (AD6, AD7).
- **Gates' panels** (the Gates page's own segment) and **email templates' text** (Emails').
- **Applications in parts** (ruling 15's next extension): one form stage for now.

## Doc impact

- `applydesk/spec/applications.md` — a "The Process page" section, after "The Form page" (at close).
- `applydesk/guide/todo_master.md` — the AD1E roadmap row (rung 1); deleted at close.
- `applydesk/README.md` — this plan's row (rung 1), moved to the archive's index at close.
