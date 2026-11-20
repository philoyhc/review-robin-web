# Segment AD1P — Apply Desk: the UI consistency sweep

**Opened:** 2026-11-20 · **Theme:** one look and one vocabulary across Apply Desk's pages, recognizably of a family with Review Robin · **Related:** `applydesk/guide/todo_master.md` (rulings 47, 50, 63, 64), `spec/ui_elements.md` (RRW's roles and primitives), `applydesk/spec/applications.md`

## Opportunity

The author opened the UI review on 2026-11-20 with ruling 63 (every toggle one shape). An audit of all 14 operator and applicant pages that day (screenshots at 1300px and 390px read against the templates, by two cold reviewers) found 40 inconsistencies: the same state in three colors, a gate named five ways, removes in four styles, control heights from 28px to 36px, two table styles, dates with and without a year in one row. A third reader checked each proposal against RRW, so the fixes bring Apply Desk toward RRW rather than away from it.

## Decision

The author approved the 19 plain fixes (F1–F19) and the rulings U1–U25 as checked against RRW (ruling 64). They land as small slices by area, tokens first so later slices build on them.

**Alternative rejected:** one sweeping PR. The changes touch every page; a reviewer could not model it, and a regression would be hard to find.

## Register

Recorded 2026-11-20. **U** rows are ruled (ruling 64); **F** rows are plain fixes. Each names the rung that lands it.

| # | What | Fix | Rung |
|---|---|---|---|
| U1 | A state's chip color differs by page | RRW's palette, one map: Draft amber, Closed red, Completed/Activated green, grey only for archived | 2 |
| U2 | Timeline heads say Done/Now/Next beside Completed/Published/Draft | Operator words on operator pages | 5 |
| U3 | Display chips uppercase, cell chips sentence case | Uppercase, as RRW; an outline marks a clickable chip | 2 |
| U4 | A gate named five ways | `Gate 1 · Peer review` | 5 |
| U5 | Lone on/off: pill, checkbox, "switch" | Native checkbox in a form (browser size); RRW's On/Off Toggle for an auto-saving row; *Required* a checkbox; *Released* not "the switch" | 4 |
| U6 | Primary first or last | Primary first; Primary only for the page's one affirmative act, Save Secondary | 4 |
| U7 | Sample pages that cannot save | A whole-page lock: controls removed, an amber lock card with reason and way out; one blocked control disabled with `title` | 4 |
| U8 | Add labels | `+ Noun` in builders; `Add new` for a table toolbar's add-row | 4 |
| U9 | Removes in four styles | Destructive for dense-row removes and irreversible deletes; an undoable Remove elsewhere Secondary | 4 |
| U10 | Cross-page links, arrows, ellipses | `Verb on Page →` at 13px; `↓` for an in-page jump; `…` only when more input comes first | 4 |
| U11 | Cards without headings; Form title as big as h1 | Every card an h2 at 18px/600, as RRW; lock cards exempt; form title 18px | 2, 3 |
| U12 | Two sortable-table styles | RRW's header band and `↕`/`1↑` badges; no sticky header | 5 |
| U13 | Download roles and verbs | Upload / Download; downloads Secondary | 4 |
| U14 | Switch colors | Theme switch stays accent-filled, as in both apps | — |
| U15 | Dossiers' cell chips under ruling 63? | Exempt (values opening a menu); display-chip size | 5 |
| U16 | Lock reasons on hover or on the page | A whole-card lock a visible amber line; one control a `title` | 4, 5 |
| U17 | Search, filters, bulk actions placed apart | Filters together at the top, visible labels; bulk actions at the top | 5 |
| U18 | Dates with and without a year | Operator pages RRW's `YYYY-MM-DD HH:MM`; applicant pages keep friendly dates | 5 |
| U19 | Dossiers' header block ~230px | Rule text two lines and *more* | 5 |
| U20 | An operator's dossier link lands in the applicant area | An operator dossier page with a Dossiers breadcrumb, and *View as applicant* in a new tab | 6a, 6b |
| U21 | Lobby and Panels tables differ | As U12 | 5 |
| U22 | Small uppercase section labels (`.xd-k`, `.mg-h`, `.dt-sec`, ...) | Sentence case: an h3 or a field label | 2 |
| U23 | Cards 16px apart | 20px, as RRW | 2 |
| U24 | Button text weight 600 | 500, as RRW | 2 |
| U25 | Extract's 30px `.xd-csv` button | RRW's short-button variant | 2 |
| F1 | Five intro-line styles | One intro class after the banner; Form gets an intro, its lock note moves | 3 |
| F2 | Emails' card help at 16px | 13px help class | 3 |
| F3 | Outline items underlined on Emails; heading colors differ | No underline; one heading color | 3 |
| F4 | Emails banner says nothing can change | Drop `emails` from that branch | 3 |
| F5 | Inputs 32–35px beside 36px buttons; three label styles | RRW's input padding and 16px text; `.fc-l` labels | 2 |
| F6 | *Remove the form* Secondary among Destructive siblings | Per U9 | 4 |
| F7 | Long chips wrap into blocks | One line, ellipsis, full text in `title` | 3 |
| F8 | Locked grips full strength; disabled inputs look editable | Dimmed grips; every disabled `.fc-in` dashed | 3 |
| F9 | Panels roster line mixes `|` and `·` | `·` | 3 |
| F10 | Home's card heads at different heights | `.cardhead` centered at `--tog-h` | 3 |
| F11 | Phone width: stranded `/`, hanging `·`, wide Process handle | Separators with their item; tighter handle | 3 |
| F12 | *Approve / Approved* a relabelled Secondary | `.btn-toggle` with `aria-pressed` | 5 |
| F13 | Lock and revert differ between Details, Dossiers, gate page | One pattern: Lock, *Discard changes*, one unsaved note | 5 |
| F14 | Evaluations' cards uneven | One heading per card, help under it; Assignments one card | 5 |
| F15 | Pairs named and counted four ways | "pairs", `{:,}`, one count pattern | 5 |
| F16 | `RRW` on Dossiers | `Review Robin` (stored value kept) | 5 |
| F17 | *Applicants as* options swap order | One order | 5 |
| F18 | /me pages: two containers, misaligned facts, no empty states | `.card`, one `dl`, empty lines, full-width empty row | 6b |
| F19 | Process and Form card bodies unseen by the audit | Look again once open, fold findings in | 3 |

