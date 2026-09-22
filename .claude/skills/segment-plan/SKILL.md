---
name: segment-plan
description: Write, revise, or close a segment plan or an item within one, in guide/segment_*.md. Use this whenever the user asks to plan a segment, item, feature, refactor, or slice of work; whenever they say "plan", "segment", "item", "PR ladder", "scope this", "spec out the work", or "what would it take to"; whenever a build reveals that an existing plan's intent and what shipped have diverged and the plan needs a status block; and whenever a segment is being closed or archived. Also use it when the user starts describing work in enough detail that a plan is the right artefact, even if they have not asked for one — offer the plan rather than starting to build. Do not use it for the spec itself (that is spec-writer's territory) or for a change small enough that a PR body carries the reasoning (see "When not to write a plan").
---
# Segment plan

A segment plan carries intent into a build and absorbs what the build discovers, so the spec never has to. It is the day-to-day source of truth for its own slices while open, and a record of intended-versus-done after it closes. The rule it serves is `rrw_sdd_in_practice.md` §6.1: **plan on the way in, spec on the way out.** Read §5 once if it is not in context; this skill is its operational form.

## When not to write a plan

Plans scale badly downward. Do not write one for a single PR touching no database schema, no spec contract, and no user-facing surface — put the reasoning in the PR body and stop. Write a plan when any of these hold:

- the work will take two or more PRs
- it changes a lifecycle, a CSV contract, a route shape, or anything a live spec governs
- it adds or restructures a page, card, or navigation affordance
- the user is unsure of the shape and needs the thinking written down before deciding

If asked for a plan below that line, say so in one sentence and offer the PR-body alternative. Do not pad a small change into a plan-shaped document.

## Segment or item

A **segment** is a scope with its own file, `guide/segment_<id>_<slug>.md`. An **item** is a unit inside it that ships on its own, under `## Item <n> — <title>`, referred to as `<segment>.<n>` — `19C.1`. Items use the same shape one heading level deeper (`###`).

Some segments are several items sharing a theme that close independently, so the two machine-read sections are written at **whichever level closes**:

- a segment closing as a whole writes `## Doc impact` once, at the end, with `(Item n)` tags on each bullet;
- a segment whose items close independently writes `### Doc impact` and `### Status` inside each item block, and has no segment-level `## Doc impact`.

One shape per file; do not mix them. `tools/close_check.py 19C` reads the segment-level section, `19C.1` reads Item 1's. A segment with item-level manifests closes when every item has.

Prefer adding an item to a live segment over opening a new one when the work shares the theme.

## The shape

These sections, in this order. Two are machine-read and must use these exact headings; the rest are the recommended vocabulary.

| Section | Heading | Machine-read | What it must contain |
|---|---|---|---|
| Opportunity | `## Opportunity` (`###` for an item) | no | What is wrong or missing, with evidence: a defect, a measurement, a user report, a spec gap. Not a feature description. |
| Decision | `## Decision` | no | The converged design, **and the alternative rejected, with the reason**. A decision without a named alternative is a description. |
| Semantics | `## Semantics` | no | Per mechanism, the boundaries: empty input, absent column, retired value, concurrent edit. Contract-level thinking before it reaches the spec. |
| Judgment calls | `## Judgment calls — decided` | no | Choices that could have gone either way, one line each with its reason. Grows during the build; that is its purpose. |
| Blast radius | `## Blast radius (measured)` | no | Files, routes, templates, tests and specs touched, **counted before the first slice is cut**, with the command that produced each count. **Open with the commit or date the counts were taken at** — *"Taken 2026-09-22 at `92f7aff`."* A number with no anchor cannot be re-run later, because a differing answer is indistinguishable from the tree having moved. Checked from segment **19S** on by `tests/unit/test_index_currency.py` (19S Item 5). |
| PR ladder | `## PR ladder` | no | Numbered slices, each independently shippable and leaving the codebase coherent. For UI, the scaffold PR is first. Each rung names what it lands and what it must not touch. |
| Definition of done | `## Definition of done` | no | Every line checkable by a command or a named artefact. Ends with the five close lines. |
| Open questions | `## Open questions` | no | Each with who or what decides it. Empty is fine; absent is not. |
| Out of scope | `## Out of scope` | no | Explicit exclusions with reasons. Deferred items name where they are recorded. |
| Doc impact | `## Doc impact` | **yes** | See "Doc impact contract". |
| Status | `## Status` | **yes** | Absent at planning time. Added during or at the end of the build. See "Revising a plan". |

