---
name: segment-plan
description: Write, revise, or close a segment plan or an item within one, in guide/segment_*.md. Use this whenever the user asks to plan a segment, item, feature, refactor, or slice of work; whenever they say "plan", "segment", "item", "PR ladder", "scope this", "spec out the work", or "what would it take to"; whenever a build reveals that an existing plan's intent and what shipped have diverged and the plan needs a status block; and whenever a segment is being closed or archived. Also use it when the user starts describing work in enough detail that a plan is the right artefact, even if they have not asked for one — offer the plan rather than starting to build. Do not use it for the spec itself (that is spec-writer's territory) or for a change small enough that a PR body carries the reasoning (see "When not to write a plan").
---

# Segment plan

A segment plan is the artefact that carries intent into a build and absorbs what the build discovers, so that the spec never has to. It is the day-to-day source of truth for its own slices while the segment is open, and a record of intended-versus-done after it closes. The rule it serves is in `rrw_sdd_in_practice.md` §6.1: **plan on the way in, spec on the way out.**

Read `rrw_sdd_in_practice.md` §5 once if it is not already in context. This skill is the operational form of that section.

## When not to write a plan

Plans scale badly downward. Do not write one for work that is a single PR touching no database schema, no spec contract, and no user-facing surface. Put the reasoning in the PR body and stop. Write a plan when any of these hold:

- the work will take two or more PRs
- it changes a lifecycle, a CSV contract, a route shape, or anything a live spec governs
- it adds or restructures a page, card, or navigation affordance
- the user is unsure of the shape and needs the thinking written down before deciding

If the user asks for a plan for something below that line, say so in one sentence and offer the PR-body alternative. Do not pad a small change into a plan-shaped document.

## Segment or item

A **segment** is a scope with its own file, `guide/segment_<id>_<slug>.md`. An **item** is a unit inside a segment that ships on its own, under `## Item <n> — <title>`, and is referred to as `<segment>.<n>` — `19C.1`. Items use the same shape as segments at one heading level deeper (`###`).

A segment is not always one coherent piece of work; some are several items that share a theme but close independently. So the two machine-read sections (below) are written at **whichever level closes**:

- a segment that closes as a whole writes `## Doc impact` once, at the end of the file, with `(Item n)` tags on each bullet;
- a segment whose items close independently writes `### Doc impact` and `### Status` inside each item block, and has no segment-level `## Doc impact`.

Pick one shape per file and do not mix them. `tools/close_check.py 19C` reads the segment-level section; `tools/close_check.py 19C.1` reads Item 1's. If a segment has item-level manifests, closing the segment means every item has closed.

Prefer adding an item to a live segment over opening a new segment when the work belongs to the same theme. Open a new segment when the theme is new or the live one has closed.

## The shape

Write these sections in this order. Two of them are machine-read and must use these exact headings; the rest are the recommended vocabulary and should be used unless there is a reason not to.

| Section | Heading | Machine-read | What it must contain |
|---|---|---|---|
| Opportunity | `## Opportunity` (or `###` for an item) | no | What is wrong or missing, in one or two paragraphs, with evidence: a defect, a measurement, a user report, a spec gap. Not a feature description. |
| Decision | `## Decision` | no | The converged design, **and the alternative that was rejected with the reason**. A decision without a named alternative is a description, not a decision. |
| Semantics | `## Semantics` | no | Per mechanism: what it does at the boundaries — empty input, absent column, retired value, concurrent edit. This is where the contract-level thinking lives before it reaches the spec. |
| Judgment calls | `## Judgment calls — decided` | no | The small choices that could have gone either way, each stated as a decision with a one-line reason. This section grows during the build; that is its purpose. |
| Blast radius | `## Blast radius (measured)` | no | The files, routes, templates, tests and specs the change touches, **counted before the first slice is cut**, with the command that produced the count. See "Measuring blast radius". |
| PR ladder | `## PR ladder` | no | Numbered slices, each independently shippable and leaving the codebase in a coherent state. For UI, the scaffold PR is first. Each rung names what it lands and what it must not touch. |
| Definition of done | `## Definition of done` | no | Every line checkable by a command or a named artefact. Ends with the five close lines (below). |
| Open questions | `## Open questions` | no | Things not yet decided, each with who or what decides it. Empty is fine; absent is not. |
| Out of scope | `## Out of scope` | no | Explicit exclusions, with the reason for each. Deferred items name where they are recorded (`guide/deferred_consolidated.md`, a later segment). |
| Doc impact | `## Doc impact` | **yes** | See "Doc impact contract". |
| Status | `## Status` | **yes** | Absent at planning time. Added during or at the end of the build. See "Revising a plan". |

`Doc impact` and `Status` are parsed by `tools/close_check.py` at `##` (segment) or `###` (item) level. Do not rename them, and do not have both a segment-level and item-level `Doc impact` in one file. `Doc impact` is matched **exactly** — suffixing the heading (`## Doc impact — segment sketch (superseded)`) is how a plan retires a stale manifest without deleting it, and Segment 19A does exactly that. `Status` tolerates a suffix, because dated headings are the convention.