## Semantics

- **Colors** come from one state-to-tone map read by every chip (`_state_chip.html`, `workflow.py`'s status row, `home_ops.py`, `_gate_state.html`, `_timeline.html`), so a new place cannot drift.
- **Dates:** operator templates format through one helper; applicant pages and emails keep their wording.
- **Behavior does not change** except U20's new page and U5's control swaps; every slice keeps its page's tests.

## Judgment calls — decided

- U14 stays as is: both apps fill the theme switch with accent, so greying it in one would split the shared chrome.
- No sticky table header (U12): RRW has none; adding one is a family decision, not Apply Desk's alone.

## Blast radius (measured)

Taken 2026-11-20 at `54c74d967`.
- `applydesk/templates/applydesk/base.html`: 981 lines, the whole stylesheet.
- Templates with chips: `grep -rln "chip" applydesk/templates | wc -l` → 23.
- Primary buttons: `grep -rn "btn-primary" applydesk/templates | wc -l` → 22.
- Uppercase section labels: `grep -rn "mg-h\|dt-sec\|xd-k\|xnav-label" applydesk/templates | wc -l` → 16.
- Date formatters: `stages.py:235`, `stages.py:770`, `timeline.py:75`.

## PR ladder

1. **This plan**, with ruling 64. Prose only.
2. **Tokens and primitives:** U1, U3, U11 (h2), U22–U25, F5. `base.html` and the chip map.
3. **Setup pages:** F1–F4, F7–F11, U11 (Form title), F19.
4. **Roles and labels:** U5–U10, U13, U16 (cards), F6.
5. **Operations pages:** U2, U4, U12, U15–U19, U21, F12–F17.
6a. **The operator dossier page, scaffold** (U20): the page, its breadcrumb and its cards as static placeholders with real copy, *View as applicant* inert; Dossiers' ID links still go where they do. A new page lands scaffold-first (`AGENTS.md`, Working approach).
6b. **The operator dossier page, wired, and the applicant pages** (U20, F18): the cards filled, Dossiers' links pointed at it, *View as applicant* live. The last build rung: the cumulative cold read runs here.
7. **Close.**

## Definition of done

- Every register row landed, or struck with its reason.
- Screenshots of the 14 pages at 1300px and 390px show no row's inconsistency.
- `## Doc impact` section present and current
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `applydesk/guide/todo_master.md` entries deleted; plan moved to `applydesk/guide/archive/` + index row
- (`tools/close_check.py` reads only RRW's top-level `guide/`; the close is checked by hand.)

## Open questions

- Should RRW adopt anything Apply Desk settled here (U10's link rules; `+Noun` spacing)? The author, after the close.

## Out of scope

- RRW's own templates: changed only if the author asks (see the open question).
- Dark-mode and hover/focus states beyond what each rung touches: not audited.

## Doc impact

- `applydesk/spec/applications.md` — chips and colors, controls, dates, the operator dossier page, *Released* wording (rungs 2–6).
- `applydesk/guide/todo_master.md` — ruling 64; the UI review roadmap row (rung 1, close).
- `applydesk/guide/archive/README.md` — the plan's index row (at close).
