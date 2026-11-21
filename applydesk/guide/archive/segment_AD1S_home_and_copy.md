# Segment AD1S — Apply Desk: Home's timeline for every participant, and leaner copy

**Opened:** 2026-11-21 · **Theme:** the timeline speaks to every participant and carries *Now* itself; the operator pages lose explanations lifted from the spec and rulings · **Related:** `applydesk/guide/todo_master.md` (rulings 46, 64, 68), `applydesk/templates/applydesk/_timeline.html`, `applydesk/timeline.py`

## Opportunity

The author's review of Home on 2026-11-21:
- **The timeline assumes applicants.** It is the part of Home participants may see, and participants are applicants and evaluators alike. Yet it says *You* ("Apply online…"), and the draft note says "what applicants will see".
- **"Now" is only in a line under the timeline.** That line restates "Now: <stage>, until <date>. Next: …", when today already has a marker on the timeline itself.
- ***Operator only* repeats per column.** In the horizontal layout each stage column carries its own label, so the band is labeled four times over.
- **The pages explain themselves at length**, often in the words of a ruling. Details carries "Invitation only hides the exercise from everyone not on its list, direct links included." It also carries "On, evaluators' dossiers redact … (ruling 43)."

## Decision

Two build rungs:
- **Home's timeline:**
  - participant wording;
  - *Now* on the Now stage, with the line under the timeline gone;
  - one *Operator only* label across the horizontal columns.
- **A copy sweep:**
  - the two named lines go;
  - every operator and `/me` template is read for explanations derived from the spec or a ruling, and those are cut to what the page needs.

**Alternative rejected:** fold the copy sweep into the next feature segment. Explanations keep accreting with each segment, so a dedicated pass is the only one that reads them all against each other.

Ruling 68 (who sees each dossier item) is recorded with this plan, but not built here: it waits for the store (AD4, AD5).

## Semantics

- **Participant wording.** The timeline's items name their audience in the third person: the form item's kicker is *Applicants*, not *You*. The draft note says "what participants will see once it is published".
- **Now on the timeline.**
  - The Now stage's today marker reads `Now · until <end>`, or `Now` when the stage has no end.
  - What comes next sits in that stage as a `Next:` item: the outcome due, and its expected date.
  - On Home, the link to the running gate joins the stage's *Operator only* rows.
  - The line under the timeline remains only for a draft (the note above) and for when no stage is under way ("Next: <stage>, from <date>" or "Every stage is done"). The marker cannot carry those.
- **One *Operator only*.**
  - **Horizontal:** a single label spans the columns. Each column's operator rows still start on one shared line, so they align as now.
  - **Vertical:** unchanged, a label per stage. The label sits beside each stage's own rows there.
- **Copy sweep rule.** Keep a line only if an operator needs it to act on the page: what a control does when its effect is not visible, or a consequence they could not otherwise see. Cut citations of rulings, segments or AD numbers, restatements of the control's label, and rationale. Template comments (`{# … #}`) are not copy and stay.

## Judgment calls — decided

- *Now*'s marker reuses the today marker rather than adding a chip, so the stage head keeps the operator's status chip (U2).
- The sweep's removals are listed in its PR, one line each, so the author's browser check can restore any line that was doing work.

## Blast radius (measured)

Taken 2026-11-21 at `6270d1540`.
- Timeline: `applydesk/templates/applydesk/_timeline.html`, plus `applydesk/timeline.py` (`_items`, `next_step`). Callers: `operator/home.html` and `me/exercise.html`.
- Tests naming the timeline's line, *Operator only* or *You*: `applydesk/tests/test_timeline.py` and `applydesk/tests/test_pages.py`.
- Copy that may cite rulings: `grep -rniE 'ruling [0-9]+|\(R[0-9]+\)|segment AD|AD-[0-9]+' applydesk/templates --include=*.html | grep -v '{#' | wc -l` → 166 lines. Most are in comments; four are visible text (`grep -rnE '>[^<{]*ruling [0-9]+' applydesk/templates | wc -l`).
- Muted help lines: `grep -rn 'class="muted[^"]*"' applydesk/templates | wc -l` → 94.

