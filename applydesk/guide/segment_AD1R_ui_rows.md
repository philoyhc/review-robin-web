# Segment AD1R — Apply Desk: the assessment's last UI rows

**Opened:** 2026-11-21 · **Theme:** close the 2026-11-18 assessment's UI rows AD1P left open, for the author's browser check · **Related:** `applydesk/guide/findings_2026-11-18_assessment.md` (the rows), `applydesk/guide/archive/segment_AD1P_ui_consistency.md` (the sweep they follow), `applydesk/guide/todo_master.md` (rulings 47, 63, 64, 67), `spec/ui_elements.md` (RRW's roles and primitives)

## Opportunity

On 2026-11-21 the 2026-11-18 register was reconciled against AD1P (#4094). Of the 27 rows that waited on "the UI sweep", six were done, one moved to AD2, and 17 still showed in the code. Ruling 67 settled four of them:
- two are declined: AD-98, and AD-92's "String" half;
- two wait for ruling 33's dossier parts: AD-69 and AD-93.

That leaves the 14 below. Each is small, but together they are what still makes one page look unlike its neighbors: unsaved markers, buttons, tables, counts and words.

## Decision

Build the 14 rows as three rungs grouped by kind: primitives in `base.html` first, then labels and copy, then the two that change behavior. Each lands on its pages' existing tests plus a test for what it changes. The author checks each rung in a browser.

**Alternative rejected:** folding them into AD2. They touch templates and CSS only, and AD2 is persistence; carrying them there would keep the inconsistencies live through the largest segment.

## Register

| Row | What is still wrong | Fix | Rung |
|---|---|---|---|
| AD-70 | The unsaved marker is two classes: `.fb-unsaved`, and Dossiers' `.ap-changes` count | One marker class; Dossiers' count is its text | 2 |
| AD-76 | Form's type summary is an uppercase chip; Panels' name chips drop uppercase | The type summary as muted text; Panels' chips as every display chip (U3) | 2 |
| AD-77 | Tables have no row hover, and rows use `--border-subtle` | RRW §7: row hover, `--border-default` | 2 |
| AD-81 | Primary and Destructive have no hover; page contexts still reshape `.btn` | A hover per role, as RRW; context overrides removed or moved to `.btn-short` | 2 |
| AD-72 | Panels' create reads "+ Panel" (Secondary) where the inline box reads "Create panel" (Primary); Form's add reads "+ New" | One label and role for creating a panel; `+ Noun` on Form (U8) | 3 |
| AD-73 | Extract reads "Zip all", "Zip gates", "Zip setup", "CSV", "Download key" | Download verbs, as U13 | 3 |
| AD-75 | Home's outcome row hard-codes Pending mute (`home_ops.py`) | Read the tone from `tones.py`, as Dossiers does | 3 |
| AD-80 | Counts read "Showing n of N" (Dossiers) and "1–200 of N" (gate page) | One count format | 3 |
| AD-84 | Extract setup's `panels.csv` is long; Panels exports wide; nothing says so | A line on Extract's setup card naming the shape (ruling 67) | 3 |
| AD-85 | Dossiers, Evaluations and Extract have no intro under the h1 | A `pc-intro` line on each (F1) | 3 |
| AD-91 | Home's timeline rows name a gate by its bare label | `Gate N · label` (U4) | 3 |
| AD-92 | Evaluations' copy names `ProfileLink` | Say what the link is in words | 3 |
| AD-79 | Operator empty states take several shapes; Dossiers' *Unlock* over no applications and Extract's chips over disabled downloads stay live | One empty-state block; controls over nothing disabled with a `title` (U16) | 4 |
| AD-83 | Panels' sort is two-state, with no clear or cascade | The gate page's three-state sort with shift-cascade | 4 |

## Semantics

- **No stored value or route changes.** This is templates, `base.html`, `home_ops.py`'s tone and Extract's copy. Every download's bytes stay as they are; AD-73 changes labels, not file names.
- **AD-83:** Panels sorts client-side today. It takes the gate page's state machine (none → asc → desc → none; shift adds a key), and the order still resets on reload, as now.
- **AD-79:** a disabled control keeps its place and says why in `title`, so the page does not reflow when data arrives.

## Judgment calls — decided

- The four ruled rows are recorded in ruling 67, not here: AD-92's "String" half and AD-98 are declined; AD-69 and AD-93 go to `applydesk/guide/ad3_plus_deferred_findings.md`.
- AD-81: where a context reshapes `.btn` only for size, `.btn-short` (U25) takes it; any other reshaping is removed.

## Blast radius (measured)

Taken 2026-11-21 at `526e94f6f`.
- `applydesk/templates/applydesk/base.html`: 1,039 lines, the whole stylesheet.
- Unsaved markers: `grep -rn "ap-changes\|fb-unsaved\|pn-unsaved" applydesk/templates | wc -l` → 19.
- Pages with an intro: `grep -rln "pc-intro" applydesk/templates | wc -l` → 8.
- Extract's verbs: `grep -n "Zip all\|Zip gates\|Zip setup\|Download key\|>CSV<" applydesk/templates/applydesk/operator/_extract.html | wc -l` → 6.
- Add labels: `grep -rn "Create panel\|+ Panel\|+ New" applydesk/templates | wc -l` → 17.
- Tests naming these surfaces: 8 files, including `test_extract.py`, and the `_browser.py` suites for Extract, Panels, Form, unsaved, Process, Evaluations and Dossiers.

## PR ladder

1. **This plan**, ruling 67, and the later-stage rows moved out. Prose only.
2. **Primitives:** AD-70, AD-76, AD-77, AD-81. `base.html` and the templates whose classes change.
3. **Labels and copy:** AD-72, AD-73, AD-75, AD-80, AD-84, AD-85, AD-91, AD-92.
4. **Behavior:** AD-79, AD-83. The last build rung: the cumulative `diff-reviewer` read runs here, over rungs 2–4.
5. **Close.**

## Definition of done

- Every register row landed and struck in `applydesk/guide/findings_2026-11-18_assessment.md`, or struck with its reason.
- With every row struck or moved, that register moves to `applydesk/guide/archive/` with its index row.
- The author's browser check of each rung's pages at 1300px and 390px.
- `## Doc impact` section present and current
- `python3 tools/close_check.py AD1R` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `applydesk/guide/todo_master.md` entries deleted; plan moved to `applydesk/guide/archive/` + index row

## Open questions

- None open. The four that needed a ruling were settled by ruling 67.

## Out of scope

- AD-69 and AD-93: they go with ruling 33's dossier parts (`applydesk/guide/ad3_plus_deferred_findings.md`).
- RRW's own templates and the shared host chrome (AD-98, declined).
- AD2's rows (`applydesk/guide/ad2_deferred_findings.md`).

## Doc impact

- `applydesk/spec/applications.md` — "One look across pages": the unsaved marker, table hover, button hovers, counts, empty states and Panels' sort (rungs 2–4).
- `applydesk/guide/findings_2026-11-18_assessment.md` — each row struck with its PR (rungs 2–4); the register archived (close).
- `applydesk/guide/todo_master.md` — ruling 67 (rung 1).
- `applydesk/README.md` — the plan's row, and the deferred file's (rung 1); the archive rows (close).