## Measuring blast radius

Do not estimate. Run and record:

- callers of a function or service: `grep -rn "<name>(" app/ | wc -l` and list them
- templates touching a surface: `grep -rln "<route-or-partial>" app/web/templates`
- specs that mention the term or route: `grep -rln "<term>" spec/ docs/`
- tests that exercise the path: `grep -rln "<route-or-function>" tests/`
- if the change renames a user-facing term: `grep -rn "<old term>" spec/ docs/ app/web/templates` — this list becomes doc-impact bullets. Add the old term to `RETIRED_TERMS` in `tests/unit/test_doc_conventions.py` only when no code constant derives the new one (button vocabulary today); a lifecycle-label rename is already caught by the `DISPLAY_LABELS`-derived check and needs no entry

Record the numbers and the commands in the plan. A blast radius that turns out wrong at build time is a finding to add to `## Status`, not a reason to silently revise the count.

## Doc impact contract

One bullet per file that the segment commits to changing. Each bullet: a backticked repo-relative path under `spec/` or `docs/`, a dash, what changes in it, and the item tag if the segment has items.

```
## Doc impact

- `spec/csv_contracts.md` — add the `<Slot>.<label>` header grammar for the three roster files (Item 1).
- `spec/settings_inventory.md` — remove `field_labels.*` from the Settings CSV inventory (Item 1).
- `docs/status.md` — row for each item as it lands.
```

Rules:

- Name the spec at **planning time**, even though the edit lands last. Committing to the spec is the point.
- If a bullet is dropped during the build, do not delete it. Append `<!-- doc-impact-waived: <reason> -->` on the same line. An empty reason fails the close check.
- If the build reveals a spec the plan did not name, add the bullet and note it in `## Status`. Undeclared spec impact is the failure mode this section exists to prevent.
- Never write the spec's content into the plan. Name the section that will change and what it will say; the words go in the spec on the way out.

## Definition of done

Every line must be something a reader can check without asking the author. Good: "`spec/csv_contracts.md` §1a documents the bare-header-clears rule." Bad: "docs updated." The last five lines are always:

```
- `## Doc impact` section present and current
- `python3 tools/close_check.py <id>` exits 0
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` records intended vs done
- `docs/status.md` row added; plan moved to `guide/archive/` + index row
```

## Revising a plan

The build will change the plan. That is the design, not a failure. The rules for recording it:

- **Never rewrite intent.** The Opportunity, Decision and original PR ladder stay as written. History is annotated, not edited.
- **Add `## Status` above the PR ladder** the first time intended and actual diverge. It records: what the ladder became and why (e.g. "collapsed to one PR — intermediate slices would have left a dual-carrier state"), then a `Decisions confirmed at build:` list. Update it as the build proceeds; date each entry.
- **Judgment calls grow.** A choice made mid-build that the plan did not anticipate goes into `## Judgment calls — decided`, dated, with its one-line reason.
- **Strike, don't delete.** A ladder rung that was dropped is `~~struck~~` with a note, not removed.
- **Scope creep is a status entry.** If a slice landed something the plan did not name, `## Status` says so and `## Doc impact` gains any bullet it implies. The `diff-reviewer` reports scope beyond the stated purpose; the plan is where that report is answered.

When asked to "update the plan" after a build, do the five things above. Do not regenerate the document unless the user specifically instructs a rewrite; if they do, keep the original under `## Superseded plan` at the end of the file rather than discarding it.

## Closing a segment

Closing is a sequence, and the plan is the record of it. `<id>` is `19C` for a segment or `19C.1` for an item. In order:

1. The `Doc impact` section at the closing level is current — every bullet honoured, waived with reason, or added.
2. `python3 tools/close_check.py <id>` exits 0. If it fails, fix the plan or the spec; do not close. It checks the manifest at the closing level (one shape per file), that every committed path exists and is live, that every un-waived path was edited inside the segment's window, and that each waiver carries a reason; a missing `Status` block warns rather than fails. It reports only — it edits nothing and moves nothing, and it asks whether an edit happened, never whether it was right. That judgement is step 3's.
3. Run `spec-writer` against the doc-impact files only. Adjudicate its flags; record any that changed a decision in `Status`.
4. `Status` carries the final intended-versus-done account.
5. Add the `docs/status.md` row. For a segment close (or the last item of a segment): move the file to `guide/archive/` and add its row to `guide/archive/README.md`. An item close leaves the file in `guide/`.

Do not run the whole-folder sweep at close; that is a separate cadence with a separate reader.

## Style

British spelling. Backtick every path, route, identifier and constant. Enum values for code-facing references, display labels for user-facing copy, and say which is which. Short sections; a plan that needs a table of contents has become a spec. Where a choice could have gone another way, one sentence on why it didn't.

## Template

A blank plan with all sections and their prompts is at `guide/segment_plan_template.md` — kept under `guide/` rather than inside this skill so that every agent reading `AGENTS.md`, and every human, finds it where the plans live. Copy it for a new segment; for a new item, copy the item block within it.