## Status — closed 2026-11-21

**Intended vs done.** Both build rungs landed as planned: Home's timeline in #4101 and the copy sweep in #4102, after the plan and ruling 68 in #4100. The author's browser check of #4101 and #4102 comes later, by the author's choice. It is a follow-up in `applydesk/guide/todo_master.md`, and any line the sweep cut can come back from it.

**Decisions confirmed at build:**
- The Now marker reads `Now · until <end>`. Today's date stays in the line under the card title, not in the marker.
- The stage's first outcome due becomes its *Next:* item where it stands, rather than a copy beside it.
- No separate gate-link row: each gate's operator row already links its page. A duplicate "Under way" row and the running-gate plumbing were dropped at build.
- One *Operator only* in horizontal is the first stage's label on a shared grid row, the others clipped. CSS grid cannot span an unknown column count. Screen readers still read each stage's label.
- The sweep also cut bare segment numbers (AD2, AD4, AD6, AD7) and "(G2)". Unbuilt controls say "… is not built yet".

**Reads.** One cumulative `diff-reviewer` read over rungs 2–3 found:
- a spec sentence describing the dropped row, fixed in #4101;
- three stale spec quotes of the unsaved notes, fixed in #4102;
- Details' two removed lines, flagged as consequences an operator cannot see elsewhere. They stay removed, since the author named them.

The read also noted gaps for the future in the citation test: bare `G2`/`U4` tokens and `data-*` text. None exists on a page today. Codex was clean on every PR. The build agents were told not to use `git stash`, and there was no repeat of AD1R's stash crossing.

**Close.** `spec-writer` brought `applydesk/spec/applications.md` up to the build:
- the Now marker, the *Next:* item, participant wording, and the one *Operator only*;
- "No citations on a page";
- ruling 33's "ruled, not built" note, now pointing at ruling 68.

Its flags needed no change: the spec's own "until AD2" prose is not a UI quote.

## PR ladder

1. **This plan and ruling 68.** AD4's roadmap row reads ruling 68, its open decision on card visibility closes, and AD-64 is struck. Prose only.
2. **Home's timeline:** participant wording, *Now* on the timeline, one *Operator only*.
3. **Copy sweep:** the two named lines, then every template. The last build rung, so the `diff-reviewer` read covers rungs 2–3.
4. **Close.**

## Definition of done

- The timeline's items and notes name no single audience as *you*; `test_timeline` holds it.
- No "Now: …" line under the timeline while a stage is under way; the Now stage carries it.
- In the horizontal layout, exactly one *Operator only* label, its rows aligned.
- No visible text on an operator or `/me` page cites a ruling, segment or AD number.
- The author's browser check of rungs 2–3; until then a follow-up in `applydesk/guide/todo_master.md`.
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD1S` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `applydesk/guide/todo_master.md` entries deleted; plan moved to `applydesk/guide/archive/` + index row

## Open questions

- None open. Ruling 68's three questions were answered on 2026-11-21:
  - a grant opens from a stage;
  - operators see everything;
  - *Next* and the gate link move onto the Now stage.

## Out of scope

- Building ruling 68's grants. It waits for AD4 and AD5, together with AD-69 and AD-93 (`applydesk/guide/ad3_plus_deferred_findings.md`).
- Review Robin's templates.

## Doc impact

- `applydesk/spec/applications.md` — Home's timeline: participant wording, *Now* on the Now stage, the one *Operator only* label; ruling 68 replacing ruling 33's "ruled, not built" note (rungs 1–3, close).
- `applydesk/guide/todo_master.md` — ruling 68, AD4's row, the closed open decision (rung 1); the browser-check follow-up (close).
- `applydesk/guide/ad3_plus_deferred_findings.md` — AD-64 struck; AD-69 and AD-93 point at ruling 68 (rung 1).
- `applydesk/README.md` — the plan's row (rung 1), and its archive row (close).
