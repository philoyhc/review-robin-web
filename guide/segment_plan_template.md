# Segment <ID> — <Title>

**Opened:** YYYY-MM-DD · **Theme:** <one line> · **Related:** `guide/<related plan>.md`, `spec/<governing spec>.md`

<!--
Delete each HTML comment as you fill its section.

LENGTH. Under ~250 lines for a segment, ~120 for an item. Past that, cut rather
than continue — the archive ran to 4,840. Most overflow is not the planning but
Status and answered Open questions growing after the thinking is done. See the
segment-plan skill, "Length".

"## Doc impact" and "## Status" are machine-read by tools/close_check.py: do
not rename them. Doc impact is matched exactly; Status tolerates a suffix.

For a segment with items, repeat the item block at the end of this file per item
at ### level, and write Doc impact once, at the end, with (Item n) tags.
-->

## Opportunity

<!-- What is wrong or missing, with evidence: a defect, a measurement, a user
report, a spec gap. One or two paragraphs. Not a feature description. -->

## Decision

<!-- The converged design. Then the alternative that was rejected, and why.
A decision without a named alternative is a description. -->

## Semantics

<!-- Per mechanism, what happens at the boundaries: empty input, absent column,
retired value, concurrent edit, second run. Contract-level thinking that moves
to the spec on the way out; name the spec section it will land in. -->

## Judgment calls — decided

<!-- Choices that could have gone either way. One line each: the decision and
the reason, dated if added after planning. A call that needs a paragraph belongs
in Semantics or as a Decision amendment. -->

- 

## Blast radius (measured)

Taken <YYYY-MM-DD> at `<sha>`.

<!-- Counted before the first slice is cut, with the command that produced each
count. Do not estimate. The line above is the anchor: without it a later
re-run cannot tell a stale number from a tree that legitimately moved.
Enforced from segment 19S on by tests/unit/test_index_currency.py. -->

| What | Count | Command |
|---|---|---|
| Callers of `<name>` | | `grep -rn "<name>(" app/ \| wc -l` |
| Templates | | `grep -rln "<route-or-partial>" app/web/templates` |
| Specs mentioning `<term>` | | `grep -rln "<term>" spec/ docs/` |
| Tests exercising the path | | `grep -rln "<route-or-function>" tests/` |

## PR ladder

<!-- Numbered slices, each independently shippable. For UI, the scaffold PR is
first. Each rung: what it lands, and what it must not touch. A dropped rung is
struck with a one-line note, not deleted and not explained at length. -->

1. **PR 1 — <title>.** Lands: … Must not touch: …
2. **PR 2 — <title>.** …

## Definition of done

<!-- Every line checkable by a command or a named artefact. Keep the last five. -->

- 
- `## Doc impact` section present and current
- `python3 tools/close_check.py <ID>` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

## Open questions

<!-- Each with who or what decides it. Empty is fine; absent is not. When one is
answered, collapse it to the answer — one line, what was decided and by what.
Do not keep a closed question at its full deliberating length. -->

- 

## Out of scope

<!-- Explicit exclusions with reasons. Deferred items name where they are
recorded. -->

- 

## Doc impact

<!-- One bullet per file: backticked path, dash, what changes, (Item n) tag if
applicable. Waive with a doc-impact-waived comment on the same line rather than
deleting the bullet. The full contract is in the segment-plan skill, "Doc impact
contract" — do not restate it here. -->

- `spec/<file>.md` — 
- `docs/status.md` — row when the segment lands.

<!--
## Status

Added the first time intended and actual diverge. Place it ABOVE the PR ladder.

**YYYY-MM-DD.** <What the ladder became and why.>

Decisions confirmed at build:
- 

A running log while open. At close it COMPACTS to the intended-versus-done
account — what the ladder became and why, decisions confirmed, scope that
moved. Superseded entries and intermediate states go; intent is never touched.
-->

---

<!-- ITEM BLOCK — copy per item into a segment that has items.

## Item <n> — <Title>

### Opportunity
### Decision
### Semantics
### Judgment calls — decided
### Blast radius (measured)
### PR ladder
### Definition of done
### Open questions
### Out of scope
### Doc impact
### Status

Items closing independently (19C.1, 19C.2, …) each carry their own
"### Doc impact" and "### Status", and the file has NO segment-level
"## Doc impact". A segment closing as a whole drops those two item-level
headings for the segment-level manifest with (Item n) tags. One shape per file.
-->
