# Segment 20Q — Review Robin on a phone

**Opened:** 2026-11-24 · **Theme:** the participant pages, the reviewer surface first, usable on a 390 px phone · **Related:** `guide/rrw_mobile_responsive.md` (the assessment this plan builds), `guide/rrw_reviewer_phone_and_scale.md` §1, `spec/reviewer-surface.md`, `spec/visual_style_rrw.md`

## Opportunity

`app/web/templates/base.html` has no viewport meta tag; only `error.html` does. A phone therefore lays every Review Robin page out at about 980 CSS px and shrinks it to fit. On a 390 px phone that is about 40% scale: body text near 6 px, buttons too small to tap. The 23 `@media` rules already in `base.html` never fire, because 980 px is wider than every breakpoint (`guide/rrw_mobile_responsive.md` §1).

With the tag added, every participant page fits, because each table already scrolls inside its `.table-scroll`. But the page that matters most, the reviewer surface, is hard to use. In *Responses across* the first answer box is half off-screen, and the reviewee's name scrolls away while answering. Each instrument repeats a visibility grid whose last column is clipped. Operator-set pixel column widths force the sideways scroll however much room a phone needs (§2 there, measured at 390 × 844 on 510 rendered participant pages).

## Decision

Build the assessment's six rungs, participants only.

- **The viewport tag, opt-in per template.** A `{% block viewport %}` in `base.html`'s `<head>` is empty by default. It is filled in the participant templates under `reviewer/` and in `about.html` and `guide.html`. Operator pages keep today's zoomed-out desktop rendering.
- **A reviewee row becomes a card under 640 px.**
  - Rows and cells become blocks, with identity and display fields at the top.
  - Each answer becomes a label-over-input line: from a `data-label` on the cell in *Responses across*, or from the stacked cell 20K already renders.
  - The operator's `<col>` pixel widths are ignored at that width.
  - Group mode gets the same.
  - A scale takes the card's full width (20P).
- **The rest of the surface stacks or wraps at the same width:**
  - the *Who can see what you wrote* grid;
  - the chips;
  - the action row;
  - addresses, which break at `@` and `.`.
- **The dashboard, summary, results and collation become cards**, reusing the response-table CSS.
- **Touch targets are at least 44 px under `pointer: coarse`.** The breakpoints consolidate to two, 640 and 900.
- **A 390 px browser guard covers each participant page.**

