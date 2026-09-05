# Segment <ID> — <Title>

**Opened:** YYYY-MM-DD · **Theme:** <one line> · **Related:** `guide/<related plan>.md`, `spec/<governing spec>.md`

<!--
Delete the HTML comments as you fill each section. Two headings are machine-read
by tools/close_check.py and must not be renamed: "## Doc impact" and "## Status".
"Doc impact" is matched EXACTLY, so suffixing it ("## Doc impact - superseded")
is how you retire a manifest without deleting it; "Status" tolerates a suffix,
so "## Status (started 2026-08-19)" still counts.
For a segment with items, repeat the item block below per item at ### level and
write Doc impact once, at the end, with (Item n) tags.
-->

## Opportunity

<!-- What is wrong or missing, with evidence: a defect, a measurement, a user report,
a spec gap. One or two paragraphs. Not a feature description. -->

## Decision

<!-- The converged design. Then: the alternative that was rejected, and why.
A decision without a named alternative is a description. -->

## Semantics

<!-- Per mechanism, what happens at the boundaries: empty input, absent column,
retired value, concurrent edit, second run. This is contract-level thinking that
will move to the spec on the way out; name the spec section it will land in. -->

## Judgment calls — decided

<!-- Small choices that could have gone either way. One line each: the decision and
the reason. This section grows during the build; date entries added after planning. -->

- 

## Blast radius (measured)

<!-- Files, routes, templates, tests and specs touched — counted before the first slice
is cut, with the command that produced each count. Do not estimate. -->

| What | Count | Command |
|---|---|---|
| Callers of `<name>` | | `grep -rn "<name>(" app/ \| wc -l` |
| Templates | | `grep -rln "<route-or-partial>" app/web/templates` |
| Specs mentioning `<term>` | | `grep -rln "<term>" spec/ docs/` |
| Tests exercising the path | | `grep -rln "<route-or-function>" tests/` |

## PR ladder

<!-- Numbered slices, each independently shippable. For UI, the scaffold PR is first.
Each rung: what it lands, and what it must not touch. Strike dropped rungs; do not delete. -->

1. **PR 1 — <title>.** Lands: … Must not touch: …
2. **PR 2 — <title>.** …

## Definition of done

<!-- Every line checkable by a command or a named artefact. Keep the last five lines. -->

- 
- `## Doc impact` section present and current
- `python3 tools/close_check.py <ID>` exits 0
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` records intended vs done
- `docs/status.md` row added; plan moved to `guide/archive/` + index row

## Open questions

<!-- Each with who or what decides it. Empty is fine; absent is not. -->

- 

## Out of scope

<!-- Explicit exclusions with reasons. Deferred items name where they are recorded. -->

- 

## Doc impact

<!-- One bullet per file. Backticked path under spec/ or docs/, dash, what changes,
(Item n) tag if applicable. Waive with <!-- doc-impact-waived: reason --> on the
same line rather than deleting. -->

- `spec/<file>.md` — 
- `docs/status.md` — row when the segment lands.

<!--
## Status

Added the first time intended and actual diverge. Place it ABOVE the PR ladder.

**YYYY-MM-DD.** <What the ladder became and why.>

Decisions confirmed at build:
- 
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

If items close independently (19C.1, 19C.2, …), each item carries its own "### Doc impact"
and "### Status" and the file has NO segment-level "## Doc impact". If the segment closes
as a whole, delete these two item-level headings and use the segment-level "## Doc impact"
with (Item n) tags. One shape per file.
-->
