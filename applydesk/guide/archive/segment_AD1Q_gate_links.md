# Segment AD1Q — Apply Desk: the gate page's layout, and links between Process, a gate and its emails

**Opened:** 2026-11-20 · **Theme:** the author's walkthrough after AD1P: four layout fixes and two pairs of cross-page links, approved from mockups · **Related:** `applydesk/guide/todo_master.md` (ruling 65), `applydesk/spec/applications.md` (the Evaluations page; Process's gate cards; Emails; Panels)

## Opportunity

Walking the RA exercise on 2026-11-20, the author found these:
- **Gate page:** its Review Robin card runs as one long column. The actions sit at the bottom, under up to 30 evaluator rows.
- **Evaluations:** the Gates table's *Review Robin card →* buttons do not sit flush right.
- **Emails:** each card's *Insert field* dropdown and *Insert* button are out of line, top and bottom.
- **Panels:** the toolbar puts Filter and *Add new* on a row of their own, above the *Show columns* chips.
- **Process to a gate:** a gate card's only way to its gate page is a link inside the shut *Gate* section, and nothing leads back.
- **Process to Emails:** an email ticked on Process has no way to its template on Emails, and nothing leads back.

## Decision

As the mockups the author approved (2026-11-20; ruling 65):

1. **The gate page's Review Robin card:**
   - **Top, in two columns:** Session name and Session code on the left; Link, Last send, Invited and Reminded on the right.
   - **What is sent:** four tiles, 2 × 2, each a title, a line and *Download*.
   - **Progress:** a full-width panel. In it come the progress line, then the actions, then the mail preview, the evaluator table, and the *Simulated* note.
2. **Evaluations:** the Gates table's last column is right-aligned.
3. **Emails:** *Insert* takes the dropdown's height. Panels' *Add new* takes the same rule beside Filter.
4. **Panels:** *Show columns* sits on the left. Filter sits on the right, with *Add new* below it.
5. **Process ↔ a gate:**
   - A gate card's body opens with a line: its pairs, session and progress are on its page, then *Open Gate N →*.
   - That line replaces the link in the shut *Gate* section. Where the page does not exist yet, the line keeps saying why (ruling 61).
   - The gate page gains an intro after its banner: *Set on Process →*, to `…/process#gate-<key>`.
6. **Process ↔ Emails:**
   - Each email ticked on Process has *Template →* beside it, to `…/emails#em-<item>-<audience>`.
   - Each card on Emails says *Set on Process →* in its *when* line, to `#form` or `#outcome-<key>`.
   - Process opens and scrolls to the card a hash names.

**Alternative rejected:** a page-level menu of jump links on each page. That costs a click and a scan where a link beside the thing goes straight there.

## Semantics

- **Anchors** name the thing, not its place on the page: an email card is `em-<item>-<audience>`, and the Outline links the same ids. A renumbered outcome's key moves its template (`rekey_templates`), so a link keeps working.
- **A hash Process does not know** (a removed gate, an old link) opens the page as usual.
- **A ticked box unsaved** shows no *Template →* until the page reloads: the link is drawn from the saved plan, as Emails lists only saved ticks.
- **The actions' code is unchanged**: the panels stay inside the card `_rr_js.html` reads from.

## Judgment calls — decided

- *Open Gate N →* takes the timeline's wording rather than *Gate N page →*.
- The gate link goes to the page's top, not `#ev-rr`: the page now opens with the card.

## Blast radius (measured)

Taken 2026-11-20 at `e13c495b0`.
- Templates: `operator/gate_evaluations.html`, `_evaluations.html`, `_emails.html`, `_panels.html`, `_process_cards.html`, `_process.html` (the hash), and `base.html`.
- Tests reading the changed markup:
  - `grep -rln "rr-files" applydesk/tests --include=*.py` → `test_handoff.py`.
  - `grep -rln "pn-toolbar\|em-insert\|#em-" applydesk/tests --include=*.py` → `test_pages.py`, `test_emails_browser.py`.
  - `grep -rln "data-pc-rr" applydesk/tests --include=*.py` → `test_gate_setup.py`, `test_process_browser.py`.

## Status — closed 2026-11-20

**Intended vs done.** All six Decision items shipped as planned. The ladder ran: 1 (#4046), 2 (#4047), 3 (#4048), then this close. Decision 3 says Panels' *Add new* sits "beside Filter"; it went under Filter, as Decision 4 and the mockups have it.

**Decisions confirmed at build:**
- A field and its button take one fixed 40px height. CI's Chromium drew the *Insert* menu at 37px, so a minimum height on the button alone left them 3px apart (#4047).
- Process opens a card from its hash both on load and on a hash change. The handler waits for `load`, so the page's own layout does not undo the scroll.
- The email anchors come from one helper, `workflow.email_anchor`, which both Emails and Process's *Template →* links call.

**Reads.** One cumulative `diff-reviewer` read over `e13c495b0..05d73e1ac` found three items, all fixed in rung 3:
- A copied stage kept stale *Template →* links.
- The hash test never followed `#gate-<key>`.
- The gate's link line was not first in its body.

Codex found nothing on the plan (#4046) or on rung 2 (#4047).

**Close.** `spec-writer` added two lines to `applydesk/spec/applications.md`: a replica's gate line and *Template →*, and Process opening the card a hash names. It found the rest current.

## PR ladder

1. **This plan**, with ruling 65. Prose only.
2. **Layout** (Decision 1–4): templates and `base.html`, their tests. No links.
3. **Links** (Decision 5–6): the lines and links, Emails' anchors, and Process's hash; spec. The last build rung: the cumulative cold read runs here.
4. **Close.**

## Definition of done

- Each of Decision 1–6 visible on the RA exercise, at 1300px and 390px.
- Every new link opens its target, by a test following the `href`.
- `## Doc impact` section present and current
- `spec-writer` run against the doc-impact specs; flags adjudicated
- `## Status` compacted to intended vs done; answered open questions collapsed
- `applydesk/guide/todo_master.md` entries deleted; plan moved to `applydesk/guide/archive/` + index row
- (`tools/close_check.py` reads only RRW's top-level `guide/`; the close is checked by hand.)

## Open questions

None.

## Out of scope

- Links from Form, Dossiers or Panels to Process: not asked for.
- Invitation and reminder templates on Emails: AD7.

## Doc impact

- `applydesk/spec/applications.md` — the gate page's Review Robin card, Evaluations' table, Emails' cards, Panels' toolbar, Process's gate and email links (rungs 2–3).
- `applydesk/guide/todo_master.md` — ruling 65 (rung 1).
- `applydesk/guide/archive/README.md` — the plan's index row (at close).