**Rejected:**
- **The tag on every page.** The operator setup pages (Band 1's 1,216 px grid, the 1,056 px field builder) would lay out at 390 px with overflowing tab strips. Making them responsive is a redesign, and the assessment recommends against it.
- **A separate mobile template.** Every rule here is CSS under a narrow media query plus a few `data-label` attributes, so desktop markup and behavior stay one code path.

## Semantics

- **Desktop is untouched.** Every new rule sits under `max-width: 639px` or `pointer: coarse`. The existing browser tests at 1,400 px stay the desktop net. *(Amended at rung 3a/3b by the author's rulings: a slide scale's end bars, its box at the widget's edge, and stacked scales sharing one side apply at every width, the Band 2 preview included.)*
- **Saved column widths** still apply at 640 px and wider. Under 640 px a card has no columns, so they have nothing to act on.
- **Branching:** a closed governed field stays dimmed in its card line, and a Require branch's required marker stays on the label.
- **Locked, submitted or closed assignments** render their cards read-only, as their rows do now.
- **Several instruments:** each keeps its own card list and its own visibility block.
- **Sorting:** the sort headers are hidden in card layout; the order of the cards is the table's current order.
- **No JavaScript:** cards are pure CSS, so the page works without script, as the table does today.

## Judgment calls — decided

- 640 px is the card breakpoint, and the only phone one. 900 px stays for tablets, where the table still fits after the header collapses.
- `data-label` goes on the cell, not in a hidden duplicate label, so screen readers read the header once.

## Blast radius (measured)

Taken 2026-11-24 at `bc229fdba`.

| What | Count | Command |
|---|---|---|
| Templates with a viewport tag | 1 (`error.html`) | `grep -rln 'name="viewport"' app/web/templates` |
| `@media` rules in `base.html` | 23 | `grep -c "@media" app/web/templates/base.html` |
| Participant templates extending `base.html` | 9 (7 under `reviewer/`, plus `about.html`, `guide.html`) | `grep -ln 'extends "base.html"' app/web/templates/reviewer/*.html app/web/templates/about.html app/web/templates/guide.html` |
| `.table-scroll` wrappers on the review surface | 3 | `grep -c "table-scroll" app/web/templates/reviewer/review_surface.html` |
| Browser test files reaching `/me/sessions` | 23 | `grep -rln "/me/sessions" tests/browser` |

## Status

**Closed 2026-11-25.** Built as laddered: plan #4201, then rungs 2–6 (#4202–#4208), with two
author-iteration rungs on the scale (#4204, #4205) after rung 3's phone check.

Intended versus done:
- **The viewport tag follows the participant chrome**, not a per-template block: `base.html`
  emits it when the body class includes `reviewer` (the `reviewer/` templates, the surface only
  outside the operator preview, and About, Guide and sign-in details for a non-operator). Its
  check rides the URL crawl, not a browser test.
- **Cards key on width alone**, so the operator's preview shows them in a narrow window too.
- **Scales (author's rulings, every width):** a slide's box is 88 px, ends at the widget's edge
  and drops under the line on a phone; a slide's line ends in a bar each side; stacked scales
  share one side, Band 2's track sized to match.
- **Addresses break anywhere** (`overflow-wrap: anywhere`), not only at `@` and `.`: a `<wbr>`
  filter would need registering in both template environments.
- **The bottom action row floats** (author, 2026-11-25), only once the top row has scrolled out
  of view; without script it stays in place.
- **Touch targets are two tiers**: controls 44 px; checkboxes, inline links, text buttons and
  role pills a 24 px target (WCAG 2.2), since 44 px links would break their lines.
- **The breakpoints were not consolidated**: the participant rules use only 640 px, and the rest
  are operator layouts.
- **The guard** visits every participant page with a table; the pre-open and
  invitation-mismatch notices are left to the URL crawl.

Reads: one cumulative `diff-reviewer` read at rung 6 (`3ff8b6b71..b82cd6675`) found no leak onto
operator pages and raised eight points, all taken, one a real defect (Band 2's stacked track
under-sized for scales widened to a shared side). Codex caught three more on the way, all fixed:
a scale's desktop minimum overflowing its card (#4203), the stacked visibility grid reaching the
Instruments page's grids (#4206), and an unbroken value widening a card (#4207). CI caught the
24 px inline targets a pixel short on its fonts (#4208).

## PR ladder

1. **Plan** (this file), with the todo pointers. Prose only.
2. **The viewport tag** on the nine participant templates; `base.html` gains the empty block. A browser test checks that each participant page has the tag and that an operator page does not. This is the scaffold: every participant page becomes legible as it stands.
3. **The reviewer surface's response table as cards** under 640 px, in both layouts and group mode, with `data-label` on each response cell. The browser test is at 390 × 844.
4. **The rest of the reviewer surface:** the visibility grid, chips, the action row and address wrapping.
5. **The dashboard, summary, results and collation as cards.**
6. **Touch targets and the breakpoint consolidation**, then **the guard:** a browser test per participant page at 390 × 844 (`is_mobile`), on a session of eight or more fields. It checks:
   - no sideways page scroll;
   - no response table needing a sideways scroll;
   - nothing tappable under 44 px.

   This is the **last build rung**, so it carries `diff-reviewer` on the cumulative diff.
7. **Close:** `spec-writer`, the todo stub deleted, the plan archived.

Each rung lands as a scaffold the author checks on a phone before the next.

## Definition of done

- At 390 × 844, no participant page scrolls sideways, and no reviewer-surface response table needs a sideways scroll, in either layout or in group mode.
- Under `pointer: coarse`, a participant page's button, box or list is at least 44 px tall, and a checkbox, text link, text button or role pill a 24 px target (`tests/browser/test_participant_pages_phone.py`).
- An operator page renders as before: no viewport tag.
- `## Doc impact` section present and current
- `python3 tools/close_check.py 20Q` exits 0; any warning adjudicated
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `guide/todo_master.md` entries deleted; plan moved to `guide/archive/` + index row

## Open questions

- ~~Should the action row be fixed to the bottom on a phone?~~ Yes, the bottom row floats (author, 2026-11-25; rung 6).

## Out of scope

- **Operator pages.** They stay desktop-first. The cheap emergency step (tab strips that scroll, the tag on lobby, Session Home and Invitations) stays in `guide/rrw_mobile_responsive.md` as a later option.
- **The invitation emails' HTML**, which phone mail clients render.
- **Real-device checks on Azure** (iOS bottom bar, Android keyboard resize). The author runs them after rung 4 lands in a deployment.

## Doc impact

- `spec/reviewer-surface.md` — the card layout under 640 px, `data-label`, the stacked visibility grid and action row (rungs 3–4).
- `spec/visual_style_rrw.md` — "Device classes": participant pages responsive with the viewport tag opt-in, the 640 px card breakpoint, touch targets of 44 px for controls and 24 px for inline targets, the floating action row (rungs 2, 6).
- `spec/participant_model.md` — results and collation as cards on a phone (rung 5).
- `guide/rrw_mobile_responsive.md` — marked as built by 20Q (at close).
- `guide/todo_master.md` — the phone stub deleted (at close).