Both are parsed at `##` (segment) or `###` (item) level. Do not rename them, and never have both a segment-level and an item-level `Doc impact` in one file. `Doc impact` is matched **exactly**, so suffixing it (`## Doc impact — superseded`) retires a stale manifest without deleting it. `Status` tolerates a suffix, because dated headings are the convention.

## Length

**A plan under ~250 lines; an item under ~120.** A signal, not a limit to game: past it, ask what a reader in six months needs and cut the rest.

The figures come from the archive. Plans ran 370 to **4,840** lines across 19A–19M, and one *item* hit 951 — at which point this skill's own test, *a plan that needs a table of contents has become a spec*, is already failing, and the plan is no longer what a reviewer reads before a slice.

**The bulk is not in the planning.** Measured over one 377-line item: every section the template asks for came in under 50 lines, while `Status` alone ran **110** and a closed `Open questions` block **61** — 45% of the item, both written after the thinking, by the append-only rules below. Staying inside the budget is not terser reasoning; it is not letting the record of the build outgrow the build. Three habits cause most of the rest: **saying it twice** (a judgment call restated in `Status`), **narrating the search** rather than keeping the conclusion and the command that proves it, and **quoting at length what a pointer would do**.

**Exempt: anything a tool reads.** `Doc impact` bullets are not consolidated, abbreviated, or stripped of their backticks to save a line, and the five definition-of-done lines stay verbatim. Brevity never buys itself out of a check.

## Measuring blast radius

Do not estimate. Run and record:

- callers of a function or service: `grep -rn "<name>(" app/ | wc -l`, and list them
- templates touching a surface: `grep -rln "<route-or-partial>" app/web/templates`
- specs mentioning the term or route: `grep -rln "<term>" spec/ docs/`
- tests exercising the path: `grep -rln "<route-or-function>" tests/`
- for a user-facing rename: `grep -rn "<old term>" spec/ docs/ app/web/templates` — this list becomes doc-impact bullets. Add the old term to `RETIRED_TERMS` in `tests/unit/test_doc_conventions.py` only when no code constant derives the new one (the pre-19B button names, plus the lobby's `Search card` after 19O Item 7 entry 16 — where the sweep missed two specs and nothing could see it); a lifecycle-label rename is already caught by the `DISPLAY_LABELS`-derived check.

Record the numbers and the commands. A blast radius that turns out wrong at build time is a finding for `## Status`, not a reason to silently revise the count.

**Open the section with when you took them** — `Taken <YYYY-MM-DD> at `<sha>``, or a line saying *measured* with the date. A count with no anchor cannot be re-run later, because a differing answer is indistinguishable from the tree having legitimately moved. From segment **19S** on this is checked by `tests/unit/test_index_currency.py`; the anchor is a backticked sha, or a date on a line that also says *taken* or *measured*, within the section's first two non-blank lines. If a row's number comes from a different tree than the rest, say so **per row** rather than under one header.

## Doc impact contract

One bullet per file the segment commits to changing: a backticked repo-relative path, a dash, what changes, and the item tag if the segment has items.

```
## Doc impact

- `spec/csv_contracts.md` — add the `<Slot>.<label>` header grammar for the three roster files (Item 1).
- `spec/settings_inventory.md` — remove `field_labels.*` from the Settings CSV inventory (Item 1).
- `docs/status.md` — row for each item as it lands.
```

- Name the spec at **planning time**, even though the edit lands last. Committing to the spec is the point.
- A dropped bullet is not deleted: append `<!-- doc-impact-waived: <reason> -->` on the same line. An empty reason fails the check.
- A `spec/` or `docs/` path counts **anywhere** in the bullet, since bullets legitimately commit to several specs after the dash. A root-level document (`constitution.md`, `CLAUDE.md`), a bare filename used as folder shorthand, or a path under `app/`, `tests/`, `tools/`, `alembic/`, `.github/` or `.claude/` counts **only in the leading position**, before the dash, because a bare name is ambiguous where a prefixed path is not.
- A bullet that *cites* a path rather than committing to it — naming the target of a pointer it edits — marks it `<!-- cites: spec/x.md -->`, comma-separated for several. Do **not** drop the backticks to hide it: bending the prose to satisfy a checker is how the checker starts lying.
- If the build reveals a spec the plan did not name, add the bullet and note it in `## Status`. Undeclared spec impact is what this section exists to prevent.
- Never write the spec's content into the plan. Name the section and what it will say; the words go in the spec on the way out.

`tools/README.md` documents what the check does with each of these; do not restate its internals here.

## Definition of done

Every line checkable without asking the author. Good: "`spec/csv_contracts.md` §1a documents the bare-header-clears rule." Bad: "docs updated." The last five lines are always:

```
- `## Doc impact` section present and current
- `python3 tools/close_check.py <id>` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row
```

## Revising a plan

The build will change the plan. That is the design, not a failure. But every rule here is append-only, and left alone they are the measured source of the overflow above — so each says what compacts at close.

- **Never rewrite intent.** Opportunity, Decision and the original PR ladder stay as written; history is annotated, not edited. This one never compacts: it is why a closed plan is worth keeping.
- **`## Status`, above the PR ladder**, from the first divergence between intended and actual: what the ladder became and why, then `Decisions confirmed at build:`. A running log while the segment is open, dated as you go. **It compacts at close** — step 4 below.
- **Judgment calls grow**, one line each, dated. A call needing a paragraph is a `Semantics` entry or a `Decision` amendment, not a judgment call.
- **An answered open question collapses to its answer** — one line, what was decided and by what. The deliberation that reached it was working memory; keeping a closed question at full deliberating length is the single largest avoidable cost in the archive after `Status`.
- **Strike, don't delete.** A dropped ladder rung is `~~struck~~` with a one-line note — one line, not the argument for the reversal. If it changed the shape of the segment, that goes in `Status`; if it did not, nowhere.
- **Scope creep is a status entry.** A slice that landed something unnamed: `Status` says so, `Doc impact` gains any bullet it implies. `diff-reviewer` reports scope beyond the stated purpose; the plan answers it.

Asked to "update the plan" after a build, do the six things above. Do not regenerate the document unless instructed; if so, keep the original under `## Superseded plan` at the end rather than discarding it.

## Closing a segment

`<id>` is `19C` for a segment or `19C.1` for an item. In order:

1. The `Doc impact` section at the closing level is current — every bullet honoured, waived with reason, or added.
2. `python3 tools/close_check.py <id>` exits 0 **and every warning is adjudicated**; if it fails, fix the plan or the spec rather than closing. It reports only — it never edits or moves anything, and it asks whether an edit happened, never whether it was right. That judgement is step 3's. `tools/README.md` has the rules it applies; read the warnings, because the exit code alone does not close the loop.
3. Run `spec-writer` against the doc-impact files only. Adjudicate its flags; record any that changed a decision in `Status`. This close pass is unconditional; the narrow cases where `spec-writer` *also* runs before a rung's push are in `CLAUDE.md` "Where work runs".
4. **Compact `Status` into the intended-versus-done account, and collapse every answered open question to its answer.** Open, `Status` was a running log and that is what it was for; closed, it is a record, and a record needs the decisions and the divergences rather than the day-by-day path to them. Keep what the ladder became and why, decisions confirmed at build, scope that moved, and anything a later reader needs to read the diff. Drop superseded entries, intermediate states, and anything the code or the spec now says better. *Nothing about intent is touched — only the log of getting there.*
5. Add the `docs/status.md` row. For a segment close, or the last item of one, move the file to `guide/archive/` and add its row to `guide/archive/README.md`. An item close leaves the file in `guide/`.

Do not run the whole-folder sweep at close; that is a separate cadence with a separate reader.

## Style

US spelling (`CLAUDE.md` → Project conventions; existing British forms in older plans stay put). Backtick every path, route, identifier and constant. Enum values for code-facing references, display labels for user-facing copy, and say which is which. Where a choice could have gone another way, one sentence on why it didn't — one sentence, not the argument that produced it.

## Template

A blank plan with every section and its prompts is at `guide/segment_plan_template.md` — under `guide/` rather than inside this skill, so every agent reading `AGENTS.md` and every human finds it where the plans live. Copy it for a new segment; for a new item, copy the item block within it.
